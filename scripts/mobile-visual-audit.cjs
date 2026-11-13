/* Auditoria visual mobile do Missal Diário (design v3) — não altera os dados do site. */
const { chromium, webkit, devices } = require('playwright');
const fs = require('fs');
const path = require('path');

const out = path.join(process.cwd(), 'mobile-visual-results');
fs.mkdirSync(out, { recursive: true });
const summary = [];
const cases = [
  { name: 'android-320', engine: 'chromium', width: 320, height: 700, ua: 'Mozilla/5.0 (Linux; Android 13; Pixel 4a) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36' },
  { name: 'android-360', engine: 'chromium', width: 360, height: 800, ua: 'Mozilla/5.0 (Linux; Android 13; SM-A536B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36' },
  { name: 'android-412', engine: 'chromium', width: 412, height: 915, ua: 'Mozilla/5.0 (Linux; Android 14; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36' },
  { name: 'iphone-se-375', engine: 'webkit', width: 375, height: 667, ua: devices['iPhone SE']?.userAgent },
  { name: 'iphone-13-390', engine: 'webkit', width: 390, height: 844, ua: devices['iPhone 13']?.userAgent },
  { name: 'iphone-plus-430', engine: 'webkit', width: 430, height: 932, ua: devices['iPhone 15 Plus']?.userAgent }
];
const target = 'http://127.0.0.1:8765/';
const emit = (row, key, okay, extra) => {
  row.checks.push({ key, pass: !!okay, details: extra || '' });
  console.log((okay ? 'OK   ' : 'FALHA') + ' ' + row.name + ' ' + key + (extra ? ' :: ' + extra : ''));
};
const rects = async (page, selector) => page.locator(selector).first().evaluate(el => {
  const r = el.getBoundingClientRect();
  const st = getComputedStyle(el);
  return { x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, bottom: r.bottom, display: st.display, visibility: st.visibility };
});
async function runCase(def) {
  const row = { name: def.name, engine: def.engine, viewport: [def.width, def.height], checks: [], consoleErrors: [], pageErrors: [] };
  const browser = await (def.engine === 'webkit' && process.env.AUDIT_CHROMIUM_ONLY !== '1' ? webkit : chromium).launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: def.width, height: def.height }, deviceScaleFactor: 2,
    isMobile: true, hasTouch: true, reducedMotion: 'reduce',
    locale: 'pt-BR', timezoneId: 'America/Sao_Paulo', ...(def.ua ? { userAgent: def.ua } : {}),
    serviceWorkers: 'block', acceptDownloads: true
  });
  const page = await context.newPage();
  page.on('pageerror', e => row.pageErrors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') row.consoleErrors.push(m.text()); });
  try {
    const resp = await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 30000 });
    emit(row, 'pagina-http', !!resp && resp.status() === 200, String(resp?.status()));
    await page.waitForTimeout(650);
    const celebration = (await page.locator('#v3Title').textContent() || '').trim();
    emit(row, 'celebracao-carregada', !/carregando|^—$|^$/i.test(celebration), celebration.slice(0, 90));
    const layout = await page.evaluate(() => {
      const glass = document.getElementById('v3Glass'), g = glass.getBoundingClientRect();
      return { viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth, bodyWidth: document.body.scrollWidth,
        quickCount: document.querySelectorAll('#v3Quick button').length, rows: document.querySelectorAll('#v3List .v3-r').length,
        navVisible: getComputedStyle(glass).display !== 'none', nav: { top: g.top, bottom: g.bottom, left: g.left, right: g.right },
        oldHidden: getComputedStyle(document.querySelector('.shell')).display === 'none' };
    });
    emit(row, 'design-novo-ativo', layout.oldHidden);
    emit(row, 'sem-rolagem-horizontal', layout.scrollWidth <= layout.viewport + 2 && layout.bodyWidth <= layout.viewport + 2, JSON.stringify(layout));
    emit(row, 'barra-inferior-visivel', layout.navVisible && layout.nav.left >= -1 && layout.nav.right <= def.width + 1 && layout.nav.bottom <= def.height + 1, JSON.stringify(layout.nav));
    emit(row, 'paginas-no-topo', layout.quickCount === 5 && layout.rows === 5, 'Páginas: ' + layout.quickCount + ' • fitas: ' + layout.rows);
    await page.screenshot({ path: path.join(out, def.name + '-inicio.png'), fullPage: false });
    const info = await page.locator('#v3Quick').evaluate(el => ({
      steps: [...el.querySelectorAll('button')].map(n => ({ x: n.getBoundingClientRect().left, right: n.getBoundingClientRect().right,
        text: n.textContent.trim(), clipped: n.scrollWidth > n.clientWidth + 2 })) }));
    emit(row, 'paginas-sem-corte', info.steps.every(x => x.x >= -2 && x.right <= def.width + 2 && !x.clipped), JSON.stringify(info).slice(0, 400));
    const firstScreen = await page.evaluate(() => document.getElementById('v3Quick').getBoundingClientRect().bottom);
    emit(row, 'paginas-visiveis-sem-rolar', firstScreen <= def.height + 2, 'Fim do cartão de páginas: ' + Math.round(firstScreen));
    const targets = await page.evaluate(() => [...document.querySelectorAll('#v3 button, #v3 a')].filter(e => e.getClientRects().length && !e.closest('.v3-sheet'))
      .map(e => { const r = e.getBoundingClientRect(); return { t: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 28), w: Math.round(r.width), h: Math.round(r.height) }; })
      .filter(x => x.h < 36 || x.w < 36));
    emit(row, 'alvos-de-toque-confortaveis', targets.length === 0, JSON.stringify(targets).slice(0, 300));
    const week = page.locator('#v3Week button:not([disabled])');
    if (await week.count() > 1) {
      const key = await week.first().getAttribute('data-date');
      await week.first().click();
      await page.waitForTimeout(120);
      emit(row, 'semana-troca-o-dia', await page.evaluate(k => window.currentDateKey === k &&
        document.querySelector('#v3Week button[aria-pressed="true"]')?.dataset.date === k &&
        document.getElementById('v3Title').textContent.trim() === getDisplayEntry(k).celebration, key), key);
      await page.evaluate(() => { const d = getVisibleDates(); render(d.includes(brasiliaTodayKey()) ? brasiliaTodayKey() : d[d.length - 1]); });
    }
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(out, def.name + '-rodape.png'), fullPage: false });
    const foot = await page.evaluate(() => { const c = document.querySelector('.v3-cred').getBoundingClientRect(), g = document.getElementById('v3Glass').getBoundingClientRect();
      return { credBottom: c.bottom, glassTop: g.top, links: document.querySelectorAll('.v3-cred a').length }; });
    emit(row, 'rodape-com-contatos-acima-da-barra', foot.links === 2 && foot.credBottom <= foot.glassTop + 2, JSON.stringify(foot));
    await page.evaluate(() => window.scrollTo(0, 0));
    const tab = name => page.locator('.v3-gt[data-v3-tab="' + name + '"]');
    const activeTab = () => page.evaluate(() => [...document.querySelectorAll('.v3-gt.on')].map(b => b.dataset.v3Tab).join());
    const waitSheet = id => page.waitForFunction(i => { const el = document.getElementById(i);
      return !!el && el.classList.contains('open') && el.getBoundingClientRect().bottom <= window.innerHeight + 3; }, id, { timeout: 5000 }).catch(() => {});
    await tab('more').click();
    await waitSheet('v3MoreSheet');
    const more = await rects(page, '#v3MoreSheet');
    emit(row, 'menu-mais-abre', await activeTab() === 'more' && await page.locator('#v3MoreSheet').evaluate(e => e.classList.contains('open')));
    emit(row, 'menu-mais-cabe-na-tela', more.y >= -3 && more.bottom <= def.height + 3, JSON.stringify(more));
    emit(row, 'menu-mais-sem-preparar-missal', await page.locator('#v3MoreSheet [data-v3-act]').evaluateAll(els => !els.some(e => /preparar/i.test(e.textContent))));
    await page.screenshot({ path: path.join(out, def.name + '-menu.png'), fullPage: false });
    await page.locator('#v3MoreSheet [data-theme-choice="auto"]').focus();
    await page.keyboard.press('Tab');
    const focusAfterTab = await page.evaluate(() => ({ html: document.activeElement?.outerHTML.slice(0, 90),
      ok: !!document.activeElement?.hasAttribute('data-v3-close') && document.getElementById('v3MoreSheet').contains(document.activeElement) }));
    emit(row, 'menu-mais-foco-nao-escapa', focusAfterTab.ok, focusAfterTab.html);
    await page.keyboard.press('Shift+Tab');
    emit(row, 'menu-mais-shift-tab-ciclico', await page.evaluate(() => document.activeElement?.dataset?.themeChoice === 'auto'));
    await page.keyboard.press('Escape');
    emit(row, 'menu-mais-escape-restaura-foco', await page.evaluate(() =>
      !document.getElementById('v3MoreSheet').classList.contains('open') && document.activeElement?.dataset?.v3Tab === 'more'));
    await tab('more').click();
    await waitSheet('v3MoreSheet');
    await page.locator('#v3MoreSheet [data-v3-close]').click();
    emit(row, 'menu-mais-fecha', await activeTab() === 'home' && !(await page.locator('#v3MoreSheet').evaluate(e => e.classList.contains('open'))));
    await tab('cal').click();
    await waitSheet('v3CalSheet');
    const cal = await rects(page, '#v3CalSheet');
    emit(row, 'calendario-abre', await activeTab() === 'cal' && cal.y >= -3 && cal.bottom <= def.height + 3, JSON.stringify(cal));
    const oldTitle = (await page.locator('#v3CalTitle').textContent() || '').trim();
    const prev = page.locator('#v3CalPrev');
    if (await prev.isEnabled()) {
      await prev.click();
      const newTitle = (await page.locator('#v3CalTitle').textContent() || '').trim();
      emit(row, 'troca-mes-sem-fechar', await page.locator('#v3CalSheet').evaluate(e => e.classList.contains('open')) && newTitle !== oldTitle, oldTitle + ' => ' + newTitle);
    } else {
      emit(row, 'troca-mes-sem-fechar', true, 'Seta anterior desabilitada no limite de datas');
    }
    await page.screenshot({ path: path.join(out, def.name + '-calendario.png'), fullPage: false });
    await page.locator('#v3CalSheet [data-v3-close]').click();
    emit(row, 'calendario-fecha', !(await page.locator('#v3CalSheet').evaluate(e => e.classList.contains('open'))) && await activeTab() === 'home');
    await tab('cel').click();
    await page.waitForTimeout(200);
    emit(row, 'modo-celebracao-abre', await page.evaluate(() => document.body.classList.contains('v3-cel') &&
      document.querySelectorAll('#v3Cards .v3-f').length === 5) && await activeTab() === 'cel');
    emit(row, 'modo-celebracao-sem-rolagem-horizontal', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
    await page.screenshot({ path: path.join(out, def.name + '-celebracao.png'), fullPage: false });
    await tab('home').click();
    emit(row, 'modo-celebracao-fecha', !(await page.evaluate(() => document.body.classList.contains('v3-cel'))) && await activeTab() === 'home');
    await page.locator('#v3List .v3-r[data-tape="4"]').click();
    await page.waitForTimeout(350);
    emit(row, 'fita-abre-no-modo-celebracao', await page.evaluate(() => document.body.classList.contains('v3-cel') &&
      document.getElementById('v3-tape-4').getBoundingClientRect().top < innerHeight));
    await tab('home').click();
    const after = await page.evaluate(() => ({ viewport: innerWidth, scroll: document.documentElement.scrollWidth }));
    emit(row, 'sem-rolagem-horizontal-final', after.scroll <= after.viewport + 2, JSON.stringify(after));
    const appErrors = row.pageErrors.filter(msg => !/cloudflareinsights\.com|\/cdn-cgi\/rum/i.test(msg));
    emit(row, 'sem-erros-javascript', appErrors.length === 0, appErrors.join(' | ').slice(0, 350));
  } catch (e) {
    emit(row, 'execucao', false, String(e.message).slice(0, 750));
    try { await page.screenshot({ path: path.join(out, def.name + '-falha.png'), fullPage: false }); } catch {}
  } finally {
    await context.close(); await browser.close();
  }
  summary.push(row);
}
(async () => {
  for (const c of cases) await runCase(c);
  const failed = summary.flatMap(r => r.checks.filter(c => !c.pass).map(c => r.name + ': ' + c.key + ' - ' + c.details));
  const report = { date: new Date().toISOString(), target, cases: summary, failed };
  fs.writeFileSync(path.join(out, 'relatorio.json'), JSON.stringify(report, null, 2));
  console.log('\nRESULTADO: ' + summary.length + ' telas, ' + failed.length + ' verificacoes falharam.');
  if (failed.length) console.error(failed.join('\n'));
  process.exitCode = failed.length ? 1 : 0;
})().catch(e => { console.error(e); process.exitCode = 1; });
