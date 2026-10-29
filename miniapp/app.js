const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
window.addEventListener("load",()=>loadMe().then(openSharedTest).then(updateAsarHero).then(()=>{loadCertHero();}).then(openDeepLink));

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
const _viewSent={};
function trackView(section){
  try{
    const t=Date.now(); if(_viewSent[section] && t-_viewSent[section]<30000) return; _viewSent[section]=t;   // 30 soniyada bir marta
    if(!tg?.initData) return;
    apiFetch(apiUrl('/api/view'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({section})}).catch(()=>{});
  }catch(e){}
}
function openSection(id) {
  if(!document.getElementById(id)){ goHome(); return; }   // v106: olib tashlangan bo‘limlarga eski havolalar
  if(id!=='bookPage' && !/^(simpleExam|simpleResult|nationalExam|nationalResult|nationalCreate)$/.test(id)) trackView(id);
  document.querySelectorAll('main').forEach(x => x.classList.add('hidden'));
  $(id).classList.remove('hidden');
  if (id === 'dict') loadData();
  if (id === 'mumtoz') loadMumtoz();
  if (id === 'paronim') loadParonim();
  if (id === 'sinonim') loadSinonim();
  if (id === 'omonim') loadOmonim();
  if (id === 'expert') loadExpert();
  if (id === 'active') loadActive();
  if (id === 'prep') { loadQuiz(); loadPrepResources(); }
  if (id === 'gazal') setupGazal();
  if (id === 'books') loadBooks();
  if (id === 'games' && typeof gmOpenHub === 'function') gmOpenHub();
  if (id === 'premium') loadColl('premium');
  if (id === 'essewin') loadColl('esse');
  if (id === 'certwin') loadCert();
  if (id === 'attestwin') loadColl('attest');
  if (id === 'gazallib') loadColl('gazal');
  if (id === 'mgramwin') loadColl('mgram');
  if (id === 'mmatnwin') loadColl('mmatn');
  if (id === 'madabwin') loadColl('madab');
  if (id === 'messewin') loadColl('messe');
  if (id === 'growth') loadGrowth();
  if (id === 'rating') loadStreakHero();
  if (id === 'author') setAuthorUser();
  if (id === 'mock') loadMocks();
  if (id === 'profil') renderProfile();
  if (id === 'national') loadNationalTests();
  if (id === 'rating') { loadRating('day'); loadNationalTests(); }
  if (id === 'admin') { loadAdminPanel(); loadViewStats(); }
  if (id === 'teacher') loadTeacher();
  if (id === 'eq' && typeof loadEq === 'function') loadEq();
  window.scrollTo(0,0);
}
function goHome() { document.querySelectorAll('main').forEach(x=>x.classList.add('hidden')); $('home').classList.remove('hidden'); window.scrollTo(0,0); try{loadHomeMock();}catch(e){} }

async function loadData(){
  if(dict.length)return;
  try{dict=await (await fetch('dictionary.json')).json(); renderList(dict.slice(0,60),$('dictResults'),'2013-yilgi imlo lug‘ati');}
  catch(e){console.error(e);$('dictResults').innerHTML='<div class="word">Imlo lug‘atini yuklashda xatolik.</div>';}
}
async function loadMumtoz(){
  if(mumtoz.length)return;
  try{mumtoz=await (await fetch('mumtoz.json')).json(); renderMumtoz(mumtoz.slice(0,60));}
  catch(e){console.error(e);$('mumtozResults').innerHTML='<div class="word">Mumtoz lug‘atni yuklashda xatolik.</div>';}
}
async function loadActive(){
  if(active.length){ renderList(active,$('activeResults'),'Faol so‘zlar — '+active.length+' ta'); return; }
  try{active=await (await fetch('active1000.json')).json(); renderList(active,$('activeResults'),'Faol so‘zlar — '+active.length+' ta');}
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
// v105: bosh sahifadagi «badiiy asarlar» banneri — soni doim 40, narx bazadan olinadi
// v105: botdagi tugmalardan Mini App'ni kerakli bo‘limda ochish (?go=essewin | gazal | books)
function openDeepLink(){
  try{
    const g=(new URLSearchParams(location.search).get('go')||'').trim();
    if(['essewin','gazal','books','certwin','teacher'].indexOf(g)>=0 && typeof openSection==='function') openSection(g);
  }catch(e){}
}

// ===================== v105: «Rasmiy natija» bo‘limi + bosh sahifa tartibi =====================
let SC=null;
function scDate(s){ if(!s) return null; const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(s); return m? new Date(+m[1],+m[2]-1,+m[3]) : null; }
function scFmt(s){ const d=scDate(s); if(!d) return '—'; const mon=['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr'][d.getMonth()]; return d.getDate()+'-'+mon; }
function scDays(s){ const d=scDate(s); if(!d) return null; const t=new Date(); t.setHours(0,0,0,0); return Math.round((d-t)/86400000); }
async function scLoad(){
  try{ const r=await (await apiFetch(apiUrl('/api/sc/info'),{cache:'no-store'})).json(); if(r&&r.ok){ SC=r; return r; } }catch(e){}
  return SC;
}
async function loadCert(){
  const d=await scLoad(); if(!d){ const x=$('scResult'); if(x) x.innerHTML='<p class="scSub">Ma’lumotni yuklab bo‘lmadi. Telegram ichidan oching va qayta urinib ko‘ring.</p>'; return; }
  const c=d.cfg;
  $('scExam').textContent=c.exam_label;
  // natija kartasi
  let h='<h3>📢 Natija</h3>';
  const rd=c.result_date? scDays(c.result_date):null;
  if(c.result_date){
    h+= (rd>0? '<div class="scBig">'+scFmt(c.result_date)+'</div><p class="scSub">Rasmiy e’lon sanasi • '+rd+' kun qoldi</p>'
        : rd===0? '<div class="scBig ok">Bugun e’lon qilinadi</div><p class="scSub">my.gov.uz da natijani tekshiring.</p>'
        : '<div class="scBig ok">E’lon qilingan</div><p class="scSub">Natijani my.gov.uz → «Mening arizalarim» bo‘limidan ko‘ring, pastdagi kalkulyatorga kiriting.</p>');
  } else {
    h+='<div class="scBig">⏳ Kutilmoqda</div><p class="scSub">Taxminan <b>'+scFmt(c.result_from)+' – '+scFmt(c.result_to)+'</b> (imtihondan keyin ~21 ish kuni ichida). Rasmiy sana e’lon qilinsa shu yerda yangilanadi. Pastdagi eslatmani yoqing — natija chiqqanda xabar beramiz.</p>';
  }
  $('scResult').innerHTML=h;
  // dekabr kartasi
  const dOpen=scDays(c.reg_open), dClose=scDays(c.reg_close);
  let chip='', cls='';
  if(d.reg_state==='before'){ chip='Ro‘yxat boshlanishiga '+dOpen+' kun'; cls='wait'; }
  else if(d.reg_state==='open'){ chip='Ro‘yxat OCHIQ • yopilishiga '+dClose+' kun'; cls='open'; }
  else if(d.reg_state==='closed'){ chip='Ro‘yxat yopilgan'; cls='closed'; }
  let n='<h3>📝 Dekabr sertifikati</h3>'+(chip?'<div class="scChip '+cls+'">'+chip+'</div>':'')
    +'<div class="scRows"><div><span>Ro‘yxatdan o‘tish</span><b>'+scFmt(c.reg_open)+' – '+scFmt(c.reg_close)+'</b></div>'
    +'<div><span>To‘lov muddati</span><b>'+scFmt(c.pay_close)+'gacha</b></div>'
    +'<div><span>Imtihon</span><b>'+scFmt(c.exam_from)+' – '+scFmt(c.exam_to)+'</b></div>'
    +(c.fee?'<div><span>To‘lov miqdori</span><b>'+fmtUzs(c.fee)+' so‘m</b></div>':'')+'</div>'
    +'<p class="scWarn">⚠️ Ro‘yxatdan o‘tish sanasini o‘tkazib yubormang! Hududingizdagi o‘rinlar tugasa, ro‘yxat muddatdan oldin yopilib qoladi — birinchi kunlari ariza topshiring.</p>'
    +'<a class="scLink" href="https://my.gov.uz" target="_blank" rel="noopener">my.gov.uz orqali ro‘yxatdan o‘tish ›</a>';
  $('scNext').innerHTML=n;
  scRenderPrefs();
}
function scRenderPrefs(){
  if(!SC) return;
  const on=new Set(SC.prefs||[]), kinds=SC.kinds||{};
  let h='';
  Object.keys(kinds).forEach(k=>{
    const isOn=on.has(k);
    h+='<button type="button" class="scTg'+(isOn?' on':'')+'" aria-pressed="'+isOn+'" onclick="scPref(\''+k+'\','+(!isOn)+')"><span>'+escapeHtml(kinds[k])+'</span><i></i></button>';
  });
  const all=Object.keys(kinds).every(k=>on.has(k));
  h+='<button type="button" class="scAll" onclick="scPref(\'all\','+(all?'false':'true')+')">'+(all?'Hammasini o‘chirish':'Hammasini yoqish')+'</button>';
  $('scPrefs').innerHTML=h;
}
async function scPref(kind,on){
  try{
    const r=await (await apiFetch(apiUrl('/api/sc/notify'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,on})})).json();
    if(r&&r.ok){ SC.prefs=r.prefs; scRenderPrefs(); if(on) notify('✅ Eslatma yoqildi. Sana kelganda bot xabar yuboradi.'); }
    else notify((r&&r.error)||'Saqlanmadi.');
  }catch(e){ notify('Aloqa xatosi. Qayta urinib ko‘ring.'); scRenderPrefs(); }
}
function scCalc(){
  const v=parseFloat(String($('scBall').value).replace(',','.')), out=$('scCalcOut');
  if(isNaN(v)||v<0||v>75){ out.innerHTML=''; return; }
  const lv=v>=70?'A+':v>=65?'A':v>=60?'B+':v>=55?'B':v>=50?'C+':v>=46?'C':'';
  if(!lv){ out.innerHTML='<div class="scLvBig no">—</div><p class="scSub">46 balldan past natijaga sertifikat berilmaydi.</p>'; return; }
  const pct=v/75*100; let t='<div class="scLvBig">'+lv+'</div><p class="scSub">'+v.toFixed(1)+' / 75 ball ('+pct.toFixed(1)+'%)</p>';
  if(pct>=86) t+='<p class="scAdm">🎓 Kirish imtihonida <b>maksimal ball</b>: 1-blok 93, 2-blok 63; majburiy ona tili bloki 11.</p>';
  else t+='<p class="scAdm">🎓 Proporsional ball: 1-blok ≈ <b>'+(93*pct/100).toFixed(1)+'</b>, 2-blok ≈ <b>'+(63*pct/100).toFixed(1)+'</b> (taxminiy); majburiy ona tili bloki 11.</p>';
  out.innerHTML=t;
}
async function loadCertHero(){
  try{
    if(!tg?.initData) return;
    const d=await scLoad(); if(!d) return;
    const c=d.cfg, el=$('certHeroS'), tt=$('certHeroT'); if(!el) return;
    const dOpen=scDays(c.reg_open), dClose=scDays(c.reg_close);
    if(d.reg_state==='open'){ el.textContent='RO‘YXAT OCHIQ • '+dClose+' kun qoldi'; tt.textContent='Dekabr sertifikatiga ro‘yxatdan o‘tishni o‘tkazib yubormang'; }
    else if(d.reg_state==='before' && dOpen!=null && dOpen<=21){ el.textContent='DEKABR RO‘YXATI • '+dOpen+' kun qoldi'; tt.textContent='Natija, ro‘yxat sanalari va eslatmalar'; }
  }catch(e){}
}
// bosh sahifa bo‘limlari: ko‘p ishlatilgani birinchi; admin qadagani — eng birinchi
async function applyHomeOrder(){
  return; // v106: tugmalar joyi qat'iy (Premium va Attestatsiya Yangi alifbo yonida)
  try{
    const r=await (await apiFetch(apiUrl('/api/home/order'),{cache:'no-store'})).json();
    if(!r||!r.ok||!Array.isArray(r.order)) return;
    r.order.forEach((sec,i)=>{ document.querySelectorAll('#home .grid > button[data-sec="'+sec+'"]').forEach(b=>{ b.style.order=String(i); }); });
  }catch(e){}
}

async function updateAsarHero(){
  try{
    const d=await (await apiFetch(apiUrl('/api/books/list?sec=asar'),{cache:'no-store'})).json();
    const pr=d.price||5000, el=$('asarHeroT');   // asar soni DOIM 40 (ba'zi papkalarda bir nechta asar birlashtirilgan — kartochkalar soni hisoblanmaydi)
    if(el) el.textContent='40 badiiy asar — '+fmtUzs(pr)+' so‘m';
  }catch(e){}
}
async function loadMe(){
  try{ const r=await apiFetch(apiUrl('/api/me'),{cache:'no-store'}); ME=await r.json(); }catch(e){ ME={ok:false,is_admin:false,can_create:false}; }
  document.querySelectorAll('.needCreate').forEach(x=>x.classList.toggle('hidden',!ME.can_create));
  document.querySelectorAll('.adminOnly').forEach(x=>x.classList.toggle('hidden',!ME.is_admin)); if(ME.is_admin) ['nDeadline','sDeadline'].forEach(id=>{ const s=$(id); if(s&&!s.querySelector('option[value="0"]')) s.insertAdjacentHTML('beforeend','<option value="0">♾ Muddatsiz (faqat admin)</option>'); });
  document.querySelectorAll('.nonAdminNote').forEach(x=>x.classList.toggle('hidden',!!ME.can_create));
  document.querySelectorAll('.prepNote').forEach(x=>x.classList.toggle('hidden',!!ME.is_admin));
  document.querySelectorAll('.adminLink').forEach(a=>{ a.textContent=ME.admin_username?'@'+ME.admin_username:'admin'; });
  renderRefCard(); renderStreak(); renderVersion(); try{loadHomeMock();}catch(e){}
  try{ if(typeof clsBoot==='function') clsBoot(); }catch(e){}   // v109: ota-ona rejimida faqat ota-ona bo‘limi
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
function shBtn(code,title){ return `<button class="delBtn" style="color:#0b35a8;border-color:#c5d1f2;background:#eff3fd" type="button" title="Testni ulashish" onclick="shareTest(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))})">📤</button>`; }
function shareCard(code,title,line){ return `<div class="result"><h4>🏁 Do‘stlaringiz bilan bellashing</h4><p class="muted">Natijangizni yuboring — do‘stlaringiz shu testni ishlab, sizdan o‘zib ketishga harakat qilishadi.</p><button class="primaryAction" type="button" onclick="shareResult(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))},${escapeHtml(JSON.stringify(line))})">📤 Do‘stlarga yuborish</button></div>`; }
function shareCreated(code,title){ return `<button class="primaryAction" type="button" style="background:linear-gradient(135deg,#1d4bc9,#0b2e8f)" onclick="shareTest(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))})">📤 Testni ulashish (havola)</button><button class="primaryAction" type="button" style="background:linear-gradient(135deg,#6b4cc3,#43297f)" onclick="showQR(${escapeHtml(JSON.stringify(code))},${escapeHtml(JSON.stringify(title||''))})">📱 QR-kod</button><p class="muted">O‘quvchilar havolani bosganda to‘g‘ri testga tushadi va botga avtomatik ro‘yxatdan o‘tadi. Havola orqali kelgan yangi o‘quvchi testni ishlasa, sizga bepul esse tekshiruvi beriladi.</p>`; }
let sharedTestOpened=false;
function openSharedTest(){
  if(sharedTestOpened) return;
  let code=new URLSearchParams(location.search).get('test')||'';
  if(!code){ const sp=tg?.initDataUnsafe?.start_param||''; if(sp.startsWith('test_')) code=sp.slice(5); }
  code=code.trim().toUpperCase().replace(/[^A-Z0-9-]/g,'');
  if(!code) return; sharedTestOpened=true;
  if(code.startsWith('T-')) startSimple(code); else startNational(code);
}
function renderExamBar(){
  const c=$('examBar'); if(!c) return;
  const d=ME&&ME.exam_date?new Date(ME.exam_date+'T00:00:00'):null;
  if(!d||isNaN(d)){ c.classList.add('hidden'); return; }
  const days=Math.ceil((d-new Date())/86400000);
  if(days<0||days>120){ c.classList.add('hidden'); return; }
  $('examDays').textContent=days===0?'Bugun!':days+' kun';
  $('examTitle').textContent=(ME.exam_name||'Imtihon')+'gacha';
  $('examSub').textContent=days<=14?'Oxirgi haftalar: esseni ekspertga tekshirtiring va paketdan foydalaning.':'Har kuni mashq qiling — natija shunga bog‘liq.';
  c.classList.remove('hidden');
}
function renderRefCard(){
  try{ const cb=$('chanBtn'); if(cb) cb.classList.toggle('hidden',!(ME&&ME.channel_url)); }catch(e){}
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
    const arrAll=d.tests||[]; const arr=msFilterTests(arrAll);   // v108: fan bo‘yicha filtr
    window.__tests=arrAll; if($('ratingTests')) renderRatingTests();
    box.innerHTML=arr.length?arr.map(x=>`<div class="testRow"><button class="listbtn" type="button" onclick="startNational(${escapeHtml(JSON.stringify(x.code))})"><b>${x.official?'⭐':'👤'} 🔑 ${escapeHtml(x.code)}</b><span>${escapeHtml(x.title)}</span><small>${escapeHtml(x.subject||'Ona tili va adabiyot')} • ${x.duration_min||180} daqiqa • 45 topshiriq</small>${statusLine(x)}</button>${(x.mine||ME.is_admin)?shBtn(x.code,x.title)+resBtn('ms',x.code):''}${ME.is_admin?`<button class="delBtn" type="button" onclick="deleteNationalTest(${escapeHtml(JSON.stringify(x.code))})">🗑</button>`:''}</div>`).join(''):'<div class="word">Hozircha e’lon qilingan testlar yo‘q.</div>';
  }catch(e){console.error(e);box.innerHTML='<div class="word">Testlarni yuklashda xatolik.</div>';}
}

function nationalUid(){ return tg?.initDataUnsafe?.user?.id || 0; }

function openNationalCreate(){
  window._mockBuild=false; mockBuildUi();
  openSection('nationalCreate');
  const box=$('builderQuestions');
  if(box.dataset.ready==='1') return;
  const rows=[];
  for(let i=1;i<=45;i++){
    const type=msType(i);
    if(type==='Y1'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol</b><div class="answerGrid four">${['A','B','C','D'].map(x=>`<button type="button" class="keyBtn" data-q="${i}" data-value="${x}">${x}</button>`).join('')}</div></div>`);
    }else if(type==='Y2'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol (Y-2)</b><p class="muted">To‘g‘ri javobni belgilang</p><div class="answerGrid six">${['A','B','C','D','E','F'].map(x=>`<button type="button" class="keyBtn" data-q="${i}" data-value="${x}">${x}</button>`).join('')}</div></div>`);
    }else if(type==='O1'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — ochiq</b><label class="field">To‘g‘ri javob<input id="co${i}" placeholder="Masalan: KITOB/KITOBLAR"></label></div>`);
    }else if(type==='O1AB'){
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — ochiq a/b</b><label class="field">a) To‘g‘ri javob<input id="caa${i}" placeholder="Masalan: NEGAKI/CHUNKI"></label><label class="field">b) To‘g‘ri javob<input id="cab${i}" placeholder="Masalan: ERGASHGAN/ERGASHGAN QO‘SHMA GAP"></label></div>`);
    }else{
      rows.push(`<div class="listbtn builderQ" data-number="${i}"><b>${i}-savol — esse</b><p class="muted">Javob kaliti kiritilmaydi. Talabgorning botdagi oxirgi esse bali avtomatik olinadi.</p></div>`);
    }
  }
  box.innerHTML='<div class="result" style="margin:0 0 10px"><b>⚠️ Ochiq javoblar qoidasi</b><br>• Bir savolga bir nechta to‘g‘ri javob bo‘lsa, ularni <b>/</b> belgisi bilan ajrating: <b>KITOB/KITOBLAR</b>.<br>• Katta-kichik harf va <b>‘ ’ ʻ ʼ</b> apostroflar farqlanmaydi.<br>• Javoblarni imlo qoidasi bo‘yicha aniq yozing: o‘quvchi javobi shu javoblardan biriga <b>aynan</b> mos kelishi kerak.<br>📜 Sertifikat test yakunlangach beriladi.</div>'+rows.map((r,idx)=>idx===44?r:r.replace('</b>','</b><textarea id="ct'+(idx+1)+'" class="rt" rows="2" maxlength="4000" placeholder="Savol matni (ixtiyoriy — foydalanuvchi savolni ko‘radi)" style="margin:6px 0"></textarea>')).join(''); box.dataset.ready='1'; if(!(box.previousElementSibling&&box.previousElementSibling.classList.contains('rtPrev'))){ box.insertAdjacentHTML('beforebegin',rtBar(true)); }
  box.querySelectorAll('.keyBtn').forEach(btn=>btn.addEventListener('click',()=>{
    const q=btn.dataset.q;
    box.querySelectorAll(`.keyBtn[data-q="${q}"]`).forEach(x=>x.classList.remove('selected'));
    btn.classList.add('selected');
  }));
}

// ===== v69: Mock ichida test kiritish (Diagnostik testdagi 45 topshiriqli quruvchi shu yerda ochiladi) =====
function mockBuildUi(){
  const on=!!window._mockBuild;
  const back=$('ncBack'); if(back){ back.textContent=on?'‹ Mock':'‹ Milliy sertifikat'; back.onclick=()=>openSection(on?'mock':'national'); }
  const dl=$('nDeadline'); if(dl && dl.closest('label')) dl.closest('label').style.display=on?'none':'';
  const hint=$('ncMockHint'); if(hint) hint.classList.toggle('hidden',!on);
}
function openMockTestBuilder(){
  openNationalCreate();
  window._mockBuild=true; mockBuildUi();
}

function selectedKey(q){
  const b=document.querySelector(`.keyBtn[data-q="${q}"].selected`);
  return b ? b.dataset.value : '';
}

