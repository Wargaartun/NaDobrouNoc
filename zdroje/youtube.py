"""YouTube: názvy videí, playlisty a (volitelně) hledání.

Dvě cesty:
  * Oficiální (veřejná verze): názvy a náhledy videí přes oEmbed – službu, kterou
    YouTube nabízí pro vkládání videí na weby. Seznam videí v playlistu zjistí
    prohlížeč přes oficiální YouTube přehrávač (IFrame API, getPlaylist) a pošle ho serveru.
  * yt-dlp (jen pro vlastní užití, když je nainstalovaný): server si playlist přečte
    sám a umí na YouTube vyhledávat chybějící díly. yt-dlp jde mimo podmínky YouTube,
    proto ho veřejná verze nepoužívá. Vypnout ho jde i proměnnou NADOBROUNOC_BEZ_YTDLP=1.
"""
import importlib.util
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlparse

RE_ID = re.compile(r"^[\w-]{11}$")
NEDOSTUPNE = {"[Private video]", "[Deleted video]", "[Soukromé video]", "[Smazané video]"}


def ma_yt_dlp() -> bool:
    if os.environ.get("NADOBROUNOC_BEZ_YTDLP") == "1":
        return False
    return importlib.util.find_spec("yt_dlp") is not None


def je_id(text) -> bool:
    return isinstance(text, str) and bool(RE_ID.match(text))


def je_playlist(url: str) -> bool:
    u = urlparse(url)
    return "youtube.com" in u.netloc and "list" in parse_qs(u.query)


def id_playlistu(url: str) -> str:
    plid = parse_qs(urlparse(url).query)["list"][0]
    if not re.fullmatch(r"[\w-]{10,64}", plid):
        raise ValueError("Neplatné ID playlistu")
    return plid


def id_videa(text: str) -> str | None:
    """Z libovolného YouTube odkazu (nebo holého ID) vrátí 11znakové ID videa; jinak None."""
    text = (text or "").strip()
    if RE_ID.match(text):
        return text
    u = urlparse(text)
    kandidat = None
    if u.netloc.endswith("youtu.be"):
        kandidat = u.path[1:12]
    elif "v" in parse_qs(u.query):
        kandidat = parse_qs(u.query)["v"][0]
    else:
        m = re.search(r"/(?:embed|shorts|live)/([\w-]{11})", u.path)
        kandidat = m.group(1) if m else None
    return kandidat if je_id(kandidat) else None


def nahled(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


# ---------- oficiální cesta: oEmbed ----------
def _oembed(url_videa: str) -> dict:
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url_videa)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def info_videa(odkaz: str) -> dict:
    """Název a náhled jednoho videa. Video se zakázaným vkládáním (oEmbed 401) odmítne."""
    vid = id_videa(odkaz)
    if not vid:
        raise ValueError(f"Neplatný odkaz na YouTube video: {odkaz}")
    try:
        data = _oembed(f"https://www.youtube.com/watch?v={vid}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError(f"Video {vid}: autor nedovolil přehrávání mimo YouTube") from e
        raise ValueError(f"Video {vid} neexistuje nebo je soukromé") from e
    except urllib.error.URLError as e:
        raise RuntimeError("nepodařilo se spojit s YouTube – zkontroluj připojení k internetu") from e
    return {"id": vid, "nazev": str(data.get("title") or vid)[:200], "typ": "youtube", "delka": None,
            "obrazek": nahled(vid), "dostupny": True}


def _info_nebo_nedostupne(vid: str, poradi: int) -> dict:
    try:
        return info_videa(vid)
    except ValueError:
        return {"id": vid, "nazev": f"Nedostupné video {poradi}", "typ": "youtube", "delka": None,
                "obrazek": nahled(vid), "dostupny": False}


def playlist_z_videi(url: str, videa: list[str]) -> dict:
    """Playlist z ID videí, která zjistil prohlížeč (veřejná verze, bez yt-dlp)."""
    videa = [v for v in dict.fromkeys(videa) if je_id(v)][:500]
    if not videa:
        raise ValueError("Playlist je prázdný nebo se ho nepodařilo načíst")
    with ThreadPoolExecutor(max_workers=8) as pool:
        dily = list(pool.map(_info_nebo_nedostupne, videa, range(1, len(videa) + 1)))
    if not any(d["dostupny"] for d in dily):
        raise RuntimeError("žádné video z playlistu nejde přehrát – zkontroluj připojení k internetu")
    try:
        nazev = _oembed(f"https://www.youtube.com/playlist?list={id_playlistu(url)}").get("title")
    except Exception:  # noqa: BLE001 – název playlistu není nutný
        nazev = None
    prvni = next(d for d in dily if d["dostupny"])
    return {"nazev": nazev or "Playlist z YouTube", "obrazek": prvni["obrazek"], "dily": dily}


# ---------- yt-dlp (jen vlastní užití) ----------
def _yt_dlp():
    if not ma_yt_dlp():
        raise RuntimeError("Tahle funkce potřebuje yt-dlp, který tato verze nepoužívá.")
    import yt_dlp
    return yt_dlp


def hledej(dotaz: str, pocet: int = 8) -> list[dict]:
    """Vyhledá videa na YouTube (jen seznam výsledků, nic se nestahuje)."""
    yt_dlp = _yt_dlp()
    volby = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(volby) as ydl:
        info = ydl.extract_info(f"ytsearch{pocet}:{dotaz}", download=False)
    return [{"id": e["id"], "nazev": e.get("title") or e["id"], "delka": e.get("duration"),
             "kanal": e.get("channel") or e.get("uploader"), "obrazek": nahled(e["id"])}
            for e in info.get("entries") or [] if e and je_id(e.get("id"))]


def nacti_playlist(url: str) -> dict:
    """Playlist přes yt-dlp: {"nazev", "obrazek", "dily": [...]}."""
    yt_dlp = _yt_dlp()
    volby = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(volby) as ydl:
        info = ydl.extract_info(f"https://www.youtube.com/playlist?list={id_playlistu(url)}", download=False)
    dily = []
    for i, e in enumerate(info.get("entries") or [], start=1):
        if not e or not je_id(e.get("id")):
            continue
        nazev = e.get("title") or f"Díl {i}"
        dily.append({"id": e["id"], "nazev": nazev, "typ": "youtube", "delka": e.get("duration"),
                     "obrazek": nahled(e["id"]), "dostupny": nazev not in NEDOSTUPNE})
    prvni = next((d for d in dily if d["dostupny"]), None)
    return {"nazev": info.get("title") or "Playlist", "obrazek": prvni["obrazek"] if prvni else None, "dily": dily}
