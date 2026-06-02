#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${SCRIPT_DIR}/ZFileUtils_mac.cpp"
OUT="${SCRIPT_DIR}/ZFileUtils.lib"

if [ ! -f "${SRC}" ]; then
  echo "[ERROR] Source not found: ${SRC}"
  exit 1
fi

ARCH_ARGS=()
if clang++ -arch arm64 -arch x86_64 -x c++ - -o /tmp/zfileutils_arch_test 2>/dev/null <<<'int main(){return 0;}'; then
  ARCH_ARGS=(-arch arm64 -arch x86_64)
  rm -f /tmp/zfileutils_arch_test
else
  HOST_ARCH="$(uname -m)"
  ARCH_ARGS=(-arch "${HOST_ARCH}")
fi

echo "Building ZFileUtils.lib (${ARCH_ARGS[*]})"
clang++ -dynamiclib -std=c++17 -O2 -fvisibility=hidden \
  "${ARCH_ARGS[@]}" \
  "${SRC}" \
  -o "${OUT}"

chmod 755 "${OUT}"

echo "OK -> ${OUT}"
file "${OUT}"
nm -gU "${OUT}" | grep -E '_(Version|FileDelete|FileRename|FileRead|LaunchAppWithFile)$'
