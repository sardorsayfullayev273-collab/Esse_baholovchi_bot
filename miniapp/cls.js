// v109: SINF NAZORATI — ustoz paneli ichida: sinflar, o'quvchilar, davomat, vazifa, test, reyting + OTA-ONA bo'limi (alohida login/parol).
// Ota-ona kirgach faqat shu bo'lim ko'rinadi (clsBoot: boshqa bo'limlar yopiladi; ruxsat serverda ham tekshiriladi).
(function(){
const E=s=>escapeHtml(String(s==null?'':s));
const ST={view:'list',cid:null,tab:'students',sid:null,hw:null,tid:null,open:null,data:null,me:null,rid:null,creds:null,msg:'',pLogin:false};
let LOCK=false;
const top=()=>$('clsTop');
async function G(path){ try{ const r=await apiFetch(apiUrl(path),{cache:'no-store'}); return await r.json(); }catch(e){ return {ok:false,error:'Server bilan bog‘lanishda xatolik.'}; } }
const P=(path,b)=>tchPost(path,b);
const V=id=>{ const x=$(id); return x?x.value.trim():''; };
const pc=v=>v==null?'—':v+'%';
const col=v=>v==null?'':v>=70?'ok':v>=50?'mid':'bad';
const bar=(v,c)=>'<div class="clBar"><i class="'+(c||col(v))+'" style="width:'+(v==null?0:Math.max(3,Math.min(100,v)))+'%"></i></div>';
const SL={p:'✅ Keldi',l:'⏰ Kechikdi',a:'❌ Kelmadi',e:'📝 Sababli'};
function ask(m){ return new Promise(res=>{ if(window.tg&&tg.showConfirm){ try{ tg.showConfirm(m,res); return; }catch(e){} } res(window.confirm(m)); }); }
function copy(t){ try{ if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(t); notify('Nusxalandi ✅'); return; } }catch(e){}
  const a=document.createElement('textarea'); a.value=t; document.body.appendChild(a); a.select(); try{ document.execCommand('copy'); notify('Nusxalandi ✅'); }catch(e){ notify(t); } a.remove(); }
function put(h){ const t=top(); if(t) t.innerHTML=h; }
const loading=()=>put('<div class="word">⏳ Yuklanmoqda...</div>');
function err(r){ notify((r&&r.error)||'Xatolik. Qayta urinib ko‘ring.'); }
const botLink=cid=>(ME&&ME.bot_username)?('https://t.me/'+ME.bot_username+'?start=c_'+cid):'';

// ===================================================== kirish nuqtalari
window.clsEnter=async function(){
  if(!top()) return false;
  const d=await G('/api/class/me'); ST.me=d; const h=$('clsH2'), tb=$('teacherBody');
  if(d.ok&&d.parent&&!d.teacher&&!(window.ME&&ME.is_admin)){
    if(tb) tb.classList.add('hidden'); if(h){ h.style.display=''; h.textContent='👪 Ota-ona bo‘limi'; } ST.view='pList'; await pList(); return true;
  }
  if(tb) tb.classList.remove('hidden'); if(h) h.textContent='🧑‍🏫 Ustoz paneli';
  if(d.ok&&d.teacher){ if(h) h.style.display='none'; ST.view='list'; await tList(); return true; }
  if(h) h.style.display=''; put(loginCard(false));
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

// ===================================================== USTOZ: sinflar ro'yxati
const IC={
  chev:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8a978f" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>',
  back:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 6l-6 6 6 6"/></svg>',
  plus:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>'};
function showTop(){ const tb=$('teacherBody'); if(tb) tb.classList.add('hidden'); const t=top(); if(t) t.classList.remove('hidden'); }
const ini=n=>String(n||'?').trim().split(/\s+/).slice(0,2).map(w=>w[0]||'').join('').toUpperCase();
const plain=(t,sub,fn)=>'<button class="pzLine" onclick="'+fn+'"><span><b>'+t+'</b><small>'+sub+'</small></span>'+IC.chev+'</button>';
async function tList(){
  showTop(); loading();
  const [d,ov]=await Promise.all([G('/api/class/list'),G('/api/teacher/overview')]);
  if(!d.ok){ put('<div class="result">❌ '+E(d.error)+'</div>'); return; }
  const adm=!!(window.ME&&ME.is_admin), n=d.classes.length, stu=d.classes.reduce((a,k)=>a+(k.students||0),0);
  const pro=ov&&ov.ok?ov.pro:null, tests=ov&&ov.ok&&ov.totals?ov.totals.tests:0;
  let right='';
  if(pro&&pro.active) right='<span>'+(pro.admin?'admin':(pro.until?E(pro.until)+' gacha faol':'faol'))+'</span>';
  else if(pro) right='<button class="pzProBtn" onclick="payByCard(\'teacher\',\'pro\')">Yoqish'+(pro.price?' · '+uzsFmt(pro.price)+' so‘m':'')+'</button>';
  let h='<div class="pzEyebrow">USTOZ PANELI</div><div class="pzTitle">Sinflaringiz</div>'
   +'<div class="pzHero"><div class="pzHeroTop"><b>USTOZ PRO</b>'+right+'</div><div class="pzStats"><div><i>'+n+'</i><small>sinf</small></div><div><i>'+stu+'</i><small>o‘quvchi</small></div><div><i>'+tests+'</i><small>test</small></div></div></div>';
  if(!n) h+='<div class="clEmpty"><b>Hali sinf yo‘q</b><small>Sinf yarating, o‘quvchilar ro‘yxatini kiriting va botni guruhga qo‘shing.</small></div>';
  h+=d.classes.map(k=>{ const pct=k.students?Math.round(k.linked*100/k.students):0;
    return '<button class="pzCls" onclick="CLS.open('+k.id+')"><div class="pzClsTop"><div><div class="pzClsName">'+E(k.name)+'</div><small>'+(k.subject?E(k.subject)+' · ':'')+k.students+' o‘quvchi'+(k.group?' · guruh ulangan':'')+'</small></div>'+IC.chev+'</div><div class="pzMeta"><span>Botga ulangan</span><span><b>'+k.linked+'</b> / '+k.students+'</span></div><div class="pzBar"><i style="width:'+pct+'%"></i></div></button>'; }).join('');
  if(d.can_create){
    h+='<button class="pzDash" onclick="CLS.newToggle()">'+IC.plus+'Yangi sinf</button>'
     +'<div id="clNew" class="clBox'+(n?' hidden':'')+'"><input id="cl_name" placeholder="Sinf nomi (masalan: 11-A)" maxlength="60"><input id="cl_subj" placeholder="Fan (ixtiyoriy)" maxlength="40"><button class="pri" onclick="CLS.create()">Sinf yaratish</button></div>';
  }
  h+='<div class="pzList">'+plain('Testlar tahlili','Natijalar, PDF hisobot','CLS.analysis()')+plain('Sozlamalar','Ota-ona kirishi'+(adm?', xabar vaqti':''),'CLS.setToggle()')+'</div>'
   +'<div id="clSet" class="hidden">'+loginCard(true)+(adm?'<div id="clAdminCfg" class="clBox"><b>Ota-onaga xabar vaqti</b> <small>(admin)</small><div class="word">⏳ Yuklanmoqda...</div></div>':(ST.me&&ST.me.send_window?'<p class="clFoot">Ota-onalarga xabar: <b>'+E(ST.me.send_window)+'</b></p>':''))
   +(ST.me&&ST.me.parent?'<button class="clGhost" onclick="CLS.toParent()">Farzandlarim (ota-ona sifatida)</button>':'')+'</div>';
  put(h);
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
   +'<div class="word">Oynadan tashqarida chiqadigan xabarlar oyna ochilguncha navbatda turadi. Saqlaganingizda navbatdagi xabarlar ham yangi oynaga qarab qayta rejalanadi. Vaqt — Toshkent.</div>'
   +'<button class="pri" onclick="CLS.cfgSave()">💾 Saqlash</button>';
}
async function adminCfgLoad(){
  const d=await G('/api/class/admin/cfg'), b=$('clAdminCfg'); if(!b) return;
  b.innerHTML=d.ok?adminCfgHtml(d):'<div class="word">❌ '+E(d.error||'Xatolik')+'</div>';
}
async function tOpen(cid,tab){
  ST.cid=cid; ST.tab=tab||ST.tab||'students'; ST.view='class'; loading();
  const d=await G('/api/class/detail?id='+cid); if(!d.ok){ err(d); return tList(); } ST.data=d; tRender();
}
function tabsHtml(){
  const T=[['students','O‘quvchilar'],['att','Davomat'],['hw','Vazifa'],['tests','Test']];
  const prim=T.some(t=>t[0]===ST.tab);
  return '<div class="pzSeg">'+T.map(t=>'<button class="'+(ST.tab===t[0]?'on':'')+'" onclick="CLS.tab(\''+t[0]+'\')">'+t[1]+'</button>').join('')+'</div>'
   +'<div class="pzSec"><button class="'+(ST.tab==='rating'?'on':'')+'" onclick="CLS.tab(\'rating\')">Reyting</button><button class="'+(ST.tab==='set'?'on':'')+'" onclick="CLS.tab(\'set\')">Sozlama</button></div>';
}
function tRender(){
  const d=ST.data, k=d.cls; ST.view='class';
  let h='<button class="pzBack" onclick="CLS.list()">'+IC.back+'Sinflar</button><div class="pzTitle">'+E(k.name)+'</div><div class="pzSub">'+(k.subject?E(k.subject)+' · ':'')+k.students+' o‘quvchi · '+(k.group?E(k.group_title||'guruh ulangan'):'guruh ulanmagan')+'</div>'+tabsHtml();
  h+=({students:tStudents,att:tAtt,hw:tHw,tests:tTests,rating:tRating,set:tSet}[ST.tab]||tStudents)(d);
  put(h);
}

// ----- o'quvchilar
function tStudents(d){
  const empty=!d.roster.length;
  let h='<button class="pzGold" onclick="CLS.tab(\'att\')">Davomatni boshlash</button>'
   +'<div class="pzActs"><button onclick="CLS.rosToggle()">Qo‘shish</button><button onclick="CLS.shareLink()">Havola</button><button onclick="CLS.credsAll()">Login/parol</button></div>'
   +'<div id="clRos" class="clBox'+(empty?'':' hidden')+'"><small>Har qatorga bittadan: <i>Ism Familiya; telefon; ota-ona telefoni</i>. Excel ustunlarini nusxalab qo‘yish mumkin.</small><textarea id="cl_ros" rows="5" placeholder="Aziz Karimov; 901112233; 901234567\nDilnoza Said; ; 935556677"></textarea><button class="pri" onclick="CLS.addRos()">Qo‘shish</button></div>';
  if(ST.creds) h+='<div class="clBox">'+credsBox(ST.creds)+'</div>';
  if(empty) return h;
  h+='<div class="pzStuList">'+d.roster.map(r=>{
    const s=r.stats||{}, open=ST.open===r.id;
    const st=(r.linked?'Ulangan':'Ulanmagan')+' · '+(r.parent_linked?'ota-ona kirgan':(r.login?'login bor':'login yo‘q'));
    let x='<div class="pzRow" onclick="CLS.toggle('+r.id+')"><i class="pzAv">'+E(ini(r.full_name))+'</i><div><b>'+E(r.full_name)+'</b><small>'+st+'</small></div><span class="pzPct '+col(s.comp)+'">'+pc(s.comp)+'</span></div>';
    if(open){
      x+='<div class="clAct"><small>Davomat '+pc(s.att)+' • Vazifa '+pc(s.hw)+' • Test '+pc(s.test)+(s.grade!=null?' • O‘rtacha ball '+s.grade:'')+'<br>Tel: '+E(r.phone||'—')+' • ota-ona: '+E(r.parent_phone||'—')+(r.login?'<br>Login: <b>'+E(r.login)+'</b>':'')+'</small>'
        +'<div class="clRow"><button class="clGhost" onclick="CLS.cred('+r.id+')">Login/parol</button>'+(r.linked?'<button class="clGhost" onclick="CLS.unlink('+r.id+')">Uzish</button>':'')+'<button class="clGhost" onclick="CLS.msgOne('+r.id+')">Ota-onaga xabar</button></div>'
        +'<div class="clRow"><input id="cl_en" value="'+E(r.full_name)+'" placeholder="Ism"><input id="cl_ep" value="'+E(r.parent_phone)+'" placeholder="Ota-ona tel" inputmode="tel"></div><div class="clRow"><input id="cl_ef" value="'+(r.fee||'')+'" placeholder="Oylik to‘lov (so‘m)" inputmode="numeric">'+(r.fee>0?'<button class="clGhost" onclick="CLS.pay('+r.id+','+(r.paid?0:1)+')">'+(r.paid?'To‘langan (bekor)':'To‘landi deb belgilash')+'</button>':'')+'</div>'
        +'<div class="clRow"><button class="clGhost" onclick="CLS.saveR('+r.id+')">Saqlash</button><button class="clGhost danger" onclick="CLS.delR('+r.id+')">O‘chirish</button></div></div>';
    }
    return '<div class="pzStu">'+x+'</div>';
  }).join('')+'</div>';
  return h;
}
function credsBox(items){
  const txt=items.map(i=>i.name+'\nLogin: '+i.login+'\nParol: '+(i.password||'(avval yaratilgan — 🔑 tugmasi bilan yangilang)')).join('\n\n');
  window._clTxt=txt;
  return '<small>Parol faqat shu paytda ko‘rinadi — ota-onaga yuboring.</small><div class="clCreds"><pre>'+E(txt)+'</pre><button class="clGhost" onclick="copy(window._clTxt)">📋 Hammasini nusxalash</button></div>';
}
window.copy=window.copy||copy;

// ----- davomat
function tAtt(d){
  let h='<div class="clBox"><b>🕘 Yangi davomat</b><input id="cl_at" placeholder="Dars nomi (ixtiyoriy)" maxlength="60"><div class="clRow"><select id="cl_am"><option value="code">Kod bilan (ishonchli)</option><option value="button">Tugma bilan (kodsiz)</option></select><select id="cl_amin"><option value="10">10 daq</option><option value="20" selected>20 daq</option><option value="30">30 daq</option><option value="60">60 daq</option></select></div><button class="pri" onclick="CLS.attStart()">Davomatni ochish</button><small>Kod rejimida o‘quvchi darsda e’lon qilingan 4 xonali kodni /keldim KOD bilan yuboradi. Vaqt tugagach belgilanmaganlar «kelmadi» bo‘ladi va ota-onalarga xabar ketadi.</small></div>';
  if(!d.sessions.length) return h+'<div class="word">Hali davomat o‘tkazilmagan.</div>';
  return h+d.sessions.map(s=>'<button class="clCard" onclick="CLS.sess('+s.id+')"><b>'+E(s.title)+'</b><small>'+E(s.when)+' • '+(s.open?'🟢 ochiq':(s.closed?'yopilgan':'🟠 vaqti o‘tdi'))+'</small><span>›</span></button>').join('');
}
async function tSess(sid){
  ST.sid=sid; ST.view='sess'; loading(); const d=await G('/api/class/att?sid='+sid); if(!d.ok){ err(d); return tOpen(ST.cid,'att'); }
  const s=d.session, op=!s.closed;
  let h='<button class="clGhost" onclick="CLS.tab(\'att\')">‹ Davomatlar</button><h3 class="clH">'+E(s.title)+'</h3>';
  if(op){ h+='<div class="clBox">'+(s.code?'🔑 Kod: <b class="clCode">'+E(s.code)+'</b><small>Darsda og‘zaki e’lon qiling.</small>':'Tugma rejimi (kodsiz)')+'<div class="clRow"><button class="clGhost" onclick="CLS.sess('+sid+')">🔄 Yangilash</button><button class="pri" onclick="CLS.attClose('+sid+')">🏁 Yakunlash</button></div></div>'; }
  else h+='<div class="clBox"><b>Yakunlangan.</b><div class="clRow"><button class="clGhost" onclick="CLS.attNotify('+sid+')">📨 Kelmaganlar ota-onasiga xabar</button></div></div>';
  const cnt={}; d.rows.forEach(r=>{ cnt[r.status||'-']=(cnt[r.status||'-']||0)+1; });
  h+='<small class="clSub">✅ '+(cnt.p||0)+' • ⏰ '+(cnt.l||0)+' • ❌ '+(cnt.a||0)+' • 📝 '+(cnt.e||0)+' • belgilanmagan '+(cnt['-']||0)+'</small>';
  h+=d.rows.map(r=>'<div class="clStu"><div class="clRowS"><div><b>'+E(r.name)+'</b>'+(r.note?'<small>💬 «'+E(r.note)+'»</small>':'')+'</div></div><div class="clSeg">'+['p','l','a','e'].map(c=>'<button class="'+(r.status===c?'on '+c:'')+'" onclick="CLS.mark('+sid+','+r.rid+',\''+c+'\')">'+SL[c]+'</button>').join('')+'</div></div>').join('');
  put(h);
}

// ----- vazifa
function tHw(d){
  let h='<div class="clBox"><b>📚 Yangi vazifa</b><input id="cl_ht" placeholder="Vazifa nomi" maxlength="100"><textarea id="cl_hx" rows="3" placeholder="Batafsil (ixtiyoriy)"></textarea><select id="cl_hh"><option value="6">Muddat: 6 soat</option><option value="12">12 soat</option><option value="24" selected>24 soat</option><option value="48">48 soat</option><option value="72">3 kun</option><option value="168">7 kun</option></select><button class="pri" onclick="CLS.hwCreate()">Vazifa berish</button><small>Guruhga ham xabar yuboriladi. Guruhda tezroq: /vazifa ertaga 18:00 matn</small></div>';
  if(!d.hw.length) return h+'<div class="word">Hali vazifa yo‘q.</div>';
  return h+d.hw.map(x=>'<button class="clCard" onclick="CLS.hwOpen('+x.id+')"><b>'+E(x.title)+'</b><small>⏰ '+E(x.due_text)+' • ✅ '+x.done+'/'+x.total+(x.finalized?' • yopilgan':'')+'</small><span>›</span></button>').join('');
}
async function tHwOpen(id){
  ST.hw=id; ST.view='hw'; loading(); const d=await G('/api/class/hw?hw='+id); if(!d.ok){ err(d); return tOpen(ST.cid,'hw'); }
  const L={done:'✅',late:'⏰',miss:'❌'};
  let h='<button class="clGhost" onclick="CLS.tab(\'hw\')">‹ Vazifalar</button><h3 class="clH">'+E(d.hw.title)+'</h3><small class="clSub">⏰ '+E(d.due_text)+(d.hw.text&&d.hw.text!==d.hw.title?'<br>'+E(d.hw.text):'')+'</small>';
  h+='<div class="clRow"><button class="clGhost" onclick="CLS.hwNotify('+id+')">📨 Topshirmaganlar ota-onasiga</button><button class="clGhost danger" onclick="CLS.hwDel('+id+')">🗑</button></div>';
  h+=d.rows.map(r=>'<div class="clStu"><div class="clRowS"><div><b>'+E(r.name)+'</b><small>'+(r.status==='miss'?'topshirmagan':(r.kind==='reply'?'javob yuborgan':r.kind==='teacher'?'ustoz belgilagan':'tugma bosgan')+' • '+E(r.at))+'</small></div><div class="clHwB"><button class="clTog '+(r.status!=='miss'?'on':'')+'" onclick="CLS.hwMark('+id+','+r.rid+','+(r.status==='miss'?1:0)+')">'+L[r.status]+'</button><input class="clGr" id="gr_'+r.rid+'" value="'+(r.grade==null?'':r.grade)+'" placeholder="ball" inputmode="numeric" onchange="CLS.hwGrade('+id+','+r.rid+',this.value)"></div></div></div>').join('');
  put(h);
}

// ----- testlar
function tTests(d){
  let h='<div class="clBox"><b>📝 Testni sinfga biriktirish</b><div class="clRow"><select id="cl_tk"><option value="simple">Oddiy test</option><option value="ms">Milliy sertifikat</option></select><input id="cl_tc" placeholder="Test kodi" maxlength="12" style="text-transform:uppercase"></div><select id="cl_th"><option value="24">Muddat: 24 soat</option><option value="48" selected>48 soat</option><option value="72">3 kun</option><option value="168">7 kun</option></select><button class="pri" onclick="CLS.testAssign()">Biriktirish</button><small>Muddat tugagach kim qatnashgani/qatnashmagani ustoz va ota-onalarga xabar qilinadi.</small></div>';
  if(!d.tests.length) return h+'<div class="word">Hali test biriktirilmagan.</div>';
  return h+d.tests.map(t=>'<button class="clCard" onclick="CLS.testOpen('+t.id+')"><b>'+E(t.title||t.code)+'</b><small>'+E(t.code)+' • ⏰ '+E(t.due_text)+(t.finalized?' • yakunlangan':'')+'</small><span>›</span></button>').join('');
}
async function tTestOpen(id){
  ST.tid=id; ST.view='test'; loading(); const d=await G('/api/class/test?tid='+id); if(!d.ok){ err(d); return tOpen(ST.cid,'tests'); }
  const took=d.rows.filter(r=>r.took).length;
  let h='<button class="clGhost" onclick="CLS.tab(\'tests\')">‹ Testlar</button><h3 class="clH">'+E(d.test.title||d.test.code)+'</h3><small class="clSub">Kod: '+E(d.test.code)+' • ⏰ '+E(d.due_text)+' • qatnashdi '+took+'/'+d.rows.length+'</small>';
  h+='<div class="clRow">'+(d.test.finalized?'<button class="clGhost" onclick="CLS.testNotify('+id+')">📨 Ota-onalarga qayta yuborish</button>':'<button class="pri" onclick="CLS.testCheck('+id+')">🏁 Hozir yakunlash</button>')+'<button class="clGhost danger" onclick="CLS.testDel('+id+')">🗑</button></div>';
  h+=d.rows.map(r=>'<div class="clStu"><div class="clRowS"><div><b>'+E(r.name)+'</b><small>'+(r.took?'✅ qatnashdi':(r.linked?'❌ qatnashmagan':'⚪ botga ulanmagan'))+'</small></div><div class="clPct '+col(r.pct)+'">'+pc(r.pct)+'</div></div></div>').join('');
  put(h);
}

// ----- reyting / sozlama
function ratingRows(rows){
  return '<div class="clTbl"><div class="clTr h"><span>#</span><span>O‘quvchi</span><span>Umumiy</span><span>Dav.</span><span>Vaz.</span><span>Test</span></div>'+rows.map(r=>'<div class="clTr'+(r.me?' me':'')+'"><span>'+r.rank+'</span><span>'+E(r.name)+'</span><span class="'+col(r.comp)+'"><b>'+pc(r.comp)+'</b></span><span>'+pc(r.att)+'</span><span>'+pc(r.hw)+'</span><span>'+pc(r.test)+'</span></div>').join('')+'</div>';
}
function tRating(d){
  const r=d.rating;
  return '<div class="clBox"><b>🏆 Sinf reytingi</b><small>Umumiy = davomat 30% + vazifa 30% + testlar 40%. Sinf o‘rtachasi: <b>'+pc(r.avg)+'</b> (davomat '+pc(r.avg_att)+', vazifa '+pc(r.avg_hw)+', test '+pc(r.avg_test)+')</small></div>'+ratingRows(r.rows);
}
function tSet(d){
  const k=d.cls;
  let h='<div class="clBox"><b>⚙️ Sinf sozlamalari</b><input id="cl_sn" value="'+E(k.name)+'" placeholder="Sinf nomi"><input id="cl_ss" value="'+E(k.subject||'')+'" placeholder="Fan"><label class="clLb">Ota-onaga xabar yuborish</label><select id="cl_sm"><option value="auto"'+(k.notify_mode==='auto'?' selected':'')+'>Avtomatik (darhol)</option><option value="approve"'+(k.notify_mode==='approve'?' selected':'')+'>Ustoz tasdiqlagach</option></select><label class="clLb">Ota-onaga ko‘rinadigan reyting</label><select id="cl_sr"><option value="short"'+(k.rating_names==='short'?' selected':'')+'>Qisqa ism (Aziz K.)</option><option value="full"'+(k.rating_names==='full'?' selected':'')+'>To‘liq ism</option></select><label class="clLb">To‘lov eslatmasi (oyning qaysi kuni, 0 — o‘chiq)</label><input id="cl_sf" value="'+(k.fee_day||0)+'" inputmode="numeric"><button class="pri" onclick="CLS.saveSet()">💾 Saqlash</button><small>Ota-onalarga xabarlar tungi 21:00–07:00 oralig‘ida yuborilmaydi — ertalabgacha kutadi.</small></div>';
  h+='<div class="clBox"><b>💬 Telegram guruh</b>'+(k.group?'<small>Ulangan: '+E(k.group_title||'guruh')+'</small><button class="clGhost danger" onclick="CLS.groupOff()">Guruhni uzish</button>':'<small>Botni guruhga qo‘shing (ADMIN qilsangiz yaxshi), so‘ng guruhda <b>/guruh_ulash</b> yozing.</small>')+'</div>';
  h+='<div class="clBox"><b>📩 Ota-onalarga xabar</b><textarea id="cl_mt" rows="3" placeholder="Hamma ota-onalarga xabar..."></textarea><button class="clGhost" onclick="CLS.msgAll()">Yuborish</button></div>';
  if(k.is_owner){
    h+='<div class="clBox"><b>🧑‍🏫 Yordamchi ustozlar</b><small>Telegram ID bilan qo‘shiladi (u botga /start bosgan bo‘lsin). Yordamchi davomat, vazifa va test bilan ishlay oladi.</small>'+d.assistants.map(a=>'<div class="clRow"><span>ID '+a+'</span><button class="clGhost danger" onclick="CLS.assist('+a+',1)">Olib tashlash</button></div>').join('')+'<div class="clRow"><input id="cl_as" placeholder="Telegram ID" inputmode="numeric"><button class="clGhost" onclick="CLS.assist(0,0)">Qo‘shish</button></div></div>';
    h+='<button class="clGhost danger" onclick="CLS.delClass()">🗑 Sinfni o‘chirish</button>';
  }
  return h;
}

// ===================================================== OTA-ONA
function loginCard(compact){
  return '<div class="clBox clLogin"><b>👪 Ota-ona kirishi</b><small>Ustoz bergan login va parolni kiriting.</small><input id="cl_lg" placeholder="Login (masalan: ota12345)" autocapitalize="off" autocomplete="username"><input id="cl_pw" type="password" placeholder="Parol" autocomplete="current-password"><button class="pri" onclick="CLS.login()">Kirish</button></div>';
}
async function pList(){
  ST.view='pList'; loading(); const d=await G('/api/parent/me'); if(!d.ok){ put('<div class="result">❌ '+E(d.error)+'</div>'+loginCard(false)); return; }
  let h='<h3 class="clH">👪 Farzandlarim</h3>';
  if(ST.me&&ST.me.teacher) h+='<button class="clGhost" onclick="CLS.list()">‹ Ustoz paneli</button>';
  h+=d.children.map(c=>'<button class="clCard big" onclick="CLS.child('+c.rid+')"><b>'+E(c.name)+'</b><small>'+E(c.class_name)+' • '+E(c.verdict)+(c.rank?' • reyting '+c.rank+'/'+c.n:'')+'</small><div class="clPct '+col(c.comp)+'">'+pc(c.comp)+'</div></button>').join('');
  h+='<details class="clBox"><summary><b>➕ Boshqa farzand qo‘shish</b></summary>'+loginCard(false)+'</details><button class="clGhost danger" onclick="CLS.logout()">🚪 Hisobdan chiqish</button>';
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
  if(d.fee>0) h+='<div class="word">💳 Joriy oy to‘lovi: '+(d.paid?'<b>to‘langan ✅</b>':'<b>to‘lanmagan</b>')+'</div>';
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
  copy, share:(l,t)=>{ if(typeof openShare==='function') openShare(l,t); else copy(l); },
  newToggle(){ const b=$('clNew'); if(b){ b.classList.toggle('hidden'); if(!b.classList.contains('hidden')) b.scrollIntoView({behavior:'smooth',block:'center'}); } },
  cfgOpen:()=>adminCfgLoad(),
  analysis(){ const t=top(), tb=$('teacherBody'); if(t) t.classList.add('hidden'); if(tb) tb.classList.remove('hidden'); if(typeof loadTeacherTests==='function') loadTeacherTests(); },
  rosToggle(){ const b=$('clRos'); if(b) b.classList.toggle('hidden'); },
  shareLink(){ const lk=botLink(ST.cid); if(!lk) return notify('Bot manzili topilmadi.'); C.share(lk,(ST.data&&ST.data.cls?ST.data.cls.name:'')+' sinfi: botda ismingizni tanlang'); },
  newToggle(){ const b=$('clNew'); if(b){ b.classList.toggle('hidden'); if(!b.classList.contains('hidden')) b.scrollIntoView({behavior:'smooth',block:'center'}); } },
  setToggle(){ const b=$('clSet'); if(!b) return; b.classList.toggle('hidden'); if(!b.classList.contains('hidden')){ if(window.ME&&ME.is_admin) adminCfgLoad(); b.scrollIntoView({behavior:'smooth',block:'start'}); } },
  list:()=>tList(), toParent:()=>pList(), pList:()=>pList(), child:id=>pChild(id), open:id=>tOpen(id,'students'),
  tab:t=>{ ST.tab=t; ST.open=null; ST.creds=null; tOpen(ST.cid,t); },
  toggle:id=>{ ST.open=(ST.open===id?null:id); tRender(); },
  async cfgSave(){
    const en=$('cf_en')&&$('cf_en').checked;
    if(!en&&!(await ask('Ota-ona va o‘quvchilarga xabar yuborish to‘xtatiladi (xabarlar navbatda saqlanadi). Davom etasizmi?'))) return;
    const r=await P('/api/class/admin/cfg',{enabled:en,from:+V('cf_from'),to:+V('cf_to'),weekly_day:+V('cf_wd'),weekly_hour:+V('cf_wh'),fee_hour:+V('cf_fh')});
    if(!r.ok) return err(r); notify('Saqlandi ✅'); const b=$('clAdminCfg'); if(b) b.innerHTML='<b>Ota-onaga xabar vaqti</b> <small>(admin)</small>'+adminCfgHtml(r);
  },
  async create(){ const r=await P('/api/class/create',{name:V('cl_name'),subject:V('cl_subj')}); if(!r.ok) return err(r); tOpen(r.id,'students'); },
  async addRos(){ const r=await P('/api/class/roster/add',{id:ST.cid,text:$('cl_ros').value}); if(!r.ok) return err(r); notify('Qo‘shildi: '+r.added+(r.skipped?' • takror: '+r.skipped:'')); tOpen(ST.cid,'students'); },
  async credsAll(){ const r=await P('/api/class/creds_all',{id:ST.cid}); if(!r.ok) return err(r); ST.creds=r.items; tRender(); },
  async cred(rid){ if(!(await ask('Yangi parol yaratilsin? Eski parol bilan kirgan qurilmalar chiqarib yuboriladi.'))) return; const r=await P('/api/class/creds',{rid}); if(!r.ok) return err(r); ST.creds=[r]; await tOpen(ST.cid,'students'); ST.creds=[r]; tRender(); },
  async unlink(rid){ if(!(await ask('O‘quvchining Telegram ulanishi uzilsinmi?'))) return; const r=await P('/api/class/roster/unlink',{rid}); if(!r.ok) return err(r); tOpen(ST.cid,'students'); },
  async saveR(rid){ const r=await P('/api/class/roster/edit',{rid,full_name:V('cl_en'),parent_phone:V('cl_ep'),fee:V('cl_ef')}); if(!r.ok) return err(r); tOpen(ST.cid,'students'); },
  async delR(rid){ if(!(await ask('O‘quvchi ro‘yxatdan o‘chirilsinmi? Ota-onasining kirishi ham yopiladi.'))) return; const r=await P('/api/class/roster/del',{rid}); if(!r.ok) return err(r); ST.open=null; tOpen(ST.cid,'students'); },
  async pay(rid,paid){ const r=await P('/api/class/pay',{rid,paid}); if(!r.ok) return err(r); tOpen(ST.cid,'students'); },
  async msgOne(rid){ const t=prompt?window.prompt('Ota-onaga xabar matni:'):''; if(!t) return; const r=await P('/api/class/msg',{id:ST.cid,rid,text:t}); if(!r.ok) return err(r); notify(r.sent?'Yuborildi ✅':'Ota-onasi hali ulanmagan: avval login/parol bering.'); },
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
  async saveSet(){ const r=await P('/api/class/update',{id:ST.cid,name:V('cl_sn'),subject:V('cl_ss'),notify_mode:V('cl_sm'),rating_names:V('cl_sr'),fee_day:V('cl_sf')}); if(!r.ok) return err(r); notify('Saqlandi ✅'); tOpen(ST.cid,'set'); },
  async groupOff(){ if(!(await ask('Guruh sinfdan uzilsinmi?'))) return; const r=await P('/api/class/group_unlink',{id:ST.cid}); if(!r.ok) return err(r); tOpen(ST.cid,'set'); },
  async assist(uid,remove){ const u=remove?uid:V('cl_as'); if(!u) return; const r=await P('/api/class/assist',{id:ST.cid,user_id:u,remove:!!remove}); if(!r.ok) return err(r); tOpen(ST.cid,'set'); },
  async delClass(){ if(!(await ask('Sinf butunlay o‘chirilsinmi? Ota-onalar kirishi ham yopiladi.'))) return; const r=await P('/api/class/delete',{id:ST.cid}); if(!r.ok) return err(r); tList(); },
  async login(){ const r=await P('/api/parent/login',{login:V('cl_lg'),password:V('cl_pw')}); if(!r.ok) return err(r); notify('Xush kelibsiz! Farzandingiz: '+r.name); if(window.ME){ ME.parent_mode=true; } const d=await G('/api/class/me'); ST.me=d; if(d.teacher||(window.ME&&ME.is_admin)) return pList(); const tb=$('teacherBody'); if(tb) tb.classList.add('hidden'); const h=$('clsH2'); if(h) h.textContent='👪 Ota-ona bo‘limi'; if(typeof clsBoot==='function') clsBoot(); pList(); },
  async logout(){ if(!(await ask('Ota-ona hisobidan chiqasizmi? Xabarlar kelishi to‘xtaydi.'))) return; const r=await P('/api/parent/logout',{}); if(!r.ok) return err(r); notify('Chiqdingiz.'); location.reload(); },
  async excuse(sid){ const n=window.prompt('Dars qoldirish sababi (ustozga yuboriladi):'); if(!n) return; const r=await P('/api/parent/excuse',{sid,rid:ST.rid,note:n}); if(!r.ok) return err(r); notify('Ustozga yuborildi ✅'); pChild(ST.rid); }
};
window.CLS_TEST={ratingRows,tStudents,tAtt,tHw,tTests,tRating,tSet,loginCard,credsBox,_st:ST};
})();
