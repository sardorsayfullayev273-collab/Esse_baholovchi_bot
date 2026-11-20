// ===== v134: Yo'riqnoma =====
// 1) Bo'limlarda «Bu bo'lim nima beradi?» izohi  2) Bosh sahifada «Qayerdan boshlay?» kartasi va spotlight-tur
// 3) Kurslar: faqat foydalanuvchi bepul imkoniyatlardan foydalangandan keyin ko'rsatiladi  4) Kurslar sahifasida «sotuvchi» kartalar
// Mavjud kodga tegmaydi: openSection / openAkad / rpRenderDiag ni o'rab oladi. Xato bo'lsa — jim o'tadi (ilova ishlashda davom etadi).
(function () {
  'use strict';
  const K = { tour: 'gd_tour_134', seen: 'gd_seen_', first: 'gd_first', free: 'gd_free', fv: 'gd_foydali', hc: 'gd_hc', dc: 'gd_dc', exp: 'gd_exp' };
  const LS = (k, v) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; };
  const $ = id => document.getElementById(id);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const inTg = () => !!(window.Telegram && Telegram.WebApp && Telegram.WebApp.initData);
  const recent = (ts, days) => ts && (Date.now() - (+ts)) < days * 864e5;
  let G = null, P = {};
  const PAID = ['books', 'expert', 'gazallib', 'gazal', 'akad', 'foydali', 'essewin', 'bookPage'];
  const GO = { books: () => openSection('books'), expert: () => openSection('expert'), gazallib: () => openSection('gazallib'), gazal: () => openSection('gazal'), akad: () => (typeof openAkad === 'function' ? openAkad() : openSection('foydali')), foydali: () => openSection('foydali'), essewin: () => openSection('essewin'), national: () => openSection('national'), mashq: () => openSection('mashq') };
  const EB = { books: 'BADIIY ASARLAR • PREMIUM', expert: 'ESSE TEKSHIRUV', gazallib: 'MUMTOZ ADABIYOT', gazal: 'MUMTOZ ADABIYOT', akad: 'MUMTOZ TAHLIL MAKTABI' };
  const CHIPS = { books: ['40 ta qo‘llanma', 'Rasmli ideografika', 'Imtihon savollari tipida', '100 ga yaqin o‘quvchi tanlagan'], expert: ['1 700+ AI tekshiruv', '50 ga yaqin ekspert tekshiruvi', 'Botda 1 ta bepul'], gazallib: ['Qo‘llanma + videodars'], gazal: ['Mumtoz adabiyot: hammasi bir joyda'], akad: ['{akad_days} kun', 'AI tekshiruv'] };
  const fill = s => String(s).replace(/\{(\w+)\}/g, (m, k) => (P[k] != null ? P[k] : m));

  async function load() {
    try { const r = await fetch('guide.json?v=134', { cache: 'no-cache' }); G = await r.json(); } catch (e) { G = null; return; }
    P = Object.assign({}, G.price_defaults || {});
    if (inTg() && typeof apiFetch === 'function') {
      try { const r = await apiFetch(apiUrl('/api/guide/prices'), { cache: 'no-store' }); const d = await r.json(); if (d && d.ok) Object.assign(P, d.p || {}); } catch (e) {}
    }
  }

  // ---------- bo'lim izohi ----------
  const pts = s => '<ul class="gdPts">' + (s.pts || []).map(p => '<li><em>' + esc(p[0]) + '</em><div><b>' + esc(fill(p[1])) + '</b><span>' + esc(fill(p[2] || '')) + '</span></div></li>').join('') + '</ul>';
  function paidRow(s) { return s.paid ? '<div class="gdPaid"><b>' + esc(fill(s.paid.price)) + ' so‘m</b><small>' + esc(fill(s.paid.note || '')) + '</small></div>' : ''; }
  function box(id) {
    const s = G && G.sections[id], m = $(id); if (!s || !m) return null;
    let b = m.querySelector(':scope > .gdBox');
    if (!b) {
      b = document.createElement('div'); b.className = 'gdBox'; b.dataset.id = id;
      b.innerHTML = '<button type="button" class="gdHead">ⓘ Bu bo‘lim nima beradi?<i>›</i></button><div class="gdBody"></div>';
      b.querySelector('.gdHead').onclick = () => b.classList.toggle('open');
      const kids = [...m.children]; const a = kids.find(c => c.classList.contains('pgHead')) || kids.find(c => c.classList.contains('back'));
      if (a) a.after(b); else m.prepend(b);
    }
    b.querySelector('.gdBody').innerHTML = '<p class="gdTag">' + esc(fill(s.tag)) + '</p>' + (s.intro ? '<p style="margin:0 0 6px;font-size:13px;color:#5a6b61">' + esc(fill(s.intro)) + '</p>' : '') + pts(s) + paidRow(s);
    return b;
  }

  // ---------- holat ----------
  function freeVisited() { try { return JSON.parse(LS(K.free) || '[]'); } catch (e) { return []; } }
  function markFree(id) { if (id === 'home' || PAID.includes(id)) return; const a = freeVisited(); if (!a.includes(id)) { a.push(id); LS(K.free, JSON.stringify(a)); } }
  function courseReady() {
    const h = window.hubD; const days = (Date.now() - (+LS(K.first) || Date.now())) / 864e5;
    return !!(h && h.forecast) || freeVisited().length >= 3 || days >= 3;
  }

  // ---------- bosh sahifa: keyingi qadam, kurslar eslatmasi ----------
  function nextStep() {
    const h = window.hubD;
    if (!h || !h.forecast) return { s: 'Sizning keyingi qadamingiz', t: 'Diagnostik testni ishlang', x: 'Darajangiz va zaif mavzularingiz aniqlanadi', go: 'national', b: 'Boshlash' };
    if (h.mistakes_due > 0) return { s: 'Sizning keyingi qadamingiz', t: 'Xatolar ustida ishlang', x: h.mistakes_due + ' ta xato takrorlashni kutyapti', go: 'mashq', b: 'Mashq qilish' };
    if (!LS(K.exp)) return { s: 'Sizning keyingi qadamingiz', t: 'Esseingizni tekshirtiring', x: 'AI yoki ekspert: ball va aniq tavsiya', go: 'expert', b: 'Tekshirtirish' };
    return { s: 'Bugungi reja', t: 'Kunlik mashqni bajaring', x: '5 daqiqa — seriyangiz saqlanadi', go: 'mashq', b: 'Mashq qilish' };
  }
  function renderNext() {
    const home = $('home'); if (!home || !G) return;
    let c = $('gdNext');
    if (!c) { c = document.createElement('section'); c.id = 'gdNext'; c.className = 'gdNext'; const hero = home.querySelector('.hero'); if (hero) hero.before(c); else home.prepend(c); }
    const n = nextStep();
    c.innerHTML = '<small>' + esc(n.s) + '</small><b>' + esc(n.t) + '</b><div style="font-size:13px;opacity:.9;margin:-4px 0 10px">' + esc(n.x) + '</div><button type="button">' + esc(n.b) + ' ›</button>';
    c.querySelector('button').onclick = () => { try { GO[n.go](); } catch (e) {} };
    // kurslar eslatmasi: faqat tayyor bo'lganda
    let k = $('gdCourse');
    const show = courseReady() && !LS(K.fv) && !recent(LS(K.hc), 7);
    if (show && !k) {
      k = document.createElement('section'); k.id = 'gdCourse'; k.className = 'gdCourse';
      k.innerHTML = '<button class="gdX" type="button" aria-label="Yopish">✕</button><b>📚 Kurslar: chuqur tayyorgarlik</b><p>Esse kursi, badiiy asarlar va mumtoz adabiyot — har birining nima berishi shu yerda.</p><button class="go" type="button">Ko‘rish ›</button>';
      k.querySelector('.go').onclick = () => openSection('foydali');
      k.querySelector('.gdX').onclick = () => { LS(K.hc, String(Date.now())); k.remove(); };
      c.after(k);
    } else if (!show && k) k.remove();
    const nav = document.querySelector('[data-k=foydali]'); if (nav) nav.classList.toggle('gdDot', courseReady() && !LS(K.fv));
  }

  // ---------- Kurslar sahifasi ----------
  function renderCourses() {
    const m = $('foydali'); if (!m || !G) return;
    let c = $('gdCourses');
    if (!c) { c = document.createElement('div'); c.id = 'gdCourses'; c.className = 'gdCards'; m.appendChild(c); }
    const akOn = $('akadHome') && !$('akadHome').classList.contains('hidden');
    let h = '<h3 class="gdH">HAR BIR KURS NIMA BERADI</h3>';
    (G.courses || []).forEach(id => {
      if (id === 'akad' && !akOn) return;
      const s = G.sections[id]; if (!s) return;
      h += '<div class="gdCard"><div class="gdEb">' + esc(EB[id] || '') + '</div><h4>' + esc(fill(s.tag)) + '</h4>' + (s.intro ? '<p style="margin:0 0 8px;font-size:14px;color:#5a6b61">' + esc(fill(s.intro)) + '</p>' : '') + pts(s)
        + '<div class="gdChips">' + (CHIPS[id] || []).map(x => '<i>' + esc(fill(x)) + '</i>').join('') + '</div>' + paidRow(s)
        + '<button type="button" class="gdCta" data-go="' + id + '">' + esc(s.paid ? s.paid.cta : 'Ochish') + '</button></div>';
    });
    c.innerHTML = h;
    c.querySelectorAll('.gdCta').forEach(b => { b.onclick = () => { try { GO[b.dataset.go](); } catch (e) {} }; });
  }

  // ---------- diagnostik natijadan keyin ----------
  function diagCard() {
    if (recent(LS(K.dc), 7)) return;
    setTimeout(() => {
      const host = $('nationalResult'); if (!host || host.querySelector('.gdDiag')) return;
      const d = document.createElement('div'); d.className = 'gdDiag';
      d.innerHTML = '<b>Zaif joylaringizni mustahkamlang</b><p>Esse yoki mumtoz adabiyotda ball yo‘qotayotgan bo‘lsangiz, kurslar aynan shu uchun.</p><button type="button" data-g="essewin">✍️ Esse kursi</button><button type="button" data-g="foydali">📚 Barcha kurslar</button>';
      d.querySelectorAll('button').forEach(b => { b.onclick = () => GO[b.dataset.g](); });
      host.appendChild(d); LS(K.dc, String(Date.now()));
    }, 500);
  }

  // ---------- spotlight-tur ----------
  let ov = null;
  function endTour() { if (ov) { ov.remove(); ov = null; } LS(K.tour, '1'); window.removeEventListener('resize', place); }
  let cur = 0, steps = [];
  function vis(el) { return el && el.offsetParent !== null; }
  function place() { if (ov) show(cur, true); }
  function show(i, keep) {
    if (!ov) return;
    while (i < steps.length && !vis(document.querySelector(steps[i].sel))) i++;
    if (i >= steps.length) { endTour(); return; }
    cur = i; const st = steps[i], el = document.querySelector(st.sel);
    if (!keep) el.scrollIntoView({ block: 'center' });
    setTimeout(() => {
      if (!ov) return; const r = el.getBoundingClientRect(), hole = ov.querySelector('.gdHole'), tip = ov.querySelector('.gdTip');
      hole.style.cssText = 'left:' + (r.left - 6) + 'px;top:' + (r.top - 6) + 'px;width:' + (r.width + 12) + 'px;height:' + (r.height + 12) + 'px';
      const last = !steps.slice(i + 1).some(s => vis(document.querySelector(s.sel)));
      tip.innerHTML = '<small>' + (i + 1) + ' / ' + steps.length + '</small><b>' + esc(st.t) + '</b><p>' + esc(st.x) + '</p><div class="r"><button class="sk" type="button">O‘tkazib yuborish</button><button class="nx" type="button">' + (last ? 'Boshlash' : 'Keyingi') + '</button></div>';
      const w = Math.min(340, innerWidth - 24); tip.style.width = w + 'px'; tip.style.left = Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width / 2 - w / 2)) + 'px';
      const th = tip.offsetHeight; const below = r.bottom + th + 22 < innerHeight;
      tip.style.top = (below ? r.bottom + 14 : Math.max(10, r.top - th - 14)) + 'px';
      tip.querySelector('.sk').onclick = endTour; tip.querySelector('.nx').onclick = () => (last ? endTour() : show(i + 1));
    }, keep ? 0 : 160);
  }
  function startTour(force) {
    if (!G || ov) return;
    if (!force && LS(K.tour)) return;
    const home = $('home'); if (!home || home.classList.contains('hidden')) { if (!force) return; try { goHome(); } catch (e) {} }
    steps = G.tour.slice(); cur = 0;
    ov = document.createElement('div'); ov.className = 'gdOv'; ov.innerHTML = '<div class="gdHole"></div><div class="gdTip"></div>';
    document.body.appendChild(ov); window.addEventListener('resize', place); show(0);
  }

  // ---------- ulash ----------
  function onOpen(id) {
    if (!G) return;
    markFree(id);
    if (id === 'expert') LS(K.exp, '1');
    if (id === 'foydali') { LS(K.fv, '1'); renderCourses(); const n = document.querySelector('[data-k=foydali]'); if (n) n.classList.remove('gdDot'); }
    if (id === 'profil') {
      const m = $('profil'); if (m && !$('gdTourBtn')) { const b = document.createElement('button'); b.id = 'gdTourBtn'; b.type = 'button'; b.className = 'gdBtn'; b.textContent = '🧭 Yo‘riqnoma: ilovadan foydalanish'; b.onclick = () => { try { goHome(); } catch (e) {} setTimeout(() => startTour(true), 250); }; m.appendChild(b); }
    }
    const b = box(id);
    if (b && !LS(K.seen + id)) { b.classList.add('open'); LS(K.seen + id, '1'); }
  }
  function wrap() {
    if (typeof window.openSection === 'function' && !window.openSection.__gd) {
      const o = window.openSection; const w = function (id) { const r = o.apply(this, arguments); try { onOpen(id); } catch (e) {} return r; }; w.__gd = 1; window.openSection = w;
    }
    if (typeof window.openAkad === 'function' && !window.openAkad.__gd) {
      const o = window.openAkad; const w = function () { const r = o.apply(this, arguments); setTimeout(() => { try { onOpen('akad'); } catch (e) {} }, 80); return r; }; w.__gd = 1; window.openAkad = w;
    }
    if (typeof window.goHome === 'function' && !window.goHome.__gd) {
      const o = window.goHome; const w = function () { const r = o.apply(this, arguments); try { renderNext(); } catch (e) {} return r; }; w.__gd = 1; window.goHome = w;
    }
    if (typeof window.rpRenderDiag === 'function' && !window.rpRenderDiag.__gd) {
      const o = window.rpRenderDiag; const w = function () { const r = o.apply(this, arguments); try { diagCard(); } catch (e) {} return r; }; w.__gd = 1; window.rpRenderDiag = w;
    }
  }
  async function init() {
    if (!LS(K.first)) LS(K.first, String(Date.now()));
    await load(); if (!G) return;
    wrap(); renderNext();
    document.addEventListener('hubdata', () => { try { renderNext(); } catch (e) {} });
    // mavjud foydalanuvchilar ham turni birinchi kirishda ko'radi (bir marta)
    if (inTg() && !LS(K.tour)) setTimeout(() => { try { startTour(false); } catch (e) {} }, 1600);
  }
  window.GD = { tour: startTour, box, onOpen };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
