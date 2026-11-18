// ===== v130: «Mashq 2.0 / Bosqich A» — premium ko‘rinish + ⭐ yulduz, 7 kunlik sovg‘a, kunlik vazifalar, 3 ta yordam =====
// games.js (o‘yin mantiqi) O‘ZGARTIRILMAGAN: bu fayl uning funksiyalarini o‘rab oladi. O‘chirish: index.html dan qz.js va qz.css satrlarini olib tashlang.
// Yulduz, sovg‘a va vazifalar SERVERDA hisoblanadi (quizara.py) — bu yerda faqat ko‘rsatiladi.
let QZ = null, QZ_TICK = null;
const qzEsc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const qzUser = () => (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) || {};

let QZT = [], QZ_GH = null, QZ_LAST = null, QZ_CD = null;
async function qzGet(path) {
  try { const r = await apiFetch(apiUrl(path), { cache: 'no-store' }); return await r.json(); } catch (e) { return { ok: false, error: 'Internetni tekshiring.' }; }
}
async function qzLoad() {
  if (!tg || !tg.initData) return null;
  const [d, t] = await Promise.all([qzGet('/api/qz/state'), qzGet('/api/qz/tours')]);
  if (t && t.ok) QZT = t.tours || [];
  if (d && d.ok) { QZ = d; return d; }
  return null;
}
async function qzPost(path, body) {
  try { const r = await apiFetch(apiUrl(path), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }); return await r.json(); }
  catch (e) { return { ok: false, error: 'Internetni tekshiring.' }; }
}

// ---------- bosh oyna: sarlavha + sovg‘a + vazifalar ----------
function qzTopHtml() {
  const u = qzUser(); const st = (typeof GM_STATE !== 'undefined' && GM_STATE) || null; const stats = gmLS('gm_stats', { xp: 0 });
  const pk = st && st.perks; const xpAll = (stats.xp || 0) + (pk ? (pk.bonus_xp || 0) : 0); const rk = gmRank(xpAll);
  const nm = qzEsc(((u.first_name || '') + (u.last_name ? ' ' + u.last_name : '')).trim() || 'O‘yinchi');
  const av = u.photo_url ? '<img src="' + qzEsc(u.photo_url) + '" alt="">' : '<b>' + qzEsc(((u.first_name || '?')[0] || '?').toUpperCase()) + '</b>';
  const stars = QZ ? QZ.stars : '—';
  let h = '<div id="qzTop" class="qzWrap"><div class="qzHead" onclick="gmShowRanks()">'
    + '<div class="qzAv"><span>' + av + '</span></div>'
    + '<div class="qzWho"><b>' + nm + '</b><small>' + qzEsc(rk.cur[2] + ' ' + rk.cur[1]) + ' • ' + xpAll + ' XP</small><i class="qzXp"><u style="width:' + rk.pct + '%"></u></i></div>'
    + '<div class="qzStars" id="qzStars"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4 6.1 20.5l1.2-6.5L2.5 9.4l6.6-.9z" fill="#ffd24d"/></svg><b>' + stars + '</b></div></div>';
  h += qzNavHtml();
  if (QZ && QZ.gift) h += qzGiftHtml(QZ.gift);
  if (QZ && QZ.tasks) h += qzTasksHtml(QZ.tasks);
  return h + '</div>';
}
function qzGiftHtml(g) {
  const days = g.days.map(d => '<div class="qzDay ' + d.state + (d.n === 7 ? ' big' : '') + '"><small>' + d.n + '-kun</small><b>' + (d.state === 'done' ? '✓' : d.reward + ' ⭐') + '</b></div>').join('');
  return '<div class="qzCard"><div class="qzCT"><span class="qzIc">🎁</span><div><b>Kunlik sovg‘a</b><small>Har kuni kiring — sovg‘a kattalashib boradi</small></div>'
    + '<em>🔥 ' + (g.streak || 0) + ' kun</em></div><div class="qzDays">' + days + '</div>'
    + (g.claimed_today ? '<div class="qzDone">Bugungi sovg‘a olindi ✓ Ertaga: <b>' + (g.day < 7 ? (g.days[g.day] ? g.days[g.day].reward : g.reward) : 10) + ' ⭐</b></div>'
      : '<button type="button" class="qzCta" id="qzGiftBtn" onclick="qzClaimGift()">🎁 Sovg‘ani olish: +' + g.reward + ' ⭐</button>') + '</div>';
}
function qzTasksHtml(ts) {
  const nDone = ts.filter(t => t.claimed).length;
  const rows = ts.map(t => '<div class="qzTask' + (t.claimed ? ' cl' : t.done ? ' rdy' : '') + '"><div class="qzTi"><b>' + qzEsc(t.title) + '</b><i class="qzSeg"><u style="width:' + Math.round(t.have / t.need * 100) + '%"></u></i><small>' + t.have + ' / ' + t.need + '</small></div>'
    + (t.claimed ? '<span class="qzOk">✓</span>' : t.done ? '<button type="button" class="qzGet" onclick="qzClaimTask(\'' + t.id + '\')">+' + t.reward + ' ⭐</button>' : '<span class="qzRw">+' + t.reward + ' ⭐</span>') + '</div>').join('');
  return '<div class="qzCard"><div class="qzCT"><span class="qzIc">✅</span><div><b>Kunlik vazifalar</b><small>Bajaring va yulduz oling</small></div><em>' + nDone + '/' + ts.length + '</em></div>' + rows + '</div>';
}
function qzDecorateHub() {
  const box = $('gmBody'); if (!box || !box.parentNode || box.parentNode.classList.contains('hidden')) return;
  const old = $('qzTop'); if (old) old.remove();
  box.insertAdjacentHTML('afterbegin', qzTopHtml());
}
function qzRefreshStars() { const el = $('qzStars'); if (el && QZ) el.querySelector('b').textContent = QZ.stars; }
async function qzClaimGift() {
  const b = $('qzGiftBtn'); if (b) b.disabled = true;
  const d = await qzPost('/api/qz/gift');
  if (!d.ok) { notify(d.error || 'Sovg‘a olinmadi.'); if (b) b.disabled = false; await qzLoad(); qzDecorateHub(); return; }
  await qzLoad(); qzDecorateHub(); qzBurst('+' + d.gained + ' ⭐');
  try { tg?.HapticFeedback?.notificationOccurred('success'); } catch (e) {}
}
async function qzClaimTask(id) {
  const d = await qzPost('/api/qz/task', { id });
  if (!d.ok) { notify(d.error || 'Mukofot olinmadi.'); await qzLoad(); qzDecorateHub(); return; }
  await qzLoad(); qzDecorateHub(); qzBurst('+' + d.gained + ' ⭐');
  try { tg?.HapticFeedback?.notificationOccurred('success'); } catch (e) {}
}
function qzBurst(txt) {
  const el = document.createElement('div'); el.className = 'qzBurst'; el.textContent = txt; document.body.appendChild(el);
  setTimeout(() => el.remove(), 1500);
}

