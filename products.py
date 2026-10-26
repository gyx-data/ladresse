"""Articles achetables de la supérette : chaque produit du catalogue (shop.CATALOG) est modélisé (bouteilles,
cannettes, briques, plaquettes...) avec un emballage imprimé dessiné d'après son nom, posé sur un présentoir.

Repère local d'un présentoir : origine au centre du plateau, façade des produits vers +z local, tourné de `rot`
degrés (même convention que room_builder) ; emprise ~0,26 x 0,44 m.
"""
import math

from PIL import Image, ImageDraw

import typography as T
from room_builder import _local, _ring
from texture_generator import textures

CHROME = (0.82, 0.82, 0.85)


# ---------------------------------------------------------------------------
# Emballages imprimés (PIL)
# ---------------------------------------------------------------------------
def _text(d, box, text, fg, px, bold=True):
    """Texte centré dans box, réduit jusqu'à tenir en largeur."""
    x0, y0, x1, y1 = box
    while px > 8:
        if T.text_width(text, "sans", px, bold) <= (x1 - x0) * 0.94:
            break
        px -= 2
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), text, font=T.pil_font("sans", px, bold), fill=fg, anchor="mm")


def _pack(name, size, draw):
    key = "_produit_" + name
    if key not in textures.images:
        img = Image.new("RGB", size, (255, 255, 255))
        draw(img, ImageDraw.Draw(img))
        textures.images[key] = img
    return key


def _tex_piles():
    def draw(img, d):
        w, h = img.size
        for y in range(h):
            k = y / h
            d.line([(0, y), (w, y)], fill=(int(20 + 30 * k), int(20 + 25 * k), int(24 + 20 * k)))
        d.rectangle((0, 0, w, 44), fill=(230, 180, 20))
        _text(d, (0, 0, w, 44), "ALCALINE", (20, 20, 20), 30)
        d.ellipse((w / 2 - 8, 52, w / 2 + 8, 68), fill=(60, 60, 60))           # trou de suspension
        _text(d, (0, h - 70, w, h - 30), "AA  x4", (255, 210, 40), 40)
        _text(d, (0, h - 32, w, h - 6), "LONGUE DURÉE", (220, 220, 220), 18)
    return _pack("piles", (160, 256), draw)


def _tex_batterie():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(28, 30, 36))
        d.rectangle((0, 0, w, 40), fill=(0, 150, 200))
        _text(d, (0, 0, w, 40), "POWERBANK", (255, 255, 255), 26)
        d.rounded_rectangle((w * 0.3, 60, w * 0.7, 170), 10, outline=(200, 200, 210), width=5)
        d.rectangle((w * 0.36, 100, w * 0.64, 160), fill=(80, 220, 120))
        _text(d, (0, 180, w, 220), "5000 mAh", (255, 255, 255), 30)
        _text(d, (0, 220, w, 250), "USB-C · 2 ports", (170, 180, 190), 16)
    return _pack("batterie", (160, 256), draw)


def _tex_bougies():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(245, 240, 228))
        d.rectangle((0, h - 70, w, h), fill=(140, 30, 40))
        for k in range(5):
            cx = 30 + k * (w - 60) / 4
            d.ellipse((cx - 18, 40, cx + 18, 76), fill=(190, 190, 195), outline=(120, 120, 125), width=2)
            d.ellipse((cx - 13, 44, cx + 13, 72), fill=(250, 248, 240))
            d.polygon([(cx, 18), (cx - 6, 40), (cx + 6, 40)], fill=(255, 170, 40))
        _text(d, (0, 90, w, 140), "BOUGIES", (110, 30, 36), 40)
        _text(d, (0, 140, w, 170), "chauffe-plat", (90, 70, 60), 22, bold=False)
        _text(d, (0, h - 70, w, h), "x10 · 4 h", (255, 255, 255), 30)
    return _pack("bougies", (256, 256), draw)


