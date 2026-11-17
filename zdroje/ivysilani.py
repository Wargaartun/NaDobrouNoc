"""iVysílání (Česká televize): načtení seznamu dílů pořadu a seznamu večerníčků.

Jak to funguje
--------------
Web iVysílání je postavený na Next.js. Každá stránka obsahuje v HTML blok
<script id="__NEXT_DATA__"> s daty, ze kterých se stránka vykresluje
(v klíči props.apolloState). Odtud čteme:
  * u pořadu: název, obrázek, počet přehratelných dílů a prvních 10 dílů,
  * u kategorie Večerníčky: seznam pořadů.

Všechny díly (i nepřehratelné) web dotahuje z GraphQL API České televize dotazem
"GetEpisodes". Je to tzv. persisted query – místo textu dotazu se posílá
jeho otisk (sha256). Když ČT web aktualizuje, otisk se může změnit.

Hodnoty, které se s aktualizací webu ČT mění (otisk, verze klienta, adresy), jsou
v souboru ct_nastaveni.json. Aplikace si jednou za 12 hodin – a hned, když API ČT
otisk odmítne – stáhne jeho aktuální verzi z repozitáře na GitHubu. Oprava po změně
webu ČT tak nepotřebuje nové vydání programu, stačí upravit soubor v repozitáři.
Jak zjistit nový otisk: viz CONTRIBUTING.md.

ID dílu (15 číslic, např. 287350951040001) je zároveň IDEC, se kterým se
díl pouští v přehrávači player.ceskatelevize.cz.
"""
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import cesty

PRODLEVA = 0.3   # s mezi dotazy na API ČT – ať ho zbytečně nezatěžujeme

# Poctivá identifikace: ČT vidí, že jde o tuhle aplikaci, ne o přestrojený prohlížeč.
HLAVICKY = {
    "User-Agent": f"NaDobrouNoc/{cesty.VERZE} (domaci prehravac vecernicku; nekomercni, open source; "
                  f"https://github.com/{cesty.REPOZITAR})",
    "Accept-Language": "cs-CZ,cs;q=0.9",
}

# ---------- nastavení ČT (ct_nastaveni.json) ----------
NASTAVENI_PRIBALENE = cesty.SLOZKA_PROGRAMU / "ct_nastaveni.json"
NASTAVENI_URL = f"https://raw.githubusercontent.com/{cesty.REPOZITAR}/main/ct_nastaveni.json"
_PRAVIDLA = {   # každá hodnota se ověří – stažený soubor nesmí aplikaci poslat jinam než na ČT
    "graphql_url": re.compile(r"^https://api\.ceskatelevize\.cz/[\w/.-]*$"),
    "graphql_klient": re.compile(r"^[\w.-]{1,40}$"),
    "graphql_verze": re.compile(r"^[\w.-]{1,20}$"),
    "hash_get_episodes": re.compile(r"^[0-9a-f]{64}$"),
    "kategorie_vecernicky": re.compile(r"^https://www\.ceskatelevize\.cz/ivysilani/kategorie/[\w/.-]+/$"),
}
_nastaveni: dict = {}
_posledni_stazeni = 0.0
_zamek_nastaveni = threading.Lock()


def _platne(data) -> bool:
    return isinstance(data, dict) and all(isinstance(data.get(k), str) and p.match(data[k]) for k, p in _PRAVIDLA.items())


def nastaveni() -> dict:
    """Aktuální hodnoty: stažené z repozitáře (když jsou platné), jinak přibalené."""
    if not _nastaveni:
        _nastaveni.update(json.loads(NASTAVENI_PRIBALENE.read_text("utf-8")))
        try:
            ulozene = json.loads((cesty.slozka_dat() / "ct_nastaveni.json").read_text("utf-8"))
            if _platne(ulozene):
                _nastaveni.update(ulozene)
        except (OSError, json.JSONDecodeError):
            pass
    return _nastaveni


