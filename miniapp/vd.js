// v128/v135: «Ichki guruhlar uchun» (avval «Videodars») — login bilan kirish, videodarslar, maxsus topshiriqlar. O‘quvchi admin bergan login bilan kiradi, videoni OXIRIGACHA ko‘rgachgina topshiriq ochiladi.
// Video Render'da saqlanmaydi: YouTube (unlisted) yoki tashqi .mp4 havola. Ko‘rish serverda tekshiriladi (sakrab o‘tish kredit bermaydi).
let VD={me:null,tab:'lessons',gid:0,groups:[],qs:[],ans:[],task:null}, VP=null, _vdYTp=null;
function vdApi(path,body){
  return apiFetch(apiUrl(path),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})}).then(r=>r.json()).catch(()=>({ok:false,error:'Aloqa xatosi. Qayta urinib ko‘ring.'}));
}
const vdE=s=>escapeHtml(String(s==null?'':s));
const vdBox=()=>$('vdBody');
function vdFmtDur(s){ s=Math.round(s||0); const h=Math.floor(s/3600), m=Math.floor(s%3600/60), x=s%60, p=n=>String(n).padStart(2,'0'); return (h?h+':'+p(m):m)+':'+p(x); }
function vdParseDur(t){ t=String(t||'').trim(); if(!t) return 0; const p=t.split(':').map(x=>parseInt(x,10)); if(p.some(isNaN)) return 0; return p.length===1?p[0]*60:p.length===2?p[0]*60+p[1]:p[0]*3600+p[1]*60+p[2]; }
function vdToast(m){ let t=$('vdToast'); if(!t){ t=document.createElement('div'); t.id='vdToast'; document.body.appendChild(t); } t.textContent=m; t.className='on'; clearTimeout(t._h); t._h=setTimeout(()=>{ t.className=''; },2200); }
function vdCopy(txt){
  try{ navigator.clipboard.writeText(txt).then(()=>vdToast('✅ Nusxalandi')).catch(()=>vdCopyOld(txt)); }catch(e){ vdCopyOld(txt); }
}
function vdCopyOld(txt){ const a=document.createElement('textarea'); a.value=txt; a.style.cssText='position:fixed;opacity:0'; document.body.appendChild(a); a.select(); try{ document.execCommand('copy'); vdToast('✅ Nusxalandi'); }catch(e){ prompt('Nusxalang:',txt); } a.remove(); }
function vdShare(txt){ const u=(typeof ME!=='undefined'&&ME&&ME.bot_username)?'https://t.me/'+ME.bot_username+'?start=videodars':'https://t.me'; openExt('https://t.me/share/url?url='+encodeURIComponent(u)+'&text='+encodeURIComponent(txt)); }

async function loadVideodars(){
  vdStopPlayer(); const box=vdBox(); if(!box) return;
  box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/me');
  if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error||'Ochib bo‘lmadi. Telegram ichidan oching.')+'</p>'; return; }
  VD.me=d;
  if(d.role==='admin'){ VD.groups=d.groups||[]; vdAdminRender(); }
  else if(d.role==='student') vdStudentHome();
  else vdLoginForm();
}

// ===================== kirish =====================
function vdLoginForm(){
  vdBox().innerHTML='<div class="vdCard"><h3>🔐 Ichki guruhlar uchun kirish</h3><p class="muted" style="margin:4px 0 10px">Bu bo‘lim ichki guruhlar uchun. Login va parolni ustozingiz (admin) beradi.</p>'
    +'<label class="vdLb">Login</label><input id="vdLg" autocapitalize="off" autocomplete="username" spellcheck="false" placeholder="masalan: vd12345">'
    +'<label class="vdLb">Parol</label><input id="vdPw" type="password" autocomplete="current-password" placeholder="Parol" onkeydown="if(event.key===\'Enter\')vdDoLogin()">'
    +'<button type="button" class="vdMain" id="vdLgBtn" onclick="vdDoLogin()">Kirish</button><p id="vdLgErr" class="vdErr"></p></div>';
}
async function vdDoLogin(){
  const b=$('vdLgBtn'); b.disabled=true; const d=await vdApi('/api/vd/login',{login:$('vdLg').value,password:$('vdPw').value}); b.disabled=false;
  if(!d.ok){ $('vdLgErr').textContent=d.error||'Xatolik'; return; }
  loadVideodars();
}
async function vdLogout(){ if(!confirm('Tizimdan chiqasizmi?')) return; await vdApi('/api/vd/logout'); loadVideodars(); }

// ===================== o‘quvchi: darslar ro‘yxati =====================
function vdStatus(l){
  if(l.completed){
    if(l.task_state==='todo'||l.task_state==='failed') return ['📝 Topshiriqni bajaring','warn'];
    if(l.task_state==='sent') return ['📨 Topshiriq yuborilgan','ok'];
    return ['✅ Bajarildi','ok'];
  }
  return l.pct>0?['⏳ '+l.pct+'% ko‘rildi','mid']:['▶️ Boshlash','new'];
}
function vdStudentHome(){
  const d=VD.me;
  let h='<div class="vdHello"><div><b>'+vdE(d.name)+'</b><small>'+vdE(d.group)+'</small></div><button type="button" class="vdGhost" onclick="vdLogout()">Chiqish</button></div>';
  h+=d.lessons.length?d.lessons.map((l,i)=>{ const st=vdStatus(l);
    return '<button type="button" class="vdLes" onclick="vdOpen('+l.id+')"><span class="vdNum">'+(i+1)+'</span><span class="vdLesMid"><b>'+vdE(l.title)+'</b><small>⏱ '+vdFmtDur(l.duration_sec)+(l.task_kind!=='none'?' • 📝 topshiriq bor':'')+'</small>'
      +'<span class="vdBar"><i style="width:'+(l.completed?100:l.pct)+'%"></i></span></span><span class="vdChip '+st[1]+'">'+st[0]+'</span></button>'; }).join('')
    :'<p class="vdEmpty">🎬 Hozircha darslar yo‘q. Tez orada qo‘shiladi.</p>';
  const ts=d.tasks||[];
  if(ts.length) h+='<h3 class="vdSec">⭐ Maxsus topshiriqlar</h3>'+ts.map(vdStTaskRow).join('');
  vdBox().innerHTML=h;
}
function vdStTaskStatus(t){
  if(t.state==='passed') return ['✅ O‘tdingiz','ok'];
  if(t.state==='sent') return ['📨 Topshirilgan','ok'];
  if(t.state==='failed') return [(t.max_attempts&&t.attempts>=t.max_attempts)?'❌ Urinish tugagan':'🔁 Qayta urinib ko‘ring','warn'];
  if(t.state==='opened') return ['⏳ Boshlangan','mid'];
  return ['▶️ Boshlash','new'];
}
function vdStTaskRow(t){
  const st=vdStTaskStatus(t), parts=[]; if(t.closed_n) parts.push(t.closed_n+' ta yopiq'); if(t.open_n) parts.push(t.open_n+' ta ochiq');
  return '<button type="button" class="vdLes" onclick="vdStOpen('+t.id+')"><span class="vdNum">⭐</span><span class="vdLesMid"><b>'+vdE(t.title)+'</b><small>'+parts.join(' • ')+(t.max_attempts?' • urinish: '+t.attempts+'/'+t.max_attempts:'')+(t.total?' • natija: '+t.score+'/'+t.total:'')+'</small></span><span class="vdChip '+st[1]+'">'+st[0]+'</span></button>';
}

