// What the launcher does on every system (see launcher_core.h).

#include "launcher_core.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <optional>
#include <sstream>
#include <vector>

namespace LauncherCore {

namespace {

fs::path g_root;

} // namespace

// ---------------------------------------------------------------------------------------------
// Where things are.

void SetRoot(const fs::path& root) { g_root = root; }
fs::path Root() { return g_root; }
fs::path UserData() { return Root() / "UserData"; }
fs::path ConfigPath() { return UserData() / "Config.toml"; }
fs::path DiscFile() { return UserData() / "disc.txt"; }

fs::path GameExecutable() {
#ifdef _WIN32
    return Root() / "Game" / "AnimalParade.exe";
#else
    return Root() / "Game" / "AnimalParade";
#endif
}

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

std::string Trim(std::string s) {
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
    return s;
}

// ---------------------------------------------------------------------------------------------
// JSON.

std::string JsonString(const std::string& text) {
    std::string out = "\"";
    for (char c : text) {
        if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else if (c == '\n') out += "\\n";
        else if (c == '\r') {}
        else if (static_cast<unsigned char>(c) < 0x20) out += ' ';
        else out += c;
    }
    return out + "\"";
}

std::map<std::string, std::string> ParseFlatJson(const std::string& json) {
    std::map<std::string, std::string> fields;
    size_t i = 0;
    auto skipSpace = [&] { while (i < json.size() && std::isspace(static_cast<unsigned char>(json[i]))) ++i; };
    auto readString = [&] {
        std::string s;
        ++i;  // the opening quote
        while (i < json.size() && json[i] != '"') {
            if (json[i] == '\\' && i + 1 < json.size()) {
                ++i;
                s += json[i] == 'n' ? '\n' : json[i];
            } else {
                s += json[i];
            }
            ++i;
        }
        ++i;  // the closing quote
        return s;
    };
    skipSpace();
    if (i < json.size() && json[i] == '{') ++i;
    while (i < json.size()) {
        skipSpace();
        if (i >= json.size() || json[i] != '"') break;
        const std::string key = readString();
        skipSpace();
        if (i < json.size() && json[i] == ':') ++i;
        skipSpace();
        std::string value;
        if (i < json.size() && json[i] == '"') {
            value = readString();
        } else {
            while (i < json.size() && json[i] != ',' && json[i] != '}') value += json[i++];
            value = Trim(value);
        }
        fields[key] = value;
        skipSpace();
        if (i < json.size() && json[i] == ',') ++i;
    }
    return fields;
}

namespace {

// ---------------------------------------------------------------------------------------------
// UserData/Config.toml, the game's settings. Only the few lines the launcher changes are touched:
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
#ifdef _WIN32
        const char* const kNewLine = "\r\n";
#else
        const char* const kNewLine = "\n";
#endif
        std::string text;
        for (const auto& line : lines) text += line + kNewLine;
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
    const char* oldKey = nullptr;  // the name older versions wrote, still read
};

const Option kOptions[] = {
    {"picture", "video", "widescreen", Option::Bool, "false"},
    {"interpolation", "video", "frame_interpolation_fps", Option::Number, "0"},
    {"resolution", "video", "resolution_multiplier", Option::Number, "1"},
    {"fullscreen", "video", "display_mode", Option::Text, "windowed"},
    {"api", "video", "graphics_api", Option::Text, "auto"},
    {"language", "console", "language", Option::Text, "english"},
    {"fastForward", "speed", "hold_to_fast_forward", Option::Bool, "false", "hold_tab_to_fast_forward"},
    {"showFps", "video", "show_fps", Option::Bool, "false"},
    // Real Wii Remotes, as the game's F10 menu keeps them (runtime_config.h).
    {"wiiRemotes", "controller", "wii_remotes", Option::Bool, "false"},
    {"wiiAutoPair", "controller", "wii_auto_pair", Option::Bool, "true"},
    {"wiiSensorBar", "controller", "wii_sensor_bar", Option::Text, "below"},
};

// The page's value (JSON: true, 60, 1.5, "vulkan") as the line in Config.toml.
std::string ConfigValue(const Option& option, const std::string& value) {
    if (std::string(option.page) == "fullscreen") return value == "true" ? "\"borderless\"" : "\"windowed\"";
    if (option.kind == Option::Text) return "\"" + value + "\"";
    if (std::string(option.key) == "resolution_multiplier" && value.find('.') == std::string::npos) return value + ".0";
    return value;
}

// The Config.toml line as the page's value.
std::string PageValue(const Option& option, const ConfigFile& config) {
    std::optional<std::string> found = config.Get(option.section, option.key);
    if (!found && option.oldKey) found = config.Get(option.section, option.oldKey);
    const std::string value = found.value_or(option.fallback);
    if (std::string(option.page) == "fullscreen") return value == "windowed" ? "false" : "true";
    if (option.kind == Option::Text) return JsonString(value);
    if (option.kind == Option::Number) {
        // 1.0 and 1 are the same choice on the page.
        char* end = nullptr;
        const double number = std::strtod(value.c_str(), &end);
        if (end == value.c_str()) return option.fallback;
        std::ostringstream out;
        out << number;
        return out.str();
    }
    return value;
}

// ---------------------------------------------------------------------------------------------
// The controls. The game reads them from two places, and the launcher writes both:
//   - UserData/keyboard_bindings.dat: the keyboard, written by the game's input library (aurora,
//     lib/dolphin/pad/pad.cpp). After a 32-byte header ("KBND", version 3) come four players, each
//     with: one byte "the keyboard is on", 12 buttons {int32 key, uint16 button, 2 bytes padding}
//     and 10 stick and trigger directions {int32 key, uint16 direction, int16 influence}. Keys are
//     SDL scancodes (the USB key numbers); -1 is no key, -2 to -6 are mouse buttons.
//   - [controller] in Config.toml: the controller, one line per button, with names like "south"
//     (the bottom face button) or "left_trigger".
// Fast-forward has its own key and controller button in [speed].
//
// The buttons are the game's (GameCube) buttons, which the game turns into the Wii Remote and
// Nunchuk: A A, B B, X 1, Y 2, Start +, Z -, L Nunchuk Z, R Nunchuk C, the D-pad the D-pad.

// The page's names, in the order of the file and of [controller].
const char* const kButtonNames[12] = {"a", "b", "x", "y", "start", "z", "l", "r", "up", "down", "left", "right"};
const uint16_t kButtonIds[12] = {0x0100, 0x0200, 0x0400, 0x0800, 0x1000, 0x0010, 0x0040, 0x0020, 0x0008, 0x0004, 0x0001, 0x0002};
// The Nunchuk stick: the first four directions of the file.
const char* const kStickNames[4] = {"stickRight", "stickLeft", "stickUp", "stickDown"};
constexpr int kAxisTriggerL = 8, kAxisTriggerR = 9;

// The keys a new player starts with (the same as the game's "Reset to the default keys", in
// settings_overlay.cpp): A Space, B Left Shift, 1 and 2, + Enter, - Backspace, Z Q, C E, the arrows
// the D-pad, WASD the stick. The mouse is the pointer, so it is left alone.
const int32_t kDefaultKeys[12] = {44, 225, 30, 31, 40, 42, 20, 8, 82, 81, 80, 79};
const int32_t kDefaultAxisKeys[10] = {7, 4, 26, 22, 15, 13, 12, 14, 20, 8};
// The controller buttons a new player starts with (aurora's own, for any XInput-like controller).
const char* const kDefaultPad[12] = {"south", "east", "west", "north", "start", "right_shoulder", "unmapped", "unmapped",
                                     "dpad_up", "dpad_down", "dpad_left", "dpad_right"};
constexpr int32_t kDefaultFastForwardKey = 43;  // Tab

// The free camera's controls (mod free_camera), each a key and a controller button or stick
// direction, kept in [mods] as free_camera_<name>_key and free_camera_<name>_button. The page calls
// them by its own names (cameraLeft...).
struct CameraControl {
    const char* page;
    const char* name;
    int32_t key;         // as it starts: J, L, I, K, U
    const char* button;  // as it starts: the right stick, and R3
};
const CameraControl kCameraControls[] = {
    {"cameraLeft", "left", 13, "right_stick_left"},    {"cameraRight", "right", 15, "right_stick_right"},
    {"cameraUp", "up", 12, "right_stick_up"},          {"cameraDown", "down", 14, "right_stick_down"},
    {"cameraReset", "reset", 24, "right_stick"},
};

const CameraControl* FindCameraControl(const std::string& page) {
    for (const auto& control : kCameraControls) if (page == control.page) return &control;
    return nullptr;
}

std::string CameraKeyLine(const CameraControl& control) { return std::string("free_camera_") + control.name + "_key"; }
std::string CameraButtonLine(const CameraControl& control) { return std::string("free_camera_") + control.name + "_button"; }

fs::path KeyboardPath() { return UserData() / "keyboard_bindings.dat"; }

struct KeyboardFile {
    struct Player {
        bool on = false;
        int32_t buttons[12];
        int32_t axes[10];
        int16_t influence[10] = {};
    };
    std::array<Player, 4> players;

