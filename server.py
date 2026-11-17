"""Na dobrou noc – lokální server.

Spuštění:   python3 server.py            (port 8000, jen tento počítač)
            python3 server.py --port 8080
Obvykle se ale spouští přes okno.py (okénko s tlačítkem Zastavit).

Server dělá dvě věci:
  1. posílá prohlížeči soubory aplikace ze složky static/,
  2. nabízí malé JSON API (/api/…), přes které aplikace čte a upravuje katalog.

Bezpečnost (server běží na počítači rodiče a je dosažitelný z jeho prohlížeče):
  * Poslouchá jen na 127.0.0.1. Přístup z mobilu se zapíná ve Správě – pak server
    otevře druhé „ucho“ na adrese počítače v domácí síti.
  * Hlavička Host musí být adresa tohoto počítače (ochrana proti DNS rebindingu).
  * Změny (POST, DELETE) musí mít Content-Type application/json a hlavičku
    X-Na-Dobrou-Noc; cizí stránka je tak nemůže poslat (prohlížeč by se nejdřív
    zeptal přes OPTIONS a server odmítne). Když přijde hlavička Origin, musí sedět s Host.
"""
import argparse
import json
import socket
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import aktualizace
import cesty
import doplnovani
import katalog
from zdroje import ivysilani

STATIC = cesty.SLOZKA_PROGRAMU / "static"
HLAVICKA_APLIKACE = "X-Na-Dobrou-Noc"
MAX_TELO = 1_000_000

# seznam večerníčků z iVysílání si pamatujeme hodinu, ať se pořád nestahuje
_vecernicky = {"cas": 0.0, "data": None}


class Server(ThreadingHTTPServer):
    """HTTP server aplikace.

    Na Windows znamená SO_REUSEADDR, že jde otevřít i port, který už používá jiný program –
    aplikace by mu ho „ukradla“. Tam proto opakované použití adresy vypínáme.
    """
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True


class ChybaPozadavku(Exception):
    def __init__(self, zprava, kod=400):
        super().__init__(zprava)
        self.kod = kod


