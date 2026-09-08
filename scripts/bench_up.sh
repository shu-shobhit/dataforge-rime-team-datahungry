#!/usr/bin/env bash
# Start the three local processes the bench needs, or report what is already up.
#
#     scripts/bench_up.sh          start what is not running
#     scripts/bench_up.sh status   say what is running
#     scripts/bench_up.sh down     stop the web server and the agent worker
#
# livekit-server is left alone by `down`: it holds no state worth restarting and
# other sessions may be using it.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# runs/logs/ is ignored. Process logs used to be written into a committed
# directory, and one livekit-server left running appended two thousand lines of
# ping traffic to a file the repository exists to preserve. Nothing here can
# reach runs/evidence/ or runs/roundtrip/ any more.
LOGS="$ROOT/runs/logs"
PIDS="$ROOT/runs/pids"
# The ML env's interpreter directly, not `conda run`. conda run holds the
# caller's file descriptors open for the life of the child, so a server started
# through it never lets the calling shell return.
PY="${WETLAB_PYTHON:-$HOME/miniconda3/envs/ML/bin/python}"

mkdir -p "$LOGS" "$PIDS"

alive() { [ -f "$PIDS/$1.pid" ] && kill -0 "$(cat "$PIDS/$1.pid")" 2>/dev/null; }

start() {
  local name="$1"; shift
  if alive "$name"; then echo "$name already running ($(cat "$PIDS/$name.pid"))"; return; fi
  # Appended, not truncated. Restarting the worker used to erase the log of
  # the run before it, which is the log you want precisely when you have just
  # restarted because something went wrong.
  echo "=== $name started $(date -Is) ===" >> "$LOGS/$name.log"
  # setsid and the three redirections detach it completely. Without them the
  # child holds the calling shell's stdin open and the caller never returns.
  ( cd "$ROOT" && setsid $* < /dev/null >> "$LOGS/$name.log" 2>&1 & echo $! > "$PIDS/$name.pid" )
  sleep 1
  echo "$name started ($(cat "$PIDS/$name.pid"))"
}

stop() {
  local name="$1"
  if alive "$name"; then
    pkill -TERM -P "$(cat "$PIDS/$name.pid")" 2>/dev/null
    kill -TERM "$(cat "$PIDS/$name.pid")" 2>/dev/null
    echo "$name stopped"
  else
    echo "$name not running"
  fi
  rm -f "$PIDS/$name.pid"
}

case "${1:-up}" in
  status)
    pgrep -af 'livekit-server' | grep -v pgrep || echo "livekit-server NOT running"
    for n in webserver agent; do alive "$n" && echo "$n running ($(cat "$PIDS/$n.pid"))" || echo "$n NOT running"; done
    ;;
  down)
    stop agent; stop webserver
    ;;
  *)
    pgrep -f 'livekit-server --dev' > /dev/null || echo "warning: livekit-server --dev is not running"
    start webserver $PY -m wetlab.webserver
    start agent $PY -m wetlab.agent dev
    echo "logs in $LOGS; open http://127.0.0.1:8080"
    ;;
esac