    KeyboardFile() {
        for (auto& player : players) {
            std::fill(std::begin(player.buttons), std::end(player.buttons), -1);
            std::fill(std::begin(player.axes), std::end(player.axes), -1);
        }
    }

    static constexpr size_t kHeader = 32, kPlayer = 1 + 12 * 8 + 10 * 8;

    static bool Exists() { return fs::exists(KeyboardPath()); }

    static KeyboardFile Load() {
        KeyboardFile file;
        const std::string data = ReadText(KeyboardPath());
        if (data.size() < kHeader + 4 * kPlayer || data.compare(0, 4, "KBND") != 0 || data[4] != 3) return file;
        auto read32 = [&](size_t at) { int32_t v; std::memcpy(&v, data.data() + at, 4); return v; };
        auto read16 = [&](size_t at) { int16_t v; std::memcpy(&v, data.data() + at, 2); return v; };
        for (size_t p = 0; p < 4; ++p) {
            const size_t at = kHeader + p * kPlayer;
            file.players[p].on = data[at] != 0;
            for (size_t i = 0; i < 12; ++i) file.players[p].buttons[i] = read32(at + 1 + i * 8);
            for (size_t i = 0; i < 10; ++i) {
                file.players[p].axes[i] = read32(at + 1 + 96 + i * 8);
                file.players[p].influence[i] = read16(at + 1 + 96 + i * 8 + 6);
            }
        }
        return file;
    }

