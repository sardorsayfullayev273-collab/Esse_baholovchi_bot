// ===== v132: O‘yinlar tartibga keltirildi =====
// • 3 ta o‘yin: Bellashuv (raqib bilan), So‘z ustasi (60 soniya), Omon qolish (3 jon). Hammasi BITTA savollar bazasidan oladi.
// • Yangi «O‘yinlar» sahifasi va «Mashq» sahifasining yuqorisidagi karta.
// games.js va qz.js O‘ZGARTIRILMAGAN: bu fayl ularning funksiyalarini o‘rab oladi (qz.js dan KEYIN ulanadi).
// O‘chirish: index.html dan qz2.js satrini olib tashlang — v131 ko‘rinishi qaytadi.

// ---------- 1) yagona savollar bazasi ----------
// dtm_bank.json + barcha bo‘lim banklari (imlo, leksikologiya, morfologiya, ...) bitta ro‘yxatda. Har savolda: c (mavzu), t (tur), d (qiyinlik).
// Tartib hamma qurilmada bir xil — shuning uchun bellashuvdagi «seed» hamma uchun bir xil savollarni beradi.
const QU = { pool: null, busy: null };
async function quPool() {
  if (QU.pool) return QU.pool;
  if (!QU.busy) {
    QU.busy = (async () => {
      if (!(await gmLoadBank())) throw new Error('bank');
      const files = [...new Set([].concat(...Object.values(GM_EXTRA_FILES)))];
      await Promise.all(files.map(f => gmLoadFile(f)));
      const seen = new Set(), all = [];
      const add = arr => (arr || []).forEach(x => { if (!x || x.id == null || seen.has(x.id)) return; seen.add(x.id); all.push(x); });
      add(GMD.bank); files.forEach(f => add(GMD.files && GMD.files[f]));
      QU.pool = all; return all;
    })().finally(() => { QU.busy = null; });
  }
  return QU.busy;
}
const quMc = P => P.filter(x => x.t === 'mc' && !x.p && Array.isArray(x.o) && x.o.length >= 3);   // qisqa yopiq savollar (matnli parchasiz)
// Zaif mavzular ko‘proq tushishi uchun og‘irlik: aniqligi past mavzu — 1.6 gacha, kuchli mavzu — 0.6
function quWeights() {
  const t = gmLS('gm_topic', {}), w = {};
  Object.keys(GM_CATS).forEach(k => { const e = t[k]; w[k] = (e && e.t >= 5) ? 1.6 - Math.min(1, e.c / e.t) : 1; });
  return w;
}

// Bellashuv: seed 1 000 000 dan katta bo‘lsa — yagona bazadan (4 yopiq, har xil mavzudan + 1 ochiq). Kichik seedlar — eski bank (oldingi raqiblar buzilmasin).
const _qu_gmBuildDuel = gmBuildDuel;
gmBuildDuel = function (seed) {
  if (!(seed >= 1000000) || !QU.pool) return _qu_gmBuildDuel(seed);
  const rnd = gmRng((seed >>> 0) || 1), P = QU.pool;
  let op = P.filter(x => x.t === 'open'); if (!op.length) op = GMD.bank.filter(x => x.t === 'open');
  return [].concat(gmBankPick(quMc(P), 4, 1, rnd), gmBankPick(op, 1, 1, rnd)).map(it => gmFromBank(it, rnd));
};
const _qu_gmStart = gmStart;
gmStart = async function (type, arg) {
  if (type === 'soz') return quStartSoz();
  if (type === 'surv') return quStartSurv();
  if (type === 'duel') {
    try { await quPool(); } catch (e) {}
    if (!(arg && arg.seed)) arg = Object.assign({}, arg, { seed: 1000000 + Math.floor(Math.random() * 899000000) });
  }
  return _qu_gmStart(type, arg);
};
const _qu_gmQuit = gmQuit;
gmQuit = function () { if (QS) { clearInterval(QS.timer); QS = null; } _qu_gmQuit(); };

