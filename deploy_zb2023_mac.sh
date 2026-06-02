#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZBRUSH_ROOT="${ZBRUSH_ROOT:-/Applications/Maxon ZBrush 2023}"
ZPLUGS_DIR="${ZBRUSH_ROOT}/ZStartup/ZPlugs64"
DATA_DIR="${ZPLUGS_DIR}/ZMeshMendData"
BACKUP_DIR="${ZPLUGS_DIR}/ZMeshMend_backup_$(date +%Y%m%d_%H%M%S)"

SRC_ZSCRIPT="${REPO_ROOT}/ZMeshMend/ZMeshMend_ZScript.txt"
SRC_CORE="${REPO_ROOT}/ZMeshMendData/zmeshmend_core"
SRC_CONFIG="${REPO_ROOT}/ZMeshMend/ZMeshMend_config.txt"
SRC_PIPELINE="${REPO_ROOT}/ZMeshMendData/ZMeshMend_pipeline.py"
SRC_ZFILEUTILS="${REPO_ROOT}/ZMeshMendData/ZFileUtils.lib"

if [ "${EUID}" -ne 0 ]; then
  exec sudo "$0" "$@"
fi

echo "============================================"
echo " ZMeshMend Deploy for Maxon ZBrush 2023 macOS"
echo "============================================"
echo

if [ ! -d "${ZPLUGS_DIR}" ]; then
  echo "[ERROR] ZBrush plugin directory not found:"
  echo "        ${ZPLUGS_DIR}"
  echo "        If your ZBrush path differs, run:"
  echo "        ZBRUSH_ROOT='/Applications/Your ZBrush Folder' $0"
  exit 1
fi

if [ ! -f "${SRC_ZSCRIPT}" ]; then
  echo "[ERROR] Missing source ZScript: ${SRC_ZSCRIPT}"
  exit 1
fi

if [ ! -x "${SRC_CORE}" ]; then
  echo "[ERROR] Missing executable core: ${SRC_CORE}"
  echo "        Build it first:"
  echo "        cd '${REPO_ROOT}/ZMeshMendData' && ./build.sh"
  exit 1
fi

mkdir -p "${BACKUP_DIR}"

backup_if_exists() {
  local path="$1"
  if [ -e "${path}" ]; then
    cp -a "${path}" "${BACKUP_DIR}/"
  fi
}

echo "[BACKUP] Saving existing ZMeshMend files to:"
echo "         ${BACKUP_DIR}"
backup_if_exists "${ZPLUGS_DIR}/ZMeshMend_ZScript.txt"
backup_if_exists "${ZPLUGS_DIR}/ZMeshMend_ZScript.zsc"
backup_if_exists "${DATA_DIR}/zmeshmend_core"
backup_if_exists "${DATA_DIR}/zmeshmend_config.txt"
backup_if_exists "${DATA_DIR}/ZMeshMend_pipeline.py"
backup_if_exists "${DATA_DIR}/ZFileUtils.lib"

mkdir -p "${DATA_DIR}"

echo "[COPY] ZScript"
cp -f "${SRC_ZSCRIPT}" "${ZPLUGS_DIR}/ZMeshMend_ZScript.txt"

echo "[COPY] CGAL core"
cp -f "${SRC_CORE}" "${DATA_DIR}/zmeshmend_core"
chmod +x "${DATA_DIR}/zmeshmend_core"

echo "[COPY] Config"
cp -f "${SRC_CONFIG}" "${DATA_DIR}/zmeshmend_config.txt"

echo "[COPY] Pipeline helper"
cp -f "${SRC_PIPELINE}" "${DATA_DIR}/ZMeshMend_pipeline.py"

if [ -f "${SRC_ZFILEUTILS}" ]; then
  echo "[COPY] ZFileUtils.lib"
  cp -f "${SRC_ZFILEUTILS}" "${DATA_DIR}/ZFileUtils.lib"
elif [ -f "${DATA_DIR}/ZFileUtils.lib" ]; then
  echo "[OK] Existing ZFileUtils.lib found in target."
else
  echo
  echo "[WARN] ZFileUtils.lib is missing."
  echo "       ZScript version on macOS requires:"
  echo "       ${DATA_DIR}/ZFileUtils.lib"
  echo "       The bundled Windows ZFileUtils64.dll cannot be used by macOS ZBrush."
fi

if [ -f "${ZPLUGS_DIR}/ZMeshMend_ZScript.zsc" ]; then
  echo "[CLEAN] Removing stale compiled ZScript."
  rm -f "${ZPLUGS_DIR}/ZMeshMend_ZScript.zsc"
fi

xattr -dr com.apple.quarantine "${ZPLUGS_DIR}/ZMeshMend_ZScript.txt" "${DATA_DIR}/zmeshmend_core" 2>/dev/null || true

echo
echo "============================================"
echo " Deploy finished"
echo " ZScript: ${ZPLUGS_DIR}/ZMeshMend_ZScript.txt"
echo " Data:    ${DATA_DIR}"
echo " Core:    ${DATA_DIR}/zmeshmend_core"
echo "============================================"
echo
echo "Next step:"
echo "  Open ZBrush 2023 > ZScript > Load > ZMeshMend_ZScript.txt"
