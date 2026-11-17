"""Doplňování chybějících dílů seriálu z iVysílání videi z YouTube.

Postup:
  1. Chybějící díly = díly pořadu, které teď na iVysílání pustit nejdou (katalog je má
     s `dostupny: false`, i s názvem), a čísla dílů, o kterých víme jen z „…/26“ v názvech.
     Díly se rozlišují podle řady i čísla. Už doplněné díly se vynechají.
  2. S yt-dlp (vlastní užití): každý díl se vyhledá na YouTube, výsledky se obodují a nabídnou.
     Bez yt-dlp (veřejná verze): aplikace jen ukáže, co chybí, s odkazem na vyhledávání
     na YouTube; video vloží rodič odkazem.
  3. Nic se nepřidá samo – rodič návrh potvrdí.

Hledání běží na pozadí; rozhraní se průběžně ptá na stav (GET /api/serialy/<id>/doplneni).
"""
import re
import statistics
import threading
import unicodedata
import urllib.parse

import katalog
from zdroje import ivysilani, youtube

_stav: dict[str, dict] = {}
_zamek = threading.Lock()

# Slova typická pro kompilace a sestřihy (porovnávají se celá slova).
SLOVA_KOMPILACE = {"kompilace", "komplet", "kompletni", "hodina", "hodiny", "hodin", "full", "mix", "sestrih"}
FRAZE_KOMPILACE = ("vsechny dily",)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def _slova(text: str) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2}


def skore(kandidat: dict, serial: str, nazev_dilu: str, cislo: int | None, typicka_delka: float | None) -> float:
    titulek = _norm(kandidat["nazev"])
    slova_titulku = set(titulek.split())
    body = 0.0

    s = _slova(serial)
    if s:
        shoda = len(s & slova_titulku)
        if not shoda:
            return 0.0   # bez názvu seriálu v titulku to skoro jistě není náš díl
        body += 3 * shoda / len(s)
    d = _slova(nazev_dilu)
    if d:
        body += 4 * len(d & slova_titulku) / len(d)
    if cislo is not None and str(cislo) in titulek.split():
        body += 0.5

    delka = kandidat.get("delka")
    if typicka_delka and delka:
        pomer = delka / typicka_delka
        if 0.6 <= pomer <= 1.6:
            body += 1.5
        elif pomer > 2.5:
            body -= 3     # nejspíš kompilace víc dílů
    # trestat jen slova, která nejsou v názvu dílu („Jak spravovali hodiny“ je v pořádku)
    podezrela = (SLOVA_KOMPILACE & slova_titulku) - _slova(nazev_dilu)
    if podezrela or any(f in titulek for f in FRAZE_KOMPILACE):
        body -= 2
    return round(body, 2)


def odkaz_hledani(serial: str, dil: dict) -> str:
    bez_cisla = ivysilani.nazev_bez_cisla(dil["nazev"])
    dotaz = f"{serial} {bez_cisla}" if bez_cisla else f"{serial} {dil['cislo']}. díl"
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote(dotaz)


def zjisti_chybejici(s: dict) -> tuple[list[dict], str | None]:
    """Vrátí (seznam chybějících dílů {cislo, rada, nazev}, případná poznámka)."""
    ze_zdroje = [d for d in s["dily"] if not d.get("rucne")]
    dostupne = {katalog._klic(d) for d in ze_zdroje if d.get("dostupny") and d.get("cislo")}
    doplnene = {katalog._klic(d) for d in s["dily"] if d.get("rucne") and d.get("cislo")}

    chybejici: dict[tuple, dict] = {}
    for d in ze_zdroje:   # díly, které ČT zná, ale teď nejdou pustit (mají i název)
        k = katalog._klic(d)
        if d.get("cislo") and not d.get("dostupny") and k not in dostupne and k not in doplnene:
            chybejici.setdefault(k, {"cislo": d["cislo"], "rada": d.get("rada"), "nazev": d["nazev"]})

    # čísla, o kterých víme jen z „…/26“ (když ČT o dílu vůbec nic nevrátila)
    rady_celkem: dict = {}
    for d in ze_zdroje:
        n, celkem = ivysilani.cislo_dilu(d["nazev"])
        if celkem:
            rady_celkem[d.get("rada")] = max(rady_celkem.get(d.get("rada"), 0), celkem)
    for rada, celkem in rady_celkem.items():
        for n in range(1, celkem + 1):
            k = (rada, n)
            if k not in dostupne and k not in doplnene:
                chybejici.setdefault(k, {"cislo": n, "rada": rada, "nazev": f"{n}/{celkem}"})

    if not chybejici and not rady_celkem and not any(d.get("cislo") for d in ze_zdroje):
        return [], ("Díly tohoto seriálu nemají v názvu číslo (např. „4/26“), takže nejde poznat, "
                    "které chybí. Přidej je ručně odkazem.")
    return sorted(chybejici.values(), key=lambda d: (str(d["rada"] or ""), d["cislo"])), None


