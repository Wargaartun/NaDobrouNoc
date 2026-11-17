"""Rozhraní v prohlížeči (Playwright + Chromium): průvodce, přehrávání, doplňování, mobil.

YouTube přehrávač se napodobuje (v testu není internet): getPlaylist vrátí tři videa,
loadVideoById po chvíli ohlásí konec. window.open vrátí objekt, jehož zavření test řídí.
Spuštění: pip install pytest-playwright && playwright install chromium
"""
import os
import shutil

import pytest

import katalog
from pomocne import TestovaciServer
from zdroje import ivysilani, youtube

playwright = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.rozhrani

OBR = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 9'%3E%3Crect width='16' height='9' fill='%234c7a4a'/%3E%3C/svg%3E"

NAPODOBENY_YT = """
window.__prehrano = [];
window.YT = { PlayerState: { ENDED: 0 }, Player: class {
  constructor(el, o) { this.o = o; setTimeout(() => o.events && o.events.onReady && o.events.onReady({ target: this }), 20); }
  getPlaylist() { return this.o.playerVars && this.o.playerVars.list ? ['aaaaaaaaaaa', 'bbbbbbbbbbb', 'ccccccccccc'] : null; }
  loadVideoById(id) { window.__prehrano.push(id); setTimeout(() => this.o.events.onStateChange({ data: 0 }), 60); }
  stopVideo() {} destroy() {} } };
window.__karta = { closed: false };
window.open = () => window.__karta;
document.addEventListener('DOMContentLoaded', () => setTimeout(() => window.onYouTubeIframeAPIReady && window.onYouTubeIframeAPIReady(), 30));
"""


@pytest.fixture
def aplikace(monkeypatch):
    def dil(n, ok):
        return {"id": f"2873509510400{n:02d}", "nazev": f"{n}/6 Jak šli na houby", "typ": "ivysilani", "cislo": n,
                "rada": None, "delka": 540, "obrazek": OBR, "dostupny": ok}
    monkeypatch.setattr(ivysilani, "nacti_porad", lambda url, log=print: {
        "nazev": "Jája a Pája", "obrazek": OBR, "programme_id": "P1", "dily": [dil(n, n not in (4, 5)) for n in range(1, 7)]})
    monkeypatch.setattr(ivysilani, "nacti_vecernicky", lambda: [
        {"nazev": n, "url": f"https://www.ceskatelevize.cz/porady/{s}/", "obrazek": OBR, "popis": ""}
        for n, s in [("Bob a Bobek", "902567-bob-a-bobek"), ("Jája a Pája", "879074-jaja-a-paja"), ("Krtek", "1-krtek")]])
    monkeypatch.setattr(youtube, "_oembed", lambda url: {"title": "Méďové" if "playlist" in url else "Méďové díl"})
    katalog.zaloz()
    with TestovaciServer() as s:
        yield s


@pytest.fixture
def prohlizec():
    chrome = os.environ.get("CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else p.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Chromium není k dispozici: {e}")
        yield b
        b.close()


def stranka(prohlizec, aplikace, napodobit_yt=True, sirka=390):
    pg = prohlizec.new_page(viewport={"width": sirka, "height": 844})
    chyby = []
    pg.on("pageerror", lambda e: chyby.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith("http://127.0.0.1") else r.continue_())
    if napodobit_yt:
        pg.add_init_script(NAPODOBENY_YT)
    pg.goto(f"http://127.0.0.1:{aplikace.port}/")
    return pg, chyby


def test_cely_vecer(prohlizec, aplikace):
    pg, chyby = stranka(prohlizec, aplikace)

    # průvodce: znělka, výběr pohádky s hledáním, playlist z YouTube
    pg.fill("#pruvodceZnelka [name=url]", "https://www.youtube.com/watch?v=USYeHXGvh7M")
    pg.click("#pruvodceZnelka button")
    pg.wait_for_selector(".volba")
    pg.fill("#hledat", "jaja")
    assert [e.inner_text() for e in pg.query_selector_all(".volba b") if e.is_visible()] == ["Jája a Pája"]
    pg.click(".volba >> text=Jája a Pája")
    pg.fill("#pruvodcePlaylisty", "https://youtube.com/playlist?list=PLmedove0001")
    assert pg.inner_text("#pruvodceHotovo") == "Hotovo – přidat 1"
    pg.click("#pruvodceHotovo")
    pg.wait_for_selector(".dlazdice")
    assert sorted(pg.locator(".dlazdice h2").all_inner_texts()) == ["Jája a Pája", "Méďové"]

    # YouTube: znělka → díl → Dobrou noc
    pg.click(".dlazdice >> text=Méďové")
    pg.click(".velke-tlacitko")
    pg.wait_for_function("document.querySelector('#kinoPanel h2')?.textContent === 'Dobrou noc!'")
    assert pg.evaluate("window.__prehrano") == ["USYeHXGvh7M", "aaaaaaaaaaa"]
    pg.click("[data-kino=zavrit]")

    # iVysílání: díly 4 a 5 chybí, znělka → nová karta → po zavření Dobrou noc
    pg.click("#zpet")
    pg.click(".dlazdice >> text=Jája a Pája")
    assert [t[:3] for t in pg.locator(".dil b").all_inner_texts()] == ["1/6", "2/6", "3/6", "6/6"]
    pg.click(".velke-tlacitko")
    pg.wait_for_selector("[data-kino=hotovo]")
    pg.evaluate("window.__karta.closed = true")
    pg.wait_for_function("document.querySelector('#kinoPanel h2')?.textContent === 'Dobrou noc!'")
    pg.click("[data-kino=zavrit]")

    # doplnění bez yt-dlp: seznam chybějících, odkaz na hledání, vložení odkazu
    pg.click("#spravaBtn")
    pg.click("[data-akce=dily][data-id='ct-879074-jaja-a-paja']")
    pg.click("[data-akce=doplnit]")
    pg.wait_for_selector(".chybejici")
    assert "chybějí 2 díly" in pg.inner_text(".doplneni > p")
    assert pg.get_attribute(".chybejici a.btn", "href").startswith("https://www.youtube.com/results?search_query=")
    f = pg.locator(".chybejici form").first
    f.locator("input").fill("https://youtu.be/okurky00004")
    f.locator("button").click()
    pg.wait_for_function("document.querySelector('.chybejici-hlava b')?.textContent.startsWith('5/6')")

    # přístup z mobilu
    pg.click("[data-akce=sit][data-zapnout='1']")
    pg.wait_for_selector("[data-akce=sit][data-zapnout='0']")
    pg.click("[data-akce=sit][data-zapnout='0']")
    pg.wait_for_selector("[data-akce=sit][data-zapnout='1']")
    assert chyby == []


def test_bez_prehravace_youtube(prohlizec, aplikace):
    katalog.nastav(pruvodce_hotov=True)
    katalog.pridej_nebo_obnov("https://youtube.com/playlist?list=PLmedove0001", videa=["aaaaaaaaaaa"])
    pg, chyby = stranka(prohlizec, aplikace, napodobit_yt=False, sirka=1280)
    pg.click(".dlazdice >> text=Méďové")
    pg.click(".velke-tlacitko")
    pg.wait_for_selector("#kinoPanel h2")
    assert pg.inner_text("#kinoPanel h2") == "Přehrávač YouTube se nenačetl"
    assert chyby == []
