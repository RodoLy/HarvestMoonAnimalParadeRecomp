// The launcher program: a window that shows web/index.html (the launcher's page) with Microsoft
// Edge WebView2, which comes with Windows 10 and 11, and does what the page asks.
//
// What the page asks, and what this program does (see web/launcher.js for the messages):
//   hello        send the page what it shows: is the game prepared, the disc, the settings
//   prepare      run play.ps1 -NoStart, the same script play.cmd runs, and report its steps
//   play         prepare (quick when nothing changed), then start Game\AnimalParade.exe and close
//   cancel       stop the preparation
//   chooseDisc   ask for the disc image, remember it in UserData\disc.txt, and prepare
//   openLog      open the newest UserData\Logs\...\console.log
//   setOption    write one setting to UserData\Config.toml
//   setKey       bind a keyboard key to a button (UserData\keyboard_bindings.dat), to fast-forward or
//                to the free camera ([mods] in Config.toml)
//   setPad       bind a controller button to a button ([controller] in Config.toml), to fast-forward or
//                to the free camera
//   setKeyboard  turn the keyboard on or off as the first player's controller
//   resetControls  put every key and controller button back as they start
//   setMod       turn a game mod on or off ([mods] in Config.toml)
//   setModSetting  set a mod's percentage (its own line in [mods])
//   setUiLanguage, minimize, drag, exit
//
// What the launcher does on every system (the settings, the controls, what the page is told) is in
// launcher_core.cpp; this file is the Windows window around it.
//
// Built with the llvm-mingw compiler that comes with the package (see launcher/build.ps1). The
// WebView2 loader is OpenWebView2Loader (third_party), compiled in, so no WebView2Loader.dll is needed.
//
// El programa del launcher: una ventana que muestra la página web/index.html con WebView2 de
// Microsoft Edge (viene con Windows 10 y 11) y hace lo que la página le pide.

#ifndef UNICODE
#define UNICODE
#endif
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0A00  // Windows 10: per-monitor DPI
#endif
#include <windows.h>
#include <commdlg.h>
#include <shellapi.h>
#include <xinput.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "WebView2.h"
#include "WebView2Loader.h"
#include "launcher_core.h"

namespace fs = std::filesystem;