// ---------- 2) So‘z ustasi: 60 soniya, imlo + leksikologiya (omonim, sinonim, paronim) ----------
const QU_SOZ = { sec: 60, max: 25 };
let QS = null;
async function quStartSoz() {
  qzShow('<div class="word">⏳ Savollar tayyorlanmoqda…</div>');
  let P = null; try { P = await quPool(); } catch (e) {}
  const items = P ? gmShuffle(quMc(P).filter(x => x.c === 'imlo' || x.c === 'leks'), Math.random).slice(0, 60) : [];
  if (items.length < 20) { notify('Savollar yuklanmadi. Internetni tekshirib, qayta urinib ko‘ring.'); gmQuit(); return; }
  QS = { qs: items.map(it => gmFromBank(it, Math.random)), i: 0, correct: 0, answered: 0, combo: 0, best: 0, end: Date.now() + QU_SOZ.sec * 1000, locked: false, timer: null };
  try { trackView('game:soz'); } catch (e) {}
  quSozQ(); QS.timer = setInterval(quSozTick, 100);
}
function quSozQ() {
  const S = QS; if (!S) return; const q = S.qs[S.i]; S.locked = false;
  $('gpBody').innerHTML = '<div class="quBlitz"><div class="quClock" id="quClock">' + Math.ceil(Math.max(0, S.end - Date.now()) / 1000) + '</div>'
    + '<div class="quBlitzMid"><div class="gmBar"><i id="quBar"></i></div><small>' + (S.combo >= 2 ? '🔥 ' + S.combo + ' ketma-ket' : '5 ta ketma-ket to‘g‘ri = +3 soniya') + '</small></div>'
    + '<div class="quScore"><b id="quSc">' + S.correct + '</b><small>to‘g‘ri</small></div></div>'
    + '<div class="gmQ"><div class="gmQt">' + gmEscBr(q.q) + '</div></div>'
    + '<div class="gmOpts">' + q.opts.map((o, i) => '<button type="button" class="gmOpt" id="gmo' + i + '" onclick="quSozPick(' + i + ')"><b class="gmLt">' + 'ABCDEF'[i] + '</b>' + gmEsc(o) + '</button>').join('') + '</div><div id="quFb"></div>';
  quSozTick();
}
function quSozTick() {
  const S = QS; if (!S) return; const left = S.end - Date.now(), c = $('quClock'), b = $('quBar');
  if (c) { c.textContent = Math.max(0, Math.ceil(left / 1000)); c.classList.toggle('low', left < 10000); }
  if (b) { b.style.width = Math.max(0, Math.min(100, left / (QU_SOZ.sec * 10))) + '%'; b.classList.toggle('low', left < 10000); }
  if (left <= 0) quSozEnd();
}
function quSozPick(i) {
  const S = QS; if (!S || S.locked) return; S.locked = true;
  const q = S.qs[S.i], ok = i === q.ans;
  document.querySelectorAll('#gpBody .gmOpt').forEach(b => b.disabled = true);
  const r = $('gmo' + q.ans); if (r) r.classList.add('right'); if (!ok) { const w = $('gmo' + i); if (w) w.classList.add('wrong'); }
  S.answered++; gmHaptic(ok); gmMistake(q, ok, 'soz'); gmStats(q, ok ? 1 : 0, 1);
  if (ok) { S.correct++; S.combo++; S.best = Math.max(S.best, S.combo); if (S.combo % 5 === 0) { S.end += 3000; qzBurst('+3 soniya'); } } else S.combo = 0;
  const sc = $('quSc'); if (sc) sc.textContent = S.correct;
  if (!ok && q.exp) $('quFb').innerHTML = '<div class="gmFb bad"><p>' + gmEscBr(q.exp) + '</p></div>';
  if (S.answered >= QU_SOZ.max || S.i + 1 >= S.qs.length) { setTimeout(quSozEnd, ok ? 350 : 1300); return; }
  setTimeout(() => { if (QS === S) { S.i++; quSozQ(); } }, ok ? 380 : 1300);
}
function quSozEnd() {
  const S = QS; if (!S) return; QS = null; clearInterval(S.timer);
  quResult({ type: 'soz', title: 'So‘z ustasi', correct: S.correct, total: S.answered, unit: 'ta to‘g‘ri javob', gold: 15, silver: 9,
    facts: [['🔥', S.best, 'eng uzun kombo'], ['🎯', S.answered ? Math.round(S.correct / S.answered * 100) + '%' : '—', 'aniqlik']], next: ['⚔️ Bellashuv', 'qzStartGhost()'] });
}

