/* Auditoria visual mobile do Missal Diário — não altera os dados do site. */
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
  const browser = await (def.engine === 'webkit' ? webkit : chromium).launch({ headless: true });
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
    const celebration = (await page.locator('#celebration').textContent() || '').trim();
    emit(row, 'celebracao-carregada', !/carregando|^—$|^$/i.test(celebration), celebration.slice(0, 90));
    const layout = await page.evaluate(() => ({
      viewport: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth,
      quickCount: document.querySelectorAll('#quickSteps .quick-step').length,
      navVisible: !!document.querySelector('.mobile-nav') && getComputedStyle(document.querySelector('.mobile-nav')).display !== 'none'
    }));
    emit(row, 'sem-rolagem-horizontal', layout.scrollWidth <= layout.viewport + 2 && layout.bodyWidth <= layout.viewport + 2, JSON.stringify(layout));
    emit(row, 'barra-inferior-visivel', layout.navVisible);
    emit(row, 'separacao-rapida-com-paginas', layout.quickCount >= 3, 'Marcadores: ' + layout.quickCount);
    await page.screenshot({ path: path.join(out, def.name + '-inicio.png'), fullPage: false });
    if (await page.locator('#quickSteps .quick-step').count()) {
      const info = await page.locator('#quickSteps').evaluate(el => {
        const p = el.getBoundingClientRect();
        return { width: p.width, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
          steps: [...el.querySelectorAll('.quick-step')].map(n => ({ x: n.getBoundingClientRect().left, right: n.getBoundingClientRect().right, text: n.textContent.trim() })) };
      });
      emit(row, 'marcadores-sem-corte', info.steps.every(x => x.x >= -2 && x.right <= def.width + 2), JSON.stringify(info).slice(0, 400));
    }
    await page.locator('#tapes').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(out, def.name + '-marcacoes.png'), fullPage: false });
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(out, def.name + '-rodape.png'), fullPage: false });
    const back = await page.locator('#backToTop').evaluate(el => ({ shown: el.classList.contains('show'), r: { ...el.getBoundingClientRect().toJSON() } }));
    const nav = await rects(page, '.mobile-nav');
    emit(row, 'subir-ao-topo-acima-menu', back.shown && back.r.bottom < nav.y + 2,
      JSON.stringify({ back: back.r, nav }));
    await page.locator('#mobileMoreBtn').click();
    await page.waitForFunction(() => {
      const el = document.getElementById('mobileMoreSheet');
      return !!el && el.classList.contains('open') && el.getBoundingClientRect().bottom <= window.innerHeight + 3;
    }, null, { timeout: 5000 }).catch(() => {});
    const more = await rects(page, '#mobileMoreSheet');
    emit(row, 'menu-mais-abre', await page.locator('#mobileMoreBtn').getAttribute('aria-expanded') === 'true');
    emit(row, 'menu-mais-cabe-na-tela', more.y >= -3 && more.bottom <= def.height + 3, JSON.stringify(more));
    await page.screenshot({ path: path.join(out, def.name + '-menu.png'), fullPage: false });
    await page.locator('#mobileMoreClose').click();
    emit(row, 'menu-mais-fecha', await page.locator('#mobileMoreBtn').getAttribute('aria-expanded') === 'false');
    await page.locator('#datePickerBtn').click();
    emit(row, 'calendario-abre', await page.locator('#dateMenu').isVisible());
    const oldTitle = (await page.locator('.calendar-head strong').textContent() || '').trim();
    const prev = page.locator('#calendarPrev');
    if (await prev.isEnabled()) {
      await prev.click();
      const newTitle = (await page.locator('.calendar-head strong').textContent() || '').trim();
      emit(row, 'troca-mes-sem-fechar', await page.locator('#dateMenu').isVisible() && newTitle !== oldTitle,
        oldTitle + ' => ' + newTitle);
    } else {
      emit(row, 'troca-mes-sem-fechar', true, 'Seta anterior desabilitada no limite de datas');
    }
    await page.screenshot({ path: path.join(out, def.name + '-calendario.png'), fullPage: false });
    await page.locator('#calendarClose').click();
    emit(row, 'calendario-fecha', !(await page.locator('#dateMenu').isVisible()));
    await page.locator('#mobileCelebrationBtn').click();
    await page.waitForTimeout(200);
    emit(row, 'modo-celebracao-abre', await page.locator('body').evaluate(el => el.classList.contains('celebration-mode')));
    await page.screenshot({ path: path.join(out, def.name + '-celebracao.png'), fullPage: false });
    const exit = page.locator('#celebrationModeExit');
    await exit.click();
    emit(row, 'modo-celebracao-fecha', !(await page.locator('body').evaluate(el => el.classList.contains('celebration-mode'))));
    await page.locator('#mobileMoreBtn').click();
    await page.locator('#mobileMoreSheet [data-action="prepare"]').click();
    await page.waitForTimeout(180);
    emit(row, 'preparar-missal-abre', await page.locator('#prepareMissalOverlay').isVisible());
    const prep = await rects(page, '#prepareMissalOverlay .prepare-missal-dialog');
    emit(row, 'dialogo-preparar-cabe-na-tela', prep.x >= -3 && prep.right <= def.width + 3, JSON.stringify(prep));
    await page.screenshot({ path: path.join(out, def.name + '-preparar.png'), fullPage: false });
    await page.locator('#prepareMissalClose').click();
    emit(row, 'preparar-missal-fecha', !(await page.locator('#prepareMissalOverlay').isVisible()));
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
