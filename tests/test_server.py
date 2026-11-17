"""Server: zabezpečení (Host, CSRF), ověřování vstupů, nastavení, přístup z mobilu, API."""
import urllib.error
import urllib.request

import pytest

import katalog
import server
from pomocne import TestovaciServer
from zdroje import youtube


@pytest.fixture
def srv():
    katalog.zaloz()
    with TestovaciServer() as s:
        yield s


def test_stranka_a_api(srv):
    assert srv.req("/")[0] == 200
    k, stav = srv.req("/api/stav")
    assert k == 200 and stav["nazev"] == "Na dobrou noc" and stav["yt_dlp"] is False and stav["sit"] is False


@pytest.mark.parametrize("host", ["rebind.zla-stranka.example", "rebind.zla-stranka.example:8000", "1.2.3.4"])
def test_cizi_host_odmitnut(srv, host):
    assert srv.req("/api/katalog", hlavicky={"Host": host})[0] == 403
    assert srv.req("/", hlavicky={"Host": host})[0] == 403


def test_localhost_povolen(srv):
    assert srv.req("/api/katalog", hlavicky={"Host": f"localhost:{srv.port}"})[0] == 200


def test_csrf(srv):
    znelka = {"url": "https://youtu.be/aaaaaaaaaaa"}
    assert srv.req("/api/znelka", "POST", znelka, aplikace=False)[0] == 403
    assert srv.req("/api/znelka", "POST", b'{"url":"https://youtu.be/aaaaaaaaaaa"}',
                   hlavicky={"Content-Type": "text/plain"})[0] == 415
    k, r = srv.req("/api/znelka", "POST", znelka, hlavicky={"Origin": "https://zla-stranka.example"})
    assert k == 403 and "cizí" in r["chyba"]
    assert srv.req("/api/serialy/x", "DELETE", aplikace=False)[0] == 403
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{srv.port}/api/znelka", method="OPTIONS"))
    assert e.value.code == 403
    assert katalog.nacti()["znelka"] is None
    k, r = srv.req("/api/znelka", "POST", znelka, hlavicky={"Origin": f"http://127.0.0.1:{srv.port}"})
    assert k == 200 and r["znelka"] == "aaaaaaaaaaa"


@pytest.mark.parametrize("cesta, telo", [
    ("/api/znelka", b"[1,2]"),
    ("/api/znelka", b"{rozbite"),
    ("/api/serialy", {"url": 5}),
    ("/api/serialy", {"url": "https://example.com/x"}),
    ("/api/nastaveni", {"sit": "ano"}),
    ("/api/vlastni", {"nazev": " "}),
])
def test_neplatne_vstupy(srv, cesta, telo):
    k, r = srv.req(cesta, "POST", telo)
    assert k == 400 and isinstance(r, dict) and r["chyba"] and "Traceback" not in r["chyba"]


def test_nezname_adresy(srv):
    assert srv.req("/api/neexistuje")[0] == 404
    assert srv.req("/api/neexistuje", "POST", {})[0] == 404


def test_pruvodce_a_kontrola_verze(srv):
    assert srv.req("/api/nastaveni", "POST", {"pruvodce_hotov": True})[1]["pruvodce_hotov"] is True
    assert srv.req("/api/nastaveni", "POST", {"kontrola_verze": False})[1]["kontrola_verze"] is False


def test_pristup_z_mobilu(srv):
    ip = server.ip_v_siti()
    if not ip:
        pytest.skip("počítač nemá adresu v síti")
    k, r = srv.req("/api/nastaveni", "POST", {"sit": True})
    assert k == 200 and r["sit"] is True
    assert srv.req("/api/stav")[1]["adresa_v_siti"] == f"http://{ip}:{srv.port}"
    assert srv.req("/api/stav", host=ip)[0] == 200                    # mobil v síti
    srv.req("/api/nastaveni", "POST", {"sit": False})
    with pytest.raises((urllib.error.URLError, ConnectionError, TimeoutError)):
        urllib.request.urlopen(f"http://{ip}:{srv.port}/api/stav", timeout=2)


def test_playlist_od_prohlizece(srv, monkeypatch):
    monkeypatch.setattr(youtube, "_oembed", lambda url: {"title": "Méďové" if "playlist" in url else "Video"})
    k, r = srv.req("/api/serialy", "POST", {"url": "https://youtube.com/playlist?list=PLabcdefghij",
                                            "videa": ["aaaaaaaaaaa", "ccccccccccc"]})
    assert k == 200 and r["id"] == "yt-PLabcdefghij" and len(r["dily"]) == 2
    k, r = srv.req("/api/serialy/yt-PLabcdefghij/obnovit", "POST", {"videa": ["ccccccccccc"]})
    assert [d["dostupny"] for d in r["dily"]] == [True, False]    # video zmizelo z playlistu
    k, r = srv.req("/api/serialy", "POST", {"url": "https://youtube.com/playlist?list=PLzzzzzzzzzz"})
    assert k == 400 and "prohlížeč" in r["chyba"]