async function createNationalTest(){
  const title=($('createTitle')?.value||'').trim();
  if(!title){notify('Test nomini kiriting.');return;}
  const essayTopic=($('createEssayTopic')?.value||'').trim();
  if(msCfg().essay&&essayTopic.length<8){notify('Esse mavzusini kiriting (kamida 8 belgi).');return;}
  const questions=[];
  for(let i=1;i<=45;i++){
    const type=msType(i);
    const q={type,points:1};
    const tx=($('ct'+i)?.value||'').trim(); if(tx) q.text=tx;
    const _ds=$('ct'+i)?.dataset||{}; if(_ds.pass) q.passage=_ds.pass; if(_ds.passFrom) q.passage_from=parseInt(_ds.passFrom,10)||0;   // v108+: uzun matn
    if(type==='Y1'||type==='Y2'){
      q.options=type==='Y1'?['A','B','C','D']:['A','B','C','D','E','F'];
      q.answer=selectedKey(i);
      if(!q.answer){notify(`${i}-savolning to‘g‘ri javobini belgilang.`);return;}
    }else if(type==='O1'){
      q.answers=($(`co${i}`)?.value||'').split(/[\/;]/).map(x=>x.trim()).filter(Boolean);
      if(!q.answers.length){notify(`${i}-savolning to‘g‘ri javobini kiriting.`);return;}
    }else if(type==='O1AB'){
      q.a_answers=($(`caa${i}`)?.value||'').split(/[\/;]/).map(x=>x.trim()).filter(Boolean);
      q.b_answers=($(`cab${i}`)?.value||'').split(/[\/;]/).map(x=>x.trim()).filter(Boolean);
      if(!q.a_answers.length||!q.b_answers.length){notify(`${i}-savolning a) va b) to‘g‘ri javoblarini kiriting.`);return;}
    }else{
      q.essay_from_bot=true;
    }
    questions.push(q);
  }
  const status=$('createStatus'); status.textContent='⏳ Test saqlanmoqda...';
  try{
    const r=await apiFetch(apiUrl('/api/national/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,questions,essay_topic:essayTopic,subject:msCfg().name,subject_key:(window.__msSubject||'ona_tili'),duration_min:msMinutes(),include_essay:true,deadline_hours:(window._mockBuild?0:Number($('nDeadline')?.value||24))})});
    const d=await r.json();
    if(!d.ok){status.textContent='❌ '+(d.error||'Test yaratilmadi');return;}
    if(window._mockBuild){   // v69: Mock ichida yaratildi — kod mock formasiga o‘zi tushadi
      window._mockBuild=false; mockBuildUi();
      if($('mkCode')) $('mkCode').value=d.code;
      if($('mkCodeInfo')) $('mkCodeInfo').textContent='✅ Test kiritildi: '+d.code+' — endi mock nomi va vaqtlarini to‘ldirib «Mockni joylash»ni bosing.';
      status.textContent=''; openSection('mock'); notify('Test saqlandi. Mock vaqtlarini kiriting.');
      return;
    }
    const btnCopy=`<button class="primaryAction" type="button" onclick="copyCode(${escapeHtml(JSON.stringify(d.code))})">📋 Kodni nusxalash</button>`;
    status.innerHTML=`<div class="result"><h3>✅ Test yaratildi!</h3><div class="scoreBig" style="font-size:34px">${escapeHtml(d.code)}</div><p>Shu kodni boshqalarga yuboring. Boshqa talabgorlar testni shu kod orqali ishlab, javoblarini tekshirtirishi mumkin.</p><p class="muted">📝 Esse mavzusi: <b>${escapeHtml(essayTopic)}</b><br>Talabgorlar shu mavzuda yozgan esse bahosi umumiy natijaga qo‘shiladi.</p>${btnCopy}${shareCreated(d.code,title)}</div>`;
  }catch(e){console.error(e);status.textContent='❌ Server bilan bog‘lanishda xatolik.';}
}

async function startNational(code){
  try{
    const r=await apiFetch(apiUrl('/api/national/test/'+encodeURIComponent(code))); const d=await r.json();
    if(!d.ok){notify(d.error||'Test topilmadi');return;}
    nationalTest=d.test; nationalIndex=0; nationalAnswers={};
    try{ const sv=JSON.parse(localStorage.getItem(natKey(nationalTest.code))||'null');   // v82: Telegram'dan chiqib qaytilsa ham javoblar yo'qolmaydi
      if(sv&&sv.a&&typeof sv.a==='object'&&Date.now()-(sv.t||0)<6*3600*1000){ nationalAnswers=sv.a; nationalIndex=Math.max(0,Math.min((sv.i|0),nationalTest.questions.length-1)); notify('Oldingi javoblaringiz tiklandi.'); } }catch(e){}
    nationalEssayScore=null;
    try{ const er=await apiFetch(apiUrl('/api/national/essay-score/'+encodeURIComponent(nationalUid())+'?code='+encodeURIComponent(nationalTest.code)),{cache:'no-store'}); const ed=await er.json(); nationalEssayScore=ed.ok?ed.essay_score:null; }catch(e){ nationalEssayScore=null; }
    openSection('nationalExam'); renderNationalQuestion();
  }catch(e){console.error(e);notify('Testni ochishda xatolik yuz berdi.');}
}
function renderNationalQuestion(){
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1), saved=nationalAnswers[key], total=nationalTest.questions.length;
  $('nationalProgress').innerHTML=`${nationalIndex+1} / ${total} • ${escapeHtml(q.type)}<div class="bar"><i style="width:${Math.round((nationalIndex+1)/total*100)}%"></i></div>`;
  $('nationalQuestion').innerHTML=(nationalIndex===0&&nationalTest.has_essay!==false?`<div class="result" style="margin:0 0 10px"><b>📝 Esse mavzusi:</b> ${escapeHtml(nationalTest.essay_topic||'ixtiyoriy (oxirgi esse)')}<br><b>Esse bali:</b> ${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'bu mavzuda esse topilmadi — avval botda shu mavzuda esse yozing'}${nationalTest.essay_link&&nationalEssayScore===null?`<br><button class="primaryAction" type="button" onclick="openEssayInBot()">✍️ Esseni botda yozish</button>`:''}</div>`:'') + (window.natPassageHtml?natPassageHtml(q):'') + (q.text?'<span class="qr">'+rich(q.text)+'</span>':`<b>${q.type==='O2'?'45-savol — esse':nationalIndex+1+'-savol: javobni belgilang yoki kiriting'}</b>`);
  let html='';
  if(q.type==='Y1'||q.type==='Y2'){
    const opts=q.options&&q.options.length?q.options:['A','B','C','D'];
    html=`<div class="answers">${opts.map(x=>`<button type="button" class="nopt${saved===x?' selected':''}" data-value="${escapeHtml(x)}">${escapeHtml(x)}</button>`).join('')}</div>`;
  }else if(q.type==='O1') html=`<p class="muted">⚠️ Faqat BITTA javob yozing (<b>/</b> belgisini ishlatmang). Imlo aniq bo‘lsin: katta-kichik harf va ‘ ’ ʻ belgilari farqlanmaydi.</p><input id="nopen" placeholder="Javobni aynan yozing (faqat bitta javob)" value="${escapeHtml(typeof saved==='string'?saved:'')}">`;
  else if(q.type==='O1AB') html=`<p class="muted">⚠️ Har qatorga faqat BITTA javob yozing (<b>/</b> ishlatmang). Imlo aniq bo‘lsin; harf kattaligi va ‘ ’ ʻ belgilari farqlanmaydi.</p><label class="field">a) javob<input id="na" placeholder="a) javobni yozing" value="${escapeHtml(Array.isArray(saved)?saved[0]:'')}"></label><label class="field">b) javob<input id="nb" placeholder="b) javobni yozing" value="${escapeHtml(Array.isArray(saved)?saved[1]:'')}"></label>`;
  else html=`<div class="result"><b>45-savol — esse</b><p class="muted">Bu yerda esse qayta yozilmaydi. Mavzu: «${escapeHtml(nationalTest.essay_topic||'—')}». Yakunlaganingizda esse ballini tanlaysiz: mavjud esse, yangi esse yozish, ballni qo‘lda kiritish yoki esse‘siz.</p><div class="scoreBig" style="font-size:32px">${nationalEssayScore!==null?escapeHtml(String(nationalEssayScore))+'/24':'Esse bali topilmadi'}</div></div>`;
  $('nationalAnswer').innerHTML=html;
  document.querySelectorAll('.nopt').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nopt').forEach(x=>x.classList.remove('selected'));b.classList.add('selected');nationalAnswers[String(nationalIndex+1)]=b.dataset.value; natSave();}));
  const last=nationalIndex===total-1;
  $('btnNext').classList.remove('hidden');
  $('btnNext').textContent=last?'Yakunlash ✓':'Keyingi ›';
  $('btnPrev').classList.toggle('hidden',nationalIndex===0);
}
async function showEssayChoice(){
  try{ const mr=await (await apiFetch(apiUrl('/api/me'),{cache:'no-store'})).json(); if(mr&&mr.ok!==false) ME=Object.assign((typeof ME!=='undefined'&&ME)||{},mr); }catch(e){}
  const m=(typeof ME!=='undefined'&&ME)||{}, tot=m.free_essay_total, left=m.free_essay_left;
  const free=tot!=null?`<p class="muted">🎁 Botda dastlabki ${tot} ta esse tekshiruvi BEPUL${left!=null?` (sizda ${left} ta qoldi)`:''}. Keyin 1 ta esse — 2 000 so‘m (3 ta — 5 000 so‘m). Esse pullik sun’iy intellekt (AI) asosida tekshiriladi.</p>`:'';
  const has=nationalEssayScore!==null;
  if(nationalTest.is_mock){   // v67: MOCK — esse majburiy, ball qo‘lda kiritilmaydi: bot (AI) yoki ekspert tekshiradi
    const ex=nationalTest.expert||{}, som=n=>String(n).replace(/\B(?=(\d{3})+(?!\d))/g,' ')+' so‘m';
    $('nationalProgress').innerHTML='✅ Test javoblari tayyor<div class="bar"><i style="width:100%"></i></div>';
    const ai=nationalTest.ai||{};
    $('nationalQuestion').innerHTML=`<div class="result" style="margin:0"><b>📝 Esse — MAJBURIY</b><p class="muted">Mavzu: «${escapeHtml(nationalTest.essay_topic||'ixtiyoriy')}». <b>Ikki yo‘ldan birini tanlash shart.</b> Esse balli bo‘lmasa test natijalari hisoblanmaydi. Esse balli qo‘lda kiritilmaydi. Esse test boshlangandan keyin yozilgan bo‘lishi kerak.</p></div>`;
    const aiCard=(ai.on&&!ai.used)
      ?`<div class="mkPromo"><b>🤖 1-yo‘l: AI orqali BEPUL tekshirish</b><p>Faqat mock ishtirokchilari uchun <b>1 martalik</b> imkoniyat. AI aynan shu mock esse mavzusini tekshiradi (boshqa mavzu emas).</p><button class="primaryAction" type="button" onclick="openMockAI(nationalTest.code)">🤖 AI bilan bepul tekshirish</button></div>`
      :(ai.used?`<div class="result" style="margin:10px 0">🤖 <b>1-yo‘l: bepul AI</b> — 1 martalik imkoniyatdan foydalanib bo‘lgansiz.</div>`:'');
    $('nationalAnswer').innerHTML=(has?`<button class="primaryAction" type="button" onclick="submitEssayChoice('auto')">✅ Tekshirilgan esse (${escapeHtml(String(nationalEssayScore))}/24) bilan yakunlash</button>`:'')
      +aiCard
      +(ex.job?`<div class="result" style="margin:10px 0">👨‍🏫 Esse ekspertga yuborilgan (#${ex.job}). ${ex.score!=null?'Ekspert balli: <b>'+ex.score+'/24</b>.':'Ball kelmaguncha natija vaqtincha ko‘rinadi, ekspert balli kelgach botda yakuniy natija yuboriladi.'}</div><button class="primaryAction" type="button" onclick="submitEssayChoice('expert')">✅ Testni yakunlash</button>`
        :`<div class="mkPromo"><b>👨‍🏫 ${ai.on&&!ai.used?'2-yo‘l':'Ekspert'}: ekspert orqali tekshirish — ${som(ex.uzs||10000)}</b><p>Haqiqiy ekspert esseni tekshirib, ball beradi (24 soat ichida). To‘lov va esse yuborish botda, so‘ng shu yerga qaytib «Yangilash»ni bosing.</p><button class="primaryAction" type="button" onclick="openMockExpert(nationalTest.code)">👨‍🏫 Ekspertga yuborish</button></div>`)
      +`<button class="listbtn" type="button" onclick="refreshMockExpert()">🔄 Yangilash (esse balli)</button>`;
    $('btnNext').classList.add('hidden'); $('btnPrev').classList.remove('hidden'); window.scrollTo(0,0); return;
  }
  $('nationalProgress').innerHTML='✅ Test javoblari tayyor<div class="bar"><i style="width:100%"></i></div>';
  $('nationalQuestion').innerHTML=`<div class="result" style="margin:0"><b>📝 Esse balli (45-topshiriq)</b><p class="muted">Mavzu: «${escapeHtml(nationalTest.essay_topic||'ixtiyoriy')}». Esse ballini qanday hisobga olamiz?</p>${free}</div>`;
  $('nationalAnswer').innerHTML=`${has?`<button class="primaryAction" type="button" onclick="submitEssayChoice('auto')">✅ Mavjud esse bali (${escapeHtml(String(nationalEssayScore))}/24) bilan hisoblash</button>`:''}
    <button class="primaryAction" type="button" onclick="writeEssayThenRefresh()">✍️ Mavzuga esse yozaman (bot tekshiradi)</button>
    <div class="result" style="margin:10px 0"><label class="field">🔢 Esse ballini o‘zim kiritaman (0–24)<input id="essayManual" type="number" min="0" max="24" step="0.5" inputmode="decimal" placeholder="Masalan: 17.5"></label><button class="primaryAction" type="button" onclick="submitEssayChoice('manual')">Shu ball bilan hisoblash</button></div>
    <button class="listbtn" type="button" onclick="submitEssayChoice('none')">⏭ Esse‘siz — esse 0 ball hisoblanadi</button>
    <p class="muted">Esse balli kiritilmasa, esse 0 ball hisoblanadi: umumiy = (test + esse) ÷ 2, ya’ni past chiqadi.</p>`;
  $('btnNext').classList.add('hidden'); $('btnPrev').classList.remove('hidden');
  window.scrollTo(0,0);
}
async function writeEssayThenRefresh(){
  openEssayInBot();
  notify('Botda esseni tekshirtiring, so‘ng bu yerga qaytib «Yangilash»ni bosing.');
  const box=$('nationalAnswer'); if(box&&!document.getElementById('essayRefreshBtn')) box.insertAdjacentHTML('afterbegin','<button id="essayRefreshBtn" class="primaryAction" type="button" onclick="refreshEssayScore()">🔄 Esse natijasini yangilash</button>');
}
async function refreshEssayScore(){
  try{ const er=await apiFetch(apiUrl('/api/national/essay-score/'+encodeURIComponent(nationalUid())+'?code='+encodeURIComponent(nationalTest.code)),{cache:'no-store'}); const ed=await er.json(); nationalEssayScore=ed.ok?ed.essay_score:null; }catch(e){}
  if(nationalEssayScore===null) notify('Bu mavzuda esse hali topilmadi.'); await showEssayChoice();
}
async function submitEssayChoice(mode){
  if(nationalBusy) return;
  let manual;
  if(mode==='manual'){
    manual=parseFloat(String(($('essayManual')?.value||'')).replace(',','.'));
    if(!isFinite(manual)||manual<0||manual>24){notify('Esse balli 0 dan 24 gacha bo‘lishi kerak.');return;}
  }
  nationalBusy=true;
  try{ await submitNational(mode,manual); } finally { nationalBusy=false; $('btnNext').classList.remove('hidden'); }
}
function openMockAI(code){   // v76: Mock — 1 martalik bepul AI tekshiruvi botda
  const u=(nationalTest&&nationalTest.ai&&nationalTest.ai.link)||(ME.bot_username?('https://t.me/'+ME.bot_username+'?start=mockai_'+encodeURIComponent(code)):'');
  if(!u){ notify('Bot havolasi topilmadi.'); return; }
  try{ if(tg?.openTelegramLink){ tg.openTelegramLink(u); return; } }catch(e){}
  window.open(u,'_blank');
}
function openMockExpert(code){   // v67: Mock aksiyasi — ekspertga yuborish botda
  const u=(nationalTest&&nationalTest.expert&&nationalTest.expert.link)||(ME.bot_username?('https://t.me/'+ME.bot_username+'?start=mockexpert_'+encodeURIComponent(code)):'');
  if(!u){ notify('Bot havolasi topilmadi.'); return; }
  try{ if(tg?.openTelegramLink){ tg.openTelegramLink(u); return; } }catch(e){}
  window.open(u,'_blank');
}
async function refreshMockExpert(){   // ekspertga yuborilgan-yuborilmaganini qayta tekshiradi
  try{
    const d=await (await apiFetch(apiUrl('/api/national/test/'+encodeURIComponent(nationalTest.code)),{cache:'no-store'})).json();
    if(d.ok&&d.test){ nationalTest.expert=d.test.expert||nationalTest.expert; nationalTest.ai=d.test.ai||nationalTest.ai; }
    try{ const er=await apiFetch(apiUrl('/api/national/essay-score/'+encodeURIComponent(nationalUid())+'?code='+encodeURIComponent(nationalTest.code)),{cache:'no-store'}); const ed=await er.json(); nationalEssayScore=ed.ok?ed.essay_score:null; }catch(e){}
  }catch(e){}
  await showEssayChoice();
}
function openEssayInBot(){
  const u=nationalTest&&nationalTest.essay_link; if(!u) return;
  try{ if(tg?.openTelegramLink){ tg.openTelegramLink(u); return; } }catch(e){}
  window.open(u,'_blank');
}
function natKey(code){ return 'natans_'+nationalUid()+'_'+String(code||'').toUpperCase(); }
function natSave(){ try{ if(nationalTest&&nationalTest.code) localStorage.setItem(natKey(nationalTest.code),JSON.stringify({a:nationalAnswers,i:nationalIndex,t:Date.now()})); }catch(e){} }
function natClear(code){ try{ localStorage.removeItem(natKey(code)); }catch(e){} }
function collectNational(){
  const q=nationalTest.questions[nationalIndex], key=String(nationalIndex+1);
  if(q.type==='O1') nationalAnswers[key]=($('nopen')?.value||'').trim();
  if(q.type==='O1AB') nationalAnswers[key]=[($('na')?.value||'').trim(),($('nb')?.value||'').trim()];
  if(q.type==='O2') nationalAnswers[key]='__ESSAY_FROM_BOT__';
  natSave();
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
  msFinish(false); return;   // v108: esse (ilova ichida yozilgan) → AI → test → yagona natija; esse yo‘q fanlarda darrov natija
}
function mockExtras(d){   // v67: Mock natijasi qo‘shimchalari
  let h='';
  if(d.essay_pending) h+='<div class="result" style="margin:10px 0">⏳ <b>Esse ekspert tekshiruvida.</b> Hozirgi ball vaqtincha (esse hisobga olinmagan). Ekspert ball bergach, yakuniy natija botga yuboriladi.</div>';
  const fr=d.fan_report||[];
  if(fr.length){
    h+='<h4>📚 Mavzular bo‘yicha xato savollar</h4><div class="tTable">'+fr.map(f=>'<div><b>'+escapeHtml(f.name)+'</b><span>'+f.correct_pct+'%</span><em>'+(f.wrong.length?'xato: '+f.wrong.map(x=>'#'+escapeHtml(String(x))).join(', '):'xato yo‘q ✅')+' ('+(f.total-f.wrong.length)+'/'+f.total+' to‘g‘ri)</em></div>').join('')+'</div>';
    const weak=fr.filter(f=>f.wrong.length).sort((a,b)=>a.correct_pct-b.correct_pct)[0];
    if(weak) h+='<p class="muted">💡 Avval takrorlang: <b>'+escapeHtml(weak.name)+'</b> ('+weak.correct_pct+'%).</p>';
  }
  return h;
}
function mkSom2(n){ return String(n).replace(/\B(?=(\d{3})+(?!\d))/g,' ')+' so‘m'; }
function fmtEtaUz(s){   // soniya -> tushunarli matn
  s=Math.max(0,Math.round(s||0)); if(s<45) return '1 daqiqadan kam'; const m=Math.round(s/60); return m<=1?'1 daqiqa':(m+' daqiqa');
}
function mockEssayAutoPoll(code,n){   // «yangilash» tugmasisiz — esse tayyor bo‘lguncha shu sahifa o‘zi yangilanadi
  clearTimeout(window._mkPoll); n=n||0; if(n>200) return;
  window._mkPoll=setTimeout(async()=>{
    const el=$('nationalResult'); if(!el||el.classList.contains('hidden')||!document.getElementById('mkChk')) return;
    try{ const d=await natPost(apiUrl('/api/mock/essay-sync'),{code}); if(d.ok){ showMockHidden(d,d.title); if(d.essay_score!=null) notify('✅ Esse balli testingizga ulandi: '+d.essay_score+'/24'); return; } }catch(e){}
    mockEssayAutoPoll(code,n+1);
  },6000);
}
function showMockHidden(d,title){   // v82: MOCK topshirildi — esse holati (bor / tekshirilmoqda / ekspert kutilmoqda / hali kerak)
  window._mkState=d; const code=String(d.code||(nationalTest&&nationalTest.code)||'');
  const st=d.streak&&d.streak.current?`<p>🔥 <b>${d.streak.current} kunlik seriya!</b></p>`:'';
  let es='';
  if(d.essay_score!=null) es=`<p>📝 Esse balingiz: <b>${escapeHtml(String(d.essay_score))}/24</b> ✅</p>`;
  else if(d.checking){
    es=`<div id="mkChk" class="result" style="margin:10px 0"><b>⏳ Esse tekshirilmoqda</b><br>`
      +(d.job_stage==='queued'?`Navbatingiz: <b>${d.job_pos}-o‘rin</b> • taxminan <b>${fmtEtaUz(d.job_eta)}</b> kutasiz.`:`Taxminan <b>${fmtEtaUz(d.job_eta||60)}</b> qoldi.`)
      +`<p class="muted">Bu sahifa o‘zi yangilanadi. Oynani yopsangiz ham bo‘ladi: esse tayyor bo‘lgach botga xabar yuboramiz va ball testingizga <b>avtomatik</b> ulanadi.</p></div>`;
    setTimeout(()=>mockEssayAutoPoll(code),0);
  }
  else if(d.expert_wait||(d.essay_pending&&d.need_essay===undefined)) es='<p>👨‍🏫 Esse ekspert tekshiruvida (24 soat ichida). Ball kelgach shu yerda va botda ko‘rinadi.</p>';
  else if(d.need_essay){
    const ai=d.ai||{}, ex=d.expert||{};
    es=`<div style="border-left:4px solid #c0392b;padding:6px 10px;margin:10px 0">⚠️ <b>Esse balli hali yo‘q.</b> Esse balli bo‘lmasa test natijangiz hisoblanmaydi. Ikkisidan birini tanlang:</div>`
      +(ai.on&&!ai.used?`<button class="primaryAction" type="button" onclick="openMockAI('${escapeHtml(code)}')">🤖 AI bilan BEPUL tekshirish (1 martalik)</button>`:(ai.used?'<p class="muted">🤖 Bepul AI imkoniyatidan foydalanib bo‘lgansiz.</p>':''))
      +`<button class="primaryAction" type="button" onclick="openMockExpert('${escapeHtml(code)}')">👨‍🏫 Ekspert orqali — ${mkSom2(ex.uzs||10000)}</button>`
      +`<button class="listbtn" type="button" onclick="refreshMockEssay('${escapeHtml(code)}')">🔄 Esse botda tekshirilgan bo‘lsa — ballni yangilash</button><p class="muted">Esseni bot orqali (AI yoki ekspert) tekshirtirgan bo‘lsangiz, bu tugma ballni testingizga ulaydi. Ball hali kelmagan bo‘lsa, kuting: AI — 1–2 daqiqa, ekspert — 24 soat.</p>`;
  }
  $('nationalResult').innerHTML=`<button class="back" onclick="openSection('mock')">‹ Mock</button><div class="result"><h3>✅ Test qabul qilindi${title?': '+escapeHtml(title):''}</h3>${es}${st}<p class="muted">Test balli, umumiy natija va sertifikat <b>admin natijalarni e‘lon qilgach</b> beriladi. Shu paytgacha ular hech kimga ko‘rinmaydi.</p></div>`;
}
async function refreshMockEssay(code){   // v82: esse AI/ekspert orqali tekshirilgach, topshirilgan testga bog'lanadi
  try{
    const d=await natPost(apiUrl('/api/mock/essay-sync'),{code});
    if(!d.ok){ notify(d.error||'Yangilab bo‘lmadi.'); return; }
    if(d.essay_score!=null) notify('✅ Esse balli ulandi: '+d.essay_score+'/24');
    else if(d.checking) notify('Esse hali tekshirilmoqda. Sahifa o‘zi yangilanadi.');
    else if(d.need_essay) notify('Esse balli hali kelmadi. AI tekshiruvi 1–2 daqiqa, ekspert 24 soat ichida yuboradi. Biroz kutib, qayta bosing.');
    showMockHidden(d,d.title);
  }catch(e){ notify('Server band. Birozdan keyin yana urinib ko‘ring.'); }
}
async function openMyMock(id){   // v68: «Natijam»
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/my-result?id='+encodeURIComponent(id)),{cache:'no-store'})).json();
    openSection('nationalResult');
    if(!d.ok){ $('nationalResult').innerHTML='<button class="back" onclick="openSection(\'mock\')">‹ Mock</button><div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    if(!d.taken){ $('nationalResult').innerHTML='<button class="back" onclick="openSection(\'mock\')">‹ Mock</button><div class="result">Siz bu mock testini topshirmagansiz.</div>'; return; }
    if(!d.published){ showMockHidden(d,d.title); return; }
    renderMockResult(d,id);
  }catch(e){ notify('Natijani yuklashda xatolik.'); }
}
const _sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function natPost(url,body){   // v82: tarmoq/server band (5xx, 429) bo'lsa 4 martagacha avtomatik qayta uriniladi
  let last=null;
  for(let i=0;i<4;i++){
    try{
      const r=await apiFetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(r.status>=500||r.status===429){ last=new Error('HTTP '+r.status); await _sleep(1500*(i+1)); continue; }
      return await r.json();
    }catch(e){ last=e; await _sleep(1500*(i+1)); }
  }
  throw last||new Error('network');
}
let _lastSubmit=null;
function retrySubmit(){ if(_lastSubmit) submitEssayChoice(_lastSubmit.mode); }
async function submitNational(mode,manual){
  const uid=nationalUid(); _lastSubmit={mode,manual};
  const wait=nationalTest&&nationalTest.is_mock;
  if(wait){ openSection('nationalResult'); $('nationalResult').innerHTML='<div class="result">⏳ Javoblaringiz yuborilmoqda… Sahifani yopmang.</div>'; }
  try{
    const d=await natPost(apiUrl('/api/national/submit'),{code:nationalTest.code,answers:nationalAnswers,essay_mode:mode||'auto',essay_manual:manual});
    openSection('nationalResult');
    if(d.already&&nationalTest.is_mock){ natClear(nationalTest.code); showMockHidden({code:nationalTest.code,need_essay:undefined,essay_pending:true,taken:true},nationalTest.title); try{ refreshMockEssay(nationalTest.code); }catch(e){} return; }
    if(!d.ok){$('nationalResult').innerHTML='<button class="back" onclick="openSection(\'national\')">‹ Milliy sertifikat</button><div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div><button class="primaryAction" type="button" onclick="retrySubmit()">🔁 Qayta yuborish</button><p class="muted">Javoblaringiz saqlangan.</p>';return;}
    natClear(nationalTest.code);
    if(d.hidden){ showMockHidden(d); return; }
    $('nationalResult').innerHTML=`<button class="back" onclick="openSection('national')">‹ Milliy sertifikat</button><div class="result">${msResultTop(d)}<p>🧪 Test (${d.rasch?'Rasch T-ball':'taxminiy, foiz'}): <b>${d.score_75}/75</b> • To‘g‘ri javob: ${d.raw_score}/${d.max_score}</p>${d.no_essay?'':`<p>📝 Esse (${d.essay_manual?'o‘zingiz kiritgan ball':escapeHtml(d.essay_topic||'oxirgi esse')}): <b>${d.essay_score!=null?d.essay_score+'/24 → '+d.essay_75+'/75':(d.essay_missing?'hali yozilmagan (umumiy ballga kirmadi)':'topilmadi → 0/75')}</b></p><p class="muted">${d.essay_missing?'Umumiy ball = faqat test. Esseni tekshirtirsangiz, (test + esse) ÷ 2 bo‘ladi.':'Umumiy ball = (test + esse) ÷ 2'}</p>`}${d.note?`<p class="muted">ℹ️ ${escapeHtml(d.note)}</p>`:''}${mockExtras(d)}<h4>❌ Xatolar: ${(d.errors||[]).length}</h4>${(d.errors||[]).map(x=>`<div class="errorCard"><b>${x.number}-savol</b>${x.wrong_parts?` <span class="muted">(${['a','b'].map(k=>k+') '+(x.wrong_parts.includes(k)?'❌':'✅')).join(' • ')} — ${x.earned}/${x.points} ball)</span>`:''}<br>Siz: ${escapeHtml(x.user_text!=null?x.user_text:JSON.stringify(x.user))}<br>To‘g‘ri: ${escapeHtml(x.correct_text!=null?x.correct_text:JSON.stringify(x.correct))}<br>${escapeHtml(x.explanation||'')}</div>`).join('')}<p class="muted">Bu diagnostik natija. Rasmiy davlat sertifikati emas.</p></div>`;
    $('nationalResult').insertAdjacentHTML('beforeend',resultExtras('ms',nationalTest.code,d)+shareCard(nationalTest.code,nationalTest.title,(d.combined_score_75 ?? d.score_75)+'/75 ('+d.level+')'+rankTxt(d)));
    $('nationalResult').insertAdjacentHTML('beforeend',ansKeyBox(nationalTest.code,'nat'));
    if(d.cert_pending){ $('nationalResult').insertAdjacentHTML('beforeend',`<div class="result"><h4>📜 Sertifikat</h4><p>Sertifikat <b>test yakunlangach</b> (muallif testni yakunlaganda yoki muddat tugaganda) avtomatik tarzda botdagi chatingizga yuboriladi.</p></div>`); }
    else if(d.level==='Sertifikat berilmadi'){ $('nationalResult').insertAdjacentHTML('beforeend',`<div class="result"><h4>📜 Sertifikat</h4><p class="muted">Sertifikat berilishi uchun kamida 46 ball (C daraja) kerak.</p></div>`); }
  }catch(e){openSection('nationalResult');$('nationalResult').innerHTML='<button class="back" onclick="openSection(\'national\')">‹ Milliy sertifikat</button><div class="result">❌ Server band yoki internet uzildi. <b>Javoblaringiz saqlangan</b> — qayta yuborishni bosing.</div><button class="primaryAction" type="button" onclick="retrySubmit()">🔁 Qayta yuborish</button>';}
}
function nationalCode(){
  const c=($('codeInput')?.value||'').trim().toUpperCase();
  if(!c){notify('Test kodini kiriting.');return;}
  startNational(c);
}


// ===== Dizayn: pastki menyu va Telegram rangi =====
(function(){
  const map={home:'home',alifbo:'home',eq:'home',national:'home',nationalCreate:'home',nationalExam:'home',simpleExam:'home',testResults:'home',panel:'home',simpleResult:'home',nationalResult:'home',expert:'home',prep:'home',teacher:'home',teacherStats:'home',foydali:'foydali',premium:'home',essewin:'foydali',gazallib:'foydali',gazal:'foydali',books:'foydali',bookPage:'foydali',growth:'foydali',active:'foydali',mashq:'mashq',games:'mashq',gamePlay:'mashq',dicts:'mashq',dict:'mashq',mumtoz:'mashq',paronim:'mashq',sinonim:'mashq',omonim:'mashq',attestwin:'home',mgramwin:'mashq',mmatnwin:'mashq',madabwin:'mashq',messewin:'mashq',mock:'mock',rating:'rating',profil:'profil',author:'profil',admin:'profil'};
  const mark=id=>document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('on',b.dataset.k===(map[id]||'')));
  const o=openSection,h=goHome;
  openSection=function(id){o(id);mark(id);};
  goHome=function(){h();mark('home');};
  try{tg?.setHeaderColor?.('#0b5a41');tg?.setBackgroundColor?.(document.documentElement.classList.contains('dk')?'#0d2b22':'#f3f8f5');}catch(e){}
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


function uzsFmt(n){ return String(n).replace(/\B(?=(\d{3})+(?!\d))/g,' '); }
async function loadExpert(){
  const box=$('expBody'); box.innerHTML='<div class="word">Yuklanmoqda…</div>';
  let d=null;
  try{ const r=await apiFetch(apiUrl('/api/expert/info')); d=await r.json(); }catch(e){}
  if(!d||!d.ok){ d={one_uzs:10000,pack_uzs:25000,pack_n:3,balance:0}; }
  const bot=(ME&&ME.bot_username)||'';
  { const how=$('expHow'); if(how&&ME&&(ME.auto_pay||ME.card_auto)) how.innerHTML='1) «Karta orqali to‘lash» tugmasini bosing — bot karta raqami va aniq summani beradi.<br>2) Shu summani o‘tkazing — to‘lov tushishi bilan avtomatik aniqlanadi (chek shart emas).<br>3) «Esseni yuborish» tugmasi chiqadi — esseni (matn, rasm yoki PDF) yuborasiz.<br>4) Ekspert tekshirib, natijani 24 soat ichida shu bot chatiga yuboradi.'; }
  const old=d.one_uzs*d.pack_n, per=Math.round(d.pack_uzs/d.pack_n);
  const proof=(d.proof&&d.proof.length)?`<div class="expProof"><b>Nega ekspert?</b>${d.proof.map(x=>'<div>'+escapeHtml(x)+'</div>').join('')}</div>`:'';
  box.innerHTML=proof+
    (d.balance>0?`<div class="expHave">💼 Sizda <b>${d.balance} ta</b> ekspert tekshiruvi bor.<button class="primaryAction" type="button" onclick="expertOpenBot('expert')">📨 Esseni yuborish</button></div>`:'')+
    `<div class="expCard"><div class="expName">1 ta esse tekshirish</div><div class="expPrice">${uzsFmt(d.one_uzs)} <small>so‘m</small></div>
      <div class="muted">Doimiy narx • ekspert tekshiradi • 24 soat ichida natija</div>
      <button class="primaryAction" type="button" onclick="payByCard('expert','e1')">💳 Karta orqali to‘lash</button></div>`+
    `<div class="expCard expHot"><div class="expBadge">🔥 Imtihongacha maxsus imkoniyat</div><div class="expName">${d.pack_n} ta esse — ${uzsFmt(d.pack_uzs)} so‘m</div>
      <div class="expPrice">${uzsFmt(d.pack_uzs)} <small>so‘m</small> <s>${uzsFmt(old)}</s></div>
      <div class="muted">Bittasi taxminan ${uzsFmt(per)} so‘m • ${d.pack_n} ta esse • 24 soat ichida natija</div>
      <button class="primaryAction" type="button" onclick="payByCard('expert','e3')">💳 Karta orqali to‘lash</button></div>`+
    `<p class="muted">${(ME&&(ME.auto_pay||ME.card_auto))?'💳 To‘lov avtomatik: karta orqali to‘laysiz va xizmat to‘lov tushishi bilan darhol ochiladi.':'💳 To‘lov bot chatida: karta raqami beriladi, chek skrinshotini yuborasiz, tasdiqlangach xizmat ochiladi.'}</p>`;
}
function expertOpenBot(p){
  const bot=(ME&&ME.bot_username)||''; if(!bot){ notify('Botdagi /ekspert buyrug‘idan foydalaning.'); return; }
  const url='https://t.me/'+bot+'?start='+p;
  if(tg?.openTelegramLink){ tg.openTelegramLink(url); setTimeout(()=>{ try{ tg.close(); }catch(e){} },400); } else window.open(url,'_blank');
}
let omonimLug=[];
async function loadOmonim(){
  if(!omonimLug.length){ try{ omonimLug=await (await fetch('omonim_lug.json?v=52')).json(); }catch(e){ $('omonimResults').innerHTML='<div class="word">Omonimlar lug‘ati yuklanmadi.</div>'; return; } }
  searchOmonim();
}
function searchOmonim(){
  const q=normalize($('omonimSearch').value);
  const a=q.length>=1 ? omonimLug.filter(e=>normalize(e.w).startsWith(q)||(q.length>=3&&normalize(e.w).includes(q))) : omonimLug;
  $('omonimResults').innerHTML=a.slice(0,40).map(e=>`<div class="word"><strong>${escapeHtml(e.w)}</strong>${e.s.map((m,i)=>`<div class="muted" style="margin-top:6px">${i+1}) ${m[0]?`<b style="color:var(--g2)">${escapeHtml(m[0])}</b> — `:''}${escapeHtml(m[1])}</div>`).join('')}</div>`).join('')||'<div class="word">So‘z topilmadi.</div>';
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
  try{ const me=await (await apiFetch(apiUrl('/api/me'),{cache:'no-store'})).json(); ME=Object.assign(ME||{},me); if($('packInfo')&&me.pack_size) $('packInfo').textContent=me.pack_size+' ta mashq/dalil — '+fmtUzs(((me.packs&&(me.packs.find(x=>x.id==='p3')||me.packs[0]))||{}).uzs||0)+' so‘m'; const left=Math.max(0,(me.ai_limit||0)-(me.ai_used||0)); $('aiLeft').textContent=left+' / '+(me.ai_limit||0)+' ta bepul qoldi'+((me.ai_credits||0)>0?' • '+me.ai_credits+' ta pullik':''); }catch(e){}
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
// ===== Paketlar (karta): bepul limit tugagach =====
function fmtUzs(n){ return String(n).replace(/\B(?=(\d{3})+(?!\d))/g,' '); }
function premPriceHtml(d){
  const old=Number(d.old_price||0), cur=Number(d.price||0);
  if(old>cur&&cur>0) return '<div class="salePrice"><span class="saleTag">🔥 '+escapeHtml(d.sale||'Imtihon haftaligi chegirmasi')+'</span><div class="saleRow"><s>'+fmtUzs(old)+'</s><b>'+fmtUzs(cur)+' so‘m</b><em>/ 30 kun</em></div><small>🎁 '+fmtUzs(old-cur)+' so‘m tejaysiz</small>'+(d.sale_left?'<small>⏳ Chegirma tugashiga: <b>'+escapeHtml(d.sale_left)+'</b></small>':'')+'</div>';
  return '';
}
function showPaywall(out,d){
  const packs=(d.packs&&d.packs.length?d.packs:(ME&&ME.packs&&ME.packs.length?ME.packs:[{id:'p3',size:d.pack_size||3,stars:0,uzs:5000}]));
  const rows=packs.map(p=>{
    const nm=p.days?(p.days+' kunlik'):(p.size+' ta esse');
    const old=(p.old_uzs&&p.old_uzs>p.uzs)?'<s>'+fmtUzs(p.old_uzs)+'</s>':'';
    return '<div class="payCard"><div class="payTop"><b>'+nm+'</b>'+(p.discount?'<span class="payBadge">−'+p.discount+'%</span>':'')+'</div>'+
      '<div class="payPrice">'+old+'<b>'+fmtUzs(p.uzs)+'</b><em>so‘m</em></div>'+
      '<div class="payBtns"><button class="primaryAction" type="button" onclick="payByCard(\'tool\',\''+p.id+'\')">💳 Karta bilan</button>'+
      '</div></div>';
  }).join('');
  out.innerHTML='<div class="result payBox"><h3>🔒 Bepul limit tugadi</h3>'+
    '<p>'+escapeHtml(d.error||'')+'</p>'+
    '<div class="payGrid">'+rows+'</div>'+
    '<p class="payNote">✅ Sotib olingan paket muddatsiz saqlanadi<br>🕛 Bepul limit har kuni 00:00 da yangilanadi (Toshkent)</p>'+
    '<p class="payNote">'+((ME&&(ME.auto_pay||ME.card_auto))?'⚡️ Karta orqali to‘lov avtomatik: to‘laysiz — paket darhol ochiladi (chek shart emas).':'💳 Karta raqami bot chatida beriladi. Chek skrinshotini yuborasiz — tasdiqlangach paket ochiladi.')+'</p></div>';
}
// Karta orqali to'lov: botda buyurtma ochiladi (karta raqami + chek skrini)
async function payByCard(kind,plan){
  if(ME&&ME.auto_pay&&tg?.openInvoice){   // v57: avtomatik karta to‘lovi — chek ham, admin ham kerak emas
    if(_payBusy) return; _payBusy=true;
    try{
      const r=await tchPost('/api/pay/uzs',{kind,plan});
      if(!r.ok||!r.link){ notify(r.error||'To‘lov oynasini ochib bo‘lmadi.'); return; }
      tg.openInvoice(r.link,st=>{ if(st==='paid') notify('✅ To‘lov qabul qilindi. Xizmat avtomatik ochildi — bot chatini tekshiring.'); });
    }finally{ _payBusy=false; }
    return;
  }
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
  const optBtn=(q,o,i)=>`<button type="button" class="sopt" data-q="${q.number}" data-v="${L[i]}"><b>${L[i]}</b>${o===L[i]?'':' <span class="qr">'+rich(o)+'</span>'}</button>`;
  $('sxQuestions').innerHTML=t.questions.map(q=>q.text
    ?`<div class="qcard" id="sq${q.number}"><div class="qtop">${q.number}-savol</div><div class="question qr">${rich(q.text)}</div><div class="answers ${q.options.every((o,i)=>o===L[i])?'inlineOpts':''}">${q.options.map((o,i)=>optBtn(q,o,i)).join('')}</div></div>`
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
      $('sxResult').innerHTML=`<div class="result"><h3>📝 ${escapeHtml(simpleTest.title)}</h3><div class="scoreBig">${d.percent}%</div><p><b>To‘g‘ri javoblar: ${d.correct} / ${d.total}</b></p><h4>❌ Xatolar: ${d.errors.length}</h4>${d.errors.map(x=>`<div class="errorCard"><b>${x.number}-savol</b><br>${x.text?'<div class="qr">'+rich(x.text)+'</div>':''}Siz: <b>${escapeHtml(x.user)}</b><br>To‘g‘ri: <b>${escapeHtml(x.correct)}${x.correct_text&&x.correct_text!==x.correct?') '+rich(x.correct_text):''}</b>${x.explanation?'<br><span class="muted qr">'+rich(x.explanation)+'</span>':''}</div>`).join('')||'<p>🎉 Barcha javoblar to‘g‘ri!</p>'}</div>`+resultExtras('simple',simpleTest.code,d)+shareCard(simpleTest.code,simpleTest.title,d.percent+'% ('+d.correct+'/'+d.total+')'+rankTxt(d));
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
function resBtn(kind,code){ return `<button class="delBtn" style="color:#0b5a41;border-color:#bfc9e3;background:#eef1f8" type="button" title="Natijalar" onclick="openResults(${escapeHtml(JSON.stringify(kind))},${escapeHtml(JSON.stringify(code))})">📊</button>`; }
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
  BK_SEC='asar';
  try{ BK=await (await apiFetch(apiUrl('/api/books/list?sec=asar'),{cache:'no-store'})).json(); }catch(e){ return; }
  const adm=BK.is_admin, show=BK.ready||adm;
  $('bProgress').classList.toggle('hidden',show);
  $('bAdmin').classList.toggle('hidden',!adm);
  if(adm){ $('bAdminInfo').textContent=BK.ready?'Bo‘lim hamma uchun ochiq (pullik).':'Foydalanuvchilarga hozir «Jarayonda» yozuvi ko‘rinadi. Siz hammasini ko‘ryapsiz. Asar ichiga kirib «Testlar» va «Ma‘lumotlar» bo‘limlarini shu yerning o‘zida to‘ldirasiz; rasm qo‘shish: botda /asar_yordam. Ochish: /asar_ochiq yoki pastdagi tugma.'; $('bToggle').textContent=BK.ready?'🚧 Jarayonda holatiga qaytarish':'✅ Foydalanuvchilar uchun ochish'; }
  $('bPay').classList.toggle('hidden',!(show&&!BK.has_access&&BK.ready));
  $('bPrice').textContent=fmtUzs(BK.price||5000)+' so‘m';
  const g=$('bGrid');
  { let ab=$('bAddBox'); if(!ab){ ab=document.createElement('div'); ab.id='bAddBox'; g.parentNode.insertBefore(ab,g); } ab.innerHTML=adm?itemAddForm('asar','asar'):''; }
  { const ps=document.querySelector('#bPay small'); if(ps) ps.textContent='Barcha asarlar: testlar, qahramonlar, voqealar rivoji, muhim manbalar'; }
  { let hb=$('bHintBox'); if(!hb){ hb=document.createElement('div'); hb.id='bHintBox'; g.parentNode.insertBefore(hb,g); }
    const its=BK.items||[], nA=its.length, nQ=its.reduce((t,x)=>t+(x.qn||0),0), fr=its.find(x=>x.free);
    hb.innerHTML=(show&&!adm&&!BK.has_access&&nA)?'<div class="word" style="margin-top:10px">✨ <b>To‘liq kirishda:</b> '+nA+' ta asar'+(nQ?' • '+nQ+' ta test savoli':'')+' • qahramonlar, voqealar rivoji, muhim manbalar.'+(fr?'<br>🆓 <b>«'+escapeHtml(fr.title)+'»</b> — bepul namuna: avval shuni ko‘rib chiqing.':'')+'</div>':''; }
  { let gb=$('bGenBox'); if(!gb){ gb=document.createElement('div'); gb.id='bGenBox'; g.parentNode.insertBefore(gb,g); }
    const G=show?BK.general:null;
    gb.innerHTML=G?'<button class="bGen" type="button" onclick="'+(G.open?'openGeneral('+G.n+')':"notify('🔒 Umumiy test tez orada ochiladi.')")+'"><b>📝 Umumiy test</b><span>Barcha asarlardan umumiy test'+(adm?(G.qn?' • '+G.qn+' ta savol':'')+' • foydalanuvchiga: '+(G.public?'ochiq':'🔒 qulf'):'')+'</span>'+(G.open?'':'<i class="bLock">🔒</i>')+'</button>':''; }
  if(show&&!(BK.items||[]).length){ g.innerHTML='<div class="word">Hali asar qo‘shilmagan.'+(adm?'<br><br>Botga o‘ting va <b>/asar</b> buyrug‘ini yuboring, so‘ng rasmni asar nomi (izoh) bilan yuboring. Keyin asarga kirib Testlar va Ma‘lumotlarni mini ilovada kiriting.':'')+'</div>'; return; }
  g.innerHTML=show?(BK.items||[]).map(it=>`<button class="bCard" type="button" onclick="openBook(${it.n})"><div class="bThumb" id="bt${it.n}"><span>⏳</span></div><span class="bName">${escapeHtml(it.title)}</span><span class="bBadges">${it.has_info?'ℹ️ ':''}${it.qn?'📝'+it.qn+' ':''}${it.pics?'🖼'+(it.pics+1):''}</span>${(BK.has_access||adm||it.free)?'':'<i class="bLock">🔒</i>'}${(it.free&&!adm&&!BK.has_access)?'<i class="bFree">🆓 Namuna</i>':''}</button>`).join(''):'';
  if(show) (BK.items||[]).forEach(async it=>{ try{ const u=await bookBlob('thumb',it.n); const el=$('bt'+it.n); if(el) el.innerHTML='<img src="'+u+'" alt="">'; }catch(e){} });
}
async function toggleBooks(){
  try{ const d=await (await apiFetch(apiUrl('/api/books/ready'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ready:!BK.ready})})).json(); if(d.ok) loadBooks(); else notify(d.error||'Xatolik'); }catch(e){ notify('Xatolik'); }
}
let BP=null, BPn=0, bqAns={}, bqKind='closed', bpInfoKey='', bpFlash='', BK_SEC='asar', COLL={};
const SEC_BACK={gazal:'gazallib',asar:'books',premium:'premium',esse:'essewin',attest:'attestwin',mgram:'mgramwin',mmatn:'mmatnwin',madab:'madabwin',messe:'messewin'};
const COLL_UI={gazal:{g:'gzGrid',a:'gzAdd'},premium:{g:'pGrid',a:'pAdd'},esse:{g:'eGrid',a:'eAdd'},attest:{g:'aGrid',a:'aAdd'},mgram:{g:'mgGrid',a:'mgAdd'},mmatn:{g:'mmGrid',a:'mmAdd'},madab:{g:'maGrid',a:'maAdd'},messe:{g:'meGrid',a:'meAdd'}};
const MQ_SEC={mgram:1,mmatn:1,madab:1,messe:1};   // v66: Mashq bo‘limlari — hamma uchun ochiq, natija reyting va seriyaga yoziladi
const FREE_PREMIUM_TOOLS=false;   // true bo‘lsa, Faol 1000 so‘z va Esse mashqi hamma uchun yana ochiq ko‘rinadi
const bpNl=s=>escapeHtml(s||'').replace(/\n/g,'<br>');
function openExt(u){ try{ if(tg&&tg.openLink) tg.openLink(u); else window.open(u,'_blank'); }catch(e){} }
function bpRich(s){   // matn + bosiladigan havolalar (Muhim manbalar uchun)
  return escapeHtml(s||'').replace(/(https?:\/\/[^\s<]+)/g,m=>{ let t='',u=m; const mm=u.match(/[.,;:!?)]+$/); if(mm){ t=mm[0]; u=u.slice(0,-t.length); }
    return '<a href="#" class="bpLink" data-u="'+u+'" onclick="openExt(this.dataset.u);return false">'+u+'</a>'+t; }).replace(/\n/g,'<br>'); }
