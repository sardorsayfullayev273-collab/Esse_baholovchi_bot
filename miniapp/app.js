const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
window.addEventListener("load",()=>loadMe());

let dict = [], mumtoz = [], active = [];
const $ = id => document.getElementById(id);

function normalize(s) {
  return String(s || '').toLowerCase().trim()
    .replaceAll('ʻ', "'").replaceAll('ʼ', "'").replaceAll('‘', "'")
    .replaceAll('’', "'").replaceAll('`', "'");
}
function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function openSection(id) {
  document.querySelectorAll('main').forEach(x => x.classList.add('hidden'));
  $(id).classList.remove('hidden');
  if (id === 'dict') loadData();
  if (id === 'mumtoz') loadMumtoz();
  if (id === 'paronim') loadParonim();
  if (id === 'sinonim') loadSinonim();
  if (id === 'active') loadActive();
  if (id === 'theory') renderTheory();
  if (id === 'prep') { loadQuiz(); loadPrepResources(); }
  if (id === 'growth') loadGrowth();
  if (id === 'author') setAuthorUser();
  if (id === 'stats') loadStats();
  if (id === 'national') loadNationalTests();
  if (id === 'rating') { loadRating('day'); loadNationalTests(); }
  if (id === 'admin') loadAdminPanel();
  window.scrollTo(0,0);
}
function goHome() { document.querySelectorAll('main').forEach(x=>x.classList.add('hidden')); $('home').classList.remove('hidden'); window.scrollTo(0,0); }

async function loadData(){
  if(dict.length)return;
  try{dict=await (await fetch('dictionary.json',{cache:'no-store'})).json(); renderList(dict.slice(0,60),$('dictResults'),'2013-yilgi imlo lug‘ati');}
  catch(e){console.error(e);$('dictResults').innerHTML='<div class="word">Imlo lug‘atini yuklashda xatolik.</div>';}
}
async function loadMumtoz(){
  if(mumtoz.length)return;
  try{mumtoz=await (await fetch('mumtoz.json',{cache:'no-store'})).json(); renderMumtoz(mumtoz.slice(0,60));}
  catch(e){console.error(e);$('mumtozResults').innerHTML='<div class="word">Mumtoz lug‘atni yuklashda xatolik.</div>';}
}
async function loadActive(){
  if(active.length)return;
  try{active=await (await fetch('active1000.json',{cache:'no-store'})).json(); renderList(active.slice(0,80),$('activeResults'),'Faol so‘zlar — manba asosida tanlangan');}
  catch(e){console.error(e);$('activeResults').innerHTML='<div class="word">Faol 1000 bazasini yuklashda xatolik.</div>';}
}
function showSuggestions(inputId,boxId,kind){
  const q=normalize($(inputId).value), box=$(boxId);
  if(q.length<3){box.innerHTML='';box.classList.add('hidden');return;}
  const source=kind==='mumtoz'?mumtoz:dict;
  const matches=source.filter(item=>{const w=typeof item==='string'?item:item.word;return normalize(w).startsWith(q);}).slice(0,12);
  box.innerHTML=matches.length?matches.map(item=>{
    const w=typeof item==='string'?item:item.word, meaning=typeof item==='string'?'':item.meaning;
    return `<button class="suggestion" type="button" onclick="chooseSuggestion(${JSON.stringify(inputId)},${JSON.stringify(boxId)},${JSON.stringify(w)},${JSON.stringify(kind)})"><b>${escapeHtml(w)}</b>${meaning?`<small>${escapeHtml(meaning)}</small>`:''}</button>`;
  }).join(''):'<div class="suggestion muted">Mos so‘z topilmadi.</div>';
  box.classList.remove('hidden');
}
function chooseSuggestion(inputId,boxId,word,kind){$(inputId).value=word;$(boxId).classList.add('hidden');kind==='mumtoz'?searchMumtoz(true):searchDict(true);}

function searchDict(exact=false){
  if(!dict.length){loadData().then(()=>searchDict(exact));return;}
  const q=normalize($('dictSearch').value); showSuggestions('dictSearch','dictSuggestions','dict');
  if(q.length<3&&!exact){renderList(dict.slice(0,60),$('dictResults'),'2013-yilgi imlo lug‘ati');return;}
  renderList(dict.filter(w=>normalize(w).startsWith(q)).slice(0,80),$('dictResults'),'2013-yilgi imlo lug‘ati');
}
function searchMumtoz(exact=false){
  if(!mumtoz.length){loadMumtoz().then(()=>searchMumtoz(exact));return;}
  const q=normalize($('mumtozSearch').value); showSuggestions('mumtozSearch','mumtozSuggestions','mumtoz');
  if(q.length<3&&!exact){renderMumtoz(mumtoz.slice(0,60));return;}
  renderMumtoz(mumtoz.filter(x=>normalize(x.word).startsWith(q)).slice(0,80));
}
function searchActive(){
  if(!active.length){loadActive().then(searchActive);return;}
  const q=normalize($('activeSearch').value);
  renderList(q.length<1?active.slice(0,80):active.filter(w=>normalize(w).startsWith(q)).slice(0,80),$('activeResults'),'Faol so‘zlar');
}
function renderList(arr,el,label){el.innerHTML=arr.length?arr.map(w=>`<div class="word"><strong>${escapeHtml(w)}</strong><div class="muted">${escapeHtml(label)}</div></div>`).join(''):'<div class="word">So‘z topilmadi.</div>';}
function renderMumtoz(arr){$('mumtozResults').innerHTML=arr.length?arr.map(x=>`<div class="word"><strong>${escapeHtml(x.word)}</strong><div class="muted">${escapeHtml(x.meaning||'Izoh mavjud emas.')}</div></div>`).join(''):'<div class="word">So‘z topilmadi.</div>';}


