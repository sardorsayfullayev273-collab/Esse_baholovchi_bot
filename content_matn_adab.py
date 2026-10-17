"""v72: «Mashq → Matn» va «Mashq → Adabiyot» hamda o'yinlar banki uchun original savollar.
Matnlar va she'riy parchalar muallif tomonidan yangidan yozilgan (namunaviy testdan ko'chirilmagan)."""
from content_gram import mc, op, mt

# ===================================================================== MATNLAR
TEXT_SUV = ('[1]Yer yuzidagi suv hech qachon bir joyda to‘xtab turmaydi. [2]Quyosh nuri ta’sirida dengiz va ko‘llardagi suv bug‘lanib, havoga ko‘tariladi. '
            '[3]Havoning yuqori qatlamlarida bug‘ soviydi va mayda tomchilarga aylanib, bulutlarni hosil qiladi. [4]Bulutlar og‘irlashgach, yomg‘ir yoki qor shaklida yerga qaytadi. '
            '[5]Yog‘in suvining bir qismi daryolar orqali yana dengizga quyiladi, bir qismi esa yer ostiga singib, buloqlarni to‘ldiradi. '
            '[6]Shu tariqa tabiatda suvning uzluksiz aylanish jarayoni kechadi.')

TEXT_KITOB = ('[1]So‘nggi yillarda yoshlar orasida kitobxonlikka qiziqish pasayib bormoqda, degan fikrni tez-tez eshitamiz. '
              '[2]Albatta, internet va ijtimoiy tarmoqlar vaqtimizning katta qismini egallamoqda. [3]Bugun havo ochiq bo‘lib, ko‘chalarda odamlar ko‘p. '
              '[4]Ammo kitob o‘qish insonda tafakkur, sabr va nutq madaniyatini shakllantiradi. Muntazam o‘qiydigan odam fikrini aniq va ravon bayon qiladi, so‘z boyligi ortadi. '
              'Shu bois kuniga kamida yigirma daqiqa kitob mutolaasiga ajratish foydadan holi emas.')

TEXT_BOG = ('[1]Bobom bog‘ni o‘z qo‘li bilan yaratgan edi. [2]Har bahorda u eng avval ko‘chatlarning ildizini ehtiyotlab tekshirar, so‘ng ularga suv quyardi. '
            '[3]Biz, nevaralari, bog‘ ichida yugurib o‘ynardik, bobom esa daraxt tagida o‘tirib, bizga qarab jilmayardi. '
            '[4]Ba’zan u: «Daraxt ekkan odam o‘lmaydi, bolam», deb qo‘yardi.')