function bpBack(label,fn){ return '<button class="back" type="button" onclick="'+fn+'">‹ '+label+'</button>'; }
const BP_LOADING='<div class="word">⏳ Yuklanmoqda...</div>';
function bpGoList(){ openSection(SEC_BACK[BK_SEC]||'books'); }
async function loadBookDetail(){
  const d=await (await apiFetch(apiUrl('/api/books/detail/'+BPn),{cache:'no-store'})).json();
  if(!d.ok) throw new Error(d.error||'Xatolik'); BP=d; return d;
}
async function bpPost(act,data){
  const r=await apiFetch(apiUrl('/api/books/admin/'+act),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({n:BPn,kind:bqKind},data||{}))});
  return r.json();
}
// ---- rasmni telefonda kichraytirib (1600px, JPEG) base64 qilish: yuklash tez va xotira kam
function imgToB64(file,max=1600,q=0.82){
  return new Promise((res,rej)=>{
    const u=URL.createObjectURL(file), im=new Image();
    im.onload=()=>{ let w=im.naturalWidth,h=im.naturalHeight; const s=Math.min(1,max/Math.max(w,h)); w=Math.max(1,Math.round(w*s)); h=Math.max(1,Math.round(h*s));
      const c=document.createElement('canvas'); c.width=w; c.height=h; c.getContext('2d').drawImage(im,0,0,w,h); URL.revokeObjectURL(u); res(c.toDataURL('image/jpeg',q).split(',')[1]); };
    im.onerror=()=>{ URL.revokeObjectURL(u); rej(new Error('Rasm o‘qilmadi. Rasm (JPG/PNG) tanlang.')); }; im.src=u; });
}
const bpStatus=m=>{ const e=$('bpUpStatus'); if(e) e.textContent=m; };
async function bpUpload(files,target,after){
  const list=[...(files||[])]; if(!list.length) return; let ok=0, err='';
  for(let i=0;i<list.length;i++){
    bpStatus('⏳ Yuklanmoqda: '+(i+1)+' / '+list.length+' ...');
    try{ const b64=await imgToB64(list[i]); const d=await bpPost('upload',{target,image:b64}); if(d.ok) ok++; else { err=d.error||'Xatolik'; break; } }
    catch(e){ err=e.message||'Rasm o‘qilmadi'; break; }
  }
  if(target==='cover'){ delete _bUrls['img'+BPn]; delete _bUrls['thumb'+BPn]; }
  try{ await loadBookDetail(); }catch(e){}
  bpFlash=(ok?'✅ '+ok+' ta rasm yuklandi. ':'')+(err?'⚠️ '+err:''); after();
}
// ---- ro'yxatlar: Badiiy asarlar (eski loadBooks) + Premium / Esse
function itemAddForm(sec,itemName){
  return '<details class="beBulk"><summary>➕ Yangi '+escapeHtml(itemName)+' qo‘shish</summary><input id="ni_t_'+sec+'" maxlength="120" placeholder="Nomi">'
    +(sec==='gazal'?'<label class="bpLbl">💰 Narxi, so‘m (bo‘sh qoldirsangiz — standart narx)</label><input id="ni_p_gazal" type="number" inputmode="numeric" min="1000" step="1000" placeholder="Masalan: 20000">':'')
    +'<label class="bpLbl">Muqova rasmi (ixtiyoriy — bo‘lmasa avtomatik yasaladi)</label><input id="ni_f_'+sec+'" type="file" accept="image/*">'
    +'<button class="primaryAction" type="button" onclick="createItem(\''+sec+'\')">➕ Qo‘shish</button><div class="muted" id="ni_s_'+sec+'"></div></details>';
}
async function createItem(sec){
  const title=($('ni_t_'+sec).value||'').trim(); if(!title){ notify('Nomini kiriting.'); return; }
  const f=$('ni_f_'+sec).files[0]; const st=$('ni_s_'+sec); st.textContent='⏳ Saqlanmoqda...';
  try{ const body={sec,title}; if(f) body.image=await imgToB64(f); if(sec==='gazal'){ const pv=($('ni_p_gazal')?.value||'').trim(); if(pv) body.price=pv; }
    const d=await (await apiFetch(apiUrl('/api/books/admin/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
    if(!d.ok){ st.textContent='⚠️ '+(d.error||'Xatolik'); return; }
    sec==='asar'?loadBooks():loadColl(sec);
  }catch(e){ st.textContent='⚠️ '+(e.message||'Xatolik'); }
}
function collCards(items,sec){
  return items.map(it=>'<button class="bCard" type="button" onclick="openBook('+it.n+',\''+sec+'\')"><div class="bThumb" id="ct'+it.n+'"><span>⏳</span></div><span class="bName">'+escapeHtml(it.title)+'</span>'
    +'<span class="bBadges">'+(sec==='esse'?(it.files?'📎'+it.files:''):'')+(sec==='esse'?'':(sec==='gazal'?(it.owned?'✅ ':'🔒 '+fmtUzs(it.price||0)+' so‘m • '):'')+(it.files?'📎'+it.files+' ':'')+(it.videos?'🎬'+it.videos+' ':'')+(it.qn?'📝'+it.qn+' ':'')+(it.slides?'🎞'+it.slides+' ':'')+(it.has_info?'ℹ️':''))+'</span></button>').join('');
}
const PROGRESS_HTML='<div class="bProgress"><div>🚧</div><h3>Bo‘lim jarayonda</h3><p>Bu bo‘lim hozir to‘ldirilmoqda. Tez orada ochiladi — kuzatib boring!</p></div>';
async function loadColl(sec){
  const ui=COLL_UI[sec]; if(!ui) return; const gid=ui.g, aid=ui.a;
  let d; try{ d=await (await apiFetch(apiUrl('/api/books/list?sec='+sec),{cache:'no-store'})).json(); }catch(e){ return; }
  COLL[sec]=d; BK_SEC=sec; const g=$(gid), box=$(aid);
  if(sec==='premium'){ const open=!!(d.is_admin||FREE_PREMIUM_TOOLS); $('pTools').classList.toggle('hidden',!open); $('pHead').classList.toggle('hidden',!!d.soon); }
  if(box) box.innerHTML=d.is_admin?itemAddForm(sec,d.item_name)+'<p class="muted bpAdminNote">👑 Bu bo‘lim foydalanuvchilarga «Jarayonda» deb ko‘rinadi (keyinchalik pullik qilinadi). Siz hammasini ko‘ryapsiz. Qo‘shilgan '+escapeHtml(d.item_name)+' ichiga kirib: 🖼 rasm • 📝 testlar (yopiq / ochiq) • 📖 ma‘lumotlar • 📎 muhim manbalar • 🎞 taqdimot qo‘shasiz.</p>':'';
  if(sec==='gazal'){
    const pay=$('gzPay'); if(pay) pay.classList.add('hidden');
    if(box) box.innerHTML=d.is_admin?itemAddForm(sec,d.item_name)+'<p class="muted bpAdminNote">👑 Holat: '+(d.ready?'🟢 foydalanuvchilarga OCHIQ':'🔴 YOPIQ (foydalanuvchi «Jarayonda» ko‘radi)')+'. Papka qo‘shgach ichiga kirib «📎 Fayllar» va «🎬 Videodarslar» orqali yuklang. Narxni papka ichida «⚙️ Boshqarish» da o‘zgartirasiz. Botda: /gazal_royxat • /gazal_narx 7 30000 • /gazal_ochish • /gazal_yopish</p>':'';
  }
  if(MQ_SEC[sec] && box) box.innerHTML=d.is_admin?itemAddForm(sec,d.item_name)+'<p class="muted bpAdminNote">👑 Bu bo‘lim hamma foydalanuvchiga OCHIQ. Mavzu qo‘shgach ichiga kiring: 📝 Testlar → ochiq / yopiq test (qo‘lda, Word fayl yoki rasm bilan), 📖 Ma‘lumotlar, 🖼 rasm, 🎞 taqdimot. Foydalanuvchilar testni ishlasa reyting balli va seriya yig‘iladi.</p>':'';
  let ban='';
  if(sec==='esse'){
    if(box) box.innerHTML=d.is_admin?itemAddForm(sec,d.item_name)+'<p class="muted bpAdminNote">👑 Namunaviy esselar Premium obunachilarga ochiq. Qo‘shgan elementingiz ichida «📖 Ma‘lumotlar» orqali PDF fayllarni yuklang — obunachi «Faylni olish» bo‘limidan oladi. «🎬 Videodars» alohida bo‘lim: videolarni shu yerdan yuklab, tayyor bo‘lgach ochasiz.</p>':'';
    ban=''; { const _es=$('eSale'); if(_es) _es.innerHTML=esseSaleCard(d); const _e2=$('eSale2'); if(_e2) _e2.innerHTML=esseSaleCta(d); const _ab=$('eAdminBox'); if(_ab) _ab.classList.toggle('hidden',!d.is_admin); }   // v88: qulf bannerining o‘rniga pastda chegirma kartasi
  }
  if(d.soon){ g.innerHTML=PROGRESS_HTML; return; }
  if(!Array.isArray(d.items)){ g.innerHTML='<div class="word">Yuklab bo‘lmadi. Internetni tekshirib, qayta urinib ko‘ring.</div>'; return; }   // v107: xato javobda bo‘lim qotib qolmasin
  const eVid=(sec==='esse')?esseVideoCard(d):'';
  if(!d.items.length){ g.innerHTML=ban+eVid+(d.is_admin?'<div class="word">Hali '+escapeHtml(d.item_name)+' qo‘shilmagan. Yuqoridagi «➕ Yangi» orqali qo‘shing.</div>':(MQ_SEC[sec]?'<div class="word">Mavzular tez orada qo‘shiladi.</div>':'<div class="word">Namunaviy esselar tez orada qo‘shiladi.</div>')); return; }
  g.innerHTML=ban+eVid+collCards(d.items,sec);
  d.items.forEach(async it=>{ try{ const u=await bookBlob('thumb',it.n); const el=$('ct'+it.n); if(el) el.innerHTML='<img src="'+u+'" alt="">'; }catch(e){} });
}
async function openBook(n,sec){
  BK_SEC=sec||BK_SEC||'asar';
  const src=BK_SEC==='asar'?BK:COLL[BK_SEC]; const it=((src&&src.items)||[]).find(x=>x.n===n); if(!it) return;
  if(BK_SEC==='asar' && !(BK.has_access||BK.is_admin||it.free)){ notify('🔒 Asarlarni ko‘rish uchun bo‘limni oching: '+fmtUzs(BK.price)+' so‘m.'); const p=$('bPay'); if(p) p.scrollIntoView({behavior:'smooth',block:'center'}); return; }
  if(BK_SEC==='esse' && COLL.esse && COLL.esse.locked){ notify('🔒 Fayllar obunachilar uchun. Pastdagi chegirma bilan sotib oling.'); const _c=$('eSaleCard'); if(_c) _c.scrollIntoView({behavior:'smooth',block:'center'}); return; }
  openSection('bookPage'); BPn=n; BP=null; trackView('book:'+n); await renderBookHome(true);
}
async function openGeneral(n){ BK_SEC='asar'; openSection('bookPage'); BPn=n; BP=null; trackView('book:'+n); await renderBookHome(true); }
// ---- element sahifasi: tepada «Testlar», «Ma'lumotlar», «Taqdimot» (hozircha faqat admin), pastda rasmlar
async function renderBookHome(reload){
  const box=$('bpBody');
  if(reload||!BP){ box.innerHTML=BP_LOADING; try{ await loadBookDetail(); }catch(e){ box.innerHTML='<div class="result">❌ '+escapeHtml(e.message||'Server bilan bog‘lanishda xatolik.')+'</div>'; return; } }
  const d=BP, n=BPn, isGen=d.sec==='general', pics=isGen?[]:[{kind:'img',id:n}].concat((d.pics||[]).map(id=>({kind:'pic',id})));
  let top='';
  if(d.extra&&d.sec==='esse'){   // v73: Esse elementida test, taqdimot va video yo‘q — faqat PDF fayl olish
    const fn=(d.files||[]).length;
    top='<div class="bpTabs"><button class="bpTab" type="button" onclick="openEsseFiles()"><b>📖</b><span>Ma‘lumotlar</span><small>'+(fn?'📎 '+fn+' PDF':'PDF yo‘q')+'</small></button></div>'
      +(d.is_admin?'<p class="muted bpAdminNote">👑 «Ma‘lumotlar» ichiga PDF yuklaysiz. Obuna bo‘lgan foydalanuvchi shu yerdan faylni oladi.</p>':'');
  } else if(d.extra){
    const c=d.counts||{closed:0,open:0}, has=Object.values(d.sections||{}).filter(Boolean).length, sl=(d.slides||[]).length, vn=(d.videos||[]).length;
    const isGz=d.sec==='gazal', fn=(d.files||[]).length, tabs=[];
    if(isGz) tabs.push('<button class="bpTab" type="button" onclick="openGazalFiles()"><b>📎</b><span>Fayllar</span><small>'+(fn?fn+' ta fayl':'fayl yo‘q')+'</small></button>');
    if(!isGz||d.is_admin||(c.open+c.closed)) tabs.push('<button class="bpTab" type="button" onclick="openBookTests(false)"><b>📝</b><span>Testlar</span><small>'+(c.open+c.closed)+' ta savol</small></button>');
    const isPf=!!FILE_SEC[d.sec]&&d.sec!=='gazal';   // v70: Esse / Attestatsiya — Ma‘lumotlar ichida PDF fayllar ham bor
    if(!isGen&&(d.is_admin||has||(isPf&&fn))) tabs.push('<button class="bpTab" type="button" onclick="openBookInfo()"><b>📖</b><span>Ma‘lumotlar</span><small>'+(has?has+' / '+(d.section_names||[]).length+' bo‘lim':'kiritilmagan')+(isPf&&fn?' • 📎 '+fn+' PDF':'')+'</small></button>');
    if(!isGen&&d.is_admin) tabs.push('<button class="bpTab" type="button" onclick="openBookSlides()"><b>🎞</b><span>Taqdimot</span><small>'+(sl?sl+' ta slayd':'slayd yo‘q')+'</small></button>');
    if(!isGen&&(d.is_admin||vn)) tabs.push('<button class="bpTab" type="button" onclick="openBookVideos()"><b>🎬</b><span>Videodarslar</span><small>'+(vn?vn+' ta video':'video yo‘q')+'</small></button>');
    top='<div class="bpTabs">'+tabs.join('')+'</div>'
      +(d.is_admin?'<p class="muted bpAdminNote">'+(isGen?'👑 «Umumiy test» foydalanuvchilarga hozircha qulf. Savollarni «Testlar» bo‘limida yuklang. Ochish: /umumiy_ochiq':MQ_SEC[d.sec]?'👑 Testlar va Ma‘lumotlar hamma foydalanuvchiga ochiq. Taqdimot faqat sizga ko‘rinadi.':'👑 Taqdimot hozircha faqat sizga ko‘rinadi. Testlar, Ma‘lumotlar va Videodarslar to‘lov qilganlarga ochiq.')+'</p>':'')
      +((d.sample&&!d.is_admin)?'<div class="gPrice bSample"><small>🆓 Bu — bepul namuna</small><b>'+fmtUzs(BK.price||5000)+' so‘m</b><em>Barcha asarlar: testlar, qahramonlar, voqealar rivoji, muhim manbalar</em><button class="primaryAction gJoin" type="button" style="margin-top:10px" onclick="payByCard(\'books\',\'all\')">🔓 Barcha asarlarni ochish</button></div>':'');
  }
  if(!d.extra&&d.sec==='gazal'){
    const fn=(d.files||[]).length, vn=(d.videos||[]).length, tabs=[];
    tabs.push('<button class="bpTab" type="button" onclick="openGazalFiles()"><b>📎</b><span>Fayllar</span><small>'+(fn?fn+' ta fayl 🔒':'fayl yo‘q')+'</small></button>');
    if(vn) tabs.push('<button class="bpTab" type="button" onclick="openBookVideos()"><b>🎬</b><span>Videodarslar</span><small>'+vn+' ta video 🔒</small></button>');
    top='<div class="bpTabs">'+tabs.join('')+'</div>'
      +'<div class="gPrice"><small>Bu qo‘llanma narxi</small><b>'+fmtUzs(d.price||0)+' so‘m</b><em>'+((ME&&(ME.auto_pay||ME.card_auto))?'💳 To‘lov karta orqali, avtomatik • fayllar shu bot chatiga darhol yuboriladi':'💳 To‘lov karta orqali • to‘lov tasdiqlangach fayllar shu bot chatiga yuboriladi')+'</em><em>🔒 Fayllar faqat bot ichida ochiladi — ularni boshqalarga yuborib bo‘lmaydi</em><button class="primaryAction gJoin" type="button" style="margin-top:10px" onclick="payByCard(\'gazalitem\','+n+')">🔓 Sotib olish</button></div>';
  }
  box.innerHTML='<h2>'+escapeHtml(d.title)+'</h2>'+(d.author?'<p class="bpAuthor">✍️ '+escapeHtml(d.author)+'</p>':'')+top
    +'<div class="bpPics">'+pics.map((x,i)=>'<div class="bpPic" id="bpp'+i+'"><span>⏳</span></div>').join('')+'</div>'
    +((d.is_admin&&!isGen)?'<button class="bpGhost" type="button" onclick="manageItem()">⚙️ Boshqarish: nom, muqova, rasmlar, o‘chirish</button>':'');
  pics.forEach(async (x,i)=>{ try{ const u=await bookBlob(x.kind,x.id); const el=$('bpp'+i); if(el) el.innerHTML='<img alt="" src="'+u+'" onclick="viewBookImg(this.src,'+escapeHtml(JSON.stringify(d.title))+')">'; }catch(e){} });
  window.scrollTo(0,0);
}
function viewBookImg(src,title){
  $('bvTitle').textContent=title||''; $('bvImg').classList.remove('zoomed'); $('bvImg').src=src;
  $('bookViewer').classList.remove('hidden'); document.body.style.overflow='hidden';
}
// ---- Taqdimot (slaydlar)
let SLi=0;
async function openBookSlides(i){
  const d=BP, box=$('bpBody'), sl=d.slides||[]; SLi=Math.max(0,Math.min(i||0,Math.max(0,sl.length-1)));
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>🎞 Taqdimot</h2><p class="muted">'+escapeHtml(d.title)+'</p>'
    +(sl.length?'<div class="slWrap" id="slWrap"><div class="slStage" id="slStage"><img id="slImg" alt=""></div><div class="slCap" id="slCap"></div>'
        +'<div class="slNav"><button type="button" onclick="slGo(-1)">‹</button><span id="slCnt"></span><button type="button" onclick="slGo(1)">›</button></div><div class="muted slHint">Suring yoki ‹ › bosing • rasmga bosing — kattalashadi</div></div>'
      :'<div class="word">Hali slayd qo‘shilmagan.</div>')
    +(d.is_admin?'<button class="bpGhost" type="button" onclick="manageSlides()">✏️ Slaydlarni boshqarish / yuklash</button>':'');
  if(sl.length){ slShow(); const w=$('slWrap'); let x0=null;
    w.addEventListener('touchstart',e=>{ x0=e.touches[0].clientX; },{passive:true});
    w.addEventListener('touchend',e=>{ if(x0===null) return; const dx=e.changedTouches[0].clientX-x0; x0=null; if(Math.abs(dx)>45) slGo(dx<0?1:-1); },{passive:true}); }
  window.scrollTo(0,0);
}
async function slShow(){
  const sl=(BP&&BP.slides)||[]; if(!sl.length||!$('slImg')) return; const s=sl[SLi];
  $('slCnt').textContent=(SLi+1)+' / '+sl.length; $('slCap').textContent=s.caption||''; $('slCap').style.display=s.caption?'block':'none';
  try{ const u=await bookBlob('slide',s.id); if(sl[SLi]===s && $('slImg')){ $('slImg').src=u; $('slImg').onclick=()=>viewBookImg(u,BP.title); } }catch(e){}
  const nx=sl[SLi+1]; if(nx) bookBlob('slide',nx.id).catch(()=>{});   // keyingisini oldindan yuklash
}
function slGo(dir){ const n=((BP&&BP.slides)||[]).length; if(!n) return; SLi=(SLi+dir+n)%n; slShow(); }
document.addEventListener('keydown',e=>{ if(!$('slImg')||!$('slImg').isConnected) return; if(e.key==='ArrowRight') slGo(1); else if(e.key==='ArrowLeft') slGo(-1); });
function manageSlides(){
  const d=BP, box=$('bpBody'), sl=d.slides||[];
  box.innerHTML=bpBack('Taqdimot','openBookSlides('+SLi+')')+'<h2>✏️ Slaydlar</h2><p class="muted">'+escapeHtml(d.title)+' • '+sl.length+' ta slayd (80 tagacha)</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +'<label class="bpLbl">➕ Slayd(lar) yuklash</label><input id="slFiles" type="file" accept="image/*" multiple onchange="bpUpload(this.files,\'slide\',manageSlides)">'
    +'<p class="muted">PowerPoint/PDF taqdimotni avval rasm (JPG/PNG) qilib saqlang — har bir slayd bitta rasm. Tanlangan tartibda yuklanadi.</p><div id="bpUpStatus" class="muted"></div>'
    +sl.map((s,i)=>'<div class="beQ slRow"><div class="slThumb" id="slt'+s.id+'"><span>⏳</span></div><div class="slInfo"><b>'+(i+1)+'-slayd</b>'
      +'<input id="slc'+s.id+'" maxlength="300" placeholder="Izoh (ixtiyoriy)" value="'+escapeHtml(s.caption||'')+'" onchange="slCaption('+s.id+')">'
      +'<div class="slBtns"><button type="button" onclick="slMove('+s.id+',-1)">⬆️</button><button type="button" onclick="slMove('+s.id+',1)">⬇️</button><button type="button" class="beDel" onclick="slDel('+s.id+')">🗑</button></div></div></div>').join('');
  bpFlash=''; sl.forEach(async s=>{ try{ const u=await bookBlob('sthumb',s.id); const el=$('slt'+s.id); if(el) el.innerHTML='<img src="'+u+'" alt="">'; }catch(e){} });
}
async function slAct(act,data){ try{ const d=await bpPost(act,data); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadBookDetail(); manageSlides(); }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); } }
const slMove=(id,dir)=>slAct('mvslide',{id,dir});
const slCaption=id=>bpPost('capslide',{id,caption:$('slc'+id).value}).then(()=>loadBookDetail()).catch(()=>{});
function slDel(id){ bpConfirm('Bu slayd o‘chirilsinmi?',()=>slAct('rmslide',{id})); }
// ---- Admin: nom, muqova, qo'shimcha rasmlar, o'chirish
function manageItem(){
  const d=BP, box=$('bpBody');
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>⚙️ Boshqarish</h2><p class="muted">'+escapeHtml(d.title)+'</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +'<label class="bpLbl">✏️ Nomi</label><input id="miTitle" maxlength="120" value="'+escapeHtml(d.title)+'"><button class="primaryAction" type="button" onclick="saveItemTitle()">💾 Nomini saqlash</button>'
    +(d.sec==='gazal'?'<label class="bpLbl">💰 Narxi (so‘m)</label><input id="miPrice" type="number" inputmode="numeric" min="1000" step="1000" value="'+(d.price||'')+'"><button class="primaryAction" type="button" onclick="saveItemPrice()">💾 Narxni saqlash</button><p class="muted">Standart narxga qaytarish uchun 0 yozing.</p>':'')
    +'<label class="bpLbl">🗂 Muqovani almashtirish</label><input type="file" accept="image/*" onchange="bpUpload(this.files,\'cover\',manageItem)">'
    +'<label class="bpLbl">🖼 Qo‘shimcha rasm qo‘shish</label><input type="file" accept="image/*" multiple onchange="bpUpload(this.files,\'pic\',manageItem)"><div id="bpUpStatus" class="muted"></div>'
    +((d.pics||[]).length?'<div class="bpPicGrid">'+d.pics.map(id=>'<div class="bpPicCell"><div id="mp'+id+'"><span>⏳</span></div><button type="button" class="beDel" onclick="rmPic('+id+')">🗑</button></div>').join('')+'</div>':'<p class="muted">Qo‘shimcha rasm yo‘q.</p>')
    +'<button class="beDel" style="margin-top:18px;width:100%" type="button" onclick="deleteItem()">🗑 Butun '+escapeHtml(d.item_name||'bo‘lim')+'ni o‘chirish</button>';
  bpFlash=''; (d.pics||[]).forEach(async id=>{ try{ const u=await bookBlob('pic',id); const el=$('mp'+id); if(el) el.innerHTML='<img src="'+u+'" alt="">'; }catch(e){} });
}
async function saveItemPrice(){
  const v=parseInt(($('miPrice').value||'').trim()||'0',10);
  try{ const d=await bpPost('setprice',{price:isNaN(v)?0:v}); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadBookDetail(); bpFlash='✅ Narx saqlandi: '+fmtUzs(d.price)+' so‘m.'; manageItem(); }catch(e){ notify('Xatolik'); }
}
async function saveItemTitle(){
  const t=$('miTitle').value.trim(); if(!t){ notify('Nomini kiriting.'); return; }
  try{ const d=await bpPost('rename',{title:t}); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadBookDetail(); bpFlash='✅ Nom saqlandi.'; manageItem(); }catch(e){ notify('Xatolik'); }
}
function rmPic(id){ bpConfirm('Bu rasm o‘chirilsinmi?',async()=>{ try{ const d=await bpPost('rmpic',{id}); if(d.ok){ await loadBookDetail(); manageItem(); } else notify(d.error||'Xatolik'); }catch(e){ notify('Xatolik'); } }); }
function deleteItem(){ bpConfirm('Butun bo‘lim (rasmlar, slaydlar, testlar, ma‘lumotlar) O‘CHIRILADI. Davom etasizmi?',async()=>{ try{ const d=await bpPost('delitem',{}); if(d.ok) bpGoList(); else notify(d.error||'Xatolik'); }catch(e){ notify('Xatolik'); } }); }

// ---- Testlar: Ochiq test / Yopiq test
async function openBookTests(reload){
  const box=$('bpBody');
  if(reload){ box.innerHTML=BP_LOADING; try{ await loadBookDetail(); }catch(e){ box.innerHTML='<div class="result">❌ '+escapeHtml(e.message||'Xatolik')+'</div>'; return; } }
  const d=BP, c=d.counts||{closed:0,open:0}, b=d.best||{};
  const card=(k,ico,name,desc)=>{ const cnt=c[k]||0, bs=b[k]&&b[k].best!=null?' • eng yaxshi natija: <b>'+b[k].best+'%</b>':'';
    return '<div class="result bpKind"><h4>'+ico+' '+name+'</h4><p class="muted">'+desc+'<br>'+cnt+' ta savol'+bs+'</p>'
      +(cnt?'<button class="primaryAction" type="button" onclick="startBookQuiz(\''+k+'\')">🚀 Boshlash</button>':'<p class="muted">Savollar hali qo‘shilmagan.</p>')
      +(d.is_admin?'<button class="bpGhost" type="button" onclick="openBookEditor(\''+k+'\')">✏️ Savollarni tahrirlash / qo‘shish</button>':'')+'</div>'; };
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>📝 Testlar</h2><p class="muted">'+escapeHtml(d.title)+'</p>'
    +card('open','✍️','Ochiq test','Javobni o‘zingiz yozasiz.')+card('closed','🔘','Yopiq test','Variantlardan to‘g‘ri javobni tanlaysiz.');
  window.scrollTo(0,0);
}
async function startBookQuiz(kind){
  bqKind=kind; bqAns={}; const box=$('bpBody'); box.innerHTML=BP_LOADING;
  try{
    const d=await (await apiFetch(apiUrl('/api/books/quiz/'+BPn+'?kind='+kind),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML=bpBack('Testlar','openBookTests(false)')+'<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    const L='ABCDEF';
    box.innerHTML=bpBack('Testlar','openBookTests(false)')+'<div class="bqHead">'+(kind==='open'?'✍️ Ochiq test':'🔘 Yopiq test')+' — '+escapeHtml(d.title)+'</div>'
      +d.questions.map(q=>'<div class="qcard" id="bq'+q.number+'"><div class="qtop">'+q.number+'-savol</div><div class="question qr">'+rich(q.text)+'</div>'
        +(kind==='open'?'<input class="bqOpen" data-q="'+q.number+'" placeholder="Javobingizni yozing" maxlength="200" autocomplete="off">'
          :'<div class="answers">'+q.options.map((o,i)=>'<button type="button" class="sopt bqopt" data-q="'+q.number+'" data-v="'+L[i]+'"><b>'+L[i]+'</b> <span class="qr">'+rich(o)+'</span></button>').join('')+'</div>')+'</div>').join('')
      +'<button class="primaryAction" type="button" onclick="submitBookQuiz('+d.questions.length+')">✅ Natijani ko‘rish</button><div id="bqResult"></div>';
    window.scrollTo(0,0);
  }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; }
}
document.addEventListener('click',e=>{
  const b=e.target.closest('.bqopt'); if(!b) return;
  document.querySelectorAll('.bqopt[data-q="'+b.dataset.q+'"]').forEach(x=>x.classList.remove('selected')); b.classList.add('selected'); bqAns[b.dataset.q]=b.dataset.v;
});
function bqExtras(d){   // v66: reyting balli va seriya (Mashq bo‘limlari)
  let h='';
  const st=d.streak; if(st&&st.current>0){ try{ ME.streak={current:st.current,best:st.best,done_today:true}; renderStreak(); }catch(e){} h+='<p>🔥 <b>'+st.current+' kunlik seriya!</b>'+(st.new_today?' Bugungi mashq hisoblandi.':'')+'</p>'; }
  const r=d.rating; if(r){
    if(r.first) h+='<p>⭐ <b>+'+r.gained+' ball</b> reytingga qo‘shildi'+(r.today_points?' (bugun jami: '+r.today_points+')':'')+'.</p>';
    else h+='<p class="muted">Bu testdan bugun ball allaqachon olgansiz. Ertaga yana ball olasiz.</p>';
    if(r.week_rank) h+='<p>🏅 Haftalik reyting: <b>'+r.week_rank+'-o‘rin</b> ('+r.week_pts+' ball, '+r.week_players+' ishtirokchi)</p>';
  }
  return h; }
async function submitBookQuiz(total){
  const ans={};
  if(bqKind==='open') document.querySelectorAll('.bqOpen').forEach(i=>{ const v=i.value.trim(); if(v) ans[i.dataset.q]=v; }); else Object.assign(ans,bqAns);
  const left=total-Object.keys(ans).length;
  if(left>0 && !confirm(left+' ta savolga javob berilmagan. Baribir yakunlaysizmi?')) return;
  try{
    const d=await (await apiFetch(apiUrl('/api/books/quiz'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({n:BPn,kind:bqKind,answers:ans})})).json();
    if(!d.ok){ notify(d.error||'Xatolik'); return; }
    d.review.forEach(r=>{ const c=$('bq'+r.number); if(!c) return; c.classList.add(r.is_ok?'bqOk':'bqBad');
      if(bqKind==='open'){ const inp=c.querySelector('.bqOpen'); if(inp) inp.disabled=true; }
      else c.querySelectorAll('.bqopt').forEach(x=>{ x.disabled=true; if(x.dataset.v===r.correct) x.classList.add('right'); else if(x.dataset.v===r.user) x.classList.add('wrong'); });
      const right=bqKind==='open'?escapeHtml(r.correct_text):escapeHtml(r.correct);
      c.insertAdjacentHTML('beforeend','<div class="bqNote">'+(r.is_ok?'✅ To‘g‘ri. ':'❌ To‘g‘ri javob: <b>'+right+'</b>. ')+(r.explanation?'<span class="qr">'+rich(r.explanation)+'</span>':'')+'</div>'); });
    $('bqResult').innerHTML='<div class="result"><div class="scoreBig">'+d.percent+'%</div><p>To‘g‘ri: <b>'+d.correct+' / '+d.total+'</b></p>'+(MQ_SEC[BK_SEC]?(d.percent>=90?'<p>🏆 Ajoyib natija!</p>':d.percent>=60?'<p>👍 Yaxshi! Xatolaringizni ko‘rib chiqing.</p>':'<p>📖 Mavzuni takrorlab, qayta urinib ko‘ring.</p>'):(d.percent>=90?'<p>🏆 Ajoyib! Asarni a’lo darajada bilasiz.</p>':d.percent>=60?'<p>👍 Yaxshi! Xatolaringizni ko‘rib chiqing.</p>':'<p>📖 Asarni yana bir bor o‘qib, qayta urinib ko‘ring.</p>'))+bqExtras(d)
      +'<button class="primaryAction" type="button" onclick="startBookQuiz(bqKind)">🔄 Qayta urinish</button><button class="bpGhost" type="button" onclick="openBookTests(true)">‹ Testlarga qaytish</button></div>';
    $('bqResult').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
// ---- Ma'lumotlar: Asar qahramonlari / Muhim ma'lumotlar / Voqealar rivoji
function openBookInfo(key){
  if(BP&&BP.sec==='esse'){ openEsseFiles(); return; }   // v73
  const d=BP, box=$('bpBody'), names=d.section_names||[], sec=d.sections||{};
  if(key) bpInfoKey=key; if(!bpInfoKey||!names.some(x=>x.key===bpInfoKey)) bpInfoKey=(names.find(x=>sec[x.key])||names[0]||{}).key;
  const cur=sec[bpInfoKey]||'';
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>📖 Ma‘lumotlar</h2><p class="muted">'+escapeHtml(d.title)+'</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +'<div class="bpSubTabs">'+names.map(x=>'<button type="button" class="bpSub'+(x.key===bpInfoKey?' on':'')+'" onclick="openBookInfo(\''+x.key+'\')"><b>'+x.icon+'</b><span>'+escapeHtml(x.name)+'</span></button>').join('')+'</div>'
    +'<div class="result bpInfo"><div class="bpText">'+(cur?bpRich(cur):'<span class="muted">Bu bo‘lim hali to‘ldirilmagan.</span>')+'</div></div>'
    +(d.is_admin?'<button class="bpGhost" type="button" onclick="editBookInfo()">✏️ Ma‘lumotlarni kiritish / tahrirlash</button>':'')
    +pdfBlock();
  bpFlash=''; window.scrollTo(0,0);
}
function editBookInfo(){
  const d=BP, box=$('bpBody'), sec=d.sections||{}, names=d.section_names||[];
  box.innerHTML=bpBack('Ma‘lumotlar','openBookInfo()')+'<h2>✏️ Ma‘lumotlarni kiritish</h2><p class="muted">'+escapeHtml(d.title)+'</p>'
    +'<label class="bpLbl">✍️ Muallif</label><input id="biAuthor" maxlength="120" placeholder="Masalan: Abdulla Qodiriy" value="'+escapeHtml(d.author||'')+'">'
    +names.map(x=>'<label class="bpLbl">'+x.icon+' '+escapeHtml(x.name)+'</label><textarea id="bi_'+x.key+'" rows="7" maxlength="8000" placeholder="'+escapeHtml(x.key==='sources'?'Havola (https://...), kitob yoki maqola nomlari — har birini yangi qatordan yozing':x.name+' haqida yozing...')+'">'+escapeHtml(sec[x.key]||'')+'</textarea>').join('')
    +'<button class="primaryAction" type="button" onclick="saveBookInfo()">💾 Saqlash</button><p class="muted">Bo‘limni bo‘sh qoldirsangiz — o‘chiriladi. Har bir bo‘lim 8000 belgigacha.</p>';
  window.scrollTo(0,0);
}
async function saveBookInfo(){
  const data={author:$('biAuthor').value.trim()}; (BP.section_names||[]).forEach(x=>{ data[x.key]=$('bi_'+x.key).value; });
  try{ const d=await bpPost('info',data); if(!d.ok){ notify(d.error||'Saqlab bo‘lmadi'); return; }
    BP.sections=d.sections; BP.author=d.author; notify('✅ Saqlandi.'); openBookInfo(); }
  catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
// ---- Admin: test savollarini kiritish (mini ilova ichida)
let beOptN=4;
const BE_SAMPLE={closed:'1. Asar muallifi kim?\nA) Oybek\nB) Abdulla Qodiriy\nC) Cho‘lpon\nJavob: B\nIzoh: ixtiyoriy\n\n2. Keyingi savol...',
                 open:'1. Asarning bosh qahramoni kim?\nJavob: Otabek | Yusufbek hoji o‘g‘li Otabek\nIzoh: ixtiyoriy\n\n2. Keyingi savol...'};
async function openBookEditor(kind){
  if(kind) bqKind=kind; const box=$('bpBody'); box.innerHTML=BP_LOADING; beOptN=4;
  let d; try{ d=await (await apiFetch(apiUrl('/api/books/admin/'+BPn),{cache:'no-store'})).json(); }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; return; }
  if(!d.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
  const open=bqKind==='open', qs=d.questions.filter(q=>q.kind===bqKind);
  const list=qs.length?qs.map(q=>'<div class="beQ"><div class="beQtop"><b>'+q.number+'.</b> <span class="qr">'+rich(q.text)+'</span></div>'
      +'<div class="muted">✅ '+(open?escapeHtml((q.accepted||[]).join(' / ')):escapeHtml(q.answer)+') '+rich((q.options||[])['ABCDEF'.indexOf(q.answer)]||''))+'</div>'
      +(!open&&q.options.length?'<div class="muted beOptsLine">'+q.options.map((o,i)=>'ABCDEF'[i]+') '+rich(o)).join(' • ')+'</div>':'')
      +'<button class="beDel" type="button" onclick="delBookQ('+q.id+')">🗑 O‘chirish</button></div>').join(''):'<div class="word">Hali savol yo‘q.</div>';
  const optInputs=Array.from({length:beOptN},(_,i)=>'<input class="beOpt rt" maxlength="800" placeholder="'+'ABCDEF'[i]+' varianti">').join('');
  const form=open
    ?'<textarea id="beText" class="rt" rows="3" maxlength="6000" placeholder="Savol matni"></textarea><textarea id="beAcc" rows="3" maxlength="1500" placeholder="To‘g‘ri javob(lar) — har biri alohida qatorda yoki | bilan ajrating.\nMasalan: Otabek"></textarea>'
    :'<textarea id="beText" class="rt" rows="3" maxlength="6000" placeholder="Savol matni"></textarea><div id="beOpts">'+optInputs+'</div><button class="bpGhost" type="button" id="beMore" onclick="addBeOpt()">＋ variant qo‘shish</button>'
      +'<select id="beAns">'+'ABCDEF'.split('').map(l=>'<option value="'+l+'">To‘g‘ri javob: '+l+'</option>').join('')+'</select>';
  box.innerHTML=bpBack('Testlar','openBookTests(true)')+'<h2>✏️ '+(open?'Ochiq test':'Yopiq test')+'</h2><p class="muted">'+escapeHtml(d.title)+' • '+qs.length+' ta savol</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +'<h3 class="bpH3">➕ Yangi savol</h3>'+rtBar()+form+'<input id="beExp" maxlength="1000" placeholder="Izoh (ixtiyoriy) — natijada ko‘rsatiladi">'
    +'<button class="primaryAction" type="button" onclick="saveBookQ()">➕ Savolni qo‘shish</button>'
    +'<details class="beBulk"><summary>📥 Ko‘p savolni bir yo‘la qo‘shish</summary><textarea id="beBulk" class="rt" rows="9" maxlength="60000" placeholder="'+escapeHtml(BE_SAMPLE[bqKind])+'"></textarea><button class="primaryAction" type="button" onclick="bulkBookQ()">📥 Hammasini qo‘shish</button><p class="muted">Xato bo‘lsa hech narsa saqlanmaydi.</p></details>'
    +'<details class="beBulk" open><summary>📄 Word (.docx) fayldan yuklash</summary>'+DOCX_HELP+'<input type="file" id="beDocx" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"><button class="primaryAction" type="button" onclick="uploadBookDocx()">📄 Word faylni yuklash</button><div id="beDocxSt" class="muted"></div></details>'
    +'<h3 class="bpH3">📋 Mavjud savollar</h3>'+list
    +(qs.length?'<button class="beDel" style="margin-top:12px" type="button" onclick="clearBookQ()">🧹 Shu testning hammasini o‘chirish</button>':'');
  bpFlash=''; window.scrollTo(0,0);
}
function addBeOpt(){
  if(beOptN>=6) return; const inp=document.createElement('input'); inp.className='beOpt rt'; inp.maxLength=800; inp.placeholder='ABCDEF'[beOptN]+' varianti';
  $('beOpts').appendChild(inp); beOptN++; if(beOptN>=6) $('beMore').classList.add('hidden');
}
async function saveBookQ(){
  const text=$('beText').value.trim(); let options, answer='';
  if(bqKind==='open'){ options=$('beAcc').value.split(/\n|\|/).map(x=>x.trim()).filter(Boolean); }
  else{
    const raw=[...document.querySelectorAll('.beOpt')].map(i=>i.value.trim()); const sel='ABCDEF'.indexOf($('beAns').value);
    if(!raw[sel]){ notify('To‘g‘ri javob sifatida tanlangan variant bo‘sh.'); return; }
    options=raw.filter(Boolean); answer='ABCDEF'[raw.slice(0,sel).filter(Boolean).length];
  }
  try{ const d=await bpPost('add',{text,options,answer,explanation:$('beExp').value.trim()});
    if(!d.ok){ notify(d.error||'Saqlab bo‘lmadi'); return; }
    bpFlash='✅ Savol qo‘shildi. Jami: '+d.count+' ta.'; openBookEditor(); }
  catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
async function bulkBookQ(){
  const text=$('beBulk').value.trim(); if(!text){ notify('Savollarni yozing.'); return; }
  try{ const d=await bpPost('bulk',{text}); if(!d.ok){ notify(d.error||'Saqlab bo‘lmadi'); return; }
    bpFlash='✅ '+d.added+' ta savol qo‘shildi. Jami: '+d.count+' ta.'; openBookEditor(); }
  catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
function bpConfirm(msg,go){ if(tg?.showConfirm) tg.showConfirm(msg,ok=>{ if(ok) go(); }); else if(confirm(msg)) go(); }
function delBookQ(id){ bpConfirm('Bu savol o‘chirilsinmi?',async()=>{ try{ const d=await bpPost('delete',{id}); if(!d.ok){ notify(d.error||'Xatolik'); return; } bpFlash='🗑 Savol o‘chirildi.'; openBookEditor(); }catch(e){ notify('Xatolik'); } }); }
function clearBookQ(){ bpConfirm('Shu testdagi BARCHA savollar o‘chirilsinmi?',async()=>{ try{ const d=await bpPost('clear',{}); if(d.ok){ bpFlash='🧹 '+d.deleted+' ta savol o‘chirildi.'; openBookEditor(); } else notify(d.error||'Xatolik'); }catch(e){ notify('Xatolik'); } }); }

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
    return `<div class="skRow" data-n="${i}"><b>${i}</b><div class="skBtns">${skL.split('').map(x=>`<button type="button" data-n="${i}" data-v="${x}">${x}</button>`).join('')}</div><button type="button" class="skTxtBtn" data-t="${i}" title="Savol matni qo‘shish">✏️</button></div><textarea class="skText rt hidden" id="skt_${i}" rows="2" maxlength="6000" placeholder="${i}-savol matni (ixtiyoriy)"></textarea>`; }).join('');
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
  return '<div class="result">'+h+'<button class="primaryAction" type="button" style="background:linear-gradient(135deg,#e0a000,#a8872f);color:#2e2403" onclick="openTop('+escapeHtml(JSON.stringify(kind))+','+escapeHtml(JSON.stringify(code))+')">🏆 Test reytingi (TOP-10)</button></div>';
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
  const tsb=$('topStreak'); if(tsb){ const ss=ME.streak; if(ME.ok){ tsb.innerHTML='🔥 <b>'+((ss&&ss.current)||0)+'</b> kun'; tsb.classList.remove('hidden'); } else tsb.classList.add('hidden'); }
  const b=$('streakBar'); if(!b) return; const s=ME.streak;
  if(!ME.ok||!s){ b.classList.add('hidden'); return; }
  b.innerHTML=s.current>0
    ?'🔥 <b>'+s.current+' kunlik seriya</b> • eng yaxshisi: '+s.best+(s.done_today?' • bugun ✅':' • bugun mashq qiling, seriya uzilmasin!')
    :'🔥 Seriyani boshlang: bugun test ishlang yoki esse yozing va har kuni davom eting!';
  b.classList.remove('hidden');
}
async function openPanelLegacy(){
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

const APP_VERSION='v110';
function renderVersion(){
  const b=$('verBar'); if(!b) return;
  if(!(ME&&ME.is_admin)){ b.innerHTML=''; return; }   // v89: versiya faqat adminga ko'rinadi
  const sv=ME.version||'';
  b.innerHTML='Mini App '+APP_VERSION+(sv?' • bot '+escapeHtml(sv):'')+(sv&&sv!==APP_VERSION?'<br>⚠️ Versiyalar mos emas: bot va Mini App fayllarini birga yangilang.':'');
}

// ===== v31: reyting tepasidagi seriya kartasi =====
function streakHeroHtml(d){
  const cur=d.current, g=d.goal||{}, medal=cur>=30?'👑':cur>=14?'🏅':cur>=7?'🥇':cur>=3?'🥈':'🔥';
  const msg=cur===0
    ?'Seriyani bugun boshlang — bitta test yoki esse yetarli!'
    :d.done_today
      ?'Bugungi mashq hisoblandi ✅ Ertaga ham davom eting!'
      :'⚠️ Bugun mashq qilmasangiz, '+cur+' kunlik seriyangiz uziladi!';
  const days=(d.week||[]).map(w=>'<div class="shDay '+(w.active?'on ':'')+(w.today?'today ':'')+(w.future?'fut':'')+'"><i>'+(w.active?'✓':(w.today?'•':''))+'</i><span>'+w.label+'</span></div>').join('');
  const goal=g.next?('<div class="shGoal"><div class="shBar"><u style="width:'+Math.max(6,g.pct)+'%"></u></div><small>'+(g.left===1?'Yana <b>1 kun</b>':'Yana <b>'+g.left+' kun</b>')+' — <b>'+g.next+' kunlik</b> medalga!</small></div>'):'<div class="shGoal"><small>🏆 Eng yuqori bosqich — siz afsonasiz!</small></div>';
  const lead=(d.leaders&&d.leaders.length)?('<div class="shLead"><b>🔥 Seriya yetakchilari</b>'+d.leaders.map(l=>'<div class="'+(l.me?'me':'')+'"><i>'+['🥇','🥈','🥉'][l.rank-1]+'</i><span>'+escapeHtml(l.name)+(l.me?' (siz)':'')+'</span><em>'+l.days+' kun</em></div>').join('')+(d.rank&&d.rank>3?'<p>Siz hozir '+d.rank+'-o‘rindasiz. Yetakchilarga yeting!</p>':'')+'</div>'):'';
  const cta=d.done_today?'':'<button class="shCta" type="button" onclick="openSection(\'growth\')">✍️ Bugun mashq qilish</button>';
  return '<div class="shTop"><div class="shFlame">'+medal+'</div><div class="shNum"><b>'+cur+'</b><span>kunlik seriya</span></div><div class="shBest">Eng yaxshi<br><b>'+d.best+'</b> kun</div></div><div class="shMsg">'+msg+'</div><div class="shWeek">'+days+'</div>'+goal+cta+lead;
}
async function loadStreakHero(){
  const box=$('streakHero'); if(!box) return;
  try{
    const d=await (await apiFetch(apiUrl('/api/streak'),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML=''; return; }
    box.innerHTML=streakHeroHtml(d);
  }catch(e){ box.innerHTML=''; }
}

// ---- Admin: ko'rishlar statistikasi (Statistikam sahifasi tagida)
async function loadViewStats(){
  let box=$('viewStatsBox');
  if(!ME||!ME.is_admin){ if(box) box.remove(); return; }
  if(!box){ box=document.createElement('div'); box.id='viewStatsBox'; $('admin').appendChild(box); }
  box.innerHTML='<div class="word">⏳ Ko‘rishlar yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/viewstats'),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML=''; return; }
    const per=[['today','Bugun'],['week','7 kun'],['month','30 kun'],['all','Hammasi']];
    window._vs=d; window._vsKey=window._vsKey||'week';
    const draw=()=>{ const k=window._vsKey, x=d[k];
      box.innerHTML='<h3 class="bpH3">👁 Mini App ko‘rishlari <small class="muted">(faqat admin)</small></h3>'
        +'<div class="bpSubTabs" style="grid-template-columns:repeat(4,1fr)">'+per.map(([key,name])=>'<button type="button" class="bpSub'+(key===k?' on':'')+'" onclick="window._vsKey=\''+key+'\';loadViewStats()"><span>'+name+'</span></button>').join('')+'</div>'
        +'<div class="result"><b>'+x.views+'</b> ta ko‘rish • <b>'+x.users+'</b> ta alohida foydalanuvchi</div>'
        +(x.items.length?x.items.map((i,n)=>'<div class="beQ"><div class="beQtop">'+(n+1)+'. '+escapeHtml(i.name)+'</div><div class="muted">👁 '+i.views+' ta • 👤 '+i.users+' kishi</div></div>').join(''):'<div class="word">Hali ma’lumot yo‘q.</div>'); };
    draw();
  }catch(e){ box.innerHTML=''; }
}

// ===== v37: boy matn (qalin/qiya/chiziq/indeks), rasm, jadval + Word (.docx) import =====
// Belgilash: [b]..[/b] [i]..[/i] [u]..[/u] [sup]..[/sup] [sub]..[/sub] [img:ID] [tbl]A|B¶1|2[/tbl]
function _rtInline(s){
  const re=/\[(\/?)(b|i|u|sup|sub)\]|\[img:(\d+)\]/g; let out='', last=0, m; const st=[];
  while((m=re.exec(s))){
    out+=s.slice(last,m.index); last=re.lastIndex;
    if(m[3]){ out+='<img class="qimg" data-qimg="'+m[3]+'" alt="">'; continue; }
    const t=m[2];
    if(!m[1]){ st.push(t); out+='<'+t+'>'; }
    else{
      const k=st.lastIndexOf(t); if(k<0) continue;
      const again=[]; while(st.length>k+1){ const x=st.pop(); out+='</'+x+'>'; again.push(x); }
      st.pop(); out+='</'+t+'>';
      while(again.length){ const x=again.pop(); st.push(x); out+='<'+x+'>'; }
    }
  }
  out+=s.slice(last); while(st.length) out+='</'+st.pop()+'>';
  return out;
}
function rich(s){
  const h=escapeHtml(s);
  return h.split(/(\[tbl\][\s\S]*?\[\/tbl\])/).map(p=>{
    const m=p.match(/^\[tbl\]([\s\S]*)\[\/tbl\]$/);
    if(!m) return _rtInline(p);
    return '<div class="qtblWrap"><table class="qtbl">'+m[1].split('¶').map(r=>'<tr>'+r.split('|').map(c=>'<td>'+_rtInline(c)+'</td>').join('')+'</tr>').join('')+'</table></div>';
  }).join('');
}
const _qimgCache={};
async function qimgUrl(id){
  if(_qimgCache[id]) return _qimgCache[id];
  const r=await apiFetch(apiUrl('/api/qimg/'+id),{cache:'force-cache'}); if(!r.ok) throw new Error('x');
  return _qimgCache[id]=URL.createObjectURL(await r.blob());
}
function hydrateQimgs(){
  document.querySelectorAll('img[data-qimg]:not([data-hyd])').forEach(im=>{
    im.dataset.hyd='1';
    qimgUrl(im.dataset.qimg).then(u=>{ im.src=u; im.classList.add('ok'); }).catch(()=>{ im.alt='🖼 (rasm yuklanmadi)'; });
  });
}
(function(){ const go=()=>{ hydrateQimgs(); new MutationObserver(hydrateQimgs).observe(document.body,{childList:true,subtree:true}); }; if(document.body) go(); else document.addEventListener('DOMContentLoaded',go); })();
document.addEventListener('click',e=>{
  const im=e.target.closest('img.qimg.ok'); if(!im) return;
  e.preventDefault(); e.stopPropagation();
  showModal('<img class="qimgBig" src="'+im.src+'" alt="">');
},true);

// --- asboblar paneli
let RT_LAST=null;
function rtBar(withTable=true){
  const sel=(cls,n,from,def)=>'<select class="'+cls+'">'+Array.from({length:n},(_,k)=>'<option'+((k+from)===def?' selected':'')+'>'+(k+from)+'</option>').join('')+'</select>';
  return '<div class="rtBar"><div class="rtRow">'
    +'<button type="button" data-rt="b" title="Qalin"><b>B</b></button><button type="button" data-rt="i" title="Qiya"><i>I</i></button><button type="button" data-rt="u" title="Tagiga chizish"><u>U</u></button>'
    +'<button type="button" data-rt="sup" title="Yuqori indeks">x²</button><button type="button" data-rt="sub" title="Quyi indeks">x₂</button>'
    +'<span class="adminOnly'+((typeof ME!=='undefined'&&ME.is_admin)?'':' hidden')+'"><button type="button" data-rt="img" title="Rasm qo‘shish (admin)">🖼 Rasm</button><input type="file" class="rtFile hidden" accept="image/*"></span>'
    +'</div><div class="rtRow"><span class="muted">Jadval:</span>'+sel('rtCols',6,2,2)+'<span class="muted">ustun ×</span>'+sel('rtRows',10,2,3)+'<span class="muted">qator</span>'
    +'<button type="button" data-rt="tbl">▦ Jadval qo‘shish</button></div>'
    +'<div class="muted rtHint">Matnni belgilab, so‘ng B / I / U ni bosing. Avval kerakli maydonni bosing.</div></div>'
    +'<div class="rtPrev question qr hidden"></div>';
}
document.addEventListener('focusin',e=>{ const t=e.target; if(t&&t.classList&&t.classList.contains('rt')) RT_LAST=t; });
document.addEventListener('mousedown',e=>{ if(e.target.closest('.rtBar button')) e.preventDefault(); });
document.addEventListener('click',e=>{ const b=e.target.closest('.rtBar button[data-rt]'); if(b) rtAct(b); });
document.addEventListener('change',e=>{ if(e.target.classList&&e.target.classList.contains('rtFile')) rtPickImage(e.target); });
document.addEventListener('input',e=>{ const t=e.target; if(t&&t.classList&&t.classList.contains('rt')) rtPrevUpdate(t); });
function rtPrevUpdate(t){
  let n=t.parentElement, pv=null; while(n&&!pv){ pv=n.querySelector('.rtPrev'); n=n.parentElement; }
  if(!pv) return; const v=(t.value||'').trim(); pv.innerHTML=v?rich(t.value):''; pv.classList.toggle('hidden',!v);
}
function rtInsertAt(el,txt,selA,selB){
  const a=el.selectionStart??el.value.length, b=el.selectionEnd??a;
  el.value=el.value.slice(0,a)+txt+el.value.slice(b);
  const from=a+(selA??txt.length), to=a+(selB??selA??txt.length);
  try{ el.focus(); el.setSelectionRange(from,to); }catch(e){}
  el.dispatchEvent(new Event('input',{bubbles:true}));
}
function rtAct(b){
  const k=b.dataset.rt, bar=b.closest('.rtBar'), el=(RT_LAST&&document.body.contains(RT_LAST))?RT_LAST:null;
  if(!el){ notify('Avval savol yoki variant yoziladigan maydonni bosing.'); return; }
  if(k==='img'){ if(!ME.is_admin){ notify('Rasm yuklash faqat admin uchun.'); return; } bar.querySelector('.rtFile').click(); return; }
  if(k==='tbl'){
    const c=+bar.querySelector('.rtCols').value, r=+bar.querySelector('.rtRows').value;
    const head=Array.from({length:c},(_,j)=>'Ustun '+(j+1)).join('|');
    const rows=[head]; for(let i=1;i<r;i++) rows.push(Array(c).fill(' ').join('|'));
    rtInsertAt(el,'[tbl]'+rows.join('¶')+'[/tbl]',5,5+'Ustun 1'.length); return;
  }
  const a=el.selectionStart??0, z=el.selectionEnd??a, o='['+k+']', cl='[/'+k+']';
  if(a===z) rtInsertAt(el,o+cl,o.length,o.length);
  else{ const sel=el.value.slice(a,z); rtInsertAt(el,o+sel+cl,o.length,o.length+sel.length); }
}
async function rtPickImage(inp){
  const f=inp.files&&inp.files[0]; inp.value=''; if(!f) return;
  const el=(RT_LAST&&document.body.contains(RT_LAST))?RT_LAST:null; if(!el){ notify('Avval maydonni bosing.'); return; }
  const hint=inp.closest('.rtBar').querySelector('.rtHint'), old=hint.textContent; hint.textContent='⏳ Rasm yuklanmoqda...';
  try{
    const b64=await imgToB64(f,1400,0.85);
    const d=await (await apiFetch(apiUrl('/api/qimg/upload'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:b64})})).json();
    if(!d.ok){ notify(d.error||'Rasm yuklanmadi'); } else rtInsertAt(el,'[img:'+d.id+']');
  }catch(e){ notify(e.message||'Rasm yuklanmadi'); }
  hint.textContent=old;
}

// --- Word (.docx)
const DOCX_HELP='<p class="muted">Word faylda har bir savol yangi qatordan, shu ko‘rinishda bo‘lsin:<br><b>1. Savol matni</b><br>A) variant &nbsp; B) variant ...<br><b>Javob: B</b><br>Izoh: ixtiyoriy<br>Ochiq testda: <b>Javob: javob1 | javob2</b>. Qalin, qiya, tagiga chiziq, jadval va rasmlar saqlanadi. Faqat .docx (eski .doc emas).</p>';
function fileToDataUrl(f){ return new Promise((res,rej)=>{ const r=new FileReader(); r.onload=()=>res(r.result); r.onerror=()=>rej(new Error('Fayl o‘qilmadi')); r.readAsDataURL(f); }); }
async function uploadBookDocx(){
  const f=$('beDocx')?.files?.[0]; const st=$('beDocxSt');
  if(!f){ notify('Avval Word (.docx) faylni tanlang.'); return; }
  if(!/\.docx$/i.test(f.name)){ notify('Faqat .docx fayl qabul qilinadi. Word’da «Saqlash → .docx» qiling.'); return; }
  if(f.size>8*1024*1024){ notify('Fayl 8 MB dan oshmasin.'); return; }
  st.textContent='⏳ Yuklanmoqda va tekshirilmoqda...';
  try{
    const d=await bpPost('docx',{file:await fileToDataUrl(f)});
    if(!d.ok){ st.textContent='❌ '+(d.error||'Xatolik'); return; }
    bpFlash='✅ Word fayldan '+d.added+' ta savol qo‘shildi. Jami: '+d.count+' ta.'+((d.warnings||[]).length?' ⚠️ '+d.warnings.join(' '):''); openBookEditor();
  }catch(e){ st.textContent='❌ '+(e.message||'Server bilan bog‘lanishda xatolik.'); }
}
async function simpleDocx(){
  const f=$('sDocx')?.files?.[0];
  if(!f){ notify('Avval Word (.docx) faylni tanlang.'); return; }
  if(!/\.docx$/i.test(f.name)){ notify('Faqat .docx fayl qabul qilinadi.'); return; }
  if(f.size>8*1024*1024){ notify('Fayl 8 MB dan oshmasin.'); return; }
  $('sPreview').textContent='⏳ Word fayl o‘qilmoqda...'; parsedSimple=null; $('sCreateBtn').classList.add('hidden');
  try{
    const d=await (await apiFetch(apiUrl('/api/simple/docx'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file:await fileToDataUrl(f)})})).json();
    if(!d.ok){ $('sPreview').textContent='❌ '+(d.error||'Xatolik'); return; }
    parsedSimple=d.questions; $('sPreview').textContent='✅ Word fayldan '+d.questions.length+' ta savol aniqlandi.'+((d.warnings||[]).length?' ⚠️ '+d.warnings.join(' '):'');
    $('sCreateBtn').classList.remove('hidden');
  }catch(e){ $('sPreview').textContent='❌ '+(e.message||'Server bilan bog‘lanishda xatolik.'); }
}
document.querySelectorAll('.rtMount').forEach(m=>{ m.innerHTML=rtBar(true); });

