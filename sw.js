// Cache limitado aos arquivos-base da aplicação: nenhuma versão query,
// PDF, resposta de monitoramento ou recurso de terceiros fica no armazenamento.
const CACHE_NAME = "missal-diario-20261015-cbe0c9709cb9";
const SHELL = [
  "./", "./index.html", "./data.js", "./status.js",
  "./manifest.webmanifest", "./app-icon.svg",
  "./app-icon-180.png", "./app-icon-192.png", "./app-icon-512.png",
  "./brand-logo.png"
];
const FILES = new Set(["index.html","data.js","status.js","manifest.webmanifest","app-icon.svg","app-icon-180.png","app-icon-192.png","app-icon-512.png","brand-logo.png", "brand-logo.webp"]);
function cacheKey(url) {
  const root=new URL(self.registration.scope).pathname;
  if(!url.pathname.startsWith(root)) return null;
  const relative=url.pathname.substring(root.length);
  const file=relative || "index.html";
  if(!FILES.has(file)) return null;
  return new URL("./"+file,self.registration.scope).toString();
}
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(SHELL)));
  self.skipWaiting();
});
self.addEventListener("activate",event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(k=>k.startsWith("missal-diario-") && k!==CACHE_NAME)
      .map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});
self.addEventListener("fetch",event=>{
  const req=event.request;
  if(req.method!=="GET") return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin) return;
  const key=cacheKey(url);
  if(!key) return;
  event.respondWith((async()=>{
    try{
      const res=await fetch(req,{cache:"no-store"});
      if(res.ok){
        const store=await caches.open(CACHE_NAME);
        await store.put(key,res.clone());
      }
      return res;
    }catch(error){
      const cached=await caches.match(key);
      if(cached)return cached;
      if(req.mode==="navigate"){
        const fallback=await caches.match(new URL("./index.html",self.registration.scope).toString());
        if(fallback)return fallback;
      }
      return new Response("Offline",{status:503,statusText:"Offline"});
    }
  })());
});