def _tex_pansements():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(250, 250, 250))
        d.rectangle((0, 0, w, 50), fill=(0, 120, 70))
        _text(d, (0, 0, w, 50), "PHARMA+", (255, 255, 255), 28)
        cx, cy = w / 2, 120
        d.rectangle((cx - 14, cy - 44, cx + 14, cy + 44), fill=(210, 30, 40))
        d.rectangle((cx - 44, cy - 14, cx + 44, cy + 14), fill=(210, 30, 40))
        _text(d, (0, 175, w, 215), "PANSEMENTS", (40, 40, 40), 30)
        _text(d, (0, 215, w, 245), "assortis · x20", (90, 90, 90), 20, bold=False)
    return _pack("pansements", (256, 256), draw)


def _tex_sel():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(30, 80, 160))
        d.rectangle((0, h * 0.36, w, h * 0.7), fill=(250, 250, 252))
        _text(d, (0, h * 0.36, w, h * 0.53), "GROS SEL", (30, 80, 160), 44)
        _text(d, (0, h * 0.53, w, h * 0.7), "de mer · 1 kg", (60, 90, 140), 26, bold=False)
        for k in range(9):                                                        # vagues
            y = 20 + k * 6
            d.arc((k * 30 - 20, y, k * 30 + 40, y + 30), 200, 340, fill=(130, 180, 240), width=3)
        _text(d, (0, h * 0.75, w, h * 0.95), "LA SALINE", (255, 255, 255), 28)
    return _pack("sel", (512, 256), draw)


def _tex_barre():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(110, 40, 20))
        d.polygon([(0, 0), (w * 0.35, 0), (w * 0.25, h), (0, h)], fill=(220, 160, 40))
        _text(d, (w * 0.3, 0, w, h * 0.6), "CHOCO", (255, 230, 180), 60)
        _text(d, (w * 0.3, h * 0.55, w, h), "caramel", (240, 200, 120), 40, bold=False)
    return _pack("barre", (512, 128), draw)


def _tex_eau():
    def draw(img, d):
        w, h = img.size
        for x in range(w):
            k = x / w
            d.line([(x, 0), (x, h)], fill=(int(40 + 60 * k), int(120 + 60 * k), int(200 + 40 * k)))
        _text(d, (0, 0, w, h * 0.6), "SOURCE DES ALPES", (255, 255, 255), 44)
        _text(d, (0, h * 0.55, w, h), "eau minérale · 50 cl", (230, 240, 255), 28, bold=False)
        for k in range(4):
            d.polygon([(40 + k * 120, h - 6), (80 + k * 120, h - 50), (120 + k * 120, h - 6)], fill=(230, 245, 255))
    return _pack("eau", (512, 128), draw)


def _tex_energisant():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(20, 60, 160))
        d.rectangle((0, h * 0.12, w, h * 0.22), fill=(200, 205, 215))
        d.rectangle((0, h * 0.78, w, h * 0.88), fill=(200, 205, 215))
        for k in range(2):
            ox = k * w / 2 + 40
            d.polygon([(ox + 60, 50), (ox + 20, 140), (ox + 55, 140), (ox + 35, 210), (ox + 100, 110), (ox + 65, 110), (ox + 90, 50)],
                      fill=(255, 210, 0))
            _text(d, (ox + 100, 70, ox + 230, 120), "VOLT", (255, 255, 255), 44)
            _text(d, (ox + 100, 120, ox + 230, 170), "energy", (190, 210, 255), 30, bold=False)
    return _pack("energisant", (512, 256), draw)


def _tex_journal():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(236, 233, 224))
        d.rectangle((0, 0, w, 58), fill=(0, 82, 150))
        _text(d, (0, 0, w, 58), "Nice-Matin", (255, 255, 255), 44)
        _text(d, (10, 64, w - 10, 110), "MONT-BORON : UNE TROISIÈME", (20, 20, 20), 26)
        _text(d, (10, 104, w - 10, 140), "DISPARITION RUE DES LILAS", (20, 20, 20), 26)
        d.rectangle((14, 150, w * 0.55, 260), fill=(120, 118, 112))                # photo
        for k in range(14):
            y = 152 + k * 8
            d.line([(w * 0.6, y), (w - 14, y)], fill=(130, 128, 122), width=3)
        for k in range(16):
            y = 272 + k * 8
            d.line([(14, y), (w - 14, y)], fill=(140, 138, 132), width=3)
    return _pack("journal", (256, 400), draw)