// gmRenderHub / gmOpenHub ni o‘rab olamiz
const _qz_gmRenderHub = gmRenderHub;
gmRenderHub = function (st) { _qz_gmRenderHub(st); qzDecorateHub(); };
const _qz_gmOpenHub = gmOpenHub;
gmOpenHub = async function () { _qz_gmOpenHub(); qzLoad().then(() => qzDecorateHub()); };

// ---------- savol oynasi: 3 ta yordam + soniya ----------
function qzLLOk(g, q) { return g && g.type !== 'dtm' && q && q.kind !== 'open' && q.kind !== 'match' && Array.isArray(q.opts) && q.opts.length >= 2; }
function qzLLHtml(g, q) {
  const l = g.ll, u = q.llUsed || {}; const two = q.opts.length <= 2;
  const btn = (k, ico, name, n, dis) => '<button type="button" class="qzLL' + (dis || n <= 0 ? ' off' : '') + (k === 's' && g.armed2 ? ' on' : '') + '" id="qzL' + k + '" onclick="qzUse(\'' + k + '\')"' + (dis || n <= 0 ? ' disabled' : '') + '><i>' + n + '</i><b>' + ico + '</b><span>' + name + '</span></button>';
  return '<div class="qzLLs" id="qzLLs">' + btn('f', '50/50', 'Yarmini olib tashla', l.f, two || !!u.f) + btn('t', '⏱', '+10 soniya', l.t, !!u.t) + btn('s', '↺', 'Ikkinchi imkon', l.s, !!u.s || g.armed2) + '</div>';
}
function qzDecorateQ() {
  const g = GM; if (!g || g.locked === undefined) return; const q = g.qs[g.i]; const box = $('gpBody'); if (!box) return;
  if (QZ_TICK) { clearInterval(QZ_TICK); QZ_TICK = null; }
  // soniya hisoblagich
  const tag = box.querySelector('.gmTag'); const top = box.querySelector('.gmTop');
  if (top && !$('qzSec')) { const s = document.createElement('span'); s.id = 'qzSec'; s.className = 'qzSec'; s.textContent = Math.ceil(g.tleft || 0); top.appendChild(s); }
  QZ_TICK = setInterval(() => { const e = $('qzSec'); if (!GM || !e) { clearInterval(QZ_TICK); QZ_TICK = null; return; } e.textContent = Math.max(0, Math.ceil(GM.tleft)); e.classList.toggle('low', GM.tleft < 5); }, 200);
  if (!qzLLOk(g, q)) return;
  if (!g.ll) g.ll = { f: 3, t: 3, s: 2 }; if (!q.llUsed) q.llUsed = {};
  const fb = $('gmFb'); if (fb && !$('qzLLs')) fb.insertAdjacentHTML('beforebegin', qzLLHtml(g, q));
}
function qzLLUpdate() { const g = GM, q = g && g.qs[g.i]; const w = $('qzLLs'); if (w && g && q) w.outerHTML = qzLLHtml(g, q); }
function qzUse(k) {
  const g = GM; if (!g || g.locked) return; const q = g.qs[g.i]; if (!q.llUsed) q.llUsed = {}; if (q.llUsed[k] || g.ll[k] <= 0) return;
  if (k === 'f') {
    const wrong = q.opts.map((_, i) => i).filter(i => i !== q.ans && !$('gmo' + i).disabled);
    gmShuffle(wrong, Math.random).slice(0, Math.max(1, Math.floor(q.opts.length / 2))).forEach(i => { const o = $('gmo' + i); if (o) { o.disabled = true; o.classList.add('gone'); } });
  } else if (k === 't') {
    g.tleft += 10; g.cur = Math.max(g.cur, g.tleft); const el = $('gmBarI'); if (el) { el.style.width = Math.min(100, g.tleft / g.cur * 100) + '%'; el.classList.remove('low'); }
  } else if (k === 's') { g.armed2 = true; notify('Ikkinchi imkon yoqildi: bu savolda xato qilsangiz, yana bir marta urinasiz.'); }
  g.ll[k]--; q.llUsed[k] = true; qzLLUpdate();
  try { tg?.HapticFeedback?.impactOccurred('light'); } catch (e) {}
}
const _qz_gmRenderQ = gmRenderQ;
gmRenderQ = function () { if (GM) GM.armed2 = false; _qz_gmRenderQ(); qzDecorateQ(); };
// «Ikkinchi imkon»: birinchi xato javob hisoblanmaydi
const _qz_gmAnswer = gmAnswer;
gmAnswer = function (i) {
  const g = GM;
  if (g && !g.locked && g.armed2 && i >= 0) {
    const q = g.qs[g.i]; g.armed2 = false;
    if (i !== q.ans) { const b = $('gmo' + i); if (b) { b.disabled = true; b.classList.add('wrong', 'gone'); } qzLLUpdate(); return; }
  }
  return _qz_gmAnswer(i);
};
const _qz_gmQuit = gmQuit;
gmQuit = function () { if (QZ_TICK) { clearInterval(QZ_TICK); QZ_TICK = null; } _qz_gmQuit(); };

