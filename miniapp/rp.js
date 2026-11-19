/* v133 — Mock va Diagnostik test BIR XIL:
   1) esse tanlovi: qo‘lda kiritish • AI da tekshirish • ekspert tekshiruvi (ixtiyoriy)
   2) premium natija sahifasi (bitta renderer — ikkalasi uchun)
   3) premium ishtirokchilar ro‘yxati: o‘rin, ism, ball, daraja (podium + chiziqli ball)
   app.js dan KEYIN ulanadi, uning funksiyalarini almashtiradi. O‘chirish: index.html dan rp.js / rp.css satrlarini olib tashlang. */
(function () {
  'use strict';
  const esc = s => escapeHtml(String(s == null ? '' : s));
  const lvOf = l => (!l || l === 'Sertifikat berilmadi') ? 'NC' : l;
  const ini = n => esc((String(n || '?').trim()[0] || '?').toUpperCase());
  const SRC = { ai: '🤖', expert: '👨‍🏫', manual: '✏️', expert_wait: '⏳' };
  const pill = l => '<span class="rpLv" style="background:' + mkLvlColor(lvOf(l)) + '">' + esc(lvOf(l)) + '</span>';

  // ---------- 1) premium ishtirokchilar ro‘yxati ----------
  // rows: [{rank,name,score,level,me,src}] — score /75
  window.rpBoard = function (rows, o) {
    o = o || {}; rows = (rows || []).filter(r => r && r.score != null);
    if (!rows.length) return '<div class="word">Hozircha natijalar yo‘q.</div>';
    rows.forEach((r, i) => { if (!r.rank) r.rank = i + 1; });
    const top = rows.slice(0, 3), rest = rows.slice(3), lim = o.limit || 40, med = ['🥇', '🥈', '🥉'];
    const order = top.length === 3 ? [top[1], top[0], top[2]] : top;
    let h = '<div class="rpBoard">';
    h += '<div class="rpPod n' + top.length + '">' + order.map(p => '<div class="rpP p' + p.rank + (p.me ? ' me' : '') + '"><div class="rpMed">' + (med[p.rank - 1] || '') + '</div>'
      + '<div class="rpAv" style="background:' + mkLvlColor(lvOf(p.level)) + '">' + ini(p.name) + '</div><b class="rpNm">' + esc(p.name) + (p.me ? ' <em>siz</em>' : '') + '</b>'
      + '<span class="rpSc">' + esc(p.score) + '<small>/75</small></span>' + pill(p.level) + (p.src && SRC[p.src] ? '<i class="rpSrc">' + SRC[p.src] + '</i>' : '') + '</div>').join('') + '</div>';
    const line = p => '<div class="rpR' + (p.me ? ' me' : '') + '"><span class="rpRk">' + p.rank + '</span><span class="rpAv sm" style="background:' + mkLvlColor(lvOf(p.level)) + '">' + ini(p.name) + '</span>'
      + '<div class="rpMid"><b>' + esc(p.name) + (p.me ? ' <em>siz</em>' : '') + (p.src && SRC[p.src] ? ' <i class="rpSrc">' + SRC[p.src] + '</i>' : '') + '</b>'
      + '<i class="rpBar"><u style="width:' + Math.max(3, Math.min(100, Number(p.score) / 75 * 100)) + '%;background:' + mkLvlColor(lvOf(p.level)) + '"></u></i></div>'
      + '<span class="rpSc2">' + esc(p.score) + '</span>' + pill(p.level) + '</div>';
    if (rest.length) h += '<div class="rpList">' + rest.slice(0, lim).map(line).join('') + '</div>';
    if (rest.length > lim) h += '<p class="muted rpMore">…yana ' + (rest.length - lim) + ' ta ishtirokchi</p>';
    if (o.meRow && !rows.some(r => r.me)) h += '<div class="rpGap">⋯</div><div class="rpList">' + line(o.meRow) + '</div>';
    if (rows.some(r => r.src && SRC[r.src])) h += '<p class="muted rpLeg">🤖 AI • 👨‍🏫 ekspert • ✏️ o‘zi kiritgan esse balli</p>';
    return h + '</div>';
  };

  // ---------- 2) bitta premium natija renderi (Mock ham, Diagnostik ham) ----------
  const MOTIV = { 'A+': '🏆 Ajoyib! Siz eng yuqori darajadasiz. Shu marrani ushlab turing!', 'A': '🌟 Juda yaxshi! A+ ga oz qoldi — zaif mavzularni mustahkamlang.', 'B+': '💪 Yaxshi natija! Endi A darajaga intiling.', 'B': '📈 Yaxshi harakat! B+ ga juda yaqinsiz — davom eting.', 'C+': '🔥 Yo‘l ochiq: tizimli takrorlash bilan B+ ga yetasiz.', 'C': '🚀 Boshlanish yomon emas. Har kuni mashq qiling — natija tez o‘sadi.', 'NC': '🌱 Hozircha chegaradan pastsiz, lekin yaxshilash imkoningiz katta.' };
  window.rpRenderResult = function (x) {
    const r = x.r || {}, cs = r.class_stats || null, h = x.history || [], mock = x.kind === 'mock';
    const fr = (r.fan_report || []).slice().sort((a, b) => a.correct_pct - b.correct_pct);
    const lv = lvOf(r.level), nl = r.next_level, sc = Number(r.combined_score_75) || 0;
    const prev = h.length >= 2 ? h[h.length - 2] : null, delta = prev ? Math.round((sc - Number(prev.score)) * 10) / 10 : null;
    let o = '<button class="back" onclick="' + x.back + '">‹ ' + (mock ? 'Mock' : 'Diagnostik test') + '</button>';
    if (mock && r.no_essay) o += '<div class="result rpWarn">⚠️ <b>Esse balli bo‘lmagani uchun test natijangiz hisoblanmadi.</b> Mock natijasi = test + esse.</div>';
    if (!mock && r.essay_creator_pending) o += '<div class="result rpWarn">👤 <b>Esse balini test kirituvchi qo‘yadi.</b> Ball qo‘yilgach umumiy natija yangilanadi. Hozirgi ball vaqtincha (esse 0 deb hisoblangan).</div>';
    else if (!mock && r.has_essay !== false && r.essay_score == null) o += '<div class="result rpWarn">📝 <b>Esse balli hozircha yo‘q — esse 0 hisoblandi.</b> Esseni AI yoki ekspert orqali tekshirtirsangiz, natija avtomatik yangilanadi.<button class="listbtn" type="button" onclick="rpDiagRefresh(\'' + esc(x.code) + '\')">🔄 Esse tekshirilgan bo‘lsa — natijani yangilash</button></div>';
    o += '<div class="result mkHero"><div class="mkTitle">🎓 ' + esc(x.title || (mock ? 'Mock' : 'Test')) + ' — yakuniy natija</div><div class="scoreBig">' + sc + '<small>/75</small></div>'
      + '<div class="mkChips"><span class="mkLvl" style="background:' + mkLvlColor(lv) + '">' + esc(lv) + '</span>' + (r.place ? '<span>🏅 ' + r.place + '-o‘rin / ' + r.total + '</span>' : '') + (cs ? '<span>Top ' + cs.top_pct + '%</span>' : '')
      + (delta != null ? '<span class="' + (delta >= 0 ? 'mkUp' : 'mkDn') + '">' + (delta >= 0 ? '▲ +' : '▼ ') + delta + ' oldingi mockdan</span>' : '') + '</div>'
      + mkScale({ result: r, bands: x.bands }) + '<p class="muted" style="text-align:center;margin:6px 0 0">' + (nl ? '<b>' + esc(nl.level) + '</b> darajaga yana <b>' + nl.need + '</b> ball kerak (' + nl.at + ' ball)' : (lv === 'A+' ? 'Eng yuqori darajadasiz 🎉' : (sc >= (mock ? 60 : 46) ? '' : '📜 Sertifikat uchun <b>' + (mock ? 'B+' : 'C') + '</b> (' + (mock ? 60 : 46) + ' ball) kerak — yana <b>' + (Math.round(((mock ? 60 : 46) - sc) * 10) / 10) + '</b> ball'))) + '</p></div>';
    o += '<div class="result"><h4 class="rpH">🧪 Ball tarkibi</h4><div class="mkGrid"><div><span>Test</span><b>' + r.score_75 + '/75</b><small>' + r.raw_score + '/' + r.max_score + ' to‘g‘ri</small></div>'
      + (r.has_essay === false ? '' : '<div><span>Esse</span><b>' + (r.essay_score != null ? r.essay_75 + '/75' : '—') + '</b><small>' + (r.essay_score != null ? r.essay_score + '/24' + (r.essay_manual ? ' • ✏️ o‘zi kiritgan' : '') : 'tekshirilmagan') + '</small></div>') + '</div>'
      + '<p class="muted" style="margin:8px 0 0">' + (r.has_essay === false ? 'Umumiy ball = test T-bali (bu fanda esse yo‘q)' : 'Umumiy ball = (test + esse) ÷ 2') + '</p>'
      + (r.essay_manual && mock ? '<p class="muted" style="margin:6px 0 0">✏️ Esse balini o‘zingiz kiritgansiz (tasdiqlanmagan): mock sertifikati faqat AI yoki ekspert tekshirgan esse uchun beriladi.</p>' : '') + '</div>';
    if (cs) {
      const df = Math.round((sc - cs.mean) * 10) / 10;
      o += '<div class="result"><h4 class="rpH">👥 Guruh bilan taqqoslash</h4><div class="mkGrid"><div><span>Sizning ball</span><b>' + sc + '</b></div><div><span>O‘rtacha</span><b>' + cs.mean + '</b></div><div><span>Mediana</span><b>' + cs.median + '</b></div><div><span>Eng yaxshi</span><b>' + cs.best + '</b></div></div>'
        + '<p class="muted" style="margin:8px 0 0">O‘rtachadan <b style="color:' + (df >= 0 ? '#1f8a5b' : '#d9534f') + '">' + (df >= 0 ? '+' : '') + df + '</b> ball. Ishtirokchilarning <b>' + cs.percentile + '%</b> idan yuqori natija ko‘rsatdingiz (' + cs.n + ' ta ishtirokchi).</p></div>';
    }
    o += '<div class="result" style="text-align:center"><b>' + (MOTIV[lv] || '') + '</b></div>';
    const lvls = cs && cs.levels, LVO = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'NC'];
    if (lvls) {
      const mx = Math.max.apply(null, LVO.map(k => lvls[k] || 0).concat([1]));
      o += '<div class="result"><h4 class="rpH">📊 Darajalar bo‘yicha taqsimot</h4>' + LVO.map(k => { const c = lvls[k] || 0, me = (k === lv);
        return '<div class="mkFan"><div class="mkFanH"><b>' + k + (me ? ' ← siz' : '') + '</b><span>' + c + ' ta</span></div><div class="mkBar"><i style="width:' + Math.max(2, Math.round(100 * c / mx)) + '%;background:' + mkLvlColor(k) + ';' + (me ? 'outline:2px solid #e0a000' : '') + '"></i></div></div>'; }).join('') + '</div>';
    }
    const t10 = (r.top10 || []).map(p => ({ rank: p.rank, name: p.name, score: p.final, level: p.level, me: !!p.me }));
    if (t10.length) o += '<div class="result"><h4 class="rpH">🏆 Eng yaxshi natijalar</h4>' + rpBoard(t10, { meRow: r.place ? { rank: r.place, name: 'Siz', score: sc, level: lv, me: true } : null }) + '</div>';
    if (fr.length) {
      o += '<div class="result"><h4 class="rpH">📚 Mavzular bo‘yicha</h4>' + fr.map(f => { const cp = f.class_pct != null ? Math.round(f.class_pct) : null;
        return '<div class="mkFan"><div class="mkFanH"><b>' + esc(f.name) + '</b><span style="color:' + mkPctColor(f.correct_pct) + '">' + f.correct_pct + '%</span></div><div class="mkBar"><i style="width:' + f.correct_pct + '%;background:' + mkPctColor(f.correct_pct) + '"></i>' + (cp != null ? '<u style="left:' + cp + '%"></u>' : '') + '</div>'
          + '<small>' + (f.wrong.length ? 'xato: ' + f.wrong.map(q => '#' + esc(q)).join(', ') : 'xato yo‘q ✅') + (cp != null ? ' • guruh o‘rtachasi ' + cp + '%' : '') + '</small></div>'; }).join('') + '<p class="muted" style="margin:6px 0 0">Oq chiziq — guruh o‘rtachasi. Avval eng pastdan boshlab takrorlang.</p></div>';
    }
    const pr = r.priority || [];
    if (pr.length) o += '<div class="result"><h4 class="rpH">🎯 Avval shularni qayta o‘rganing</h4><p class="muted" style="margin:0 0 6px">Guruh ko‘pchiligi topgan, lekin siz xato qilgan savollar eng muhim.</p>'
      + pr.map(q => '<div class="mkPri"><b>#' + esc(q.item) + '</b><span>' + esc(q.fan || '') + '</span><em>' + (q.class_pct != null ? 'guruhda ' + Math.round(q.class_pct) + '%' : '') + '</em></div>').join('') + '</div>';
    if (mock) o += '<div class="result"><h4 class="rpH">📈 Mocklar dinamikasi</h4>' + mkSpark(h) + '</div>';
    const er = r.errors || [];
    o += '<details class="result mkDet"><summary><b>❌ Xatolar tafsiloti: ' + er.length + '</b></summary>' + er.map(q => '<div class="errorCard"><b>' + q.number + '-savol</b><br>Siz: ' + esc(q.user_text != null ? q.user_text : JSON.stringify(q.user)) + '<br>To‘g‘ri: ' + esc(q.correct_text != null ? q.correct_text : JSON.stringify(q.correct)) + '<br>' + esc(q.explanation || '') + '</div>').join('') + '</details>';
    const wk = fr.filter(f => f.correct_pct < 70).slice(0, 3);
    if (wk.length) o += '<div class="result"><h4 class="rpH">🎯 Keyingi urinishgacha shularni mustahkamlang</h4>' + wk.map(f => '<div class="mkPri"><b>' + esc(f.name) + '</b><span>' + f.correct_pct + '%</span></div>').join('') + '<button class="primaryAction" type="button" style="margin-top:10px" onclick="openSection(\'games\')">🎮 Mashq qilishni boshlash</button></div>';
    if (mock) { if (!r.no_essay && ME && ME.ref_link) o += '<button class="listbtn" type="button" onclick="mockShareResult(' + sc + ',\'' + (lv === 'NC' ? '—' : lv) + '\')">📤 Natijamni do‘stlarga ulashish</button>'; }
    else o += shareCard(x.code, x.title, sc + '/75 (' + lv + ')' + (r.place ? ' — ' + r.place + '-o‘rin' : ''));
    o += ansKeyBox(x.code, mock ? 'mock' : 'nat', x.id);
    o += x.certNote || '';
    $('nationalResult').innerHTML = o; window.scrollTo(0, 0);
  };
  window.renderMockResult = function (d, id) {   // Mock: eski chaqiruv imzosi saqlanadi
    const r = d.result || {}; rpRenderResult({ kind: 'mock', r, title: d.title, code: d.code || r.code, id, history: d.history || [], bands: d.bands || [], back: "openSection('mock')",
      certNote: r.cert_eligible ? '<p class="muted">📜 Sertifikatingiz botdagi chatga yuborilgan.</p>' : '<p class="muted">📜 Mock sertifikati faqat B+, A va A+ darajalar (AI/ekspert tekshirgan esse bilan) uchun beriladi.</p>' });
  };
  window.rpRenderDiag = function (d) {   // Diagnostik test: topshirgan zahoti ham xuddi shunday premium natija
    const r = d.result || {}, lvl = d.level || r.level;
    rpRenderResult({ kind: 'diag', r, title: nationalTest.title, code: nationalTest.code, history: [], bands: d.bands || [], back: "openSection('national')",
      certNote: (d.cert_pending ? '<div class="result"><h4 class="rpH">📜 Sertifikat</h4><p>Sertifikat <b>test yakunlangach</b> (muallif yakunlaganda yoki muddat tugaganda) botdagi chatingizga yuboriladi.</p></div>'
        : (lvl === 'Sertifikat berilmadi' ? '<div class="result"><h4 class="rpH">📜 Sertifikat</h4><p class="muted">Sertifikat uchun kamida 46 ball (C daraja) kerak.</p></div>' : '')) });
    try { $('nationalResult').insertAdjacentHTML('beforeend', resultExtras('ms', nationalTest.code, d)); } catch (e) {}
  };
  window.rpDiagRefresh = async function (code) {
    try {
      const d = await natPost(apiUrl('/api/national/essay-refresh'), { code });
      if (!d.ok) { notify(d.error || 'Yangilab bo‘lmadi.'); return; }
      if (!d.changed) { notify('Esse balli hali topilmadi. AI — 1–2 daqiqa, ekspert — 24 soat ichida.'); return; }
      notify('✅ Esse balli ulandi: ' + d.result.essay_score + '/24');
      rpRenderResult({ kind: 'diag', r: d.result, title: d.result.title, code, history: [], bands: d.bands || [], back: "openSection('national')" });
    } catch (e) { notify('Server band. Birozdan keyin yana urinib ko‘ring.'); }
  };

  // ---------- 3) yagona esse tanlovi (Mock va Diagnostik test) ----------
  const _origChoice = window.showEssayChoice;
  const som = n => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' so‘m';
  window.showEssayChoice = async function () {
    const t = nationalTest || {}, mock = !!t.is_mock, emode = t.essay_mode || 'any';
    if (!mock && (emode === 'creator' || emode === 'manual')) return _origChoice();   // muallif belgilagan maxsus usullar o‘zgarmaydi
    try { const mr = await (await apiFetch(apiUrl('/api/me'), { cache: 'no-store' })).json(); if (mr && mr.ok !== false) ME = Object.assign((typeof ME !== 'undefined' && ME) || {}, mr); } catch (e) {}
    const m = ME || {}, ai = t.ai || {}, ex = t.expert || {}, has = nationalEssayScore !== null, code = esc(t.code);
    $('nationalProgress').innerHTML = '✅ Test javoblari tayyor<div class="bar"><i style="width:100%"></i></div>';
    $('nationalQuestion').innerHTML = '<div class="result" style="margin:0"><b>📝 Esse (45-topshiriq) — ixtiyoriy</b><p class="muted">Mavzu: «' + esc(t.essay_topic || 'ixtiyoriy') + '». Esse ballini o‘zingizga qulay yo‘l bilan hisobga oling. '
      + (mock ? 'Hozir tanlamasangiz ham bo‘ladi: natijalar e‘lon qilinguncha qo‘shish mumkin.' : 'Esse bo‘lmasa, esse 0 ball hisoblanadi (keyin qo‘shsangiz natija yangilanadi).') + '</p></div>';
    let h = '';
    if (has) h += '<button class="primaryAction" type="button" onclick="submitEssayChoice(\'auto\')">✅ ' + (mock ? 'Tekshirilgan' : 'Mavjud') + ' esse bali (' + esc(nationalEssayScore) + '/24) bilan yakunlash</button>';
    // 🤖 AI
    const aiTxt = mock ? (ai.on && !ai.used ? 'Mock ishtirokchilari uchun <b>1 martalik BEPUL</b> tekshiruv (1–2 daqiqa).' : (ai.used ? 'Bepul AI imkoniyatidan foydalanib bo‘lgansiz.' : 'Bepul AI tekshiruvi hozir o‘chirilgan.'))
      : (m.free_essay_total != null ? 'Dastlabki ' + m.free_essay_total + ' ta tekshiruv BEPUL' + (m.free_essay_left != null ? ' (sizda ' + m.free_essay_left + ' ta qoldi)' : '') + ', keyin 1 ta esse — 2 000 so‘m.' : 'Botda esse yuborasiz, AI ball beradi (1–2 daqiqa).');
    const aiOk = !mock || (ai.on && !ai.used);
    h += '<div class="rpOpt"><b>🤖 AI da tekshirish</b><p>' + aiTxt + '</p>' + (aiOk ? '<button class="primaryAction" type="button" onclick="rpOpenAI()">🤖 AI da tekshirish</button>' : '') + '</div>';
    // 👨‍🏫 ekspert
    h += '<div class="rpOpt"><b>👨‍🏫 Ekspert tekshiruvi' + (ex.score == null && !ex.job ? ' — ' + som(ex.uzs || 10000) : '') + '</b>'
      + (ex.score != null ? '<p>✅ Ekspert balli: <b>' + esc(ex.score) + '/24</b></p><button class="primaryAction" type="button" onclick="submitEssayChoice(\'auto\')">Shu ball bilan yakunlash</button>'
        : ex.job ? '<p>Esse ekspertga yuborilgan (#' + esc(ex.job) + '). Ball kelgach natijaga avtomatik qo‘shiladi (24 soat ichida).</p><button class="primaryAction" type="button" onclick="submitEssayChoice(\'' + (mock ? 'auto' : 'none') + '\')">✅ Testni yakunlash</button>'
        : '<p>Haqiqiy ekspert esseni tekshirib, ball beradi (24 soat ichida). To‘lov va esse yuborish botda.</p><button class="primaryAction" type="button" onclick="openMockExpert(nationalTest.code)">👨‍🏫 Ekspertga yuborish</button>') + '</div>';
    // 🔢 qo‘lda
    if (emode !== 'bot') h += '<div class="rpOpt"><b>🔢 Qo‘lda kiritish</b><p>Esse ballini o‘zingiz yozasiz (0–24)' + (mock ? '. ✏️ Tasdiqlanmagan ball sifatida belgilanadi: mock sertifikati faqat AI/ekspert esse uchun beriladi' : '') + '.</p>'
      + '<label class="field"><input id="essayManual" type="number" min="0" max="24" step="0.5" inputmode="decimal" placeholder="Masalan: 17.5"></label><button class="primaryAction" type="button" onclick="submitEssayChoice(\'manual\')">Shu ball bilan hisoblash</button></div>';
    h += '<button class="listbtn" type="button" onclick="refreshMockExpert()">🔄 Esse tekshirilgan bo‘lsa — yangilash</button>';
    if (mock) h += '<button class="listbtn" type="button" onclick="submitEssayChoice(\'auto\')">⏭ Keyinroq qo‘shaman (e‘longacha)</button>';
    else if (emode === 'any') h += '<button class="listbtn" type="button" onclick="submitEssayChoice(\'none\')">⏭ Esse‘siz — esse 0 ball hisoblanadi</button>';
    $('nationalAnswer').innerHTML = h;
    $('btnNext').classList.add('hidden'); $('btnPrev').classList.remove('hidden'); window.scrollTo(0, 0);
  };
  window.rpOpenAI = function () { openMockAI(nationalTest.code); notify('Botda esseni tekshirtiring, so‘ng bu yerga qaytib «Yangilash»ni bosing.'); };

  // Mock: topshirgandan keyin ham qo‘lda ball qo‘shish (AI / ekspert tugmalari yoniga)
  const _smh = window.showMockHidden;
  window.showMockHidden = function (d, title) {
    _smh(d, title);
    try {
      if (d && d.need_essay && d.essay_score == null) {
        const box = document.querySelector('#nationalResult .result'), code = String(d.code || (nationalTest && nationalTest.code) || '');
        if (box) box.insertAdjacentHTML('beforeend', '<div class="rpOpt"><b>🔢 Qo‘lda kiritish</b><p>Esse ballini o‘zingiz yozing (0–24). ✏️ Tasdiqlanmagan ball: mock sertifikati faqat AI/ekspert esse uchun beriladi.</p>'
          + '<label class="field"><input id="rpMkManual" type="number" min="0" max="24" step="0.5" inputmode="decimal" placeholder="Masalan: 17.5"></label><button class="primaryAction" type="button" onclick="rpMockManual(\'' + esc(code) + '\')">Ballni qo‘shish</button></div>');
      }
    } catch (e) { console.error(e); }
  };
  window.rpMockManual = async function (code) {
    const v = parseFloat(String(($('rpMkManual') || {}).value || '').replace(',', '.'));
    if (!isFinite(v) || v < 0 || v > 24) { notify('Esse balli 0 dan 24 gacha bo‘lishi kerak.'); return; }
    try { const d = await natPost(apiUrl('/api/mock/essay-manual'), { code, score: v }); if (!d.ok) { notify(d.error || 'Xatolik'); return; } notify('✅ Esse balli qo‘shildi: ' + v + '/24'); showMockHidden(d, d.title); }
    catch (e) { notify('Server band. Birozdan keyin yana urinib ko‘ring.'); }
  };

  // ---------- 4) premium ro‘yxatlar (muallif / admin) ----------
  window.openResults = async function (kind, code) {   // Diagnostik test: «Kim ishladi»
    resCtx = { kind, code }; openSection('testResults');
    const box = $('trBody'); box.innerHTML = '<div class="word">⏳ Yuklanmoqda...</div>';
    try {
      const d = await (await apiFetch(apiUrl('/api/test/results?kind=' + encodeURIComponent(kind) + '&code=' + encodeURIComponent(code)), { cache: 'no-store' })).json();
      if (!d.ok) { box.innerHTML = '<div class="result">❌ ' + esc(d.error || 'Xatolik') + '</div>'; return; }
      const ps = d.participants || [], users = new Set(ps.map(p => p.username || p.name)).size;
      const state = d.closed ? ('🏁 Yakunlangan' + (d.finished_at ? ' • ' + fmtDT(d.finished_at) : '')) : (d.closes_at ? ('⏳ Davom etmoqda • tugash: ' + fmtDT(d.closes_at)) : '♾ Davom etmoqda (muddatsiz)');
      const val = p => (p.combined != null && p.combined !== '' ? Number(p.combined) : (isFinite(Number(p.score)) ? Number(p.score) : null));
      const first = new Map(); ps.forEach(p => { const k = p.user_id || p.name; if (!first.has(k)) first.set(k, p); });
      const rows = Array.from(first.values()).map(p => ({ name: p.name || '—', score: val(p) != null ? Math.round(val(p) * 10) / 10 : null, level: p.level || 'NC', pct: p.percent })).filter(r => r.score != null)
        .sort((a, b) => b.score - a.score).map((r, i) => Object.assign(r, { rank: i + 1 }));
      const avg = rows.length ? Math.round(rows.reduce((s, r) => s + r.score, 0) / rows.length * 10) / 10 : 0;
      const dist = {}; rows.forEach(r => { const k = lvOf(r.level); dist[k] = (dist[k] || 0) + 1; });
      box.innerHTML = '<div class="result"><b>📝 ' + esc(d.title) + '</b><p class="muted">Kod: ' + esc(d.code) + '<br>' + esc(state) + '</p>'
        + '<div class="pStats"><div><b>' + users + '</b><small>ishtirokchi</small></div><div><b>' + ps.length + '</b><small>urinish</small></div><div><b>' + avg + '</b><small>o‘rtacha /75</small></div></div>'
        + '<div class="rpDist">' + ['A+', 'A', 'B+', 'B', 'C+', 'C', 'NC'].filter(k => dist[k]).map(k => '<span style="background:' + mkLvlColor(k) + '">' + k + ' · ' + dist[k] + '</span>').join('') + '</div>'
        + '<button class="primaryAction" type="button" onclick="sendResultsFile()">📄 Natijalar faylini olish (Excel)</button>'
        + (d.closed ? '' : '<button class="primaryAction" style="background:linear-gradient(135deg,#b3412f,#8e2c1d)" type="button" onclick="finishTest()">🏁 Testni yakunlash</button>') + '</div>'
        + '<h3 class="rpH2">🏆 Ishtirokchilar ro‘yxati</h3>' + (rows.length ? rpBoard(rows, { limit: 60 }) : '<div class="word">Hozircha hech kim ishlamagan.</div>')
        + (ps.length ? '<details class="result mkDet"><summary><b>❌ Xatolar tafsiloti (' + ps.length + ' ta urinish)</b></summary>' + ps.map((p, i) => '<div class="errorCard"><b>' + (i + 1) + '. ' + esc(p.name || '—') + '</b> ' + (p.username ? '<span class="muted">' + esc(p.username) + '</span>' : '')
          + '<br>Natija: <b>' + esc(val(p) != null ? val(p) : p.score) + '</b> (' + p.percent + '%)' + (p.level ? ' • ' + esc(p.level) : '') + '<br>❌ Xatolar: ' + (p.errors && p.errors.length ? esc(p.errors.join(', ')) : 'yo‘q 🎉') + '<br><span class="muted">' + p.attempt + '-urinish • ' + esc(p.at) + '</span></div>').join('') + '</details>' : '');
    } catch (e) { box.innerHTML = '<div class="result">❌ Yuklashda xatolik.</div>'; }
  };
  const _omr = window.openMockResults;   // Mock (admin): to‘liq ishtirokchilar ro‘yxati sahifa tepasiga qo‘shiladi
  window.openMockResults = async function (id) {
    await _omr(id);
    try {
      const d = window._rpMock || await (await apiFetch(apiUrl('/api/mock/results?id=' + encodeURIComponent(id)), { cache: 'no-store' })).json();
      const a = d && d.analytics, ppl = (a && a.people) || [], es = {}; (d.essays || []).forEach(e => { es[e.user_id] = e.essay_status; });
      if (!ppl.length) return;
      const rows = ppl.map(p => ({ rank: p.rank, name: p.name, score: p.final, level: p.level, src: es[p.user_id] })).filter(r => r.score != null);
      const sec = '<div class="result rpAdm"><h4 class="rpH">🏆 Ishtirokchilar ro‘yxati • ' + rows.length + ' ta</h4>' + rpBoard(rows, { limit: 80 }) + '</div>';
      const box = $('tsBody'), anchor = box && box.querySelector('.pStats');
      if (anchor && anchor.parentElement) anchor.parentElement.insertAdjacentHTML('afterend', sec); else if (box) box.insertAdjacentHTML('afterbegin', sec);
    } catch (e) { console.error(e); }
  };
  window.renderMockEssays = function (d) {   // admin: esse holati (qo‘lda ball ham ko‘rinadi)
    const rows = d.essays || [], c = d.essay_counts || {};
    const st = { ai: '🤖 AI', expert: '👨‍🏫 Ekspert', manual: '✏️ Qo‘lda', expert_wait: '⏳ Ekspert kutilmoqda', none: '— yo‘q' }, f = v => (v == null ? '—' : v);
    const tr = rows.map(r => '<tr><td>' + esc(r.name) + '</td><td>' + (r.submitted ? f(r.test75) : '<small>topshirmagan</small>') + '</td><td>' + (r.essay24 == null ? '—' : r.essay24 + '<small>/24</small>') + '</td><td>' + (st[r.essay_status] || '') + '</td><td>' + (!r.submitted ? '—' : (r.essay24 == null ? '<small>esse yo‘q — hisoblanmaydi</small>' : '<b>' + f(r.final) + (r.provisional ? '<small>*</small>' : '') + '</b>')) + '</td></tr>').join('');
    return '<details class="result" style="margin:0 0 10px"><summary style="cursor:pointer"><b>📝 Esse holati</b> • ' + ((c.ai || 0) + (c.expert || 0) + (c.manual || 0)) + ' tekshirilgan • ' + (c.expert_wait || 0) + ' ekspert kutmoqda • ' + (c.none || 0) + ' esse yo‘q</summary>'
      + '<p class="muted" style="margin:8px 0">🤖 AI: <b>' + (c.ai || 0) + '</b> • 👨‍🏫 Ekspert: <b>' + (c.expert || 0) + '</b> • ✏️ Qo‘lda: <b>' + (c.manual || 0) + '</b> • Ro‘yxatdan o‘tgan: <b>' + (c.registered || 0) + '</b> • Topshirgan: <b>' + (c.submitted || 0) + '</b></p>'
      + '<div style="overflow-x:auto"><table class="mkEsT"><thead><tr><th>Ism</th><th>Test /75</th><th>Esse</th><th>Kim tekshirdi</th><th>Umumiy /75</th></tr></thead><tbody>' + tr + '</tbody></table></div>'
      + '<p class="muted" style="margin:6px 0 0;font-size:11.5px">* Esse hali testga bog‘lanmagan — umumiy ball taxminiy; e‘londa yakuniy hisoblanadi.</p></details>';
  };
})();
