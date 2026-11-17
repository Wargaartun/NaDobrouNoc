"""Kde aplikace ukládá data a jak se jmenuje.

Data (katalog, záloha, log) leží v profilu uživatele, ne ve složce programu,
takže je aktualizace programu nikdy nesmaže:
  Windows:  %APPDATA%\\NaDobrouNoc
  macOS:    ~/Library/Application Support/NaDobrouNoc
  Linux:    $XDG_DATA_HOME/na-dobrou-noc  (obvykle ~/.local/share/na-dobrou-noc)

Proměnná prostředí NADOBROUNOC_DATA složku přebije (hodí se pro testy).
"""
import os
import shutil
import sys
from pathlib import Path

NAZEV = "Na dobrou noc"
VERZE = "0.6.0"
REPOZITAR = "Wargaartun/NaDobrouNoc"
# Zabalený program (PyInstaller) má své soubory v sys._MEIPASS, jinak leží vedle tohoto souboru.
ZABALENO = getattr(sys, "frozen", False)
SLOZKA_PROGRAMU = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def slozka_dat() -> Path:
    if os.environ.get("NADOBROUNOC_DATA"):
        return Path(os.environ["NADOBROUNOC_DATA"])
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "NaDobrouNoc"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "NaDobrouNoc"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "na-dobrou-noc"


def preved_stara_data(nova: Path) -> str | None:
    """Jednorázově zkopíruje katalog ze staré složky data/ vedle programu (verze do 0.3)."""
    stary = SLOZKA_PROGRAMU / "data" / "katalog.json"
    novy = nova / "katalog.json"
    if stary.exists() and not novy.exists():
        nova.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stary, novy)
        return f"Katalog přenesen z {stary} do {novy}"
    return None
