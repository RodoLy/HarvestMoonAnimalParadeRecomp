// The launcher program on Linux and macOS: it shows the same page as on Windows (web/index.html),
// in the computer's own browser, and does what the page asks.
//
// The page is served at http://127.0.0.1:<port>/<key>/, where the key is a random number made at
// start, so only this program's page can talk to it. The page sends its messages to "message"
// (POST, JSON), and the program sends its own to "events" (server-sent events) as they happen.
// What the messages do is the same as on Windows (see launcher.cpp and launcher_core.cpp):
//   prepare      run play.sh --no-start and report its steps
//   play         prepare (quick when nothing changed), then start Game/AnimalParade
//   chooseDisc   ask for the disc image (zenity or kdialog on Linux, the Finder on macOS)
//   openLog      open the newest UserData/Logs/.../console.log
//   update       download a newer version with update.sh, then stop so that it can be put in place
//                (the script starts the launcher again, in a new tab)
//   exit         stop; the program also stops a minute after the page was closed
//
// Built by launcher/build.sh with the computer's C++ compiler.
//
// El programa del launcher en Linux y macOS: muestra la misma página que en Windows, en el navegador
// de la computadora, y hace lo que la página le pide. La página se sirve en http://127.0.0.1 con una
// clave al azar, para que solo esa página pueda hablarle.

#include "launcher_core.h"

#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <iostream>
#include <mutex>
#include <random>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#ifndef MSG_NOSIGNAL
#define MSG_NOSIGNAL 0  // macOS: SIGPIPE is ignored instead (see main)
#endif

namespace {

using namespace LauncherCore;

// ---------------------------------------------------------------------------------------------
// The package folder: the one this program is in.

fs::path ProgramFolder() {
#ifdef __APPLE__
    char path[4096];
    uint32_t size = sizeof(path);
    if (_NSGetExecutablePath(path, &size) == 0) return fs::canonical(path).parent_path();
    return fs::current_path();
#else
    std::error_code error;
    const fs::path self = fs::read_symlink("/proc/self/exe", error);
    return error ? fs::current_path() : self.parent_path();
#endif
}

// A command's output (its first line), or empty when it could not run.
std::string RunAndRead(const std::string& command) {
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) return {};
    std::string out;
    char buffer[4096];
    while (fgets(buffer, sizeof(buffer), pipe)) out += buffer;
    pclose(pipe);
    const auto newline = out.find('\n');
    return Trim(newline == std::string::npos ? out : out.substr(0, newline));
}

bool HasCommand(const char* name) {
    return std::system((std::string("command -v ") + name + " >/dev/null 2>&1").c_str()) == 0;
}

// A path or an address in single quotes, for the shell.
std::string Quoted(const std::string& text) {
    std::string out = "'";
    for (char c : text) out += c == '\'' ? std::string("'\\''") : std::string(1, c);
    return out + "'";
}

// Opens a file or an address with what the computer opens it with. If nothing opens it, the
// address is still in the terminal.
void OpenWithSystem(const std::string& what) {
#ifdef __APPLE__
    const std::string command = "open " + Quoted(what) + " >/dev/null 2>&1 &";
#else
    const std::string command = "xdg-open " + Quoted(what) + " >/dev/null 2>&1 &";
#endif
    if (std::system(command.c_str()) != 0) std::cerr << "Could not open / No se pudo abrir: " << what << '\n';
}

// ---------------------------------------------------------------------------------------------
// Messages to the page: a queue the "events" connection sends from.

std::mutex g_eventsLock;
std::condition_variable g_eventsChanged;
std::deque<std::string> g_events;
std::atomic<bool> g_quit{false};
std::atomic<int> g_pageConnections{0};

void PostToPage(const std::string& json) {
    {
        std::lock_guard lock(g_eventsLock);
        g_events.push_back(json);
    }
    g_eventsChanged.notify_all();
}

void Quit() {
    g_quit = true;
    g_eventsChanged.notify_all();
}

// ---------------------------------------------------------------------------------------------
// The controllers the computer sees: on Linux each is a /dev/input/js<n>. macOS does not tell
// without a framework; the page then just shows none.