def _tex_pates():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(20, 70, 150))
        d.ellipse((w * 0.1, h * 0.28, w * 0.9, h * 0.72), fill=(250, 220, 110))       # fenêtre sur les pâtes
        for k in range(14):
            cx = w * 0.2 + (k % 5) * w * 0.15
            cy = h * 0.36 + (k // 5) * h * 0.11
            d.arc((cx - 14, cy - 12, cx + 14, cy + 12), 30, 300, fill=(200, 150, 40), width=7)
        _text(d, (0, 0, w, h * 0.26), "Pasta Bella", (255, 255, 255), 34)
        _text(d, (0, h * 0.74, w, h * 0.9), "COQUILLETTES", (255, 230, 120), 30)
        _text(d, (0, h * 0.88, w, h), "500 g", (255, 255, 255), 22)
    return _pack("pates", (256, 384), draw)


def _tex_lait():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(250, 250, 252))
        d.rectangle((0, h * 0.62, w, h), fill=(40, 110, 200))
        d.polygon([(0, h * 0.62), (w * 0.3, h * 0.5), (w * 0.6, h * 0.6), (w, h * 0.48), (w, h * 0.62)], fill=(80, 160, 70))
        _text(d, (0, h * 0.05, w, h * 0.2), "Lait des Alpes", (40, 90, 170), 30)
        _text(d, (0, h * 0.22, w, h * 0.38), "DEMI-ÉCRÉMÉ", (20, 60, 140), 32)
        _text(d, (0, h * 0.72, w, h * 0.9), "1 L", (255, 255, 255), 56)
    return _pack("lait", (256, 512), draw)


def _tex_baguette():
    def draw(img, d):
        w, h = img.size
        for y in range(h):
            k = 0.5 + 0.5 * math.sin(y / h * math.pi)
            d.line([(0, y), (w, y)], fill=(int(170 + 50 * k), int(110 + 50 * k), int(40 + 30 * k)))
        for k in range(5):                                                          # grignes
            y = 30 + k * (h - 60) / 4
            d.line([(w * 0.2, y), (w * 0.8, y + 30)], fill=(240, 210, 150), width=10)
    return _pack("baguette", (128, 512), draw)


def _tex_cafe():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(60, 30, 20))
        d.rectangle((0, h * 0.7, w, h), fill=(180, 30, 40))
        d.ellipse((w * 0.3, h * 0.25, w * 0.7, h * 0.55), fill=(110, 60, 30))
        d.line([(w * 0.5, h * 0.27), (w * 0.47, h * 0.53)], fill=(60, 30, 20), width=6)
        _text(d, (0, 0, w, h * 0.22), "Café Noir", (240, 210, 160), 34)
        _text(d, (0, h * 0.56, w, h * 0.7), "MOULU · 250 g", (230, 200, 150), 24)
        _text(d, (0, h * 0.72, w, h * 0.95), "PUR ARABICA", (255, 255, 255), 26)
    return _pack("cafe", (256, 384), draw)


def _tex_pizza():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(180, 30, 30))
        cx, cy, r = w / 2, h * 0.55, w * 0.36
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(215, 150, 70))
        d.ellipse((cx - r * 0.88, cy - r * 0.88, cx + r * 0.88, cy + r * 0.88), fill=(250, 220, 130))
        for k, (dx, dy) in enumerate(((-0.4, -0.3), (0.3, -0.4), (0.5, 0.2), (-0.2, 0.4), (0.0, 0.0), (-0.55, 0.15), (0.2, 0.55))):
            px, py = cx + dx * r, cy + dy * r
            d.ellipse((px - 14, py - 10, px + 14, py + 10), fill=(255, 245, 200) if k % 2 else (230, 190, 80))
        _text(d, (0, 0, w, h * 0.16), "PIZZA 4 FROMAGES", (255, 255, 255), 34)
        _text(d, (0, h * 0.9, w, h), "surgelé · 400 g", (255, 220, 200), 20, bold=False)
    return _pack("pizza", (384, 384), draw)