// ---------- 3) Omon qolish: 3 jon, tobora qiyinlashadi, zaif mavzulardan ----------
function quBuildSurv(P) {
  const W = quWeights();
  const top = quMc(P).map(x => [Math.pow(Math.random(), 1 / (W[x.c] || 1)), x]).sort((a, b) => b[0] - a[0]).slice(0, 30).map(k => k[1]);
  return top.map(x => [(x.d || 2) + Math.random() * 1.2, x]).sort((a, b) => a[0] - b[0]).map(k => { const q = gmFromBank(k[1], Math.random); q.sec = 20; return q; });
}
async function quStartSurv() {
  qzShow('<div class="word">⏳ Savollar tayyorlanmoqda…</div>');
  let P = null; try { P = await quPool(); } catch (e) {}
  const qs = P ? quBuildSurv(P) : [];
  if (qs.length < 15) { notify('Savollar yuklanmadi. Internetni tekshirib, qayta urinib ko‘ring.'); gmQuit(); return; }
  if (!GM_TYPES.surv) GM_TYPES.surv = { ico: '❤️', name: 'Omon qolish', title: 'Omon qolish', desc: '' };
  gmShowPlay();
  GM = { type: 'surv', qzMode: 'surv', qs, i: 0, hasLives: true, lives: GM_LIVES, correct: 0, answered: 0, total: 0, combo: 0, best: 0, locked: false, tsec: 20, tleft: 20, timer: null, log: [] };
  try { trackView('game:surv'); } catch (e) {}
  gmRenderQ();
}

