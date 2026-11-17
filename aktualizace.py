"""Kontrola nové verze aplikace.

Jednou denně se aplikace zeptá GitHubu na nejnovější vydání (releases/latest).
Když je novější než běžící verze, rozhraní ukáže „Je dostupná nová verze“ s odkazem
ke stažení. Nic se samo nestahuje ani neinstaluje. Kontrolu jde vypnout ve Správě.
"""
import json
import re
import threading
import time
import urllib.request

import cesty

URL = f"https://api.github.com/repos/{cesty.REPOZITAR}/releases/latest"
INTERVAL = 24 * 3600

_stav: dict = {"nova": None}
_zamek = threading.Lock()


def _cislo_verze(text: str) -> tuple:
    """'v1.2.3' → (1, 2, 3); co nejde přečíst, je (0,)."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)", (text or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def je_novejsi(kandidat: str, aktualni: str = cesty.VERZE) -> bool:
    return _cislo_verze(kandidat) > _cislo_verze(aktualni)


def _soubor():
    return cesty.slozka_dat() / "aktualizace.json"


def zkontroluj(vynutit: bool = False) -> dict | None:
    """Vrátí {"verze", "url"} když je k dispozici novější vydání, jinak None."""
    with _zamek:
        try:
            ulozene = json.loads(_soubor().read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            ulozene = {}
        if vynutit or time.time() - ulozene.get("cas", 0) > INTERVAL:
            try:
                req = urllib.request.Request(URL, headers={"Accept": "application/vnd.github+json",
                                                           "User-Agent": f"NaDobrouNoc/{cesty.VERZE}"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8"))
                url = data.get("html_url") or ""
                ulozene = {"cas": time.time(), "verze": str(data.get("tag_name") or ""),
                           "url": url if url.startswith(f"https://github.com/{cesty.REPOZITAR}/") else ""}
                cesty.slozka_dat().mkdir(parents=True, exist_ok=True)
                _soubor().write_text(json.dumps(ulozene), "utf-8")
            except Exception:  # noqa: BLE001 – bez připojení nebo bez vydání se nic neděje
                pass
        verze = ulozene.get("verze")
        _stav["nova"] = {"verze": verze.lstrip("v"), "url": ulozene.get("url")} \
            if verze and je_novejsi(verze) and ulozene.get("url") else None
        return _stav["nova"]


def nova_verze() -> dict | None:
    return _stav["nova"]


def spust_na_pozadi(povoleno) -> None:
    """Kontrola při startu a pak jednou denně, dokud je povolená (povoleno = funkce → bool)."""
    def smycka():
        while True:
            if povoleno():
                zkontroluj()
            else:
                _stav["nova"] = None
            time.sleep(3600)
    threading.Thread(target=smycka, daemon=True).start()