def aktualizuj_nastaveni(vynutit: bool = False, log=print) -> bool:
    """Stáhne ct_nastaveni.json z repozitáře. Vrací True, když se hodnoty změnily."""
    global _posledni_stazeni
    with _zamek_nastaveni:
        if not vynutit and time.time() - _posledni_stazeni < 12 * 3600:
            return False
        _posledni_stazeni = time.time()
        try:
            req = urllib.request.Request(NASTAVENI_URL, headers=HLAVICKY)
            with urllib.request.urlopen(req, timeout=10) as r:
                nove = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001 – bez připojení nevadí, platí dosavadní hodnoty
            log(f"Nastavení ČT se nepodařilo aktualizovat ({e}); používám dosavadní.")
            return False
        if not _platne(nove):
            log("⚠️  Stažené nastavení ČT je neplatné, používám dosavadní.")
            return False
        stare = dict(nastaveni())
        _nastaveni.update({k: nove[k] for k in _PRAVIDLA})
        try:
            cesty.slozka_dat().mkdir(parents=True, exist_ok=True)
            (cesty.slozka_dat() / "ct_nastaveni.json").write_text(json.dumps(nove, indent=2), "utf-8")
        except OSError:
            pass
        zmena = any(stare.get(k) != _nastaveni[k] for k in _PRAVIDLA)
        if zmena:
            log("🔧 Nastavení ČT aktualizováno z repozitáře.")
        return zmena

RE_POHAD = re.compile(r"ceskatelevize\.cz/porady/([^/?#]+)")
RE_IDEC = re.compile(r"^\d{15}$")


def je_porad(url: str) -> bool:
    return bool(RE_POHAD.search(url))


def slug_poradu(url: str) -> str:
    """Z odkazu na pořad (nebo na jeho díl) vrátí např. '879074-jaja-a-paja'."""
    m = RE_POHAD.search(url)
    if not m:
        raise ValueError("Odkaz nevede na pořad na ceskatelevize.cz/porady/…")
    return m.group(1)


def url_prehravace(idec: str) -> str:
    return "https://player.ceskatelevize.cz/?" + urllib.parse.urlencode(
        {"origin": "iVysilani", "autoStart": "true", "client": "iVysilaniWeb", "IDEC": idec}
    )


