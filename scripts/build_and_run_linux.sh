#!/usr/bin/env bash
# Build ModernGekko and the recompiled Harvest Moon: Animal Parade on Ubuntu
# (native, or inside WSL2 on Windows), then start the game.
#
# Compila ModernGekko y Harvest Moon: Animal Parade recompilado en Ubuntu
# (nativo, o dentro de WSL2 en Windows) y arranca el juego.
#
# Adapted from the Magical Melody recompilation (github.com/RodoLy/hmmmgc).
# Not tested with this game yet.
# Adaptado del recomp de Magical Melody. Todavía no se ha probado con este juego.
#
# Usage / Uso:
#   scripts/build_and_run_linux.sh "/mnt/c/Users/you/Downloads/Harvest Moon.rvz"   # first time
#   scripts/build_and_run_linux.sh                                                  # afterwards
#
# Every step is skipped when its result already exists, so later runs only
# start the game, and a run that stopped halfway continues where it was.
# Everything is built under $HOME; only the apt packages need sudo.
# docs/BUILDING.md explains each step in Spanish and English.
#
# Optional environment variables:
#   MODERNGEKKO_TEMPLATE  where ModernGekko-Template lives (default: ~/ModernGekko-Template)
#   GRAPHICS_BACKEND      Vulkan or OGL, when the automatic choice is wrong
#   EXTRA_RUN_ARGS        more arguments for moderngekko-run, e.g. "--mute"
#   MODERNGEKKO_USER_DIR  ModernGekko's user folder: settings, saves and mods
#                         (default: ~/.local/share/moderngekko)

set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPOSITORY_ROOT

# The ModernGekko-Template version that boots Magical Melody (it pins
# ModernGekko edd460a and DolRecomp 1bec355). Animal Parade starts from the
# same one; a newer version may be needed if this one fails with a Wii game.
readonly TEMPLATE_URL="https://github.com/ExpansionPak/ModernGekko-Template.git"
readonly TEMPLATE_COMMIT="c2553a99584b2045dbe46a70e1570994dae8beef"
readonly TEMPLATE_DIRECTORY="${MODERNGEKKO_TEMPLATE:-$HOME/ModernGekko-Template}"

# Dolphin externals only its Windows (Qt, FFmpeg-bin) and Android
# (libadrenotools) builds use; ModernGekko builds Dolphin without Qt. Skipping
# them saves about 600 MB, most of it Qt, the download most likely to break.
readonly SUBMODULES_UNUSED_ON_LINUX=(Externals/Qt Externals/FFmpeg-bin Externals/libadrenotools)
readonly SUBMODULE_DOWNLOAD_ATTEMPTS=3

# The template keeps each game under extracted/<slug>/.
readonly GAME_SLUG="Harvest-Moon-Animal-Parade"
readonly EXTRACTED_DIRECTORY="$TEMPLATE_DIRECTORY/extracted/$GAME_SLUG"
readonly DOLRECOMP="$TEMPLATE_DIRECTORY/lib/DolRecomp/build/dolrecomp"

# Where ModernGekko keeps settings (config.ini), saves and mods. This is the
# folder it picks on its own; the script passes it explicitly so that
# MODERNGEKKO_USER_DIR can move it.
readonly USER_DIRECTORY="${MODERNGEKKO_USER_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/moderngekko}"

# ModernGekko-Template's package list for Ubuntu (from its README), plus what
# this script needs: git and curl to download, python3 for our disc tools,
# mesa-utils and vulkan-tools to see which graphics drivers are available.
readonly APT_PACKAGES=(
    ninja-build build-essential pkg-config cmake
    libevdev-dev libudev-dev libgtk-3-dev libsystemd-dev
    libbluetooth-dev libasound2-dev libpulse-dev libgl1-mesa-dev
    libxrandr-dev libxi-dev
    git curl python3 mesa-utils vulkan-tools
)

step() { printf '\n==> %s\n' "$*"; }
note() { printf '    %s\n' "$*"; }
fail() {
    printf '\nerror: %s\n' "$*" >&2
    exit 1
}

