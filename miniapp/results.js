// v126: «Natijalarimiz» — sertifikatlar (rasm + ism + daraja) va «Maxsus fikrlar». Hamma ma'lumotni admin kiritadi va admin ko'rsatgandagina foydalanuvchiga chiqadi.
let RS=null, rsTab='cert', rsBusy=false;
const RS_LEVEL_CLS={'A+':'gold','A':'gold','B+':'green','B':'green','C+':'soft'};
function rsApi(path,body){
  return apiFetch(apiUrl(path),body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{cache:'no-store'}).then(r=>r.json());
}
function rsInit(n){ n=String(n||'').trim().split(/\s+/).filter(Boolean); return ((n[0]||'?')[0]+((n[1]||'')[0]||'')).toUpperCase(); }
async function loadResults(){
  const box=$('resBody'); if(!box) return;
  if(!RS) box.innerHTML='<p class="rsEmpty">Yuklanmoqda…</p>';
  try{ const d=await rsApi('/api/results/list'); if(d&&d.ok) RS=d; }catch(e){}
  if(!RS){ box.innerHTML='<p class="rsEmpty">Ma’lumotni yuklab bo‘lmadi. Telegram ichidan oching va qayta urinib ko‘ring.</p>'; return; }
  rsRender();
}
function rsShareBtn(){ return RS.link?'<div class="rsShare rsAdmin"><button type="button" onclick="rsCopyLink()">📋 Havolani nusxalash</button><button type="button" onclick="rsShareTg()">📤 Telegramda ulashish</button></div>':''; }
function rsRender(){
  const box=$('resBody'), d=RS, adm=!!d.is_admin;
  let h='<div class="rsTabs"><button type="button" class="'+(rsTab==='cert'?'on':'')+'" onclick="rsSetTab(\'cert\')">🏆 Sertifikatlar</button><button type="button" class="'+(rsTab==='op'?'on':'')+'" onclick="rsSetTab(\'op\')">💬 Maxsus fikrlar</button></div>';
  if(adm) h+='<div class="rsAdmin"><button type="button" onclick="'+(rsTab==='cert'?'rsCertForm()':'rsOpForm()')+'">➕ '+(rsTab==='cert'?'Sertifikat qo‘shish':'Fikr qo‘shish')+'</button></div>'+'<p class="muted" style="margin:0 0 10px;font-size:12px">👑 Admin: yozuv «Hammaga ko‘rsatish» bosilgandagina foydalanuvchiga chiqadi.</p>';
  if(rsTab==='cert'){
    h+=d.certs.length?d.certs.map(c=>{
      const cls=RS_LEVEL_CLS[c.level]||'soft', hid=adm&&c.visible===false;
      return '<div class="rsCard'+(hid?' hid':'')+'"><div class="rsCert"><img alt="Sertifikat" data-u="/api/results/thumb/'+c.id+'" data-f="/api/results/img/'+c.id+'" onclick="rsZoom(this)">'
        +'<div><span class="rsBadge '+cls+'">'+escapeHtml(c.level)+' daraja</span><p class="rsName">'+escapeHtml(c.name)+'</p>'
        +(c.score?'<p class="rsMeta">Ball: '+escapeHtml(c.score)+'</p>':'')+(c.note?'<p class="rsMeta">'+escapeHtml(c.note)+'</p>':'')
        +(hid?'<p class="rsHidTag">🔒 Faqat admin ko‘radi</p>':'<p class="rsOk">✔ Tasdiqlangan natija</p>')+'</div></div>'
        +(adm?'<div class="rsRow"><button type="button" class="'+(hid?'main':'')+'" onclick="rsVis(\'cert\','+c.id+','+(hid?1:0)+')">'+(hid?'👁 Hammaga ko‘rsatish':'🙈 Yashirish')+'</button><button type="button" onclick="rsCertForm('+c.id+')">✏️ Tahrirlash</button><button type="button" class="del" onclick="rsDel(\'cert\','+c.id+')">🗑</button></div>':'')+'</div>';
    }).join(''):'<p class="rsEmpty">🏆 Natijalar tez orada shu yerda joylanadi.</p>';
  }else{
    h+=d.ops.length?d.ops.map(o=>{
      const hid=adm&&o.visible===false;
      return '<div class="rsCard rsOp'+(hid?' hid':'')+'"><div class="rsHead"><div class="rsAv">'+escapeHtml(rsInit(o.name))+'</div><div style="flex:1;min-width:0"><div class="rsName" style="margin:0">'+escapeHtml(o.name)+'</div>'+(o.who?'<div class="rsMeta" style="margin:0">'+escapeHtml(o.who)+'</div>':'')+'</div><span class="rsTag">'+escapeHtml(o.kind_label)+'</span></div>'
        +'<p class="rsQ">«'+escapeHtml(o.text)+'»</p>'+(o.gain?'<span class="rsGain">📈 '+escapeHtml(o.gain)+'</span>':'')
        +(hid?'<p class="rsHidTag">🔒 Faqat admin ko‘radi</p>':'')
        +(adm?'<div class="rsRow"><button type="button" class="'+(hid?'main':'')+'" onclick="rsVis(\'op\','+o.id+','+(hid?1:0)+')">'+(hid?'👁 Hammaga ko‘rsatish':'🙈 Yashirish')+'</button><button type="button" onclick="rsOpForm('+o.id+')">✏️ Tahrirlash</button><button type="button" class="del" onclick="rsDel(\'op\','+o.id+')">🗑</button></div>':'')+'</div>';
    }).join(''):'<p class="rsEmpty">💬 O‘quvchilar fikrlari tez orada shu yerda joylanadi.</p>';
  }
  h+=rsShareBtn();
  box.innerHTML=h; rsLoadImgs();
}
async function rsBlob(u){ try{ const r=await apiFetch(apiUrl(u)); if(!r.ok) return ''; return URL.createObjectURL(await r.blob()); }catch(e){ return ''; } }
async function rsLoadImgs(){ const im=[...document.querySelectorAll('#resBody img[data-u]')]; for(const el of im){ const s=await rsBlob(el.dataset.u); if(s) el.src=s; } }
function rsSetTab(t){ rsTab=t; rsRender(); }
async function rsZoom(el){
  let v=$('rsViewer'); if(!v){ v=document.createElement('div'); v.id='rsViewer'; v.onclick=()=>{ v.style.display='none'; }; v.innerHTML='<b>×</b><img alt="">'; document.body.appendChild(v); }
  const im=v.querySelector('img'); im.src=el.src||''; v.style.display='flex';
  const s=await rsBlob(el.dataset.f); if(s) im.src=s;
}
function rsCopyLink(){ const t=RS&&RS.link; if(!t) return; try{ navigator.clipboard.writeText(t).then(()=>notify('✅ Havola nusxalandi.')).catch(()=>prompt('Havolani nusxalang:',t)); }catch(e){ prompt('Havolani nusxalang:',t); } }
function rsShareTg(){ const t=RS&&RS.link; if(!t) return; openExt('https://t.me/share/url?url='+encodeURIComponent(t)+'&text='+encodeURIComponent('🏆 Natijalarimiz — sertifikatlar va o‘quvchilar fikrlari:')); }
async function rsVis(kind,id,v){ const d=await rsApi('/api/results/admin/'+kind+'_vis',{id,visible:!!v}); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadResults(); }
async function rsDel(kind,id){ if(!confirm('O‘chirilsinmi?')) return; const d=await rsApi('/api/results/admin/'+kind+'_del',{id}); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadResults(); }
function rsBack(){ return '<button class="back" type="button" onclick="rsRender()">‹ Orqaga</button>'; }
function rsCertForm(id){
  const c=id?(RS.certs.find(x=>x.id===id)||{}):{}; const box=$('resBody');
  box.innerHTML=rsBack()+'<h3>'+(id?'✏️ Sertifikatni tahrirlash':'➕ Sertifikat qo‘shish')+'</h3><div class="rsForm">'
    +'<label>Sertifikat rasmi'+(id?' (almashtirish shart emas)':'')+'</label><input id="rfImg" type="file" accept="image/*">'
    +'<label>Ism familiya</label><input id="rfName" maxlength="80" placeholder="Masalan: Madina Karimova" value="'+escapeHtml(c.name||'')+'">'
    +'<label>Daraja</label><select id="rfLevel">'+RS.levels.map(l=>'<option'+(c.level===l?' selected':'')+'>'+l+'</option>').join('')+'</select>'
    +'<label>Ball (ixtiyoriy)</label><input id="rfScore" maxlength="20" placeholder="Masalan: 72 / 75" value="'+escapeHtml(c.score||'')+'">'
    +'<label>Izoh (ixtiyoriy)</label><input id="rfNote" maxlength="120" placeholder="Masalan: 2026-yil, Toshkent" value="'+escapeHtml(c.note||'')+'">'
    +(id?'':'<div class="chk"><input id="rfVis" type="checkbox"><label for="rfVis" style="margin:0">Darhol hammaga ko‘rsatilsin</label></div>')
    +'<div class="rsErr" id="rfErr"></div><button class="primaryAction" type="button" id="rfGo" onclick="rsCertSave('+(id||0)+')">Saqlash</button></div>';
}
async function rsCertSave(id){
  if(rsBusy) return; const err=$('rfErr'); err.textContent='';
  const f=$('rfImg').files[0]; if(!id&&!f){ err.textContent='Sertifikat rasmini tanlang.'; return; }
  rsBusy=true; $('rfGo').textContent='Saqlanmoqda…';
  try{
    const body={id,name:$('rfName').value,level:$('rfLevel').value,score:$('rfScore').value,note:$('rfNote').value,visible:!!($('rfVis')&&$('rfVis').checked)};
    if(f) body.image=await imgToB64(f);
    const d=await rsApi('/api/results/admin/'+(id?'cert_edit':'cert_add'),body);
    if(!d.ok){ err.textContent=d.error||'Xatolik'; return; }
    await loadResults();
  }catch(e){ err.textContent='Saqlab bo‘lmadi: '+(e.message||'xatolik'); }
  finally{ rsBusy=false; const b=$('rfGo'); if(b) b.textContent='Saqlash'; }
}
function rsOpForm(id){
  const o=id?(RS.ops.find(x=>x.id===id)||{}):{}; const box=$('resBody');
  box.innerHTML=rsBack()+'<h3>'+(id?'✏️ Fikrni tahrirlash':'➕ Maxsus fikr qo‘shish')+'</h3><div class="rsForm">'
    +'<label>Kim nomidan</label><input id="rfName" maxlength="60" placeholder="Masalan: Dilnoza R." value="'+escapeHtml(o.name||'')+'">'
    +'<label>Kimligi (ixtiyoriy)</label><input id="rfWho" maxlength="60" placeholder="Masalan: Mumtoz tahlil maktabi o‘quvchisi" value="'+escapeHtml(o.who||'')+'">'
    +'<label>Turi</label><select id="rfKind">'+Object.keys(RS.kinds).map(k=>'<option value="'+k+'"'+(o.kind===k?' selected':'')+'>'+escapeHtml(RS.kinds[k])+'</option>').join('')+'</select>'
    +'<label>Fikr matni</label><textarea id="rfText" maxlength="600" placeholder="Fikrni shu yerga yozing">'+escapeHtml(o.text||'')+'</textarea>'
    +'<label>Ball o‘sishi (ixtiyoriy)</label><input id="rfGain" maxlength="40" placeholder="Masalan: 45 → 68 ball" value="'+escapeHtml(o.gain||'')+'">'
    +(id?'':'<div class="chk"><input id="rfVis" type="checkbox"><label for="rfVis" style="margin:0">Darhol hammaga ko‘rsatilsin</label></div>')
    +'<div class="rsErr" id="rfErr"></div><button class="primaryAction" type="button" id="rfGo" onclick="rsOpSave('+(id||0)+')">Saqlash</button></div>';
}
async function rsOpSave(id){
  if(rsBusy) return; const err=$('rfErr'); err.textContent=''; rsBusy=true; $('rfGo').textContent='Saqlanmoqda…';
  try{
    const d=await rsApi('/api/results/admin/'+(id?'op_edit':'op_add'),{id,name:$('rfName').value,who:$('rfWho').value,kind:$('rfKind').value,text:$('rfText').value,gain:$('rfGain').value,visible:!!($('rfVis')&&$('rfVis').checked)});
    if(!d.ok){ err.textContent=d.error||'Xatolik'; return; }
    await loadResults();
  }catch(e){ err.textContent='Saqlab bo‘lmadi.'; }
  finally{ rsBusy=false; const b=$('rfGo'); if(b) b.textContent='Saqlash'; }
}
