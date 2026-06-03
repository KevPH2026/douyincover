#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/skills/mrk-douyin-cover"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
TARGET_DIR="$CODEX_HOME_DIR/skills/mrk-douyin-cover"

if [[ ! -f "$SOURCE_DIR/SKILL.md" ]]; then
  echo "Skill source not found: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET_DIR")"
rsync -a --delete "$SOURCE_DIR/" "$TARGET_DIR/"

if [[ -f "$TARGET_DIR/scripts/launch_local_studio.sh" ]]; then
  chmod +x "$TARGET_DIR/scripts/launch_local_studio.sh"
fi

echo "Installed Skill: $TARGET_DIR"
echo 'Invoke with: $mrk-douyin-cover'
