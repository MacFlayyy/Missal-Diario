const {chromium,webkit}=require('playwright');
const fs=require('fs');
const path=require('path');
const out=path.resolve('deep-audit-results');fs.mkdirSync(out,{recursive:true});
const base='http://127.0.0.1:8765/';
const publicUrl='https://macflayyy.github.io/Missal-Diario/';
const views=[
  {name:'android-280',engine:'chromium',w:280,h:600,mobile:true},
  {name:'android-320',engine:'chromium',w:320,h:700,mobile:true},
  {name:'android-360',engine:'chromium',w:360,h:800,mobile:true},
  {name:'iphone-375',engine:'webkit',w:375,h:667,mobile:true},
  {name:'iphone-390',engine:'webkit',w:390,h:844,mobile:true},
  {name:'iphone-430',engine:'webkit',w:430,h:932,mobile:true},
  {name:'tablet-768',engine:'chromium',w:768,h:1024,mobile:false},
  {name:'desktop-1280',engine:'chromium',w:1280,h:800,mobile:false},
  {name:'landscape-667',engine:'webkit',w:667,h:375,mobile:true}
];
const result={generated:new Date().toISOString(),screens:[],issues:[],warnings:[],live:[]};
function mark(view,name,pass,info,important=true){
  const test={name,pass:!!pass,info};
  view.tests.push(test);
  if(!pass && important)result.issues.push({view:view.name,test:name,info});
  console.log((pass?'OK  ':'FAIL')+' '+view.name+' '+name+' '+JSON.stringify(info||{}).slice(0,450));
}
function warn(view,key,value){result.warnings.push({view:view.name,kind:key,detail:value});console.log('WARN '+view.name+' '+key+' '+JSON.stringify(value).slice(0,500))}
async function screenshot(page,name,full=false){
 try{await page.screenshot({path:path.join(out,name+'.png'),fullPage:full,timeout:15000});}
 catch(e){console.log('WARN SCREENSHOT '+name+' '+e.message.slice(0,150))}
}
async function visibleMetrics(page){
return page.evaluate(()=>{
 const ids=['.topbar','.hero-main','.side','.section-title','#tapes','.mobile-nav'];
 const m=Object.fromEntries(ids.map(id=>{const e=document.querySelector(id);if(!e)return[id,null];const b=e.getBoundingClientRect(),s=getComputedStyle(e);return[id,{x:b.x,y:b.y,w:b.width,h:b.height,opacity:Number(s.opacity),visibility:s.visibility,display:s.display}] }));
 const viewport={width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,bodyWidth:document.body.scrollWidth};
 const colors=[...document.querySelectorAll('.meta-item span,.calendar-week span,.mobile-nav button span,.detail-text')].slice(0,22).map(x=>({element:x.tagName,selector:x.className,text:x.textContent.slice(0,50),color:getComputedStyle(x).color,fontSize:parseFloat(getComputedStyle(x).fontSize)}));
 return {elements:m,viewport,colors,title:document.querySelector('#celebration')?.textContent||'',ready:document.body.classList.contains('is-ready')};
});
}
async function runView(v){
 const row={name:v.name,width:v.w,height:v.h,tests:[],runtimeErrors:[]};result.screens.push(row);
 const browser=await (v.engine==='webkit'?webkit:chromium).launch({headless:true});
 const context=await browser.newContext({
   viewport:{width:v.w,height:v.h},deviceScaleFactor:1,isMobile:v.mobile,hasTouch:v.mobile,
   timezoneId:'America/Sao_Paulo',locale:'pt-BR',serviceWorkers:'block',
   ...(v.engine==='webkit'?{userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'}:{})
 });
 const page=await context.newPage();
 page.setDefaultTimeout(7000);
 page.on('pageerror',e=>{if(!/cloudflareinsights\.com|cdn-cgi\/rum/i.test(e.message))row.runtimeErrors.push(e.message)});
 try{
  const res=await page.goto(base,{waitUntil:'domcontentloaded',timeout:30000});
  mark(row,'response',res?.status()===200,{status:res?.status()});
  await page.waitForTimeout(350);
  row.firstPaint=await visibleMetrics(page);
  await screenshot(page,v.name+'-first-paint',false);
  await page.waitForTimeout(2200);
  row.stable=await visibleMetrics(page);
  await screenshot(page,v.name+'-stable',false);
  mark(row,'no-document-overflow',row.stable.viewport.documentWidth<=v.w+1,{doc:row.stable.viewport.documentWidth,w:v.w});
  const el=row.stable.elements['.hero-main'];
  mark(row,'main-visible-after-settle',el?.opacity>=0.95&&el?.visibility==='visible'&&el?.h>80,el);
  if(row.firstPaint.elements['.hero-main']?.opacity<0.4)warn(row,'flash-of-blank-or-faded-content',{initial:row.firstPaint.elements['.hero-main'].opacity,settled:el?.opacity});
  mark(row,'no-runtime-error',row.runtimeErrors.length===0,row.runtimeErrors);
  const nav=row.stable.elements['.mobile-nav'];
  if(v.w<=620)mark(row,'bottom-menu-visible',nav?.display!=='none'&&nav?.y>=0&&nav?.y+nav?.h<=v.h+1,nav);
  await page.locator('#datePickerBtn').click();
  await page.waitForTimeout(250);
  const calendar=await page.locator('#dateMenu').evaluate(el=>{const b=el.getBoundingClientRect();return{open:!el.hidden,x:b.x,right:b.right,y:b.y,bottom:b.bottom,height:b.height,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth}});
  mark(row,'calendar-fits-viewport',calendar.open&&calendar.x>=-2&&calendar.right<=v.w+2&&calendar.y>=-2&&calendar.bottom<=v.h+2,calendar);
  mark(row,'calendar-no-inner-overflow',calendar.scrollWidth<=calendar.clientWidth+3,calendar);
  const focusBefore=await page.evaluate(()=>document.activeElement?.id);
  await page.keyboard.press('Tab');
  const focusAfter=await page.evaluate(()=>({id:document.activeElement?.id,within:document.getElementById('dateMenu').contains(document.activeElement)}));
  mark(row,'calendar-keyboard-focus-enters-dialog',focusAfter.within,{before:focusBefore,after:focusAfter},false);
  if(!focusAfter.within)warn(row,'calendar-keyboard-accessibility',{before:focusBefore,after:focusAfter});
  const close=page.locator('#calendarClose');
  if(await close.count()){await close.click();mark(row,'calendar-close-control-works',await page.locator('#dateMenu').isHidden(),{});}
  // Archive and tricky special days. Not released to users; inspected in a test-only browser.
  const probes=await page.evaluate(()=>{
   const picks=['2026-10-11','2026-11-02','2026-12-24','2026-12-25','2026-12-31'];
   const original=window.currentDateKey,errors=[],res=[];
   try{
    for(const k of picks){
     try{
      render(k);
      const m=document.querySelector('.quick .quick-steps'), d=window.MISSAL_DATA[k];
      res.push({date:k,tapes:document.querySelectorAll('#tapes .tape').length,
       quickSteps:document.querySelectorAll('#quickSteps .quick-step').length,
       quickDocWidth:m?.scrollWidth,quickClientWidth:m?.clientWidth,
       pages:d?.tapes?.map(t=>t.page),title:document.querySelector('#celebration')?.textContent,
       pageLabels:[...document.querySelectorAll('#tapes .page')].map(x=>x.textContent)});
     }catch(e){errors.push({date:k,message:String(e.message)})}
    }
   }finally{render(original)}
   return{res,errors};
  });
  row.holidayProbes=probes;
  mark(row,'five-cards-all-special-dates',probes.errors.length===0&&probes.res.every(x=>x.tapes===5&&x.quickSteps===5),probes);
  const overlaps=probes.res.filter(x=>x.quickDocWidth>x.quickClientWidth+4);
  if(overlaps.length)warn(row,'quick-steps-overflow-on-complex-dates',overlaps);
  if(['android-320','iphone-390','desktop-1280'].includes(v.name)){
   const shotDays=['2026-10-11','2026-12-24','2026-12-25'];
   for(const key of shotDays){
    await page.evaluate(key=>render(key),key);
    await page.waitForTimeout(650);
    await screenshot(page,v.name+'-'+key,v.w<700?false:true);
   }
   await page.evaluate(()=>render(brasiliaTodayKey()));
  }
  if(v.name==='android-360'||v.name==='iphone-390'){
   for(const dateKey of ['2026-10-11','2026-12-25']){
    await page.evaluate(key=>render(key),dateKey);
    try{
     const png=await page.evaluate(async()=>{const blob=await buildShareImageBlob(); if(!blob)throw new Error('blob vazio');return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)})});
     const fileName=v.name+'-compartilhar-'+dateKey+'.png';
     fs.writeFileSync(path.join(out,fileName),Buffer.from(png,'base64'));
     mark(row,'share-image-created-'+dateKey,fs.statSync(path.join(out,fileName)).size>15000,{size:fs.statSync(path.join(out,fileName)).size});
    }catch(e){mark(row,'share-image-created-'+dateKey,false,{error:String(e).slice(0,250)})}
   }
   await page.evaluate(()=>render(brasiliaTodayKey()));
  }
  // Render the entire stored 2026 calendar once; detect hidden exceptions without opening future days publicly.
  if(v.name==='desktop-1280'){
   const all=await page.evaluate(()=>{
    const keys=Object.keys(window.MISSAL_DATA).sort(),issues=[],original=window.currentDateKey;
    for(const key of keys){
     try{render(key);const d=window.MISSAL_DATA[key];if(document.querySelectorAll('#tapes article').length!==5)issues.push(key+': fitas');
     if(!d.quick || !d.celebration || !d.tapes?.length)issues.push(key+': dados');}
     catch(e){issues.push(key+': '+String(e.message))}
    }
    render(original);return{tested:keys.length,issues};
   });
   mark(row,'every-registered-day-renders',all.issues.length===0,all);
  }
 }catch(e){mark(row,'scenario-finished',false,{error:String(e.stack).slice(0,700)})}
 finally{await context.close();await browser.close()}
}
(async()=>{
 for(const v of views)await runView(v);
 const browser=await chromium.launch({headless:true});
 const ctx=await browser.newContext({serviceWorkers:'block',timezoneId:'America/Sao_Paulo'});
 const page=await ctx.newPage();
 for(const filename of ['','index.html','data.js','status.js','sw.js','manifest.webmanifest','Missal-Diario-Standalone.html']){
  const url=publicUrl+filename;
  try{
   const r=await ctx.request.get(url,{timeout:28000,failOnStatusCode:false});
   result.live.push({path:filename||'/',status:r.status(),contentType:r.headers()['content-type']||''});
   console.log((r.ok()?'OK':'FAIL')+' LIVE '+filename+' '+r.status());
  }catch(e){result.live.push({path:filename,error:String(e.message).slice(0,200)})}
 }
 await ctx.close();await browser.close();
 fs.writeFileSync(path.join(out,'relatorio-deep.json'),JSON.stringify(result,null,2));
 console.log('DEEP_AUDIT_END '+JSON.stringify({screens:result.screens.length,checks:result.screens.reduce((n,v)=>n+v.tests.length,0),failures:result.issues.length,warnings:result.warnings.length,failuresList:result.issues.map(x=>({view:x.view,test:x.test}))}));
 // Important distinctions: issues are reported without hiding artifacts.
 process.exitCode=result.issues.length>0?1:0;
})();