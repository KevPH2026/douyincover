#!/usr/bin/env bash
set -euo pipefail

MODE="foreground"
if [[ "${1:-}" == "--background" ]]; then
  MODE="background"
  shift
fi

PROJECT_DIR="${1:-/Users/k/Documents/SNS}"
START_PORT="${PORT:-8765}"
PAGE="${PAGE:-mrk-cover-studio.html}"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

if [[ ! -f "$PROJECT_DIR/cover_studio_server.py" ]]; then
  echo "cover_studio_server.py not found in: $PROJECT_DIR" >&2
  exit 1
fi

PORT_TO_USE="$(
  python3 - "$START_PORT" <<'PY'
import socket
import sys

start = int(sys.argv[1])
for port in range(start, start + 100):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        continue
    finally:
        sock.close()
    print(port)
    break
else:
    raise SystemExit("No free local port found.")
PY
)"

STATE_DIR="$PROJECT_DIR/.codex-local"
mkdir -p "$STATE_DIR"
LOG_FILE="$STATE_DIR/mrk-cover-studio-$PORT_TO_USE.log"
PID_FILE="$STATE_DIR/mrk-cover-studio-$PORT_TO_USE.pid"

URL="http://127.0.0.1:$PORT_TO_USE/$PAGE"
echo "$URL"
echo "log=$LOG_FILE"

if [[ "$MODE" == "background" ]]; then
  (
    cd "$PROJECT_DIR"
    PORT="$PORT_TO_USE" nohup python3 -u cover_studio_server.py >"$LOG_FILE" 2>&1 < /dev/null &
    echo $! >"$PID_FILE"
  )

  sleep 0.6

  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Server failed to start. Log: $LOG_FILE" >&2
    exit 1
  fi

  echo "pid=$(cat "$PID_FILE")"
  exit 0
fi

cd "$PROJECT_DIR"
echo "Starting foreground server. Keep this process running while using the page."
exec env PORT="$PORT_TO_USE" python3 cover_studio_server.py
