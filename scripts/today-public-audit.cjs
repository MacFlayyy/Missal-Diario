const {chromium,webkit}=require('playwright');
const fs=require('fs');const path=require('path');
const ROOT=path.join(process.cwd(),'today-audit-results');fs.mkdirSync(ROOT,{recursive:true});
const origin='https://macflayyy.github.io/Missal-Diario/';
const brDate=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{
 timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'
}).formatToParts(new Date()).map(part=>[part.type,part.value]));
const today=`${brDate.year}-${brDate.month}-${brDate.day}`;
const configs=[
 {name:'android-small',engine:'chromium',width:320,height:700,mobile:true},
 {name:'android-regular',engine:'chromium',width:360,height:800,mobile:true},
 {name:'iphone-small',engine:'webkit',width:375,height:667,mobile:true},
 {name:'iphone',engine:'webkit',width:390,height:844,mobile:true},
 {name:'iphone-large',engine:'webkit',width:430,height:932,mobile:true},
 {name:'tablet',engine:'chromium',width:768,height:1024,mobile:false},
 {name:'desktop',engine:'chromium',width:1440,height:900,mobile:false},
 {name:'landscape',engine:'webkit',width:667,height:375,mobile:true}
];
const checks=[],fails=[],warnings=[],screenData=[];
function test(scope,name,pass,detail={}){const obj={scope,name,pass:!!pass,detail};checks.push(obj);console.log((pass?'PASS ':'FAIL ')+scope+' '+name+' '+JSON.stringify(detail).slice(0,600));if(!pass)fails.push(obj)}
function warn(scope,name,detail={}){const obj={scope,name,detail};warnings.push(obj);console.log('WARN '+scope+' '+name+' '+JSON.stringify(detail).slice(0,600))}
async function capture(page,name){try{await page.screenshot({path:path.join(ROOT,name+'.png'),timeout:12000})}catch(e){warn(name,'screenshot-failed',{error:e.message.slice(0,160)})}}
async function measure(page){
return await page.evaluate(()=>{
 const ids=['.hero-main','#tapes','#quickSteps','#sourceStatus','#backToTop','.mobile-nav','.footer'];
 const b=Object.fromEntries(ids.map(id=>{const el=document.querySelector(id);if(!el)return[id,null];const r=el.getBoundingClientRect(),css=getComputedStyle(el);return[id,{x:r.x,y:r.y,w:r.width,h:r.height,bottom:r.bottom,display:css.display,opacity:css.opacity}]}));
 const buttons=[...document.querySelectorAll('button')].filter(el=>{const s=getComputedStyle(el);return s.display!=='none'&&s.visibility!=='hidden'&&el.getClientRects().length}).map(el=>{const r=el.getBoundingClientRect();return{id:el.id,label:(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,35),width:r.width,height:r.height}});
 return {w:innerWidth,h:innerHeight,scrollWidth:document.documentElement.scrollWidth,selected:window.currentDateKey,status:window.MISSAL_STATUS?.availableThrough,
  entries:Object.keys(window.MISSAL_DATA||{}).length,quick:[...document.querySelectorAll('#quickSteps .quick-step')].map(x=>x.textContent.trim()),
  source:document.getElementById('sourceStatusText')?.textContent.trim(),tapes:document.querySelectorAll('#tapes article').length,
  celebration:document.querySelector('#celebration')?.textContent.trim(),buttons,boxes:b};
});
}
async function run(c){
const row={name:c.name,errors:[],snapshots:{}};screenData.push(row);
const browser=await(c.engine==='webkit'?webkit:chromium).launch({headless:true});
const ctx=await browser.newContext({viewport:{width:c.width,height:c.height},isMobile:c.mobile,hasTouch:c.mobile,deviceScaleFactor:1,
 timezoneId:'America/Sao_Paulo',locale:'pt-BR',serviceWorkers:'block',acceptDownloads:true,
 ...(c.engine==='webkit'?{userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'}:{})});
const page=await ctx.newPage();page.setDefaultTimeout(8500);
page.on('pageerror',e=>row.errors.push(e.message));
try{
 const r=await page.goto(origin,{waitUntil:'domcontentloaded',timeout:30000});
 test(c.name,'public-http-200',r?.status()===200,{code:r?.status()});
 await page.waitForTimeout(600);
 row.snapshots.start=await measure(page);
 await capture(page,c.name+'-home');
 const s=row.snapshots.start;
 const expectedSelection=await page.evaluate(()=>{
   const available=getVisibleDates();
   const current=brasiliaTodayKey();
   return available.includes(current)?current:(available.at(-1)||current);
 });
 test(c.name,'live-date-matches-brasilia-release',s.selected===expectedSelection,{selected:s.selected,expected:expectedSelection,today,status:s.status});
 test(c.name,'five-tapes-and-quick-pages',s.tapes===5&&s.quick.length===5,{tapes:s.tapes,quick:s.quick});
 const expectedQuick=await page.evaluate(()=>String(getDisplayEntry(window.currentDateKey)?.quick || ''));
 const digits=v=>String(v).replace(/[^0-9?]/g,'');
 test(c.name,'quick-pages-match-current-entry',digits(s.quick.join(''))===digits(expectedQuick),{quick:s.quick,expectedQuick});
 test(c.name,'no-horizontal-overflow',s.scrollWidth<=c.width+1,{scrollWidth:s.scrollWidth,width:c.width});
 const hero=s.boxes['.hero-main'];
 test(c.name,'hero-visible',!!hero&&Number(hero.opacity)>0.95&&hero.w>0&&hero.h>100,hero);
 test(c.name,'no-unhandled-js-errors',row.errors.length===0,{errors:row.errors});
 const nav=s.boxes['.mobile-nav'];
 if(c.width<=620)test(c.name,'mobile-nav-inside-screen',nav?.display!=='none'&&nav?.bottom<=c.height+2&&nav?.y>=0,nav);
 const tiny=s.buttons.filter(b=>b.height<30 || b.width<25);
 if(tiny.length)warn(c.name,'small-touch-targets',{tiny:tiny.slice(0,8),count:tiny.length});
 await page.locator('#datePickerBtn').click();
 const cm=await page.locator('#dateMenu').evaluate(el=>{const r=el.getBoundingClientRect();return{hidden:el.hidden,x:r.x,y:r.y,right:r.right,bottom:r.bottom,overflow:el.scrollWidth-el.clientWidth,active:document.activeElement?.id,modal:el.getAttribute('aria-modal')}});
 test(c.name,'calendar-within-viewport',!cm.hidden&&cm.x>=-2&&cm.y>=-2&&cm.right<=c.width+2&&cm.bottom<=c.height+2&&cm.overflow<=3,cm);
 await capture(page,c.name+'-calendar');
 if(c.width<=950)test(c.name,'calendar-focus-in-dialog',cm.active==='calendarClose'&&cm.modal==='true',cm);
 await page.keyboard.press('Escape');
 test(c.name,'calendar-escape-returns-focus',await page.locator('#dateMenu').isHidden()&&await page.evaluate(()=>document.activeElement?.id==='datePickerBtn'));
 // Share image from current date and rich-text date.
 if(['iphone','android-regular','desktop'].includes(c.name)){
   for(const d of [s.selected,'2026-10-11','2026-12-25']){
    const b=await page.evaluate(async k=>{render(k);const blob=await buildShareImageBlob();if(!blob)throw Error('image empty');return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=reject;r.readAsDataURL(blob)})},d);
    const f=path.join(ROOT,c.name+'-share-'+d+'.png');fs.writeFileSync(f,Buffer.from(b,'base64'));
    test(c.name,'share-png-'+d,fs.statSync(f).size>15000,{size:fs.statSync(f).size});
   }
   await page.evaluate(()=>render(brasiliaTodayKey()));
 }
 if(c.width<=620){
  await page.locator('#mobileMoreBtn').click();
  test(c.name,'more-menu-opens',await page.locator('#mobileMoreSheet').evaluate(e=>e.classList.contains('open')));
  await capture(page,c.name+'-more');
  await page.locator('#mobileMoreClose').click();
  await page.locator('#mobileCelebrationBtn').click();
  test(c.name,'celebration-mode',await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
  await capture(page,c.name+'-celebration');
  await page.locator('#celebrationModeExit').click();
 }else{
  await page.locator('#celebrationModeBtn').click();
  test(c.name,'celebration-mode',await page.locator('body').evaluate(el=>el.classList.contains('celebration-mode')));
  await capture(page,c.name+'-celebration');
  await page.locator('#celebrationModeExit').click();
 }
 const leaflet=await page.evaluate(()=>getDominicalLeafletUrl());
 test(c.name,'leaflet-direct-pdf',/^https:\/\/.+\.pdf(?:\?|#|$)/.test(leaflet),{url:leaflet});
 }catch(e){test(c.name,'test-complete',false,{error:String(e.stack||e).slice(0,650)})}
 finally{await ctx.close();await browser.close()}
}
(async()=>{
 for(const c of configs)await run(c);
 const browser=await chromium.launch();
 const ctx=await browser.newContext({serviceWorkers:'block'});
 for(const name of ['index.html','data.js','status.js','sw.js','manifest.webmanifest','Missal-Diario-Standalone.html']){
  try{const res=await ctx.request.get(origin+name,{timeout:22000,failOnStatusCode:false});test('public-assets',name+'-http-200',res.status()===200,{code:res.status(),bytes:(await res.body()).length})}
  catch(e){test('public-assets',name+'-http-200',false,{error:String(e).slice(0,250)})}
 }
 await ctx.close();await browser.close();
 const report={time:new Date().toISOString(),checks,fails,warnings,screenData};
 fs.writeFileSync(path.join(ROOT,'relatorio-site-15-10-2026.json'),JSON.stringify(report,null,2));
 console.log('TODAY_AUDIT_END '+JSON.stringify({checks:checks.length,failures:fails.length,warnings:warnings.length,failed:fails.map(x=>x.scope+' '+x.name)}));
 process.exitCode=fails.length?1:0;
})();