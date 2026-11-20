#!/usr/bin/env bash
# Builds the Android version of Harvest Moon: Animal Parade from your own disc, on Linux.
# Compila la versión de Android de Harvest Moon: Animal Parade desde tu propio disco, en Linux.
#
# Needs the Linux (x86-64) package, already used once to prepare the game (./play.sh or the
# launcher), and the Android add-on unpacked into the same folder. The same steps as
# build-android.ps1 on Windows:
#   1. translates your main.dol again for the Android build (Android/BuildWorkspace/generated);
#   2. compiles it with the add-on's Android NDK for 64-bit ARM (the first time takes a while);
#   3. makes AnimalParade.apk, signed with a key of your own (UserData/android-signing.pfx: keep
#      it, so the next build installs over this one and keeps the saves);
#   4. with a device connected over USB with USB debugging on, installs the app and copies your
#      disc's files to it (once).
#
# Hace falta el paquete de Linux, ya usado una vez para preparar el juego, y el complemento de
# Android descomprimido en la misma carpeta. Mismos pasos que build-android.ps1 en Windows.
#
# Usage / Uso: ./build-android.sh [--rebuild] [--no-install] [--disc FOLDER]
#   --disc   a disc folder already unpacked (with sys/main.dol and files/), instead of the one the
#            computer version was prepared from / una carpeta del disco ya desempacada
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
toolkit=$root/Toolkit
android=$root/Android
workspace=$android/BuildWorkspace
user_data=$root/UserData
project=projects/animal-parade/recomp.yml
package_name=io.github.hmaprecomp.animalparade
apk=$root/AnimalParade.apk

rebuild=0
install=1
disc_folder=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --rebuild) rebuild=1; shift ;;
        --no-install) install=0; shift ;;
        --disc) disc_folder=${2:?--disc needs a folder}; shift 2 ;;
        -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "build-android.sh: unknown option / opción desconocida: $1" >&2; exit 2 ;;
    esac
done

step() { printf '\n== %s\n   %s\n' "$1" "$2"; }
fail() { printf 'build-android.sh: %s\n' "$*" >&2; exit 1; }
sha256_of() { sha256sum "$1" | cut -d' ' -f1; }

[[ -f "$workspace/runtime/CMakeLists.txt" ]] ||
    fail 'The Android add-on is not in this folder (Android/BuildWorkspace is missing). Unpack it next to play.sh. / El complemento de Android no está en esta carpeta.'
if [[ -f "$android/version.txt" && -f "$root/version.txt" && "$(cat "$android/version.txt")" != "$(cat "$root/version.txt")" ]]; then
    echo "Warning: the Android add-on is $(cat "$android/version.txt") and the package $(cat "$root/version.txt"); use the add-on of the same version. / Aviso: versiones distintas." >&2
fi

# The disc the computer version was prepared from (play.sh remembers it in UserData/disc.txt).
find_disc_root() {
    local candidate
    for candidate in "$1" "$1/DATA"; do
        if [[ -f "$candidate/sys/main.dol" && -d "$candidate/files" ]]; then
            (cd "$candidate" && pwd)
            return 0
        fi
    done
    return 1
}
disc_root=""
if [[ -n "$disc_folder" ]]; then
    disc_root=$(find_disc_root "$disc_folder") || fail "No unpacked disc in $disc_folder (it needs sys/main.dol and files/). / No hay un disco desempacado ahí."
elif [[ -f "$user_data/disc.txt" ]]; then
    disc=$(head -n 1 "$user_data/disc.txt" | tr -d '\r')
    if [[ -f "$disc" ]]; then disc_root=$(find_disc_root "$root/Disc/DATA") || disc_root=""
    elif [[ -d "$disc" ]]; then disc_root=$(find_disc_root "$disc") || disc_root=""; fi
fi
[[ -n "$disc_root" ]] ||
    fail 'Prepare the game on this computer first (./play.sh or the launcher): the Android build uses the same disc. / Prepara primero el juego en esta computadora: la versión de Android usa el mismo disco.'
main_dol=$disc_root/sys/main.dol
echo "Disc / Disco: $disc_root"

ndk=$android/ndk
ndk_bin=$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin
cmake=$toolkit/toolchain/bin/cmake
ninja=$toolkit/toolchain/bin/ninja
translator=$toolkit/translator/Translator.Cli
apk_pack=$android/ApkPack/ApkPack
shell_apk=$android/AnimalParade-shell.apk
adb=$android/platform-tools/adb
for required in "$ndk/build/cmake/android.toolchain.cmake" "$ndk_bin/llvm-strip" "$cmake" "$ninja" "$translator" "$apk_pack" "$shell_apk"; do
    [[ -e "$required" ]] || fail "A package file is missing: $required / Falta un archivo del paquete."
done

processors=$(nproc)
memory_gib=$(( $(awk '/^MemTotal:/ {print $2}' /proc/meminfo) / 1048576 ))
(( memory_gib >= 1 )) || memory_gib=1
translator_threads=$(( processors < 16 ? processors : 16 ))
translated_jobs=$(( (memory_gib - 2) * 2 ))
(( translated_jobs > processors )) && translated_jobs=$processors
(( translated_jobs >= 1 )) || translated_jobs=1
global_jobs=$(( translated_jobs > processors ? translated_jobs : processors ))

# ---------------------------------------------------------------- the build