// ===== v38: Videodarslar (Telegram file_id orqali) =====
function fmtDur(s){ s=+s||0; if(!s) return ''; const m=Math.floor(s/60), r=s%60; return m+':'+String(r).padStart(2,'0'); }
function openBookVideos(){
  const d=BP, box=$('bpBody'), vs=d.videos||[];
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>🎬 Videodarslar</h2><p class="muted">'+escapeHtml(d.title)+' • '+vs.length+' ta video</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +(vs.length?vs.map((v,i)=>'<button class="bpTab vidRow" type="button" onclick="playBookVideo('+v.id+')"><b>'+((d.sec==='gazal'&&!d.owned)?'🔒':'▶️')+'</b><span>'+(i+1)+'. '+escapeHtml(v.title)+'</span><small>'+(fmtDur(v.duration)||'video')+'</small></button>').join('')
      :'<div class="word">Hali video qo‘shilmagan.</div>')
    +'<p class="muted">Videoni bossangiz, u shu bot chatiga yuboriladi (saqlash va ulashish yopiq).</p>'
    +(d.is_admin?'<button class="bpGhost" type="button" onclick="manageVideos()">✏️ Videolarni boshqarish / yuklash</button>':'');
  bpFlash=''; window.scrollTo(0,0);
}
async function playBookVideo(id){
  try{
    const r=await apiFetch(apiUrl('/api/books/video/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    const d=await r.json();
    if(!d.ok){ notify(d.error||'Video yuborilmadi.'); return; }
    notify('🎬 Video bot chatiga yuborildi. Botga o‘tib ko‘ring.');
    try{ setTimeout(()=>tg.close(),900); }catch(e){}
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
function manageVideos(){
  const d=BP, box=$('bpBody'), vs=d.videos||[];
  box.innerHTML=bpBack('Videodarslar','openBookVideos()')+'<h2>✏️ Videolar</h2><p class="muted">'+escapeHtml(d.title)+' • '+vs.length+' ta video</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +'<label class="bpLbl">➕ Yangi videodars</label><input id="vidTitle" maxlength="150" placeholder="Dars nomi (ixtiyoriy)">'
    +'<button class="primaryAction" type="button" onclick="startVideoUpload()">🎬 Video qo‘shishni boshlash</button>'
    +'<p class="muted">Tugmani bosgach botga o‘ting va videoni yuboring (ketma-ket bir nechta ham mumkin). Video izohiga (caption) nom yozsangiz, shu nom bo‘ladi. Tugatish: /asar_tamom. Katta videoni «fayl» sifatida emas, oddiy video qilib yuboring.</p>'
    +vs.map((v,i)=>'<div class="beQ"><b>'+(i+1)+'.</b> '+(fmtDur(v.duration)?'<span class="muted">'+fmtDur(v.duration)+'</span>':'')
      +'<input id="vt'+v.id+'" maxlength="150" value="'+escapeHtml(v.title)+'" onchange="vidRename('+v.id+')">'
      +'<div class="slBtns"><button type="button" onclick="vidAct(\'mvvideo\',{id:'+v.id+',dir:-1})">⬆️</button><button type="button" onclick="vidAct(\'mvvideo\',{id:'+v.id+',dir:1})">⬇️</button><button type="button" class="beDel" onclick="vidDel('+v.id+')">🗑</button></div></div>').join('');
  bpFlash='';
}
async function startVideoUpload(){
  try{
    const d=await bpPost('vidmode',{title:($('vidTitle').value||'').trim()});
    if(!d.ok){ notify(d.error||'Xatolik'); return; }
    bpFlash='✅ Tayyor! Endi botga o‘ting va videoni yuboring. Tugatgach /asar_tamom yozing, so‘ng bu yerga qaytib sahifani yangilang.'; manageVideos();
    try{ setTimeout(()=>tg.close(),1500); }catch(e){}
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
async function vidAct(act,data){ try{ const d=await bpPost(act,data); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadBookDetail(); manageVideos(); }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); } }
const vidRename=id=>bpPost('renvideo',{id,title:$('vt'+id).value}).then(()=>loadBookDetail()).catch(()=>{});
function vidDel(id){ bpConfirm('Bu video o‘chirilsinmi?',()=>vidAct('rmvideo',{id})); }


// ===== G'azal tahlilini o'rganamiz: fayllar (Telegram file_id; fayl bot chatiga protect_content bilan yuboriladi)
function gzSize(b){ b=+b||0; if(!b) return ''; return b>=1048576?(b/1048576).toFixed(1)+' MB':Math.max(1,Math.round(b/1024))+' KB'; }
function gzType(f){ const m=(f.mime||'').toLowerCase(); if(m.includes('pdf')) return 'PDF'; if(m.includes('word')||m.includes('wordprocessing')) return 'Word'; if(m.includes('presentation')||m.includes('powerpoint')) return 'Slayd'; if(m.includes('sheet')||m.includes('excel')) return 'Excel'; if(m.startsWith('audio')) return 'Audio'; if(m.startsWith('video')) return 'Video'; return 'Fayl'; }
function openGazalFiles(){
  const d=BP, box=$('bpBody'), fs=d.files||[];
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>📎 Fayllar</h2><p class="muted">'+escapeHtml(d.title)+' • '+fs.length+' ta fayl</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +(fs.length?fs.map((f,i)=>'<button class="bpTab vidRow" type="button" onclick="sendGazalFile('+f.id+')"><b>'+(d.owned?'📥':'🔒')+'</b><span>'+(i+1)+'. '+escapeHtml(f.title)+'</span><small>'+gzType(f)+(gzSize(f.size)?' • '+gzSize(f.size):'')+'</small></button>').join('')
      :'<div class="word">Hali fayl qo‘shilmagan.</div>')
    +(d.owned?'<p class="muted">Faylni bossangiz, u shu bot chatiga yuboriladi. 🔒 Fayl faqat bot ichida ochiladi: uni boshqalarga yuborish (forward) va saqlash yopiq. Tarqatish taqiqlanadi.</p>':'<p class="muted">🔒 Fayllarni olish uchun qo‘llanmani sotib oling ('+fmtUzs(d.price||0)+' so‘m). Sotib olgach fayllar shu bot chatiga yuboriladi.</p>')
    +(d.is_admin?'<button class="bpGhost" type="button" onclick="manageGazalFiles()">✏️ Fayllarni boshqarish / yuklash</button>':'');
  bpFlash=''; window.scrollTo(0,0);
}
let _gzBusy=false;
async function sendGazalFile(id){
  if(_gzBusy) return; _gzBusy=true;
  try{
    const r=await apiFetch(apiUrl('/api/gazal/file/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});
    const d=await r.json();
    if(!d.ok){ notify(d.error||'Fayl yuborilmadi.'); return; }
    notify('📎 Fayl bot chatiga yuborildi. Botga o‘tib oching.');
    try{ setTimeout(()=>tg.close(),900); }catch(e){}
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
  finally{ setTimeout(()=>{ _gzBusy=false; },1500); }
}
function manageGazalFiles(){
  const d=BP, box=$('bpBody'), fs=d.files||[];
  const pf=!!FILE_SEC[d.sec]&&d.sec!=='gazal';
  box.innerHTML=bpBack(pf?'Ma‘lumotlar':'Fayllar',pf?(d.sec==='esse'?'openEsseFiles()':'openBookInfo()'):'openGazalFiles()')+'<h2>✏️ '+(pf?'PDF fayllar':'Fayllar')+'</h2><p class="muted">'+escapeHtml(d.title)+' • '+fs.length+' ta fayl</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +(pf?pdfUploadForm():'')
    +'<label class="bpLbl">➕ Yangi fayl</label><input id="gzTitle" maxlength="150" placeholder="Fayl nomi (ixtiyoriy)">'
    +'<button class="'+(pf?'bpGhost':'primaryAction')+'" type="button" onclick="startGazalUpload()">📎 '+(pf?'Boshqa usul: botga o‘tib yuborish (Word va h.k.)':'Fayl qo‘shishni boshlash')+'</button>'
    +'<p class="muted">Tugmani bosgach botga o‘ting va faylni «Fayl» (document) qilib yuboring — PDF, Word va boshqalar, ketma-ket bir nechta ham mumkin. Izohga (caption) nom yozsangiz shu nom bo‘ladi. Tugatish: /asar_tamom. Fayl serverda emas, Telegram’da saqlanadi.</p>'
    +fs.map((f,i)=>'<div class="beQ"><b>'+(i+1)+'.</b> <span class="muted">'+gzType(f)+(gzSize(f.size)?' • '+gzSize(f.size):'')+'</span>'
      +'<input id="gf'+f.id+'" maxlength="150" value="'+escapeHtml(f.title)+'" onchange="gzRename('+f.id+')">'
      +'<div class="slBtns"><button type="button" onclick="gzAct(\'mvfile\',{id:'+f.id+',dir:-1})">⬆️</button><button type="button" onclick="gzAct(\'mvfile\',{id:'+f.id+',dir:1})">⬇️</button><button type="button" class="beDel" onclick="gzDel('+f.id+')">🗑</button></div></div>').join('');
  bpFlash='';
}
async function startGazalUpload(){
  try{
    const d=await bpPost('filemode',{title:($('gzTitle').value||'').trim()});
    if(!d.ok){ notify(d.error||'Xatolik'); return; }
    bpFlash='✅ Tayyor! Endi botga o‘ting va faylni yuboring. Tugatgach /asar_tamom yozing, so‘ng bu yerga qaytib sahifani yangilang.'; manageGazalFiles();
    try{ setTimeout(()=>tg.close(),1500); }catch(e){}
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
async function gzAct(act,data){ try{ const d=await bpPost(act,data); if(!d.ok){ notify(d.error||'Xatolik'); return; } await loadBookDetail(); manageGazalFiles(); }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); } }
const gzRename=id=>bpPost('renfile',{id,title:$('gf'+id).value}).then(()=>loadBookDetail()).catch(()=>{});
function gzDel(id){ bpConfirm('Bu fayl o‘chirilsinmi?',()=>gzAct('rmfile',{id})); }

// ===== v71: MOCK yakuniy natija sahifasi (daraja shkalasi, sinf bilan taqqoslash, mavzular, dinamika, ustuvor takrorlash, PDF hisobot)
function mkLvlColor(l){ return ({NC:'#d9534f',C:'#e0a000','C+':'#e0a000',B:'#5fb88a','B+':'#3a9a6b',A:'#1f8a5b','A+':'#0e6e4a'})[l]||'#8aa398'; }
function mkPctColor(p){ return p>=70?'#1f8a5b':(p>=40?'#e0a000':'#d9534f'); }
function mkScale(d){
  const r=d.result||{}, bands=d.bands||[], sc=Number(r.combined_score_75)||0, n=bands.length; if(!n) return '';
  let pos=0; bands.forEach((b,i)=>{ if(sc>=b.from&&sc<b.to) pos=(i+(sc-b.from)/(b.to-b.from))/n*100; }); if(sc>=75) pos=98;
  pos=Math.max(3,Math.min(97,pos));
  return '<div class="mkScale"><div class="mkSegs">'+bands.map(b=>'<i style="background:'+mkLvlColor(b.level)+'"></i>').join('')+'<b class="mkMark" style="left:'+pos+'%">'+sc+'</b></div><div class="mkLbls">'+bands.map(b=>'<span>'+escapeHtml(b.level)+'</span>').join('')+'</div></div>';
}
function mkSpark(h){
  if(!h||h.length<2) return '<p class="muted">Keyingi mockdan keyin bu yerda ball dinamikasi paydo bo‘ladi.</p>';
  const v=h.map(x=>Number(x.score)), lo=Math.min(...v,40), hi=Math.max(...v,60), W=300, H=90;
  const pts=v.map((y,i)=>[20+(W-40)*i/(v.length-1), 14+(H-34)*(1-(y-lo)/Math.max(hi-lo,1))]);
  return '<svg viewBox="0 0 '+W+' '+(H+14)+'" width="100%" role="img" aria-label="Mocklar bo‘yicha ball dinamikasi"><polyline points="'+pts.map(q=>q.join(',')).join(' ')+'" fill="none" stroke="#0b5a41" stroke-width="2.5"/>'
    +pts.map((q,i)=>'<circle cx="'+q[0]+'" cy="'+q[1]+'" r="4.5" fill="#e0a000"/><text x="'+q[0]+'" y="'+(q[1]-9)+'" font-size="11" font-weight="700" text-anchor="middle" fill="#0d2b22">'+v[i].toFixed(1)+'</text><text x="'+q[0]+'" y="'+(H+10)+'" font-size="10" text-anchor="middle" fill="#5f7a6e">'+escapeHtml(String(h[i].title||'').slice(0,14))+'</text>').join('')+'</svg>';
}
function renderMockResult(d,id){
  const r=d.result||{}, cs=r.class_stats||null, h=d.history||[], fr=(r.fan_report||[]).slice().sort((a,b)=>a.correct_pct-b.correct_pct);
  const lv=(r.level&&r.level!=='Sertifikat berilmadi')?r.level:'NC', nl=r.next_level, sc=Number(r.combined_score_75)||0;
  const prev=h.length>=2?h[h.length-2]:null, delta=prev?Math.round((sc-Number(prev.score))*10)/10:null;
  let o='<button class="back" onclick="openSection(\'mock\')">‹ Mock</button>';
  if(r.no_essay) o+='<div class="result" style="border-left:4px solid #c0392b">⚠️ <b>Esse balli bo‘lmagani uchun test natijangiz hisoblanmadi.</b> Mock natijasi = test + esse. Keyingi mockda esseni (bepul AI yoki ekspert orqali) albatta tekshirtiring.</div>';
  o+='<div class="result mkHero"><div class="mkTitle">🎓 '+escapeHtml(d.title||'Mock')+' — yakuniy natija</div><div class="scoreBig">'+sc+'<small>/75</small></div>'
    +'<div class="mkChips"><span class="mkLvl" style="background:'+mkLvlColor(lv)+'">'+escapeHtml(lv)+'</span>'
    +(r.place?'<span>🏅 '+r.place+'-o‘rin / '+r.total+'</span>':'')+(cs?'<span>Top '+cs.top_pct+'%</span>':'')
    +(delta!=null?'<span class="'+(delta>=0?'mkUp':'mkDn')+'">'+(delta>=0?'▲ +':'▼ ')+delta+' oldingi mockdan</span>':'')+'</div>'
    +mkScale(d)+'<p class="muted" style="text-align:center;margin:6px 0 0">'+(nl?'<b>'+escapeHtml(nl.level)+'</b> darajaga yana <b>'+nl.need+'</b> ball kerak ('+nl.at+' ball)':(lv==='A+'?'Eng yuqori darajadasiz 🎉':(sc>=60?'':'📜 Sertifikat uchun <b>B+</b> (60 ball) kerak — yana <b>'+(Math.round((60-sc)*10)/10)+'</b> ball')))+'</p></div>';
  o+='<div class="result"><h4 style="margin:0 0 8px">🧪 Ball tarkibi</h4><div class="mkGrid"><div><span>Test</span><b>'+r.score_75+'/75</b><small>'+r.raw_score+'/'+r.max_score+' to‘g‘ri</small></div>'
    +(r.has_essay===false?'':'<div><span>Esse</span><b>'+(r.essay_score!=null?r.essay_75+'/75':'—')+'</b><small>'+(r.essay_score!=null?r.essay_score+'/24':'tekshirilmagan')+'</small></div>')+'</div><p class="muted" style="margin:8px 0 0">'+(r.has_essay===false?'Umumiy ball = test T-bali (bu fanda esse yo‘q)':'Umumiy ball = (test + esse) ÷ 2')+'</p></div>';
  if(cs){
    const df=Math.round((sc-cs.mean)*10)/10;
    o+='<div class="result"><h4 style="margin:0 0 8px">👥 Sinf bilan taqqoslash</h4><div class="mkGrid"><div><span>Sizning ball</span><b>'+sc+'</b></div><div><span>O‘rtacha</span><b>'+cs.mean+'</b></div><div><span>Mediana</span><b>'+cs.median+'</b></div><div><span>Eng yaxshi</span><b>'+cs.best+'</b></div></div>'
      +'<p class="muted" style="margin:8px 0 0">O‘rtachadan <b style="color:'+(df>=0?'#1f8a5b':'#d9534f')+'">'+(df>=0?'+':'')+df+'</b> ball. Siz ishtirokchilarning <b>'+cs.percentile+'%</b> idan yuqori natija ko‘rsatdingiz ('+cs.n+' ta ishtirokchi).</p></div>';
  }
  const MK_MOTIV={'A+':'🏆 Ajoyib! Siz eng yuqori darajadasiz. Shu marrani ushlab turing!','A':'🌟 Juda yaxshi! A+ ga oz qoldi — zaif mavzularni mustahkamlang.','B+':'💪 Yaxshi natija, sertifikat qo‘lingizda! Endi A darajaga intiling.','B':'📈 Yaxshi harakat! B+ va sertifikatga juda yaqinsiz — davom eting.','C+':'🔥 Yo‘l ochiq: tizimli takrorlash bilan keyingi mockda B+ ga yetasiz.','C':'🚀 Boshlanish yomon emas. Har kuni mashq qiling — natija tez o‘sadi.','NC':'🌱 Hozircha chegaradan pastsiz, lekin keyingi mockda yaxshilash imkoningiz katta.'};
  o+='<div class="result" style="text-align:center"><b>'+(MK_MOTIV[lv]||'')+'</b></div>';
  const lvls=cs&&cs.levels, LVO=['A+','A','B+','B','C+','C','NC'];
  if(lvls){
    const mx=Math.max.apply(null,LVO.map(k=>lvls[k]||0).concat([1]));
    o+='<div class="result"><h4 style="margin:0 0 8px">📊 Darajalar bo‘yicha taqsimot</h4>'+LVO.map(k=>{const c=lvls[k]||0, me=(k===lv);
      return '<div class="mkFan"><div class="mkFanH"><b>'+k+(me?' ← siz':'')+'</b><span>'+c+' ta</span></div><div class="mkBar"><i style="width:'+Math.max(2,Math.round(100*c/mx))+'%;background:'+mkLvlColor(k)+';'+(me?'outline:2px solid #e0a000':'')+'"></i></div></div>';}).join('')+'</div>';
  }
  const t10=r.top10||[];
  if(t10.length){
    const medal=['🥇','🥈','🥉'];
    o+='<div class="result"><h4 style="margin:0 0 8px">🏆 TOP-10</h4>'+t10.map(x=>'<div class="mkPri" style="'+(x.me?'background:#fff6d9;border-radius:8px;':'')+'"><b>'+(x.rank<=3?medal[x.rank-1]:x.rank+'.')+'</b><span>'+escapeHtml(x.name)+(x.me?' (siz)':'')+'</span><em>'+x.final+' • '+escapeHtml(x.level)+'</em></div>').join('')+'</div>';
  }
  if(fr.length){
    o+='<div class="result"><h4 style="margin:0 0 8px">📚 Mavzular bo‘yicha</h4>'+fr.map(f=>{
      const cp=f.class_pct!=null?Math.round(f.class_pct):null;
      return '<div class="mkFan"><div class="mkFanH"><b>'+escapeHtml(f.name)+'</b><span style="color:'+mkPctColor(f.correct_pct)+'">'+f.correct_pct+'%</span></div><div class="mkBar"><i style="width:'+f.correct_pct+'%;background:'+mkPctColor(f.correct_pct)+'"></i>'+(cp!=null?'<u style="left:'+cp+'%"></u>':'')+'</div>'
        +'<small>'+(f.wrong.length?'xato: '+f.wrong.map(x=>'#'+escapeHtml(String(x))).join(', '):'xato yo‘q ✅')+(cp!=null?' • sinf o‘rtachasi '+cp+'%':'')+'</small></div>';
    }).join('')+'<p class="muted" style="margin:6px 0 0">Oq chiziq — sinf o‘rtachasi. Avval eng pastdan boshlab takrorlang.</p></div>';
  }
  const pr=r.priority||[];
  if(pr.length){
    o+='<div class="result"><h4 style="margin:0 0 4px">🎯 Avval shularni qayta o‘rganing</h4><p class="muted" style="margin:0 0 6px">Sinf ko‘pchiligi topgan, lekin siz xato qilgan savollar eng muhim.</p>'
      +pr.map(x=>'<div class="mkPri"><b>#'+escapeHtml(String(x.item))+'</b><span>'+escapeHtml(x.fan||'')+'</span><em>'+(x.class_pct!=null?'sinfda '+Math.round(x.class_pct)+'%':'')+'</em></div>').join('')+'</div>';
  }
  o+='<div class="result"><h4 style="margin:0 0 6px">📈 Mocklar dinamikasi</h4>'+mkSpark(h)+'</div>';
  const er=r.errors||[];
  o+='<details class="result mkDet"><summary><b>❌ Xatolar tafsiloti: '+er.length+'</b></summary>'+er.map(x=>`<div class="errorCard"><b>${x.number}-savol</b><br>Siz: ${escapeHtml(x.user_text!=null?x.user_text:JSON.stringify(x.user))}<br>To‘g‘ri: ${escapeHtml(x.correct_text!=null?x.correct_text:JSON.stringify(x.correct))}<br>${escapeHtml(x.explanation||'')}</div>`).join('')+'</details>';
  const _wk=fr.filter(f=>f.correct_pct<70).slice(0,3);
  if(_wk.length) o+='<div class="result"><h4 style="margin:0 0 6px">🎯 Keyingi mockgacha shularni mustahkamlang</h4>'+_wk.map(f=>'<div class="mkPri"><b>'+escapeHtml(f.name)+'</b><span>'+f.correct_pct+'%</span></div>').join('')+'<button class="primaryAction" type="button" style="margin-top:10px" onclick="openSection(\'games\')">🎮 Mashq qilishni boshlash</button></div>';
  if(!r.no_essay&&ME&&ME.ref_link) o+='<button class="listbtn" type="button" onclick="mockShareResult('+sc+',\''+String(lv==='NC'?'—':lv)+'\')">📤 Natijamni do‘stlarga ulashish</button>';
  o+=ansKeyBox(d.code||r.code,'mock',id);
  o+=(r.cert_eligible?'<p class="muted">📜 Sertifikatingiz botdagi chatga yuborilgan.</p>':'<p class="muted">📜 Mock sertifikati faqat B+, A va A+ darajalar uchun beriladi.</p>');
  $('nationalResult').innerHTML=o; window.scrollTo(0,0);
}
function mockShareResult(sc,lv){ if(!ME||!ME.ref_link) return; openShare(ME.ref_link,'🎓 Men Milliy sertifikat mockida '+sc+'/75 ball oldim (daraja: '+lv+')! Sen ham o‘zingni sinab ko‘r 👇'); }
let _mkRepBusy=false;
async function sendMockReport(id){
  if(_mkRepBusy) return; _mkRepBusy=true; const b=$('mkRepBtn'); if(b){ b.disabled=true; b.textContent='⏳ Hisobot tayyorlanmoqda...'; }
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/my-report'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})})).json();
    notify(d.ok?'✅ PDF hisobot botga yuborildi. Botni oching.':(d.error||'Xatolik'));
  }catch(e){ notify('Hisobotni yuborishda xatolik.'); }
  _mkRepBusy=false; if(b){ b.disabled=false; b.textContent='📄 PDF hisobotni botga yuborish'; }
}

// ===== v71: MOCK natijalarining chuqur tahlili (ustoz/admin): ishonchlilik, sertifikat chegarasi, mavzu x daraja, esse-test, shubhali kalitlar, dinamika
function mkAlphaColor(a){ return a>=0.8?'#1f8a5b':(a>=0.7?'#3b9a6d':(a>=0.5?'#e0a000':'#d9534f')); }
function renderMockDeep(a,trend,mock){
  const I=a.insights||{}, E=escapeHtml; let h='<div class="result mkDeepBox"><h3 style="margin:0 0 8px">🧠 Chuqur tahlil</h3>';
  if((I.headlines||[]).length) h+='<div class="mkHL">'+I.headlines.map(x=>'<p>• '+E(x)+'</p>').join('')+'</div>';
  if((I.actions||[]).length) h+='<div class="mkAct"><b>💡 Ustoz uchun amaliy qadamlar</b>'+I.actions.map((x,i)=>'<p>'+(i+1)+'. '+E(x)+'</p>').join('')+'</div>';
  const R=I.reliability;
  h+='<h4 class="mkH4">📐 Test ishonchliligi</h4>';
  h+=R?'<div class="mkGrid"><div><span>KR-20 (α)</span><b style="color:'+mkAlphaColor(R.alpha)+'">'+R.alpha+'</b><small>'+E(R.label)+'</small></div><div><span>O‘lchov xatosi</span><b>±'+R.sem+'</b><small>savol ('+R.k+' ta band, '+R.n+' kishi)</small></div></div><p class="muted" style="margin:6px 0 0">0.8 dan yuqori: ball ishonchli. 0.7 dan past: shubhali savollarni almashtiring.'+(R.small_n?' Ishtirokchilar kam, natija taxminiy.':'')+'</p>':'<p class="muted">Hisoblash uchun ishtirokchilar yoki farqlovchi savollar yetarli emas (kamida 8 kishi).</p>';
  const C=I.cert;
  if(C){
    h+='<h4 class="mkH4">📜 Sertifikat chegarasi (46 ball)</h4><div class="mkGrid"><div><span>O‘tganlar</span><b style="color:#1f8a5b">'+C.pass_n+'</b><small>'+C.pass_pct+'%</small></div><div><span>O‘tmaganlar</span><b style="color:#d9534f">'+C.fail_n+'</b><small>NC</small></div></div>';
    if((C.edge||[]).length) h+='<p class="muted" style="margin:8px 0 2px"><b>Chegaraga 3 ball ichida pastda:</b></p>'+C.edge.map(x=>'<div class="mkPri"><b>'+E(x.name)+'</b><span>'+x.final+' ball</span><em>C ga '+x.need+' ball</em></div>').join('');
    if((C.near_next||[]).length) h+='<details class="mkDet2"><summary>Keyingi darajaga yaqinlar ('+C.near_next.length+')</summary>'+C.near_next.map(x=>'<div class="mkPri"><b>'+E(x.name)+'</b><span>'+E(x.level)+' → '+E(x.next)+'</span><em>'+x.need+' ball</em></div>').join('')+'</details>';
  }
  const F=I.fan_levels;
  if(F&&(F.rows||[]).length){
    h+='<h4 class="mkH4">🧩 Mavzu × daraja kesimi</h4><p class="muted" style="margin:0 0 6px">Har daraja guruhi shu mavzuda necha foiz to‘g‘ri yechgan. Kuchli va kuchsiz guruh farqi eng katta mavzu ajratuvchi hisoblanadi.</p><div class="mkMat mkMatH"><span></span>'+F.groups.map((g,i)=>'<span>'+E(g)+'<small>'+(F.counts[F.keys[i]]||0)+'</small></span>').join('')+'<span>Farq</span></div>'
      +F.rows.map(r=>'<div class="mkMat"><b>'+E(r.name)+'</b>'+F.keys.map(k=>{const v=r.groups[k];return '<span style="'+(v==null?'':'background:'+mkPctColor(v)+';color:#fff')+'">'+(v==null?'—':v+'%')+'</span>';}).join('')+'<span>'+(r.gap==null?'—':'+'+r.gap)+'</span></div>').join('');
  }
  const Es=I.essay;
  if(Es){
    h+='<h4 class="mkH4">📝 Esse va test</h4><div class="mkGrid"><div><span>Test (o‘rtacha)</span><b>'+(Es.mean_test!=null?Es.mean_test:'—')+'</b><small>75 ballik</small></div><div><span>Esse (o‘rtacha)</span><b>'+(Es.mean_essay!=null?Es.mean_essay:'—')+'</b><small>75 ballik</small></div></div>'
      +'<p class="muted" style="margin:6px 0 0">'+(Es.corr!=null?'Test va esse bog‘liqligi (r) = <b>'+Es.corr+'</b>. ':'')+(Es.missing?'Esse yo‘q: '+Es.missing+' ta'+((Es.missing_names||[]).length?' ('+Es.missing_names.map(E).join(', ')+')':'')+'.':'Hammada esse bor.')+'</p>';
    if((Es.gap||[]).length) h+='<details class="mkDet2"><summary>Esse va test o‘rtasida katta farq ('+Es.gap.length+')</summary>'+Es.gap.map(x=>'<div class="mkPri"><b>'+E(x.name)+'</b><span>test '+x.test+' • esse '+x.essay+'</span><em style="color:'+(x.diff<0?'#d9534f':'#1f8a5b')+'">'+(x.diff>0?'+':'')+x.diff+'</em></div>').join('')+'</details>';
  }
  const fc=I.flag_counts||{};
  if((I.flags||[]).length){
    h+='<h4 class="mkH4">🔎 Tekshirish kerak bo‘lgan savollar</h4><p class="muted" style="margin:0 0 6px">Kalit shubhali: '+(fc.key||0)+' • juda qiyin: '+(fc.hard||0)+' • juda oson: '+(fc.easy||0)+' • farqlamaydi: '+(fc.flat||0)+'</p>'
      +I.flags.map(f=>'<div class="mkFlag'+(f.key?' key':'')+'"><b>#'+E(String(f.item))+'</b> <span>'+f.pct+'% to‘g‘ri</span><small>'+f.reasons.map(E).join(' • ')+'</small></div>').join('');
  }
  const tr=(trend||[]).slice(); if(mock&&!tr.some(x=>x.code===mock.code)&&a.summary) tr.push({title:mock.title,mean:a.summary.mean,n:a.n,pass_pct:a.summary.pass_pct});
  if(tr.length>=2) h+='<h4 class="mkH4">📈 Sinf dinamikasi (mocklar bo‘yicha o‘rtacha)</h4>'+mkSpark(tr.map(x=>({title:x.title,score:x.mean})))+'<p class="muted" style="margin:4px 0 0">'+tr.map(x=>E(x.title)+': '+x.mean+(x.pass_pct!=null?' ('+x.pass_pct+'% o‘tgan)':'')).join(' • ')+'</p>';
  else h+='<h4 class="mkH4">📈 Sinf dinamikasi</h4><p class="muted">Kamida 2 ta mock natijasi e‘lon qilingach, o‘rtacha ball dinamikasi shu yerda chiqadi.</p>';
  return h+'</div>';
}

// ===== v70: Esse va Attestatsiya — Ma‘lumotlar ichida PDF fayllar (Mini App'dan yuklanadi, bot orqali Telegram'ga ketadi; Render xotirasida saqlanmaydi)
const FILE_SEC={esse:1,attest:1,gazal:1};
const PDF_MAX_MB=14;
function pdfUploadForm(){
  return '<div class="result bpInfo"><label class="bpLbl">📎 PDF yuklash</label><input id="pdfTitle" maxlength="150" placeholder="Fayl nomi (ixtiyoriy)">'
    +'<input id="pdfFile" type="file" accept="application/pdf,.pdf" multiple>'
    +'<button class="primaryAction" type="button" id="pdfBtn" onclick="uploadPdfs()">📤 PDF ni botga yuklash</button><div id="pdfSt" class="muted"></div>'
    +'<p class="muted">PDF avtomatik botga yuboriladi va Telegram’da saqlanadi (serverda joy egallamaydi). Har bir fayl '+PDF_MAX_MB+' MB gacha. Bir nechta PDF ni birdan tanlash mumkin.</p></div>';
}
function pdfBlock(){
  const d=BP; if(!FILE_SEC[d.sec]||d.sec==='gazal') return '';
  const fs=d.files||[];
  return '<h3 class="bpH3">📎 PDF fayllar</h3>'
    +(fs.length?fs.map((f,i)=>'<button class="bpTab vidRow" type="button" onclick="sendGazalFile('+f.id+')"><b>📥</b><span>'+(i+1)+'. '+escapeHtml(f.title)+'</span><small>'+gzType(f)+(gzSize(f.size)?' • '+gzSize(f.size):'')+'</small></button>').join('')
        +'<p class="muted">Faylni bossangiz, u shu bot chatiga yuboriladi. 🔒 Fayl faqat bot ichida ochiladi (forward va saqlash yopiq).</p>'
      :'<div class="word">Hali PDF yuklanmagan.</div>')
    +(d.is_admin?pdfUploadForm()+'<button class="bpGhost" type="button" onclick="manageGazalFiles()">✏️ PDF fayllarni boshqarish (nom, tartib, o‘chirish)</button>':'');
}
function fileToB64(f){ return new Promise((res,rej)=>{ const r=new FileReader(); r.onload=()=>res(String(r.result).split(',',2)[1]||''); r.onerror=()=>rej(new Error('Fayl o‘qilmadi')); r.readAsDataURL(f); }); }
let _pdfBusy=false;
async function uploadPdfs(){
  if(_pdfBusy) return;
  const inp=$('pdfFile'), st=$('pdfSt'), btn=$('pdfBtn'), list=[...((inp&&inp.files)||[])];
  if(!list.length){ notify('Avval PDF faylni tanlang.'); return; }
  for(const f of list){
    if(!/\.pdf$/i.test(f.name)&&f.type!=='application/pdf'){ notify('Faqat PDF qabul qilinadi: '+f.name); return; }
    if(f.size>PDF_MAX_MB*1024*1024){ notify('«'+f.name+'» '+PDF_MAX_MB+' MB dan katta. Hajmini kamaytiring.'); return; }
  }
  const title=(($('pdfTitle')||{}).value||'').trim();
  _pdfBusy=true; if(btn) btn.disabled=true; let ok=0, err='';
  for(let i=0;i<list.length;i++){
    st.textContent='⏳ Botga yuklanmoqda: '+(i+1)+' / '+list.length+' ('+list[i].name+') ...';
    try{
      const b64=await fileToB64(list[i]);
      const d=await bpPost('pdfup',{file:b64,name:list[i].name,title:(list.length===1?title:'')});
      if(d.ok) ok++; else { err=d.error||'Xatolik'; break; }
    }catch(e){ err=e.message||'Server bilan bog‘lanishda xatolik.'; break; }
  }
  _pdfBusy=false; if(btn) btn.disabled=false;
  try{ await loadBookDetail(); }catch(e){}
  bpFlash=(ok?'✅ '+ok+' ta PDF botga yuklandi va saqlandi. ':'')+(err?'⚠️ '+err:'');
  const h=document.querySelector('#bpBody h2'); if(h&&/✏️/.test(h.textContent)) manageGazalFiles(); else if(BP&&BP.sec==='esse') openEsseFiles(); else openBookInfo();
}

// ===== v56: Ustoz paneli / Ustoz Pro (Milliy sertifikat va oddiy test tahlili) =====
let TCH=null, tchKind='ms';
function openTeacher(){ openSection('teacher'); }
async function tchPost(path,body){
  try{ const r=await apiFetch(apiUrl(path),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); return await r.json(); }
  catch(e){ return {ok:false,error:'Server bilan bog‘lanishda xatolik.'}; }
}
async function loadTeacher(){
  try{ if(typeof clsEnter==='function' && await clsEnter()) return; }catch(e){ console.error(e); }   // v109: sinf nazorati / ota-ona bo‘limi
  const box=$('teacherBody'); box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/teacher/overview'),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    TCH=d; renderTeacher();
  }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; }
}
function tchKindSet(k){ tchKind=k; renderTeacher(); }
function renderTeacher(){
  const d=TCH, p=d.pro, J=x=>escapeHtml(JSON.stringify(x)), box=$('teacherBody');
  const hero='<div class="tHero"><b>Sinfingiz natijasini bir qarashda ko‘ring</b><p>Milliy sertifikat va oddiy testlar bo‘yicha batafsil tahlil, o‘quvchilarga chegirma va ustoz ulushi.</p></div>';
  const perks=[['📊','Sinf hisoboti (PDF)','Umumiy ball, toifalar, fanlar kesimi'],['🏆','Ishtirokchilar reytingi','Rasch, esse, yakuniy ball, daraja'],['🎯','Sust va kuchli savollar','Ko‘p tanlangan xato javob bilan'],['📈','O‘quvchi rivoji','Ball dinamikasi, o‘sish va pasayish'],['🎟','O‘quvchilarga −30% chegirma','Shaxsiy havolangiz orqali'],['🪙','Ustoz ulushi','Havola orqali kelgan o‘quvchilar uchun bonus']]
    .map(x=>'<div class="tPerk"><b>'+x[0]+'</b><div><strong>'+x[1]+'</strong><small>'+x[2]+'</small></div></div>').join('');
  let pro;
  if(p.active){
    pro='<div class="tPro on">✅ <b>Ustoz Pro faol</b>'+(p.admin?' (admin)':(p.until?' — '+escapeHtml(p.until)+' gacha':''))+'<small>Hamma tahlillar va PDF hisobotlar ochiq.'+(p.admin?'':' Muddat tugamasidan oldin qayta to‘lasangiz, kunlar ustiga qo‘shiladi.')+'</small>'+(p.admin?'':'<button type="button" class="pri" onclick="payByCard(\'teacher\',\'pro\')">💳 Uzaytirish — '+uzsFmt(p.price)+' so‘m</button>')+'</div>';
  }else{
    pro='<div class="tPlan"><span class="tBadge">Tavsiya</span><div class="tPlanH"><b>Ustoz Pro</b><b>'+uzsFmt(p.price)+' so‘m / '+p.days+' kun</b></div><small>Cheksiz PDF hisobot va reyting, sust va kuchli savollar, Rasch asosida Milliy sertifikat tahlili, oddiy test statistikasi, o‘quvchilar rivoji.</small>'
      +'<button type="button" class="pri" onclick="payByCard(\'teacher\',\'pro\')">💳 Ustoz Pro’ni yoqish</button>'
      +(d.free_left?'<p class="muted" style="margin:8px 0 0;text-align:center">🎁 Birinchi hisobot bepul ('+d.free_max_n+' o‘quvchigacha) — pastdagi testingizda «Tahlil» ni bosing.</p>':'')+'</div>';
  }
  const t=d.totals, stats='<div class="pStats"><div><b>'+t.tests+'</b><small>testlar</small></div><div><b>'+t.users+'</b><small>ishtirokchilar</small></div><div><b>'+t.visits+'</b><small>havolani ochganlar</small></div><div><b>'+t.new_users+'</b><small>yangi o‘quvchilar</small></div></div>';
  const tabs='<div class="tTabs"><button type="button" class="'+(tchKind==='ms'?'on':'')+'" onclick="tchKindSet(\'ms\')">🎓 Milliy sertifikat</button><button type="button" class="'+(tchKind==='simple'?'on':'')+'" onclick="tchKindSet(\'simple\')">📝 Oddiy test</button></div>';
  const list=d.tests.filter(x=>x.kind===tchKind);
  const cards=list.length?list.map(x=>'<div class="result" style="margin:8px 0"><b>'+escapeHtml(x.title)+'</b><p class="muted">Kod: '+escapeHtml(x.code)+' • '+(x.closed?'🏁 Yakunlangan':'🟢 Davom etmoqda')+'<br>👥 '+x.users+' ishtirokchi • '+x.attempts+' urinish'+(x.avg!=null?' • '+x.avg+' '+escapeHtml(x.avg_label):'')+'</p>'
      +'<div class="pBtns"><button type="button" class="tMain" onclick="openTStats('+J(x.kind)+','+J(x.code)+')">📊 Tahlil</button><button type="button" onclick="sendTPdf('+J(x.kind)+','+J(x.code)+')">📄 PDF</button><button type="button" onclick="shareTest('+J(x.code)+','+J(x.title)+')">📤 Ulashish</button><button type="button" onclick="showQR('+J(x.code)+','+J(x.title)+')">📱 QR</button></div></div>').join('')
    :'<div class="word">Bu bo‘limda hozircha test yaratmagansiz.</div><button type="button" class="primaryAction" onclick="openSection(\'national\')">➕ Test yaratish</button>';
  const bonus='<div class="result" style="margin:10px 0 0">🎁 Havola orqali kelib testni ishlagan yangi o‘quvchilar uchun bonusingiz: <b>'+t.bonus+'</b> ta bepul esse tekshiruvi (har biri uchun +'+t.bonus_per_student+').</div>';
  box.innerHTML=hero+pro+'<h3 style="margin:16px 0 6px">Ustoz imkoniyatlari</h3><div class="tPerks">'+perks+'</div><h3 style="margin:16px 0 6px">Mening testlarim</h3>'+stats+tabs+cards+bonus;
}
async function sendTPdf(kind,code){
  const r=await tchPost('/api/teacher/pdf',{kind,code});
  notify(r.ok?'📄 PDF hisobot bot chatiga yuborildi.':(r.error||'Xatolik'));
}
function tCol(p){ return p>=70?'#128a63':(p>=40?'#d9a21b':'#c0392b'); }
function tBars(rows){ return rows.map(r=>'<div class="tRow"><span class="tLab">'+escapeHtml(r.l)+'</span><div class="tBar"><i style="width:'+Math.max(2,r.w)+'%;background:'+r.c+'"></i></div><span class="tVal">'+escapeHtml(r.v)+'</span></div>').join(''); }
async function openTStats(kind,code){
  openSection('teacherStats'); const box=$('tsBody'); box.innerHTML='<div class="word">⏳ Tahlil tayyorlanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/teacher/stats?kind='+encodeURIComponent(kind)+'&code='+encodeURIComponent(code)),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    renderTStats(d);
  }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; }
}
function tKpis(s,n,ms){ return '<div class="pStats"><div><b>'+n+'</b><small>ishtirokchi</small></div><div><b>'+s.mean+'</b><small>o‘rtacha '+(ms?'ball':'%')+'</small></div><div><b>'+s.median+'</b><small>mediana</small></div><div><b>'+s.pass_pct+'%</b><small>o‘tganlar</small></div></div>'; }
function renderTStats(d){
  const box=$('tsBody'), ms=d.kind==='ms', J=x=>escapeHtml(JSON.stringify(x));
  let h='<h2 style="margin:0">'+escapeHtml(d.title)+'</h2><p class="muted">'+(ms?'🎓 Milliy sertifikat testi':'📝 Oddiy test')+' • kod '+escapeHtml(d.code)+'</p>';
  if(d.n===0 || d.empty){ box.innerHTML=h+'<div class="word">Bu testni hali hech kim topshirmagan. Havolani ulashing — natijalar kelgach tahlil to‘ladi.</div>'; return; }
  const lvC={'A+':'#128a63','A':'#128a63','B+':'#3b549a','B':'#3b549a','C+':'#d9a21b','C':'#d9a21b','NC':'#c0392b','5':'#128a63','4':'#3b549a','3':'#d9a21b','2':'#c0392b'};
  if(d.locked){
    const tz=d.teaser||{}; if(tz.summary) h+=tKpis(tz.summary,d.n,ms);
    const dist=tz.levels||tz.grades||[]; if(dist.length){ const mx=Math.max(1,...dist.map(x=>x.n)); h+='<h3 style="margin:12px 0 6px">'+(ms?'Toifa taqsimoti':'Baholar taqsimoti')+'</h3>'+tBars(dist.map(x=>({l:ms?x.name:'«'+x.name+'»',w:x.n/mx*100,c:lvC[x.name]||'#128a63',v:x.n+' ('+x.pct+'%)'}))); }
    h+='<div class="tPlan" style="margin-top:14px"><div class="tPlanH"><b>🔒 Batafsil tahlil — Ustoz Pro</b></div><small>'+(d.reason==='limit_n'?'Bepul hisobot '+d.free_max_n+' o‘quvchigacha. Bu testda '+d.n+' ishtirokchi bor.':'Bepul hisobotdan foydalangansiz.')+' Pro bilan: har savol bo‘yicha foiz, sust va kuchli savollar, ko‘p tanlangan xato javob, fanlar kesimi'+(ms?', Rasch ballari':'')+', ishtirokchilar jadvali va PDF.</small><button type="button" class="pri" onclick="payByCard(\'teacher\',\'pro\')">💳 Ustoz Pro — '+uzsFmt(d.price)+' so‘m / 30 kun</button></div>';
    box.innerHTML=h; return;
  }
  h+=tKpis(d.summary,d.n,ms);
  if(d.note) h+='<p class="muted" style="margin:6px 0">'+(ms&&d.rasch?'✅ ':'ℹ️ ')+escapeHtml(d.note)+'</p>';
  if(d.advice&&d.advice.length) h+='<div class="result" style="margin:10px 0"><b>💡 Ustoz uchun xulosa</b><br>'+d.advice.map(x=>'• '+escapeHtml(x)).join('<br>')+'</div>';
  const dist=d.levels||d.grades, mxd=Math.max(1,...dist.map(x=>x.n));
  h+='<h3 style="margin:14px 0 6px">'+(ms?'Toifa taqsimoti':'Baholar taqsimoti')+'</h3>'+tBars(dist.map(x=>({l:ms?x.name:'«'+x.name+'»',w:x.n/mxd*100,c:lvC[x.name]||'#128a63',v:x.n+' ('+x.pct+'%)'})));
  if(d.fans&&d.fans.length) h+='<h3 style="margin:14px 0 6px">Fan / mavzu bo‘yicha o‘rtacha</h3><p class="muted" style="margin:0 0 6px">Eng pastdan boshlab — avval shularni takrorlang.</p>'+tBars(d.fans.map(f=>({l:f.name,w:f.pct,c:tCol(f.pct),v:f.pct+'%'})));
  if(d.fans&&d.fans.some(f=>f.worst&&f.worst.length)) h+='<h3 style="margin:14px 0 6px">Mavzular bo‘yicha xato savollar tahlili</h3><p class="muted" style="margin:0 0 6px">Har mavzuda eng ko‘p xato qilingan savollar (80% dan past).</p><div class="tTable">'+d.fans.map(f=>'<div><b>'+escapeHtml(f.name)+'</b><span>xato '+f.wrong_pct+'%</span><em>'+((f.worst||[]).map(w=>'#'+escapeHtml(String(w.item))+' ('+w.pct+'%'+(w.wrong?', ko‘p tanlangan xato: '+escapeHtml(w.wrong.option):'')+')').join(' • ')||'hammasi yaxshi')+'</em></div>').join('')+'</div>';
  if(d.essay_stats&&!d.essay_stats.missing&&d.essay_stats.mean24!=null) h+='<p class="muted" style="margin:8px 0">📝 Esse: o‘rtacha '+d.essay_stats.mean24+'/24</p>';
  h+='<details class="tFan"><summary>⚙️ '+(d.fanmap_set?'Fan / mavzu xaritasini o‘zgartirish':'Fan / mavzu bo‘yicha tahlilni yoqish')+'</summary><p class="muted">Har qatorga bitta fan: nomi va savol raqamlari. Masalan:<br><code>Grammatika: 1-23<br>G‘azal tahlili: 39-43</code></p><textarea id="tFanTxt" rows="6" placeholder="Grammatika: 1-23&#10;Badiiy matn: 24-28">'+escapeHtml(d.fanmap_text||'')+'</textarea><button type="button" class="pri" onclick="saveTFan('+J(d.kind)+','+J(d.code)+')">Saqlash</button></details>';
  const hc=d.hist.counts, he=d.hist.edges, mxh=Math.max(1,...hc);
  h+='<h3 style="margin:14px 0 6px">'+(ms?'Ball':'Foiz')+' taqsimoti</h3><div class="tHist">'+hc.map((c,i)=>'<div><b>'+c+'</b><i style="height:'+Math.max(3,c/mxh*90)+'px"></i><small>'+he[i]+'-'+he[i+1]+'</small></div>').join('')+'</div>';
  h+='<h3 style="margin:14px 0 6px">Har savol bo‘yicha foiz</h3><p class="muted" style="margin:0 0 6px">Yashil: 70% dan yuqori • sariq: 40–70% • qizil: 40% dan past</p><div class="tGrid">'+d.items.map(x=>'<div style="background:'+tCol(x.pct)+'"><small>#'+escapeHtml(x.item)+'</small><b>'+Math.round(x.pct)+'%</b></div>').join('')+'</div>';
  if(d.weak.length) h+='<h3 style="margin:14px 0 6px">Sust savollar — qayta o‘rgatish kerak</h3><div class="tTable">'+d.weak.map(w=>'<div><b>#'+escapeHtml(w.item)+'</b><span>'+w.pct+'%</span><em>'+escapeHtml(w.fan||'—')+(w.wrong?' • ko‘p tanlangan xato: <b>'+escapeHtml(w.wrong.option)+'</b> ('+w.wrong.share+'%)':'')+'</em></div>').join('')+'</div>';
  h+='<h3 style="margin:14px 0 6px">Kuchli savollar</h3><div class="tTable">'+d.strong.map(w=>'<div><b>#'+escapeHtml(w.item)+'</b><span>'+w.pct+'%</span><em>'+escapeHtml(w.fan||'—')+'</em></div>').join('')+'</div>';
  if(d.bad_disc&&d.bad_disc.length) h+='<h3 style="margin:14px 0 6px">⚠️ Yomon farqlovchi savollar</h3><p class="muted" style="margin:0 0 6px">Kuchli va kuchsiz o‘quvchilar bir xil javob bergan: kalit yoki shartni tekshiring.</p><div class="tTable">'+d.bad_disc.map(w=>'<div><b>#'+escapeHtml(w.item)+'</b><span>'+w.pct+'%</span><em>farqlash '+w.d+'</em></div>').join('')+'</div>';
  const pe=d.people.slice(0,40);
  h+='<h3 style="margin:14px 0 6px">Ishtirokchilar'+(d.people.length>40?' (birinchi 40 ta, hammasi PDF da)':'')+'</h3><div class="tPeople">'+pe.map(x=>ms
    ?'<div><span>'+x.rank+'</span><strong>'+escapeHtml(x.name)+'</strong><em>'+x.correct+' to‘g‘ri • Rasch '+x.rasch+(x.essay!=null?' • esse '+(x.essay24!=null?x.essay24+'/24':x.essay):'')+'</em><b style="color:'+(x.level==='NC'?'#c0392b':'#128a63')+'">'+x.final+' • '+x.level+'</b></div>'
    :'<div><span>'+x.rank+'</span><strong>'+escapeHtml(x.name)+'</strong><em>'+x.correct+'/'+x.total+' to‘g‘ri</em><b style="color:'+(x.grade===2?'#c0392b':'#128a63')+'">'+x.pct+'% • «'+x.grade+'»</b></div>').join('')+'</div>';
  if(ms&&d.progress&&d.progress.length) h+='<h3 style="margin:14px 0 6px">O‘quvchilar rivoji</h3><div class="tPeople">'+d.progress.slice(0,20).map(x=>'<div><span>'+x.n+'</span><strong>'+escapeHtml(x.name)+'</strong><em>'+x.scores.slice(-6).join(' › ')+'</em><b style="color:'+(x.delta<0?'#c0392b':'#128a63')+'">'+(x.delta>0?'+':'')+x.delta+'</b></div>').join('')+'</div>';
  h+='<div class="pBtns" style="margin-top:14px"><button type="button" class="tMain" onclick="sendTPdf('+J(d.kind)+','+J(d.code)+')">📄 PDF hisobotni botga yuborish</button><button type="button" onclick="openResults('+J(d.kind)+','+J(d.code)+')">📊 Natijalar / Excel</button></div>';
  box.innerHTML=h;
}
async function saveTFan(kind,code){
  const r=await tchPost('/api/teacher/fanmap',{kind,code,text:($('tFanTxt')||{}).value||''});
  if(r.ok){ notify('Saqlandi: '+r.fans+' ta fan/mavzu.'); openTStats(kind,code); } else notify(r.error||'Xatolik');
}

function openPanel(){ openTeacher(); }


// ===== v60: Mock bo'limi, Profil, bosh sahifa =====
let _mkTimer=null;
const mkSom=n=>fmtUzs(n)+' so‘m';
const MK_OY=['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr'];
function mkHM(iso){ const d=new Date(iso); return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0'); }
function mkFmt(iso){ try{ const d=new Date(iso); return d.getDate()+'-'+MK_OY[d.getMonth()]+', '+mkHM(iso); }catch(e){ return iso||''; } }
function mkLeft(ms){ if(ms<0) ms=0; const s=Math.floor(ms/1000); return {h:Math.floor(s/3600),m:Math.floor(s%3600/60),s:s%60}; }
async function loadMocks(){
  const box=$('mockBody'); if(!box) return;
  clearInterval(_mkTimer);
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/list'),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="word">Mocklarni yuklab bo‘lmadi.</div>'; return; }
    const skew=d.server_time?(new Date(d.server_time).getTime()-Date.now()):0; window._mkSkew=skew; window._mocks=d.mocks;
    const act=d.mocks.filter(m=>m.status!=='closed').sort((x,y)=>new Date(x.opens_at)-new Date(y.opens_at));
    const past=d.mocks.filter(m=>m.status==='closed');
    const adm=ME&&ME.is_admin;
    const priceTxt=m=>'';
    const admRow=m=>adm?'<div class="mkAdm">'+(m.test_code?'<button type="button" onclick="openMockResults('+m.id+')">📊 Natijalar</button>':'')+(m.test_code?'<button type="button" onclick="openTestEdit(\''+escapeHtml(m.test_code)+'\')">✏️ Savol/javoblarni tahrirlash</button>':'')+'<button type="button" onclick="openMockPdf('+m.id+')">📄 Test PDF'+(m.pdf_n?' ('+m.pdf_n+')':'')+'</button><button type="button" onclick="mockDelete('+m.id+')">🗑 O‘chirish</button><div class="mkRegEd"><small>⏰ Ro‘yxat: '+escapeHtml(mkFmt(m.reg_until))+' gacha'+(m.reg_open?'':' (yopilgan)')+'</small><input type="datetime-local" id="mkRegEd'+m.id+'" value="'+mkLocalInp(m.reg_until)+'"><button type="button" onclick="mockSetReg('+m.id+')">⏰ Muddatni saqlash</button></div></div>':'';
    const payBar=adm?'<div class="mkPay"><div><b>💳 Mock to‘lovi</b><small>'+(d.pay_on?'Yoqilgan':'O‘chiq')+' • 1 ta mock — '+mkSom(d.price||10000)+' (karta orqali)</small></div><button type="button" class="'+(d.pay_on?'on':'')+'" onclick="mockPayToggle('+(d.pay_on?0:1)+')">'+(d.pay_on?'O‘chirish':'Faollashtirish')+'</button></div>':'';
    let html=payBar;
    if(act.length){
      const m=act[0];
      html+='<section class="mkHero"><div class="mkTop"><span class="mkTag">'+escapeHtml(m.title)+'</span><span class="mkLive" id="mkState"></span></div>'
        +'<div class="mkDate">'+escapeHtml(mkFmt(m.opens_at))+' – '+escapeHtml(mkHM(m.closes_at))+'</div>'
        +'<div class="mkCdLbl" id="mkCdLbl"></div><div class="mkCd" id="mkCd"><div><b id="mkH">--</b><small>soat</small></div><div><b id="mkM">--</b><small>daqiqa</small></div><div><b id="mkS">--</b><small>soniya</small></div></div>'
        +'<div class="mkPeople">👥 '+m.regs+' kishi qatnashmoqchi</div><div id="mkAct"></div>'+priceTxt(m)+admRow(m)+'</section>';
      if(act.length>1) html+='<h3 class="mkH3">Keyingi mocklar</h3>'+act.slice(1).map(x=>'<div class="mkRow"><div><b>'+escapeHtml(x.title)+'</b><small>'+escapeHtml(mkFmt(x.opens_at))+' • '+x.regs+' kishi</small></div>'+(x.locked?'<button type="button" onclick="mockPay('+x.id+')">🔒 '+mkSom(x.price||10000)+'</button>':(x.joined?'<em>✓ Ro‘yxatda</em>':'<button type="button" onclick="mockJoin('+x.id+')">Qatnashaman</button>'))+'</div>'+admRow(x)).join('');
    } else html+='<div class="mkEmpty"><b>🗓</b><h3>Yaqin mock yo‘q</h3><p>Yangi mock e’lon qilinishi bilan shu yerda ko‘rasiz.</p></div>';
    if(past.length) html+='<h3 class="mkH3">O‘tgan mocklar</h3>'+past.slice(0,8).map(x=>'<div class="mkRow past"><div><b>'+escapeHtml(x.title)+'</b><small>'+escapeHtml(mkFmt(x.opens_at))+' • '+x.regs+' ishtirokchi'+(x.published?' • natijalar e‘lon qilingan':'')+'</small></div>'+(x.joined?'<button type="button" class="mkMy" onclick="openMyMock('+x.id+')">📊 Natijam</button>':'<em>Yakunlangan</em>')+'</div>'+admRow(x)).join('');
    if(act.length) html='<div class="result mkRules"><b>📌 Mock qoidalari</b><ul style="margin:6px 0 0;padding-left:18px"><li>Test <b>bir marta</b> topshiriladi.</li><li>Esse <b>majburiy</b>: sun‘iy intellekt (bepul, 1 martalik) yoki ekspert yordamida — ikkisidan birini tanlang. <b>Ro‘yxatdan o‘tgan zahoti esse mavzusi ko‘rinadi — esseni testgacha yozib tekshirtiring</b>; mock kuni faqat test topshirasiz.</li><li>Esse balli bo‘lmasa test natijasi <b>hisoblanmaydi</b>.</li><li>Natijalar admin e‘lon qilgach chiqadi: <b>Mini App → Mock → «📊 Natijam»</b>.</li><li>📜 Sertifikat faqat <b>B+, A va A+</b> darajalar uchun beriladi.</li></ul></div>'+html;
     box.innerHTML=html;
    if(act.length){ mkTick(act[0]); _mkTimer=setInterval(()=>mkTick(act[0]),1000); }
  }catch(e){ box.innerHTML='<div class="word">Xatolik yuz berdi.</div>'; }
}
function mkPromoHtml(m){
  if(!m.expert_promo) return '';
  const free=(m.ai_free&&m.ai_free.on&&!m.ai_free.used);
  const sum=String(m.expert_promo.uzs).replace(/\B(?=(\d{3})+(?!\d))/g,' ');
  return '<div class="mkPromo"><b>📝 '+(m.essay_early?'Esseni testgacha yozib tekshirtiring':'Esse tekshirish')+'</b>'
    +'<p>⏳ <b>Testgacha muddat:</b> <span id="mkPromoLeft">--</span></p>'
    +'<p>📌 <b>Esse mavzusi:</b> '+(m.essay_topic?'«'+escapeHtml(m.essay_topic)+'»':'tez orada e‘lon qilinadi')+'</p>'
    +'<p class="muted">Esseni mock kunigacha yozib tekshirtiring — mock kuni faqat testni topshirasiz, esse balli avtomatik hisobga olinadi. Ikki usuldan birini tanlang:</p>'
    +(free?'<p>🤖 <b>Sun‘iy intellekt yordamida — BEPUL</b> (1 martalik, aynan mock mavzusi).</p><button type="button" onclick="openMockAI(\''+escapeHtml(m.test_code)+'\')">🤖 AI bilan bepul tekshirish</button>':'<p class="muted">🤖 Sun‘iy intellekt yordamida tekshirish ishlatib bo‘lingan.</p>')
    +'<p>👨‍🏫 <b>Ekspert yordamida</b> — '+sum+' so‘m. Ball 24 soat ichida.</p><button type="button" onclick="openMockExpert(\''+escapeHtml(m.test_code)+'\')">👨‍🏫 Ekspertga yuborish</button>'
    +'<p class="muted">Esse balli bo‘lmasa test natijasi hisoblanmaydi.</p></div>';
}
function mkLeftTxt(ms){
  if(ms<=0) return 'boshlandi';
  const d=Math.floor(ms/86400000), h=Math.floor(ms%86400000/3600000), mi=Math.floor(ms%3600000/60000);
  return (d?d+' kun ':'')+(d||h?h+' soat ':'')+mi+' daqiqa';
}
function mkTick(m){
  if(!$('mkH')) { clearInterval(_mkTimer); return; }
  const now=Date.now()+(window._mkSkew||0), o=new Date(m.opens_at).getTime(), c=new Date(m.closes_at).getTime();
  const open=now>=o&&now<c, closed=now>=c;
  const t=mkLeft(open?c-now:o-now), p=n=>String(n).padStart(2,'0');
  $('mkH').textContent=p(t.h); $('mkM').textContent=p(t.m); $('mkS').textContent=p(t.s);
  if($('mkCdLbl')) $('mkCdLbl').textContent=closed?'':(open?'⏳ Mock tugashigacha qolgan vaqt':'⏳ Testgacha muddat');
  if($('mkPromoLeft')) $('mkPromoLeft').textContent=mkLeftTxt(o-now);
  $('mkState').textContent=closed?'Yakunlandi':(open?'● Hozir ochiq':'Tez orada');
  const a=$('mkAct'); const key=(closed?'c':open?'o':'u')+(m.joined?'j':'n')+(m.locked?'l':'')+(m.reg_open?'r':'x')+(m.expert_promo?'p':'')+(m.essay_topic?'t':'')+(m.essay_early?'e':'')+((m.ai_free&&m.ai_free.on&&!m.ai_free.used)?'a':'')+(m.pdf_n?'f':'');
  if(a.dataset.k===key) return; a.dataset.k=key;
  if(closed) a.innerHTML='';
  else if(m.locked) a.innerHTML='<button class="primaryAction mkGo" type="button" onclick="mockPay('+m.id+')">🔒 Mockni ochish — '+mkSom(m.price||10000)+'</button><div class="mkNote">To‘lov karta orqali. To‘lov tasdiqlangach mock avtomatik ochiladi.</div>';
  else if(open&&(m.joined||(ME&&ME.is_admin))&&m.test_code) a.innerHTML='<button class="primaryAction mkGo" type="button" onclick="startNational(\''+escapeHtml(m.test_code)+'\')">▶ Mockni boshlash</button>'+(m.pdf_n?'<button type="button" class="mkMy" onclick="openMockPdf('+m.id+')">📄 Test PDF ('+m.pdf_n+')</button>':'')+'<div class="mkNote">📝 Esse majburiy: natija = test + esse. Natija admin e‘lon qilgach ko‘rinadi.</div>'+(m.joined?'<button type="button" class="mkMy" onclick="openMyMock('+m.id+')">📊 Natijam (esse balli)</button>':'')+mkPromoHtml(m);
  else if(open&&m.joined&&!m.test_code) a.innerHTML='<div class="mkNote">Test tez orada biriktiriladi.</div>';
  else if(m.joined) a.innerHTML='<div class="mkNote ok">✓ Siz ro‘yxatdasiz. Mock ochilganda shu yerda «Boshlash» tugmasi chiqadi.</div>'+mkPromoHtml(m);
  else if(m.reg_open) a.innerHTML='<button class="primaryAction mkGo" type="button" onclick="mockJoin('+m.id+')">✓ Qatnashaman</button><div class="mkNote">Testda qatnashish uchun avval «Qatnashaman»ni bosing. Test faqat ro‘yxatdan o‘tganlarga ko‘rinadi.</div>';
  else a.innerHTML='<div class="mkNote">Ro‘yxatga olish '+escapeHtml(mkFmt(m.reg_until))+' da yopilgan. Keyingi mockda qatnashing.</div>';
}
async function mockJoin(id){
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/join'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})})).json();
    if(d.need_pay){ mockPay(d.mock_id||id); return; }
    if(!d.ok){ notify(d.error||'Xatolik'); return; }
    loadMocks();
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
async function mockCreate(){
  const st=$('mkStatus'); const v=id=>$(id).value;
  if(!v('mkTitle').trim()||!v('mkOpen')||!v('mkClose')){ st.textContent='❌ Nom, ochilish va yopilish vaqtini kiriting.'; return; }
  if(!v('mkCode').trim()){ st.textContent='❌ Avval testni kiriting: «📝 Testni shu yerda kiritish» tugmasini bosing.'; return; }
  st.textContent='⏳ Saqlanmoqda...';
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/create'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:v('mkTitle'),opens_at:new Date(v('mkOpen')).toISOString(),closes_at:new Date(v('mkClose')).toISOString(),test_code:v('mkCode'),reg_until:v('mkReg')?new Date(v('mkReg')).toISOString():''})})).json();
    if(!d.ok){ st.textContent='❌ '+(d.error||'Xatolik'); return; }
    const pf=$('mkPdf')&&$('mkPdf').files[0]; let pmsg='';
    if(pf&&d.id){ st.textContent='⏳ PDF yuklanmoqda...'; const pr=await mockPdfUpload(d.id,pf,''); pmsg=pr.ok?' • 📄 PDF yuklandi':' • ⚠️ PDF yuklanmadi: '+(pr.error||'xatolik')+' («📄 Test PDF» tugmasi orqali qayta yuklang)'; }
    if($('mkPdf')) $('mkPdf').value='';
    st.textContent='✅ Mock joylandi'+pmsg; ['mkTitle','mkOpen','mkClose','mkCode','mkReg'].forEach(i=>{ if($(i)) $(i).value=''; }); if($('mkCodeInfo')) $('mkCodeInfo').textContent=''; loadMocks();
  }catch(e){ st.textContent='❌ Server bilan bog‘lanishda xatolik.'; }
}
async function openMockResults(id){   // v67: Mock natijalari — test + esse birga, mavzular bo‘yicha xato tahlili, qatnashmaganlar
  openSection('teacherStats'); const box=$('tsBody'); box.innerHTML='<div class="word">⏳ Tahlil tayyorlanmoqda...</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/results?id='+encodeURIComponent(id)),{cache:'no-store'})).json();
    if(!d.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    const a=d.analytics; if(a&&!a.empty) renderTStats(a); else box.innerHTML='<h2 style="margin:0">'+escapeHtml(d.mock.title)+'</h2><div class="word">Hali hech kim topshirmagan.</div>';
    if(a&&a.insights) box.insertAdjacentHTML('afterbegin',renderMockDeep(a,d.trend||[],d.mock));
    const es=(a&&a.essay_stats)||null;
    if((d.essays||[]).length) box.insertAdjacentHTML('afterbegin',renderMockEssays(d));   // v94: kim esse tekshirtirgani va ballari (admin)
    if(a&&!a.empty&&d.mock.code) box.insertAdjacentHTML('afterbegin','<button type="button" class="primaryAction" style="margin:0 0 10px" onclick="sendTPdf(\'ms\',\''+escapeHtml(d.mock.code)+'\')">📄 PDF hisobotni olish (guruhga yuborish uchun)</button>');
    box.insertAdjacentHTML('afterbegin','<div class="result" style="margin:0 0 10px"><b>🎯 '+escapeHtml(d.mock.title)+'</b><div class="pStats" style="margin-top:8px"><div><b>'+d.registered+'</b><small>ro‘yxatdan o‘tgan</small></div><div><b>'+d.participated+'</b><small>qatnashdi</small></div><div><b>'+d.absent+'</b><small>qatnashmadi</small></div></div>'
      +(es?'<p class="muted" style="margin:8px 0 0">📝 Esse: '+es.with+' ta tekshirilgan'+(es.mean24!=null?', o‘rtacha '+es.mean24+'/24':'')+(es.missing?' • '+es.missing+' tasida esse hali yo‘q (ekspert kutilmoqda)':'')+'</p>':'')
      +(d.absent?'<p class="muted" style="margin:8px 0 0">Qatnashmaganlar: '+d.absent_names.map(escapeHtml).join(', ')+(d.absent>d.absent_names.length?' …':'')+'</p>':'')
      +(d.open&&d.absent?'<button type="button" class="tMain" style="margin-top:8px" onclick="mockRemind('+d.mock.id+')">⏰ Qatnashmaganlarga eslatma</button>':'')
      +(d.published?'<p style="margin:8px 0 0">✅ <b>Natijalar e‘lon qilingan</b> (foydalanuvchilar va sertifikatlar yuborilgan).</p>':(d.closed?'<button type="button" class="tMain" style="margin-top:8px" onclick="mockPublish('+d.mock.id+','+((es&&es.missing)||0)+')">📣 Natijalarni e‘lon qilish</button><p class="muted" style="margin:6px 0 0">E‘longacha foydalanuvchi faqat esse balini biladi. E‘londan keyin umumiy natija va sertifikatlar beriladi.</p>':'<p class="muted" style="margin:8px 0 0">🔒 Natijalar yashirin. Mock yopilgach «E‘lon qilish» tugmasi chiqadi.</p>'))+'</div>');
  }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; }
}
function renderMockEssays(d){   // v94: admin — mock ishtirokchilarining esse holati va ballari
  const rows=d.essays||[], c=d.essay_counts||{};
  const st={ai:'🤖 AI',expert:'👨‍🏫 Ekspert',expert_wait:'⏳ Ekspert kutilmoqda',none:'— yo‘q'};
  const f=v=>(v==null?'—':v);
  const tr=rows.map(r=>'<tr><td>'+escapeHtml(r.name)+'</td><td>'+(r.submitted?f(r.test75):'<small>topshirmagan</small>')+'</td><td>'+(r.essay24==null?'—':r.essay24+'<small>/24</small>')+'</td><td>'+(st[r.essay_status]||'')+'</td><td>'+(!r.submitted?'—':(r.essay24==null?'<small>esse yo‘q — hisoblanmaydi</small>':'<b>'+f(r.final)+(r.provisional?'<small>*</small>':'')+'</b>'))+'</td></tr>').join('');
  return '<details class="result" style="margin:0 0 10px"><summary style="cursor:pointer"><b>📝 Esse holati</b> • '+((c.ai||0)+(c.expert||0))+' tekshirilgan • '+(c.expert_wait||0)+' ekspert kutmoqda • '+(c.none||0)+' esse yo‘q</summary>'
    +'<p class="muted" style="margin:8px 0">🤖 AI: <b>'+(c.ai||0)+'</b> • 👨‍🏫 Ekspert: <b>'+(c.expert||0)+'</b> • Ro‘yxatdan o‘tgan: <b>'+(c.registered||0)+'</b> • Topshirgan: <b>'+(c.submitted||0)+'</b></p>'
    +'<div style="overflow-x:auto"><table class="mkEsT"><thead><tr><th>Ism</th><th>Test /75</th><th>Esse</th><th>Kim tekshirdi</th><th>Umumiy /75</th></tr></thead><tbody>'+tr+'</tbody></table></div>'
    +'<p class="muted" style="margin:6px 0 0;font-size:11.5px">* Esse hali testga bog‘lanmagan — umumiy ball taxminiy; natijalar e‘lon qilinganda yakuniy hisoblanadi.</p></details>';
}
async function mockPublish(id,missing){
  const msg=(missing>0?'⚠️ '+missing+' ta ishtirokchining essesi hali tekshirilmagan (ekspert kutilmoqda). Ular uchun umumiy ball esse’siz hisoblanadi.\n\n':'')+'Natijalar HAMMAGA e‘lon qilinadi, sertifikatlar yuboriladi. Qaytarib bo‘lmaydi. Davom etasizmi?';
  if(!confirm(msg)) return;
  const r=await adminPost('/api/mock/publish',{id}); if(r){ notify('Natijalar e‘lon qilindi. Sertifikatlar yuborilmoqda.'); openMockResults(id); }
}
async function mockRemind(id){ if(!confirm('Qatnashmaganlarga eslatma yuborilsinmi?')) return; const r=await adminPost('/api/mock/remind',{id}); if(r) notify('Eslatma yuborilmoqda.'); }
function mkLocalInp(iso){ const d=new Date(iso); if(isNaN(d)) return ''; const p=n=>String(n).padStart(2,'0'); return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+'T'+p(d.getHours())+':'+p(d.getMinutes()); }
async function mockSetReg(id){ const v=$('mkRegEd'+id)&&$('mkRegEd'+id).value; if(!v){ notify('Vaqtni tanlang'); return; } if(await adminPost('/api/mock/reg',{id,reg_until:new Date(v).toISOString()})){ notify('✅ Ro‘yxat muddati saqlandi'); loadMocks(); loadHomeMock(); } }
async function mockDelete(id){ if(!confirm('Mock o‘chirilsinmi?')) return; if(await adminPost('/api/mock/delete',{id})) loadMocks(); }
function mockPay(id){ payByCard('mock',String(id)); }
async function mockPayToggle(on){
  if(!confirm(on?'Mock to‘lovi faollashtirilsinmi? Foydalanuvchilar mockni to‘lab ochadi.':'Mock to‘lovi o‘chirilsinmi?')) return;
  if(await adminPost('/api/mock/payon',{on:!!on})) loadMocks();
}
function renderProfile(){
  const u=tg?.initDataUnsafe?.user||{}; const nm=((u.first_name||'')+' '+(u.last_name||'')).trim()||'Foydalanuvchi';
  if($('pfName')) $('pfName').textContent=nm;
  if($('pfSub')) $('pfSub').textContent=u.username?('@'+u.username):(ME&&ME.is_admin?'Admin':'');
  const av=$('pfAv'); if(av){ if(u.photo_url){ av.innerHTML='<img alt="" src="'+escapeHtml(u.photo_url)+'">'; } else av.textContent=nm.slice(0,1).toUpperCase(); }
}


