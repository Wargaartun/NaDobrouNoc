"""Pomocné funkce pro testy: napodobené odpovědi ČT a YouTube, testovací server."""
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from functools import partial


def dil_ct(n: int, prehratelny: bool = True, rada=None, celkem: int = 26) -> dict:
    """Díl ve tvaru, v jakém ho vrací GraphQL API ČT (EpisodePreview)."""
    return {"__typename": "EpisodePreview", "id": f"2873509510400{n:02d}", "title": f"{n}/{celkem} Díl {n}",
            "playable": prehratelny, "showId": "879074", "duration": 500, "season": rada,
            "images": {'card({"height":270,"width":480})': f"https://img/{n}.jpg"}}


def graphql_get_episodes(prehratelne: set, celkem: int = 26):
    """Napodobený dotaz GetEpisodes (onlyPlayable=false, stránkování po 10)."""
    def odpoved(url: str) -> str:
        v = json.loads(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["variables"][0])
        od = v["offset"]
        polozky = [dil_ct(n, n in prehratelne, celkem=celkem) for n in range(od + 1, min(od + 11, celkem + 1))]
        return json.dumps({"data": {"episodesPreviewFind": {"items": polozky}}})
    return odpoved


class TestovaciServer:
    """Server aplikace na náhodném portu (jen 127.0.0.1)."""

    __test__ = False   # pytest: není to testovací třída

    def __init__(self):
        import server
        self.srv = server.Server(("127.0.0.1", 0), partial(server.Obsluha, directory=str(server.STATIC)))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        import server
        server.vypni_sit()
        self.srv.shutdown()
        self.srv.server_close()

    def req(self, cesta, metoda="GET", telo=None, hlavicky=None, aplikace=True, host=None):
        h = {"Content-Type": "application/json"}
        if aplikace and metoda not in ("GET", "OPTIONS"):
            h["X-Na-Dobrou-Noc"] = "1"
        h.update(hlavicky or {})
        data = None
        if telo is not None:
            data = telo if isinstance(telo, bytes) else json.dumps(telo).encode()
        r = urllib.request.Request(f"http://{host or '127.0.0.1'}:{self.port}{cesta}", method=metoda, data=data, headers=h)
        try:
            with urllib.request.urlopen(r, timeout=10) as o:
                b = o.read()
                return o.status, (json.loads(b) if "json" in o.headers.get("Content-Type", "") else b)
        except urllib.error.HTTPError as e:
            b = e.read()
            try:
                return e.code, json.loads(b)
            except ValueError:
                return e.code, b