generated=$workspace/generated
functions=$generated/functions
metadata=$generated/base_translation_metadata.json
sources=$generated/base_translation_sources.bin
shards=$generated/build_shards
build=$workspace/build
stamp=$generated/translated-from.txt
dol_sha=$(sha256_of "$main_dol")

export RECOMP_RBIEE9_DOL=$main_dol
cd "$workspace"
if [[ "$rebuild" -eq 1 || ! -f "$shards/shards.cmake" || ! -f "$stamp" || "$(cat "$stamp")" != "$dol_sha" ]]; then
    step 'Translating your main.dol into C++' 'Traduciendo tu main.dol a C++'
    rm -f "$stamp"
    mkdir -p "$generated"
    "$translator" translate-recursive 0x80004050 --project "$project" \
        --outdir "$functions" --output-metadata "$metadata" \
        --production-source-bundle "$sources" --no-function-files --prune-stale \
        --threads "$translator_threads"
    "$translator" generate-data-init --project "$project"
    "$translator" emit-build-shards --project "$project" --base-metadata "$metadata" \
        --base-functions-dir "$functions" \
        --native-source-dir "$workspace/projects/animal-parade/native" --out "$shards"
    printf '%s\n' "$dol_sha" > "$stamp"
else
    step 'The translation is current' 'La traducción está al día'
fi

[[ "$rebuild" -eq 1 ]] && rm -rf "$build"
if [[ ! -f "$build/CMakeCache.txt" ]]; then
    step 'Configuring the Android build' 'Configurando la compilación de Android'
    # The dependencies' sources come with the add-on, so nothing is downloaded.
    mapfile -t extra < <(grep -v '^[[:space:]]*$' "$android/configure-flags.txt")
    "$cmake" -S "$workspace/runtime" -B "$build" -G Ninja \
        -DCMAKE_MAKE_PROGRAM="$ninja" \
        -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
        -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-30 -DANDROID_STL=c++_static \
        -DCMAKE_BUILD_TYPE=Release \
        -DFETCHCONTENT_BASE_DIR="$workspace/Dependencies" -DFETCHCONTENT_FULLY_DISCONNECTED=ON \
        -DMKW_ANDROID_NOD_DIR="$android/nod" \
        -DMKW_TRANSLATED_COMPILE_JOBS="$translated_jobs" "${extra[@]}"
fi
step 'Compiling for Android (the first time takes a while)' 'Compilando para Android (la primera vez tarda un rato)'
"$cmake" --build "$build" --target WiiCompiled --parallel "$global_jobs"

# ---------------------------------------------------------------- the app

step 'Making the app (AnimalParade.apk)' 'Armando la app (AnimalParade.apk)'
stage=$build/apk
rm -rf "$stage"
mkdir -p "$stage/game"
for name in dsp_coef.bin initial_pipeline_cache.db cacert.pem noshaders.zip; do
    if [[ -f "$build/$name" ]]; then cp -f "$build/$name" "$stage/game/"; fi
done
for name in config wii_bootstrap; do
    if [[ -d "$build/$name" ]]; then cp -R "$build/$name" "$stage/game/"; fi
done
"$ndk_bin/llvm-strip" --strip-unneeded -o "$stage/libmain.so" "$build/libmain.so"
mkdir -p "$user_data"
"$apk_pack" --shell "$shell_apk" --lib "arm64-v8a=$stage/libmain.so" --assets "$stage/game" \
    --key "$user_data/android-signing.pfx" --out "$apk"
echo "Done / Listo: $apk"

# ---------------------------------------------------------------- the device

[[ "$install" -eq 1 && -x "$adb" ]] || exit 0
"$adb" start-server >/dev/null 2>&1 || true
mapfile -t devices < <("$adb" devices | tail -n +2 | grep -P '\tdevice$' || true)
if [[ ${#devices[@]} -eq 0 ]]; then
    echo
    echo 'No device connected with USB debugging: install AnimalParade.apk and copy the disc yourself (README-Android.txt).'
    echo 'No hay un dispositivo conectado con la depuración USB: instala AnimalParade.apk y copia el disco tú (README-Android.txt).'
    exit 0
fi
[[ ${#devices[@]} -eq 1 ]] || { echo 'More than one device is connected; leave only one. / Hay más de un dispositivo conectado; deja solo uno.'; exit 0; }
step 'Installing the app on the device' 'Instalando la app en el dispositivo'
"$adb" install -r "$apk"
"$adb" shell am start -n "$package_name/.SetupActivity" >/dev/null
sleep 3
device_folder=/sdcard/Android/data/$package_name/files
if [[ "$("$adb" shell "test -f $device_folder/Disc/DATA/sys/main.dol && echo yes" | tr -d '\r')" != yes ]]; then
    step 'Copying your disc to the device (once; a few minutes)' 'Copiando tu disco al dispositivo (una sola vez; unos minutos)'
    "$adb" shell "mkdir -p $device_folder/Disc" >/dev/null
    "$adb" push "$disc_root" "$device_folder/Disc/"
    leaf=$(basename "$disc_root")
    [[ "$leaf" == DATA ]] || "$adb" shell "mv '$device_folder/Disc/$leaf' $device_folder/Disc/DATA" >/dev/null
fi
"$adb" shell am start -n "$package_name/.SetupActivity" >/dev/null
echo
echo 'The game is on the device. / El juego está en el dispositivo.'
