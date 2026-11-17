"""Doplňování chybějících dílů: zjištění, řady, bodování, oba režimy (bez a s yt-dlp)."""
import time

import pytest

import doplnovani
import katalog
from pomocne import dil_ct
from zdroje import ivysilani, youtube

SID = "ct-879074-jaja-a-paja"


@pytest.fixture
def serial(monkeypatch):
    def nacti_porad(url, log=print):
        return {"nazev": "Jája a Pája", "obrazek": "o", "programme_id": "P1",
                "dily": [ivysilani._dil(dil_ct(n, n <= 13)) for n in range(1, 27)]}
    monkeypatch.setattr(ivysilani, "nacti_porad", nacti_porad)
    katalog.pridej_nebo_obnov("https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/")


def pockej(sid):
    for _ in range(200):
        st = doplnovani.stav(sid)
        if st["stav"] != "hledam":
            return st
        time.sleep(0.01)
    raise AssertionError("hledání neskončilo")


def test_chybejici_z_katalogu(serial):
    katalog.pridej_yt_dily(SID, [], cislo=14, meta={"id": "okurky00014", "nazev": "YT"})
    ch, poznamka = doplnovani.zjisti_chybejici(katalog.najdi(katalog.nacti(), SID))
    assert [d["cislo"] for d in ch] == list(range(15, 27)) and poznamka is None
    assert ch[0]["nazev"] == "15/26 Díl 15"


def test_rady_se_nepletou():
    s = {"dily": [{**ivysilani._dil(dil_ct(n, n != 2, {"title": r}, celkem=2)), "rucne": False}
                  for r in ("1. řada", "2. řada") for n in (1, 2)]}
    assert [(d["rada"], d["cislo"]) for d in doplnovani.zjisti_chybejici(s)[0]] == [("1. řada", 2), ("2. řada", 2)]


def test_serial_bez_cisel():
    s = {"dily": [{"id": "1", "nazev": "Pohádka", "dostupny": True, "rucne": False}]}
    ch, poznamka = doplnovani.zjisti_chybejici(s)
    assert ch == [] and "číslo" in poznamka


@pytest.mark.parametrize("titulek, nazev_dilu, ocekavam", [
    ("Jája a Pája - Jak spravovali hodiny", "Jak spravovali hodiny", 8.5),   # slovo z názvu dílu se netrestá
    ("Jája a Pája remix", "x", 4.5),                                         # 'mix' ≠ 'remix'
    ("Recept na guláš", "Jak pěstovali okurky", 0.0),                        # bez názvu seriálu = nic
])
def test_bodovani(titulek, nazev_dilu, ocekavam):
    assert doplnovani.skore({"nazev": titulek, "delka": 500}, "Jája a Pája", nazev_dilu, 4, 500) == ocekavam


def test_kompilace_ma_minus():
    k = {"nazev": "Jája a Pája – všechny díly (1 hodina)", "delka": 3600}
    assert doplnovani.skore(k, "Jája a Pája", "Jak pěstovali okurky", 4, 500) < 0


def test_bez_ytdlp_seznam_a_odkaz_na_hledani(serial):
    doplnovani.spust(SID)
    st = pockej(SID)
    assert st["stav"] == "hotovo" and st["hledani"] is False and len(st["chybejici"]) == 13
    assert st["chybejici"][0]["hledat_url"].startswith("https://www.youtube.com/results?search_query=J%C3%A1ja")


def test_s_ytdlp_navrhy(serial, monkeypatch):
    monkeypatch.setattr(youtube, "ma_yt_dlp", lambda: True)
    monkeypatch.setattr(youtube, "hledej", lambda q, pocet=8: [
        {"id": "kandidat001", "nazev": "Jája a Pája - Díl", "delka": 510, "kanal": "K", "obrazek": "o"},
        {"id": "gulas000001", "nazev": "Recept na guláš", "delka": 500, "kanal": "Z", "obrazek": "g"}])
    doplnovani.spust(SID)
    st = pockej(SID)
    assert st["hledani"] and [k["id"] for k in st["chybejici"][0]["kandidati"]] == ["kandidat001"]


def test_vyrizeno_podle_rady_a_cisla(serial):
    doplnovani.spust(SID)
    pockej(SID)
    doplnovani.vyrizeno(SID, 14, None)
    assert doplnovani.stav(SID)["chybejici"][0]["cislo"] == 15


def test_odebrany_serial_neuvizne():
    doplnovani._stav["zmizel"] = {"stav": "hledam"}
    doplnovani._hledej_vse("zmizel")
    assert doplnovani.stav("zmizel")["stav"] == "chyba"


def test_jen_pro_ivysilani():
    with pytest.raises(KeyError):
        doplnovani.spust("ct-neexistuje")