// ===================== dars sahifasi + ko‘rishni kuzatish =====================
function vdYT(){
  if(window.YT&&YT.Player) return Promise.resolve();
  if(_vdYTp) return _vdYTp;
  _vdYTp=new Promise((res,rej)=>{
    const prev=window.onYouTubeIframeAPIReady; window.onYouTubeIframeAPIReady=()=>{ try{ prev&&prev(); }catch(e){} res(); };
    const s=document.createElement('script'); s.src='https://www.youtube.com/iframe_api'; s.onerror=()=>{ _vdYTp=null; rej(); }; document.head.appendChild(s);
    setTimeout(()=>{ if(!(window.YT&&YT.Player)){ _vdYTp=null; rej(); } },12000);
  });
  return _vdYTp;
}
function vdStopPlayer(){
  if(!VP) return; clearInterval(VP.tick); clearInterval(VP.hbT); document.removeEventListener('visibilitychange',VP.vis);
  try{ if(VP.yt&&VP.yt.destroy) VP.yt.destroy(); }catch(e){}
  try{ const v=$('vdVid'); if(v){ v.pause(); v.removeAttribute('src'); v.load(); } }catch(e){}
  VP=null;
}
async function vdOpen(id){
  vdStopPlayer(); const box=vdBox(); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/lesson',{id});
  if(!d.ok){ notify(d.error||'Xatolik'); loadVideodars(); return; }
  const L=d.lesson, adm=VD.me.role==='admin';
  box.innerHTML='<button class="back" type="button" onclick="loadVideodars()">‹ Darslar</button><h3 class="vdT">'+vdE(L.title)+'</h3>'
    +'<div class="vdPlayer"><div id="vdPlayerIn"></div></div>'
    +(adm?'<p class="vdNote">👑 Admin ko‘rinishi: ko‘rish hisobga olinmaydi, topshiriq va to‘g‘ri javoblar ochiq.</p>'
          :'<div class="vdProg"><div class="vdBar big"><i id="vdBarI"></i></div><small id="vdProgTx"></small></div>')
    +(L.descr?'<p class="vdDescr">'+vdE(L.descr)+'</p>':'')+'<div id="vdTask"></div>';
  VP={L,adm,maxOk:Math.max(L.allow_to||0,L.resume||0),last:L.resume||0,hbBusy:false,done:!!L.completed,A:null};
  if(!adm) vdProgress(L.pct,L.completed,L.min_pct);
  if(adm||L.completed) vdShowTask(L.id); else $('vdTask').innerHTML='<div class="vdLock">🔒 Topshiriq videoni <b>oxirigacha</b> ko‘rgandan keyin ochiladi. Videoni oldinga o‘tkazib bo‘lmaydi.</div>';
  if(L.kind==='youtube') await vdStartYT(L); else vdStartDirect(L);
}
function vdProgress(pct,done,minp){
  const i=$('vdBarI'), t=$('vdProgTx'); if(!i) return;
  i.style.width=(done?100:pct)+'%';
  t.textContent=done?'✅ Dars to‘liq ko‘rildi':'Ko‘rildi: '+pct+'% (kamida '+(minp||90)+'% va oxirigacha ko‘rish kerak)';
}
async function vdStartYT(L){
  const host=$('vdPlayerIn'); if(!host) return; host.innerHTML='<div id="vdYT"></div>';
  try{ await vdYT(); }catch(e){ host.innerHTML='<p class="vdErr" style="padding:14px">Video yuklanmadi (YouTube ochilmayapti). Internetni tekshirib, qayta oching.</p>'; return; }
  const p=VP; if(!p||p.L!==L||!$('vdYT')) return;
  const yt=new YT.Player('vdYT',{videoId:L.src,width:'100%',height:'100%',playerVars:{playsinline:1,rel:0,modestbranding:1,disablekb:1,fs:1,iv_load_policy:3,start:Math.floor(L.resume||0)},
    events:{onStateChange:e=>{ if(e.data===0) vdHb(true); else if(e.data===1||e.data===2) vdHb(false); }}});
  p.yt=yt;
  p.A={pos:()=>{ try{ return yt.getCurrentTime()||0; }catch(e){ return 0; } }, playing:()=>{ try{ return yt.getPlayerState()===1; }catch(e){ return false; } },
       rate:()=>{ try{ return yt.getPlaybackRate()||1; }catch(e){ return 1; } }, seek:t=>{ try{ yt.seekTo(t,true); }catch(e){} },
       pause:()=>{ try{ yt.pauseVideo(); }catch(e){} }, dur:()=>{ try{ return yt.getDuration()||0; }catch(e){ return 0; } }};
  vdBeginTracking();
}
function vdStartDirect(L){
  const host=$('vdPlayerIn'); if(!host) return;
  host.innerHTML='<video id="vdVid" controls playsinline preload="metadata" controlsList="nodownload noremoteplayback" disablepictureinpicture></video>';
  const v=$('vdVid'); v.src=L.src;
  v.addEventListener('error',()=>{ host.innerHTML='<p class="vdErr" style="padding:14px">Video yuklanmadi. Havola ishlamayapti — adminga xabar bering.</p>'; if(VP) VP.A=null; });
  v.addEventListener('loadedmetadata',()=>{ if(L.resume&&VP&&!VP.done){ try{ v.currentTime=L.resume; }catch(e){} } });
  v.addEventListener('ended',()=>vdHb(true)); v.addEventListener('pause',()=>vdHb(false)); v.addEventListener('play',()=>vdHb(false));
  v.addEventListener('contextmenu',e=>e.preventDefault());
  VP.A={pos:()=>v.currentTime||0, playing:()=>!v.paused&&!v.ended, rate:()=>v.playbackRate||1, seek:t=>{ try{ v.currentTime=t; }catch(e){} }, pause:()=>v.pause(), dur:()=>isFinite(v.duration)?v.duration:0};
  vdBeginTracking();
}
function vdBeginTracking(){
  const p=VP; if(!p) return;
  p.tick=setInterval(vdTick,1000); p.hbT=setInterval(()=>vdHb(false),5000);
  p.vis=()=>{ if(document.hidden&&p.A) p.A.pause(); }; document.addEventListener('visibilitychange',p.vis);
}
function vdTick(){
  const p=VP; if(!p||!p.A) return; const A=p.A, pos=A.pos(), adv=pos-p.last;
  if(A.playing()&&adv>=0&&adv<=3*A.rate()+1) p.maxOk=Math.max(p.maxOk,pos);
  if(!p.adm&&!p.done&&pos>p.maxOk+4){ A.seek(p.maxOk); p.last=p.maxOk; vdToast('⏩ Videoni oldinga o‘tkazib bo‘lmaydi'); return; }
  p.last=pos;
}
async function vdHb(ended){
  const p=VP; if(!p||!p.A) return; const A=p.A;
  if(p.adm){ if(!p.admSent){ const du=A.dur(); if(du>10){ p.admSent=1; vdApi('/api/vd/hb',{id:p.L.id,pos:0,dur:du}); } } return; }
  if(p.hbBusy&&!ended) return; p.hbBusy=true;
  const d=await vdApi('/api/vd/hb',{id:p.L.id,pos:A.pos(),playing:(A.playing()||!!ended)&&!document.hidden,rate:A.rate(),ended:!!ended,dur:A.dur()});
  p.hbBusy=false; if(VP!==p) return;
  if(d.ok){
    p.maxOk=Math.max(p.maxOk,d.allow_to||0); vdProgress(d.pct,d.completed,d.min_pct);
    if(d.completed&&!p.done){ p.done=true; vdShowTask(p.L.id); }
  }else if(d.error&&/login/i.test(d.error)){ vdToast(d.error); }
}

// ===================== topshiriq =====================
async function vdShowTask(id){
  const box=$('vdTask'); if(!box) return; box.innerHTML='<p class="vdEmpty">Topshiriq yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/task',{id}); if(!$('vdTask')) return;
  if(!d.ok){ box.innerHTML='<div class="vdLock">'+vdE(d.error||'Ochib bo‘lmadi')+'</div>'; return; }
  const t=d.task, adm=VD.me.role==='admin'; VD.task={id,t};
  if(t.kind==='none'){ box.innerHTML='<div class="vdCard vdOk"><h3>✅ Dars yakunlandi</h3><p class="muted">Bu darsda topshiriq yo‘q. Barakalla!</p></div>'; return; }
  if(t.kind==='text') return vdTextTask(t,adm);
  VD.ans=new Array(t.questions.length).fill(-1); vdTestTask(t,adm);
}
function vdTestTask(t,adm,wrong){
  const box=$('vdTask'), done=t.passed&&!adm, ca=adm?t.questions.map(q=>q.correct):(t.answers||[]);
  let h='<div class="vdCard"><h3>📝 Topshiriq</h3>'+(t.text?'<p class="vdDescr" style="margin:0 0 8px">'+vdE(t.text)+'</p>':'')+'<small class="muted">O‘tish: '+t.pass_pct+'% • '+t.questions.length+' ta savol</small>';
  if(t.last&&!adm&&!wrong) h+='<p class="vdNote">Oxirgi urinish ('+vdE(t.last.time)+'): '+t.last.score+'/'+t.last.total+' — '+(t.last.passed?'✅ o‘tdingiz':'❌ o‘tmadingiz')+'</p>';
  if(wrong&&wrong.length) h+='<p class="vdErrBox">❌ Noto‘g‘ri javob berilgan savollar: '+wrong.map(i=>i+1).join(', ')+'. Qayta urinib ko‘ring.</p>';
  h+=t.questions.map((q,i)=>'<div class="vdQView'+(wrong&&wrong.indexOf(i)>=0?' bad':'')+'"><b>'+(i+1)+'. '+vdE(q.q)+'</b>'
    +q.options.map((o,j)=>'<button type="button" class="vdOpt'+((done||adm)&&ca[i]===j?' right':'')+'" id="vo_'+i+'_'+j+'" '+(done||adm?'disabled':'onclick="vdPick('+i+','+j+')"')+'><i>'+String.fromCharCode(65+j)+'</i>'+vdE(o)+'</button>').join('')+'</div>').join('');
  if(!done&&!adm) h+='<button type="button" class="vdMain" id="vdSubBtn" onclick="vdSubmitTest()">✅ Javoblarni yuborish</button>';
  if(done) h+='<p class="vdOkBox">🎉 Topshiriq bajarildi!</p>';
  box.innerHTML=h+'</div>';
}
function vdPick(i,j){
  VD.ans[i]=j; document.querySelectorAll('[id^="vo_'+i+'_"]').forEach(b=>b.classList.remove('sel')); const b=$('vo_'+i+'_'+j); if(b) b.classList.add('sel');
}
async function vdSubmitTest(){
  if(VD.ans.some(x=>x<0)){ notify('Hamma savolga javob bering.'); return; }
  const b=$('vdSubBtn'); b.disabled=true; const d=await vdApi('/api/vd/submit',{id:VD.task.id,answers:VD.ans}); b.disabled=false;
  if(!d.ok){ notify(d.error||'Xatolik'); return; }
  if(d.result.passed){ vdShowTask(VD.task.id); try{ tg&&tg.HapticFeedback&&tg.HapticFeedback.notificationOccurred('success'); }catch(e){} }
  else{ const t=VD.task.t; VD.ans=new Array(t.questions.length).fill(-1); vdTestTask(t,false,d.result.wrong); window.scrollTo(0,document.body.scrollHeight); vdToast('Natija: '+d.result.score+'/'+d.result.total); }
}
function vdTextTask(t,adm){
  const box=$('vdTask'), l=t.last;
  let h='<div class="vdCard"><h3>📝 Topshiriq</h3><p class="vdDescr" style="margin:0 0 8px;white-space:pre-wrap">'+vdE(t.text)+'</p>';
  if(adm){ box.innerHTML=h+'<p class="vdNote">Matnli javob topshiriq. O‘quvchilar javoblari «📊 Natijalar»da.</p></div>'; return; }
  if(l){ h+='<div class="vdSent"><small>📨 Yuborilgan ('+vdE(l.time)+')</small><p style="white-space:pre-wrap">'+vdE(l.text)+'</p>'+(l.comment?'<div class="vdCmt">💬 Ustoz: '+vdE(l.comment)+'</div>':'<small class="muted">Ustoz hali ko‘rmagan.</small>')+'</div><p class="muted" style="margin:10px 0 4px;font-size:12px">Xohlasangiz, javobni yangilab qayta yuborishingiz mumkin:</p>'; }
  h+='<textarea id="vdAns" rows="6" maxlength="4000" placeholder="Javobingizni shu yerga yozing…"></textarea><button type="button" class="vdMain" id="vdSubBtn" onclick="vdSubmitText()">📨 Yuborish</button></div>';
  box.innerHTML=h;
}
async function vdSubmitText(){
  const tx=$('vdAns').value.trim(); if(tx.length<2){ notify('Javobingizni yozing.'); return; }
  const b=$('vdSubBtn'); b.disabled=true; const d=await vdApi('/api/vd/submit',{id:VD.task.id,text:tx}); b.disabled=false;
  if(!d.ok){ notify(d.error||'Xatolik'); return; } vdToast('✅ Yuborildi'); vdShowTask(VD.task.id);
}

