#!/usr/bin/env bash
# Copies the parts of an Android NDK that build-android needs, for 64-bit ARM and Android 11
# (API 30), into a new folder: the compiler, the linker and the archiver, the C and C++ headers and
# libraries for that one target, and the CMake toolchain file. The debugger, the other processors,
# the other API levels, Python and the sources stay out (about a fifth of the NDK is kept).
#
# Copia del NDK de Android solo lo que build-android usa, para ARM de 64 bits y Android 11.
#
# Usage: prune-ndk.sh NDK_DIR OUT_DIR HOST_TAG   (HOST_TAG: windows-x86_64 or linux-x86_64)
set -euo pipefail
ndk=$1
out=$2
host=$3
api=30

[[ -f "$ndk/build/cmake/android.toolchain.cmake" ]] || { echo "prune-ndk.sh: $ndk is not an NDK" >&2; exit 1; }
rm -rf "$out"
mkdir -p "$out/toolchains/llvm/prebuilt"
cp -a "$ndk/source.properties" "$ndk/build" "$ndk/meta" "$out/"
# Crypto++ uses the NDK's cpufeatures library (a header and one C file).
mkdir -p "$out/sources/android"
cp -a "$ndk/sources/android/cpufeatures" "$out/sources/android/"
[[ -f "$ndk/NOTICE" ]] && cp -a "$ndk/NOTICE" "$out/"
cp -a "$ndk/toolchains/llvm/prebuilt/$host" "$out/toolchains/llvm/prebuilt/"
prebuilt=$out/toolchains/llvm/prebuilt/$host

# Tools that are not the compiler, the linker or the binary utilities.
rm -rf "$prebuilt/python3" "$prebuilt/share" "$prebuilt/musl" "$prebuilt/lib/python3"* "$prebuilt/lib64/python3"*
find "$prebuilt/bin" -maxdepth 1 \( -name 'lldb*' -o -name 'clang-tidy*' -o -name 'clangd*' -o -name 'clang-format*' \
    -o -name 'clang-check*' -o -name 'clang-apply-replacements*' -o -name 'clang-include-*' -o -name 'run-clang-tidy*' \
    -o -name 'git-clang-format*' -o -name 'scan-*' -o -name 'llvm-bolt*' -o -name 'perf2bolt*' -o -name 'bolt*' \
    -o -name 'i686-*' -o -name 'x86_64-linux-android*' -o -name 'armv7a-*' -o -name 'riscv64-*' \) -exec rm -rf {} +

# Runtime libraries of the compiler: only 64-bit ARM, and no sanitizers.
find "$prebuilt/lib/clang" -path '*/lib/linux/*' \( -name '*i686*' -o -name '*x86_64*' -o -name '*arm-*' \
    -o -name '*armhf*' -o -name '*riscv64*' -o -name '*san*' -o -name '*scudo*' -o -name 'arm' -o -name 'i386' \
    -o -name 'x86_64' -o -name 'riscv64' \) -prune -exec rm -rf {} +

# The C library and the C++ library for aarch64-linux-android at API 30 only.
sysroot=$prebuilt/sysroot/usr/lib
for triple in arm-linux-androideabi i686-linux-android x86_64-linux-android riscv64-linux-android; do
    rm -rf "${sysroot:?}/$triple"
done
find "$sysroot/aarch64-linux-android" -mindepth 1 -maxdepth 1 -type d -regex '.*/[0-9]+' ! -name "$api" -exec rm -rf {} +

du -sh "$out"
