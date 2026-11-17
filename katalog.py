"""Katalog seriálů: ukládání do katalog.json v datové složce a obnova ze zdrojů.

Datová složka je v profilu uživatele (viz cesty.py). Struktura souboru:
{
  "znelka": "USYeHXGvh7M" | null,          # ID YouTube videa se znělkou (vybere uživatel)
  "nastaveni": {"pruvodce_hotov": false, "sit": false},
  "serialy": [
    {
      "id": "ct-879074-jaja-a-paja",        # "yt-<playlist>", "ct-<slug pořadu>" nebo "vl-<číslo>" (vlastní)
      "zdroj": "https://…",                 # odkaz, ze kterého se seriál obnovuje (u vlastních null)
      "nazev": "Jája a Pája",               # název ze zdroje
      "nazev_vlastni": null,                # tvůj název (přebije název ze zdroje)
      "obrazek": "https://…",
      "programme_id": "6489…",              # jen iVysílání
      "aktualizovano": "2026-11-17T15:30:00",
      "chyba": null,                        # poslední chyba při načítání
      "dily": [
        {"id": "…", "nazev": "…", "typ": "youtube" | "ivysilani", "cislo": 4, "rada": null,
         "delka": 520, "obrazek": "…", "dostupny": true, "skryty": false, "zhlednuto": null,
         "rucne": false,        # díl přidaný ručně (YouTube odkaz) – obnova ze zdroje ho nesmaže
         "nahrazeno": false}    # ruční díl, který je teď dostupný na iVysílání → hraje se ten z ČT
      ]
    }
  ]
}
Díly z iVysílání jsou v katalogu všechny, i ty, které teď nejdou pustit (dostupny: false).
"""
import json
import os
import shutil
import threading
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import aktualizace
import cesty
from zdroje import ivysilani, youtube

SLOZKA_DAT = cesty.slozka_dat()
SOUBOR = SLOZKA_DAT / "katalog.json"

_zamek = threading.RLock()
_zpravy: list[dict] = []         # posledních pár zpráv pro rozhraní: {"n": pořadí, "text": …}
_pocitadlo = 0
_nacita_se: set[str] = set()     # názvy/odkazy, které se právě načítají


def log(zprava: str) -> None:
    global _pocitadlo
    radek = f"[{datetime.now():%H:%M:%S}] {zprava}"
    print(radek, flush=True)
    with _zamek:
        _pocitadlo += 1
        _zpravy.append({"n": _pocitadlo, "text": zprava})
        del _zpravy[:-30]


def stav() -> dict:
    with _zamek:
        return {"nacita_se": sorted(_nacita_se), "zpravy": list(_zpravy), "posledni": _pocitadlo,
                "yt_dlp": youtube.ma_yt_dlp(), "nazev": cesty.NAZEV, "verze": cesty.VERZE,
                "data": str(SLOZKA_DAT), "nova_verze": aktualizace.nova_verze(),
                "repozitar": f"https://github.com/{cesty.REPOZITAR}"}


# ---------- čtení a zápis ----------
def _prazdny() -> dict:
    return {"znelka": None, "nastaveni": {"pruvodce_hotov": False, "sit": False, "kontrola_verze": True}, "serialy": []}


def nacti() -> dict:
    with _zamek:
        for soubor in (SOUBOR, SOUBOR.with_suffix(".json.bak")):
            if soubor.exists():
                try:
                    data = json.loads(soubor.read_text("utf-8"))
                    data.setdefault("nastaveni", {}).setdefault("pruvodce_hotov", bool(data.get("serialy")))
                    data["nastaveni"].setdefault("sit", False)
                    data["nastaveni"].setdefault("kontrola_verze", True)
                    data.setdefault("znelka", None)
                    return data
                except (ValueError, OSError):   # neplatný JSON i neplatné UTF-8 (UnicodeDecodeError)
                    log(f"⚠️  {soubor.name} je poškozený, zkouším zálohu")
        return _prazdny()


def uloz(data: dict) -> None:
    with _zamek:
        SLOZKA_DAT.mkdir(parents=True, exist_ok=True)
        docasny = SOUBOR.with_suffix(".tmp")
        with open(docasny, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())           # opravdu zapsáno na disk
        if SOUBOR.exists():
            shutil.copy2(SOUBOR, SOUBOR.with_suffix(".json.bak"))   # předchozí verze jako záloha
        os.replace(docasny, SOUBOR)        # zápis "naráz", soubor se nikdy nepoškodí napůl


def najdi(data: dict, serial_id: str) -> dict | None:
    return next((s for s in data["serialy"] if s["id"] == serial_id), None)


def nazev(s: dict) -> str:
    return s.get("nazev_vlastni") or s.get("nazev") or "Bez názvu"