// ===================== ADMIN =====================
function vdGname(id){ const g=VD.groups.find(x=>x.id===id); return g?g.name:'—'; }
async function vdRefreshGroups(){ const d=await vdApi('/api/vd/admin/groups'); if(d.ok) VD.groups=d.groups; }
function vdAdminRender(sid){
  const tabs=[['lessons','🎬 Darslar'],['tasks','⭐ Maxsus topshiriq'],['students','👥 O‘quvchilar'],['log','🕵️ Kim kirdi']];
  vdBox().innerHTML='<div class="rsTabs vdTabs">'+tabs.map(t=>'<button type="button" class="'+(VD.tab===t[0]?'on':'')+'" onclick="vdTab(\''+t[0]+'\')">'+t[1]+'</button>').join('')+'</div><div id="vdAdm"></div>';
  if(VD.tab==='lessons') vdAdmLessons(); else if(VD.tab==='tasks') vdAdmTasks(); else if(VD.tab==='students') vdAdmStudents(); else vdAdmLog(sid);
}
function vdTab(t){ VD.tab=t; vdAdminRender(); }
function vdGroupBar(){
  return '<div class="vdChips"><button type="button" class="'+(!VD.gid?'on':'')+'" onclick="vdSetGid(0)">Hammasi</button>'+VD.groups.map(g=>'<button type="button" class="'+(VD.gid===g.id?'on':'')+'" onclick="vdSetGid('+g.id+')">'+vdE(g.name)+' <small>'+g.students+'</small></button>').join('')+'</div>';
}
function vdSetGid(g){ VD.gid=g; vdAdminRender(); }

// ---- darslar
async function vdAdmLessons(){
  const box=$('vdAdm'); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/lessons',{group_id:VD.gid}); if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  VD.lessons=d.lessons;
  let h=vdGroupBar();
  if(!VD.groups.length) h+='<div class="vdLock">Avval «👥 O‘quvchilar» bo‘limida guruh oching va o‘quvchi qo‘shing.</div>';
  else h+='<div class="rsAdmin"><button type="button" onclick="vdLessonForm()">➕ Dars qo‘shish</button></div>';
  h+=d.lessons.length?d.lessons.map(l=>{
    const tk=l.task.kind==='test'?'📝 Test ('+l.task.questions.length+')':l.task.kind==='text'?'📝 Matnli topshiriq':'— topshiriqsiz';
    return '<div class="vdCard'+(l.published?'':' hid')+'"><b>'+vdE(l.title)+'</b> <span class="vdChip new">'+vdE(vdGname(l.group_id))+'</span>'
      +'<small class="vdMeta">⏱ '+vdFmtDur(l.duration_sec)+' • '+(l.kind==='youtube'?'YouTube':'Havola')+' • '+tk+' • ✅ '+l.done+'/'+l.students+' ko‘rdi'+(l.published?'':' • 🔒 yashirin')+'</small>'
      +'<div class="rsRow"><button type="button" class="main" onclick="vdOpen('+l.id+')">▶️ Ko‘rish</button><button type="button" onclick="vdResults('+l.id+')">📊 Natijalar</button><button type="button" onclick="vdLessonForm('+l.id+')">✏️</button>'
      +'<button type="button" onclick="vdMove('+l.id+',\'up\')">⬆</button><button type="button" onclick="vdMove('+l.id+',\'down\')">⬇</button>'
      +'<button type="button" onclick="vdPub('+l.id+','+(l.published?0:1)+')">'+(l.published?'🙈':'👁')+'</button><button type="button" class="del" onclick="vdLDel('+l.id+')">🗑</button></div></div>'; }).join('')
    :(VD.groups.length?'<p class="vdEmpty">🎬 Hali dars yo‘q. «➕ Dars qo‘shish» ni bosing.</p>':'');
  box.innerHTML=h;
}
async function vdMove(id,dir){ await vdApi('/api/vd/admin/lesson_move',{id,dir}); vdAdmLessons(); }
async function vdPub(id,v){ await vdApi('/api/vd/admin/lesson_pub',{id,published:!!v}); vdAdmLessons(); }
async function vdLDel(id){ if(!confirm('Dars va uning natijalari o‘chiriladi. Davom etasizmi?')) return; const d=await vdApi('/api/vd/admin/lesson_del',{id}); if(!d.ok) notify(d.error||'Xatolik'); vdAdmLessons(); }

