"""Testy proti skutečnému webu České televize.

Spouštějí se jen s volbou --zivy (každý týden automaticky na GitHubu, viz
.github/workflows/zivy-web.yml). Když selžou, ČT pravděpodobně změnila web nebo API
a je potřeba upravit ct_nastaveni.json nebo zdroje/ivysilani.py – viz CONTRIBUTING.md.
"""
import pytest

from zdroje import ivysilani

pytestmark = pytest.mark.zivy
URL_JAJA = "https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/"


def test_stranka_poradu_ma_ocekavanou_strukturu():
    p = ivysilani.zpracuj_stranku_poradu(ivysilani._stahni(URL_JAJA), "879074-jaja-a-paja")
    assert p["nazev"] and p["programme_id"]
    assert p["dily"], "na stránce pořadu nejsou díly (EpisodePreview) – změnila se struktura __NEXT_DATA__?"


def test_dotaz_getepisodes_funguje():
    p = ivysilani.zpracuj_stranku_poradu(ivysilani._stahni(URL_JAJA), "879074-jaja-a-paja")
    # bez automatické aktualizace nastavení – chceme vědět, jestli platí hodnoty v repozitáři
    dily = ivysilani._dotaz_get_episodes(p["programme_id"], 0, "oldest", False)
    assert dily, "GetEpisodes nevrátil žádné díly – změnil se otisk dotazu nebo verze klienta?"
    assert all(ivysilani.RE_IDEC.match(d["id"]) for d in dily)


def test_cely_porad():
    p = ivysilani.nacti_porad(URL_JAJA, log=lambda z: pytest.fail(f"varování při načítání: {z}"))
    assert len(p["dily"]) >= len([d for d in p["dily"] if d["dostupny"]]) > 0


def test_kategorie_vecernicky():
    porady, celkem = ivysilani.zpracuj_kategorii(ivysilani._stahni(ivysilani.nastaveni()["kategorie_vecernicky"]))
    assert porady and celkem and celkem >= len(porady)


def test_prehravac_ct_existuje():
    import urllib.request
    req = urllib.request.Request(ivysilani.url_prehravace("287350951040001"), headers=ivysilani.HLAVICKY)
    with urllib.request.urlopen(req, timeout=20) as r:
        assert r.status == 200
