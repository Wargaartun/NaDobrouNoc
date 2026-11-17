#!/usr/bin/env bash
# Spustí aplikaci Na dobrou noc (Linux, verze ze zdrojového kódu).
# okno.py samo pozná, jestli aplikace už běží, najde volný port a otevře prohlížeč.
# Výpis serveru se ukládá do server.log v datové složce (~/.local/share/na-dobrou-noc).

cd "$(dirname "$(readlink -f "$0")")" || exit 1
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/na-dobrou-noc"
mkdir -p "$DATA"
LOG="$DATA/server.log"

zprava() {  # oznámení na ploše, případně do terminálu
  notify-send -i "$PWD/static/ikona.svg" "Na dobrou noc" "$1" 2>/dev/null || echo "$1"
}

if [ -x .venv/bin/python3 ]; then PY=.venv/bin/python3; else PY=python3; fi

# log nenecháme růst donekonečna
if [ -f "$LOG" ] && [ "$(stat -c %s "$LOG")" -gt 1000000 ]; then mv -f "$LOG" "$LOG.1"; fi
echo "===== $(date '+%Y-%m-%d %H:%M:%S') spuštění =====" >> "$LOG"

if "$PY" -c "import tkinter" 2>/dev/null; then
  nohup "$PY" -u okno.py >> "$LOG" 2>&1 &
else
  zprava "Chybí okno aplikace (sudo apt install python3-tk). Běží na pozadí – zastavíš ji přes ikonu → Zastavit."
  nohup "$PY" -u server.py >> "$LOG" 2>&1 &
  for _ in $(seq 1 50); do
    "$PY" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/stav', timeout=1)" 2>/dev/null && break
    sleep 0.2
  done
  xdg-open "http://localhost:8000" >/dev/null 2>&1 &
fi
