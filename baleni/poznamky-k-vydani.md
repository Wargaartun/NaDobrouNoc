## Stažení

| Systém | Soubor |
|---|---|
| **Windows 10 a 11** | `NaDobrouNoc-…-instalator.exe` |
| **Linux** (Mint, Ubuntu, Fedora…) | `NaDobrouNoc-…-x86_64.AppImage` |

Co je nového: [CHANGELOG](https://github.com/Wargaartun/NaDobrouNoc/blob/main/CHANGELOG.md)

## Instalace na Windows

1. Stáhni `NaDobrouNoc-…-instalator.exe` a spusť ho.
2. Windows nejspíš ukáže modré okno **„Systém Windows ochránil váš počítač“**. Je to proto, že aplikace
   je zdarma a nemá placený digitální podpis, ne proto, že by byla nebezpečná.
   Klikni na **Další informace** a pak na **Přesto spustit**.
3. Projdi instalací (stačí klikat na **Další**). Práva správce nejsou potřeba.
4. Na ploše a v nabídce Start bude ikona **Na dobrou noc**.

Po spuštění se otevře prohlížeč s aplikací a malé okno s tlačítky **Otevřít** a **Zastavit**.
Okno nech otevřené, dokud se díváte; jeho zavřením se aplikace vypne.

**Aktualizace:** stáhni nový instalátor a spusť ho – pohádky i zhlédnuté díly zůstanou.
**Odinstalace:** Nastavení → Aplikace → Na dobrou noc → Odinstalovat. Data (seznam pohádek)
zůstanou ve složce `%APPDATA%\NaDobrouNoc`; kdo je chce smazat, smaže tu složku.

## Instalace na Linuxu

1. Stáhni `NaDobrouNoc-…-x86_64.AppImage`, třeba do složky `Aplikace` v domovské složce.
2. Klikni na soubor pravým tlačítkem → **Vlastnosti** → **Oprávnění** → zaškrtni
   **Povolit spouštění souboru jako programu**.
3. Spusť ho dvojklikem.

Z terminálu: `chmod +x NaDobrouNoc-*.AppImage && ./NaDobrouNoc-*.AppImage`.

## Na mobilu

Aplikace běží na počítači. Ve Správě (⚙) zapni **Přístup z mobilu** a v mobilu připojeném
ke stejné Wi-Fi otevři adresu, kterou aplikace ukáže. Počítač musí zůstat zapnutý.

## Když něco nefunguje

[Nahlas chybu](https://github.com/Wargaartun/NaDobrouNoc/issues/new?template=chyba.md) a přilož soubor
`server.log` z datové složky (cesta je ve Správě úplně dole).
