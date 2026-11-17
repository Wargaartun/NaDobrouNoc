# PyInstaller – zabalení aplikace do složky se spustitelným programem (bez Pythonu u uživatele).
#
#   python -m pip install "pyinstaller>=6.10,<7"
#   python -m PyInstaller --noconfirm baleni/na_dobrou_noc.spec
#
# Výsledek: dist/NaDobrouNoc/ (NaDobrouNoc.exe na Windows, NaDobrouNoc na Linuxu).
# Režim „onedir“ (složka, ne jeden soubor) a bez UPX – méně falešných poplachů antivirů
# a rychlejší start. yt-dlp se do veřejné verze nikdy nepřibaluje.
import re
import sys
from pathlib import Path

KOREN = Path(SPECPATH).parent
VERZE = re.search(r'VERZE = "([\d.]+)"', (KOREN / "cesty.py").read_text("utf-8")).group(1)

a = Analysis(
    [str(KOREN / "okno.py")],
    pathex=[str(KOREN)],
    datas=[
        (str(KOREN / "static"), "static"),
        (str(KOREN / "ct_nastaveni.json"), "."),
        (str(KOREN / "LICENSE"), "."),
    ],
    excludes=["yt_dlp", "pytest", "PIL", "numpy", "playwright"],
    noarchive=False,
)
pyz = PYZ(a.pure)

verze_windows = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct,
                                                     StringTable, VarFileInfo, VarStruct, VSVersionInfo)
    cisla = tuple(int(x) for x in (VERZE.split(".") + ["0"] * 4)[:4])
    verze_windows = VSVersionInfo(
        ffi=FixedFileInfo(filevers=cisla, prodvers=cisla),
        kids=[
            StringFileInfo([StringTable("040504B0", [   # čeština, Unicode
                StringStruct("CompanyName", "Projekt Na dobrou noc"),
                StringStruct("FileDescription", "Na dobrou noc – večerníčky a pohádky před spaním"),
                StringStruct("FileVersion", VERZE),
                StringStruct("InternalName", "NaDobrouNoc"),
                StringStruct("LegalCopyright", "GNU GPL v3.0 – github.com/Wargaartun/NaDobrouNoc"),
                StringStruct("OriginalFilename", "NaDobrouNoc.exe"),
                StringStruct("ProductName", "Na dobrou noc"),
                StringStruct("ProductVersion", VERZE),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0405, 1200])]),
        ],
    )

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NaDobrouNoc",
    console=False,          # bez černého okna konzole; výpis jde do server.log
    icon=str(KOREN / "baleni" / "ikona.ico") if sys.platform == "win32" else None,
    version=verze_windows,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="NaDobrouNoc", upx=False)
