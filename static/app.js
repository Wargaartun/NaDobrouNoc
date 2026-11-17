// Na dobrou noc – rozhraní aplikace
// Obrazovky: "pruvodce" (první spuštění) · "domu" (seriály) → "serial" (díly) → přehrávač · "sprava"

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const NAZEV = 'Na dobrou noc';

let katalog = { znelka: null, nastaveni: {}, serialy: [] };
let schopnosti = { yt_dlp: false, sit: false, adresa_v_siti: null };   // z /api/stav
let obrazovka = { typ: 'domu' };   // {typ:'domu'} | {typ:'serial', id} | {typ:'sprava'} | {typ:'pruvodce', krok}

// ---------- komunikace se serverem ----------
// Každá změna nese hlavičku X-Na-Dobrou-Noc – server tak pozná, že ji neposlala cizí webová stránka.
async function api(cesta, metoda = 'GET', telo) {
  const r = await fetch('/api/' + cesta, {
    method: metoda,
    headers: metoda === 'GET' ? {} : { 'Content-Type': 'application/json', 'X-Na-Dobrou-Noc': '1' },
    body: telo ? JSON.stringify(telo) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.chyba || `Chyba serveru (${r.status})`);
  return data;
}

async function nactiKatalog() {
  katalog = await api('katalog');
  vykresli();
}

async function nactiSchopnosti() {
  schopnosti = await api('stav');
  return schopnosti;
}

function zprava(text, ms = 3500) {
  const el = document.createElement('div');
  el.className = 'zprava';
  el.textContent = text;
  $('zpravy').append(el);
  setTimeout(() => el.remove(), ms);
}

// Sleduje načítání na serveru (např. „Obnovit vše“) a ukazuje jeho zprávy
let hlidani = null;
let posledniZprava = 0;
function hlidejNacitani() {
  if (hlidani) return;
  hlidani = setInterval(async () => {
    try {
      const s = await api('stav');
      s.zpravy.filter(z => z.n > posledniZprava).forEach(z => zprava(z.text, 5000));
      posledniZprava = s.posledni;
      if (!s.nacita_se.length) {
        clearInterval(hlidani); hlidani = null;
        await nactiKatalog();
      }
    } catch { /* server se mohl restartovat, zkusíme příště */ }
  }, 1500);
}

// ---------- pomocné funkce pro data ----------
const nazevSerialu = s => s.nazev_vlastni || s.nazev || 'Bez názvu';
const viditelneDily = s => s.dily.filter(d => d.dostupny && !d.skryty && !d.nahrazeno);
// 1 díl, 2–4 díly, 0 a 5+ dílů
const dilu = n => `${n} ${n === 1 ? 'díl' : n >= 2 && n <= 4 ? 'díly' : 'dílů'}`;
const delka = sek => sek ? `${Math.round(sek / 60)} min` : '';
const minuty = sek => sek ? `${Math.floor(sek / 60)}:${String(Math.round(sek % 60)).padStart(2, '0')}` : '';
const bezDiakritiky = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const idZUrlCT = url => { const m = url.match(/ceskatelevize\.cz\/porady\/([^/?#]+)/); return m ? 'ct-' + m[1] : null; };
const typSerialu = s => s.id.startsWith('yt-') ? 'YouTube playlist' : s.id.startsWith('ct-') ? 'iVysílání' : 'Vlastní (YouTube)';

// První nezhlédnutý díl; když je zadán `po`, hledá se nejdřív za tímto dílem.
// Když je všechno zhlédnuté, začne se znovu od začátku.
function dalsiDil(s, po = null) {
  const dily = viditelneDily(s);
  const i = po ? dily.findIndex(d => d.id === po.id) : -1;
  const poradi = [...dily.slice(i + 1), ...dily.slice(0, i + 1)].filter(d => d !== po);
  return poradi.find(d => !d.zhlednuto) || poradi[0] || null;
}

// Odkud díl je – ukazuje se jen tam, kde to není jasné (např. díl z YouTube v seriálu z iVysílání)
function znackaZdroje(s, d) {
  if (d.typ === 'ivysilani') return '<span class="zdroj-ct">iVysílání</span>';
  if (!s.id.startsWith('yt-')) return '<span class="zdroj-yt">YouTube</span>';
  return '';
}

function obrazek(url, nahradni = '🌙') {
  return url
    ? `<img src="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
    : `<div class="bez-obrazku" aria-hidden="true">${nahradni}</div>`;
}

// ---------- YouTube playlisty přes oficiální přehrávač ----------
// Veřejná verze nepoužívá yt-dlp: seznam videí v playlistu zjistí oficiální YouTube přehrávač
// (IFrame API, getPlaylist) přímo v prohlížeči a pošle ho serveru. Funguje pro veřejné
// a neveřejné (unlisted) playlisty, YouTube vrací nejvýš 200 videí.
const listId = url => { try { return new URL(url).searchParams.get('list'); } catch { return null; } };
const jeVideo = url => { try { const u = new URL(url); return u.searchParams.has('v') || u.hostname.endsWith('youtu.be') || u.pathname.includes('/shorts/'); } catch { return false; } };

function nactiPlaylistVProhlizeci(id) {
  return new Promise((hotovo, chyba) => {
    if (!window.YT?.Player) return chyba(new Error('Přehrávač YouTube se nenačetl – zkontroluj připojení k internetu'));
    const obal = document.createElement('div');
    obal.style.cssText = 'position:fixed;left:-10000px;top:0;width:320px;height:180px';
    const misto = document.createElement('div');
    obal.append(misto);
    document.body.append(obal);
    let konec = false, casovac = null, prehravac = null;
    const skonci = (fn, x) => {
      if (konec) return;
      konec = true; clearInterval(casovac);
      try { prehravac?.destroy(); } catch {}
      obal.remove(); fn(x);
    };
    const nejde = () => skonci(chyba, new Error('Playlist se nepodařilo načíst. Je veřejný nebo neveřejný (ne soukromý)?'));
    prehravac = new YT.Player(misto, {
      host: 'https://www.youtube-nocookie.com',
      playerVars: { listType: 'playlist', list: id },
      events: {
        onReady: () => {
          let pokusy = 0;
          casovac = setInterval(() => {
            const videa = prehravac.getPlaylist?.();
            if (videa?.length) skonci(hotovo, videa);
            else if (++pokusy > 40) nejde();
          }, 250);
        },
        onError: nejde,
      },
    });
    setTimeout(nejde, 20000);
  });
}

// Videa playlistu – bez yt-dlp je zjistí prohlížeč, s yt-dlp si je server přečte sám (undefined)
async function videaPlaylistu(url) {
  if (schopnosti.yt_dlp || !listId(url) || jeVideo(url)) return undefined;
  return nactiPlaylistVProhlizeci(listId(url));
}

// Odkazy na playlisty rozbalí na odkazy na jednotlivá videa (jen bez yt-dlp)
async function rozbalOdkazy(odkazy) {
  if (schopnosti.yt_dlp) return odkazy;
  const vysledek = [];
  for (const o of odkazy) {
    if (listId(o) && !jeVideo(o)) {
      const videa = await nactiPlaylistVProhlizeci(listId(o));
      vysledek.push(...videa.map(v => `https://www.youtube.com/watch?v=${v}`));
    } else vysledek.push(o);
  }
  return vysledek;
}

async function pridejSerial(url, nazev) {
  return api('serialy', 'POST', { url, nazev, videa: await videaPlaylistu(url) });
}

async function obnovSerial(s) {
  return api(`serialy/${encodeURIComponent(s.id)}/obnovit`, 'POST', { videa: await videaPlaylistu(s.zdroj) });
}

// ---------- vykreslování ----------
function htmlNoveVerze() {
  const n = schopnosti.nova_verze;
  return n ? `<a class="banner" href="${esc(n.url)}" target="_blank" rel="noopener">
    ✨ Je dostupná nová verze ${esc(n.verze)} – klikni pro stažení</a>` : '';
}

function jdi(nova) {
  obrazovka = nova;
  vykresli();
  scrollTo(0, 0);
}

function vykresli() {
  if (obrazovka.typ !== 'pruvodce' && !katalog.nastaveni?.pruvodce_hotov) obrazovka = { typ: 'pruvodce', krok: 1 };
  const s = obrazovka.typ === 'serial' ? katalog.serialy.find(x => x.id === obrazovka.id) : null;
  if (obrazovka.typ === 'serial' && !s) obrazovka = { typ: 'domu' };

  $('zpet').hidden = obrazovka.typ === 'domu' || obrazovka.typ === 'pruvodce';
  $('spravaBtn').hidden = obrazovka.typ === 'sprava' || obrazovka.typ === 'pruvodce';
  $('nadpis').textContent =
    obrazovka.typ === 'serial' ? nazevSerialu(s) :
    obrazovka.typ === 'sprava' ? 'Správa' : `🌙 ${NAZEV}`;

  if (obrazovka.typ === 'pruvodce') vykresliPruvodce();
  else if (obrazovka.typ === 'domu') vykresliDomu();
  else if (obrazovka.typ === 'serial') vykresliSerial(s);
  else vykresliSpravu();
}

function vykresliDomu() {
  const serialy = katalog.serialy.filter(s => viditelneDily(s).length);
  if (!serialy.length) {
    $('obsah').innerHTML = `<div class="sekce"><h2>Zatím tu nic není</h2>
      <p class="napoveda">Pohádky přidáš ve Správě (⚙).</p>
      <button class="btn hlavni" id="doSpravy">Přidat pohádky</button></div>`;
    return;
  }
  $('obsah').innerHTML = htmlNoveVerze() + `<div class="mrizka">${serialy.map(s => {
    const dily = viditelneDily(s);
    const hotovo = dily.filter(d => d.zhlednuto).length;
    return `<button class="dlazdice" data-serial="${esc(s.id)}">
      ${obrazek(s.obrazek)}
      <div class="popis"><h2>${esc(nazevSerialu(s))}</h2>
        <small>${dilu(dily.length)} · zhlédnuto ${hotovo}</small>
        <div class="pruh"><i style="width:${Math.round(100 * hotovo / dily.length)}%"></i></div>
      </div></button>`;
  }).join('')}</div>`;
}

function vykresliSerial(s) {
  const dily = viditelneDily(s);
  const dalsi = dalsiDil(s);
  $('obsah').innerHTML = `
    ${dalsi ? `<button class="velke-tlacitko" data-prehrat="${esc(dalsi.id)}">
      <span class="play">▶</span><div>Pustit další díl<span>${esc(dalsi.nazev)}</span></div></button>` : ''}
    <div class="seznam">${dily.map(d => `
      <button class="dil ${d.zhlednuto ? 'zhlednuty' : ''}" data-prehrat="${esc(d.id)}">
        ${obrazek(d.obrazek, '▶')}
        <div><b>${esc(d.nazev)}</b>
          <small>${[delka(d.delka), znackaZdroje(s, d)].filter(Boolean).join(' · ')}</small></div>
        <span class="znacka">${d.zhlednuto ? '✓' : ''}</span>
      </button>`).join('')}</div>`;
}

// ---------- nabídka večerníčků z iVysílání (Správa i průvodce) ----------
let vecernickyCT = null;
let nacitamCT = false;
let chybaCT = null;

async function nactiNabidkuCT() {
  if (nacitamCT || vecernickyCT) return;
  nacitamCT = true; chybaCT = null;
  try { vecernickyCT = await api('vecernicky'); }
  catch (err) { chybaCT = err.message; }
  nacitamCT = false;
  // překreslí jen nabídku, ať se nezruší rozepsané hledání
  const el = $('nabidkaCT');
  if (el) { el.innerHTML = obrazovka.typ === 'pruvodce' ? htmlVyberuPruvodce() : htmlNabidky(); filtruj(); }
}

let hledany = '';
function filtruj() {
  const q = bezDiakritiky(hledany).trim();
  for (const box of document.querySelectorAll('[data-hledat-v]')) {
    let videt = 0;
    for (const el of box.querySelectorAll('[data-hledat]')) {
      const ok = !q || el.dataset.hledat.includes(q);
      el.hidden = !ok;
      videt += ok;
    }
    const nic = box.querySelector('.nic-nenalezeno');
    if (nic) nic.hidden = videt > 0 || !q;
  }
}

function htmlNabidky() {
  if (chybaCT) return `<p class="chyba">Nabídku se nepodařilo načíst: ${esc(chybaCT)}</p>
    <button class="btn" data-akce="nacist-ct">Zkusit znovu</button>`;
  if (!vecernickyCT) return '<p class="napoveda">Načítám nabídku z iVysílání…</p>';
  const vKatalogu = new Set(katalog.serialy.map(s => s.id));
  return `<p class="napoveda">${vecernickyCT.length} večerníčků z kategorie Večerníčky na iVysílání.</p>
    <div class="nabidka">${vecernickyCT.map(v => {
      const id = idZUrlCT(v.url), uz = vKatalogu.has(id);
      return `<article data-hledat="${esc(bezDiakritiky(v.nazev))}" class="${uz ? 'pridany' : ''}">${obrazek(v.obrazek)}<div>
        <b>${esc(v.nazev)}</b>
        ${uz ? `<small class="v-aplikaci">✓ V aplikaci</small>
                <button class="btn maly nebezpecne" data-akce="smazat" data-id="${esc(id)}">Odebrat</button>`
             : `<button class="btn maly hlavni" data-pridat-ct="${esc(v.url)}">+ Přidat</button>`}
      </div></article>`;
    }).join('')}</div>
    <p class="napoveda nic-nenalezeno" hidden>Na iVysílání nic takového není.</p>`;
}

// ---------- průvodce prvním spuštěním ----------
const vybrane = new Set();   // odkazy na pořady ČT vybrané v průvodci

function vykresliPruvodce() {
  if (obrazovka.krok === 1) {
    $('obsah').innerHTML = `<section class="sekce pruvodce">
      <p class="krok">Krok 1 ze 2</p>
      <h2>Vítej v aplikaci ${NAZEV}</h2>
      <p>Aplikace pouští pohádky z iVysílání a YouTube a před každým dílem může přehrát znělku –
         tak jako v televizi.</p>
      <h3>Znělka před díly</h3>
      <p class="napoveda">Najdi na YouTube video se znělkou, kterou máte rádi, a vlož sem jeho odkaz.
         <a href="https://www.youtube.com/results?search_query=zn%C4%9Blka+ve%C4%8Dern%C3%AD%C4%8Dku" target="_blank" rel="noopener">Hledat znělku na YouTube</a></p>
      <form id="pruvodceZnelka" class="radek">
        <input type="url" name="url" placeholder="Odkaz na YouTube video se znělkou" value="${katalog.znelka ? `https://www.youtube.com/watch?v=${esc(katalog.znelka)}` : ''}">
        <button class="btn hlavni">Pokračovat</button>
      </form>
      <p class="napoveda"><button class="odkaz" data-akce="pruvodce-bez-znelky">Pokračovat bez znělky</button> – můžeš ji přidat později ve Správě.</p>
    </section>`;
    return;
  }
  $('obsah').innerHTML = `<section class="sekce pruvodce">
    <p class="krok">Krok 2 ze 2</p>
    <h2>Vyber pohádky</h2>
    <p class="napoveda">Klepnutím vyber večerníčky z iVysílání. Další přidáš kdykoli ve Správě.</p>
    <div class="hledani"><input type="search" id="hledat" placeholder="🔍 Hledat večerníček" value="${esc(hledany)}" autocomplete="off"></div>
    <div data-hledat-v id="nabidkaCT">${htmlVyberuPruvodce()}</div>
    <h3>Playlisty z YouTube (nepovinné)</h3>
    <textarea id="pruvodcePlaylisty" rows="3" placeholder="Odkaz na playlist s pohádkami, každý na nový řádek"></textarea>
    <div class="radek konec-pruvodce">
      <button class="btn" data-akce="pruvodce-zpet">Zpět</button>
      <button class="btn hlavni" data-akce="pruvodce-hotovo" id="pruvodceHotovo">Hotovo</button>
    </div>
  </section>`;
  filtruj();
  nactiNabidkuCT();
  aktualizujTlacitkoPruvodce();
}

function htmlVyberuPruvodce() {
  if (chybaCT) return `<p class="chyba">Nabídku z iVysílání se nepodařilo načíst: ${esc(chybaCT)}</p>
    <button class="btn" data-akce="nacist-ct">Zkusit znovu</button>`;
  if (!vecernickyCT) return '<p class="napoveda">Načítám nabídku z iVysílání…</p>';
  return `<div class="nabidka vyber">${vecernickyCT.map(v => `
    <button type="button" class="volba ${vybrane.has(v.url) ? 'vybrano' : ''}" data-vybrat="${esc(v.url)}"
      data-hledat="${esc(bezDiakritiky(v.nazev))}" aria-pressed="${vybrane.has(v.url)}">
      ${obrazek(v.obrazek)}<b>${esc(v.nazev)}</b><span class="fajfka" aria-hidden="true">✓</span>
    </button>`).join('')}</div>
    <p class="napoveda nic-nenalezeno" hidden>Nic takového na iVysílání není.</p>`;
}

function aktualizujTlacitkoPruvodce() {
  const b = $('pruvodceHotovo');
  if (b) b.textContent = vybrane.size ? `Hotovo – přidat ${vybrane.size}` : 'Hotovo';
}

async function dokonciPruvodce(tlacitko) {
  tlacitko.disabled = true;
  const playlisty = ($('pruvodcePlaylisty')?.value || '').split(/\s+/).filter(Boolean);
  const vse = [...vybrane, ...playlisty];
  let i = 0;
  for (const url of vse) {
    tlacitko.textContent = `Přidávám ${++i} z ${vse.length}…`;
    try { await pridejSerial(url); }
    catch (err) { zprava(`${url}: ${err.message}`, 7000); }
  }
  await api('nastaveni', 'POST', { pruvodce_hotov: true });
  vybrane.clear(); hledany = '';
  obrazovka = { typ: 'domu' };
  await nactiKatalog();
}

// ---------- správa ----------
let rozbaleny = null;      // id seriálu, u kterého jsou rozbalené díly
const doplneni = {};       // id seriálu → stav hledání chybějících dílů (ze serveru)
let hlidaniDoplneni = null;

function htmlDilySpravy(s) {
  const dily = s.dily.filter(d => d.dostupny);
  return `<div class="rozbaleno">
    <div class="dily-sprava">${dily.map(d => `
      <label class="${d.nahrazeno ? 'nahrazeny' : ''}">
        <input type="checkbox" data-viditelnost="${esc(d.id)}" data-serial="${esc(s.id)}" ${d.skryty ? '' : 'checked'} ${d.nahrazeno ? 'disabled' : ''}>
        <span>${esc(d.nazev)}
          ${d.rucne ? `<small class="zdroj-yt">${d.nahrazeno ? 'YouTube – teď je na iVysílání, hraje se odtamtud' : 'YouTube'}</small>` : ''}</span>
        ${d.rucne ? `<button class="btn maly nebezpecne" data-akce="smazat-dil" data-id="${esc(s.id)}" data-dil="${esc(d.id)}" title="Smazat díl">✕</button>` : ''}
      </label>`).join('') || '<p class="napoveda">Zatím žádné díly.</p>'}
    </div>
    <p class="napoveda">Odškrtnuté díly se v nabídce nezobrazí. Díly přidané z YouTube jde smazat (✕).</p>

    <form class="radek pridat-yt" data-serial="${esc(s.id)}">
      <input type="url" name="odkaz" required placeholder="Přidat díl: odkaz na YouTube video nebo playlist">
      <button class="btn">+ Přidat</button>
    </form>

    ${s.id.startsWith('ct-') ? `<div class="doplneni" data-doplneni="${esc(s.id)}">${htmlDoplneni(s)}</div>` : ''}
  </div>`;
}

function htmlDoplneni(s) {
  const st = doplneni[s.id] || { stav: 'nic', hledani: schopnosti.yt_dlp };
  const id = esc(s.id);
  if (st.stav === 'nic') return st.hledani
    ? `<button class="btn hlavni" data-akce="doplnit" data-id="${id}">🔍 Najít chybějící díly na YouTube</button>
       <p class="napoveda">Zjistí, které díly na iVysílání chybí, a najde je na YouTube. Nic se nepřidá samo – vybereš ty.</p>`
    : `<button class="btn hlavni" data-akce="doplnit" data-id="${id}">🔍 Zjistit chybějící díly</button>
       <p class="napoveda">Ukáže díly, které na iVysílání teď nejsou. Na YouTube je najdeš jedním klepnutím a odkaz vložíš sem.</p>`;
  if (st.stav === 'chyba') return `<p class="chyba">Nepodařilo se: ${esc(st.poznamka)}</p>
    <button class="btn" data-akce="doplnit" data-id="${id}">Zkusit znovu</button>`;

  const hlava = st.stav === 'hledam'
    ? `<p><b>Hledám na YouTube…</b> ${st.celkem == null ? 'zjišťuji, které díly chybí' : `${st.hotovo} z ${st.celkem}`}</p>`
    : st.chybejici.length
      ? (st.hledani
        ? `<p><b>Návrhy pro chybějící díly</b> – u každého vyber správné video, nebo vlož vlastní odkaz.</p>`
        : `<p><b>Na iVysílání teď ${st.chybejici.length >= 2 && st.chybejici.length <= 4 ? 'chybějí' : 'chybí'} ${dilu(st.chybejici.length)}.</b> Najdi je na YouTube a vlož odkaz na video.</p>`)
      : `<p><b>${st.celkem ? 'Hotovo – všechny díly jsou doplněné nebo přeskočené.' : 'Nic nechybí.'}</b></p>`;
  const data = d => `data-id="${id}" data-cislo="${d.cislo}" data-rada="${esc(d.rada ?? '')}"`;
  return `${hlava}
    ${st.poznamka ? `<p class="napoveda">${esc(st.poznamka)}</p>` : ''}
    ${st.chybejici.map(d => `<div class="chybejici">
      <div class="chybejici-hlava"><b>${esc(d.nazev)}${d.rada ? ` <small>(${esc(d.rada)})</small>` : ''}</b>
        <button class="btn maly" data-akce="preskocit" ${data(d)}>Přeskočit</button></div>
      ${st.hledani ? (d.kandidati.length ? `<div class="kandidati">${d.kandidati.map((k, i) => `
        <div class="kandidat">
          <a href="https://www.youtube.com/watch?v=${esc(k.id)}" target="_blank" rel="noopener" title="Otevřít na YouTube">
            <img src="${esc(k.obrazek)}" alt="" loading="lazy" referrerpolicy="no-referrer"><span class="delka">${minuty(k.delka)}</span></a>
          <div><b>${esc(k.nazev)}</b><small>${esc(k.kanal || '')}${i === 0 ? ' · nejlepší shoda' : ''}</small></div>
          <button class="btn maly ${i === 0 ? 'hlavni' : ''}" data-pouzit="${esc(k.id)}" ${data(d)}>Použít</button>
        </div>`).join('')}</div>`
        : `<p class="napoveda">${d.chyba ? 'Hledání selhalo: ' + esc(d.chyba) : 'Na YouTube jsem nic vhodného nenašel.'}</p>`) : ''}
      <div class="radek">
        <a class="btn maly" href="${esc(d.hledat_url)}" target="_blank" rel="noopener">🔍 Hledat na YouTube</a>
      </div>
      <form class="radek pridat-yt" data-serial="${id}" data-cislo="${d.cislo}" data-rada="${esc(d.rada ?? '')}" data-nazev="${esc(d.nazev)}">
        <input type="url" name="odkaz" required placeholder="Vlož odkaz na video s tímto dílem">
        <button class="btn maly">Použít odkaz</button>
      </form>
    </div>`).join('')}
    ${st.stav === 'hotovo' ? `<button class="btn maly" data-akce="doplnit" data-id="${id}">⟳ Zjistit znovu</button>` : ''}`;
}

function prekresliDoplneni(serialId) {
  const s = katalog.serialy.find(x => x.id === serialId);
  const el = document.querySelector(`[data-doplneni="${CSS.escape(serialId)}"]`);
  if (s && el) el.innerHTML = htmlDoplneni(s);
}

function hlidejDoplneni(serialId) {
  clearInterval(hlidaniDoplneni);
  hlidaniDoplneni = setInterval(async () => {
    try {
      doplneni[serialId] = await api(`serialy/${encodeURIComponent(serialId)}/doplneni`);
      prekresliDoplneni(serialId);
      if (doplneni[serialId].stav !== 'hledam') clearInterval(hlidaniDoplneni);
    } catch { /* zkusíme příště */ }
  }, 1500);
}

function vykresliSpravu() {
  $('obsah').innerHTML = htmlNoveVerze() + `
    <div class="hledani">
      <input type="search" id="hledat" placeholder="🔍 Hledat večerníček – v aplikaci i na iVysílání"
        value="${esc(hledany)}" autocomplete="off">
    </div>

    <section class="sekce" data-hledat-v>
      <h2>Seriály v aplikaci</h2>
      <div class="radek"><button class="btn" data-akce="obnovit-vse">⟳ Obnovit vše ze zdrojů</button></div>
      ${katalog.serialy.map(s => {
        const dostupne = s.dily.filter(d => d.dostupny);
        const skryte = dostupne.filter(d => d.skryty).length;
        const rucne = s.dily.filter(d => d.rucne && !d.nahrazeno).length;
        const chybi = s.dily.filter(d => !d.dostupny && !d.rucne).length;
        return `<div class="sprava-serial" data-hledat="${esc(bezDiakritiky(nazevSerialu(s) + ' ' + (s.nazev || '')))}">
          <div class="hlava">
            ${s.obrazek ? `<img src="${esc(s.obrazek)}" alt="" referrerpolicy="no-referrer">` : ''}
            <div class="jmeno"><b>${esc(nazevSerialu(s))}</b>
              <small>${typSerialu(s)} · ${dilu(viditelneDily(s).length)}${rucne && s.zdroj ? `, z toho ${rucne} doplněných z YouTube` : ''}${skryte ? `, ${skryte} skrytých` : ''}${chybi && s.id.startsWith('ct-') ? `, ${chybi} teď na iVysílání chybí` : ''}
              ${s.aktualizovano ? ` · obnoveno ${new Date(s.aktualizovano).toLocaleDateString('cs-CZ')}` : ''}</small>
              ${s.chyba ? `<small class="chyba">Poslední načtení selhalo: ${esc(s.chyba)}</small>` : ''}
            </div>
            <div class="radek">
              <button class="btn maly" data-akce="dily" data-id="${esc(s.id)}">${rozbaleny === s.id ? 'Zavřít díly' : 'Díly a doplnění'}</button>
              <button class="btn maly" data-akce="prejmenovat" data-id="${esc(s.id)}">Přejmenovat</button>
              ${s.zdroj ? `<button class="btn maly" data-akce="obnovit" data-id="${esc(s.id)}" title="Obnovit ze zdroje">⟳</button>` : ''}
              <button class="btn maly" data-akce="vynulovat" data-id="${esc(s.id)}">Zrušit zhlédnutí</button>
              <button class="btn maly nebezpecne" data-akce="smazat" data-id="${esc(s.id)}">Odebrat</button>
            </div>
          </div>
          ${rozbaleny === s.id ? htmlDilySpravy(s) : ''}
        </div>`;
      }).join('') || '<p class="napoveda">Zatím žádné.</p>'}
      <p class="napoveda nic-nenalezeno" hidden>V aplikaci nic takového není.</p>
    </section>

    <section class="sekce" data-hledat-v>
      <h2>Večerníčky z iVysílání</h2>
      <div id="nabidkaCT">${htmlNabidky()}</div>
    </section>

    <section class="sekce">
      <h2>Přidat seriál odkazem</h2>
      <form id="pridat" class="radek">
        <input type="url" name="url" required placeholder="Odkaz na YouTube playlist nebo pořad na iVysílání">
        <input type="text" name="nazev" placeholder="Vlastní název (nepovinné)">
        <button class="btn hlavni">Přidat</button>
      </form>
      <p class="napoveda">Pro pohádky, které nejsou v nabídce výše. YouTube: odkaz na playlist (obsahuje <code>list=</code>) –
        seriál se pak dá obnovovat, když do playlistu někdo přidá díly. iVysílání: odkaz na pořad, např. ceskatelevize.cz/porady/…</p>
    </section>

    <section class="sekce">
      <h2>Vytvořit vlastní seriál z YouTube</h2>
      <form id="vlastni" class="sloupec">
        <input type="text" name="nazev" required placeholder="Název seriálu">
        <textarea name="odkazy" rows="4" placeholder="Odkazy na YouTube – jednotlivá videa i playlisty, každý na nový řádek"></textarea>
        <div class="radek"><button class="btn hlavni">Vytvořit</button></div>
      </form>
      <p class="napoveda">Díly se seřadí v pořadí odkazů. Další díly přidáš později přes „Díly a doplnění“.</p>
    </section>

    <section class="sekce">
      <h2>Znělka</h2>
      <form id="znelka" class="radek">
        <input type="url" name="url" placeholder="Odkaz na YouTube video se znělkou (prázdné = bez znělky)"
          value="${katalog.znelka ? `https://www.youtube.com/watch?v=${esc(katalog.znelka)}` : ''}">
        <button class="btn">Uložit</button>
      </form>
      <p class="napoveda"><a href="https://www.youtube.com/results?search_query=zn%C4%9Blka+ve%C4%8Dern%C3%AD%C4%8Dku" target="_blank" rel="noopener">Hledat znělku na YouTube</a></p>
    </section>

    <section class="sekce">
      <h2>Přístup z mobilu</h2>
      ${schopnosti.sit
        ? `<p>Zapnuto. V mobilu připojeném ke stejné Wi-Fi otevři <b>${esc(schopnosti.adresa_v_siti || '')}</b></p>
           <button class="btn" data-akce="sit" data-zapnout="0">Vypnout přístup z mobilu</button>`
        : `<p class="napoveda">Vypnuto – aplikace jde otevřít jen na tomto počítači.</p>
           <button class="btn" data-akce="sit" data-zapnout="1">Zapnout přístup z mobilu</button>`}
      <p class="napoveda">Zapínej jen doma. Kdokoli ve stejné Wi-Fi pak může aplikaci otevřít a ovládat.
        Počítač se při prvním zapnutí může zeptat na povolení ve firewallu.</p>
    </section>

    <section class="sekce">
      <h2>Aktualizace</h2>
      <label class="prepinac"><input type="checkbox" id="kontrolaVerze" ${katalog.nastaveni?.kontrola_verze !== false ? 'checked' : ''}>
        Upozornit na novou verzi aplikace</label>
      <p class="napoveda">Jednou denně se aplikace zeptá GitHubu, jestli nevyšla nová verze. Nic se samo nestahuje.
        <a href="${esc(schopnosti.repozitar || '')}" target="_blank" rel="noopener">Stránka projektu</a></p>
    </section>

    <p class="napoveda pata">${NAZEV} ${esc(schopnosti.verze || '')}${schopnosti.yt_dlp ? ' · s yt-dlp (vlastní užití)' : ''} · data: ${esc(schopnosti.data || '')}</p>`;
  filtruj();
  nactiNabidkuCT();
}

document.addEventListener('input', e => {
  if (e.target.id === 'hledat') { hledany = e.target.value; filtruj(); }
});

document.addEventListener('change', async e => {
  if (e.target.id !== 'kontrolaVerze') return;
  try {
    katalog.nastaveni = await api('nastaveni', 'POST', { kontrola_verze: e.target.checked });
    zprava(e.target.checked ? 'Kontrola nové verze zapnuta' : 'Kontrola nové verze vypnuta');
  } catch (err) { zprava(err.message); e.target.checked = !e.target.checked; }
});

// ---------- obsluha kliknutí ----------
document.addEventListener('click', async e => {
  const t = e.target.closest('button, [data-viditelnost]');
  if (!t || t.closest('#kino')) return;
  const rada = el => el.dataset.rada || null;

  if (t.id === 'zpet') return jdi({ typ: 'domu' });
  if (t.id === 'spravaBtn' || t.id === 'doSpravy') { await nactiSchopnosti().catch(() => {}); return jdi({ typ: 'sprava' }); }
  if (t.dataset.serial && t.classList.contains('dlazdice')) return jdi({ typ: 'serial', id: t.dataset.serial });
  if (t.dataset.prehrat) {
    const s = katalog.serialy.find(x => x.id === obrazovka.id);
    return prehraj(s, s.dily.find(d => d.id === t.dataset.prehrat));
  }
  if (t.dataset.vybrat) {   // výběr v průvodci
    const url = t.dataset.vybrat;
    vybrane.has(url) ? vybrane.delete(url) : vybrane.add(url);
    t.classList.toggle('vybrano', vybrane.has(url));
    t.setAttribute('aria-pressed', vybrane.has(url));
    return aktualizujTlacitkoPruvodce();
  }
  if (t.dataset.viditelnost) {
    try {
      await api(`serialy/${encodeURIComponent(t.dataset.serial)}/dily/${encodeURIComponent(t.dataset.viditelnost)}`, 'POST', { skryty: !t.checked });
      const s = katalog.serialy.find(x => x.id === t.dataset.serial);
      s.dily.find(d => d.id === t.dataset.viditelnost).skryty = !t.checked;
    } catch (err) { zprava(err.message); t.checked = !t.checked; }
    return;
  }
  if (t.dataset.pridatCt) {
    t.disabled = true; t.textContent = 'Načítám…';
    try { await pridejSerial(t.dataset.pridatCt); zprava('Přidáno'); await nactiKatalog(); }
    catch (err) { zprava(err.message, 6000); t.disabled = false; t.textContent = '+ Přidat'; }
    return;
  }
  // návrh z YouTube pro chybějící díl → přidat do seriálu
  if (t.dataset.pouzit) {
    const sid = t.dataset.id, cislo = Number(t.dataset.cislo);
    const dil = doplneni[sid]?.chybejici.find(d => d.cislo === cislo && (d.rada || null) === rada(t));
    const k = dil?.kandidati.find(x => x.id === t.dataset.pouzit);
    if (!k) return;
    t.disabled = true; t.textContent = '…';
    try {
      await api(`serialy/${encodeURIComponent(sid)}/youtube`, 'POST', { meta: k, cislo, rada: rada(t), nazev: dil.nazev });
      doplneni[sid] = await api(`serialy/${encodeURIComponent(sid)}/doplneni`);
      zprava(`Doplněno: ${dil.nazev}`);
      await nactiKatalog();
    } catch (err) { zprava(err.message, 6000); t.disabled = false; t.textContent = 'Použít'; }
    return;
  }

  const id = t.dataset.id, akce = t.dataset.akce;
  if (!akce) return;
  const cesta = id && `serialy/${encodeURIComponent(id)}`;
  try {
    if (akce === 'pruvodce-bez-znelky') return jdi({ typ: 'pruvodce', krok: 2 });
    if (akce === 'pruvodce-zpet') return jdi({ typ: 'pruvodce', krok: 1 });
    if (akce === 'pruvodce-hotovo') return await dokonciPruvodce(t);
    if (akce === 'dily') {
      rozbaleny = rozbaleny === id ? null : id;
      vykresli();
      if (rozbaleny && id.startsWith('ct-')) {   // hledání mohlo běžet už dřív
        doplneni[id] = await api(cesta + '/doplneni');
        prekresliDoplneni(id);
        if (doplneni[id].stav === 'hledam') hlidejDoplneni(id);
      }
      return;
    }
    if (akce === 'doplnit') {
      doplneni[id] = await api(cesta + '/doplnit', 'POST', {});
      prekresliDoplneni(id);
      return hlidejDoplneni(id);
    }
    if (akce === 'preskocit') {
      doplneni[id] = await api(cesta + '/preskocit', 'POST', { cislo: Number(t.dataset.cislo), rada: rada(t) });
      return prekresliDoplneni(id);
    }
    if (akce === 'nacist-ct') {
      chybaCT = null;
      $('nabidkaCT').innerHTML = obrazovka.typ === 'pruvodce' ? htmlVyberuPruvodce() : htmlNabidky();
      return nactiNabidkuCT();
    }
    if (akce === 'sit') {
      t.disabled = true;
      await api('nastaveni', 'POST', { sit: t.dataset.zapnout === '1' });
      await nactiSchopnosti();
      return vykresli();
    }
    if (akce === 'obnovit-vse') {
      await api('obnovit', 'POST', {});
      zprava('Obnovuji seriály…');
      hlidejNacitani();
      if (!schopnosti.yt_dlp) {   // playlisty z YouTube obnovuje prohlížeč
        for (const s of katalog.serialy.filter(x => x.id.startsWith('yt-'))) {
          try { await obnovSerial(s); } catch (err) { zprava(`${nazevSerialu(s)}: ${err.message}`, 6000); }
        }
      }
      return;
    }
    if (akce === 'smazat-dil') {
      const d = katalog.serialy.find(x => x.id === id)?.dily.find(x => x.id === t.dataset.dil);
      if (!confirm(`Smazat díl „${d?.nazev ?? ''}“?`)) return;
      await api(`${cesta}/dily/${encodeURIComponent(t.dataset.dil)}`, 'DELETE');
    }
    if (akce === 'obnovit') {
      t.disabled = true; t.textContent = '…';
      await obnovSerial(katalog.serialy.find(x => x.id === id));
      zprava('Obnoveno');
    }
    if (akce === 'prejmenovat') {
      const s = katalog.serialy.find(x => x.id === id);
      const novy = prompt('Název seriálu (prázdné = název ze zdroje):', nazevSerialu(s));
      if (novy === null) return;
      await api(cesta, 'POST', { nazev_vlastni: novy });
    }
    if (akce === 'vynulovat') {
      if (!confirm('Označit všechny díly jako nezhlédnuté?')) return;
      await api(cesta, 'POST', { zrusit_zhlednuti: true });
    }
    if (akce === 'smazat') {
      const s = katalog.serialy.find(x => x.id === id);
      if (!confirm(`Odebrat „${s ? nazevSerialu(s) : 'seriál'}“ z aplikace? Zmizí i záznam o zhlédnutých dílech.`)) return;
      await api(cesta, 'DELETE');
    }
    await nactiKatalog();
  } catch (err) {
    zprava(err.message, 6000);
    await nactiKatalog().catch(() => {});
  }
});

document.addEventListener('submit', async e => {
  e.preventDefault();
  const f = e.target, data = Object.fromEntries(new FormData(f));
  const tlacitko = f.querySelector('button');
  const puvodniText = tlacitko.textContent;
  tlacitko.disabled = true;
  tlacitko.textContent = 'Načítám…';
  try {
    if (f.id === 'pruvodceZnelka') {
      if (data.url.trim()) await api('znelka', 'POST', data);
      katalog = await api('katalog');
      return jdi({ typ: 'pruvodce', krok: 2 });
    }
    if (f.id === 'pridat') {
      const s = await pridejSerial(data.url, data.nazev);
      zprava(`Přidáno: ${nazevSerialu(s)}`);
    }
    if (f.id === 'znelka') { await api('znelka', 'POST', data); zprava(data.url.trim() ? 'Znělka uložena' : 'Znělka vypnuta'); }
    if (f.id === 'vlastni') {
      const odkazy = await rozbalOdkazy(data.odkazy.split(/\s+/).filter(Boolean));
      const v = await api('vlastni', 'POST', { nazev: data.nazev, odkazy });
      zprava(`Vytvořeno: ${v.serial.nazev} (${dilu(v.pridano)})`);
      v.chyby.forEach(ch => zprava(ch, 7000));
      rozbaleny = v.serial.id;
    }
    if (f.classList.contains('pridat-yt')) {   // díl(y) z YouTube do seriálu
      const sid = f.dataset.serial;
      const telo = { odkazy: await rozbalOdkazy([data.odkaz]) };
      if (f.dataset.cislo) Object.assign(telo, { cislo: Number(f.dataset.cislo), rada: f.dataset.rada || null, nazev: f.dataset.nazev });
      const v = await api(`serialy/${encodeURIComponent(sid)}/youtube`, 'POST', telo);
      zprava(v.pridano === 1 ? 'Díl přidán' : `Přidáno: ${dilu(v.pridano)}`);
      v.chyby.forEach(ch => zprava(ch, 7000));
      if (f.dataset.cislo) doplneni[sid] = await api(`serialy/${encodeURIComponent(sid)}/doplneni`);
    }
    await nactiKatalog();
  } catch (err) {
    zprava(err.message, 6000);
    tlacitko.disabled = false; tlacitko.textContent = puvodniText;
  }
});

// ---------- přehrávání ----------
// Postup: znělka (YouTube) → díl. YouTube díl hraje přímo tady, díl z iVysílání se otevře v nové kartě
// (ČT nedovoluje vložit svůj přehrávač do cizí stránky).

let yt = null, ytPripraven = null;
let prehravani = null;        // { serial, dil, faze: 'znelka' | 'dil' | 'konec' }
let hlidaniKarty = null;

window.onYouTubeIframeAPIReady = () => {
  ytPripraven = new Promise(hotovo => {
    yt = new YT.Player('ytPlayer', {
      width: '100%', height: '100%',
      host: 'https://www.youtube-nocookie.com',   // méně sledování, i když jde o stejný přehrávač
      playerVars: { rel: 0, playsinline: 1, fs: 0 },
      events: { onReady: hotovo, onStateChange: ytStav, onError: ytChyba },
    });
  });
};

const urlPrehravaceCT = idec => 'https://player.ceskatelevize.cz/?' + new URLSearchParams({
  origin: 'iVysilani', autoStart: 'true', client: 'iVysilaniWeb', IDEC: idec,
});

async function prehraj(serial, dil) {
  if (!dil) return;
  prehravani = { serial, dil, faze: 'znelka' };
  $('kino').hidden = false;
  panel(null);
  try { await $('kino').requestFullscreen(); } catch { /* např. iPhone celou obrazovku pro stránku neumí */ }

  if (!yt) {   // přehrávač YouTube se nenačetl (bez internetu, blokátor…)
    if (dil.typ === 'youtube') return bezPrehravace();
    return poZnelce();
  }
  if (!katalog.znelka) return poZnelce();
  await ytPripraven;
  $('ytHost').hidden = false;
  yt.loadVideoById(katalog.znelka);
}

function bezPrehravace() {
  const { dil } = prehravani;
  panel(`<div class="mesic">😕</div><h2>Přehrávač YouTube se nenačetl</h2>
    <p>Zkontroluj připojení k internetu, případně vypni blokátor reklam pro tuto stránku a obnov ji.</p>
    <div class="radek">
      <a class="btn" href="https://www.youtube.com/watch?v=${esc(dil.id)}" target="_blank" rel="noopener">Otevřít na YouTube</a>
      <button class="btn hlavni" data-kino="zavrit">Zavřít</button></div>`);
}

function ytStav(e) {
  if (!prehravani || e.data !== YT.PlayerState.ENDED) return;
  if (prehravani.faze === 'znelka') poZnelce();
  else if (prehravani.faze === 'dil') dilDohral();
}

function ytChyba(e) {
  if (!prehravani) return;
  if (prehravani.faze === 'znelka') { zprava('Znělku nejde přehrát, pouštím rovnou díl'); return poZnelce(); }
  const zakazano = e.data === 101 || e.data === 150;
  panel(`<div class="mesic">😕</div><h2>Tenhle díl nejde pustit</h2>
    <p>${zakazano ? 'Autor videa nedovolil přehrávání mimo YouTube.' : 'Video není dostupné (možná bylo smazáno).'}</p>
    <div class="radek">
      ${zakazano ? `<a class="btn" href="https://www.youtube.com/watch?v=${esc(prehravani.dil.id)}" target="_blank" rel="noopener">Otevřít na YouTube</a>` : ''}
      <button class="btn hlavni" data-kino="dalsi">Další díl</button>
      <button class="btn" data-kino="zavrit">Zavřít</button></div>`);
}

function poZnelce() {
  const { dil } = prehravani;
  prehravani.faze = 'dil';
  if (dil.typ === 'youtube') {
    if (!yt) return bezPrehravace();
    $('ytHost').hidden = false;
    yt.loadVideoById(dil.id);
  } else {
    try { yt?.stopVideo(); } catch {}
    $('ytHost').hidden = true;
    otevriCT();
  }
}

function otevriCT() {
  const { dil } = prehravani;
  const karta = window.open(urlPrehravaceCT(dil.id), 'nadobrounoc-ct');
  if (!karta) {
    // Prohlížeč zablokoval otevření bez kliknutí → necháme rodiče kliknout
    return panel(`<div class="mesic">🌙</div><h2>${esc(dil.nazev)}</h2>
      <p>Díl je z iVysílání a pustí se v nové kartě.</p>
      <div class="radek"><button class="btn hlavni" data-kino="otevrit-ct">▶ Pustit díl</button></div>`);
  }
  oznacZhlednuto();
  panel(`<div class="mesic">📺</div><h2>${esc(dil.nazev)}</h2>
    <p>Díl běží v nové kartě. Když nehraje zvuk, klikni v přehrávači na reproduktor.
       Celou obrazovku zapneš tlačítkem v přehrávači nebo klávesou F11. Až kartu zavřeš, vrátíme se sem.</p>
    <div class="radek"><button class="btn" data-kino="hotovo">Hotovo</button></div>`);
  clearInterval(hlidaniKarty);
  hlidaniKarty = setInterval(() => {
    if (karta.closed) { clearInterval(hlidaniKarty); if (prehravani?.faze === 'dil') dilDohral(true); }
  }, 1000);
}

async function oznacZhlednuto() {
  const { serial, dil } = prehravani;
  dil.zhlednuto = new Date().toISOString();
  try {
    await api(`serialy/${encodeURIComponent(serial.id)}/dily/${encodeURIComponent(dil.id)}`, 'POST', { zhlednuto: dil.zhlednuto });
  } catch (err) { zprava('Nepodařilo se uložit zhlédnutí: ' + err.message); }
}

function dilDohral(uzOznaceno = false) {
  if (!uzOznaceno && prehravani.dil.typ === 'youtube') oznacZhlednuto();
  prehravani.faze = 'konec';
  try { yt?.stopVideo(); } catch {}
  $('ytHost').hidden = true;
  const dalsi = dalsiDil(prehravani.serial, prehravani.dil);
  panel(`<div class="mesic">🌙</div><h2>Dobrou noc!</h2>
    <div class="radek">
      <button class="btn" data-kino="zavrit">Zpět</button>
      ${dalsi ? '<button class="btn hlavni" data-kino="dalsi">Ještě jeden díl</button>' : ''}
    </div>`);
}

function panel(html) {
  $('kinoPanel').hidden = !html;
  $('kinoPanel').innerHTML = html || '';
}

function zavritKino() {
  clearInterval(hlidaniKarty);
  try { yt?.stopVideo(); } catch {}
  prehravani = null;
  $('ytHost').hidden = true;
  panel(null);
  $('kino').hidden = true;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  vykresli();
}

$('stop').addEventListener('click', zavritKino);
$('kino').addEventListener('click', e => {
  const akce = e.target.closest('[data-kino]')?.dataset.kino;
  if (akce === 'zavrit' || akce === 'hotovo') zavritKino();
  if (akce === 'otevrit-ct') otevriCT();
  if (akce === 'dalsi') {
    const { serial, dil } = prehravani;
    const dalsi = dalsiDil(serial, dil);
    if (dalsi) prehraj(serial, dalsi); else zavritKino();
  }
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('kino').hidden && !document.fullscreenElement) zavritKino(); });

// ---------- start ----------
Promise.all([nactiSchopnosti(), api('katalog')])
  .then(([s, k]) => {
    katalog = k;
    posledniZprava = s.posledni;
    vykresli();
    if (s.nacita_se.length) { zprava('Načítám seriály…'); hlidejNacitani(); }
  })
  .catch(err => zprava('Server neodpovídá: ' + err.message, 8000));
