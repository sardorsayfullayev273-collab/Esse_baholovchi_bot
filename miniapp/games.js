// ===== 🎮 Ona tilini o‘ynab o‘rganamiz (v41) =====
// Hamma o‘yin telefonning o‘zida ishlaydi: savollar tayyor lug‘atlardan (imlo, sinonim, paronim, omonim) yasaladi.
// AI chaqirilmaydi — xarajat yo‘q. Serverga faqat natija (to‘g‘ri javoblar soni) yuboriladi.

const GM_TYPES = {
  imlo:    { ico: '✍️', name: 'Imlo', title: 'Qaysi biri to‘g‘ri?', desc: 'Ikki yozilishdan to‘g‘risini toping' },
  sinonim: { ico: '🔗', name: 'Sinonim', title: 'Ortiqchasini top', desc: 'Ma’nodosh bo‘lmagan so‘zni toping' },
  paronim: { ico: '🔀', name: 'Paronim', title: 'Bo‘sh joyni to‘ldir', desc: 'Gapga mos paronimni tanlang' },
  omonim:  { ico: '🎭', name: 'Omonim', title: 'Qaysi ma’noda?', desc: 'So‘z gapda nimani bildiradi' },
};
const GM_LIVES = 3;
const GMD = { ready: false, loading: null };
let GM = null;          // joriy o‘yin
let GM_STATE = null;    // serverdan kelgan holat (seriya, reyting)

