# -*- coding: utf-8 -*-
"""v127 (renderer) — «Sertifikatni chiroyli qilish»: talabgor sertifikat rasmini yuboradi, bot 3D-effektli natija kartasini (1080x1350) yasab beradi.
Hamma uchun ochiq. Kartada bot linki bor. Ism, daraja (A+, A, B+, B, C+) va ball talabgorning o'zi kiritadi (sertifikatni o'qish yo'q).
Oqim: cc:start -> rasm -> ism -> daraja -> ball (ixtiyoriy) -> karta. Tugmalar: 🎨 boshqa rang, 📥 aniq fayl, 📤 ulashish."""
import io, math, random, time, asyncio, logging
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from result_cards import F, clean

logger = logging.getLogger(__name__)
W, H = 1080, 1350
LEVELS = ('A+', 'A', 'B+', 'B', 'C+')
THEMES = {
    'emerald':  {'bg1': (3, 38, 29), 'bg2': (12, 98, 70), 'dark': (2, 28, 21), 'accent': (45, 190, 140)},
    'midnight': {'bg1': (7, 13, 38), 'bg2': (28, 52, 112), 'dark': (4, 8, 26), 'accent': (110, 150, 255)},
}
GOLD_L, GOLD_M, GOLD_D = (255, 226, 130), (236, 176, 38), (150, 100, 14)
CREAM = (248, 243, 228)


# ------------------------------------------------------------------ chizish yordamchilari
def _lerp(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _grad_img(size, c_top, c_bot, angle=False):
    w, h = size
    g = Image.new('RGB', (1, h))
    px = g.load()
    for y in range(h): px[0, y] = _lerp(c_top, c_bot, y / max(1, h - 1))
    return g.resize((w, h))


def _text_w(d, s, f, sp=0): return sum(d.textlength(ch, font=f) for ch in s) + sp * max(0, len(s) - 1)


def _spaced(d, xy, s, f, fill, sp=0, anchor='mm'):
    x, y = xy; tw = _text_w(d, s, f, sp)
    cx = x - tw / 2 if anchor == 'mm' else x
    for ch in s:
        d.text((cx, y), ch, font=f, fill=fill, anchor='lm'); cx += d.textlength(ch, font=f) + sp


def _gold_text(canvas, xy, s, f, anchor='mm', shadow=True, emboss=True):
    """Oltin gradient + chuqurlik (soya va yorug' qirra) bilan matn."""
    x, y = xy
    tmp = Image.new('L', (W, H), 0); d = ImageDraw.Draw(tmp); d.text((x, y), s, font=f, fill=255, anchor=anchor)
    bb = tmp.getbbox()
    if not bb: return
    if shadow:
        sh = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sh.putalpha(tmp.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * .55)))
        canvas.alpha_composite(ImageChops.offset(sh, 4, 8))
    if emboss:
        dk = Image.new('RGBA', (W, H), GOLD_D + (255,)); dk.putalpha(ImageChops.offset(tmp, 0, 4)); canvas.alpha_composite(dk)
    gr = _grad_img((W, H), GOLD_L, GOLD_D)
    top, bot = bb[1], bb[3]
    g2 = Image.new('RGB', (W, H)); col = _grad_img((W, bot - top + 1), GOLD_L, GOLD_M); g2.paste(col, (0, top))
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0)); layer.paste(g2, (0, 0), tmp); canvas.alpha_composite(layer)
    hi = Image.new('RGBA', (W, H), (255, 255, 255, 0)); hi.putalpha(ImageChops.subtract(tmp, ImageChops.offset(tmp, 0, 3)).point(lambda v: int(v * .7)))
    canvas.alpha_composite(hi)


def _fit_font(d, s, size, maxw, w='b', mn=34):
    while size > mn and d.textlength(s, font=F(size, w)) > maxw: size -= 2
    return F(size, w)


def _coeffs(pa, pb):
    """Perspektiva koeffitsiyentlari (chiqish -> kirish). pa — chiqish burchaklari, pb — kirish burchaklari."""
    A = []; B = []
    for (x, y), (u, v) in zip(pa, pb):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); B.append(v)
    n = 8
    M = [A[i] + [B[i]] for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(M[r][i])); M[i], M[p] = M[p], M[i]
        for r in range(i + 1, n):
            k = M[r][i] / M[i][i]
            for c in range(i, n + 1): M[r][c] -= k * M[i][c]
    x = [0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))) / M[i][i]
    return x


