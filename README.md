# 🌙 Na dobrou noc

Večerníčky a pohádky před spaním z **iVysílání** a **YouTube** – na jednom místě, se znělkou
před každým dílem, tak jako v televizi.

Aplikace je pro rodiče: běží na domácím počítači a ovládá se v prohlížeči na počítači
(třeba připojeném k televizi) nebo na mobilu v domácí Wi-Fi. Pamatuje si zhlédnuté díly,
umí pustit „další díl“ a místo doporučených videí ukáže na konci „Dobrou noc!“.

- **Zdarma, bez reklam, svobodný software** (GPL-3.0).
- **Nic nestahuje:** díly hrají oficiální přehrávače iVysílání a YouTube.
- **Data zůstávají u tebe:** katalog je jen na tvém počítači.

> Projekt není spojený s Českou televizí ani s YouTube. Slovo „večerníček“ používá jen
> popisně. Pořady patří jejich autorům a vysílatelům.

## Stažení

Nejnovější verze je na stránce **[Vydání (Releases)](https://github.com/Wargaartun/NaDobrouNoc/releases/latest)**:

- **Windows 10 a 11:** `NaDobrouNoc-…-instalator.exe` – stáhnout, spustit, klikat na Další.
  Windows napoprvé ukáže okno „Systém Windows ochránil váš počítač“, protože aplikace nemá placený
  podpis: klikni na **Další informace** → **Přesto spustit**.
- **Linux:** `NaDobrouNoc-…-x86_64.AppImage` – povolit spouštění (Vlastnosti → Oprávnění) a spustit dvojklikem.

Podrobný návod je u každého vydání. Python ani nic dalšího instalovat nemusíš.
Aplikace sama upozorní, když vyjde nová verze.

## Co aplikace umí

- **Průvodce prvním spuštěním:** znělka (odkaz na video na YouTube, nepovinné) a výběr pohádek.
- **Celá nabídka Večerníčků z iVysílání**, přidání jedním klepnutím, hledání bez diakritiky.
- **YouTube playlisty** a **vlastní seriály** z jednotlivých videí.
- **Chybějící díly:** když díl na iVysílání zrovna není, aplikace ho ukáže a pomůže ho najít na YouTube.
- **Přehrávání:** znělka → díl → „Dobrou noc!“; díly z iVysílání v nové kartě (ČT nedovoluje vložit
  svůj přehrávač do cizí stránky).
- **Přístup z mobilu** jako vypínač ve Správě.

## Spuštění ze zdrojového kódu

Pro vývoj nebo když nechceš instalátor (Python 3.10 a novější).

### Linux (Mint, Ubuntu)

```bash
sudo apt install python3-tk                 # okno aplikace
git clone https://github.com/Wargaartun/NaDobrouNoc.git
cd NaDobrouNoc
python3 okno.py
```

Ikona na plochu a do nabídky: `bash instalovat-ikonu.sh`.

### Windows

Nainstaluj [Python](https://www.python.org/downloads/) (zaškrtni „Add python.exe to PATH“),
stáhni zdrojový kód (Code → Download ZIP), rozbal ho a ve složce spusť `okno.py` dvojklikem
nebo příkazem `py okno.py`.

Aplikace otevře prohlížeč a malé okno s tlačítky **Otevřít** a **Zastavit**; zavřením okna se vypne.

## Soukromí a bezpečnost

- Server poslouchá jen na tomto počítači. Přístup z mobilu se zapíná ve Správě – zapínej ho jen doma.
- Cizí webové stránky nemůžou aplikaci ovládat (kontrola hlaviček `Host` a `Origin`, vlastní hlavička
  u změn).
- Aplikace se připojuje jen na: web a API České televize, YouTube (přehrávač, oEmbed) a GitHub
  (jednou denně kontrola nové verze – jde vypnout – a aktuální nastavení pro web ČT).
- Data: `%APPDATA%\NaDobrouNoc` (Windows), `~/.local/share/na-dobrou-noc` (Linux),
  `~/Library/Application Support/NaDobrouNoc` (macOS).

## Díly z iVysílání hrají potichu?

Prohlížeče v nové kartě bez kliknutí nedovolí přehrávání se zvukem. Stačí kliknout v přehrávači
na reproduktor. Ve Firefoxu to jde povolit natrvalo: ikona vlevo v adresním řádku →
**Automatické přehrávání** → **Povolit zvuk i video**.

## Vlastní užití s yt-dlp

S nainstalovaným [yt-dlp](https://github.com/yt-dlp/yt-dlp) (`pip install -r requirements-vlastni.txt`)
aplikace sama vyhledává chybějící díly na YouTube a čte playlisty na serveru. yt-dlp jde mimo
podmínky YouTube, proto ho veřejná verze nepoužívá a nikdy ho nepřibalí.

## Pro vývojáře

Jak aplikace funguje, jak spustit testy a co dělat, když se změní web ČT: [CONTRIBUTING.md](CONTRIBUTING.md).
Změny verzí: [CHANGELOG.md](CHANGELOG.md).

## Licence

[GNU GPL v3.0](LICENSE) – aplikaci můžeš používat, šířit a upravovat; upravené verze musí zůstat
svobodné pod stejnou licencí.
