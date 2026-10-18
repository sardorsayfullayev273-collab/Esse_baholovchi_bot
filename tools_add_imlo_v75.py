"""v75: «Imlo» uchun qiyinroq (d=3) savollarni miniapp/dtm_bank.json ga qo'shadi. Qayta ishga tushirsa takrorlamaydi (s='v75')."""
import json, os
P = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miniapp', 'dtm_bank.json')
ID0 = 71001
W = 'Qaysi so‘zda imlo xatosi bor?'
ALL = 'Qaysi qatordagi barcha so‘zlar to‘g‘ri yozilgan?'
SENT = 'Qaysi gapda imlo xatosi bor?'
CMB = ['Faqat I', 'Faqat II', 'I va II', 'I va III', 'II va III', 'Hammasi']
def mc(q, right, w1, w2, w3, e): return {'t': 'mc', 'c': 'imlo', 'd': 3, 'q': q, 'o': [right, w1, w2, w3], 'a': 0, 'e': e}
def cb(words, a, e): return {'t': 'mc', 'c': 'imlo', 'd': 3, 'q': 'Quyidagi so‘zlardan qaysilari to‘g‘ri yozilgan?\n' + '\n'.join('%s. %s' % (r, w) for r, w in zip(('I', 'II', 'III'), words)), 'o': CMB, 'a': a, 'e': e, 'fix': 1}
def op(q, ans, e): return {'t': 'open', 'c': 'imlo', 'd': 3, 'q': q, 'ans': ans, 'e': e}
ITEMS = [
 # --- Xatoli so'zni toping (to'g'ri javob = xatoli so'z)
 mc(W, 'maxsulot', 'maxsus', 'axborot', 'ixtiyor', 'To‘g‘ri yozilishi: mahsulot (h bilan). Maxsus, axborot, ixtiyor so‘zlarida x yoziladi.'),
 mc(W, 'tuygu', 'sog‘inch', 'qo‘ng‘iroq', 'g‘ayrat', 'To‘g‘ri yozilishi: tuyg‘u (g‘ harfi bilan).'),
 mc(W, 'ko‘ng‘il', 'qo‘ng‘iz', 'yong‘oq', 'tuyg‘u', 'To‘g‘ri yozilishi: ko‘ngil (ng + i). Qolgan so‘zlarda ng‘ yoziladi.'),
 mc(W, 'taasurot', 'tasavvur', 'muassasa', 'mutaxassis', 'To‘g‘ri yozilishi: taassurot (qo‘sh s).'),
 mc(W, 'muamo', 'muallif', 'mukammal', 'muhandis', 'To‘g‘ri yozilishi: muammo (qo‘sh m).'),
 mc(W, 'etuk', 'eshik', 'ertaga', 'yelka', 'To‘g‘ri yozilishi: yetuk (ye bilan).'),
 mc(W, 'mexnat', 'mehmon', 'sahna', 'bahor', 'To‘g‘ri yozilishi: mehnat (h bilan).'),
 mc(W, 'xurmat', 'hayot', 'xulosa', 'hozir', 'To‘g‘ri yozilishi: hurmat (h bilan). Xulosa so‘zida x yoziladi.'),
 mc(W, 'daraht', 'baxt', 'taxmin', 'axloq', 'To‘g‘ri yozilishi: daraxt (x bilan).'),
 mc(W, 'shahmat', 'shaxs', 'shaxsiy', 'shahar', 'To‘g‘ri yozilishi: shaxmat (x bilan). Shahar so‘zida h yoziladi.'),
 mc(W, 'masuliyat', 'ma’naviyat', 'she’riyat', 'ma’rifat', 'To‘g‘ri yozilishi: mas’uliyat (tutuq belgisi bilan).'),
 mc(W, 'tatil', 'ta’sir', 'jur’at', 'e’tibor', 'To‘g‘ri yozilishi: ta’til (tutuq belgisi bilan).'),
 # --- Barcha so'zlar to'g'ri yozilgan qator
 mc(ALL, 'mahsulot, maxsus, axborot, mahorat', 'maxsulot, maxsus, axborot, mahorat', 'mahsulot, mahsus, axborot, mahorat', 'mahsulot, maxsus, ahborot, mahorat', 'Mahsulot, mahorat — h bilan; maxsus, axborot — x bilan yoziladi.'),
 mc(ALL, 'tuyg‘u, sog‘inch, ko‘ngil, yong‘oq', 'tuygu, sog‘inch, ko‘ngil, yong‘oq', 'tuyg‘u, sog‘inch, ko‘ng‘il, yong‘oq', 'tuyg‘u, sog‘inch, ko‘ngil, yongoq', 'To‘g‘ri: tuyg‘u, sog‘inch, ko‘ngil (ng‘ emas), yong‘oq.'),
 mc(ALL, 'o‘rni, ko‘ngli, burni, singlisi', 'o‘rini, ko‘ngli, burni, singlisi', 'o‘rni, ko‘ngili, burni, singlisi', 'o‘rni, ko‘ngli, burini, singlisi', 'Egalik qo‘shimchasi olganda unli tushadi: o‘rin → o‘rni, ko‘ngil → ko‘ngli, burun → burni, singil → singlisi.'),
 mc(ALL, 'muassasa, taassurot, mutaxassis, tasavvur', 'muasasa, taassurot, mutaxassis, tasavvur', 'muassasa, taasurot, mutaxassis, tasavvur', 'muassasa, taassurot, mutaxasis, tasavur', 'Qo‘sh undosh saqlanadi: muassasa, taassurot, mutaxassis, tasavvur.'),
 mc(ALL, 'e’lon, ta’sir, jur’at, ma’ruza', 'elon, ta’sir, jur’at, ma’ruza', 'e’lon, tasir, jur’at, ma’ruza', 'e’lon, ta’sir, jur’at, maruza', 'Tutuq belgisi: e’lon, ta’sir, jur’at, ma’ruza.'),
 mc(ALL, 'yetuk, yetakchi, yechim, yelka', 'etuk, yetakchi, yechim, yelka', 'yetuk, etakchi, yechim, yelka', 'yetuk, yetakchi, echim, yelka', 'Bu so‘zlar ye bilan boshlanadi: yetuk, yetakchi, yechim, yelka.'),
 mc(ALL, 'ehtiyot, ehtimol, hurmat, haqiqat', 'extiyot, ehtimol, hurmat, haqiqat', 'ehtiyot, extimol, hurmat, haqiqat', 'ehtiyot, ehtimol, xurmat, haqiqat', 'Ehtiyot, ehtimol, hurmat, haqiqat so‘zlarida h yoziladi.'),
 mc(ALL, 'asta-sekin, tez-tez, ota-ona, kecha-kunduz', 'asta sekin, tez-tez, ota-ona, kecha-kunduz', 'asta-sekin, teztez, ota-ona, kecha-kunduz', 'asta-sekin, tez-tez, otaona, kecha-kunduz', 'Juft va takroriy so‘zlar chiziqcha bilan yoziladi.'),
 # --- Gapda xato
 mc(SENT, 'Mahkama qarori e’lon qilingach, xalq orasida katta taasurot qoldirdi.', 'Muhim axborot maxfiy saqlandi, ammo ba’zi xodimlar xabardor bo‘ldi.', 'Ehtiyotkor bo‘ling: shoshilinch qaror ba’zan xatoga olib keladi.', 'Yetuk mutaxassislar tashkilot ishini muassasa talablariga moslashtirdi.', 'Xato: taasurot. To‘g‘ri yozilishi: taassurot.'),
 mc(SENT, 'Bu ishga masul shaxs hamma ma’lumotni taqdim etdi.', 'Ota-onamning mehnati va g‘ayrati menga doim ilhom beradi.', 'Kitobxonlar ma’naviyat va madaniyat haqida bahs yuritdi.', 'U yangi sahifani oldingi sahifaga solishtirib, xulosa chiqardi.', 'Xato: masul. To‘g‘ri yozilishi: mas’ul.'),
 mc(SENT, 'Ular birbiriga yordam berdi.', 'Hech kim kelmadi.', 'Ona tili darsi boshlandi.', 'Xalqaro anjuman temiryo‘l vokzalida o‘tkazildi.', 'Xato: birbiriga. To‘g‘ri yozilishi: bir-biriga (chiziqcha bilan).'),
 mc(SENT, 'Etakchi o‘quvchi barcha topshiriqlarni bajardi.', 'Ertaga yangi eshik o‘rnatishadi.', 'Yetim bolalarga yordam berildi.', 'Elchi mehmonlarni kutib oldi.', 'Xato: etakchi. To‘g‘ri yozilishi: yetakchi.'),
 # --- I-II-III
 cb(['mahsulot', 'maxsus', 'maxorat'], 2, 'Mahorat so‘zi h bilan yoziladi (III xato).'),
 cb(['ko‘ng‘il', 'tuyg‘u', 'sog‘inch'], 4, 'To‘g‘ri yozilishi: ko‘ngil (I xato).'),
 cb(['taassurot', 'mutaxasis', 'tasavvur'], 3, 'To‘g‘ri yozilishi: mutaxassis (II xato).'),
 cb(['o‘rni', 'ko‘ngli', 'burni'], 5, 'Egalik qo‘shimchasi olganda unli tushadi: o‘rni, ko‘ngli, burni (hammasi to‘g‘ri).'),
 cb(['yetuk', 'etakchi', 'yelka'], 3, 'To‘g‘ri yozilishi: yetakchi (II xato).'),
 cb(['ma’lumot', 'mas’uliyat', 'tatil'], 2, 'To‘g‘ri yozilishi: ta’til (III xato).'),
 # --- Yozma javob
 op('«Taasurot» so‘zining to‘g‘ri imlosini yozing.', ['taassurot'], 'To‘g‘ri yozilishi: taassurot (qo‘sh s).'),
 op('«Mutaxasis» so‘zining to‘g‘ri imlosini yozing.', ['mutaxassis'], 'To‘g‘ri yozilishi: mutaxassis (qo‘sh s).'),
 op('«Tuygu» so‘zining to‘g‘ri imlosini yozing.', ['tuyg‘u'], 'To‘g‘ri yozilishi: tuyg‘u.'),
 op('«Mexnat» so‘zining to‘g‘ri imlosini yozing.', ['mehnat'], 'To‘g‘ri yozilishi: mehnat (h bilan).'),
]

def main():
    d = json.load(open(P, encoding='utf-8'))
    if any(x.get('s') == 'v75' for x in d):
        print('v75 savollari allaqachon bor:', sum(1 for x in d if x.get('s') == 'v75')); return
    used = {x['id'] for x in d}; nid = ID0
    for it in ITEMS:
        while nid in used: nid += 1
        it = dict(it, id=nid, s='v75'); d.append(it); used.add(nid); nid += 1
    json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('qo‘shildi:', len(ITEMS), '— jami:', len(d))

if __name__ == '__main__': main()
