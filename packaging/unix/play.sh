#!/usr/bin/env bash
# Builds Harvest Moon: Animal Parade from your own disc and starts it (Linux and macOS).
# Compila Harvest Moon: Animal Parade desde tu propio disco y lo inicia (Linux y macOS).
#
# The package has no game code in it. This script makes the game on your computer, the same way
# play.ps1 does on Windows:
#
#   1. The translator turns your main.dol into C++ (BuildWorkspace/generated, under a minute).
#   2. The compiler compiles that C++ together with WiiCompiled's runtime
#      (BuildWorkspace/native-build; the first time takes a while).
#   3. The game goes to Game/, its settings to UserData/Config.toml, and it starts.
#
# The next time only what changed is compiled again, so it starts much sooner.
#
# El paquete no trae código del juego. Este script hace el juego en tu computadora, igual que
# play.ps1 en Windows: el traductor convierte tu main.dol en C++, el compilador lo compila junto con
# el runtime de WiiCompiled, y el juego queda en Game/, con su configuración en
# UserData/Config.toml. La siguiente vez solo se compila lo que cambió.
#
# Usage / Uso:
#   ./play.sh [--disc IMAGE_OR_FOLDER] [--rebuild] [--no-start] [--progress]
#
#   --disc       Your disc image (.rvz, .iso, .wbfs, .wia or .ciso), or a folder Dolphin extracted
#                (with sys/main.dol, sys/fst.bin and files/). Asked for if left out, and remembered
#                in UserData/disc.txt after that.
#                Tu imagen del disco, o una carpeta extraída con Dolphin. Se pide si falta y se
#                recuerda en UserData/disc.txt.
#   --rebuild    Translate and compile again even if nothing changed. / Traducir y compilar otra vez.
#   --no-start   Build the game but do not start it. / Compilar el juego pero no iniciarlo.
#   --progress   Also print each step as a "progress <0..1> <step>" line, as RecompLauncher's setup
#                step reads them. / Además escribe cada paso como una línea "progress <0..1> <paso>".
#
# What the computer needs / Lo que necesita la computadora:
#   Linux: a Vulkan driver to play. The package brings its own compiler, CMake and Ninja, and the
#          C and C++ libraries' files to compile against (Toolkit/sysroot), so nothing has to be
#          installed, not even on a Steam Deck. Without Toolkit/sysroot (built from the sources),
#          the computer's own: libc6-dev on Debian and Ubuntu, glibc-devel on Fedora.
#   macOS: Apple's command line tools (xcode-select --install), for the compiler.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
toolkit=$root/Toolkit
workspace=$root/BuildWorkspace
game=$root/Game
user_data=$root/UserData
remembered_disc=$user_data/disc.txt
extracted=$root/Disc
project=projects/animal-parade/recomp.yml
game_id=RBIEE9

disc=""
rebuild=0
no_start=0
progress=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --disc) disc=${2:-}; shift 2 ;;
        --rebuild) rebuild=1; shift ;;
        --no-start) no_start=1; shift ;;
        --progress) progress=1; shift ;;
        -h|--help) sed -n '2,37p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "play.sh: unknown option / opción desconocida: $1" >&2; exit 2 ;;
    esac
done

# The launcher reads these lines to show the steps (launcher/host): keep their beginnings.
step() {
    if [[ "$progress" -eq 1 ]]; then
        # How far along each step starts; compiling is most of the time the first time.
        local share=""
        case "$1" in
            'Extracting the disc image'*) share=0.02 ;;
            'Translating your main.dol'*) share=0.10 ;;
            'The translation is current') share=0.20 ;;
            'Configuring the build') share=0.25 ;;
            'Compiling'*) share=0.30 ;;
            'Copying the game'*) share=0.97 ;;
        esac
        [[ -n "$share" ]] && printf 'progress %s %s\n' "$share" "$1"
    fi
    printf '\n== %s\n   %s\n' "$1" "$2"
}

fail() {
    printf 'play.sh: %s\n' "$*" >&2
    exit 1
}