// ---------- yordamchilar ----------
function gmRng(seed) { let a = seed >>> 0; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function gmHash(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function gmPick(arr, rnd) { return arr[Math.floor(rnd() * arr.length)]; }
function gmShuffle(arr, rnd) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
function gmDayKey() { return new Date(Date.now() + 5 * 3600 * 1000).toISOString().slice(0, 10); }   // Toshkent sanasi
function gmNorm(s) { return String(s || '').toLowerCase().trim().replace(/[‘’ʻʼ`']/g, "'"); }
function gmPretty(w) { return w.replace(/([oOgG])['’‘ʻʼ`]/g, '$1\u0001').replace(/['’‘ʻʼ`]/g, '’').replace(/\u0001/g, '‘'); }
function gmEsc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function gmLS(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
function gmLSset(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

// ---------- ma’lumotlarni yuklash ----------
async function gmLoad() {
  if (GMD.ready) return true;
  if (GMD.loading) return GMD.loading;
  GMD.loading = (async () => {
    const get = async f => { const r = await fetch(f); if (!r.ok) throw new Error(f); return r.json(); };
    try {
      const [d, s, p, o, a] = await Promise.all([get('dictionary.json'), get('sinonim.json'), get('paronim.json'), get('omonim.json?v=41'), get('active1000.json').catch(() => [])]);
      gmPrep(d, s, p, o, a);
      GMD.ready = true; return true;
    } catch (e) { console.error(e); return false; }
    finally { GMD.loading = null; }
  })();
  return GMD.loading;
}

function gmPrep(d, s, p, o, a) {
  // --- imlo
  const iw = []; const dset = new Set();
  for (const raw of d) {
    if (typeof raw !== 'string') continue;
    dset.add(gmNorm(raw));
    if (raw.length < 4 || raw.length > 14 || raw !== raw.toLowerCase()) continue;
    const w = gmPretty(raw);
    if (/^[a-z‘’]{4,13}$/.test(w)) iw.push(w);
  }
  const hasHX = w => /x/.test(w) || /(^|[^sc])h/.test(w);
  const pools = { apos: [], dbl: [], hx: [], qk: [] };
  for (const w of iw) {
    if (/[og]‘|’/.test(w)) pools.apos.push(w);
    if (/([bdfjklmnpqrstvxyz])\1/.test(w)) pools.dbl.push(w);
    if (hasHX(w)) pools.hx.push(w);
    if (/[qk]/.test(w)) pools.qk.push(w);
  }
  GMD.dset = dset; GMD.pools = pools;
  // tanish so‘zlar: faol 1000, sinonim, paronim, omonim ro‘yxatlaridagi so‘zlar (savollar tanishroq bo‘lishi uchun)
  const cand = new Set(); const addC = x => { const w = gmPretty(String(x || '').trim().toLowerCase()); if (/^[a-z‘’]{4,13}$/.test(w) && dset.has(gmNorm(w))) cand.add(w); };
  (a || []).forEach(x => String(x).split(/[\s,;\/]+/).forEach(addC));
  s.forEach(e => (e.h || []).forEach(addC));
  p.forEach(e => (e.w || []).forEach(w => addC(w.w)));
  (o || []).forEach(e => addC(e.w));
  const cp = { apos: [], dbl: [], hx: [], qk: [] };
  for (const w of cand) {
    if (/[og]‘|’/.test(w)) cp.apos.push(w);
    if (/([bdfjklmnpqrstvxyz])\1/.test(w)) cp.dbl.push(w);
    if (hasHX(w)) cp.hx.push(w);
    if (/[qk]/.test(w)) cp.qk.push(w);
  }
  GMD.cpools = cp;
  // --- sinonim
  const idx = new Map(); const sets = [];
  s.forEach((e, id) => {
    (e.h || []).forEach(x => { const k = gmNorm(x); if (!idx.has(k)) idx.set(k, new Set()); idx.get(k).add(id); });
    const words = (e.h || []).map(x => String(x).trim()).filter(x => x && !/[\s,;()]/.test(x));
    if (words.length >= 3 && words.every(x => dset.has(gmNorm(x)))) sets.push({ id, words });
  });
  GMD.sinIdx = idx; GMD.sinSets = sets;
  // --- paronim
  const ex = [];
  for (const e of p) {
    if (!e.w || e.w.length < 2) continue;
    e.w.forEach((w, wi) => {
      const key = gmNorm(w.w); if (!key || /\s/.test(key)) return;
      (w.ex || []).forEach(t => { const r = gmParSentence(t, key); if (r) ex.push({ e, wi, r }); });
    });
  }
  GMD.parEx = ex;
  // --- omonim
  GMD.omo = (o || []).filter(x => x.s && x.s.length >= 2 && x.s.every(m => m.ex && m.ex.length));
}

function gmParSentence(text, key) {
  let t = String(text).replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  const sents = t.match(/[^.!?…]+[.!?…]*/g) || [];
  for (let s of sents) {
    s = s.trim().replace(/^[—–-]\s*/, '');
    if (s.length < 25 || s.length > 150) continue;
    for (const m of s.matchAll(/[A-Za-zʻ‘’'`ʼ]+/g)) {
      const tok = m[0];
      if (tok.length < key.length || tok.length > key.length + 5) continue;
      if (gmNorm(tok).startsWith(key)) return { pre: s.slice(0, m.index), suf: tok.slice(key.length), post: s.slice(m.index + tok.length) };
    }
  }
  return null;
}

// ---------- savol yasash ----------
function gmMut(rule, w, rnd) {
  const pos = (re) => { const r = []; let m; const g = new RegExp(re.source, 'g'); while ((m = g.exec(w))) r.push(m.index); return r; };
  if (rule === 'apos') {
    const og = pos(/[og]‘/).map(i => i + 1), tu = pos(/’/);
    const ways = [];
    if (og.length) ways.push(() => { const p = gmPick(og, rnd); return { wrong: w.slice(0, p) + w.slice(p + 1), label: 'o‘ va g‘ harflari belgi (‘) bilan yoziladi.' }; });
    if (tu.length) {
      ways.push(() => { const p = gmPick(tu, rnd); return { wrong: w.slice(0, p) + w.slice(p + 1), label: 'Tutuq belgisi (’) tushib qolmasligi kerak.' }; });
      ways.push(() => { const p = gmPick(tu, rnd); return { wrong: w.slice(0, p) + '‘' + w.slice(p + 1), label: 'Tutuq belgisi (’) bilan o‘ / g‘ belgisini (‘) adashtirmang.' }; });
    }
    return ways.length ? gmPick(ways, rnd)() : null;
  }
  if (rule === 'dbl') {
    const p = pos(/([bdfjklmnpqrstvxyz])\1/); if (!p.length) return null; const i = gmPick(p, rnd);
    return { wrong: w.slice(0, i) + w.slice(i + 1), label: 'Qo‘sh undosh (ikki harf) saqlanadi.' };
  }
  if (rule === 'hx') {
    const p = [];
    for (let i = 0; i < w.length; i++) { if (w[i] === 'x' || (w[i] === 'h' && !(i > 0 && (w[i - 1] === 's' || w[i - 1] === 'c')))) p.push(i); }
    if (!p.length) return null; const i = gmPick(p, rnd);
    return { wrong: w.slice(0, i) + (w[i] === 'x' ? 'h' : 'x') + w.slice(i + 1), label: 'H va X harflarini adashtirmang.' };
  }
  if (rule === 'qk') {
    const p = pos(/[qk]/); if (!p.length) return null; const i = gmPick(p, rnd);
    return { wrong: w.slice(0, i) + (w[i] === 'q' ? 'k' : 'q') + w.slice(i + 1), label: 'Q va K harflarini adashtirmang.' };
  }
  return null;
}

function gmQImlo(rnd) {
  for (let tr = 0; tr < 80; tr++) {
    const r = rnd(); const rule = r < .38 ? 'apos' : r < .62 ? 'dbl' : r < .80 ? 'hx' : 'qk';
    const cp = GMD.cpools[rule]; const pool = (cp.length > 20 && rnd() < .8) ? cp : GMD.pools[rule]; if (!pool.length) continue;
    const w = gmPick(pool, rnd); const m = gmMut(rule, w, rnd);
    if (!m || m.wrong === w || GMD.dset.has(gmNorm(m.wrong))) continue;
    const first = rnd() < .5;
    return { t: 'imlo', q: 'Qaysi yozilishi to‘g‘ri?', opts: first ? [w, m.wrong] : [m.wrong, w], ans: first ? 0 : 1, exp: 'To‘g‘ri yozilishi: «' + w + '». ' + m.label };
  }
  return null;
}

function gmQSin(rnd) {
  const sets = GMD.sinSets; if (!sets.length) return null;
  for (let tr = 0; tr < 60; tr++) {
    const A = gmPick(sets, rnd);
    const three = gmShuffle(A.words, rnd).slice(0, 3);
    const ids = new Set(); three.forEach(x => (GMD.sinIdx.get(gmNorm(x)) || []).forEach(i => ids.add(i)));
    const B = gmPick(sets, rnd); if (B.id === A.id) continue;
    const odd = gmPick(B.words, rnd); const on = gmNorm(odd);
    if (three.some(x => gmNorm(x) === on)) continue;
    const oi = GMD.sinIdx.get(on); if (oi && [...oi].some(i => ids.has(i))) continue;
    const opts = gmShuffle(three.concat([odd]), rnd);
    return { t: 'sinonim', q: 'Qaysi so‘z qolganlariga ma’nodosh emas?', opts, ans: opts.indexOf(odd), exp: 'Ma’nodosh so‘zlar: ' + three.join(', ') + '. «' + odd + '» ularga ma’nodosh emas.' };
  }
  return null;
}

function gmQPar(rnd) {
  const ex = GMD.parEx; if (!ex.length) return null;
  for (let tr = 0; tr < 40; tr++) {
    const it = gmPick(ex, rnd); const ws = it.e.w;
    const right = ws[it.wi]; const others = ws.filter((_, i) => i !== it.wi);
    const other = gmPick(others, rnd); if (gmNorm(other.w) === gmNorm(right.w)) continue;
    const a = right.w.toLowerCase(), b = other.w.toLowerCase(); const first = rnd() < .5;
    const cut = s => String(s || '').replace(/\s+/g, ' ').slice(0, 130);
    return { t: 'paronim', q: 'Bo‘sh joyga mos so‘zni tanlang:', sentPlain: it.r.pre + '_____' + it.r.suf + it.r.post, sentParts: [it.r.pre, it.r.suf + it.r.post],
             opts: first ? [a, b] : [b, a], ans: first ? 0 : 1, exp: '«' + a + '» — ' + cut(right.m) + '\n«' + b + '» — ' + cut(other.m) };
  }
  return null;
}

function gmQOmo(rnd) {
  const list = GMD.omo; if (!list.length) return null;
  for (let tr = 0; tr < 20; tr++) {
    const it = gmPick(list, rnd); const k = Math.floor(rnd() * it.s.length); const meaning = it.s[k];
    const sentence = gmPick(meaning.ex, rnd); const mm = sentence.match(/\[([^\]]+)\]/); if (!mm) continue;
    let labels = it.s.map(x => x.m);
    if (labels.length < 3) {
      const o = gmPick(list, rnd); if (o.w !== it.w) { const extra = gmPick(o.s, rnd).m; if (!labels.includes(extra)) labels = labels.concat([extra]); }
    }
    const opts = gmShuffle(labels, rnd);
    return { t: 'omonim', q: '«' + it.w + '» so‘zi bu gapda qaysi ma’noda?', sentHtml: gmEsc(sentence).replace(/\[([^\]]+)\]/, '<b>$1</b>'),
             opts, ans: opts.indexOf(meaning.m), exp: '«' + it.w + '» omonimi: ' + it.s.map((x, i) => (i + 1) + ') ' + x.m).join('; ') + '.' };
  }
  return null;
}

const GM_MAKERS = { imlo: gmQImlo, sinonim: gmQSin, paronim: gmQPar, omonim: gmQOmo };
function gmQKey(q) { return q.t + '|' + q.q + '|' + (q.sentPlain || q.sentHtml || '') + '|' + q.opts.join('/'); }
function gmMake(type, rnd, used) {
  for (let i = 0; i < 40; i++) { const q = GM_MAKERS[type](rnd); if (!q) continue; const k = gmQKey(q); if (used.has(k)) continue; used.add(k); return q; }
  return null;
}

// ---------- o‘yinni boshlash ----------
async function gmStart(type) {
  const box = $('gpBody'); gmShowPlay(); box.innerHTML = '<div class="word">⏳ Savollar tayyorlanmoqda...</div>';
  if (!(await gmLoad())) { notify('Ma’lumotlar yuklanmadi. Internetni tekshirib, qayta urinib ko‘ring.'); gmQuit(); return; }
  const used = new Set(); let qs = [], rnd = Math.random, total = 10, tsec = 15;
  if (type === 'daily') {
    rnd = gmRng(gmHash('daily' + gmDayKey())); total = 5; tsec = 20;
    const seq = ['imlo', 'sinonim', 'paronim', 'omonim']; seq.push(gmPick(seq, rnd));
    for (const t of gmShuffle(seq, rnd)) { const q = gmMake(t, rnd, used); if (q) qs.push(q); }
  } else if (type === 'mistakes') {
    qs = gmShuffle(gmLS('gm_wrong', []), Math.random).slice(0, 10); total = qs.length;
    if (!qs.length) { notify('Xatolar daftari hozircha bo‘sh. Avval o‘yin o‘ynang.'); gmQuit(); return; }
  } else {
    for (let i = 0; i < total; i++) { const q = gmMake(type, rnd, used); if (q) qs.push(q); }
  }
  if (!qs.length) { notify('Savol yasab bo‘lmadi. Keyinroq urinib ko‘ring.'); gmQuit(); return; }
  GM = { type, qs, i: 0, lives: type === 'daily' || type === 'mistakes' ? 99 : GM_LIVES, correct: 0, answered: 0, combo: 0, best: 0, locked: false, tsec, tleft: tsec, timer: null };
  try { trackView('game:' + type); } catch (e) {}
  gmRenderQ();
}

function gmShowPlay() { document.querySelectorAll('main').forEach(x => x.classList.add('hidden')); $('gamePlay').classList.remove('hidden'); window.scrollTo(0, 0); }
function gmQuit() { if (GM && GM.timer) clearInterval(GM.timer); GM = null; openSection('games'); }

function gmRenderQ() {
  const g = GM; if (!g) return; const q = g.qs[g.i]; const box = $('gpBody');
  const hearts = (g.type === 'daily' || g.type === 'mistakes') ? '' : '❤️'.repeat(g.lives) + '🖤'.repeat(GM_LIVES - g.lives);
  const info = GM_TYPES[q.t] || {};
  box.innerHTML =
    '<div class="gmTop"><span>' + (hearts || '📅') + '</span><span class="gmTag">' + (info.ico || '') + ' ' + (info.name || '') + '</span><span>' + (g.i + 1) + '/' + g.qs.length + '</span></div>'
    + '<div class="gmBar"><i id="gmBarI"></i></div>'
    + '<div class="gmQ"><div class="gmQt">' + gmEsc(q.q) + '</div>'
    + (q.sentParts ? '<div class="gmSent">' + gmEsc(q.sentParts[0]) + '<u class="gmBlank">&nbsp;&nbsp;?&nbsp;&nbsp;</u>' + gmEsc(q.sentParts[1]) + '</div>' : '')
    + (q.sentHtml ? '<div class="gmSent">' + q.sentHtml + '</div>' : '') + '</div>'
    + '<div class="gmOpts">' + q.opts.map((o, i) => '<button type="button" class="gmOpt" id="gmo' + i + '" onclick="gmAnswer(' + i + ')">' + gmEsc(o) + '</button>').join('') + '</div>'
    + '<div id="gmFb"></div>'
    + '<div class="gmFoot">⭐ ' + g.correct + (g.combo >= 3 ? ' • 🔥 ' + g.combo + ' ketma-ket' : '') + '</div>';
  g.locked = false; g.tleft = g.tsec; if (g.timer) clearInterval(g.timer);
  g.timer = setInterval(() => {
    if (!GM || GM.locked) return; GM.tleft -= 0.1;
    const el = $('gmBarI'); if (el) { el.style.width = Math.max(0, GM.tleft / GM.tsec * 100) + '%'; if (GM.tleft < 5) el.classList.add('low'); }
    if (GM.tleft <= 0) gmAnswer(-1);
  }, 100);
  window.scrollTo(0, 0);
}

function gmHaptic(ok) { try { tg?.HapticFeedback?.notificationOccurred(ok ? 'success' : 'error'); } catch (e) {} }

function gmAnswer(i) {
  const g = GM; if (!g || g.locked) return; g.locked = true; clearInterval(g.timer);
  const q = g.qs[g.i]; const ok = (i === q.ans); g.answered++;
  document.querySelectorAll('.gmOpt').forEach(b => b.disabled = true);
  const right = $('gmo' + q.ans); if (right) right.classList.add('right');
  if (ok) { g.correct++; g.combo++; g.best = Math.max(g.best, g.combo); }
  else { g.combo = 0; if (g.type !== 'daily' && g.type !== 'mistakes') g.lives--; const w = $('gmo' + i); if (w) w.classList.add('wrong'); }
  gmHaptic(ok); gmMistake(q, ok, g.type);
  const last = (g.i + 1 >= g.qs.length) || g.lives <= 0;
  $('gmFb').innerHTML = '<div class="gmFb ' + (ok ? 'ok' : 'bad') + '"><b>' + (ok ? '✅ To‘g‘ri!' : (i < 0 ? '⏰ Vaqt tugadi' : '❌ Noto‘g‘ri')) + '</b><p>' + gmEsc(q.exp).replace(/\n/g, '<br>') + '</p>'
    + '<button type="button" class="primaryAction" onclick="' + (last ? 'gmFinish()' : 'gmNext()') + '">' + (last ? 'Natijani ko‘rish' : 'Keyingisi →') + '</button></div>';
  const fb = $('gmFb'); if (fb) fb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function gmNext() { if (!GM) return; GM.i++; gmRenderQ(); }

// ---------- xatolar daftari ----------
function gmMistake(q, ok, type) {
  let list = gmLS('gm_wrong', []); const k = gmQKey(q);
  if (ok) { if (type === 'mistakes') { list = list.filter(x => gmQKey(x) !== k); gmLSset('gm_wrong', list); } return; }
  if (list.some(x => gmQKey(x) === k)) return;
  list.unshift({ t: q.t, q: q.q, sentParts: q.sentParts, sentHtml: q.sentHtml, sentPlain: q.sentPlain, opts: q.opts, ans: q.ans, exp: q.exp });
  gmLSset('gm_wrong', list.slice(0, 40));
}

// ---------- natija ----------
async function gmSubmit(type, correct, total) {
  if (!tg?.initData) return null;
  try {
    const r = await apiFetch(apiUrl('/api/game/submit'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ game: type, correct, total }) });
    const d = await r.json(); return d && d.ok ? d : null;
  } catch (e) { return null; }
}

async function gmFinish() {
  const g = GM; if (!g) return; clearInterval(g.timer);
  const { type, correct, answered } = g; const total = Math.max(1, answered);
  const bests = gmLS('gm_best', {}); if (!bests[type] || correct > bests[type]) { bests[type] = correct; gmLSset('gm_best', bests); }
  const pct = correct / total; const medal = pct >= .9 ? '🏆' : pct >= .7 ? '🥇' : pct >= .5 ? '👍' : '💪';
  const title = type === 'daily' ? 'Kunlik 5 savol' : type === 'mistakes' ? 'Xatolar ustida ishlash' : (GM_TYPES[type] || {}).name;
  const box = $('gpBody');
  box.innerHTML = '<div class="gmRes"><div class="gmMedal">' + medal + '</div><h2>' + gmEsc(title) + '</h2><div class="gmBig">' + correct + ' / ' + total + '</div>'
    + '<p class="muted">' + (pct >= .7 ? 'Zo‘r natija!' : pct >= .5 ? 'Yomon emas, davom eting!' : 'Mashq qilsangiz, albatta oshadi!') + '</p>'
    + '<div id="gmSrv" class="gmSrv">⏳ Natija saqlanmoqda...</div>'
    + '<div class="gmBtns"><button type="button" class="primaryAction" id="gmShareBtn" onclick="gmShare(' + correct + ',' + total + ')">📤 Do‘stlarga ulashish</button>'
    + (type === 'daily' ? '' : '<button type="button" class="bpGhost" onclick="gmStart(\'' + type + '\')">🔁 Yana o‘ynash</button>')
    + '<button type="button" class="bpGhost" onclick="gmQuit()">‹ O‘yinlar</button></div></div>';
  GM = null;
  const res = await gmSubmit(type, correct, answered);
  const el = $('gmSrv'); if (!el) return;
  if (res) {
    GM_STATE = res;
    el.innerHTML = (res.already ? 'ℹ️ Bugungi kunlik savollar allaqachon hisoblangan.' : '⭐ +' + (res.gained || 0) + ' ball (haftalik o‘yin reytingiga)')
      + (res.streak ? '<br>🔥 Seriya: <b>' + res.streak + ' kun</b>' : '');
    window.GM_LASTSTREAK = res.streak || 0;
  } else { el.textContent = tg?.initData ? 'Natija serverga yuborilmadi (internet?).' : 'Natija faqat Telegram ichida saqlanadi.'; }
}

function gmShare(correct, total) {
  const link = (typeof ME !== 'undefined' && ME.ref_link) || ((typeof ME !== 'undefined' && ME.bot_username) ? 'https://t.me/' + ME.bot_username : '');
  const st = window.GM_LASTSTREAK ? ' • 🔥 ' + window.GM_LASTSTREAK + ' kun' : '';
  const text = '🎮 «Ona tilini o‘ynab o‘rganamiz»: ' + correct + '/' + total + st + '. Imlo, sinonim, paronim, omonim — sen ham sinab ko‘r!';
  if (!link) { notify(text); return; }
  openShare(link, text);
}

// ---------- bosh sahifa (o‘yinlar bo‘limi) ----------
async function gmOpenHub() {
  gmRenderHub(GM_STATE);
  try { const r = await apiFetch(apiUrl('/api/game/state')); const d = await r.json(); if (d && d.ok) { GM_STATE = d; gmRenderHub(d); } } catch (e) {}
  gmLoad();   // fon rejimida oldindan yuklab qo‘yamiz
}

function gmRenderHub(st) {
  const box = $('gmBody'); if (!box) return; const bests = gmLS('gm_best', {}); const wrong = gmLS('gm_wrong', []).length;
  let h = '';
  const done = st && st.today_done;
  h += '<div class="gmDaily"><div class="gmDl"><b>📅 Kunlik 5 savol</b><small>' + (done ? '✅ Bugun bajarildi' + (st.daily ? ': ' + st.daily.correct + '/' + st.daily.total : '') + ' • ertaga yangi savollar' : 'Hamma uchun bir xil • har kuni yangi • +3 bonus ball') + '</small></div>'
    + '<div class="gmStreak"><span>🔥</span><b>' + ((st && st.streak) || 0) + '</b><small>kun</small></div></div>'
    + '<button type="button" class="primaryAction gmDailyBtn" ' + (done ? 'disabled' : '') + ' onclick="gmStart(\'daily\')">' + (done ? '✅ Bugun bajarildi' : '▶️ Boshlash') + '</button>';
  h += '<h3 class="gmH">O‘yinlar</h3><div class="gmGrid">' + Object.keys(GM_TYPES).map(k => {
    const t = GM_TYPES[k]; return '<button type="button" class="gmTile" onclick="gmStart(\'' + k + '\')"><b>' + t.ico + '</b><strong>' + t.title + '</strong><small>' + t.desc + '</small>' + (bests[k] ? '<em>Rekord: ' + bests[k] + '/10</em>' : '<em>' + t.name + '</em>') + '</button>'; }).join('') + '</div>';
  h += '<button type="button" class="gmWrong" onclick="gmStart(\'mistakes\')">📒 Xatolarim <span>' + wrong + ' ta</span><small>Adashgan savollaringizni qayta yeching</small></button>';
  const wk = st && st.week;
  h += '<h3 class="gmH">🏆 Haftalik o‘yin reytingi' + (wk && wk.range ? '<small> ' + gmEsc(wk.range) + '</small>' : '') + '</h3>';
  if (wk && wk.top && wk.top.length) {
    h += '<div class="gmTop10">' + wk.top.map(r => '<div class="gmRow' + (r.me ? ' me' : '') + '"><span class="gmRk">' + (r.rank <= 3 ? ['🥇', '🥈', '🥉'][r.rank - 1] : r.rank) + '</span><span class="gmNm">' + gmEsc(r.name) + '</span><b>' + r.pts + '</b></div>').join('') + '</div>';
    h += '<p class="muted gmMe">' + (wk.me ? 'Sizning o‘rningiz: <b>' + wk.me.rank + '</b> • ' + wk.me.pts + ' ball' : 'Siz hali ball yig‘magansiz — birinchi o‘yinni boshlang!') + '</p>';
  } else { h += '<p class="muted">Bu hafta hali hech kim ball yig‘magan. Birinchi bo‘ling! 🚀</p>'; }
  h += '<p class="muted gmNote">Har to‘g‘ri javob = 1 ball. Bu reyting rasmiy «Reyting» va sovrinlardan alohida, o‘yin-kulgi uchun.</p>';
  box.innerHTML = h;
}
