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
  if (id === 'prep') { loadQuiz(); loadPrepResources(); }
  if (id === 'gazal') setupGazal();
  if (id === 'books') loadBooks();
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
  if(active.length){ renderList(active,$('activeResults'),'Faol so‘zlar — '+active.length+' ta'); return; }
  try{active=await (await fetch('active1000.json',{cache:'no-store'})).json(); renderList(active,$('activeResults'),'Faol so‘zlar — '+active.length+' ta');}
  catch(e){console.error(e);$('activeResults').innerHTML='<div class="word">Faol 1000 bazasini yuklashda xatolik.</div>';}
}
function showSuggestions(inputId,boxId,kind){
  const q=normalize($(inputId).value), box=$(boxId);
  if(q.length<3){box.innerHTML='';box.classList.add('hidden');return;}
  const source=kind==='mumtoz'?mumtoz:dict;
  const matches=source.filter(item=>{const w=typeof item==='string'?item:item.word;return normalize(w).startsWith(q);}).slice(0,12);
  box.innerHTML=matches.length?matches.map(item=>{
    const w=typeof item==='string'?item:item.word, meaning=typeof item==='string'?'':item.meaning;
    return `<button class="suggestion" type="button" onclick="chooseSuggestion(${escapeHtml(JSON.stringify(inputId))},${escapeHtml(JSON.stringify(boxId))},${escapeHtml(JSON.stringify(w))},${escapeHtml(JSON.stringify(kind))})"><b>${escapeHtml(w)}</b>${meaning?`<small>${escapeHtml(meaning)}</small>`:''}</button>`;
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
  document.querySelectorAll('.adminOnly').forEach(x=>x.classList.toggle('hidden',!ME.is_admin)); if(ME.is_admin) ['nDeadline','sDeadline'].forEach(id=>{ const s=$(id); if(s&&!s.querySelector('option[value="0"]')) s.insertAdjacentHTML('beforeend','<option value="0">♾ Muddatsiz (faqat admin)</option>'); });
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
    box.innerHTML=arr.length?arr.map(x=>`<div class="testRow"><button class="listbtn" type="button" onclick="startNational(${escapeHtml(JSON.stringify(x.code))})"><b>${x.official?'⭐':'👤'} 🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${escapeHtml(x.subject||'Ona tili va adabiyot')} • ${x.duration_min||180} daqiqa • 45 topshiriq</small>${statusLine(x)}</button>${(x.mine||ME.is_admin)?resBtn('ms',x.code):''}${ME.is_admin?`<button class="delBtn" type="button" onclick="deleteNationalTest(${escapeHtml(JSON.stringify(x.code))})">🗑</button>`:''}</div>`).join(''):'<div class="word">Hozircha e’lon qilingan testlar yo‘q.</div>';
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
  const essayTopic=($('createEssayTopic')?.value||'').trim();
  if(essayTopic.length<8){notify('Esse mavzusini kiriting (kamida 8 belgi).');return;}
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
    const r=await apiFetch(apiUrl('/api/national/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,questions,essay_topic:essayTopic,subject:'Ona tili va adabiyot',duration_min:180,include_essay:true,deadline_hours:Number($('nDeadline')?.value||24)})});
    const d=await r.json();
    if(!d.ok){status.textContent='❌ '+(d.error||'Test yaratilmadi');return;}
    const btnCopy=`<button class="primaryAction" type="button" onclick="copyCode(${escapeHtml(JSON.stringify(d.code))})">📋 Kodni nusxalash</button>`;
    status.innerHTML=`<div class="result"><h3>✅ Test yaratildi!</h3><div class="scoreBig" style="font-size:34px">${escapeHtml(d.code)}</div><p>Shu kodni boshqalarga yuboring. Boshqa talabgorlar testni shu kod orqali ishlab, javoblarini tekshirtirishi mumkin.</p><p class="muted">📝 Esse mavzusi: <b>${escapeHtml(essayTopic)}</b><br>Talabgorlar shu mavzuda yozgan esse bahosi umumiy natijaga qo‘shiladi.</p>${btnCopy}</div>`;
  }catch(e){console.error(e);status.textContent='❌ Server bilan bog‘lanishda xatolik.';}
}

async function startNational(code){
  try{
    const r=await apiFetch(apiUrl('/api/national/test/'+encodeURIComponent(code))); const d=await r.json();
    if(!d.ok){notify(d.error||'Test topilmadi');return;}
    nationalTest=d.test; nationalIndex=0; nationalAnswers={};
    nationalEssayScore=null;
    try{ const er=await apiFetch(apiUrl('/api/national/essay-score/'+encodeURIComponent(nationalUid())+'?code='+encodeURIComponent(nationalTest.code)),{cache:'no-store'}); const ed=await er.json(); nationalEssayScore=ed.ok?ed.essay_score:null; }catch(e){ nationalEssayScore=null; }
    openSection('nationalExam'); renderNationalQuestion();
  }catch(e){console.error(e);notify('Testni ochishda xatolik yuz berdi.');}
}
function renderNationalQuestion(){
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1), saved=nationalAnswers[key], total=nationalTest.questions.length;
  $('nationalProgress').innerHTML=`${nationalIndex+1} / ${total} • ${escapeHtml(q.type)}<div class="bar"><i style="width:${Math.round((nationalIndex+1)/total*100)}%"></i></div>`;
  $('nationalQuestion').innerHTML=(nationalIndex===0?`<div class="result" style="margin:0 0 10px"><b>📝 Esse mavzusi:</b> ${escapeHtml(nationalTest.essay_topic||'ixtiyoriy (oxirgi esse)')}<br><b>Esse bali:</b> ${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'bu mavzuda esse topilmadi — avval botda shu mavzuda esse yozing'}${nationalTest.essay_link&&nationalEssayScore===null?`<br><button class="primaryAction" type="button" onclick="openEssayInBot()">✍️ Esseni botda yozish</button>`:''}</div>`:'') + (q.text?escapeHtml(q.text):`<b>${q.type==='O2'?'45-savol — esse':nationalIndex+1+'-savol: javobni belgilang yoki kiriting'}</b>`);
  let html='';
  if(q.type==='Y1'||q.type==='Y2'){
    const opts=q.options&&q.options.length?q.options:['A','B','C','D'];
    html=`<div class="answers">${opts.map(x=>`<button type="button" class="nopt${saved===x?' selected':''}" data-value="${escapeHtml(x)}">${escapeHtml(x)}</button>`).join('')}</div>`;
  }else if(q.type==='O1') html=`<input id="nopen" placeholder="Javobni aynan yozing" value="${escapeHtml(typeof saved==='string'?saved:'')}">`;
  else if(q.type==='O1AB') html=`<label class="field">a) javob<input id="na" placeholder="a) javobni yozing" value="${escapeHtml(Array.isArray(saved)?saved[0]:'')}"></label><label class="field">b) javob<input id="nb" placeholder="b) javobni yozing" value="${escapeHtml(Array.isArray(saved)?saved[1]:'')}"></label>`;
  else html=`<div class="result"><b>45-savol — esse</b><p class="muted">Bu yerda esse qayta yozilmaydi. Mavzu: «${escapeHtml(nationalTest.essay_topic||'—')}». Talabgorning shu mavzuda botda tekshirtirgan oxirgi esse bali avtomatik hisobga olinadi.</p><div class="scoreBig" style="font-size:32px">${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'Esse bali topilmadi'}</div></div>`;
  $('nationalAnswer').innerHTML=html;
  document.querySelectorAll('.nopt').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nopt').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');nationalAnswers[String(nationalIndex+1)]=b.dataset.value;}));
  const last=nationalIndex===total-1;
  $('btnNext').textContent=last?'Yakunlash ✓':'Keyingi ›';
  $('btnPrev').classList.toggle('hidden',nationalIndex===0);
}
function openEssayInBot(){
  const u=nationalTest&&nationalTest.essay_link; if(!u) return;
  try{ if(tg?.openTelegramLink){ tg.openTelegramLink(u); return; } }catch(e){}
  window.open(u,'_blank');
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
    $('nationalResult').innerHTML=`<button class="back" onclick="openSection('national')">‹ Milliy sertifikat</button><div class="result"><h3>🎓 Diagnostik natija</h3><div class="scoreBig">${d.combined_score_75 ?? d.score_75}/75</div><p><b>Daraja: ${escapeHtml(d.level)}</b></p><p>🧪 Test (${d.rasch?'Rasch T-ball':'taxminiy, foiz'}): <b>${d.score_75}/75</b> • To‘g‘ri javob: ${d.raw_score}/${d.max_score}</p><p>📝 Esse (${escapeHtml(d.essay_topic||'oxirgi esse')}): <b>${d.essay_score!=null?d.essay_score+'/24 → '+d.essay_75+'/75':'topilmadi → 0/75'}</b></p><p class="muted">Umumiy ball = (test + esse) ÷ 2</p>${d.note?`<p class="muted">ℹ️ ${escapeHtml(d.note)}</p>`:''}<h4>❌ Xatolar: ${(d.errors||[]).length}</h4>${(d.errors||[]).map(x=>`<div class="errorCard"><b>${x.number}-savol</b>${x.wrong_parts?` <span class="muted">(${['a','b'].map(k=>k+') '+(x.wrong_parts.includes(k)?'❌':'✅')).join(' • ')} — ${x.earned}/${x.points} ball)</span>`:''}<br>Siz: ${escapeHtml(JSON.stringify(x.user))}<br>To‘g‘ri: ${escapeHtml(JSON.stringify(x.correct))}<br>${escapeHtml(x.explanation||'')}</div>`).join('')}<p class="muted">Bu diagnostik natija. Rasmiy davlat sertifikati emas.</p></div>`;
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
  const map={home:'home',rating:'rating',admin:'home',gazal:'home',books:'home',growth:'home',author:'home',dict:'dict',mumtoz:'dict',paronim:'dict',sinonim:'dict',active:'dict',national:'test',nationalCreate:'test',nationalExam:'test',simpleExam:'test',testResults:'test',simpleResult:'test',nationalResult:'test',stats:'stats'};
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
    box.innerHTML=`<div class="muted">${escapeHtml(d.label)} • ${escapeHtml(d.range)}</div>`+(d.prize_days>0?`<div class="result" style="margin:8px 0">🎁 <b>1-o‘rin sovrini:</b> Premium ${Number(d.prize_days)} kun</div>`:'')+me+(d.top.length?d.top.map(x=>`<div class="word" style="${x.me?'border-color:var(--g3);background:var(--mint)':''}"><strong>${medal(x.rank)} ${escapeHtml(x.name)}</strong><div class="muted">${x.pts} ball • ${x.n} ta topshiriq</div></div>`).join(''):'<div class="word">Bu davrda hali natija yo‘q. Birinchi bo‘ling! 🚀</div>');
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
function gTab(t){ const ids={practice:'gPractice',evidence:'gEvidence',theory:'gTheory'}; Object.keys(ids).forEach(x=>{ $('gt_'+x).classList.toggle('on',x===t); $(ids[x]).classList.toggle('hidden',x!==t); }); if(t==='theory') renderTheory(); }
async function loadGrowth(){
  try{ renderTheory(); }catch(e){}
  try{ const me=await (await apiFetch(apiUrl('/api/me'),{cache:'no-store'})).json(); ME=Object.assign(ME||{},me); if($('packInfo')&&me.pack_size) $('packInfo').textContent=me.pack_size+' ta mashq/dalil — '+me.pack_stars+' ⭐ yoki '+fmtUzs((me.packs&&me.packs[0]&&me.packs[0].uzs)||0)+' so‘m'; const left=Math.max(0,(me.ai_limit||0)-(me.ai_used||0)); $('aiLeft').textContent=left+' / '+(me.ai_limit||0)+' ta bepul qoldi'+((me.ai_credits||0)>0?' • '+me.ai_credits+' ta pullik':''); }catch(e){}
  try{ const d=await (await apiFetch(apiUrl('/api/practice/topic'),{cache:'no-store'})).json(); $('pTopic').textContent=d.topic||'—'; }catch(e){ $('pTopic').textContent='Mavzuni yuklab bo‘lmadi.'; }
}
function pCount(){ const n=($('pEssay').value.trim().match(/\S+/g)||[]).length; $('pWords').textContent=n+' so‘z'+(n<40?' (kamida 40)':''); }
async function aiPost(path,body,out){
  out.innerHTML='<div class="word">⏳ Sun’iy intellekt ishlamoqda, bir daqiqa kuting...</div>';
  try{
    const d=await (await apiFetch(apiUrl(path),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(!d.ok){
      if(d.need_payment){ showPaywall(out,d); return null; }
      out.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return null;
    }
    for(let i=0;i<60;i++){
      await new Promise(r=>setTimeout(r,2000));
      const s=await (await apiFetch(apiUrl('/api/job/'+d.job),{cache:'no-store'})).json();
      if(s.status==='done') return s.data;
      if(s.status==='error'){ out.innerHTML='<div class="result">❌ '+escapeHtml(s.error||'Xatolik')+'</div>'; return null; }
    }
    out.innerHTML='<div class="result">⌛ Javob kechikdi. Birozdan so‘ng qayta urinib ko‘ring.</div>'; return null;
  }catch(e){ out.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; return null; }
}
// ===== Stars paketi: bepul limit tugagach =====
function fmtUzs(n){ return String(n).replace(/\B(?=(\d{3})+(?!\d))/g,' '); }
function showPaywall(out,d){
  const packs=(d.packs&&d.packs.length?d.packs:(ME&&ME.packs&&ME.packs.length?ME.packs:[{id:'p3',size:d.pack_size||3,stars:d.pack_stars||50,uzs:9000}]));
  const rows=packs.map(p=>'<div class="word" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><strong style="flex:1 1 100%">'+p.size+' ta</strong>'+
    '<button class="primaryAction" type="button" style="flex:1" onclick="buyPack(\'tool\',\''+p.id+'\')">⭐ '+p.stars+(p.discount?' (−'+p.discount+'%)':'')+'</button>'+
    '<button class="primaryAction" type="button" style="flex:1" onclick="payByCard(\'tool\',\''+p.id+'\')">💳 '+fmtUzs(p.uzs)+' so‘m</button></div>').join('');
  out.innerHTML='<div class="result"><h3>🔒 Bepul limit tugadi</h3>'+
    '<p>'+escapeHtml(d.error||'')+'</p>'+
    '<p class="muted">✅ Sotib olingan paket muddatsiz saqlanadi. Bepul limit har kuni 00:00 da (Toshkent vaqti) yangilanadi.</p>'+rows+
    '<p class="muted">💳 Karta orqali to‘lov: bot chatida karta raqami beriladi, chek skrinshotini yuborasiz, admin tasdiqlagach avtomatik ochiladi.</p></div>';
}
// Karta orqali to'lov: botda buyurtma ochiladi (karta raqami + chek skrini)
function payByCard(kind,plan){
  const bot=(ME&&ME.bot_username)||'';
  if(!bot){ notify('Karta orqali to‘lash uchun botdagi /paket buyrug‘idan foydalaning.'); return; }
  const url='https://t.me/'+bot+'?start=pay_'+kind+'_'+plan;
  if(tg?.openTelegramLink){ tg.openTelegramLink(url); setTimeout(()=>{ try{ tg.close(); }catch(e){} },400); }
  else window.open(url,'_blank');
}
let _payBusy=false;
async function buyPack(kind,plan){
  if(_payBusy) return; _payBusy=true;
  try{
    if(!tg?.openInvoice){ notify('To‘lov faqat Telegram ichida ishlaydi. Botdagi /balans orqali ham sotib olishingiz mumkin.'); return; }
    const d=await (await apiFetch(apiUrl('/api/pay/invoice'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,plan:plan||'p3'})})).json();
    if(!d.ok||!d.link){ notify(d.error||'To‘lov oynasini ochib bo‘lmadi.'); return; }
    tg.openInvoice(d.link,async status=>{
      if(status==='paid'){
        // Telegram to'lovni botga yetkazguncha biroz kutamiz
        let ok=false;
        for(let i=0;i<8&&!ok;i++){
          await new Promise(r=>setTimeout(r,1200));
          try{ const me=await (await apiFetch(apiUrl('/api/me'),{cache:'no-store'})).json(); if((me.ai_credits||0)>0) ok=true; }catch(e){}
        }
        await loadGrowth();
        ['pResult','eResult'].forEach(id=>{ const el=$(id); if(el && el.innerHTML.includes('Bepul limit tugadi')) el.innerHTML='<div class="result">🎉 To‘lov qabul qilindi. Endi qayta yuboring.</div>'; });
        notify(ok?'🎉 To‘lov qabul qilindi! Endi so‘rovingizni qayta yuboring.':'To‘lov qabul qilindi. Hisob birozdan so‘ng yangilanadi.');
      }else if(status==='failed'){ notify('To‘lov amalga oshmadi. Qayta urinib ko‘ring.'); }
    });
  }catch(e){ notify('To‘lov oynasini ochishda xatolik.'); }
  finally{ _payBusy=false; }
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


// ===== G'azal kursi: guruhga qo'shilish (faqat karta orqali, 15 000 so'm) =====
function setupGazal(){
  const price=(ME&&ME.gazal_price)||15000;
  const el=$('gazalPrice'); if(el) el.textContent=fmtUzs(price)+' so‘m';
  const b=$('gazalJoinBtn'); if(!b) return;
  if(ME&&ME.gazal_joined){ b.textContent='✅ Siz guruhga qabul qilingansiz — havolani olish'; }
  else b.textContent='🌙 Guruhga qo‘shilish';
}
function joinGazal(){ payByCard('group','gazal'); }


// ===== Diagnostik test: Milliy sertifikat / Oddiy testlar =====
function dTab(t){
  $('dt_ms').classList.toggle('on',t==='ms'); $('dt_simple').classList.toggle('on',t==='simple');
  $('dMs').classList.toggle('hidden',t!=='ms'); $('dSimple').classList.toggle('hidden',t!=='simple');
  if(t==='simple') loadSimpleTests();
}
async function loadSimpleTests(){
  const box=$('simpleTests'); box.innerHTML='<div class="word">⏳ Testlar yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/simple/tests'),{cache:'no-store'})).json(); const arr=d.tests||[];
    box.innerHTML=arr.length?arr.map(x=>`<div class="testRow"><button class="listbtn" type="button" onclick="startSimple(${escapeHtml(JSON.stringify(x.code))})"><b>📝 🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${x.subject?escapeHtml(x.subject)+' • ':''}${x.n} savol • ${x.attempts} marta ishlangan</small>${statusLine(x)}</button>${(x.mine||ME.is_admin)?resBtn('simple',x.code):''}${(ME.is_admin||x.mine)?`<button class="delBtn" type="button" onclick="deleteSimple(${escapeHtml(JSON.stringify(x.code))})">🗑</button>`:''}</div>`).join(''):'<div class="word">Hozircha oddiy testlar yo‘q.</div>';
  }catch(e){ box.innerHTML='<div class="word">Testlarni yuklashda xatolik.</div>'; }
}
function simpleByCode(){ const c=($('sCodeInput')?.value||'').trim().toUpperCase(); if(!c){notify('Test kodini kiriting.');return;} startSimple(c); }
let simpleTest=null, simpleAnswers={}, simpleBusy=false;
async function startSimple(code){
  try{
    const d=await (await apiFetch(apiUrl('/api/simple/test/'+encodeURIComponent(code)))).json();
    if(!d.ok){ notify(d.error||'Test topilmadi.'); return; }
    simpleTest=d.test; simpleAnswers={};
    openSection('simpleExam'); renderSimple();
  }catch(e){ notify('Testni yuklashda xatolik.'); }
}
function renderSimple(){
  const t=simpleTest, L='ABCDEF';
  $('sxTitle').textContent='📝 '+t.title;
  $('sxInfo').textContent=(t.subject?t.subject+' • ':'')+t.questions.length+' ta savol • belgilangani: 0';
  $('sxQuestions').innerHTML=t.questions.map(q=>`<div class="qcard" id="sq${q.number}"><div class="qtop">${q.number}-savol</div><div class="question">${escapeHtml(q.text)}</div><div class="answers">${q.options.map((o,i)=>`<button type="button" class="sopt" data-q="${q.number}" data-v="${L[i]}"><b>${L[i]}</b> ${escapeHtml(o)}</button>`).join('')}</div></div>`).join('');
  document.querySelectorAll('.sopt').forEach(b=>b.addEventListener('click',()=>{
    const q=b.dataset.q; document.querySelectorAll('.sopt[data-q="'+q+'"]').forEach(x=>x.classList.remove('selected')); b.classList.add('selected');
    simpleAnswers[q]=b.dataset.v; $('sxInfo').textContent=(t.subject?t.subject+' • ':'')+t.questions.length+' ta savol • belgilangani: '+Object.keys(simpleAnswers).length;
  }));
}
async function submitSimple(){
  if(simpleBusy||!simpleTest) return;
  const blank=simpleTest.questions.filter(q=>!simpleAnswers[String(q.number)]).length;
  const go=async()=>{
    simpleBusy=true; $('sxSubmit').disabled=true;
    try{
      const d=await (await apiFetch(apiUrl('/api/simple/submit'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:simpleTest.code,answers:simpleAnswers})})).json();
      openSection('simpleResult');
      if(!d.ok){ $('sxResult').innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
      $('sxResult').innerHTML=`<div class="result"><h3>📝 ${escapeHtml(simpleTest.title)}</h3><div class="scoreBig">${d.percent}%</div><p><b>To‘g‘ri javoblar: ${d.correct} / ${d.total}</b></p><h4>❌ Xatolar: ${d.errors.length}</h4>${d.errors.map(x=>`<div class="errorCard"><b>${x.number}-savol</b><br>${escapeHtml(x.text)}<br>Siz: <b>${escapeHtml(x.user)}</b><br>To‘g‘ri: <b>${escapeHtml(x.correct)}) ${escapeHtml(x.correct_text)}</b>${x.explanation?'<br><span class="muted">'+escapeHtml(x.explanation)+'</span>':''}</div>`).join('')||'<p>🎉 Barcha javoblar to‘g‘ri!</p>'}</div>`;
    }catch(e){ notify('Natijani yuborishda xatolik.'); }
    finally{ simpleBusy=false; $('sxSubmit').disabled=false; }
  };
  if(blank>0){ const msg=blank+' ta savolga javob berilmagan. Baribir yakunlaysizmi?'; if(tg?.showConfirm) tg.showConfirm(msg,ok=>{if(ok)go();}); else if(confirm(msg)) go(); }
  else go();
}
async function deleteSimple(code){
  const go=()=>apiFetch(apiUrl('/api/simple/delete'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})}).then(r=>r.json()).then(d=>{ if(d.ok) loadSimpleTests(); else notify('Xatolik'); });
  if(tg?.showConfirm) tg.showConfirm(code+' testini o‘chiraysizmi?',ok=>{if(ok)go();}); else if(confirm(code+' testini o‘chiraysizmi?')) go();
}
// Admin: matndan savollarni ajratib olish
function parseSimple(text){
  const L='ABCDEF', qs=[]; let cur=null; const errs=[];
  const flush=()=>{ if(cur){ qs.push(cur); cur=null; } };
  text.replace(/\r/g,'').split('\n').forEach(raw=>{
    const line=raw.trim(); if(!line) return;
    let m;
    if((m=line.match(/^(?:Javob|Жавоб|Answer)\s*[:\-]\s*([A-Fa-f])\b/i))&&cur){ cur.answer=m[1].toUpperCase(); return; }
    if((m=line.match(/^Izoh\s*[:\-]\s*(.+)$/i))&&cur){ cur.explanation=m[1]; return; }
    if((m=line.match(/^([A-Fa-f])\s*[\)\.]\s*(.+)$/))&&cur){ cur.options.push(m[2].trim()); return; }
    if((m=line.match(/^\d+\s*[\.\)]\s*(.+)$/))){ flush(); cur={text:m[1].trim(),options:[],answer:'',explanation:''}; return; }
    if(cur&&!cur.options.length) cur.text+=' '+line;
  });
  flush();
  qs.forEach((q,i)=>{ if(q.options.length<2) errs.push((i+1)+'-savolda variantlar yetarli emas'); else if(!q.answer) errs.push((i+1)+'-savolda «Javob: X» yo‘q'); else if(L.indexOf(q.answer)>=q.options.length) errs.push((i+1)+'-savolning javobi variantlar orasida yo‘q'); });
  return {qs,errs};
}
let parsedSimple=null;
function previewSimple(){
  const {qs,errs}=parseSimple($('sBulk').value||''); parsedSimple=null; $('sCreateBtn').classList.add('hidden');
  if(!qs.length){ $('sPreview').textContent='❌ Savol topilmadi. Namunadagi ko‘rinishda yozing.'; return; }
  if(errs.length){ $('sPreview').innerHTML='❌ Topilgan savollar: '+qs.length+'<br>'+errs.slice(0,6).map(escapeHtml).join('<br>'); return; }
  parsedSimple=qs; $('sPreview').textContent='✅ '+qs.length+' ta savol to‘g‘ri aniqlandi.'; $('sCreateBtn').classList.remove('hidden');
}
async function createSimple(){
  const title=($('sTitle').value||'').trim(); if(!title){notify('Test nomini kiriting.');return;} if(!parsedSimple){previewSimple();if(!parsedSimple)return;}
  try{
    const d=await (await apiFetch(apiUrl('/api/simple/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,subject:($('sSubject').value||'').trim(),questions:parsedSimple,deadline_hours:Number($('sDeadline')?.value||24)})})).json();
    if(!d.ok){ $('sPreview').textContent='❌ '+(d.error||'Xatolik'); return; }
    $('sPreview').innerHTML='✅ Test yaratildi. Kod: <b>'+escapeHtml(d.code)+'</b> ('+d.count+' savol)'; $('sBulk').value=''; $('sTitle').value=''; $('sCreateBtn').classList.add('hidden'); parsedSimple=null; loadSimpleTests();
  }catch(e){ $('sPreview').textContent='❌ Server bilan bog‘lanishda xatolik.'; }
}


// ===== Test muddati, kuzatuv va natijalar fayli =====
function fmtDT(iso){ try{ const d=new Date(iso); return d.toLocaleString('uz-UZ',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}); }catch(e){ return iso||''; } }
function statusLine(x){
  if(x.closed) return '<small>🏁 Yakunlangan — javob qabul qilinmaydi</small>';
  if(x.closes_at) return '<small>⏳ Tugash: '+escapeHtml(fmtDT(x.closes_at))+'</small>';
  return '<small>♾ Muddatsiz (muallif yakunlaydi)</small>';
}
function resBtn(kind,code){ return `<button class="delBtn" style="color:#075b43;border-color:#bfe3d3;background:#eef8f3" type="button" title="Natijalar" onclick="openResults(${escapeHtml(JSON.stringify(kind))},${escapeHtml(JSON.stringify(code))})">📊</button>`; }
let resCtx={kind:'',code:''};
async function openResults(kind,code){
  resCtx={kind,code}; openSection('testResults');
  const box=$('trBody'); box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/test/results?kind='+encodeURIComponent(kind)+'&code='+encodeURIComponent(code)),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    const ps=d.participants||[]; const users=new Set(ps.map(p=>p.username||p.name)).size;
    const state=d.closed?('🏁 Yakunlangan'+(d.finished_at?' • '+fmtDT(d.finished_at):'')):(d.closes_at?('⏳ Davom etmoqda • tugash: '+fmtDT(d.closes_at)):'♾ Davom etmoqda (muddatsiz)');
    box.innerHTML=`<div class="result"><b>📝 ${escapeHtml(d.title)}</b><p class="muted">Kod: ${escapeHtml(d.code)}<br>${escapeHtml(state)}<br>👥 Ishtirokchilar: ${users} • urinishlar: ${ps.length}</p>
      <button class="primaryAction" type="button" onclick="sendResultsFile()">📄 Natijalar faylini olish (Excel)</button>
      ${d.closed?'':'<button class="primaryAction" style="background:linear-gradient(135deg,#b3412f,#8e2c1d)" type="button" onclick="finishTest()">🏁 Testni yakunlash</button>'}
      <p class="muted">Fayl botga yuboriladi: ism, familiya, natija va xato qilingan savollar raqamlari.</p></div>
      <h3 style="margin:14px 0 6px">👥 Kim ishladi</h3>`+(ps.length?ps.map((p,i)=>`<div class="errorCard" style="background:#fff;border-color:var(--line)"><b>${i+1}. ${escapeHtml(p.name||'—')}</b> ${p.username?'<span class="muted">'+escapeHtml(p.username)+'</span>':''}<br>Natija: <b>${escapeHtml(p.score)}</b> (${p.percent}%)${p.level?' • '+escapeHtml(p.level):''}<br>❌ Xatolar: ${p.errors.length?escapeHtml(p.errors.join(', ')):'yo‘q 🎉'}<br><span class="muted">${p.attempt}-urinish • ${escapeHtml(p.at)}</span></div>`).join(''):'<div class="word">Hozircha hech kim ishlamagan.</div>');
  }catch(e){ box.innerHTML='<div class="result">❌ Yuklashda xatolik.</div>'; }
}
async function sendResultsFile(){
  try{
    const d=await (await apiFetch(apiUrl('/api/test/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(resCtx)})).json();
    notify(d.ok?'📄 Fayl botga yuborildi. Telegram chatini oching.':(d.error||'Xatolik'));
  }catch(e){ notify('Xatolik yuz berdi.'); }
}
function finishTest(){
  const go=async()=>{
    try{
      const d=await (await apiFetch(apiUrl('/api/test/finish'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(resCtx)})).json();
      notify(d.ok?(d.already?'Test avval yakunlangan.':'🏁 Test yakunlandi. Natijalar fayli botga yuborildi.'):(d.error||'Xatolik'));
      openResults(resCtx.kind,resCtx.code);
    }catch(e){ notify('Xatolik yuz berdi.'); }
  };
  const msg='Testni yakunlaysizmi? Keyin hech kim javob topshira olmaydi va natijalar fayli yuboriladi.';
  if(tg?.showConfirm) tg.showConfirm(msg,ok=>{if(ok)go();}); else if(confirm(msg)) go();
}


// ===== Badiiy asarlar (pullik, 5 000 so'm) =====
let BK={ready:false,is_admin:false,has_access:false,price:5000,items:[]}; const _bUrls={};
async function bookBlob(kind,n){
  const key=kind+n; if(_bUrls[key]) return _bUrls[key];
  const r=await apiFetch(apiUrl('/api/books/'+kind+'/'+n),{cache:'force-cache'}); if(!r.ok) throw new Error('x');
  return _bUrls[key]=URL.createObjectURL(await r.blob());
}
async function loadBooks(){
  try{ BK=await (await apiFetch(apiUrl('/api/books/list'),{cache:'no-store'})).json(); }catch(e){ return; }
  const adm=BK.is_admin, show=BK.ready||adm;
  $('bProgress').classList.toggle('hidden',show);
  $('bAdmin').classList.toggle('hidden',!adm);
  if(adm){ $('bAdminInfo').textContent=BK.ready?'Bo‘lim hamma uchun ochiq (pullik).':'Foydalanuvchilarga hozir «Jarayonda» yozuvi ko‘rinadi. Siz hammasini ko‘ryapsiz.'; $('bToggle').textContent=BK.ready?'🚧 Jarayonda holatiga qaytarish':'✅ Foydalanuvchilar uchun ochish'; }
  $('bPay').classList.toggle('hidden',!(show&&!BK.has_access&&BK.ready));
  $('bPrice').textContent=fmtUzs(BK.price||5000)+' so‘m';
  const g=$('bGrid');
  if(show&&!(BK.items||[]).length){ g.innerHTML='<div class="word">Hali asar qo‘shilmagan.'+(adm?'<br><br>Botga o‘ting va <b>/asar</b> buyrug‘ini yuboring, so‘ng rasmni asar nomi (izoh) bilan yuboring.':'')+'</div>'; return; }
  g.innerHTML=show?(BK.items||[]).map(it=>`<button class="bCard" type="button" onclick="openBook(${it.n})"><div class="bThumb" id="bt${it.n}"><span>⏳</span></div><span class="bName">${escapeHtml(it.title)}</span>${(BK.has_access||adm)?'':'<i class="bLock">🔒</i>'}</button>`).join(''):'';
  if(show) (BK.items||[]).forEach(async it=>{ try{ const u=await bookBlob('thumb',it.n); const el=$('bt'+it.n); if(el) el.innerHTML='<img src="'+u+'" alt="">'; }catch(e){} });
}
async function toggleBooks(){
  try{ const d=await (await apiFetch(apiUrl('/api/books/ready'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ready:!BK.ready})})).json(); if(d.ok) loadBooks(); else notify(d.error||'Xatolik'); }catch(e){ notify('Xatolik'); }
}
async function openBook(n){
  const it=(BK.items||[]).find(x=>x.n===n); if(!it) return;
  if(!(BK.has_access||BK.is_admin)){ notify('🔒 Asarlarni ko‘rish uchun bo‘limni oching: '+fmtUzs(BK.price)+' so‘m.'); const p=$('bPay'); if(p) p.scrollIntoView({behavior:'smooth',block:'center'}); return; }
  $('bvTitle').textContent=it.title; $('bvImg').classList.remove('zoomed'); $('bvImg').removeAttribute('src');
  $('bookViewer').classList.remove('hidden'); document.body.style.overflow='hidden';
  try{ $('bvImg').src=await bookBlob('img',n); }catch(e){ notify('Rasmni yuklab bo‘lmadi.'); closeBook(); }
}
function closeBook(){ $('bookViewer').classList.add('hidden'); document.body.style.overflow=''; }
function zoomBook(){ $('bvImg').classList.toggle('zoomed'); }
