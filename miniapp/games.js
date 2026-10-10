// ===== 🎮 Ona tilini o‘ynab o‘rganamiz (v43) =====
// Hamma o‘yin telefonning o‘zida ishlaydi: savollar tayyor lug‘atlar va dtm_bank.json (DTM / Milliy sertifikat formatidagi
// yopiq, moslashtirish va ochiq javobli savollar) dan yasaladi. AI chaqirilmaydi — xarajat yo‘q.
// Serverga faqat natija (to‘g‘ri javoblar soni) yuboriladi.

const GM_TYPES = {
  imlo:    { ico: '✍️', name: 'Imlo', title: 'Qaysi biri to‘g‘ri?', desc: 'Imlo qoidalari bo‘yicha to‘g‘ri yozilishni toping' },
  sinonim: { ico: '🔗', name: 'Sinonim', title: 'Ma’nodoshini top', desc: 'Ma’nodosh yoki ortiqcha so‘zni toping' },
  paronim: { ico: '🔀', name: 'Paronim', title: 'Bo‘sh joyni to‘ldir', desc: 'Gapga mos paronimni tanlang' },
  omonim:  { ico: '🎭', name: 'Omonim', title: 'Qaysi ma’noda?', desc: 'So‘z gapda nimani bildiradi' },
};
const GM_CATS = {
  imlo:  { ico: '✍️', name: 'Imlo' },
  soz:   { ico: '🧩', name: 'So‘z yasalishi' },
  morf:  { ico: '🔤', name: 'Morfologiya' },
  sint:  { ico: '📐', name: 'Sintaksis' },
  punk:  { ico: '❗', name: 'Punktuatsiya' },
  leks:  { ico: '📖', name: 'Leksikologiya' },
  usl:   { ico: '🎙', name: 'Uslubiyat' },
  nazar: { ico: '🎼', name: 'Adabiyot nazariyasi' },
  tarix: { ico: '🏛', name: 'Adabiyot tarixi' },
  matn:  { ico: '📄', name: 'Matn bilan ishlash' },
};
const GM_RANKS = [[0, 'Yangi boshlovchi', '🌱'], [60, 'Izlanuvchi', '🔎'], [200, 'Bilimdon', '📘'], [450, 'Mohir', '🎯'], [900, 'Ustoz', '🎓'], [1600, 'Alloma', '👑']];
const GM_LIVES = 3;
const GM_LIVE_TYPES = { imlo: 1, sinonim: 1, paronim: 1, omonim: 1 };
const GMD = { ready: false, loading: null, bank: null, bankLoading: null };
let GM = null;          // joriy o‘yin
let GM_STATE = null;    // serverdan kelgan holat (seriya, reyting)

