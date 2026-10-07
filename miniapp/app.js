const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
window.addEventListener("load",()=>loadMe().then(openSharedTest));

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
  if (id === 'rating') { loadRating('day'); loadNationalTests(); loadStreakCal(); }
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
  renderRefCard(); renderStreak();
}

// ===== Ulashish: test havolasi, natija, taklif =====
function testLink(code){ return ME.bot_username?('https://t.me/'+ME.bot_username+'?start=test_'+encodeURIComponent(code)):''; }
function openShare(link,text){
  const u='https://t.me/share/url?url='+encodeURIComponent(link)+'&text='+encodeURIComponent(text);
  if(tg?.openTelegramLink) tg.openTelegramLink(u); else window.open(u,'_blank');
}
function shareTest(code,title){
  const l=testLink(code); if(!l){ notify('Havola hozircha tayyor emas. Birozdan so‘ng urinib ko‘ring.'); return; }
  openShare(l,'📝 '+(title?('«'+title+'» — '):'')+'testini ishlang va natijangizni darhol biling. Kod: '+code);
}
function shareResult(code,title,line){
  const l=testLink(code); if(!l){ notify('Havola hozircha tayyor emas.'); return; }
  openShare(l,'🏆 Men «'+title+'» testida '+line+' natija oldim! Sen ham o‘zib keta olasanmi?');
}
function shBtn(code,title){ return `<button class="delBtn" style="color:#0b5ea8;border-color:#c5dcf2;background:#eff6fd" type="button" title="Testni ulashish" onclick="shareTest(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))})">📤</button>`; }
function shareCard(code,title,line){ return `<div class="result"><h4>🏁 Do‘stlaringiz bilan bellashing</h4><p class="muted">Natijangizni yuboring — do‘stlaringiz shu testni ishlab, sizdan o‘zib ketishga harakat qilishadi.</p><button class="primaryAction" type="button" onclick="shareResult(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))},${escapeHtml(JSON.stringify(line))})">📤 Do‘stlarga yuborish</button></div>`; }
function shareCreated(code,title){ return `<button class="primaryAction" type="button" style="background:linear-gradient(135deg,#1d74c9,#0b4f8f)" onclick="shareTest(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))})">📤 Testni ulashish (havola)</button><button class="primaryAction" type="button" style="background:linear-gradient(135deg,#6b4cc3,#43297f)" onclick="showQR(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))})">📱 QR-kod</button><p class="muted">O‘quvchilar havolani bosganda to‘g‘ri testga tushadi va botga avtomatik ro‘yxatdan o‘tadi. Havola orqali kelgan yangi o‘quvchi testni ishlasa, sizga bepul esse tekshiruvi beriladi.</p>`; }
let sharedTestOpened=false;
function openSharedTest(){
  if(sharedTestOpened) return;
  let code=new URLSearchParams(location.search).get('test')||'';
  if(!code){ const sp=tg?.initDataUnsafe?.start_param||''; if(sp.startsWith('test_')) code=sp.slice(5); }
  code=code.trim().toUpperCase().replace(/[^A-Z0-9-]/g,'');
  if(!code) return; sharedTestOpened=true;
  if(code.startsWith('T-')) startSimple(code); else startNational(code);
}
function renderRefCard(){
  const c=$('refCard'); if(!c) return;
  if(!ME.ok||!ME.ref_link){ c.classList.add('hidden'); return; }
  const st=ME.ref_stats||{invited:0,rewarded:0,left:0};
  $('refSub').textContent='Do‘stingiz +'+(ME.ref_invitee_bonus||1)+' ta, birinchi esseni tekshirtirsa siz +'+(ME.ref_inviter_bonus||1)+' ta bepul esse tekshiruvi olasiz.';
  $('refStats').innerHTML='👥 Taklif qilganlar: <b>'+st.invited+'</b> • 🎁 Mukofot olingan: <b>'+st.rewarded+'</b>'+(st.left>0?' • yana '+st.left+' ta mumkin':'');
  c.classList.remove('hidden');
}
function shareRef(){ if(!ME.ref_link){ notify('Havola hozircha tayyor emas.'); return; } openShare(ME.ref_link,'✍️ Esseni sun’iy intellekt bilan tekshiring — Milliy sertifikat (ona tili) uchun. Bepul sinab ko‘ring:'); }
function copyRef(){ if(!ME.ref_link) return; try{ navigator.clipboard.writeText(ME.ref_link); notify('Havola nusxalandi.'); }catch(e){ notify(ME.ref_link); } }
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
    box.innerHTML=arr.length?arr.map(x=>`<div class="testRow"><button class="listbtn" type="button" onclick="startNational(${escapeHtml(JSON.stringify(x.code))})"><b>${x.official?'⭐':'👤'} 🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${escapeHtml(x.subject||'Ona tili va adabiyot')} • ${x.duration_min||180} daqiqa • 45 topshiriq</small>${statusLine(x)}</button>${(x.mine||ME.is_admin)?shBtn(x.code,x.title)+resBtn('ms',x.code):''}${ME.is_admin?`<button class="delBtn" type="button" onclick="deleteNationalTest(${escapeHtml(JSON.stringify(x.code))})">🗑</button>`:''}</div>`).join(''):'<div class="word">Hozircha e’lon qilingan testlar yo‘q.</div>';
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
    status.innerHTML=`<div class="result"><h3>✅ Test yaratildi!</h3><div class="scoreBig" style="font-size:34px">${escapeHtml(d.code)}</div><p>Shu kodni boshqalarga yuboring. Boshqa talabgorlar testni shu kod orqali ishlab, javoblarini tekshirtirishi mumkin.</p><p class="muted">📝 Esse mavzusi: <b>${escapeHtml(essayTopic)}</b><br>Talabgorlar shu mavzuda yozgan esse bahosi umumiy natijaga qo‘shiladi.</p>${btnCopy}${shareCreated(d.code,title)}</div>`;
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
    $('nationalResult').insertAdjacentHTML('beforeend',resultExtras('ms',nationalTest.code,d)+shareCard(nationalTest.code,nationalTest.title,(d.combined_score_75 ?? d.score_75)+'/75 ('+d.level+')'+rankTxt(d)));
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
  const map={home:'home',rating:'rating',admin:'home',gazal:'home',books:'home',growth:'home',author:'home',dict:'dict',mumtoz:'dict',paronim:'dict',sinonim:'dict',active:'dict',national:'test',nationalCreate:'test',nationalExam:'test',simpleExam:'test',testResults:'test',panel:'test',simpleResult:'test',nationalResult:'test',stats:'stats'};
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
    box.innerHTML=arr.length?arr.map(x=>`<div class="testRow"><button class="listbtn" type="button" onclick="startSimple(${escapeHtml(JSON.stringify(x.code))})"><b>📝 🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${x.subject?escapeHtml(x.subject)+' • ':''}${x.n} savol • ${x.attempts} marta ishlangan</small>${statusLine(x)}</button>${(x.mine||ME.is_admin)?shBtn(x.code,x.title)+resBtn('simple',x.code):''}${(ME.is_admin||x.mine)?`<button class="delBtn" type="button" onclick="deleteSimple(${escapeHtml(JSON.stringify(x.code))})">🗑</button>`:''}</div>`).join(''):'<div class="word">Hozircha oddiy testlar yo‘q.</div>';
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
  const info=()=>(t.subject?t.subject+' • ':'')+t.questions.length+' ta savol • belgilangani: '+Object.keys(simpleAnswers).length;
  $('sxInfo').textContent=info();
  const optBtn=(q,o,i)=>`<button type="button" class="sopt" data-q="${q.number}" data-v="${L[i]}"><b>${L[i]}</b>${o===L[i]?'':' '+escapeHtml(o)}</button>`;
  $('sxQuestions').innerHTML=t.questions.map(q=>q.text
    ?`<div class="qcard" id="sq${q.number}"><div class="qtop">${q.number}-savol</div><div class="question">${escapeHtml(q.text)}</div><div class="answers ${q.options.every((o,i)=>o===L[i])?'inlineOpts':''}">${q.options.map((o,i)=>optBtn(q,o,i)).join('')}</div></div>`
    :`<div class="qcard keyq" id="sq${q.number}"><div class="qtop">${q.number}</div><div class="answers">${q.options.map((o,i)=>optBtn(q,o,i)).join('')}</div></div>`).join('');
  document.querySelectorAll('.sopt').forEach(b=>b.addEventListener('click',()=>{
    const q=b.dataset.q; document.querySelectorAll('.sopt[data-q="'+q+'"]').forEach(x=>x.classList.remove('selected')); b.classList.add('selected');
    simpleAnswers[q]=b.dataset.v; $('sxInfo').textContent=info();
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
      $('sxResult').innerHTML=`<div class="result"><h3>📝 ${escapeHtml(simpleTest.title)}</h3><div class="scoreBig">${d.percent}%</div><p><b>To‘g‘ri javoblar: ${d.correct} / ${d.total}</b></p><h4>❌ Xatolar: ${d.errors.length}</h4>${d.errors.map(x=>`<div class="errorCard"><b>${x.number}-savol</b><br>${x.text?escapeHtml(x.text)+'<br>':''}Siz: <b>${escapeHtml(x.user)}</b><br>To‘g‘ri: <b>${escapeHtml(x.correct)}${x.correct_text&&x.correct_text!==x.correct?') '+escapeHtml(x.correct_text):''}</b>${x.explanation?'<br><span class="muted">'+escapeHtml(x.explanation)+'</span>':''}</div>`).join('')||'<p>🎉 Barcha javoblar to‘g‘ri!</p>'}</div>`+resultExtras('simple',simpleTest.code,d)+shareCard(simpleTest.code,simpleTest.title,d.percent+'% ('+d.correct+'/'+d.total+')'+rankTxt(d));
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
    $('sPreview').innerHTML='✅ Test yaratildi. Kod: <b>'+escapeHtml(d.code)+'</b> ('+d.count+' savol)'+shareCreated(d.code,title); $('sBulk').value=''; $('sTitle').value=''; $('sCreateBtn').classList.add('hidden'); parsedSimple=null; loadSimpleTests();
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


// ===== v27: oddiy test — javoblar kaliti (MS testi kabi) =====
function sMode(m){ [['key','Key'],['text','Text']].forEach(([k,K])=>{ $('sMode'+K).classList.toggle('hidden',k!==m); $('sm_'+k).classList.toggle('on',k===m); }); }
let skAns={}, skN=0, skL='ABCD';
function buildSimpleKey(){
  const n=parseInt($('sKeyN').value,10), o=parseInt($('sKeyOpts').value,10)||4;
  if(!(n>=1)||n>1000){ notify('Savollar soni 1 dan 1000 gacha bo‘lsin.'); return; }
  skN=n; skL='ABCDEF'.slice(0,o); skAns={};
  $('sKeyList').innerHTML=Array.from({length:n},(_,k)=>{ const i=k+1;
    return `<div class="skRow" data-n="${i}"><b>${i}</b><div class="skBtns">${skL.split('').map(x=>`<button type="button" data-n="${i}" data-v="${x}">${x}</button>`).join('')}</div><button type="button" class="skTxtBtn" data-t="${i}" title="Savol matni qo‘shish">✏️</button></div><textarea class="skText hidden" id="skt_${i}" rows="2" maxlength="1500" placeholder="${i}-savol matni (ixtiyoriy)"></textarea>`; }).join('');
  $('sKeyBuilder').classList.remove('hidden'); updSkCount();
}
document.addEventListener('click',e=>{
  const b=e.target.closest('#sKeyList button'); if(!b) return;
  if(b.dataset.v){ setSk(b.dataset.n,b.dataset.v); updSkCount(); }
  else if(b.dataset.t){ const t=$('skt_'+b.dataset.t); if(t){ t.classList.toggle('hidden'); if(!t.classList.contains('hidden')) t.focus(); } }
});
function setSk(i,v){ skAns[i]=v; document.querySelectorAll('#sKeyList button[data-n="'+i+'"]').forEach(x=>x.classList.toggle('selected',x.dataset.v===v)); }
function updSkCount(){ $('sKeyCount').textContent='Belgilangan: '+Object.keys(skAns).length+' / '+skN; }
function applyQuickKey(){
  const t=($('sKeyQuick').value||'').toUpperCase().replace(/\s+/g,''); if(!t){ notify('Javoblarni yozing.'); return; }
  if(!skN){ notify('Avval javoblar kartasini tayyorlang.'); return; }
  const ok=new Set(skL.split('')); let cnt=0;
  if(/^[A-F]+$/.test(t)){ for(let i=0;i<t.length&&i<skN;i++){ if(ok.has(t[i])){ setSk(i+1,t[i]); cnt++; } } }
  else { const re=/(\d+)[\-\.\):=,;]*([A-F])/g; let m; while((m=re.exec(t))){ const n=+m[1]; if(n>=1&&n<=skN&&ok.has(m[2])){ setSk(n,m[2]); cnt++; } } }
  updSkCount(); notify(cnt+' ta javob qo‘llandi.');
}
async function createSimpleKey(){
  const title=($('sTitle').value||'').trim(); if(!title){ notify('Test nomini kiriting.'); return; }
  if(!skN){ notify('Avval javoblar kartasini tayyorlang.'); return; }
  const missing=[]; for(let i=1;i<=skN;i++) if(!skAns[i]) missing.push(i);
  if(missing.length){ notify(missing.length+' ta savolning javobi belgilanmagan: '+missing.slice(0,10).join(', ')+(missing.length>10?' ...':'')); const r=document.querySelector('#sKeyList .skRow[data-n="'+missing[0]+'"]'); if(r) r.scrollIntoView({block:'center'}); return; }
  const questions=[]; for(let i=1;i<=skN;i++) questions.push({text:($('skt_'+i)?.value||'').trim(),options:skL.split(''),answer:skAns[i]});
  const st=$('sKeyStatus'); st.textContent='⏳ Test saqlanmoqda...';
  try{
    const d=await (await apiFetch(apiUrl('/api/simple/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,subject:($('sSubject').value||'').trim(),questions,deadline_hours:Number($('sDeadline')?.value||24)})})).json();
    if(!d.ok){ st.textContent='❌ '+(d.error||'Xatolik'); return; }
    st.innerHTML='<div class="result"><h3>✅ Test yaratildi!</h3><div class="scoreBig" style="font-size:34px">'+escapeHtml(d.code)+'</div><p>'+d.count+' ta savol.</p><button class="primaryAction" type="button" onclick="copyCode('+escapeHtml(JSON.stringify(d.code))+')">📋 Kodni nusxalash</button>'+shareCreated(d.code,title)+'</div>';
    $('sKeyList').innerHTML=''; $('sKeyCount').textContent=''; $('sKeyQuick').value=''; $('sTitle').value=''; skAns={}; skN=0; $('sKeyBuilder').classList.add('hidden'); loadSimpleTests();
  }catch(e){ st.textContent='❌ Server bilan bog‘lanishda xatolik.'; }
}

// ===== v27: modal, reyting, natija qo'shimchalari, seriya, ustoz paneli =====
function showModal(html){
  let m=$('modalBg'); if(!m){ m=document.createElement('div'); m.id='modalBg'; m.className='modalBg'; m.addEventListener('click',e=>{ if(e.target===m) closeModal(); }); document.body.appendChild(m); }
  m.innerHTML='<div class="modalBox">'+html+'<button class="primaryAction" style="margin-top:14px" type="button" onclick="closeModal()">Yopish</button></div>';
}
function closeModal(){ const m=$('modalBg'); if(m) m.remove(); }
function copyText(t){ try{ navigator.clipboard.writeText(t); notify('Nusxalandi.'); }catch(e){ notify(t); } }
function rankTxt(d){ return d&&d.rank&&d.rank.rank?(' — '+d.rank.rank+'-o‘rin'):''; }
function resultExtras(kind,code,d){
  let h='';
  if(d.streak&&d.streak.current>0){ ME.streak={current:d.streak.current,best:d.streak.best,done_today:true}; renderStreak(); h+='<p>🔥 <b>'+d.streak.current+' kunlik seriya!</b>'+(d.streak.new_today?' Bugungi mashq hisoblandi.':'')+'</p>'; }
  if(d.rank&&d.rank.rank) h+='<p>🏅 Test reytingida <b>'+d.rank.rank+'-o‘rin</b> ('+d.rank.participants+' ishtirokchi ichida)</p>';
  return '<div class="result">'+h+'<button class="primaryAction" type="button" style="background:linear-gradient(135deg,#c8a85b,#a8872f);color:#2e2403" onclick="openTop('+escapeHtml(JSON.stringify(kind))+','+escapeHtml(JSON.stringify(code))+')">🏆 Test reytingi (TOP-10)</button></div>';
}
async function openTop(kind,code){
  showModal('<div class="word">⏳ Yuklanmoqda...</div>');
  try{
    const d=await (await apiFetch(apiUrl('/api/test/top?kind='+encodeURIComponent(kind)+'&code='+encodeURIComponent(code)),{cache:'no-store'})).json();
    if(!d.ok){ showModal('<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'); return; }
    const val=r=>r.score!=null?r.score+'/75':r.percent+'%';
    const rows=d.top.map(r=>'<div class="topRow '+(r.me?'me':'')+'"><i>'+(r.rank<=3?['🥇','🥈','🥉'][r.rank-1]:r.rank)+'</i><span>'+escapeHtml(r.name)+(r.me?' (siz)':'')+'</span><em>'+val(r)+'</em></div>').join('');
    const meOut=d.me&&!d.top.some(r=>r.me)?'<div class="topRow me"><i>'+d.me.rank+'</i><span>Siz</span><em>'+d.me.percent+'%</em></div>':'';
    showModal('<h3>🏆 Test reytingi</h3><p class="muted">'+d.participants+' ishtirokchi • har bir o‘quvchining eng yaxshi natijasi</p>'+(rows||'<p>Hali natija yo‘q.</p>')+meOut);
  }catch(e){ showModal('<div class="result">❌ Yuklab bo‘lmadi.</div>'); }
}
function renderStreak(){
  const b=$('streakBar'); if(!b) return; const s=ME.streak;
  if(!ME.ok||!s){ b.classList.add('hidden'); return; }
  b.innerHTML=s.current>0
    ?'🔥 <b>'+s.current+' kunlik seriya</b> • eng yaxshisi: '+s.best+(s.done_today?' • bugun ✅':' • bugun mashq qiling, seriya uzilmasin!')
    :'🔥 Seriyani boshlang: bugun test ishlang yoki esse yozing va har kuni davom eting!';
  b.classList.remove('hidden');
}
async function openPanel(){
  openSection('panel'); const box=$('panelBody'); box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/panel'),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    const t=d.totals, J=x=>escapeHtml(JSON.stringify(x));
    const head='<div class="pStats"><div><b>'+t.tests+'</b><small>testlar</small></div><div><b>'+t.users+'</b><small>ishtirokchilar</small></div><div><b>'+t.visits+'</b><small>havolani ochganlar</small></div><div><b>'+t.new_users+'</b><small>havola orqali kelgan yangi</small></div></div>'
      +'<div class="result" style="margin:0 0 10px">🎁 Havola orqali kelib testni ishlagan yangi o‘quvchilar uchun bonusingiz: <b>'+t.bonus+'</b> ta bepul esse tekshiruvi (har biri uchun +'+t.bonus_per_student+').</div>';
    const list=d.tests.length?d.tests.map(x=>'<div class="result" style="margin:8px 0"><b>'+(x.kind==='ms'?'🎓':'📝')+' '+escapeHtml(x.title)+'</b><p class="muted">Kod: '+escapeHtml(x.code)+' • '+(x.closed?'🏁 Yakunlangan':(x.closes_at?'⏳ '+escapeHtml(fmtDT(x.closes_at)):'♾ Muddatsiz'))
      +'<br>👥 '+x.users+' ishtirokchi • '+x.attempts+' urinish • 🔗 '+x.visits+' havola orqali ochgan • 🆕 '+x.new_users+' yangi'+(x.avg!=null?' • '+x.avg+' '+escapeHtml(x.avg_label):'')+'</p>'
      +'<div class="pBtns"><button type="button" onclick="shareTest('+J(x.code)+','+J(x.title)+')">📤 Ulashish</button><button type="button" onclick="showQR('+J(x.code)+','+J(x.title)+')">📱 QR</button><button type="button" onclick="openResults('+J(x.kind)+','+J(x.code)+')">📊 Natijalar</button><button type="button" onclick="openTop('+J(x.kind)+','+J(x.code)+')">🏆 Reyting</button></div></div>').join('')
      :'<div class="word">Hozircha test yaratmagansiz.</div>';
    box.innerHTML=head+list;
  }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; }
}
function showQR(code,title){
  const l=testLink(code); if(!l){ notify('Havola hozircha tayyor emas.'); return; }
  showModal('<h3>📱 Test QR-kodi</h3><p class="muted">'+escapeHtml(title||code)+' • '+escapeHtml(code)+'</p><canvas id="qrCanvas" width="260" height="260"></canvas><div class="linkTxt">'+escapeHtml(l)+'</div><button class="primaryAction" type="button" onclick="copyText('+escapeHtml(JSON.stringify(l))+')">📋 Havolani nusxalash</button><p class="muted">Ekran rasmini oling yoki proyektorda ko‘rsating — o‘quvchi kamerani QR-kodga tutsa, test ochiladi.</p>');
  try{ drawQR($('qrCanvas'),l); }catch(e){ const c=$('qrCanvas'); if(c) c.outerHTML='<p class="muted">QR yaratib bo‘lmadi — havoladan foydalaning.</p>'; }
}

// ===== QR-kod (kutubxonasiz, ECC M, 1–10 versiya) =====
const QRX=(function(){
  const EXP=new Array(512), LOG=new Array(256); let x=1;
  for(let i=0;i<255;i++){ EXP[i]=x; LOG[x]=i; x<<=1; if(x&256) x^=0x11d; }
  for(let i=255;i<512;i++) EXP[i]=EXP[i-255];
  const mul=(a,b)=>(a&&b)?EXP[LOG[a]+LOG[b]]:0;
  function rsGen(n){ let g=[1]; for(let i=0;i<n;i++){ const ng=new Array(g.length+1).fill(0); for(let j=0;j<g.length;j++){ ng[j]^=g[j]; ng[j+1]^=mul(g[j],EXP[i]); } g=ng; } return g; }
  function rsEnc(data,n){ const g=rsGen(n), res=new Array(n).fill(0); for(const b of data){ const f=b^res[0]; res.shift(); res.push(0); if(f) for(let i=0;i<n;i++) res[i]^=mul(g[i+1],f); } return res; }
  const T=[null,[10,[[1,16]]],[16,[[1,28]]],[26,[[1,44]]],[18,[[2,32]]],[24,[[2,43]]],[16,[[4,27]]],[18,[[4,31]]],[22,[[2,38],[2,39]]],[22,[[3,36],[2,37]]],[26,[[4,43],[1,44]]]];
  const AL=[null,[],[6,18],[6,22],[6,26],[6,30],[6,34],[6,22,38],[6,24,42],[6,26,46],[6,28,50]];
  const bit=(v,i)=>((v>>>i)&1)!==0;
  function encode(text){
    const bytes=Array.from(new TextEncoder().encode(text));
    let ver=0;
    for(let v=1;v<=10;v++){ const cap=T[v][1].reduce((a,b)=>a+b[0]*b[1],0)*8; if(4+(v<10?8:16)+8*bytes.length<=cap){ ver=v; break; } }
    if(!ver) throw new Error('matn juda uzun');
    const [ecLen,groups]=T[ver]; const dataCw=groups.reduce((a,b)=>a+b[0]*b[1],0), size=17+4*ver;
    const bits=[]; const put=(val,len)=>{ for(let i=len-1;i>=0;i--) bits.push((val>>>i)&1); };
    put(4,4); put(bytes.length,ver<10?8:16); bytes.forEach(b=>put(b,8));
    put(0,Math.min(4,dataCw*8-bits.length)); while(bits.length%8) bits.push(0);
    const data=[]; for(let i=0;i<bits.length;i+=8){ let b=0; for(let j=0;j<8;j++) b=(b<<1)|bits[i+j]; data.push(b); }
    for(let p=0;data.length<dataCw;p++) data.push(p%2?0x11:0xEC);
    const blocks=[]; let off=0;
    groups.forEach(([cnt,len])=>{ for(let k=0;k<cnt;k++){ const d=data.slice(off,off+len); off+=len; blocks.push({d,e:rsEnc(d,ecLen)}); } });
    const all=[]; const maxD=Math.max(...blocks.map(b=>b.d.length));
    for(let i=0;i<maxD;i++) blocks.forEach(b=>{ if(i<b.d.length) all.push(b.d[i]); });
    for(let i=0;i<ecLen;i++) blocks.forEach(b=>all.push(b.e[i]));
    const mod=Array.from({length:size},()=>new Array(size).fill(false)), fn=Array.from({length:size},()=>new Array(size).fill(false));
    const setF=(xx,yy,v)=>{ mod[yy][xx]=v; fn[yy][xx]=true; };
    for(let i=0;i<size;i++){ setF(6,i,i%2===0); setF(i,6,i%2===0); }
    const finder=(cx,cy)=>{ for(let dy=-4;dy<=4;dy++) for(let dx=-4;dx<=4;dx++){ const d=Math.max(Math.abs(dx),Math.abs(dy)), xx=cx+dx, yy=cy+dy; if(xx>=0&&xx<size&&yy>=0&&yy<size) setF(xx,yy,d!==2&&d!==4); } };
    finder(3,3); finder(size-4,3); finder(3,size-4);
    const ap=AL[ver], last=ap.length-1;
    for(let i=0;i<ap.length;i++) for(let j=0;j<ap.length;j++){
      if((i===0&&j===0)||(i===0&&j===last)||(i===last&&j===0)) continue;
      for(let dy=-2;dy<=2;dy++) for(let dx=-2;dx<=2;dx++) setF(ap[i]+dx,ap[j]+dy,Math.max(Math.abs(dx),Math.abs(dy))!==1);
    }
    const drawFmt=(mask)=>{
      const d=(0<<3)|mask; let rem=d; for(let i=0;i<10;i++) rem=(rem<<1)^((rem>>>9)*0x537);
      const b=((d<<10)|rem)^0x5412;
      for(let i=0;i<=5;i++) setF(8,i,bit(b,i)); setF(8,7,bit(b,6)); setF(8,8,bit(b,7)); setF(7,8,bit(b,8));
      for(let i=9;i<15;i++) setF(14-i,8,bit(b,i));
      for(let i=0;i<8;i++) setF(size-1-i,8,bit(b,i));
      for(let i=8;i<15;i++) setF(8,size-15+i,bit(b,i));
      setF(8,size-8,true);
    };
    drawFmt(0);
    if(ver>=7){ let rem=ver; for(let i=0;i<12;i++) rem=(rem<<1)^((rem>>>11)*0x1F25); const b=(ver<<12)|rem;
      for(let i=0;i<18;i++){ const c=bit(b,i), a=size-11+i%3, bb=Math.floor(i/3); setF(a,bb,c); setF(bb,a,c); } }
    let k=0;
    for(let right=size-1;right>=1;right-=2){ if(right===6) right=5;
      for(let vert=0;vert<size;vert++) for(let j=0;j<2;j++){
        const xx=right-j, up=((right+1)&2)===0, yy=up?size-1-vert:vert;
        if(!fn[yy][xx]&&k<all.length*8){ mod[yy][xx]=bit(all[k>>>3],7-(k&7)); k++; }
      } }
    const masks=[(x,y)=>(x+y)%2===0,(x,y)=>y%2===0,(x,y)=>x%3===0,(x,y)=>(x+y)%3===0,(x,y)=>(Math.floor(x/3)+Math.floor(y/2))%2===0,(x,y)=>x*y%2+x*y%3===0,(x,y)=>(x*y%2+x*y%3)%2===0,(x,y)=>((x+y)%2+x*y%3)%2===0];
    const applyMask=m=>{ for(let y=0;y<size;y++) for(let xx=0;xx<size;xx++) if(!fn[y][xx]&&masks[m](xx,y)) mod[y][xx]=!mod[y][xx]; };
    const penalty=()=>{
      let r=0;
      const line=(get)=>{ for(let a=0;a<size;a++){ let run=1; for(let b=1;b<size;b++){ if(get(a,b)===get(a,b-1)){ run++; if(run===5) r+=3; else if(run>5) r++; } else run=1; }
        const s=[]; for(let b=0;b<size;b++) s.push(get(a,b)?1:0); const str=s.join('');
        for(const pat of ['00001011101','10111010000']){ let q=-1; while((q=str.indexOf(pat,q+1))>=0) r+=40; } } };
      line((a,b)=>mod[a][b]); line((a,b)=>mod[b][a]);
      for(let y=0;y<size-1;y++) for(let xx=0;xx<size-1;xx++){ const c=mod[y][xx]; if(c===mod[y][xx+1]&&c===mod[y+1][xx]&&c===mod[y+1][xx+1]) r+=3; }
      let dark=0; mod.forEach(row=>row.forEach(v=>{ if(v) dark++; })); const tot=size*size;
      r+=(Math.ceil(Math.abs(dark*20-tot*10)/tot)-1)*10; return r;
    };
    let best=0, bestP=1e9;
    for(let m=0;m<8;m++){ applyMask(m); drawFmt(m); const p=penalty(); if(p<bestP){ bestP=p; best=m; } applyMask(m); }
    applyMask(best); drawFmt(best);
    return mod;
  }
  return {encode};
})();
function drawQR(canvas,text){
  const m=QRX.encode(text), n=m.length, quiet=4, sc=Math.max(2,Math.floor(260/(n+quiet*2)));
  canvas.width=canvas.height=(n+quiet*2)*sc; const g=canvas.getContext('2d');
  g.fillStyle='#fff'; g.fillRect(0,0,canvas.width,canvas.height); g.fillStyle='#000';
  for(let y=0;y<n;y++) for(let x=0;x<n;x++) if(m[y][x]) g.fillRect((x+quiet)*sc,(y+quiet)*sc,sc,sc);
}

// ===== v28: seriya kalendari (Reyting sahifasi tepasida) =====
const CAL_MONTHS=['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktyabr','Noyabr','Dekabr'];
let CAL={y:0,m:0,ty:0,tm:0,td:0,inited:false};
async function loadStreakCal(y,m){
  const box=$('streakCal'); if(!box) return;
  try{
    const q=(y&&m)?('?y='+y+'&m='+m):'';
    const d=await (await apiFetch(apiUrl('/api/streak/cal'+q),{cache:'no-store'})).json();
    if(!d.ok){ box.classList.add('hidden'); return; }
    const t=d.today.split('-').map(Number); CAL.ty=t[0]; CAL.tm=t[1]; CAL.td=t[2]; CAL.y=d.year; CAL.m=d.month;
    if(!CAL.inited){
      CAL.inited=true;
      $('calWk').innerHTML=['Du','Se','Ch','Pa','Ju','Sh','Ya'].map(x=>'<div class="calW">'+x+'</div>').join('');
      $('calPv').onclick=()=>{ let y=CAL.y,m=CAL.m-1; if(m<1){m=12;y--;} loadStreakCal(y,m); };
      $('calNx').onclick=()=>{ if(CAL.y===CAL.ty&&CAL.m===CAL.tm) return; let y=CAL.y,m=CAL.m+1; if(m>12){m=1;y++;} loadStreakCal(y,m); };
    }
    renderStreakCal(d); box.classList.remove('hidden');
  }catch(e){ box.classList.add('hidden'); }
}
function renderStreakCal(d){
  const y=d.year,mo=d.month,done=new Set(d.days||[]);
  const first=(new Date(y,mo-1,1).getDay()+6)%7, n=new Date(y,mo,0).getDate();
  const cur=y===CAL.ty&&mo===CAL.tm, past=(y<CAL.ty)||(y===CAL.ty&&mo<CAL.tm);
  let h=''; for(let i=0;i<first;i++) h+='<div class="calC"></div>';
  for(let k=1;k<=n;k++){
    const col=(first+k-1)%7, isD=done.has(k), fut=!past&&!(cur&&k<=CAL.td)&&!(y<CAL.ty);
    let s='';
    if(isD&&col>0&&done.has(k-1)) s+='<div class="calS" style="left:0;right:50%"></div>';
    if(isD&&col<6&&done.has(k+1)) s+='<div class="calS" style="left:50%;right:0"></div>';
    h+='<div class="calC'+(isD?' d':'')+(fut?' f':'')+(cur&&k===CAL.td?' t':'')+'">'+s+'<span>'+k+'</span></div>';
  }
  $('calGr').innerHTML=h;
  $('calMn').textContent=CAL_MONTHS[mo-1]+' '+y;
  $('calMc').textContent=done.size+' kun';
  $('calCur').textContent=d.current>0?(d.current+' kunlik seriya'):'Seriyani boshlang';
  $('calSub').textContent='Eng yaxshisi: '+d.best+' kun';
  const td=$('calTd'); td.textContent=d.done_today?'Bajarildi ✅':'Hali yo‘q'; td.style.color=d.done_today?'#0b7656':'#a8741a';
  $('calNx').style.opacity=cur?'.35':'1';
}
