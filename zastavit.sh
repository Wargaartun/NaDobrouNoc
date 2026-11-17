#!/usr/bin/env bash
# Zastaví aplikaci Na dobrou noc spuštěnou přes spustit.sh.

cd "$(dirname "$(readlink -f "$0")")" || exit 1
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/na-dobrou-noc"
PIDSOUBOR="$DATA/server.pid"

zprava() {
  notify-send -i "$PWD/static/ikona.svg" "Na dobrou noc" "$1" 2>/dev/null || echo "$1"
}

PID="$(cat "$PIDSOUBOR" 2>/dev/null)"
# zabít jen proces, který je opravdu náš server (PID mohl mezitím dostat jiný program)
if [ -n "$PID" ] && tr '\0' ' ' 2>/dev/null < "/proc/$PID/cmdline" | grep -qE '(okno|server)\.py'; then
  kill "$PID" && zprava "Aplikace zastavena."
else
  zprava "Aplikace neběžela."
fi
rm -f "$PIDSOUBOR"