# ---------- síť ----------
def ip_v_siti() -> str | None:
    """Adresa počítače v domácí síti (pro otevření z mobilu)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 1))  # nic se neposílá, jen se zjistí rozhraní
            ip = s.getsockname()[0]
            return None if ip.startswith("127.") else ip
    except OSError:
        return None


def povolene_hosty() -> set[str]:
    jmeno = socket.gethostname().lower()
    hosty = {"localhost", "127.0.0.1", "::1", jmeno, f"{jmeno}.local"}
    if _sit["server"]:
        hosty.add(_sit["ip"])
    return hosty


def _jen_host(hodnota: str) -> str:
    """'192.168.1.5:8000' → '192.168.1.5', '[::1]:8000' → '::1'."""
    hodnota = (hodnota or "").strip().lower()
    if hodnota.startswith("["):
        return hodnota[1:hodnota.find("]")]
    return hodnota.rsplit(":", 1)[0] if hodnota.count(":") == 1 else hodnota


_sit = {"server": None, "ip": None, "port": None}


def zapni_sit(port: int) -> str:
    """Otevře server i pro zařízení v domácí síti. Vrací adresu pro mobil."""
    if _sit["server"]:
        return f"http://{_sit['ip']}:{_sit['port']}"
    ip = ip_v_siti()
    if not ip:
        raise ChybaPozadavku("Počítač není připojený k domácí síti")
    try:
        srv = Server((ip, port), partial(Obsluha, directory=str(STATIC)))
    except OSError as e:
        raise ChybaPozadavku(f"Přístup ze sítě nejde zapnout: {e.strerror or e}") from e
    _sit.update(server=srv, ip=ip, port=port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    katalog.log(f"📱 Přístup z mobilu zapnut: http://{ip}:{port}")
    return f"http://{ip}:{port}"


def vypni_sit() -> None:
    srv = _sit["server"]
    if srv:
        _sit.update(server=None, ip=None, port=None)
        srv.shutdown()
        srv.server_close()
        katalog.log("📱 Přístup z mobilu vypnut")


# ---------- obsluha požadavků ----------
class Obsluha(SimpleHTTPRequestHandler):
    # ---------- pomocné ----------
    def _json(self, data, kod=200):
        telo = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(telo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(telo)

    def _chyba(self, zprava, kod=400):
        self._json({"chyba": zprava}, kod)

    def _telo(self) -> dict:
        delka = int(self.headers.get("Content-Length") or 0)
        if delka > MAX_TELO:
            raise ChybaPozadavku("Požadavek je příliš velký", 413)
        if not delka:
            return {}
        try:
            data = json.loads(self.rfile.read(delka))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ChybaPozadavku("Tělo požadavku není platný JSON") from e
        if not isinstance(data, dict):
            raise ChybaPozadavku("Tělo požadavku musí být objekt JSON")
        return data

    def _cesta(self) -> list[str]:
        return [c for c in urlparse(self.path).path.split("/") if c]

    def _over_host(self) -> bool:
        if _jen_host(self.headers.get("Host", "")) in povolene_hosty():
            return True
        self.send_error(403, "Neznama adresa serveru")
        return False

    def _over_zmenu(self):
        """Změny smí posílat jen tahle aplikace (ochrana proti cizím stránkám – CSRF)."""
        if self.headers.get(HLAVICKA_APLIKACE) != "1":
            raise ChybaPozadavku("Chybí hlavička aplikace", 403)
        if self.command == "POST" and not (self.headers.get("Content-Type") or "").startswith("application/json"):
            raise ChybaPozadavku("Očekávám application/json", 415)
        origin = self.headers.get("Origin")
        if origin and origin != "null":
            if _jen_host(urlparse(origin).netloc) != _jen_host(self.headers.get("Host", "")):
                raise ChybaPozadavku("Požadavek z cizí stránky", 403)

    def log_message(self, fmt, *args):  # tišší výpis – jen API, bez častých dotazů na stav
        p = self.path
        if p.startswith("/api/") and not (self.command == "GET" and (p.startswith("/api/stav") or p.endswith("/doplneni"))):
            super().log_message(fmt, *args)

    def end_headers(self):
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _obsluz(self, funkce):
        try:
            if self.command != "GET":
                self._over_zmenu()
            funkce()
        except ChybaPozadavku as e:
            self._chyba(str(e), e.kod)
        except (ValueError, KeyError) as e:
            self._chyba(str(e).strip("'"), 400)
        except TypeError:
            self._chyba("Neplatný požadavek", 400)
        except Exception as e:  # noqa: BLE001
            self._chyba(str(e), 500)

    # ---------- metody ----------
    def do_OPTIONS(self):   # žádné CORS – cizí stránky odmítáme
        self.send_error(403)

    def do_GET(self):
        if not self._over_host():
            return
        if self._cesta()[:1] != ["api"]:
            return super().do_GET()
        self._obsluz(self._get)

    def do_POST(self):
        if self._over_host():
            self._obsluz(self._post)

    def do_DELETE(self):
        if self._over_host():
            self._obsluz(self._delete)

    # ---------- GET ----------
    def _get(self):
        c = self._cesta()
        if c == ["api", "katalog"]:
            return self._json(katalog.nacti())
        if c == ["api", "stav"]:
            port = self.server.server_address[1]
            ip = _sit["ip"] or ip_v_siti()
            return self._json({**katalog.stav(), "sit": bool(_sit["server"]),
                               "adresa_v_siti": f"http://{ip}:{port}" if ip else None})
        if c == ["api", "vecernicky"]:
            if time.time() - _vecernicky["cas"] > 3600 or not _vecernicky["data"]:
                _vecernicky["data"] = ivysilani.nacti_vecernicky()
                _vecernicky["cas"] = time.time()
            return self._json(_vecernicky["data"])
        if len(c) == 4 and c[1] == "serialy" and c[3] == "doplneni":
            return self._json(doplnovani.stav(c[2]))
        raise ChybaPozadavku("Neznámá adresa", 404)

    # ---------- POST ----------
    def _post(self):
        c = self._cesta()
        t = self._telo()
        # přidat seriál: {"url": "...", "nazev": "volitelně", "videa": [id, …] – playlist načtený prohlížečem}
        if c == ["api", "serialy"]:
            url = _text(t.get("url"), 500)
            katalog.id_pro_url(url)  # ověří, že odkaz umíme (jinak ValueError)
            return self._json(katalog.pridej_nebo_obnov(url, _text(t.get("nazev"), 100) or None, _seznam(t.get("videa"))))
        if c == ["api", "obnovit"]:
            threading.Thread(target=katalog.obnov_vse, daemon=True).start()
            return self._json({"ok": True})
        if c == ["api", "vlastni"]:
            return self._json(katalog.vytvor_vlastni(t.get("nazev"), _odkazy(t)))
        if c == ["api", "znelka"]:
            return self._json({"znelka": katalog.nastav_znelku(t.get("url"))})
        if c == ["api", "nastaveni"]:
            return self._json(self._nastaveni(t))
        if len(c) >= 3 and c[1] == "serialy":
            sid = c[2]
            if len(c) == 3:   # {"nazev_vlastni": "...", "zrusit_zhlednuti": true}
                return self._json(katalog.uprav_serial(sid, nazev_vlastni=t.get("nazev_vlastni"),
                                                       zrusit_zhlednuti=t.get("zrusit_zhlednuti") is True))
            akce = c[3]
            if akce == "obnovit" and len(c) == 4:
                s = katalog.najdi(katalog.nacti(), sid)
                if not s:
                    raise ChybaPozadavku("Seriál nenalezen", 404)
                if not s.get("zdroj"):
                    raise ChybaPozadavku("Vlastní seriál nemá odkud se obnovit")
                return self._json(katalog.pridej_nebo_obnov(s["zdroj"], videa=_seznam(t.get("videa")),
                                                            jen_existujici=True))
            if akce == "youtube" and len(c) == 4:
                # {"odkazy": [...]} nebo {"meta": {…návrh z hledání…}, "cislo": 4, "rada": null, "nazev": "4/26 …"}
                cislo, rada = t.get("cislo"), t.get("rada")
                v = katalog.pridej_yt_dily(sid, _odkazy(t), cislo=cislo, rada=rada,
                                           nazev_dilu=t.get("nazev"), meta=t.get("meta"))
                if v["pridano"]:
                    doplnovani.vyrizeno(sid, cislo, rada)
                elif v["chyby"]:
                    raise ChybaPozadavku("; ".join(v["chyby"]))
                return self._json(v)
            if akce == "doplnit" and len(c) == 4:
                return self._json(doplnovani.spust(sid))
            if akce == "preskocit" and len(c) == 4:
                doplnovani.vyrizeno(sid, t.get("cislo"), t.get("rada"))
                return self._json(doplnovani.stav(sid))
            if akce == "dily" and len(c) == 5:   # {"skryty": true} / {"zhlednuto": "…"}
                return self._json(katalog.uprav_dil(sid, c[4], skryty=t.get("skryty"), zhlednuto=t.get("zhlednuto")))
        raise ChybaPozadavku("Neznámá adresa", 404)

    def _nastaveni(self, t: dict) -> dict:
        if "sit" in t:
            if t["sit"] is True:
                zapni_sit(self.server.server_address[1])
            elif t["sit"] is False:
                vypni_sit()
            else:
                raise ChybaPozadavku("„sit“ musí být ano/ne")
        vysledek = katalog.nastav(**{k: t[k] for k in ("sit", "pruvodce_hotov", "kontrola_verze") if k in t})
        if t.get("kontrola_verze") is True:
            threading.Thread(target=aktualizace.zkontroluj, daemon=True).start()
        return vysledek

    # ---------- DELETE ----------
    def _delete(self):
        c = self._cesta()
        if len(c) == 3 and c[:2] == ["api", "serialy"]:
            katalog.odeber(c[2])
            return self._json({"ok": True})
        if len(c) == 5 and c[:2] == ["api", "serialy"] and c[3] == "dily":
            katalog.odeber_dil(c[2], c[4])
            return self._json({"ok": True})
        raise ChybaPozadavku("Neznámá adresa", 404)


def _text(hodnota, delka: int) -> str:
    if hodnota is None:
        return ""
    if not isinstance(hodnota, str):
        raise ChybaPozadavku("Očekávám text")
    return hodnota.strip()[:delka]


def _seznam(hodnota) -> list[str] | None:
    if hodnota is None:
        return None
    if not isinstance(hodnota, list) or not all(isinstance(x, str) for x in hodnota):
        raise ChybaPozadavku("Očekávám seznam textů")
    return hodnota[:500]


def _odkazy(telo: dict) -> list[str]:
    """Odkazy z těla požadavku – seznam, nebo text s odkazem na každém řádku."""
    o = telo.get("odkazy") or []
    if isinstance(o, str):
        o = o.split()
    return [x.strip() for x in _seznam(o) or [] if x and x.strip()]


# ---------- spuštění ----------
def nas_server_bezi(port: int) -> bool:
    """Běží už na tomhle portu naše aplikace?"""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/stav", timeout=1) as r:
            return json.loads(r.read()).get("nazev") == cesty.NAZEV
    except Exception:  # noqa: BLE001
        return False


def vytvor_server(port: int) -> ThreadingHTTPServer:
    """Připraví server na 127.0.0.1 (ještě neběží – spustí ho serve_forever())."""
    katalog.zaloz()
    server = Server(("127.0.0.1", port), partial(Obsluha, directory=str(STATIC)))
    # na pozadí: aktuální nastavení ČT z repozitáře a kontrola nové verze (jednou denně)
    threading.Thread(target=ivysilani.aktualizuj_nastaveni, kwargs={"log": katalog.log}, daemon=True).start()
    aktualizace.spust_na_pozadi(lambda: katalog.nacti()["nastaveni"].get("kontrola_verze", True))
    print(f"🌙 {cesty.NAZEV} běží: http://localhost:{port}", flush=True)
    if katalog.nacti()["nastaveni"].get("sit"):
        try:
            print(f"   z mobilu ve stejné Wi-Fi: {zapni_sit(port)}", flush=True)
        except ChybaPozadavku as e:
            print(f"   přístup z mobilu: {e}", flush=True)
    return server


def main():
    p = argparse.ArgumentParser(description=f"{cesty.NAZEV} – lokální server")
    p.add_argument("--port", type=int, default=8000)
    a = p.parse_args()

    server = vytvor_server(a.port)
    pid = cesty.slozka_dat() / "server.pid"
    pid.write_text(str(__import__("os").getpid()))
    print("   Ukončení: Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKonec.")
    finally:
        pid.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