# ---------- stahování ----------
def _stahni(url: str, extra_hlavicky: dict | None = None) -> str:
    req = urllib.request.Request(url, headers={**HLAVICKY, **(extra_hlavicky or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"web ČT odpověděl chybou {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError("nepodařilo se spojit s webem ČT – zkontroluj připojení k internetu") from e


def next_data(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("Na stránce ČT chybí blok __NEXT_DATA__ – web se zřejmě změnil.")
    return json.loads(m.group(1))


# ---------- pomocné funkce pro data ----------
def _obrazek(images) -> str | None:
    """Z objektu 'images' vybere vhodný obrázek (přednostně karta ~480 px)."""
    if not isinstance(images, dict):
        return None
    karty = {k: v for k, v in images.items() if k.startswith("card") and isinstance(v, str)}
    for k, v in karty.items():
        if "480" in k:
            return v
    if karty:
        return next(iter(karty.values()))
    for v in images.values():  # cokoli dalšího, i vnořeného
        if isinstance(v, str) and v.startswith("http"):
            return v
        if isinstance(v, dict):
            o = _obrazek(v)
            if o:
                return o
    return None


RE_CISLO = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\b")


def cislo_dilu(nazev: str) -> tuple[int | None, int | None]:
    """'4/26 Jak pěstovali okurky' → (4, 26); bez čísla → (None, None)."""
    m = RE_CISLO.match(nazev or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def nazev_bez_cisla(nazev: str) -> str:
    return RE_CISLO.sub("", nazev or "").strip(" -–:")


def _rada(o: dict) -> str | None:
    """Řada (sezóna) dílu – u seriálů s víc řadami se čísla dílů opakují."""
    s = o.get("season")
    if isinstance(s, dict):
        r = s.get("title") or s.get("name") or s.get("id") or s.get("__ref")
        return str(r) if r else None
    return str(s) if s else None


def _dil(o: dict) -> dict:
    nazev = o.get("title") or o["id"]
    return {
        "id": o["id"],
        "nazev": nazev,
        "typ": "ivysilani",
        "cislo": cislo_dilu(nazev)[0],
        "rada": _rada(o),
        "delka": o.get("duration"),
        "obrazek": _obrazek(o.get("images")),
        "dostupny": o.get("playable", True) is not False,
    }


def _je_dil(o) -> bool:
    return (
        isinstance(o, dict)
        and isinstance(o.get("id"), str)
        and RE_IDEC.match(o["id"])
        and "title" in o
        and "Episode" in str(o.get("__typename", "Episode"))
    )


def _najdi_dily(data) -> list[dict]:
    """Projde libovolnou JSON strukturu a vrátí všechny objekty, které vypadají jako díl."""
    nalezene = []

    def projdi(x):
        if _je_dil(x):
            nalezene.append(x)
        if isinstance(x, dict):
            for v in x.values():
                projdi(v)
        elif isinstance(x, list):
            for v in x:
                projdi(v)

    projdi(data)
    return nalezene


# ---------- pořad ----------
def zpracuj_stranku_poradu(html: str, slug: str) -> dict:
    """Vytáhne údaje o pořadu a prvních ~10 dílů z HTML stránky pořadu."""
    stav = next_data(html)["props"]["apolloState"]
    show_id = slug.split("-")[0]
    show = stav.get(f"Show:{show_id}") or next(
        (v for k, v in stav.items() if k.startswith("Show:") and v.get("slug") == slug), None
    )
    if not show:
        raise RuntimeError("Na stránce ČT jsem nenašel údaje o pořadu.")

    # pořadí dílů podle seznamu odkazů v pořadu (klíč "episodes:{...}")
    poradi = []
    for k, v in show.items():
        if k.startswith("episodes"):
            poradi = re.findall(r'"__ref":\s*"EpisodePreview:(\d{15})"', json.dumps(v))
            break
    dily_dle_id = {
        v["id"]: _dil(v)
        for k, v in stav.items()
        if k.startswith("EpisodePreview:") and v.get("showId", show_id) == show_id and _je_dil(v)
    }
    dily = [dily_dle_id[i] for i in poradi if i in dily_dle_id]
    dily += [d for i, d in dily_dle_id.items() if i not in poradi]

    return {
        "nazev": show.get("title") or slug,
        "obrazek": _obrazek(show.get("images")),
        "programme_id": show.get("programmeId"),
        "pocet_prehratelnych": show.get("playableEpisodeCount"),
        "radit": show.get("defaultSort") or "oldest",
        "dily": dily,
    }


def _dotaz_get_episodes(programme_id: str, offset: int, radit: str, jen_prehratelne: bool) -> list[dict]:
    n = nastaveni()
    promenne = {"limit": 10, "offset": offset, "programmeId": programme_id,
                "orderBy": radit, "onlyPlayable": jen_prehratelne}
    rozsireni = {"persistedQuery": {"version": 1, "sha256Hash": n["hash_get_episodes"]}}
    url = n["graphql_url"] + "?" + urllib.parse.urlencode({
        "client": n["graphql_klient"],
        "version": n["graphql_verze"],
        "operationName": "GetEpisodes",
        "variables": json.dumps(promenne, separators=(",", ":")),
        "extensions": json.dumps(rozsireni, separators=(",", ":")),
    })
    odpoved = json.loads(_stahni(url, {
        "Accept": "*/*", "Content-Type": "application/json",
        "Origin": "https://www.ceskatelevize.cz", "Referer": "https://www.ceskatelevize.cz/",
    }))
    if odpoved.get("errors"):
        raise RuntimeError(f"GraphQL ČT vrátilo chybu: {odpoved['errors'][0].get('message')}")
    return [_dil(o) for o in _najdi_dily(odpoved.get("data"))]


def _dalsi_dily(programme_id: str, offset: int, radit: str, jen_prehratelne: bool = True) -> list[dict]:
    """Dotaz GetEpisodes. Když ho API odmítne, zkusí stáhnout nové nastavení ČT a zopakovat ho."""
    try:
        return _dotaz_get_episodes(programme_id, offset, radit, jen_prehratelne)
    except RuntimeError:
        if not aktualizuj_nastaveni(vynutit=True):
            raise
        return _dotaz_get_episodes(programme_id, offset, radit, jen_prehratelne)


def nacti_porad(url: str, log=print) -> dict:
    """Vrátí {"nazev", "obrazek", "programme_id", "dily": [...]} pro pořad na iVysílání.

    Načítají se VŠECHNY díly, i ty, které teď na iVysílání pustit nejdou
    (`dostupny: false`). Díky tomu díl, který dočasně zmizí, neztratí v katalogu
    zhlédnutí ani skrytí, a aplikace ví, které díly chybí.
    """
    slug = slug_poradu(url)
    porad = zpracuj_stranku_poradu(_stahni(f"https://www.ceskatelevize.cz/porady/{slug}/"), slug)
    zaklad = {"nazev": porad["nazev"], "obrazek": porad["obrazek"], "programme_id": porad["programme_id"]}

    if porad["programme_id"]:
        try:
            vsechny = nacti_vsechny_dily(porad["programme_id"], porad["radit"])
            if vsechny:
                # obrázky ze stránky použijeme tam, kde je API nevrátilo
                ze_stranky = {d["id"]: d for d in porad["dily"]}
                for d in vsechny:
                    if not d["obrazek"] and d["id"] in ze_stranky:
                        d["obrazek"] = ze_stranky[d["id"]]["obrazek"]
                return {**zaklad, "dily": vsechny}
        except Exception as e:  # noqa: BLE001 – nouzově stačí díly ze stránky
            log(f"⚠️  {porad['nazev']}: seznam všech dílů se nepodařilo načíst ({e}). "
                f"Použiji {len(porad['dily'])} dílů ze stránky. Viz README – „Když přestane fungovat iVysílání“.")
    return {**zaklad, "dily": porad["dily"]}


def nacti_vsechny_dily(programme_id: str, radit: str = "oldest", limit: int = 400) -> list[dict]:
    """Všechny díly pořadu (dotaz GetEpisodes s onlyPlayable=false), po 10 kusech."""
    dily, videne = [], set()
    while len(dily) < limit:
        if dily:
            time.sleep(PRODLEVA)
        davka = _dalsi_dily(programme_id, len(dily), radit, jen_prehratelne=False)
        nove = [d for d in davka if d["id"] not in videne]
        dily += nove
        videne.update(d["id"] for d in nove)
        if len(davka) < 10 or not nove:   # neúplná dávka = poslední stránka
            break
    return dily


# ---------- kategorie Večerníčky ----------
def zpracuj_kategorii(html: str) -> tuple[list[dict], int | None]:
    """Vrátí (pořady na této stránce kategorie, celkový počet pořadů v kategorii)."""
    stav = next_data(html)["props"]["apolloState"]

    # pořadí a celkový počet z klíče programmeFind({...}) u objektu Genre
    poradi, celkem = [], None
    for v in stav.values():
        if isinstance(v, dict) and v.get("__typename") == "Genre":
            for k, seznam in v.items():
                if k.startswith("programmeFind") and isinstance(seznam, dict):
                    celkem = seznam.get("totalCount")
                    poradi = [i.get("__ref") for i in seznam.get("items", []) if isinstance(i, dict)]

    klice = [k for k in poradi if k in stav] or [k for k in stav if k.startswith("Show:")]
    porady = []
    for k in klice:
        v = stav[k]
        if v.get("slug"):
            porady.append({
                "nazev": v.get("title") or v["slug"],
                "url": f"https://www.ceskatelevize.cz/porady/{v['slug']}/",
                "obrazek": _obrazek(v.get("images")),
                "popis": v.get("shortDescription"),
            })
    return porady, celkem


def nacti_vecernicky() -> list[dict]:
    """Všechny pořady z kategorie Večerníčky (web je stránkuje po 80: ?page=2, …)."""
    vsechny, videne = [], set()
    for strana in range(1, 11):
        url = nastaveni()["kategorie_vecernicky"] + (f"?page={strana}" if strana > 1 else "")
        porady, celkem = zpracuj_kategorii(_stahni(url))
        nove = [p for p in porady if p["url"] not in videne]
        vsechny += nove
        videne.update(p["url"] for p in nove)
        if not nove or (celkem and len(vsechny) >= celkem):
            break
        time.sleep(PRODLEVA)
    # Web řadí podle sledovanosti za 7 dní – pro výběr a hledání je lepší abeceda.
    return sorted(vsechny, key=lambda p: _klic_razeni(p["nazev"]))


def _klic_razeni(text: str) -> str:
    """Zjednodušené české řazení: č, ř, š, ž až za svým písmenem (C < Č < D), jinak bez diakritiky."""
    import unicodedata
    klic = []
    for znak in text.casefold():
        zaklad = unicodedata.normalize("NFD", znak).encode("ascii", "ignore").decode()
        klic.append(zaklad + "{" if znak in "čřšž" else zaklad)   # „{“ je v ASCII hned za „z“
    return "".join(klic)
