#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--background" ]]; then
  shift
  exec "$ROOT_DIR/skills/mrk-douyin-cover/scripts/launch_local_studio.sh" --background "$ROOT_DIR" "$@"
fi

exec "$ROOT_DIR/skills/mrk-douyin-cover/scripts/launch_local_studio.sh" "$ROOT_DIR" "$@"