def zaloz() -> None:
    """Při startu: přenese data ze staré verze, jinak založí prázdný katalog (vyplní ho průvodce)."""
    zprava = cesty.preved_stara_data(SLOZKA_DAT)
    if zprava:
        log(f"📦 {zprava}")
    if not SOUBOR.exists():
        uloz(_prazdny())
    log(f"Data: {SLOZKA_DAT}")


def nastav(**zmeny) -> dict:
    with _zamek:
        data = nacti()
        for k in ("pruvodce_hotov", "sit", "kontrola_verze"):
            if k in zmeny:
                if not isinstance(zmeny[k], bool):
                    raise ValueError(f"{k} musí být ano/ne")
                data["nastaveni"][k] = zmeny[k]
        uloz(data)
        return data["nastaveni"]


# ---------- zdroje ----------
def id_pro_url(url: str) -> str:
    url = (url or "").strip()
    if youtube.je_playlist(url):
        return "yt-" + youtube.id_playlistu(url)
    if ivysilani.je_porad(url):
        return "ct-" + ivysilani.slug_poradu(url)
    raise ValueError("Podporované jsou YouTube playlisty a pořady z ceskatelevize.cz/porady/…")


def _nacti_ze_zdroje(url: str, videa: list[str] | None) -> dict:
    if youtube.je_playlist(url):
        if videa:
            return youtube.playlist_z_videi(url, videa)     # seznam poslal prohlížeč (oficiální cesta)
        if youtube.ma_yt_dlp():
            return youtube.nacti_playlist(url)
        raise ValueError("Seznam videí playlistu musí načíst prohlížeč – obnov stránku a zkus to znovu")
    return ivysilani.nacti_porad(url, log=log)


def _klic(d: dict):
    return (d.get("rada"), d.get("cislo"))


def serad(dily: list[dict]) -> list[dict]:
    """Díly s číslem seřadí podle řady (v pořadí, jak se objevily) a čísla; bez čísla nechá na konci."""
    if not any(d.get("cislo") for d in dily):
        return dily
    rady = list(dict.fromkeys(d.get("rada") for d in dily if d.get("cislo")))
    poradi = {id(d): i for i, d in enumerate(dily)}
    return sorted(dily, key=lambda d: (d.get("cislo") is None, rady.index(d.get("rada")) if d.get("cislo") else 0,
                                       d.get("cislo") or 0, poradi[id(d)]))


def _spoj_dily(stare: list[dict], nove: list[dict]) -> list[dict]:
    """Díly ze zdroje + tvoje údaje (skrytí, zhlédnutí) + ručně přidané díly."""
    puvodni = {d["id"]: d for d in stare}
    ze_zdroje_ids = {d["id"] for d in nove}
    vysledek = []
    for d in nove:
        p = puvodni.get(d["id"], {})
        vysledek.append({**d, "skryty": p.get("skryty", False), "zhlednuto": p.get("zhlednuto"),
                         "rucne": False, "nahrazeno": False})
    # Díl ze zdroje, který tam teď vůbec není (u YouTube playlistu běžné), si ponecháme jako
    # nedostupný – kdyby se vrátil, má zachované zhlédnutí a skrytí.
    for d in stare:
        if not d.get("rucne") and d["id"] not in ze_zdroje_ids:
            vysledek.append({**d, "dostupny": False})

    # ruční díly zůstávají; když je stejný díl (řada + číslo) zase na iVysílání, má přednost iVysílání
    dostupne_klice = {_klic(d) for d in vysledek if d.get("dostupny") and d.get("cislo")}
    for d in stare:
        if d.get("rucne"):
            vysledek.append({**d, "nahrazeno": bool(d.get("cislo")) and _klic(d) in dostupne_klice})
    return serad(vysledek)


# ---------- seriály ze zdroje ----------
def pridej_nebo_obnov(url: str, nazev_vlastni: str | None = None, videa: list[str] | None = None,
                      jen_existujici: bool = False) -> dict | None:
    """Načte seriál ze zdroje a uloží ho do katalogu. Vrací uložený seriál.

    jen_existujici=True (obnova): když seriál mezitím někdo odebral, nic se nezapíše a vrátí None.
    """
    serial_id = id_pro_url(url)
    znacka = nazev_vlastni or url
    with _zamek:
        _nacita_se.add(znacka)
    try:
        info = _nacti_ze_zdroje(url, videa)
        with _zamek:
            data = nacti()
            s = najdi(data, serial_id)
            if s is None:
                if jen_existujici:
                    return None   # seriál byl během obnovy odebrán – nezakládat ho znovu
                s = {"id": serial_id, "zdroj": url, "nazev_vlastni": nazev_vlastni, "dily": []}
                data["serialy"].append(s)
            elif nazev_vlastni:
                s["nazev_vlastni"] = nazev_vlastni
            s.update({
                "nazev": info["nazev"],
                "obrazek": info["obrazek"],
                "dily": _spoj_dily(s["dily"], info["dily"]),
                "aktualizovano": datetime.now().isoformat(timespec="seconds"),
                "chyba": None,
            })
            if info.get("programme_id"):
                s["programme_id"] = info["programme_id"]
            uloz(data)
        dostupne = sum(1 for d in s["dily"] if d["dostupny"] and not d.get("nahrazeno"))
        log(f"✅ {nazev(s)}: {dostupne} dílů")
        return s
    except Exception as e:
        log(f"❌ {znacka}: {e}")
        with _zamek:
            data = nacti()
            s = najdi(data, serial_id)
            if s:
                s["chyba"] = str(e)
                uloz(data)
        raise
    finally:
        with _zamek:
            _nacita_se.discard(znacka)


