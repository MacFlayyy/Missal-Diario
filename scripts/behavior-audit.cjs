/* Auditoria de comportamento do Missal Diário (Chromium e WebKit).
   Cobre o que as outras auditorias não cobrem:
   1. Todos os dias do data.js abrem sem erro de JavaScript, sem texto quebrado
      e sem rolagem horizontal, no celular e no computador.
   2. A página não "pula" ao abrir (CLS < 0,05), mesmo com fontes lentas.
   3. A primeira visita não recarrega quando o Service Worker assume.
   4. Offline: a página abre com o dia certo.
   5. Virada das 05h: antes das 05h mostra o dia anterior; às 05h libera o dia;
      no sábado às 05h libera o domingo; aberta na véspera, avança às 05h.
   Sai com código 1 se qualquer verificação falhar. */
const {chromium, webkit} = require('playwright');
const ORIGIN = process.env.AUDIT_ORIGIN || 'http://127.0.0.1:8765/';
const URL = ORIGIN + 'index.html';
const onlyChromium = process.env.AUDIT_CHROMIUM_ONLY === '1';
let failures = 0, total = 0;
const ok = (name, cond, extra = '') => {
  total++; if (!cond) failures++;
  console.log((cond ? 'OK    ' : 'FALHA ') + name + (extra && !cond ? ' :: ' + extra : ''));
};
const blockBeacon = ctx => ctx.route('**/cloudflareinsights.com/**', r => r.abort());

async function allDays(browserType, label, viewport) {
  const b = await browserType.launch();
  const ctx = await b.newContext({viewport, timezoneId: 'America/Sao_Paulo', serviceWorkers: 'block', reducedMotion: 'reduce'});
  await blockBeacon(ctx);
  const page = await ctx.newPage(); const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(URL, {waitUntil: 'load'});
  const res = await page.evaluate(async () => {
    const bad = [];
    const keys = Object.keys(window.MISSAL_DATA).sort();
    for (const k of keys) {
      render(k);
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      const v3 = document.getElementById('v3');
      const txt = v3.innerText;
      const e = getDisplayEntry(k);
      if (/\bundefined\b|\bnull\b|NaN|\[object/.test(txt)) bad.push(k + ' texto quebrado');
      if (document.getElementById('v3Title').textContent.trim() !== e.celebration) bad.push(k + ' título diferente');
      if (document.querySelectorAll('#v3List .v3-r').length !== 5) bad.push(k + ' fitas ≠ 5');
      if (document.documentElement.scrollWidth > innerWidth + 1) bad.push(k + ' rolagem horizontal');
    }
    return {n: keys.length, bad};
  });
  ok(`${label} ${viewport.width}px: ${res.n} dias sem erro`, res.bad.length === 0 && errors.length === 0,
     JSON.stringify(res.bad.slice(0, 6)) + ' ' + errors.slice(0, 3).join(' | '));
  await b.close();
}

async function layoutShift(browserType, label, viewport) {
  const b = await browserType.launch();
  const ctx = await b.newContext({viewport, timezoneId: 'America/Sao_Paulo', serviceWorkers: 'block'});
  await blockBeacon(ctx);
  await ctx.route('**/fonts.gstatic.com/**', async r => { await new Promise(s => setTimeout(s, 1200)); r.continue(); });
  await ctx.addInitScript(() => { window.__cls = 0; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({type: 'layout-shift', buffered: true}); } catch (e) { window.__cls = -1; } });
  const page = await ctx.newPage();
  await page.goto(URL, {waitUntil: 'load'}); await page.waitForTimeout(2500);
  const cls = await page.evaluate(() => window.__cls);
  if (cls >= 0) ok(`${label} ${viewport.width}px: página não pula ao abrir (CLS ${cls.toFixed(3)})`, cls < 0.05, String(cls));
  await b.close();
}

async function serviceWorker() {
  const b = await chromium.launch();
  const ctx = await b.newContext({timezoneId: 'America/Sao_Paulo'});
  await blockBeacon(ctx);
  const page = await ctx.newPage(); let navs = 0;
  page.on('framenavigated', f => { if (f === page.mainFrame()) navs++; });
  await page.goto(URL); await page.waitForTimeout(5000);
  const controlled = await page.evaluate(() => !!navigator.serviceWorker.controller);
  ok('primeira visita não recarrega a página', navs === 1, 'navegações: ' + navs);
  ok('Service Worker assume a página', controlled);
  await ctx.setOffline(true); await page.reload(); await page.waitForTimeout(1500);
  const title = await page.evaluate(() => (document.getElementById('v3Title') || {}).textContent || '');
  ok('offline: abre com o dia', title.trim().length > 3 && !/carregando/i.test(title), title);
  await b.close();
}