// ---------- natija oynasi: yulduzlar ----------
const _qz_gmFinish = gmFinish;
gmFinish = async function () {
  if (QZ_TICK) { clearInterval(QZ_TICK); QZ_TICK = null; }
  const g = GM, pct = g ? g.correct / Math.max(1, g.total) : 0;
  await _qz_gmFinish();
  const res = (typeof GM_STATE !== 'undefined') ? GM_STATE : null; const body = $('gpBody'); if (!body) return;
  const med = body.querySelector('.gmMedal'); if (med) med.classList.add(pct >= .7 ? 'qzWin' : 'qzOk');
  if (res && typeof res.stars_gained === 'number') {
    if (QZ) QZ.stars = res.stars;
    const el = $('gmSrv'); if (el) el.insertAdjacentHTML('afterend', '<div class="qzStarsRes"><div><b>+' + res.stars_gained + ' ⭐</b><small>yulduz' + (res.duel_bonus ? ' (g‘alaba bonusi +' + res.duel_bonus + ')' : '') + '</small></div><div><b>' + res.stars + ' ⭐</b><small>jami hisobingiz</small></div></div>');
    if (pct >= .7) qzBurst('Zo‘r natija!');
  }
};


// =====================================================================================
// v131: BOSQICH B + C — yangi o‘yin tanlovi, raqib bilan o‘yin, viloyatlar, turnir
// =====================================================================================
const qzIni = n => qzEsc(((n || '?').trim()[0] || '?').toUpperCase());
const qzAvSm = (txt, cls) => '<span class="qzAv sm ' + (cls || '') + '"><span>' + txt + '</span></span>';
function qzShow(html) {
  if (QZ_CD) { clearInterval(QZ_CD); QZ_CD = null; }
  if (GM && GM.timer) clearInterval(GM.timer); GM = null;
  gmShowPlay(); $('gpBody').innerHTML = html; window.scrollTo(0, 0);
}
function qzLeft(sec) {
  sec = Math.max(0, Math.floor(sec)); const d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
  if (d > 0) return d + ' kun ' + h + ' soat'; const p = n => String(n).padStart(2, '0'); return p(h) + ':' + p(m) + ':' + p(s);
}
function qzCountdown() {   // sahifadagi barcha [data-end] (epoch soniya) hisoblagichlari
  if (QZ_CD) clearInterval(QZ_CD);
  const tick = () => { const els = document.querySelectorAll('[data-end]'); if (!els.length) { clearInterval(QZ_CD); QZ_CD = null; return; } els.forEach(e => { e.textContent = qzLeft(+e.getAttribute('data-end') - Date.now() / 1000); }); };
  tick(); QZ_CD = setInterval(tick, 1000);
}
const qzBackBtn = (fn, label) => '<button type="button" class="back qzBack" onclick="' + fn + '">‹ ' + (label || 'Orqaga') + '</button>';

// ---------- hub: «Yangi o‘yin» + bo‘limlar ----------
function qzNavHtml() {
  const open = (QZT || []).filter(t => t.state === 'open').length, soon = (QZT || []).filter(t => t.state === 'soon').length;
  const tsub = open ? open + ' ta faol turnir' : soon ? 'Tez orada boshlanadi' : 'Musobaqalar va sovrinlar';
  const rsub = QZ && QZ.region_set === false ? 'Viloyatingizni tanlang' : 'Har kuni 10 ta savol';
  return '<button type="button" class="qzCta" onclick="qzNewGame()">▶ Yangi o‘yin</button>'
    + '<div class="qzNav"><button type="button" onclick="qzOpenRegion()"><span class="qzIc">📍</span><b>Viloyatlar bellashuvi</b><small>' + rsub + '</small></button>'
    + '<button type="button" onclick="qzOpenTours()"><span class="qzIc">🏆</span><b>Turnirlar</b><small>' + tsub + '</small>' + (open ? '<i class="qzLive">LIVE</i>' : '') + '</button></div>';
}

// ---------- «Kim bilan o‘ynaysiz?» ----------
function qzNewGame() {
  qzShow('<h2 class="qzTitle">Kim bilan o‘ynaysiz?</h2><p class="muted" style="text-align:center">G‘olib raqibidan 20 ⭐ oladi</p>'
    + '<button type="button" class="qzMode m1" onclick="qzStartGhost()"><span class="qzIc">🔀</span><div><b>Tasodifiy raqib</b><small>Kutmaysiz: o‘yin darhol boshlanadi</small></div></button>'
    + '<button type="button" class="qzMode m2" onclick="gmStart(\'duel\')"><span class="qzIc">👥</span><div><b>Do‘st bilan</b><small>5 ta savol, havola yuboring</small></div></button>'
    + '<button type="button" class="qzMode m3" onclick="gmQuit()"><span class="qzIc">🏋️</span><div><b>Yakka mashq</b><small>O‘zingiz, istalgan mavzuda</small></div></button>');
}