def _tex_socca():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(245, 230, 190))
        d.ellipse((w * 0.08, h * 0.2, w * 0.55, h * 0.9), fill=(220, 160, 60), outline=(150, 90, 30), width=4)
        for k in range(12):
            a = k * 0.52
            px, py = w * 0.315 + math.cos(a) * w * 0.15, h * 0.55 + math.sin(a) * h * 0.22
            d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=(120, 70, 25))
        _text(d, (w * 0.55, h * 0.15, w, h * 0.5), "SOCCA", (160, 60, 20), 48)
        _text(d, (w * 0.55, h * 0.5, w, h * 0.8), "de Nice", (110, 70, 40), 30, bold=False)
    return _pack("socca", (384, 256), draw)


def _tex_huile():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(240, 232, 200))
        d.rectangle((0, 0, w, 12), fill=(150, 120, 40))
        d.rectangle((0, h - 12, w, h), fill=(150, 120, 40))
        for k in range(6):                                                          # rameau d'olivier
            x = w * 0.25 + k * 18
            d.ellipse((x, h * 0.35 + (k % 2) * 16, x + 26, h * 0.35 + (k % 2) * 16 + 12), fill=(90, 110, 40))
            d.ellipse((x + 6, h * 0.55, x + 18, h * 0.55 + 16), fill=(50, 50, 30))
        _text(d, (w * 0.45, h * 0.1, w, h * 0.45), "HUILE D'OLIVE", (60, 70, 20), 34)
        _text(d, (w * 0.45, h * 0.45, w, h * 0.7), "de Nice AOP", (120, 90, 30), 28, bold=False)
        _text(d, (w * 0.45, h * 0.7, w, h * 0.9), "50 cl", (60, 70, 20), 26)
    return _pack("huile", (512, 192), draw)


# ---------------------------------------------------------------------------
# Géométrie
# ---------------------------------------------------------------------------
class _Frame:
    """Repère local du présentoir : (lx, ly, lz) -> monde."""

    def __init__(self, b, x, y, z, rot):
        self.b, self.x, self.y, self.z, self.rot = b, x, y, z, rot

    def p(self, lx, ly, lz):
        wx, wz = _local(self.x, self.z, self.rot, lx, lz)
        return (wx, self.y + ly, wz)

    def front(self, tex, lx, ly, lz, w, h, col=(1, 1, 1), lean=0.0):
        """Face imprimée tournée vers +z local (centre bas en lx, ly, lz)."""
        n = (math.sin(math.radians(self.rot)), 0.0, math.cos(math.radians(self.rot)))
        # vu de face (regard vers -z local), la gauche du lecteur est +x local : u part de +x
        a, bq = self.p(lx + w / 2, ly, lz), self.p(lx - w / 2, ly, lz)
        c, d = self.p(lx - w / 2, ly + h, lz - lean), self.p(lx + w / 2, ly + h, lz - lean)
        self.b.quad(tex, a, bq, c, d, n, col, tile=(w, h))

    def top(self, tex, lx, ly, lz, w, d, col=(1, 1, 1)):
        """Face imprimée horizontale (dessus d'une boîte), haut de l'image vers -z local."""
        a, bq = self.p(lx + w / 2, ly, lz + d / 2), self.p(lx - w / 2, ly, lz + d / 2)
        c, e = self.p(lx - w / 2, ly, lz - d / 2), self.p(lx + w / 2, ly, lz - d / 2)
        self.b.quad(tex, a, bq, c, e, (0, 1, 0), col, tile=(w, d))

    def box(self, tex, lx, ly, lz, w, h, d, col, front_tex=None):
        cx, cz = _local(self.x, self.z, self.rot, lx, lz)
        self.b.obox(tex, cx, self.y + ly, cz, w, h, d, self.rot, col)
        if front_tex:
            self.front(front_tex, lx, ly + 0.002, lz + d / 2 + 0.002, w * 0.98, h * 0.98)

    def cyl(self, tex, lx, ly, lz, r, h, col, seg=16):
        cx, cz = _local(self.x, self.z, self.rot, lx, lz)
        self.b.cyl(tex, cx, self.y + ly, cz, r, h, seg, col)

    def lathe(self, tex, lx, lz, prof, col, seg=20):
        """Solide de révolution vertical : prof = [(hauteur, rayon), ...] de bas en haut."""
        cx, cz = _local(self.x, self.z, self.rot, lx, lz)
        rings = [_ring(cx, cz, self.y + y, r, r, 0.0, 2.0, seg=seg) for (y, r) in prof]
        self.b.loft(tex, rings, col)
        self.b.cap(tex, rings[0], (0, -1, 0), col)
        if prof[-1][1] > 0.003:
            self.b.cap(tex, rings[-1], (0, 1, 0), col)


