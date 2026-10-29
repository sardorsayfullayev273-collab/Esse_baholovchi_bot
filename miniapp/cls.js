// v110: USTOZ PANELI — soddalashtirilgan va premium ko'rinish.
// 3 qadam: sinf yarating → havolani yuboring → vazifa/test bering. Qolganini bot yuritadi (eslatma, natija, reyting, ota-onaga hisobot).
// Ikki bo'lim: «Sinflarim» (shu fayl) va «Test tahlili» (eski Ustoz Pro — app.js renderTeacher, #teacherBody).
// Ota-ona: ustoz yuborgan havola orqali (login/parolsiz); eski login/parol kirishi pastda ixcham saqlangan.
(function(){
const E=s=>escapeHtml(String(s==null?'':s));
const ST={view:'home',main:'classes',cid:null,tab:'students',sid:null,hw:null,tid:null,open:null,data:null,me:null,rid:null,home:null,msTests:null};
let LOCK=false;
const top=()=>$('clsTop');
async function G(path){ try{ const r=await apiFetch(apiUrl(path),{cache:'no-store'}); return await r.json(); }catch(e){ return {ok:false,error:'Server bilan bog‘lanishda xatolik.'}; } }
const P=(path,b)=>tchPost(path,b);
const V=id=>{ const x=$(id); return x?x.value.trim():''; };
const pc=v=>v==null?'—':v+'%';
const col=v=>v==null?'':v>=70?'ok':v>=50?'mid':'bad';
const bar=(v,c)=>'<div class="clBar"><i class="'+(c||col(v))+'" style="width:'+(v==null?0:Math.max(3,Math.min(100,v)))+'%"></i></div>';
const SL={p:'✅ Keldi',l:'⏰ Kechikdi',a:'❌ Kelmadi',e:'📝 Sababli'};
const ini=n=>String(n||'?').trim().split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase()||'?';
function ask(m){ return new Promise(res=>{ if(window.tg&&tg.showConfirm){ try{ tg.showConfirm(m,res); return; }catch(e){} } res(window.confirm(m)); }); }
function copy(t){ try{ if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(t); notify('Nusxalandi ✅'); return; } }catch(e){}
  const a=document.createElement('textarea'); a.value=t; document.body.appendChild(a); a.select(); try{ document.execCommand('copy'); notify('Nusxalandi ✅'); }catch(e){ notify(t); } a.remove(); }
function put(h){ const t=top(); if(t) t.innerHTML=h; }
const loading=()=>put('<div class="clSk"><i></i><i></i><i></i></div>');
function err(r){ notify((r&&r.error)||'Xatolik. Qayta urinib ko‘ring.'); }
const uname=()=>(window.ME&&ME.bot_username)?String(ME.bot_username).replace(/^@/,''):'';
const botLink=cid=>uname()?('https://t.me/'+uname()+'?start=c_'+cid):'';
const startLink=st=>uname()?('https://t.me/'+uname()+'?start='+st):'';
const share=(l,t)=>{ if(typeof openShare==='function') openShare(l,t); else copy(l); };

// ===================================================== kirish nuqtalari
window.clsEnter=async function(){
  if(!top()) return false;
  const d=await G('/api/class/me'); ST.me=d; const h=$('clsH2'), tb=$('teacherBody');
  if(d.ok&&d.parent&&!d.teacher&&!(window.ME&&ME.is_admin)){
    if(tb) tb.classList.add('hidden'); if(h) h.textContent='👪 Ota-ona bo‘limi'; ST.view='pList'; await pList(); return true;
  }
  if(h) h.textContent='🧑‍🏫 Ustoz paneli';
  if(d.ok&&d.teacher){ ST.view='home'; await tHome(); } else { if(tb) tb.classList.add('hidden'); put(notTeacher()); }
  return false;
};
window.clsBoot=function(){
  if(LOCK||!window.ME||!ME.parent_mode||ME.class_teacher||ME.is_admin) return;
  LOCK=true; document.body.classList.add('parentLock');
  const os=window.openSection;
  window.openSection=function(id){ return os.call(window,'teacher'); };
  window.goHome=function(){ return os.call(window,'teacher'); };
  os.call(window,'teacher');
};
function syncMain(){ const tb=$('teacherBody'); if(tb) tb.classList.toggle('hidden',!(ST.view==='home'&&ST.main==='tahlil')); }
function mainTabs(){
  return '<div class="clMain"><button class="'+(ST.main==='classes'?'on':'')+'" onclick="CLS.main(\'classes\')">🏫 Sinflarim</button><button class="'+(ST.main==='tahlil'?'on':'')+'" onclick="CLS.main(\'tahlil\')">📊 Test tahlili</button></div>';
}
function notTeacher(){
  return '<div class="clHero"><span class="clTag">USTOZ PANELI</span><h2>Sinfingizni bir joyda boshqaring</h2><p>Vazifa va test bering, natijalarni kuzating, ota-onalarga avtomatik hisobot yuboring.</p></div>'
    +'<div class="clBox"><b>Ustoz sifatida ulanish</b><small>Ustoz panelini yoqish uchun botda /ustoz buyrug‘ini yuboring yoki admin bilan bog‘laning.</small></div>'+parentEntry();
}

// ===================================================== USTOZ: BOSH EKRAN
function steps(){
  return '<div class="clSteps"><div><b>1</b><span>Sinf yarating</span></div><i></i><div><b>2</b><span>Havolani yuboring</span></div><i></i><div><b>3</b><span>Vazifa yoki test bering</span></div></div>';
}
function createForm(first){
  return '<div class="clBox clCreate"><b>'+(first?'Birinchi sinfingizni yarating':'Yangi sinf')+'</b>'
    +'<input id="cl_name" placeholder="Masalan: 11-A yoki Ona tili guruhi" maxlength="60"><input id="cl_subj" placeholder="Fan (ixtiyoriy)" maxlength="40">'
    +'<button class="pri" onclick="CLS.create()">＋ Sinf yaratish</button><small>Ro‘yxat yozish shart emas — o‘quvchilar havola orqali o‘zlari qo‘shiladi.</small></div>';
}
async function tHome(){
  ST.view='home'; syncMain();
  if(ST.main==='tahlil'){ put(mainTabs()); return; }
  loading(); const d=await G('/api/class/home'); if(!d.ok){ put(mainTabs()+'<div class="result">❌ '+E(d.error)+'</div>'); return; }
  ST.home=d; const st=d.stats||{}; const has=d.classes.length>0;
  let h=mainTabs();
  if(!has){
    h+='<div class="clHero"><span class="clTag">USTOZ PANELI</span><h2>Sinfingizni 1 daqiqada ishga tushiring</h2><p>Vazifa va test bering — natija, eslatma va ota-onaga hisobotni bot o‘zi yuritadi.</p></div>'+steps()+(d.can_create?createForm(true):'<div class="clBox"><b>Ustoz sifatida ulanish</b><small>Sinf yaratish uchun botda /ustoz yuboring.</small></div>');
  }else{
    h+='<div class="clHero sm"><div><span class="clTag">USTOZ PANELI</span><h2>Sinflaringiz bir joyda</h2></div>'+(d.can_create?'<button class="clCta" onclick="CLS.newClass()">＋ Sinf</button>':'')+'</div>';
    h+='<div class="clMets"><div><b>'+st.classes+'</b><small>sinf</small></div><div><b>'+st.students+'</b><small>o‘quvchi</small></div><div><b class="'+col(st.week_pct)+'">'+pc(st.week_pct)+'</b><small>shu hafta topshirdi</small></div></div>';
    h+='<div id="clNew" class="hidden">'+createForm(false)+'</div>';
    if(d.today.length){
      h+='<h3 class="clH">Bugun</h3><div class="clList">'+d.today.map(x=>'<button class="clRowT" onclick="CLS.'+(x.kind==='hw'?'goHw('+x.cid+','+x.id+')':'goTest('+x.cid+','+x.id+')')+'"><span class="clIc '+(x.kind==='hw'?'warn':'acc')+'">'+(x.kind==='hw'?'📚':'📝')+'</span><div><b>'+E(x.title)+'</b><small>'+E(x.class)+' • muddat '+E(x.due_text)+(x.kind==='hw'&&x.total?' • '+x.missing+' kishi topshirmagan':'')+'</small></div><i>›</i></button>').join('')+'</div>';
    }
    h+='<h3 class="clH">Sinflarim</h3>'+d.classes.map(k=>'<div class="clClass" onclick="CLS.open('+k.id+')"><div class="clCt"><div><b>'+E(k.name)+'</b><small>'+(k.subject?E(k.subject)+' • ':'')+'👥 '+k.students+(k.linked<k.students?' • botda '+k.linked:'')+'</small></div><i>›</i></div>'
      +(k.avg!=null?'<div class="clAvg">'+bar(k.avg)+'<span class="'+col(k.avg)+'">'+k.avg+'%</span></div>':'<small class="clHint">Hali natija yo‘q — vazifa yoki test bering</small>')
      +(k.top?'<small class="clTop">🥇 '+E(k.top.name)+' • '+k.top.comp+'%</small>':'')
      +'<div class="clAct2" onclick="event.stopPropagation()"><button class="clGhost" onclick="CLS.copy(\''+botLink(k.id)+'\')">🔗 Havolani nusxalash</button></div></div>').join('');
  }
  h+=parentEntry();
  const adm=!!(window.ME&&ME.is_admin);
  if(adm) h+='<details class="clBox clAdm"><summary>⚙️ Admin: ota-onaga xabar vaqti</summary><div id="clAdminCfg"><div class="word">⏳ Yuklanmoqda...</div></div></details>';
  put(h); if(adm) adminCfgLoad();
}
function parentEntry(){
  let h='';
  if(ST.me&&ST.me.parent) h+='<button class="clGhost wide" onclick="CLS.toParent()">👪 Farzandlarim (ota-ona sifatida)</button>';
  h+='<details class="clPar"><summary>👪 Ota-onamisiz? Farzandimni ko‘rish</summary><p class="clHint">Ustoz yuborgan havolani oching — kirish o‘zi bajariladi. Havolangiz bo‘lmasa, ustozdan so‘rang. Eski usul: login va parol bilan kirish.</p>'+loginCard()+'</details>';
  return h;
}

// ----- ADMIN: ota-onaga xabar yuborish vaqti
const DAYS=['Dushanba','Seshanba','Chorshanba','Payshanba','Juma','Shanba','Yakshanba'];
const hrs=(sel,lo,hi)=>{ let o=''; for(let i=lo;i<=hi;i++) o+='<option value="'+i+'"'+(i===sel?' selected':'')+'>'+String(i).padStart(2,'0')+':00</option>'; return o; };
function adminCfgHtml(d){
  const c=d.cfg, s=d.stats;
  return '<div class="word">Hozir Toshkentda <b>'+E(d.now)+'</b> • oyna '+(c.enabled?(d.open?'<b>ochiq ✅</b>':'<b>yopiq 🌙</b>'):'<b>to‘xtatilgan ⏸</b>')+'<br>Navbatda: <b>'+s.pending+'</b> ta (hoziroq ketadi: '+s.ready+', kutmoqda: '+s.waiting+')</div>'
   +'<label class="clCk"><input type="checkbox" id="cf_en"'+(c.enabled?' checked':'')+'> Ota-ona va o‘quvchilarga xabar yuborish yoqilgan</label>'
   +'<div class="clRow2"><label>Yuborish boshlanishi<select id="cf_from">'+hrs(c.from,0,23)+'</select></label><label>Yuborish tugashi<select id="cf_to">'+hrs(c.to,1,24)+'</select></label></div>'
   +'<div class="clRow2"><label>Haftalik hisobot kuni<select id="cf_wd">'+DAYS.map((n,i)=>'<option value="'+i+'"'+(i===c.weekly_day?' selected':'')+'>'+n+'</option>').join('')+'</select></label><label>Soati (shundan keyin)<select id="cf_wh">'+hrs(c.weekly_hour,0,23)+'</select></label></div>'
   +'<label>To‘lov eslatmasi soati (shundan keyin)<select id="cf_fh">'+hrs(c.fee_hour,0,23)+'</select></label>'
   +'<div class="word">Oynadan tashqarida chiqadigan xabarlar oyna ochilguncha navbatda turadi. Vaqt — Toshkent.</div>'
   +'<button class="pri" onclick="CLS.cfgSave()">💾 Saqlash</button>';
}
async function adminCfgLoad(){
  const d=await G('/api/class/admin/cfg'), b=$('clAdminCfg'); if(!b) return;
  b.innerHTML=d.ok?adminCfgHtml(d):'<div class="word">❌ '+E(d.error||'Xatolik')+'</div>';
}

// ===================================================== USTOZ: SINF SAHIFASI
async function tOpen(cid,tab){
  ST.cid=cid; ST.tab=tab||ST.tab||'students'; ST.view='class'; syncMain(); loading();
  const d=await G('/api/class/detail?id='+cid); if(!d.ok){ err(d); return tHome(); } ST.data=d; tRender();
}
function tabsHtml(){
  const T=[['students','👥 O‘quvchilar'],['hw','📚 Vazifa'],['tests','📝 Test'],['rating','🏆 Reyting'],['more','⋯ Qo‘shimcha']];
  return '<div class="clTabs">'+T.map(t=>'<button class="'+(ST.tab===t[0]?'on':'')+'" onclick="CLS.tab(\''+t[0]+'\')">'+t[1]+'</button>').join('')+'</div>';
}
function inviteBox(k){
  const lk=botLink(k.id); if(!lk) return '';
  const nm=E(k.name).replace(/'/g,'’');
  return '<div class="clInvite"><div><b>🔗 O‘quvchilarni chaqiring</b><small>Havolani yuboring — ular bir bosishda qo‘shiladi. Ro‘yxat yozish shart emas.</small></div><div class="clRow"><button class="clCta" onclick="CLS.copy(\''+lk+'\')">Nusxalash</button><button class="clGhost" onclick="CLS.share(\''+lk+'\',\''+nm+' sinfiga qo‘shiling\')">📤 Ulashish</button></div></div>';
}
function tRender(){
  const d=ST.data, k=d.cls; ST.view='class'; syncMain();
  const avg=(d.rating&&d.rating.avg!=null)?d.rating.avg:null;
  let h='<button class="clGhost" onclick="CLS.list()">‹ Sinflar</button><div class="clHead"><div class="clAv">🏫</div><div><h3 class="clH">'+E(k.name)+'</h3><small class="clSub">'+(k.subject?E(k.subject)+' • ':'')+'👥 '+k.students+(k.linked<k.students?' • botda '+k.linked:'')+(avg!=null?' • o‘rtacha '+avg+'%':'')+'</small></div></div>'+inviteBox(k)+tabsHtml();
  h+=({students:tStudents,hw:tHw,tests:tTests,rating:tRating,more:tMore}[ST.tab]||tStudents)(d);
  put(h);
}

// ----- o'quvchilar
function tStudents(d){
  let h='';
  if(!d.roster.length) h+='<div class="clEmpty"><b>Hali o‘quvchi yo‘q</b><small>Yuqoridagi havolani guruhingizga yuboring — o‘quvchilar shu yerda paydo bo‘ladi.</small></div>';
  h+=d.roster.map(r=>{
    const s=r.stats||{}, open=ST.open===r.id;
    const b1=r.linked?'<em class="clB ok">botda</em>':'<em class="clB">kutilmoqda</em>';
    const b2=r.parent_linked?'<em class="clB ok">ota-ona ulangan</em>':'';
    let x='<div class="clRowS" onclick="CLS.toggle('+r.id+')"><div class="clAv sm">'+E(ini(r.full_name))+'</div><div class="clGrow"><b>'+E(r.full_name)+'</b><small>'+b1+b2+'</small></div><div class="clPct '+col(s.comp)+'">'+pc(s.comp)+'</div></div>';
    if(open){
      x+='<div class="clAct"><div class="clMeters"><div><span>Vazifa</span>'+bar(s.hw)+'<b>'+pc(s.hw)+'</b></div><div><span>Test</span>'+bar(s.test)+'<b>'+pc(s.test)+'</b></div><div><span>Davomat</span>'+bar(s.att)+'<b>'+pc(s.att)+'</b></div></div>'
        +'<div class="clRow"><button class="clGhost" onclick="CLS.parentLink('+r.id+')">👪 Ota-ona havolasi</button><button class="clGhost" onclick="CLS.msgOne('+r.id+')">📩 Xabar</button>'+(r.linked?'<button class="clGhost" onclick="CLS.unlink('+r.id+')">⛓ Uzish</button>':'')+'<button class="clGhost danger" onclick="CLS.delR('+r.id+')">🗑</button></div></div>';
    }
    return '<div class="clStu">'+x+'</div>';
  }).join('');
  h+='<details class="clBox clMore"><summary>👪 Ota-onalarni ulash</summary><small>Har bir o‘quvchi uchun alohida havola. Ota-ona havolani bossa — login/parolsiz ulanadi va hisobotlar botga keladi.</small><button class="clGhost" onclick="CLS.parentLinks()">📋 Hamma ota-onalar havolalarini nusxalash</button></details>';
  h+='<details class="clBox clMore"><summary>＋ Ism qo‘shish (Telegramsiz o‘quvchi)</summary><div class="clRow"><input id="cl_one" placeholder="Ism Familiya" maxlength="60"><button class="clGhost" onclick="CLS.addOne()">Qo‘shish</button></div></details>';
  return h;
}

// ----- davomat (Qo'shimcha ichida)
function attHtml(d){
  let h='<div class="clBox"><b>🕘 Yangi davomat</b><input id="cl_at" placeholder="Dars nomi (ixtiyoriy)" maxlength="60"><div class="clRow"><select id="cl_am"><option value="code">Kod bilan (ishonchli)</option><option value="button">Tugma bilan (kodsiz)</option></select><select id="cl_amin"><option value="10">10 daq</option><option value="20" selected>20 daq</option><option value="30">30 daq</option><option value="60">60 daq</option></select></div><button class="pri" onclick="CLS.attStart()">Davomatni ochish</button><small>Kod rejimida o‘quvchi darsda e’lon qilingan 4 xonali kodni /keldim KOD bilan yuboradi. Vaqt tugagach belgilanmaganlar «kelmadi» bo‘ladi va ota-onalarga xabar ketadi.</small></div>';
  if(!d.sessions.length) return h+'<div class="clEmpty"><small>Hali davomat o‘tkazilmagan.</small></div>';
  return h+d.sessions.map(s=>'<button class="clCard" onclick="CLS.sess('+s.id+')"><b>'+E(s.title)+'</b><small>'+E(s.when)+' • '+(s.open?'🟢 ochiq':(s.closed?'yopilgan':'🟠 vaqti o‘tdi'))+'</small><span>›</span></button>').join('');
}
async function tSess(sid){
  ST.sid=sid; ST.view='sess'; loading(); const d=await G('/api/class/att?sid='+sid); if(!d.ok){ err(d); return tOpen(ST.cid,'more'); }
  const s=d.session, op=!s.closed;
  let h='<button class="clGhost" onclick="CLS.tab(\'more\')">‹ Qo‘shimcha</button><h3 class="clH">'+E(s.title)+'</h3>';
  if(op){ h+='<div class="clBox">'+(s.code?'🔑 Kod: <b class="clCode">'+E(s.code)+'</b><small>Darsda og‘zaki e’lon qiling.</small>':'Tugma rejimi (kodsiz)')+'<div class="clRow"><button class="clGhost" onclick="CLS.sess('+sid+')">🔄 Yangilash</button><button class="pri" onclick="CLS.attClose('+sid+')">🏁 Yakunlash</button></div></div>'; }
  else h+='<div class="clBox"><b>Yakunlangan.</b><div class="clRow"><button class="clGhost" onclick="CLS.attNotify('+sid+')">📨 Kelmaganlar ota-onasiga xabar</button></div></div>';
  const cnt={}; d.rows.forEach(r=>{ cnt[r.status||'-']=(cnt[r.status||'-']||0)+1; });
  h+='<small class="clSub">✅ '+(cnt.p||0)+' • ⏰ '+(cnt.l||0)+' • ❌ '+(cnt.a||0)+' • 📝 '+(cnt.e||0)+' • belgilanmagan '+(cnt['-']||0)+'</small>';
  h+=d.rows.map(r=>'<div class="clStu"><div class="clRowS"><div class="clGrow"><b>'+E(r.name)+'</b>'+(r.note?'<small>💬 «'+E(r.note)+'»</small>':'')+'</div></div><div class="clSeg">'+['p','l','a','e'].map(c=>'<button class="'+(r.status===c?'on '+c:'')+'" onclick="CLS.mark('+sid+','+r.rid+',\''+c+'\')">'+SL[c]+'</button>').join('')+'</div></div>').join('');
  put(h);
}

// ----- vazifa
function tHw(d){
  let h='<div class="clBox"><b>📚 Yangi vazifa</b><input id="cl_ht" placeholder="Vazifa nomi" maxlength="100"><textarea id="cl_hx" rows="3" placeholder="Batafsil (ixtiyoriy)"></textarea><select id="cl_hh"><option value="6">Muddat: 6 soat</option><option value="12">12 soat</option><option value="24" selected>24 soat</option><option value="48">48 soat</option><option value="72">3 kun</option><option value="168">7 kun</option></select><button class="pri" onclick="CLS.hwCreate()">Vazifa berish</button><small>Muddatdan oldin eslatma va tugagach xulosa avtomatik ketadi.</small></div>';
  if(!d.hw.length) return h+'<div class="clEmpty"><small>Hali vazifa yo‘q.</small></div>';
  return h+d.hw.map(x=>'<button class="clCard" onclick="CLS.hwOpen('+x.id+')"><b>'+E(x.title)+'</b><small>⏰ '+E(x.due_text)+' • ✅ '+x.done+'/'+x.total+(x.finalized?' • yopilgan':'')+'</small><span>›</span></button>').join('');
}
async function tHwOpen(id){
  ST.hw=id; ST.view='hw'; loading(); const d=await G('/api/class/hw?hw='+id); if(!d.ok){ err(d); return tOpen(ST.cid,'hw'); }
  const L={done:'✅',late:'⏰',miss:'❌'};
  let h='<button class="clGhost" onclick="CLS.tab(\'hw\')">‹ Vazifalar</button><h3 class="clH">'+E(d.hw.title)+'</h3><small class="clSub">⏰ '+E(d.due_text)+(d.hw.text&&d.hw.text!==d.hw.title?'<br>'+E(d.hw.text):'')+'</small>';
  h+='<div class="clRow"><button class="clGhost" onclick="CLS.hwNotify('+id+')">📨 Topshirmaganlar ota-onasiga</button><button class="clGhost danger" onclick="CLS.hwDel('+id+')">🗑</button></div>';
  h+=d.rows.map(r=>'<div class="clStu"><div class="clRowS"><div class="clGrow"><b>'+E(r.name)+'</b><small>'+(r.status==='miss'?'topshirmagan':(r.kind==='reply'?'javob yuborgan':r.kind==='teacher'?'ustoz belgilagan':'tugma bosgan')+' • '+E(r.at))+'</small></div><div class="clHwB"><button class="clTog '+(r.status!=='miss'?'on':'')+'" onclick="CLS.hwMark('+id+','+r.rid+','+(r.status==='miss'?1:0)+')">'+L[r.status]+'</button><input class="clGr" id="gr_'+r.rid+'" value="'+(r.grade==null?'':r.grade)+'" placeholder="ball" inputmode="numeric" onchange="CLS.hwGrade('+id+','+r.rid+',this.value)"></div></div></div>').join('');
  put(h);
}

// ----- testlar (kodni qo'lda yozish shart emas: tayyor testlardan tanlanadi)
async function loadMsTests(){
  if(ST.msTests) return ST.msTests;
  const d=await G('/api/national/tests'); ST.msTests=(d&&d.tests)?d.tests.slice(0,30):[]; return ST.msTests;
}
function tTests(d){
  let h='<div class="clBox"><b>📝 Sinfga test bering</b><small>Tayyor testni tanlang yoki kodini yozing. Muddat tugagach kim qatnashgani ustoz va ota-onalarga xabar qilinadi.</small><div id="clPick" class="clPick"><span class="clHint">Testlar yuklanmoqda…</span></div>'
    +'<div class="clRow"><select id="cl_tk"><option value="ms">Milliy sertifikat</option><option value="simple">Oddiy test</option></select><input id="cl_tc" placeholder="Test kodi" maxlength="12" style="text-transform:uppercase"></div><select id="cl_th"><option value="24">Muddat: 24 soat</option><option value="48" selected>48 soat</option><option value="72">3 kun</option><option value="168">7 kun</option></select><button class="pri" onclick="CLS.testAssign()">Biriktirish</button></div>';
  if(!d.tests.length) h+='<div class="clEmpty"><small>Hali test biriktirilmagan.</small></div>';
  else h+=d.tests.map(t=>'<button class="clCard" onclick="CLS.testOpen('+t.id+')"><b>'+E(t.title||t.code)+'</b><small>'+E(t.code)+' • ⏰ '+E(t.due_text)+(t.finalized?' • yakunlangan':'')+'</small><span>›</span></button>').join('');
  setTimeout(async()=>{ const box=$('clPick'); if(!box) return; const L=await loadMsTests(); if(!$('clPick')) return;
    $('clPick').innerHTML=L.length?L.slice(0,8).map(t=>'<button class="clChip" onclick="CLS.pick(\''+E(t.code)+'\')">'+E(t.title||t.code)+'<small>'+E(t.subject||'')+'</small></button>').join(''):'<span class="clHint">Tayyor test topilmadi — kodni yozing.</span>'; },0);
  return h;
}
async function tTestOpen(id){
  ST.tid=id; ST.view='test'; loading(); const d=await G('/api/class/test?tid='+id); if(!d.ok){ err(d); return tOpen(ST.cid,'tests'); }
  const took=d.rows.filter(r=>r.took).length;
  let h='<button class="clGhost" onclick="CLS.tab(\'tests\')">‹ Testlar</button><h3 class="clH">'+E(d.test.title||d.test.code)+'</h3><small class="clSub">Kod: '+E(d.test.code)+' • ⏰ '+E(d.due_text)+' • qatnashdi '+took+'/'+d.rows.length+'</small>';
  h+='<div class="clRow">'+(d.test.finalized?'<button class="clGhost" onclick="CLS.testNotify('+id+')">📨 Ota-onalarga qayta yuborish</button>':'<button class="pri" onclick="CLS.testCheck('+id+')">🏁 Hozir yakunlash</button>')+'<button class="clGhost danger" onclick="CLS.testDel('+id+')">🗑</button></div>';
  h+=d.rows.map(r=>'<div class="clStu"><div class="clRowS"><div class="clGrow"><b>'+E(r.name)+'</b><small>'+(r.took?'✅ qatnashdi':(r.linked?'❌ qatnashmagan':'⚪ botga ulanmagan'))+'</small></div><div class="clPct '+col(r.pct)+'">'+pc(r.pct)+'</div></div></div>').join('');
  put(h);
}

// ----- reyting
function ratingRows(rows){
  return '<div class="clTbl"><div class="clTr h"><span>#</span><span>O‘quvchi</span><span>Umumiy</span><span>Dav.</span><span>Vaz.</span><span>Test</span></div>'+rows.map(r=>'<div class="clTr'+(r.me?' me':'')+'"><span>'+(r.rank<=3?['🥇','🥈','🥉'][r.rank-1]:r.rank)+'</span><span>'+E(r.name)+'</span><span class="'+col(r.comp)+'"><b>'+pc(r.comp)+'</b></span><span>'+pc(r.att)+'</span><span>'+pc(r.hw)+'</span><span>'+pc(r.test)+'</span></div>').join('')+'</div>';
}
function tRating(d){
  const r=d.rating;
  if(!r.rows||!r.rows.length) return '<div class="clEmpty"><b>Reyting hali yo‘q</b><small>Vazifa yoki test natijalari kelgach avtomatik tuziladi.</small></div>';
  return '<div class="clBox"><b>🏆 Sinf reytingi</b><small>Umumiy = davomat 30% + vazifa 30% + testlar 40% (mavjudlari bo‘yicha). Sinf o‘rtachasi: <b>'+pc(r.avg)+'</b></small></div>'+ratingRows(r.rows);
}

// ----- qo'shimcha: davomat, ota-onalarga xabar, sozlama
function tMore(d){
  const k=d.cls;
  let h='<details class="clBox clMore"'+(ST.moreOpen==='att'?' open':'')+'><summary>📋 Davomat</summary>'+attHtml(d)+'</details>';
  h+='<details class="clBox clMore"><summary>📩 Ota-onalarga xabar</summary><textarea id="cl_mt" rows="3" placeholder="Hamma ota-onalarga xabar..."></textarea><button class="clGhost" onclick="CLS.msgAll()">Yuborish</button></details>';
  h+='<details class="clBox clMore"><summary>⚙️ Sinf sozlamalari</summary><input id="cl_sn" value="'+E(k.name)+'" placeholder="Sinf nomi"><input id="cl_ss" value="'+E(k.subject||'')+'" placeholder="Fan"><label class="clLb">Ota-onaga xabar yuborish</label><select id="cl_sm"><option value="auto"'+(k.notify_mode==='auto'?' selected':'')+'>Avtomatik (darhol)</option><option value="approve"'+(k.notify_mode==='approve'?' selected':'')+'>Ustoz tasdiqlagach</option></select><label class="clLb">Ota-onaga ko‘rinadigan reyting</label><select id="cl_sr"><option value="short"'+(k.rating_names==='short'?' selected':'')+'>Qisqa ism (Aziz K.)</option><option value="full"'+(k.rating_names==='full'?' selected':'')+'>To‘liq ism</option></select><input type="hidden" id="cl_sf" value="'+(k.fee_day||0)+'"><button class="pri" onclick="CLS.saveSet()">💾 Saqlash</button>'
    +(k.group?'<small>💬 Telegram guruh ulangan: '+E(k.group_title||'guruh')+'</small><button class="clGhost danger" onclick="CLS.groupOff()">Guruhni uzish</button>':'<small>💬 Telegram guruhga ulash (ixtiyoriy): botni guruhga qo‘shing va guruhda /guruh_ulash yozing.</small>')+'</details>';
  if(k.is_owner) h+='<button class="clGhost danger wide" onclick="CLS.delClass()">🗑 Sinfni o‘chirish</button>';
  return h;
}

// ===================================================== OTA-ONA
function loginCard(){
  return '<div class="clLogin"><input id="cl_lg" placeholder="Login (masalan: ota12345)" autocapitalize="off" autocomplete="username"><input id="cl_pw" type="password" placeholder="Parol" autocomplete="current-password"><button class="pri" onclick="CLS.login()">Kirish</button></div>';
}
async function pList(){
  ST.view='pList'; loading(); const d=await G('/api/parent/me'); if(!d.ok){ put('<div class="result">❌ '+E(d.error)+'</div>'+parentEntry()); return; }
  let h='<h3 class="clH">👪 Farzandlarim</h3>';
  if(ST.me&&ST.me.teacher) h+='<button class="clGhost" onclick="CLS.list()">‹ Ustoz paneli</button>';
  h+=d.children.map(c=>'<button class="clCard big" onclick="CLS.child('+c.rid+')"><b>'+E(c.name)+'</b><small>'+E(c.class_name)+' • '+E(c.verdict)+(c.rank?' • reyting '+c.rank+'/'+c.n:'')+'</small><div class="clPct '+col(c.comp)+'">'+pc(c.comp)+'</div></button>').join('');
  h+='<details class="clBox"><summary><b>➕ Boshqa farzand qo‘shish</b></summary><p class="clHint">Ustoz yuborgan havolani oching yoki login/parol kiriting.</p>'+loginCard()+'</details><button class="clGhost danger" onclick="CLS.logout()">🚪 Hisobdan chiqish</button>';
  put(h);
}
async function pChild(rid){
  ST.rid=rid; ST.view='child'; loading(); const d=await G('/api/parent/child?rid='+rid); if(!d.ok){ err(d); return pList(); }
  const s=d.stats||{};
  let h='<button class="clGhost" onclick="CLS.pList()">‹ Farzandlarim</button><div class="clHero"><div><b>'+E(d.name)+'</b><small>'+E(d.class_name)+(d.subject?' • '+E(d.subject):'')+'</small><span class="clVd">'+E(d.verdict)+'</span></div><div class="clPct big '+col(s.comp)+'">'+pc(s.comp)+'</div></div>';
  if(d.rank) h+='<div class="word">🏆 Sinf reytingida <b>'+d.rank+'-o‘rin</b> ('+d.n+' o‘quvchidan). Sinf o‘rtachasi: <b>'+pc(d.class_avg)+'</b></div>';
  const M=[['Davomat',s.att,d.class_avg_att,'Keldi '+(s.present||0)+' • kechikdi '+(s.late||0)+' • kelmadi '+(s.absent||0)],['Vazifa',s.hw,d.class_avg_hw,''],['Testlar',s.test,d.class_avg_test,'']];
  h+='<div class="clBox">'+M.map(m=>'<div class="clMeter"><div><b>'+m[0]+'</b><span class="'+col(m[1])+'">'+pc(m[1])+'</span></div>'+bar(m[1])+'<small>Sinf o‘rtachasi: '+pc(m[2])+(m[3]?' • '+m[3]:'')+'</small></div>').join('')+(s.grade!=null?'<small>Vazifalar bo‘yicha o‘rtacha ball: <b>'+s.grade+'</b></small>':'')+'</div>';
  if(d.weeks&&d.weeks.some(w=>w.n)) h+='<div class="clBox"><b>📅 Davomat — so‘nggi 4 hafta</b><div class="clWeeks">'+d.weeks.map((w,i)=>'<div><div class="clWb"><i class="'+col(w.pct)+'" style="height:'+(w.pct==null?4:Math.max(6,w.pct))+'%"></i></div><small>'+(w.pct==null?'—':w.pct+'%')+'</small><small>'+(i===3?'bu hafta':(3-i)+' hafta oldin')+'</small></div>').join('')+'</div></div>';
  if(d.activity) h+='<div class="word">🎮 Bot mashqlari (7 kun): <b>'+d.activity.points+' ball</b>, '+d.activity.days+' kun faol</div>';
  if(!d.linked) h+='<div class="word">ℹ️ Farzandingiz botga hali ulanmagan — test natijalari ko‘rinishi uchun ustoz bergan havola orqali botga kirsin.</div>';
  h+='<div class="clBox"><b>📋 Davomat tarixi</b>'+(d.att.length?d.att.map(a=>'<div class="clLine"><span>'+E(a.date)+' • '+E(a.title)+'</span><span class="clSt '+a.status+'">'+E(a.status_uz)+'</span></div>'+((a.status==='a'||a.status==='l')?(a.note?'<small class="clNote">💬 Sizning izohingiz: «'+E(a.note)+'»</small>':'<button class="clLink" onclick="CLS.excuse('+a.sid+')">Sabab yozish</button>'):'')).join(''):'<small>Hali davomat yo‘q.</small>')+'</div>';
  const HL={done:'✅ topshirgan',late:'⏰ kech topshirgan',miss:'❌ topshirmagan',open:'⏳ muddat bor'};
  h+='<div class="clBox"><b>📚 Vazifalar</b>'+(d.hw.length?d.hw.map(x=>'<div class="clLine"><span>'+E(x.title)+'<small>⏰ '+E(x.due)+'</small></span><span class="clSt '+x.status+'">'+HL[x.status]+(x.grade!=null?' • '+x.grade:'')+'</span></div>').join(''):'<small>Hali vazifa yo‘q.</small>')+'</div>';
  const TL={took:'✅ qatnashdi',miss:'❌ qatnashmagan',open:'⏳ muddat bor'};
  h+='<div class="clBox"><b>📝 Testlar</b>'+(d.tests.length?d.tests.map(x=>'<div class="clLine"><span>'+E(x.title)+'<small>⏰ '+E(x.due)+'</small></span><span class="clSt '+x.status+'">'+TL[x.status]+(x.pct!=null?' • '+x.pct+'%':'')+'</span></div>').join(''):'<small>Hali test yo‘q.</small>')+'</div>';
  h+='<div class="clBox"><b>🏆 Sinf reytingi</b><small>Boshqa o‘quvchilar ismi qisqartirib ko‘rsatiladi.</small></div>'+ratingRows(d.rating);
  put(h);
}

// ===================================================== amallar
const C=window.CLS={
  copy, share,
  list:()=>{ ST.main='classes'; return tHome(); }, toParent:()=>pList(), pList:()=>pList(), child:id=>pChild(id),
  main:m=>{ ST.main=m; tHome(); },
  newClass:()=>{ const b=$('clNew'); if(b){ b.classList.toggle('hidden'); const i=$('cl_name'); if(i&&!b.classList.contains('hidden')) i.focus(); } },
  open:id=>{ ST.open=null; ST.moreOpen=null; tOpen(id,'students'); },
  goHw:async(cid,id)=>{ ST.cid=cid; await tOpen(cid,'hw'); tHwOpen(id); },
  goTest:async(cid,id)=>{ ST.cid=cid; await tOpen(cid,'tests'); tTestOpen(id); },
  tab:t=>{ ST.tab=t; ST.open=null; tOpen(ST.cid,t); },
  toggle:id=>{ ST.open=(ST.open===id?null:id); tRender(); },
  pick:code=>{ const i=$('cl_tc'), k=$('cl_tk'); if(i) i.value=code; if(k) k.value='ms'; notify('Tanlandi: '+code); },
  async cfgSave(){
    const en=$('cf_en')&&$('cf_en').checked;
    if(!en&&!(await ask('Ota-ona va o‘quvchilarga xabar yuborish to‘xtatiladi (xabarlar navbatda saqlanadi). Davom etasizmi?'))) return;
    const r=await P('/api/class/admin/cfg',{enabled:en,from:+V('cf_from'),to:+V('cf_to'),weekly_day:+V('cf_wd'),weekly_hour:+V('cf_wh'),fee_hour:+V('cf_fh')});
    if(!r.ok) return err(r); notify('Saqlandi ✅'); const b=$('clAdminCfg'); if(b) b.innerHTML=adminCfgHtml(r);
  },
  async create(){ const r=await P('/api/class/create',{name:V('cl_name'),subject:V('cl_subj')}); if(!r.ok) return err(r); notify('Sinf yaratildi 🎉 Endi havolani yuboring'); tOpen(r.id,'students'); },
  async addOne(){ const t=V('cl_one'); if(!t) return; const r=await P('/api/class/roster/add',{id:ST.cid,text:t}); if(!r.ok) return err(r); notify(r.added?'Qo‘shildi':'Bu ism allaqachon bor'); tOpen(ST.cid,'students'); },
  async parentLink(rid){ const r=await P('/api/class/parent_link',{rid}); if(!r.ok) return err(r); const l=startLink(r.start); if(!l) return notify('Bot manzili topilmadi.'); copy(l); notify('Ota-ona havolasi nusxalandi. «'+r.name+'» ota-onasiga yuboring.'); },
  async parentLinks(){ const r=await P('/api/class/parent_links',{id:ST.cid}); if(!r.ok) return err(r); const txt=r.items.filter(i=>!i.connected).map(i=>i.name+': '+startLink(i.start)).join('\n'); if(!txt) return notify('Hamma ota-onalar ulangan 👍'); copy(txt); },
  async unlink(rid){ if(!(await ask('O‘quvchining Telegram ulanishi uzilsinmi?'))) return; const r=await P('/api/class/roster/unlink',{rid}); if(!r.ok) return err(r); tOpen(ST.cid,'students'); },
  async delR(rid){ if(!(await ask('O‘quvchi ro‘yxatdan o‘chirilsinmi? Ota-onasining ulanishi ham yopiladi.'))) return; const r=await P('/api/class/roster/del',{rid}); if(!r.ok) return err(r); ST.open=null; tOpen(ST.cid,'students'); },
  async msgOne(rid){ const t=window.prompt('Ota-onaga xabar matni:'); if(!t) return; const r=await P('/api/class/msg',{id:ST.cid,rid,text:t}); if(!r.ok) return err(r); notify(r.sent?'Yuborildi ✅':'Ota-onasi hali ulanmagan: «👪 Ota-ona havolasi» ni yuboring.'); },
  async msgAll(){ const t=V('cl_mt'); if(!t) return; const r=await P('/api/class/msg',{id:ST.cid,text:t}); if(!r.ok) return err(r); notify('Yuborildi: '+r.sent+' ta'+(r.no_parent.length?'\nOta-onasi ulanmagan: '+r.no_parent.length+' ta':'')); $('cl_mt').value=''; },
  async attStart(){ const r=await P('/api/class/att/start',{id:ST.cid,title:V('cl_at'),mode:V('cl_am'),minutes:V('cl_amin')}); if(!r.ok) return err(r); tSess(r.sid); },
  sess:id=>tSess(id),
  async mark(sid,rid,st){ const r=await P('/api/class/att/mark',{sid,rid,status:st}); if(!r.ok) return err(r); tSess(sid); },
  async attClose(sid){ if(!(await ask('Davomat yakunlansinmi? Belgilanmaganlar «kelmadi» bo‘ladi.'))) return; const r=await P('/api/class/att/close',{sid}); if(!r.ok) return err(r); tSess(sid); },
  async attNotify(sid){ const r=await P('/api/class/att/notify',{sid}); if(!r.ok) return err(r); notify('Yuborildi: '+r.sent+' ta'+(r.no_parent.length?'\nOta-onasi ulanmagan: '+r.no_parent.join(', '):'')); },
  async hwCreate(){ const r=await P('/api/class/hw/create',{id:ST.cid,title:V('cl_ht'),text:$('cl_hx').value,hours:V('cl_hh')}); if(!r.ok) return err(r); tHwOpen(r.id); },
  hwOpen:id=>tHwOpen(id),
  async hwMark(hw,rid,on){ const r=await P('/api/class/hw/mark',{hw,rid,on}); if(!r.ok) return err(r); tHwOpen(hw); },
  async hwGrade(hw,rid,g){ const r=await P('/api/class/hw/grade',{hw,rid,grade:g}); if(!r.ok) return err(r); tHwOpen(hw); },
  async hwNotify(hw){ const r=await P('/api/class/hw/notify',{hw}); if(!r.ok) return err(r); notify('Yuborildi: '+r.sent+' ta'+(r.no_parent.length?'\nOta-onasi ulanmagan: '+r.no_parent.join(', '):'')); },
  async hwDel(hw){ if(!(await ask('Vazifa o‘chirilsinmi?'))) return; const r=await P('/api/class/hw/delete',{hw}); if(!r.ok) return err(r); tOpen(ST.cid,'hw'); },
  async testAssign(){ const r=await P('/api/class/test/assign',{id:ST.cid,kind:V('cl_tk'),code:V('cl_tc'),hours:V('cl_th')}); if(!r.ok) return err(r); tTestOpen(r.id); },
  testOpen:id=>tTestOpen(id),
  async testCheck(tid){ if(!(await ask('Test hozir yakunlansinmi? Natija ustoz va ota-onalarga yuboriladi.'))) return; const r=await P('/api/class/test/check',{tid}); if(!r.ok) return err(r); tTestOpen(tid); },
  async testNotify(tid){ const r=await P('/api/class/test/notify',{tid}); if(!r.ok) return err(r); notify('Yuborildi: '+r.sent+' ta'+(r.no_parent.length?'\nOta-onasi ulanmagan: '+r.no_parent.join(', '):'')); },
  async testDel(tid){ if(!(await ask('Test sinfdan olib tashlansinmi?'))) return; const r=await P('/api/class/test/delete',{tid}); if(!r.ok) return err(r); tOpen(ST.cid,'tests'); },
  async saveSet(){ const r=await P('/api/class/update',{id:ST.cid,name:V('cl_sn'),subject:V('cl_ss'),notify_mode:V('cl_sm'),rating_names:V('cl_sr'),fee_day:V('cl_sf')}); if(!r.ok) return err(r); notify('Saqlandi ✅'); tOpen(ST.cid,'more'); },
  async groupOff(){ if(!(await ask('Guruh sinfdan uzilsinmi?'))) return; const r=await P('/api/class/group_unlink',{id:ST.cid}); if(!r.ok) return err(r); tOpen(ST.cid,'more'); },
  async delClass(){ if(!(await ask('Sinf butunlay o‘chirilsinmi? Ota-onalar ulanishi ham yopiladi.'))) return; const r=await P('/api/class/delete',{id:ST.cid}); if(!r.ok) return err(r); tHome(); },
  async login(){ const r=await P('/api/parent/login',{login:V('cl_lg'),password:V('cl_pw')}); if(!r.ok) return err(r); notify('Xush kelibsiz! Farzandingiz: '+r.name); if(window.ME){ ME.parent_mode=true; } const d=await G('/api/class/me'); ST.me=d; if(d.teacher||(window.ME&&ME.is_admin)) return pList(); const tb=$('teacherBody'); if(tb) tb.classList.add('hidden'); const h=$('clsH2'); if(h) h.textContent='👪 Ota-ona bo‘limi'; if(typeof clsBoot==='function') clsBoot(); pList(); },
  async logout(){ if(!(await ask('Ota-ona hisobidan chiqasizmi? Xabarlar kelishi to‘xtaydi.'))) return; const r=await P('/api/parent/logout',{}); if(!r.ok) return err(r); notify('Chiqdingiz.'); location.reload(); },
  async excuse(sid){ const n=window.prompt('Dars qoldirish sababi (ustozga yuboriladi):'); if(!n) return; const r=await P('/api/parent/excuse',{sid,rid:ST.rid,note:n}); if(!r.ok) return err(r); notify('Ustozga yuborildi ✅'); pChild(ST.rid); }
};
window.CLS_TEST={ratingRows,tStudents,tHw,tTests,tRating,tMore,loginCard,steps,createForm,_st:ST};
})();