system=$(uname -s)
case "$(uname -m)" in
    x86_64|amd64) processor=x86_64 ;;
    aarch64|arm64) processor=aarch64 ;;
    *) fail "This processor ($(uname -m)) is not supported. / Este procesador no está soportado." ;;
esac

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# The size and date of a file, to know whether a disc image is the one extracted before.
file_identity() {
    if [[ "$system" == Darwin ]]; then stat -f '%z|%m' "$1"; else stat -c '%s|%Y' "$1"; fi
}

# ---------------------------------------------------------------- the disc

# The folder itself, or the DATA folder inside it: Dolphin writes a Wii disc both ways.
find_disc_root() {
    local candidate
    for candidate in "$1" "$1/DATA"; do
        if [[ -f "$candidate/sys/main.dol" && -f "$candidate/sys/fst.bin" && -d "$candidate/files" ]]; then
            (cd "$candidate" && pwd)
            return 0
        fi
    done
    return 1
}

read_disc_id() {
    [[ -f "$1/sys/boot.bin" ]] && head -c 6 "$1/sys/boot.bin" | tr -d '\0' || true
}

# Asks for the disc image: a file window where there is one, the terminal otherwise.
choose_disc_image() {
    local title="Harvest Moon: Animal Parade (RBIEE9) - disc image / imagen del disco" chosen=""
    if [[ "$system" == Darwin ]]; then
        chosen=$(osascript -e "POSIX path of (choose file with prompt \"$title\")" 2>/dev/null) || true
    elif command -v zenity >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
        chosen=$(zenity --file-selection --title="$title" \
            --file-filter='Wii disc images | *.rvz *.iso *.wbfs *.wia *.ciso' --file-filter='All files | *' 2>/dev/null) || true
    elif command -v kdialog >/dev/null 2>&1 && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
        chosen=$(kdialog --title "$title" --getopenfilename "$HOME" '*.rvz *.iso *.wbfs *.wia *.ciso' 2>/dev/null) || true
    elif [[ -t 0 ]]; then
        read -r -p "Disc image or extracted folder / Imagen del disco o carpeta extraída: " chosen
    fi
    [[ -n "$chosen" ]] || fail "No disc image was chosen. / No se eligió la imagen del disco."
    printf '%s\n' "$chosen"
}

# Extracts the image's data partition to Disc/DATA once. Disc/extracted-from.txt records which
# image (path, size, date) it came from, so the same image is not extracted again; a half-finished
# extraction has no record and is redone.
expand_disc_image() {
    local image=$1 source record=$extracted/extracted-from.txt data_root=$extracted/DATA
    source="$image|$(file_identity "$image")"
    if [[ -f "$record" && "$(cat "$record")" == "$source" ]] && find_disc_root "$data_root" >/dev/null; then
        printf '%s\n' "$data_root"
        return
    fi
    step 'Extracting the disc image (once; a few minutes)' 'Extrayendo la imagen del disco (una sola vez; unos minutos)' >&2
    rm -rf "$extracted"
    mkdir -p "$extracted"
    local nodtool=$toolkit/nodtool
    [[ -x "$nodtool" ]] || fail "The disc tool is missing: $nodtool / Falta la herramienta del disco."
    "$nodtool" extract "$image" "$data_root" -q >&2 || fail 'The disc image could not be extracted. / No se pudo extraer la imagen.'
    printf '%s\n' "$source" > "$record"
    printf '%s\n' "$data_root"
}

# macOS marks every file of a download as coming from the internet, and then refuses to start the
# package's own programs (the translator, the disc tool) because they are not signed. They are the
# package's, so the mark comes off them (as play.ps1 does on Windows).
if [[ "$system" == Darwin ]]; then
    xattr -dr com.apple.quarantine "$root" 2>/dev/null || true
fi

mkdir -p "$user_data"
if [[ -z "$disc" && -f "$remembered_disc" ]]; then
    disc=$(head -n 1 "$remembered_disc" | tr -d '\r')
fi
[[ -n "$disc" ]] || disc=$(choose_disc_image)
[[ -e "$disc" ]] || fail "$disc does not exist. / $disc no existe."
disc=$(cd "$(dirname "$disc")" && pwd)/$(basename "$disc")
if [[ -f "$disc" ]]; then
    disc_root=$(find_disc_root "$(expand_disc_image "$disc")") || disc_root=""
