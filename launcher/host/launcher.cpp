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
//   setUiLanguage, minimize, drag, exit
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
#include <atomic>
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

namespace fs = std::filesystem;

namespace {

// ---------------------------------------------------------------------------------------------
// Text: the page talks JSON in UTF-16; files are UTF-8.

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

std::wstring JsonString(const std::wstring& text) {
    std::wstring out = L"\"";
    for (wchar_t c : text) {
        if (c == L'"' || c == L'\\') { out += L'\\'; out += c; }
        else if (c == L'\n') out += L"\\n";
        else if (c == L'\r') {}
        else if (c < 0x20) out += L' ';
        else out += c;
    }
    return out + L"\"";
}

// The page only sends flat objects ({"cmd":"setOption","key":"picture","value":true}), so this
// reads one: each key with its value as text (strings without their quotes).
std::map<std::wstring, std::wstring> ParseFlatJson(const std::wstring& json) {
    std::map<std::wstring, std::wstring> fields;
    size_t i = 0;
    auto skipSpace = [&] { while (i < json.size() && iswspace(json[i])) ++i; };
    auto readString = [&] {
        std::wstring s;
        ++i;  // the opening quote
        while (i < json.size() && json[i] != L'"') {
            if (json[i] == L'\\' && i + 1 < json.size()) {
                ++i;
                s += json[i] == L'n' ? L'\n' : json[i];
            } else {
                s += json[i];
            }
            ++i;
        }
        ++i;  // the closing quote
        return s;
    };
    skipSpace();
    if (i < json.size() && json[i] == L'{') ++i;
    while (i < json.size()) {
        skipSpace();
        if (i >= json.size() || json[i] != L'"') break;
        const std::wstring key = readString();
        skipSpace();
        if (i < json.size() && json[i] == L':') ++i;
        skipSpace();
        std::wstring value;
        if (i < json.size() && json[i] == L'"') {
            value = readString();
        } else {
            while (i < json.size() && json[i] != L',' && json[i] != L'}') value += json[i++];
            while (!value.empty() && iswspace(value.back())) value.pop_back();
        }
        fields[key] = value;
        skipSpace();
        if (i < json.size() && json[i] == L',') ++i;
    }
    return fields;
}

// ---------------------------------------------------------------------------------------------
// Where things are: everything is next to this program, in the package folder.

fs::path Root() {
    wchar_t path[MAX_PATH * 4];
    GetModuleFileNameW(nullptr, path, static_cast<DWORD>(std::size(path)));
    return fs::path(path).parent_path();
}

fs::path UserData() { return Root() / L"UserData"; }
fs::path ConfigPath() { return UserData() / L"Config.toml"; }
fs::path DiscFile() { return UserData() / L"disc.txt"; }
fs::path GameExe() { return Root() / L"Game" / L"AnimalParade.exe"; }

std::string ReadText(const fs::path& path) {
    std::ifstream file(path, std::ios::binary);
    std::stringstream text;
    text << file.rdbuf();
    std::string s = text.str();
    if (s.rfind("\xEF\xBB\xBF", 0) == 0) s.erase(0, 3);  // a UTF-8 mark, as PowerShell writes it
    return s;
}

void WriteText(const fs::path& path, const std::string& text) {
    std::error_code ignored;
    fs::create_directories(path.parent_path(), ignored);
    std::ofstream(path, std::ios::binary | std::ios::trunc) << text;
}

std::wstring Trim(std::wstring s) {
    while (!s.empty() && iswspace(s.back())) s.pop_back();
    while (!s.empty() && iswspace(s.front())) s.erase(s.begin());
    return s;
}

// ---------------------------------------------------------------------------------------------
// UserData\Config.toml, the game's settings. Only the few lines the launcher changes are touched:
// "key = value" under "[section]"; everything else in the file stays as it is.

struct ConfigFile {
    std::vector<std::string> lines;

    static ConfigFile Load() {
        ConfigFile config;
        std::istringstream text(ReadText(ConfigPath()));
        for (std::string line; std::getline(text, line);) {
            if (!line.empty() && line.back() == '\r') line.pop_back();
            config.lines.push_back(line);
        }
        return config;
    }

    void Save() const {
        std::string text;
        for (const auto& line : lines) text += line + "\r\n";
        WriteText(ConfigPath(), text);
    }

    static std::string Strip(const std::string& s) {
        const auto begin = s.find_first_not_of(" \t");
        const auto end = s.find_last_not_of(" \t");
        return begin == std::string::npos ? std::string() : s.substr(begin, end - begin + 1);
    }

