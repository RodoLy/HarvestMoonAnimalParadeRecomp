#!/usr/bin/env bash
# Updates this folder to a newer version of Harvest Moon: Animal Parade from its GitHub release
# (Linux and macOS). The launcher runs it when its Game tab's "Update to vX" is chosen
# (launcher/README.md); it does not need to be run by hand.
#
#   1. Downloads this computer's package of that version to .update/, printing "progress <0..1>"
#      lines that the launcher shows.
#   2. Unpacks it there and checks that it is that version (its version.txt).
#   3. Prints "apply": the launcher stops. From here on nothing more is printed; what happens goes
#      to UserData/Logs/update.log.
#   4. When the launcher has stopped, copies the new package over this folder. UserData (the saves,
#      the settings and the controls) is not in the package, so it stays as it is.
#   5. Starts the launcher again (a new tab in the browser). Its Play prepares the game again, since
#      the package changed.
#
# When something fails before step 3 it prints "error <message>" and nothing here changed.
#
# Actualiza esta carpeta a una versión más nueva desde GitHub (Linux y macOS). El launcher lo ejecuta
# cuando eliges "Actualizar a la vX"; no hace falta ejecutarlo a mano. Baja el paquete de esa versión
# a .update/ mostrando cuánto lleva, lo desempaca, comprueba que sea esa versión y dice "apply": el
# launcher se detiene, el paquete nuevo se copia encima de esta carpeta (UserData, con tus partidas y
# ajustes, no viene en el paquete y se queda) y el launcher se abre otra vez. Si algo falla antes de
# "apply", dice "error <mensaje>" y aquí no cambió nada.
#
# Usage / Uso:
#   ./update.sh <version> [launcher pid]      e.g. ./update.sh 0.2.4 12345
set -uo pipefail

# Bash reads a script as it runs it, and this file is replaced by the update: the rest runs from a
# copy. / Bash lee el script mientras lo ejecuta y este archivo se reemplaza: sigue desde una copia.
if [[ -z ${HMAP_UPDATE_ROOT:-} ]]; then
  root=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  copy=$(mktemp "${TMPDIR:-/tmp}/hmap-update.XXXXXX") || { echo 'error mktemp failed.'; exit 1; }
  cp "${BASH_SOURCE[0]}" "$copy"
  HMAP_UPDATE_ROOT=$root exec bash "$copy" "$@"
fi
root=$HMAP_UPDATE_ROOT
self=${BASH_SOURCE[0]}
trap 'rm -f "$self"' EXIT

version=${1:-}
launcher_pid=${2:-0}
repository=RodoLy/HarvestMoonAnimalParadeRecomp
staging="$root/.update"
logs="$root/UserData/Logs"
log="$logs/update.log"

note() {
  mkdir -p "$logs"
  printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$log"
}

fail() {
  note "Failed: $1"
  rm -rf "$staging"
  echo "error $1"
  exit 1
}

# x86_64 or aarch64 on Linux, as AnimalParadeLauncher is (the ELF header's machine); arm64 on macOS.
asset_name() {
  if [[ "$(uname -s)" == Darwin ]]; then
    echo 'HarvestMoonAnimalParade-macos-arm64.zip'
    return
  fi
  local machine
  machine=$(od -An -tx1 -j18 -N2 "$root/AnimalParadeLauncher" 2>/dev/null | tr -d ' \n')
  case "$machine" in
    3e00) echo 'HarvestMoonAnimalParade-linux-x86_64.tar.gz' ;;
    b700) echo 'HarvestMoonAnimalParade-linux-aarch64.tar.gz' ;;
    *) case "$(uname -m)" in
         aarch64|arm64) echo 'HarvestMoonAnimalParade-linux-aarch64.tar.gz' ;;
         *) echo 'HarvestMoonAnimalParade-linux-x86_64.tar.gz' ;;
       esac ;;
  esac
}

# ---------------------------------------------------------------------------------------------
# 1-3: download, unpack, check. Nothing in this folder changes yet.