    void Save() const {
        std::string data(kHeader + 4 * kPlayer, '\0');
        std::memcpy(data.data(), "KBND", 4);
        data[4] = 3;
        auto write = [&](size_t at, const void* value, size_t size) { std::memcpy(data.data() + at, value, size); };
        for (size_t p = 0; p < 4; ++p) {
            const size_t at = kHeader + p * kPlayer;
            data[at] = players[p].on ? 1 : 0;
            for (size_t i = 0; i < 12; ++i) {
                write(at + 1 + i * 8, &players[p].buttons[i], 4);
                write(at + 1 + i * 8 + 4, &kButtonIds[i], 2);
            }
            for (size_t i = 0; i < 10; ++i) {
                const uint16_t direction = static_cast<uint16_t>(i);
                write(at + 1 + 96 + i * 8, &players[p].axes[i], 4);
                write(at + 1 + 96 + i * 8 + 4, &direction, 2);
                write(at + 1 + 96 + i * 8 + 6, &players[p].influence[i], 2);
            }
        }
        WriteText(KeyboardPath(), data);
    }

    void SetDefaults(Player& player) {
        player.on = true;
        std::copy(std::begin(kDefaultKeys), std::end(kDefaultKeys), player.buttons);
        std::copy(std::begin(kDefaultAxisKeys), std::end(kDefaultAxisKeys), player.axes);
    }
};

int ButtonIndex(const std::string& name) {
    for (int i = 0; i < 12; ++i) if (name == kButtonNames[i]) return i;
    return -1;
}

int StickIndex(const std::string& name) {
    for (int i = 0; i < 4; ++i) if (name == kStickNames[i]) return i;
    return -1;
}

int ToInt(const std::string& text, int fallback) {
    char* end = nullptr;
    const long value = std::strtol(text.c_str(), &end, 10);
    return end == text.c_str() ? fallback : static_cast<int>(value);
}

// A [controller] line is "name" or "name,second name"; a name may end in "@threshold".
std::string PadPrimary(const std::string& value) {
    std::string name = ConfigFile::Strip(value.substr(0, value.find(',')));
    return name.substr(0, name.find('@'));
}

// What the page shows for the controller button of game button i.
std::string PadShown(const ConfigFile& config, int i) {
    std::string name = PadPrimary(config.Get("controller", kButtonNames[i]).value_or(kDefaultPad[i]));
    // L and R left alone follow the triggers.
    if (name == "unmapped" && i == 6) return "left_trigger";
    if (name == "unmapped" && i == 7) return "right_trigger";
    return name;
}

std::string ControlsJson(const ConfigFile& config) {
    const KeyboardFile keyboard = KeyboardFile::Load();
    const auto& player = keyboard.players[0];
    std::ostringstream json;
    json << "{\"keyboard\":" << (player.on ? "true" : "false") << ",\"keys\":{";
    for (int i = 0; i < 12; ++i) json << (i ? "," : "") << "\"" << kButtonNames[i] << "\":" << player.buttons[i];
    for (int i = 0; i < 4; ++i) json << ",\"" << kStickNames[i] << "\":" << player.axes[i];
    json << "},\"pad\":{";
    for (int i = 0; i < 12; ++i) json << (i ? "," : "") << "\"" << kButtonNames[i] << "\":" << JsonString(PadShown(config, i));
    const int fastKey = ToInt(config.Get("speed", "fast_forward_key").value_or("43"), kDefaultFastForwardKey);
    json << "},\"fastForwardKey\":" << fastKey
         << ",\"fastForwardButton\":" << JsonString(PadPrimary(config.Get("speed", "fast_forward_button").value_or("disabled")));
    json << ",\"camera\":{\"keys\":{";
    for (size_t i = 0; i < std::size(kCameraControls); ++i) {
        const auto& control = kCameraControls[i];
        const int key = ToInt(config.Get("mods", CameraKeyLine(control)).value_or(std::to_string(control.key)), control.key);
        json << (i ? "," : "") << "\"" << control.page << "\":" << key;
    }
    json << "},\"pad\":{";
    for (size_t i = 0; i < std::size(kCameraControls); ++i) {
        const auto& control = kCameraControls[i];
        json << (i ? "," : "") << "\"" << control.page << "\":"
             << JsonString(PadPrimary(config.Get("mods", CameraButtonLine(control)).value_or(control.button)));
    }
    json << "}}}";
    return json.str();
}

// A key for a button, a stick direction, fast-forward or the free camera. The keyboard turns on with
// a button's or a stick direction's.
void SetKey(const std::string& action, int32_t key) {
    if (const CameraControl* control = FindCameraControl(action)) {
        ConfigFile config = ConfigFile::Load();
        config.Set("mods", CameraKeyLine(*control), std::to_string(key));
        config.Save();
        return;
    }
    if (action == "fastForward") {
        ConfigFile config = ConfigFile::Load();
        config.Set("speed", "fast_forward_key", std::to_string(key));
        config.Save();
        return;
    }
    KeyboardFile keyboard = KeyboardFile::Load();
    auto& player = keyboard.players[0];
    if (const int i = ButtonIndex(action); i >= 0) {
        player.buttons[i] = key;
        // Nunchuk Z and C also follow the analog triggers, so those move with them.
        if (i == 6) player.axes[kAxisTriggerL] = key;
        if (i == 7) player.axes[kAxisTriggerR] = key;
    } else if (const int i = StickIndex(action); i >= 0) {
        player.axes[i] = key;
    } else {
        return;
    }
    player.on = true;
    keyboard.Save();
}

// A controller button ("south", "left_trigger"...) for a button, fast-forward or the free camera. A
// second button someone wrote by hand in Config.toml stays.
void SetPad(const std::string& action, const std::string& value) {
    ConfigFile config = ConfigFile::Load();
    if (const CameraControl* control = FindCameraControl(action)) {
        config.Set("mods", CameraButtonLine(*control), "\"" + value + "\"");
    } else if (action == "fastForward") {
        config.Set("speed", "fast_forward_button", "\"" + value + "\"");
    } else if (const int i = ButtonIndex(action); i >= 0) {
        const std::string old = config.Get("controller", kButtonNames[i]).value_or("");
        const auto comma = old.find(',');
        config.Set("controller", kButtonNames[i], "\"" + value + (comma == std::string::npos ? "" : old.substr(comma)) + "\"");
    } else {
        return;
    }
    config.Save();
}

void SetKeyboardOn(bool on) {
    KeyboardFile keyboard = KeyboardFile::Load();
    auto& player = keyboard.players[0];
    const bool noKeys = std::all_of(std::begin(player.buttons), std::end(player.buttons), [](int32_t k) { return k == -1; });
    if (on && noKeys) keyboard.SetDefaults(player);
    player.on = on;
    keyboard.Save();
}

void ResetControls() {
    KeyboardFile keyboard = KeyboardFile::Load();
    keyboard.SetDefaults(keyboard.players[0]);
    keyboard.Save();
    ConfigFile config = ConfigFile::Load();
    for (int i = 0; i < 12; ++i) config.Set("controller", kButtonNames[i], std::string("\"") + kDefaultPad[i] + "\"");
    config.Set("speed", "fast_forward_key", std::to_string(kDefaultFastForwardKey));
    config.Set("speed", "fast_forward_button", "\"disabled\"");
    for (const auto& control : kCameraControls) {
        config.Set("mods", CameraKeyLine(control), std::to_string(control.key));
        config.Set("mods", CameraButtonLine(control), std::string("\"") + control.button + "\"");
    }
    config.Save();
}

// The game's mods (runtime/src/hle/game_mods in WiiCompiled's patch): each is a line in [mods] of
// Config.toml, off unless it says true. Some have a setting, a percentage in a line of its own in
// [mods] (from 100, the original game, to 300). The page has their names, descriptions and limits.
const char* const kMods[] = {"romance_any_gender",     "no_place_sign",        "faster_actions",  "faster_walking", "free_camera",
                              "cheat_infinite_stamina", "cheat_infinite_money", "cheat_infinite_lumber",
                              "cheat_infinite_stone", "cheat_infinite_feed", "cheat_stop_time"};
const char* const kModSettings[] = {"faster_actions_percent", "faster_walking_percent"};
// Settings that are a yes or no, in a line of their own in [mods] (true or false); the page knows
// what each is while its line is missing.
const char* const kModYesNo[] = {"free_camera_talk"};

template <size_t N>
bool OneOf(const char* const (&list)[N], const std::string& name) {
    return std::find_if(std::begin(list), std::end(list), [&](const char* item) { return name == item; }) != std::end(list);
}

// A whole number of at most three digits: what a percentage line may hold.
bool IsPercent(const std::string& text) {
    return !text.empty() && text.size() <= 3 &&
           std::all_of(text.begin(), text.end(), [](char c) { return std::isdigit(static_cast<unsigned char>(c)); });
}

std::string Field(const std::map<std::string, std::string>& message, const char* key) {
    const auto found = message.find(key);
    return found == message.end() ? std::string() : found->second;
}

} // namespace