function vdLessonForm(id){
  const L=id?VD.lessons.find(x=>x.id===id):null, task=(L&&L.task)||{kind:'none'};
  VD.qs=(task.questions||[]).map(q=>({q:q.q,options:q.options.slice(),correct:q.correct}));
  VD.editId=id||0;
  const gs=VD.groups.map(g=>'<option value="'+g.id+'"'+((L?L.group_id:VD.gid)===g.id?' selected':'')+'>'+vdE(g.name)+'</option>').join('');
  $('vdAdm').innerHTML='<button class="back" type="button" onclick="vdAdminRender()">‹ Orqaga</button><h3>'+(L?'✏️ Darsni tahrirlash':'➕ Yangi dars')+'</h3><div class="vdForm">'
    +'<label>Guruh</label><select id="vfGroup">'+gs+'</select>'
    +'<label>Dars nomi</label><input id="vfTitle" maxlength="120" placeholder="Masalan: 1-dars. Gap bo‘laklari" value="'+vdE(L?L.title:'')+'">'
    +'<label>Video havolasi</label><input id="vfUrl" autocapitalize="off" spellcheck="false" placeholder="YouTube havolasi yoki https://…/video.mp4" value="'+vdE(L?L.url:'')+'" onchange="vdDetect()">'
    +'<p class="muted vdHint">Video Render\'da saqlanmaydi. YouTube’da videoni <b>«Ro‘yxatda ko‘rinmaydigan» (Unlisted)</b> qilib yuklang va havolani shu yerga joylang. Yoki tashqi saqlagichdagi .mp4 havolani kiriting.</p>'
    +'<label>Davomiyligi (daqiqa:soniya)</label><div class="vdDurRow"><input id="vfDur" inputmode="numeric" placeholder="12:30" value="'+(L?vdFmtDur(L.duration_sec):'')+'"><button type="button" onclick="vdDetect()">⏱ Aniqlash</button></div><small id="vfDetTx" class="muted"></small><div id="vfProbe" class="vdProbe"></div>'
    +'<label>Qancha ko‘rilsa hisoblansin</label><select id="vfPct">'+[70,80,90,95].map(x=>'<option'+((L?L.min_pct:90)===x?' selected':'')+' value="'+x+'">'+x+'% va oxirigacha</option>').join('')+'</select>'
    +'<label>Izoh (ixtiyoriy)</label><textarea id="vfDescr" rows="2" maxlength="600" placeholder="Dars haqida qisqa ma’lumot">'+vdE(L?L.descr:'')+'</textarea>'
    +'<label>Topshiriq (video tugagach ochiladi)</label><select id="vfKind" onchange="vdKindChange()"><option value="none"'+(task.kind==='none'?' selected':'')+'>Topshiriqsiz</option><option value="test"'+(task.kind==='test'?' selected':'')+'>📝 Test (avtomatik tekshiriladi)</option><option value="text"'+(task.kind==='text'?' selected':'')+'>✍️ Matnli javob (ustoz ko‘radi)</option></select>'
    +'<div id="vfTaskBox"></div>'
    +'<label class="vdCheck"><input type="checkbox" id="vfPub"'+(!L||L.published?' checked':'')+'> O‘quvchilarga ko‘rsatilsin</label>'
    +'<button type="button" class="vdMain" id="vfSave" onclick="vdLessonSave()">💾 Saqlash</button></div>';
  vd_taskBox(task);
}
function vd_taskBox(task){
  const k=$('vfKind').value, b=$('vfTaskBox'); task=task||{};
  if(k==='none'){ b.innerHTML=''; return; }
  let h='<label>'+(k==='test'?'Topshiriq sharti (ixtiyoriy)':'Topshiriq matni')+'</label><textarea id="vfText" rows="3" maxlength="2000" placeholder="'+(k==='test'?'Masalan: Mavzu bo‘yicha savollarga javob bering':'O‘quvchi nima qilishi kerak?')+'">'+vdE(task.text||'')+'</textarea>';
  if(k==='test'){
    h+='<label>O‘tish bali (%)</label><input id="vfPass" type="number" min="1" max="100" inputmode="numeric" value="'+(task.pass_pct||60)+'"><div id="vfQs"></div>'
      +'<div class="rsAdmin"><button type="button" onclick="vdQAdd()">➕ Savol qo‘shish</button></div>'
      +'<details class="vdPaste"><summary>⚡ Matndan tez kiritish</summary><p class="muted" style="font-size:12px;margin:6px 0">Savollar orasida bo‘sh qator. Birinchi qator — savol, keyingilari — variantlar. To‘g‘ri variant oldiga <b>*</b> qo‘ying:<br><code>1. Poytaxt qaysi?<br>A) Toshkent *<br>B) Samarqand</code></p><textarea id="vfPaste" rows="6" placeholder="Matnni shu yerga joylang"></textarea><button type="button" onclick="vdImportQs()">⬇️ Savollarga aylantirish</button></details>';
  }
  b.innerHTML=h; if(k==='test') vdQRender();
}
function vdKindChange(){ vd_taskBox({}); }
function vdQCollect(){
  const out=[]; document.querySelectorAll('#vfQs .vdQ').forEach(el=>{
    const opts=[...el.querySelectorAll('.vqOpt')].map(x=>x.value); const r=el.querySelector('input[type=radio]:checked');
    out.push({q:el.querySelector('.vqText').value,options:opts,correct:r?parseInt(r.value,10):-1});
  }); if(document.querySelector('#vfQs')) VD.qs=out;
}
function vdQRender(){
  const box=$('vfQs'); if(!box) return;
  box.innerHTML=VD.qs.map((q,i)=>'<div class="vdQ"><div class="vdQh"><b>'+(i+1)+'-savol</b><button type="button" class="del" onclick="vdQDel('+i+')">🗑</button></div>'
    +'<textarea class="vqText" rows="2" maxlength="400" placeholder="Savol matni">'+vdE(q.q)+'</textarea>'
    +q.options.map((o,j)=>'<div class="vdOptRow"><input type="radio" name="vqc'+i+'" value="'+j+'"'+(q.correct===j?' checked':'')+' title="To‘g‘ri javob"><input class="vqOpt" maxlength="200" placeholder="Variant '+String.fromCharCode(65+j)+'" value="'+vdE(o)+'"><button type="button" onclick="vdOptDel('+i+','+j+')">✕</button></div>').join('')
    +'<button type="button" class="vdSmall" onclick="vdOptAdd('+i+')">➕ Variant</button><small class="muted"> To‘g‘ri javob yonidagi doirani belgilang.</small></div>').join('')||'<p class="muted" style="font-size:12.5px">Hali savol yo‘q.</p>';
}
function vdQAdd(){ vdQCollect(); VD.qs.push({q:'',options:['','','',''],correct:-1}); vdQRender(); }
function vdQDel(i){ vdQCollect(); VD.qs.splice(i,1); vdQRender(); }
function vdOptAdd(i){ vdQCollect(); if(VD.qs[i].options.length<6) VD.qs[i].options.push(''); vdQRender(); }
function vdOptDel(i,j){ vdQCollect(); const q=VD.qs[i]; if(q.options.length<=2){ notify('Kamida 2 ta variant bo‘lsin.'); return; } q.options.splice(j,1); if(q.correct===j) q.correct=-1; else if(q.correct>j) q.correct--; vdQRender(); }
function vdParseQs(txt){
  const out=[]; String(txt||'').replace(/\r/g,'').split(/\n\s*\n/).forEach(b=>{
    const ls=b.split('\n').map(x=>x.trim()).filter(Boolean); if(ls.length<3) return;
    const q=ls[0].replace(/^\d+\s*[.)\-]\s*/,''), opts=[]; let c=-1;
    ls.slice(1).forEach(l=>{ let ok=false; if(/^[*+]/.test(l)){ ok=true; l=l.replace(/^[*+]\s*/,''); } if(/\s*[*✓✔]\s*$/.test(l)){ ok=true; l=l.replace(/\s*[*✓✔]\s*$/,''); }
      l=l.replace(/^[A-Za-zА-Яа-я0-9]\s*[.)]\s+/,'').trim(); if(!l) return; if(ok) c=opts.length; opts.push(l); });
    if(q&&opts.length>=2) out.push({q,options:opts.slice(0,6),correct:c});
  }); return out;
}
function vdImportQs(){
  const r=vdParseQs($('vfPaste').value); if(!r.length){ notify('Savol topilmadi. Namunadagidek yozing (savol + kamida 2 variant).'); return; }
  vdQCollect(); VD.qs=VD.qs.concat(r); $('vfPaste').value=''; vdQRender();
  const miss=r.filter(x=>x.correct<0).length; notify('✅ '+r.length+' ta savol qo‘shildi.'+(miss?'\nDiqqat: '+miss+' tasida to‘g‘ri javob belgilanmagan — doirani belgilang.':''));
}
async function vdDetect(){
  const url=($('vfUrl').value||'').trim(), tx=$('vfDetTx'); if(!url){ tx.textContent='Avval havolani kiriting.'; return; }
  tx.textContent='Aniqlanmoqda…'; const p=await vdApi('/api/vd/parse',{url}); if(!p.ok){ tx.textContent='⚠️ '+p.error; return; }
  const host=$('vfProbe'); host.innerHTML=''; let dur=0;
  if(p.kind==='youtube'){
    try{ await vdYT(); }catch(e){ tx.textContent='YouTube ochilmadi — davomiylikni qo‘lda kiriting.'; return; }
    dur=await new Promise(res=>{
      host.innerHTML='<div id="vfProbeYT"></div>'; let pl, fin0=false; const fin=v=>{ if(fin0) return; fin0=true; try{ pl.destroy(); }catch(e){} res(v); };
      pl=new YT.Player('vfProbeYT',{videoId:p.src,width:'160',height:'90',playerVars:{playsinline:1},events:{onReady:()=>{ let n=0; const iv=setInterval(()=>{ let d=0; try{ d=pl.getDuration(); }catch(e){} if(d>0){ clearInterval(iv); fin(d); } else if(++n>24){ clearInterval(iv); fin(0); } },500); }, onError:()=>fin(0)}});
      setTimeout(()=>fin(0),15000);
    });
  }else{
    dur=await new Promise(res=>{ const v=document.createElement('video'); v.preload='metadata'; v.onloadedmetadata=()=>res(isFinite(v.duration)?v.duration:0); v.onerror=()=>res(0); v.src=p.src; setTimeout(()=>res(0),12000); });
  }
  host.innerHTML='';
  if(dur>0){ $('vfDur').value=vdFmtDur(dur); tx.textContent='✅ Aniqlandi: '+vdFmtDur(dur); }
  else tx.textContent='⚠️ Aniqlanmadi — davomiylikni qo‘lda kiriting (masalan 12:30). Videoni «▶️ Ko‘rish»da ochsangiz, u o‘zi tuzatiladi.';
}
async function vdLessonSave(){
  vdQCollect(); const kind=$('vfKind').value;
  const task={kind}; if(kind!=='none'){ task.text=($('vfText')||{}).value||''; if(kind==='test'){ task.pass_pct=parseInt(($('vfPass')||{}).value,10)||60; task.questions=VD.qs; } }
  const body={id:VD.editId||0,group_id:parseInt($('vfGroup').value,10)||0,title:$('vfTitle').value,url:$('vfUrl').value,duration_sec:vdParseDur($('vfDur').value),min_pct:parseInt($('vfPct').value,10),descr:$('vfDescr').value,published:$('vfPub').checked,task};
  const b=$('vfSave'); b.disabled=true; const d=await vdApi('/api/vd/admin/lesson_save',body); b.disabled=false;
  if(!d.ok){ notify(d.error||'Saqlab bo‘lmadi'); return; }
  vdToast('✅ Saqlandi'); VD.gid=body.group_id; await vdRefreshGroups(); vdAdminRender();
}