[[ $version =~ ^[0-9]+(\.[0-9]+)+$ ]] || fail "Not a version: $version"
command -v curl > /dev/null || fail 'curl is needed to download the update. / Hace falta curl para bajar la actualización.'
asset=$(asset_name)
url="https://github.com/$repository/releases/download/v$version/$asset"

rm -rf "$staging"
mkdir -p "$staging" || fail "Could not write in $root. / No se pudo escribir en $root."
archive="$staging/$asset"
note "Downloading $url"
echo 'progress 0'

# curl's progress bar says how far it is ("####    45.3%", each one ending in a carriage return);
# its last line is how it ended. / La barra de curl dice cuánto lleva; su última línea, cómo terminó.
# If the launcher stops during the download, nobody reads these lines any more: this stops too.
trap 'rm -rf "$staging"; exit 1' PIPE
shown=-1
ended=''
last=''
while IFS= read -r -d $'\r' chunk || [[ -n $chunk ]]; do
  chunk=${chunk//$'\n'/ }
  if [[ $chunk =~ ^exit\ ([0-9]+) ]]; then
    ended=${BASH_REMATCH[1]}
  elif [[ $chunk =~ ([0-9]+)(\.[0-9])?%[[:space:]]*$ ]]; then
    # The download is most of the time; unpacking is the last 5%.
    percent=$(( 95 * 10#${BASH_REMATCH[1]} / 100 ))
    if (( percent != shown )); then
      shown=$percent
      printf 'progress 0.%02d\n' "$percent"
    fi
  elif [[ -n ${chunk// /} ]]; then
    last=$chunk
  fi
done < <(curl -fL --progress-bar --retry 2 -o "$archive" "$url" 2>&1; printf '\rexit %d\r' "$?")
if [[ $ended != 0 ]]; then
  [[ $last == *404* ]] &&
    fail "v$version has no package for this computer yet. / La v$version todavía no tiene paquete para esta computadora."
  fail "The download failed (${last:-curl $ended}). / No se pudo bajar."
fi

note 'Unpacking'
unpacked="$staging/package"
mkdir -p "$unpacked"
case "$asset" in
  *.tar.gz) tar -xzf "$archive" -C "$unpacked" || fail 'The download could not be unpacked. / No se pudo desempacar lo que se bajó.' ;;
  *.zip) { if command -v ditto > /dev/null; then ditto -x -k "$archive" "$unpacked"; else unzip -q "$archive" -d "$unpacked"; fi; } ||
           fail 'The download could not be unpacked. / No se pudo desempacar lo que se bajó.' ;;
esac
rm -f "$archive"
found=$(find "$unpacked" -maxdepth 3 -name version.txt -type f -print -quit)
[[ -n $found ]] || fail 'The download is not a package of the game. / Lo que se bajó no es un paquete del juego.'
package=$(dirname "$found")
got=$(tr -d '[:space:]' < "$found")
[[ $got == "v$version" ]] || fail "The download is $got, not v$version. / Lo que se bajó es la $got, no la v$version."
[[ -x $package/AnimalParadeLauncher ]] || fail 'The download has no AnimalParadeLauncher. / Lo que se bajó no trae AnimalParadeLauncher.'
echo 'progress 1'

# ---------------------------------------------------------------------------------------------
# 4-5: the launcher stops, the package goes over this folder, the launcher starts again. Whatever
# happens, it starts again at the end: with the new version, or with the old one if the copy failed.

echo 'apply'
trap - PIPE
exec >> "$log" 2>&1 < /dev/null
note "Putting v$version in place"
if (( launcher_pid > 0 )); then
  for _ in $(seq 120); do
    kill -0 "$launcher_pid" 2>/dev/null || break
    sleep 0.5
  done
fi
# -f: a file that cannot be written over (a program still running) is removed and written anew.
if cp -Rpf "$package/." "$root/"; then
  note "Now at v$version"
else
  note 'Failed: not every file could be copied.'
fi
rm -rf "$staging"
cd "$root" && nohup ./AnimalParadeLauncher > /dev/null 2>&1 &