// ---------------------------------------------------------------------------------------------
// The first time.

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

void WriteFirstKeyboard() {
    if (KeyboardFile::Exists()) return;
    KeyboardFile file;
    file.SetDefaults(file.players[0]);
    file.Save();
}

// ---------------------------------------------------------------------------------------------
// What the page shows.

bool HasDisc() {
    if (fs::exists(DiscFile()) && !Trim(ReadText(DiscFile())).empty()) return true;
    return fs::exists(Root() / "Disc" / "sys" / "main.dol") || fs::exists(Root() / "Disc" / "DATA" / "sys" / "main.dol");
}

std::string StateJson(const char* status, int controllers) {
    const ConfigFile config = ConfigFile::Load();
    std::ostringstream json;
    json << "{\"type\":\"state\",\"status\":\"" << status << "\",\"hasDisc\":" << (HasDisc() ? "true" : "false")
         << ",\"discId\":\"" << (HasDisc() ? "RBIEE9" : "—") << "\",\"controllers\":" << controllers;
    const std::string version = Trim(ReadText(Root() / "version.txt"));
    json << ",\"version\":" << JsonString(version.empty() ? "dev" : version);
    json << ",\"uiLanguage\":" << JsonString(config.Get("launcher", "language").value_or("en"));
    json << ",\"options\":{";
    bool first = true;
    for (const auto& option : kOptions) {
        json << (first ? "" : ",") << "\"" << option.page << "\":" << PageValue(option, config);
        first = false;
    }
    json << "},\"controls\":" << ControlsJson(config) << ",\"mods\":{";
    for (size_t i = 0; i < std::size(kMods); ++i) {
        json << (i ? "," : "") << "\"" << kMods[i] << "\":"
             << (config.Get("mods", kMods[i]).value_or("false") == "false" ? "false" : "true");
    }
    json << "},\"modSettings\":{";
    for (size_t i = 0; i < std::size(kModSettings); ++i) {
        const std::string value = config.Get("mods", kModSettings[i]).value_or("");
        json << (i ? "," : "") << "\"" << kModSettings[i] << "\":" << (IsPercent(value) ? value : "null");
    }
    for (const char* key : kModYesNo) {
        const std::string value = config.Get("mods", key).value_or("");
        json << ",\"" << key << "\":" << (value == "true" ? "true" : value == "false" ? "false" : "null");
    }
    json << "}}";
    return json.str();
}