def _bottle(f, lx, lz, height, r, glass_col, label_tex, cap_col, neck=0.32):
    """Bouteille : corps, épaule, goulot (verre/plastique teinté), étiquette, bouchon."""
    hb = height * (1 - neck)
    prof = [(0.0, r * 0.92), (0.01, r), (hb * 0.95, r), (hb, r * 0.95), (hb + height * neck * 0.4, r * 0.45),
            (height * 0.95, r * 0.38), (height, r * 0.38)]
    f.lathe("vitre", lx, lz, prof, glass_col)
    # étiquette : bande cylindrique légèrement plus large que le corps
    cx, cz = _local(f.x, f.z, f.rot, lx, lz)
    band = [_ring(cx, cz, f.y + y, r * 1.01, r * 1.01, f.rot, 2.0, seg=20) for y in (hb * 0.3, hb * 0.75)]
    f.b.loft(label_tex, band, (1, 1, 1), tile=(2 * math.pi * r * 1.01, hb * 0.45))
    f.cyl("metal", lx, height, lz, r * 0.42, 0.018, cap_col, seg=12)


def build(b, art_id, x, y, z, rot, floor=False):
    """Présentoir + produits `art_id` (id du catalogue) au point (x, y, z) : y = dessus du plateau."""
    f = _Frame(b, x, y, z, rot)
    # présentoir grillagé fixé au rayon : plateau, rebord avant, deux équerres
    f.box("metal", 0.0, -0.02, 0.0, 0.42, 0.02, 0.26, (0.55, 0.56, 0.6))
    f.box("metal", 0.0, 0.0, 0.125, 0.42, 0.04, 0.01, (0.6, 0.62, 0.66))
    if floor:
        # présentoir sur pied (devant le mur réfrigéré : rien à quoi l'accrocher)
        f.box("metal", 0.0, -y + 0.02, 0.0, 0.04, y - 0.04, 0.04, (0.45, 0.46, 0.5))
        f.box("metal", 0.0, -y, 0.0, 0.34, 0.02, 0.24, (0.4, 0.41, 0.45))
    else:
        for sx in (-0.2, 0.2):
            f.box("metal", sx, -0.16, -0.1, 0.012, 0.14, 0.06, (0.45, 0.46, 0.5))
    fn = _BUILDERS.get(art_id)
    if fn:
        fn(f)


def _piles(f):
    tex = _tex_piles()
    for k, lx in enumerate((-0.13, 0.0, 0.13)):
        f.box("papier", lx, 0.0, 0.02, 0.095, 0.15, 0.006, (0.15, 0.15, 0.17), front_tex=tex)
        for j in range(4):                                                         # piles sous blister
            f.cyl("metal", lx - 0.03 + j * 0.02, 0.02, 0.035, 0.007, 0.05, (0.95, 0.75, 0.1), seg=10)


def _batterie(f):
    tex = _tex_batterie()
    for lx in (-0.13, 0.0, 0.13):
        f.box("papier", lx, 0.0, 0.0, 0.1, 0.16, 0.035, (0.12, 0.13, 0.16), front_tex=tex)


