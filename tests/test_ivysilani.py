"""Čtení dat z webu České televize – na skutečných vzorcích stránek (tests/vzorky)."""
import json

import pytest

from pomocne import dil_ct, graphql_get_episodes
from zdroje import ivysilani

URL_JAJA = "https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/"


def test_stranka_poradu_ze_skutecneho_vzorku(vzorek):
    p = ivysilani.zpracuj_stranku_poradu(vzorek("ct_porad_jaja_a_paja.html"), "879074-jaja-a-paja")
    assert p["nazev"] == "Jája a Pája"
    assert p["programme_id"] == "64892871f144ad37b50962c9"
    assert p["pocet_prehratelnych"] == 13
    assert [d["cislo"] for d in p["dily"]] == list(range(1, 11))
    assert p["dily"][3]["nazev"] == "4/26 Jak pěstovali okurky"
    assert p["dily"][0]["delka"] == 520 and p["dily"][0]["obrazek"].startswith("https://ctfs.ceskatelevize.cz/")
    assert "480" in p["obrazek"]


def test_kategorie_ze_skutecneho_vzorku(vzorek):
    porady, celkem = ivysilani.zpracuj_kategorii(vzorek("ct_kategorie_vecernicky_strana2.html"))
    assert celkem == 112 and len(porady) == 32
    assert porady[0] == {"nazev": "Gogo a Figi", "url": "https://www.ceskatelevize.cz/porady/1100266982-gogo-a-figi/",
                         "obrazek": porady[0]["obrazek"], "popis": None}


def test_nacti_porad_vsechny_dily(monkeypatch, vzorek):
    html = vzorek("ct_porad_jaja_a_paja.html")
    gql = graphql_get_episodes(set(range(1, 14)))
    monkeypatch.setattr(ivysilani, "_stahni", lambda url, extra=None: gql(url) if "graphql" in url else html)
    p = ivysilani.nacti_porad(URL_JAJA)
    assert len(p["dily"]) == 26
    assert sum(d["dostupny"] for d in p["dily"]) == 13
    assert p["dily"][-1]["nazev"] == "26/26 Díl 26"


def test_dotaz_pouziva_nastaveni_a_onlyplayable_false(monkeypatch, vzorek):
    dotazy = []

    def stahni(url, extra=None):
        dotazy.append(url)
        return graphql_get_episodes(set())(url) if "graphql" in url else vzorek("ct_porad_jaja_a_paja.html")
    monkeypatch.setattr(ivysilani, "_stahni", stahni)
    ivysilani.nacti_porad(URL_JAJA)
    g = [u for u in dotazy if "graphql" in u]
    assert len(g) == 3                                   # 26 dílů po 10
    assert ivysilani.nastaveni()["hash_get_episodes"] in g[0]
    assert "onlyPlayable%22%3Afalse" in g[0] and "programmeId%22%3A%2264892871f144ad37b50962c9" in g[0]


def test_pri_chybe_api_zustanou_dily_ze_stranky(monkeypatch, vzorek):
    html = vzorek("ct_porad_jaja_a_paja.html")

    def stahni(url, extra=None):
        if "graphql" in url:
            raise RuntimeError("PersistedQueryNotFound")
        return html
    monkeypatch.setattr(ivysilani, "_stahni", stahni)
    monkeypatch.setattr(ivysilani, "aktualizuj_nastaveni", lambda vynutit=False, log=print: False)
    zpravy = []
    p = ivysilani.nacti_porad(URL_JAJA, log=zpravy.append)
    assert len(p["dily"]) == 10 and "Použiji 10 dílů" in zpravy[0]


def test_odmitnuty_otisk_stahne_nove_nastaveni_a_zopakuje(monkeypatch, vzorek):
    html = vzorek("ct_porad_jaja_a_paja.html")
    novy = "a" * 64

    def stahni(url, extra=None):
        if "graphql" in url:
            if novy not in url:
                raise RuntimeError("PersistedQueryNotFound")
            return graphql_get_episodes(set(range(1, 27)))(url)
        return html

    def aktualizuj(vynutit=False, log=print):
        ivysilani.nastaveni()["hash_get_episodes"] = novy
        return True
    monkeypatch.setattr(ivysilani, "_stahni", stahni)
    monkeypatch.setattr(ivysilani, "aktualizuj_nastaveni", aktualizuj)
    assert len(ivysilani.nacti_porad(URL_JAJA)["dily"]) == 26


