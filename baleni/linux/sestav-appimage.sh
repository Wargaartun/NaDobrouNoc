#!/usr/bin/env bash
# Sestaví AppImage z výstupu PyInstalleru (dist/NaDobrouNoc).
#   bash baleni/linux/sestav-appimage.sh 0.6.0
# Potřebuje appimagetool (stáhne se, když chybí). Výsledek: dist/NaDobrouNoc-<verze>-x86_64.AppImage
set -euo pipefail
VERZE="${1:?Zadej verzi, např. 0.6.0}"
KOREN="$(cd "$(dirname "$0")/../.." && pwd)"
APPDIR="$KOREN/build/NaDobrouNoc.AppDir"

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/lib"
cp -r "$KOREN/dist/NaDobrouNoc" "$APPDIR/usr/lib/NaDobrouNoc"
install -m 755 "$KOREN/baleni/linux/AppRun" "$APPDIR/AppRun"
cp "$KOREN/baleni/linux/na-dobrou-noc.desktop" "$APPDIR/"
cp "$KOREN/static/ikona.png" "$APPDIR/na-dobrou-noc.png"
ln -sf na-dobrou-noc.png "$APPDIR/.DirIcon"

NASTROJ="$KOREN/build/appimagetool"
if [ ! -x "$NASTROJ" ]; then
  curl -fsSL -o "$NASTROJ" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "$NASTROJ"
fi
# APPIMAGE_EXTRACT_AND_RUN: appimagetool poběží i tam, kde chybí FUSE (např. na GitHubu)
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$NASTROJ" "$APPDIR" "$KOREN/dist/NaDobrouNoc-$VERZE-x86_64.AppImage"
echo "Hotovo: dist/NaDobrouNoc-$VERZE-x86_64.AppImage"
