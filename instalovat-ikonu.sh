#!/usr/bin/env bash
# Vytvoří ikonu Na dobrou noc v nabídce aplikací a na ploše (Linux, verze ze zdrojového kódu).
# Spusť jednou:  bash instalovat-ikonu.sh
# (Když projekt přesuneš do jiné složky, spusť znovu.)

set -e
SLOZKA="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
chmod +x "$SLOZKA/spustit.sh" "$SLOZKA/zastavit.sh"

ZASTUPCE=$(cat <<EOF
[Desktop Entry]
Type=Application
Name=Na dobrou noc
Comment=Večerníčky a pohádky před spaním v prohlížeči
Exec="$SLOZKA/spustit.sh"
Path=$SLOZKA
Icon=$SLOZKA/static/ikona.svg
Terminal=false
Categories=AudioVideo;Video;
Actions=zastavit;

[Desktop Action zastavit]
Name=Zastavit
Exec="$SLOZKA/zastavit.sh"
EOF
)

# 1) nabídka aplikací
mkdir -p "$HOME/.local/share/applications"
rm -f "$HOME/.local/share/applications/vecernicek.desktop"   # ikona ze starší verze
echo "$ZASTUPCE" > "$HOME/.local/share/applications/na-dobrou-noc.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# 2) plocha (složka se jmenuje podle jazyka systému, např. "Plocha")
PLOCHA="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$PLOCHA" ]; then
  rm -f "$PLOCHA/vecernicek.desktop"
  echo "$ZASTUPCE" > "$PLOCHA/na-dobrou-noc.desktop"
  chmod +x "$PLOCHA/na-dobrou-noc.desktop"
  # Cinnamon jinak u ikony z plochy napoprvé ukáže varování "nedůvěryhodná aplikace"
  gio set "$PLOCHA/na-dobrou-noc.desktop" metadata::trusted true 2>/dev/null || true
  echo "✅ Ikona je na ploše ($PLOCHA) i v nabídce aplikací (Zvuk a video → Na dobrou noc)."
else
  echo "✅ Ikona je v nabídce aplikací (Zvuk a video → Na dobrou noc)."
fi
echo "   Aplikaci zastavíš v jejím okně, pravým tlačítkem na ikoně v nabídce → Zastavit, nebo ./zastavit.sh"
