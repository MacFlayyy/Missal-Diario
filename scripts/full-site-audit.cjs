/* Auditoria integral do Missal Diário (design v3: cabeçalho com semana, páginas no topo,
   modo Celebração como aba e barra de vidro). Não altera os dados do site. */
const {chromium, webkit}=require('playwright');
const fs=require('fs');
const path=require('path');
const ROOT=path.join(process.cwd(),'full-audit-results');fs.mkdirSync(ROOT,{recursive:true});
const local='http://127.0.0.1:8765/';
const publicUrl='https://macflayyy.github.io/Missal-Diario/';
const onlyChromium=process.env.AUDIT_CHROMIUM_ONLY==='1';
const skipPublic=process.env.AUDIT_SKIP_PUBLIC==='1';
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
const engineFor=c=>(c.engine==='webkit'&&!onlyChromium)?webkit:chromium;
async function run(config){
 const row={name:config.name,checks:[],errors:[],warnings:[]};results.push(row);
 const wide=config.w>=900;
 const browser=await engineFor(config).launch({headless:true});
 const ctx=await browser.newContext({viewport:{width:config.w,height:config.h},isMobile:config.mobile,hasTouch:config.mobile,
 deviceScaleFactor:2,timezoneId:'America/Sao_Paulo',locale:'pt-BR',serviceWorkers:'block',acceptDownloads:true,reducedMotion:'reduce',
 ...(config.engine==='webkit'?{userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'}:{})});
 const page=await ctx.newPage();
 page.on('pageerror',e=>{if(!/cloudflareinsights\.com|\/cdn-cgi\/rum/i.test(e.message))row.errors.push(e.message)});
 const sheetOpen=id=>page.waitForFunction(i=>{const e=document.getElementById(i);return e?.classList.contains('open')&&e.getBoundingClientRect().bottom<=innerHeight+3;},id,{timeout:4500}).catch(()=>{});
 const openMore=async()=>{await page.locator(wide?'[data-v3-act="more"]:visible':'.v3-gt[data-v3-tab="more"]').first().click();await sheetOpen('v3MoreSheet');};
 try{
   const r=await page.goto(local,{waitUntil:'domcontentloaded',timeout:30000});
   mark(row,'http-load',r?.status()===200,{code:r?.status()});
   await page.waitForTimeout(450);
   const metrics=await page.evaluate(()=>{
     const overflow=[];
     document.querySelectorAll('#v3 button').forEach(el=>{if(!el.getClientRects().length)return;const t=(el.textContent||'').trim();if(t&&el.scrollWidth>el.clientWidth+4)overflow.push({id:el.id||el.className,text:t.slice(0,45),w:el.clientWidth,scroll:el.scrollWidth})});
     const glass=document.getElementById('v3Glass'),g=glass.getBoundingClientRect();
     const week=[...document.querySelectorAll('#v3Week button')];
     const visible=new Set(getVisibleDates());
     return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,
       v3:document.body.classList.contains('v3'),oldHidden:getComputedStyle(document.querySelector('.shell')).display==='none',
       quick:document.querySelectorAll('#v3Quick button').length,rows:document.querySelectorAll('#v3List .v3-r').length,
       pages:[...document.querySelectorAll('#v3Quick b')].map(e=>e.textContent.trim()),
       dataPages:(getDisplayEntry(window.currentDateKey)?.tapes||[]).map(t=>String(t.page)),
       title:document.getElementById('v3Title').textContent.trim(),celebration:getDisplayEntry(window.currentDateKey)?.celebration,
       overflow,selected:window.currentDateKey,available:window.MISSAL_STATUS?.availableThrough,
       glass:{display:getComputedStyle(glass).display,top:g.top,bottom:g.bottom,left:g.left,right:g.right,
         tabs:glass.querySelectorAll('.v3-gt').length,active:[...glass.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab)},
       deskButtons:getComputedStyle(document.querySelector('.v3-hb')).display,
       week:{count:week.length,pressed:week.filter(b=>b.getAttribute('aria-pressed')==='true').map(b=>b.dataset.date),
         wrongLock:week.filter(b=>b.disabled===visible.has(b.dataset.date)).map(b=>b.dataset.date)},
       ribbon:getComputedStyle(document.getElementById('v3Rib')).backgroundColor+getComputedStyle(document.getElementById('v3Rib')).backgroundImage,
       contacts:[...document.querySelectorAll('.v3-cred a')].map(a=>a.getAttribute('href')),
       prepareVisible:[...document.querySelectorAll('[data-action="prepare"],#prepareMissalBtn')].some(e=>e.getClientRects().length>0)};
   });
   row.metrics=metrics;
   mark(row,'new-design-active-old-layout-hidden',metrics.v3&&metrics.oldHidden,{v3:metrics.v3,oldHidden:metrics.oldHidden});
   mark(row,'no-horizontal-page-overflow',metrics.documentWidth<=config.w+1,{doc:metrics.documentWidth,viewport:config.w});
   mark(row,'five-quick-pages',metrics.quick===5,{count:metrics.quick});
   mark(row,'five-summary-rows',metrics.rows===5,{count:metrics.rows});
   mark(row,'quick-pages-match-data',metrics.pages.length===metrics.dataPages.length&&metrics.pages.every((p,i)=>p===metrics.dataPages[i]),{pages:metrics.pages,data:metrics.dataPages});
   mark(row,'title-matches-data',!!metrics.title&&metrics.title===metrics.celebration,{title:metrics.title});
   mark(row,'valid-day',metrics.selected===await page.evaluate(() => getVisibleDates().includes(brasiliaTodayKey()) ? brasiliaTodayKey() : getVisibleDates().at(-1)),{selected:metrics.selected,available:metrics.available});
   mark(row,'buttons-text-not-clipped',metrics.overflow.length===0,{overflow:metrics.overflow.slice(0,8)});
   mark(row,'week-strip-marks-selected-day-and-locks-future',metrics.week.count===7&&metrics.week.pressed.length===1&&metrics.week.pressed[0]===metrics.selected&&metrics.week.wrongLock.length===0,metrics.week);
   mark(row,'liturgical-ribbon-painted',/rgb|gradient/.test(metrics.ribbon),{ribbon:metrics.ribbon.slice(0,90)});
   mark(row,'creator-contacts-present',metrics.contacts.includes('mailto:macflay.contact@gmail.com')&&metrics.contacts.some(h=>/instagram\.com\/macflayyy/.test(h)),{contacts:metrics.contacts});
   mark(row,'prepare-missal-removed',!metrics.prepareVisible,{visible:metrics.prepareVisible});
   if(wide) mark(row,'desktop-panel-buttons-instead-of-bar',metrics.glass.display==='none'&&metrics.deskButtons!=='none',{glass:metrics.glass.display,panel:metrics.deskButtons});
   else mark(row,'glass-bar-visible-with-home-active',metrics.glass.display!=='none'&&metrics.glass.tabs===5&&metrics.glass.active.length===1&&metrics.glass.active[0]==='home'&&
     metrics.glass.left>=-1&&metrics.glass.right<=config.w+1&&metrics.glass.bottom<=config.h+1,metrics.glass);
   await page.screenshot({path:path.join(ROOT,config.name+'-start.png'),fullPage:false});

   /* ---- calendário ---- */
   await page.locator('#v3MonthBtn').click();await sheetOpen('v3CalSheet');
   const calendar=await page.evaluate(()=>{const el=document.getElementById('v3CalSheet'),r=el.getBoundingClientRect();
     return {open:el.classList.contains('open'),x:r.x,right:r.right,top:r.top,bottom:r.bottom,winWidth:innerWidth,winHeight:innerHeight,
       dots:el.querySelectorAll('#v3CalGrid button i').length,days:el.querySelectorAll('#v3CalGrid button').length};});
   mark(row,'calendar-visible-within-screen',calendar.open&&calendar.x>=-2&&calendar.right<=config.w+2&&calendar.top>=-3&&calendar.bottom<=config.h+3,calendar);
   mark(row,'calendar-days-carry-liturgical-dot',calendar.days>0&&calendar.dots===calendar.days,{days:calendar.days,dots:calendar.dots});
   const scrollLock=await page.evaluate(()=>({bodyPosition:getComputedStyle(document.body).position,rootOverflow:document.documentElement.style.overflow,scrollY:window.scrollY}));
   if(!(config.mobile&&config.engine==='webkit')){await page.mouse.wheel(0,410);await page.waitForTimeout(70);}
   const scrollAfterWheel=await page.evaluate(()=>window.scrollY);
   mark(row,'calendar-locks-background-scroll',scrollLock.bodyPosition==='fixed'&&scrollLock.rootOverflow==='hidden'&&scrollAfterWheel===scrollLock.scrollY,{...scrollLock,scrollAfterWheel});
   if(!wide) mark(row,'calendar-tab-highlighted-while-open',await page.evaluate(()=>[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join()==='cal'));
   await page.screenshot({path:path.join(ROOT,config.name+'-calendar.png'),fullPage:false});
   const narrower=config.w===1024?900:Math.max(280,config.w-20);
   await page.setViewportSize({width:narrower,height:config.h});
   mark(row,'calendar-resize-keeps-dialog-open',await page.evaluate(()=>document.getElementById('v3CalSheet').classList.contains('open')),{before:config.w,after:narrower});
   await page.setViewportSize({width:config.w,height:config.h});
   const prev=page.locator('#v3CalPrev');
   if(await prev.isEnabled()){
     const title=await page.locator('#v3CalTitle').innerText();
     await prev.click();
     mark(row,'calendar-month-change-does-not-close',await page.evaluate(()=>document.getElementById('v3CalSheet').classList.contains('open'))&&(await page.locator('#v3CalTitle').innerText())!==title);
   }
   const day=page.locator('#v3CalGrid button[data-date]').first();
   if(await day.count()){
     const selected=await day.getAttribute('data-date');
     await day.click();
     // a data é aplicada no quadro seguinte, depois que a folha começou a fechar
     await page.waitForFunction(k=>window.currentDateKey===k,selected,{timeout:3000}).catch(()=>{});
     mark(row,'calendar-select-historic-date',await page.evaluate(k=>window.currentDateKey===k&&!document.getElementById('v3CalSheet').classList.contains('open')&&
       document.getElementById('v3Title').textContent.trim()===getDisplayEntry(k).celebration,selected),{selected});
   }else await page.keyboard.press('Escape');
   const scrollUnlocked=await page.evaluate(()=>({bodyPosition:getComputedStyle(document.body).position,rootOverflow:document.documentElement.style.overflow}));
   mark(row,'calendar-restores-background-scroll',scrollUnlocked.bodyPosition!=='fixed'&&scrollUnlocked.rootOverflow!=='hidden',scrollUnlocked);
   await page.evaluate(()=>{const dates=getVisibleDates();render(dates[dates.length-1]);});
   const visibility=await page.evaluate(()=>{const d=getVisibleDates(),last=d[d.length-1];
     return {today:brasiliaTodayKey(),last,total:d.length,
       futureEnabled:[...document.querySelectorAll('#v3Week button')].filter(b=>b.dataset.date>last&&!b.disabled).length};});
   mark(row,'future-dates-locked',visibility.futureEnabled===0&&visibility.last<=new Date(Date.parse(visibility.today+'T00:00:00Z')+86400000).toISOString().slice(0,10),visibility);

   /* ---- regras de liberação (05h, sábado/domingo), com status simulado ---- */
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
   const satNote=await page.evaluate(()=>{
     const realDay=brasiliaTodayKey,realClock=brasiliaClockParts,realStatus=window.MISSAL_STATUS,previous=window.currentDateKey;
     try{brasiliaTodayKey=()=>'2026-10-10';brasiliaClockParts=()=>({hour:'9'});window.MISSAL_STATUS={availableThrough:'2026-10-10',sundayPreview:'2026-10-11'};
       render('2026-10-10');
       const shown=!document.getElementById('v3SundayNote').hidden;
       const sundayEnabled=!document.querySelector('#v3Week button[data-date="2026-10-11"]').disabled;
       document.getElementById('v3SundayBtn').click();
       return {shown,sundayEnabled,moved:window.currentDateKey==='2026-10-11',hiddenAfter:document.getElementById('v3SundayNote').hidden};
     }finally{brasiliaTodayKey=realDay;brasiliaClockParts=realClock;window.MISSAL_STATUS=realStatus;render(previous);}
   });
   mark(row,'saturday-shows-sunday-shortcut',satNote.shown&&satNote.sundayEnabled&&satNote.moved&&satNote.hiddenAfter,satNote);

   /* ---- 24/12: a Vigília NUNCA é escolhida pelo relógio ---- */
   const christmas=await page.evaluate(()=>{
     const previousDate=window.currentDateKey,oldDay=brasiliaTodayKey,oldClock=brasiliaClockParts,oldChoice=december24Choice;
     const samples=[];
     try{
       brasiliaTodayKey=()=> "2026-12-24";
       for(const hour of [10,13,21]){
         brasiliaClockParts=()=>({hour:String(hour)});
         for(const choice of [null,"morning","vigil"]){
           december24Choice=choice;render("2026-12-24");
           const pressed=[...document.querySelectorAll('#v3Dec24 button[aria-pressed="true"]')].map(el=>el.dataset.dec24Mass);
           samples.push({hour,choice,pressed,shown:!document.getElementById('v3Dec24').hidden,
             title:document.getElementById("v3Title").textContent,
             quick:[...document.querySelectorAll('#v3Quick b')].map(e=>e.textContent).join(" → "),
             label:document.getElementById("v3Chip").textContent});
         }
       }
     }finally{brasiliaTodayKey=oldDay;brasiliaClockParts=oldClock;december24Choice=oldChoice;render(previousDate);}
     return samples;
   });
   mark(row,'christmas-selections-match-data',christmas.every(x=>
     x.shown&&x.pressed.length===1&&x.pressed[0]===(x.choice||"combined") &&
     (x.choice==="vigil"?x.title.includes("Vigília") && x.label.startsWith("Branca") && x.quick.includes("126"):
       x.choice==="morning"?x.title.includes("manhã") && x.label.startsWith("Roxa ·") && x.quick.includes("124"):
       x.title.includes("Féria privilegiada") && x.label.includes("Roxa") && x.quick.includes("124 / 126"))
   ),{samples:christmas});
   mark(row,'christmas-choice-hidden-on-other-days',await page.evaluate(()=>document.getElementById('v3Dec24').hidden));
   const christmasCycle=await page.evaluate(()=>{const d=window.MISSAL_DATA["2026-12-25"];return{label:cycleLabelFor("2026-12-25",d),value:d.cycle};});
   mark(row,'no-false-ferial-cycle-on-christmas',christmasCycle.label==="Ciclo litúrgico" && christmasCycle.value==="—",christmasCycle);

   /* ---- cópia e imagem ---- */
   const copied=await page.evaluate(()=>buildDetailedCopyText());
   mark(row,'copy-includes-detailed-rites',copied.includes('Saudação')&&copied.includes('Ato Penitencial')&&copied.includes('Separação rápida'),{length:copied.length});
   let img;
   try{img=await page.evaluate(async()=>{const b=await buildShareImageBlob();const bmp=await createImageBitmap(b);return {size:b?.size,type:b?.type,w:bmp.width,h:bmp.height};});}
   catch(e){img={error:String(e)}}
   mark(row,'share-image-png-created',img?.size>15000&&img.type==='image/png'&&img.w===1080&&img.h>900,img);

   /* ---- folheto ---- */
   await page.route(/\.pdf(?:[?#]|$)/i,route=>route.abort());
   const expectedLeaflet=await page.evaluate(()=>getDominicalLeafletUrl());
   if(!expectedLeaflet){
     mark(row,'leaflet-unavailable-is-explained',/ainda não está disponível/.test(await page.evaluate(()=>openDominicalLeaflet.toString())),{url:expectedLeaflet});
   }else if(config.w>700){
     await page.locator(wide?'[data-v3-act="leaflet"]:visible':'.v3-gt[data-v3-tab="leaflet"]').first().click();
     const inlineReader=await page.evaluate(()=>{
       const panel=document.getElementById('leafletReader'),frame=document.getElementById('leafletReaderFrame'),original=document.getElementById('leafletReaderExternal');
       return {open:!panel.hidden,official:frame.getAttribute('data-official-pdf'),original:original.href,
         responsivePages:typeof renderLeafletPages==='function'&&!!document.getElementById('leafletCanvasPages'),
         bodyLocked:getComputedStyle(document.body).position==='fixed',
         tab:[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join()};
     });
     mark(row,'official-leaflet-opens-inside-site',inlineReader.open&&/^https:\/\/.+\.pdf(?:[?#]|$)/i.test(inlineReader.official||'')&&
       inlineReader.official===expectedLeaflet&&inlineReader.original===expectedLeaflet&&inlineReader.responsivePages&&inlineReader.bodyLocked&&
       (wide||inlineReader.tab==='leaflet'),inlineReader);
     await page.locator('#leafletReaderClose').click();
     const closedReader=await page.evaluate(()=>({hidden:document.getElementById('leafletReader').hidden,
       src:document.getElementById('leafletReaderFrame').getAttribute('src'),unlocked:getComputedStyle(document.body).position!=='fixed',
       tab:[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join()}));
     mark(row,'leaflet-reader-closes-cleans-frame-restores-scroll',closedReader.hidden&&closedReader.src===null&&closedReader.unlocked&&closedReader.tab==='home',closedReader);
   }else{
     const mobileLeaflet=await page.evaluate(()=>({url:getDominicalLeafletUrl(),
       originalDirect:/link\.target="_blank"/.test(openDominicalLeaflet.toString()),
       noThirdPartyPreview:!leafletFallbackFrame.toString().includes('docs.google.com')}));
     mark(row,'mobile-official-leaflet-direct-link',mobileLeaflet.url===expectedLeaflet&&mobileLeaflet.originalDirect&&mobileLeaflet.noThirdPartyPreview,mobileLeaflet);
   }

   /* ---- Mais opções e tema ---- */
   await openMore();
   const sheet=await page.locator('#v3MoreSheet').boundingBox();
   mark(row,'more-sheet-not-off-screen',!!sheet&&sheet.y>=-2&&sheet.y+sheet.height<=config.h+2&&sheet.x>=-2&&sheet.x+sheet.width<=config.w+2,{sheet});
   if(!wide) mark(row,'more-tab-highlighted-while-open',await page.evaluate(()=>[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join()==='more'));
   await page.screenshot({path:path.join(ROOT,config.name+'-more.png'),fullPage:false});
   await page.locator('#v3MoreSheet [data-theme-choice="auto"]').focus();
   await page.keyboard.press('Tab');
   mark(row,'more-sheet-focus-does-not-escape',await page.evaluate(()=>document.getElementById('v3MoreSheet').contains(document.activeElement)));
   await page.locator('#v3MoreSheet [data-theme-choice="escuro"]').click();
   await page.waitForTimeout(700);
   const dark=await page.evaluate(()=>({dark:document.documentElement.classList.contains('theme-dark'),
     pressed:document.querySelector('#v3MoreSheet [data-theme-choice="escuro"]').getAttribute('aria-pressed'),
     num:getComputedStyle(document.querySelector('#v3Quick b')).color,bg:getComputedStyle(document.body).backgroundColor,
     hero:getComputedStyle(document.getElementById('v3Hero')).backgroundImage.slice(0,40)}));
   mark(row,'dark-theme-white-numbers-wine-header',dark.dark&&dark.pressed==='true'&&dark.num==='rgb(255, 255, 255)'&&dark.bg==='rgb(0, 0, 0)'&&/gradient/.test(dark.hero),dark);
   await page.screenshot({path:path.join(ROOT,config.name+'-dark.png'),fullPage:false});
   await page.locator('#v3MoreSheet [data-theme-choice="claro"]').click();
   await page.waitForTimeout(700);
   mark(row,'light-theme-is-restored',await page.evaluate(()=>!document.documentElement.classList.contains('theme-dark')&&getComputedStyle(document.querySelector('#v3Quick b')).color==='rgb(122, 24, 36)'));
   await page.keyboard.press('Escape');
   mark(row,'more-sheet-escape-closes-and-restores',await page.evaluate(()=>!document.getElementById('v3MoreSheet').classList.contains('open')&&
     getComputedStyle(document.body).position!=='fixed'&&[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join()==='home'));

   /* ---- modo Celebração ---- */
   await page.locator(wide?'#v3DeskCel':'.v3-gt[data-v3-tab="cel"]').click();
   await page.waitForTimeout(120);
   const cel=await page.evaluate(()=>{const d=getDisplayEntry(window.currentDateKey);
     const cards=[...document.querySelectorAll('#v3Cards .v3-f')];
     return {mode:document.body.classList.contains('v3-cel'),homeHidden:document.getElementById('v3Home').hidden,celHidden:document.getElementById('v3Cel').hidden,
       cards:cards.length,details:cards.map(c=>c.querySelectorAll('.v3-d').length),expected:d.tapes.map(t=>t.details.length),
       pages:cards.map(c=>c.querySelector('.v3-num').lastChild.textContent.trim()),dataPages:d.tapes.map(t=>String(t.page)),
       tab:[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join(),
       note:!document.getElementById('v3NoteCel').hidden,doc:document.documentElement.scrollWidth};});
   mark(row,'celebration-mode-shows-every-detail',cel.mode&&cel.homeHidden&&!cel.celHidden&&cel.cards===5&&
     cel.details.every((n,i)=>n===cel.expected[i])&&cel.pages.every((p,i)=>p===cel.dataPages[i])&&cel.tab==='cel'&&cel.doc<=config.w+1,cel);
   await page.screenshot({path:path.join(ROOT,config.name+'-celebration.png'),fullPage:false});
   if(!wide){
     await openMore();await page.keyboard.press('Escape');
     mark(row,'celebration-tab-restored-after-more',await page.evaluate(()=>[...document.querySelectorAll('.v3-gt.on')].map(b=>b.dataset.v3Tab).join()==='cel'));
   }
   await page.locator(wide?'#v3DeskCel':'.v3-gt[data-v3-tab="home"]').click();
   mark(row,'celebration-mode-exits',await page.evaluate(()=>!document.body.classList.contains('v3-cel')&&!document.getElementById('v3Home').hidden&&document.getElementById('v3Cel').hidden));
   await page.locator('#v3Quick button[data-tape="3"]').click();
   await page.waitForTimeout(450);
   const jump=await page.evaluate(()=>{const c=document.getElementById('v3-tape-3').getBoundingClientRect();
     return {mode:document.body.classList.contains('v3-cel'),top:c.top,bottom:c.bottom,h:innerHeight};});
   mark(row,'quick-third-page-opens-preface-in-celebration',jump.mode&&jump.top>=-4&&jump.top<jump.h*0.75,jump);
   await page.locator(wide?'#v3DeskCel':'.v3-gt[data-v3-tab="home"]').click();
   await page.locator('#v3List .v3-r[data-tape="5"]').click();
   await page.waitForTimeout(450);
   mark(row,'summary-row-opens-its-tape',await page.evaluate(()=>document.body.classList.contains('v3-cel')&&document.getElementById('v3-tape-5').getBoundingClientRect().top<innerHeight));
   await page.locator(wide?'#v3DeskCel':'.v3-gt[data-v3-tab="home"]').click();
   const origins=await page.evaluate(()=>{
     const out=[];for(const k of Object.keys(window.MISSAL_DATA)){render(k);const d=getDisplayEntry(k);const t=d.tapes.find(x=>x.n===2);if(!t)continue;
       const label=document.querySelector('#v3List .v3-r[data-tape="2"] em')?.textContent||'';
       const want=t.verifiedByFolheto?'Conferido no folheto':t.suggestion?'Sugestão':(d.grade==='Dia de semana'&&/Tempo Comum/.test(d.season))?'Missa do domingo da semana':'Própria do dia';
       if(label!==want)out.push({k,label,want});}
     const dates=getVisibleDates();render(dates[dates.length-1]);return out;});
   mark(row,'mass-of-the-day-origin-labels',origins.length===0,{wrong:origins.slice(0,5)});
   mark(row,'no-app-javascript-errors',row.errors.length===0,{errors:row.errors});
 }catch(e){mark(row,'test-run-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await ctx.close();await browser.close();}
}
(async()=>{
 for(const c of scenarios)await run(c);
 const pwa={name:'pwa-offline',checks:[]};results.push(pwa);
 const pwaBrowser=await chromium.launch({headless:true});
 const pwaContext=await pwaBrowser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,serviceWorkers:'allow',timezoneId:'America/Sao_Paulo',locale:'pt-BR'});
 const pwaPage=await pwaContext.newPage();
 try{
   await pwaPage.goto(local,{waitUntil:'domcontentloaded',timeout:30000});
   await pwaPage.waitForFunction(()=>!!navigator.serviceWorker?.controller,{timeout:18000});
   await pwaPage.waitForTimeout(500);
   const initial=await pwaPage.locator('#v3Title').textContent();
   mark(pwa,'service-worker-controlling-page',await pwaPage.evaluate(()=>!!navigator.serviceWorker?.controller));
   await pwaContext.setOffline(true);
   const offlineRes=await pwaPage.goto(local+'index.html',{waitUntil:'domcontentloaded',timeout:15000});
   await pwaPage.waitForTimeout(350);
   const offlineTitle=await pwaPage.locator('#v3Title').textContent();
   const offlinePages=await pwaPage.locator('#v3Quick button').count();
   mark(pwa,'pwa-offline-page-and-data',offlineRes.status()===200&&offlineTitle.trim()===initial.trim()&&offlinePages===5,
     {status:offlineRes.status(),initial:initial.trim(),offline:offlineTitle.trim(),pages:offlinePages});
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
     note:document.querySelector('#v3Quick .v3-empty')?.textContent||'',
     pages:document.querySelectorAll('#v3Quick button').length,rows:document.querySelectorAll('#v3List .v3-r').length,
     cards:document.querySelectorAll('#v3Cards .v3-f').length,selected:window.currentDateKey}));
   mark(missing,'data-script-failure-does-not-crash',response?.status()===200&&state.ready&&missingErrors.length===0,{state,errors:missingErrors});
   mark(missing,'no-fabricated-missal-pages',state.pages===0&&state.rows===0&&state.cards===0&&/Não foi possível carregar/.test(state.note),state);
 }catch(e){mark(missing,'data-script-failure-test-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await missingContext.close();await missingBrowser.close();}

 if(!skipPublic){
 const check={name:'public-deployment',checks:[]};results.push(check);
 const browser=await chromium.launch();
 const ctx=await browser.newContext({timezoneId:'America/Sao_Paulo',serviceWorkers:'block'});
 const page=await ctx.newPage();
 try{
   const res=await page.goto(publicUrl,{waitUntil:'domcontentloaded',timeout:40000});
   mark(check,'live-status-200',res?.status()===200,{status:res?.status(),url:page.url()});
   await page.waitForTimeout(400);
   const live=await page.evaluate(()=>({title:document.title,date:window.currentDateKey,status:window.MISSAL_STATUS?.availableThrough,token:document.querySelector('script[src^="data.js"]')?.getAttribute('src'),ready:!!window.MISSAL_DATA}));
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
   mark(check,'standalone-published-and-self-contained',standalone.ok()&&standaloneText.includes('window.MISSAL_DATA =')&&standaloneText.includes('window.MISSAL_STATUS =')&& !/<script src="(?:data|status)\.js/i.test(standaloneText),{status:standalone.status(),size:standaloneText.length});
 }catch(e){mark(check,'public-test-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await ctx.close();await browser.close();}
 }
 const summary={when:new Date().toISOString(),results,failures};
 fs.writeFileSync(path.join(ROOT,'relatorio-auditoria-completa.json'),JSON.stringify(summary,null,2));
 console.log('AUDITORIA_FIM '+JSON.stringify({scenarios:results.length,total:results.reduce((n,r)=>n+r.checks.length,0),failures:failures.length,failedTests:failures}));
 process.exitCode=failures.length?1:0;
})();
