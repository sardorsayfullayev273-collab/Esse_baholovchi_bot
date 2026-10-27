// ===== v107: Attestatsiya testlari =====
// Rasmiy tuzilma: 50 savol = 35 asosiy fan + 5 kasbiy standart + 10 pedagogik mahorat; har biri 2 ball; 90 daqiqa.
// Test kiritish — faqat admin. Natija: «Natijalar» kartasi + «Test sinovi natijalari» oynasi (savollar xaritasi).
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const api = (p, o) => apiFetch(apiUrl(p), o);
  const jget = async p => { try { const r = await api(p, { cache: 'no-store' }); return await r.json(); } catch (e) { return { ok: false, error: 'Aloqa xatosi. Qayta urinib ko‘ring.' }; } };
  const jpost = async (p, b) => { try { const r = await api(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }); return await r.json(); } catch (e) { return { ok: false, error: 'Aloqa xatosi. Qayta urinib ko‘ring.' }; } };
  const say = m => { try { notify(m); } catch (e) { alert(m); } };
  const ask = (m, yes) => { if (window.Telegram && Telegram.WebApp && Telegram.WebApp.showConfirm) Telegram.WebApp.showConfirm(m, ok => ok && yes()); else if (confirm(m)) yes(); };
  const LS = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };

  const S = { tab: 'tests', list: null, ex: null, res: null, rev: null };
  const LET = 'ABCD';
  const SEC_NAME = { fan: 'Asosiy fan', kasb: 'Kasbiy standart', ped: 'Pedagogik mahorat' };

  // ------------------------------------------------------------ kirish / tablar
  function init() {
    const w = $('atwTabs'); if (!w) return;
    w.querySelectorAll('button').forEach(b => { b.onclick = () => setTab(b.dataset.t); });
    setTab(S.tab === 'create' ? 'tests' : S.tab);
  }
  function hl() { const w = $('atwTabs'); if (w) w.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.t === (S.tab === 'create' || S.tab === 'obj' ? 'tests' : S.tab))); const mat = $('atMat'), body = $('atBody'); if (mat) mat.classList.toggle('hidden', S.tab !== 'mat'); if (body) body.classList.toggle('hidden', S.tab === 'mat'); }
  function setTab(t) {
    S.tab = t; hl();
    const mat = $('atMat'), body = $('atBody');
    if (mat) mat.classList.toggle('hidden', t !== 'mat');
    if (body) body.classList.toggle('hidden', t === 'mat');
    if (t === 'tests') loadTests(); else if (t === 'mine') loadMine(); else if (t === 'create') renderCreate(); else if (t === 'obj') loadObj();
  }

  // ------------------------------------------------------------ testlar ro'yxati
  async function loadTests() {
    const b = $('atBody'); if (!b) return;
    b.innerHTML = '<div class="atCard atMut">Yuklanmoqda…</div>';
    const d = await jget('/api/att/list'); S.list = d;
    if (!d.ok) { b.innerHTML = '<div class="atErr">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    const st = d.structure || {};
    let h = '<div class="atCard"><h3>Rasmiy tuzilma</h3><div class="atMut">' + (st.total || 50) + ' ta test topshirig‘i • ' + (st.minutes || 90) + ' daqiqa • har bir to‘g‘ri javob ' + (st.points || 2) + ' ball • jami ' + (st.max || 100) + ' ball</div>' +
      '<div class="atChips"><span class="atChip">1–35 Asosiy fan</span><span class="atChip">36–40 Kasbiy standart</span><span class="atChip">41–50 Pedagogik mahorat</span></div></div>';
    if (d.is_admin) {
      h += '<div class="atCard"><div class="atRow"><button class="atBtn grow" id="atNew">＋ Test kiritish</button><button class="atBtn sec" id="atObjBtn">💬 E‘tirozlar</button></div>' +
        '<div class="atRow" style="margin-top:10px"><span class="atMut grow">Foydalanuvchilar uchun: <b>' + (d.public ? 'OCHIQ' : 'yopiq (faqat admin)') + '</b></span><button class="atBtn sec" id="atPub">' + (d.public ? 'Yopish' : 'Ochish') + '</button></div></div>';
    }
    if (d.locked) h += '<div class="atCard"><h3>🚧 Jarayonda</h3><div class="atMut">Attestatsiya testlari tez orada ochiladi.</div></div>';
    else if (!d.items.length) h += '<div class="atCard atMut">Hozircha test yo‘q.' + (d.is_admin ? ' «Test kiritish» tugmasi orqali 50 ta savolni joylang.' : '') + '</div>';
    d.items.forEach(t => {
      h += '<div class="atCard"><h3>' + esc(t.title) + '</h3><div class="atMut">' + esc(t.subject) + ' • 50 savol • ' + t.minutes + ' daqiqa' + (t.published ? '' : ' • <b>yashirin</b>') + (t.attempts != null ? ' • topshirilgan: ' + t.attempts : '') + '</div>' +
        '<div class="atRow" style="margin-top:12px"><button class="atBtn grow" data-go="' + esc(t.code) + '">' + (t.in_progress ? '▶ Davom ettirish' : 'Boshlash') + '</button>' +
        (d.is_admin ? '<button class="atBtn sec" data-pub="' + esc(t.code) + '" data-on="' + (t.published ? 0 : 1) + '">' + (t.published ? 'Yashirish' : 'Ko‘rsatish') + '</button><button class="atBtn red" data-del="' + esc(t.code) + '">🗑</button>' : '') + '</div></div>';
    });
    b.innerHTML = h;
    b.querySelectorAll('[data-go]').forEach(x => x.onclick = () => startExam(x.dataset.go));
    b.querySelectorAll('[data-del]').forEach(x => x.onclick = () => ask('Test va uning barcha natijalari o‘chiriladi. Davom etasizmi?', async () => { const r = await jpost('/api/att/delete', { code: x.dataset.del }); if (!r.ok) say(r.error); loadTests(); }));
    b.querySelectorAll('[data-pub]').forEach(x => x.onclick = async () => { const r = await jpost('/api/att/publish', { code: x.dataset.pub, on: x.dataset.on === '1' }); if (!r.ok) say(r.error); loadTests(); });
    const nw = $('atNew'); if (nw) nw.onclick = () => setTab('create');
    const ob = $('atObjBtn'); if (ob) ob.onclick = () => setTab('obj');
    const pb = $('atPub'); if (pb) pb.onclick = async () => { const r = await jpost('/api/att/public', { on: !d.public }); if (!r.ok) say(r.error); loadTests(); };
  }

  // ------------------------------------------------------------ test kiritish (admin)
  function renderCreate() {
    const b = $('atBody'); if (!b) return;
    b.innerHTML = '<button class="atBtn sec" id="atBk" style="margin-bottom:12px">‹ Testlar</button><div class="atCard"><h3>Yangi test kiritish</h3>' +
      '<input class="atIn" id="atTitle" maxlength="120" placeholder="Test nomi (masalan: Ona tili — 1-variant)">' +
      '<input class="atIn" id="atSubj" maxlength="80" placeholder="Fan (ixtiyoriy)" value="Ona tili va adabiyot">' +
      '<div class="atMut" style="margin:8px 0 4px">Jami <b>50 ta</b> savol: 1–35 fan, 36–40 kasbiy standart, 41–50 pedagogik mahorat. Format:</div>' +
      '<div class="atPre">1. Savol matni?\nA) birinchi variant\nB) ikkinchi variant\nC) uchinchi variant\nD) to‘rtinchi variant\nJavob: B</div>' +
      '<div class="atMut" style="margin:6px 0">To‘g‘ri variantni <b>*B)</b> deb belgilash yoki oxirida <b>Javoblar: 1-A 2-C 3-B …</b> yozish ham mumkin.</div>' +
      '<textarea class="atTa" id="atTxt" placeholder="50 ta savolni shu yerga joylang"></textarea><div id="atMsg"></div>' +
      '<div class="atRow"><button class="atBtn sec grow" id="atChk">✔ Tekshirish</button><button class="atBtn grow" id="atSave">Saqlash</button></div></div>';
    $('atBk').onclick = () => setTab('tests');
    const run = async dry => {
      const text = $('atTxt').value, title = $('atTitle').value.trim();
      if (!text.trim()) { say('Savollar matnini joylang.'); return; }
      if (!dry && !title) { say('Test nomini kiriting.'); return; }
      const btn = $(dry ? 'atChk' : 'atSave'); btn.disabled = true;
      const r = await jpost('/api/att/create', { title, subject: $('atSubj').value, text, dry_run: dry });
      btn.disabled = false;
      const m = $('atMsg');
      if (dry) {
        if (r.ok) m.innerHTML = '<div class="atOkBox">✅ ' + r.count + ' ta savol to‘g‘ri tanildi (fan ' + r.split.fan + ' • kasbiy ' + r.split.kasb + ' • pedagogik ' + r.split.ped + ')</div>';
        else m.innerHTML = '<div class="atErr">' + (r.errors || [r.error || 'Xatolik']).map(esc).join('<br>') + (r.count ? '<br><b>Tanilgan savollar: ' + r.count + '</b>' : '') + '</div>';
      } else if (r.ok) { say('Test saqlandi: ' + r.code); setTab('tests'); }
      else m.innerHTML = '<div class="atErr">' + esc(r.error || 'Xatolik') + '</div>';
    };
    $('atChk').onclick = () => run(true); $('atSave').onclick = () => run(false);
  }

  // ------------------------------------------------------------ e'tirozlar (admin)
  async function loadObj() {
    const b = $('atBody'); if (!b) return;
    b.innerHTML = '<button class="atBtn sec" id="atBk" style="margin-bottom:12px">‹ Testlar</button><div id="atObjL" class="atMut">Yuklanmoqda…</div>';
    $('atBk').onclick = () => setTab('tests');
    const d = await jget('/api/att/objections'); const L = $('atObjL');
    if (!d.ok) { L.innerHTML = '<div class="atErr">' + esc(d.error) + '</div>'; return; }
    if (!d.items.length) { L.innerHTML = '<div class="atCard">Ko‘rib chiqilmagan e‘tiroz yo‘q 👍</div>'; return; }
    L.innerHTML = d.items.map(o => '<div class="atCard"><div class="atMut">' + esc(o.test) + ' • ' + o.qn + '-savol • foydalanuvchi ' + o.user_id + '</div><div class="atQt" style="margin-top:8px">' + esc(o.q) + '</div>' +
      o.o.map((t, i) => '<div class="atOpt ' + (i === o.correct ? 'ok' : (i === o.given ? 'bad' : '')) + '" style="pointer-events:none"><b>' + LET[i] + '</b><span>' + esc(t) + '</span></div>').join('') +
      '<div class="atMut" style="margin:6px 0">Kalit: <b>' + LET[o.correct] + '</b> • Foydalanuvchi: <b>' + (o.given == null ? 'javob yo‘q' : LET[o.given]) + '</b></div><div class="atErr" style="background:#fff7e8;color:#8a5a00">' + esc(o.reason) + '</div>' +
      '<div class="atRow"><button class="atBtn grow" data-d="' + o.id + '" data-a="1">✅ Qabul (+2 ball)</button><button class="atBtn red grow" data-d="' + o.id + '" data-a="0">Rad etish</button></div></div>').join('');
    L.querySelectorAll('[data-d]').forEach(x => x.onclick = async () => { const r = await jpost('/api/att/objection/decide', { id: +x.dataset.d, accept: x.dataset.a === '1' }); if (!r.ok) say(r.error); loadObj(); });
  }

  // ------------------------------------------------------------ natijalarim
  async function loadMine() {
    const b = $('atBody'); if (!b) return;
    b.innerHTML = '<div class="atCard atMut">Yuklanmoqda…</div>';
    const d = await jget('/api/att/mine');
    if (!d.ok) { b.innerHTML = '<div class="atErr">' + esc(d.error || 'Bu bo‘lim hozircha yopiq.') + '</div>'; return; }
    if (!d.items.length) { b.innerHTML = '<div class="atCard atMut">Hali test topshirmagansiz.</div>'; return; }
    b.innerHTML = d.items.map(x => '<button class="atCard" style="display:block;width:100%;text-align:left" data-r="' + x.id + '"><h3>' + esc(x.title) + '</h3><div class="atMut">' + esc(x.date) + ' • <b>' + x.total + ' / ' + x.max + ' ball</b></div></button>').join('');
    b.querySelectorAll('[data-r]').forEach(x => x.onclick = () => showResult(+x.dataset.r));
  }

  // ------------------------------------------------------------ imtihon
  function fmtT(sec) { sec = Math.max(0, sec | 0); const m = (sec / 60) | 0, s = sec % 60; return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0'); }
  async function startExam(code) {
    const d = await jpost('/api/att/start', { code });
    if (!d.ok) { say(d.error || 'Testni boshlab bo‘lmadi.'); return; }
    S.ex = { id: d.attempt_id, q: d.questions, ans: d.answers || {}, i: 0, deadline: d.deadline_ts, off: d.server_ts - Date.now() / 1000, t: null, sv: null, nav: false, done: false };
    let w = $('atExam'); if (!w) { w = document.createElement('div'); w.id = 'atExam'; document.body.appendChild(w); }
    w.classList.remove('hidden'); document.body.style.overflow = 'hidden';
    const first = S.ex.q.findIndex(q => S.ex.ans[String(q.n)] == null); S.ex.i = first < 0 ? 0 : first;
    drawExam();
    S.ex.t = setInterval(tick, 500); tick();
  }
  const left = () => S.ex.deadline - (Date.now() / 1000 + S.ex.off);
  function tick() {
    if (!S.ex || S.ex.done) return;
    const el = $('atTm'), l = left();
    if (el) { el.textContent = fmtT(l); el.classList.toggle('low', l < 300); }
    if (l <= 0) finishExam(true);
  }
  function drawExam() {
    const e = S.ex, w = $('atExam'); if (!e || !w) return;
    const q = e.q[e.i], n = Object.keys(e.ans).length, a = e.ans[String(q.n)];
    let h = '<div class="atTop"><button class="atX" id="atClose">✕</button><div class="atMut"><b>' + (e.i + 1) + ' / ' + e.q.length + '</b> • javob: ' + n + '</div><div class="atTimer" id="atTm">' + fmtT(left()) + '</div></div>' +
      '<div class="atProg"><i style="width:' + Math.round(n * 100 / e.q.length) + '%"></i></div>' +
      '<div class="atQ"><span class="atSecTag">' + SEC_NAME[q.section] + '</span><p class="atQt">' + q.n + '. ' + esc(q.q) + '</p>' +
      q.o.map((t, i) => '<button class="atOpt' + (a === i ? ' sel' : '') + '" data-o="' + i + '"><b>' + LET[i] + '</b><span>' + esc(t) + '</span></button>').join('') + '</div>' +
      '<div class="atNav"><button class="atBtn sec" id="atPv"' + (e.i ? '' : ' disabled') + '>‹ Oldingi</button><button class="atBtn sec" id="atMp">▦ Savollar</button><button class="atBtn" id="atNx">' + (e.i < e.q.length - 1 ? 'Keyingi ›' : 'Yakunlash') + '</button></div>';
    if (e.nav) {
      h += '<div class="atCard"><div class="atGrid">' + e.q.map((x, i) => '<button data-g="' + i + '" class="' + (e.ans[String(x.n)] != null ? 'done' : '') + (i === e.i ? ' cur' : '') + '">' + x.n + '</button>').join('') + '</div>' +
        '<button class="atBtn blue" id="atFin" style="width:100%">Testni yakunlash</button></div>';
    }
    w.innerHTML = h;
    w.querySelectorAll('[data-o]').forEach(x => x.onclick = () => { e.ans[String(q.n)] = +x.dataset.o; scheduleSave(); if (e.i < e.q.length - 1) { setTimeout(() => { if (S.ex === e && e.q[e.i] === q) { e.i++; drawExam(); } }, 220); } drawExam(); });
    w.querySelectorAll('[data-g]').forEach(x => x.onclick = () => { e.i = +x.dataset.g; e.nav = false; drawExam(); window.scrollTo(0, 0); w.scrollTop = 0; });
    $('atPv').onclick = () => { if (e.i) { e.i--; drawExam(); } };
    $('atNx').onclick = () => { if (e.i < e.q.length - 1) { e.i++; drawExam(); } else { e.nav = true; drawExam(); } };
    $('atMp').onclick = () => { e.nav = !e.nav; drawExam(); };
    $('atClose').onclick = () => ask('Chiqsangiz javoblaringiz saqlanadi, lekin vaqt ketaveradi. Chiqasizmi?', () => closeExam(true));
    const f = $('atFin'); if (f) f.onclick = () => { const miss = e.q.length - Object.keys(e.ans).length; ask((miss ? miss + ' ta savolga javob bermadingiz. ' : '') + 'Testni yakunlaysizmi?', () => finishExam(false)); };
  }
  function scheduleSave() {
    const e = S.ex; if (!e) return; clearTimeout(e.sv);
    e.sv = setTimeout(() => { jpost('/api/att/save', { attempt_id: e.id, answers: e.ans }); }, 700);
  }
  function closeExam(keep) {
    const e = S.ex; if (e) { clearInterval(e.t); clearTimeout(e.sv); if (keep) jpost('/api/att/save', { attempt_id: e.id, answers: e.ans }); }
    S.ex = null; const w = $('atExam'); if (w) { w.classList.add('hidden'); w.innerHTML = ''; } document.body.style.overflow = '';
    if (S.tab === 'tests') loadTests();
  }
  async function finishExam(auto) {
    const e = S.ex; if (!e || e.done) return; e.done = true; clearInterval(e.t); clearTimeout(e.sv);
    if (auto) say('Vaqt tugadi. Test avtomatik yakunlandi.');
    const r = await jpost('/api/att/submit', { attempt_id: e.id, answers: e.ans });
    if (!r.ok) { e.done = false; e.t = setInterval(tick, 500); say(r.error || 'Yuborib bo‘lmadi. Internetni tekshirib qayta urining.'); return; }
    const id = e.id; S.tab = 'mine'; closeExam(false); hl(); showResult(id);
  }

  // ------------------------------------------------------------ natija (rasmdagidek)
  async function showResult(id) {
    const d = await jget('/api/att/result/' + id);
    if (!d.ok) { say(d.error || 'Natija topilmadi.'); return; }
    S.res = d; S.rev = null;
    const b = $('atBody'); if (!b) return;
    const cur = LS.get('att_cur') || '';
    b.innerHTML = '<div class="atResHead"><button class="atBtn sec" id="atBk">← Orqaga</button><span class="atCode">' + esc(d.title) + '</span></div>' +
      '<div class="atTag">Testda qatnashdi</div>' +
      '<div class="atCard atRes"><h3>Natijalar</h3>' +
      '<div class="atLbl">Asosiy fan / ball:</div><div class="atVal">' + d.main.total + ' ta savol / ' + d.main.ok + ' ta to‘g‘ri - ' + d.main.ball + ' ball</div>' +
      '<div class="atLbl">Qo‘shimcha fan / ball:</div><div class="atVal">' + d.ped.total + ' ta savol / ' + d.ped.ok + ' ta to‘g‘ri - ' + d.ped.ball + ' ball</div>' +
      '<div class="atLbl">Jami:</div><div class="atVal">' + d.total + ' ball</div>' +
      '<div class="atLbl">E‘tirozlar soni / ball:</div><div class="atVal">' + d.objections.count + ' ta / ' + d.objections.ball + ' ball' + (d.objections.pending ? ' <span class="atMut">(' + d.objections.pending + ' ta ko‘rib chiqilmoqda)</span>' : '') + '</div>' +
      '<div style="margin-top:14px"><button class="atBtn blue" id="atDet">👁 Batafsil</button></div>' +
      '<div class="atDec"><div class="atLbl">Attestatsiya yakunlari to‘g‘risidagi qaror (buyruq) loyihasi:</div>' +
      '<select class="atSel" id="atCur"><option value="">Hozirgi toifangizni tanlang…</option>' + Object.keys(d.cat_names).map(k => '<option value="' + k + '"' + (cur === k ? ' selected' : '') + '>' + esc(d.cat_names[k]) + '</option>').join('') + '</select>' +
      '<div class="atVal" id="atDecT"></div></div></div>';
    $('atBk').onclick = () => setTab('mine');
    $('atDet').onclick = openModal;
    const dec = () => {
      const c = $('atCur').value; LS.set('att_cur', c);
      const t = $('atDecT'); let h = '';
      if (c && d.rules[c]) {
        const r = d.rules[c].find(x => d.total >= x.min);
        if (r) h = '<b>' + (r.text.indexOf('o‘tdi') > 0 ? 'QAROR: ' : 'QARORSIZ: ') + '</b>' + esc(r.text);
      } else h = d.cat_by_score ? 'Ball bo‘yicha erishilgan daraja: <b>' + esc(d.cat_names[d.cat_by_score]) + '</b>' : '<b>Toifa uchun yetarli emas</b> (kamida 55 ball kerak).';
      h += '<div class="atMut" style="margin-top:6px">Chegaralar: 80 — oliy, 70 — birinchi, 60 — ikkinchi, 55 — mutaxassis. Bu — taxminiy hisob, rasmiy qaror emas.' + (d.note86 ? ' ' + esc(d.note86) : '') + '</div>';
      t.innerHTML = h;
    };
    $('atCur').onchange = dec; dec();
    window.scrollTo(0, 0);
  }

  function ring(p) {
    const r = 48, c = 2 * Math.PI * r, off = c * (1 - Math.min(100, p) / 100);
    return '<svg viewBox="0 0 112 112"><circle cx="56" cy="56" r="' + r + '" fill="none" stroke="#fff" stroke-width="10"/><circle cx="56" cy="56" r="' + r + '" fill="none" stroke="#2d8cf0" stroke-width="10" stroke-linecap="round" stroke-dasharray="' + c.toFixed(1) + '" stroke-dashoffset="' + off.toFixed(1) + '"/></svg>';
  }
  function tilesOf(d, key) {
    return d.tiles.filter(t => t.section === key).map(t => '<button data-n="' + t.n + '" class="' + (t.section === 'kasb' ? 'ci ' : '') + (t.ok ? '' : 'bad') + '">' + t.n + (t.obj ? '<i>!</i>' : '') + '</button>').join('');
  }
  function openModal() {
    const d = S.res; if (!d) return;
    let m = $('atModal'); if (!m) { m = document.createElement('div'); m.id = 'atModal'; document.body.appendChild(m); }
    m.classList.remove('hidden'); document.body.style.overflow = 'hidden';
    m.innerHTML = '<div class="atSheet"><div class="atSheetHd"><h3>Test sinovi natijalari</h3><button class="atX" id="atMx">✕</button></div>' +
      '<div class="atSumm"><div class="atRing">' + ring(d.percent) + '<div class="c"><b>' + d.percent + '%</b><span>Bajarildi</span></div></div>' +
      '<div class="atInfo"><div class="sc">Jami ball: <b>' + d.total + '</b></div><div>📅 Sanasi: <b>' + esc(d.date) + '</b></div><div>▶️ Boshlandi: <b>' + esc(d.start) + '</b></div><div>⏹ Yakunlandi: <b>' + esc(d.end) + '</b></div></div></div>' +
      '<div class="atLeg"><div><span class="sh"></span>To‘g‘ri javoblar</div><div><span class="sh bd"></span>Noto‘g‘ri javoblar</div><div><span class="sh ci"></span>Kasbiy standart</div><div><span class="sh in">ⓘ</span>E‘tirozlar</div></div>' +
      '<div class="atSecT">Asosiy fan</div><div class="atTiles">' + tilesOf(d, 'fan') + '</div>' +
      '<div class="atSecT">Kasbiy standart</div><div class="atTiles">' + tilesOf(d, 'kasb') + '</div>' +
      '<div class="atSecT">Pedagogik mahorat</div><div class="atTiles">' + tilesOf(d, 'ped') + '</div>' +
      '<div class="atRv" id="atRv"><div class="atMut">Savolni ko‘rish uchun raqamni bosing.</div></div></div>';
    $('atMx').onclick = closeModal; m.onclick = ev => { if (ev.target === m) closeModal(); };
    m.querySelectorAll('[data-n]').forEach(x => x.onclick = () => showQ(+x.dataset.n));
  }
  function closeModal() { const m = $('atModal'); if (m) { m.classList.add('hidden'); m.innerHTML = ''; } document.body.style.overflow = ''; }

  async function showQ(n) {
    const box = $('atRv'); if (!box) return;
    if (!S.rev) { box.innerHTML = '<div class="atMut">Yuklanmoqda…</div>'; const r = await jget('/api/att/review/' + S.res.attempt_id); if (!r.ok) { box.innerHTML = '<div class="atErr">' + esc(r.error) + '</div>'; return; } S.rev = r.items; }
    const it = S.rev[n - 1], t = S.res.tiles[n - 1];
    let h = '<span class="atSecTag">' + SEC_NAME[it.section] + '</span><p class="atQt">' + it.n + '. ' + esc(it.q) + '</p>' +
      it.o.map((x, i) => '<div class="atOpt ' + (i === it.correct ? 'ok' : (i === it.given ? 'bad' : '')) + '" style="pointer-events:none"><b>' + LET[i] + '</b><span>' + esc(x) + '</span></div>').join('');
    h += '<div class="atMut">Sizning javobingiz: <b>' + (it.given == null ? 'javob berilmagan' : LET[it.given]) + '</b> • To‘g‘ri javob: <b>' + LET[it.correct] + '</b></div>';
    if (it.obj) h += '<div class="atObjSt">ⓘ E‘tiroz: ' + ({ pending: 'ko‘rib chiqilmoqda', accepted: 'qabul qilindi (+2 ball)', rejected: 'rad etildi' }[it.obj] || it.obj) + '</div>';
    else if (it.given !== it.correct && S.res.objections.left > 0) h += '<div style="margin-top:10px"><textarea class="atIn" id="atObjTx" rows="3" maxlength="500" placeholder="E‘tiroz sababi (kamida 5 belgi)"></textarea><button class="atBtn red" id="atObjGo" style="width:100%">ⓘ E‘tiroz bildirish</button></div>';
    box.innerHTML = h; box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    const go = $('atObjGo');
    if (go) go.onclick = async () => {
      go.disabled = true; const r = await jpost('/api/att/objection', { attempt_id: S.res.attempt_id, qn: n, reason: $('atObjTx').value });
      if (!r.ok) { go.disabled = false; say(r.error || 'Yuborib bo‘lmadi.'); return; }
      say('E‘tiroz yuborildi. Admin ko‘rib chiqadi.'); const id = S.res.attempt_id; closeModal(); await showResult(id); openModal(); showQ(n);
    };
  }

  // ------------------------------------------------------------ ulash
  const _os = window.openSection;
  if (typeof _os === 'function') window.openSection = function (id) { const r = _os.apply(this, arguments); if (id === 'attestwin') { try { init(); } catch (e) { console.error(e); } } return r; };
  window.attInit = init;
})();