// ===== v63: bosh sahifadagi «Keyingi mock» kartasi =====
var _hmTimer=null, _hmMock=null;   // v72: let edi — goHome() ishga tushganda hali e'lon qilinmagan bo'lib qolardi
async function loadHomeMock(){
  const box=$('homeMock'); if(!box) return; clearInterval(_hmTimer);
  try{
    const d=await (await apiFetch(apiUrl('/api/mock/list'),{cache:'no-store'})).json();
    if(!d||!d.ok){ box.classList.add('hidden'); return; }
    window._mkSkew=d.server_time?(new Date(d.server_time).getTime()-Date.now()):0;
    const act=(d.mocks||[]).filter(m=>m.status!=='closed').sort((x,y)=>new Date(x.opens_at)-new Date(y.opens_at));
    if(!act.length){ box.classList.add('hidden'); return; }
    const m=act[0]; _hmMock=m;
    box.innerHTML='<div class="hmRow"><div class="hmInfo"><div class="hmTop"><span class="hmTag" id="hmTag">KEYINGI MOCK</span><span class="hmPpl" id="hmPpl">'+m.regs+' kishi</span></div>'
      +'<h3>'+escapeHtml(m.title)+' <small>'+escapeHtml(mkFmt(m.opens_at))+'</small></h3>'
      +'<div class="hmMini"><b id="hmH">--</b>:<b id="hmM">--</b>:<b id="hmS">--</b><span id="hmCap"></span></div></div>'
      +'<button type="button" class="hmGo" id="hmGo" onclick="homeMockGo()">Qatnashaman</button></div>';
    box.classList.remove('hidden'); hmTick(); _hmTimer=setInterval(hmTick,1000);
  }catch(e){ box.classList.add('hidden'); }
}
function hmTick(){
  const m=_hmMock; if(!m||!$('hmH')){ clearInterval(_hmTimer); return; }
  const now=Date.now()+(window._mkSkew||0), o=new Date(m.opens_at).getTime(), c=new Date(m.closes_at).getTime();
  const open=now>=o&&now<c, closed=now>=c, t=mkLeft(open?c-now:o-now), p=n=>String(n).padStart(2,'0');
  $('hmH').textContent=p(t.h); $('hmM').textContent=p(t.m); $('hmS').textContent=p(t.s);
  const g=$('hmGo'); if(!g) return;
  if(closed){ clearInterval(_hmTimer); $('homeMock').classList.add('hidden'); return; }
  // v81: mock boshlangan bo'lsa, taymer TUGASHIGACHA ekani aniq yozilsin (avval «Keyingi mock» deb ko'rinardi)
  const ru=m.reg_until?new Date(m.reg_until).getTime():o, regClosed=!m.joined&&now>=ru;
  if($('hmTag')) $('hmTag').textContent=open?'MOCK BOSHLANDI':'KEYINGI MOCK';
  if($('hmPpl')) $('hmPpl').textContent=m.regs+(open?' kishi ro‘yxatda':' kishi qatnashmoqchi');
  if($('hmCap')) $('hmCap').textContent=open?'⏳ Mock tugashigacha qoldi':'⏳ Boshlanishigacha qoldi';
  g.textContent=m.locked?'🔒 Mockni ochish':(open&&m.test_code&&(m.joined||!m.locked)?'▶ Mockni boshlash':(m.joined?'✓ Siz ro‘yxatdasiz':(regClosed?'Ro‘yxatga olish yopilgan':'Qatnashaman')));
  g.disabled=!m.locked&&regClosed; g.style.opacity=g.disabled?'.6':'';
  g.classList.toggle('done',!!m.joined&&!open);
}
function homeMockGo(){
  const m=_hmMock; if(!m) return;
  const now=Date.now()+(window._mkSkew||0), open=now>=new Date(m.opens_at).getTime()&&now<new Date(m.closes_at).getTime();
  if(m.locked){ mockPay(m.id); return; }
  if(open&&m.test_code){ startNational(m.test_code); return; }
  if(!m.joined){ mockJoin(m.id).then(()=>{ loadHomeMock(); }); return; }
  openSection('mock');
}