def _bougies(f):
    tex = _tex_bougies()
    f.box("papier", -0.08, 0.0, 0.0, 0.16, 0.08, 0.1, (0.95, 0.92, 0.85), front_tex=tex)
    for j in range(3):                                                             # chauffe-plats en vrac
        for k in range(2):
            lx, lz = 0.07 + j * 0.042, -0.03 + k * 0.045
            f.cyl("metal", lx, 0.0, lz, 0.019, 0.016, (0.8, 0.8, 0.82), seg=14)
            f.cyl("papier", lx, 0.016, lz, 0.016, 0.002, (0.98, 0.97, 0.92), seg=14)


def _pansements(f):
    tex = _tex_pansements()
    for k, lx in enumerate((-0.13, 0.0, 0.13)):
        f.box("papier", lx, 0.0, 0.0, 0.1, 0.07, 0.045, (0.96, 0.96, 0.96), front_tex=tex)
        f.box("papier", lx, 0.07, 0.0, 0.1, 0.07, 0.045, (0.96, 0.96, 0.96), front_tex=tex)


def _sel(f):
    tex = _tex_sel()
    for lx in (-0.1, 0.1):
        cx, cz = _local(f.x, f.z, f.rot, lx, 0.0)
        rings = [_ring(cx, cz, f.y + yy, 0.048, 0.048, f.rot, 2.0, seg=24) for yy in (0.0, 0.17)]
        f.b.loft(tex, rings, (1, 1, 1), tile=(2 * math.pi * 0.048, 0.17))
        f.b.cap("metal", rings[1], (0, 1, 0), (0.85, 0.85, 0.9))
        f.b.cap("papier", rings[0], (0, -1, 0), (0.2, 0.4, 0.75))


def _barre(f):
    tex = _tex_barre()
    for k in range(4):
        for j in range(2):
            f.box("papier", -0.07 + j * 0.14, k * 0.022, 0.0, 0.13, 0.02, 0.035, (0.4, 0.15, 0.08), front_tex=tex)


def _eau(f):
    tex = _tex_eau()
    for j, lx in enumerate((-0.15, -0.05, 0.05, 0.15)):
        _bottle(f, lx, 0.02 if j % 2 else -0.02, 0.21, 0.032, (0.75, 0.88, 1.0), tex, (0.2, 0.5, 0.9))


def _energisant(f):
    tex = _tex_energisant()
    for j, lx in enumerate((-0.15, -0.075, 0.0, 0.075, 0.15)):
        cx, cz = _local(f.x, f.z, f.rot, lx, 0.02 * (j % 2))
        prof = [(0.0, 0.026), (0.008, 0.032), (0.105, 0.032), (0.115, 0.027)]
        rings = [_ring(cx, cz, f.y + yy, r, r, f.rot, 2.0, seg=20) for (yy, r) in prof]
        f.b.loft("metal", [rings[0], rings[1]], CHROME)
        f.b.loft(tex, [rings[1], rings[2]], (1, 1, 1), tile=(2 * math.pi * 0.032, 0.097))
        f.b.loft("metal", [rings[2], rings[3]], CHROME)
        f.b.cap("metal", rings[3], (0, 1, 0), CHROME)


def _journal(f):
    tex = _tex_journal()
    for lx in (-0.1, 0.1):                                                         # deux piles de journaux pliés
        for k in range(4):
            f.box("papier", lx, k * 0.008, 0.0, 0.16, 0.008, 0.245, (0.9, 0.89, 0.85))
        f.top(tex, lx, 0.0325, 0.0, 0.156, 0.24)


def _pates(f):
    tex = _tex_pates()
    for lx in (-0.12, 0.0, 0.12):
        f.box("papier", lx, 0.0, 0.0, 0.1, 0.16, 0.05, (0.15, 0.3, 0.6), front_tex=tex)