TOPICS_MATN = [
    {'sec': 'mmatn', 'title': 'Ilmiy matn: «Suvning aylanishi»',
     'rules': 'Matn bilan ishlashda avval matnni to‘liq o‘qing, so‘ng savolga qaytib, javobni matndan toping.\n'
              'Variantlarda matnda aytilmagan yoki matnga zid fikr bo‘lsa, u noto‘g‘ri hisoblanadi.\n'
              'Uslubiy xatolik: ortiqcha so‘z (mayda kichik), mavzudan chetga chiqish, mantiqiy ketma-ketlikning buzilishi.\n'
              'Ilmiy matnda aniq ma’lumot, atamalar va sabab-natija bog‘lanishi bo‘ladi.',
     'examples': 'Matndagi sabab-natija: Quyosh nuri → bug‘lanish → bulut → yog‘in.',
     'text': TEXT_SUV,
     'items': [
         mc('matn', 'Matn mazmuniga mos to‘g‘ri shakllantirilgan gapni aniqlang.',
            'Suvning bug‘lanishi uchun Quyosh energiyasi zarur.', 'Bulutlar faqat qish faslida hosil bo‘ladi.',
            'Yog‘in suvi butunlay yer ostiga singib ketadi.', 'Dengiz suvi bug‘langanda tuzini ham havoga olib chiqadi.',
            e='[2]-gapda suv Quyosh nuri ta’sirida bug‘lanishi aytilgan.', p=TEXT_SUV),
         mc('matn', 'Matnda aks etgan ma’lumotni aniqlang.',
            'Yog‘in suvining bir qismi buloqlarni to‘ldiradi.', 'Daryolar suvi hech qachon dengizga yetib bormaydi.',
            'Suv aylanishi faqat yoz oylarida kechadi.', 'Bulutlar havoning quyi qatlamida isib hosil bo‘ladi.',
            e='[5]-gapda buni ko‘rish mumkin.', p=TEXT_SUV),
         mc('matn', 'Suv aylanishining to‘g‘ri ketma-ketligini aniqlang.',
            'bug‘lanish → bulut hosil bo‘lishi → yog‘in → oqim', 'bulut hosil bo‘lishi → bug‘lanish → yog‘in → oqim',
            'yog‘in → bug‘lanish → bulut hosil bo‘lishi → oqim', 'oqim → bulut hosil bo‘lishi → bug‘lanish → yog‘in',
            e='Matndagi tartib: [2] bug‘lanish, [3] bulut, [4] yog‘in, [5] oqim.', p=TEXT_SUV),
         mc('matn', 'Matnga mos sarlavhani tanlang.',
            'Tabiatda suvning aylanishi', 'Dengizlarning sho‘rligi sababi', 'Yomg‘ir keltiradigan ofatlar', 'Quyoshning issiqligi',
            e='Matnning asosiy mavzusi suvning uzluksiz aylanishi.', p=TEXT_SUV),
         mc('matn', '[6]-gapdagi «uzluksiz» so‘zining ma’nodoshini toping.',
            'to‘xtovsiz', 'ba’zan', 'kamdan-kam', 'vaqtinchalik',
            e='Uzluksiz — to‘xtovsiz, doimiy.', p=TEXT_SUV),
         mc('matn', 'Quyidagi gaplardan qaysi biri matn mazmuniga mos va uslubiy xatosiz?',
            'Havo sovigach, bug‘ mayda tomchilarga aylanadi.', 'Havo sovigach, bug‘ mayda kichik tomchilarga aylanadi.',
            'Havo sovigach, bug‘ yana qaytadan qayta suvga aylanadi.', 'Havo sovigach, bug‘ mayda tomchilarga aylanib, ular daryolarga aylanadi.',
            e='«Mayda kichik» va «qaytadan qayta» ortiqcha so‘z (pleonazm).', p=TEXT_SUV),
         op('matn', 'Matnga ko‘ra, suv nima ta’sirida bug‘lanadi? (ikki so‘z bilan yozing)',
            ['Quyosh nuri', 'quyosh nuri ta’sirida', 'Quyosh nuri ta’sirida'], e='[2]-gap: Quyosh nuri ta’sirida.', p=TEXT_SUV),
     ]},
    {'sec': 'mmatn', 'title': 'Publitsistik matn: «Kitobxonlik»',
     'rules': 'Publitsistik matnda muallif ijtimoiy muammoga o‘z munosabatini bildiradi, fikr dalillar bilan asoslanadi.\n'
              'Matnning mazmuniy tuzilishini buzadigan gap — mavzuga aloqasi yo‘q yoki fikr izchilligini uzadigan gap.\n'
              'Asosiy fikr ko‘pincha «ammo», «shu bois» kabi so‘zlardan keyin keladi.',
     'examples': 'Mavzudan chetga chiqqan gap: «Bugun havo ochiq bo‘lib, ko‘chalarda odamlar ko‘p.» (kitobxonlik haqidagi fikrga aloqasi yo‘q)',
     'text': TEXT_KITOB,
     'items': [
         mc('matn', 'Raqamlab ko‘rsatilgan qaysi gap matnning mazmuniy tuzilishida uslubiy xatolikni yuzaga keltirgan?',
            '3', '1', '2', '4', e='[3]-gap kitobxonlik mavzusiga aloqador emas, fikr izchilligini buzgan.', p=TEXT_KITOB),
         mc('matn', 'Muallifning asosiy fikrini aniqlang.',
            'Muntazam kitob o‘qish tafakkur va nutq madaniyatini rivojlantiradi.', 'Internet va ijtimoiy tarmoqlar butunlay zararli.',
            'Yoshlar kitob o‘qimaydi va bu hech qachon o‘zgarmaydi.', 'Kitobni faqat maktabda o‘qish kerak.',
            e='Asosiy fikr [4]-gap va undan keyingi jumlalarda.', p=TEXT_KITOB),
         mc('matn', 'Matn qaysi uslubda yozilgan?',
            'publitsistik', 'ilmiy', 'badiiy', 'rasmiy', e='Muallif ijtimoiy muammoga munosabat bildirgan va ommaga murojaat qilgan.', p=TEXT_KITOB),
         mc('matn', '«Mutolaa» so‘zining ma’nodoshini toping.',
            'o‘qish', 'yozish', 'tinglash', 'sanash', e='Mutolaa — kitob o‘qish, o‘rganish.', p=TEXT_KITOB),
         mc('matn', 'Matn mazmuniga mos to‘g‘ri gapni aniqlang.',
            'Muntazam o‘quvchining so‘z boyligi ortadi.', 'Kitob o‘qish nutqni sekinlashtiradi.',
            'Ijtimoiy tarmoqlar kitobxonlikni to‘liq almashtiradi.', 'Kuniga bir soat kitob o‘qish majburiydir.',
            e='Matndagi 4-gapdan keyingi jumla bilan mos.', p=TEXT_KITOB),
         op('matn', 'Matnga ko‘ra, kuniga kamida necha daqiqa kitob o‘qish tavsiya etiladi? (raqam bilan yozing)',
            ['20', 'yigirma'], e='Matnda «kamida yigirma daqiqa» deyilgan.', p=TEXT_KITOB),
     ]},
    {'sec': 'mmatn', 'title': 'Badiiy matn: «Bobomning bog‘i»',
     'rules': 'Badiiy matnda obraz (qahramon) xarakteri uning ish-harakati, so‘zi va boshqalarning munosabati orqali ochiladi.\n'
              'Qahramonning so‘zi (ko‘chirma gap) ko‘pincha asosiy g‘oyani ifodalaydi.\n'
              'Gap bo‘laklarini tahlil qilishda raqamlangan gapga e’tibor bering.',
     'examples': 'Izohlovchi: «Biz, nevaralari, ...» — «nevaralari» «biz» so‘zini izohlaydi.',
     'text': TEXT_BOG,
     'items': [
         mc('matn', 'Bobo obrazini ifodalovchi javobni aniqlang.',
            'mehnatsevar, mehribon inson', 'loqayd va ichiqora kishi', 'shoshqaloq, jahldor odam', 'yolg‘izlikni yoqtiruvchi, begona ko‘ringan kishi',
            e='Bobo bog‘ yaratgan, ko‘chatlarni parvarish qilgan, nevaralariga mehr bilan boqqan.', p=TEXT_BOG),
         mc('matn', '[2]-gapdagi «ehtiyotlab» so‘zi qaysi fe’l shaklida?',
            'ravishdosh', 'sifatdosh', 'harakat nomi', 'buyruq mayli', e='-b qo‘shimchasi bilan yasalgan ravishdosh.', p=TEXT_BOG),
         mc('matn', '[4]-gapda ifodalangan asosiy fikr qaysi javobda to‘g‘ri izohlangan?',
            'Odam qilgan yaxshi ishi bilan xotirada qoladi.', 'Daraxt ekish faqat yozda bajariladigan ish.',
            'Keksalik odamni hech qachon charchatmaydi.', 'Bog‘ yaratish juda qiyin va foydasiz.',
            e='«Daraxt ekkan odam o‘lmaydi» — yaxshi amal xotirada abadiy qolishi haqida.', p=TEXT_BOG),
         mc('matn', '[3]-gapdagi «nevaralari» so‘zi qaysi gap bo‘lagi?',
            'izohlovchi', 'aniqlovchi', 'hol', 'to‘ldiruvchi', e='«Biz» so‘zini izohlab keladi.', p=TEXT_BOG),
         mc('matn', 'Matn mazmuniga mos to‘g‘ri gapni aniqlang.',
            'Bobo bog‘ni o‘z qo‘li bilan barpo etgan.', 'Bog‘ni bobom emas, nevaralari yaratgan.',
            'Bobom ko‘chatlarni suvsiz qoldirardi.', 'Bobom nevalarini bog‘dan haydardi.', e='[1]-gapda aytilgan.', p=TEXT_BOG),
         op('matn', 'Bobo har bahorda eng avval ko‘chatlarning nimasini tekshirardi? (bir so‘z)',
            ['ildizini', 'ildiz'], e='[2]-gap: ko‘chatlarning ildizini tekshirardi.', p=TEXT_BOG),
     ]},
]