// ===== v73: Esse — element ichida faqat «Faylni olish» (admin yuklagan PDF) + alohida «Videodars» bo‘limi
function openEsseFiles(){
  const d=BP, box=$('bpBody'), fs=d.files||[];
  box.innerHTML=bpBack('Orqaga','renderBookHome(false)')+'<h2>📎 Faylni olish</h2><p class="muted">'+escapeHtml(d.title)+'</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +(fs.length?fs.map((f,i)=>'<button class="bpTab vidRow" type="button" onclick="sendGazalFile('+f.id+')"><b>📥</b><span>'+(i+1)+'. '+escapeHtml(f.title)+'</span><small>'+gzType(f)+(gzSize(f.size)?' • '+gzSize(f.size):'')+'</small></button>').join('')
        +'<p class="muted">Faylni bossangiz, u shu bot chatiga yuboriladi. 🔒 Fayl faqat bot ichida ochiladi (forward va saqlash yopiq).</p>'
      :'<div class="word">Hali PDF yuklanmagan.</div>')
    +(d.is_admin?pdfUploadForm()+'<button class="bpGhost" type="button" onclick="manageGazalFiles()">✏️ PDF fayllarni boshqarish (nom, tartib, o‘chirish)</button>':'');
  bpFlash=''; window.scrollTo(0,0);
}
function bundleSoon(){ notify('🎁 To‘liq to‘plam tez orada ochiladi. Hozircha kurslarni alohida sotib olish mumkin.'); }
function esseSaleCard(d){
  const old=Number(d.old_price||0), cur=Number(d.price||0), hasSale=old>cur&&cur>0;
  if(d.is_admin && !(cur>0)) return '';
  if(!d.is_admin && !d.locked) return '<div class="esKOk"><b>✅ Kurs faol</b><small>Barcha PDF va videodarslar sizga ochiq. Fayllar faqat bot ichida ochiladi.</small></div>';
  const act=d.is_admin?"notify('👑 Bu foydalanuvchi ko‘rinishi — admin sotib olmaydi.')":"payByCard('growth','growth')";
  return '<div id="eSaleCard" class="esKBuy">'+(d.is_admin?'<p class="esKAdmNote">👑 Foydalanuvchi shu kartani ko‘radi</p>':'')+'<div class="esKPrice">'+(hasSale?'<span class="esKTagS">🔥 '+escapeHtml(d.sale||'Imtihon chegirmasi')+'</span>':'')
    +'<div class="esKNum">'+(hasSale?'<s>'+fmtUzs(old)+'</s>':'')+'<b>'+fmtUzs(cur)+'</b><em>so‘m</em></div>'
    +'<small>30 kun • barcha PDF va videodarslar'+(d.sale_left?' • ⏳ '+escapeHtml(d.sale_left):'')+'</small></div>'
    +'<button type="button" class="esKBtn" onclick="'+act+'">Sotib olish</button></div>';
}
// v105: pastdagi ikkinchi «Sotib olish» tugmasi (faqat kursni hali olmaganlarga)
function esseSaleCta(d){
  const cur=Number(d.price||0); if(d.is_admin||!d.locked||!(cur>0)) return '';
  return '<button type="button" class="esKBtn" onclick="payByCard(\'growth\',\'growth\')">Sotib olish — '+fmtUzs(cur)+' so‘m</button>';
}
// v105: ro‘yxat satri bosilganda: olmagan odamni narx kartasiga, olganni materiallarga olib boradi
function esseGo(){ const c=$('eSaleCard')||$('eGrid'); if(c) c.scrollIntoView({behavior:'smooth',block:'center'}); }
function esseVideoCard(d){
  const vs=d.video_n||0; let b;
  if(d.is_admin) b=(d.video_open?'🟢 ochiq':'🔴 yopiq')+' • 🎬'+vs;
  else if(d.locked) b='🔒 Premium';
  else b=d.video_open?('🎬'+vs):'⏳ Tez orada';
  return '<button class="bCard" type="button" onclick="openEsseVideos()"><div class="bThumb"><span style="font-size:44px">🎬</span></div><span class="bName">Videodars</span><span class="bBadges">'+b+'</span></button>';
}
let EV=null;
async function eveReload(){ EV=await (await apiFetch(apiUrl('/api/esse/videos'),{cache:'no-store'})).json(); return EV; }
async function openEsseVideos(){
  BK_SEC='esse'; openSection('bookPage'); BPn=0; BP=null; const box=$('bpBody'); box.innerHTML=BP_LOADING;
  try{ await eveReload(); }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; return; }
  if(!EV||!EV.ok){ box.innerHTML='<div class="result">❌ '+escapeHtml((EV&&EV.error)||'Xatolik')+'</div>'; return; }
  renderEsseVideos();
}
function renderEsseVideos(){
  const d=EV, box=$('bpBody'), vs=d.videos||[]; let h=bpBack('Orqaga','bpGoList()')+'<h2>🎬 Videodars</h2>';
  if(bpFlash){ h+='<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>'; bpFlash=''; }
  if(d.locked&&!d.is_admin){
    h+='<div class="tPlan"><div class="tPlanH"><b>🔒 Premium obunachilar uchun</b></div><small>Esse videodarslari Premium obunachilarga ochiladi.</small>'+premPriceHtml(d)+'<button type="button" class="pri" onclick="payByCard(\'growth\',\'growth\')">💳 Premium — '+fmtUzs(d.price||0)+' so‘m / 30 kun</button></div>';
  } else if(d.soon){
    h+='<div class="bProgress"><div>🚧</div><h3>Tez orada ochiladi</h3><p>Videodarslar tayyorlanmoqda. Ochilishi bilan shu yerda ko‘rinadi.</p></div>';
  } else {
    h+=(vs.length?vs.map((v,i)=>'<button class="bpTab vidRow" type="button" onclick="playBookVideo('+v.id+')"><b>▶️</b><span>'+(i+1)+'. '+escapeHtml(v.title)+'</span><small>'+(fmtDur(v.duration)||'video')+'</small></button>').join('')
      :'<div class="word">Hali video qo‘shilmagan.</div>')
      +'<p class="muted">Videoni bossangiz, u shu bot chatiga yuboriladi (saqlash va ulashish yopiq).</p>';
  }
  if(d.is_admin){
    h+='<p class="muted bpAdminNote">👑 Holat: '+(d.open?'🟢 Premium obunachilarga OCHIQ':'🔴 YOPIQ — obunachilar «Tez orada ochiladi» ko‘radi')+'. Siz hamma narsani ko‘rasiz.</p>'
      +'<button class="primaryAction" type="button" onclick="eveToggle()">'+(d.open?'🔒 Yopish':'🟢 Obunachilarga ochish')+'</button>'
      +'<button class="bpGhost" type="button" onclick="eveManage()">✏️ Videolarni boshqarish / yuklash</button>';
  }
  box.innerHTML=h; window.scrollTo(0,0);
}
async function eveToggle(){
  try{ const d=await (await apiFetch(apiUrl('/api/esse/video/open'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({open:!EV.open})})).json();
    if(!d.ok){ notify(d.error||'Xatolik'); return; } await eveReload(); bpFlash=d.open?'✅ Videodars obunachilarga ochildi.':'🔒 Videodars yopildi.'; renderEsseVideos(); }
  catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
function eveManage(){
  const d=EV, box=$('bpBody'), vs=d.videos||[];
  box.innerHTML=bpBack('Videodars','renderEsseVideos()')+'<h2>✏️ Videolar</h2><p class="muted">'+vs.length+' ta video</p>'
    +(bpFlash?'<div class="result bpFlash">'+escapeHtml(bpFlash)+'</div>':'')
    +'<label class="bpLbl">➕ Yangi videodars</label><input id="vidTitle" maxlength="150" placeholder="Dars nomi (ixtiyoriy)">'
    +'<button class="primaryAction" type="button" onclick="eveStartUpload()">🎬 Video qo‘shishni boshlash</button>'
    +'<p class="muted">Tugmani bosgach botga o‘ting va videoni yuboring (ketma-ket bir nechta ham mumkin). Izohiga (caption) nom yozsangiz, shu nom bo‘ladi. Tugatish: /asar_tamom. Botda: /esse_video_yuklash • /esse_video_och • /esse_video_yop</p>'
    +vs.map((v,i)=>'<div class="beQ"><b>'+(i+1)+'.</b> '+(fmtDur(v.duration)?'<span class="muted">'+fmtDur(v.duration)+'</span>':'')
      +'<input id="vt'+v.id+'" maxlength="150" value="'+escapeHtml(v.title)+'" onchange="eveRename('+v.id+')">'
      +'<div class="slBtns"><button type="button" onclick="eveAct(\'mvvideo\',{id:'+v.id+',dir:-1})">⬆️</button><button type="button" onclick="eveAct(\'mvvideo\',{id:'+v.id+',dir:1})">⬇️</button><button type="button" class="beDel" onclick="eveDel('+v.id+')">🗑</button></div></div>').join('');
  bpFlash='';
}
async function eveStartUpload(){
  try{ const d=await bpPost('vidmode',{n:0,title:($('vidTitle').value||'').trim()});
    if(!d.ok){ notify(d.error||'Xatolik'); return; }
    bpFlash='✅ Tayyor! Endi botga o‘ting va videoni yuboring. Tugatgach /asar_tamom yozing, so‘ng bu yerga qaytib sahifani yangilang.'; eveManage();
    try{ setTimeout(()=>tg.close(),1500); }catch(e){}
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
}
async function eveAct(act,data){ try{ const d=await bpPost(act,Object.assign({n:0},data)); if(!d.ok){ notify(d.error||'Xatolik'); return; } await eveReload(); eveManage(); }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); } }
const eveRename=id=>bpPost('renvideo',{n:0,id,title:$('vt'+id).value}).then(()=>eveReload()).catch(()=>{});
function eveDel(id){ bpConfirm('Bu video o‘chirilsinmi?',()=>eveAct('rmvideo',{id})); }


