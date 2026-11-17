# Jak přispět

Díky za zájem! Projekt je malý a psaný česky – česky jsou i názvy v kódu, komentáře a commity.

## Jak aplikace funguje

```
prohlížeč (static/)  ⇄  server.py (API /api/…)  ⇄  web a API ČT, YouTube oEmbed (příp. yt-dlp)
                                 ⇅
                  katalog.json v datové složce uživatele
```

| Soubor | Co dělá |
|---|---|
| `okno.py` | Hlavní spuštění: volný port (8000–8009), server, prohlížeč, okno s Otevřít a Zastavit (tkinter). |
| `server.py` | Statické soubory a JSON API. Kontrola `Host`, `Origin` a hlavičky `X-Na-Dobrou-Noc`. Jen standardní knihovna. |
| `cesty.py` | Název, verze, repozitář a datová složka podle systému. |
| `katalog.py` | Katalog (`katalog.json` + `.bak`), slučování při obnově, ruční díly, vlastní seriály. |
| `doplnovani.py` | Zjištění chybějících dílů; s yt-dlp i hledání a bodování návrhů. |
| `aktualizace.py` | Kontrola nové verze přes GitHub Releases (1× denně, jde vypnout). |
| `zdroje/ivysilani.py` | Web ČT: `__NEXT_DATA__` ze stránek, GraphQL dotaz `GetEpisodes`, kategorie Večerníčky. |
| `zdroje/youtube.py` | oEmbed, playlist ze seznamu videí od prohlížeče, volitelně yt-dlp. |
| `ct_nastaveni.json` | Hodnoty, které se mění s webem ČT (otisk dotazu, verze klienta, adresy). |
| `static/` | Rozhraní: HTML, CSS a JavaScript bez frameworku. |

Zásady:
- **Bez závislostí:** aplikace musí běžet jen se standardní knihovnou Pythonu 3.10+.
- **Veřejná verze bez yt-dlp:** cokoli, co potřebuje yt-dlp, musí být volitelné (`youtube.ma_yt_dlp()`).
- **Nic nestahovat:** díly hrají jen oficiální přehrávače.
- **Údaje z prohlížeče se ověřují na serveru** (ID videí, čísla, texty).

## Testy

```bash
python -m pip install -r requirements-vyvoj.txt
python -m pytest                      # offline testy (vzorky v tests/vzorky)
python -m pytest --zivy tests/test_zivy_web.py   # proti skutečnému webu ČT
```

Test rozhraní v prohlížeči navíc potřebuje `pip install playwright && python -m playwright install chromium`.

Na GitHubu běží testy při každém nahrání (Linux i Windows) a jednou týdně kontrola proti
skutečnému webu ČT. Když ta selže, založí se hlášení se štítkem `web-ct`.

## Když se změní web ČT

### Načte se jen 10 dílů / GetEpisodes vrací chybu

Změnil se otisk dotazu nebo verze klienta.

1. Ve Firefoxu nebo Chrome otevři pořad s víc než 10 díly, např.
   <https://www.ceskatelevize.cz/porady/879074-jaja-a-paja/>.
2. Otevři vývojářské nástroje (F12) → záložka **Síť** (Network), do filtru napiš `GetEpisodes`.
3. Na stránce klikni na „Další díly“.
4. V adrese požadavku najdi `version=…` a v parametru `extensions` hodnotu `sha256Hash`.
5. Přepiš `graphql_verze` a `hash_get_episodes` v `ct_nastaveni.json`, zvyš `verze_souboru`
   a pošli pull request.

Po sloučení do větve `main` si aplikace nové hodnoty **stáhne sama** (do 12 hodin, nebo hned,
když API ČT starý otisk odmítne). Nové vydání programu není potřeba.

### Chyba „chybí blok __NEXT_DATA__“ nebo „nenašel údaje o pořadu“

Změnila se struktura stránek. Ulož si aktuální stránku, porovnej ji se vzorky v `tests/vzorky`
a uprav `zdroje/ivysilani.py`. Vzorek pak nahraď novým (stačí zkrácená data z `__NEXT_DATA__`),
ať testy hlídají novou podobu.

## Vydání nové verze

1. Zvyš `VERZE` v `cesty.py` a `version` v `pyproject.toml`, doplň `CHANGELOG.md`.
2. Vytvoř na GitHubu vydání (Release) s tagem `vX.Y.Z`. Aplikace uživatelům do jednoho dne
   ukáže upozornění na novou verzi.
