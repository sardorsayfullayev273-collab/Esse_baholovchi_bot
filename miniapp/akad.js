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
      (s.admin ? '<button class="akCard" onclick="akadAdmin()"><b>🛠 Javoblarni tekshirish (admin)</b><div class="muted">Javobni tuzatish va tasdiqlash.</div></button>' : '') + payBox();
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
      d.items.map(x => '<div class="word ' + (x.locked ? 'akLock' : '') + '" style="margin-bottom:8px"><strong>' + (x.locked ? '🔒 ' : '') + esc(x.art) + '</strong>' + (x.locked ? '<div class="muted">Obuna bilan ochiladi</div>' : '<div class="muted" style="color:#0d2b22">' + esc(x.text) + '</div>') + '</div>').join('') + payBox();
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
    let h = '<div class="akFb ' + (r.correct ? 'ok' : 'bad') + '"><b>' + (r.correct ? '✅ To‘g‘ri: ' : '❌ To‘g‘ri javob: ') + esc(r.right) + '</b><div style="margin-top:6px">' + esc(r.qoida) + '</div>' +
      (!r.correct && r.tanlangan_qoida ? '<div class="muted" style="margin-top:8px"><b>Siz tanlagan:</b> ' + esc(choice) + ' — ' + esc(r.tanlangan_qoida) + '</div>' : '') + '</div>';
    h += CUR.free ? '<button class="primaryAction" onclick="akadHome()">Bosh sahifa</button>' + payBox() : '<button class="primaryAction" onclick="akadSan(' + (CUR.dars_filter || 0) + ')">Keyingi savol ›</button>';
    h += '<button class="akSm" onclick="akadFlag()">Javob noto‘g‘ri deb o‘ylaysizmi? Xabar bering</button>';
    if (ST.admin) h += '<div class="muted" style="margin-top:8px">Admin: /san_javob ' + esc(CUR.qid) + ' San’at nomi</div>';
    $('akFb').innerHTML = h;
  };
  window.akadFlag = async function () { if (!CUR) return; await req('/api/akad/flag', { qid: CUR.qid || CUR.id, text: 'foydalanuvchi shikoyati' }); notify('Rahmat! Adminga yuborildi.'); };

  // ------------------------------------------------ G'AZAL TABDILI
  window.akadTabHome = async function () {
    root().innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    const d = await req('/api/akad/tab/rules'); if (!d.ok) { root().innerHTML = '<div class="result">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    root().innerHTML = '<button class="back" onclick="akadHome()">‹ Mumtoz tahlil maktabi</button><h2>📖 G‘azal tabdili</h2>' +
      '<button class="primaryAction" onclick="akadTab()">▶️ Trenajyorni boshlash' + (ST.access ? '' : ' (bepul namuna)') + '</button><h3 style="margin:16px 0 6px">Tabdil qoidalari</h3>' +
      d.items.map(x => '<div class="word ' + (x.locked ? 'akLock' : '') + '" style="margin-bottom:8px"><strong>' + (x.locked ? '🔒 ' : '') + x.id + '. ' + esc(x.nom) + '</strong>' + (x.locked ? '' : '<div class="muted" style="color:#0d2b22">' + esc(x.matn) + '</div>') + '</div>').join('') + payBox();
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
    $('akFb').innerHTML = '<div class="akFb ' + (r.correct ? 'ok' : 'bad') + '"><b>' + (r.correct ? '✅ To‘g‘ri qoida: ' : '❌ To‘g‘ri qoida: ') + esc(r.nom) + '</b><div style="margin-top:6px">' + esc(r.qoida) + '</div></div>' +
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
      '<p><b>Namunaviy tabdil:</b><br>' + esc(r.namuna) + '</p></div>' + (CUR.free ? '<button class="primaryAction" onclick="akadHome()">Bosh sahifa</button>' + payBox() : '<button class="primaryAction" onclick="akadTab()">Keyingi bayt ›</button>'));
  };

  // ------------------------------------------------ ADMIN
  window.akadAdmin = async function () {
    root().innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    const d = await req('/api/akad/admin/list?dars=0'); if (!d.ok) { root().innerHTML = '<div class="result">' + esc(d.error || 'Xatolik') + '</div>'; return; }
    const low = d.items.filter(x => x.ishonch === 'past' && !x.tasdiq);
    root().innerHTML = '<button class="back" onclick="akadHome()">‹ Mumtoz tahlil maktabi</button><h2>🛠 Javoblar</h2><p class="muted">AI kiritgan javoblar. Avval «past ishonch» larni tekshiring. Tuzatish: <b>/san_javob d3-24 San’at nomi</b> • tasdiqlash: <b>/san_tasdiq d3-24</b> • hammasi: <b>/san_tasdiq hammasi</b>. Tasdiqlangan: ' + d.items.filter(x => x.tasdiq).length + ' / ' + d.items.length + '</p>' +
      '<h3>⚠️ Past ishonch (' + low.length + ')</h3>' + low.map(x => '<div class="word" style="margin-bottom:8px"><b>' + esc(x.qid) + '</b> → <b style="color:#0b5a41">' + esc(x.javob) + '</b><div class="akVerse" style="font-size:14px;padding:10px">' + mark(x.bayt, x.ajratilgan) + '</div></div>').join('');
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => setTimeout(init, 400)); else setTimeout(init, 400);
})();