else
    disc_root=$(find_disc_root "$disc") || disc_root=""
fi
[[ -n "$disc_root" ]] || fail "$disc is not a disc image nor a folder with sys/main.dol, sys/fst.bin and files/. / $disc no es una imagen de disco ni una carpeta con sys/main.dol, sys/fst.bin y files/."
disc_id=$(read_disc_id "$disc_root")
if [[ -n "$disc_id" && "$disc_id" != "$game_id" ]]; then
    fail "This disc is $disc_id; the package is for $game_id (Harvest Moon: Animal Parade, USA). / Este disco es $disc_id; el paquete es para $game_id."
fi
printf '%s\n' "$disc" > "$remembered_disc"
main_dol=$disc_root/sys/main.dol
echo "Disc / Disco: $disc_root"

# ---------------------------------------------------------------- the tools

# The package's own compiler, CMake and Ninja (Toolkit/toolchain), or the computer's when the
# package has none. On macOS the compiler is always Apple's.
toolchain_bin=$toolkit/toolchain/bin
find_tool() {
    if [[ -x "$toolchain_bin/$1" ]]; then printf '%s\n' "$toolchain_bin/$1"
    elif command -v "$1" >/dev/null 2>&1; then command -v "$1"
    else return 1; fi
}
if [[ "$system" == Darwin ]]; then
    xcrun --find clang >/dev/null 2>&1 ||
        fail "Apple's command line tools are missing: run xcode-select --install / Faltan las herramientas de línea de comandos de Apple: corre xcode-select --install"
    cc=$(xcrun --find clang)
    cxx=$(xcrun --find clang++)
else
    cc=$(find_tool clang) || fail 'No C compiler (clang). / No hay compilador de C (clang).'
    cxx=$(find_tool clang++) || fail 'No C++ compiler (clang++). / No hay compilador de C++ (clang++).'
fi
# The macOS package keeps CMake as Kitware ships it (Toolkit/toolchain/cmake/bin/cmake).
if [[ -x "$toolkit/toolchain/cmake/bin/cmake" ]]; then cmake=$toolkit/toolchain/cmake/bin/cmake
else cmake=$(find_tool cmake) || fail 'CMake is missing. / Falta CMake.'; fi
ninja=$(find_tool ninja) || fail 'Ninja is missing. / Falta Ninja.'

# The translator: the package's own program, or, when building from the sources, dotnet with
# TRANSLATOR_DLL (Translator.Cli.dll).
translator() {
    if [[ -x "$toolkit/translator/Translator.Cli" ]]; then
        "$toolkit/translator/Translator.Cli" "$@"
    elif [[ -n "${TRANSLATOR_DLL:-}" ]]; then
        dotnet "$TRANSLATOR_DLL" "$@"
    else
        fail "The translator is missing: $toolkit/translator/Translator.Cli / Falta el traductor."
    fi
}

# Linux: the package's compiler compiles against the package's own C and C++ libraries
# (packaging/unix/make-sysroot.sh), the same ones its precompiled archives were built with, so the
# computer needs no development files (SteamOS has none, and cannot easily get them).
sysroot=''
if [[ "$system" == Linux && "$cc" == "$toolchain_bin/"* && -f "$toolkit/sysroot/usr/include/stdio.h" ]]; then
    sysroot=$toolkit/sysroot
elif [[ "$system" == Linux && ! -f /usr/include/stdio.h ]]; then
    fail 'The C library headers are missing. Debian, Ubuntu: sudo apt install libc6-dev; Fedora: sudo dnf install glibc-devel / Faltan los encabezados de la biblioteca de C (mismos comandos).'
fi

# The same three knobs as play.ps1: a translated file takes about half a GB in clang, so the
# compile jobs are capped by memory as well as by processors.
if [[ "$system" == Darwin ]]; then
    processors=$(sysctl -n hw.ncpu)
    memory_gib=$(( $(sysctl -n hw.memsize) / 1073741824 ))
else
    processors=$(nproc)
    memory_gib=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1048576 ))
