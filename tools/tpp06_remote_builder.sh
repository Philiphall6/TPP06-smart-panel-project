#!/usr/bin/env bash
set -euo pipefail

# Reproducible remote ARMv5 build server for the official ESPHome Device Builder.
# No project-specific absolute paths are stored in this script.

ESPHOME_VERSION="${ESPHOME_VERSION:-2026.10.2}"
DEVICE_BUILDER_VERSION="${DEVICE_BUILDER_VERSION:-1.28.1}"
TOOLCHAIN_SHA256="2e78440c4b37a9c84d6165f12fd2525e72bf88c32445e1c3400d1e01384c92ce"
DATA_ROOT="${TPP06_BUILDER_DATA:-${XDG_DATA_HOME:-${HOME}/.local/share}/tpp06-remote-builder}"
VENV_DIR="${DATA_ROOT}/venv"
CONFIG_DIR="${DATA_ROOT}/config"
TOOLCHAIN_DIR="${DATA_ROOT}/toolchain"
TOOLCHAIN_RECORD="${DATA_ROOT}/toolchain.path"

usage() {
  printf '%s\n' \
    "Usage:" \
    "  $0 install TOOLCHAIN_ARCHIVE_OR_DIRECTORY" \
    "  $0 run HOME_ASSISTANT_IP [PORT]" \
    "  $0 status"
}

find_prefix() {
  local root="$1" gcc
  gcc="$(find "${root}" -type f -path '*/bin/arm-buildroot-linux-uclibcgnueabi-gcc' -print -quit)"
  if [ -z "${gcc}" ]; then
    printf 'ARMv5/uClibc compiler not found below %s\n' "${root}" >&2
    exit 1
  fi
  printf '%s\n' "${gcc%-gcc}"
}

install_builder() {
  local source="$1" actual_hash prefix
  mkdir -p "${DATA_ROOT}" "${CONFIG_DIR}"

  if [ -f "${source}" ]; then
    actual_hash="$(sha256sum "${source}" | awk '{print $1}')"
    if [ "${actual_hash}" != "${TOOLCHAIN_SHA256}" ]; then
      printf 'Unexpected toolchain SHA-256: %s\n' "${actual_hash}" >&2
      exit 1
    fi
    mkdir -p "${TOOLCHAIN_DIR}"
    tar -xf "${source}" -C "${TOOLCHAIN_DIR}"
    prefix="$(find_prefix "${TOOLCHAIN_DIR}")"
  elif [ -d "${source}" ]; then
    prefix="$(find_prefix "${source}")"
  else
    printf 'Toolchain archive or directory not found: %s\n' "${source}" >&2
    exit 1
  fi

  printf '%s\n' "${prefix}" > "${TOOLCHAIN_RECORD}"
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/pip" install --upgrade pip
  "${VENV_DIR}/bin/pip" install \
    "esphome==${ESPHOME_VERSION}" \
    "esphome-device-builder==${DEVICE_BUILDER_VERSION}"
  printf 'Installed in %s\n' "${DATA_ROOT}"
  printf 'Next: %s run HOME_ASSISTANT_IP 6057\n' "$0"
}

run_builder() {
  local ha_ip="$1" port="${2:-6057}" prefix
  if [ ! -x "${VENV_DIR}/bin/esphome-device-builder" ] || [ ! -f "${TOOLCHAIN_RECORD}" ]; then
    printf 'Run the install command first.\n' >&2
    exit 1
  fi
  prefix="$(cat "${TOOLCHAIN_RECORD}")"
  exec env \
    CC="${prefix}-gcc" \
    CXX="${prefix}-g++" \
    AR="${prefix}-ar" \
    OBJDUMP="${prefix}-objdump" \
    READELF="${prefix}-readelf" \
    ESPHOME_PCH_ENABLE=0 \
    "${VENV_DIR}/bin/esphome-device-builder" "${CONFIG_DIR}" \
      --remote-build-only \
      --remote-build-host 0.0.0.0 \
      --remote-build-port "${port}" \
      --allow-pairing-source "${ha_ip}"
}

case "${1:-}" in
  install)
    [ "$#" -eq 2 ] || { usage; exit 2; }
    install_builder "$2"
    ;;
  run)
    [ "$#" -ge 2 ] && [ "$#" -le 3 ] || { usage; exit 2; }
    run_builder "$2" "${3:-6057}"
    ;;
  status)
    printf 'Data: %s\n' "${DATA_ROOT}"
    "${VENV_DIR}/bin/esphome" version 2>/dev/null || true
    "${VENV_DIR}/bin/esphome-device-builder" --version 2>/dev/null || true
    ;;
  *)
    usage
    exit 2
    ;;
esac