def _background(th):
    bg = _grad_img((W, H), th['bg1'], th['bg2']).convert('RGBA')
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(glow)
    for i, (cx, cy, r, a) in enumerate(((820, 260, 520, 70), (160, 980, 480, 55))):
        for k in range(r, 0, -14): d.ellipse([cx - k, cy - k, cx + k, cy + k], fill=th['accent'] + (int(a * (1 - k / r) ** 1.8),))
    bg.alpha_composite(glow)
    rnd = random.Random(7); dust = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(dust)
    for _ in range(70):
        x, y, r = rnd.randint(30, W - 30), rnd.randint(30, H - 30), rnd.choice((2, 3, 4, 6))
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD_L + (rnd.randint(40, 120),))
    bg.alpha_composite(dust.filter(ImageFilter.GaussianBlur(1.2)))
    vig = Image.new('L', (W, H), 0); vd = ImageDraw.Draw(vig)
    vd.rectangle([0, 0, W, H], fill=170); vd.ellipse([-260, -200, W + 260, H + 200], fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(120))
    shade = Image.new('RGBA', (W, H), th['dark'] + (255,)); shade.putalpha(vig); bg.alpha_composite(shade)
    return bg


def _frame(canvas):
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([26, 26, W - 26, H - 26], radius=34, outline=GOLD_M + (255,), width=3)
    d.rounded_rectangle([40, 40, W - 40, H - 40], radius=26, outline=GOLD_M + (110,), width=1)
    for x, y in ((40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)):
        d.polygon([(x, y - 12), (x + 12, y), (x, y + 12), (x - 12, y)], fill=GOLD_L + (255,))


def _plate(canvas, cert, th):
    """Sertifikat — perspektivada qiyshaygan, oltin qirrali, qalinlik va soya bilan (3D)."""
    cert = cert.convert('RGB'); cert.thumbnail((1500, 1500))
    pw = 700; ph = max(300, min(420, int(pw * cert.height / cert.width))); pw = min(pw, int(ph * cert.width / cert.height)) if ph == 420 else pw
    pad = 10
    src = Image.new('RGB', (pw + pad * 2, ph + pad * 2), GOLD_M); src.paste(cert.resize((pw, ph), Image.LANCZOS), (pad, pad))
    sw, sh = src.size
    cx, cy = W // 2, 384
    dest = [(cx - sw / 2 + 6, cy - sh / 2 - 22), (cx + sw / 2 - 6, cy - sh / 2 + 10), (cx + sw / 2 - 6, cy + sh / 2 - 12), (cx - sw / 2 + 6, cy + sh / 2 + 22)]
    co = _coeffs(dest, [(0, 0), (sw, 0), (sw, sh), (0, sh)])
    warped = src.convert('RGBA').transform((W, H), Image.PERSPECTIVE, co, Image.BICUBIC)
    mask = Image.new('L', src.size, 255).transform((W, H), Image.PERSPECTIVE, co, Image.BICUBIC)
    warped.putalpha(mask)
    # soya
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sm = mask.filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * .65))
    shadow.putalpha(sm); canvas.alpha_composite(ImageChops.offset(shadow, 18, 46))
    # qalinlik (ekstruziya)
    for i in range(16, 0, -1):
        edge = Image.new('RGBA', (W, H), _lerp(GOLD_D, (80, 52, 8), i / 16) + (255,)); edge.putalpha(mask)
        canvas.alpha_composite(ImageChops.offset(edge, int(i * .55), i))
    canvas.alpha_composite(warped)
    # yaltiroq (glyanets) va ichki ramka
    gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
    gd.polygon([(cx - sw / 2, cy - sh / 2 - 30), (cx - 40, cy - sh / 2 - 30), (cx - 220, cy + sh / 2 + 30), (cx - sw / 2, cy + sh / 2 + 30)], fill=(255, 255, 255, 46))
    gl = gl.filter(ImageFilter.GaussianBlur(10)); gl.putalpha(ImageChops.multiply(gl.getchannel('A'), mask)); canvas.alpha_composite(gl)


