const {chromium, webkit}=require('playwright');
const fs=require('fs');
const path=require('path');
const ROOT=path.join(process.cwd(),'full-audit-results');fs.mkdirSync(ROOT,{recursive:true});
const local='http://127.0.0.1:8765/';
const publicUrl='https://macflayyy.github.io/Missal-Diario/';
const scenarios=[
 {name:'android-mini',engine:'chromium',w:320,h:700,mobile:true},
 {name:'android-360',engine:'chromium',w:360,h:800,mobile:true},
 {name:'iphone-390',engine:'webkit',w:390,h:844,mobile:true},
 {name:'iphone-430',engine:'webkit',w:430,h:932,mobile:true},
 {name:'tablet-768',engine:'chromium',w:768,h:1024,mobile:false},
 {name:'desktop-1024',engine:'chromium',w:1024,h:768,mobile:false},
 {name:'desktop-1440',engine:'chromium',w:1440,h:900,mobile:false},
 {name:'landscape-667x375',engine:'webkit',w:667,h:375,mobile:true}
];
const results=[], failures=[];
const mark=(row,key,pass,info={})=>{const entry={key,pass:!!pass,info};row.checks.push(entry);console.log((pass?'PASS':'FAIL')+' '+row.name+' '+key+' '+JSON.stringify(info).slice(0,330));if(!pass)failures.push(row.name+' '+key)};
async function run(config){
 const row={name:config.name,checks:[],errors:[],warnings:[]};results.push(row);
 const browser=await (config.engine==='webkit'?webkit:chromium).launch({headless:true});
 const ctx=await browser.newContext({viewport:{width:config.w,height:config.h},isMobile:config.mobile,hasTouch:config.mobile,
 deviceScaleFactor:2,timezoneId:'America/Sao_Paulo',locale:'pt-BR',serviceWorkers:'block',acceptDownloads:true,
 ...(config.engine==='webkit'?{userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'}:{})});
 const page=await ctx.newPage();
 page.on('pageerror',e=>{if(!/cloudflareinsights\.com|\/cdn-cgi\/rum/i.test(e.message))row.errors.push(e.message)});
 try{
   const r=await page.goto(local,{waitUntil:'domcontentloaded',timeout:30000});
   mark(row,'http-load',r?.status()===200,{code:r?.status()});
   await page.waitForTimeout(350);
   const metrics=await page.evaluate(()=>{
     const r=el=>{const b=el.getBoundingClientRect();return {x:b.x,y:b.y,right:b.right,bottom:b.bottom,w:b.width,h:b.height,display:getComputedStyle(el).display}};
     const ids=['.topbar','.hero','#tapes','.mobile-nav','#quickSteps','#backToTop','#datePickerBtn'];
     let boxes=Object.fromEntries(ids.map(k=>[k,document.querySelector(k)?r(document.querySelector(k)):null]));
     const overflow=[];
     document.querySelectorAll('button').forEach(el=>{if(getComputedStyle(el).display==='none')return;const t=(el.textContent||'').trim();if(t&&el.scrollWidth>el.clientWidth+4)overflow.push({id:el.id||el.className,text:t.slice(0,45),w:el.clientWidth,scroll:el.scrollWidth})});
     return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,tapes:document.querySelectorAll('#tapes article').length,quick:document.querySelectorAll('#quickSteps .quick-step').length,boxes,overflow,selected:window.currentDateKey,celebration:document.getElementById('celebration').textContent.trim(),
       sourceBadge:document.getElementById('sourceBadge').textContent.trim(),
       available:window.MISSAL_STATUS?.availableThrough,
       countLinks:document.querySelectorAll('a[href]').length,
       cacheController:!!navigator.serviceWorker?.controller,
       currentToken:document.querySelector('script[src^="data.js"]')?.getAttribute('src')};
   });
   row.metrics=metrics;
   mark(row,'no-horizontal-page-overflow',metrics.documentWidth<=config.w+1,{doc:metrics.documentWidth,viewport:config.w});
   mark(row,'five-tapes',metrics.tapes===5,{count:metrics.tapes});
   mark(row,'five-quick-pages',metrics.quick===5,{count:metrics.quick});
   const pageAlignment=await page.evaluate(()=>{
     return [...document.querySelectorAll('#tapes .tape .page-number')].map(el=>{
       const parent=el.closest('.page');
       const p=parent.getBoundingClientRect(),n=el.getBoundingClientRect();
       return {page:el.textContent.trim(),delta:Math.abs((p.left+p.right-n.left-n.right)/2),
         align:getComputedStyle(parent).alignItems,textAlign:getComputedStyle(el).textAlign};
     });
   });
   mark(row,'page-numbers-centered-in-cards',
     pageAlignment.length===5&&pageAlignment.every(v=>v.delta<=1.5&&v.align==='center'&&v.textAlign==='center'),
     {alignment:pageAlignment});
   if(config.w<=620){
     const initialTab=await page.locator('#mobileMarkingsBtn').evaluate(el=>el.classList.contains('active'));
     mark(row,'markings-tab-not-permanently-active',!initialTab,{active:initialTab});
     const atTapes=await page.evaluate(()=>{
       const root=document.documentElement;
       const previous=root.style.scrollBehavior;
       root.style.scrollBehavior='auto';
       const tapes=document.getElementById('tapes');
       window.scrollTo(0,tapes.getBoundingClientRect().top+window.scrollY-12);
       syncMarkingsActiveTab();
       const rect=tapes.getBoundingClientRect();
       const result={active:document.getElementById('mobileMarkingsBtn').classList.contains('active'),
         y:window.scrollY,tapeTop:rect.top,tapeBottom:rect.bottom};
       root.style.scrollBehavior=previous;
       return result;
     });
     mark(row,'markings-tab-active-at-tapes',atTapes.active,atTapes);
     const backAtTop=await page.evaluate(()=>{
       const root=document.documentElement;
       const previous=root.style.scrollBehavior;
       root.style.scrollBehavior='auto';
       window.scrollTo(0,0);
       syncMarkingsActiveTab();
       const result={active:document.getElementById('mobileMarkingsBtn').classList.contains('active'),
         y:window.scrollY,tapeTop:document.getElementById('tapes').getBoundingClientRect().top};
       root.style.scrollBehavior=previous;
       return result;
     });
     mark(row,'markings-tab-resets-at-top',!backAtTop.active&&backAtTop.y<3,backAtTop);
   }
   mark(row,'valid-day',metrics.selected===await page.evaluate(() => getVisibleDates().includes(brasiliaTodayKey()) ? brasiliaTodayKey() : getVisibleDates().at(-1)),{selected:metrics.selected,available:metrics.available});
   mark(row,'buttons-text-not-clipped',metrics.overflow.length===0,{overflow:metrics.overflow.slice(0,8)});
   await page.screenshot({path:path.join(ROOT,config.name+'-start.png'),fullPage:false});
   await page.locator('#datePickerBtn').click();
   const calendar=await page.evaluate(()=>{
     const el=document.querySelector('#dateMenu'),r=el.getBoundingClientRect();
     return {open:!el.hidden,x:r.x,right:r.right,top:r.top,bottom:r.bottom,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,winWidth:innerWidth,winHeight:innerHeight};
   });
   mark(row,'calendar-visible-within-screen',calendar.open && calendar.x>=-2 && calendar.right<=config.w+2 && calendar.top>=-3 && calendar.bottom<=config.h+3,calendar);
   const scrollLock=await page.evaluate(()=>({
     bodyPosition:getComputedStyle(document.body).position,
     rootOverflow:document.documentElement.style.overflow,scrollY:window.scrollY
   }));
   // O WebKit móvel não implementa mouse.wheel no Playwright.
   // Em iOS, verificar o bloqueio via posição fixa/overflow; nos outros
   // navegadores, testar também a rolagem física com wheel.
   if(!(config.mobile && config.engine==='webkit')){
     await page.mouse.wheel(0,410);
     await page.waitForTimeout(70);
   }
   const scrollAfterWheel=await page.evaluate(()=>window.scrollY);
   mark(row,'calendar-locks-background-scroll',
     scrollLock.bodyPosition==='fixed'&&scrollLock.rootOverflow==='hidden'&&
     scrollAfterWheel===scrollLock.scrollY,{...scrollLock,scrollAfterWheel,input:config.engine==='webkit'&&config.mobile?'mobile-scroll-lock-css':'mouse-wheel'});
   await page.screenshot({path:path.join(ROOT,config.name+'-calendar.png'),fullPage:false});
   // Teste de regressão: resize do navegador NÃO deve fechar o calendário,
   // inclusive ao atravessar o breakpoint de tablet para desktop.
   const narrower=config.w===1024 ? 900 : Math.max(280,config.w-20);
   await page.setViewportSize({width:narrower,height:config.h});
   const stillOpen=await page.locator('#dateMenu').isVisible();
   mark(row,'calendar-resize-keeps-dialog-open',stillOpen,{before:config.w,after:narrower});
   await page.setViewportSize({width:config.w,height:config.h});
   mark(row,'calendar-resize-back-keeps-dialog-open',await page.locator('#dateMenu').isVisible(),{restored:config.w});
   const prev=page.locator('#calendarPrev');
   if(await prev.isEnabled()){
     const title=await page.locator('.calendar-head strong').innerText();
     await prev.click();
     mark(row,'calendar-next-month-does-not-close',await page.locator('#dateMenu').isVisible() && (await page.locator('.calendar-head strong').innerText())!==title);
   }
   // verifies previous date selecting and restoring.
   const day=page.locator('.calendar-day[data-date]').first();
   if(await day.count()){
     const selected=await day.getAttribute('data-date');
     await day.click();
     mark(row,'calendar-select-historic-date',await page.evaluate(k=>window.currentDateKey===k,selected),{selected});
   }else await page.locator('#datePickerBtn').click();
   const scrollUnlocked=await page.evaluate(()=>({
     bodyPosition:getComputedStyle(document.body).position,
     rootOverflow:document.documentElement.style.overflow
   }));
   mark(row,'calendar-restores-background-scroll',
     scrollUnlocked.bodyPosition!=='fixed'&&scrollUnlocked.rootOverflow!=='hidden',scrollUnlocked);
   await page.evaluate(()=>{const dates=getVisibleDates();render(dates[dates.length-1]);});
   const visibility=await page.evaluate(()=>{
     const d=getVisibleDates(),last=d[d.length-1],all=getRegisteredDates();
     return {today:brasiliaTodayKey(),last,total:d.length,all:all.length,next:document.getElementById('nextBtn').disabled};
   });
   mark(row,'future-dates-locked',visibility.next && visibility.last <= new Date(Date.parse(visibility.today+'T00:00:00Z')+86400000).toISOString().slice(0,10),{last:visibility.last,count:visibility.total});
   // test date release rules with simulated source status, leaving external data untouched.
   const gate=await page.evaluate(()=>{
     const realDay=brasiliaTodayKey,realClock=brasiliaClockParts,realStatus=window.MISSAL_STATUS;
     const statuses={};function test(date,hour,available,preview){brasiliaTodayKey=()=>date;brasiliaClockParts=()=>({hour:String(hour)});window.MISSAL_STATUS={availableThrough:available,sundayPreview:preview};return {visible:getVisibleDates().slice(-2),preview:getSundayPreview(),limit:getAvailableThrough()};}
     try {
       statuses.satBefore=test('2026-10-10',4,'2026-10-10','2026-10-11');
       statuses.satAfter=test('2026-10-10',5,'2026-10-10','2026-10-11');
       statuses.sunBefore=test('2026-10-11',4,'2026-10-10','2026-10-11');
       statuses.sunEarlyPublished=test('2026-10-11',4,'2026-10-11','2026-10-11');
       statuses.solemnitySaturday=test('2026-10-31',6,'2026-10-31','2026-11-01');
       statuses.sunAfter=test('2026-10-11',5,'2026-10-11',undefined);
     }finally{brasiliaTodayKey=realDay;brasiliaClockParts=realClock;window.MISSAL_STATUS=realStatus;}return statuses;
   });
   mark(row,'saturday-release-rule',gate.satBefore.preview===null && gate.satAfter.preview==='2026-10-11' && gate.satBefore.limit==='2026-10-09',gate);
   mark(row,'sunday-midnight-preview-rule',gate.sunBefore.preview==='2026-10-11'&&gate.sunAfter.limit==='2026-10-11',gate);
   mark(row,'sunday-prepared-early-remains-visible',gate.sunEarlyPublished.preview==='2026-10-11'&&gate.sunEarlyPublished.limit==='2026-10-10',gate.sunEarlyPublished);
   mark(row,'sunday-solemnity-saturday-visible',gate.solemnitySaturday.preview==='2026-11-01'&&gate.solemnitySaturday.visible.includes('2026-11-01'),gate.solemnitySaturday);
   // Cobertura regressiva: a Vigília NUNCA é escolhida pelo relógio.
   const christmas=await page.evaluate(()=>{
     const previousDate=window.currentDateKey,oldDay=brasiliaTodayKey,oldClock=brasiliaClockParts,oldChoice=december24Choice;
     const samples=[];
     try{
       brasiliaTodayKey=()=> "2026-12-24";
       for(const hour of [10,13,21]){
         brasiliaClockParts=()=>({hour:String(hour)});
         for(const choice of [null,"morning","vigil"]){
           december24Choice=choice;render("2026-12-24");
           const pressed=[...document.querySelectorAll('#dec24MassChoice button[aria-pressed="true"]')]
             .map(el=>el.dataset.dec24Mass);
           const title=document.getElementById("celebration").textContent;
           const quick=document.getElementById("quickSep").textContent;
           const label=document.getElementById("colorName").textContent;
           const dot=getComputedStyle(document.documentElement).getPropertyValue("--liturgical");
           samples.push({hour,choice,pressed,title,quick,label,dot});
         }
       }
     }finally{
       brasiliaTodayKey=oldDay;brasiliaClockParts=oldClock;december24Choice=oldChoice;render(previousDate);
     }
     return samples;
   });
   mark(row,'christmas-selections-match-data',christmas.every(x=>
     x.pressed.length===1&&x.pressed[0]===(x.choice||"combined") &&
     (x.choice==="vigil"?x.title.includes("Vigília") && x.label==="Branca" && x.quick.includes("126"):
       x.choice==="morning"?x.title.includes("manhã") && x.label==="Roxa" && x.quick.includes("124"):
       x.title.includes("Féria privilegiada") && x.label.includes("Roxa") && x.quick.includes("124 / 126"))
   ),{samples:christmas});
   const christmasCycle=await page.evaluate(()=>{const d=window.MISSAL_DATA["2026-12-25"];return{label:cycleLabelFor("2026-12-25",d),value:d.cycle};});
   mark(row,'no-false-ferial-cycle-on-christmas',christmasCycle.label==="Ciclo litúrgico" && christmasCycle.value==="—",christmasCycle);
   const copied=await page.evaluate(()=>buildDetailedCopyText());
   mark(row,'copy-includes-detailed-rites',copied.includes('Saudação')&&copied.includes('Ato Penitencial')&&copied.includes('Separação rápida'),{length:copied.length});
   let img;
   try{img=await page.evaluate(async()=>{const b=await buildShareImageBlob();return {size:b?.size,type:b?.type};});}
   catch(e){img={error:String(e)}}
   mark(row,'share-image-png-created',img?.size>15000&&img.type==='image/png',img);
   // As mídias externas não são necessárias para testar a UI do leitor.
   // Evita depender da rede da Arquidiocese durante a auditoria.
   await page.route(/\.pdf(?:[?#]|$)/i,route=>route.abort());
   const expectedLeaflet=await page.evaluate(()=>getDominicalLeafletUrl());
   const leafletLaunch=config.w<=620?'#mobileLeafletBtn':'#desktopLeafletBtn';
   await page.locator(leafletLaunch).click();
   const inlineReader=await page.evaluate(()=>{
     const panel=document.getElementById('leafletReader'),frame=document.getElementById('leafletReaderFrame');
     const original=document.getElementById('leafletReaderExternal');
     const nav=document.querySelector('.mobile-nav'),p=panel.getBoundingClientRect();
     const n=nav.getBoundingClientRect();
     return {open:!panel.hidden,src:frame.getAttribute('src'),original:original.href,
       bodyLocked:getComputedStyle(document.body).position==='fixed',
       navDisplay:getComputedStyle(nav).display,
       navSelected:[...nav.querySelectorAll('button.active')].map(el=>el.id),
       readerBottom:p.bottom,navTop:n.top};
   });
   mark(row,'official-leaflet-opens-inside-site',
     inlineReader.open&&/^https:\/\/.+\.pdf(?:[?#]|$)/i.test(inlineReader.src||'')&&
     inlineReader.src===expectedLeaflet&&inlineReader.original===expectedLeaflet&&
     inlineReader.bodyLocked,inlineReader);
   if(config.w<=620){
     mark(row,'leaflet-tab-persists-below-pdf-viewer',
       inlineReader.navDisplay==='grid'&&
       inlineReader.navSelected.length===1&&inlineReader.navSelected[0]==='mobileLeafletBtn'&&
       inlineReader.readerBottom<=inlineReader.navTop+3,inlineReader);
   }
   await page.locator('#leafletReaderClose').click();
   const closedReader=await page.evaluate(()=>({
     hidden:document.getElementById('leafletReader').hidden,
     src:document.getElementById('leafletReaderFrame').getAttribute('src'),
     unlocked:getComputedStyle(document.body).position!=='fixed',
     active:[...document.querySelectorAll('.mobile-nav button.active')].map(el=>el.id)
   }));
   mark(row,'leaflet-reader-closes-cleans-frame-restores-scroll',
     closedReader.hidden&&closedReader.src===null&&closedReader.unlocked,closedReader);
   if(config.w<=620){
     await page.locator('#mobileLeafletBtn').click();
     await page.locator('#mobileCelebrationBtn').click();
     const switched=await page.evaluate(()=>({
       closed:document.getElementById('leafletReader').hidden,
       celebration:document.body.classList.contains('celebration-mode'),
       active:[...document.querySelectorAll('.mobile-nav button.active')].map(el=>el.id)
     }));
     mark(row,'leaflet-to-celebration-switch-keeps-navigation',
       switched.closed&&switched.celebration&&switched.active.length===1&&
       switched.active[0]==='mobileCelebrationBtn',switched);
     await page.locator('#celebrationModeExit').click();
   }
   if(config.w<=620){
     await page.locator('#mobileMoreBtn').click();
     await page.waitForFunction(()=>{let e=document.querySelector('#mobileMoreSheet');return e?.classList.contains('open')&&e.getBoundingClientRect().bottom<=innerHeight+3;},null,{timeout:4500}).catch(()=>{});
     const sheet=await page.locator('#mobileMoreSheet').boundingBox();
     mark(row,'more-sheet-not-off-screen',!!sheet&&sheet.y>=-2&&sheet.y+sheet.height<=config.h+2,{sheet});
     await page.screenshot({path:path.join(ROOT,config.name+'-more.png'),fullPage:false});
     await page.locator('#mobileMoreClose').click();
     await page.locator('#mobileCelebrationBtn').click();
     mark(row,'celebration-mode-opens',await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
     const exitLayout=await page.evaluate(()=>{
       const a=document.getElementById('celebrationModeExit').getBoundingClientRect();
       const b=document.getElementById('celebrationModeDate').getBoundingClientRect();
       const h=document.querySelector('.celebration-header-row').getBoundingClientRect();
       const overlap=a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom;
       return {exit:{left:a.left,right:a.right,top:a.top,bottom:a.bottom},date:{left:b.left,right:b.right,top:b.top,bottom:b.bottom},
         row:{left:h.left,right:h.right},overlap};
     });
     mark(row,'celebration-exit-balanced-beside-date',!exitLayout.overlap&&
       exitLayout.exit.left>=exitLayout.date.right-2&&
       exitLayout.exit.right<=exitLayout.row.right+2,exitLayout);
     const navState=await page.evaluate(()=>{
       const el=document.querySelector('.mobile-nav'),bounds=el.getBoundingClientRect();
       return {display:getComputedStyle(el).display,visible:bounds.width>0&&bounds.height>0,
         active:[...el.querySelectorAll('button.active')].map(b=>b.id),bottom:bounds.bottom};
     });
     mark(row,'celebration-bottom-tabs-persist-and-highlight',
       navState.display==='grid'&&navState.visible&&navState.active.length===1&&
       navState.active[0]==='mobileCelebrationBtn'&&navState.bottom<=config.h+2,navState);
     await page.locator('#mobileMoreBtn').click();
     // A transição de 260ms não pode ser medida no quadro inicial.
     await page.waitForFunction(()=>{
       const sheet=document.getElementById('mobileMoreSheet');
       const nav=document.querySelector('.mobile-nav');
       return sheet?.classList.contains('open')&&
         sheet.getBoundingClientRect().bottom<=nav.getBoundingClientRect().top+2;
     },null,{timeout:2400}).catch(()=>{});
     const moreState=await page.evaluate(()=>{
       const nav=document.querySelector('.mobile-nav'),sheet=document.getElementById('mobileMoreSheet');
       const a=nav.getBoundingClientRect(),b=sheet.getBoundingClientRect();
       return {active:[...nav.querySelectorAll('button.active')].map(el=>el.id),
         navTop:a.top,navBottom:a.bottom,sheetBottom:b.bottom,
         sheetVisible:sheet.classList.contains('open'),navZ:getComputedStyle(nav).zIndex};
     });
     mark(row,'celebration-more-keeps-tabs-visible-and-active',
       moreState.sheetVisible&&moreState.active.length===1&&moreState.active[0]==='mobileMoreBtn'&&
       moreState.sheetBottom<=moreState.navTop+2,moreState);
     await page.locator('#mobileMoreClose').click();
     mark(row,'celebration-tab-restored-after-more',
       await page.locator('#mobileCelebrationBtn').evaluate(el=>el.classList.contains('active')));
     await page.locator('#mobileMarkingsBtn').click();
     mark(row,'markings-tab-exits-celebration',
       !await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
     await page.locator('#mobileCelebrationBtn').click();
     await page.screenshot({path:path.join(ROOT,config.name+'-celebration.png'),fullPage:false});
     await page.locator('#celebrationModeExit').click();
     mark(row,'celebration-mode-exits',!await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
   } else {
     await page.locator('#celebrationModeBtn').click();
     mark(row,'desktop-celebration-mode-opens',await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
     const exitLayout=await page.evaluate(()=>{
       const a=document.getElementById('celebrationModeExit').getBoundingClientRect();
       const b=document.getElementById('celebrationModeDate').getBoundingClientRect();
       return {exitLeft:a.left,dateRight:b.right,intersects:a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom};
     });
     mark(row,'desktop-celebration-exit-beside-date',
       !exitLayout.intersects&&exitLayout.exitLeft>=exitLayout.dateRight-2,exitLayout);
     await page.screenshot({path:path.join(ROOT,config.name+'-celebration.png'),fullPage:false});
     await page.locator('#celebrationModeExit').click();
   }
   // Navegação nova: apenas páginas visíveis, com salto real à fita.
   const quickButtons=await page.locator('#quickSteps .quick-jump').count();
   const printed=await page.locator('#quickSteps .quick-jump').allTextContents();
   mark(row,'interactive-quick-pages-only',quickButtons===5&&printed.every(t=>!/[Ff]ita|[Mm]arcador/.test(t)),{count:quickButtons,pages:printed});
   if(quickButtons===5){
     await page.locator('#quickSteps .quick-jump').nth(2).click();
     const target=await page.evaluate(()=>({
       highlighted:document.querySelectorAll('#tapes .tape')[2]?.classList.contains('tape-jump-highlight'),
       correctPage:document.querySelectorAll('#tapes .tape')[2]?.querySelector('.page-number')?.textContent.trim()
     }));
     mark(row,'quick-third-page-jumps-to-preface',target.highlighted&&!!target.correctPage,target);
   }
   await page.evaluate(()=>setPrepareMissal(true));
   const prepButtons=await page.locator('#prepareMissalOverlay .quick-jump').count();
   mark(row,'prepare-missal-pages-interactive',prepButtons===5,{count:prepButtons});
   if(prepButtons===5){
     await page.locator('#prepareMissalOverlay .quick-jump').nth(0).click();
     const closed=await page.evaluate(()=>document.getElementById('prepareMissalOverlay').hidden);
     mark(row,'prepare-missal-jump-closes-overlay',closed,{closed});
   }else await page.evaluate(()=>setPrepareMissal(false));
   mark(row,'no-app-javascript-errors',row.errors.length===0,{errors:row.errors});
 }catch(e){mark(row,'test-run-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await ctx.close();await browser.close();}
}
(async()=>{
 for(const c of scenarios)await run(c);
 const pwa={name:'pwa-offline',checks:[]};results.push(pwa);
 const pwaBrowser=await chromium.launch({headless:true});
 const pwaContext=await pwaBrowser.newContext({
   viewport:{width:390,height:844},isMobile:true,hasTouch:true,
   serviceWorkers:'allow',timezoneId:'America/Sao_Paulo',locale:'pt-BR'
 });
 const pwaPage=await pwaContext.newPage();
 try{
   await pwaPage.goto(local,{waitUntil:'domcontentloaded',timeout:30000});
   await pwaPage.waitForFunction(()=>!!navigator.serviceWorker?.controller,{timeout:18000});
   await pwaPage.waitForTimeout(500);
   const initial=await pwaPage.locator('#celebration').textContent();
   mark(pwa,'service-worker-controlling-page',await pwaPage.evaluate(()=>!!navigator.serviceWorker?.controller));
   await pwaContext.setOffline(true);
   const offlineRes=await pwaPage.goto(local+'index.html',{waitUntil:'domcontentloaded',timeout:15000});
   await pwaPage.waitForTimeout(350);
   const offlineTitle=await pwaPage.locator('#celebration').textContent();
   mark(pwa,'pwa-offline-page-and-data',offlineRes.status()===200&&offlineTitle.trim()===initial.trim(),
     {status:offlineRes.status(),initial:initial.trim(),offline:offlineTitle.trim()});
   await pwaPage.screenshot({path:path.join(ROOT,'pwa-offline.png')});
 }catch(e){mark(pwa,'offline-run-completed',false,{error:String(e.message).slice(0,500)})}
 finally{await pwaContext.close();await pwaBrowser.close();}
 // Um primeiro acesso pode perder data.js por conexão instável.
 // O site deve explicar a falha sem fabricar fitas ou lançar erro JS.
 const missing={name:'missing-data-recovery',checks:[]};results.push(missing);
 const missingBrowser=await chromium.launch({headless:true});
 const missingContext=await missingBrowser.newContext({serviceWorkers:'block',timezoneId:'America/Sao_Paulo'});
 const missingPage=await missingContext.newPage();
 const missingErrors=[];
 missingPage.on('pageerror',e=>missingErrors.push(e.message));
 try{
   await missingPage.route(/\/data\.js(?:\?|$)/,route=>route.abort());
   const response=await missingPage.goto(local,{waitUntil:'domcontentloaded',timeout:30000});
   await missingPage.waitForTimeout(400);
   const state=await missingPage.evaluate(()=>({
     ready:document.body.classList.contains('is-ready'),
     note:document.querySelector('#note')?.textContent||'',
     tapes:document.querySelectorAll('#tapes .tape').length,
     selected:window.currentDateKey
   }));
   mark(missing,'data-script-failure-does-not-crash',response?.status()===200&&state.ready&&missingErrors.length===0,
     {state,errors:missingErrors});
   mark(missing,'no-fabricated-missal-pages',state.tapes===0&&/Não foi possível carregar/.test(state.note),state);
 }catch(e){mark(missing,'data-script-failure-test-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await missingContext.close();await missingBrowser.close();}

 const check={name:'public-deployment',checks:[]};results.push(check);
 const browser=await chromium.launch();
 const ctx=await browser.newContext({timezoneId:'America/Sao_Paulo',serviceWorkers:'block'});
 const page=await ctx.newPage();
 try{
   const res=await page.goto(publicUrl,{waitUntil:'domcontentloaded',timeout:40000});
   mark(check,'live-status-200',res?.status()===200,{status:res?.status(),url:page.url()});
   await page.waitForTimeout(400);
   const live=await page.evaluate(()=>({
      title:document.title,date:window.currentDateKey,status:window.MISSAL_STATUS?.availableThrough,token:document.querySelector('script[src^="data.js"]')?.getAttribute('src'),ready:!!window.MISSAL_DATA
   }));
   mark(check,'live-data-and-status',live.ready&&/\d{4}-\d{2}-\d{2}/.test(live.status)&&/\d{4}-\d{2}-\d{2}/.test(live.date),live);

   const pdf=await page.evaluate(()=>getDominicalLeafletUrl());
   mark(check,'folheto-opens-direct-pdf',/^https:\/\/[^?#]+\.pdf(?:[?#]|$)/i.test(pdf),{url:pdf});
   try{
     const response=await ctx.request.head(pdf,{timeout:20000,failOnStatusCode:false});
     console.log('INFO PDF_HTTPS '+JSON.stringify({status:response.status(),type:response.headers()['content-type'],url:response.url()}));
     check.pdfHttp={status:response.status(),contentType:response.headers()['content-type']||null};
   }catch(e){check.pdfHttp={error:String(e).slice(0,250)};console.log('INFO PDF_HTTPS '+JSON.stringify(check.pdfHttp));}
   const standalone=await ctx.request.get(publicUrl+'Missal-Diario-Standalone.html',{timeout:20000,failOnStatusCode:false});
   const standaloneText=standalone.ok()?await standalone.text():'';
   mark(check,'standalone-published-and-self-contained',standalone.ok()&&standaloneText.includes('window.MISSAL_DATA =')&&standaloneText.includes('window.MISSAL_STATUS =')&& !/<script src="(?:data|status)\.js/i.test(standaloneText),{status:standalone.status(),bytes:standaloneText.length});

 }catch(e){mark(check,'public-test-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await ctx.close();await browser.close();}
 const summary={when:new Date().toISOString(),results,failures};
 fs.writeFileSync(path.join(ROOT,'relatorio-auditoria-completa.json'),JSON.stringify(summary,null,2));
 console.log('AUDITORIA_FIM '+JSON.stringify({scenarios:results.length,total:results.reduce((n,r)=>n+r.checks.length,0),failures:failures.length,failedTests:failures}));
 process.exitCode=failures.length?1:0;
})();