// ---------- tasodifiy raqib (oldin yozilgan natija yoki Bot) ----------
async function qzStartGhost() {
  qzShow('<div class="qzSearch"><div class="qzRadar"><span></span><span></span>' + qzAvSm(qzIni(qzUser().first_name)) + '</div><h2 class="qzTitle">Raqib qidirilmoqda…</h2></div>');
  const [d] = await Promise.all([qzPost('/api/qz/match'), new Promise(r => setTimeout(r, 900))]);
  if (!d || !d.ok) { notify((d && d.error) || 'Raqib topilmadi. Keyinroq urinib ko‘ring.'); qzNewGame(); return; }
  QZ_GH = d; await gmStart('duel', { seed: d.seed, vs: d.correct, from: 0 });
}
function qzVsHtml(g) {
  const gh = g.ghost, me = qzUser();
  return '<div class="qzVs" id="qzVs"><div class="qzP">' + qzAvSm(qzIni(me.first_name)) + '<b id="qzMy">0</b></div>'
    + '<div class="qzDots">' + [0, 1, 2, 3, 4].map(i => '<i id="qzD' + i + '"></i>').join('') + '</div>'
    + '<div class="qzP"><b id="qzTh">0</b>' + qzAvSm(gh.bot ? '🤖' : qzIni(gh.name), 'rival') + '</div></div>'
    + '<p class="qzVsName">Raqib: <b>' + qzEsc(gh.name) + '</b>' + (gh.bot ? ' <em>(bot)</em>' : '') + '</p>';
}
function qzVsUpdate() {
  const g = GM; if (!g || !g.ghost) return; const k = g.i; let th = 0;
  for (let j = 0; j <= k && j < 5; j++) { th += g.ghost.log[j] ? 1 : 0; const d = $('qzD' + j); if (d) d.classList.add('on'); }
  const a = $('qzMy'), b = $('qzTh'); if (a) a.textContent = g.correct; if (b) b.textContent = th;
}
const _qz_gmResolve = gmResolve;
gmResolve = function (got, x) { const was = GM && GM.locked; _qz_gmResolve(got, x); if (GM && !was) qzVsUpdate(); };
// savol oynasiga raqib paneli va (viloyat/turnirda) yordamsiz rejim
const _qz_gmRenderQ2 = gmRenderQ;
gmRenderQ = function () {
  if (QZ_GH && GM && GM.type === 'duel' && !GM.ghost) { GM.ghost = QZ_GH; GM.qzMode = 'ghost'; QZ_GH = null; }
  _qz_gmRenderQ2();
  const g = GM, box = $('gpBody');
  if (g && g.ghost && box && !$('qzVs')) { box.insertAdjacentHTML('afterbegin', qzVsHtml(g)); if (g.i > 0) { for (let j = 0; j < g.i; j++) { const d = $('qzD' + j); if (d) d.classList.add('on'); } let th = 0; for (let j = 0; j < g.i; j++) th += g.ghost.log[j] ? 1 : 0; const a = $('qzMy'), b = $('qzTh'); if (a) a.textContent = g.correct; if (b) b.textContent = th; } }
};
qzLLOk = (g, q) => g && g.type !== 'dtm' && g.qzMode !== 'region' && q && q.kind !== 'open' && q.kind !== 'match' && Array.isArray(q.opts) && q.opts.length >= 2;