def _lait(f):
    tex = _tex_lait()
    for lx in (-0.13, -0.045, 0.045, 0.13):
        f.box("papier", lx, 0.0, 0.0, 0.07, 0.19, 0.07, (0.96, 0.96, 0.98), front_tex=tex)
        # sommet en toit (brique pignon)
        a, bq = f.p(lx - 0.035, 0.19, 0.035), f.p(lx + 0.035, 0.19, 0.035)
        c, d = f.p(lx + 0.035, 0.19, -0.035), f.p(lx - 0.035, 0.19, -0.035)
        r1, r2 = f.p(lx - 0.035, 0.225, 0.0), f.p(lx + 0.035, 0.225, 0.0)
        n_f = (math.sin(math.radians(f.rot)) * 0.7, 0.7, math.cos(math.radians(f.rot)) * 0.7)
        n_b = (-n_f[0], 0.7, -n_f[2])
        f.b.quad("papier", a, bq, r2, r1, n_f, (0.95, 0.95, 0.97))
        f.b.quad("papier", c, d, r1, r2, n_b, (0.95, 0.95, 0.97))
        f.b.tri("papier", a, r1, d, (-math.cos(math.radians(f.rot)), 0, math.sin(math.radians(f.rot))), (0.9, 0.9, 0.92))
        f.b.tri("papier", bq, c, r2, (math.cos(math.radians(f.rot)), 0, -math.sin(math.radians(f.rot))), (0.9, 0.9, 0.92))


def _baguette(f):
    tex = _tex_baguette()
    # panier en osier, baguettes debout
    cx, cz = _local(f.x, f.z, f.rot, 0.0, 0.0)
    basket = [_ring(cx, cz, f.y + yy, r, r * 0.6, f.rot, 2.4, seg=24) for (yy, r) in ((0.0, 0.15), (0.12, 0.19))]
    f.b.loft("planches", basket, (0.75, 0.55, 0.3))
    f.b.cap("planches", basket[0], (0, 1, 0), (0.6, 0.45, 0.25))
    for j, (lx, lz, lean) in enumerate(((-0.1, -0.02, 0.0), (-0.035, 0.03, 0.0), (0.03, -0.03, 0.0), (0.1, 0.02, 0.0))):
        bx, bz = _local(f.x, f.z, f.rot, lx, lz)
        prof = [(0.0, 0.012), (0.03, 0.026), (0.3, 0.03), (0.55, 0.026), (0.6, 0.008)]
        rings = [_ring(bx, bz, f.y + 0.02 + yy, r, r * 0.85, f.rot + j * 40, 2.0, seg=14) for (yy, r) in prof]
        f.b.loft(tex, rings, (1, 1, 1), tile=(0.17, 0.6))


def _cafe(f):
    tex = _tex_cafe()
    for lx in (-0.12, 0.0, 0.12):
        f.box("papier", lx, 0.0, 0.0, 0.085, 0.13, 0.05, (0.25, 0.13, 0.08), front_tex=tex)


def _pizza(f):
    tex = _tex_pizza()
    for k in range(3):
        f.box("papier", 0.0, k * 0.032, 0.0, 0.25, 0.03, 0.25, (0.7, 0.15, 0.12))
    f.top(tex, 0.0, 0.097, 0.0, 0.245, 0.245)


def _socca(f):
    tex = _tex_socca()
    for k in range(3):
        f.box("papier", 0.0, k * 0.022, 0.0, 0.24, 0.02, 0.16, (0.9, 0.8, 0.55))
    f.top(tex, 0.0, 0.067, 0.0, 0.235, 0.155)


def _huile(f):
    tex = _tex_huile()
    for lx in (-0.12, 0.0, 0.12):
        _bottle(f, lx, 0.0, 0.29, 0.034, (0.35, 0.45, 0.12), tex, (0.75, 0.6, 0.15), neck=0.38)


_BUILDERS = {
    "piles": _piles, "batterie": _batterie, "bougies": _bougies, "pansements": _pansements, "sel": _sel,
    "barre": _barre, "eau": _eau, "energisant": _energisant, "journal": _journal, "pates": _pates, "lait": _lait,
    "baguette": _baguette, "cafe": _cafe, "pizza_surg": _pizza, "socca_pack": _socca, "huile": _huile,
}