// ---- natijalar (dars bo‘yicha)
async function vdResults(id){
  const box=$('vdAdm'); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>'; const d=await vdApi('/api/vd/admin/results',{id});
  if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  const tk=d.lesson.task_kind;
  let h='<button class="back" type="button" onclick="vdAdminRender()">‹ Darslar</button><h3>📊 '+vdE(d.lesson.title)+'</h3>';
  const done=d.rows.filter(r=>r.completed).length; h+='<p class="muted" style="margin:0 0 8px">Oxirigacha ko‘rgan: <b>'+done+'/'+d.rows.length+'</b></p>';
  h+=d.rows.map(r=>{
    let task='';
    if(tk==='test') task=r.best?('📝 '+r.best.score+'/'+r.best.total+(r.best.passed?' ✅':' ❌')+' • '+r.attempts+' urinish'):(r.completed?'📝 hali topshirmagan':'');
    else if(tk==='text') task=r.sub?'📨 javob yuborgan':(r.completed?'✍️ hali yubormagan':'');
    return '<div class="vdCard'+(r.active?'':' hid')+'"><div class="vdRowTop"><b>'+vdE(r.name)+'</b><span class="vdChip '+(r.completed?'ok':r.pct>0?'mid':'new')+'">'+(r.completed?'✅ ko‘rdi':r.pct>0?r.pct+'%':'boshlamagan')+'</span></div>'
      +'<span class="vdBar"><i style="width:'+(r.completed?100:r.pct)+'%"></i></span>'
      +'<small class="vdMeta">'+(r.completed?'Tugatgan: '+vdE(r.completed):(r.last_watch?'Oxirgi ko‘rish: '+vdE(r.last_watch):'Hali ochmagan'))+(task?' • '+task:'')+'</small>'
      +(r.sub?'<div class="vdSent"><small>'+vdE(r.sub.time)+'</small><p style="white-space:pre-wrap">'+vdE(r.sub.text)+'</p><textarea id="cm'+r.sub.id+'" rows="2" maxlength="600" placeholder="Izoh yozing (o‘quvchi ko‘radi)">'+vdE(r.sub.comment)+'</textarea><button type="button" class="vdSmall" onclick="vdReview('+r.sub.id+','+id+')">💬 Izohni saqlash</button></div>':'')+'</div>'; }).join('')||'<p class="vdEmpty">Bu guruhda o‘quvchi yo‘q.</p>';
  box.innerHTML=h;
}
async function vdReview(sid,lid){ const d=await vdApi('/api/vd/admin/review',{id:sid,comment:$('cm'+sid).value}); if(!d.ok){ notify(d.error||'Xatolik'); return; } vdToast('✅ Saqlandi'); }

// ---- o‘quvchilar va guruhlar
async function vdAdmStudents(){
  const box=$('vdAdm'); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  await vdRefreshGroups(); const d=await vdApi('/api/vd/admin/students',{group_id:VD.gid});
  if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  let h=vdGroupBar()+'<div class="rsAdmin"><button type="button" onclick="vdGroupForm(0)">➕ Guruh</button>'+(VD.gid?'<button type="button" onclick="vdGroupForm('+VD.gid+')">✏️ Guruh nomi</button><button type="button" onclick="vdGroupDel('+VD.gid+')">🗑 Guruhni o‘chirish</button>':'')
    +(VD.groups.length?'<button type="button" onclick="vdAddStudentsForm()">➕ O‘quvchilar qo‘shish</button>':'')+'</div>';
  if(!VD.groups.length) h+='<div class="vdLock">Avval «➕ Guruh» bilan guruh oching (masalan: «9-A guruh»).</div>';
  h+=d.students.length?d.students.map(s=>'<div class="vdCard'+(s.active?'':' hid')+'"><div class="vdRowTop"><b>'+vdE(s.full_name)+'</b><span class="vdChip new">'+vdE(vdGname(s.group_id))+'</span></div>'
    +'<small class="vdMeta">🔑 Login: <code>'+vdE(s.login)+'</code> • Parol: '+(s.password?'<code class="vdPw" id="pw'+s.id+'" onclick="vdTogglePw('+s.id+')">••••••</code> <button type="button" class="vdSmall" onclick="vdTogglePw('+s.id+')">👁</button> <button type="button" class="vdSmall" onclick="vdCopyCred('+s.id+')">📋</button>':'<i>noma‘lum (eski hisob) — «🔑 Yangi parol» bosing</i>')+'<br>📱 '+s.devices+'/'+(VD.me.max_dev||2)+' • ✅ '+s.done+' dars<br>'+(s.last_login?'Oxirgi kirish: '+vdE(s.last_login):'Hali kirmagan')+(s.last_seen?' • Faol: '+vdE(s.last_seen):'')+(s.active?'':' • ⏸ o‘chirilgan')+'</small>'
    +'<div class="rsRow"><button type="button" onclick="vdReset('+s.id+')">🔑 Yangi parol</button><button type="button" onclick="vdSetPw('+s.id+')">✍️ Parol belgilash</button><button type="button" onclick="vdStForm('+s.id+')">✏️</button><button type="button" onclick="vdStLog('+s.id+')">🕵️</button><button type="button" onclick="vdStActive('+s.id+','+(s.active?0:1)+')">'+(s.active?'⏸':'▶️')+'</button><button type="button" class="del" onclick="vdStDel('+s.id+')">🗑</button></div></div>').join('')
    :(VD.groups.length?'<p class="vdEmpty">Bu yerda o‘quvchi yo‘q.</p>':'');
  VD.students=d.students; box.innerHTML=h;
}
function vdGroupForm(id){
  const g=id?VD.groups.find(x=>x.id===id):null;
  $('vdAdm').innerHTML='<button class="back" type="button" onclick="vdAdminRender()">‹ Orqaga</button><h3>'+(g?'✏️ Guruh nomi':'➕ Yangi guruh')+'</h3><div class="vdForm"><label>Guruh nomi</label><input id="vgName" maxlength="50" placeholder="Masalan: 9-A guruh" value="'+vdE(g?g.name:'')+'"><button type="button" class="vdMain" onclick="vdGroupSave('+(id||0)+')">💾 Saqlash</button></div>';
}
async function vdGroupSave(id){
  const name=$('vgName').value, d=await vdApi(id?'/api/vd/admin/group_rename':'/api/vd/admin/group_add',{id,name});
  if(!d.ok){ notify(d.error||'Xatolik'); return; } if(!id&&d.id) VD.gid=d.id; await vdRefreshGroups(); vdAdminRender();
}
async function vdGroupDel(id){ if(!confirm('Guruh o‘chirilsinmi?')) return; const d=await vdApi('/api/vd/admin/group_del',{id}); if(!d.ok){ notify(d.error||'Xatolik'); return; } VD.gid=0; await vdRefreshGroups(); vdAdminRender(); }
function vdAddStudentsForm(){
  const gs=VD.groups.map(g=>'<option value="'+g.id+'"'+(VD.gid===g.id?' selected':'')+'>'+vdE(g.name)+'</option>').join('');
  $('vdAdm').innerHTML='<button class="back" type="button" onclick="vdAdminRender()">‹ Orqaga</button><h3>➕ O‘quvchilar qo‘shish</h3><div class="vdForm"><label>Guruh</label><select id="vsGroup">'+gs+'</select>'
    +'<label>Ism familiyalar (har qatorda bittadan)</label><textarea id="vsNames" rows="8" placeholder="Ali Valiyev&#10;Madina Karimova"></textarea><p class="muted vdHint">Har biriga login va parol avtomatik yaratiladi. Keyin ham «👥 O‘quvchilar» ro‘yxatida ko‘rinib turadi.</p><button type="button" class="vdMain" id="vsBtn" onclick="vdAddStudents()">✅ Yaratish</button></div>';
}
async function vdAddStudents(){
  const b=$('vsBtn'); b.disabled=true; const d=await vdApi('/api/vd/admin/students_add',{group_id:parseInt($('vsGroup').value,10),names:$('vsNames').value}); b.disabled=false;
  if(!d.ok){ notify(d.error||'Xatolik'); return; } vdRefreshGroups(); vdShowCreds(d.created);
}
function vdCredText(list){ return '👥 Ichki guruhlar uchun\n'+list.map(c=>c.name+'\nLogin: '+c.login+'\nParol: '+c.password).join('\n\n'); }
function vdShowCreds(list){
  VD._cred=vdCredText(list);
  $('vdAdm').innerHTML='<button class="back" type="button" onclick="vdAdminRender()">‹ Tayyor</button><h3>🔑 Login va parollar</h3><p class="vdErrBox">Parollar «👥 O‘quvchilar» ro‘yxatida ham doim ko‘rinib turadi (👁 bosing). Hozir nusxalab oling.</p>'
    +list.map(c=>'<div class="vdCard"><b>'+vdE(c.name)+'</b><div class="vdCred">Login: <code>'+vdE(c.login)+'</code><br>Parol: <code>'+vdE(c.password)+'</code></div></div>').join('')
    +'<div class="rsAdmin"><button type="button" onclick="vdCopy(VD._cred)">📋 Hammasini nusxalash</button><button type="button" onclick="vdShare(VD._cred)">📤 Telegramda yuborish</button></div>';
}
async function vdReset(id){ if(!confirm('Yangi parol yaratilsinmi? Eski parol va barcha qurilmalar o‘chadi.')) return; const d=await vdApi('/api/vd/admin/student_reset',{id}); if(!d.ok){ notify(d.error||'Xatolik'); return; } vdShowCreds([d.cred]); }
function vdStForm(id){
  const s=VD.students.find(x=>x.id===id); if(!s) return;
  const gs=VD.groups.map(g=>'<option value="'+g.id+'"'+(s.group_id===g.id?' selected':'')+'>'+vdE(g.name)+'</option>').join('');
  $('vdAdm').innerHTML='<button class="back" type="button" onclick="vdAdminRender()">‹ Orqaga</button><h3>✏️ O‘quvchi</h3><div class="vdForm"><label>Ism familiya</label><input id="veName" maxlength="60" value="'+vdE(s.full_name)+'"><label>Login</label><input id="veLogin" autocapitalize="off" value="'+vdE(s.login)+'"><label>Guruh</label><select id="veGroup">'+gs+'</select><button type="button" class="vdMain" onclick="vdStSave('+id+')">💾 Saqlash</button></div>';
}
async function vdStSave(id){ const d=await vdApi('/api/vd/admin/student_edit',{id,name:$('veName').value,login:$('veLogin').value,group_id:parseInt($('veGroup').value,10)}); if(!d.ok){ notify(d.error||'Xatolik'); return; } vdAdminRender(); }
async function vdStActive(id,v){ await vdApi('/api/vd/admin/student_edit',{id,active:!!v}); vdAdmStudents(); }
async function vdStDel(id){ if(!confirm('O‘quvchi va uning natijalari o‘chiriladi. Davom etasizmi?')) return; const d=await vdApi('/api/vd/admin/student_del',{id}); if(!d.ok) notify(d.error||'Xatolik'); vdRefreshGroups(); vdAdmStudents(); }
function vdStLog(id){ VD.tab='log'; vdAdminRender(id); }