// ---------- yordamchilar ----------
function gmRng(seed) { let a = seed >>> 0; return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function gmHash(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
function gmPick(arr, rnd) { return arr[Math.floor(rnd() * arr.length)]; }
function gmShuffle(arr, rnd) { const a = arr.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); const t = a[i]; a[i] = a[j]; a[j] = t; } return a; }
function gmDayKey() { return new Date(Date.now() + 5 * 3600 * 1000).toISOString().slice(0, 10); }   // Toshkent sanasi
function gmNorm(s) { return String(s || '').toLowerCase().trim().replace(/[‘’ʻʼ`']/g, "'"); }
function gmNormAns(s) { return gmNorm(s).replace(/[«»"“”]/g, '').replace(/\s+/g, ' ').replace(/^[-–—\s]+|[.\s]+$/g, ''); }
function gmPretty(w) { return w.replace(/([oOgG])['’‘ʻʼ`]/g, '$1\u0001').replace(/['’‘ʻʼ`]/g, '’').replace(/\u0001/g, '‘'); }
function gmEsc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
function gmEscBr(s) { return gmEsc(s).replace(/\n/g, '<br>'); }
function gmLS(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
function gmLSset(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
function gmLevel() { return gmLS('gm_level', 'dtm') === 'oson' ? 'oson' : 'dtm'; }
const gmHasHX = w => /x/.test(w) || /(^|[^sc])h/.test(w);
function gmRulesOf(w) {
  const r = [];
  if (/[og]‘|’/.test(w)) r.push('apos');
  if (/([bdfjklmnpqrstvxyz])\1/.test(w)) r.push('dbl');
  if (gmHasHX(w)) r.push('hx');
  if (/[qk]/.test(w)) r.push('qk');
  return r;
}

// ---------- ma’lumotlarni yuklash ----------
async function gmGet(f) { const r = await fetch(f); if (!r.ok) throw new Error(f); return r.json(); }
async function gmLoadBank() {
  if (GMD.bank) return true;
  if (GMD.bankLoading) return GMD.bankLoading;
  GMD.bankLoading = (async () => {
    try { const b = await gmGet('dtm_bank.json?v=43'); GMD.bank = b; GMD.bankById = {}; b.forEach(x => { GMD.bankById[x.id] = x; }); return true; }
    catch (e) { console.error(e); return false; }
    finally { GMD.bankLoading = null; }
  })();
  return GMD.bankLoading;
}
async function gmLoad() {
  if (GMD.ready) return true;
  if (GMD.loading) return GMD.loading;
  GMD.loading = (async () => {
    try {
      const [d, s, p, o, a] = await Promise.all([gmGet('dictionary.json'), gmGet('sinonim.json'), gmGet('paronim.json'), gmGet('omonim.json?v=41'), gmGet('active1000.json').catch(() => [])]);
      gmPrep(d, s, p, o, a);
      await gmLoadBank();
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
  const pools = { apos: [], dbl: [], hx: [], qk: [] };
  for (const w of iw) gmRulesOf(w).forEach(r => pools[r].push(w));
  GMD.dset = dset; GMD.pools = pools;
  // tanish so‘zlar: faol 1000, sinonim, paronim, omonim ro‘yxatlaridagi so‘zlar (savollar tanishroq bo‘lishi uchun)
  const cand = new Set(); const addC = x => { const w = gmPretty(String(x || '').trim().toLowerCase()); if (/^[a-z‘’]{4,13}$/.test(w) && dset.has(gmNorm(w))) cand.add(w); };
  (a || []).forEach(x => String(x).split(/[\s,;\/]+/).forEach(addC));
  s.forEach(e => (e.h || []).forEach(addC));
  p.forEach(e => (e.w || []).forEach(w => addC(w.w)));
  (o || []).forEach(e => addC(e.w));
  const cp = { apos: [], dbl: [], hx: [], qk: [] };
  for (const w of cand) gmRulesOf(w).forEach(r => cp[r].push(w));
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
  p.forEach((e, ei) => {
    if (!e.w || e.w.length < 2) return;
    e.w.forEach((w, wi) => {
      const key = gmNorm(w.w); if (!key || /\s/.test(key)) return;
      (w.ex || []).forEach(t => { const r = gmParSentence(t, key); if (r) ex.push({ e, ei, wi, r }); });
    });
  });
  GMD.parEx = ex; GMD.parList = p;
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

// ---------- tayyor lug‘atlardan savol yasash ----------
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

function gmQImlo(rnd, hard) {
  for (let tr = 0; tr < 120; tr++) {
    const r = rnd(); const rule = r < .38 ? 'apos' : r < .62 ? 'dbl' : r < .80 ? 'hx' : 'qk';
    const cp = GMD.cpools[rule]; const pool = (cp.length > 20 && rnd() < .8) ? cp : GMD.pools[rule]; if (!pool.length) continue;
    const w = gmPick(pool, rnd);
    if (!hard) {
      const m = gmMut(rule, w, rnd);
      if (!m || m.wrong === w || GMD.dset.has(gmNorm(m.wrong))) continue;
      const first = rnd() < .5;
      return { t: 'imlo', q: 'Qaysi yozilishi to‘g‘ri?', opts: first ? [w, m.wrong] : [m.wrong, w], ans: first ? 0 : 1, exp: 'To‘g‘ri yozilishi: «' + w + '». ' + m.label };
    }
    // DTM darajasi: 4 variantdan to‘g‘risini topish yoki 4 so‘zdan xatosini topish
    const rules = gmRulesOf(w); if (!rules.length) continue;
    const wrongs = new Map();
    for (let k = 0; k < 16 && wrongs.size < 3; k++) {
      const m = gmMut(gmPick(rules, rnd), w, rnd);
      if (m && m.wrong !== w && !GMD.dset.has(gmNorm(m.wrong)) && !wrongs.has(m.wrong)) wrongs.set(m.wrong, m.label);
    }
    if (!wrongs.size) continue;
    if (rnd() < .5 && wrongs.size >= 2) {
      const opts = gmShuffle([w].concat([...wrongs.keys()]), rnd);
      return { t: 'imlo', q: 'Qaysi yozilishi to‘g‘ri?', opts, ans: opts.indexOf(w), exp: 'To‘g‘ri yozilishi: «' + w + '». ' + [...new Set(wrongs.values())].join(' ') };
    }
    const bad = [...wrongs.keys()][0]; const others = new Set();
    const src = (GMD.cpools[rule].length > 20 ? GMD.cpools[rule] : GMD.pools[rule]);
    for (let k = 0; k < 40 && others.size < 3; k++) { const o = gmPick(src, rnd); if (o !== w) others.add(o); }
    if (others.size < 3) continue;
    const opts = gmShuffle([bad].concat([...others]), rnd);
    return { t: 'imlo', q: 'Qaysi so‘zda imlo xatosi bor?', opts, ans: opts.indexOf(bad), exp: 'To‘g‘ri yozilishi: «' + w + '» (ko‘rsatilgan variant: «' + bad + '»). ' + wrongs.get(bad) };
  }
  return null;
}

function gmQSin(rnd, hard) {
  const sets = GMD.sinSets; if (!sets.length) return null;
  if (hard && rnd() < .55) {
    for (let tr = 0; tr < 60; tr++) {
      const A = gmPick(sets, rnd); const target = gmPick(A.words, rnd);
      const right = gmPick(A.words.filter(x => gmNorm(x) !== gmNorm(target)), rnd);
      const tIds = GMD.sinIdx.get(gmNorm(target)) || new Set(); const rIds = GMD.sinIdx.get(gmNorm(right)) || new Set();
      const cands = [];
      for (let k = 0; k < 40; k++) {
        const B = gmPick(sets, rnd); if (B.id === A.id) continue; const w2 = gmPick(B.words, rnd); const n2 = gmNorm(w2);
        if (n2 === gmNorm(target) || n2 === gmNorm(right) || cands.includes(w2)) continue;
        const i2 = GMD.sinIdx.get(n2) || new Set();
        if ([...i2].some(i => tIds.has(i) || rIds.has(i))) continue;
        cands.push(w2);
      }
      if (cands.length < 3) continue;
      cands.sort((x, y) => Math.abs(x.length - right.length) - Math.abs(y.length - right.length));
      const opts = gmShuffle([right].concat(cands.slice(0, 3)), rnd);
      return { t: 'sinonim', q: '«' + gmPretty(target) + '» so‘ziga ma’nodosh so‘zni toping.', opts: opts.map(gmPretty), ans: opts.indexOf(right), exp: 'Ma’nodosh so‘zlar: ' + A.words.map(gmPretty).join(', ') + '.' };
    }
  }
  for (let tr = 0; tr < 60; tr++) {
    const A = gmPick(sets, rnd);
    const three = gmShuffle(A.words, rnd).slice(0, 3);
    const ids = new Set(); three.forEach(x => (GMD.sinIdx.get(gmNorm(x)) || []).forEach(i => ids.add(i)));
    const B = gmPick(sets, rnd); if (B.id === A.id) continue;
    const odd = gmPick(B.words, rnd); const on = gmNorm(odd);
    if (three.some(x => gmNorm(x) === on)) continue;
    const oi = GMD.sinIdx.get(on); if (oi && [...oi].some(i => ids.has(i))) continue;
    const opts = gmShuffle(three.concat([odd]), rnd);
    return { t: 'sinonim', q: 'Qaysi so‘z qolganlariga ma’nodosh emas?', opts: opts.map(gmPretty), ans: opts.indexOf(odd), exp: 'Ma’nodosh so‘zlar: ' + three.map(gmPretty).join(', ') + '. «' + gmPretty(odd) + '» ularga ma’nodosh emas.' };
  }
  return null;
}

function gmQPar(rnd, hard) {
  const ex = GMD.parEx; if (!ex.length) return null;
  for (let tr = 0; tr < 40; tr++) {
    const it = gmPick(ex, rnd); const ws = it.e.w;
    const right = ws[it.wi]; const a = right.w.toLowerCase();
    const cut = s => String(s || '').replace(/\s+/g, ' ').slice(0, 130);
    const others = ws.filter((_, i) => i !== it.wi).filter(o => gmNorm(o.w) !== gmNorm(right.w));
    if (!others.length) continue;
    let cands = [gmPick(others, rnd).w.toLowerCase()];
    if (hard) {
      cands = others.map(o => o.w.toLowerCase()).slice(0, 2);
      for (const dlt of [1, -1, 2, -2, 3, -3]) {
        if (cands.length >= 3) break;
        const ne = GMD.parList[it.ei + dlt]; if (!ne || !ne.w || !ne.w.length) continue;
        const nw = gmPick(ne.w, rnd).w.toLowerCase();
        if (!/\s/.test(nw) && nw !== a && !cands.includes(nw)) cands.push(nw);
      }
    }
    cands = [...new Set(cands)].filter(x => x !== a);
    if (!cands.length) continue;
    const opts = gmShuffle([a].concat(cands.slice(0, 3)), rnd);
    const exp = ws.slice(0, 3).map(o => '«' + o.w.toLowerCase() + '» — ' + cut(o.m)).join('\n');
    return { t: 'paronim', q: 'Bo‘sh joyga mos so‘zni tanlang:', sentPlain: it.r.pre + '_____' + it.r.suf + it.r.post, sentParts: [it.r.pre, it.r.suf + it.r.post],
             opts, ans: opts.indexOf(a), exp };
  }
  return null;
}

function gmQOmo(rnd, hard) {
  const list = GMD.omo; if (!list.length) return null;
  for (let tr = 0; tr < 20; tr++) {
    const it = gmPick(list, rnd); const k = Math.floor(rnd() * it.s.length); const meaning = it.s[k];
    const sentence = gmPick(meaning.ex, rnd); const mm = sentence.match(/\[([^\]]+)\]/); if (!mm) continue;
    let labels = it.s.map(x => x.m);
    const want = hard ? 4 : 3;
    for (let z = 0; z < 8 && labels.length < want; z++) {
      const o = gmPick(list, rnd); if (o.w === it.w) continue; const extra = gmPick(o.s, rnd).m; if (!labels.includes(extra)) labels = labels.concat([extra]);
    }
    const opts = gmShuffle(labels, rnd);
    return { t: 'omonim', q: '«' + it.w + '» so‘zi bu gapda qaysi ma’noda?', sentHtml: gmEsc(sentence).replace(/\[([^\]]+)\]/, '<b>$1</b>'),
             opts, ans: opts.indexOf(meaning.m), exp: '«' + it.w + '» omonimi: ' + it.s.map((x, i) => (i + 1) + ') ' + x.m).join('; ') + '.' };
  }
  return null;
}

const GM_MAKERS = { imlo: gmQImlo, sinonim: gmQSin, paronim: gmQPar, omonim: gmQOmo };
function gmQKey(q) { return q.src === 'bank' ? 'b' + q.id : q.t + '|' + q.q + '|' + (q.sentPlain || q.sentHtml || '') + '|' + (q.opts || []).join('/'); }
function gmMake(type, rnd, used, hard) {
  for (let i = 0; i < 40; i++) { const q = GM_MAKERS[type](rnd, hard); if (!q) continue; const k = gmQKey(q); if (used.has(k)) continue; used.add(k); q.kind = 'mc'; q.max = 1; return q; }
  return null;
}

// ---------- DTM / Milliy sertifikat banki ----------
function gmFromBank(it, rnd) {
  const base = { src: 'bank', id: it.id, t: 'bank', c: it.c, d: it.d, q: it.q, pass: it.p || null, exp: it.e, max: 1 };
  if (it.t === 'mc') {
    let opts = it.o.slice(), ans = it.a;
    if (!it.fix) { const ix = gmShuffle(it.o.map((_, i) => i), rnd); opts = ix.map(i => it.o[i]); ans = ix.indexOf(it.a); }
    return Object.assign(base, { kind: 'mc', opts, ans, sec: it.p ? 50 : 35, sect: 'Y-1 • Yopiq savol' });
  }
  if (it.t === 'open') return Object.assign(base, { kind: 'open', opts: [], ans: -1, accept: it.ans, sec: 50, sect: 'O-1 • Ochiq javob' });
  return Object.assign(base, { kind: 'match', opts: it.o, rows: it.r, ansArr: it.a, max: 3, sec: 90, sect: 'Y-2 • Moslashtirish' });
}
function gmBankPick(arr, n, cap, rnd) {
  const cnt = {}, out = [];
  for (const x of gmShuffle(arr, rnd)) { if (out.length >= n) break; if ((cnt[x.c] || 0) >= cap) continue; cnt[x.c] = (cnt[x.c] || 0) + 1; out.push(x); }
  if (out.length < n) for (const x of gmShuffle(arr, rnd)) { if (out.length >= n) break; if (!out.includes(x)) out.push(x); }
  return out;
}
// Milliy sertifikat tuzilmasiga o‘xshash: 12 yopiq + 1 moslashtirish (3 ball) + 5 ochiq = 20 ball
function gmBuildMock(rnd) {
  const B = GMD.bank, f = t => B.filter(x => x.t === t);
  return [].concat(gmBankPick(f('mc'), 12, 3, rnd), gmBankPick(f('match'), 1, 1, rnd), gmBankPick(f('open'), 5, 2, rnd)).map(it => gmFromBank(it, rnd));
}
function gmBuildTopic(cat, rnd) {
  const pool = gmShuffle(GMD.bank.filter(x => x.c === cat), rnd); const out = []; let m = 0;
  for (const x of pool) { if (out.length >= 10) break; if (x.t === 'match') { if (m >= 1) continue; m++; } out.push(x); }
  return out.map(it => gmFromBank(it, rnd));
}
function gmBuildDuel(seed) {
  const rnd = gmRng((seed >>> 0) || 1); const B = GMD.bank;
  const items = [].concat(gmBankPick(B.filter(x => x.t === 'mc'), 4, 1, rnd), gmBankPick(B.filter(x => x.t === 'open'), 1, 1, rnd));
  return items.map(it => gmFromBank(it, rnd));
}

// ---------- o‘yinni boshlash ----------
async function gmStart(type, arg) {
  const box = $('gpBody'); gmShowPlay(); box.innerHTML = '<div class="word">⏳ Savollar tayyorlanmoqda...</div>';
  if (GM && GM.timer) clearInterval(GM.timer);
  const bankOnly = (type === 'dtm' || type === 'topic' || type === 'duel');
  const ok = bankOnly ? await gmLoadBank() : await gmLoad();
  if (!ok) { notify('Ma’lumotlar yuklanmadi. Internetni tekshirib, qayta urinib ko‘ring.'); gmQuit(); return; }
  const hard = gmLevel() === 'dtm';
  const used = new Set(); let qs = [], rnd = Math.random, tsec = hard ? 20 : 15, meta = {};
  if (type === 'daily') {
    rnd = gmRng(gmHash('daily' + gmDayKey())); tsec = 22;
    const mcs = GMD.bank.filter(x => x.t === 'mc'), ops = GMD.bank.filter(x => x.t === 'open');
    const seq = gmShuffle(['imlo', gmPick(['sinonim', 'paronim'], rnd), 'omonim'], rnd);
    qs.push(gmFromBank(gmPick(mcs, rnd), rnd));
    for (const t of seq) { const q = gmMake(t, rnd, used, true); if (q) qs.push(q); }
    qs.push(gmFromBank(gmPick(ops, rnd), rnd));
  } else if (type === 'mistakes') {
    let list = gmShuffle(gmLS('gm_wrong', []), Math.random), pts = 0;
    for (const x of list) {
      const q = x.src === 'bank' ? (GMD.bankById && GMD.bankById[x.id] ? gmFromBank(GMD.bankById[x.id], Math.random) : null) : Object.assign({ kind: 'mc', max: 1 }, x);
      if (!q) continue; if (pts + (q.max || 1) > 10) continue; qs.push(q); pts += q.max || 1; if (qs.length >= 10) break;
    }
    if (!qs.length) { notify('Xatolar daftari hozircha bo‘sh. Avval o‘yin o‘ynab ko‘ring.'); gmQuit(); return; }
  } else if (type === 'dtm') {
    qs = gmBuildMock(Math.random);
  } else if (type === 'topic') {
    qs = gmBuildTopic(arg, Math.random); meta.cat = arg;
  } else if (type === 'duel') {
    const seed = (arg && arg.seed) ? (arg.seed >>> 0) : (1 + Math.floor(Math.random() * 899999));
    qs = gmBuildDuel(seed); meta = { seed, vs: (arg && arg.vs !== undefined) ? arg.vs : null, from: (arg && arg.from) || 0 };
  } else {
    for (let i = 0; i < 10; i++) { const q = gmMake(type, rnd, used, hard); if (q) qs.push(q); }
  }
  if (!qs.length) { notify('Savol yasab bo‘lmadi. Keyinroq urinib ko‘ring.'); gmQuit(); return; }
  GM = Object.assign({ type, qs, i: 0, hasLives: !!GM_LIVE_TYPES[type], lives: GM_LIVES, correct: 0, answered: 0, total: 0, combo: 0, best: 0, locked: false, tsec, tleft: tsec, timer: null, log: [] }, meta);
  try { trackView('game:' + type); } catch (e) {}
  gmRenderQ();
}

function gmShowPlay() { document.querySelectorAll('main').forEach(x => x.classList.add('hidden')); $('gamePlay').classList.remove('hidden'); window.scrollTo(0, 0); }
function gmQuit() { if (GM && GM.timer) clearInterval(GM.timer); GM = null; openSection('games'); }

function gmRenderQ() {
  const g = GM; if (!g) return; const q = g.qs[g.i]; const box = $('gpBody');
  const hearts = g.hasLives ? '❤️'.repeat(g.lives) + '🖤'.repeat(GM_LIVES - g.lives) : '';
  const info = q.t === 'bank' ? (GM_CATS[q.c] || {}) : (GM_TYPES[q.t] || {});
  const sect = (g.type === 'dtm' && q.sect) ? '<div class="gmSect">' + gmEsc(q.sect) + '</div>' : '';
  let body = '<div class="gmQ">' + (q.pass ? '<div class="gmPass">' + gmEscBr(q.pass) + '</div>' : '') + '<div class="gmQt">' + gmEscBr(q.q) + '</div>'
    + (q.sentParts ? '<div class="gmSent">' + gmEsc(q.sentParts[0]) + '<u class="gmBlank">&nbsp;&nbsp;?&nbsp;&nbsp;</u>' + gmEsc(q.sentParts[1]) + '</div>' : '')
    + (q.sentHtml ? '<div class="gmSent">' + q.sentHtml + '</div>' : '') + '</div>';
  if (q.kind === 'open') {
    body += '<div class="gmOpen"><input id="gmInp" class="gmInp" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Javobingizni yozing" onkeydown="if(event.key===\'Enter\')gmSubmitOpen()">'
      + '<button type="button" class="primaryAction" id="gmOk" onclick="gmSubmitOpen()">Tekshirish</button><p class="muted gmHintTxt">Katta-kichik harf va apostrof turi farq qilmaydi.</p></div>';
  } else if (q.kind === 'match') {
    body += '<div class="gmMopts">' + q.opts.map((o, i) => '<div><b>' + 'ABCDEF'[i] + ')</b> ' + gmEsc(o) + '</div>').join('') + '</div><div class="gmMrows">'
      + q.rows.map((r, i) => '<div class="gmMrow"><span>' + gmEsc(r) + '</span><select id="gms' + i + '" class="gmSel"><option value="">—</option>' + q.opts.map((_, k) => '<option value="' + k + '">' + 'ABCDEF'[k] + '</option>').join('') + '</select></div>').join('')
      + '</div><button type="button" class="primaryAction" id="gmOk" onclick="gmSubmitMatch()">Tekshirish</button>';
  } else {
    const pkj = GM_STATE && GM_STATE.perks; const jk = (g.type === 'dtm' && pkj && pkj.jokers_left > 0 && q.opts.length > 2) ? '<button type="button" class="gmJoker" id="gmJk" onclick="gmJoker()">🃏 50/50 <b>' + pkj.jokers_left + '</b></button>' : '';
    body += jk + '<div class="gmOpts">' + q.opts.map((o, i) => '<button type="button" class="gmOpt" id="gmo' + i + '" onclick="gmAnswer(' + i + ')">' + (q.opts.length > 2 ? '<b class="gmLt">' + 'ABCDEF'[i] + '</b>' : '') + gmEsc(o) + '</button>').join('') + '</div>';
  }
  box.innerHTML =
    '<div class="gmTop"><span>' + (hearts || (g.type === 'duel' ? '⚔️' : g.type === 'daily' ? '📅' : '🎯')) + '</span><span class="gmTag">' + (info.ico || '') + ' ' + (info.name || '') + '</span><span>' + (g.i + 1) + '/' + g.qs.length + '</span></div>'
    + '<div class="gmBar"><i id="gmBarI"></i></div>' + sect + body + '<div id="gmFb"></div>'
    + '<div class="gmFoot">⭐ ' + g.correct + (g.combo >= 3 ? ' • 🔥 ' + g.combo + ' ketma-ket' : '') + '</div>';
  g.locked = false; g.cur = q.sec || g.tsec; g.tleft = g.cur; if (g.timer) clearInterval(g.timer);
  g.timer = setInterval(() => {
    if (!GM || GM.locked) return; GM.tleft -= 0.1;
    const el = $('gmBarI'); if (el) { el.style.width = Math.max(0, GM.tleft / GM.cur * 100) + '%'; if (GM.tleft < 5) el.classList.add('low'); }
    if (GM.tleft <= 0) gmTimeout();
  }, 100);
  window.scrollTo(0, 0);
}

function gmHaptic(ok) { try { tg?.HapticFeedback?.notificationOccurred(ok ? 'success' : 'error'); } catch (e) {} }
function gmTimeout() { const g = GM; if (!g || g.locked) return; const q = g.qs[g.i]; if (q.kind === 'open') gmSubmitOpen(true); else if (q.kind === 'match') gmSubmitMatch(true); else gmAnswer(-1); }

// ---------- javob berish ----------
function gmAnswer(i) {
  const g = GM; if (!g || g.locked) return; const q = g.qs[g.i]; const ok = (i === q.ans);
  document.querySelectorAll('.gmOpt').forEach(b => b.disabled = true);
  const right = $('gmo' + q.ans); if (right) right.classList.add('right');
  if (!ok) { const w = $('gmo' + i); if (w) w.classList.add('wrong'); }
  gmResolve(ok ? 1 : 0, { timeout: i < 0 });
}
function gmSubmitOpen(timeout) {
  const g = GM; if (!g || g.locked) return; const q = g.qs[g.i]; const inp = $('gmInp'); const val = inp ? inp.value : '';
  if (!timeout && !gmNormAns(val)) { if (inp) inp.focus(); return; }
  const ok = q.accept.some(a => gmNormAns(a) === gmNormAns(val));
  if (inp) { inp.disabled = true; inp.classList.add(ok ? 'right' : 'wrong'); } const b = $('gmOk'); if (b) b.disabled = true;
  gmResolve(ok ? 1 : 0, { timeout: !!timeout && !gmNormAns(val), correctText: ok ? '' : q.accept[0] });
}
function gmSubmitMatch(timeout) {
  const g = GM; if (!g || g.locked) return; const q = g.qs[g.i]; let got = 0, empty = 0;
  q.rows.forEach((_, i) => {
    const s = $('gms' + i); if (!s) return; const v = s.value; if (v === '') empty++;
    const ok = (v !== '' && +v === q.ansArr[i]); if (ok) got++; s.disabled = true; s.classList.add(ok ? 'right' : 'wrong');
  });
  if (!timeout && empty === q.rows.length) { q.rows.forEach((_, i) => { const s = $('gms' + i); if (s) { s.disabled = false; s.classList.remove('right', 'wrong'); } }); notify('Kamida bitta moslikni tanlang.'); return; }
  const b = $('gmOk'); if (b) b.disabled = true;
  gmResolve(got, { timeout: !!timeout && got === 0, correctRows: q.rows.map((r, i) => r + ' → ' + 'ABCDEF'[q.ansArr[i]] + ') ' + q.opts[q.ansArr[i]]) });
}

function gmResolve(got, x) {
  const g = GM; if (!g || g.locked) return; g.locked = true; clearInterval(g.timer);
  const q = g.qs[g.i]; const max = q.max || 1; const full = got === max;
  g.answered++; g.total += max; g.correct += got; g.log.push({ c: q.c || q.t, got, max });
  if (full) { g.combo++; g.best = Math.max(g.best, g.combo); } else { g.combo = 0; if (g.hasLives) g.lives--; }
  gmHaptic(full); gmMistake(q, full, g.type); gmStats(q, got, max);
  const last = (g.i + 1 >= g.qs.length) || (g.hasLives && g.lives <= 0);
  const head = full ? '✅ To‘g‘ri!' : got > 0 ? '🟡 Qisman to‘g‘ri: ' + got + '/' + max : (x && x.timeout ? '⏰ Vaqt tugadi' : '❌ Noto‘g‘ri');
  let extra = '';
  if (x && x.correctText) extra += '<p><b>To‘g‘ri javob:</b> ' + gmEsc(x.correctText) + '</p>';
  if (x && x.correctRows && !full) extra += '<p><b>To‘g‘ri moslik:</b><br>' + x.correctRows.map(gmEsc).join('<br>') + '</p>';
  $('gmFb').innerHTML = '<div class="gmFb ' + (full ? 'ok' : got > 0 ? 'mid' : 'bad') + '"><b>' + head + '</b>' + extra + '<p>' + gmEscBr(q.exp) + '</p>'
    + '<button type="button" class="primaryAction" onclick="' + (last ? 'gmFinish()' : 'gmNext()') + '">' + (last ? 'Natijani ko‘rish' : 'Keyingisi →') + '</button></div>';
  const fb = $('gmFb'); if (fb) fb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
async function gmJoker() {
  const g = GM; if (!g || g.locked) return; const q = g.qs[g.i]; const b = $('gmJk'); if (!b || q.jokerUsed) return; b.disabled = true;
  try {
    const r = await apiFetch(apiUrl('/api/game/joker'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); const d = await r.json();
    if (!d || !d.ok) { notify((d && d.error) || 'Joker ishlamadi.'); return; }
    q.jokerUsed = true; if (GM_STATE && GM_STATE.perks) GM_STATE.perks.jokers_left = d.left;
    const wrong = q.opts.map((_, i) => i).filter(i => i !== q.ans); gmShuffle(wrong, Math.random).slice(0, Math.max(1, q.opts.length - 2)).forEach(i => { const o = $('gmo' + i); if (o) { o.disabled = true; o.classList.add('gone'); } });
    b.remove();
  } catch (e) { notify('Internetni tekshiring.'); b.disabled = false; }
}
function gmNext() { if (!GM) return; GM.i++; gmRenderQ(); }

// ---------- xatolar daftari va statistika ----------
function gmMistake(q, ok, type) {
  let list = gmLS('gm_wrong', []); const k = gmQKey(q);
  if (ok) { if (type === 'mistakes') { list = list.filter(x => gmQKey(x) !== k); gmLSset('gm_wrong', list); } return; }
  if (list.some(x => gmQKey(x) === k)) return;
  list.unshift(q.src === 'bank' ? { src: 'bank', id: q.id, c: q.c }
    : { t: q.t, q: q.q, sentParts: q.sentParts, sentHtml: q.sentHtml, sentPlain: q.sentPlain, opts: q.opts, ans: q.ans, exp: q.exp });
  gmLSset('gm_wrong', list.slice(0, 40));
}
function gmStats(q, got, max) {
  const s = gmLS('gm_stats', { xp: 0, answered: 0, dtmBest: 0, duelWins: 0 });
  s.xp = (s.xp || 0) + got; s.answered = (s.answered || 0) + 1; gmLSset('gm_stats', s);
  if (q.src === 'bank' && q.c) { const t = gmLS('gm_topic', {}); const e = t[q.c] || { c: 0, t: 0 }; e.c += got; e.t += max; t[q.c] = e; gmLSset('gm_topic', t); }
}
function gmRank(xp) { let r = 0; for (let i = 0; i < GM_RANKS.length; i++) if (xp >= GM_RANKS[i][0]) r = i; const cur = GM_RANKS[r], nxt = GM_RANKS[r + 1]; return { cur, nxt, pct: nxt ? Math.round((xp - cur[0]) / (nxt[0] - cur[0]) * 100) : 100 }; }
function gmWeak() {
  const t = gmLS('gm_topic', {}); let w = null;
  for (const k of Object.keys(GM_CATS)) { const e = t[k]; if (!e || e.t < 5) continue; const p = e.c / e.t; if (p < .75 && (!w || p < w.p)) w = { c: k, p: p }; }
  return w;
}

// ---------- natija ----------
async function gmSubmit(type, correct, total, meta) {
  if (!tg?.initData) return null;
  try {
    const r = await apiFetch(apiUrl('/api/game/submit'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ game: type, correct, total, meta: meta || {} }) });
    const d = await r.json(); return d && d.ok ? d : null;
  } catch (e) { return null; }
}

function gmTitle(g) { return ({ daily: 'Kunlik 5 savol', mistakes: 'Xatolar ustida ishlash', dtm: 'DTM sinov (20 ball)', duel: 'Bellashuv', topic: 'Mavzu: ' + ((GM_CATS[g.cat] || {}).name || '') }[g.type]) || (GM_TYPES[g.type] || {}).name; }

async function gmFinish() {
  const g = GM; if (!g) return; clearInterval(g.timer);
  const { type, correct } = g; const total = Math.max(1, g.total);
  const bests = gmLS('gm_best', {}); if (!bests[type] || correct > bests[type]) { bests[type] = correct; gmLSset('gm_best', bests); }
  const st = gmLS('gm_stats', { xp: 0, answered: 0, dtmBest: 0, duelWins: 0 });
  if (type === 'dtm' && correct > (st.dtmBest || 0)) st.dtmBest = correct;
  let vsHtml = '';
  if (type === 'duel' && g.vs !== null && g.vs !== undefined) {
    const res = correct > g.vs ? ['🏆', 'Siz g‘olib bo‘ldingiz!'] : correct === g.vs ? ['🤝', 'Durang!'] : ['💪', 'Bu safar do‘stingiz oldinda.'];
    if (correct > g.vs) st.duelWins = (st.duelWins || 0) + 1;
    vsHtml = '<div class="gmVs"><b>' + res[0] + ' ' + res[1] + '</b><div class="gmVsRow"><span>Siz<br><strong>' + correct + '/' + total + '</strong></span><span>⚔️</span><span>Do‘stingiz<br><strong>' + g.vs + '/' + total + '</strong></span></div></div>';
  }
  gmLSset('gm_stats', st);
  const pct = correct / total; const medal = pct >= .9 ? '🏆' : pct >= .7 ? '🥇' : pct >= .5 ? '👍' : '💪';
  // mavzular kesimi
  let breakdown = '';
  if (type === 'dtm' || type === 'mistakes' || type === 'daily') {
    const by = {}; g.log.forEach(l => { if (!GM_CATS[l.c]) return; const e = by[l.c] || (by[l.c] = { c: 0, t: 0 }); e.c += l.got; e.t += l.max; });
    const rows = Object.keys(by).map(k => { const p = by[k].c / by[k].t; return '<div class="gmBrk"><span>' + GM_CATS[k].ico + ' ' + GM_CATS[k].name + '</span><i><u style="width:' + Math.round(p * 100) + '%" class="' + (p < .5 ? 'lo' : p < .8 ? 'mid' : 'hi') + '"></u></i><b>' + by[k].c + '/' + by[k].t + '</b></div>'; });
    if (rows.length) breakdown = '<h3 class="gmH">Mavzular bo‘yicha</h3><div class="gmBrkBox">' + rows.join('') + '</div>';
  }
  const note = type === 'dtm' ? (pct >= .85 ? 'A’lo tayyorgarlik! Shu tezlikda davom eting.' : pct >= .65 ? 'Yaxshi natija. Zaif mavzularni takrorlang.' : pct >= .45 ? 'O‘rtacha. Mavzu bo‘yicha mashqlar yordam beradi.' : 'Hali ko‘p ishlash kerak — mavzu bo‘yicha mashqdan boshlang.')
    : (pct >= .7 ? 'Zo‘r natija!' : pct >= .5 ? 'Yomon emas, davom eting!' : 'Mashq qilsangiz, albatta oshadi!');
  const again = (type === 'daily' || type === 'mistakes') ? '' : '<button type="button" class="bpGhost" onclick="' + (type === 'topic' ? 'gmStart(\'topic\',\'' + g.cat + '\')' : type === 'duel' ? 'gmStart(\'duel\')' : 'gmStart(\'' + type + '\')') + '">🔁 Yana o‘ynash</button>';
  const wk = (type === 'dtm' || type === 'mistakes') ? gmWeak() : null;
  const weakBtn = wk ? '<button type="button" class="bpGhost" onclick="gmStart(\'topic\',\'' + wk.c + '\')">🎯 Zaif mavzu: ' + GM_CATS[wk.c].name + '</button>' : '';
  const shareBtn = type === 'duel'
    ? '<button type="button" class="primaryAction gmInvPrim" onclick="gmShareDuel(' + g.seed + ',' + correct + ',' + total + ')">⚔️ Do‘stni chaqirish</button>'
    : '<button type="button" class="primaryAction" id="gmShareBtn" onclick="gmShare(' + correct + ',' + total + ',\'' + type + '\')">📤 Do‘stlarga ulashish</button>';
  const invHint = '<p class="gmInvHint">' + (type === 'duel' ? '⚔️ Do‘stingiz o‘zib keta oladimi? Chaqiring — u o‘ynasa, sizga ❄️ seriya himoyasi tegadi.' : type === 'daily' ? '🔥 Ertaga seriyani do‘st bilan davom ettiring — u o‘ynasa, sizga ❄️ himoya tegadi.' : pct >= .5 ? '🎁 Natijangizni ko‘rsating: do‘stingiz o‘ynasa, sizga ❄️ seriya himoyasi tegadi.' : '') + '</p>';
  const duelBtn = type === 'duel' ? '' : '<button type="button" class="bpGhost" onclick="gmStart(\'duel\')">⚔️ Do‘st bilan bellashish</button>';
  $('gpBody').innerHTML = '<div class="gmRes"><div class="gmMedal">' + medal + '</div><h2>' + gmEsc(gmTitle(g)) + '</h2><div class="gmBig">' + correct + ' / ' + total + '</div>'
    + '<p class="muted">' + note + '</p>' + vsHtml
    + '<div id="gmSrv" class="gmSrv">⏳ Natija saqlanmoqda...</div>' + breakdown
    + invHint + '<div class="gmBtns">' + shareBtn + again + weakBtn + duelBtn + '<button type="button" class="bpGhost" onclick="gmQuit()">‹ O‘yinlar</button></div></div>';
  GM = null;
  const res = await gmSubmit(type, correct, total, type === 'duel' ? { from: g.from || 0, seed: g.seed, vs: g.vs } : null);
  const el = $('gmSrv'); if (!el) return;
  if (res) {
    GM_STATE = res;
    el.innerHTML = (res.already ? 'ℹ️ Bugungi kunlik savollar allaqachon hisoblangan.' : '⭐ +' + (res.gained || 0) + ' ball (haftalik o‘yin reytingiga)')
      + (res.streak ? '<br>🔥 Seriya: <b>' + res.streak + ' kun</b>' : '');
    window.GM_LASTSTREAK = res.streak || 0;
  } else { el.textContent = tg?.initData ? 'Natija serverga yuborilmadi (internet?).' : 'Natija faqat Telegram ichida saqlanadi.'; }
}

function gmLinkBase() { return (typeof ME !== 'undefined' && ME.ref_link) || ((typeof ME !== 'undefined' && ME.bot_username) ? 'https://t.me/' + ME.bot_username : ''); }
// v44: chiroyli taklif — Telegram'da rasmli karta + «Qabul qilaman» tugmasi bilan ketadi (eski Telegram'da oddiy havola)
async function gmInvite(kind, correct, total, seed) {
  const me = (typeof ME !== 'undefined') ? ME : {}; const bot = me.bot_username || ''; const uid = me.uid || 0;
  if (!bot) { notify('Havola hozircha tayyor emas. Birozdan so‘ng urinib ko‘ring.'); return; }
  const isDuel = kind === 'duel';
  let link = isDuel ? 'https://t.me/' + bot + '?start=duel_' + seed + '_' + correct + (uid ? '_' + uid : '') : 'https://t.me/' + bot + '?start=play_' + (uid || '');
  const st = window.GM_LASTSTREAK ? '\n🔥 ' + window.GM_LASTSTREAK + ' kunlik seriya' : '';
  const text = isDuel ? '⚔️ Ona tili bellashuvi!\n🎯 Men ' + correct + '/' + total + ' oldim. O‘zib keta olasanmi?\n⏱ 5 savol, 2 daqiqa 👇'
    : '🎮 Ona tilini o‘ynab o‘rganyapman!' + st + '\n📅 Kunlik 5 savol • 📝 DTM sinov • ⚔️ bellashuv\nSen ham sinab ko‘r 👇';
  try {
    if (tg && tg.shareMessage && tg.isVersionAtLeast && tg.isVersionAtLeast('8.0') && tg.initData) {
      const r = await apiFetch(apiUrl('/api/game/share'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind, correct, total, seed: seed || 1 }) });
      const d = await r.json();
      if (d && d.link) link = d.link;
      if (d && d.ok && d.msg_id) { tg.shareMessage(d.msg_id); return; }
    }
  } catch (e) {}
  openShare(link, text);
}
function gmShare(correct, total, type) { gmInvite('play', correct, total, 0); }
function gmShareDuel(seed, correct, total) { gmInvite('duel', correct, total, seed); }
function gmInvHide() { gmLSset('gm_inv_hide', Date.now() + 3 * 86400000); gmRenderHub(GM_STATE); }

// do‘st taklifi: bosh sahifadagi ingichka qator + yutuqlar
function gmInviteBand(pk) {
  pk = pk || { friends: 0, pending: 0, freeze_left: 0, jokers_left: 0, next: { need: 1, left: 1, reward: '❄️ Seriya himoyasi' }, steps: [] };
  const hidden = gmLS('gm_inv_hide', 0) > Date.now() && !pk.friends;
  const chips = [];
  if (pk.freeze_left > 0) chips.push('<span class="gmChip">❄️ ' + pk.freeze_left + ' himoya</span>');
  if (pk.jokers_left > 0) chips.push('<span class="gmChip">🃏 ' + pk.jokers_left + ' joker</span>');
  if (pk.elchi) chips.push('<span class="gmChip gold">🏅 Elchi</span>');
  let h = '';
  if (!hidden) {
    const nx = pk.next; const stepsHtml = (pk.steps || []).map(x => '<i class="' + (x.done ? 'on' : '') + '" title="' + gmEsc(x.title) + '">' + x.need + '</i>').join('<u></u>');
    h += '<div class="gmInv"><div class="gmInvTop"><b class="gmInvIco">🤝</b><div class="gmInvTx"><strong>' + (pk.friends ? 'Do‘stlaringiz: ' + pk.friends + ' ta' : 'Do‘st chaqiring — birga o‘ynang') + '</strong>'
      + '<small>' + (nx ? 'Yana <b>' + nx.left + '</b> ta do‘st → ' + gmEsc(nx.reward) : 'Barcha mukofotlar ochildi!') + '</small></div>'
      + (pk.friends ? '' : '<button type="button" class="gmInvX" aria-label="Yopish" onclick="gmInvHide()">×</button>') + '</div>'
      + (stepsHtml ? '<div class="gmInvSteps">' + stepsHtml + '</div>' : '')
      + '<div class="gmInvBtm"><div class="gmChips">' + (chips.join('') || '<span class="gmHint">Do‘st o‘yinni boshlasa — ❄️ seriya himoyasi sizga 🎁</span>') + '</div>'
      + '<button type="button" class="gmInvBtn" onclick="gmInvite(\'play\',0,5,0)">📤 Chaqirish</button></div>'
      + (pk.pending ? '<small class="gmInvPend">⏳ ' + pk.pending + ' ta do‘st hali o‘ynamagan</small>' : '') + '</div>';
  } else if (chips.length) { h += '<div class="gmChips gmChipsRow">' + chips.join('') + '</div>'; }
  return h;
}

// ---------- bosh sahifa (o‘yinlar bo‘limi) ----------
async function gmOpenHub() {
  gmRenderHub(GM_STATE);
  try { const r = await apiFetch(apiUrl('/api/game/state')); const d = await r.json(); if (d && d.ok) { GM_STATE = d; gmRenderHub(d); } } catch (e) {}
  gmLoadBank();   // fon rejimida oldindan yuklab qo‘yamiz (kichik fayl)
}
function gmSetLevel(l) { gmLSset('gm_level', l === 'oson' ? 'oson' : 'dtm'); gmRenderHub(GM_STATE); }

function gmRenderHub(st) {
  const box = $('gmBody'); if (!box) return; const bests = gmLS('gm_best', {}); const wrong = gmLS('gm_wrong', []).length;
  const stats = gmLS('gm_stats', { xp: 0, answered: 0, dtmBest: 0, duelWins: 0 }); const topic = gmLS('gm_topic', {}); const lvl = gmLevel();
  const pk = (st && st.perks) || null; const xpAll = (stats.xp || 0) + (pk ? (pk.bonus_xp || 0) : 0); const rk = gmRank(xpAll);
  let h = '';
  h += '<div class="gmProf"><div class="gmPr1"><span class="gmRkIco">' + rk.cur[2] + '</span><div><b>' + rk.cur[1] + '</b><small>' + xpAll + ' XP' + (rk.nxt ? ' • keyingi daraja: ' + rk.nxt[1] + ' (' + rk.nxt[0] + ')' : ' • eng yuqori daraja') + '</small></div></div><div class="gmXp"><i style="width:' + rk.pct + '%"></i></div></div>';
  const done = st && st.today_done;
  h += '<div class="gmDaily"><div class="gmDl"><b>📅 Kunlik 5 savol</b><small>' + (done ? '✅ Bugun bajarildi' + (st.daily ? ': ' + st.daily.correct + '/' + st.daily.total : '') + ' • ertaga yangi savollar' : 'Hamma uchun bir xil • har kuni yangi • +3 bonus ball') + '</small></div>'
    + '<div class="gmStreak"><span>🔥</span><b>' + ((st && st.streak) || 0) + '</b><small>kun</small></div></div>'
    + '<button type="button" class="primaryAction gmDailyBtn" ' + (done ? 'disabled' : '') + ' onclick="gmStart(\'daily\')">' + (done ? '✅ Bugun bajarildi' : '▶️ Boshlash') + '</button>';
  h += gmInviteBand(pk);
  h += '<div class="gmBig2"><button type="button" class="gmDtm" onclick="gmStart(\'dtm\')"><b>📝</b><span><strong>DTM sinov — 20 ball</strong><small>12 yopiq + moslashtirish + 5 ochiq javob • milliy sertifikat tuzilmasiga yaqin' + (stats.dtmBest ? ' • rekord: ' + stats.dtmBest + '/20' : '') + '</small></span></button>'
    + '<button type="button" class="gmDuelB" onclick="gmStart(\'duel\')"><b>⚔️</b><span><strong>Do‘st bilan bellashuv</strong><small>5 savol • natijangizni havola qilib yuboring' + (stats.duelWins ? ' • g‘alabalar: ' + stats.duelWins : '') + '</small></span></button></div>';
  h += '<h3 class="gmH">O‘yinlar <small>qiyinlik:</small></h3><div class="gmLvl"><button type="button" class="' + (lvl === 'oson' ? 'on' : '') + '" onclick="gmSetLevel(\'oson\')">🟢 Oson</button><button type="button" class="' + (lvl === 'dtm' ? 'on' : '') + '" onclick="gmSetLevel(\'dtm\')">🔴 DTM (qiyin)</button></div>';
  h += '<div class="gmGrid">' + Object.keys(GM_TYPES).map(k => {
    const t = GM_TYPES[k]; return '<button type="button" class="gmTile" onclick="gmStart(\'' + k + '\')"><b>' + t.ico + '</b><strong>' + t.title + '</strong><small>' + t.desc + '</small>' + (bests[k] ? '<em>Rekord: ' + bests[k] + '/10</em>' : '<em>' + t.name + '</em>') + '</button>'; }).join('') + '</div>';
  const wk = gmWeak();
  h += '<h3 class="gmH">🎯 Mavzu bo‘yicha mashq</h3>';
  if (wk) h += '<button type="button" class="gmWeak" onclick="gmStart(\'topic\',\'' + wk.c + '\')">💡 Zaif mavzu: <b>' + GM_CATS[wk.c].name + '</b> (' + Math.round(wk.p * 100) + '%) <span>Mashq →</span></button>';
  h += '<div class="gmCats">' + Object.keys(GM_CATS).map(k => { const c = GM_CATS[k], e = topic[k]; const p = e && e.t ? Math.round(e.c / e.t * 100) : null;
    return '<button type="button" class="gmCat" onclick="gmStart(\'topic\',\'' + k + '\')"><span>' + c.ico + '</span><b>' + c.name + '</b><em class="' + (p === null ? '' : p < 50 ? 'lo' : p < 80 ? 'mid' : 'hi') + '">' + (p === null ? 'yangi' : p + '%') + '</em></button>'; }).join('') + '</div>';
  h += '<button type="button" class="gmWrong" onclick="gmStart(\'mistakes\')">📒 Xatolarim <span>' + wrong + ' ta</span><small>Adashgan savollaringizni qayta yeching</small></button>';
  // yutuqlar
  const bs = (st && st.best_streak) || 0; const allCats = Object.keys(GM_CATS).every(k => topic[k] && topic[k].t > 0);
  const badges = [['📚', '100 savol', (stats.answered || 0) >= 100], ['🎯', 'DTM sinov 80%+', (stats.dtmBest || 0) >= 16], ['⚔️', '3 g‘alaba', (stats.duelWins || 0) >= 3], ['🔥', '7 kun seriya', bs >= 7], ['🏅', '30 kun seriya', bs >= 30], ['🧭', 'Barcha mavzular', allCats], ['🤝', 'Elchi: 3 do‘st', !!(pk && pk.elchi)]];
  h += '<h3 class="gmH">🏅 Yutuqlar</h3><div class="gmBadges">' + badges.map(b => '<div class="gmBd' + (b[2] ? ' on' : '') + '"><span>' + b[0] + '</span><small>' + b[1] + '</small></div>').join('') + '</div>';
  const wkr = st && st.week;
  h += '<h3 class="gmH">🏆 Haftalik o‘yin reytingi' + (wkr && wkr.range ? '<small> ' + gmEsc(wkr.range) + '</small>' : '') + '</h3>';
  if (wkr && wkr.top && wkr.top.length) {
    h += '<div class="gmTop10">' + wkr.top.map(r => '<div class="gmRow' + (r.me ? ' me' : '') + '"><span class="gmRk">' + (r.rank <= 3 ? ['🥇', '🥈', '🥉'][r.rank - 1] : r.rank) + '</span><span class="gmNm">' + gmEsc(r.name) + '</span><b>' + r.pts + '</b></div>').join('') + '</div>';
    h += '<p class="muted gmMe">' + (wkr.me ? 'Sizning o‘rningiz: <b>' + wkr.me.rank + '</b> • ' + wkr.me.pts + ' ball' : 'Siz hali ball yig‘magansiz — birinchi o‘yinni boshlang!') + '</p>';
  } else { h += '<p class="muted">Bu hafta hali hech kim ball yig‘magan. Birinchi bo‘ling! 🚀</p>'; }
  h += '<p class="muted gmNote">Har to‘g‘ri javob = 1 ball. Bu reyting rasmiy «Reyting» va sovrinlardan alohida, o‘yin-kulgi uchun. Savollar rasmiy namunalar tuzilmasi (DTM / Milliy sertifikat) asosida tuzilgan mustaqil mashq savollaridir.</p>';
  box.innerHTML = h;
}

// ---------- bellashuv havolasidan kirish ----------
window.addEventListener('load', () => {
  try {
    const q = new URLSearchParams(location.search).get('duel');
    const sp = tg?.initDataUnsafe?.start_param || '';
    const raw = q || (sp.startsWith('duel_') ? sp.slice(5) : '');
    const m = /^(\d{1,9})(?:_(\d{1,2})?)?(?:_(\d{1,12}))?/.exec(raw || '');
    if (m) setTimeout(() => gmStart('duel', { seed: +m[1], vs: m[2] ? +m[2] : null, from: m[3] ? +m[3] : 0 }), 700);
    else if (new URLSearchParams(location.search).get('game') === '1' || sp.startsWith('play_')) setTimeout(() => openSection('games'), 700);
  } catch (e) {}
});
