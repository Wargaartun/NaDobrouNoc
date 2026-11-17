"""Okno (volba portu, už běžící aplikace) a kontrola nové verze."""
import json
import socket
import sys
import threading
import types

import pytest

import aktualizace
import cesty


@pytest.fixture
def okno(monkeypatch):
    """okno.py bez skutečného tkinteru (v CI není grafické prostředí)."""
    tk = types.ModuleType("tkinter")
    tk.Tk = object
    mb = types.ModuleType("tkinter.messagebox")
    tk.messagebox = mb
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setitem(sys.modules, "tkinter.messagebox", mb)
    monkeypatch.setattr(aktualizace, "spust_na_pozadi", lambda povoleno: None)
    sys.modules.pop("okno", None)
    import okno
    return okno


def test_obsazeny_port_a_bezici_aplikace(okno):
    cizi = socket.socket()
    cizi.bind(("127.0.0.1", 0))
    cizi.listen()
    obsazeny = cizi.getsockname()[1]
    try:
        srv, port = okno.spust_server(obsazeny)
        assert srv is not None and port != obsazeny          # cizí program → další port
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            srv2, port2 = okno.spust_server(port)
            assert srv2 is None and port2 == port             # naše aplikace už běží → jen otevřít
        finally:
            srv.shutdown()
            srv.server_close()
    finally:
        cizi.close()


@pytest.mark.parametrize("kandidat, aktualni, novejsi", [
    ("v0.6.0", "0.5.0", True), ("0.5.1", "0.5.0", True), ("v1.0", "0.9.9", True),
    ("v0.5.0", "0.5.0", False), ("0.4.9", "0.5.0", False), ("nesmysl", "0.5.0", False),
])
def test_porovnani_verzi(kandidat, aktualni, novejsi):
    assert aktualizace.je_novejsi(kandidat, aktualni) is novejsi


def test_kontrola_verze(monkeypatch, cista_data):
    import io

    class Odpoved(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass
    vydani = {"tag_name": "v9.0.0", "html_url": f"https://github.com/{cesty.REPOZITAR}/releases/tag/v9.0.0"}
    monkeypatch.setattr(aktualizace.urllib.request, "urlopen", lambda req, timeout=10: Odpoved(json.dumps(vydani).encode()))
    assert aktualizace.zkontroluj(vynutit=True) == {"verze": "9.0.0", "url": vydani["html_url"]}
    # podvržený odkaz mimo repozitář se nezobrazí
    vydani["html_url"] = "https://zla-stranka.example/stahni"
    assert aktualizace.zkontroluj(vynutit=True) is None


def test_kontrola_verze_bez_internetu():
    assert aktualizace.zkontroluj(vynutit=True) is None


def test_kontrolni_spusteni(okno):
    assert okno.kontrola(8790) == 0


def test_vypis_do_souboru_v_zabalenem_programu(okno, monkeypatch, cista_data):
    monkeypatch.setattr(cesty, "ZABALENO", True)
    monkeypatch.setattr(sys, "stdout", None)        # Windows bez konzole
    monkeypatch.setattr(sys, "stderr", None)
    okno.nastav_vypis()
    print("ahoj z testu")
    sys.stdout.flush()
    sys.stdout.close()                               # na Windows nejde smazat otevřený soubor
    log = (cista_data / "server.log").read_text("utf-8")
    assert "spuštění Na dobrou noc" in log and "ahoj z testu" in log


def test_prostredi_pro_prohlizec_na_linuxu(okno, monkeypatch):
    monkeypatch.setattr(cesty, "ZABALENO", True)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/puvodni")
    okno.oprav_prostredi()
    import os
    assert os.environ["LD_LIBRARY_PATH"] == "/usr/lib/puvodni" and "LD_LIBRARY_PATH_ORIG" not in os.environ