    // The line index of key in section, or -1.
    int Find(const std::string& section, const std::string& key) const {
        std::string current;
        for (size_t i = 0; i < lines.size(); ++i) {
            const std::string line = Strip(lines[i]);
            if (line.size() > 1 && line.front() == '[') { current = line.substr(1, line.find(']') - 1); continue; }
            if (current != section || line.empty() || line[0] == '#') continue;
            const auto equals = line.find('=');
            if (equals != std::string::npos && Strip(line.substr(0, equals)) == key) return static_cast<int>(i);
        }
        return -1;
    }

    std::optional<std::string> Get(const std::string& section, const std::string& key) const {
        const int i = Find(section, key);
        if (i < 0) return std::nullopt;
        std::string value = Strip(lines[i].substr(lines[i].find('=') + 1));
        const auto comment = value.find(" #");
        if (comment != std::string::npos) value = Strip(value.substr(0, comment));
        if (value.size() >= 2 && value.front() == '"' && value.back() == '"') value = value.substr(1, value.size() - 2);
        return value;
    }

    void Set(const std::string& section, const std::string& key, const std::string& value) {
        const std::string line = key + " = " + value;
        const int i = Find(section, key);
        if (i >= 0) { lines[i] = line; return; }
        // A new key goes at the end of its section, or in a new section at the end of the file.
        for (size_t s = 0; s < lines.size(); ++s) {
            if (Strip(lines[s]) != "[" + section + "]") continue;
            size_t end = s + 1;
            while (end < lines.size() && Strip(lines[end]).rfind('[', 0) != 0) ++end;
            while (end > s + 1 && Strip(lines[end - 1]).empty()) --end;
            lines.insert(lines.begin() + end, line);
            return;
        }
        if (!lines.empty() && !Strip(lines.back()).empty()) lines.push_back("");
        lines.push_back("[" + section + "]");
        lines.push_back(line);
    }
};

// Each option on the page and where it lives in Config.toml. "fallback" is what the game does
// when the line is missing: the original game's behaviour.
struct Option {
    const char* page;
    const char* section;
    const char* key;
    enum Kind { Bool, Number, Text } kind;
    const char* fallback;
};

const Option kOptions[] = {
    {"picture", "video", "widescreen", Option::Bool, "false"},
    {"interpolation", "video", "frame_interpolation_fps", Option::Number, "0"},
    {"resolution", "video", "resolution_multiplier", Option::Number, "1"},
    {"fullscreen", "video", "display_mode", Option::Text, "windowed"},
    {"api", "video", "graphics_api", Option::Text, "auto"},
    {"language", "console", "language", Option::Text, "english"},
    {"fastForward", "speed", "hold_tab_to_fast_forward", Option::Bool, "false"},
    {"showFps", "video", "show_fps", Option::Bool, "false"},
};

// The first time, before the game ever ran, the settings start as the original game: 4:3, 30 FPS,
// no FPS counter. The game fills in the rest of the file itself.
void WriteFirstConfig() {
    if (fs::exists(ConfigPath())) return;
    ConfigFile config;
    for (const auto& option : kOptions) {
        const std::string value = option.kind == Option::Text ? std::string("\"") + option.fallback + "\"" : option.fallback;
        config.Set(option.section, option.key, value);
    }
    config.Set("launcher", "language", "\"en\"");
    config.Save();
}

// The page's value (JSON: true, 60, 1.5, "vulkan") as the line in Config.toml.
std::string ConfigValue(const Option& option, const std::wstring& pageValue) {
    const std::string value = Utf8(pageValue);
    if (std::string(option.page) == "fullscreen") return value == "true" ? "\"borderless\"" : "\"windowed\"";
    if (option.kind == Option::Text) return "\"" + value + "\"";
    if (std::string(option.key) == "resolution_multiplier" && value.find('.') == std::string::npos) return value + ".0";
    return value;
}

// The Config.toml line as the page's value.
std::wstring PageValue(const Option& option, const ConfigFile& config) {
    const std::string value = config.Get(option.section, option.key).value_or(option.fallback);
    if (std::string(option.page) == "fullscreen") return value == "windowed" ? L"false" : L"true";
    if (option.kind == Option::Text) return JsonString(Wide(value));
    if (option.kind == Option::Number) {
        // 1.0 and 1 are the same choice on the page.
        try {
            const double number = std::stod(value);
            std::wostringstream out;
            out << number;
            return out.str();
        } catch (...) {
            return Wide(option.fallback);
        }
    }
    return Wide(value);
}

// ---------------------------------------------------------------------------------------------
// The window and the page.

HWND g_window = nullptr;
ICoreWebView2Controller* g_controller = nullptr;
ICoreWebView2* g_webview = nullptr;

constexpr UINT WM_APP_POST = WM_APP + 1;  // lParam: a new std::wstring of JSON for the page
constexpr UINT WM_APP_DONE = WM_APP + 2;  // the preparation ended; wParam: its exit code

void PostToPage(const std::wstring& json) {
    // From any thread: the page is only touched on the window's thread.
    PostMessageW(g_window, WM_APP_POST, 0, reinterpret_cast<LPARAM>(new std::wstring(json)));
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

// Turns a line that play.ps1 (or the compiler under it) printed into the page's progress.
void ReadProgressLine(const std::wstring& line, int& stage, double& fraction) {
    auto has = [&](const wchar_t* text) { return line.find(text) != std::wstring::npos; };
    if (has(L"== Extracting")) { stage = 0; fraction = 0; }
    else if (has(L"== Translating") || has(L"== The translation is current")) { stage = 1; fraction = has(L"current") ? 1 : 0; }
    else if (has(L"== Configuring")) { stage = 2; fraction = 0; }
    else if (has(L"== Compiling")) { stage = 2; fraction = 0.02; }
    else if (has(L"== Copying")) { stage = 2; fraction = 0.98; }
    else if (stage == 2 && line.size() > 3 && line[0] == L'[') {
        // Ninja: "[123/4567] Building CXX object ...".
        unsigned done = 0, total = 0;
        if (swscanf(line.c_str(), L"[%u/%u]", &done, &total) == 2 && total) fraction = std::min(0.97, 0.02 + 0.95 * done / total);
    } else if (stage == 0) {
        // nodtool shows how far the extraction is as a percentage.
        const auto percent = line.rfind(L'%');
        if (percent != std::wstring::npos && percent > 0) {
            size_t begin = percent;
            while (begin > 0 && (iswdigit(line[begin - 1]) || line[begin - 1] == L'.')) --begin;
            if (begin < percent) fraction = std::min(1.0, _wtof(line.substr(begin, percent - begin).c_str()) / 100.0);
        }
    }
}

void SendProgress(int stage, double fraction) {
    std::wostringstream json;
    json << L"{\"type\":\"progress\",\"stage\":" << stage << L",\"fraction\":" << fraction << L"}";
    PostToPage(json.str());
}

void StartPreparation(bool startGameAfter) {
    if (g_prep.running) return;
    g_prep.running = true;
    g_prep.cancelled = false;
    g_prep.startGameAfter = startGameAfter;
    { std::lock_guard lock(g_prep.errorLock); g_prep.error.clear(); }
    SendProgress(0, 0);

    std::wstring command = L"powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File \"" +
                           (Root() / L"play.ps1").wstring() + L"\" -NoStart";

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

    std::thread([readEnd, processHandle = process.hProcess] {
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
                const std::wstring line = Trim(Wide(pending.substr(0, end), CP_OEMCP));
                pending.erase(0, end + 1);
                if (line.empty()) continue;
                const int oldStage = stage;
                const double oldFraction = fraction;
                ReadProgressLine(line, stage, fraction);
                if (stage != oldStage || fraction - oldFraction > 0.004) SendProgress(stage, fraction);
                // An error from the script: "play.ps1 : <message>" or the message on its own line.
                if (line.find(L"play.ps1 :") == 0) {
                    std::lock_guard lock(g_prep.errorLock);
                    g_prep.error = Trim(line.substr(10));
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

void StartGame() {
    STARTUPINFOW startup{sizeof(startup)};
    PROCESS_INFORMATION process{};
    std::wstring command = L"\"" + GameExe().wstring() + L"\"";
    if (CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE, 0, nullptr,
                       GameExe().parent_path().c_str(), &startup, &process)) {
        CloseHandle(process.hThread);
        CloseHandle(process.hProcess);
        DestroyWindow(g_window);
    }
}

// ---------------------------------------------------------------------------------------------
// What the page shows about the game.

bool HasDisc() {
    if (fs::exists(DiscFile()) && !Trim(Wide(ReadText(DiscFile()))).empty()) return true;
    return fs::exists(Root() / L"Disc" / L"sys" / L"main.dol") || fs::exists(Root() / L"Disc" / L"DATA" / L"sys" / L"main.dol");
}

int ConnectedControllers() {
    // XInput controllers (Xbox and the many that work like one). Others still work in the game;
    // they just are not counted here.
    static auto getState = [] {
        HMODULE xinput = LoadLibraryW(L"xinput1_4.dll");
        if (!xinput) xinput = LoadLibraryW(L"xinput9_1_0.dll");
        return xinput ? reinterpret_cast<DWORD(WINAPI*)(DWORD, XINPUT_STATE*)>(GetProcAddress(xinput, "XInputGetState")) : nullptr;
    }();
    if (!getState) return 0;
    int count = 0;
    for (DWORD i = 0; i < XUSER_MAX_COUNT; ++i) {
        XINPUT_STATE state{};
        if (getState(i, &state) == ERROR_SUCCESS) ++count;
    }
    return count;
}

std::wstring StateJson(const wchar_t* status) {
    const ConfigFile config = ConfigFile::Load();
    std::wostringstream json;
    json << L"{\"type\":\"state\",\"status\":\"" << status << L"\",\"hasDisc\":" << (HasDisc() ? L"true" : L"false")
         << L",\"discId\":\"" << (HasDisc() ? L"RBIEE9" : L"—") << L"\",\"controllers\":" << ConnectedControllers();
    const std::wstring version = Trim(Wide(ReadText(Root() / L"version.txt")));
    json << L",\"version\":" << JsonString(version.empty() ? L"dev" : version);
    json << L",\"uiLanguage\":" << JsonString(Wide(config.Get("launcher", "language").value_or("en")));
    json << L",\"options\":{";
    bool first = true;
    for (const auto& option : kOptions) {
        json << (first ? L"" : L",") << L"\"" << Wide(option.page) << L"\":" << PageValue(option, config);
        first = false;
    }
    json << L"}}";
    return json.str();
}

const wchar_t* CurrentStatus() {
    if (g_prep.running) return L"preparing";
    return HasDisc() && fs::exists(GameExe()) ? L"ready" : L"notPrepared";
}

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
    fs::path newest;
    fs::file_time_type newestTime{};
    std::error_code error;
    for (const auto& entry : fs::directory_iterator(UserData() / L"Logs", error)) {
        const fs::path log = entry.path() / L"console.log";
        if (!fs::exists(log)) continue;
        const auto time = fs::last_write_time(log, error);
        if (newest.empty() || time > newestTime) { newest = log; newestTime = time; }
    }
    if (newest.empty()) { PostToPage(L"{\"type\":\"toast\",\"key\":\"noLog\"}"); return; }
    ShellExecuteW(g_window, L"open", newest.c_str(), nullptr, nullptr, SW_SHOWNORMAL);
}

void OnPageMessage(const std::wstring& json) {
    auto message = ParseFlatJson(json);
    const std::wstring& cmd = message[L"cmd"];
    if (cmd == L"hello") {
        PostToPage(StateJson(CurrentStatus()));
    } else if (cmd == L"prepare" || cmd == L"play") {
        if (!HasDisc() && !ChooseDisc()) return;
        StartPreparation(cmd == L"play");
    } else if (cmd == L"chooseDisc") {
        if (!g_prep.running && ChooseDisc()) StartPreparation(false);
    } else if (cmd == L"cancel") {
        CancelPreparation();
    } else if (cmd == L"openLog") {
        OpenNewestLog();
    } else if (cmd == L"setOption") {
        for (const auto& option : kOptions) {
            if (Wide(option.page) != message[L"key"]) continue;
            ConfigFile config = ConfigFile::Load();
            config.Set(option.section, option.key, ConfigValue(option, message[L"value"]));
            config.Save();
        }
    } else if (cmd == L"setUiLanguage") {
        ConfigFile config = ConfigFile::Load();
        config.Set("launcher", "language", message[L"value"] == L"es" ? "\"es\"" : "\"en\"");
        config.Save();
    } else if (cmd == L"minimize") {
        ShowWindow(g_window, SW_MINIMIZE);
    } else if (cmd == L"drag") {
        // The page's title bar moves the window, like a normal one.
        ReleaseCapture();
        SendMessageW(g_window, WM_NCLBUTTONDOWN, HTCAPTION, 0);
    } else if (cmd == L"exit") {
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
    const std::wstring dataFolder = (UserData() / L"Cache" / L"Launcher").wstring();
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
                            const std::wstring page = L"file:///" + (Root() / L"Launcher" / L"index.html").generic_wstring();
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
            if (now != last) { last = now; PostToPage(StateJson(CurrentStatus())); }
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
        PostToPage(StateJson(CurrentStatus()));
        PostToPage(std::wstring(L"{\"type\":\"finished\",\"ok\":") + (ok ? L"true" : L"false") + L",\"cancelled\":" +
                   (g_prep.cancelled ? L"true" : L"false") + L",\"error\":" + JsonString(ok ? L"" : error) + L"}");
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
    WriteFirstConfig();

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
