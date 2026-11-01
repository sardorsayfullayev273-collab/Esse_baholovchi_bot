// ===== v113: IMLO va MUMTOZ lug'atlari — yangi qidiruv =====
// Oldin: faqat so'z BOSHIDAN qidirish, kamida 3 harf, natija 80 taga kesilgan, mumtoz so'z boshlari («Avli//avlo-», «Ajuba, A’juba-») topilmasdi.
// Endi: so'zning istalgan joyidan, apostrof/tire/bo'sh joyga befarq, natija cheklanmaydi («Yana ko'rsatish»), harf bo'yicha ko'rish,
// mumtoz lug'atda izohdan qidirish; imlo lug'ati dasturdagi boshqa fayllardan (dictionary_extra.json) to'ldirilgan.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const PAGE = 60;
  const LETTERS = ['A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'X', 'Y', 'Z', 'O‘', 'G‘', 'Sh', 'Ch'];
  const SRC = { 1: 'Dasturdagi lug‘atlardan', faol: 'Faol so‘zlar', sinonim: 'Sinonimlar lug‘atidan', paronim: 'Paronimlar lug‘atidan', omonim: 'Omonimlar lug‘atidan' };
  const norm = s => (typeof normalize === 'function' ? normalize(s) : String(s || '').toLowerCase().trim());
  const skel = s => norm(s).replace(/[^a-z0-9]/g, '');
  const ROMAN = /\s+(?:I{1,3}|IV|V|VI{0,3})\s*$/;
  const S = { imlo: null, mum: null, st: { imlo: { q: '', list: [], shown: 0 }, mum: { q: '', list: [], shown: 0 } } };
  let tm = {};

  // so'z boshi variantlari: «Avli//avlo-», «Ajuba, A’juba-», «Azm I –», «Azro (Uzro)-»
  function heads(raw) {
    let s = String(raw || ''); const alts = []; s = s.replace(/\(([^)]*)\)/g, (m, a) => { alts.push(a); return ' '; });
    const out = [];
    s.split(/\/\/|,|;/).concat(alts).forEach(p => { p = p.replace(/^[\s\-–—=:]+|[\s\-–—=:]+$/g, ''); p = p.replace(ROMAN, '').replace(/[\s\-–—=:]+$/g, '').trim(); if (p.length >= 2) out.push(p); });
    return out.length ? out : [String(raw || '').trim()];
  }

  // ------------------------------------------------------------ ma'lumot yuklash
  async function getJson(f) { try { const r = await fetch(f, { cache: 'default' }); if (!r.ok) return null; return await r.json(); } catch (e) { return null; } }
  async function ensureImlo() {
    if (S.imlo) return S.imlo;
    const base = (typeof dict !== 'undefined' && dict.length) ? dict : await getJson('dictionary.json');
    if (!base) return null;
    const extra = (await getJson('dictionary_extra.json?v=113')) || [];
    const items = [], seen = new Set();
    const push = (w, src) => { const n = norm(w); if (!n || seen.has(n)) return; seen.add(n); items.push({ w, n, k: skel(w), src }); };
    base.forEach(w => { w = String(w); if (w.length === 2 && w[0].toLowerCase() === w[1]) return; push(w, 0); });   // «Aa», «Bb» — harf sarlavhalari
    extra.forEach(e => push(e[0], e[1] || 1));
    S.imlo = items;
    try { if (typeof dict !== 'undefined' && dict.length) { /* app.js ro'yxati: boshqa joylar uchun to'ldiramiz */ extra.forEach(e => { if (dict.indexOf(e[0]) < 0) dict.push(e[0]); }); } } catch (e) {}
    return items;
  }
  async function ensureMum() {
    if (S.mum) return S.mum;
    const base = (typeof mumtoz !== 'undefined' && mumtoz.length) ? mumtoz : await getJson('mumtoz.json');
    if (!base) return null;
    const extra = (await getJson('mumtoz_extra.json?v=113')) || [];
    S.mum = base.concat(extra).map(x => {
      const hs = heads(x.word), v = hs.map(h => ({ n: norm(h), k: skel(h) }));
      return { word: x.word, meaning: x.meaning || '', v, mn: norm(x.meaning || ''), disp: String(x.word).replace(/[\s\-–—=:]+$/g, '').trim(), n0: v[0] ? v[0].n : norm(x.word) };
    });
    return S.mum;
  }

  // ------------------------------------------------------------ qidiruv
  function tier(v, q, qs) {
    if (v.n === q) return 0;
    if (v.n.startsWith(q)) return 1;
    if (v.n.indexOf(' ' + q) >= 0 || v.n.indexOf('-' + q) >= 0) return 2;
    if (v.n.indexOf(q) >= 0) return 3;
    if (qs.length >= 2 && v.k.startsWith(qs)) return 4;       // apostrofni unutgan: «manoviy» → «ma’naviy»
    if (qs.length >= 3 && v.k.indexOf(qs) >= 0) return 5;
    return 9;
  }
  function rank(items, getV, q, prefixOnly) {
    const qs = skel(q), res = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i], vs = getV(it); let best = 9;
      for (let j = 0; j < vs.length; j++) { const t = tier(vs[j], q, qs); if (t < best) best = t; if (best === 0) break; }
      if (best < 9 && (!prefixOnly || best <= 1)) res.push([best, it]);
    }
    res.sort((a, b) => a[0] - b[0] || (a[1].n0 || a[1].n).length - (b[1].n0 || b[1].n).length || (a[1].n0 || a[1].n).localeCompare(b[1].n0 || b[1].n, 'uz'));
    return res.map(x => x[1]);
  }
  const letterQ = ch => ({ 'O‘': 'o\'', 'G‘': 'g\'', 'Sh': 'sh', 'Ch': 'ch' }[ch] || ch.toLowerCase());

  // ------------------------------------------------------------ ko'rsatish
  function chips(kind) {
    const el = $(kind === 'imlo' ? 'dictChips' : 'mumtozChips'); if (!el || el.dataset.ready) return; el.dataset.ready = '1';
    el.innerHTML = LETTERS.map(l => '<button type="button" class="lgChip" data-l="' + esc(l) + '">' + esc(l) + '</button>').join('');
    const inp0 = $(kind === 'imlo' ? 'dictSearch' : 'mumtozSearch'), sug0 = $(kind === 'imlo' ? 'dictSuggestions' : 'mumtozSuggestions');
    if (inp0) { inp0.addEventListener('blur', () => setTimeout(() => { if (sug0) sug0.classList.add('hidden'); }, 220)); inp0.addEventListener('keydown', e => { if (e.key === 'Escape' || e.key === 'Enter') { if (sug0) sug0.classList.add('hidden'); inp0.blur(); } }); }
    el.querySelectorAll('button').forEach(b => b.onclick = () => {
      const inp = $(kind === 'imlo' ? 'dictSearch' : 'mumtozSearch'); inp.value = letterQ(b.dataset.l); if (sug0) sug0.classList.add('hidden');
      el.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); run(kind, true);
    });
  }
  function itemHtml(kind, it) {
    if (kind === 'imlo') return '<div class="word"><strong>' + esc(it.w) + '</strong><div class="muted">' + esc(it.src ? (SRC[it.src] || SRC[1]) : '2013-yilgi imlo lug‘ati') + '</div></div>';
    return '<div class="word"><strong>' + esc(it.disp) + '</strong><div class="muted">' + esc(it.meaning || 'Izoh mavjud emas.') + '</div></div>';
  }
  function paint(kind) {
    const st = S.st[kind], box = $(kind === 'imlo' ? 'dictResults' : 'mumtozResults'), info = $(kind === 'imlo' ? 'dictInfo' : 'mumtozInfo'), more = $(kind === 'imlo' ? 'dictMore' : 'mumtozMore');
    const total = st.list.length, part = st.list.slice(0, st.shown);
    let html = part.map(it => itemHtml(kind, it)).join('');
    if (kind === 'mum' && st.mnList && st.mnList.length) {
      html += '<div class="lgSep">Izohlarda topildi (' + st.mnList.length + ')</div>' + st.mnList.slice(0, st.mnShown).map(it => itemHtml(kind, it)).join('');
    }
    if (!total && !(st.mnList && st.mnList.length)) html = '<div class="word">So‘z topilmadi. Boshqacha yozib ko‘ring (apostrofsiz yoki so‘zning bir bo‘lagini).</div>';
    box.innerHTML = html;
    const left = Math.max(0, total - st.shown) + (st.mnList ? Math.max(0, st.mnList.length - st.mnShown) : 0);
    if (info) info.textContent = st.q ? ('Topilgan: ' + total + ' ta' + (st.mnList && st.mnList.length ? ' + izohlarda ' + st.mnList.length + ' ta' : '')) : ('Jami ' + (kind === 'imlo' ? S.imlo.length : S.mum.length) + ' ta so‘z. Harfni tanlang yoki so‘zni yozing.');
    if (more) { more.classList.toggle('hidden', !left); more.textContent = 'Yana ko‘rsatish (' + Math.min(PAGE, left) + ' / qoldi ' + left + ')'; more.onclick = () => { if (st.shown < total) st.shown += PAGE; else if (st.mnList) st.mnShown += PAGE; paint(kind); }; }
  }
  async function run(kind, browse) {
    const items = await (kind === 'imlo' ? ensureImlo() : ensureMum()); chips(kind);
    const box = $(kind === 'imlo' ? 'dictResults' : 'mumtozResults');
    if (!items) { if (box) box.innerHTML = '<div class="word">Lug‘atni yuklashda xatolik. Internetni tekshirib qayta oching.</div>'; return; }
    const q = norm($(kind === 'imlo' ? 'dictSearch' : 'mumtozSearch').value), st = S.st[kind];
    st.q = q; st.mnList = null;
    if (!q) { st.list = items.slice(0, PAGE); st.shown = PAGE; paint(kind); return; }
    const prefixOnly = q.replace(/'/g, '').length <= 2 || browse;        // 1-2 harf: faqat shu harfdan boshlanuvchilar (alifbo tartibida)
    const getV = kind === 'imlo' ? (it => [it]) : (it => it.v);
    let list = rank(items, getV, q, prefixOnly);
    if (prefixOnly) list.sort((a, b) => (a.n0 || a.n).localeCompare(b.n0 || b.n, 'uz'));
    st.list = list; st.shown = PAGE;
    if (kind === 'mum') {
      const ck = $('mumtozMeaning'); const want = (ck && ck.checked) || (!list.length && q.length >= 3);
      if (want && q.length >= 3) { const seen = new Set(list); st.mnList = items.filter(it => !seen.has(it) && it.mn.indexOf(q) >= 0).slice(0, 400); st.mnShown = PAGE; }
    }
    paint(kind);
  }
  const debounced = (kind) => { clearTimeout(tm[kind]); tm[kind] = setTimeout(() => run(kind, false), 90); };

  // ------------------------------------------------------------ takliflar (qidiruv yozilayotganda)
  async function suggest(kind) {
    const inputId = kind === 'imlo' ? 'dictSearch' : 'mumtozSearch', boxId = kind === 'imlo' ? 'dictSuggestions' : 'mumtozSuggestions', box = $(boxId);
    const items = await (kind === 'imlo' ? ensureImlo() : ensureMum()); const q = norm($(inputId).value);
    if (!items || q.length < 2) { box.innerHTML = ''; box.classList.add('hidden'); return; }
    const m = rank(items, kind === 'imlo' ? (it => [it]) : (it => it.v), q, true).slice(0, 8);
    box.innerHTML = m.length ? m.map((it, i) => '<button class="suggestion" type="button" data-i="' + i + '"><b>' + esc(kind === 'imlo' ? it.w : it.disp) + '</b>' + (kind === 'mum' && it.meaning ? '<small>' + esc(it.meaning.slice(0, 90)) + '</small>' : '') + '</button>').join('') : '<div class="suggestion muted">Mos so‘z topilmadi.</div>';
    box.classList.remove('hidden');
    box.querySelectorAll('button[data-i]').forEach(b => b.onclick = () => { const it = m[+b.dataset.i]; $(inputId).value = kind === 'imlo' ? it.w : it.disp; box.classList.add('hidden'); run(kind, false); });
  }

  // ------------------------------------------------------------ app.js funksiyalarini almashtirish
  window.loadData = async function () { await run('imlo', false); };
  window.loadMumtoz = async function () { await run('mum', false); };
  window.searchDict = function () { suggest('imlo'); debounced('imlo'); };
  window.searchMumtoz = function () { suggest('mum'); debounced('mum'); };
  window.showSuggestions = function (inputId, boxId, kind) { suggest(kind === 'mumtoz' ? 'mum' : 'imlo'); };
  window.chooseSuggestion = function () {};
  window.lgMeaningToggle = function () { run('mum', false); };
  window.LG_TEST = { heads, rank, tier, skel };
})();