def obnov_vse() -> None:
    """Obnoví seriály, které umí obnovit server. YouTube playlisty bez yt-dlp obnovuje prohlížeč."""
    for s in nacti()["serialy"]:
        if not s.get("zdroj") or (s["id"].startswith("yt-") and not youtube.ma_yt_dlp()):
            continue
        try:
            pridej_nebo_obnov(s["zdroj"], jen_existujici=True)
        except Exception:  # noqa: BLE001 – chyba je zalogovaná, pokračujeme dalším
            pass


# ---------- ruční díly z YouTube a vlastní seriály ----------
def _je_video(odkaz: str) -> bool:
    """Odkaz na konkrétní video (i když je otevřené v playlistu: watch?v=…&list=…)."""
    u = urlparse(odkaz.strip())
    return "v" in parse_qs(u.query) or u.netloc.endswith("youtu.be") or "/shorts/" in u.path \
        or (youtube.id_videa(odkaz) is not None and "list" not in parse_qs(u.query))


def _dily_z_odkazu(odkaz: str) -> list[dict]:
    """YouTube odkaz → seznam dílů (jedno video, nebo s yt-dlp i všechna videa z playlistu)."""
    odkaz = odkaz.strip()
    if _je_video(odkaz):
        return [youtube.info_videa(odkaz)]
    if youtube.je_playlist(odkaz):
        if not youtube.ma_yt_dlp():
            raise ValueError("Playlist musí načíst prohlížeč – obnov stránku a zkus to znovu")
        return [d for d in youtube.nacti_playlist(odkaz)["dily"] if d["dostupny"]]
    raise ValueError(f"Tohle není odkaz na YouTube video ani playlist: {odkaz}")


def _over_meta(meta) -> dict:
    """Údaje o videu z prohlížeče (návrh z hledání) – nevěříme jim, sestavíme je znovu."""
    if not isinstance(meta, dict) or not youtube.je_id(meta.get("id")):
        raise ValueError("Neplatné údaje o videu")
    delka = meta.get("delka")
    return {"id": meta["id"], "nazev": str(meta.get("nazev") or meta["id"])[:200],
            "delka": delka if isinstance(delka, (int, float)) and 0 < delka < 86400 else None,
            "obrazek": youtube.nahled(meta["id"])}


def _rucni_dil(d: dict, cislo: int | None = None, rada: str | None = None, nazev_dilu: str | None = None) -> dict:
    return {
        "id": d["id"], "nazev": nazev_dilu or d["nazev"], "typ": "youtube", "cislo": cislo, "rada": rada,
        "delka": d.get("delka"), "obrazek": youtube.nahled(d["id"]),
        "dostupny": True, "skryty": False, "zhlednuto": None, "rucne": True, "nahrazeno": False,
        "puvodni_nazev": d["nazev"],
    }