// ---- «Kim kirdi»
async function vdAdmLog(sid){
  const box=$('vdAdm'); if(!box) return; box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/admin/activity',{limit:150,student_id:sid||0}); if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  let h='<div class="rsAdmin"><button type="button" onclick="vdAdmLog()">🔄 Yangilash</button><button type="button" onclick="vdToggleNotify()">'+(VD.me.notify?'🔔 Xabar: YOQILGAN':'🔕 Xabar: O‘CHIQ')+'</button></div>'
    +'<p class="muted" style="margin:0 0 8px;font-size:12px">'+(sid?'Tanlangan o‘quvchi faoliyati. ':'')+'Vaqt — Toshkent vaqti bilan. Kirganda sizga Telegramga ham xabar keladi (yoqilgan bo‘lsa).</p>';
  h+=d.rows.length?d.rows.map(r=>'<div class="vdLog"><div><b>'+vdE(r.name)+'</b> <small>'+vdE(r.group)+'</small><br><span>'+vdE(r.label)+(r.lesson?' — '+vdE(r.lesson):'')+'</span></div><time>'+vdE(r.time)+'</time></div>').join(''):'<p class="vdEmpty">Hali hech kim kirmagan.</p>';
  box.innerHTML=h;
}
async function vdToggleNotify(){ const on=!VD.me.notify; const d=await vdApi('/api/vd/admin/notify',{on}); if(d.ok){ VD.me.notify=d.notify; vdAdmLog(); } }

// ===================== v135: parol ko‘rinishi =====================
function vdTogglePw(id){
  const el=$('pw'+id), s=(VD.students||[]).find(x=>x.id===id); if(!el||!s) return;
  const shown=el.dataset.on==='1'; el.dataset.on=shown?'0':'1'; el.textContent=shown?'••••••':s.password;
}
function vdCopyCred(id){ const s=(VD.students||[]).find(x=>x.id===id); if(s) vdCopy(s.full_name+'\nLogin: '+s.login+'\nParol: '+s.password); }
async function vdSetPw(id){
  const pw=prompt('Yangi parolni kiriting (kamida 4 belgi):'); if(pw===null) return;
  const d=await vdApi('/api/vd/admin/student_setpw',{id,password:pw}); if(!d.ok){ notify(d.error||'Xatolik'); return; } vdShowCreds([d.cred]);
}

// ===================== v135: MAXSUS TOPSHIRIQ — o‘quvchi =====================
async function vdStOpen(id){
  vdStopPlayer(); const box=vdBox(); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/st/open',{id}); if(!d.ok){ notify(d.error||'Xatolik'); loadVideodars(); return; }
  VD.st=d.task; VD.stAns=d.task.items.map(it=>it.type==='open'?'':-1); vdStRender();
}
function vdStRender(wrong){
  const t=VD.st, adm=!!t.admin, L=t.last, box=vdBox();
  let h='<button class="back" type="button" onclick="loadVideodars()">‹ Orqaga</button><h3 class="vdT">⭐ '+vdE(t.title)+'</h3>'+(t.descr?'<p class="vdDescr" style="white-space:pre-wrap">'+vdE(t.descr)+'</p>':'');
  const cl=t.items.filter(x=>x.type!=='open').length;
  h+='<small class="muted">'+(cl?'O‘tish: '+t.pass_pct+'% • ':'')+t.items.length+' ta savol'+(t.max_attempts?' • urinish: '+(t.attempts||0)+'/'+t.max_attempts:' • urinishlar cheklanmagan')+'</small>';
  if(adm) h+='<p class="vdNote">👑 Admin ko‘rinishi: to‘g‘ri javoblar ko‘rsatilgan, natija yozilmaydi.</p>';
  if(L&&!adm){
    h+='<p class="vdNote">Oxirgi topshirish ('+vdE(L.time)+'): '+(L.total?L.score+'/'+L.total+' — '+(L.passed?'✅ o‘tdingiz':'❌ o‘tmadingiz'):'📨 yuborildi')+(L.open_n?' • ochiq javoblarni ustoz tekshiradi':'')+'</p>';
    if(L.comment) h+='<div class="vdCmt">💬 Ustoz: '+vdE(L.comment)+'</div>';
  }
  if(wrong&&wrong.length) h+='<p class="vdErrBox">❌ Noto‘g‘ri javob berilgan savollar: '+wrong.map(i=>i+1).join(', ')+'. Qayta urinib ko‘ring.</p>';
  const locked=!adm&&!t.can_submit, correct=adm?t.items.map(x=>x.type==='open'?null:x.correct):(t.correct||[]), prev=(L&&L.answers)||[];
  h+=t.items.map((q,i)=>{
    if(q.type==='open'){
      const val=locked?(typeof prev[i]==='string'?prev[i]:''):(VD.stAns[i]||'');
      return '<div class="vdQView"><b>'+(i+1)+'. '+vdE(q.q)+'</b><small class="muted">✍️ ochiq savol</small>'+((adm&&q.answer)?'<div class="vdOpt right" style="pointer-events:none">✅ '+vdE(q.answer)+'</div>':'')+((!adm&&locked&&typeof correct[i]==='string')?'<div class="vdOpt right" style="pointer-events:none">✅ To‘g‘ri javob: '+vdE(correct[i])+'</div>':'')+(adm?'':'<textarea rows="3" maxlength="3000" '+(locked?'disabled':'oninput="VD.stAns['+i+']=this.value"')+' placeholder="Javobingizni yozing…">'+vdE(val)+'</textarea>')+'</div>';
    }
    return '<div class="vdQView'+(wrong&&wrong.indexOf(i)>=0?' bad':'')+'"><b>'+(i+1)+'. '+vdE(q.q)+'</b>'+q.options.map((o,j)=>{
      const sel=locked?prev[i]===j:VD.stAns[i]===j, right=correct[i]===j&&(adm||locked);
      return '<button type="button" class="vdOpt'+(right?' right':'')+(sel&&!right?' sel':'')+'" id="so_'+i+'_'+j+'" '+(adm||locked?'disabled':'onclick="vdStPick('+i+','+j+')"')+'><i>'+String.fromCharCode(65+j)+'</i>'+vdE(o)+'</button>'; }).join('')+'</div>';
  }).join('');
  if(!adm&&t.can_submit) h+='<button type="button" class="vdMain" id="vdStBtn" onclick="vdStSubmit()">✅ Javoblarni yuborish</button>';
  else if(!adm) h+='<p class="vdOkBox">'+(t.state==='passed'?'🎉 Topshiriq bajarildi!':'Topshiriq yakunlangan.')+'</p>';
  box.innerHTML=h;
}
function vdStPick(i,j){
  VD.stAns[i]=j; document.querySelectorAll('[id^="so_'+i+'_"]').forEach(b=>b.classList.remove('sel')); const b=$('so_'+i+'_'+j); if(b) b.classList.add('sel');
}
async function vdStSubmit(){
  const t=VD.st; for(let i=0;i<t.items.length;i++){
    const a=VD.stAns[i]; if(t.items[i].type==='open'?String(a||'').trim().length<2:a<0){ notify(t.items[i].type==='open'?(i+1)+'-savolga javob yozing.':(i+1)+'-savolga javob bering.'); return; } }
  const b=$('vdStBtn'); b.disabled=true; const d=await vdApi('/api/vd/st/submit',{id:t.id,answers:VD.stAns}); b.disabled=false;
  if(!d.ok){ notify(d.error||'Xatolik'); return; }
  const r=d.result; vdToast(r.total?'Natija: '+r.score+'/'+r.total:'✅ Yuborildi');
  try{ tg&&tg.HapticFeedback&&tg.HapticFeedback.notificationOccurred(r.passed?'success':'warning'); }catch(e){}
  if(!r.can_retry){ vdStOpen(t.id); return; }
  VD.stAns=t.items.map(it=>it.type==='open'?'':-1); t.attempts=r.attempts; t.can_submit=true; t.last={score:r.score,total:r.total,open_n:r.open_n,passed:r.passed,comment:'',time:'hozir',answers:[]};
  vdStRender(r.wrong); window.scrollTo(0,0);
}

