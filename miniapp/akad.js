// ===== v123: Sardor Sayfullayev — Mumtoz tahlil maktabi (pullik: g‘azal tabdili + she’riy san’atlar) =====
// Savollar serverda turadi va bittalab beriladi; ekranda foydalanuvchi ID si suv belgisi bo‘lib turadi; matnni nusxalash o‘chirilgan.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let ST = null, CUR = null;
  const TITLE = 'Sardor Sayfullayev: Mumtoz tahlil maktabi';

  async function req(path, body) {
    try {
      const opt = body === undefined ? { cache: 'no-store' } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
      const r = await apiFetch(apiUrl(path), opt); let j = {}; try { j = await r.json(); } catch (e) {}
      j._s = r.status; return j;
    } catch (e) { return { ok: false, error: 'Aloqa xatosi. Qayta urinib ko‘ring.', _s: 0 }; }
  }
  function root() { return $('akadBody'); }
  function ensureMain() {
    if ($('akad')) return;
    const m = document.createElement('main'); m.id = 'akad'; m.className = 'page hidden';
    m.innerHTML = '<button class="back" onclick="goHome()">‹ Bosh sahifa</button><div id="akadWm" class="akWm"></div><div id="akadBody"></div>';
    ($('more') && $('more').parentNode ? $('more').parentNode : document.body).appendChild(m);
    ['contextmenu', 'copy', 'cut', 'selectstart', 'dragstart'].forEach(ev => m.addEventListener(ev, e => { if (e.target && /^(TEXTAREA|INPUT)$/.test(e.target.tagName)) return; e.preventDefault(); }));
  }
  function watermark() {
    const t = (ST && ST.wm) || 'ID', w = $('akadWm'); if (!w) return;
    const svg = '<svg xmlns="http://www.w3.org/2000/svg" width="190" height="130"><text x="10" y="70" font-size="16" font-family="Arial" fill="#08402f" transform="rotate(-25 95 65)">' + esc(t) + '</text></svg>';
    w.style.backgroundImage = 'url("data:image/svg+xml;utf8,' + encodeURIComponent(svg) + '")';
  }
  async function loadState() { ST = await req('/api/akad/state'); return ST; }

  function injectCard() {   // v123: bosh sahifadagi «Mumtoz tahlil maktabi» kartasi (Tayyorlov o‘rnida) — bo‘lim ochiq bo‘lsa ko‘rinadi
    const b = $('akadHome'); if (b) b.classList.remove('hidden');
  }
  async function init() {
    if (typeof apiFetch !== 'function') { setTimeout(init, 500); return; }
    const s = await loadState(); if (s && s.visible) injectCard();
  }

  window.openAkad = async function () {
    ensureMain(); openSection('akad'); root().innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    const s = await loadState();
    if (!s || !s.visible) { root().innerHTML = '<div class="result"><h3>🚧 Tez orada</h3><p class="muted">Bo‘lim hozircha jarayonda.</p></div>'; return; }
    watermark(); home();
  };

  function pay() {
    const bot = (typeof ME !== 'undefined' && ME && ME.bot_username) || '';
    if (!bot) { notify('To‘lov uchun botdagi chatga o‘ting.'); return; }
    const url = 'https://t.me/' + bot + '?start=pay_akad_pro';
    if (tg && tg.openTelegramLink) { tg.openTelegramLink(url); setTimeout(() => { try { tg.close(); } catch (e) {} }, 400); } else window.open(url, '_blank');
  }
  window.akadPay = pay;
  const fmt = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  function payBox() {
    if (ST.access) return '';
    return '<div class="akPay"><b>🔒 To‘liq kirish — ' + fmt(ST.price) + ' so‘m / ' + ST.days + ' kun</b><ul><li>G‘azal tabdili trenajyori: ' + ST.tab_total + ' ta bayt, 12 ta qoida</li><li>She’riy san’atlar: 38 san’at, ' + ST.total + ' ta amaliy bayt</li><li>AI tekshiruvi: xatongiz qaysi qoidadan ekanini ko‘rsatadi</li><li>Xatolar daftari va natijalar</li></ul><button class="primaryAction" onclick="akadPay()">💳 Obuna bo‘lish</button><p class="muted" style="margin:8px 0 0">Har bir qismdan 1 ta namuna bepul. To‘lov karta orqali, tasdiqlangach bo‘lim avtomatik ochiladi.</p></div>';
  }
  function home() {
    CUR = null; const s = ST, pct = s.total ? Math.round(100 * s.done / s.total) : 0;
    root().innerHTML =
      '<div class="akHero"><h2>🎓 Mumtoz tahlil maktabi</h2><p>Mumtoz adabiyot bo‘yicha mutaxassis <b>Sardor Sayfullayev</b> usuli: baytni o‘qishdan tabdil va tahlilgacha, qadamma-qadam.</p>' +
      '<div class="akBar"><i style="width:' + pct + '%"></i></div><p style="margin-top:6px">Bajarilgan: ' + s.done + ' / ' + s.total + (s.access ? ' • to‘g‘ri: ' + s.right : '') + '</p></div>' +
      (s.admin && !s.open ? '<div class="result" style="margin:0 0 12px"><b>🚧 Bo‘lim yopiq</b><p class="muted">Faqat siz (admin) ko‘rasiz. Ochish: /mumtoz_och</p></div>' : '') +
      (s.access ? '<p class="muted">✅ ' + (s.admin ? 'Admin kirishi' : 'Obuna faol: ' + esc(s.until) + ' gacha (' + s.days_left + ' kun)') + ' • bugungi savollar qoldig‘i: ' + (s.admin ? '∞' : s.left_today) + '</p>' : '') +
      '<button class="akCard" onclick="akadTabHome()"><div class="akRow"><b>📖 G‘azal tabdili</b><span class="akTag' + (s.access ? '' : ' pro') + '">' + (s.access ? s.tab_total + ' bayt' : '1 namuna bepul') + '</span></div><div class="muted" style="margin-top:6px">Qoidani toping, baytni tabdil qiling, AI xatoni qoida bo‘yicha tushuntiradi.</div></button>' +
      '<button class="akCard" onclick="akadSanHome()"><div class="akRow"><b>✨ She’riy san’atlar</b><span class="akTag' + (s.access ? '' : ' pro') + '">' + (s.access ? s.total + ' savol' : '1 namuna bepul') + '</span></div><div class="muted" style="margin-top:6px">Nazariya kartalari va amaliy baytlar: ajratilgan so‘zdan san’atni aniqlang.</div></button>' +
      (s.admin ? '<button class="akCard" onclick="akadAdmin()"><b>🛠 Muharrir (admin)</b><div class="muted">Savol va ma’lumot qo‘shish, xatoni tuzatish, o‘chirish — shu yerning o‘zida.</div></button>' : '') + payBox();
  }
  window.akadHome = home;

  // ------------------------------------------------ SHE'RIY SAN'ATLAR
  window.akadSanHome = function () {
    let h = '<button class="back" onclick="akadHome()">‹ Mumtoz tahlil maktabi</button><h2>✨ She’riy san’atlar</h2>';
    h += '<button class="akCard" onclick="akadTheory()"><b>📘 Nazariya kartalari</b><div class="muted">Har bir san’atning ta’rifi va tuzoqlari.</div></button>';
    h += '<button class="akCard" onclick="akadSan(0)"><b>🎯 Amaliyot' + (ST.access ? '' : ' (bepul namuna)') + '</b><div class="muted">Baytni o‘qing, ajratilgan so‘zga qarab san’atni toping.</div></button>';
    if (ST.access) h += (ST.lessons || []).map(l => '<button class="akCard" onclick="akadSan(' + l.dars + ')"><div class="akRow"><b>' + l.dars + '-dars</b><span class="akTag">' + l.n + ' bayt</span></div><div class="muted">' + esc(l.nom) + '</div></button>').join('');
    root().innerHTML = h + payBox();
  };
  window.akadTheory = async function () {
    root().innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    const d = await req('/api/akad/theory'); if (!d.ok) { root().innerHTML = '<div class="result">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    root().innerHTML = '<button class="back" onclick="akadSanHome()">‹ She’riy san’atlar</button><h2>📘 Nazariya</h2>' +
      d.items.map(x => '<div class="word ' + (x.locked ? 'akLock' : '') + '" style="margin-bottom:8px"><strong>' + (x.locked ? '🔒 ' : '') + esc(x.art) + '</strong>' + (x.locked ? '<div class="muted">Obuna bilan ochiladi</div>' : '<div class="muted" style="color:#0d2b22">' + esc(x.text) + '</div>') + (ST.admin ? '<button class="akSm" data-id="' + esc(x.art) + '" onclick="akadEditArt(this.dataset.id, akadTheory)">✏️ Tuzatish (admin)</button>' : '') + '</div>').join('') + (ST.admin ? '<button class="primaryAction" onclick="akadEditArt(\'\', akadTheory)">➕ Yangi san’at (admin)</button>' : '') + payBox();
  };
  function mark(verse, marks) {
    let t = esc(verse);
    (marks || []).slice().sort((a, b) => b.length - a.length).forEach(m => {
      const e = esc(m).trim(); if (!e) return; const i = t.indexOf(e); if (i < 0 || /<mark>/.test(t.slice(Math.max(0, i - 6), i))) return;
      t = t.slice(0, i) + '<mark>' + e + '</mark>' + t.slice(i + e.length);
    });
    return t;
  }
  window.akadSan = async function (dars) {
    ST._dars = dars || 0;
    root().innerHTML = '<div class="word">⏳ Savol yuklanmoqda...</div>';
    const d = await req('/api/akad/san/next?dars=' + (dars || 0));
    if (d.need_pay) { root().innerHTML = '<button class="back" onclick="akadSanHome()">‹ She’riy san’atlar</button><div class="result"><h3>🔒 Bepul namuna ishlandi</h3><p class="muted">Davom etish uchun obuna bo‘ling.</p></div>' + payBox(); return; }
    if (!d.ok) { root().innerHTML = '<button class="back" onclick="akadSanHome()">‹ She’riy san’atlar</button><div class="result">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    CUR = d; CUR.dars_filter = ST._dars || 0;
    root().innerHTML = '<button class="back" onclick="akadSanHome()">‹ She’riy san’atlar</button><div class="akRow"><span class="t akTag">' + d.dars + '-dars • ' + d.raqam + '-bayt</span>' + (d.free ? '<span class="akTag pro">Bepul namuna</span>' : '') + '</div>' +
      '<h3 style="margin:10px 0 0">Baytda qaysi she’riy san’at qo‘llangan?</h3><div class="akVerse">' + mark(d.bayt, d.ajratilgan) + '</div><div id="akOpts">' +
      d.options.map((o, i) => '<button class="akOpt" data-o="' + esc(o) + '" onclick="akadPick(this)">' + 'ABCD'[i] + ') ' + esc(o) + '</button>').join('') + '</div><div id="akFb"></div>';
  };
  window.akadPick = async function (btn) {
    if (!CUR || CUR.done) return; CUR.done = true; const choice = btn.getAttribute('data-o');
    const r = await req('/api/akad/san/answer', { qid: CUR.qid, choice });
    if (!r.ok) { CUR.done = false; notify(r.error || 'Xatolik'); return; }
    document.querySelectorAll('#akOpts .akOpt').forEach(b => { const o = b.getAttribute('data-o'); if (o === r.right) b.classList.add('ok'); else if (b === btn) b.classList.add('bad'); b.disabled = true; });
    let h = '<div class="akFb ' + (r.correct ? 'ok' : 'bad') + '"><b>' + (r.correct ? '✅ To‘g‘ri: ' : '❌ To‘g‘ri javob: ') + esc(r.right) + '</b><div style="margin-top:6px">' + esc(r.qoida) + '</div>' + (r.izoh ? '<div style="margin-top:8px"><b>Izoh:</b> ' + esc(r.izoh) + '</div>' : '') +
      (!r.correct && r.tanlangan_qoida ? '<div class="muted" style="margin-top:8px"><b>Siz tanlagan:</b> ' + esc(choice) + ' — ' + esc(r.tanlangan_qoida) + '</div>' : '') + '</div>';
    h += CUR.free ? '<button class="primaryAction" onclick="akadHome()">Bosh sahifa</button>' + payBox() : '<button class="primaryAction" onclick="akadSan(' + (CUR.dars_filter || 0) + ')">Keyingi savol ›</button>';
    h += '<button class="akSm" onclick="akadFlag()">Javob noto‘g‘ri deb o‘ylaysizmi? Xabar bering</button>';
    if (ST.admin) h += '<button class="akBtn" style="margin-top:10px" onclick="akadFixCur()">✏️ Savolni tuzatish (admin)</button>';
    $('akFb').innerHTML = h;
  };
  window.akadFlag = async function () { if (!CUR) return; await req('/api/akad/flag', { qid: CUR.qid || CUR.id, text: 'foydalanuvchi shikoyati' }); notify('Rahmat! Adminga yuborildi.'); };

  // ------------------------------------------------ G'AZAL TABDILI
  window.akadTabHome = async function () {
    root().innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    const d = await req('/api/akad/tab/rules'); if (!d.ok) { root().innerHTML = '<div class="result">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    root().innerHTML = '<button class="back" onclick="akadHome()">‹ Mumtoz tahlil maktabi</button><h2>📖 G‘azal tabdili</h2>' +
      '<button class="primaryAction" onclick="akadTab()">▶️ Trenajyorni boshlash' + (ST.access ? '' : ' (bepul namuna)') + '</button><h3 style="margin:16px 0 6px">Tabdil qoidalari</h3>' +
      d.items.map(x => '<div class="word ' + (x.locked ? 'akLock' : '') + '" style="margin-bottom:8px"><strong>' + (x.locked ? '🔒 ' : '') + x.id + '. ' + esc(x.nom) + '</strong>' + (x.locked ? '' : '<div class="muted" style="color:#0d2b22">' + esc(x.matn) + '</div>') + (ST.admin ? '<button class="akSm" data-id="' + x.id + '" onclick="akadEditRule(this.dataset.id, akadTabHome)">✏️ Tuzatish (admin)</button>' : '') + '</div>').join('') + (ST.admin ? '<button class="primaryAction" onclick="akadEditRule(\'\', akadTabHome)">➕ Yangi qoida (admin)</button>' : '') + payBox();
  };
  window.akadTab = async function () {
    root().innerHTML = '<div class="word">⏳ Bayt yuklanmoqda...</div>';
    const d = await req('/api/akad/tab/next');
    if (d.need_pay) { root().innerHTML = '<button class="back" onclick="akadTabHome()">‹ G‘azal tabdili</button><div class="result"><h3>🔒 Bepul namuna ishlandi</h3><p class="muted">Davom etish uchun obuna bo‘ling.</p></div>' + payBox(); return; }
    if (!d.ok) { root().innerHTML = '<button class="back" onclick="akadTabHome()">‹ G‘azal tabdili</button><div class="result">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    CUR = d; CUR.step = 1;
    root().innerHTML = '<button class="back" onclick="akadTabHome()">‹ G‘azal tabdili</button>' + (d.free ? '<span class="akTag pro">Bepul namuna</span>' : '') +
      '<div class="akVerse">' + esc(d.bayt) + '</div><h3 style="margin:8px 0 0">1-qadam: bu baytda qaysi qoida ishlaydi?</h3><div id="akOpts">' +
      d.options.map(o => '<button class="akOpt" data-o="' + esc(o.id) + '" onclick="akadRule(this)">' + esc(o.nom) + '</button>').join('') + '</div><div id="akFb"></div>';
  };
  window.akadRule = async function (btn) {
    if (!CUR || CUR.step !== 1) return; CUR.step = 2; const choice = btn.getAttribute('data-o');
    const r = await req('/api/akad/tab/rule', { id: CUR.id, choice });
    if (!r.ok) { CUR.step = 1; notify(r.error || 'Xatolik'); return; }
    document.querySelectorAll('#akOpts .akOpt').forEach(b => { const o = b.getAttribute('data-o'); if (o === r.right) b.classList.add('ok'); else if (b === btn) b.classList.add('bad'); b.disabled = true; });
    $('akFb').innerHTML = '<div class="akFb ' + (r.correct ? 'ok' : 'bad') + '"><b>' + (r.correct ? '✅ To‘g‘ri qoida: ' : '❌ To‘g‘ri qoida: ') + esc(r.nom) + '</b><div style="margin-top:6px">' + esc(r.qoida) + '</div></div>' + (ST.admin ? '<button class="akBtn" onclick="akadFixTab()">✏️ Baytni tuzatish (admin)</button>' : '') +
      '<h3 style="margin:14px 0 6px">2-qadam: tabdilingizni yozing</h3><textarea id="akText" placeholder="Baytning nasriy bayonini shu yerga yozing..."></textarea><button class="primaryAction" id="akGo" onclick="akadCheck()">🤖 Tekshirish</button>';
  };
  window.akadCheck = async function () {
    const t = ($('akText').value || '').trim(); if (t.length < 15) { notify('Tabdilni to‘liq yozing.'); return; }
    const b = $('akGo'); b.disabled = true; b.textContent = '⏳ Tekshirilmoqda...';
    const r = await req('/api/akad/tab/check', { id: CUR.id, text: t });
    b.disabled = false; b.textContent = '🤖 Qayta tekshirish';
    if (r.need_pay) { payBox(); root().innerHTML += payBox(); return; }
    if (!r.ok) { notify(r.error || 'Xatolik'); return; }
    const good = r.ball >= 70;
    $('akFb').insertAdjacentHTML('beforeend', '<div class="akFb ' + (good ? 'ok' : 'bad') + '" style="margin-top:14px"><div class="akScore">' + r.ball + '/100</div><div class="muted">Ma’no: ' + esc(r.ma_no) + ' • Tartib: ' + esc(r.tartib) + '</div><p>' + esc(r.izoh) + '</p>' + (r.tuzatish ? '<p><b>Tuzatish:</b> ' + esc(r.tuzatish) + '</p>' : '') +
      '<p><b>Namunaviy tabdil:</b><br>' + esc(r.namuna) + '</p></div>' + (ST.admin ? '<button class="akBtn" onclick="akadFixTab()">✏️ Baytni tuzatish (admin)</button>' : '') + (CUR.free ? '<button class="primaryAction" onclick="akadHome()">Bosh sahifa</button>' + payBox() : '<button class="primaryAction" onclick="akadTab()">Keyingi bayt ›</button>'));
  };

  // ------------------------------------------------ ADMIN MUHARRIR (v124)
  // Savol va ma'lumotlarni Mini App ichida qo'shish / tuzatish / o'chirish. Saqlangan narsa bazada turadi (qayta ishga tushganda ham yo'qolmaydi).
  let AD = null, RET = null;
  const TABS = [['q', '✨ Savollar'], ['art', '📘 San’at ma’lumoti'], ['tq', '📖 Tabdil baytlari'], ['rule', '📏 Tabdil qoidalari'], ['low', '⚠️ Past ishonch'], ['flag', '🚩 Shikoyatlar'], ['del', '🗑 O‘chirilganlar']];
  const val = id => { const e = $(id); return e ? (e.type === 'checkbox' ? e.checked : e.value) : ''; };
  const cut = (s, n) => { s = String(s || '').replace(/\s*\n\s*/g, ' / '); return s.length > n ? s.slice(0, n) + '…' : s; };
  const lbl = t => '<div class="akLbl">' + t + '</div>';
  const BACK = '<button class="back" onclick="akadCancel()">‹ Bekor qilish</button>';
  const ask = msg => new Promise(res => { try { if (tg && tg.showConfirm) { tg.showConfirm(msg, res); return; } } catch (e) {} res(window.confirm(msg)); });
  async function adLoad() {
    const d = await req('/api/akad/admin/content'); if (!d.ok) { notify(d.error || 'Yuklab bo‘lmadi'); return null; }
    d.tab = (AD && AD.tab) || 'q'; d.s = ''; d.dars = 0; d.lim = 40; AD = d; return d;
  }
  window.akadAdmin = async function (tab) {
    root().innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    if (!AD || tab === 'reload') { if (!await adLoad()) { root().innerHTML = '<button class="back" onclick="akadHome()">‹ Mumtoz tahlil maktabi</button><div class="result">Yuklab bo‘lmadi.</div>'; return; } }
    if (tab && tab !== 'reload') { if (AD.tab !== tab) { AD.s = ''; AD.lim = 40; } AD.tab = tab; }
    RET = () => akadAdmin(); adRender();
  };
  window.akadCancel = function () { (RET || akadAdmin)(); };
  function badge(t) {
    const n = t === 'low' ? AD.q.filter(x => x.ishonch === 'past' && !x.tasdiq).length : t === 'flag' ? AD.flags.length : t === 'del' ? AD.deleted.length : 0;
    return n ? ' <i class="akBdg">' + n + '</i>' : '';
  }
  function adRender() {
    root().innerHTML = '<button class="back" onclick="akadHome()">‹ Mumtoz tahlil maktabi</button><h2>🛠 Muharrir</h2><p class="muted">Savol va ma’lumotlarni shu yerning o‘zida qo‘shing, tuzating yoki o‘chiring.</p>' +
      '<div class="akTabs">' + TABS.map(t => '<button class="akTab' + (AD.tab === t[0] ? ' on' : '') + '" onclick="akadAdmin(\'' + t[0] + '\')">' + t[1] + badge(t[0]) + '</button>').join('') + '</div><div id="adTop"></div><div id="adList"></div>';
    adTop(); adItems();
  }
  function adTop() {
    const t = AD.tab, add = { q: ['➕ Yangi savol', "akadEditQ('')"], art: ['➕ Yangi san’at ma’lumoti', "akadEditArt('')"], tq: ['➕ Yangi tabdil bayti', "akadEditTQ('')"], rule: ['➕ Yangi qoida', "akadEditRule('')"] }[t];
    let h = add ? '<button class="primaryAction" onclick="' + add[1] + '">' + add[0] + '</button>' : '';
    if (add) h += '<input type="text" id="adS" class="akInp" placeholder="🔎 Qidirish..." value="' + esc(AD.s) + '" oninput="akadAdS(this.value)">';
    if (t === 'q') h += '<select id="adD" class="akInp" onchange="akadAdD(this.value)"><option value="0">Barcha darslar</option>' + AD.lessons.map(l => '<option value="' + l.dars + '"' + (AD.dars === l.dars ? ' selected' : '') + '>' + l.dars + '-dars: ' + esc(l.nom) + '</option>').join('') + '</select>';
    $('adTop').innerHTML = h;
  }
  window.akadAdS = v => { AD.s = v; AD.lim = 40; adItems(); };
  window.akadAdD = v => { AD.dars = +v; AD.lim = 40; adItems(); };
  window.akadAdMore = () => { AD.lim += 40; adItems(); };
  const hit = (o, keys) => { const s = AD.s.trim().toLowerCase(); return !s || keys.some(k => String(o[k] == null ? '' : o[k]).toLowerCase().includes(s)); };
  const tags = x => (x.free ? '<span class="akTag pro">🎁 bepul</span>' : '') + (x.edited ? '<span class="akTag">✏️ tahrirlangan</span>' : '');
  const btn = (txt, fn, id, cls) => '<button class="akBtn ' + (cls || '') + '" data-id="' + esc(id) + '" onclick="' + fn + '(this.dataset.id)">' + txt + '</button>';
  function adItems() {
    const t = AD.tab; let rows = [], h = '';
    if (t === 'q' || t === 'low') {
      rows = AD.q.filter(x => t === 'q' ? ((!AD.dars || x.dars === AD.dars) && hit(x, ['qid', 'bayt', 'javob'])) : (x.ishonch === 'past' && !x.tasdiq));
      h = (t === 'low' ? '<p class="muted">AI yozgan, ishonchi past javoblar. «✅ To‘g‘ri» — tasdiqlash; xato bo‘lsa «✏️ Tuzatish».</p>' : '') + rows.slice(0, AD.lim).map(x =>
        '<div class="akItem"><div class="akRow"><b>' + esc(x.qid) + '</b><span class="akTag">' + esc(x.javob) + '</span>' + tags(x) + '</div><div class="akVerse sm">' + mark(x.bayt, x.ajratilgan) + '</div><div class="akBtns">' +
        btn('✏️ Tuzatish', 'akadEditQ', x.qid) + (t === 'low' ? btn('✅ To‘g‘ri', 'akadConfirm', x.qid, 'ok') : '') + '</div></div>').join('');
    } else if (t === 'art') {
      rows = AD.arts.filter(x => hit(x, ['art', 'text']));
      h = rows.slice(0, AD.lim).map(x => '<div class="akItem"><div class="akRow"><b>' + esc(x.art) + '</b><span class="akTag">' + x.used + ' savol</span>' + tags(x) + '</div><div class="muted">' + esc(cut(x.text, 150)) + '</div><div class="akBtns">' + btn('✏️ Tuzatish', 'akadEditArt', x.art) + '</div></div>').join('');
    } else if (t === 'tq') {
      rows = AD.tq.filter(x => hit(x, ['id', 'bayt', 'tabdil']));
      h = rows.slice(0, AD.lim).map(x => { const r = AD.rules.find(o => o.id === x.ish); return '<div class="akItem"><div class="akRow"><b>' + esc(x.id) + '</b><span class="akTag">' + esc(r ? r.nom : x.ish) + '</span>' + tags(x) + '</div><div class="akVerse sm">' + esc(x.bayt) + '</div><div class="akBtns">' + btn('✏️ Tuzatish', 'akadEditTQ', x.id) + '</div></div>'; }).join('');
    } else if (t === 'rule') {
      rows = AD.rules.filter(x => hit(x, ['id', 'nom', 'matn']));
      h = rows.slice(0, AD.lim).map(x => '<div class="akItem"><div class="akRow"><b>' + esc(x.id) + '. ' + esc(x.nom) + '</b><span class="akTag">' + x.used + ' bayt</span></div><div class="muted">' + esc(cut(x.matn, 150)) + '</div><div class="akBtns">' + btn('✏️ Tuzatish', 'akadEditRule', x.id) + '</div></div>').join('');
    } else if (t === 'flag') {
      rows = AD.flags;
      h = (rows.length ? '<p class="muted">Foydalanuvchilar «javob noto‘g‘ri» deb xabar bergan savollar. Savolni tuzatsangiz, shikoyat o‘zi yopiladi.</p>' : '') + rows.map(x => '<div class="akItem"><div class="akRow"><b>' + esc(x.qid) + '</b><span class="muted">' + esc(String(x.at || '').slice(0, 10)) + '</span></div><div class="muted">' + esc(x.text || '—') + '</div><div class="akBtns">' +
        btn('✏️ Tuzatish', /^t\d/.test(x.qid) ? 'akadEditTQ' : 'akadEditQ', x.qid) + btn('✔️ Yopish', 'akadFlagClear', String(x.id)) + '</div></div>').join('');
    } else if (t === 'del') {
      rows = AD.deleted;
      h = rows.map(x => '<div class="akItem"><div class="akRow"><b>' + esc({ q: 'Savol', art: 'San’at', tq: 'Tabdil bayti', rule: 'Qoida' }[x.kind] || x.kind) + ' • ' + esc(x.id) + '</b></div><div class="muted">' + esc(x.label) + '</div><div class="akBtns"><button class="akBtn ok" data-id="' + esc(x.id) + '" data-k="' + esc(x.kind) + '" onclick="akadRestore(this.dataset.k, this.dataset.id)">↩️ Qaytarish</button></div></div>').join('');
    }
    $('adList').innerHTML = (h || '<div class="word">Hech narsa topilmadi.</div>') + (rows.length > AD.lim ? '<button class="akSm" onclick="akadAdMore()">Yana ko‘rsatish (' + (rows.length - AD.lim) + ')</button>' : '');
  }
  async function adSave(path, b) {
    const r = await req(path, b); if (!r.ok) { notify(r.error || 'Saqlab bo‘lmadi'); return false; }
    notify('✅ Saqlandi'); await adLoad(); (RET || akadAdmin)(); return true;
  }
  const freeBox = (cur, what) => '<label class="akChk"><input type="checkbox" id="fFree"' + (cur ? ' checked disabled' : '') + '> 🎁 ' + what + ' sifatida bepul namuna qilish' + (cur ? ' (hozir shu)' : '') + '</label>';
  const saveRow = (fn, key, kind, canDel) => '<button class="primaryAction" onclick="' + fn + '(\'' + esc(key) + '\')">💾 Saqlash</button>' + (canDel ? '<button class="akDanger" onclick="akadDel(\'' + kind + '\', \'' + esc(key) + '\')">🗑 O‘chirish</button>' : '');
  async function adReady(ret) { if (ret) RET = ret; if (!AD && !await adLoad()) return false; return true; }

  window.akadEditQ = async function (qid, ret) {
    if (!await adReady(ret)) return;
    const x = qid ? AD.q.find(o => o.qid === qid) : null; if (qid && !x) { notify('Savol topilmadi'); return; }
    const dars = x ? '<input type="text" class="akInp" disabled value="' + x.dars + '-dars: ' + esc(x.dars_nom) + '">' :
      '<select id="fDars" class="akInp" onchange="akadDarsSel()">' + AD.lessons.map(l => '<option value="' + l.dars + '">' + l.dars + '-dars: ' + esc(l.nom) + '</option>').join('') + '<option value="new">➕ Yangi dars...</option></select>' +
      '<div id="fNewD" class="hidden"><input type="number" id="fDarsN" class="akInp" placeholder="Dars raqami (masalan: 12)"><input type="text" id="fDarsNom" class="akInp" placeholder="Yangi dars nomi"></div>';
    root().innerHTML = BACK + '<h2>' + (x ? '✏️ Savolni tuzatish • ' + esc(x.qid) : '➕ Yangi savol') + '</h2>' + lbl('Dars') + dars +
      lbl('Bayt (to‘liq matn; misralar yangi qatordan)') + '<textarea id="fBayt" oninput="akadPrev()">' + esc(x ? x.bayt : '') + '</textarea>' +
      lbl('Ajratilgan so‘z/ibora — har qatorda bitta (baytdagi yozilishi bilan bir xil)') + '<textarea id="fAj" class="sm" oninput="akadPrev()">' + esc(x ? x.ajratilgan.join('\n') : '') + '</textarea><div class="akVerse" id="fPrev"></div>' +
      lbl('To‘g‘ri san’at') + '<select id="fJavob" class="akInp">' + AD.arts.map(a => '<option' + (x && a.art === x.javob ? ' selected' : '') + '>' + esc(a.art) + '</option>').join('') + '</select>' +
      lbl('Izoh (ixtiyoriy — javobdan keyin foydalanuvchiga ko‘rsatiladi)') + '<textarea id="fIzoh" class="sm">' + esc(x ? x.izoh : '') + '</textarea>' + freeBox(x && x.free, 'savol') + saveRow('akadSaveQ', x ? x.qid : '', 'q', !!x);
    akadPrev();
  };
  window.akadDarsSel = function () { const n = $('fNewD'); if (n) n.classList.toggle('hidden', val('fDars') !== 'new'); };
  window.akadPrev = function () { const p = $('fPrev'); if (p) p.innerHTML = mark(val('fBayt'), String(val('fAj')).split('\n')); };
  window.akadSaveQ = async function (qid) {
    const b = { qid, bayt: val('fBayt'), ajratilgan: val('fAj'), javob: val('fJavob'), izoh: val('fIzoh'), free: !!val('fFree') };
    if (!qid) { const d = val('fDars'); if (d === 'new') { b.dars = +val('fDarsN'); b.dars_nom = val('fDarsNom'); } else b.dars = +d; }
    await adSave('/api/akad/admin/q/save', b);
  };
  window.akadEditArt = async function (name, ret) {
    if (!await adReady(ret)) return;
    const x = name ? AD.arts.find(o => o.art === name) : null; if (name && !x) { notify('San’at topilmadi'); return; }
    const ch = x ? x.chalgitish : [], opts = sel => '<option value="">— tanlanmagan (avtomatik) —</option>' + AD.arts.filter(a => !x || a.art !== x.art).map(a => '<option' + (a.art === sel ? ' selected' : '') + '>' + esc(a.art) + '</option>').join('');
    root().innerHTML = BACK + '<h2>' + (x ? '✏️ San’at ma’lumotini tuzatish' : '➕ Yangi san’at ma’lumoti') + '</h2>' + lbl('San’at nomi') + '<input type="text" id="fArt" class="akInp" value="' + esc(x ? x.art : '') + '"' + (x ? ' disabled' : '') + '>' +
      lbl('Ta’rif va tuzoqlar (kamida 20 belgi)') + '<textarea id="fText">' + esc(x ? x.text : '') + '</textarea>' +
      lbl('Savolda chalg‘itadigan variantlar (3 tagacha; bo‘sh qoldirsangiz avtomatik tanlanadi)') + [0, 1, 2].map(i => '<select id="fCh' + i + '" class="akInp">' + opts(ch[i]) + '</select>').join('') +
      (x ? '<p class="muted">Ishlatilgan: ' + x.used + ' ta savolda.</p>' : '') + freeBox(x && x.free, 'nazariya') + saveRow('akadSaveArt', x ? x.art : '', 'art', !!x);
  };
  window.akadSaveArt = async function (name) {
    await adSave('/api/akad/admin/art/save', { art: name || val('fArt'), text: val('fText'), chalgitish: [val('fCh0'), val('fCh1'), val('fCh2')].filter(Boolean), free: !!val('fFree') });
  };
  window.akadEditTQ = async function (id, ret) {
    if (!await adReady(ret)) return;
    const x = id ? AD.tq.find(o => o.id === id) : null; if (id && !x) { notify('Bayt topilmadi'); return; }
    root().innerHTML = BACK + '<h2>' + (x ? '✏️ Tabdil baytini tuzatish • ' + esc(x.id) : '➕ Yangi tabdil bayti') + '</h2>' + lbl('Bayt (misralar yangi qatordan)') + '<textarea id="fBayt">' + esc(x ? x.bayt : '') + '</textarea>' +
      lbl('Qaysi qoida ishlaydi?') + '<select id="fIsh" class="akInp">' + AD.rules.map(r => '<option value="' + r.id + '"' + (x && r.id === x.ish ? ' selected' : '') + '>' + r.id + '. ' + esc(r.nom) + '</option>').join('') + '</select>' +
      lbl('Namunaviy tabdil (nasriy bayon, kamida 15 belgi)') + '<textarea id="fTab">' + esc(x ? x.tabdil : '') + '</textarea>' + freeBox(x && x.free, 'bayt') + saveRow('akadSaveTQ', x ? x.id : '', 'tq', !!x);
  };
  window.akadSaveTQ = async function (id) { await adSave('/api/akad/admin/tq/save', { id, bayt: val('fBayt'), ish: val('fIsh'), tabdil: val('fTab'), free: !!val('fFree') }); };
  window.akadEditRule = async function (id, ret) {
    if (!await adReady(ret)) return;
    const x = id ? AD.rules.find(o => o.id === id) : null; if (id && !x) { notify('Qoida topilmadi'); return; }
    root().innerHTML = BACK + '<h2>' + (x ? '✏️ Qoidani tuzatish • ' + esc(x.id) : '➕ Yangi tabdil qoidasi') + '</h2>' + lbl('Qoida nomi') + '<input type="text" id="fNom" class="akInp" value="' + esc(x ? x.nom : '') + '">' +
      lbl('Qoida matni (kamida 20 belgi)') + '<textarea id="fMatn">' + esc(x ? x.matn : '') + '</textarea>' + (x ? '<p class="muted">Ishlatilgan: ' + x.used + ' ta baytda.</p>' : '') + saveRow('akadSaveRule', x ? x.id : '', 'rule', !!x);
  };
  window.akadSaveRule = async function (id) { await adSave('/api/akad/admin/rule/save', { id, nom: val('fNom'), matn: val('fMatn') }); };
  window.akadDel = async function (kind, id) {
    if (!(await ask('Rostdan ham o‘chirasizmi? («🗑 O‘chirilganlar» bo‘limidan qaytarish mumkin.)'))) return;
    const r = await req('/api/akad/admin/' + kind + '/delete', kind === 'q' ? { qid: id } : kind === 'art' ? { art: id } : { id });
    if (!r.ok) { notify(r.error || 'Xatolik'); return; }
    notify('🗑 O‘chirildi'); await adLoad(); (RET || akadAdmin)();
  };
  window.akadRestore = async function (kind, id) {
    const r = await req('/api/akad/admin/restore', { kind, id }); if (!r.ok) { notify(r.error || 'Xatolik'); return; }
    notify('↩️ Qaytarildi'); const t = AD.tab; await adLoad(); AD.tab = t; adRender();
  };
  window.akadConfirm = async function (qid) {
    const r = await req('/api/akad/admin/confirm', { qid }); if (!r.ok) { notify(r.error || 'Xatolik'); return; }
    const o = AD.q.find(x => x.qid === qid); if (o) o.tasdiq = true; notify('✅ Tasdiqlandi'); adRender();
  };
  window.akadFlagClear = async function (id) {
    const r = await req('/api/akad/admin/flag/clear', { id }); if (!r.ok) { notify(r.error || 'Xatolik'); return; }
    AD.flags = AD.flags.filter(f => String(f.id) !== String(id)); adRender();
  };
  // mashq paytida admin xato savolni ko'rsa — shu yerning o'zida tuzatadi (tuzatgach keyingi savolga o'tadi)
  window.akadFixCur = function () { if (CUR) akadEditQ(CUR.qid, () => akadSan((CUR && CUR.dars_filter) || 0)); };
  window.akadFixTab = function () { if (CUR) akadEditTQ(CUR.id, () => akadTab()); };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(init, 400)); else setTimeout(init, 400);
})();