// ===== v74: Mock testining PDF varianti
async function mockPdfUpload(id,file,title){
  if(!/\.pdf$/i.test(file.name)&&file.type!=='application/pdf') return {ok:false,error:'Faqat PDF qabul qilinadi.'};
  if(file.size>PDF_MAX_MB*1024*1024) return {ok:false,error:'«'+file.name+'» '+PDF_MAX_MB+' MB dan katta.'};
  try{ const b64=await fileToB64(file);
    return await (await apiFetch(apiUrl('/api/mock/pdf/up'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,file:b64,name:file.name,title})})).json();
  }catch(e){ return {ok:false,error:e.message||'Server bilan bog‘lanishda xatolik.'}; }
}
let MPDF=null, MPDFid=0;
async function openMockPdf(id){
  MPDFid=id; openSection('teacherStats'); const box=$('tsBody'); box.innerHTML='<div class="word">⏳ Yuklanmoqda...</div>';
  try{ MPDF=await (await apiFetch(apiUrl('/api/mock/pdf/list?id='+encodeURIComponent(id)),{cache:'no-store'})).json(); }catch(e){ box.innerHTML='<div class="result">❌ Server bilan bog‘lanishda xatolik.</div>'; return; }
  if(!MPDF.ok){ box.innerHTML=bpBack('Mock',"openSection('mock')")+'<div class="result">❌ '+escapeHtml(MPDF.error||'Xatolik')+'</div>'; return; }
  renderMockPdf();
}
function renderMockPdf(msg){
  const d=MPDF, box=$('tsBody'), fs=d.pdfs||[], adm=d.is_admin;
  box.innerHTML=bpBack('Mock',"openSection('mock');loadMocks()")+'<h2>📄 Test PDF</h2>'
    +(msg?'<div class="result bpFlash">'+escapeHtml(msg)+'</div>':'')
    +(fs.length?fs.map((f,i)=>'<div class="beQ"><button class="bpTab vidRow" type="button" onclick="mockPdfSend('+f.id+')"><b>📥</b><span>'+(i+1)+'. '+escapeHtml(f.title)+'</span><small>'+(gzSize(f.size)||'PDF')+'</small></button>'
        +(adm?'<div class="slBtns"><button type="button" class="beDel" onclick="mockPdfDel('+f.id+')">🗑 O‘chirish</button></div>':'')+'</div>').join('')
        +'<p class="muted">Bossangiz, PDF shu bot chatiga yuboriladi (forward va saqlash yopiq).</p>'
      :'<div class="word">Hali PDF yuklanmagan.</div>')
    +(adm?'<div class="result bpInfo"><label class="bpLbl">📎 PDF yuklash</label><input id="mpTitle" maxlength="150" placeholder="Nomi (ixtiyoriy)"><input id="mpFile" type="file" accept="application/pdf,.pdf">'
        +'<button class="primaryAction" type="button" id="mpBtn" onclick="mockPdfDo()">📤 PDF ni yuklash</button><div id="mpSt" class="muted"></div></div>'
        +(fs.length?'<button class="primaryAction" type="button" onclick="mockPdfBlast()">📤 Ro‘yxatdan o‘tganlarga yuborish ('+(d.regs||0)+' kishi)</button><p class="muted">Har bir PDF har kimga faqat bir marta yuboriladi — qayta bossangiz, faqat yangi qo‘shilganlarga ketadi. Ro‘yxatdan o‘tganlar mock ochiq paytda PDF ni Mock bo‘limidagi «📄 Test PDF» tugmasidan o‘zlari ham oladi.</p>':''):'');
  window.scrollTo(0,0);
}
async function mockPdfDo(){
  const f=$('mpFile').files[0], st=$('mpSt'), btn=$('mpBtn'); if(!f){ notify('Avval PDF faylni tanlang.'); return; }
  btn.disabled=true; st.textContent='⏳ Yuklanmoqda...';
  const r=await mockPdfUpload(MPDFid,f,($('mpTitle').value||'').trim()); btn.disabled=false;
  if(!r.ok){ st.textContent='⚠️ '+(r.error||'Xatolik'); return; }
  MPDF.pdfs=r.pdfs; renderMockPdf('✅ PDF yuklandi va saqlandi.');
}
function mockPdfDel(pid){ bpConfirm('Bu PDF o‘chirilsinmi?',async()=>{ const r=await (await apiFetch(apiUrl('/api/mock/pdf/del'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:MPDFid,pdf:pid})})).json(); if(!r.ok){ notify(r.error||'Xatolik'); return; } MPDF.pdfs=r.pdfs; renderMockPdf(); }); }
let _mpBusy=false;
async function mockPdfSend(pid){
  if(_mpBusy) return; _mpBusy=true;
  try{ const r=await (await apiFetch(apiUrl('/api/mock/pdf/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:MPDFid,pdf:pid})})).json();
    if(!r.ok){ notify(r.error||'PDF yuborilmadi.'); return; }
    notify('📄 PDF bot chatiga yuborildi. Botga o‘tib oching.'); try{ setTimeout(()=>tg.close(),900); }catch(e){}
  }catch(e){ notify('Server bilan bog‘lanishda xatolik.'); }
  finally{ setTimeout(()=>{ _mpBusy=false; },1500); }
}
function mockPdfBlast(){
  bpConfirm('PDF mockga ro‘yxatdan o‘tgan barcha foydalanuvchilarga yuborilsinmi?',async()=>{
    const r=await (await apiFetch(apiUrl('/api/mock/pdf/blast'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:MPDFid})})).json();
    if(!r.ok){ notify(r.error||'Xatolik'); return; }
    renderMockPdf(r.sent?('✅ '+r.sent+' kishiga yuborilmoqda (ro‘yxatda jami '+r.registered+' kishi).'):'ℹ️ Hamma ro‘yxatdagilarga PDF allaqachon yuborilgan.');
  });
}

// ---- v101: «Test javoblari» — natijadan keyin alohida to'liq ro'yxat + Word fayl (diagnostik: darrov; mock: e'longach)
function ansKeyBox(code,where,id){
  if(!code) return '';
  return '<div class="result"><h4 style="margin:0 0 4px">📥 Test javoblari</h4><p class="muted" style="margin:0 0 8px">Hamma savolning to‘g‘ri javobi va sizning javobingiz — alohida ro‘yxat. Xohlasangiz Word fayl qilib chatga yuboramiz.</p>'
    +'<button class="primaryAction" type="button" onclick="openAnswerKey(\''+String(code).replace(/[^A-Za-z0-9_-]/g,'')+'\',\''+where+'\','+(Number(id)||0)+')">📥 Test javoblarini ochish</button></div>';
}
function akBack(where,id){ return where==='mock'?'openMyMock('+(Number(id)||0)+')':"openSection('national')"; }
async function openAnswerKey(code,where,id){
  openSection('nationalResult');
  const bk='<button class="back" onclick="'+akBack(where,id)+'">‹ Natijaga qaytish</button>';
  $('nationalResult').innerHTML=bk+'<div class="result">⏳ Javoblar yuklanmoqda…</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/national/answers?code='+encodeURIComponent(code)),{cache:'no-store'})).json();
    if(!d.ok){ $('nationalResult').innerHTML=bk+'<div class="result">'+(d.wait?'⏳ ':'❌ ')+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    const ic={ok:'✅',bad:'❌',partial:'🟡',key:'•',essay:'✍️'};
    const nBad=d.items.filter(x=>x.status==='bad'||x.status==='partial').length;
    let o=bk+'<div class="result"><h3 style="margin:0 0 4px">📥 Test javoblari</h3><p style="margin:0"><b>'+escapeHtml(d.title||'')+'</b></p>'
      +(d.taken&&d.raw!=null?'<p class="muted" style="margin:4px 0 0">To‘g‘ri javob: <b>'+d.raw+'/'+d.max+'</b> • xato/qisman: <b>'+nBad+'</b></p>':'<p class="muted" style="margin:4px 0 0">To‘g‘ri javoblar kaliti</p>')+'</div>';
    o+='<div class="akBar"><button type="button" class="listbtn akOn" id="akAll" onclick="akFilter(0)">Hammasi</button>'+(d.taken?'<button type="button" class="listbtn" id="akBad" onclick="akFilter(1)">Faqat xatolarim ('+nBad+')</button>':'')+'</div>';
    o+='<div id="akList">'+d.items.map(x=>{
      const bad=(x.status==='bad'||x.status==='partial')?' akBadRow':'';
      return '<div class="akRow '+x.status+bad+'"><div class="akH"><b>'+x.number+'</b><span>'+(ic[x.status]||'')+'</span><em>'+escapeHtml(x.type==='O2'?'Esse':x.type)+'</em></div>'
        +(x.text?'<div class="akQ">'+escapeHtml(x.text)+'</div>':'')
        +(x.status==='essay'?'<div class="akC">'+escapeHtml(x.correct_text)+'</div>'
          :(x.status==='key'?'':'<div class="akU">Siz: <b>'+escapeHtml(x.user_text)+'</b></div>')+'<div class="akC">To‘g‘ri: <b>'+escapeHtml(x.correct_text)+'</b></div>')
        +(x.explanation?'<div class="akE">💡 '+escapeHtml(x.explanation)+'</div>':'')+'</div>';
    }).join('')+'</div>';
    if(ME&&ME.is_admin) o+='<button class="primaryAction" type="button" onclick="openTestEdit(\''+String(code).replace(/[^A-Za-z0-9_-]/g,'')+'\')">✏️ Savol/javoblarni tahrirlash (admin)</button>';
    o+='<button class="primaryAction" type="button" onclick="sendAnswerKey(\''+String(code).replace(/[^A-Za-z0-9_-]/g,'')+'\',this)">📄 Word fayl sifatida chatga yuborish</button>';
    $('nationalResult').innerHTML=o; window.scrollTo(0,0);
  }catch(e){ $('nationalResult').innerHTML=bk+'<div class="result">❌ Javoblarni yuklab bo‘lmadi. Birozdan keyin urinib ko‘ring.</div>'; }
}