int ConnectedControllers() {
#ifdef __APPLE__
    return 0;
#else
    int count = 0;
    std::error_code error;
    for (const auto& entry : fs::directory_iterator("/dev/input", error)) {
        if (entry.path().filename().string().rfind("js", 0) == 0) ++count;
    }
    return count;
#endif
}

// ---------------------------------------------------------------------------------------------
// The preparation: play.sh --no-start, read line by line.

struct Preparation {
    pid_t process = -1;  // play.sh, the leader of its own process group (the compiler is in it too)
    std::atomic<bool> running{false};
    std::atomic<bool> cancelled{false};
    bool startGameAfter = false;
    std::mutex errorLock;
    std::string error;   // what play.sh said when it stopped
};
Preparation g_prep;

const char* CurrentStatus() {
    if (g_prep.running) return "preparing";
    return HasDisc() && fs::exists(GameExecutable()) ? "ready" : "notPrepared";
}

std::string CurrentState() { return StateJson(CurrentStatus(), ConnectedControllers()); }

void StartGame() {
    const pid_t child = fork();
    if (child == 0) {
        setsid();
        const fs::path game = GameExecutable();
        if (chdir(game.parent_path().c_str()) != 0) _exit(1);
        const int null = open("/dev/null", O_RDWR);
        dup2(null, 0);
        dup2(null, 1);
        dup2(null, 2);
        execl(game.c_str(), game.c_str(), static_cast<char*>(nullptr));
        _exit(127);
    }
    if (child < 0) return;
    // As on Windows, the launcher's work is done once the game is open.
    PostToPage(ToastJson("gameStarted"));
    std::thread([] {
        std::this_thread::sleep_for(std::chrono::seconds(2));
        Quit();
    }).detach();
}

void StartPreparation(bool startGameAfter) {
    if (g_prep.running.exchange(true)) return;
    g_prep.cancelled = false;
    g_prep.startGameAfter = startGameAfter;
    { std::lock_guard lock(g_prep.errorLock); g_prep.error.clear(); }
    // Preparing shows its steps from the start. Playing first checks, in a second or two, that the
    // game is current; the steps show only if there is real work (a new disc, a changed package).
    if (!startGameAfter) PostToPage(ProgressJson(0, 0));

    int pipeEnds[2];
    if (pipe(pipeEnds) != 0) {
        g_prep.running = false;
        PostToPage(FinishedJson(false, false, "play.sh could not be started."));
        return;
    }
    const pid_t child = fork();
    if (child == 0) {
        setpgid(0, 0);
        dup2(pipeEnds[1], 1);
        dup2(pipeEnds[1], 2);
        close(pipeEnds[0]);
        close(pipeEnds[1]);
        if (chdir(Root().c_str()) != 0) _exit(1);
        const std::string script = (Root() / "play.sh").string();
        execl("/bin/bash", "bash", script.c_str(), "--no-start", static_cast<char*>(nullptr));
        _exit(127);
    }
    close(pipeEnds[1]);
    if (child < 0) {
        close(pipeEnds[0]);
        g_prep.running = false;
        PostToPage(FinishedJson(false, false, "play.sh could not be started."));
        return;
    }
    setpgid(child, child);
    g_prep.process = child;

    std::thread([readEnd = pipeEnds[0], child, showSteps = !startGameAfter]() mutable {
        int stage = 0;
        double fraction = 0;
        std::string pending, lastLine;
        char buffer[4096];
        ssize_t got;
        while ((got = read(readEnd, buffer, sizeof(buffer))) > 0) {
            pending.append(buffer, static_cast<size_t>(got));
            size_t end;
            while ((end = pending.find_first_of("\r\n")) != std::string::npos) {
                const std::string line = Trim(pending.substr(0, end));
                pending.erase(0, end + 1);
                if (line.empty()) continue;
                std::cout << line << '\n';
                const int oldStage = stage;
                const double oldFraction = fraction;
                ReadProgressLine(line, stage, fraction);
                if (!showSteps && ShowsRealWork(line)) {
                    showSteps = true;
                    PostToPage(ProgressJson(stage, fraction));
                }
                if (showSteps && (stage != oldStage || fraction - oldFraction > 0.004)) PostToPage(ProgressJson(stage, fraction));
                // An error from the script: "play.sh: <message>"; otherwise its last line.
                if (line.rfind("play.sh: ", 0) == 0) {
                    std::lock_guard lock(g_prep.errorLock);
                    g_prep.error = line.substr(9);
                } else {
                    lastLine = line;
                }
            }
        }
        close(readEnd);
        int status = 0;
        waitpid(child, &status, 0);
        const bool ok = WIFEXITED(status) && WEXITSTATUS(status) == 0 && !g_prep.cancelled;
        std::string error;
        {
            std::lock_guard lock(g_prep.errorLock);
            if (g_prep.error.empty()) g_prep.error = lastLine;
            error = g_prep.error;
        }
        g_prep.process = -1;
        g_prep.running = false;
        PostToPage(CurrentState());
        PostToPage(FinishedJson(ok, g_prep.cancelled, error));
        if (ok && g_prep.startGameAfter) StartGame();
    }).detach();
}