const theory=[
['📝 Argumentli esse nima?','Argumentli esse — berilgan muammo yoki masala yuzasidan turli qarashlarni tahlil qilish, ularni dalillar bilan asoslash va muallifning shaxsiy munosabatini bildirishga qaratilgan yozma ish.'],
['🏗️ Esse tuzilishi','Kirish → 1-qarash va dalil → 2-qarash va dalil → shaxsiy pozitsiya → xulosa.'],
['💡 Dalil turlari','Statistik dalil, hayotiy misol, tarixiy dalil, mutaxassis fikri va mantiqiy dalil. Soxta statistika yoki mavjud bo‘lmagan iqtiboslardan foydalanmang.'],
['🏆 Kuchli asosiy qism','Fikr → sabab → dalil → izoh tizimi asosida yozing.'],
['🎯 Shaxsiy pozitsiya','Fikringizni sabab va dalil bilan asoslang.'],
['🏁 Kuchli xulosa','Asosiy fikrlarni umumlashtiring va yakuniy pozitsiyangizni aniq bildiring.'],
['📊 BBA 24 ballik mezonlar','1. Publitsistik uslub; 2. Ikkala qarash + shaxsiy qarash; 3. Har ikkala qarashning dalillar bilan asoslanishi; 4. Kirish, asosiy qism, xulosa; 5. Mantiqiy qurilish va xatboshilar; 6. Izchillik va fikrlar takrori; 7. Imlo; 8. Punktuatsiya; 9. Qo‘shimcha qo‘llash; 10. So‘z qo‘llash uslubiyati; 11. Leksik xilma-xillik; 12. Sheva/vulgarizm/varvarizm/parazit so‘zlar.'],
['⚠️ Ko‘p uchraydigan xatolar','Mavzudan chetga chiqish, faqat bitta qarashni yoritish, dalilsiz fikr, fikrni takrorlash, chalkash gaplar, xulosada yangi fikr boshlash, imlo va punktuatsiya xatolari.'],
['🧠 Esse yozishdan oldingi 7 savol','Mavzu nimani so‘rayapti? Muammo nima? Birinchi qarash nima? Ikkinchi qarash nima? Har biriga qanday dalil keltiraman? Qaysi fikrni qo‘llab-quvvatlayman? Xulosada fikrimni qanday yakunlayman?'],
['✅ CHECK-LIST','Mavzudan chetga chiqmadimmi? Ikki qarashni yoritdimmi? Har ikki qarashga dalil keltirdimmi? Shaxsiy fikrim aniqmi? Kirish, asosiy qism, xulosa bormi? Imlo, tinish belgilari va qo‘shimchalarni tekshirdimmi?']
];
function renderTheory(){$('theoryContent').innerHTML=theory.map(x=>`<article class="theory-card"><h3>${x[0]}</h3><p>${x[1]}</p></article>`).join('');}
goHome();


// ===== Added without changing the existing dictionary / theory data =====
async function loadStats(){
  const box=$('statsContent');
  const uid=tg?.initDataUnsafe?.user?.id;
  if(!uid){box.innerHTML='<div class="result">Statistikani ko‘rish uchun Mini Appni Telegram ichida oching.</div>';return;}
  box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const r=await apiFetch(apiUrl('/api/stats/'+encodeURIComponent(uid)),{cache:'no-store'});
    const d=await r.json();
    if(!d.ok) throw new Error(d.error||'Xatolik');
    const s=d.stats||{}, n=s.n||0;
    if(!n){box.innerHTML='<div class="result"><h3>Hozircha natija yo‘q</h3><p class="muted">Botga esse yuboring — tekshiruvdan keyin statistika shu yerda paydo bo‘ladi.</p></div>';return;}
    const last=d.last?Number(d.last.total||0):null, prev=d.previous?Number(d.previous.total||0):null;
    let trend='';
    if(last!==null&&prev!==null){const diff=(last-prev).toFixed(1);trend=`<p>Oxirgi esse: <b>${last}/24</b> (${diff>0?'📈 +':diff<0?'📉 ':'➖ '}${diff} oldingisiga nisbatan)</p>`;}
    else if(last!==null) trend=`<p>Oxirgi esse: <b>${last}/24</b></p>`;
    box.innerHTML=`<div class="stats-grid">
      <div class="stat"><b>${n}</b><small>Tekshirilgan esse</small></div>
      <div class="stat"><b>${Number(s.avg||0).toFixed(1)}</b><small>O‘rtacha ball</small></div>
      <div class="stat"><b>${s.hi||0}</b><small>Eng yuqori ball</small></div></div>
      <div class="result"><h3>📈 Rivojlanish</h3>${trend}<p class="muted">Matn: ${s.text_n||0} • Rasm: ${s.image_n||0} • Eng past ball: ${s.lo??0}</p></div>`;
  }catch(e){ box.innerHTML='<div class="result">Statistikani yuklashda xatolik yuz berdi.</div>'; }
}

