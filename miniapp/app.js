const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

let dict = [], mumtoz = [], active = [], questions = [];
let quizIndex = 0, quizScore = 0, quizLocked = false;
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
  if (id === 'active') loadActive();
  if (id === 'theory') renderTheory();
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
async function loadQuestions(){
  if(questions.length)return;
  try{questions=await (await fetch('test_questions.json',{cache:'no-store'})).json();}
  catch(e){console.error(e);$('quiz').innerHTML='<div class="word">Test bazasini yuklashda xatolik.</div>';}
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

async function startTest(n){
  await loadQuestions(); if(!questions.length)return;
  quizIndex=0;quizScore=0;quizLocked=false;
  const start=(n*17)%questions.length, picked=[];
  for(let i=0;i<n;i++)picked.push(questions[(start+i*37)%questions.length]);
  questions._current=picked; renderQuestion();
}
function renderQuestion(){
  const bank=questions._current||[];
  if(quizIndex>=bank.length){const pct=Math.round(quizScore/bank.length*100);$('quiz').innerHTML=`<div class="result"><h3>Natija</h3><p><b>${quizScore}/${bank.length}</b> ta to‘g‘ri javob.</p><p>Aniqlik: <b>${pct}%</b></p><p class="muted">To‘g‘ri javoblar 2013-yilgi “O‘zbek tilining imlo lug‘ati” yozuvlari asosida.</p><button class="testOptions" onclick="startTest(${bank.length})">Qayta ishlash</button></div>`;return;}
  const q=bank[quizIndex];
  $('quiz').innerHTML=`<div class="qcard"><div class="qtop">${quizIndex+1} / ${bank.length}</div><div class="question">${escapeHtml(q.question)}</div><div class="answers">${q.options.map((o,j)=>`<button type="button" onclick="answerQuestion(${j})">${String.fromCharCode(65+j)}) ${escapeHtml(o)}</button>`).join('')}</div><div class="muted source">Manba: ${escapeHtml(q.source)}</div></div>`;
}
function answerQuestion(index){
  if(quizLocked)return;quizLocked=true;
  const q=questions._current[quizIndex], buttons=document.querySelectorAll('.answers button'), chosen=q.options[index];
  buttons.forEach(b=>b.disabled=true);
  if(normalize(chosen)===normalize(q.answer)){buttons[index].classList.add('correct');quizScore++;}
  else{buttons[index].classList.add('wrong');q.options.forEach((o,j)=>{if(normalize(o)===normalize(q.answer))buttons[j].classList.add('correct');});}
  setTimeout(()=>{quizIndex++;quizLocked=false;renderQuestion();},450);
}

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
async function sendGrowth(action){
  const payload=JSON.stringify({action:"growth",type:action});
  if(tg?.sendData){ tg.sendData(payload); return; }
  alert("Bu funksiya Telegram Mini App ichida ishlaydi.");
}
async function loadStats(){
  const box=$('statsContent');
  const uid=tg?.initDataUnsafe?.user?.id;
  if(!uid){box.innerHTML='<div class="result">Telegram foydalanuvchi ma’lumoti topilmadi.</div>';return;}
  try{
    const r=await fetch('/api/stats/'+encodeURIComponent(uid),{cache:'no-store'});
    const d=await r.json();
    if(!d.ok) throw new Error(d.error||'Xatolik');
    const s=d.stats||{};
    box.innerHTML=`<div class="stats-grid">
      <div class="stat"><b>${s.total_checks||0}</b><small>Tekshirilgan esse</small></div>
      <div class="stat"><b>${Number(s.avg_score||0).toFixed(1)}</b><small>O‘rtacha ball</small></div>
      <div class="stat"><b>${s.best_score||0}</b><small>Eng yuqori ball</small></div>
    </div>
    <div class="result"><h3>📈 Rivojlanish</h3><p>Oxirgi natijalar botdagi mavjud statistika bazasidan olinadi.</p></div>`;
  }catch(e){
    box.innerHTML='<div class="result">Statistikani yuklashda xatolik yuz berdi.</div>';
  }
}
let nationalTest=null, nationalIndex=0, nationalAnswers={}, nationalEssayScore=null;

