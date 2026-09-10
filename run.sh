#!/usr/bin/env bash
# Build the mod and drive the local Fabric 1.21.11 test server on port 25613.
#
#   ./run.sh build     compile the jar
#   ./run.sh start     build, install into run/mods, boot the server
#   ./run.sh stop      stop the server
#   ./run.sh cmd "..." send a console command
#   ./run.sh test      run the mineflayer checks against a running server
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
RUN="$DIR/run"
GRADLE="$HOME/.gradle/wrapper/dists/gradle-9.6.1-bin/4ticwg1pgcbps2hj28r8so764/gradle-9.6.1/bin/gradle"
JAR="$DIR/build/libs/goldencarrotbuff-1.0.0.jar"
FIFO="$RUN/console.in"

build() {
  "$GRADLE" -p "$DIR" build -q
}

start() {
  stop || true
  build
  cp "$JAR" "$RUN/mods/"
  rm -f "$FIFO"; mkfifo "$FIFO"
  cd "$RUN"
  # Hold the fifo open so the server never sees EOF on stdin.
  ( while true; do sleep 3600; done ) > "$FIFO" &
  echo $! > "$RUN/holder.pid"
  nohup java -Xms1G -Xmx2G -jar fabric-server-launch.jar --nogui < "$FIFO" > "$RUN/server.log" 2>&1 &
  echo $! > "$RUN/server.pid"
  for _ in $(seq 1 120); do
    grep -q 'Done (' "$RUN/server.log" 2>/dev/null && { echo "server up on 25613"; return 0; }
    sleep 1
  done
  echo "server did not finish booting; see run/server.log" >&2
  return 1
}

stop() {
  # Writing to a fifo with no reader blocks forever, so only talk to a live server,
  # and background the write so a dead one cannot wedge the script.
  if [ -f "$RUN/server.pid" ] && kill -0 "$(cat "$RUN/server.pid")" 2>/dev/null; then
    [ -p "$FIFO" ] && ( echo stop > "$FIFO" & ) 2>/dev/null || true
    sleep 3
  fi
  rm -f "$FIFO"
  [ -f "$RUN/server.pid" ] && kill "$(cat "$RUN/server.pid")" 2>/dev/null || true
  [ -f "$RUN/holder.pid" ] && kill "$(cat "$RUN/holder.pid")" 2>/dev/null || true
  rm -f "$RUN/server.pid" "$RUN/holder.pid"
  return 0
}

case "${1:-start}" in
  build) build ;;
  start) start ;;
  stop)  stop ;;
  cmd)   echo "${2:?command}" > "$FIFO" ;;
  test)  cd "$DIR" && node bots/test.js && node bots/foods.js ;;
  *) echo "usage: $0 {build|start|stop|cmd|test}" >&2; exit 2 ;;
esac