// ===================== v135: MAXSUS TOPSHIRIQ — admin =====================
async function vdAdmTasks(){
  const box=$('vdAdm'); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>';
  const d=await vdApi('/api/vd/st/list',{group_id:VD.gid}); if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  VD.tasks=d.tasks; let h=vdGroupBar();
  if(!VD.groups.length) h+='<div class="vdLock">Avval «👥 O‘quvchilar» bo‘limida guruh oching va o‘quvchi qo‘shing.</div>';
  else h+='<div class="rsAdmin"><button type="button" onclick="vdTaskForm()">➕ Maxsus topshiriq</button></div>';
  h+=d.tasks.length?d.tasks.map(t=>'<div class="vdCard'+(t.published?'':' hid')+'"><b>'+vdE(t.title)+'</b> <span class="vdChip new">'+vdE(vdGname(t.group_id))+'</span>'
    +'<small class="vdMeta">'+(t.closed_n?'🔒 yopiq: '+t.closed_n:'')+(t.closed_n&&t.open_n?' • ':'')+(t.open_n?'✍️ ochiq: '+t.open_n:'')+' • urinish: '+(t.max_attempts||'∞')+'<br>👀 ochgan: '+t.opened+'/'+t.students+' • 📨 topshirgan: '+t.submitted+'/'+t.students+(t.published?'':' • 🔒 yashirin')+'</small>'
    +'<div class="rsRow"><button type="button" class="main" onclick="vdTaskResults('+t.id+')">📊 Natijalar</button><button type="button" onclick="vdStOpen('+t.id+')">▶️ Ko‘rish</button><button type="button" onclick="vdTaskForm('+t.id+')">✏️</button>'
    +'<button type="button" onclick="vdTaskPub('+t.id+','+(t.published?0:1)+')">'+(t.published?'🙈':'👁')+'</button><button type="button" class="del" onclick="vdTaskDel('+t.id+')">🗑</button></div></div>').join('')
    :(VD.groups.length?'<p class="vdEmpty">⭐ Hali maxsus topshiriq yo‘q. «➕ Maxsus topshiriq» ni bosing.</p>':'');
  box.innerHTML=h;
}
async function vdTaskPub(id,v){ await vdApi('/api/vd/admin/task_pub',{id,published:!!v}); vdAdmTasks(); }
async function vdTaskDel(id){ if(!confirm('Topshiriq va barcha natijalari o‘chiriladi. Davom etasizmi?')) return; const d=await vdApi('/api/vd/admin/task_del',{id}); if(!d.ok) notify(d.error||'Xatolik'); vdAdmTasks(); }

function vdTaskForm(id){
  const T=id?VD.tasks.find(x=>x.id===id):null; VD.tEdit=id||0;
  VD.tq=(T?T.items:[]).map(q=>q.type==='open'?{type:'open',q:q.q,answer:q.answer||''}:{type:'closed',q:q.q,options:q.options.slice(),correct:q.correct});
  const gs=VD.groups.map(g=>'<option value="'+g.id+'"'+((T?T.group_id:VD.gid)===g.id?' selected':'')+'>'+vdE(g.name)+'</option>').join('');
  $('vdAdm').innerHTML='<button class="back" type="button" onclick="vdAdminRender()">‹ Orqaga</button><h3>'+(T?'✏️ Maxsus topshiriqni tahrirlash':'⭐ Yangi maxsus topshiriq')+'</h3><div class="vdForm">'
    +'<label>Guruh</label><select id="tfGroup">'+gs+'</select>'
    +'<label>Nomi</label><input id="tfTitle" maxlength="120" placeholder="Masalan: Yakuniy nazorat" value="'+vdE(T?T.title:'')+'">'
    +'<label>Izoh (ixtiyoriy)</label><textarea id="tfDescr" rows="2" maxlength="1000" placeholder="O‘quvchiga ko‘rsatma">'+vdE(T?T.descr:'')+'</textarea>'
    +'<label>Yopiq testdan o‘tish bali (%)</label><input id="tfPass" type="number" min="1" max="100" inputmode="numeric" value="'+(T?T.pass_pct:60)+'">'
    +'<label>Necha marta topshirish mumkin</label><select id="tfAtt">'+[[1,'1 marta'],[2,'2 marta'],[3,'3 marta'],[5,'5 marta'],[0,'Cheklanmagan']].map(a=>'<option value="'+a[0]+'"'+((T?T.max_attempts:1)===a[0]?' selected':'')+'>'+a[1]+'</option>').join('')+'</select>'
    +'<label>Savollar</label><div id="tfQs"></div>'
    +'<div class="rsAdmin"><button type="button" onclick="vdTqAdd(\'closed\')">➕ Yopiq test (variantli)</button><button type="button" onclick="vdTqAdd(\'open\')">➕ Ochiq savol (matnli)</button></div>'
    +'<details class="vdPaste"><summary>⚡ Ochiq savollarni matndan tez kiritish</summary><p class="muted" style="font-size:12px;margin:6px 0">Har qatorda bitta savol. Javob kaliti ixtiyoriy — <b>=&gt;</b> dan keyin yozing, variantlar <b>|</b> bilan:<br><code>1. Poytaxt qaysi? =&gt; Toshkent | Tashkent<br>2. Gap bo‘laklarini yozing</code></p><textarea id="tfPasteO" rows="6" placeholder="1. Poytaxt qaysi? =&gt; Toshkent"></textarea><button type="button" onclick="vdTqImportOpen()">⬇️ Savollarga aylantirish</button></details>'
    +'<details class="vdPaste"><summary>⚡ Yopiq testlarni matndan tez kiritish</summary><p class="muted" style="font-size:12px;margin:6px 0">Savollar orasida bo‘sh qator. Birinchi qator — savol, keyingilari — variantlar. To‘g‘ri variant oldiga <b>*</b> qo‘ying.</p><textarea id="tfPaste" rows="6" placeholder="1. Poytaxt qaysi?&#10;A) Toshkent *&#10;B) Samarqand"></textarea><button type="button" onclick="vdTqImport()">⬇️ Savollarga aylantirish</button></details>'
    +'<label class="vdCheck"><input type="checkbox" id="tfPub"'+(!T||T.published?' checked':'')+'> O‘quvchilarga ko‘rsatilsin</label>'
    +'<button type="button" class="vdMain" id="tfSave" onclick="vdTaskSave()">💾 Saqlash</button></div>';
  vdTqRender();
}
function vdTqCollect(){
  const els=document.querySelectorAll('#tfQs .vdQ'); if(!document.querySelector('#tfQs')) return;
  const out=[]; els.forEach((el,i)=>{
    const old=VD.tq[i]||{type:'closed'};
    if(old.type==='open'){ out.push({type:'open',q:el.querySelector('.vqText').value,answer:(el.querySelector('.vqAns')||{}).value||''}); return; }
    const r=el.querySelector('input[type=radio]:checked');
    out.push({type:'closed',q:el.querySelector('.vqText').value,options:[...el.querySelectorAll('.vqOpt')].map(x=>x.value),correct:r?parseInt(r.value,10):-1});
  }); VD.tq=out;
}
function vdTqRender(){
  const box=$('tfQs'); if(!box) return;
  box.innerHTML=VD.tq.map((q,i)=>{
    const head='<div class="vdQh"><b>'+(i+1)+'-savol • '+(q.type==='open'?'✍️ ochiq':'🔒 yopiq')+'</b><button type="button" class="del" onclick="vdTqDel('+i+')">🗑</button></div>';
    if(q.type==='open') return '<div class="vdQ">'+head+'<textarea class="vqText" rows="2" maxlength="500" placeholder="Savol matni (o‘quvchi o‘z so‘zi bilan javob yozadi)">'+vdE(q.q)+'</textarea><input class="vqAns" maxlength="300" placeholder="To‘g‘ri javob (ixtiyoriy). Bir nechta variant: javob1 | javob2" value="'+vdE(q.answer||'')+'"><small class="muted">Javob yozsangiz — avtomatik tekshiriladi (katta-kichik harf, bo‘sh joy hisobga olinmaydi). Bo‘sh qoldirsangiz — o‘zingiz tekshirasiz.</small></div>';
    return '<div class="vdQ">'+head+'<textarea class="vqText" rows="2" maxlength="500" placeholder="Savol matni">'+vdE(q.q)+'</textarea>'
      +q.options.map((o,j)=>'<div class="vdOptRow"><input type="radio" name="tqc'+i+'" value="'+j+'"'+(q.correct===j?' checked':'')+' title="To‘g‘ri javob"><input class="vqOpt" maxlength="200" placeholder="Variant '+String.fromCharCode(65+j)+'" value="'+vdE(o)+'"><button type="button" onclick="vdTqOptDel('+i+','+j+')">✕</button></div>').join('')
      +'<button type="button" class="vdSmall" onclick="vdTqOptAdd('+i+')">➕ Variant</button><small class="muted"> To‘g‘ri javob yonidagi doirani belgilang.</small></div>';
  }).join('')||'<p class="muted" style="font-size:12.5px">Hali savol yo‘q.</p>';
}
function vdTqAdd(type){ vdTqCollect(); VD.tq.push(type==='open'?{type:'open',q:'',answer:''}:{type:'closed',q:'',options:['','','',''],correct:-1}); vdTqRender(); }
function vdTqDel(i){ vdTqCollect(); VD.tq.splice(i,1); vdTqRender(); }
function vdTqOptAdd(i){ vdTqCollect(); if(VD.tq[i].options.length<6) VD.tq[i].options.push(''); vdTqRender(); }
function vdTqOptDel(i,j){ vdTqCollect(); const q=VD.tq[i]; if(q.options.length<=2){ notify('Kamida 2 ta variant bo‘lsin.'); return; } q.options.splice(j,1); if(q.correct===j) q.correct=-1; else if(q.correct>j) q.correct--; vdTqRender(); }
function vdTqImport(){
  const r=vdParseQs($('tfPaste').value); if(!r.length){ notify('Savol topilmadi. Namunadagidek yozing (savol + kamida 2 variant).'); return; }
  vdTqCollect(); VD.tq=VD.tq.concat(r.map(x=>({type:'closed',q:x.q,options:x.options,correct:x.correct}))); $('tfPaste').value=''; vdTqRender();
  const miss=r.filter(x=>x.correct<0).length; notify('✅ '+r.length+' ta savol qo‘shildi.'+(miss?'\nDiqqat: '+miss+' tasida to‘g‘ri javob belgilanmagan — doirani belgilang.':''));
}
function vdParseOpen(txt){
  return String(txt||'').replace(/\r/g,'').split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{
    const i=l.indexOf('=>'), q=(i<0?l:l.slice(0,i)).replace(/^\d+\s*[.)\-]\s*/,'').trim(), a=i<0?'':l.slice(i+2).trim();
    return {type:'open',q,answer:a};
  }).filter(x=>x.q.length>=2);
}
function vdTqImportOpen(){
  const r=vdParseOpen($('tfPasteO').value); if(!r.length){ notify('Savol topilmadi. Har qatorda bitta savol yozing.'); return; }
  vdTqCollect(); VD.tq=VD.tq.concat(r); $('tfPasteO').value=''; vdTqRender();
  notify('✅ '+r.length+' ta ochiq savol qo‘shildi ('+r.filter(x=>x.answer).length+' tasida javob kaliti bor).');
}
async function vdTaskSave(){
  vdTqCollect();
  const body={id:VD.tEdit||0,group_id:parseInt($('tfGroup').value,10)||0,title:$('tfTitle').value,descr:$('tfDescr').value,pass_pct:parseInt($('tfPass').value,10)||60,max_attempts:parseInt($('tfAtt').value,10),published:$('tfPub').checked,items:VD.tq};
  const b=$('tfSave'); b.disabled=true; const d=await vdApi('/api/vd/admin/task_save',body); b.disabled=false;
  if(!d.ok){ notify(d.error||'Saqlab bo‘lmadi'); return; }
  vdToast('✅ Saqlandi'); VD.gid=body.group_id; await vdRefreshGroups(); vdAdminRender();
}