std::string ProgressJson(int stage, double fraction) {
    std::ostringstream json;
    json << "{\"type\":\"progress\",\"stage\":" << stage << ",\"fraction\":" << fraction << "}";
    return json.str();
}

std::string FinishedJson(bool ok, bool cancelled, const std::string& error) {
    return std::string("{\"type\":\"finished\",\"ok\":") + (ok ? "true" : "false") + ",\"cancelled\":" +
           (cancelled ? "true" : "false") + ",\"error\":" + JsonString(ok ? "" : error) + "}";
}

std::string ToastJson(const char* key) { return std::string("{\"type\":\"toast\",\"key\":\"") + key + "\"}"; }

fs::path NewestLog() {
    fs::path newest;
    fs::file_time_type newestTime{};
    std::error_code error;
    for (const auto& entry : fs::directory_iterator(UserData() / "Logs", error)) {
        const fs::path log = entry.path() / "console.log";
        if (!fs::exists(log, error)) continue;
        const auto time = fs::last_write_time(log, error);
        if (newest.empty() || time > newestTime) { newest = log; newestTime = time; }
    }
    return newest;
}

// ---------------------------------------------------------------------------------------------
// The page's settings messages.

bool HandleSettingsMessage(const std::map<std::string, std::string>& message, bool& sendState) {
    const std::string cmd = Field(message, "cmd");
    sendState = true;
    if (cmd == "setOption") {
        sendState = false;
        for (const auto& option : kOptions) {
            if (Field(message, "key") != option.page) continue;
            ConfigFile config = ConfigFile::Load();
            config.Set(option.section, option.key, ConfigValue(option, Field(message, "value")));
            config.Save();
        }
    } else if (cmd == "setKey") {
        const std::string scancode = Field(message, "scancode");
        if (!scancode.empty()) SetKey(Field(message, "action"), ToInt(scancode, -1));
    } else if (cmd == "setPad") {
        // Only the names the game knows: letters, digits and "_".
        const std::string value = Field(message, "value");
        if (!value.empty() && std::all_of(value.begin(), value.end(), [](char c) { return std::isalnum(static_cast<unsigned char>(c)) || c == '_'; }))
            SetPad(Field(message, "action"), value);
    } else if (cmd == "setKeyboard") {
        SetKeyboardOn(Field(message, "value") == "true");
    } else if (cmd == "setMod") {
        const std::string name = Field(message, "name");
        if (OneOf(kMods, name)) {
            ConfigFile config = ConfigFile::Load();
            config.Set("mods", name, Field(message, "value") == "true" ? "true" : "false");
            config.Save();
        }
    } else if (cmd == "setModSetting") {
        // A mod's percentage, from 100 to 300, or a yes or no.
        const std::string name = Field(message, "name");
        const std::string value = Field(message, "value");
        if (OneOf(kModSettings, name) && IsPercent(value) && std::stoi(value) >= 100 && std::stoi(value) <= 300) {
            ConfigFile config = ConfigFile::Load();
            config.Set("mods", name, value);
            config.Save();
        } else if (OneOf(kModYesNo, name) && (value == "true" || value == "false")) {
            ConfigFile config = ConfigFile::Load();
            config.Set("mods", name, value);
            config.Save();
        }
    } else if (cmd == "resetControls") {
        ResetControls();
    } else if (cmd == "setUiLanguage") {
        sendState = false;
        ConfigFile config = ConfigFile::Load();
        config.Set("launcher", "language", Field(message, "value") == "es" ? "\"es\"" : "\"en\"");
        config.Save();
    } else {
        sendState = false;
        return false;
    }
    return true;
}

