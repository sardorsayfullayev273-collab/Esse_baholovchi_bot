// ===== v72: O‘quv markazi =====
// Bugungi reja • ball bashorati • xatolar daftari (1-3-7-14 kunlik takrorlash) • zaif mavzular xaritasi.
// Mavjud games.js / app.js ga tegmaydi: faqat gmMistake, gmFinish, openSection va loadHomeMock ni o‘rab oladi.
(function () {
  'use strict';
  const H = { d: null, done: [], loadedAt: 0, loading: null, q: [], timer: null, S: null };
  const inTg = () => !!(window.Telegram && Telegram.WebApp && Telegram.WebApp.initData);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // faqat oddiy belgilash teglariga ruxsat (serverdan qaytgan savol matni uchun)
  const safeHtml = s => esc(s).replace(/&lt;(\/?)(u|b|i|em|strong|mark)&gt;/g, '<$1$2>');
  const $$ = id => document.getElementById(id);
  const api = (p, o) => apiFetch(apiUrl(p), o);
  const jpost = (p, b, extra) => api(p, Object.assign({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) }, extra || {}));
  const hubLS = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };

  // ------------------------------------------------------------ ma'lumot
  async function hubLoad(force) {
    if (!inTg()) return null;
    if (H.loading) return H.loading;
    if (!force && H.d && Date.now() - H.loadedAt < 20000) return H.d;
    H.loading = (async () => {
      try {
        const r = await api('/api/hub/home', { cache: 'no-store' }); const d = await r.json();
        if (d && d.ok) { H.d = d; H.done = d.done || []; H.loadedAt = Date.now(); }
      } catch (e) { /* oflayn: eski ma'lumot bilan davom */ }
      finally { H.loading = null; }
      return H.d;
    })();
    return H.loading;
  }
  function examDays() {
    const s = (typeof ME !== 'undefined' && ME && ME.exam_date) || ''; if (!s) return null;
    const d = new Date(s + 'T00:00:00'); if (isNaN(d)) return null;
    const n = Math.ceil((d - new Date()) / 86400000); return (n < 0 || n > 400) ? null : n;
  }
  function topicStats() {
    const m = {}; ((H.d && H.d.topics) || []).forEach(x => { m[x.c] = { ok: x.ok, t: x.t }; });
    const loc = hubLS('gm_topic', {}); Object.keys(loc).forEach(k => { const e = loc[k]; if (e && e.t && (!m[k] || e.t > m[k].t)) m[k] = { ok: e.c, t: e.t }; });
    return m;
  }
  function weakTopic() {
    const m = topicStats(); let w = null;
    Object.keys(GM_CATS).forEach(k => { const e = m[k]; if (!e || e.t < 5) return; const p = e.ok / e.t; if (p < .75 && (!w || p < w.p)) w = { c: k, p: p }; });
    return w;
  }
  const catName = k => (GM_CATS[k] || {}).name || k;

  // ------------------------------------------------------------ sinxronizatsiya (xatolar → server)
  function hubTrack(q, ok) {
    if (!inTg() || !q) return;
    const key = gmQKey(q);
    const topic = q.src === 'bank' ? (q.c || '') : ({ imlo: 'imlo', sinonim: 'leks', paronim: 'leks', omonim: 'leks' }[q.t] || '');
    let payload;
    if (q.src === 'bank') payload = { src: 'bank', id: q.id, c: q.c };
    else payload = { t: q.t, q: q.q, sentParts: q.sentParts, sentHtml: q.sentHtml, opts: q.opts, ans: q.ans, exp: q.exp };
    pushQ({ key, payload: ok ? undefined : payload, topic, ok: !!ok });
  }
  function pushQ(it) {
    H.q = H.q.filter(x => x.key !== it.key); H.q.push(it);
    clearTimeout(H.timer); H.timer = setTimeout(() => flush(false), 2500);
  }
  function flush(keep) {
    if (!H.q.length || !inTg()) return;
    const items = H.q.splice(0, 30);
    jpost('/api/hub/sync', { items }, keep ? { keepalive: true } : {}).then(r => r.json()).then(d => {
      if (d && d.ok && H.d) { H.d.mistakes_due = d.mistakes_due; H.d.mistakes_total = d.mistakes_total; }
    }).catch(() => { H.q = items.concat(H.q).slice(0, 120); });
    if (H.q.length) setTimeout(() => flush(keep), 400);
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush(true); });
  async function hubDone(task) {
    if (!H.done.includes(task)) H.done.push(task);
    if (!inTg()) return;
    try { const r = await jpost('/api/hub/done', { task }); const d = await r.json(); if (d && d.ok) H.done = d.done; } catch (e) {}
    try { if (!$$('home').classList.contains('hidden')) renderHome(); } catch (e) {}
  }

  // ------------------------------------------------------------ BOSH SAHIFA
  function greet() { const h = new Date(Date.now() + 5 * 3600 * 1000).getUTCHours(); return h < 5 ? 'Xayrli tun' : h < 11 ? 'Xayrli tong' : h < 18 ? 'Xayrli kun' : 'Xayrli kech'; }
  function buildTasks() {
    const done = H.done || []; const T = [];
    const dailyDone = done.includes('daily') || !!(typeof GM_STATE !== 'undefined' && GM_STATE && GM_STATE.today_done);
    T.push({ id: 'daily', t: 'Kunlik 5 savol', s: 'Bugun: ' + (typeof gmDailyLabel === 'function' ? gmDailyLabel() : 'yangi savollar') + ' • seriyani saqlaydi', min: 4, done: dailyDone, go: () => gmStart('daily') });
    const due = (H.d && H.d.mistakes_due) || 0;
    if (due > 0 || done.includes('mistakes')) T.push({ id: 'mistakes', t: 'Xatolar daftari' + (due ? ' • ' + due + ' ta' : ''), s: 'Unutmaslik uchun takrorlash', min: Math.max(2, Math.ceil(Math.min(due || 4, 10) * .5)), done: done.includes('mistakes') && !due, go: openMistakes });
    const w = weakTopic();
    T.push(w ? { id: 'topic', t: 'Zaif mavzu: ' + catName(w.c) + ' (' + Math.round(w.p * 100) + '%)', s: 'Eng ko‘p yutadigan joy', min: 6, done: done.includes('topic'), go: () => gmStart('topic', w.c) }
      : { id: 'topic', t: 'Mavzu bo‘yicha mashq', s: 'Mavzuni o‘zingiz tanlang', min: 6, done: done.includes('topic'), go: () => openSection('mashq') });
    return T;
  }
  const CHK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-10"/></svg>';
  function renderHome() {
    const home = $$('home'); if (!home) return;
    const hero = home.querySelector('.hero');
    const user = (typeof tg !== 'undefined' && tg && tg.initDataUnsafe && tg.initDataUnsafe.user) || {};
    const days = examDays();
    if (hero) {
      hero.classList.add('hbHero');
      hero.innerHTML = '<div class="hbTop"><div><span>' + greet() + '</span><h2>Salom, ' + esc(user.first_name || 'o‘quvchi') + '</h2></div>'
        + '</div>'
        + '<div class="hbChips">' + ''
        + '<span class="hbChip">🎯 Milliy sertifikat • ona tili</span></div>'
        + '<div class="heroAuthor">Muallif: <b>Sardor Sayfullayev</b></div>';
    }
    let box = $$('hubHome');
    if (!box) { box = document.createElement('section'); box.id = 'hubHome'; box.className = 'hbWrap'; (hero || home.firstChild).after(box); }
    let h = '';
    // ball bashorati
    const f = H.d && H.d.forecast;
    if (f) {
      h += '<div class="hbTwo"><div class="hbStat"><small>Taxminiy ball</small><b>' + f.score + ' <i>/ ' + f.max + '</i></b><div class="hbBar"><u style="width:' + Math.min(100, Math.round(f.score / f.max * 100)) + '%"></u></div><em>Daraja: ' + esc(f.level) + ' • bot hisobi</em></div>'
        + '<div class="hbStat"><small>' + (f.next_level ? esc(f.next_level) + ' darajagacha' : 'Eng yuqori daraja') + '</small><b class="gold">' + (f.next_level ? f.next_gap + ' <i>ball</i>' : '🏆') + '</b><em>Oxirgi ' + f.attempts + ' ta diagnostik testdan</em></div></div>'
        + ((typeof ME !== 'undefined' && ME && ME.ref_link) ? '<button type="button" class="hbShare" data-i="s">📤 Natijamni do‘stlarga ulashish</button>' : '');
    } else if (inTg()) {
      h += '<button type="button" class="hbCta" data-i="d"><b>📈</b><span><strong>Ball bashoratingizni ko‘ring</strong><small>Bitta diagnostik test — va qaysi darajada ekaningiz hamda nimani o‘qish kerakligi chiqadi.</small></span></button>';
    }
    box.innerHTML = h;
    box.onclick = ev => {
      const b = ev.target.closest('[data-i]'); if (!b) return; const i = b.getAttribute('data-i');
      if (i === 'e') return openSection('essewin'); if (i === 'm') return openSection('mock'); if (i === 'd') return openSection('national'); if (i === 's') return shareForecast();
    };
    loadRules().then(() => renderRule(box));
    renderPromo(home);
    hubLoad().then(d => { if (d && d !== H._rendered) { H._rendered = d; renderHome(); } });
  }
  function renderPromo(home) {
    let p = $$('hubPromo');
    if (!p) { p = document.createElement('div'); p.id = 'hubPromo'; (home.querySelector('.grid') || home).after(p); }
    const f = H.d && H.d.forecast; const days = examDays(); let h = '';
    const near = f && f.next_level && f.next_gap > 0 && f.next_gap <= 8;
    const closing = false;
    if (near || closing) {
      h += '<button type="button" class="hbPromo gold" onclick="openSection(\'expert\')"><b>👨‍🏫</b><span><strong>' + (near ? esc(f.next_level) + ' darajagacha ' + f.next_gap + ' ball qoldi' : 'Imtihongacha ' + days + ' kun qoldi') + '</strong><small>Esseni ekspert tekshirsa — eng tez o‘sish yo‘li. 24 soat ichida batafsil natija.</small></span><i>›</i></button>';
    }
    // v89: obuna holati (bitta chip)
    { const act = ME && ME.premium_active;
      h += '<button type="button" class="hbSub' + (act ? ' on' : '') + '" onclick="openSection(\'' + 'premium' + '\')">' + (act ? '✅ Premium faol • ' + (ME.premium_days_left || 0) + ' kun qoldi' : '🏷️ Obuna yo‘q • chegirmali narxlarni ko‘ring') + '<i>›</i></button>'; }
    p.innerHTML = h;
  }
  window.hubOpenChannel = function () {
    const u = ME && ME.channel_url; if (!u) return;
    try { if (tg && tg.openTelegramLink) return tg.openTelegramLink(u); } catch (e) {}
    window.open(u, '_blank');
  };

  // ------------------------------------------------------------ MASHQ: xatolar kartasi + xarita
  function renderPlan(page) {
    let box = $$('hubPlan');
    if (!box) { box = document.createElement('section'); box.id = 'hubPlan'; (page.querySelector('.pgHead') || page.firstChild).after(box); }
    const T = buildTasks(); const nDone = T.filter(x => x.done).length; const cur = T.find(x => !x.done);
    const left = T.filter(x => !x.done).reduce((a, x) => a + x.min, 0);
    const dash = Math.round(nDone / T.length * 157.08);
    let h = '<div class="hbCard"><div class="hbPlanHead">'
      + '<svg class="hbRing" width="62" height="62" viewBox="0 0 62 62" role="img" aria-label="' + T.length + ' dan ' + nDone + ' vazifa bajarildi"><circle cx="31" cy="31" r="25" fill="none" stroke="#e3f1ea" stroke-width="7"/><circle cx="31" cy="31" r="25" fill="none" stroke="#128a63" stroke-width="7" stroke-linecap="round" stroke-dasharray="' + dash + ' 157" transform="rotate(-90 31 31)"/><text x="31" y="36" text-anchor="middle" font-size="15" font-weight="800" fill="#0d2b22">' + nDone + '/' + T.length + '</text></svg>'
      + '<div><h3>Bugungi reja</h3><p>' + (cur ? 'Taxminan ' + left + ' daqiqa • ' + (T.length - nDone) + ' ta qoldi' : 'Bugungi reja bajarildi — barakalla!') + '</p></div></div><div class="hbTasks">';
    T.forEach((x, i) => {
      h += '<button type="button" class="hbTask' + (x.done ? ' done' : '') + (cur && cur.id === x.id ? ' cur' : '') + '" data-i="' + i + '"><span class="hbChk">' + (x.done ? CHK : '') + '</span><span class="hbTi">' + esc(x.t) + '<small>' + esc(x.s) + '</small></span><span class="hbMin">' + x.min + ' daq</span></button>';
    });
    h += '<button type="button" class="hbTask hint" data-i="e"><span class="hbChk"></span><span class="hbTi">Esse mashqi<small>Ixtiyoriy • 24 ballik topshiriq uchun</small></span><span class="hbMin">8 daq</span></button>';
    h += '</div><button type="button" class="hbGo' + (cur ? '' : ' ghost') + '" data-i="' + (cur ? T.indexOf(cur) : 'm') + '" id="hbGo">' + (cur ? (nDone ? 'Davom ettirish' : 'Boshlash') : 'Mock imtihonga o‘tish') + '</button></div>';
    box.innerHTML = h;
    box.onclick = ev => {
      const b = ev.target.closest('[data-i]'); if (!b) return; const i = b.getAttribute('data-i');
      if (i === 'e') return openSection('essewin'); if (i === 'm') return openSection('mock');
      const t = T[+i]; if (t) t.go();
    };
  }
  function renderMap() {
    const page = $$('mashq'); if (!page) return;
    try { renderPlan(page); } catch (e) { console.error(e); }
    let box = $$('hubMap');
    if (!box) { box = document.createElement('section'); box.id = 'hubMap'; (page.querySelector('.pgHead') || page.firstChild).after(box); }
    const m = topicStats(); const keys = Object.keys(GM_CATS);
    const total = (H.d && H.d.mistakes_total) || 0, due = (H.d && H.d.mistakes_due) || 0;
    let h = '';
    if (inTg()) {
      h += '<div class="hbCard"><div class="hmBig"><b>' + due + '</b><span>ta savol bugun takrorlanadi' + (total ? ' • daftarda ' + total + ' ta' : '') + '</span></div>'
        + '<div class="hmSteps">Takror oralig‘i: <i>1 kun</i><i>3 kun</i><i>7 kun</i><i>14 kun</i></div>'
        + '<button type="button" class="hbGo' + (due ? '' : ' ghost') + '" onclick="hubOpenMistakes()">' + (due ? '📒 Takrorlashni boshlash' : '📒 Xatolar daftarini ochish') + '</button></div>';
    }
    const rows = keys.map(k => { const e = m[k]; return { k, p: e && e.t ? Math.round(e.ok / e.t * 100) : null, t: e ? e.t : 0 }; })
      .sort((a, b) => (a.p === null) - (b.p === null) || (a.p || 0) - (b.p || 0));
    h += '<div class="hbCard"><div class="hmH"><h3>Zaif mavzular xaritasi</h3><small>Barcha javoblaringiz asosida</small></div>';
    rows.forEach(r => {
      const cls = r.p === null ? '' : r.p < 50 ? 'lo' : r.p < 75 ? 'mid' : '';
      h += '<button type="button" class="hmRow" onclick="gmStart(\'topic\',\'' + r.k + '\')"><span class="hmN">' + esc((GM_CATS[r.k].ico || '') + ' ' + GM_CATS[r.k].name) + '</span><span class="hmTr"><u class="' + cls + '" style="width:' + (r.p === null ? 0 : Math.max(3, r.p)) + '%"></u></span><span class="hmP' + (r.p === null ? ' new' : '') + '">' + (r.p === null ? 'yangi' : r.p + '%') + '</span></button>';
    });
    const w = weakTopic();
    if (w) h += '<div class="hmTip"><b>💡</b><span><strong>Bugun: ' + esc(catName(w.c)) + '</strong>Hozir ' + Math.round(w.p * 100) + '% — shu mavzu ballingizni eng tez oshiradi</span><button type="button" onclick="gmStart(\'topic\',\'' + w.c + '\')">Mashq</button></div>';
    else if (!rows.some(r => r.p !== null)) h += '<p class="muted" style="margin:10px 0 0">Mavzularni ishlashni boshlang — xarita shu yerda paydo bo‘ladi.</p>';
    h += '</div>';
    box.innerHTML = h;
    hubLoad().then(d => { if (d && d !== H._mapRendered) { H._mapRendered = d; renderMap(); } });
  }

  // ------------------------------------------------------------ XATOLAR DAFTARI (intervalli takrorlash)
  function ensureMistakesPage() {
    if ($$('hubMistakes')) return;
    const m = document.createElement('main'); m.id = 'hubMistakes'; m.className = 'page hidden';
    m.innerHTML = '<button class="back" type="button" onclick="openSection(\'mashq\')">‹ Mashq</button><h2>📒 Xatolar daftari</h2><p class="muted" style="margin:0 0 12px">Adashgan savollar 1, 3, 7 va 14 kundan keyin qaytadi. 4 marta to‘g‘ri javob bersangiz — savol o‘zlashtirilgan hisoblanadi.</p><div id="hmBody"></div>';
    const nav = document.querySelector('nav.nav'); if (nav) nav.before(m); else document.body.appendChild(m);
  }
  async function resolveItem(it) {
    const p = it.payload || {};
    if (p.src === 'bank') {
      await gmLoadBank(); const b = GMD.bankById && GMD.bankById[p.id]; if (!b) return null;
      const q = gmFromBank(b, Math.random); q.key = it.key; q.topic = it.topic || p.c || ''; q.payload = { src: 'bank', id: p.id, c: p.c }; return q;
    }
    if (Array.isArray(p.opts) && typeof p.ans === 'number' && p.opts.length > 1) {
      return { key: it.key, kind: 'mc', q: p.q, sentParts: p.sentParts, sentHtml: p.sentHtml, opts: p.opts, ans: p.ans, exp: p.exp || '', topic: it.topic || '', payload: p };
    }
    return null;
  }
  window.hubOpenMistakes = openMistakes;
  async function openMistakes() {
    ensureMistakesPage(); openSection('hubMistakes'); const body = $$('hmBody');
    if (!inTg()) { body.innerHTML = '<div class="hbCard hmEmpty"><b>📲</b><p class="muted">Xatolar daftari faqat Telegram ichida ishlaydi.</p></div>'; return; }
    body.innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    flush(false);
    let d; try { const r = await api('/api/hub/mistakes', { cache: 'no-store' }); d = await r.json(); } catch (e) { d = null; }
    if (!d || !d.ok) { body.innerHTML = '<div class="hbCard hmEmpty"><b>⚠️</b><p class="muted">Yuklanmadi. Internetni tekshirib, qayta urinib ko‘ring.</p></div>'; return; }
    if (H.d) { H.d.mistakes_due = d.due; H.d.mistakes_total = d.total; }
    const qs = []; for (const it of d.items) { try { const q = await resolveItem(it); if (q) qs.push(q); } catch (e) {} }
    if (!qs.length) {
      body.innerHTML = '<div class="hbCard hmEmpty"><b>' + (d.total ? '✅' : '🌱') + '</b><strong>' + (d.total ? 'Bugun takrorlash uchun savol yo‘q' : 'Daftar hozircha bo‘sh') + '</strong><p class="muted">' + (d.total ? 'Daftarda ' + d.total + ' ta savol bor — ular muddati kelganda o‘zi qaytadi.' : 'O‘yin yoki mashqda adashgan savollaringiz shu yerga avtomatik tushadi va kerakli vaqtda qaytadi.') + '</p>'
        + '<button type="button" class="hbGo" onclick="gmStart(\'daily\')">📅 Kunlik 5 savolni ishlash</button></div>';
      return;
    }
    H.S = { qs, i: 0, ok: 0, log: [], total: d.due };
    renderQ();
  }
  function renderQ() {
    const S = H.S, body = $$('hmBody'); if (!S) return; const q = S.qs[S.i];
    const dots = S.qs.map((_, k) => '<i class="' + (S.log[k] === true ? 'on' : S.log[k] === false ? 'bad' : '') + '"></i>').join('');
    let h = '<div class="hmProg"><span class="hmTag">' + esc(catName(q.topic) || 'Savol') + '</span><span>' + (S.i + 1) + ' / ' + S.qs.length + '</span></div><div class="hmDots">' + dots + '</div>'
      + '<div class="gmQ">' + (q.pass ? '<div class="gmPass">' + esc(q.pass).replace(/\n/g, '<br>') + '</div>' : '') + '<div class="gmQt">' + esc(q.q).replace(/\n/g, '<br>') + '</div>'
      + (q.sentParts ? '<div class="gmSent">' + esc(q.sentParts[0]) + '<u class="gmBlank">&nbsp;&nbsp;?&nbsp;&nbsp;</u>' + esc(q.sentParts[1]) + '</div>' : '')
      + (q.sentHtml ? '<div class="gmSent">' + safeHtml(q.sentHtml) + '</div>' : '') + '</div>';
    if (q.kind === 'mc') {
      h += '<div class="gmOpts">' + q.opts.map((o, i) => '<button type="button" class="gmOpt" data-o="' + i + '">' + (q.opts.length > 2 ? '<b class="gmLt">' + 'ABCDEF'[i] + '</b>' : '') + esc(o) + '</button>').join('') + '</div>';
    } else if (q.kind === 'open') {
      h += '<div class="gmOpen"><input id="hmInp" class="gmInp" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Javobingizni yozing"><button type="button" class="primaryAction" id="hmOk">Tekshirish</button></div>';
    } else {
      h += '<div class="gmMopts">' + q.opts.map((o, i) => '<div><b>' + 'ABCDEF'[i] + ')</b> ' + esc(o) + '</div>').join('') + '</div><div class="gmMrows">' + q.rows.map(r => '<div class="gmMrow"><span>' + esc(r) + '</span></div>').join('') + '</div>'
        + '<button type="button" class="primaryAction" id="hmShow">Javobni ko‘rish</button>';
    }
    h += '<div id="hmFb"></div>';
    body.innerHTML = h; window.scrollTo(0, 0);
    body.querySelectorAll('[data-o]').forEach(b => b.onclick = () => answer(+b.getAttribute('data-o') === q.ans, +b.getAttribute('data-o')));
    const ok = $$('hmOk'); if (ok) { ok.onclick = submitOpen; $$('hmInp').onkeydown = e => { if (e.key === 'Enter') submitOpen(); }; }
    const sh = $$('hmShow'); if (sh) sh.onclick = () => selfCheck(q);
  }
  function submitOpen() {
    const q = H.S.qs[H.S.i], inp = $$('hmInp'); if (!inp || !gmNormAns(inp.value)) { if (inp) inp.focus(); return; }
    const ok = (q.accept || []).some(a => gmNormAns(a) === gmNormAns(inp.value));
    inp.disabled = true; inp.classList.add(ok ? 'right' : 'wrong'); $$('hmOk').disabled = true;
    answer(ok, -1, ok ? '' : (q.accept || [])[0]);
  }
  function selfCheck(q) {
    $$('hmShow').remove();
    const rows = q.rows.map((r, i) => esc(r) + ' → ' + 'ABCDEF'[q.ansArr[i]] + ') ' + esc(q.opts[q.ansArr[i]])).join('<br>');
    $$('hmFb').innerHTML = '<div class="gmFb mid"><b>To‘g‘ri moslik:</b><p>' + rows + '</p><p>' + esc(q.exp) + '</p>'
      + '<button type="button" class="primaryAction" id="hmYes">✅ Hammasini bilardim</button><button type="button" class="bpGhost" id="hmNo">❌ Adashdim</button></div>';
    $$('hmYes').onclick = () => finishQ(true); $$('hmNo').onclick = () => finishQ(false);
  }
  function answer(ok, picked, correctText) {
    const S = H.S, q = S.qs[S.i];
    document.querySelectorAll('#hmBody .gmOpt').forEach(b => { b.disabled = true; const i = +b.getAttribute('data-o'); if (i === q.ans) b.classList.add('right'); else if (i === picked) b.classList.add('wrong'); });
    try { tg && tg.HapticFeedback && tg.HapticFeedback.notificationOccurred(ok ? 'success' : 'error'); } catch (e) {}
    $$('hmFb').innerHTML = '<div class="gmFb ' + (ok ? 'ok' : 'bad') + '"><b>' + (ok ? '✅ To‘g‘ri!' : '❌ Noto‘g‘ri') + '</b>' + (correctText ? '<p><b>To‘g‘ri javob:</b> ' + esc(correctText) + '</p>' : '') + '<p>' + esc(q.exp).replace(/\n/g, '<br>') + '</p>'
      + '<p class="muted">' + (ok ? 'Keyingi takror vaqti uzayadi.' : 'Savol ertaga yana qaytadi.') + '</p>' + repHTML(q.key)
      + '<button type="button" class="primaryAction" id="hmNext">' + (S.i + 1 >= S.qs.length ? 'Natijani ko‘rish' : 'Keyingisi →') + '</button></div>';
    S.pending = ok; $$('hmNext').onclick = () => finishQ(ok);
    const fb = $$('hmFb'); if (fb) fb.scrollIntoView({ behavior: 'smooth', block: 'center' });   // pastki navigatsiya tagida qolmasin
  }
  function finishQ(ok) {
    const S = H.S; if (!S) return; const q = S.qs[S.i]; if (!q || S.log[S.i] !== undefined) return;   // ikki marta bosishdan himoya
    S.log[S.i] = ok; if (ok) S.ok++;
    pushQ({ key: q.key, payload: ok ? undefined : q.payload, topic: q.topic, ok });
    S.i++; if (S.i >= S.qs.length) return summary(); renderQ();
  }
  async function summary() {
    const S = H.S, body = $$('hmBody'); flush(false);
    body.innerHTML = '<div class="word">⏳ Natija saqlanmoqda...</div>';
    const pct = S.ok / S.qs.length; const medal = pct >= .9 ? '🏆' : pct >= .6 ? '🥇' : '💪';
    await new Promise(r => setTimeout(r, 450)); await hubLoad(true);
    const left = (H.d && H.d.mistakes_due) || 0;
    body.innerHTML = '<div class="hbCard hmSum"><div class="hmMedal">' + medal + '</div><div class="hmScore">' + S.ok + ' / ' + S.qs.length + '</div>'
      + '<p class="muted">' + (S.ok === S.qs.length ? 'Hammasi to‘g‘ri! Bu savollar endi kamroq qaytadi.' : 'Adashganlaringiz ertaga yana qaytadi — shunda esda qoladi.') + '</p></div>'
      + (left ? '<button type="button" class="hbGo" onclick="hubOpenMistakes()">Yana ' + Math.min(left, 10) + ' ta takrorlash</button>' : '')
      + '<button type="button" class="hbGo ghost" onclick="goHome()">Bosh sahifaga</button>';
    hubDone('mistakes'); H.S = null;
  }

  // ------------------------------------------------------------ KUN QOIDASI va natijani ulashish
  let RULES = null, ruleOff = 0;
  async function loadRules() {
    if (RULES) return RULES;
    try { const r = await fetch('rules.json?v=72'); RULES = await r.json(); } catch (e) { RULES = []; }
    return RULES;
  }
  function renderRule(box) {
    if (!box || !RULES || !RULES.length) return;
    const day = Math.floor((Date.now() + 5 * 3600 * 1000) / 86400000);
    const r = RULES[(day + ruleOff) % RULES.length];
    let el = box.querySelector('.hbRule'); if (!el) { el = document.createElement('div'); el.className = 'hbCard hbRule'; box.appendChild(el); }
    el.innerHTML = '<div class="hmH"><h3>💡 Kun qoidasi</h3><small>' + esc(r.t) + '</small></div><p class="hbRuleT">' + esc(r.r) + '</p>'
      + '<div class="hbRuleB"><button type="button" class="hbGo" data-act="train">✍️ Shu mavzuda mashq</button><button type="button" class="hbGo ghost" data-act="next">Keyingi qoida ›</button></div>';
    el.onclick = ev => {
      const b = ev.target.closest('[data-act]'); if (!b) return;
      if (b.getAttribute('data-act') === 'next') { ruleOff++; renderRule(box); } else if (GM_CATS[r.c]) gmStart('topic', r.c);
    };
  }
  function shareForecast() {
    const f = H.d && H.d.forecast; if (!f || !ME || !ME.ref_link) return;
    const text = '🎯 Milliy sertifikatga tayyorlanyapman! Taxminiy ballim: ' + f.score + '/' + f.max + ' (' + f.level + '). Sen ham sinab ko‘r:';
    const url = 'https://t.me/share/url?url=' + encodeURIComponent(ME.ref_link) + '&text=' + encodeURIComponent(text);
    try { if (tg && tg.openTelegramLink) return tg.openTelegramLink(url); } catch (e) {}
    window.open(url, '_blank');
  }

  // ------------------------------------------------------------ SAVOL SIFATI: «Savolda xato bor» va yashirilgan savollar
  const REASONS = [['xato', 'Javob noto‘g‘ri'], ['matn', 'Matn tushunarsiz'], ['oson', 'Juda oson']];
  function repHTML(key) { return '<div class="hbRep" data-k="' + esc(key) + '"><button type="button" class="hbRepB">⚠️ Savolda xato bor</button></div>'; }
  document.addEventListener('click', ev => {
    const b = ev.target.closest && ev.target.closest('.hbRepB');
    if (b) { b.parentNode.innerHTML = '<span class="hbRepQ">Nima noto‘g‘ri?</span>' + REASONS.map(r => '<button type="button" class="hbRepC" data-r="' + r[0] + '">' + r[1] + '</button>').join(''); return; }
    const c = ev.target.closest && ev.target.closest('.hbRepC');
    if (c) {
      const box = c.closest('.hbRep'), key = box.getAttribute('data-k'), why = c.getAttribute('data-r');
      box.innerHTML = '<span class="hbRepQ">✅ Rahmat! Savolni tekshiramiz.</span>';
      if (inTg()) jpost('/api/hub/report', { key: key, reason: why }).catch(() => {});
    }
  });
  (function watchGameFeedback() {
    const gp = $$('gpBody'); if (!gp) return;
    new MutationObserver(() => {
      try {
        const fb = gp.querySelector('.gmFb'); if (!fb || fb.querySelector('.hbRep')) return;
        if (typeof GM === 'undefined' || !GM || !GM.qs) return; const q = GM.qs[GM.i]; if (!q) return;
        fb.insertAdjacentHTML('beforeend', repHTML(gmQKey(q)));
      } catch (e) {}
    }).observe(gp, { childList: true, subtree: true });
  })();
  // 3 ta foydalanuvchi shikoyat qilgan (yoki admin yashirgan) savollar ro‘yxati — 6 soatda bir marta yangilanadi
  async function syncHidden() {
    if (!inTg()) return;
    if (Date.now() - ((hubLS('hub_hidden', {}) || {}).ts || 0) < 6 * 3600 * 1000) return;
    try { const r = await api('/api/hub/hidden', { cache: 'no-store' }); const d = await r.json(); if (d && d.ok) localStorage.setItem('hub_hidden', JSON.stringify({ ids: d.ids, ts: Date.now() })); } catch (e) {}
  }
  setTimeout(syncHidden, 2500);

  // ------------------------------------------------------------ mavjud funksiyalarga ulanish
  function wrap(name, fn) { const o = window[name]; if (typeof o !== 'function') return; window[name] = function () { const a = arguments; return fn.call(this, o, a); }; }
  wrap('gmMistake', (o, a) => { const r = o.apply(null, a); try { hubTrack(a[0], a[1]); } catch (e) {} return r; });
  wrap('gmFinish', async (o, a) => {
    const g = (typeof GM !== 'undefined') ? GM : null; const r = await o.apply(null, a);
    try { if (g && g.type === 'daily') hubDone('daily'); else if (g && g.type === 'topic') hubDone('topic'); flush(false); H.loadedAt = 0; } catch (e) {}
    return r;
  });
  wrap('openSection', (o, a) => {
    const r = o.apply(null, a);
    try { if (a[0] === 'mashq') { renderMap(); hubLoad(true); } } catch (e) {}
    return r;
  });
  wrap('loadHomeMock', (o, a) => { try { renderHome(); } catch (e) { console.error(e); } return o.apply(null, a); });
  if (document.readyState !== 'loading') { try { renderHome(); } catch (e) {} } else document.addEventListener('DOMContentLoaded', () => { try { renderHome(); } catch (e) {} });
})();