async function loadPrepResources(){
  const box=$('prepResources');
  if(!box) return;
  box.innerHTML='<div class="word">⏳ Materiallar yuklanmoqda...</div>';
  try{
    const r=await apiFetch(apiUrl('/api/national/prep/resources'),{cache:'no-store'});
    const d=await r.json();
    const arr=d.resources||[];
    box.innerHTML=arr.length?arr.map(x=>{
      const body=x.content?`<div class="muted" style="white-space:pre-wrap;margin-top:8px">${escapeHtml(x.content)}</div>`:'';
      const file=x.file_url?`<a class="primaryAction" href="${escapeHtml(apiUrl(x.file_url))}" target="_blank" rel="noopener">📥 Faylni ochish</a>`:'';
      return `<div class="listbtn"><b>📚 ${escapeHtml(x.title)}</b><small>${escapeHtml(x.kind||'Manba')}</small>${body}${file}</div>`;
    }).join(''):'<div class="word">Hozircha tayyorlov materiallari joylanmagan.</div>';
  }catch(e){console.error(e);box.innerHTML='<div class="word">Tayyorlov materiallarini yuklashda xatolik.</div>';}
}

let nationalTest=null, nationalIndex=0, nationalAnswers={}, nationalEssayScore=null;

// Mini App may be hosted on GitHub Pages while the API runs on Render.
// Set window.MINIAPP_API_BASE when hosted separately; when served by Render,
// the same-origin API is used automatically.
const MINIAPP_API_BASE = (new URLSearchParams(location.search).get('api') || window.MINIAPP_API_BASE || '').replace(/\/$/, '');
function apiUrl(path){ return MINIAPP_API_BASE + path; }
function apiFetch(url,opt={}){ opt.headers=Object.assign({'X-Init-Data':tg?.initData||''},opt.headers||{}); return fetch(url,opt); }
function notify(msg){ if(tg?.showAlert){ try{ tg.showAlert(msg); return; }catch(e){} } window.alert(msg); }
let ME={ok:false,is_admin:false,can_create:false};
async function loadMe(){
  try{ const r=await apiFetch(apiUrl('/api/me'),{cache:'no-store'}); ME=await r.json(); }catch(e){ ME={ok:false,is_admin:false,can_create:false}; }
  document.querySelectorAll('.needCreate').forEach(x=>x.classList.toggle('hidden',!ME.can_create));
  document.querySelectorAll('.adminOnly').forEach(x=>x.classList.toggle('hidden',!ME.is_admin));
  document.querySelectorAll('.nonAdminNote').forEach(x=>x.classList.toggle('hidden',!!ME.can_create));
  document.querySelectorAll('.adminLink').forEach(a=>{ a.textContent=ME.admin_username?'@'+ME.admin_username:'admin'; });
}
function openAdmin(){
  if(!ME.admin_username){ notify('Admin bilan bot orqali bog‘laning.'); return; }
  const u='https://t.me/'+ME.admin_username;
  if(tg?.openTelegramLink) tg.openTelegramLink(u); else window.open(u,'_blank');
}


async function loadNationalTests(){
  const box=$('nationalTests'); box.innerHTML='<div class="word">⏳ Testlar yuklanmoqda...</div>';
  try{
    const r=await apiFetch(apiUrl('/api/national/tests'),{cache:'no-store'}); const d=await r.json();
    const arr=d.tests||[];
    window.__tests=arr; if($('ratingTests')) renderRatingTests();
    box.innerHTML=arr.length?arr.map(x=>`<div class="testRow"><button class="listbtn" type="button" onclick="startNational(${escapeHtml(JSON.stringify(x.code))})"><b>${x.official?'⭐':'👤'} 🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${escapeHtml(x.subject||'Ona tili va adabiyot')} • ${x.duration_min||180} daqiqa • 45 topshiriq</small></button>${ME.is_admin?`<button class="delBtn" type="button" onclick="deleteNationalTest(${escapeHtml(JSON.stringify(x.code))})">🗑</button>`:''}</div>`).join(''):'<div class="word">Hozircha e’lon qilingan testlar yo‘q.</div>';
  }catch(e){console.error(e);box.innerHTML='<div class="word">Testlarni yuklashda xatolik.</div>';}
}

function nationalUid(){ return tg?.initDataUnsafe?.user?.id || 0; }