# ===================================================================== ADABIYOT
POEM_ILM = ('Ilm — ulkan dengiz, qirg‘og‘i yo‘q,\nUnda suzgan kishi gavhar topadi.\n'
            'Dangasa esa qirg‘oqda qoladi,\nMehnatkash har ishda g‘olib chiqadi.')

TOPICS_ADAB = [
    {'sec': 'madab', 'title': 'She’riy san’atlar: tashbeh, tashxis, mubolag‘a, tazod, talmeh',
     'rules': 'Tashbeh — ikki narsani bir-biriga o‘xshatish: «Yuzing oy kabi porlar».\n'
              'Tashxis — jonsiz narsani jonli mavjudot kabi tasvirlash: «Tog‘lar jilmayib bahorni kutib oldi».\n'
              'Mubolag‘a — voqea-hodisani haddan tashqari bo‘rttirish.\n'
              'Tazod — zid ma’noli so‘zlarni yonma-yon qo‘llash: kecha va kunduz, oq va qora.\n'
              'Talmeh — mashhur tarixiy yoki afsonaviy voqea, shaxsga ishora: «Boshimga Majnunning kuni tushdi».\n'
              'Husni ta’lil — hodisaga go‘zal, to‘qima sabab ko‘rsatish.',
     'examples': 'Mubolag‘a: «Ko‘z yoshim daryo bo‘lib oqdi, dengizlar to‘ldi.»\nHusni ta’lil: «Bulut yig‘ladi — quyosh sog‘inchidan.»',
     'items': [
         mc('nazar', '«Yuzing oy kabi porlar» misrasida qaysi she’riy san’at qo‘llangan?', 'tashbeh', 'tazod', 'mubolag‘a', 'talmeh',
            e='Yuz oyga o‘xshatilgan — tashbeh.'),
         mc('nazar', '«Ko‘z yoshim daryo bo‘lib oqdi, dengizlar to‘ldi» misrasida qaysi she’riy san’at qo‘llangan?', 'mubolag‘a', 'tazod', 'talmeh', 'tashxis',
            e='Ko‘z yoshining dengiz to‘ldirishi bo‘rttirilgan tasvir — mubolag‘a.'),
         mc('nazar', '«Kecha va kunduz, oq va qora — barchasi o‘z o‘rnida» misrasida qaysi she’riy san’at qo‘llangan?', 'tazod', 'tashbeh', 'mubolag‘a', 'husni ta’lil',
            e='Zid ma’noli so‘zlar yonma-yon keltirilgan (kecha — kunduz, oq — qora).'),
         mc('nazar', '«Boshimga Majnunning kuni tushdi» misrasida qaysi she’riy san’at qo‘llangan?', 'talmeh', 'tashxis', 'mubolag‘a', 'tazod',
            e='Majnun obrazi — mashhur dostonga ishora, ya’ni talmeh.'),
         mc('nazar', '«Tog‘lar jilmayib bahorni kutib oldi» misrasida qaysi she’riy san’at qo‘llangan?', 'tashxis', 'tazod', 'talmeh', 'mubolag‘a',
            e='Tog‘ jonli mavjudot kabi jilmaygan — tashxis.'),
         mc('nazar', '«Bulut yig‘ladi — quyosh sog‘inchidan» misrasida hodisaga to‘qima sabab ko‘rsatilgan. Bu qaysi she’riy san’at?',
            'husni ta’lil', 'tazod', 'tashbeh', 'talmeh', e='Yomg‘ir yog‘ishiga go‘zal to‘qima sabab keltirilgan.'),
         mc('nazar', 'Jonsiz narsa yoki hodisani jonli mavjudot kabi tasvirlash san’ati qaysi?', 'tashxis', 'tashbeh', 'tazod', 'talmeh',
            e='Jonlantirish — tashxis.'),
         op('nazar', '«Boshimga Majnunning kuni tushdi» misrasidagi she’riy san’atni yozing.', ['talmeh'], e='Talmeh — mashhur obrazga ishora.'),
         op('nazar', 'Voqea-hodisani haddan tashqari bo‘rttirib tasvirlash san’atini yozing.',
            ['mubolag‘a', 'mubolag’a', 'mubolag\'a', 'mubolaga'], e='Mubolag‘a.'),
     ]},
    {'sec': 'madab', 'title': 'Qofiya, radif va she’riy janrlar',
     'rules': 'Qofiya — misralar oxiridagi uyg‘un tovushlar: yurak — tilak.\n'
              'Radif — qofiyadan keyin aynan takrorlanadigan so‘z yoki so‘zlar.\n'
              'G‘azal: birinchi bayti — matla’, takhallus aytiladigan oxirgi bayti — maqta’.\n'
              'Ruboiy — 4 misrali she’r. Fard — bir baytdan iborat she’r. Masnaviy — har bir bayti o‘z qofiyasiga ega (aa, bb, vv).',
     'examples': 'Bu dunyoda ilmdan ulug‘ boylik yo‘q, ey do‘st,\nIlm yo‘lida yurmoqdan ulug‘ shodlik yo‘q, ey do‘st.\nBu yerda qofiya: boylik — shodlik; radif: yo‘q, ey do‘st.',
     'items': [
         mc('nazar', 'Quyidagi juftliklardan qaysi biri qofiyadosh?', 'yurak — tilak', 'bahor — daryo', 'ko‘z — qalam', 'tong — kitob', e='Ikkalasi ham -ak bilan tugaydi.'),
         mc('nazar', 'Misralardagi radifni aniqlang.\nBu dunyoda ilmdan ulug‘ boylik yo‘q, ey do‘st,\nIlm yo‘lida yurmoqdan ulug‘ shodlik yo‘q, ey do‘st.',
            'yo‘q, ey do‘st', 'boylik — shodlik', 'ulug‘', 'ilm yo‘lida', e='Radif qofiyadan keyin aynan takrorlanadi.'),
         mc('nazar', 'Misralardagi qofiyadosh so‘zlarni aniqlang.\nBu dunyoda ilmdan ulug‘ boylik yo‘q, ey do‘st,\nIlm yo‘lida yurmoqdan ulug‘ shodlik yo‘q, ey do‘st.',
            'boylik — shodlik', 'yo‘q — yo‘q', 'ilmdan — yo‘lida', 'ulug‘ — ulug‘', e='Qofiya radifdan oldin keladi: boylik — shodlik.'),
         mc('nazar', 'G‘azalning birinchi baytiga nima deyiladi?', 'matla’', 'maqta’', 'radif', 'fard', e='Birinchi bayt — matla’.'),
         mc('nazar', 'G‘azalning takhallus keltirilgan oxirgi bayti nima deb ataladi?', 'maqta’', 'matla’', 'tuyuq', 'masnaviy', e='Takhallusli oxirgi bayt — maqta’.'),
         mc('nazar', 'Ruboiy necha misradan iborat?', '4', '2', '6', '8', e='Ruboiy to‘rt misrali she’r.'),
         mc('nazar', 'Bir baytdan iborat, mustaqil fikrli she’riy janr qaysi?', 'fard', 'ruboiy', 'qit’a', 'masnaviy', e='Fard — bir bayt.'),
         mc('nazar', 'Har bir bayti o‘z qofiyasiga ega (aa, bb, vv...) bo‘lgan janr qaysi?', 'masnaviy', 'g‘azal', 'ruboiy', 'tuyuq', e='Masnaviy dostonlar shu shaklda yoziladi.'),
         op('nazar', 'G‘azalning takhallus aytiladigan oxirgi baytini nima deyiladi? (bir so‘z)',
            ['maqta’', 'maqta', 'maqta\'', 'maqtaʼ'], e='Maqta’.'),
         mt('nazar', 'She’riy janrlarni ta’rif bilan moslang.', ['1. fard', '2. ruboiy', '3. masnaviy'],
            ['bir baytdan iborat she’r', 'to‘rt misrali she’r', 'har bayti o‘z qofiyasiga ega she’r', 'ikki baytli she’r', 'takhallus bilan tugaydigan bayt', 'besh baytli she’r'],
            [0, 1, 2], e='Fard — bir bayt; ruboiy — 4 misra; masnaviy — har bayt o‘z qofiyasi bilan.'),
     ]},
    {'sec': 'madab', 'title': 'She’riy parcha tahlili',
     'rules': 'She’riy parchani tahlil qilishda: 1) mazmunni, 2) obrazlarni (nima nimaga o‘xshatilgan), 3) she’riy san’atni, 4) qofiya va radifni aniqlang.\n'
              'Tire bilan kelgan o‘xshatish («Ilm — dengiz») tashbeh hisoblanadi.',
     'examples': POEM_ILM,
     'items': [
         mc('nazar', 'She’riy parcha haqidagi to‘g‘ri hukmni aniqlang.\n' + POEM_ILM,
            'Ilm dengizga o‘xshatilgan.', 'Dangasalik ulug‘langan.', 'Tazod san’ati asosiy o‘rin tutgan.', 'Parchada radif qo‘llangan.',
            e='«Ilm — ulkan dengiz» — tashbeh.'),
         mc('nazar', 'Parchaning g‘oyaviy mazmunini aniqlang.\n' + POEM_ILM,
            'Ilm va mehnat orqali yutuqqa erishish ulug‘lanadi.', 'Tabiat go‘zalligi madh etilgan.', 'Vatan sog‘inchi tasvirlangan.', 'Yoshlik o‘tkinchi ekani aytilgan.',
            e='Dangasa qirg‘oqda qoladi, mehnatkash g‘olib chiqadi.'),
         mc('nazar', 'Parchadagi «gavhar» so‘zi qanday ma’noda qo‘llangan?\n' + POEM_ILM,
            'ilm samarasi, qimmatli bilim', 'tosh', 'qum', 'baliq', e='Ko‘chma ma’noda — ilm orqali topilgan qadrli narsa.'),
     ]},
    {'sec': 'madab', 'title': 'Mumtoz adabiyot: asosiy so‘zlar',
     'rules': 'Mumtoz she’riyatda ko‘p uchraydigan so‘zlar:\nashk — ko‘zyosh; hajr — ayriliq; visol — uchrashuv, yetishish; zulf — soch; ag‘yor — begona, raqib;\nxazon — to‘kilgan barg; jafo — zulm; vafo — sadoqat.',
     'examples': 'Hajr — visol; jafo — vafo (zid ma’noli juftliklar).',
     'items': [
         mc('nazar', 'Mumtoz adabiyotda «ashk» so‘zi qanday ma’noni bildiradi?', 'ko‘zyosh', 'yuz', 'soch', 'ayriliq', e='Ashk — ko‘zyosh.'),
         mc('nazar', 'Mumtoz adabiyotda «hajr» so‘zi qanday ma’noni bildiradi?', 'ayriliq', 'uchrashuv', 'sadoqat', 'zulm', e='Hajr — ayriliq, visol esa uning ziddi.'),
         mc('nazar', 'Mumtoz adabiyotda «visol» so‘zi qanday ma’noni bildiradi?', 'uchrashuv, yetishish', 'ayriliq', 'qayg‘u', 'jazo', e='Visol — sevgilisiga yetishish.'),
         mc('nazar', 'Mumtoz adabiyotda «zulf» so‘zi qanday ma’noni bildiradi?', 'soch', 'ko‘z', 'lab', 'yuz', e='Zulf — sevgilining sochi.'),
         mc('nazar', 'Mumtoz adabiyotda «ag‘yor» so‘zi qanday ma’noni bildiradi?', 'begona, raqib', 'do‘st', 'yor', 'ustoz', e='Ag‘yor — begonalar, raqiblar.'),
         mc('nazar', 'Mumtoz adabiyotda «xazon» so‘zi qanday ma’noni bildiradi?', 'to‘kilgan barg, kuz', 'bahor', 'gul', 'yomg‘ir', e='Xazon — xazonrezgi, to‘kilgan barglar.'),
         mc('nazar', 'Mumtoz adabiyotda «jafo» so‘zi qanday ma’noni bildiradi?', 'zulm, ozor', 'sadoqat', 'muhabbat', 'baxt', e='Jafo — zulm; vafo — sadoqat.'),
         op('nazar', 'Mumtoz adabiyotdagi «hajr» so‘zining ma’nosini yozing (bir so‘z).', ['ayriliq', 'ayrilik'], e='Hajr — ayriliq.'),
     ]},
    {'sec': 'madab', 'title': 'Badiiy asarlar: muallif, janr, qahramon',
     'rules': 'Alisher Navoiy «Xamsa» (5 doston): «Hayrat ul-abror», «Farhod va Shirin», «Layli va Majnun», «Sab’ai sayyor», «Saddi Iskandariy». Boshqa asarlari: «Mahbub ul-qulub», «Muhokamat ul-lug‘atayn».\n'
              'Abdulla Qodiriy — «O‘tkan kunlar», «Mehrobdan chayon». Cho‘lpon — «Kecha va kunduz». Abdulla Qahhor — «Sarob», «Anor».\n'
              'Oybek — «Navoiy». Odil Yoqubov — «Ulug‘bek xazinasi». O‘tkir Hoshimov — «Ikki eshik orasi». G‘afur G‘ulom — «Shum bola».\n'
              'Yusuf Xos Hojib — «Qutadg‘u bilig». Mahmud Koshg‘ariy — «Devonu lug‘otit turk». Bobur — «Boburnoma».',
     'examples': '«O‘tkan kunlar»: Otabek va Kumush. «Sarob»: Saidiy.',
     'items': [
         mc('tarix', '«Kecha va kunduz» romani muallifi kim?', 'Cho‘lpon', 'Abdulla Qodiriy', 'Oybek', 'Abdulla Qahhor', e='«Kecha va kunduz» — Cho‘lponning romani.'),
         mc('tarix', '«Ikki eshik orasi» romani muallifi kim?', 'O‘tkir Hoshimov', 'Odil Yoqubov', 'Oybek', 'G‘afur G‘ulom', e='O‘tkir Hoshimov asari.'),
         mc('tarix', 'Quyidagi asarlardan qaysi biri «Xamsa» tarkibiga kirmaydi?', 'Mahbub ul-qulub', 'Sab’ai sayyor', 'Farhod va Shirin', 'Saddi Iskandariy',
            e='«Mahbub ul-qulub» — Navoiyning nasriy asari.'),
         mc('tarix', '«Qutadg‘u bilig» asarining muallifi kim?', 'Yusuf Xos Hojib', 'Mahmud Koshg‘ariy', 'Ahmad Yugnakiy', 'Alisher Navoiy', e='Yusuf Xos Hojib asari.'),
         mc('tarix', '«Devonu lug‘otit turk» qanday asar?', 'turkiy so‘zlar lug‘ati', 'doston', 'tarixiy roman', 'she’riy devon', e='Mahmud Koshg‘ariyning turkiy tillar lug‘ati.'),
         mc('tarix', '«Sarob» romanining bosh qahramoni kim?', 'Saidiy', 'Otabek', 'Anvar', 'Mirzakarim', e='Abdulla Qahhorning «Sarob» romani qahramoni — Saidiy.'),
         mc('tarix', '«O‘tkan kunlar» romanining bosh qahramonlari kimlar?', 'Otabek va Kumush', 'Anvar va Ra’no', 'Farhod va Shirin', 'Zebi va Miryoqub',
            e='Abdulla Qodiriy romanining qahramonlari — Otabek va Kumush.'),
         mc('tarix', '«Boburnoma» qanday asar?', 'xotira (memuar) asar', 'doston', 'drama', 'ertak', e='Bobur o‘z hayoti va davri haqida yozgan xotira asar.'),
         mc('tarix', 'Quyidagilardan qaysi biri Abdulla Qahhorning hikoyasi?', 'Anor', 'Sarob', 'O‘tkan kunlar', 'Navoiy', e='«Anor» — Abdulla Qahhor hikoyasi.'),
         mc('tarix', '«O‘tkan kunlar» romanida qaysi davr hayoti tasvirlangan?', 'XIX asr o‘rtalaridagi Qo‘qon xonligi hayoti', 'Amir Temur davri', 'Xorazmshohlar davri', 'XX asr oxiri',
            e='Asar voqealari Qo‘qon xonligi davrida kechadi.'),
         mc('tarix', '«Navoiy» romani muallifi kim?', 'Oybek', 'Odil Yoqubov', 'Cho‘lpon', 'Abdulla Qodiriy', e='«Navoiy» — Oybekning romani.'),
         op('tarix', '«Xamsa» nechta dostondan iborat? (raqam bilan yozing)', ['5', 'besh', 'beshta'], e='«Xamsa» — besh doston.'),
         op('tarix', '«O‘tkan kunlar» romani muallifining familiyasini yozing.', ['Qodiriy'], e='Abdulla Qodiriy.'),
         mt('tarix', 'Muallifni asar bilan moslang.', ['1. Cho‘lpon', '2. Oybek', '3. Odil Yoqubov'],
            ['«Kecha va kunduz»', '«Navoiy»', '«Ulug‘bek xazinasi»', '«Sarob»', '«Shum bola»', '«Anor»'], [0, 1, 2],
            e='Cho‘lpon — «Kecha va kunduz»; Oybek — «Navoiy»; Odil Yoqubov — «Ulug‘bek xazinasi».'),
     ]},
]