def _medal(canvas, cx, cy, level, th):
    S = 3; R = 150; box = (R * 2 + 120) * S
    m = Image.new('RGBA', (box, box), (0, 0, 0, 0)); d = ImageDraw.Draw(m); c = box // 2
    for i, r in enumerate(range(R * S + 30 * S, R * S - 1, -S // 2)):   # tashqi halqa: radial oltin
        t = 1 - (r - (R * S - 1)) / (30 * S + 1)
        d.ellipse([c - r, c - r, c + r, c + r], fill=_lerp(GOLD_D, GOLD_L, min(1, max(0, t * 0.9 + 0.05))) + (255,))
    r1 = R * S - 8 * S
    for r in range(r1, r1 - 22 * S, -S):
        t = (r1 - r) / (22 * S); d.ellipse([c - r, c - r, c + r, c + r], fill=_lerp(GOLD_L, GOLD_D, t) + (255,))
    r2 = r1 - 22 * S
    for r in range(r2, 0, -S):                                          # ichki disk
        t = 1 - r / r2; d.ellipse([c - r, c - r, c + r, c + r], fill=_lerp(th['bg2'], th['dark'], t * .9) + (255,))
    rr = r2 - 12 * S; d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=GOLD_M + (200,), width=2 * S)
    for k in range(48):                                                  # tishchalar (medal qirrasi)
        a = k * math.tau / 48; x1, y1 = c + math.cos(a) * (R * S + 28 * S), c + math.sin(a) * (R * S + 28 * S)
        d.ellipse([x1 - 3 * S, y1 - 3 * S, x1 + 3 * S, y1 + 3 * S], fill=GOLD_L + (255,))
    hl = Image.new('RGBA', (box, box), (0, 0, 0, 0)); hd = ImageDraw.Draw(hl)                  # yaltiroq nur
    hd.ellipse([c - R * S + 30 * S, c - R * S + 10 * S, c + 20 * S, c - 40 * S], fill=(255, 255, 255, 70))
    m.alpha_composite(hl.filter(ImageFilter.GaussianBlur(14 * S)))
    m = m.resize((box // S, box // S), Image.LANCZOS)
    sh = Image.new('RGBA', m.size, (0, 0, 0, 0)); sh.putalpha(m.getchannel('A').filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * .6)))
    ox, oy = cx - m.width // 2, cy - m.height // 2
    canvas.alpha_composite(sh, (ox + 10, oy + 30)); canvas.alpha_composite(m, (ox, oy))
    d2 = ImageDraw.Draw(canvas)
    f = F(160 if len(level) == 1 else 134, 'b')
    _gold_text(canvas, (cx, cy + 22), level, f)
    d2 = ImageDraw.Draw(canvas); _spaced(d2, (cx, cy - 78), 'DARAJA', F(24, 'm'), GOLD_L + (255,), sp=10)


def render(cert_bytes, name, level, score='', theme='emerald', bot=''):
    th = THEMES.get(theme, THEMES['emerald']); name = clean(name).strip(); level = level if level in LEVELS else 'B'
    canvas = _background(th); _frame(canvas)
    d = ImageDraw.Draw(canvas)
    _spaced(d, (W // 2, 96), 'MILLIY SERTIFIKAT NATIJASI', F(30, 'm'), GOLD_L + (255,), sp=9)
    d.line([(W // 2 - 90, 132), (W // 2 + 90, 132)], fill=GOLD_M + (255,), width=2)
    cert = Image.open(io.BytesIO(cert_bytes))
    _plate(canvas, cert, th)
    _medal(canvas, W // 2, 864, level, th)
    d = ImageDraw.Draw(canvas)
    f = _fit_font(d, name, 84, W - 160, 'b'); _gold_text(canvas, (W // 2, 1102), name, f)
    d = ImageDraw.Draw(canvas)
    sub = ('Ball: %s  •  ' % clean(score) if score else '') + 'Dekabr 2026'
    d.text((W // 2, 1162), sub, font=F(36, 'm'), fill=CREAM + (235,), anchor='mm')
    link = 't.me/%s' % bot if bot else 't.me/Esse_baholovchi_bot'
    d.text((W // 2, 1212), 'Sertifikatingizni ham chiroyli qiling', font=F(26, 'r'), fill=CREAM + (200,), anchor='mm')
    fl = F(40, 'b'); tw = d.textlength(link, font=fl); px, py = W // 2 - tw / 2 - 40, 1236
    pill = Image.new('RGBA', (W, H), (0, 0, 0, 0)); pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle([px, py, px + tw + 80, py + 64], radius=32, fill=(0, 0, 0, 120), outline=GOLD_M + (255,), width=3)
    canvas.alpha_composite(pill.filter(ImageFilter.GaussianBlur(0.6)))
    d = ImageDraw.Draw(canvas); d.text((W // 2, py + 32), link, font=fl, fill=GOLD_L + (255,), anchor='mm')
    out = io.BytesIO(); canvas.convert('RGB').save(out, 'PNG', optimize=True)
    return out.getvalue()