def _hledej_vse(serial_id: str) -> None:
    try:
        s = katalog.najdi(katalog.nacti(), serial_id)
        if s is None:
            raise KeyError("seriál byl mezitím odebrán")
        serial = s.get("nazev") or katalog.nazev(s)   # název ze zdroje je pro hledání lepší než vlastní
        chybejici, poznamka = zjisti_chybejici(s)
        hledat = youtube.ma_yt_dlp()
        for d in chybejici:
            d["hledat_url"] = odkaz_hledani(serial, d)
            d["kandidati"] = []
        with _zamek:
            _stav[serial_id].update(celkem=len(chybejici), poznamka=poznamka, hledani=hledat,
                                    chybejici=[] if hledat else chybejici)
        if not hledat:
            with _zamek:
                _stav[serial_id]["stav"] = "hotovo"
            katalog.log(f"🔍 {katalog.nazev(s)}: chybí {len(chybejici)} dílů")
            return

        delky = [d["delka"] for d in s["dily"] if d.get("delka")]
        typicka = statistics.median(delky) if delky else None
        for i, dil in enumerate(chybejici, start=1):
            bez_cisla = ivysilani.nazev_bez_cisla(dil["nazev"])
            dotaz = f"{serial} {bez_cisla}" if bez_cisla else f"{serial} {dil['cislo']}. díl"
            try:
                vysledky = youtube.hledej(dotaz)
            except Exception as e:  # noqa: BLE001
                vysledky = []
                dil["chyba"] = str(e)
            obodovane = sorted(({**k, "skore": skore(k, serial, bez_cisla, dil["cislo"], typicka)} for k in vysledky),
                               key=lambda k: -k["skore"])
            dil["kandidati"] = [k for k in obodovane if k["skore"] > 1][:3]
            with _zamek:
                if serial_id not in _stav:
                    return
                _stav[serial_id]["chybejici"].append(dil)
                _stav[serial_id]["hotovo"] = i
        with _zamek:
            _stav[serial_id]["stav"] = "hotovo"
        nalezeno = sum(1 for d in chybejici if d.get("kandidati"))
        katalog.log(f"🔍 {katalog.nazev(s)}: chybí {len(chybejici)} dílů, na YouTube nalezeno {nalezeno}")
    except Exception as e:  # noqa: BLE001
        with _zamek:
            if serial_id in _stav:
                _stav[serial_id].update(stav="chyba", poznamka=str(e).strip("'"))
        katalog.log(f"❌ Doplňování: {e}")


def spust(serial_id: str) -> dict:
    s = katalog.najdi(katalog.nacti(), serial_id)
    if not s:
        raise KeyError("Seriál nenalezen")
    if not serial_id.startswith("ct-"):
        raise ValueError("Doplňování chybějících dílů je jen pro seriály z iVysílání")
    with _zamek:
        if _stav.get(serial_id, {}).get("stav") == "hledam":
            return dict(_stav[serial_id])
        _stav[serial_id] = {"stav": "hledam", "hotovo": 0, "celkem": None, "chybejici": [],
                            "poznamka": None, "hledani": youtube.ma_yt_dlp()}
    threading.Thread(target=_hledej_vse, args=(serial_id,), daemon=True).start()
    return stav(serial_id)


def stav(serial_id: str) -> dict:
    with _zamek:
        return dict(_stav.get(serial_id) or {"stav": "nic", "hledani": youtube.ma_yt_dlp()})


def vyrizeno(serial_id: str, cislo, rada=None) -> None:
    """Díl byl doplněn (nebo přeskočen) → zmizí ze seznamu chybějících."""
    with _zamek:
        st = _stav.get(serial_id)
        if st and cislo is not None:
            st["chybejici"] = [d for d in st["chybejici"] if (d.get("rada"), d["cislo"]) != (rada, cislo)]
