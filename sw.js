'use strict';
const CACHE='crypto-conte-live-shell-v2';
const BASE=new URL('./',self.location.href);
const ASSETS=['./','manifest.webmanifest','icons/live-192.png','icons/live-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS.map(path=>new URL(path,BASE).href))).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('crypto-conte-live-shell-')&&key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==BASE.origin||!url.pathname.startsWith(BASE.pathname)||url.pathname.startsWith(BASE.pathname+'data/'))return;
  if(event.request.mode==='navigate'){
    event.respondWith(fetch(event.request).then(response=>{
      if(response.ok){const copy=response.clone();event.waitUntil(caches.open(CACHE).then(cache=>cache.put(BASE.href,copy)));}
      return response;
    }).catch(()=>caches.match(BASE.href)));
  }else if(ASSETS.slice(1).some(path=>url.pathname===new URL(path,BASE).pathname)){
    event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)));
  }
});

