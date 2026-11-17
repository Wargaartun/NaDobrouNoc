"""YouTube bez yt-dlp: ID videí, oEmbed, playlist ze seznamu videí od prohlížeče."""
import urllib.error

import pytest

from zdroje import youtube


@pytest.mark.parametrize("odkaz, vid", [
    ("https://www.youtube.com/watch?v=USYeHXGvh7M", "USYeHXGvh7M"),
    ("https://youtu.be/USYeHXGvh7M?si=abc", "USYeHXGvh7M"),
    ("https://www.youtube.com/shorts/USYeHXGvh7M", "USYeHXGvh7M"),
    ("USYeHXGvh7M", "USYeHXGvh7M"),
    ("https://www.youtube.com/watch?v=<script>", None),
    ("nesmysl", None),
])
def test_id_videa(odkaz, vid):
    assert youtube.id_videa(odkaz) == vid


def test_bez_ytdlp_ve_verejne_verzi():
    assert youtube.ma_yt_dlp() is False


@pytest.fixture
def oembed(monkeypatch):
    def odpoved(url):
        if "zakazane" in url:
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
        if "playlist" in url:
            return {"title": "Méďové"}
        return {"title": "Video " + url[-11:]}
    monkeypatch.setattr(youtube, "_oembed", odpoved)


def test_info_videa(oembed):
    assert youtube.info_videa("https://youtu.be/aaaaaaaaaaa")["nazev"] == "Video aaaaaaaaaaa"
    with pytest.raises(ValueError, match="nedovolil"):
        youtube.info_videa("https://youtu.be/zakazane001")


def test_playlist_z_videi(oembed):
    p = youtube.playlist_z_videi("https://youtube.com/playlist?list=PLabcdefghij",
                                 ["aaaaaaaaaaa", "zakazane001", "aaaaaaaaaaa", "<spatne>"])
    assert p["nazev"] == "Méďové"
    assert [(d["id"], d["dostupny"]) for d in p["dily"]] == [("aaaaaaaaaaa", True), ("zakazane001", False)]


def test_playlist_bez_videi(oembed):
    with pytest.raises(ValueError):
        youtube.playlist_z_videi("https://youtube.com/playlist?list=PLabcdefghij", [])


def test_bez_internetu_je_srozumitelna_chyba():
    with pytest.raises(RuntimeError, match="připojení"):
        youtube.info_videa("https://youtu.be/aaaaaaaaaaa")


def test_ytdlp_funkce_hlasi_ze_chybi():
    with pytest.raises(RuntimeError, match="yt-dlp"):
        youtube.hledej("Jája a Pája")