running_in_wsl() { grep -qi microsoft /proc/version 2> /dev/null; }

check_system() {
    step "Checking the system"
    [[ "$(uname -s)" == Linux ]] || fail "this script is for Linux; on Windows, run it inside WSL2 (see docs/BUILDING.md)"
    command -v apt-get > /dev/null ||
        fail "only Ubuntu and Debian are automated; install the packages from docs/BUILDING.md by hand"
    if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
        running_in_wsl &&
            fail "WSL has no window support yet: run 'wsl --update' in Windows PowerShell, then reopen Ubuntu"
        fail "no graphical session (DISPLAY and WAYLAND_DISPLAY are empty)"
    fi
    if running_in_wsl; then
        note "$(uname -m), inside WSL2"
    else
        note "$(uname -m), native Linux"
    fi
}

install_missing_packages() {
    local missing=()
    local package
    for package in "${APT_PACKAGES[@]}"; do
        dpkg -s "$package" > /dev/null 2>&1 || missing+=("$package")
    done
    [[ ${#missing[@]} -eq 0 ]] && return

    step "Installing ${#missing[@]} packages (sudo asks for your Linux password)"
    local as_root=()
    [[ "$(id -u)" -ne 0 ]] && as_root=(sudo)
    "${as_root[@]}" apt-get update
    "${as_root[@]}" apt-get install -y "${missing[@]}"
}

# Without a GPU the processor draws every frame, and ModernGekko's default
# internal resolution (1920x1080, nine times the pixels of the console's own
# 640x528) makes that several times slower. On a first run, start at the
# console's resolution. An existing config.ini is the user's choice, so it is
# only mentioned.
use_light_resolution_without_gpu() {
    local config_file="$USER_DIRECTORY/config.ini"
    if [[ ! -f "$config_file" ]]; then
        mkdir -p "$USER_DIRECTORY"
        # Only the resolution: ModernGekko fills every other setting with its
        # default and rewrites the file in full the next time it saves.
        printf '%s\n' \
            '# Written by scripts/build_and_run_linux.sh because this PC has no GPU.' \
            '[Video]' \
            'resolution=640x528' > "$config_file"
        note "without a GPU the game starts at 640x528; raise resolution= in $config_file once there is one"
    elif ! grep -Eq '^resolution *= *640x528' "$config_file"; then
        note "to make the game lighter, set resolution=640x528 in $config_file"
    fi
}

# Pick the graphics backend that reaches the GPU. Sets GRAPHICS_BACKEND.
choose_graphics_backend() {
    step "Looking for GPU acceleration"
    # "|| true": with no working driver these tools fail, and that is an
    # answer here, not a reason for set -e to stop the script.
    local opengl_renderer vulkan_device_types
    opengl_renderer="$(glxinfo -B 2> /dev/null | sed -n 's/^OpenGL renderer string: //p' || true)"
    vulkan_device_types="$(vulkaninfo --summary 2> /dev/null |
        sed -n 's/^[[:space:]]*deviceType[[:space:]]*= //p' || true)"
    note "OpenGL renderer: ${opengl_renderer:-none}"
    note "Vulkan devices:  $(echo "${vulkan_device_types:-none}" | paste -sd ' ' -)"

    if [[ -n "${GRAPHICS_BACKEND:-}" ]]; then
        note "using GRAPHICS_BACKEND=$GRAPHICS_BACKEND as given"
        return
    fi
    if running_in_wsl && [[ "$opengl_renderer" == *D3D12* ]]; then
        # WSL reaches the Windows GPU driver through Mesa's Direct3D 12
        # layer, whose OpenGL driver is more mature than its Vulkan one.
        GRAPHICS_BACKEND=OGL
    elif grep -qE 'PHYSICAL_DEVICE_TYPE_(INTEGRATED|DISCRETE|VIRTUAL)_GPU' <<< "$vulkan_device_types"; then
        GRAPHICS_BACKEND=Vulkan
    elif [[ -n "$opengl_renderer" && "$opengl_renderer" != *llvmpipe* ]]; then
        GRAPHICS_BACKEND=OGL
    else
        # Software Vulkan (lavapipe) is what the game was tested with on a
        # machine without a GPU: it works, at a few frames per second.
        GRAPHICS_BACKEND=Vulkan
        note "no GPU acceleration found: the game will run, but very slowly"
        if running_in_wsl && [[ "$(uname -m)" == aarch64 ]]; then
            # On Windows-on-ARM laptops (Snapdragon) /dev/dxg exists but
            # /dev/dri/renderD128 never appears, so Mesa falls back to
            # software; updating drivers has not helped anyone so far.
            note "WSL2 on Windows-on-ARM laptops has not been able to use the GPU so far (microsoft/wslg issue 1470)"
        elif running_in_wsl && [[ ! -e /dev/dxg ]]; then
            note "WSL cannot see the GPU (/dev/dxg is missing): update Windows, the GPU driver and WSL"
        fi
        use_light_resolution_without_gpu
    fi
    note "graphics backend: $GRAPHICS_BACKEND"
}

download_template() {
    # Written only once every submodule is in place. Checking for the folder
    # alone is not enough: a download stopped halfway (Ctrl+C, the computer
    # going to sleep) leaves the folder with submodules missing.
    local download_finished_marker="$TEMPLATE_DIRECTORY/.git/hm-ap-recomp-download-finished"
    [[ -f "$download_finished_marker" ]] && return

    step "Downloading ModernGekko-Template and its submodules (a few hundred MB)"
    note "Keep the computer awake until this finishes; a sleeping PC stalls the download."
    if [[ ! -d "$TEMPLATE_DIRECTORY/.git" ]]; then
        git clone --no-checkout "$TEMPLATE_URL" "$TEMPLATE_DIRECTORY"
    fi
    git -C "$TEMPLATE_DIRECTORY" checkout --quiet "$TEMPLATE_COMMIT"
    git -C "$TEMPLATE_DIRECTORY" submodule sync --recursive --quiet

    # Options passed with -c reach the nested submodules too.
    local download_options=(-c http.version=HTTP/1.1) # HTTP/2 often cuts big fetches ("curl 92")
    local submodule
    for submodule in "${SUBMODULES_UNUSED_ON_LINUX[@]}"; do
        download_options+=(-c "submodule.$submodule.update=none")
    done
    local attempt
    for ((attempt = 1; attempt <= SUBMODULE_DOWNLOAD_ATTEMPTS; attempt++)); do
        # --force checks every submodule out again, which also restores the
        # files an interrupted earlier run never got to write.
        if git -C "$TEMPLATE_DIRECTORY" "${download_options[@]}" \
            submodule update --init --recursive --force; then
            touch "$download_finished_marker"
            return
        fi
        note "download attempt $attempt of $SUBMODULE_DOWNLOAD_ATTEMPTS failed"
    done
    fail "could not download ModernGekko-Template's submodules; check the internet connection and run the script again"
}

build_tools() {
    local build_directory="$TEMPLATE_DIRECTORY/lib/ModernGekko/build"
    [[ -x "$build_directory/moderngekko-port" && -x "$build_directory/moderngekko-run" ]] && return
    step "Building DolRecomp and ModernGekko (the longest step, 15 to 40 minutes)"
    make -C "$TEMPLATE_DIRECTORY" tools
}

# DolRecomp extracts Wii discs through Wiimms ISO Tools (wit), which it
# downloads into the template the first time ("make wit"). A Wii disc has
# several partitions; the game is in DATA, which is moved up to the top level
# so the folder looks like an extracted GameCube disc, as the template does.
extract_disc() {
    [[ -f "$EXTRACTED_DIRECTORY/sys/main.dol" ]] && return
    local disc_image="$1"
    [[ -n "$disc_image" ]] ||
        fail "the game is not extracted yet; give your disc image, for example: $0 \"/mnt/c/Users/you/Downloads/Harvest Moon - Animal Parade (USA).rvz\""
    # Accept a Windows path pasted from Explorer, such as C:\Users\you\game.rvz.
    if [[ "$disc_image" == [A-Za-z]:\\* ]] && command -v wslpath > /dev/null; then
        disc_image="$(wslpath -u "$disc_image")"
    fi
    [[ -f "$disc_image" ]] || fail "disc image not found: $disc_image"
    disc_image="$(realpath "$disc_image")"

    step "Setting up Wiimms ISO Tools, which read Wii discs"
    make -C "$TEMPLATE_DIRECTORY" wit

    step "Extracting your disc into $EXTRACTED_DIRECTORY"
    # Extract beside the final folder and rename it once done, so a stopped
    # extraction never looks finished; whatever it left behind is redone.
    local partial_directory="$EXTRACTED_DIRECTORY.partial"
    rm -rf "$partial_directory" "$EXTRACTED_DIRECTORY"
    (cd "$TEMPLATE_DIRECTORY" && "$DOLRECOMP" extract "$disc_image" "$partial_directory")
    if [[ ! -f "$partial_directory/sys/main.dol" && -f "$partial_directory/DATA/sys/main.dol" ]]; then
        mv "$partial_directory/DATA"/* "$partial_directory/"
        rmdir "$partial_directory/DATA"
    fi
    mv "$partial_directory" "$EXTRACTED_DIRECTORY"
}

# Checked on every run, so a wrong disc never reaches the recompiler.
verify_disc() {
    step "Checking that the disc is Harvest Moon: Animal Parade (USA)"
    python3 "$REPOSITORY_ROOT/tools/check_disc.py" "$EXTRACTED_DIRECTORY" > /dev/null ||
        fail "$EXTRACTED_DIRECTORY is not the RBIEE9 revision 1 disc; delete it and run again with the right image"
    note "OK"
}

# Dolphin settings that this game runs better with (config/RBIEE9/game_settings.ini): the loop of the
# operating system's idle thread that the runner skips, and the disc speed. Dolphin reads the game's
# own file in the user folder on top of its list for the game, so the file only has to be there.
# A file that is already there is the user's choice, so it is only mentioned.
install_game_settings() {
    local project_settings="$REPOSITORY_ROOT/config/RBIEE9/game_settings.ini"
    local user_settings="$USER_DIRECTORY/GameSettings/RBIEE9.ini"
    if [[ ! -f "$user_settings" ]]; then
        mkdir -p "$(dirname "$user_settings")"
        cp "$project_settings" "$user_settings"
        note "game settings written to $user_settings"
    elif ! cmp -s "$project_settings" "$user_settings"; then
        note "$user_settings is not the project's file; to use the project's settings, delete it"
    fi
}

run_game() {
    step "Starting the game"
    note "The first start also compiles the game module (a few minutes); later starts are immediate."
    note "The game is played with a Wii Remote and Nunchuk. Their keyboard and gamepad"
    note "mapping comes from Dolphin's defaults; check it in ModernGekko's settings."
    local extra_arguments=()
    read -r -a extra_arguments <<< "${EXTRA_RUN_ARGS:-}"
    # moderngekko-port directly rather than the template's 'make run', which
    # reconfigures CMake on every start. wit was already set up by extract_disc.
    "$TEMPLATE_DIRECTORY/lib/ModernGekko/build/moderngekko-port" run "$EXTRACTED_DIRECTORY" \
        --backend c --toolchain auto --output "$TEMPLATE_DIRECTORY/build/modules" \
        -- --graphics "$GRAPHICS_BACKEND" --user-dir "$USER_DIRECTORY" "${extra_arguments[@]}"
}

main() {
    local disc_image="${1:-}"
    check_system
    install_missing_packages
    choose_graphics_backend
    download_template
    build_tools
    extract_disc "$disc_image"
    verify_disc
    install_game_settings
    run_game
}

# Run only when executed, so a test can source this file and call one function.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