void CancelPreparation() {
    if (!g_prep.running || g_prep.process <= 0) return;
    g_prep.cancelled = true;
    kill(-g_prep.process, SIGTERM);
}

// ---------------------------------------------------------------------------------------------
// Updating: update.sh downloads the new version's package while the page shows how far it is, then
// says "apply"; the launcher stops, and the script (in its own session, so it goes on alone) puts the
// package over this folder and starts the launcher again. See launcher_core.h.

std::atomic<bool> g_updating{false};

void StartUpdate(const std::string& version) {
    if (!IsVersion(version) || g_updating.exchange(true)) return;
    int pipeEnds[2];
    if (pipe(pipeEnds) != 0) {
        g_updating = false;
        PostToPage(UpdateJson(0, "update.sh could not be started."));
        return;
    }
    const std::string launcherPid = std::to_string(getpid());
    const pid_t child = fork();
    if (child == 0) {
        setsid();
        dup2(pipeEnds[1], 1);
        dup2(pipeEnds[1], 2);
        close(pipeEnds[0]);
        close(pipeEnds[1]);
        if (chdir(Root().c_str()) != 0) _exit(1);
        const std::string script = (Root() / "update.sh").string();
        execl("/bin/bash", "bash", script.c_str(), version.c_str(), launcherPid.c_str(), static_cast<char*>(nullptr));
        _exit(127);
    }
    close(pipeEnds[1]);
    if (child < 0) {
        close(pipeEnds[0]);
        g_updating = false;
        PostToPage(UpdateJson(0, "update.sh could not be started."));
        return;
    }

    std::thread([readEnd = pipeEnds[0], child] {
        std::string pending, error;
        bool applying = false;
        char buffer[4096];
        ssize_t got;
        while (!applying && (got = read(readEnd, buffer, sizeof(buffer))) > 0) {
            pending.append(buffer, static_cast<size_t>(got));
            size_t end;
            while ((end = pending.find_first_of("\r\n")) != std::string::npos) {
                const std::string line = Trim(pending.substr(0, end));
                pending.erase(0, end + 1);
                if (line.empty()) continue;
                std::cout << line << '\n';
                if (line.rfind("progress ", 0) == 0) PostToPage(UpdateJson(std::atof(line.c_str() + 9), ""));
                else if (line.rfind("error ", 0) == 0) error = line.substr(6);
                else if (line == "apply") { applying = true; break; }
            }
        }
        close(readEnd);
        if (applying) {
            // The script waits for this program to end before it replaces its files.
            PostToPage(UpdateJson(1, ""));
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
            Quit();
            return;
        }
        waitpid(child, nullptr, 0);
        g_updating = false;
        PostToPage(UpdateJson(0, error.empty() ? "update.sh stopped." : error));
    }).detach();
}

// ---------------------------------------------------------------------------------------------
// The disc: asked for in a file window, remembered in UserData/disc.txt (play.sh reads it there).

