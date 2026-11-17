"""Katalog: ukládání, záloha, přenos starých dat, slučování při obnově, ruční díly."""
import json

import pytest

import cesty
import katalog
from zdroje import ivysilani, youtube

SID = "ct-879074-jaja-a-paja"
URL = "https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/"


@pytest.fixture
def ct(monkeypatch):
    """Napodobený pořad z iVysílání: 26 dílů, přehratelné podle množiny `prehratelne`."""
    prehratelne = set(range(1, 14))

    def nacti_porad(url, log=print):
        dily = [ivysilani._dil({"id": f"2873509510400{n:02d}", "title": f"{n}/26 Díl {n}", "playable": n in prehratelne,
                                "duration": 500, "images": {}}) for n in range(1, 27)]
        return {"nazev": "Jája a Pája", "obrazek": "o", "programme_id": "P1", "dily": dily}
    monkeypatch.setattr(ivysilani, "nacti_porad", nacti_porad)
    return prehratelne


def test_novy_katalog_je_prazdny():
    katalog.zaloz()
    d = katalog.nacti()
    assert d["serialy"] == [] and d["znelka"] is None
    assert d["nastaveni"] == {"pruvodce_hotov": False, "sit": False, "kontrola_verze": True}


def test_prenos_starych_dat(tmp_path, monkeypatch, cista_data):
    stara = tmp_path / "program"
    (stara / "data").mkdir(parents=True)
    (stara / "data" / "katalog.json").write_text(json.dumps({"znelka": "USYeHXGvh7M", "serialy": [{"id": "vl-1", "dily": []}]}))
    monkeypatch.setattr(cesty, "SLOZKA_PROGRAMU", stara)
    katalog.zaloz()
    d = katalog.nacti()
    assert d["znelka"] == "USYeHXGvh7M" and d["nastaveni"]["pruvodce_hotov"] is True   # průvodce se přeskočí


def test_zaloha_pri_poskozeni(cista_data):
    katalog.uloz({**katalog._prazdny(), "znelka": "aaaaaaaaaaa"})
    katalog.uloz({**katalog._prazdny(), "znelka": "bbbbbbbbbbb"})
    katalog.SOUBOR.write_text("{rozbité")
    assert katalog.nacti()["znelka"] == "aaaaaaaaaaa"


def test_docasne_zmizely_dil_si_pamatuje_stav(ct):
    katalog.pridej_nebo_obnov(URL)
    katalog.uprav_dil(SID, "287350951040003", zhlednuto="2026-11-17", skryty=True)
    ct.discard(3)
    katalog.pridej_nebo_obnov(URL)
    ct.add(3)
    katalog.pridej_nebo_obnov(URL)
    d3 = next(d for d in katalog.najdi(katalog.nacti(), SID)["dily"] if d["cislo"] == 3)
    assert d3["dostupny"] and d3["zhlednuto"] == "2026-11-17" and d3["skryty"]


def test_obnova_odebraneho_serialu_ho_nezalozi(ct):
    katalog.pridej_nebo_obnov(URL)
    katalog.odeber(SID)
    assert katalog.pridej_nebo_obnov(URL, jen_existujici=True) is None
    assert katalog.najdi(katalog.nacti(), SID) is None


def test_rucni_dil_zarazeni_a_nahrazeni(ct):
    katalog.pridej_nebo_obnov(URL)
    katalog.pridej_yt_dily(SID, [], cislo=14, meta={"id": "okurky00014", "nazev": "YT"})
    dily = [d for d in katalog.najdi(katalog.nacti(), SID)["dily"] if d["dostupny"] and not d["nahrazeno"]]
    assert [d["cislo"] for d in dily] == list(range(1, 15))     # díl 14 z YouTube hned za 13 z ČT
    ct.add(14)
    katalog.pridej_nebo_obnov(URL)
    rucni = next(d for d in katalog.najdi(katalog.nacti(), SID)["dily"] if d["id"] == "okurky00014")
    assert rucni["nahrazeno"]                          # díl je zpět na ČT → hraje se odtamtud
    ct.discard(14)
    katalog.pridej_nebo_obnov(URL)
    rucni = next(d for d in katalog.najdi(katalog.nacti(), SID)["dily"] if d["id"] == "okurky00014")
    assert not rucni["nahrazeno"]


@pytest.mark.parametrize("meta", [{"id": "<script>"}, {"id": "kratke"}, "text", {"nazev": "bez id"}])
def test_overeni_udaju_o_videu(ct, meta):
    katalog.pridej_nebo_obnov(URL)
    with pytest.raises(ValueError):
        katalog.pridej_yt_dily(SID, [], meta=meta)


def test_udaje_o_videu_se_sestavi_znovu(ct):
    katalog.pridej_nebo_obnov(URL)
    katalog.pridej_yt_dily(SID, [], cislo=14, meta={"id": "okurky00014", "nazev": "x" * 500,
                                                    "obrazek": "javascript:alert(1)", "delka": "nekonečno"})
    d = next(d for d in katalog.najdi(katalog.nacti(), SID)["dily"] if d["id"] == "okurky00014")
    assert len(d["nazev"]) == 200 and d["obrazek"] == youtube.nahled("okurky00014") and d["delka"] is None


def test_cislo_dilu_musi_byt_cislo(ct):
    katalog.pridej_nebo_obnov(URL)
    with pytest.raises(ValueError):
        katalog.pridej_yt_dily(SID, ["https://youtu.be/bbbbbbbbbbb"], cislo="pět")


def test_smazat_jde_jen_rucni_dil(ct):
    katalog.pridej_nebo_obnov(URL)
    katalog.pridej_yt_dily(SID, [], meta={"id": "okurky00014", "nazev": "YT"})
    with pytest.raises(ValueError):
        katalog.odeber_dil(SID, "287350951040001")
    katalog.odeber_dil(SID, "okurky00014")


def test_vlastni_serial(monkeypatch):
    monkeypatch.setattr(youtube, "info_videa", lambda o: {"id": youtube.id_videa(o), "nazev": "V", "typ": "youtube",
                                                          "delka": None, "obrazek": "x", "dostupny": True})
    v = katalog.vytvor_vlastni("Moje pohádky", ["https://youtu.be/aaaaaaaaaaa", "https://youtube.com/playlist?list=PLabcdefghij"])
    assert v["pridano"] == 1 and "prohlížeč" in v["chyby"][0]   # playlist bez yt-dlp musí rozbalit prohlížeč
    with pytest.raises(ValueError):
        katalog.vytvor_vlastni("  ", [])


def test_znelka():
    with pytest.raises(ValueError):
        katalog.nastav_znelku("https://www.youtube.com/watch?v=<script>")
    assert katalog.nastav_znelku("https://youtu.be/USYeHXGvh7M") == "USYeHXGvh7M"
    assert katalog.nastav_znelku("") is None


def test_playlist_bez_seznamu_videi_vyzaduje_prohlizec():
    with pytest.raises(ValueError, match="prohlížeč"):
        katalog.pridej_nebo_obnov("https://youtube.com/playlist?list=PLabcdefghij")


def test_nastaveni_overuje_typy():
    with pytest.raises(ValueError):
        katalog.nastav(sit="ano")
    assert katalog.nastav(kontrola_verze=False)["kontrola_verze"] is False
