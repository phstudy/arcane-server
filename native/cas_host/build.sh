#!/usr/bin/env bash
# Build the battle-engine helper: native/cas_host/out/cas_host (Android arm64, API 24+).
# It links against engine_stub.c's stand-in for libcas-battle.so, so no game file is needed here; the battle host
# (tools/battle_host.py setup takes out/cas_host when it exists) pairs it with the real library and bionic. The
# release workflow runs this same script and attaches the helper to the release.
#
# Usage: native/cas_host/build.sh
# Needs: the Android NDK (ANDROID_NDK, ANDROID_NDK_HOME, or the newest under the SDK's ndk/).
set -euo pipefail
cd "$(dirname "$0")"

SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}
[ -d "$SDK" ] || SDK=$HOME/Android/Sdk
NDK=${ANDROID_NDK:-${ANDROID_NDK_HOME:-$(ls -d "$SDK"/ndk/* 2>/dev/null | sort -V | tail -1)}}
CC=$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android24-clang 2>/dev/null | head -1)
[ -n "$CC" ] || { echo "Android NDK not found: set ANDROID_NDK" >&2; exit 1; }

OUT=out
rm -rf "$OUT"
mkdir -p "$OUT/stub"
"$CC" -O2 -Wall -Wextra -Werror -shared -fPIC -Wl,-soname,libcas-battle.so -o "$OUT/stub/libcas-battle.so" engine_stub.c
"$CC" -O2 -Wall -Wextra -Werror -o "$OUT/cas_host" cas_host.c -L"$OUT/stub" -lcas-battle
rm -rf "$OUT/stub"
echo "built $(pwd)/$OUT/cas_host"