def pridej_yt_dily(serial_id: str, odkazy: list[str], cislo: int | None = None, rada: str | None = None,
                   nazev_dilu: str | None = None, meta: dict | None = None) -> dict:
    """Přidá do seriálu díly z YouTube odkazů. Vrací {"pridano": n, "chyby": [...]}.

    `meta` = údaje o videu, které už známe z vyhledávání (ověří se, nic se nestahuje).
    """
    if cislo is not None and (not isinstance(cislo, int) or isinstance(cislo, bool) or not 0 < cislo < 10000):
        raise ValueError("Číslo dílu musí být celé číslo")
    if nazev_dilu is not None:
        nazev_dilu = str(nazev_dilu).strip()[:200] or None
    rada = str(rada)[:100] if rada else None

    nove, chyby = [], []
    if meta is not None:
        nove.append(_over_meta(meta))
    else:
        for odkaz in [o for o in odkazy if isinstance(o, str) and o.strip()][:500]:
            try:
                nove += _dily_z_odkazu(odkaz)
            except (ValueError, RuntimeError) as e:
                chyby.append(str(e))

    with _zamek:
        data = nacti()
        s = najdi(data, serial_id)
        if not s:
            raise KeyError("Seriál nenalezen")
        existujici = {d["id"] for d in s["dily"]}
        dostupne_klice = {_klic(d) for d in s["dily"] if not d.get("rucne") and d["dostupny"] and d.get("cislo")}
        jediny = len(nove) == 1
        pridano = 0
        for d in nove:
            if d["id"] in existujici:
                chyby.append(f"„{d['nazev']}“ už v seriálu je")
                continue
            dil = _rucni_dil(d, cislo if jediny else None, rada if jediny else None, nazev_dilu if jediny else None)
            dil["nahrazeno"] = bool(dil["cislo"]) and _klic(dil) in dostupne_klice
            s["dily"].append(dil)
            existujici.add(d["id"])
            pridano += 1
        s["dily"] = serad(s["dily"])
        if not s.get("obrazek") and s["dily"]:
            s["obrazek"] = s["dily"][0]["obrazek"]
        uloz(data)
    if pridano:
        log(f"➕ {nazev(s)}: přidáno {pridano} dílů z YouTube")
    return {"pridano": pridano, "chyby": chyby}


def vytvor_vlastni(jmeno, odkazy: list[str]) -> dict:
    """Nový vlastní seriál složený z YouTube videí (a s yt-dlp i playlistů)."""
    jmeno = str(jmeno or "").strip()[:100]
    if not jmeno:
        raise ValueError("Vlastní seriál potřebuje název")
    serial_id = f"vl-{int(time.time() * 1000)}"
    with _zamek:
        data = nacti()
        data["serialy"].append({"id": serial_id, "zdroj": None, "nazev": jmeno, "nazev_vlastni": None,
                                "obrazek": None, "dily": [], "chyba": None,
                                "aktualizovano": datetime.now().isoformat(timespec="seconds")})
        uloz(data)
    vysledek = pridej_yt_dily(serial_id, odkazy) if odkazy else {"pridano": 0, "chyby": []}
    log(f"✅ Vlastní seriál „{jmeno}“: {vysledek['pridano']} dílů")
    return {"serial": najdi(nacti(), serial_id), **vysledek}


def odeber_dil(serial_id: str, dil_id: str) -> None:
    """Smaže ručně přidaný díl (díly ze zdroje jde jen skrýt – při obnově by se vrátily)."""
    with _zamek:
        data = nacti()
        s = najdi(data, serial_id)
        dil = next((d for d in (s or {}).get("dily", []) if d["id"] == dil_id), None)
        if not dil:
            raise KeyError("Díl nenalezen")
        if not dil.get("rucne"):
            raise ValueError("Díl ze zdroje nejde smazat, jen skrýt")
        s["dily"].remove(dil)
        uloz(data)


# ---------- ostatní úpravy ----------
def odeber(serial_id: str) -> None:
    with _zamek:
        data = nacti()
        data["serialy"] = [s for s in data["serialy"] if s["id"] != serial_id]
        uloz(data)


def uprav_dil(serial_id: str, dil_id: str, skryty=None, zhlednuto=None, **_) -> dict:
    with _zamek:
        data = nacti()
        s = najdi(data, serial_id)
        dil = next((d for d in (s or {}).get("dily", []) if d["id"] == dil_id), None)
        if not dil:
            raise KeyError("Díl nenalezen")
        if skryty is not None:
            if not isinstance(skryty, bool):
                raise ValueError("„skryty“ musí být ano/ne")
            dil["skryty"] = skryty
        if zhlednuto is not None:
            if not isinstance(zhlednuto, str) or len(zhlednuto) > 40:
                raise ValueError("Neplatné datum zhlédnutí")
            dil["zhlednuto"] = zhlednuto
        uloz(data)
        return dil


def uprav_serial(serial_id: str, nazev_vlastni=None, zrusit_zhlednuti=False, **_) -> dict:
    with _zamek:
        data = nacti()
        s = najdi(data, serial_id)
        if not s:
            raise KeyError("Seriál nenalezen")
        if nazev_vlastni is not None:
            s["nazev_vlastni"] = str(nazev_vlastni).strip()[:100] or None
        if zrusit_zhlednuti is True:
            for d in s["dily"]:
                d["zhlednuto"] = None
        uloz(data)
        return s


def nastav_znelku(odkaz) -> str | None:
    """Uloží znělku (YouTube video). Prázdný odkaz znělku vypne."""
    odkaz = str(odkaz or "").strip()
    vid = youtube.id_videa(odkaz) if odkaz else None
    if odkaz and not vid:
        raise ValueError("Neplatný odkaz na YouTube video")
    with _zamek:
        data = nacti()
        data["znelka"] = vid
        uloz(data)
    return vid