fi
(( memory_gib >= 1 )) || memory_gib=1
translator_threads=$(( processors < 16 ? processors : 16 ))
translated_jobs=$(( (memory_gib - 2) * 2 ))
(( translated_jobs > processors )) && translated_jobs=$processors
(( translated_jobs >= 1 )) || translated_jobs=1
global_jobs=$(( translated_jobs > processors ? translated_jobs : processors ))
# x86-64: the newer instructions (v3: AVX2) only where the processor has them.
cpu_profile=v2
if [[ "$processor" == x86_64 && "$system" == Linux ]] && grep -qw avx2 /proc/cpuinfo && grep -qw bmi2 /proc/cpuinfo &&
    grep -qw fma /proc/cpuinfo; then
    cpu_profile=v3
elif [[ "$processor" == x86_64 && "$system" == Darwin ]] && sysctl -n machdep.cpu.leaf7_features 2>/dev/null | grep -qw AVX2; then
    cpu_profile=v3
fi

# ---------------------------------------------------------------- the build

generated=$workspace/generated
functions=$generated/functions
metadata=$generated/base_translation_metadata.json
sources=$generated/base_translation_sources.bin
shards=$generated/build_shards
build=$workspace/native-build
stamp=$generated/translated-from.txt
dol_sha=$(sha256_of "$main_dol")

export RECOMP_RBIEE9_DOL=$main_dol
cd "$workspace"

translated=0
if [[ -f "$shards/shards.cmake" && -f "$stamp" && "$(cat "$stamp")" == "$dol_sha" ]]; then
    translated=1
    # The project (recomp.yml, MAP.txt, the natives' addresses) decides what is translated, so a
    # newer project file translates again.
    newer=$(find "$workspace/projects/animal-parade" -type f -newer "$stamp" | head -n 1)
    if [[ -n "$newer" ]]; then
        echo "Project changed ($(basename "$newer")); translating again / El proyecto cambió; se traduce otra vez"
        translated=0
    fi
fi
if [[ "$rebuild" -eq 1 || "$translated" -eq 0 ]]; then
    step 'Translating your main.dol into C++' 'Traduciendo tu main.dol a C++'
    rm -f "$stamp"
    mkdir -p "$generated"
    translator translate-recursive 0x80004050 --project "$project" \
        --outdir "$functions" --output-metadata "$metadata" \
        --production-source-bundle "$sources" --no-function-files --prune-stale \
        --threads "$translator_threads"
    translator generate-data-init --project "$project"
    translator emit-build-shards --project "$project" --base-metadata "$metadata" \
        --base-functions-dir "$functions" \
        --native-source-dir "$workspace/projects/animal-parade/native" --out "$shards"
    printf '%s\n' "$dol_sha" > "$stamp"
else
    step 'The translation is current' 'La traducción está al día'
fi
grep -q 'MKW_TRANSLATED_GUEST_REGION 3' "$shards/shards.cmake" ||
    fail 'The translation was not made for a foreign game (region 3); the translator patch is missing.'

[[ "$rebuild" -eq 1 ]] && rm -rf "$build"
# A runtime or aurora file newer than the last configuration (a fix copied into BuildWorkspace)
# configures again; what was compiled is kept.
cache=$build/CMakeCache.txt
# A build configured with other C libraries (before the package had its own, or the folder was
# moved) configures again.
if [[ -f "$cache" ]] && [[ "$(sed -n 's/^CMAKE_SYSROOT:[A-Z]*=//p' "$cache")" != "$sysroot" ]]; then
    echo "The C libraries changed; configuring again / Cambiaron las bibliotecas de C; se configura otra vez"
    rm -f "$cache"
fi
if [[ -f "$cache" ]]; then
    changed=$(find "$workspace/runtime" "$workspace/aurora-main/lib" "$workspace/aurora-main/include" \
        -type f -newer "$cache" 2>/dev/null | head -n 1)
    if [[ -n "$changed" ]]; then
        echo "Sources changed ($(basename "$changed")); configuring again / Cambió el código; se configura otra vez"
        rm -f "$cache"
    fi