namespace {

using namespace LauncherCore;

// ---------------------------------------------------------------------------------------------
// Text: WebView2 talks JSON in UTF-16; the launcher's core, and its files, UTF-8.

std::string Utf8(const std::wstring& text) {
    if (text.empty()) return {};
    const int size = WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string out(size, '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), out.data(), size, nullptr, nullptr);
    return out;
}

std::wstring Wide(const std::string& text, UINT codePage = CP_UTF8) {
    if (text.empty()) return {};
    const int size = MultiByteToWideChar(codePage, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
    std::wstring out(size, L'\0');
    MultiByteToWideChar(codePage, 0, text.data(), static_cast<int>(text.size()), out.data(), size);
    return out;
}

std::wstring TrimWide(std::wstring s) {
    while (!s.empty() && iswspace(s.back())) s.pop_back();
    while (!s.empty() && iswspace(s.front())) s.erase(s.begin());
    return s;
}

// ---------------------------------------------------------------------------------------------
// The package folder: the one this program is in.

fs::path ProgramFolder() {
    wchar_t path[MAX_PATH * 4];
    GetModuleFileNameW(nullptr, path, static_cast<DWORD>(std::size(path)));
    return fs::path(path).parent_path();
}

// ---------------------------------------------------------------------------------------------
// The window and the page.

HWND g_window = nullptr;
ICoreWebView2Controller* g_controller = nullptr;
ICoreWebView2* g_webview = nullptr;

constexpr UINT WM_APP_POST = WM_APP + 1;  // lParam: a new std::wstring of JSON for the page
constexpr UINT WM_APP_DONE = WM_APP + 2;  // the preparation ended; wParam: its exit code

void PostToPage(const std::string& json) {
    // From any thread: the page is only touched on the window's thread.
    PostMessageW(g_window, WM_APP_POST, 0, reinterpret_cast<LPARAM>(new std::wstring(Wide(json))));
}

// A COM callback from a lambda, for the few WebView2 handlers this program needs.
template <typename Interface, typename... Args>
class Callback : public Interface {
public:
    explicit Callback(std::function<HRESULT(Args...)> function) : function_(std::move(function)) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** object) override {
        // WebView2 only asks a callback for IUnknown or for the handler interface it was given as;
        // the header has no IIDs to compare with under mingw, so every request gets this object.
        (void)riid;
        *object = this;
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++references_; }
    ULONG STDMETHODCALLTYPE Release() override {
        const ULONG left = --references_;
        if (left == 0) delete this;
        return left;
    }
    HRESULT STDMETHODCALLTYPE Invoke(Args... args) override { return function_(args...); }

private:
    std::function<HRESULT(Args...)> function_;
    std::atomic<ULONG> references_{1};
};

// ---------------------------------------------------------------------------------------------
// The preparation: play.ps1 -NoStart in a hidden PowerShell, read line by line.

struct Preparation {
    HANDLE job = nullptr;       // the PowerShell and everything it starts (the compiler), to cancel
    HANDLE process = nullptr;
    std::atomic<bool> running{false};
    std::atomic<bool> cancelled{false};
    bool startGameAfter = false;
    std::mutex errorLock;
    std::wstring error;         // what play.ps1 said when it stopped
};
Preparation g_prep;

void SendProgress(int stage, double fraction) { PostToPage(ProgressJson(stage, fraction)); }

void StartPreparation(bool startGameAfter) {
    if (g_prep.running) return;
    g_prep.running = true;
    g_prep.cancelled = false;
    g_prep.startGameAfter = startGameAfter;
    { std::lock_guard lock(g_prep.errorLock); g_prep.error.clear(); }
    // Preparing shows its steps from the start. Playing first checks, in a second or two, that the
    // game is current; the steps show only if there is real work (a new disc, a changed package).
    if (!startGameAfter) SendProgress(0, 0);

    std::wstring command = L"powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File \"" +
                           (Root() / "play.ps1").wstring() + L"\" -NoStart";

    SECURITY_ATTRIBUTES inherit{sizeof(inherit), nullptr, TRUE};
    HANDLE readEnd = nullptr, writeEnd = nullptr;
    CreatePipe(&readEnd, &writeEnd, &inherit, 0);
    SetHandleInformation(readEnd, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW startup{sizeof(startup)};
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdOutput = writeEnd;
    startup.hStdError = writeEnd;
    startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    PROCESS_INFORMATION process{};

    // A job, so that cancelling also stops the compiler the script started.
    g_prep.job = CreateJobObjectW(nullptr, nullptr);
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    SetInformationJobObject(g_prep.job, JobObjectExtendedLimitInformation, &limits, sizeof(limits));

    const BOOL started = CreateProcessW(nullptr, command.data(), nullptr, nullptr, TRUE,
                                        CREATE_NO_WINDOW | CREATE_SUSPENDED, nullptr, Root().c_str(), &startup, &process);
    CloseHandle(writeEnd);
    if (!started) {
        CloseHandle(readEnd);
        { std::lock_guard lock(g_prep.errorLock); g_prep.error = L"PowerShell could not be started."; }
        PostMessageW(g_window, WM_APP_DONE, 1, 0);
        return;
    }
    AssignProcessToJobObject(g_prep.job, process.hProcess);
    ResumeThread(process.hThread);
    CloseHandle(process.hThread);
    g_prep.process = process.hProcess;

    std::thread([readEnd, processHandle = process.hProcess, showSteps = !startGameAfter]() mutable {
        int stage = 0;
        double fraction = 0;
        std::string pending;
        std::wstring lastLine;
        char buffer[4096];
        DWORD read = 0;
        // Windows PowerShell writes to a pipe in the console's code page.
        while (ReadFile(readEnd, buffer, sizeof(buffer), &read, nullptr) && read) {
            pending.append(buffer, read);
            size_t end;
            while ((end = pending.find_first_of("\r\n")) != std::string::npos) {
                const std::wstring line = TrimWide(Wide(pending.substr(0, end), CP_OEMCP));
                pending.erase(0, end + 1);
                if (line.empty()) continue;
                const int oldStage = stage;
                const double oldFraction = fraction;
                ReadProgressLine(Utf8(line), stage, fraction);
                // Real work: extracting, translating (not "is current"), configuring the build (a
                // couple of minutes after an update, before the compiler prints anything), or
                // compiling something.
                if (!showSteps && ShowsRealWork(Utf8(line))) {
                    showSteps = true;
                    SendProgress(stage, fraction);
                }
                if (showSteps && (stage != oldStage || fraction - oldFraction > 0.004)) SendProgress(stage, fraction);
                // An error from the script: "play.ps1 : <message>" or the message on its own line.
                if (line.find(L"play.ps1 :") == 0) {
                    std::lock_guard lock(g_prep.errorLock);
                    g_prep.error = TrimWide(line.substr(10));
                } else if (line.find(L"At ") != 0 && line.find(L"+ ") != 0 && line.find(L"    + ") != 0) {
                    lastLine = line;
                }
            }
        }
        CloseHandle(readEnd);
        WaitForSingleObject(processHandle, INFINITE);
        DWORD exitCode = 1;
        GetExitCodeProcess(processHandle, &exitCode);
        {
            std::lock_guard lock(g_prep.errorLock);
            if (g_prep.error.empty()) g_prep.error = lastLine;
        }
        PostMessageW(g_window, WM_APP_DONE, exitCode, 0);
    }).detach();
}

void CancelPreparation() {
    if (!g_prep.running) return;
    g_prep.cancelled = true;
    TerminateJobObject(g_prep.job, 1);
}

// Started by RecompLauncher (it sets RECOMPLAUNCHER=1 for what it starts): RecompLauncher takes
// the end of this program for the end of the game, and backs up the saves then. So the launcher
// hides and stays until the game closes, instead of closing as soon as the game starts.
bool StartedByRecompLauncher() {
    wchar_t value[8] = {};
    return GetEnvironmentVariableW(L"RECOMPLAUNCHER", value, 8) > 0 && std::wstring(value) == L"1";
}

void StartGame() {
    STARTUPINFOW startup{sizeof(startup)};
    PROCESS_INFORMATION process{};
    std::wstring command = L"\"" + GameExecutable().wstring() + L"\"";
    if (CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE, 0, nullptr,
                       GameExecutable().parent_path().c_str(), &startup, &process)) {
        CloseHandle(process.hThread);
        if (StartedByRecompLauncher()) {
            ShowWindow(g_window, SW_HIDE);
            std::thread([game = process.hProcess, window = g_window] {
                WaitForSingleObject(game, INFINITE);
                CloseHandle(game);
                PostMessageW(window, WM_CLOSE, 0, 0);
            }).detach();
            return;
        }
        CloseHandle(process.hProcess);
        DestroyWindow(g_window);
    }
}

// ---------------------------------------------------------------------------------------------
// What the page shows about the game.

// Controllers Windows sees as game pads or joysticks that are not XInput ones: a PlayStation or
// Switch controller, for example (the game reads them all through SDL). XInput controllers show up
// here too, with "IG_" in their device name; they are left out, since XInput counts them.
int OtherControllers() {
    UINT devices = 0;
    if (GetRawInputDeviceList(nullptr, &devices, sizeof(RAWINPUTDEVICELIST)) != 0 || devices == 0) return 0;
    std::vector<RAWINPUTDEVICELIST> list(devices);
    devices = GetRawInputDeviceList(list.data(), &devices, sizeof(RAWINPUTDEVICELIST));
    if (devices == static_cast<UINT>(-1)) return 0;
    int count = 0;
    for (UINT i = 0; i < devices; ++i) {
        if (list[i].dwType != RIM_TYPEHID) continue;
        RID_DEVICE_INFO info{};
        info.cbSize = sizeof(info);
        UINT size = sizeof(info);
        if (GetRawInputDeviceInfoW(list[i].hDevice, RIDI_DEVICEINFO, &info, &size) == static_cast<UINT>(-1)) continue;
        // Generic desktop controls (usage page 1): a joystick (4) or a game pad (5).
        if (info.hid.usUsagePage != 1 || (info.hid.usUsage != 4 && info.hid.usUsage != 5)) continue;
        UINT length = 0;
        GetRawInputDeviceInfoW(list[i].hDevice, RIDI_DEVICENAME, nullptr, &length);
        std::wstring name(length, L'\0');
        if (length > 0 && GetRawInputDeviceInfoW(list[i].hDevice, RIDI_DEVICENAME, name.data(), &length) != static_cast<UINT>(-1) &&
            name.find(L"IG_") != std::wstring::npos) {
            continue;
        }
        ++count;
    }
    return count;
}

int ConnectedControllers() {
    // XInput controllers (Xbox and the many that work like one), and the others Windows sees as game
    // pads (OtherControllers).
    static auto getState = [] {
        HMODULE xinput = LoadLibraryW(L"xinput1_4.dll");
        if (!xinput) xinput = LoadLibraryW(L"xinput9_1_0.dll");
        return xinput ? reinterpret_cast<DWORD(WINAPI*)(DWORD, XINPUT_STATE*)>(GetProcAddress(xinput, "XInputGetState")) : nullptr;
    }();
    int count = OtherControllers();
    for (DWORD i = 0; getState && i < XUSER_MAX_COUNT; ++i) {
        XINPUT_STATE state{};
        if (getState(i, &state) == ERROR_SUCCESS) ++count;
    }
    return count;
}

const char* CurrentStatus() {
    if (g_prep.running) return "preparing";
    return HasDisc() && fs::exists(GameExecutable()) ? "ready" : "notPrepared";
}

std::string CurrentState() { return StateJson(CurrentStatus(), ConnectedControllers()); }

bool ChooseDisc() {
    wchar_t file[MAX_PATH * 4] = L"";
    OPENFILENAMEW dialog{sizeof(dialog)};
    dialog.hwndOwner = g_window;
    dialog.lpstrFilter = L"Wii disc image (*.rvz;*.iso;*.wbfs;*.wia;*.ciso)\0*.rvz;*.iso;*.wbfs;*.wia;*.ciso\0All files\0*.*\0";
    dialog.lpstrFile = file;
    dialog.nMaxFile = static_cast<DWORD>(std::size(file));
    dialog.lpstrTitle = L"Harvest Moon: Animal Parade (USA) - RBIEE9";
    dialog.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    if (!GetOpenFileNameW(&dialog)) return false;
    // play.ps1 reads the disc from here.
    WriteText(DiscFile(), Utf8(file) + "\r\n");
    return true;
}

void OpenNewestLog() {
    const fs::path newest = NewestLog();
    if (newest.empty()) { PostToPage(ToastJson("noLog")); return; }
    ShellExecuteW(g_window, L"open", newest.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
}

void OnPageMessage(const std::wstring& json) {
    const auto message = ParseFlatJson(Utf8(json));
    const auto field = [&](const char* key) { const auto found = message.find(key); return found == message.end() ? std::string() : found->second; };
    const std::string cmd = field("cmd");
    bool sendState = false;
    if (cmd == "hello") {
        PostToPage(CurrentState());
    } else if (cmd == "prepare" || cmd == "play") {
        if (!HasDisc() && !ChooseDisc()) return;
        StartPreparation(cmd == "play");
    } else if (cmd == "chooseDisc") {
        if (!g_prep.running && ChooseDisc()) StartPreparation(false);
    } else if (cmd == "cancel") {
        CancelPreparation();
    } else if (cmd == "openLog") {
        OpenNewestLog();
    } else if (HandleSettingsMessage(message, sendState)) {
        if (sendState) PostToPage(CurrentState());
    } else if (cmd == "minimize") {
        ShowWindow(g_window, SW_MINIMIZE);
    } else if (cmd == "drag") {
        // The page's title bar moves the window, like a normal one.
        ReleaseCapture();
        SendMessageW(g_window, WM_NCLBUTTONDOWN, HTCAPTION, 0);
    } else if (cmd == "exit") {
        CancelPreparation();
        DestroyWindow(g_window);
    }
}

void ResizePage() {
    if (!g_controller) return;
    RECT bounds;
    GetClientRect(g_window, &bounds);
    g_controller->put_Bounds(bounds);
}

void CreatePage() {
    const std::wstring dataFolder = (UserData() / "Cache" / "Launcher").wstring();
    const HRESULT result = CreateCoreWebView2EnvironmentWithOptions(nullptr, dataFolder.c_str(), nullptr,
        new Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler, HRESULT, ICoreWebView2Environment*>(
            [](HRESULT error, ICoreWebView2Environment* environment) -> HRESULT {
                if (FAILED(error) || !environment) return error;
                return environment->CreateCoreWebView2Controller(g_window,
                    new Callback<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler, HRESULT, ICoreWebView2Controller*>(
                        [](HRESULT error, ICoreWebView2Controller* controller) -> HRESULT {
                            if (FAILED(error) || !controller) return error;
                            g_controller = controller;
                            g_controller->AddRef();
                            g_controller->get_CoreWebView2(&g_webview);

                            ICoreWebView2Settings* settings = nullptr;
                            if (SUCCEEDED(g_webview->get_Settings(&settings)) && settings) {
                                settings->put_AreDefaultContextMenusEnabled(FALSE);
                                settings->put_IsZoomControlEnabled(FALSE);
                                settings->put_IsStatusBarEnabled(FALSE);
                                settings->put_AreDevToolsEnabled(FALSE);
                                settings->Release();
                            }

                            EventRegistrationToken token;
                            g_webview->add_WebMessageReceived(
                                new Callback<ICoreWebView2WebMessageReceivedEventHandler, ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs*>(
                                    [](ICoreWebView2*, ICoreWebView2WebMessageReceivedEventArgs* args) -> HRESULT {
                                        LPWSTR json = nullptr;
                                        if (SUCCEEDED(args->get_WebMessageAsJson(&json)) && json) {
                                            OnPageMessage(json);
                                            CoTaskMemFree(json);
                                        }
                                        return S_OK;
                                    }),
                                &token);

                            ResizePage();
                            const std::wstring page = L"file:///" + (Root() / "Launcher" / "index.html").generic_wstring();
                            g_webview->Navigate(page.c_str());
                            return S_OK;
                        }));
            }));
    if (FAILED(result)) {
        // No WebView2 runtime: it comes with Windows 11 and current Windows 10; older ones need it.
        if (MessageBoxW(g_window,
                        L"The launcher needs Microsoft Edge WebView2, which is missing.\n"
                        L"El launcher necesita Microsoft Edge WebView2, que no está instalado.\n\n"
                        L"Open the download page? / ¿Abrir la página de descarga?",
                        L"Harvest Moon: Animal Parade", MB_YESNO | MB_ICONWARNING) == IDYES) {
            ShellExecuteW(nullptr, L"open", L"https://developer.microsoft.com/microsoft-edge/webview2/", nullptr, nullptr, SW_SHOWNORMAL);
        }
        DestroyWindow(g_window);
    }
}

LRESULT CALLBACK WindowProc(HWND window, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_SIZE:
        ResizePage();
        return 0;
    case WM_TIMER:
        // A controller plugged in or out shows on the Controls tab.
        if (g_webview && !g_prep.running) {
            static int last = -1;
            const int now = ConnectedControllers();
            if (now != last) { last = now; PostToPage(CurrentState()); }
        }
        return 0;
    case WM_APP_POST: {
        std::unique_ptr<std::wstring> json(reinterpret_cast<std::wstring*>(lParam));
        if (g_webview) g_webview->PostWebMessageAsJson(json->c_str());
        return 0;
    }
    case WM_APP_DONE: {
        g_prep.running = false;
        CloseHandle(g_prep.process);
        CloseHandle(g_prep.job);
        g_prep.process = g_prep.job = nullptr;
        const bool ok = wParam == 0 && !g_prep.cancelled;
        std::wstring error;
        { std::lock_guard lock(g_prep.errorLock); error = g_prep.error; }
        PostToPage(CurrentState());
        PostToPage(FinishedJson(ok, g_prep.cancelled, Utf8(error)));
        if (ok && g_prep.startGameAfter) StartGame();
        return 0;
    }
    case WM_DESTROY:
        CancelPreparation();
        if (g_controller) g_controller->Close();
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(window, message, wParam, lParam);
}

} // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int show) {
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2);
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    SetRoot(ProgramFolder());
    WriteFirstConfig();
    WriteFirstKeyboard();

