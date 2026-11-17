"""Společné nastavení testů.

* Každý test má vlastní prázdnou datovou složku (NADOBROUNOC_DATA).
* Testy jsou ve výchozím stavu offline: spojení mimo tento počítač jsou zablokovaná,
  zdroje (ČT, YouTube) se nahrazují vzorky. Výjimkou jsou testy označené @pytest.mark.zivy,
  které ověřují skutečný web ČT (spouštějí se jen s volbou --zivy).
* Veřejná verze je výchozí: yt-dlp je vypnutý (NADOBROUNOC_BEZ_YTDLP=1).
"""
import os
import socket
import sys
import tempfile
from pathlib import Path

import pytest

KOREN = Path(__file__).resolve().parent.parent
VZORKY = Path(__file__).resolve().parent / "vzorky"
sys.path.insert(0, str(KOREN))
os.environ.setdefault("NADOBROUNOC_DATA", tempfile.mkdtemp(prefix="nadobrounoc-test-"))
os.environ["NADOBROUNOC_BEZ_YTDLP"] = "1"


def pytest_addoption(parser):
    parser.addoption("--zivy", action="store_true", help="spustit i testy proti skutečnému webu ČT")


def pytest_configure(config):
    config.addinivalue_line("markers", "zivy: test proti skutečnému webu ČT (jen s --zivy)")
    config.addinivalue_line("markers", "rozhrani: test rozhraní v prohlížeči (potřebuje Playwright)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--zivy"):
        return
    preskocit = pytest.mark.skip(reason="test proti živému webu – spusť s --zivy")
    for item in items:
        if "zivy" in item.keywords:
            item.add_marker(preskocit)


@pytest.fixture(autouse=True)
def offline(request, monkeypatch):
    """Zablokuje spojení mimo tento počítač (kromě testů @zivy)."""
    if "zivy" in request.keywords:
        yield
        return
    import server
    povolene = {"127.0.0.1", "localhost", "::1", server.ip_v_siti()}
    puvodni = socket.create_connection

    def jen_mistni(adresa, *a, **k):
        if adresa[0] not in povolene:
            raise OSError(f"test je offline – spojení na {adresa[0]} zablokováno")
        return puvodni(adresa, *a, **k)

    monkeypatch.setattr(socket, "create_connection", jen_mistni)
    yield


@pytest.fixture(autouse=True)
def cista_data(tmp_path, monkeypatch):
    """Prázdná datová složka a čisté vnitřní stavy modulů pro každý test."""
    import doplnovani
    import katalog
    from zdroje import ivysilani
    data = tmp_path / "data"
    monkeypatch.setenv("NADOBROUNOC_DATA", str(data))
    monkeypatch.setattr(katalog, "SLOZKA_DAT", data)
    monkeypatch.setattr(katalog, "SOUBOR", data / "katalog.json")
    monkeypatch.setattr(katalog, "log", lambda z: None)
    monkeypatch.setattr(ivysilani, "PRODLEVA", 0)
    ivysilani._nastaveni.clear()
    ivysilani._posledni_stazeni = 0.0
    doplnovani._stav.clear()
    yield data


@pytest.fixture
def vzorek():
    return lambda jmeno: (VZORKY / jmeno).read_text("utf-8")