fi
if [[ ! -f "$cache" ]]; then
    step 'Configuring the build' 'Configurando la compilación'
    configure=(-S "$workspace/runtime" -B "$build" -G Ninja
        -DCMAKE_BUILD_TYPE=Release
        -DCMAKE_C_COMPILER="$cc" -DCMAKE_CXX_COMPILER="$cxx" -DCMAKE_ASM_COMPILER="$cc"
        -DCMAKE_MAKE_PROGRAM="$ninja"
        -DMKW_TRANSLATED_COMPILE_JOBS="$translated_jobs")
    [[ "$processor" == x86_64 ]] && configure+=(-DMKW_X86_CPU_PROFILE="$cpu_profile")
    # macOS: as WiiCompiled's own local-build-macos.command, for this Mac's processor, with SDL
    # built from its source.
    if [[ "$system" == Darwin ]]; then
        configure+=(-DCMAKE_OSX_ARCHITECTURES="$(uname -m)" -DCMAKE_OSX_DEPLOYMENT_TARGET=12.0
            -DCMAKE_OSX_SYSROOT="$(xcrun --show-sdk-path)" -DAURORA_SDL3_PROVIDER=vendor)
    fi
    # The package's own linker and archiver go with its own compiler.
    if [[ "$cc" == "$toolchain_bin/"* ]]; then
        configure+=(-DCMAKE_AR="$toolchain_bin/llvm-ar" -DCMAKE_RANLIB="$toolchain_bin/llvm-ranlib"
            -DCMAKE_LINKER="$toolchain_bin/ld.lld" -DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld)
    fi
    [[ -n "$sysroot" ]] && configure+=(-DCMAKE_SYSROOT="$sysroot")
    # The precompiled aurora and libraries, made with the same compiler (the package's), save most
    # of the first build. Without them aurora is compiled here too.
    if [[ -f "$workspace/NativePrebuilt/native_prebuilt.cmake" ]]; then
        configure+=(-DMKW_NATIVE_PREBUILT_DIR="$workspace/NativePrebuilt")
    fi
    "$cmake" "${configure[@]}"
fi

step 'Compiling (the first time takes a while)' 'Compilando (la primera vez tarda un rato)'
"$cmake" --build "$build" --target WiiCompiled --parallel "$global_jobs"

# ---------------------------------------------------------------- the game folder

step 'Copying the game to Game/' 'Copiando el juego a Game/'
mkdir -p "$game"
cp -f "$build/WiiCompiled" "$game/AnimalParade"
for name in dsp_coef.bin initial_pipeline_cache.db cacert.pem noshaders.zip; do
    [[ -f "$build/$name" ]] && cp -f "$build/$name" "$game/"
done
for name in config wii_bootstrap; do
    [[ -d "$build/$name" ]] && cp -Rf "$build/$name" "$game/"
done

# portable.txt next to this script makes the runtime keep its settings, saves and logs in
# UserData/. The disc's folder goes to dvd_root in [paths].
config=$user_data/Config.toml
escaped=$(printf '%s' "$disc_root" | sed 's/\\/\\\\/g; s/"/\\"/g')
if [[ -f "$config" ]]; then
    if grep -qE '^[[:space:]]*dvd_root[[:space:]]*=' "$config"; then
        awk -v line="dvd_root = \"$escaped\"" '/^[[:space:]]*dvd_root[[:space:]]*=/ {print line; next} {print}' "$config" > "$config.new"
    elif grep -qE '^\[paths\][[:space:]]*$' "$config"; then
        awk -v line="dvd_root = \"$escaped\"" '{print} /^\[paths\][[:space:]]*$/ {print line}' "$config" > "$config.new"
    else
        { cat "$config"; printf '\n[paths]\ndvd_root = "%s"\n' "$escaped"; } > "$config.new"
    fi
    mv -f "$config.new" "$config"
else
    printf '[paths]\ndvd_root = "%s"\n' "$escaped" > "$config"
fi

echo
echo "Done / Listo: $game/AnimalParade"
if [[ "$no_start" -eq 0 ]]; then
    cd "$game"
    nohup ./AnimalParade >/dev/null 2>&1 &
fi
