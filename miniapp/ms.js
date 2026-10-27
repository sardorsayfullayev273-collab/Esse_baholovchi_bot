// ===== v108: Milliy sertifikat — fanlar (ona tili / matematika / tarix), taymer, esseni imtihon ichida yozish, natija xaritasi =====
// Diagnostik test va Mock bir xil oqimdan foydalanadi: test → esse → yagona natija.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const LS = { get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }, del(k) { try { localStorage.removeItem(k); } catch (e) {} } };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ---------------------------------------------------------------- fanlar (server: ms_exam.py bilan bir xil)
  const YA = [[1, 32, 'Y1'], [33, 35, 'Y2'], [36, 45, 'O1AB']];
  const SUBJ = {
    ona_tili: { name: 'Ona tili va adabiyot', short: 'Ona tili', minutes: 180, essay: true, emoji: '📖', layout: [[1, 32, 'Y1'], [33, 35, 'Y2'], [36, 39, 'O1'], [40, 44, 'O1AB'], [45, 45, 'O2']] },
    matematika: { name: 'Matematika', short: 'Matematika', minutes: 150, essay: false, emoji: '➗', layout: YA },
    tarix: { name: 'O‘zbekiston tarixi', short: 'Tarix', minutes: 90, essay: false, emoji: '🏛', layout: YA }
  };
  const keyOf = s => { s = String(s || '').toLowerCase(); return SUBJ[s] ? s : (s.indexOf('matem') >= 0 ? 'matematika' : (s.indexOf('tarix') >= 0 ? 'tarix' : 'ona_tili')); };
  window.__msSubject = window.__msSubject || 'ona_tili';
  window.msCfg = () => SUBJ[window.__msSubject] || SUBJ.ona_tili;
  window.msType = i => { for (const [a, b, t] of window.msCfg().layout) if (i >= a && i <= b) return t; return 'Y1'; };

  // ---------------------------------------------------------------- test yaratish: fan tanlash
  window.msSubject = function (v) {
    const mb = window._mockBuild; window.__msSubject = SUBJ[v] ? v : 'ona_tili';
    const box = $('builderQuestions'); if (box) box.dataset.ready = '';
    try { openNationalCreate(); } catch (e) { console.error(e); }
    window._mockBuild = mb; try { mockBuildUi(); } catch (e) {}
    msCreateUi(true);
  };
  function msCreateUi(reset) {
    const c = window.msCfg();
    const ew = $('createEssayWrap'), en = $('createEssayNote'); if (ew) ew.style.display = c.essay ? '' : 'none'; if (en) en.style.display = c.essay ? '' : 'none';
    const sel = $('createSubject'); if (sel && sel.value !== window.__msSubject) sel.value = window.__msSubject;
    const mi = $('createMinutes'); if (mi && (reset || !mi.value)) mi.value = c.minutes;
  }
  window.msMinutes = function () { const v = parseInt(($('createMinutes') || {}).value, 10); return (v >= 10 && v <= 240) ? v : window.msCfg().minutes; };

  // ---------------------------------------------------------------- testlar ro'yxati: fan bo'yicha filtr
  window.__msFilter = window.__msFilter || 'all';
  window.msFilterTests = function (arr) {
    const f = window.__msFilter; renderChips(arr);
    return f === 'all' ? arr : arr.filter(x => keyOf(x.subject) === f);
  };
  function renderChips(arr) {
    const box = $('msSubjTabs'); if (!box) return;
    const cnt = k => arr.filter(x => keyOf(x.subject) === k).length;
    const items = [['all', 'Hammasi', arr.length]].concat(Object.keys(SUBJ).map(k => [k, SUBJ[k].emoji + ' ' + SUBJ[k].short, cnt(k)]));
    box.innerHTML = items.map(([k, n, c]) => '<button type="button" class="msChip' + (window.__msFilter === k ? ' on' : '') + '" data-k="' + k + '">' + esc(n) + ' <i>' + c + '</i></button>').join('');
    box.querySelectorAll('button').forEach(b => b.onclick = () => { window.__msFilter = b.dataset.k; try { loadNationalTests(); } catch (e) {} });
  }

  // ---------------------------------------------------------------- imtihon: taymer
  let tmr = null, msBusy = false;
  const uid = () => { try { return nationalUid(); } catch (e) { return 0; } };
  const code = () => String((nationalTest && nationalTest.code) || '').toUpperCase();
  const kStart = () => 'msstart_' + uid() + '_' + code();
  const kEssay = () => 'msessay_' + uid() + '_' + code();
  const minutes = () => +(nationalTest && (nationalTest.minutes || nationalTest.duration_min)) || 180;
  const fmt = s => { s = Math.max(0, s | 0); const h = (s / 3600) | 0, m = ((s % 3600) / 60) | 0, x = s % 60; return (h ? h + ':' : '') + String(m).padStart(h ? 2 : 2, '0') + ':' + String(x).padStart(2, '0'); };
  function stopTimer() { if (tmr) { clearInterval(tmr); tmr = null; } }
  function startTimer() {
    stopTimer();
    const mins = minutes(), now = Date.now(); let st = +LS.get(kStart()) || 0;
    if (!st || now - st > mins * 60000 + 6 * 3600 * 1000) { st = now; LS.set(kStart(), String(st)); }
    window.__msStart = st; window.__msDeadline = st + mins * 60000;
    let bar = $('msBar'); const page = $('nationalExam');
    if (!bar && page) { bar = document.createElement('div'); bar.id = 'msBar'; bar.className = 'msBar'; page.insertBefore(bar, page.firstChild); }
    tick(); tmr = setInterval(tick, 1000);
  }
  function tick() {
    const page = $('nationalExam'); if (!nationalTest || !page || page.classList.contains('hidden')) { if (!msBusy) stopTimer(); return; }
    const left = Math.round((window.__msDeadline - Date.now()) / 1000), bar = $('msBar');
    if (bar) {
      const c = SUBJ[keyOf(nationalTest.subject)] || SUBJ.ona_tili;
      bar.innerHTML = '<span>' + c.emoji + ' ' + esc(nationalTest.subject || c.name) + '</span><b class="' + (left < 300 ? 'low' : '') + '">⏱ ' + fmt(left) + '</b>';
    }
    if (left <= 0) timeUp();
  }
  async function timeUp() {
    if (msBusy || (typeof nationalBusy !== 'undefined' && nationalBusy)) return;
    stopTimer(); try { notify('⏰ Vaqt tugadi. Javoblaringiz yuborilmoqda…'); } catch (e) {}
    try { collectNational(); } catch (e) {}
    await finish(true);
  }

  // ---------------------------------------------------------------- esse muharriri (45-topshiriq)
  const essayText = () => { const el = $('msEssay'); return (el ? el.value : (LS.get(kEssay()) || '')).trim(); };
  const words = t => (String(t || '').match(/[^\W_]+(?:['‘’`ʻʼ-][^\W_]+)*/g) || []).length;
  function afterRender() {
    if (!nationalTest) return;
    const q = nationalTest.questions[nationalIndex]; if (!q || q.type !== 'O2' || nationalTest.has_essay === false) return;
    const box = $('nationalAnswer'); if (!box) return;
    const min = nationalTest.min_words || 40, max = nationalTest.max_words || 1500;
    box.innerHTML = '<div class="result msEssay"><b>📝 45-topshiriq — yozma ish (esse)</b>' +
      '<p class="muted">Mavzu: «' + esc(nationalTest.essay_topic || 'ixtiyoriy') + '»</p>' +
      '<textarea id="msEssay" rows="14" placeholder="Esseni shu yerga yozing…" autocapitalize="sentences"></textarea>' +
      '<div class="msWc"><span id="msWc">0 so‘z</span><span>kamida ' + min + ' • ko‘pi bilan ' + max + '</span></div>' +
      '<p class="muted">«Yakunlash» bosilganda esse AI orqali 24 ballik mezon bo‘yicha tekshiriladi va natijangizga qo‘shiladi. Matn avtomatik saqlanadi.</p></div>';
    const ta = $('msEssay'), wc = $('msWc'); ta.value = LS.get(kEssay()) || '';
    const upd = () => { const n = words(ta.value); wc.textContent = n + ' so‘z'; wc.classList.toggle('bad', n > 0 && n < min || n > max); };
    ta.addEventListener('input', () => { LS.set(kEssay(), ta.value); upd(); }); upd();
  }

  // ---------------------------------------------------------------- yakunlash: esse → AI → test topshirish → natija
  async function finish(force) {
    if (!nationalTest || msBusy) return;
    window.__msElapsed = Math.max(0, Math.min(Date.now(), window.__msDeadline || Date.now()) - (window.__msStart || Date.now()));
    if (nationalTest.has_essay === false) { stopTimer(); submitEssayChoice('auto'); return; }
    const t = essayText(), min = nationalTest.min_words || 40;
    if (t && words(t) >= min) { await essayThenSubmit(t); return; }
    if (t && !force) { notify('Esse juda qisqa: kamida ' + min + ' so‘z yozing (hozir ' + words(t) + ').'); nationalIndex = nationalTest.questions.length - 1; renderNationalQuestion(); return; }
    stopTimer();
    if (nationalTest.is_mock) { submitEssayChoice('auto'); return; }
    showEssayChoice();
  }
  async function poll(job) {
    for (let i = 0; i < 100; i++) {
      await sleep(i < 4 ? 2500 : 3000);
      try {
        const r = await apiFetch(apiUrl('/api/job/' + encodeURIComponent(job)), { cache: 'no-store' }); const d = await r.json();
        if (d.ok && d.status === 'done') return { ok: true, data: d.data };
        if (d.ok && d.status === 'error') return { ok: false, error: d.error };
        if (!d.ok && r.status === 404) return { ok: false, error: 'Tekshiruv topilmadi.' };
      } catch (e) { /* tarmoq: qayta uriniladi */ }
    }
    return { ok: false, error: 'Tekshiruv uzoq davom etdi.' };
  }
  function note(html) { const q = $('nationalQuestion'), a = $('nationalAnswer'); if (q) q.innerHTML = html; if (a) a.innerHTML = ''; const n = $('btnNext'), p = $('btnPrev'); if (n) n.classList.add('hidden'); if (p) p.classList.add('hidden'); window.scrollTo(0, 0); }
  function fallback(msg) {
    note('<div class="result"><b>⚠️ Esse tekshirilmadi</b><p class="muted">' + esc(msg || 'Xatolik') + '</p><p class="muted">Matningiz saqlangan.</p></div>');
    const a = $('nationalAnswer');
    a.innerHTML = '<button class="primaryAction" type="button" id="msRetry">🔁 Qayta urinish</button><button class="listbtn" type="button" id="msOther">Esse ballini boshqa yo‘l bilan kiritish</button>';
    $('msRetry').onclick = () => finish(false);
    $('msOther').onclick = () => { stopTimer(); showEssayChoice(); };
  }
  async function essayThenSubmit(text) {
    if (msBusy) return; msBusy = true;
    note('<div class="result"><b>🤖 Esse tekshirilmoqda…</b><p class="muted">24 ballik mezon bo‘yicha. Odatda 30–90 soniya. Sahifani yopmang.</p><div class="msSpin"></div></div>');
    try {
      const r = await natPost(apiUrl('/api/ms/essay'), { code: nationalTest.code, text });
      if (!r.ok) { msBusy = false; fallback(r.error); return; }
      const res = await poll(r.job);
      if (!res.ok) { msBusy = false; fallback(res.error); return; }
      window.__msEssayInfo = res.data; nationalEssayScore = res.data.total; msBusy = false; stopTimer();
      note('<div class="result"><b>✅ Esse bali: ' + esc(String(res.data.total)) + '/24</b><p class="muted">Test javoblari yuborilmoqda…</p></div>');
      await submitEssayChoice('auto');
    } catch (e) { console.error(e); msBusy = false; fallback('Aloqa xatosi.'); }
  }
  window.msFinish = finish;

  // ---------------------------------------------------------------- natija: halqa + bo'limlar + savollar xaritasi
  function ring(p) {
    const r = 48, c = 2 * Math.PI * r, off = c * (1 - Math.max(0, Math.min(100, p)) / 100);
    return '<svg viewBox="0 0 112 112"><circle cx="56" cy="56" r="48" fill="none" stroke="#fff" stroke-width="10"/><circle cx="56" cy="56" r="48" fill="none" stroke="#2d8cf0" stroke-width="10" stroke-linecap="round" stroke-dasharray="' + c.toFixed(1) + '" stroke-dashoffset="' + off.toFixed(1) + '"/></svg>';
  }
  window.msResultTop = function (d) {
    window.__msRes = d;
    const comb = +(d.combined_score_75 != null ? d.combined_score_75 : d.score_75) || 0, pct = Math.round(comb / 75 * 100);
    const bd = d.breakdown || { sections: [], tiles: [] };
    const secs = (bd.sections || []).map(s => s.essay
      ? '<div><span>' + esc(s.name) + '</span><b>' + (d.essay_score != null ? esc(String(d.essay_score)) + '/24' : '—') + '</b></div>'
      : '<div><span>' + esc(s.name) + '</span><b>' + s.ok + '/' + s.total + (s.partial ? ' <small>(+' + s.partial + ' qisman)</small>' : '') + '</b></div>').join('');
    const el = window.__msElapsed ? '<div>⏱ Sarflangan vaqt: <b>' + Math.max(1, Math.round(window.__msElapsed / 60000)) + ' daqiqa</b></div>' : '';
    const crit = (window.__msEssayInfo && window.__msEssayInfo.criteria && window.__msEssayInfo.criteria.length)
      ? '<div class="msCrit"><b>📝 Esse mezonlari (AI)</b>' + window.__msEssayInfo.criteria.map(c => '<div><span>' + esc(c.n + '. ' + c.name) + '</span><b>' + c.score + '/2</b></div>').join('') + '</div>' : '';
    return '<h3>🎓 Diagnostik natija' + (d.subject ? ' — ' + esc(d.subject) : '') + '</h3>' +
      '<div class="msSumm"><div class="atRing">' + ring(pct) + '<div class="c"><b>' + comb + '</b><span>/ 75 ball</span></div></div>' +
      '<div class="msInfo"><div class="lv">Daraja: <b>' + esc(d.level) + '</b></div>' + el + '</div></div>' +
      '<div class="msSecs">' + secs + '</div>' + crit +
      '<button class="primaryAction" type="button" onclick="msOpenMap()">🗺 Savollar xaritasi</button>';
  };
  window.msOpenMap = function () {
    const d = window.__msRes; if (!d || !d.breakdown) return;
    const tiles = d.breakdown.tiles || [];
    let m = $('msModal'); if (!m) { m = document.createElement('div'); m.id = 'msModal'; m.className = 'msModal'; document.body.appendChild(m); }
    m.classList.remove('hidden'); document.body.style.overflow = 'hidden';
    const part = (name, a, b) => {
      const arr = tiles.filter(t => t.n >= a && t.n <= b); if (!arr.length) return '';
      return '<div class="atSecT">' + esc(name) + '</div><div class="atTiles">' + arr.map(t => '<button type="button" class="' + (t.status === 'essay' ? 'ci' : '') + (t.status === 'bad' || t.status === 'skip' ? ' bad' : '') + (t.status === 'partial' ? ' half' : '') + '">' + t.n + '</button>').join('') + '</div>';
    };
    const secs = (d.breakdown.sections || []).map(s => part(s.name, s.from, s.to)).join('');
    m.innerHTML = '<div class="atSheet"><div class="atSheetHd"><h3>Savollar xaritasi</h3><button class="atX" type="button" id="msMx">✕</button></div>' +
      '<div class="atLeg"><div><span class="sh"></span>To‘g‘ri</div><div><span class="sh bd"></span>Noto‘g‘ri / javobsiz</div><div><span class="sh half"></span>Qisman (a/b dan bittasi)</div><div><span class="sh ci"></span>Esse</div></div>' + secs + '</div>';
    const close = () => { m.classList.add('hidden'); m.innerHTML = ''; document.body.style.overflow = ''; };
    $('msMx').onclick = close; m.onclick = ev => { if (ev.target === m) close(); };
  };

  // ---------------------------------------------------------------- ulash (app.js funksiyalarini o'rash)
  const _start = window.startNational;
  if (typeof _start === 'function') window.startNational = async function (c) { await _start(c); try { if (nationalTest && $('nationalExam') && !$('nationalExam').classList.contains('hidden')) startTimer(); } catch (e) { console.error(e); } };
  const _rnq = window.renderNationalQuestion;
  if (typeof _rnq === 'function') window.renderNationalQuestion = function () { _rnq.apply(this, arguments); try { afterRender(); } catch (e) { console.error(e); } };
  const _clr = window.natClear;
  if (typeof _clr === 'function') window.natClear = function (c) { _clr.apply(this, arguments); try { stopTimer(); const k = String(c || '').toUpperCase(); LS.del('msstart_' + uid() + '_' + k); LS.del('msessay_' + uid() + '_' + k); } catch (e) {} };
  const _od = window.openNationalCreate;
  if (typeof _od === 'function') window.openNationalCreate = function () { const r = _od.apply(this, arguments); try { msCreateUi(false); } catch (e) {} return r; };
})();