// ---------- 4) natija oynasi (So‘z ustasi va Omon qolish uchun) ----------
const _qu_gmFinish = gmFinish;
gmFinish = async function () {
  const g = GM;
  if (g && g.qzMode === 'surv') {
    clearInterval(g.timer); GM = null;
    const left = Math.max(0, g.lives), cleared = g.i + 1 >= g.qs.length && left > 0;
    return quResult({ type: 'surv', title: cleared ? 'Hammasini yechdingiz!' : 'Omon qolish', correct: g.correct, total: Math.max(1, g.answered), unit: 'ta savol omon qoldingiz', gold: 20, silver: 10,
      facts: [['🔥', g.best, 'eng uzun kombo'], ['❤️', left, 'jon qoldi']], next: ['🔤 So‘z ustasi', 'gmStart(\'soz\')'] });
  }
  return _qu_gmFinish();
};
async function quResult(o) {
  const bests = gmLS('gm_best', {}), prev = bests[o.type] || 0, rec = o.correct > prev && o.correct > 0;
  if (rec) { bests[o.type] = o.correct; gmLSset('gm_best', bests); }
  const medal = o.correct >= o.gold ? '🏆' : o.correct >= o.silver ? '🥇' : o.correct > 0 ? '👍' : '💪';
  const recTxt = rec && prev ? '🎉 Yangi rekord! Oldingisi: ' + prev : rec ? '🎉 Birinchi rekordingiz!' : prev ? 'Rekordingiz: ' + prev + (o.correct < prev ? ' — yana ' + (prev - o.correct + 1) + ' ta va yangilaysiz' : '') : '';
  $('gpBody').innerHTML = '<div class="gmRes quRes"><div class="gmMedal ' + (rec ? 'qzWin' : '') + '">' + medal + '</div><h2>' + gmEsc(o.title) + '</h2>'
    + '<div class="gmBig">' + o.correct + '</div><p class="muted">' + o.unit + '</p>' + (recTxt ? '<div class="quRec' + (rec ? '' : ' dim') + '">' + recTxt + '</div>' : '')
    + '<div class="quFacts">' + o.facts.map(f => '<div><span>' + f[0] + '</span><b>' + f[1] + '</b><small>' + f[2] + '</small></div>').join('') + '</div>'
    + '<div class="qzStarsRes" id="gmSrv"><div><b>…</b><small>yulduz hisoblanmoqda</small></div><div><b>' + (QZ ? QZ.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div></div>'
    + '<button type="button" class="qzCta" onclick="gmStart(\'' + o.type + '\')">▶ Yana o‘ynash</button>'
    + '<button type="button" class="bpGhost" onclick="' + o.next[1] + '">' + o.next[0] + '</button>'
    + '<button type="button" class="bpGhost" onclick="gmShare(' + o.correct + ',' + o.total + ',\'' + o.type + '\')">📤 Do‘stlarga ulashish</button>'
    + '<button type="button" class="bpGhost" onclick="gmQuit()">‹ O‘yinlar</button></div>';
  if (rec || o.correct >= o.silver) { qzBurst(rec ? 'Yangi rekord!' : 'Zo‘r natija!'); try { tg?.HapticFeedback?.notificationOccurred('success'); } catch (e) {} }
  if (o.total < 1) { const e0 = $('gmSrv'); if (e0) e0.innerHTML = '<div><b>0</b><small>javob berilmadi</small></div><div><b>' + (QZ ? QZ.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div>'; return; }
  const r = await gmSubmit(o.type, o.correct, Math.min(o.total, o.type === 'soz' ? QU_SOZ.max : 30), null);
  const box = $('gmSrv'); if (!box) return;
  if (r) {
    GM_STATE = r; if (QZ && typeof r.stars === 'number') QZ.stars = r.stars;
    const capped = !r.gained && o.correct > 0;
    box.innerHTML = '<div><b>+' + (r.stars_gained || 0) + ' ⭐</b><small>' + (capped ? 'bugungi ball chegarasi to‘ldi' : 'yulduz') + '</small></div><div><b>' + (r.stars != null ? r.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div>';
  } else box.innerHTML = '<div><b>—</b><small>' + (tg && tg.initData ? 'natija saqlanmadi' : 'natija faqat Telegramda saqlanadi') + '</small></div><div><b>' + (QZ ? QZ.stars : '—') + ' ⭐</b><small>jami hisobingiz</small></div>';
}

// ---------- 5) yangi «O‘yinlar» sahifasi ----------
function quHeadHtml(st) {
  const u = qzUser(), stats = gmLS('gm_stats', { xp: 0 }), pk = st && st.perks, xp = (stats.xp || 0) + (pk ? (pk.bonus_xp || 0) : 0), rk = gmRank(xp);
  const nm = qzEsc(((u.first_name || '') + (u.last_name ? ' ' + u.last_name : '')).trim() || 'O‘yinchi');
  const av = u.photo_url ? '<img src="' + qzEsc(u.photo_url) + '" alt="">' : '<b>' + qzEsc(((u.first_name || '?')[0] || '?').toUpperCase()) + '</b>';
  return '<div class="qzHead" onclick="gmShowRanks()"><div class="qzAv"><span>' + av + '</span></div>'
    + '<div class="qzWho"><b>' + nm + '</b><small>' + qzEsc(rk.cur[2] + ' ' + rk.cur[1]) + ' • ' + xp + ' XP' + (rk.nxt ? ' • ' + rk.nxt[1] + 'gacha ' + (rk.nxt[0] - xp) + ' XP' : '') + '</small><i class="qzXp"><u style="width:' + rk.pct + '%"></u></i></div>'
    + '<div class="qzStars" id="qzStars"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4 6.1 20.5l1.2-6.5L2.5 9.4l6.6-.9z" fill="#ffd24d"/></svg><b>' + (QZ ? QZ.stars : '—') + '</b></div></div>';
}
function quGiftBar() {
  const g = QZ && QZ.gift; if (!g || g.claimed_today) return '';
  return '<button type="button" class="quGiftBar" onclick="qzClaimGift()"><span>🎁</span><b>Bugungi sovg‘a tayyor</b><em>+' + g.reward + ' ⭐ olish</em></button>';
}
function quDailyHtml(st) {
  const done = !!(st && st.today_done), streak = (st && st.streak) || 0, pk = st && st.perks;
  const sub = done ? '✅ Bugun bajarildi' + (st.daily ? ': ' + st.daily.correct + '/' + st.daily.total : '') + ' • ertaga yangi savollar'
    : streak ? '🔥 ' + streak + ' kunlik seriyangiz bugun uzilmasin' : 'Bugungi mavzu: ' + gmDailyLabel();
  return '<div class="quDaily' + (done ? ' done' : '') + '"><div class="quDl"><b>Kunlik 5 savol</b><small>' + sub + '</small>'
    + (pk && pk.freeze_left > 0 ? '<small>❄️ ' + pk.freeze_left + ' ta seriya himoyasi bor</small>' : '') + '</div>'
    + '<div class="quFlame"><span>🔥</span><b>' + streak + '</b><small>kun</small></div></div>'
    + (done ? '<button type="button" class="qzCta" onclick="qzStartGhost()">⚔️ Endi raqibni yenging</button>' : '<button type="button" class="qzCta" onclick="gmStart(\'daily\')">▶ Kunlik savollarni boshlash</button>');
}
function quGamesHtml() {
  const b = gmLS('gm_best', {}), stats = gmLS('gm_stats', {}); const chip = (k, u) => b[k] ? '<i class="quRecChip">Rekord ' + b[k] + (u || '') + '</i>' : '<i class="quRecChip new">Yangi</i>';
  const card = (cls, ico, name, txt, rec, btns) => '<div class="quG ' + cls + '"><div class="quGt"><span class="quGi">' + ico + '</span><div><b>' + name + '</b><small>' + txt + '</small></div>' + rec + '</div><div class="quGb">' + btns + '</div></div>';
  return card('g1', '⚔️', 'Bellashuv', 'Raqib bilan 5 ta savol. G‘olib +20 ⭐' + (stats.duelWins ? ' • ' + stats.duelWins + ' g‘alaba' : ''), chip('duel', '/5'),
      '<button type="button" class="quBtn" onclick="qzStartGhost()">🔀 Tasodifiy raqib</button><button type="button" class="quBtn alt" onclick="gmStart(\'duel\')">👥 Do‘st bilan</button>')
    + card('g2', '🔤', 'So‘z ustasi', '60 soniya. Imlo, sinonim, paronim, omonim. Kombo vaqt beradi', chip('soz'), '<button type="button" class="quBtn" onclick="gmStart(\'soz\')">▶ O‘ynash</button>')
    + card('g3', '❤️', 'Omon qolish', '3 jon. Savollar tobora qiyinlashadi, zaif mavzularingizdan', chip('surv'), '<button type="button" class="quBtn" onclick="gmStart(\'surv\')">▶ O‘ynash</button>');
}
function quContestHtml() {
  const open = (QZT || []).filter(t => t.state === 'open').length, soon = (QZT || []).filter(t => t.state === 'soon').length;
  const tsub = open ? open + ' ta faol turnir' : soon ? 'Tez orada boshlanadi' : 'Musobaqalar va sovrinlar';
  const rsub = QZ && QZ.region_set === false ? 'Viloyatingizni tanlang' : 'Har kuni 10 ta savol';
  return '<div class="qzNav"><button type="button" onclick="qzOpenRegion()"><span class="qzIc">📍</span><b>Viloyatlar bellashuvi</b><small>' + rsub + '</small></button>'
    + '<button type="button" onclick="qzOpenTours()"><span class="qzIc">🏆</span><b>Turnirlar</b><small>' + tsub + '</small>' + (open ? '<i class="qzLive">LIVE</i>' : '') + '</button></div>';
}
function quTailHtml(st) {
  const stats = gmLS('gm_stats', {}), b = gmLS('gm_best', {}), topic = gmLS('gm_topic', {}), pk = st && st.perks, bs = (st && st.best_streak) || 0;
  const allCats = Object.keys(GM_CATS).every(k => topic[k] && topic[k].t > 0);
  const badges = [['📚', '100 savol', (stats.answered || 0) >= 100], ['⚔️', '3 g‘alaba', (stats.duelWins || 0) >= 3], ['🔤', 'So‘z ustasi 15+', (b.soz || 0) >= 15], ['❤️', 'Omon qolish 15+', (b.surv || 0) >= 15],
    ['🔥', '7 kun seriya', bs >= 7], ['🏅', '30 kun seriya', bs >= 30], ['🧭', 'Barcha mavzular', allCats], ['🤝', 'Elchi: 3 do‘st', !!(pk && pk.elchi)]];
  let h = '<h3 class="gmH">🏅 Yutuqlar</h3><div class="gmBadges">' + badges.map(x => '<div class="gmBd' + (x[2] ? ' on' : '') + '"><span>' + x[0] + '</span><small>' + x[1] + '</small></div>').join('') + '</div>';
  const w = st && st.week;
  h += '<h3 class="gmH">🏆 Haftalik reyting' + (w && w.range ? '<small> ' + gmEsc(w.range) + '</small>' : '') + '</h3>';
  if (w && w.top && w.top.length) {
    h += '<div class="gmTop10">' + w.top.map(r => '<div class="gmRow' + (r.me ? ' me' : '') + '"><span class="gmRk">' + (r.rank <= 3 ? ['🥇', '🥈', '🥉'][r.rank - 1] : r.rank) + '</span><span class="gmNm">' + gmEsc(r.name) + '</span><b>' + r.pts + '</b></div>').join('') + '</div>';
    h += '<p class="muted gmMe">' + (w.me ? 'Sizning o‘rningiz: <b>' + w.me.rank + '</b> • ' + w.me.pts + ' ball' : 'Siz hali ball yig‘magansiz — birinchi o‘yinni boshlang!') + '</p>';
  } else h += '<p class="muted">Bu hafta hali hech kim ball yig‘magan. Birinchi bo‘ling! 🚀</p>';
  return h + '<p class="muted gmNote">Har to‘g‘ri javob = 1 ball. Bu reyting rasmiy «Reyting» va sovrinlardan alohida, o‘yin-kulgi uchun.</p>';
}
function quRenderHub(st) {
  const box = $('gmBody'); if (!box) return; st = st || GM_STATE || null; const pk = st && st.perks;
  box.innerHTML = '<div id="qzTop" class="qzWrap">' + quHeadHtml(st) + '</div>' + quGiftBar() + quDailyHtml(st)
    + '<h3 class="gmH">O‘yinlar</h3>' + quGamesHtml()
    + '<h3 class="gmH">Musobaqalar</h3>' + quContestHtml()
    + ((QZ && (QZ.gift || QZ.tasks)) ? '<h3 class="gmH">Bugungi mukofotlar</h3><div class="qzWrap">' + (QZ.gift ? qzGiftHtml(QZ.gift) : '') + (QZ.tasks ? qzTasksHtml(QZ.tasks) : '') + '</div>' : '')
    + gmInviteBand(pk) + quTailHtml(st) + gmAdminBlock();
}
gmRenderHub = function (st) { quRenderHub(st); };
qzDecorateHub = function () { quRenderHub(GM_STATE); };

// ---------- 6) «Mashq» sahifasi tepasidagi karta ----------
let QU_ST_AT = 0;
function quHeroPaint() {
  const el = $('mqGameHero'); if (!el) return;
  const st = GM_STATE, streak = (st && st.streak) || 0, done = !!(st && st.today_done), stars = QZ ? QZ.stars : null;
  el.innerHTML = '<div class="mqhTop"><div class="mqhTx"><b>Ona tilini o‘ynab o‘rganamiz</b><small>' + (done ? 'Bugungi 5 savol bajarildi ✓ Endi raqibni yenging' : 'Bugungi 5 savol sizni kutmoqda') + '</small></div>'
    + '<div class="mqhChips">' + (streak ? '<i>🔥 ' + streak + '</i>' : '') + (stars != null ? '<i>⭐ ' + stars + '</i>' : '') + '</div></div>'
    + '<button type="button" class="mqhGo" onclick="' + (done ? 'qzStartGhost()' : 'gmStart(\'daily\')') + '">' + (done ? '⚔️ Bellashuvni boshlash' : '▶ Kunlik savollarni boshlash') + '</button>'
    + '<div class="mqhRow"><button type="button" onclick="qzStartGhost()"><span>⚔️</span>Bellashuv</button><button type="button" onclick="gmStart(\'soz\')"><span>🔤</span>So‘z ustasi</button>'
    + '<button type="button" onclick="gmStart(\'surv\')"><span>❤️</span>Omon qolish</button><button type="button" class="all" onclick="openSection(\'games\')"><span>›</span>Barchasi</button></div>';
}
async function quMashqHero() {
  quHeroPaint();
  if (!(tg && tg.initData) || Date.now() - QU_ST_AT < 45000) return;
  QU_ST_AT = Date.now();
  try { const r = await apiFetch(apiUrl('/api/game/state')); const d = await r.json(); if (d && d.ok) GM_STATE = d; } catch (e) {}
  try { await qzLoad(); } catch (e) {}
  quHeroPaint();
}
const _qu_openSection = openSection;
openSection = function (id) { const r = _qu_openSection.apply(this, arguments); if (id === 'mashq') { try { quMashqHero(); } catch (e) {} } return r; };
window.addEventListener('load', () => { try { quHeroPaint(); } catch (e) {} });