// do‘st duelida ham natija «raqib» sifatida saqlansin (javob jurnali)
const _qz_gmSubmit = gmSubmit;
gmSubmit = async function (type, correct, total, meta) {
  if (type === 'duel' && QZ_LAST && meta && meta.seed === QZ_LAST.seed && !meta.log) meta = Object.assign({}, meta, { log: QZ_LAST.log });
  return _qz_gmSubmit(type, correct, total, meta);
};
const _qz_gmFinish2 = gmFinish;
gmFinish = async function () {
  const g = GM;
  if (g && g.qzMode === 'ghost') return qzGhostFinish();
  if (g && g.qzMode === 'region') return qzRegionFinish();
  if (g && g.type === 'duel' && g.seed) QZ_LAST = { seed: g.seed, log: g.log.map(l => (l.got >= l.max ? 1 : 0)) };
  return _qz_gmFinish2();
};
async function qzGhostFinish() {
  const g = GM; if (!g) return; clearInterval(g.timer); const gh = g.ghost, correct = g.correct, total = 5;
  const bests = gmLS('gm_best', {}); if (!bests.duel || correct > bests.duel) { bests.duel = correct; gmLSset('gm_best', bests); }
  const st = gmLS('gm_stats', { xp: 0, answered: 0, dtmBest: 0, duelWins: 0 }); if (correct > gh.correct) st.duelWins = (st.duelWins || 0) + 1; gmLSset('gm_stats', st);
  const log = g.log.map(l => (l.got >= l.max ? 1 : 0)); GM = null;
  const res = correct > gh.correct ? ['win', 'G‘alaba!', 'trophy'] : correct === gh.correct ? ['draw', 'Durang!', 'hand'] : ['lose', 'Bu safar raqib oldinda', 'muscle'];
  const me = qzUser(), nm = qzEsc(gh.name);
  $('gpBody').innerHTML = '<div class="gmRes qzGhostRes"><div class="gmMedal ' + (res[0] === 'win' ? 'qzWin' : '') + '">' + (res[0] === 'win' ? '🏆' : res[0] === 'draw' ? '🤝' : '💪') + '</div>'
    + '<h2>' + res[1] + '</h2><p class="muted">' + (res[0] === 'win' ? nm + ' ni ' + correct + ' : ' + gh.correct + ' hisobida yengdingiz' : res[0] === 'draw' ? nm + ' bilan durang' : nm + ' ' + gh.correct + ' : ' + correct + ' hisobida o‘zib ketdi') + '</p>'
    + '<div class="qzVsRes">' + qzAvSm(qzIni(me.first_name)) + '<b>' + correct + ' : ' + gh.correct + '</b>' + qzAvSm(gh.bot ? '🤖' : qzIni(gh.name), 'rival') + '</div>'
    + '<div class="qzStarsRes" id="gmSrv"><div><b>…</b><small>yulduz hisoblanmoqda</small></div><div><b>' + (QZ ? QZ.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div></div>'
    + '<button type="button" class="qzCta" onclick="qzStartGhost()">▶ Yana o‘ynash</button>'
    + '<button type="button" class="bpGhost" onclick="gmShareDuel(' + gh.seed + ',' + correct + ',' + total + ')">⚔️ Do‘stni chaqirish</button>'
    + '<button type="button" class="bpGhost" onclick="gmQuit()">Bosh sahifa</button></div>';
  if (res[0] === 'win') { qzBurst('G‘alaba!'); try { tg?.HapticFeedback?.notificationOccurred('success'); } catch (e) {} }
  const r = await gmSubmit('duel', correct, total, { mode: 'ghost', ghost_id: gh.ghost_id, seed: gh.seed, log });
  const box = $('gmSrv'); if (!box) return;
  if (r) { GM_STATE = r; if (QZ && typeof r.stars === 'number') QZ.stars = r.stars; const gn = (r.stars_gained || 0);
    box.innerHTML = '<div><b>+' + gn + ' ⭐</b><small>' + (r.ghost && r.ghost.bonus ? 'g‘alaba/durang bonusi +' + r.ghost.bonus : 'yulduz') + '</small></div><div><b>' + (r.stars != null ? r.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div>'; }
  else box.innerHTML = '<div><b>—</b><small>natija saqlanmadi</small></div><div><b>' + (QZ ? QZ.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div>';
}

// ---------- VILOYATLAR BELLASHUVI ----------
async function qzOpenRegion() {
  qzShow(qzBackBtn('qzGoHub()', 'O‘yinlar') + '<div class="word">⏳ Yuklanmoqda…</div>');
  const d = await qzGet('/api/qz/region');
  if (!d || !d.ok) { qzShow(qzBackBtn('qzGoHub()', 'O‘yinlar') + '<div class="word">❌ ' + qzEsc((d && d.error) || 'Yuklanmadi') + '</div>'); return; }
  if (QZ) QZ.region_set = !!d.mine;
  const names = Object.fromEntries(d.regions.map(r => [r.key, r.name]));
  let h = qzBackBtn('qzGoHub()', 'O‘yinlar') + '<h2 class="qzTitle">📍 Viloyatlar bellashuvi</h2>';
  if (!d.mine) {
    h += '<p class="muted" style="text-align:center">Viloyatingizni tanlang — to‘g‘ri javoblaringiz shu viloyatga ball qo‘shadi.</p><div class="qzRegGrid">'
      + d.regions.map(r => '<button type="button" onclick="qzSetRegion(\'' + r.key + '\')">' + qzEsc(r.name) + '</button>').join('') + '</div>';
  } else {
    const me = d.board.find(b => b.key === d.mine);
    h += '<div class="qzCard"><div class="qzCT"><span class="qzIc">📍</span><div><b>' + qzEsc(names[d.mine]) + '</b><small>Hafta reytingida ' + (me ? me.rank : '—') + '-o‘rin • ' + (me ? me.pts : 0) + ' ball</small></div></div>'
      + (d.played_today ? '<div class="qzDone">Bugun o‘ynadingiz: <b>' + d.today.correct + '/' + d.today.total + '</b>. Yangi savollarga: <b data-end="' + (Date.now() / 1000 + d.secs_left) + '"></b></div>'
        : '<p class="muted">Bugungi 10 ta savol. Faqat bir marta o‘ynaladi. Yangilanishga: <b data-end="' + (Date.now() / 1000 + d.secs_left) + '"></b></p><button type="button" class="qzCta" onclick="qzRegionPlay()">▶ Bugungi savollarni o‘ynash</button>')
      + (d.can_change ? '<button type="button" class="qzLink" onclick="qzChangeRegion()">Viloyatni almashtirish</button>' : '') + '</div>';
    h += '<h3 class="gmH">Viloyatlar reytingi (hafta)</h3><div class="qzBoard">' + qzRegionRows(d) + '</div>';
    if (d.top && d.top.length) h += '<h3 class="gmH">' + qzEsc(names[d.mine]) + ' — eng yaxshilar</h3><div class="qzBoard">' + d.top.map((t, i) => '<div class="qzBRow' + (t.me ? ' me' : '') + '"><i>' + (i + 1) + '</i><span>' + qzEsc(t.name) + '</span><b>' + t.pts + '</b></div>').join('') + '</div>';
  }
  qzShow(h); if (d.mine) qzCountdown();
}
function qzRegionRows(d) {
  const mx = Math.max(1, ...d.board.map(b => b.pts));
  return d.board.map(b => '<div class="qzBRow' + (b.key === d.mine ? ' me' : '') + '"><i>' + b.rank + '</i><span>' + qzEsc(b.name) + '<u style="width:' + Math.round(b.pts / mx * 100) + '%"></u></span><b>' + b.pts + '</b></div>').join('');
}
function qzGoHub() { gmQuit(); }
async function qzSetRegion(k) {
  const d = await qzPost('/api/qz/region/set', { key: k });
  if (!d.ok) { notify(d.error || 'Tanlanmadi.'); return; } qzOpenRegion();
}
async function qzChangeRegion() {
  const d = await qzGet('/api/qz/region'); if (!d || !d.ok) return;
  qzShow(qzBackBtn('qzOpenRegion()') + '<h2 class="qzTitle">Viloyatni almashtirish</h2><p class="muted" style="text-align:center">Keyingi almashtirish 7 kundan keyin mumkin.</p><div class="qzRegGrid">'
    + d.regions.map(r => '<button type="button" class="' + (r.key === d.mine ? 'on' : '') + '" onclick="qzSetRegion(\'' + r.key + '\')">' + qzEsc(r.name) + '</button>').join('') + '</div>');
}
async function qzRegionPlay() {
  qzShow('<div class="word">⏳ Savollar tayyorlanmoqda…</div>');
  if (!(await gmLoadBank())) { notify('Savollar yuklanmadi. Internetni tekshiring.'); qzOpenRegion(); return; }
  const rnd = gmRng(gmHash('region' + gmDayKey())), seen = new Set(), qs = [];
  for (const it of (await gmBuildDaily(rnd)).concat(await gmBuildDaily(rnd))) { const k = it.id != null ? it.id : JSON.stringify(it).slice(0, 80); if (seen.has(k)) continue; seen.add(k); qs.push(gmFromBank(it, rnd)); if (qs.length >= 10) break; }
  if (qs.length < 5) { notify('Savollar yetarli emas. Keyinroq urinib ko‘ring.'); qzOpenRegion(); return; }
  if (!GM_TYPES.region) GM_TYPES.region = { ico: '📍', name: 'Viloyat', title: 'Viloyatlar bellashuvi', desc: '' };
  gmShowPlay();
  GM = { type: 'region', qzMode: 'region', qs, i: 0, hasLives: false, lives: 0, correct: 0, answered: 0, total: 0, combo: 0, best: 0, locked: false, tsec: 20, tleft: 20, timer: null, log: [] };
  gmRenderQ();
}
async function qzRegionFinish() {
  const g = GM; if (!g) return; clearInterval(g.timer); const correct = g.correct, total = g.qs.length; GM = null;
  $('gpBody').innerHTML = '<div class="gmRes"><div class="gmMedal qzWin">📍</div><h2>' + correct + ' / ' + total + '</h2><p class="muted">Natija saqlanmoqda…</p></div>';
  const d = await qzPost('/api/qz/region/play', { correct, total });
  if (!d.ok) { $('gpBody').innerHTML = '<div class="gmRes"><div class="gmMedal">⚠️</div><h2>' + correct + ' / ' + total + '</h2><p class="muted">' + qzEsc(d.error || 'Saqlanmadi') + '</p><button type="button" class="qzCta" onclick="qzOpenRegion()">Reytingga o‘tish</button></div>'; return; }
  if (QZ) QZ.stars = d.stars; qzBurst('+' + d.gained + ' ⭐');
  const me = d.board.find(b => b.key === d.mine);
  $('gpBody').innerHTML = '<div class="gmRes"><div class="gmMedal qzWin">📍</div><h2>' + correct + ' / ' + total + '</h2><p class="muted">Viloyatingiz uchun +' + correct + ' ball qo‘shildi</p>'
    + '<div class="qzStarsRes"><div><b>+' + d.gained + ' ⭐</b><small>yulduz</small></div><div><b>' + (me ? me.rank : '—') + '-o‘rin</b><small>viloyat reytingida</small></div></div>'
    + '<button type="button" class="qzCta" onclick="qzOpenRegion()">Viloyatlar reytingi</button><button type="button" class="bpGhost" onclick="gmQuit()">Bosh sahifa</button></div>';
}

// ---------- TURNIRLAR ----------
const qzMs = ms => (ms / 1000).toFixed(1) + ' s';
function qzPrizeTxt(p) { return (p || []).map(x => (x[0] === x[1] ? x[0] : x[0] + '–' + x[1]) + '-o‘rin: ' + x[2] + ' ⭐').join(' • '); }
async function qzOpenTours() {
  qzShow(qzBackBtn('qzGoHub()', 'O‘yinlar') + '<div class="word">⏳ Yuklanmoqda…</div>');
  const d = await qzGet('/api/qz/tours');
  if (!d || !d.ok) { qzShow(qzBackBtn('qzGoHub()', 'O‘yinlar') + '<div class="word">❌ ' + qzEsc((d && d.error) || 'Yuklanmadi') + '</div>'); return; }
  QZT = d.tours || []; const adm = typeof ME !== 'undefined' && ME && ME.is_admin;
  let h = qzBackBtn('qzGoHub()', 'O‘yinlar') + '<h2 class="qzTitle">🏆 Turnirlar</h2>';
  if (adm) h += '<button type="button" class="bpGhost" onclick="qzTourForm()">➕ Turnir yaratish</button>';
  if (!QZT.length) h += '<div class="word">Hozircha turnir yo‘q. Yangi turnirlar e’lon qilinadi — kuzatib boring.</div>';
  QZT.slice().sort((a, b) => ({ open: 0, soon: 1, ended: 2 }[a.state] - { open: 0, soon: 1, ended: 2 }[b.state]) || a.start - b.start).forEach(t => { h += qzTourCard(t, adm); });
  qzShow(h);
  if (QZT.some(t => t.state !== 'ended')) qzCountdown();
}
function qzTourCard(t, adm) {
  const badge = t.state === 'open' ? '<i class="qzBadge on">Hozir ochiq</i>' : t.state === 'soon' ? '<i class="qzBadge">Kutilmoqda</i>' : '<i class="qzBadge end">Tugadi</i>';
  const endAt = Date.now() / 1000 + t.secs, when = t.state === 'open' ? 'Tugashiga: <b data-end="' + endAt + '"></b>' : t.state === 'soon' ? 'Boshlanishiga: <b data-end="' + endAt + '"></b>' : 'Turnir yakunlandi';
  let act = '';
  if (t.state === 'open' && !(t.my && t.my.started)) act = t.can_join ? '<button type="button" class="qzCta" onclick="qzTourStart(' + t.id + ')">▶ Turnirni boshlash</button>' : '<p class="muted">Qatnashish uchun yana ' + t.need_plays + ' ta o‘yin o‘ynang.</p>';
  else if (t.my && t.my.finished) act = '<div class="qzDone">Sizning natijangiz: <b>' + t.my.correct + '/' + t.n + '</b> • ' + qzMs(t.my.ms) + (t.my.rank ? ' • <b>' + t.my.rank + '-o‘rin</b>' : '') + '</div>';
  else if (t.my && t.my.started) act = '<p class="muted">Siz turnirni boshlagansiz, natija yuborilmagan.</p>';
  return '<div class="qzCard qzTour"><div class="qzCT"><span class="qzIc">🏆</span><div><b>' + qzEsc(t.title) + '</b><small>' + t.n + ' savol • har biriga ' + t.per_q + ' s • ' + t.players + ' kishi o‘ynadi</small></div>' + badge + '</div>'
    + '<p class="qzPr">' + qzPrizeTxt(t.prizes) + '</p><p class="muted">' + when + '</p>' + act
    + '<button type="button" class="qzLink" onclick="qzTourBoard(' + t.id + ')">📊 Natijalar jadvali</button>'
    + (adm ? '<div class="qzAdm"><button type="button" onclick="qzTourFinal(' + t.id + ')">Yakunlash</button><button type="button" onclick="qzTourDel(' + t.id + ')">O‘chirish</button></div>' : '') + '</div>';
}
async function qzTourBoard(tid) {
  const d = await qzGet('/api/qz/tour/board?id=' + tid); if (!d || !d.ok) { notify((d && d.error) || 'Yuklanmadi'); return; }
  const medal = i => ['🥇', '🥈', '🥉'][i] || (i + 1);
  qzShow(qzBackBtn('qzOpenTours()') + '<h2 class="qzTitle">📊 Natijalar jadvali</h2><p class="muted" style="text-align:center">' + d.players + ' kishi • ball, keyin tezlik bo‘yicha</p>'
    + (d.my ? '<div class="qzDone">Sizning o‘rningiz: <b>' + d.my.rank + '</b> • ' + d.my.correct + ' ta to‘g‘ri • ' + qzMs(d.my.ms) + '</div>' : '')
    + '<div class="qzBoard">' + (d.top.length ? d.top.map((t, i) => '<div class="qzBRow' + (t.me ? ' me' : '') + '"><i>' + medal(i) + '</i><span>' + qzEsc(t.name) + '</span><b>' + t.correct + '</b><em>' + qzMs(t.ms) + '</em></div>').join('') : '<div class="word">Hali natija yo‘q.</div>') + '</div>');
}
function qzConfirm(msg, ok) { if (tg && tg.showConfirm) tg.showConfirm(msg, y => { if (y) ok(); }); else if (confirm(msg)) ok(); }
function qzTourStart(tid) {
  qzConfirm('Turnirda faqat BIR marta qatnashasiz. Boshlangach chiqib ketsangiz, qayta o‘ynab bo‘lmaydi. Boshlaymizmi?', async () => {
    const d = await qzPost('/api/qz/tour/start', { id: tid });
    if (!d.ok) { notify(d.error || 'Boshlab bo‘lmadi.'); qzOpenTours(); return; }
    qzTourPlay(tid, d);
  });
}
let QZTP = null;
function qzTourPlay(tid, d) {
  QZTP = { tid, d, i: 0, ans: [], left: d.per_q, t: null }; qzTourQ();
}
function qzTourQ() {
  const S = QZTP; if (!S) return; if (S.i >= S.d.questions.length) return qzTourDone();
  const q = S.d.questions[S.i]; S.left = S.d.per_q; S.locked = false; clearInterval(S.t);
  qzShow('<div class="gmTop"><span class="gmTag">🏆 ' + qzEsc(S.d.title) + ' • ' + (S.i + 1) + '/' + S.d.questions.length + '</span><span class="qzSec" id="qzTs">' + S.left + '</span></div>'
    + '<div class="gmBar"><i id="qzTb" style="width:100%"></i></div><div class="gmQ"><div class="gmQt">' + qzEsc(q.q) + '</div></div>'
    + '<div class="gmOpts">' + q.opts.map((o, i) => '<button type="button" class="gmOpt" id="qzTo' + i + '" onclick="qzTourPick(' + i + ')"><span class="gmLt">' + 'ABCDE'[i] + '</span>' + qzEsc(o) + '</button>').join('') + '</div>'
    + '<p class="muted" style="text-align:center">To‘g‘ri javob oxirida ko‘rsatiladi</p>');
  S.t = setInterval(() => { S.left -= 0.2; const e = $('qzTs'), b = $('qzTb'); if (e) { e.textContent = Math.max(0, Math.ceil(S.left)); e.classList.toggle('low', S.left < 5); } if (b) b.style.width = Math.max(0, S.left / S.d.per_q * 100) + '%'; if (S.left <= 0) qzTourPick(-1); }, 200);
}
function qzTourPick(i) {
  const S = QZTP; if (!S || S.locked) return; S.locked = true; clearInterval(S.t); S.ans.push(i);
  const b = $('qzTo' + i); if (b) b.classList.add('picked');
  setTimeout(() => { S.i++; qzTourQ(); }, 350);
}
async function qzTourDone() {
  const S = QZTP; if (!S) return; clearInterval(S.t); const tid = S.tid; QZTP = null;
  qzShow('<div class="gmRes"><div class="gmMedal qzWin">🏆</div><h2>Natija hisoblanmoqda…</h2></div>');
  const d = await qzPost('/api/qz/tour/finish', { id: tid, answers: S.ans });
  if (!d.ok) { qzShow('<div class="gmRes"><div class="gmMedal">⚠️</div><h2>Natija yuborilmadi</h2><p class="muted">' + qzEsc(d.error || '') + '</p><button type="button" class="qzCta" onclick="qzOpenTours()">Turnirlarga qaytish</button></div>'); return; }
  if (QZ) QZ.stars = d.stars; qzBurst('+' + d.gained + ' ⭐');
  qzShow('<div class="gmRes"><div class="gmMedal qzWin">🏆</div><h2>' + d.correct + ' / ' + d.total + '</h2><p class="muted">Vaqtingiz: ' + qzMs(d.ms) + '</p>'
    + '<div class="qzStarsRes"><div><b>' + (d.rank || '—') + '-o‘rin</b><small>hozirgi reytingda</small></div><div><b>+' + d.gained + ' ⭐</b><small>qatnashgani uchun</small></div></div>'
    + '<button type="button" class="qzCta" onclick="qzTourBoard(' + tid + ')">📊 Natijalar jadvali</button><button type="button" class="bpGhost" onclick="qzOpenTours()">Turnirlar</button></div>');
}
// ---------- admin: turnir yaratish ----------
function qzTourForm() {
  const pad = n => String(n).padStart(2, '0'), dt = new Date(Date.now() + 5 * 3600 * 1000 + 3600e3), iso = x => x.getUTCFullYear() + '-' + pad(x.getUTCMonth() + 1) + '-' + pad(x.getUTCDate()) + 'T' + pad(x.getUTCHours()) + ':00';
  const e = new Date(dt.getTime() + 24 * 3600e3);
  qzShow(qzBackBtn('qzOpenTours()') + '<h2 class="qzTitle">➕ Yangi turnir</h2>'
    + '<div class="qzCard"><label class="qzL">Nomi<input id="qtT" class="qzIn" maxlength="80" placeholder="Quizara Kubogi #4"></label>'
    + '<label class="qzL">Boshlanish (Toshkent vaqti)<input id="qtS" class="qzIn" type="datetime-local" value="' + iso(dt) + '"></label>'
    + '<label class="qzL">Tugash<input id="qtE" class="qzIn" type="datetime-local" value="' + iso(e) + '"></label>'
    + '<div class="qzRow2"><label class="qzL">Savolga soniya<input id="qtQ" class="qzIn" type="number" min="5" max="60" value="15"></label><label class="qzL">Kamida o‘yin<input id="qtM" class="qzIn" type="number" min="0" max="50" value="3"></label></div>'
    + '<label class="qzL">Savollar (5–30 ta)<textarea id="qtX" class="qzIn" rows="10" placeholder="1. Savol matni?\nA) variant\nB) to‘g‘ri variant*\nC) variant\nD) variant\n\n2. Keyingi savol..."></textarea></label>'
    + '<p class="muted">To‘g‘ri javob oxiriga <b>*</b> qo‘yiladi. Savollar bo‘sh qator bilan ajratiladi. Mukofot: 1-o‘rin 2000 ⭐, 2-o‘rin 1000, 3–4-o‘rin 500, 5–8-o‘rin 200.</p>'
    + '<button type="button" class="bpGhost" onclick="qzTourPreview()">🔍 Savollarni tekshirish</button><div id="qtR"></div>'
    + '<button type="button" class="qzCta" onclick="qzTourCreate()">Turnirni yaratish</button></div>');
}
async function qzTourPreview() {
  const d = await qzPost('/api/qz/tour/preview', { text: ($('qtX') || {}).value || '' });
  $('qtR').innerHTML = '<div class="word">' + (d.errors && d.errors.length ? '⚠️ ' + d.errors.map(qzEsc).join('<br>') + '<br>' : '') + '✅ To‘g‘ri o‘qilgan savollar: <b>' + (d.count || 0) + '</b></div>';
}
async function qzTourCreate() {
  const g = id => ($(id) || {}).value || '';
  const d = await qzPost('/api/qz/tour/create', { title: g('qtT'), start: g('qtS'), end: g('qtE'), per_q: +g('qtQ') || 15, min_plays: +g('qtM'), text: g('qtX') });
  if (!d.ok) { notify(d.error || 'Yaratilmadi.'); return; } notify('✅ Turnir yaratildi (' + d.questions + ' savol).'); qzOpenTours();
}
function qzTourDel(id) { qzConfirm('Turnir va barcha natijalari o‘chadi. Davom etasizmi?', async () => { const d = await qzPost('/api/qz/tour/delete', { id }); notify(d.ok ? 'O‘chirildi.' : (d.error || 'Xato')); qzOpenTours(); }); }
function qzTourFinal(id) { qzConfirm('Mukofotlar hozir tarqatiladi (bir marta). Davom etasizmi?', async () => { const d = await qzPost('/api/qz/tour/final', { id }); notify(d.ok ? 'Mukofot berildi: ' + d.winners + ' kishi.' : (d.error || 'Xato')); qzOpenTours(); }); }
const _qz_gmQuit2 = gmQuit;
gmQuit = function () { if (QZ_CD) { clearInterval(QZ_CD); QZ_CD = null; } if (QZTP) { clearInterval(QZTP.t); QZTP = null; } _qz_gmQuit2(); };
