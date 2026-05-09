#!/usr/bin/env bash
set -euo pipefail

TARGET_PATH="${1:-}"
if [[ -z "${TARGET_PATH}" ]]; then
  exit 0
fi

case "${OSTYPE:-}" in
  darwin*)
    open "$TARGET_PATH" >/dev/null 2>&1 || true
    ;;
  linux*)
    xdg-open "$TARGET_PATH" >/dev/null 2>&1 || true
    ;;
  msys*|cygwin*|win32*)
    explorer "$TARGET_PATH" >/dev/null 2>&1 || true
    ;;
  *)
    if command -v explorer >/dev/null 2>&1; then
      explorer "$TARGET_PATH" >/dev/null 2>&1 || true
    fi
    ;;
esac