bool ChooseDisc() {
    const std::string title = "Harvest Moon: Animal Parade (USA) - RBIEE9";
    std::string chosen;
#ifdef __APPLE__
    chosen = RunAndRead("osascript -e " + Quoted("POSIX path of (choose file with prompt \"" + title + "\")") + " 2>/dev/null");
#else
    if (HasCommand("zenity")) {
        chosen = RunAndRead("zenity --file-selection --title=" + Quoted(title) +
                            " --file-filter='Wii disc images | *.rvz *.iso *.wbfs *.wia *.ciso' --file-filter='All files | *' 2>/dev/null");
    } else if (HasCommand("kdialog")) {
        chosen = RunAndRead("kdialog --title " + Quoted(title) + " --getopenfilename \"$HOME\" '*.rvz *.iso *.wbfs *.wia *.ciso' 2>/dev/null");
    } else {
        PostToPage(ToastJson("noDiscWindow"));
        return false;
    }
#endif
    if (chosen.empty()) return false;
    WriteText(DiscFile(), chosen + "\n");
    return true;
}

void OnPageMessage(const std::string& json) {
    const auto message = ParseFlatJson(json);
    const auto found = message.find("cmd");
    const std::string cmd = found == message.end() ? std::string() : found->second;
    bool sendState = false;
    // While a new version is being downloaded, this one is not prepared or played.
    if (g_updating && (cmd == "prepare" || cmd == "play" || cmd == "chooseDisc")) return;
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
        const fs::path log = NewestLog();
        if (log.empty()) PostToPage(ToastJson("noLog"));
        else OpenWithSystem(log.string());
    } else if (cmd == "update") {
        const auto version = message.find("version");
        if (!g_prep.running && version != message.end()) StartUpdate(version->second);
    } else if (HandleSettingsMessage(message, sendState)) {
        if (sendState) PostToPage(CurrentState());
    } else if (cmd == "exit") {
        CancelPreparation();
        Quit();
    }
    // minimize and drag: the browser's tab is the window.
}

// ---------------------------------------------------------------------------------------------
// The little web server, on 127.0.0.1 only.

std::string g_key;  // the random part of the page's address

bool SendAll(int socket, const std::string& data) {
    size_t sent = 0;
    while (sent < data.size()) {
        const ssize_t n = send(socket, data.data() + sent, data.size() - sent, MSG_NOSIGNAL);
        if (n <= 0) return false;
        sent += static_cast<size_t>(n);
    }
    return true;
}

void Respond(int socket, const char* status, const char* type, const std::string& body) {
    std::ostringstream head;
    head << "HTTP/1.1 " << status << "\r\nContent-Type: " << type << "\r\nContent-Length: " << body.size()
         << "\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
    SendAll(socket, head.str() + body);
}

const char* ContentType(const fs::path& file) {
    const std::string extension = file.extension().string();
    if (extension == ".html") return "text/html; charset=utf-8";
    if (extension == ".css") return "text/css; charset=utf-8";
    if (extension == ".js") return "text/javascript; charset=utf-8";
    if (extension == ".svg") return "image/svg+xml";
    if (extension == ".png") return "image/png";
    if (extension == ".woff2") return "font/woff2";
    if (extension == ".ttf") return "font/ttf";
    if (extension == ".txt") return "text/plain; charset=utf-8";
    return "application/octet-stream";
}

// "events": the page's messages as they come, until the page goes away.
void ServeEvents(int socket) {
    if (!SendAll(socket, "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-store\r\nConnection: keep-alive\r\n\r\n")) return;
    ++g_pageConnections;
    while (!g_quit) {
        std::unique_lock lock(g_eventsLock);
        g_eventsChanged.wait_for(lock, std::chrono::seconds(15), [] { return !g_events.empty() || g_quit; });
        std::string out;
        while (!g_events.empty()) {
            out += "data: " + g_events.front() + "\n\n";
            g_events.pop_front();
        }
        lock.unlock();
        // A comment line every 15 seconds finds out whether the page is still there.
        if (!SendAll(socket, out.empty() ? std::string(": still here\n\n") : out)) break;
    }
    --g_pageConnections;
}