def test_kategorie_strankuje_a_radi_abecedne(monkeypatch):
    def stranka(od, n):
        ap = {"Genre:x": {"__typename": "Genre", f'programmeFind({{"limit":80,"offset":{od}}})':
                          {"totalCount": 4, "items": [{"__ref": f"Show:{i}"} for i in range(od, od + n)]}}}
        jmena = ["Čtyřlístek", "Bob a Bobek", "O krtkovi", "Cvalda Olda"]
        for i in range(od, od + n):
            ap[f"Show:{i}"] = {"slug": f"{i}-x", "title": jmena[i], "images": {}}
        return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({"props": {"apolloState": ap}}) + "</script>"
    dotazy = []

    def stahni(url, extra=None):
        dotazy.append(url)
        return stranka(2, 2) if "page=2" in url else stranka(0, 2)
    monkeypatch.setattr(ivysilani, "_stahni", stahni)
    v = ivysilani.nacti_vecernicky()
    assert [p["nazev"] for p in v] == ["Bob a Bobek", "Cvalda Olda", "Čtyřlístek", "O krtkovi"]
    assert len(dotazy) == 2


@pytest.mark.parametrize("odkaz, slug", [
    ("https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/", "879074-jaja-a-paja"),
    ("https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/287350951040001/", "879074-jaja-a-paja"),
])
def test_slug_poradu(odkaz, slug):
    assert ivysilani.slug_poradu(odkaz) == slug


def test_cislo_dilu_a_rada():
    assert ivysilani.cislo_dilu("4/26 Jak pěstovali okurky") == (4, 26)
    assert ivysilani.cislo_dilu("Bez čísla") == (None, None)
    assert ivysilani.nazev_bez_cisla("4/26 Jak pěstovali okurky") == "Jak pěstovali okurky"
    assert ivysilani._rada({"season": {"title": "2. řada"}}) == "2. řada"
    assert ivysilani._dil(dil_ct(3, rada={"title": "1. řada"}))["rada"] == "1. řada"


def test_poctivy_user_agent():
    ua = ivysilani.HLAVICKY["User-Agent"]
    assert ua.startswith("NaDobrouNoc/") and "Chrome" not in ua


def test_nastaveni_ct_pribalene_je_platne():
    assert ivysilani._platne(json.loads(ivysilani.NASTAVENI_PRIBALENE.read_text("utf-8")))


@pytest.mark.parametrize("zmena", [
    {"graphql_url": "https://zla-stranka.example/graphql/"},
    {"hash_get_episodes": "neni-hash"},
    {"kategorie_vecernicky": "https://www.ceskatelevize.cz/../../etc/"},
])
def test_nastaveni_ct_odmitne_podvrh(zmena):
    data = {**json.loads(ivysilani.NASTAVENI_PRIBALENE.read_text("utf-8")), **zmena}
    assert not ivysilani._platne(data)


def test_stazene_nastaveni_se_ulozi_a_pouzije(monkeypatch, cista_data):
    import io
    nove = {**json.loads(ivysilani.NASTAVENI_PRIBALENE.read_text("utf-8")), "graphql_verze": "9.9.9"}

    class Odpoved(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass
    monkeypatch.setattr(ivysilani.urllib.request, "urlopen", lambda req, timeout=10: Odpoved(json.dumps(nove).encode()))
    assert ivysilani.aktualizuj_nastaveni(vynutit=True, log=lambda z: None)
    assert ivysilani.nastaveni()["graphql_verze"] == "9.9.9"
    assert json.loads((cista_data / "ct_nastaveni.json").read_text())["graphql_verze"] == "9.9.9"
    ivysilani._nastaveni.clear()                         # po restartu se vezme uložená verze
    assert ivysilani.nastaveni()["graphql_verze"] == "9.9.9"


def test_aktualizace_nastaveni_bez_internetu_nic_nerozbije():
    assert ivysilani.aktualizuj_nastaveni(vynutit=True, log=lambda z: None) is False
    assert ivysilani._platne(ivysilani.nastaveni())
