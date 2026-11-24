// What the launcher does on every system: the game's settings (UserData/Config.toml), the controls
// (UserData/keyboard_bindings.dat and [controller]), what the page is told about the game, and how
// the preparation's lines become the page's progress. The window around the page is each system's
// own: launcher.cpp on Windows (WebView2), launcher_unix.cpp on Linux and macOS (the browser).
//
// Lo que hace el launcher en todos los sistemas: la configuración del juego, los controles, lo que
// la página sabe del juego y cómo las líneas de la preparación se vuelven su progreso. La ventana es
// de cada sistema: launcher.cpp en Windows, launcher_unix.cpp en Linux y macOS.
//
// All text here is UTF-8; the page's messages are JSON.

#pragma once

#include <filesystem>
#include <map>
#include <string>

namespace LauncherCore {

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------------------------
// Where things are: everything is in the package folder, which the program sets once at start.

void SetRoot(const fs::path& root);
fs::path Root();
fs::path UserData();
fs::path ConfigPath();
fs::path DiscFile();
// Game/AnimalParade.exe on Windows, Game/AnimalParade elsewhere.
fs::path GameExecutable();

std::string ReadText(const fs::path& path);
void WriteText(const fs::path& path, const std::string& text);
std::string Trim(std::string text);

// Started by RecompLauncher (RECOMPLAUNCHER=1): the page does not look for new versions then, since
// RecompLauncher updates the game itself.
void SetStartedByRecompLauncher(bool started);

// A version as the releases name it, "0.2.3" (numbers and dots only).
bool IsVersion(const std::string& text);
// This package's version: version.txt ("v0.2.3") without its "v".
std::string BareVersion();

// ---------------------------------------------------------------------------------------------
// JSON, as much as the page needs.

std::string JsonString(const std::string& text);
// The page only sends flat objects ({"cmd":"setOption","key":"picture","value":true}): each key
// with its value as text (strings without their quotes).
std::map<std::string, std::string> ParseFlatJson(const std::string& json);

// ---------------------------------------------------------------------------------------------
// The first time, before the game ever ran: the settings as the original game, and the keyboard
// on with the default keys.

void WriteFirstConfig();
void WriteFirstKeyboard();

// ---------------------------------------------------------------------------------------------
// What the page shows.

// A disc was chosen (UserData/disc.txt) or extracted (Disc/).
bool HasDisc();
// {"type":"state",...}: is the game prepared ("ready", "notPrepared", "preparing"), the disc, the
// settings, the controls and the mods. `controllers` is how many controllers the system sees.
std::string StateJson(const char* status, int controllers);
std::string ProgressJson(int stage, double fraction);
std::string FinishedJson(bool ok, bool cancelled, const std::string& error);
std::string ToastJson(const char* key);

// The newest UserData/Logs/.../console.log, or an empty path.
fs::path NewestLog();

// ---------------------------------------------------------------------------------------------
// The page's settings messages: setOption, setKey, setPad, setKeyboard, setMod, setModSetting,
// resetControls, setUiLanguage and seenWhatsNew (a new version's notes were shown). True when the
// message was one of them; `sendState` then says whether the page should get the state again.

bool HandleSettingsMessage(const std::map<std::string, std::string>& message, bool& sendState);

// ---------------------------------------------------------------------------------------------
// Updating to a new version (update.ps1 or update.sh): the script downloads this system's package
// of that version from the GitHub release and prints "progress <0..1>" as it goes, then "apply"
// when the launcher should close so that its files can be replaced; it puts the package over this
// folder (UserData stays) and opens the launcher again. "error <message>" when it could not.

// The page's {"type":"update",...}: how far the download is, or why it failed.
std::string UpdateJson(double fraction, const std::string& error);

// ---------------------------------------------------------------------------------------------
// The preparation (play.ps1 or play.sh with --no-start), line by line.

// Turns a line the script (or the compiler under it) printed into the page's progress: stage 0
// extracting the disc, 1 translating, 2 compiling; fraction from 0 to 1 within the stage.
void ReadProgressLine(const std::string& line, int& stage, double& fraction);
// Whether the line shows real work (extracting, translating, configuring, compiling): playing
// shows the steps only then, and starts at once when the game is already current.
bool ShowsRealWork(const std::string& line);

} // namespace LauncherCore
