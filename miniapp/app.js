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
  if (id === 'tests') loadQuestions();
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
  try{active=await (await fetch('active1000.json',{cache:'no-store'})).json(); renderList(active.slice(0,80),$('activeResults'),'Faol 1000 — manba asosida tanlangan');}
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
  renderList(q.length<1?active.slice(0,80):active.filter(w=>normalize(w).startsWith(q)).slice(0,80),$('activeResults'),'Faol 1000');
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