// ---- natijalar: kim, qachon kirdi, qachon topshirdi, natijasi
const VD_TST={new:['⚪ Ochmagan','new'],opened:['👀 Ochgan, topshirmagan','mid'],sent:['📨 Topshirgan','ok'],passed:['✅ O‘tgan','ok'],failed:['❌ O‘tmagan','warn']};
async function vdTaskResults(id){
  const box=$('vdAdm'); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>'; const d=await vdApi('/api/vd/admin/task_results',{id});
  if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  const T=d.task, rows=d.rows, opened=rows.filter(r=>r.first_open).length, sent=rows.filter(r=>r.attempts>0).length, passed=rows.filter(r=>r.state==='passed').length;
  let h='<button class="back" type="button" onclick="vdAdminRender()">‹ Topshiriqlar</button><h3>📊 '+vdE(T.title)+'</h3>'
    +'<p class="muted" style="margin:0 0 8px">👀 Ochgan: <b>'+opened+'/'+rows.length+'</b> • 📨 Topshirgan: <b>'+sent+'/'+rows.length+'</b>'+(T.closed_n?' • ✅ O‘tgan: <b>'+passed+'</b>':'')+'</p>';
  h+=rows.map(r=>{ const st=VD_TST[r.state]||VD_TST.new;
    return '<div class="vdCard'+(r.active?'':' hid')+'"><div class="vdRowTop"><b>'+vdE(r.name)+'</b><span class="vdChip '+st[1]+'">'+st[0]+'</span></div>'
      +'<small class="vdMeta">'+(r.first_open?'🕒 Birinchi kirgan: '+vdE(r.first_open)+(r.opens>1?' • oxirgi: '+vdE(r.last_open)+' • '+r.opens+' marta ochgan':''):'Hali ochmagan')
      +(r.submitted_at?'<br>📨 Topshirgan: '+vdE(r.submitted_at)+(r.spent?' • ⏱ '+vdE(r.spent):'')+' • urinish: '+r.attempts:'')
      +(r.total?'<br>📝 Yopiq natija: <b>'+r.score+'/'+r.total+'</b>':'')+(r.open_n?'<br>✍️ Ochiq javoblar: '+r.open_n+' ta'+(r.reviewed?' (izoh berilgan)':' (tekshirilmagan)'):'')+'</small>'
      +(r.attempts?'<div class="rsRow"><button type="button" class="main" onclick="vdTaskDetail('+id+','+r.student_id+')">🔍 Javoblarni ko‘rish</button></div>':'')+'</div>'; }).join('')||'<p class="vdEmpty">Bu guruhda o‘quvchi yo‘q.</p>';
  box.innerHTML=h;
}
async function vdTaskDetail(tid,sid){
  const box=$('vdAdm'); box.innerHTML='<p class="vdEmpty">Yuklanmoqda…</p>'; const d=await vdApi('/api/vd/admin/task_detail',{id:tid,student_id:sid});
  if(!d.ok){ box.innerHTML='<p class="vdEmpty">'+vdE(d.error)+'</p>'; return; }
  let h='<button class="back" type="button" onclick="vdTaskResults('+tid+')">‹ Natijalar</button><h3>🔍 '+vdE(d.student.name)+'</h3><p class="muted" style="margin:0 0 8px">'+vdE(d.title)+'</p>';
  h+=d.subs.map((sb,k)=>'<div class="vdCard"><b>'+(d.subs.length-k)+'-urinish</b> <small class="muted">'+(sb.started?'Boshlagan: '+vdE(sb.started)+' • ':'')+'Topshirgan: '+vdE(sb.time)+(sb.spent?' • ⏱ '+vdE(sb.spent):'')+'</small>'
    +(sb.total?'<p style="margin:6px 0"><b>Yopiq natija: '+sb.score+'/'+sb.total+'</b> '+(sb.passed?'✅':'❌')+'</p>':'')
    +sb.items.map((q,i)=>q.type==='open'
      ?'<div class="vdQView"><b>'+(i+1)+'. '+vdE(q.q)+'</b><small class="muted">✍️ ochiq'+(q.key?' • '+(q.ok?'✅ to‘g‘ri':'❌ noto‘g‘ri'):'')+'</small><div class="vdSent"><p style="white-space:pre-wrap;margin:0">'+vdE(q.answer)+'</p>'+(q.key?'<small class="muted">Kalit: '+vdE(q.key)+'</small>':'')+'</div></div>'
      :'<div class="vdQView'+(q.ok?'':' bad')+'"><b>'+(i+1)+'. '+vdE(q.q)+'</b>'+q.options.map((o,j)=>'<div class="vdOpt'+(q.correct===j?' right':(q.chosen===j?' sel':''))+'" style="pointer-events:none"><i>'+String.fromCharCode(65+j)+'</i>'+vdE(o)+(q.chosen===j?' ← javobi':'')+'</div>').join('')+'</div>').join('')
    +(sb.open_n||sb.comment||k===0?'<textarea id="tc'+sb.id+'" rows="2" maxlength="600" placeholder="Izoh yozing (o‘quvchi ko‘radi)">'+vdE(sb.comment)+'</textarea><button type="button" class="vdSmall" onclick="vdTaskReview('+sb.id+')">💬 Izohni saqlash</button>':'')+'</div>').join('');
  box.innerHTML=h;
}
async function vdTaskReview(id){ const d=await vdApi('/api/vd/admin/task_review',{id,comment:$('tc'+id).value}); if(!d.ok){ notify(d.error||'Xatolik'); return; } vdToast('✅ Saqlandi'); }
