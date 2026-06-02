#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
OUTPUT_NAME="zmeshmend_core"

echo
echo "============================================"
echo " ZMeshMend CGAL Core Build (macOS)"
echo "============================================"
echo

CMAKE_BIN="$(command -v cmake || true)"
BREW_BIN="$(command -v brew || true)"

if [ -z "${BREW_BIN}" ] && [ -x "/opt/homebrew/bin/brew" ]; then
  BREW_BIN="/opt/homebrew/bin/brew"
elif [ -z "${BREW_BIN}" ] && [ -x "/usr/local/bin/brew" ]; then
  BREW_BIN="/usr/local/bin/brew"
fi

if [ -z "${CMAKE_BIN}" ] && [ -n "${BREW_BIN}" ] && [ -x "$("${BREW_BIN}" --prefix cmake 2>/dev/null)/bin/cmake" ]; then
  CMAKE_BIN="$("${BREW_BIN}" --prefix cmake)/bin/cmake"
fi

if [ -z "${CMAKE_BIN}" ]; then
  echo "[ERROR] CMake not found."
  echo "        Install with: brew install cmake"
  exit 1
fi

CONFIGURE_ARGS=(
  -S "${SCRIPT_DIR}"
  -B "${BUILD_DIR}"
  -DCMAKE_BUILD_TYPE=Release
)

if [ -z "${BREW_BIN}" ]; then
  echo "[WARN] Homebrew not found. Continuing with system CMake paths."
  echo "       If configure fails, install dependencies manually."
else
  BREW_PREFIX="$("${BREW_BIN}" --prefix)"
  CMAKE_PREFIX_PATH="${BREW_PREFIX}"

  for package in cgal eigen boost gmp mpfr libomp; do
    if package_prefix="$("${BREW_BIN}" --prefix "${package}" 2>/dev/null)"; then
      CMAKE_PREFIX_PATH="${CMAKE_PREFIX_PATH};${package_prefix}"
    fi
  done

  if ! "${BREW_BIN}" list --versions cgal >/dev/null 2>&1; then
    echo "[ERROR] CGAL is not installed."
    echo "        Run: ${BREW_BIN} install cgal eigen boost gmp mpfr libomp"
    exit 1
  fi

  CONFIGURE_ARGS+=("-DCMAKE_PREFIX_PATH=${CMAKE_PREFIX_PATH}")
  echo "[OK] Homebrew prefix: ${BREW_PREFIX}"
  echo "[OK] CMake prefix path: ${CMAKE_PREFIX_PATH}"
fi

echo "[INFO] Required packages:"
echo "       brew install cmake cgal eigen boost gmp mpfr libomp"
echo

if [ -d "${BUILD_DIR}" ]; then
  echo "[CLEAN] Removing previous build..."
  rm -rf "${BUILD_DIR}"
fi

echo "[CONFIGURE] Running CMake..."
"${CMAKE_BIN}" "${CONFIGURE_ARGS[@]}"

echo
echo "[BUILD] Compiling..."
"${CMAKE_BIN}" --build "${BUILD_DIR}" --config Release --parallel

SRC="${BUILD_DIR}/${OUTPUT_NAME}"
if [ ! -f "${SRC}" ]; then
  SRC="${BUILD_DIR}/Release/${OUTPUT_NAME}"
fi

if [ ! -f "${SRC}" ]; then
  echo "[ERROR] Build finished but executable was not found."
  echo "        Expected: ${BUILD_DIR}/${OUTPUT_NAME}"
  exit 1
fi

cp -f "${SRC}" "${SCRIPT_DIR}/${OUTPUT_NAME}"
chmod +x "${SCRIPT_DIR}/${OUTPUT_NAME}"

echo
echo "============================================"
echo " BUILD SUCCESS"
echo " Output: ${SCRIPT_DIR}/${OUTPUT_NAME}"
echo "============================================"
