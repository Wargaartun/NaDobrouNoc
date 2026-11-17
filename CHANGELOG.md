# Změny

## 0.6.0 – instalátory

- Instalátor pro **Windows** (Inno Setup): instalace jen pro aktuálního uživatele bez práv správce,
  ikona v nabídce Start a na ploše, česky, aktualizace přes starou verzi a odinstalace (data zůstanou).
- **AppImage pro Linux** – jeden soubor, nic se neinstaluje.
- Sestavení na GitHubu (PyInstaller, bez Pythonu u uživatele) s kontrolním spuštěním zabaleného
  programu, tichou instalací a odinstalací na Windows; vydání se zakládá jako koncept s návodem
  a kontrolními součty.
- Zabalený program píše výpis do `server.log` v datové složce (na Windows nemá konzoli).
- Ikona aplikace (`.ico`, `.png`) a ikona okna.
- `okno.py --kontrola`: spustí server, ověří ho a skončí (pro testy sestavení).
- Linux: otevíraný prohlížeč nezdědí knihovny zabaleného programu.

## 0.5.0 – první verze v repozitáři

- Hodnoty pro web ČT (otisk dotazu `GetEpisodes`, verze klienta, adresy) jsou v `ct_nastaveni.json`.
  Aplikace si jejich aktuální verzi stahuje z repozitáře (1× za 12 h a hned, když API ČT otisk
  odmítne); stažené hodnoty se přísně ověřují.
- Kontrola nové verze přes GitHub Releases (1× denně, jde vypnout ve Správě), upozornění v rozhraní.
- Windows: aplikace už nemůže obsadit port, který používá jiný program.
- Načítání dílů z API ČT skončí po poslední neúplné stránce (o jeden dotaz méně).
- Nabídka večerníčků se řadí česky (C < Č < D).
- Testy (pytest) se skutečnými vzorky stránek ČT, test rozhraní v prohlížeči, týdenní kontrola
  proti živému webu ČT, automatické testy na Linuxu a Windows.

## 0.4.0

- Veřejný název **Na dobrou noc**.
- Zabezpečení API: kontrola `Host` (DNS rebinding), změny jen jako JSON s hlavičkou
  `X-Na-Dobrou-Noc`, kontrola `Origin`; ověřování vstupů, české chybové hlášky.
- Výchozí poslech jen na 127.0.0.1, přístup z mobilu jako vypínač.
- Data v profilu uživatele, záloha `.bak`, přenos ze staré složky `data/`.
- Veřejná verze bez yt-dlp: playlisty přes oficiální YouTube přehrávač (`getPlaylist`) a oEmbed.
- Všechny díly z iVysílání včetně nedostupných – zachování zhlédnutí; řady (sezóny).
- Průvodce prvním spuštěním, prázdný výchozí katalog, žádná výchozí znělka.
- Hláška při nenačteném přehrávači YouTube, youtube-nocookie.com, systémová písma.
- Okno: volný port, otevření prohlížeče, rozpoznání běžící aplikace.

## 0.3.0 a starší

Vývojové verze „Večerníček“: lokální server, přehrávání se znělkou, iVysílání a YouTube,
doplňování chybějících dílů, okno serveru.