function openNationalCreate(){
  openSection('nationalCreate');
  const box=$('builderQuestions');
  if(box.dataset.ready==='1') return;
  const rows=[];
  for(let i=1;i<=45;i++){
    const type=i===45?'O2':(i<=32?'Y1':(i<=35?'Y2':(i<=39?'O1':'O1AB')));
    if(type==='Y1'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol</b><div class="answerGrid four">${['A','B','C','D'].map(x=>`<button type="button" class="keyBtn" data-q="${i}" data-value="${x}">${x}</button>`).join('')}</div></div>`);
    }else if(type==='Y2'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol (Y-2)</b><p class="muted">To‘g‘ri javobni belgilang</p><div class="answerGrid six">${['A','B','C','D','E','F'].map(x=>`<button type="button" class="keyBtn" data-q="${i}" data-value="${x}">${x}</button>`).join('')}</div></div>`);
    }else if(type==='O1'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — ochiq</b><label class="field">To‘g‘ri javob<input id="co${i}" placeholder="Masalan: OCHIQ"></label></div>`);
    }else if(type==='O1AB'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — ochiq a/b</b><label class="field">a) To‘g‘ri javob<input id="caa${i}" placeholder="Masalan: OCHIQ"></label><label class="field">b) To‘g‘ri javob<input id="cab${i}" placeholder="Masalan: KITOB"></label></div>`);
    }else{
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — esse</b><p class="muted">Javob kaliti kiritilmaydi. Talabgorning botdagi oxirgi esse bali avtomatik olinadi.</p></div>`);
    }
  }
  box.innerHTML=rows.map((r,idx)=>idx===44?r:r.replace('</b>','</b><textarea id="ct'+(idx+1)+'" rows="2" maxlength="1200" placeholder="Savol matni (ixtiyoriy — foydalanuvchi savolni ko‘radi)" style="margin:6px 0"></textarea>')).join(''); box.dataset.ready='1';
  box.querySelectorAll('.keyBtn').forEach(btn=>btn.addEventListener('click',()=>{
    const q=btn.dataset.q;
    box.querySelectorAll(`.keyBtn[data-q="${q}"]`).forEach(x=>x.classList.remove('selected'));
    btn.classList.add('selected');
  }));
}

function selectedKey(q){
  const b=document.querySelector(`.keyBtn[data-q="${q}"].selected`);
  return b ? b.dataset.value : '';
}

async function createNationalTest(){
  const title=($('createTitle')?.value||'').trim();
  if(!title){notify('Test nomini kiriting.');return;}
  const questions=[];
  for(let i=1;i<=45;i++){
    const type=i===45?'O2':(i<=32?'Y1':(i<=35?'Y2':(i<=39?'O1':'O1AB')));
    const q={type,points:1};
    const tx=($('ct'+i)?.value||'').trim(); if(tx) q.text=tx;
    if(type==='Y1'||type==='Y2'){
      q.options=type==='Y1'?['A','B','C','D']:['A','B','C','D','E','F'];
      q.answer=selectedKey(i);
      if(!q.answer){notify(`${i}-savolning to‘g‘ri javobini belgilang.`);return;}
    }else if(type==='O1'){
      q.answers=($(`co${i}`)?.value||'').split(';').map(x=>x.trim()).filter(Boolean);
      if(!q.answers.length){notify(`${i}-savolning to‘g‘ri javobini kiriting.`);return;}
    }else if(type==='O1AB'){
      q.a_answers=($(`caa${i}`)?.value||'').split(';').map(x=>x.trim()).filter(Boolean);
      q.b_answers=($(`cab${i}`)?.value||'').split(';').map(x=>x.trim()).filter(Boolean);
      if(!q.a_answers.length||!q.b_answers.length){notify(`${i}-savolning a) va b) to‘g‘ri javoblarini kiriting.`);return;}
    }else{
      q.essay_from_bot=true;
    }
    questions.push(q);
  }
  const status=$('createStatus'); status.textContent='⏳ Test saqlanmoqda...';
  try{
    const r=await apiFetch(apiUrl('/api/national/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,questions,subject:'Ona tili va adabiyot',duration_min:180,include_essay:true})});
    const d=await r.json();
    if(!d.ok){status.textContent='❌ '+(d.error||'Test yaratilmadi');return;}
    const btnCopy=`<button class="primaryAction" type="button" onclick="copyCode(${escapeHtml(JSON.stringify(d.code))})">📋 Kodni nusxalash</button>`;
    status.innerHTML=`<div class="result"><h3>✅ Test yaratildi!</h3><div class="scoreBig" style="font-size:34px">${escapeHtml(d.code)}</div><p>Shu kodni boshqalarga yuboring. Boshqa talabgorlar testni shu kod orqali ishlab, javoblarini tekshirtirishi mumkin.</p><p class="muted">📝 Esse bali talabgorning botdagi oxirgi esse natijasidan avtomatik olinadi.</p>${btnCopy}</div>`;
  }catch(e){console.error(e);status.textContent='❌ Server bilan bog‘lanishda xatolik.';}
}

async function startNational(code){
  try{
    const r=await apiFetch(apiUrl('/api/national/test/'+encodeURIComponent(code))); const d=await r.json();
    if(!d.ok){notify(d.error||'Test topilmadi');return;}
    nationalTest=d.test; nationalIndex=0; nationalAnswers={};
    nationalEssayScore=null;
    try{ const er=await apiFetch(apiUrl('/api/national/essay-score/'+encodeURIComponent(nationalUid())),{cache:'no-store'}); const ed=await er.json(); nationalEssayScore=ed.ok?ed.essay_score:null; }catch(e){ nationalEssayScore=null; }
    openSection('nationalExam'); renderNationalQuestion();
  }catch(e){console.error(e);notify('Testni ochishda xatolik yuz berdi.');}
}
function renderNationalQuestion(){
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1), saved=nationalAnswers[key], total=nationalTest.questions.length;
  $('nationalProgress').innerHTML=`${nationalIndex+1} / ${total} • ${escapeHtml(q.type)}<div class="bar"><i style="width:${Math.round((nationalIndex+1)/total*100)}%"></i></div>`;
  $('nationalQuestion').innerHTML=(nationalIndex===0?`<div class="result" style="margin:0 0 10px"><b>📝 Esse bali:</b> ${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'topilmadi — avval botda esse tekshirtiring'}</div>`:'') + (q.text?escapeHtml(q.text):`<b>${q.type==='O2'?'45-savol — esse':nationalIndex+1+'-savol: javobni belgilang yoki kiriting'}</b>`);
  let html='';
  if(q.type==='Y1'||q.type==='Y2'){
    const opts=q.options&&q.options.length?q.options:['A','B','C','D'];
    html=`<div class="answers">${opts.map(x=>`<button type="button" class="nopt${saved===x?' selected':''}" data-value="${escapeHtml(x)}">${escapeHtml(x)}</button>`).join('')}</div>`;
  }else if(q.type==='O1') html=`<input id="nopen" placeholder="Javobni aynan yozing" value="${escapeHtml(typeof saved==='string'?saved:'')}">`;
  else if(q.type==='O1AB') html=`<label class="field">a) javob<input id="na" placeholder="a) javobni yozing" value="${escapeHtml(Array.isArray(saved)?saved[0]:'')}"></label><label class="field">b) javob<input id="nb" placeholder="b) javobni yozing" value="${escapeHtml(Array.isArray(saved)?saved[1]:'')}"></label>`;
  else html=`<div class="result"><b>45-savol — esse</b><p class="muted">Bu yerda esse qayta yozilmaydi. Talabgorning botda tekshirtirgan oxirgi esse bali avtomatik hisobga olinadi.</p><div class="scoreBig" style="font-size:32px">${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'Esse bali topilmadi'}</div></div>`;
  $('nationalAnswer').innerHTML=html;
  document.querySelectorAll('.nopt').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nopt').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');nationalAnswers[String(nationalIndex+1)]=b.dataset.value;}));
  const last=nationalIndex===total-1;
  $('btnNext').textContent=last?'Yakunlash ✓':'Keyingi ›';
  $('btnPrev').classList.toggle('hidden',nationalIndex===0);
}
function collectNational(){
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1);
  if(q.type==='O1') nationalAnswers[key]=($('nopen')?.value||'').trim();
  if(q.type==='O1AB') nationalAnswers[key]=[($('na')?.value||'').trim(),($('nb')?.value||'').trim()];
  if(q.type==='O2') nationalAnswers[key]='__ESSAY_FROM_BOT__';
}
function prevNational(){ if(nationalIndex===0)return; collectNational(); nationalIndex--; renderNationalQuestion(); window.scrollTo(0,0); }
let nationalBusy=false;
async function nextNational(){
  if(nationalBusy)return;
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1);
  collectNational();
  const v=nationalAnswers[key];
  if(q.type!=='O2' && (v==null || v==='' || (Array.isArray(v)&&v.some(x=>!x)))){notify('Javobni kiriting.');return;}
  if(nationalIndex<nationalTest.questions.length-1){nationalIndex++;renderNationalQuestion();window.scrollTo(0,0);return;}
  const blank=nationalTest.questions.findIndex((qq,i)=>qq.type!=='O2'&&!nationalAnswers[String(i+1)]);
  if(blank>=0){notify((blank+1)+'-savolga javob berilmagan.');nationalIndex=blank;renderNationalQuestion();return;}
  nationalBusy=true; $('btnNext').disabled=true;
  try{ await submitNational(); } finally { nationalBusy=false; $('btnNext').disabled=false; }
}
async function submitNational(){
  const uid=nationalUid();
  try{
    const r=await apiFetch(apiUrl('/api/national/submit'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:nationalTest.code,answers:nationalAnswers})});
    const d=await r.json();
    openSection('nationalResult');
    if(!d.ok){$('nationalResult').innerHTML='<button class="back" onclick="openSection(\'national\')">‹ Milliy sertifikat</button><div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>';return;}
    $('nationalResult').innerHTML=`<button class="back" onclick="openSection('national')">‹ Milliy sertifikat</button><div class="result"><h3>🎓 Diagnostik natija</h3><div class="scoreBig">${d.combined_score_75 ?? d.score_75}/75</div><p><b>Daraja: ${escapeHtml(d.level)}</b></p><p>Test: ${d.score_75}/75 • To‘g‘ri javob balli: ${d.raw_score}/${d.max_score}</p><p>📝 Botdagi esse bali: ${d.essay_score??'—'}/24</p><h4>❌ Xatolar: ${(d.errors||[]).length}</h4>${(d.errors||[]).map(x=>`<div class="errorCard"><b>${x.number}-savol</b><br>Siz: ${escapeHtml(JSON.stringify(x.user))}<br>To‘g‘ri: ${escapeHtml(JSON.stringify(x.correct))}<br>${escapeHtml(x.explanation||'')}</div>`).join('')}<p class="muted">Bu diagnostik natija. Rasmiy davlat sertifikati emas.</p></div>`;
    if(d.cert_code){ $('nationalResult').insertAdjacentHTML('beforeend',`<div class="result"><h4>📜 Sertifikatingiz</h4><img src="${apiUrl('/api/cert/'+encodeURIComponent(d.cert_code)+'.png')}" alt="Sertifikat" style="width:100%;border-radius:12px;border:1px solid var(--line)"><p class="muted">Sertifikat avtomatik tarzda botdagi chatingizga ham yuborildi.</p><button class="primaryAction" type="button" onclick="sendCert('${escapeHtml(d.cert_code)}')">📩 Chatga qayta yuborish</button></div>`); }
  }catch(e){openSection('nationalResult');$('nationalResult').innerHTML='<button class="back" onclick="openSection(\'national\')">‹ Milliy sertifikat</button><div class="result">❌ Natijani yuborishda xatolik.</div>';}
}
function nationalCode(){
  const c=($('codeInput')?.value||'').trim().toUpperCase();
  if(!c){notify('Test kodini kiriting.');return;}
  startNational(c);
}


// ===== Dizayn: pastki menyu va Telegram rangi =====
(function(){
  const map={home:'home',rating:'rating',admin:'home',growth:'home',author:'home',dict:'dict',mumtoz:'dict',paronim:'dict',sinonim:'dict',active:'dict',national:'test',nationalCreate:'test',nationalExam:'test',nationalResult:'test',stats:'stats'};
  const mark=id=>document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('on',b.dataset.k===(map[id]||'')));
  const o=openSection,h=goHome;
  openSection=function(id){o(id);mark(id);};
  goHome=function(){h();mark('home');};
  try{tg?.setHeaderColor?.('#075b43');tg?.setBackgroundColor?.('#f2f7f5');}catch(e){}
})();


// ===== Admin: tayyorlov materiali qo'shish, test o'chirish =====
async function addPrepResource(){
  const title=($('prepTitle')?.value||'').trim(), content=($('prepContent')?.value||'').trim();
  if(!title||!content){notify('Sarlavha va matnni kiriting.');return;}
  const st=$('prepStatus'); st.textContent='⏳ Saqlanmoqda...';
  try{
    const r=await apiFetch(apiUrl('/api/national/prep/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,content,kind:'manba'})});
    const d=await r.json();
    if(!d.ok){st.textContent='❌ '+(d.error||'Xatolik');return;}
    st.textContent='✅ Qo‘shildi'; $('prepTitle').value=''; $('prepContent').value=''; loadPrepResources();
  }catch(e){st.textContent='❌ Server bilan bog‘lanishda xatolik.';}
}
async function deleteNationalTest(code){
  const go=()=>apiFetch(apiUrl('/api/national/delete'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})}).then(r=>r.json()).then(d=>{if(d.ok)loadNationalTests();else notify(d.error||'Xatolik');});
  if(tg?.showConfirm) tg.showConfirm(code+' testini o‘chiraysizmi?',ok=>{if(ok)go();}); else if(confirm(code+' testini o‘chiraysizmi?')) go();
}
function copyCode(code){ try{navigator.clipboard.writeText(code);notify('Kod nusxalandi: '+code);}catch(e){notify('Kod: '+code);} }


// ===== Paronim va sinonim lug'atlari =====
let paronim=[], sinonim=[];
async function loadParonim(){
  if(!paronim.length){ try{ paronim=await (await fetch('paronim.json')).json(); }catch(e){ $('paronimResults').innerHTML='<div class="word">Paronimlar lug‘ati yuklanmadi.</div>'; return; } }
  searchParonim();
}
function searchParonim(){
  const q=normalize($('paronimSearch').value);
  const a=q.length>=2 ? paronim.filter(e=>normalize(e.n).includes(q)||e.w.some(w=>normalize(w.w).includes(q))) : paronim;
  $('paronimResults').innerHTML=a.slice(0,40).map(e=>`<div class="word"><strong>${escapeHtml(e.n)}</strong>${e.w.map(w=>`<div class="muted" style="margin-top:8px"><b style="color:var(--g2)">${escapeHtml(w.w)}</b> — ${escapeHtml(w.m)}${w.ex[0]?`<br><i>${escapeHtml(w.ex[0])}</i>`:''}</div>`).join('')}</div>`).join('')||'<div class="word">So‘z topilmadi.</div>';
}
async function loadSinonim(){
  if(!sinonim.length){ try{ sinonim=await (await fetch('sinonim.json')).json(); }catch(e){ $('sinonimResults').innerHTML='<div class="word">Sinonimlar lug‘ati yuklanmadi.</div>'; return; } }
  searchSinonim();
}
function searchSinonim(){
  const q=normalize($('sinonimSearch').value);
  const a=q.length>=2 ? sinonim.filter(e=>e.h.some(w=>normalize(w).includes(q))) : sinonim;
  $('sinonimResults').innerHTML=a.slice(0,40).map(e=>`<div class="word"><strong>${escapeHtml(e.h.join(', '))}</strong><div class="muted" style="margin-top:6px">${escapeHtml(e.t)}</div></div>`).join('')||'<div class="word">So‘z topilmadi.</div>';
}


// ===== Reyting, sertifikat va admin panel =====
async function sendCert(code){
  try{ const r=await apiFetch(apiUrl('/api/cert/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})}); const d=await r.json(); notify(d.ok?'Sertifikat chatingizga yuborildi.':(d.error||'Xatolik')); }catch(e){ notify('Yuborib bo‘lmadi.'); }
}
function renderRatingTests(){
  const a=(window.__tests||[]).filter(x=>x.official);
  $('ratingTests').innerHTML=a.length?a.map(x=>`<button class="listbtn" type="button" onclick="startNational(${escapeHtml(JSON.stringify(x.code))})"><b>⭐ ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${x.attempts||0} marta ishlangan • 45 topshiriq</small></button>`).join(''):'<div class="word">Hozircha rasmiy test yo‘q.</div>';
}
async function loadRating(kind){
  ['day','week','month'].forEach(k=>$('tab_'+k).classList.toggle('on',k===kind));
  const box=$('ratingBox'); box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/rating/'+kind),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="word">Reytingni yuklab bo‘lmadi.</div>'; return; }
    const medal=r=>r===1?'🥇':r===2?'🥈':r===3?'🥉':r+'.';
    const me=d.me?`<div class="result"><b>Sizning o‘rningiz: ${d.me.rank}-o‘rin</b><p class="muted">${d.me.pts} ball • ${d.me.n} ta topshiriq • jami ${d.total} ishtirokchi</p></div>`:'<div class="result"><b>Siz hali reytingda emassiz</b><p class="muted">Quyidagi ⭐ rasmiy testlardan birini ishlang.</p></div>';
    box.innerHTML=`<div class="muted">${escapeHtml(d.label)} • ${escapeHtml(d.range)}</div>`+me+(d.top.length?d.top.map(x=>`<div class="word" style="${x.me?'border-color:var(--g3);background:var(--mint)':''}"><strong>${medal(x.rank)} ${escapeHtml(x.name)}</strong><div class="muted">${x.pts} ball • ${x.n} ta topshiriq</div></div>`).join(''):'<div class="word">Bu davrda hali natija yo‘q. Birinchi bo‘ling! 🚀</div>');
  }catch(e){ box.innerHTML='<div class="word">Xatolik yuz berdi.</div>'; }
}
async function loadAdminPanel(){
  const box=$('adminBox'); if(!ME.is_admin){ box.innerHTML='<div class="word">Faqat admin uchun.</div>'; return; }
  box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/admin/overview'),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="word">'+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    const st=`<div class="stats-grid"><div class="stat"><b>${d.users}</b><small>Foydalanuvchi</small></div><div class="stat"><b>${d.user_tests}/${d.tests}</b><small>Foydalanuvchi testlari</small></div><div class="stat"><b>${d.attempts_today}</b><small>Bugun ishlangan</small></div></div>`;
    const rows=d.recent_tests.map(t=>`<div class="word"><strong>${t.official?'⭐':'👤'} ${escapeHtml(t.code)} — ${escapeHtml(t.title)}</strong><div class="muted">Muallif: ${escapeHtml(t.creator)} (ID ${t.created_by}) • ${t.attempts} urinish • ${escapeHtml((t.created_at||'').slice(0,10))}</div>${t.official?'':`<div class="adminRow"><button onclick="adminDelete('${escapeHtml(t.code)}')">🗑 O‘chirish</button><button onclick="adminBan(${t.created_by})">🚫 Muallifni bloklash</button></div>`}</div>`).join('');
    const bans=d.banned.length?d.banned.map(b=>`<div class="word"><strong>🚫 ID ${b.user_id}</strong><div class="muted">${escapeHtml(b.reason||'')} • ${escapeHtml((b.banned_at||'').slice(0,10))}</div><div class="adminRow"><button onclick="adminUnban(${b.user_id})">✅ Blokdan chiqarish</button></div></div>`).join(''):'<div class="word">Bloklanganlar yo‘q.</div>';
    box.innerHTML=st+'<h3>So‘nggi testlar</h3>'+(rows||'<div class="word">Test yo‘q.</div>')+'<h3 style="margin-top:14px">Bloklanganlar</h3>'+bans;
  }catch(e){ box.innerHTML='<div class="word">Xatolik yuz berdi.</div>'; }
}
async function adminPost(path,body){ const d=await (await apiFetch(apiUrl(path),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json(); if(!d.ok) notify(d.error||'Xatolik'); return d.ok; }
async function adminDelete(code){ if(await adminPost('/api/national/delete',{code})) loadAdminPanel(); }
async function adminBan(id){ if(await adminPost('/api/admin/ban',{user_id:id,reason:'Admin tomonidan bloklandi'})) loadAdminPanel(); }
async function adminUnban(id){ if(await adminPost('/api/admin/unban',{user_id:id})) loadAdminPanel(); }


// ===== Savollar: admin yozadi, foydalanuvchi savol tagida javob beradi =====
const quizSel={};
function qzToggle(){ const o=$('qzKind').value==='open'; $('qzOpen').classList.toggle('hidden',!o); $('qzClosed').classList.toggle('hidden',o); }
async function addQuiz(){
  const kind=$('qzKind').value, st=$('qzStatus');
  const body={title:$('qzTitle').value,question:$('qzText').value,kind,points:+$('qzPoints').value,explanation:$('qzExpl').value};
  if(kind==='closed'){ body.options=[0,1,2,3].map(i=>$('qzOpt'+i).value.trim()).filter(Boolean); body.correct=$('qzCorrect').value; }
  else body.answers=$('qzAnswers').value.split(';').map(x=>x.trim()).filter(Boolean);
  st.textContent='⏳ Saqlanmoqda...';
  try{ const d=await (await apiFetch(apiUrl('/api/quiz/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(!d.ok){ st.textContent='❌ '+(d.error||'Xatolik'); return; }
    st.textContent='✅ Savol joylandi!'; ['qzTitle','qzText','qzAnswers','qzExpl','qzOpt0','qzOpt1','qzOpt2','qzOpt3'].forEach(i=>$(i).value=''); loadQuiz();
  }catch(e){ st.textContent='❌ Server bilan bog‘lanishda xatolik.'; }
}
async function loadQuiz(){
  const box=$('quizBox'); box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/quiz/list'),{cache:'no-store'})).json();
    const items=d.items||[];
    box.innerHTML=items.length?items.map(renderQuizItem).join(''):'<div class="word">Hozircha savol yo‘q.</div>';
  }catch(e){ box.innerHTML='<div class="word">Savollarni yuklab bo‘lmadi.</div>'; }
}
function renderQuizItem(it){
  const L='ABCDEF';
  let body='';
  if(it.my){
    body=`<div class="result" style="margin:10px 0 0"><b>${it.my.correct?'✅ To‘g‘ri! +'+it.my.points+' ball':'❌ Noto‘g‘ri'}</b><p class="muted">Sizning javobingiz: ${escapeHtml(it.my.answer)}<br>To‘g‘ri javob: <b>${escapeHtml(it.right||'')}</b></p>${it.explanation?`<p class="muted">💡 ${escapeHtml(it.explanation)}</p>`:''}</div>`;
  }else if(it.kind==='closed'){
    body=`<div class="answers" style="margin-top:10px">${it.options.map((o,i)=>`<button type="button" class="nopt" data-q="${it.id}" data-v="${L[i]}" onclick="quizPick(${it.id},'${L[i]}',this)">${L[i]}) ${escapeHtml(o)}</button>`).join('')}</div><button class="primaryAction" type="button" onclick="quizSend(${it.id})">📤 Javobni yuborish</button>`;
  }else{
    body=`<input id="qa${it.id}" placeholder="Javobingizni yozing" maxlength="300"><button class="primaryAction" type="button" onclick="quizSend(${it.id})">📤 Javobni yuborish</button>`;
  }
  const adm=ME.is_admin?`<div class="adminRow"><span class="muted">To‘g‘ri: ${escapeHtml(it.right||'')}</span><button onclick="quizDelete(${it.id})">🗑 O‘chirish</button></div>`:'';
  return `<div class="listbtn" style="cursor:default"><b>📚 ${escapeHtml(it.title)} <small style="font-weight:600;color:var(--mut)">• ${it.points} ball</small></b><div style="white-space:pre-wrap;margin-top:6px">${escapeHtml(it.question)}</div>${body}${adm}</div>`;
}
function quizPick(id,v,btn){ quizSel[id]=v; document.querySelectorAll(`.nopt[data-q="${id}"]`).forEach(x=>x.classList.remove('selected')); btn.classList.add('selected'); }
async function quizSend(id){
  const ans=quizSel[id]||($('qa'+id)?.value||'').trim();
  if(!ans){ notify('Avval javobni tanlang yoki yozing.'); return; }
  try{ const d=await (await apiFetch(apiUrl('/api/quiz/answer'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,answer:ans})})).json();
    if(!d.ok){ notify(d.error||'Xatolik'); loadQuiz(); return; }
    loadQuiz();
  }catch(e){ notify('Javobni yuborib bo‘lmadi.'); }
}
async function quizDelete(id){ try{ await apiFetch(apiUrl('/api/quiz/delete'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}); loadQuiz(); }catch(e){} }


// ===== Esse mashqi va dalil topish (AI, kunlik limit) =====
function gTab(t){ ['practice','evidence'].forEach(x=>{ $('gt_'+x).classList.toggle('on',x===t); $(x==='practice'?'gPractice':'gEvidence').classList.toggle('hidden',x!==t); }); }
async function loadGrowth(){
  try{ const me=await (await apiFetch(apiUrl('/api/me'),{cache:'no-store'})).json(); const left=Math.max(0,(me.ai_limit||0)-(me.ai_used||0)); $('aiLeft').textContent=left+' / '+(me.ai_limit||0)+' ta qoldi'; }catch(e){}
  try{ const d=await (await apiFetch(apiUrl('/api/practice/topic'),{cache:'no-store'})).json(); $('pTopic').textContent=d.topic||'—'; }catch(e){ $('pTopic').textContent='Mavzuni yuklab bo‘lmadi.'; }
}
function pCount(){ const n=($('pEssay').value.trim().match(/\S+/g)||[]).length; $('pWords').textContent=n+' so‘z'+(n<40?' (kamida 40)':''); }
async function aiPost(path,body,out){
  out.innerHTML='<div class="word">⏳ Sun’iy intellekt ishlamoqda, bir daqiqa kuting...</div>';
  try{
    const d=await (await apiFetch(apiUrl(path),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(!d.ok){ out.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return null; }
    for(let i=0;i<60;i++){
      await new Promise(r=>setTimeout(r,2000));
      const s=await (await apiFetch(apiUrl('/api/job/'+d.job),{cache:'no-store'})).json();
      if(s.status==='done') return s.data;
      if(s.status==='error'){ out.innerHTML='<div class="result">❌ '+escapeHtml(s.error||'Xatolik')+'</div>'; return null; }
    }
    out.innerHTML='<div class="result">⌛ Javob kechikdi. Birozdan so‘ng qayta urinib ko‘ring.</div>'; return null;
  }catch(e){ out.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; return null; }
}
async function submitPractice(){
  const out=$('pResult'); const d=await aiPost('/api/practice/submit',{essay:$('pEssay').value},out); loadGrowth(); if(!d) return;
  out.innerHTML=`<div class="result"><h3>📝 Natija: ${d.total}/24</h3><p class="muted">75 ballik ekvivalent: <b>${d.to75}/75</b> • ${d.words} so‘z</p>
  ${(d.criteria||[]).map(c=>`<div class="word"><strong>${escapeHtml(c.name)}: ${c.score}</strong><div class="muted">${escapeHtml(c.reason)}</div></div>`).join('')}
  ${d.summary?`<p>${escapeHtml(d.summary)}</p>`:''}${(d.improvements||[]).length?'<h4>💡 Tavsiyalar</h4>'+d.improvements.map(x=>`<div class="word">${escapeHtml(x)}</div>`).join(''):''}</div>`;
}
async function submitEvidence(){
  const out=$('eResult'); const d=await aiPost('/api/evidence',{topic:$('eTopic').value},out); loadGrowth(); if(!d) return;
  const card=(t,x)=>`<div class="word"><strong>${t}</strong><div class="muted" style="margin-top:4px">${x}</div></div>`;
  out.innerHTML=`<div class="result"><h3>💡 Dalillar banki</h3><p class="muted">${escapeHtml(d.topic)}</p>`+
   card('📊 Statistik dalil',escapeHtml(d.statistical.claim)+'<br><i>Manba: '+escapeHtml(d.statistical.source)+'</i>')+card('🌿 Hayotiy misol',escapeHtml(d.life))+card('🏛 Tarixiy misol',escapeHtml(d.historical))+
   card('🎓 Mutaxassis fikri',escapeHtml(d.expert.claim)+'<br><i>Manba: '+escapeHtml(d.expert.source)+'</i>')+card('🧠 Mantiqiy dalil',escapeHtml(d.logical))+
   '<p class="muted">⚠️ Raqam va manbalarni foydalanishdan oldin tekshiring.</p></div>';
}

// ===== Muallif haqida =====
function authorUser(){ return (ME&&ME.admin_username)||'Sardor_Sayfullayev777'; }
function setAuthorUser(){ $('aUser').textContent='@'+authorUser(); }
function contactAuthor(msg){
  const u='https://t.me/'+authorUser()+'?text='+encodeURIComponent(msg||'');
  try{ if(tg?.openTelegramLink){ tg.openTelegramLink(u); return; } }catch(e){}
  window.open(u,'_blank');
}