async function release() {
  // Simula a publicação como o robô faz: em cada dia D o status libera D
  // (e, no sábado, marca o domingo como prévia). Assim o teste não depende
  // do status real do dia em que roda.
  const b = await chromium.launch();
  const addDays = (k, n) => { const d = new Date(k + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
  const open = async (iso, statusFor) => {
    const ctx = await b.newContext({timezoneId: 'America/Sao_Paulo', serviceWorkers: 'block'});
    await blockBeacon(ctx);
    await ctx.route('**/status.js*', r => {
      const sat = new Date(statusFor + 'T12:00:00Z').getUTCDay() === 6;
      const body = 'window.MISSAL_STATUS = ' + JSON.stringify({availableThrough: statusFor, timezone: 'America/Sao_Paulo',
        sundayPreview: sat ? addDays(statusFor, 1) : ''}) + ';';
      r.fulfill({status: 200, contentType: 'application/javascript', body});
    });
    const page = await ctx.newPage();
    await page.clock.install({time: new Date(iso)});
    await page.goto(URL, {waitUntil: 'load'}); await page.clock.runFor(1500);
    return {ctx, page};
  };
  // Uma semana com sexta, sábado e domingo cadastrados em data.js.
  const probe = await open(new Date().toISOString(), addDays(new Date().toISOString().slice(0, 10), -1));
  const keys = await probe.page.evaluate(() => Object.keys(window.MISSAL_DATA).sort());
  await probe.ctx.close();
  const fri = keys.find(k => new Date(k + 'T12:00:00Z').getUTCDay() === 5 && keys.includes(addDays(k, 2)) && keys.includes(addDays(k, -1)));
  if (!fri) { ok('virada das 05h: semana completa encontrada', false); await b.close(); return; }
  const thu = addDays(fri, -1), sat = addDays(fri, 1), sun = addDays(fri, 2);
  const last = async (iso, statusFor) => { const {ctx, page} = await open(iso, statusFor); const v = await page.evaluate(() => getVisibleDates().slice(-1)[0]); await ctx.close(); return v; };
  // O robô publica o dia por volta das 04h; antes das 05h a página ainda mostra o dia anterior.
  ok(`sexta ${fri} 04:59 mostra até a quinta`, await last(fri + 'T04:59:00-03:00', fri) === thu);
  ok(`sexta ${fri} 05:00 libera a sexta`, await last(fri + 'T05:00:30-03:00', fri) === fri);
  ok(`sábado ${sat} 04:59 mostra até a sexta`, await last(sat + 'T04:59:00-03:00', sat) === fri);
  ok(`sábado ${sat} 05:00 libera o domingo`, await last(sat + 'T05:00:30-03:00', sat) === sun);
  ok(`domingo ${sun} 02:00 continua mostrando o domingo`, await last(sun + 'T02:00:00-03:00', sat) === sun);
  ok(`segunda não aparece antes da hora (domingo ${sun} 13h)`, await last(sun + 'T13:00:00-03:00', addDays(sun, 1)) === sun);
  for (const [label, iso, statusFor] of [['aberta às 04:59:50', fri + 'T04:59:50-03:00', fri], ['aberta na véspera às 22h', thu + 'T22:00:00-03:00', fri]]) {
    const {ctx, page} = await open(iso, statusFor);
    const before = await page.evaluate(() => { window.__paginaAntiga = true; return window.currentDateKey; });
    await page.clock.runFor(label.includes('véspera') ? 7 * 3600e3 + 180e3 : 180e3).catch(() => {});
    // A recarga acontece durante o avanço do relógio; espera a página nova desenhar o dia.
    let after;
    for (let i = 0; i < 40 && !after; i++) {
      await page.waitForLoadState('load').catch(() => {});
      after = await page.evaluate(() => window.__paginaAntiga ? undefined : window.currentDateKey).catch(() => undefined);
      if (!after) await page.clock.runFor(500).catch(() => {});
    }
    ok(`página ${label} avança às 05h (${before} → ${after})`, before !== fri && after === fri, after);
    await ctx.close();
  }
  await b.close();
}

async function leafletOfSelectedDay() {
  // Ao abrir um domingo anterior pela faixa da semana, o botão Folheto
  // precisa abrir o folheto DAQUELE domingo, não o do próximo.
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport: {width: 1280, height: 800}, timezoneId: 'America/Sao_Paulo', serviceWorkers: 'block'});
  await blockBeacon(ctx);
  const page = await ctx.newPage();
  await page.goto(URL, {waitUntil: 'load'});
  const res = await page.evaluate(() => {
    const bad = []; let checked = 0;
    const url = d => d && (d.folhetoDesktopUrl || d.folhetoUrl || d.folhetoMobileUrl || '');
    const visible = getVisibleDates();
    for (const k of visible) {
      if (weekdayForKey(k) !== 0 || !url(window.MISSAL_DATA[k]) || k === brasiliaTodayKey()) continue;
      render(k); checked++;
      const got = getDominicalLeafletUrl(); const d = window.MISSAL_DATA[k];
      if (![d.folhetoDesktopUrl, d.folhetoMobileUrl, d.folhetoUrl].includes(got)) bad.push(k + ' → ' + got.slice(-40));
    }
    return {bad, checked};
  });
  ok(`folheto do domingo escolhido (${res.checked} domingos)`, res.checked > 0 && res.bad.length === 0, JSON.stringify(res.bad.slice(0, 4)));
  await b.close();
}

(async () => {
  const engines = onlyChromium ? [[chromium, 'Chromium']] : [[chromium, 'Chromium'], [webkit, 'WebKit']];
  for (const [type, label] of engines) {
    await allDays(type, label, {width: 390, height: 844});
    await allDays(type, label, {width: 1280, height: 800});
  }
  await layoutShift(chromium, 'Chromium', {width: 390, height: 844});
  await layoutShift(chromium, 'Chromium', {width: 1350, height: 940});
  await serviceWorker();
  await leafletOfSelectedDay();
  await release();
  console.log(`COMPORTAMENTO_FIM ${JSON.stringify({total, failures})}`);
  process.exit(failures ? 1 : 0);
})().catch(e => { console.error(e); process.exit(1); });
