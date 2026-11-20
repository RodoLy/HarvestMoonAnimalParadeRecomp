#!/usr/bin/env bash
# Builds the launcher for Linux or macOS and puts it, with its page, in a package folder.
# Compila el launcher para Linux o macOS y lo pone, con su página, en la carpeta de un paquete.
#
#   launcher/build.sh <package folder>
#
# The result / El resultado:
#   <package>/AnimalParadeLauncher   the program (host/launcher_unix.cpp and host/launcher_core.cpp):
#                                    it serves the page to the computer's browser
#   <package>/Launcher/              its page (web/: index.html, launcher.js, the animals, the fonts)
#
# CXX picks the compiler (c++ by default). On Linux the C++ library is linked in, so the program
# runs on any distribution of the same processor.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
package=${1:?usage: launcher/build.sh <package folder>}
mkdir -p "$package"
compiler=${CXX:-c++}
flags=(-std=c++17 -O2 -pthread)
[[ "$(uname -s)" == Linux ]] && flags+=(-static-libstdc++ -static-libgcc)

"$compiler" "${flags[@]}" "$here/host/launcher_unix.cpp" "$here/host/launcher_core.cpp" -o "$package/AnimalParadeLauncher"
rm -rf "$package/Launcher"
cp -R "$here/web" "$package/Launcher"
echo "AnimalParadeLauncher and its page are in $package"
