#!/usr/bin/env bash
# Copies the C and C++ libraries' development files of this computer (the one that builds the Linux
# package) into a folder: the package's Toolkit/sysroot. play.sh compiles the game against it, so a
# player's computer needs none of its own (libc6-dev, glibc-devel, a C++ compiler). That matters
# where they cannot be installed, as on a Steam Deck: SteamOS leaves out every header and its
# system is read-only.
#
# Copia los archivos de desarrollo de las bibliotecas de C y C++ de esta computadora (la que arma el
# paquete de Linux) a una carpeta: Toolkit/sysroot del paquete. play.sh compila el juego contra ella,
# así la computadora de quien juega no necesita los suyos (libc6-dev, glibc-devel, un compilador de
# C++). Importa donde no se pueden instalar, como en una Steam Deck: SteamOS no trae ningún
# encabezado y su sistema es de solo lectura.
#
# Usage / Uso (on Debian or Ubuntu, from the packages already installed):
#   packaging/unix/make-sysroot.sh <folder>
#
# What it takes / Lo que toma:
#   libc6, libc6-dev, linux-libc-dev     the C library: headers, startup files, libc.so and friends
#   libgcc-N-dev, libstdc++-N-dev        the compiler runtime and the C++ library of the computer's
#   libgcc-s1, libstdc++6                GCC N (clang uses them, as it does on any Linux)
# Only headers and libraries are kept (no documentation, translations or character set modules);
# the packages' copyright files go to <folder>/licenses.
#
# The game compiled against it needs that glibc or a newer one, as the precompiled archives built on
# the same computer already do. / El juego compilado así necesita esa glibc o una más nueva, igual
# que los archivos precompilados armados en la misma computadora.
set -euo pipefail

out=${1:?usage: make-sysroot.sh <folder>}
gcc_major=$(gcc -dumpversion | cut -d. -f1)
packages=(libc6 libc6-dev linux-libc-dev "libgcc-$gcc_major-dev" "libstdc++-$gcc_major-dev" libgcc-s1 libstdc++6)

rm -rf "$out"
mkdir -p "$out/usr/lib" "$out/usr/lib64" "$out/usr/include" "$out/licenses"
# The same layout as the system ("merged /usr"): /lib and /lib64 lead to /usr, so the paths the
# libraries' linker scripts name (/lib/<triple>/libc.so.6) are found inside the folder.
ln -s usr/lib "$out/lib"
ln -s usr/lib64 "$out/lib64"

for package in "${packages[@]}"; do
    dpkg -s "$package" > /dev/null 2>&1 || { echo "make-sysroot.sh: $package is not installed" >&2; exit 1; }
    while IFS= read -r path; do
        [[ -f $path || -L $path ]] || continue
        [[ -d $path && ! -L $path ]] && continue
        # /lib/... and /usr/lib/... are the same place.
        inside=${path#/}
        case "$inside" in
            lib/*|lib64/*) inside="usr/$inside" ;;
        esac
        case "$inside" in
            usr/include/*|usr/lib/*|usr/lib64/*) ;;
            *) continue ;;
        esac
        case "$inside" in
            */gconv/*|*/audit/*) continue ;;
        esac
        mkdir -p "$out/$(dirname "$inside")"
        cp -a "$path" "$out/$inside"
    done < <(dpkg -L "$package")
    cp "/usr/share/doc/$package/copyright" "$out/licenses/$package.txt" 2>/dev/null || true
done

# A link that names a path of this computer (/lib/<triple>/...) is made relative, so it leads to
# the copy in the folder and not to whatever the player's computer has there.
while IFS= read -r link; do
    target=$(readlink "$link")
    [[ $target == /* ]] || continue
    inside=${target#/}
    case "$inside" in
        lib/*|lib64/*) inside="usr/$inside" ;;
    esac
    ln -sfn "$(realpath -m -s --relative-to="$(dirname "$link")" "$out/$inside")" "$link"
done < <(find "$out/usr" -type l)

# Links to libraries of packages that were not taken (the sanitizers, OpenMP) lead nowhere: out.
find "$out" -xtype l -delete

echo "make-sysroot.sh: $(du -sh "$out" | cut -f1) in $out (gcc $gcc_major, $(dpkg-query -W -f='${Version}' libc6))"
