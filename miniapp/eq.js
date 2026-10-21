/* eq.js — «Tushgan savollar» bo'limi (v97). Admin tahrirlaydi (matn, A-D variantlar, TO'G'RI javob, izoh) -> nashr -> hammaga ko'rinadi.
   Foydalanuvchilar anonim ("1-foydalanuvchi"). Test: variantni belgilash. Ulashish: teaser + bot manzili (savol matni emas). */
(function () {
  const tg = window.Telegram && Telegram.WebApp;
  const L4 = ['A', 'B', 'C', 'D'];
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const $q = id => document.getElementById(id);
  const api = (p, o) => apiFetch(apiUrl(p), Object.assign({ cache: 'no-store' }, o || {})).then(r => r.json());
  const post = (p, b) => api(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) });
  let D = null, RAW = null, tab = 'pub', focusId = null;
  const MAP = {};

  const slotOptions = sel => '<option value="">Boshqa</option>' + ((D && D.slots) || []).map(s => `<option value="${s.code}"${s.code === sel ? ' selected' : ''}>${esc(s.label)}</option>`).join('');
  const MODE = { all: 'hammaga ochiq', contrib: 'hissa qo‘shuvchilarga', closed: 'yopiq' };

  window.eqShare = function (id) {
    if (!D || !D.bot) return notify('Bot manzili topilmadi.');
    const link = `https://t.me/${D.bot}?start=q_${id}`;
    const u = 'https://t.me/share/url?url=' + encodeURIComponent(link) + '&text=' + encodeURIComponent(D.share_text || 'Imtihonda tushgan savol! Bot orqali sinab ko‘ring 👇');
    if (tg && tg.openTelegramLink) tg.openTelegramLink(u); else window.open(u, '_blank');
  };

  function answerHtml(it) {
    if (it.answer === null || it.answer === undefined) {
      return it.lock === 'contrib'
        ? '<span class="eqLock">🔑 Javob hissa qo‘shuvchilarga birinchi ochiladi — botda <b>/savollar</b> orqali savollaringizni kiriting</span>'
        : '<span class="eqLock">🔒 Admin ochganda ko‘rinadi</span>';
    }
    const i = L4.indexOf(String(it.answer).toUpperCase());
    let h = i >= 0 && it.opts && it.opts[i] ? `<b>${L4[i]}) ${esc(it.opts[i])}</b>` : `<b>${esc(it.answer || '—')}</b>`;
    if (it.explain) h += `<div class="eqEx">💡 ${esc(it.explain)}</div>`;
    if (D.is_admin && it.mode !== 'all') h += ` <span class="eqLock">(hamma uchun: ${MODE[it.mode] || 'yopiq'})</span>`;
    return h;
  }

  function optsHtml(it, vote) {
    const has = it.opts && it.opts.some(x => x);
    if (!has) return '';
    return '<div class="eqOpts">' + L4.map((L, i) => it.opts[i] ? `<div class="eqOpt${vote && it.my_vote === L ? ' mine' : ''}">${L}) ${esc(it.opts[i])}</div>` : '').join('') + '</div>';
  }

  function voteBar(it) {
    if (!it.opts || !it.opts.some(x => x)) return '';
    const btns = L4.map((L, i) => it.opts[i] ? `<button type="button" class="eqV${it.my_vote === L ? ' on' : ''}" onclick="eqVote(${it.id},'${L}')">${L}</button>` : '').join('');
    return `<div class="eqVote"><span>Sizningcha javob:</span>${btns}</div>`;
  }

  function card(it, mode) {
    const key = mode + ':' + (it.id || (it.src_user + '_' + it.src_qno));
    MAP[key] = it;
    const adm = D.is_admin;
    const badge = mode === 'raw' ? `<span class="eqBadge ${it.status}">${it.status === 'published' ? 'nashr qilingan' : it.status === 'draft' ? 'qoralama' : 'yangi'}${it.src_qno ? ' • ' + it.src_qno + '-savol' : ''}</span>` : '';
    const hint = mode === 'raw' ? `<div class="eqHint">👁 Faqat admin: ${esc(it.real_name || '—')} • belgilagan javobi: <b>${esc(it.user_pick || '—')}</b> (taxmin, to‘g‘ri javob emas)</div>` : '';
    const btns = [];
    if (mode === 'pub' && D.bot) btns.push(`<button type="button" class="eqBtn" onclick="eqShare(${it.id})">📤 Ulashish</button>`);
    if (adm) btns.push(`<button type="button" class="eqBtn" onclick="eqEdit('${key}')">✏️ Tahrirlash</button>`);
    if (adm && it.id && mode !== 'raw') btns.push(`<button type="button" class="eqBtn red" onclick="eqDel(${it.id})">🗑</button>`);
    const showVote = mode === 'pub' && !adm;
    return `<article class="eqCard" id="eq-${it.id || ''}">${badge}${hint}
      <div class="eqRow"><span>👤 Foydalanuvchi:</span> <b>${esc(mode === 'raw' ? (it.name || 'avto: N-foydalanuvchi') : it.name)}</b></div>
      <div class="eqQ"><span>❓ Tushgan savol:</span><div class="eqTxt">${esc(it.question)}</div>${optsHtml(it, showVote)}</div>
      ${showVote ? voteBar(it) : ''}
      ${mode === 'raw' ? `<div class="eqA">✅ To‘g‘ri javob: ${it.answer ? '<b>' + esc(it.answer) + '</b>' : '<span class="eqLock">hali kiritilmagan</span>'}</div>` : `<div class="eqA">✅ Javob: ${answerHtml(it)}</div>`}
      ${btns.length ? `<div class="eqBtns">${btns.join('')}</div>` : ''}</article>`;
  }

  function groups(gs, mode, empty) {
    if (!gs || !gs.length) return `<div class="word">${empty}</div>`;
    return gs.map(g => `<h3 class="eqH">📅 ${esc(g.label)} <small>${g.items.length} ta</small></h3>` + g.items.map(it => card(it, mode)).join('')).join('');
  }

  function adminBar() {
    const opts = '<option value="all">Hammasi</option>' + (D.slots || []).map(s => `<option value="${s.code}">${esc(s.label)} — ${MODE[s.mode] || 'yopiq'}</option>`).join('');
    return `<div class="eqAdm">
      <div class="eqSt">Bo‘lim: <b>${D.public ? 'hammaga ochiq ✅' : 'faqat admin (jarayonda) 🔒'}</b>
        <button type="button" class="eqBtn" onclick="eqPublic(${D.public ? 'false' : 'true'})">${D.public ? '🔒 Yopish' : '🔓 Hammaga ochish'}</button></div>
      <div class="eqSt">Javoblar: <select id="eqAnsSel">${opts}</select>
        <button type="button" class="eqBtn" onclick="eqAns('contrib')">🔑 Hissa qo‘shuvchilarga</button>
        <button type="button" class="eqBtn" onclick="eqAns('all')">🔓 Hammaga</button>
        <button type="button" class="eqBtn" onclick="eqAns('closed')">🔒 Yopish</button></div>
      <div class="eqTabs">${[['pub', 'Nashr qilingan'], ['draft', 'Qoralama'], ['raw', 'Kelgan savollar'], ['new', '＋ Yangi']].map(t => `<button type="button" class="${tab === t[0] ? 'on' : ''}" onclick="eqTab('${t[0]}')">${t[1]}</button>`).join('')}</div></div>`;
  }

  function contribNote() {
    if (D.is_admin || !D.public) return '';
    return D.contributor
      ? '<div class="eqNote ok">🔑 Siz <b>hissa qo‘shuvchi</b>siz: javoblar ochilganda birinchilar qatorida ko‘rasiz.</div>'
      : `<div class="eqNote">💡 Imtihondan keyin botda <b>/savollar</b> orqali kamida ${D.q_min} ta savolni kiriting — to‘g‘ri javoblarni <b>boshqalardan oldin</b> ko‘rasiz.</div>`;
  }

  function render() {
    const box = $q('eqBox'); if (!box) return;
    if (!D || !D.ok) { box.innerHTML = '<div class="word">Yuklab bo‘lmadi. Telegram orqali oching.</div>'; return; }
    let h = '';
    if (D.is_admin) h += adminBar();
    if (!D.public && !D.is_admin) {
      h = '<div class="eqSoon"><div class="eqSoonI">🛠</div><b>Tushgan savollar tayyorlanmoqda</b><p>Imtihonda kelgan savollarni admin tekshirib, tartibga solmoqda. Tayyor bo‘lgach shu yerda ochiladi.</p></div>';
    } else if (!D.is_admin || tab === 'pub') {
      h += contribNote() + groups(D.groups, 'pub', 'Hozircha nashr qilingan savollar yo‘q.');
    } else if (tab === 'draft') {
      h += groups(D.drafts, 'pub', 'Qoralamalar yo‘q.');
    } else if (tab === 'raw') {
      h += RAW ? groups(RAW.groups, 'raw', 'Foydalanuvchilardan savol hali kelmagan.') : '<div class="word">⏳ Yuklanmoqda…</div>';
    } else if (tab === 'new') {
      h += '<div class="word">Yangi savolni qo‘lda qo‘shish:</div><button type="button" class="eqBtn big" onclick="eqEdit(\'new\')">＋ Yangi savol</button>';
    }
    box.innerHTML = h;
    if (!D.is_admin) { box.oncopy = e => e.preventDefault(); box.oncontextmenu = e => e.preventDefault(); box.classList.add('eqNoCopy'); }
    if (focusId) { const el = $q('eq-' + focusId); if (el) { el.scrollIntoView({ block: 'center' }); el.classList.add('eqFocus'); } focusId = null; }
  }

  window.loadEq = async function () {
    const box = $q('eqBox'); if (box && !D) box.innerHTML = '<div class="word">⏳ Yuklanmoqda…</div>';
    try { D = await api('/api/eq/list'); if (D.ok && D.is_admin && tab === 'raw') RAW = await api('/api/eq/raw'); } catch (e) { D = { ok: false }; }
    render();
  };
  window.eqTab = async function (t) {
    tab = t;
    if (t === 'raw') { RAW = null; render(); try { RAW = await api('/api/eq/raw'); } catch (e) { RAW = { groups: [] }; } }
    render();
  };
  window.eqPublic = async function (on) { const r = await post('/api/eq/settings', { public: on }); if (!r.ok) return notify(r.error || 'Xatolik'); loadEq(); };
  window.eqAns = async function (mode) {
    const slot = ($q('eqAnsSel') || {}).value || 'all';
    const r = await post('/api/eq/settings', { answers: { slot, mode } });
    if (!r.ok) return notify(r.error || 'Xatolik');
    notify(mode === 'closed' ? '🔒 Javoblar yopildi' : mode === 'contrib' ? '🔑 Javoblar hissa qo‘shuvchilarga ochildi (xabar yuborish uchun botda /javob_och buyrug‘ini ishlating)' : '🔓 Javoblar hammaga ochildi (xabar yuborish uchun botda /javob_och buyrug‘ini ishlating)');
    loadEq();
  };
  window.eqDel = async function (id) { if (!confirm('Bu savol o‘chirilsinmi?')) return; const r = await post('/api/eq/delete', { id }); if (!r.ok) return notify(r.error || 'Xatolik'); loadEq(); };

  window.eqVote = async function (id, letter) {
    const r = await post('/api/eq/vote', { id, letter });
    if (!r.ok) return notify(r.error || 'Xatolik');
    if (r.visible) notify(r.is_right ? '✅ To‘g‘ri!' : '❌ Noto‘g‘ri. To‘g‘ri javob: ' + (r.correct || '—'));
    else notify(r.lock === 'contrib' ? '✅ Qabul qilindi. To‘g‘ri javob hissa qo‘shuvchilarga birinchi ochiladi.' : '✅ Javobingiz qabul qilindi. To‘g‘ri javob ochilganda xabar beramiz.');
    loadEq();
  };

  window.eqEdit = function (key) {
    const it = key === 'new' ? { id: null, slot: '', name: '', question: '', opts: ['', '', '', ''], answer: '', explain: '' } : MAP[key];
    if (!it) return;
    const old = $q('eqModal'); if (old) old.remove();
    const o = (it.opts || ['', '', '', '']);
    const m = document.createElement('div'); m.id = 'eqModal'; m.className = 'eqModal';
    m.innerHTML = `<div class="eqSheet"><h3>${it.id || it.src_user ? '✏️ Savolni tahrirlash' : '＋ Yangi savol'}</h3>
      ${it.user_pick || it.real_name ? `<div class="eqHint">👁 Faqat admin: ${esc(it.real_name || '—')} • foydalanuvchi belgilagan: <b>${esc(it.user_pick || '—')}</b> (taxmin)</div>` : ''}
      ${it.raw_question ? `<details class="eqRawD"><summary>Foydalanuvchi yozgan asl matn</summary><div class="eqTxt">${esc(it.raw_question)}</div></details>` : ''}
      <label>Smena</label><select id="eqfSlot">${slotOptions(it.slot)}</select>
      <label>Foydalanuvchi nomi — bo‘sh qoldirsangiz avtomatik «N-foydalanuvchi» bo‘ladi</label><input id="eqfName" maxlength="40" value="${esc(it.name)}" placeholder="N-foydalanuvchi (avto)">
      <label>Tushgan savol (matn)</label><textarea id="eqfQ" rows="5">${esc(it.question)}</textarea>
      <label>Variantlar (bo‘sh qoldirish mumkin)</label>
      ${L4.map((L, i) => `<div class="eqOptIn"><b>${L}</b><input id="eqfO${i}" maxlength="200" value="${esc(o[i] || '')}"></div>`).join('')}
      <label>✅ TO‘G‘RI javob (A/B/C/D yoki matn) — hammaga ko‘rinadi, admin buyrug‘i bilan</label><input id="eqfA" maxlength="300" value="${esc(it.answer || '')}">
      <label>💡 Izoh (ixtiyoriy)</label><input id="eqfE" maxlength="500" value="${esc(it.explain || '')}">
      <div class="eqBtns"><button type="button" class="eqBtn big" id="eqfPub">✅ Saqlash va nashr qilish</button><button type="button" class="eqBtn" id="eqfDraft">💾 Qoralama</button><button type="button" class="eqBtn" id="eqfX">Bekor</button></div></div>`;
    document.body.appendChild(m);
    const save = async publish => {
      const body = { id: it.pub_id || it.id || null, src_user: it.src_user || null, src_qno: it.src_qno || null,
        slot: $q('eqfSlot').value, name: $q('eqfName').value, question: $q('eqfQ').value,
        opts: [0, 1, 2, 3].map(i => $q('eqfO' + i).value), answer: $q('eqfA').value, explain: $q('eqfE').value, publish };
      const r = await post('/api/eq/save', body);
      if (!r.ok) return notify(r.error || 'Xatolik');
      m.remove(); notify(publish ? '✅ Nashr qilindi — bo‘limga tushdi (' + r.name + ')' : '💾 Qoralama saqlandi');
      if (tab === 'raw') RAW = await api('/api/eq/raw'); loadEq();
    };
    $q('eqfPub').onclick = () => save(true); $q('eqfDraft').onclick = () => save(false); $q('eqfX').onclick = () => m.remove();
  };

  try {
    const p = new URLSearchParams(location.search).get('eq');
    if (p) { focusId = /^\d+$/.test(p) ? p : null; setTimeout(() => { if (typeof openSection === 'function') openSection('eq'); }, 700); }
  } catch (e) {}
})();