void ServeConnection(int socket) {
    std::string request;
    char buffer[8192];
    // The head, then as much body as Content-Length says.
    size_t headEnd;
    while ((headEnd = request.find("\r\n\r\n")) == std::string::npos) {
        const ssize_t n = recv(socket, buffer, sizeof(buffer), 0);
        if (n <= 0 || request.size() > 65536) { close(socket); return; }
        request.append(buffer, static_cast<size_t>(n));
    }
    size_t length = 0;
    for (const char* name : {"Content-Length:", "content-length:"}) {
        const auto at = request.find(name);
        if (at != std::string::npos && at < headEnd) length = std::strtoul(request.c_str() + at + std::strlen(name), nullptr, 10);
    }
    while (request.size() < headEnd + 4 + length && length < 65536) {
        const ssize_t n = recv(socket, buffer, sizeof(buffer), 0);
        if (n <= 0) break;
        request.append(buffer, static_cast<size_t>(n));
    }
    std::istringstream firstLine(request.substr(0, request.find("\r\n")));
    std::string method, target;
    firstLine >> method >> target;
    const std::string prefix = "/" + g_key + "/";
    if (target.rfind(prefix, 0) != 0) {
        Respond(socket, "404 Not Found", "text/plain", "Not found");
        close(socket);
        return;
    }
    std::string name = target.substr(prefix.size());
    name = name.substr(0, name.find('?'));
    if (method == "GET" && name == "events") {
        ServeEvents(socket);
    } else if (method == "POST" && name == "message") {
        Respond(socket, "204 No Content", "text/plain", "");
        close(socket);
        OnPageMessage(request.substr(headEnd + 4, length));
        return;
    } else if (method == "GET") {
        if (name.empty()) name = "index.html";
        const fs::path page = Root() / "Launcher";
        const fs::path file = (page / name).lexically_normal();
        // Only files of the page's own folder.
        const std::string inside = (page.lexically_normal() / "").string();
        if (file.string().rfind(inside, 0) == 0 && fs::is_regular_file(file)) {
            Respond(socket, "200 OK", ContentType(file), ReadText(file));
        } else {
            Respond(socket, "404 Not Found", "text/plain", "Not found");
        }
    } else {
        Respond(socket, "405 Method Not Allowed", "text/plain", "");
    }
    close(socket);
}

} // namespace

int main() {
    signal(SIGPIPE, SIG_IGN);
    signal(SIGCHLD, SIG_DFL);
    SetRoot(ProgramFolder());
    const char* recompLauncher = std::getenv("RECOMPLAUNCHER");
    SetStartedByRecompLauncher(recompLauncher && std::string(recompLauncher) == "1");
    WriteFirstConfig();
    WriteFirstKeyboard();

    std::random_device random;
    g_key = std::to_string(random()) + std::to_string(random());

    const int server = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    address.sin_port = 0;  // any free port
    if (server < 0 || bind(server, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0 || listen(server, 16) != 0) {
        std::cerr << "The launcher could not open its page. / El launcher no pudo abrir su página.\n";
        return 1;
    }
    socklen_t size = sizeof(address);
    getsockname(server, reinterpret_cast<sockaddr*>(&address), &size);
    const std::string url = "http://127.0.0.1:" + std::to_string(ntohs(address.sin_port)) + "/" + g_key + "/";
    std::cout << "Harvest Moon: Animal Parade - launcher\n"
              << "If the browser did not open, open / Si el navegador no se abrió, abre: " << url << std::endl;
    OpenWithSystem(url);

    // A controller plugged in or out shows on the Controls tab; and a minute with the page closed
    // (and nothing being prepared) ends the program. Before the page ever opened, it waits longer.
    std::thread([] {
        int lastControllers = ConnectedControllers();
        int secondsAlone = 0;
        bool pageOpened = false;
        while (!g_quit) {
            std::this_thread::sleep_for(std::chrono::seconds(2));
            const int now = ConnectedControllers();
            if (now != lastControllers && !g_prep.running) { lastControllers = now; PostToPage(CurrentState()); }
            pageOpened = pageOpened || g_pageConnections > 0;
            secondsAlone = g_pageConnections > 0 || g_prep.running ? 0 : secondsAlone + 2;
            if (secondsAlone >= (pageOpened ? 60 : 600)) Quit();
        }
    }).detach();

    // Each connection on its own thread: "events" stays open, and choosing the disc waits for its window.
    std::thread([server] {
        while (!g_quit) {
            const int client = accept(server, nullptr, nullptr);
            if (client < 0) continue;
            std::thread(ServeConnection, client).detach();
        }
    }).detach();

    while (!g_quit) std::this_thread::sleep_for(std::chrono::milliseconds(200));
    std::this_thread::sleep_for(std::chrono::milliseconds(300));  // the last events reach the page
    close(server);
    return 0;
}
