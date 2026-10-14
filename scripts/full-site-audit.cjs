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
   mark(row,'valid-day',metrics.selected==='2026-10-14',{selected:metrics.selected,available:metrics.available});
   mark(row,'buttons-text-not-clipped',metrics.overflow.length===0,{overflow:metrics.overflow.slice(0,8)});
   await page.screenshot({path:path.join(ROOT,config.name+'-start.png'),fullPage:false});
   await page.locator('#datePickerBtn').click();
   const calendar=await page.evaluate(()=>{
     const el=document.querySelector('#dateMenu'),r=el.getBoundingClientRect();
     return {open:!el.hidden,x:r.x,right:r.right,top:r.top,bottom:r.bottom,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,winWidth:innerWidth,winHeight:innerHeight};
   });
   mark(row,'calendar-visible-within-screen',calendar.open && calendar.x>=-2 && calendar.right<=config.w+2 && calendar.top>=-3 && calendar.bottom<=config.h+3,calendar);
   await page.screenshot({path:path.join(ROOT,config.name+'-calendar.png'),fullPage:false});
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
   await page.evaluate(()=>{const dates=getVisibleDates();render(dates[dates.length-1]);});
   const visibility=await page.evaluate(()=>{
     const d=getVisibleDates(),last=d[d.length-1],all=getRegisteredDates();
     return {today:brasiliaTodayKey(),last,total:d.length,all:all.length,next:document.getElementById('nextBtn').disabled};
   });
   mark(row,'future-dates-locked',visibility.last==='2026-10-14'&&visibility.next,{last:visibility.last,count:visibility.total});
   // test date release rules with simulated source status, leaving external data untouched.
   const gate=await page.evaluate(()=>{
     const realDay=brasiliaTodayKey,realClock=brasiliaClockParts,realStatus=window.MISSAL_STATUS;
     const statuses={};function test(date,hour,available,preview){brasiliaTodayKey=()=>date;brasiliaClockParts=()=>({hour:String(hour)});window.MISSAL_STATUS={availableThrough:available,sundayPreview:preview};return {visible:getVisibleDates().slice(-2),preview:getSundayPreview(),limit:getAvailableThrough()};}
     try {
       statuses.satBefore=test('2026-10-10',4,'2026-10-10','2026-10-11');
       statuses.satAfter=test('2026-10-10',5,'2026-10-10','2026-10-11');
       statuses.sunBefore=test('2026-10-11',4,'2026-10-10','2026-10-11');
       statuses.sunAfter=test('2026-10-11',5,'2026-10-11',undefined);
     }finally{brasiliaTodayKey=realDay;brasiliaClockParts=realClock;window.MISSAL_STATUS=realStatus;}return statuses;
   });
   mark(row,'saturday-release-rule',gate.satBefore.preview===null && gate.satAfter.preview==='2026-10-11' && gate.satBefore.limit==='2026-10-09',gate);
   mark(row,'sunday-midnight-preview-rule',gate.sunBefore.preview==='2026-10-11'&&gate.sunAfter.limit==='2026-10-11',gate);
   const copied=await page.evaluate(()=>buildDetailedCopyText());
   mark(row,'copy-includes-detailed-rites',copied.includes('Saudação')&&copied.includes('Ato Penitencial')&&copied.includes('Separação rápida'),{length:copied.length});
   let img;
   try{img=await page.evaluate(async()=>{const b=await buildShareImageBlob();return {size:b?.size,type:b?.type};});}
   catch(e){img={error:String(e)}}
   mark(row,'share-image-png-created',img?.size>15000&&img.type==='image/png',img);
   if(config.mobile){
     await page.locator('#mobileMoreBtn').click();
     await page.waitForFunction(()=>{let e=document.querySelector('#mobileMoreSheet');return e?.classList.contains('open')&&e.getBoundingClientRect().bottom<=innerHeight+3;},null,{timeout:4500}).catch(()=>{});
     const sheet=await page.locator('#mobileMoreSheet').boundingBox();
     mark(row,'more-sheet-not-off-screen',!!sheet&&sheet.y>=-2&&sheet.y+sheet.height<=config.h+2,{sheet});
     await page.screenshot({path:path.join(ROOT,config.name+'-more.png'),fullPage:false});
     await page.locator('#mobileMoreClose').click();
     await page.locator('#mobileCelebrationBtn').click();
     mark(row,'celebration-mode-opens',await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
     await page.screenshot({path:path.join(ROOT,config.name+'-celebration.png'),fullPage:false});
     await page.locator('#celebrationModeExit').click();
     mark(row,'celebration-mode-exits',!await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
   } else {
     await page.locator('#celebrationModeBtn').click();
     mark(row,'desktop-celebration-mode-opens',await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
     await page.screenshot({path:path.join(ROOT,config.name+'-celebration.png'),fullPage:false});
     await page.locator('#celebrationModeExit').click();
   }
   mark(row,'no-app-javascript-errors',row.errors.length===0,{errors:row.errors});
 }catch(e){mark(row,'test-run-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await ctx.close();await browser.close();}
}
(async()=>{
 for(const c of scenarios)await run(c);
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
   mark(check,'live-data-and-status',live.ready&&live.status==='2026-10-14'&&live.date==='2026-10-14',live);
 }catch(e){mark(check,'public-test-completed',false,{error:String(e.message).slice(0,500)});}
 finally{await ctx.close();await browser.close();}
 const summary={when:new Date().toISOString(),results,failures};
 fs.writeFileSync(path.join(ROOT,'relatorio-auditoria-completa.json'),JSON.stringify(summary,null,2));
 console.log('AUDITORIA_FIM '+JSON.stringify({scenarios:results.length,total:results.reduce((n,r)=>n+r.checks.length,0),failures:failures.length,failedTests:failures}));
 process.exitCode=failures.length?1:0;
})();