// ---------------------------------------------------------------------------------------------
// The preparation, line by line.

void ReadProgressLine(const std::string& line, int& stage, double& fraction) {
    auto has = [&](const char* text) { return line.find(text) != std::string::npos; };
    if (has("== Extracting")) { stage = 0; fraction = 0; }
    else if (has("== Translating") || has("== The translation is current")) { stage = 1; fraction = has("current") ? 1 : 0; }
    else if (has("== Configuring")) { stage = 2; fraction = 0; }
    else if (has("== Compiling")) { stage = 2; fraction = 0.02; }
    else if (has("== Copying")) { stage = 2; fraction = 0.98; }
    else if (stage == 2 && line.size() > 3 && line[0] == '[') {
        // Ninja: "[123/4567] Building CXX object ...".
        unsigned done = 0, total = 0;
        if (std::sscanf(line.c_str(), "[%u/%u]", &done, &total) == 2 && total) fraction = std::min(0.97, 0.02 + 0.95 * done / total);
    } else if (stage == 0) {
        // nodtool shows how far the extraction is as a percentage.
        const auto percent = line.rfind('%');
        if (percent != std::string::npos && percent > 0) {
            size_t begin = percent;
            while (begin > 0 && (std::isdigit(static_cast<unsigned char>(line[begin - 1])) || line[begin - 1] == '.')) --begin;
            if (begin < percent) fraction = std::min(1.0, std::atof(line.substr(begin, percent - begin).c_str()) / 100.0);
        }
    }
}

bool ShowsRealWork(const std::string& line) {
    return line.find("== Extracting") != std::string::npos || line.find("== Translating") != std::string::npos ||
           line.find("== Configuring") != std::string::npos ||
           (line.size() > 1 && line[0] == '[' && line.find('/') != std::string::npos);
}

} // namespace LauncherCore