    WNDCLASSW windowClass{};
    windowClass.lpfnWndProc = WindowProc;
    windowClass.hInstance = instance;
    windowClass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    windowClass.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(1));
    windowClass.hbrBackground = CreateSolidBrush(RGB(0x3a, 0x24, 0x10));
    windowClass.lpszClassName = L"HarvestMoonAnimalParadeLauncher";
    RegisterClassW(&windowClass);

    // The page is drawn at 1280 x 752; the window is that size times the screen's scale, made
    // smaller to fit on small screens, and centred.
    RECT work;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    const double dpiScale = GetDpiForSystem() / 96.0;
    const double fit = std::min({1.0, (work.right - work.left) * 0.92 / (1280 * dpiScale), (work.bottom - work.top) * 0.92 / (752 * dpiScale)});
    const int width = static_cast<int>(1280 * dpiScale * fit), height = static_cast<int>(752 * dpiScale * fit);
    g_window = CreateWindowExW(0, windowClass.lpszClassName, L"Harvest Moon: Animal Parade",
                               WS_POPUP | WS_MINIMIZEBOX | WS_SYSMENU,
                               work.left + (work.right - work.left - width) / 2, work.top + (work.bottom - work.top - height) / 2,
                               width, height, nullptr, nullptr, instance, nullptr);
    ShowWindow(g_window, show);
    CreatePage();
    SetTimer(g_window, 1, 2000, nullptr);

    MSG message;
    while (GetMessageW(&message, nullptr, 0, 0)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }
    CoUninitialize();
    return 0;
}