async function loadNationalTests(){
  const box=$('nationalTests'); box.innerHTML='<div class="word">⏳ Testlar yuklanmoqda...</div>';
  try{
    const r=await fetch('/api/national/tests',{cache:'no-store'}); const d=await r.json();
    const arr=d.tests||[];
    box.innerHTML=arr.length?arr.map(x=>`<button class="listbtn" type="button" onclick="startNational(${JSON.stringify(x.code)})"><b>🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${escapeHtml(x.subject||'Ona tili va adabiyot')} • ${x.duration_min||180} daqiqa • 45 topshiriq</small></button>`).join(''):'<div class="word">Hozircha e’lon qilingan testlar yo‘q.</div>';
  }catch(e){console.error(e);box.innerHTML='<div class="word">Testlarni yuklashda xatolik.</div>';}
}

function nationalUid(){ return tg?.initDataUnsafe?.user?.id || 0; }

function openNationalCreate(){
  openSection('nationalCreate');
  const box=$('builderQuestions');
  if(box.dataset.ready==='1') return;
  const rows=[];
  for(let i=1;i<=45;i++){
    const type=i<=32?'Y1':(i<=35?'Y2':(i<=44?'O1AB':'O2'));
    if(type==='Y1'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol</b><div class="answerGrid four">${['A','B','C','D'].map(x=>`<button type="button" class="keyBtn" data-q="${i}" data-value="${x}">${x}</button>`).join('')}</div></div>`);
    }else if(type==='Y2'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol (Y-2)</b><p class="muted">To‘g‘ri javobni belgilang</p><div class="answerGrid six">${['A','B','C','D','E','F'].map(x=>`<button type="button" class="keyBtn" data-q="${i}" data-value="${x}">${x}</button>`).join('')}</div></div>`);
    }else if(type==='O1AB'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — ochiq a/b</b><label class="field">a) To‘g‘ri javob<input id="caa${i}" placeholder="Masalan: OCHIQ"></label><label class="field">b) To‘g‘ri javob<input id="cab${i}" placeholder="Masalan: KITOB"></label></div>`);
    }else{
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — esse</b><p class="muted">Javob kaliti kiritilmaydi. Talabgorning botdagi oxirgi esse bali avtomatik olinadi.</p></div>`);
    }
  }
  box.innerHTML=rows.join(''); box.dataset.ready='1';
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
  if(!title){alert('Test nomini kiriting.');return;}
  const questions=[];
  for(let i=1;i<=45;i++){
    const type=i<=32?'Y1':(i<=35?'Y2':(i<=44?'O1AB':'O2'));
    const q={type,points:1};
    if(type==='Y1'||type==='Y2'){
      q.options=type==='Y1'?['A','B','C','D']:['A','B','C','D','E','F'];
      q.answer=selectedKey(i);
      if(!q.answer){alert(`${i}-savolning to‘g‘ri javobini belgilang.`);return;}
    }else if(type==='O1AB'){
      q.a_answers=($(`caa${i}`)?.value||'').split(';').map(x=>x.trim()).filter(Boolean);
      q.b_answers=($(`cab${i}`)?.value||'').split(';').map(x=>x.trim()).filter(Boolean);
      if(!q.a_answers.length||!q.b_answers.length){alert(`${i}-savolning a) va b) to‘g‘ri javoblarini kiriting.`);return;}
    }else{
      q.essay_from_bot=true;
    }
    questions.push(q);
  }
  const status=$('createStatus'); status.textContent='⏳ Test saqlanmoqda...';
  try{
    const r=await fetch('/api/national/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:nationalUid(),title,questions,subject:'Ona tili va adabiyot',duration_min:180,include_essay:true})});
    const d=await r.json();
    if(!d.ok){status.textContent='❌ '+(d.error||'Test yaratilmadi');return;}
    status.innerHTML=`<div class="result"><h3>✅ Test yaratildi!</h3><div class="scoreBig" style="font-size:34px">${escapeHtml(d.code)}</div><p>Shu kodni boshqalarga yuboring. Boshqa talabgorlar testni shu kod orqali ishlab, javoblarini tekshirtirishi mumkin.</p><p class="muted">📝 Esse bali talabgorning botdagi oxirgi esse natijasidan avtomatik olinadi.</p></div>`;
  }catch(e){console.error(e);status.textContent='❌ Server bilan bog‘lanishda xatolik.';}
}