// ===== v103: ADMIN — mavjud testning savol matni / to'g'ri javobi / izohini tahrirlash =====
let _te={code:'',items:[],edits:{}};
function teCount(){ return Object.keys(_te.edits).length; }
function teMark(n){
  const r=$('teR'+n); if(r) r.classList.toggle('teDirty',!!_te.edits[n]);
  const b=$('teSave'); if(b){ b.textContent='💾 Saqlash'+(teCount()?' ('+teCount()+' ta o‘zgarish)':''); b.disabled=!teCount(); }
}
function teSet(n,field,val){
  const it=_te.items.find(x=>x.number===n); if(!it) return;
  const orig=(field==='answer'||field==='text'||field==='explanation')?String(it[field]||''):(it[field]||[]).join(' / ');
  const e=_te.edits[n]||{number:n}; e[field]=val;
  // hamma maydon asl holatiga qaytgan bo'lsa — o'zgarish ro'yxatidan olib tashlanadi
  const same=Object.keys(e).filter(k=>k!=='number').every(k=>{
    const o=(k==='answer'||k==='text'||k==='explanation')?String(it[k]||''):(it[k]||[]).join(' / ');
    return String(e[k]).trim()===o.trim();
  });
  if(same) delete _te.edits[n]; else _te.edits[n]=e;
  teMark(n);
}
function teKey(n,L){
  document.querySelectorAll('#teR'+n+' .teKey').forEach(b=>b.classList.toggle('on',b.dataset.v===L));
  teSet(n,'answer',L);
}
async function openTestEdit(code){
  _te={code:code,items:[],edits:{}};
  openSection('nationalResult');
  const bk='<button class="back" onclick="openSection(\'mock\')">‹ Mock</button>';
  $('nationalResult').innerHTML=bk+'<div class="result">⏳ Savollar yuklanmoqda…</div>';
  try{
    const d=await (await apiFetch(apiUrl('/api/national/test-edit?code='+encodeURIComponent(code)),{cache:'no-store'})).json();
    if(!d.ok){ $('nationalResult').innerHTML=bk+'<div class="result">❌ '+escapeHtml(d.error||'Xatolik')+'</div>'; return; }
    _te.items=d.items;
    let o=bk+'<div class="result"><h3 style="margin:0 0 4px">✏️ Savol va javoblarni tahrirlash</h3><p style="margin:0"><b>'+escapeHtml(d.title||'')+'</b> • '+escapeHtml(d.code)+'</p>'
      +'<p class="muted" style="margin:6px 0 0">Ishtirokchilar: <b>'+d.attempts+'</b>. Saqlaganda ularning test ballari yangi javoblar bo‘yicha o‘zi qayta hisoblanadi.</p>'
      +(d.published?'<p style="margin:6px 0 0;color:#b4531a"><b>⚠️ Natijalar allaqachon e‘lon qilingan.</b> E‘lon qilingan umumiy ball, o‘rin va sertifikatlar avtomatik o‘zgarmaydi.</p>':'')+'</div>';
    o+=d.items.map(x=>{
      const n=x.number; let ctl='';
      if(x.type==='Y1'||x.type==='Y2'){
        const opts=(x.options&&x.options.length)?x.options:(x.type==='Y1'?['A','B','C','D']:['A','B','C','D','E','F']);
        ctl='<div class="teKeys">'+opts.map(L=>'<button type="button" class="teKey'+(String(x.answer).toUpperCase()===L?' on':'')+'" data-v="'+L+'" onclick="teKey('+n+',\''+L+'\')">'+L+'</button>').join('')+'</div>';
      }else if(x.type==='O1'){
        ctl='<label class="teLb">To‘g‘ri javob (bir nechta bo‘lsa «/» bilan)</label><input class="teIn" value="'+escapeHtml((x.answers||[]).join(' / '))+'" oninput="teSet('+n+',\'answers\',this.value)">';
      }else if(x.type==='O1AB'){
        ctl='<label class="teLb">a) to‘g‘ri javob</label><input class="teIn" value="'+escapeHtml((x.a_answers||[]).join(' / '))+'" oninput="teSet('+n+',\'a_answers\',this.value)">'
           +'<label class="teLb">b) to‘g‘ri javob</label><input class="teIn" value="'+escapeHtml((x.b_answers||[]).join(' / '))+'" oninput="teSet('+n+',\'b_answers\',this.value)">';
      }else ctl='<div class="muted">Esse — test javoblariga kirmaydi.</div>';
      return '<div class="teRow" id="teR'+n+'"><div class="teH"><b>'+n+'</b><em>'+escapeHtml(x.type==='O2'?'Esse':x.type)+'</em></div>'
        +'<textarea class="teTx" rows="2" placeholder="Savol matni (ixtiyoriy)" oninput="teSet('+n+',\'text\',this.value)">'+escapeHtml(x.text||'')+'</textarea>'
        +ctl
        +(x.type==='O2'?'':'<input class="teIn teEx" placeholder="💡 Izoh (ixtiyoriy)" value="'+escapeHtml(x.explanation||'')+'" oninput="teSet('+n+',\'explanation\',this.value)">')+'</div>';
    }).join('');
    o+='<div class="teBar"><button type="button" class="primaryAction" id="teSave" onclick="teSave()" disabled>💾 Saqlash</button></div><div id="teMsg"></div>';
    $('nationalResult').innerHTML=o; window.scrollTo(0,0);
  }catch(e){ $('nationalResult').innerHTML=bk+'<div class="result">❌ Yuklab bo‘lmadi. Birozdan keyin urinib ko‘ring.</div>'; }
}
async function teSave(){
  const edits=Object.values(_te.edits); if(!edits.length) return;
  const b=$('teSave'); if(b){ b.disabled=true; b.textContent='⏳ Saqlanmoqda…'; }
  try{
    const d=await (await apiFetch(apiUrl('/api/national/test-update'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:_te.code,edits})})).json();
    if(!d.ok){ notify(d.error||'Saqlab bo‘lmadi'); if(b){ b.disabled=false; teMark(0); } return; }
    // saqlangan qiymatlar endi "asl" holat
    edits.forEach(e=>{ const it=_te.items.find(x=>x.number===e.number); if(!it) return;
      Object.keys(e).forEach(k=>{ if(k==='number') return;
        if(k==='answer'||k==='text'||k==='explanation') it[k]=e[k]; else it[k]=String(e[k]).split(/[\/;]/).map(x=>x.trim()).filter(Boolean); });
      const r=$('teR'+e.number); if(r) r.classList.remove('teDirty'); });
    _te.edits={}; teMark(0);
    $('teMsg').innerHTML='<div class="result"><b>✅ Saqlandi.</b><p style="margin:6px 0 0">Yangilangan savollar: <b>'+d.changed_questions+'</b><br>Qayta hisoblangan ishtirokchilar: <b>'+d.attempts+'</b> (ballari o‘zgargani: <b>'+d.changed_attempts+'</b>)</p>'
      +(d.published?'<p style="margin:6px 0 0;color:#b4531a">⚠️ Natijalar oldin e‘lon qilingan edi — e‘lon qilingan o‘rin/umumiy ball va sertifikatlar avtomatik yangilanmadi.</p>':'')+'</div>';
    notify('Saqlandi.');
  }catch(e){ notify('Server bilan aloqa yo‘q. Qayta urinib ko‘ring.'); if(b){ b.disabled=false; teMark(0); } }
}
function akFilter(bad){
  const l=$('akList'); if(!l) return;
  l.classList.toggle('akOnlyBad',!!bad);
  const a=$('akAll'), b=$('akBad'); if(a) a.classList.toggle('akOn',!bad); if(b) b.classList.toggle('akOn',!!bad);
}
async function sendAnswerKey(code,btn){
  if(btn){ btn.disabled=true; btn.dataset.t=btn.textContent; btn.textContent='⏳ Yuborilmoqda…'; }
  try{
    const r=await apiFetch(apiUrl('/api/national/answers/send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
    const d=await r.json();
    notify(d.ok?'📥 Fayl botdagi chatingizga yuborildi.':(d.error||'Yuborib bo‘lmadi.'));
  }catch(e){ notify('Yuborishda xatolik. Qayta urinib ko‘ring.'); }
  if(btn){ btn.disabled=false; btn.textContent=btn.dataset.t||'📄 Word fayl sifatida chatga yuborish'; }
}
