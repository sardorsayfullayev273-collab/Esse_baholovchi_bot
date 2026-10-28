// ===== v108+: Tez kiritish (matnni joylab qo‘yish) va uzun matnlar =====
// Test egasi 45 qatorni bittalab to‘ldirmaydi: matnni joylaydi — kalit, savol matnlari va uzun matnlar avtomatik joylashadi.
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const TAG = /^\s*#\s*(matn-tugadi|matn|savollar|esse)\b\s*[:\-–]?\s*(.*)$/i;
  const QRE = /^\s*(\d{1,2})\s*[.)](?!\d)\s*(.*)$/;   // «15.11.2024» savol raqami emas
  const OPT = /^\s*([*+✅✔]?)\s*\(?([A-Fa-f])\)?\s*[.)]\s*(.*)$/;
  const ANS = /^\s*(?:javob|to['‘’`ʻ]?g['‘’`ʻ]?ri\s+javob|kalit|answer)\s*[:=\-–]\s*(.+?)\s*$/i;
  const KEYHDR = /^\s*(?:javoblar(?:\s+kaliti)?|kalitlar|kalit)\s*[:\-–]?\s*(.*)$/i;
  const PAIR = /(?:^|\s)(\d{1,2})\s*[-–.:)=]+\s*([A-Fa-f])(?![A-Za-z0-9])/g;
  const OPENKEY = /^\s*(\d{1,2})\s*[=:]\s*(.+?)\s*$/;

  // type(n) — fan tuzilmasidan: 'Y1' | 'Y2' | 'O1' | 'O1AB' | 'O2'
  function parse(text, type) {
    text = String(text || '').replace(/\r/g, '');
    const items = {}, warn = []; let essay = '', passages = 0;
    let cur = null, curP = null, inPass = false, buf = [], lastOpt = false, inKey = false; const keyTxt = [];
    const flush = () => { cur = null; };
    for (const raw of text.split('\n')) {
      const line = raw.replace(/\s+$/, '');
      if (inPass) {
        const t = TAG.exec(line);
        if (t && t[1].toLowerCase() === 'savollar') {
          const body = buf.join('\n').trim(); buf = []; inPass = false;
          if (!body) { warn.push('Bo‘sh #matn bloki'); continue; }
          curP = { text: body, first: null }; passages++; continue;
        }
        buf.push(line); continue;
      }
      if (!line.trim()) continue;
      const t = TAG.exec(line);
      if (t) {
        const tag = t[1].toLowerCase();
        if (tag === 'matn') { inPass = true; buf = t[2] ? [t[2]] : []; flush(); }
        else if (tag === 'matn-tugadi') { curP = null; }
        else if (tag === 'esse') { essay = t[2].trim(); }
        continue;
      }
      if (inKey) { keyTxt.push(line); continue; }
      const kh = KEYHDR.exec(line);
      if (kh && !OPT.test(line) && !QRE.test(line)) { inKey = true; if (kh[1]) keyTxt.push(kh[1]); continue; }
      const am = ANS.exec(line);
      if (am && cur) { cur.raw = am[1].trim(); lastOpt = false; continue; }
      const om = OPT.exec(line);
      if (om && cur && !(cur.n >= 36 && cur.type !== 'Y1' && cur.type !== 'Y2')) {
        cur.lines.push(om[2].toUpperCase() + ') ' + om[3].trim()); if (om[1]) cur.raw = om[2].toUpperCase(); lastOpt = true; continue;
      }
      const qm = QRE.exec(line);
      if (qm && (!cur || cur.raw != null || cur.lines.length > 1 || !cur.opt)) {
        const n = +qm[1]; if (n < 1 || n > 45) { warn.push(n + '-savol: raqam 1–45 oralig‘ida bo‘lsin'); continue; }
        const ty = type(n);
        cur = { n, type: ty, lines: [qm[2].trim()], raw: null, opt: false };
        items[n] = cur;
        if (curP) { if (curP.first == null) { curP.first = n; cur.passage = curP.text; } else cur.from = curP.first; }
        lastOpt = false; continue;
      }
      if (cur) {
        if (lastOpt && cur.lines.length > 1) cur.lines[cur.lines.length - 1] += ' ' + line.trim();
        else cur.lines.push(line.trim());
      }
    }
    if (inPass) warn.push('#matn bloki #savollar bilan yopilmagan');
    // alohida «Javoblar: 1-A 2-B …» bloki
    const keys = {}; let m; const kt = keyTxt.join(' ');
    PAIR.lastIndex = 0; while ((m = PAIR.exec(' ' + kt))) keys[+m[1]] = m[2].toUpperCase();
    // ochiq javoblar: «36 = KITOB/KITOBLAR» yoki «40 = a) X ; b) Y»
    const openKeys = {};
    keyTxt.forEach(l => { const o = OPENKEY.exec(l); if (o && +o[1] >= 36) openKeys[+o[1]] = o[2]; });
    const out = {};
    Object.keys(items).forEach(k => {
      const q = items[k], n = q.n, ty = q.type; const o = { n, type: ty, text: q.lines.join('\n').trim() };
      if (q.passage) o.passage = q.passage; if (q.from) o.from = q.from;
      let raw = q.raw != null ? q.raw : (ty === 'Y1' || ty === 'Y2' ? keys[n] : openKeys[n]);
      if (ty === 'Y1' || ty === 'Y2') {
        const L = String(raw || '').trim().toUpperCase().charAt(0), max = ty === 'Y1' ? 'D' : 'F';
        if (L && L >= 'A' && L <= max) o.key = L; else warn.push(n + '-savol: to‘g‘ri javob (A–' + max + ') ko‘rsatilmagan');
      } else if (ty === 'O1') {
        const a = String(raw || '').split(/[\/;]/).map(x => x.trim()).filter(Boolean);
        if (a.length) o.ans = a.join('/'); else warn.push(n + '-savol: «Javob:» yo‘q');
      } else if (ty === 'O1AB') {
        const mm = /a\)?\s*(.*?)\s*[;|]\s*b\)?\s*(.*)$/i.exec(String(raw || ''));
        if (mm && mm[1] && mm[2]) { o.a = mm[1].trim(); o.b = mm[2].trim(); } else warn.push(n + '-savol: «Javob: a) …; b) …» ko‘rinishida yozing');
      }
      out[n] = o;
    });
    // faqat kalit berilgan (savol matnisiz) raqamlar
    Object.keys(keys).forEach(k => { const n = +k; if (!out[n] && n >= 1 && n <= 45) { const ty = type(n); if (ty === 'Y1' || ty === 'Y2') out[n] = { n, type: ty, text: '', key: keys[n] }; } });
    return { items: out, essay, passages, warn };
  }

  // ---- builder qatorlariga joylash
  function apply(res) {
    const cfg = window.msCfg ? window.msCfg() : null; let filled = 0; const missing = [];
    for (let n = 1; n <= 45; n++) {
      const it = res.items[n]; const ty = window.msType(n);
      if (ty === 'O2') continue;
      if (!it) { missing.push(n); continue; }
      const ct = $('ct' + n);
      if (ct) { ct.value = it.text || ''; delete ct.dataset.pass; delete ct.dataset.passFrom; if (it.passage) ct.dataset.pass = it.passage; if (it.from) ct.dataset.passFrom = String(it.from); }
      if (it.key) { document.querySelectorAll('.keyBtn[data-q="' + n + '"]').forEach(b => b.classList.toggle('selected', b.dataset.value === it.key)); }
      if (ty === 'O1' && $('co' + n)) $('co' + n).value = it.ans || '';
      if (ty === 'O1AB') { if ($('caa' + n)) $('caa' + n).value = it.a || ''; if ($('cab' + n)) $('cab' + n).value = it.b || ''; }
      const ok = (ty === 'Y1' || ty === 'Y2') ? !!it.key : (ty === 'O1' ? !!it.ans : !!(it.a && it.b));
      if (ok) filled++; else missing.push(n);
    }
    if (res.essay && cfg && cfg.essay && $('createEssayTopic') && !$('createEssayTopic').value.trim()) $('createEssayTopic').value = res.essay.slice(0, 300);
    return { filled, missing };
  }

  function run() {
    const ta = $('msQuickText'), out = $('msQuickOut'); if (!ta || !out) return;
    const box = $('builderQuestions');
    if (!box || box.dataset.ready !== '1') { try { openNationalCreate(); } catch (e) {} }
    const res = parse(ta.value, window.msType);
    const r = apply(res);
    const nq = Object.keys(res.items).length;
    let h = '<div class="result"><b>' + (nq ? '✅ ' + nq + ' ta topshiriq o‘qildi' : '⚠️ Birorta ham topshiriq topilmadi') + '</b>';
    h += '<p class="muted">To‘liq to‘ldirilgan: <b>' + r.filled + ' / ' + (window.msCfg().essay ? 44 : 45) + '</b>' + (res.passages ? ' • uzun matnlar: <b>' + res.passages + '</b>' : '') + (res.essay ? ' • esse mavzusi olindi' : '') + '</p>';
    if (r.missing.length) h += '<p class="muted">Kalit yetishmaydi: ' + r.missing.slice(0, 30).join(', ') + (r.missing.length > 30 ? '…' : '') + '. Quyidagi qatorlarda qo‘lda to‘ldirishingiz mumkin.</p>';
    res.warn.slice(0, 8).forEach(w => { h += '<p class="muted">• ' + esc(w) + '</p>'; });
    out.innerHTML = h + '<p class="muted">Pastga tushib tekshiring va «Testni yaratish»ni bosing.</p></div>';
  }

  const SAMPLE = '#matn\nAlisher Navoiy ulug‘ shoir va mutafakkir bo‘lgan. U ko‘plab asarlar yozgan.\n(Matn istagancha uzun bo‘lishi mumkin)\n#savollar\n1. Matn kim haqida?\nA) Navoiy\nB) Bobur\nC) Fitrat\nD) Cho‘lpon\nJavob: A\n2. Navoiy nima qilgan?\nA) asar yozgan\nB) ekin ekkan\nC) sayohat qilgan\nD) rasm chizgan\nJavob: A\n#matn-tugadi\n3. Oddiy savol\nA) a\nB) b\nC) c\nD) d\nJavob: C\n\n36. Ochiq savol matni\nJavob: KITOB/KITOBLAR\n40. a) va b) bandli savol\nJavob: a) NEGAKI ; b) ERGASHGAN\n\n(Faqat kalit ham bo‘ladi:)\nJavoblar: 4-B 5-C 6-D\n#esse Texnologiya davrida kitob o‘qishning ahamiyati';

  function ui() {
    const page = $('nationalCreate'); if (!page || $('msQuick')) return;
    const host = $('builderQuestions'); if (!host) return;
    const d = document.createElement('details'); d.id = 'msQuick'; d.className = 'result msQuick'; d.open = false;
    d.innerHTML = '<summary><b>⚡ Tez kiritish</b> — matnni joylang, qatorlar o‘zi to‘ldiriladi</summary>' +
      '<p class="muted">Word yoki Telegramdan nusxalab joylang. Savol, variantlar, <b>Javob: B</b>. Uzun matn uchun <b>#matn</b> … <b>#savollar</b> — shu matnga tegishli barcha savollar uni bitta joyda ko‘radi (<b>#matn-tugadi</b> bilan tugaydi). Faqat kalit uchun: <b>Javoblar: 1-A 2-C …</b>. Ochiq savol: <b>Javob: KITOB/KITOBLAR</b>, a/b bandli: <b>Javob: a) … ; b) …</b>. Esse: <b>#esse Mavzu</b>.</p>' +
      '<textarea id="msQuickText" rows="10" maxlength="400000" placeholder="Matnni shu yerga joylang…"></textarea>' +
      '<div class="msQRow"><button type="button" class="ghostAction" id="msQuickSample">📄 Namuna</button><button type="button" class="primaryAction" id="msQuickRun">⚡ Qatorlarga joylash</button></div><div id="msQuickOut"></div>';
    host.parentNode.insertBefore(d, host);
    $('msQuickRun').onclick = run;
    $('msQuickSample').onclick = () => { $('msQuickText').value = SAMPLE; };
  }

  // ---- foydalanuvchi uchun uzun matn o‘quvchisi (imtihon oynasida)
  window.natPassageHtml = function (q) {
    try {
      let p = q.passage || '', id = q.number;
      if (!p && q.passage_from > 0) { const nt = (typeof nationalTest !== 'undefined') ? nationalTest : null; const s = nt && nt.questions[q.passage_from - 1]; p = (s && s.passage) || ''; id = q.passage_from; }
      if (!p) return '';
      const st = window.__natPass = window.__natPass || { shut: {}, big: {}, fs: +(localStorage.getItem('ms_pfs') || 16) };
      const shut = st.shut[id], big = st.big[id];
      return '<div class="natPass' + (shut ? ' shut' : '') + (big ? ' big' : '') + '" style="--natfs:' + st.fs + 'px"><div class="natPassHd"><b>📖 Matn</b><span><button type="button" onclick="natPass(\'fs\',-1)">A−</button><button type="button" onclick="natPass(\'fs\',1)">A+</button><button type="button" onclick="natPass(\'big\',' + id + ')">' + (big ? '⤡' : '⤢') + '</button><button type="button" onclick="natPass(\'shut\',' + id + ')">' + (shut ? 'Ochish' : 'Yopish') + '</button></span></div><div class="natPassBd">' + rich(p) + '</div></div>';
    } catch (e) { return ''; }
  };
  window.natPass = function (what, v) {
    const st = window.__natPass = window.__natPass || { shut: {}, big: {}, fs: 16 };
    if (what === 'fs') { st.fs = Math.max(13, Math.min(24, st.fs + v)); try { localStorage.setItem('ms_pfs', st.fs); } catch (e) {} }
    else st[what][v] = !st[what][v];
    try { renderNationalQuestion(); } catch (e) {}
  };

  window.msQuickParse = parse;
  document.addEventListener('DOMContentLoaded', ui);
  if (document.readyState !== 'loading') ui();
})();
