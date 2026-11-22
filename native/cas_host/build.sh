#!/usr/bin/env bash
# Build the battle-engine helper for an x86_64 Linux battle host: native/cas_host/out/
#   qemu-aarch64-static          QEMU user-mode emulator (static, from Ubuntu 24.04 qemu-user-static)
#   sysroot/system/bin/linker64  bionic dynamic linker      } pulled from an arm64 Android device/emulator
#   sysroot/system/lib64/*.so    libc, libm, libdl, liblog,  } (adb), the engine from the game's arm64 split
#                                libc++, ld-android, libdl_android, libcas-battle.so
#   sysroot/system/bin/cas_host  the helper (cas_host.c, NDK)
# The battle server runs: out/qemu-aarch64-static -L out/sysroot out/sysroot/system/bin/cas_host
# (arcane_server.battle_server.engine.EngineCommand). Android binaries stay out of git (out/ is ignored).
#
# Usage: native/cas_host/build.sh <split_config.arm64_v8a.apk | base.apk with lib/arm64-v8a> \
#          [--adb-serial SERIAL]   arm64 device or emulator to copy bionic from (default: the only one)
#          [--docker-host URL]     where to run the throw-away container that provides qemu (e.g. ssh://battle-host)
# Needs: Android NDK (ANDROID_NDK or the newest under ~/Library/Android/sdk/ndk), adb, docker CLI, unzip.
set -euo pipefail
cd "$(dirname "$0")"

APK=${1:?usage: build.sh <arm64 split apk> [--adb-serial S] [--docker-host URL]}
shift
SERIAL=""
DOCKER_HOST_ARG=""
while [ $# -gt 0 ]; do
  case $1 in
    --adb-serial) SERIAL=$2; shift 2 ;;
    --docker-host) DOCKER_HOST_ARG=$2; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

SDK=${ANDROID_HOME:-$HOME/Library/Android/sdk}
NDK=${ANDROID_NDK:-$(ls -d "$SDK"/ndk/* | sort -V | tail -1)}
CC=$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android24-clang | head -1)
ADB=(adb)
command -v adb >/dev/null || ADB=("$SDK/platform-tools/adb")
[ -n "$SERIAL" ] && ADB+=(-s "$SERIAL")

OUT=out
SYS=$OUT/sysroot/system
rm -rf "$OUT"
mkdir -p "$SYS/bin" "$SYS/lib64"

# the engine, as shipped in the game
unzip -p "$APK" lib/arm64-v8a/libcas-battle.so > "$SYS/lib64/libcas-battle.so"
test -s "$SYS/lib64/libcas-battle.so" || { echo "no lib/arm64-v8a/libcas-battle.so in $APK" >&2; exit 1; }

# bionic (Android 10+: the runtime APEX)
"${ADB[@]}" pull /apex/com.android.runtime/bin/linker64 "$SYS/bin/linker64" >/dev/null
for f in libc.so libm.so libdl.so libdl_android.so; do
  "${ADB[@]}" pull "/apex/com.android.runtime/lib64/bionic/$f" "$SYS/lib64/$f" >/dev/null
done
for f in liblog.so libc++.so ld-android.so; do
  "${ADB[@]}" pull "/system/lib64/$f" "$SYS/lib64/$f" >/dev/null
done

# the helper
"$CC" -O2 -Wall -Wextra -o "$SYS/bin/cas_host" cas_host.c -L"$SYS/lib64" -lcas-battle
chmod +x "$SYS/bin/"*

# qemu-user (static binary; only the container is Docker, nothing runs in Docker later)
DOCKER=(docker)
[ -n "$DOCKER_HOST_ARG" ] && DOCKER=(env DOCKER_HOST="$DOCKER_HOST_ARG" docker)
"${DOCKER[@]}" run --rm ubuntu:24.04 sh -c \
  'apt-get update -qq >/dev/null && apt-get install -y -qq qemu-user-static >/dev/null 2>&1 && cat /usr/bin/qemu-aarch64-static' \
  > "$OUT/qemu-aarch64-static"
chmod +x "$OUT/qemu-aarch64-static"
test -s "$OUT/qemu-aarch64-static"

echo "built $(pwd)/$OUT"
