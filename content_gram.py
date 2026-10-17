"""v72: «Mashq → Grammatika» va o'yinlar banki uchun original savollar (milliy sertifikat namunaviy testi formatida).
Hamma savol muallif tomonidan yangidan tuzilgan; namunaviy testdan ko'chirilmagan.
mc(c, savol, TO'G'RI, xato1, xato2, xato3, e=izoh) — birinchi variant to'g'ri javob (aralashtirish keyin qilinadi)."""


def mc(c, q, right, *wrong, e='', p=None, fix=False):
    d = {'k': 'mc', 'c': c, 'q': q, 'o': [right] + list(wrong), 'e': e}
    if p: d['p'] = p
    if fix: d['fix'] = True
    return d


def op(c, q, ans, e='', p=None):
    d = {'k': 'open', 'c': c, 'q': q, 'ans': list(ans), 'e': e}
    if p: d['p'] = p
    return d


def mt(c, q, rows, opts, ans, e=''):
    return {'k': 'match', 'c': c, 'q': q, 'r': rows, 'o': opts, 'a': ans, 'e': e}


TOPICS = [
    # ------------------------------------------------------------------ IMLO
    {'sec': 'mgram', 'title': 'Imlo: to‘g‘ri yozilgan so‘zlar qatori',
     'rules': 'Tutuq belgisi (’) ba’zi so‘zlarda unlini ajratadi: ma’no, san’at, she’r, a’zo, mas’ul, qat’iy. «Tabiat» so‘zida tutuq belgisi yozilmaydi.\n'
              'o‘ va g‘ harflari (‘) belgisi bilan yoziladi: o‘zbek, g‘oya, to‘g‘ri, qo‘ng‘iroq.\n'
              'Qo‘sh undosh saqlanadi: tasavvur, muassasa, taassurot, mutaxassis.\n'
              'H va X ni adashtirmang: xulosa, xayol, xizmat, xalq; hikoya, hayot, hozir, hukm.\n'
              'Q va K: qimmat, taqdir, qat’iy; kitob, kuch.',
     'examples': 'Juft so‘zlar defis bilan yoziladi: ota-ona, kecha-kunduz, oq-qora.\nYaxlit yoziladigan qo‘shma so‘zlar: ko‘zoynak, o‘rinbosar, mehnatsevar.',
     'items': [
         mc('imlo', 'Imloviy jihatdan to‘g‘ri yozilgan so‘zlar qatorini aniqlang.',
            'tasavvur, muassasa, mas’ul', 'tasavur, muassasa, mas’ul', 'tasavvur, muasasa, mas’ul', 'tasavvur, muassasa, masul',
            e='To‘g‘ri yozilishi: tasavvur (qo‘sh v), muassasa (qo‘sh s), mas’ul (tutuq belgisi).'),
         mc('imlo', 'Imloviy jihatdan to‘g‘ri yozilgan so‘zlar qatorini aniqlang.',
            'xulosa, hikoya, hayot', 'hulosa, hikoya, hayot', 'xulosa, xikoya, hayot', 'xulosa, hikoya, xayot',
            e='xulosa (x bilan), hikoya (h bilan), hayot (h bilan) yoziladi.'),
         mc('imlo', 'Imloviy jihatdan to‘g‘ri yozilgan so‘zlar qatorini aniqlang.',
            'mutaxassis, taassurot, muassasa', 'mutahassis, taassurot, muassasa', 'mutaxassis, tasurot, muassasa', 'mutaxassis, taassurot, muasasa',
            e='mutaxassis (x), taassurot (qo‘sh a) va muassasa (qo‘sh s) to‘g‘ri yoziladi.'),
         mc('imlo', 'Imloviy jihatdan to‘g‘ri yozilgan so‘zlar qatorini aniqlang.',
            'qat’iy, taqdir, qimmatli', 'kat’iy, taqdir, qimmatli', 'qat’iy, takdir, qimmatli', 'qat’iy, taqdir, kimmatli',
            e='Q harfi bilan: qat’iy, taqdir, qimmatli.'),
         mc('imlo', 'Qaysi qatordagi barcha so‘zlar to‘g‘ri yozilgan?',
            'ota-ona, kecha-kunduz, oq-qora', 'ota ona, kecha-kunduz, oq-qora', 'ota-ona, kechakunduz, oq-qora', 'ota-ona, kecha-kunduz, oqqora',
            e='Juft so‘zlar defis bilan yoziladi.'),
         mc('imlo', 'Qaysi qatordagi barcha so‘zlar to‘g‘ri yozilgan?',
            'ko‘zoynak, o‘rinbosar, mehnatsevar', 'ko‘z oynak, o‘rinbosar, mehnatsevar', 'ko‘zoynak, o‘rin-bosar, mehnatsevar', 'ko‘zoynak, o‘rinbosar, mehnat sevar',
            e='Bular yaxlit yoziladigan qo‘shma so‘zlar.'),
         mc('imlo', 'Qaysi so‘zda imlo xatosi bor?',
            'qongiroq', 'mo‘jiza', 'o‘rgatmoq', 'g‘aznachi',
            e='To‘g‘ri yozilishi: qo‘ng‘iroq (o‘ va g‘ harflari belgisi bilan).'),
         mc('imlo', 'Qaysi so‘zda tutuq belgisi noto‘g‘ri qo‘llangan?',
            'tabi’at', 'ma’no', 'she’r', 'san’at',
            e='To‘g‘ri yozilishi: tabiat. Tutuq belgisi bu so‘zda yozilmaydi.'),
     ]},
    # ------------------------------------------------------------------ PUNKTUATSIYA
    {'sec': 'mgram', 'title': 'Punktuatsiya: tire, ikki nuqta, vergul',
     'rules': 'Tire: ega va kesim ot (yoki son) bilan ifodalansa, ular orasiga qo‘yiladi: «Samarqand — Sharqning gavhari.»\n'
              'Uyushiq bo‘laklardan keyin umumlashtiruvchi so‘z kelsa, oldiga tire qo‘yiladi: «Olma, nok, uzum — hammasi shirin meva.»\n'
              'Umumlashtiruvchi so‘z oldin kelsa, undan keyin ikki nuqta qo‘yiladi: «Sumkamda kerakli narsalar bor: daftar, qalam, kitob.»\n'
              'Uyushiq bo‘laklar orasida vergul qo‘yiladi, lekin «va» bog‘lovchisi oldidan qo‘yilmaydi.\n'
              'Undalma gapdan vergul bilan ajratiladi.',
     'examples': 'Navoiy — buyuk shoir.\nAziza, bu yerga kel.\nOlma, nok va uzum pishdi.',
     'items': [
         mc('punk', 'Qaysi gaplarda tire o‘zaro bir xil punktuatsion qoida asosida qo‘yilgan?\n'
            '1) Navoiy — mumtoz adabiyotimizning buyuk namoyandasi.\n2) Daryolar, ko‘llar, dengizlar — barchasi suv havzalaridir.\n'
            '3) — Bugun uyda qolaman, — dedi Aziza.\n4) Samarqand — Sharqning gavhari.\n5) Olma, nok, uzum — hammasi shirin meva.',
            '1 va 4', '2 va 3', '3 va 5', '1 va 2',
            e='1 va 4-gapda tire ega va kesim ot bilan ifodalangani uchun, 2 va 5-gapda umumlashtiruvchi so‘z oldidan, 3-gapda ko‘chirma gap uchun qo‘yilgan.'),
         mc('punk', 'Qaysi gapda vergul noto‘g‘ri qo‘llangan?',
            'Olma, nok, va uzum pishib yetildi.', 'Olma, nok va uzum pishib yetildi.', 'Aziza, sen qayerdan kelyapsan?', 'Yomg‘ir yog‘di, lekin biz sayrga chiqdik.',
            e='Uyushiq bo‘laklar orasidagi «va» bog‘lovchisi oldidan vergul qo‘yilmaydi.'),
         mc('punk', 'Qaysi gapda ikki nuqta to‘g‘ri qo‘yilgan?',
            'Sumkamda kerakli narsalar bor: daftar, qalam, kitob.', 'Sumkamda: kerakli narsalar bor daftar, qalam, kitob.',
            'Sumkamda kerakli narsalar: bor daftar, qalam, kitob.', 'Sumkamda kerakli narsalar bor, daftar: qalam, kitob.',
            e='Umumlashtiruvchi so‘z (narsalar) uyushiq bo‘laklardan oldin kelganda, undan keyin ikki nuqta qo‘yiladi.'),
         mc('punk', 'Qaysi gapda tinish belgisi to‘g‘ri qo‘yilgan?',
            'Ustoz, savolimga javob bering.', 'Ustoz savolimga, javob bering.', 'Ustoz savolimga javob, bering.', 'Ustoz savolimga javob bering,',
            e='Undalma («Ustoz») gapning qolgan qismidan vergul bilan ajratiladi.'),
         mc('punk', 'Qaysi gapda qo‘shtirnoq to‘g‘ri qo‘llangan?',
            '«O‘tkan kunlar» romanini o‘qidim.', 'O‘tkan kunlar romanini «o‘qidim».', '«O‘tkan» kunlar romanini o‘qidim.', 'O‘tkan kunlar «romanini» o‘qidim.',
            e='Asar nomi qo‘shtirnoq ichida yoziladi.'),
         op('punk', 'Nuqtalar o‘rniga qo‘yiladigan tinish belgisi nomini yozing: «Yomg‘ir yog‘di ... ammo sayr bekor bo‘lmadi.»',
            ['vergul', ','], e='Qarama-qarshi bog‘lovchi (ammo) oldidan vergul qo‘yiladi.'),
     ]},
    # ------------------------------------------------------------------ SINTAKSIS
    {'sec': 'mgram', 'title': 'Sintaksis: gap turlari va gap bo‘laklari',
     'rules': 'Atov gap — faqat atash ma’nosini bildiradi: «Kech. Sokin ko‘cha.»\n'
              'Shaxsi noma’lum gap — ish-harakatni kim bajargani noma’lum, kesim III shaxs ko‘plikda: «Bizni bayramga taklif qilishdi.»\n'
              'To‘liqsiz gap — gap bo‘laklaridan biri tushib qolgan: «Men uyga bordim, u — maktabga.»\n'
              'Kiritma — fikrga munosabat bildiradi: «Aytishlaricha, bahor erta keladi.»\n'
              'Qo‘shma gap: bog‘lovchili, bog‘lovchisiz va ergash gapli bo‘ladi.',
     'examples': 'Ergash gapli: «Agar mehnat qilsang, natijaga erishasan.» (shart ergash gap)\nBog‘lovchisiz: «Kuz keldi, havo sovuq tortdi.»',
     'items': [
         mc('sint', 'Quyidagi gaplardan qaysi biri atov gap?',
            'Kech. Sokin ko‘cha.', 'Bugun havo ochiq.', 'Men maktabga bordim.', 'U nimani o‘ylayapti?',
            e='Atov gaplarda kesim bo‘lmaydi, faqat narsa yoki hodisa nomi aytiladi.'),
         mc('sint', 'Qaysi gap shaxsi noma’lum gap?',
            'Bizni bayramga taklif qilishdi.', 'Biz bayramga bordik.', 'Bayram yaqinlashmoqda.', 'Men bayramni kutaman.',
            e='Kesim III shaxs ko‘plikda, ish-harakatni kim bajargani noma’lum.'),
         mc('sint', 'Qaysi gap to‘liqsiz gap?',
            'Men kitob o‘qidim, u — gazeta.', 'Men kitob o‘qidim.', 'Kitob o‘qish foydali.', 'Qanday yaxshi kitob!',
            e='Ikkinchi qismda kesim («o‘qidi») tushib qolgan.'),
         mc('sint', 'Qaysi gapda kiritma qo‘llangan?',
            'Aytishlaricha, bahor erta keladi.', 'Bahor keldi, qushlar kela boshladi.', 'Ustoz, bugun dars bormi?', 'Bahor — yilning eng go‘zal fasli.',
            e='«Aytishlaricha» — fikrning kimdandir olinganini bildiruvchi kiritma. «Ustoz» undalma.'),
         mc('sint', '«Bog‘da olma, nok va uzum pishdi.» gapida uyushgan bo‘lak qaysi?',
            'ega', 'kesim', 'hol', 'to‘ldiruvchi',
            e='Olma, nok va uzum — «pishdi» kesimining egalari, ya’ni uyushgan ega.'),
         mc('sint', '«Yosh avlodni milliy ruhda tarbiyalash zarur.» gapida «milliy ruhda» qaysi gap bo‘lagi?',
            'hol', 'aniqlovchi', 'to‘ldiruvchi', 'ega',
            e='«Qanday qilib tarbiyalash?» — «milliy ruhda» tarz holi.'),
         mc('sint', '«Kuz keldi, havo sovuq tortdi.» gapi qanday qo‘shma gap?',
            'bog‘lovchisiz qo‘shma gap', 'ergash gapli qo‘shma gap', 'sodda yig‘iq gap', 'bog‘lovchili qo‘shma gap',
            e='Qismlar bog‘lovchisiz, faqat ohang va vergul yordamida bog‘langan.'),
         mc('sint', '«Agar mehnat qilsang, natijaga erishasan.» gapi qanday qo‘shma gap?',
            'shart ergash gapli qo‘shma gap', 'sabab ergash gapli qo‘shma gap', 'bog‘lovchisiz qo‘shma gap', 'ega ergash gapli qo‘shma gap',
            e='«Agar» yordamida shart ma’nosi ifodalangan.'),
         op('sint', '«Agar mehnat qilsang, natijaga erishasan.» gapidagi ergash gap turini yozing (bir so‘z).',
            ['shart', 'shart ergash gap', 'shart ergash gapli'], e='Shart ergash gap.'),
         mt('sint', 'Gaplarni sintaktik tahlilga oid izohlar bilan moslang.',
            ['1. Kech. Sokin ko‘cha.', '2. Bizni bayramga taklif qilishdi.', '3. Men uyga bordim, u — maktabga.'],
            ['atov gap', 'shaxsi noma’lum gap', 'to‘liqsiz gap', 'kiritmali gap', 'undalmali gap', 'shaxsi umumlashgan gap'], [0, 1, 2],
            e='1 — atov gap; 2 — shaxsi noma’lum gap; 3 — to‘liqsiz gap.'),
     ]},
    # ------------------------------------------------------------------ SO'Z BIRIKMASI
    {'sec': 'mgram', 'title': 'So‘z birikmalari va bog‘lanish usullari',
     'rules': 'Tobe bog‘lanishning uch usuli bor:\n'
              'Bitishuv — tobe so‘zga hech qanday qo‘shimcha qo‘shilmaydi: go‘zal bog‘, tez yugurmoq.\n'
              'Boshqaruv — tobe so‘z tushum, jo‘nalish, o‘rin-payt yoki chiqish kelishigida bo‘ladi: kitobni o‘qimoq, maktabga bormoq.\n'
              'Moslashuv — hokim so‘z egalik qo‘shimchasini oladi: maktabning bog‘i, kitobning sahifasi.',
     'examples': 'Bitishuv: yangi kitob\nBoshqaruv: dars tayyorlamoq\nMoslashuv: o‘quvchining daftari',
     'items': [
         mc('sint', 'Qaysi birikma bitishuv yo‘li bilan bog‘langan?',
            'go‘zal bog‘', 'bog‘ning go‘zalligi', 'bog‘ni sug‘ormoq', 'maktabga bormoq',
            e='Tobe so‘z (go‘zal) hech qanday qo‘shimchasiz hokim so‘zga bog‘langan.'),
         mc('sint', 'Qaysi birikma boshqaruv bilan bog‘langan?',
            'kitobni o‘qimoq', 'tez yugurmoq', 'yangi kitob', 'kitobning sahifasi',
            e='Tobe so‘z tushum kelishigida (kitobni).'),
         mc('sint', 'Qaysi birikma moslashuv yo‘li bilan hosil bo‘lgan?',
            'maktabning bog‘i', 'aqlli bola', 'dars tayyorlamoq', 'tez yurmoq',
            e='Qaratqich kelishigi (maktabning) va egalik qo‘shimchasi (bog‘i) moslashgan.'),
         op('sint', '«Yangi kitob» birikmasida hokim so‘zni yozing.', ['kitob'], e='Hokim so‘z — kitob, tobe so‘z — yangi.'),
     ]},
    # ------------------------------------------------------------------ USLUBIYAT
    {'sec': 'mgram', 'title': 'Uslubiy xatoliklar',
     'rules': 'Pleonazm (ortiqcha so‘z): ma’nosi bir xil so‘zlarni ketma-ket qo‘llash — «kelajak istiqbol», «muhim ahamiyat», «eng a’lo».\n'
              'Paronimlarni adashtirish: ishchi (zavod xodimi) — ishchan (mehnatsevar).\n'
              'Rasmiy uslubda so‘zlashuv unsurlari (-da, -ku, qo‘pol so‘zlar) ishlatilmaydi.\n'
              'Son bilan kelgan otga ko‘plik qo‘shimchasi qo‘shilmaydi: uchta daraxt (daraxtlar emas).',
     'examples': 'Noto‘g‘ri: bizning kelajak istiqbolimiz. To‘g‘ri: bizning kelajagimiz.\nNoto‘g‘ri: uchta daraxtlar. To‘g‘ri: uchta daraxt.',
     'items': [
         mc('usl', 'Qaysi gapda ortiqcha so‘z qo‘llanishi (pleonazm) bilan bog‘liq uslubiy xatolik bor?',
            'Bizning kelajak istiqbolimiz yorqin bo‘lishiga ishonamiz.', 'Bizning kelajagimiz yorqin bo‘lishiga ishonamiz.',
            'Kelajakda yorqin natijalarga erishamiz.', 'Istiqbolli rejalarimiz ko‘p.',
            e='«Kelajak» va «istiqbol» ma’nodosh, ikkalasini birga qo‘llash ortiqcha.'),
         mc('usl', 'Quyidagi birikmalardan qaysi birida ortiqcha so‘z bor?',
            'eng a’lo daraja', 'yuksak daraja', 'a’lo baho', 'yaxshi natija',
            e='«A’lo» o‘zi eng yuqori ma’noni bildiradi, «eng» ortiqcha.'),
         mc('usl', 'Qaysi gapda paronim noto‘g‘ri qo‘llangan?',
            'Zavodda ming nafar ishchan ishlaydi.', 'Zavodda ming nafar ishchi ishlaydi.', 'Ishchan bola darsga erta keldi.', 'U ishchan va mehnatsevar inson.',
            e='Zavodda ishlovchi kishi — ishchi. Ishchan — mehnatsevar degani.'),
         mc('usl', 'Qaysi gap rasmiy uslubga mos kelmaydi?',
            'Ariza yozdim, lekin ish bitmadi-da.', 'Sizdan arizamni ko‘rib chiqishni so‘rayman.', 'Mazkur hujjat qonuniy kuchga ega.', 'Ariza belgilangan tartibda topshirildi.',
            e='«-da» yuklamasi va erkin ohang so‘zlashuv uslubiga xos.'),
         mc('usl', 'Qaysi gapda ko‘plik qo‘shimchasi noto‘g‘ri qo‘llangan?',
            'Bog‘da uchta daraxtlar bor edi.', 'Bog‘da uchta daraxt bor edi.', 'Bog‘da daraxtlar ko‘p edi.', 'Bog‘da ko‘p daraxt bor edi.',
            e='Son bilan kelgan otga -lar qo‘shilmaydi.'),
     ]},
    # ------------------------------------------------------------------ LEKSIKA
    {'sec': 'mgram', 'title': 'Lug‘aviy ma’no: o‘z va ko‘chma, omonim, ma’nodosh',
     'rules': 'O‘z ma’no — so‘zning asosiy, to‘g‘ridan to‘g‘ri ma’nosi: «Daryo bo‘yida katta tosh yotardi.»\n'
              'Ko‘chma ma’no — o‘xshashlik asosida boshqa narsaga ko‘chadi: «tosh yurak odam».\n'
              'Omonim — shakli bir xil, ma’nosi har xil so‘zlar: qo‘y (hayvon) — qo‘y (buyruq).\n'
              'Ma’nodosh (sinonim): botir, mard, jasur. Zid ma’noli (antonim): saxiy — xasis.',
     'examples': 'Frazeologizm: «qo‘l uzatmoq» — yordam bermoq.\nParonim: tuzum (qurilma) — tuzuk (yaxshi).',
     'items': [
         mc('leks', 'Qaysi gapda «tosh» so‘zi ko‘chma ma’noda qo‘llangan?',
            'U tosh yurak odam, hech kimga rahm qilmaydi.', 'Daryo bo‘yida katta tosh yotardi.', 'Bola toshni suvga otdi.', 'Toshdan yasalgan haykal ko‘rkam edi.',
            e='«Tosh yurak» — rahmsiz degani, ko‘chma ma’no.'),
         mc('leks', 'Qaysi gapda «ko‘z» so‘zi o‘z ma’nosida qo‘llangan?',
            'Ko‘zim og‘riyapti, shifokorga bordim.', 'Bu masalaga yengil ko‘z bilan qarab bo‘lmaydi.', 'Ko‘zi ochiq odam aldanmaydi.', 'Mehmonlar ko‘zdan yo‘qoldi.',
            e='Birinchi gapda «ko‘z» — a’zo, o‘z ma’no.'),
         mc('leks', 'Quyidagi so‘zlardan qaysi biri omonim?',
            'qo‘y', 'kitob', 'daraxt', 'tinch',
            e='«Qo‘y» — hayvon va «qo‘ymoq» fe’lining buyruq shakli.'),
         mc('leks', 'Qaysi qatordagi so‘zlar o‘zaro ma’nodosh?',
            'botir, mard, dovyurak', 'botir, qo‘rqoq, dovyurak', 'mard, tinch, jasur', 'jasur, xasis, mard',
            e='Botir, mard, dovyurak — jasur ma’nosidagi sinonimlar.'),
         mc('leks', '«Saxiy» so‘ziga zid ma’noli so‘zni toping.',
            'xasis', 'mard', 'kamtar', 'shirin',
            e='Saxiy — qo‘li ochiq, xasis — ziqna.'),
         mc('leks', '«Qo‘l uzatmoq» iborasining ma’nosi qaysi javobda to‘g‘ri berilgan?',
            'yordam bermoq', 'urmoq', 'xayrlashmoq', 'hadya qilmoq',
            e='Ibora ko‘chma ma’noda «yordam bermoq» degani.'),
         mc('leks', 'Bo‘sh o‘rinni to‘ldiring: «Jamiyatdagi ijtimoiy ... tubdan o‘zgardi.»',
            'tuzum', 'tuzuk', 'tuzatma', 'tuzish',
            e='Tuzum — ijtimoiy-siyosiy qurilma. Tuzuk — yaxshi, joyida degani.'),
         op('leks', '«Saxiy» so‘ziga zid ma’noli so‘zni yozing.', ['xasis', 'baxil'], e='Saxiy — xasis (baxil).'),
     ]},
    # ------------------------------------------------------------------ SO'Z YASALISHI
    {'sec': 'mgram', 'title': 'So‘z yasalishi va shakl yasalishi',
     'rules': 'So‘z yasovchi qo‘shimchalar yangi so‘z hosil qiladi: ish → ishchi, aql → aqlli, yoz → yozuv.\n'
              'Lug‘aviy shakl yasovchilar so‘zning shaklini o‘zgartiradi, lekin yangi so‘z yasamaydi: -roq (qiyosiy daraja), nisbat qo‘shimchalari.\n'
              'Sintaktik shakl yasovchilar so‘zni boshqa so‘zlarga bog‘laydi: kelishik (-ning, -ni, -ga), egalik, kesimlik qo‘shimchalari.\n'
              'Qo‘shma so‘z ikki o‘zakdan yasaladi: ko‘zoynak, gulkosa, oqqush.',
     'examples': 'ish + chi = ishchi (so‘z yasalishi)\nbalandroq (lug‘aviy shakl)\nkitobning (sintaktik shakl)',
     'items': [
         mc('soz', 'Qaysi qatordagi barcha so‘zlar yasama so‘z?',
            'ishchi, aqlli, yozuvchi', 'ish, aql, yozuv', 'maktab, kitob, qalam', 'bola, ota, ona',
            e='ish+chi, aql+li, yoz+uvchi — qo‘shimcha bilan yasalgan.'),
         mc('soz', 'Qaysi qatordagi so‘zlar qo‘shma so‘z?',
            'ko‘zoynak, gulkosa, oqqush', 'ishchi, bilimli, yozuvchi', 'kitob, qalam, daftar', 'aqlli, mehribon, chiroyli',
            e='Qo‘shma so‘zlar ikki mustaqil o‘zakdan tuziladi.'),
         mc('soz', 'Qaysi qo‘shimcha lug‘aviy shakl yasovchi?',
            '-roq', '-lik', '-chi', '-ning',
            e='-roq (balandroq) qiyosiy daraja shaklini yasaydi. -lik va -chi so‘z yasovchi, -ning sintaktik shakl yasovchi.'),
         mc('soz', 'Qaysi qo‘shimcha so‘z yasovchi?',
            '-chi', '-ni', '-ning', '-ga',
            e='-chi ot yasaydi (ish → ishchi). Qolganlari kelishik qo‘shimchalari.'),
     ]},
    # ------------------------------------------------------------------ MORFOLOGIYA
    {'sec': 'mgram', 'title': 'Morfologiya: so‘z turkumlari va fe’l shakllari',
     'rules': 'Ravishdosh -b, -a, -ib, -gach kabi qo‘shimchalar bilan yasaladi: o‘qib, ketgach.\n'
              'Sifatdosh -gan, -ayotgan, -adigan: yozayotgan, kelgan.\n'
              'Nisbat: o‘zlik (-n, -in): yuvindi; orttirma (-tir, -dir): ishlatdi; majhul (-il, -in): yozildi.\n'
              'Kelishiklar: bosh, qaratqich (-ning), tushum (-ni), jo‘nalish (-ga), o‘rin-payt (-da), chiqish (-dan).',
     'examples': 'Ravish: bugun, tez. Tartib son: ikkinchi.',
     'items': [
         mc('morf', '«Kitobni o‘qib, uyga qaytdim» gapidagi «o‘qib» qaysi fe’l shakli?',
            'ravishdosh', 'sifatdosh', 'harakat nomi', 'shart mayli', e='-b qo‘shimchasi bilan yasalgan ravishdosh.'),
         mc('morf', '«Yozayotgan bola» birikmasidagi «yozayotgan» qaysi shakl?',
            'sifatdosh', 'ravishdosh', 'harakat nomi', 'buyruq mayli', e='-ayotgan qo‘shimchasi sifatdosh yasaydi.'),
         mc('morf', 'Qaysi qatordagi barcha so‘zlar sifat?',
            'aqlli, yaxshi, go‘zal', 'kitob, daftar, qalam', 'yugurdi, o‘qidi, bordi', 'men, sen, u', e='Sifat narsaning belgisini bildiradi.'),
         mc('morf', '«Ikkinchi qavat» birikmasida «ikkinchi» qaysi so‘z turkumiga oid?',
            'son', 'sifat', 'ravish', 'olmosh', e='Tartib son (nechanchi?) ma’nosini bildiradi.'),
         mc('morf', '«Bugun dars bor» gapidagi «bugun» qaysi so‘z turkumiga oid?',
            'ravish', 'ot', 'sifat', 'fe’l', e='Payt ma’nosini bildiruvchi ravish.'),
         mc('morf', '«Yuvindi» fe’li qaysi nisbatda?',
            'o‘zlik nisbat', 'majhul nisbat', 'orttirma nisbat', 'birgalik nisbat', e='-in qo‘shimchasi harakat eganing o‘ziga qaytishini bildiradi.'),
         mc('morf', '«Maktabdan» so‘zi qaysi kelishikda?',
            'chiqish kelishigi', 'jo‘nalish kelishigi', 'o‘rin-payt kelishigi', 'tushum kelishigi', e='-dan — chiqish kelishigi qo‘shimchasi.'),
     ]},
]