async function startNational(code){
  try{
    const r=await fetch('/api/national/test/'+encodeURIComponent(code)); const d=await r.json();
    if(!d.ok){alert(d.error||'Test topilmadi');return;}
    nationalTest=d.test; nationalIndex=0; nationalAnswers={};
    nationalEssayScore=null;
    try{ const er=await fetch('/api/national/essay-score/'+encodeURIComponent(nationalUid()),{cache:'no-store'}); const ed=await er.json(); nationalEssayScore=ed.ok?ed.essay_score:null; }catch(e){ nationalEssayScore=null; }
    openSection('nationalExam'); renderNationalQuestion();
  }catch(e){console.error(e);alert('Testni ochishda xatolik yuz berdi.');}
}
function renderNationalQuestion(){
  const q=nationalTest.questions[nationalIndex];
  $('nationalProgress').textContent=`${nationalIndex+1} / ${nationalTest.questions.length} • ${q.type}`;
  $('nationalQuestion').innerHTML=(nationalIndex===0?`<div class="result" style="margin-bottom:10px"><b>📝 Esse bali:</b> ${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'topilmadi — avval botda esse tekshirtiring'}</div>`:'') + (q.text?escapeHtml(q.text):`<b>${q.type==='O2'?'45-savol — esse':'Javobni belgilang yoki kiriting'}</b>`);
  let html='';
  if(q.type==='Y1'||q.type==='Y2'){
    const opts=q.options&&q.options.length?q.options:['A','B','C','D'];
    html=`<div class="answers">${opts.map(x=>`<button type="button" class="nopt" data-value="${escapeHtml(x)}">${escapeHtml(x)}</button>`).join('')}</div>`;
  }else if(q.type==='O1') html='<input id="nopen" placeholder="Javobni aynan yozing">';
  else if(q.type==='O1AB') html='<label class="field">a) javob<input id="na" placeholder="a) javobni yozing"></label><label class="field">b) javob<input id="nb" placeholder="b) javobni yozing"></label>';
  else html=`<div class="result"><b>45-savol — esse</b><p class="muted">Bu yerda esse qayta yozilmaydi. Talabgorning botda tekshirtirgan oxirgi esse bali avtomatik hisobga olinadi.</p><div class="scoreBig" style="font-size:32px">${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'Esse bali topilmadi'}</div></div>`;
  $('nationalAnswer').innerHTML=html;
  document.querySelectorAll('.nopt').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nopt').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');nationalAnswers[String(nationalIndex+1)]=b.dataset.value;}));
}
async function nextNational(){
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1);
  if(q.type==='O1') nationalAnswers[key]=($('nopen')?.value||'').trim();
  if(q.type==='O1AB') nationalAnswers[key]=[($('na')?.value||'').trim(),($('nb')?.value||'').trim()];
  if(q.type==='O2') nationalAnswers[key]='__ESSAY_FROM_BOT__';
  const v=nationalAnswers[key];
  if(q.type!=='O2' && (v==null || v==='' || (Array.isArray(v)&&v.some(x=>!x)))){alert('Javobni kiriting.');return;}
  nationalIndex++;
  if(nationalIndex<nationalTest.questions.length){renderNationalQuestion();window.scrollTo(0,0);return;}
  await submitNational();
}
async function submitNational(){
  const uid=nationalUid();
  try{
    const r=await fetch('/api/national/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:nationalTest.code,user_id:uid,answers:nationalAnswers})});
    const d=await r.json();
    openSection('nationalResult');
    if(!d.ok){$('nationalResult').innerHTML='<button class="back" onclick="openSection(\'national\')">‹ Milliy sertifikat</button><div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>';return;}
    $('nationalResult').innerHTML=`<button class="back" onclick="openSection('national')">‹ Milliy sertifikat</button><div class="result"><h3>🎓 Diagnostik natija</h3><div class="scoreBig">${d.combined_score_75 ?? d.score_75}/75</div><p><b>Daraja: ${escapeHtml(d.level)}</b></p><p>Test: ${d.score_75}/75 • To‘g‘ri javob balli: ${d.raw_score}/${d.max_score}</p><p>📝 Botdagi esse bali: ${d.essay_score??'—'}/24</p><h4>❌ Xatolar: ${(d.errors||[]).length}</h4>${(d.errors||[]).map(x=>`<div class="errorCard"><b>${x.number}-savol</b><br>Siz: ${escapeHtml(JSON.stringify(x.user))}<br>To‘g‘ri: ${escapeHtml(JSON.stringify(x.correct))}<br>${escapeHtml(x.explanation||'')}</div>`).join('')}<p class="muted">Bu diagnostik natija. Rasmiy davlat sertifikati emas.</p></div>`;
  }catch(e){openSection('nationalResult');$('nationalResult').innerHTML='<button class="back" onclick="openSection(\'national\')">‹ Milliy sertifikat</button><div class="result">❌ Natijani yuborishda xatolik.</div>';}
}
function nationalCode(){
  const c=prompt('Test kodini kiriting:');
  if(c) startNational(c.trim().toUpperCase());
}
