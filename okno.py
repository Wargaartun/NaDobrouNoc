"""Na dobrou noc – spuštění s okénkem (hlavní způsob spuštění).

Co udělá:
  * Když aplikace už běží, jen otevře prohlížeč a skončí.
  * Jinak spustí server (port 8000, když je obsazený jiným programem, zkusí 8001–8009),
    otevře prohlížeč a ukáže malé okno s tlačítky „Otevřít“ a „Zastavit“.
    Zavření okna server také vypne.

Spuštění:  python3 okno.py [--port 8000]
Okno používá tkinter – na Linux Mintu: sudo apt install python3-tk
"""
import argparse
import os
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox

import cesty
import server

BARVY = {"pozadi": "#14193d", "text": "#f3f1ea", "tlumeny": "#a9afd0", "mesic": "#f7c95c", "tlacitko": "#27306a"}


def spust_server(prvni_port: int):
    """Vrátí (server, port), nebo (None, port) když už naše aplikace běží."""
    chyba = None
    for port in range(prvni_port, prvni_port + 10):
        if server.nas_server_bezi(port):
            return None, port
        try:
            return server.vytvor_server(port), port
        except OSError as e:   # port obsadil jiný program → zkusíme další
            chyba = e
    raise OSError(f"Nenašel jsem volný port ({prvni_port}–{prvni_port + 9}): {chyba}")


def main():
    p = argparse.ArgumentParser(description=f"{cesty.NAZEV} – server s okénkem")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--neotvirat", action="store_true", help="neotvírat prohlížeč (pro testy)")
    a = p.parse_args()

    try:
        srv, port = spust_server(a.port)
    except OSError as e:
        koren = tk.Tk()
        koren.withdraw()
        messagebox.showerror(cesty.NAZEV, f"Aplikaci se nepodařilo spustit.\n\n{e}")
        return
    adresa = f"http://localhost:{port}"
    if srv is None:                       # už běží → jen otevřít
        if not a.neotvirat:
            webbrowser.open(adresa)
        return

    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pid = cesty.slozka_dat() / "server.pid"     # pro zastavit.sh a nabídku ikony
    pid.write_text(str(os.getpid()))
    if not a.neotvirat:
        webbrowser.open(adresa)

    okno = tk.Tk()
    okno.title(cesty.NAZEV)
    okno.configure(bg=BARVY["pozadi"], padx=28, pady=22)
    okno.resizable(False, False)

    def zastavit():
        tl_stop.configure(text="Zastavuji…", state="disabled")
        okno.update_idletasks()
        server.vypni_sit()
        srv.shutdown()        # zastaví příjem nových požadavků
        srv.server_close()
        print("Server zastaven.", flush=True)
        pid.unlink(missing_ok=True)
        okno.destroy()

    okno.protocol("WM_DELETE_WINDOW", zastavit)   # křížek = zastavit

    tk.Label(okno, text=f"{cesty.NAZEV} běží", font=("Sans", 16, "bold"),
             bg=BARVY["pozadi"], fg=BARVY["mesic"]).pack(anchor="w")
    tk.Label(okno, text="Nech toto okno otevřené, dokud se díváte.\n"
                        "Přístup z mobilu zapneš v aplikaci ve Správě.",
             justify="left", font=("Sans", 10), bg=BARVY["pozadi"], fg=BARVY["tlumeny"]
             ).pack(anchor="w", pady=(6, 16))
    tk.Button(okno, text=f"Otevřít {cesty.NAZEV}", command=lambda: webbrowser.open(adresa),
              font=("Sans", 12, "bold"), bg=BARVY["mesic"], fg="#1c1a10", activebackground="#ffd56f",
              relief="flat", padx=18, pady=10, cursor="hand2").pack(fill="x")
    tl_stop = tk.Button(okno, text="Zastavit", command=zastavit, font=("Sans", 11),
                        bg=BARVY["tlacitko"], fg=BARVY["text"], activebackground="#333d80",
                        activeforeground=BARVY["text"], relief="flat", padx=18, pady=8, cursor="hand2")
    tl_stop.pack(fill="x", pady=(8, 0))
    tk.Label(okno, text="Zavřením okna se aplikace také vypne.", font=("Sans", 9),
             bg=BARVY["pozadi"], fg=BARVY["tlumeny"]).pack(pady=(10, 0))

    okno.mainloop()


if __name__ == "__main__":
    main()
