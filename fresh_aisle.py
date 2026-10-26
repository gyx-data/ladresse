"""Rayons de la supérette entièrement modelés (décor, articles non achetables) :

  * mur réfrigéré « FRAIS » : modules à portes vitrées (cadres alu, poignées chromées, étagères éclairées,
    rails de prix avec étiquettes, socle ventilé, bandeau lumineux) remplis de produits frais modelés
    (lait, yaourts, fromages, beurre, jambon, œufs, jus, desserts, pizzas fraîches, salades) ;
  * épicerie des gondoles : céréales, pâtes, conserves, bocaux, biscuits, chips, sauces, boissons,
    chacun avec un emballage illustré dessiné à la volée (marques fictives) ;
  * étal de fruits et légumes et cagettes de la vitrine : vrais modèles 3D Poly Haven (CC0, fetch_models.py)
    posés sur des tas de fruits modelés.
"""
import math

from PIL import ImageDraw

from products import _Frame, _bottle, _pack, _text
from room_builder import _local, _ring

WHITE = (0.94, 0.95, 0.97)
ALU = (0.78, 0.8, 0.84)
CHROME = (0.88, 0.89, 0.92)
DARK = (0.16, 0.17, 0.19)


# =============================================================================
# Emballages illustrés
# =============================================================================
def _grad(d, w, h, c0, c1):
    for y in range(h):
        k = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * k) for i in range(3)))


def _motif(d, kind, w, h, accent):
    cx, cy = w / 2, h * 0.5
    r = min(w, h) * 0.2
    if kind == "fruit":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
        d.ellipse((cx - r * 0.45, cy - r * 0.6, cx - r * 0.1, cy - r * 0.25), fill=(255, 255, 255))
        d.polygon([(cx, cy - r), (cx + r * 0.6, cy - r * 1.5), (cx + r * 0.2, cy - r * 0.9)], fill=(60, 150, 50))
    elif kind == "spots":
        for (x, y, s) in ((0.2, 0.42, 0.14), (0.7, 0.5, 0.18), (0.45, 0.62, 0.1), (0.82, 0.3, 0.08)):
            d.ellipse((w * x - w * s, h * y - w * s * 0.7, w * x + w * s, h * y + w * s * 0.7), fill=(25, 25, 30))
    elif kind == "bowl":
        d.chord((cx - r * 1.5, cy - r * 0.6, cx + r * 1.5, cy + r * 1.4), 0, 180, fill=(250, 250, 250))
        for k in range(9):
            x = cx - r * 1.1 + k * r * 0.28
            d.ellipse((x, cy + r * 0.1 - (k % 3) * 4, x + r * 0.35, cy + r * 0.35 - (k % 3) * 4), fill=accent)
    elif kind == "slices":
        for k in range(3):
            y = cy - r * 0.6 + k * r * 0.5
            d.ellipse((cx - r * 1.4, y, cx + r * 1.4, y + r * 0.7), fill=accent, outline=(255, 235, 235), width=3)
    elif kind == "eggs":
        for k in range(3):
            x = cx - r * 1.2 + k * r * 0.9
            d.ellipse((x, cy - r * 0.6, x + r * 0.75, cy + r * 0.45), fill=(245, 230, 205), outline=(200, 170, 130), width=2)
    elif kind == "cheese":
        d.polygon([(cx - r * 1.3, cy + r * 0.6), (cx + r * 1.3, cy + r * 0.6), (cx + r * 1.3, cy - r * 0.3), (cx - r * 1.3, cy + r * 0.1)],
                  fill=accent)
        for (x, y) in ((-0.6, 0.3), (0.2, 0.2), (0.8, 0.05), (-0.1, 0.45)):
            d.ellipse((cx + r * x - 6, cy + r * y - 5, cx + r * x + 6, cy + r * y + 5), fill=tuple(int(c * 0.8) for c in accent))
    elif kind == "wave":
        pts = [(x, cy + math.sin(x / w * math.pi * 3) * r * 0.5) for x in range(0, w + 8, 8)]
        d.line(pts, fill=accent, width=int(r * 0.5))
    elif kind == "leaf":
        for k, ang in enumerate((-30, 0, 30)):
            a = math.radians(ang - 90)
            x2, y2 = cx + math.cos(a) * r * 1.6, cy + math.sin(a) * r * 1.6
            d.line([(cx, cy + r * 0.6), (x2, y2)], fill=(40, 120, 40), width=int(r * 0.55))
    elif kind == "pasta":
        for k in range(7):
            x = cx - r * 1.2 + k * r * 0.4
            d.line([(x, cy - r), (x + r * 0.3, cy + r)], fill=accent, width=6)
    elif kind == "chips":
        for k in range(5):
            x, y = cx - r + (k % 3) * r * 0.8, cy - r * 0.5 + (k // 3) * r * 0.8
            d.ellipse((x - r * 0.45, y - r * 0.3, x + r * 0.45, y + r * 0.3), fill=accent, outline=(170, 110, 20), width=2)
    elif kind == "bubbles":
        for (x, y, s) in ((0.3, 0.45, 0.13), (0.62, 0.38, 0.09), (0.55, 0.58, 0.16), (0.78, 0.52, 0.07), (0.22, 0.6, 0.06)):
            d.ellipse((w * x - w * s, h * y - w * s, w * x + w * s, h * y + w * s), fill=(255, 255, 255), outline=accent, width=3)
    elif kind == "rolls":
        for k in range(3):
            x = cx - r * 1.5 + k * r * 1.05
            d.ellipse((x, cy - r * 0.55, x + r * 0.95, cy + r * 0.4), fill=(252, 252, 250), outline=(190, 200, 215), width=3)
            d.ellipse((x + r * 0.33, cy - r * 0.22, x + r * 0.62, cy + r * 0.08), fill=accent)
    elif kind == "sponge":
        for k in range(2):
            y = cy - r * 0.6 + k * r * 0.75
            d.rectangle((cx - r * 1.3, y, cx + r * 1.3, y + r * 0.42), fill=(250, 215, 50))
            d.rectangle((cx - r * 1.3, y + r * 0.42, cx + r * 1.3, y + r * 0.62), fill=accent)
    elif kind == "bulb":
        d.ellipse((cx - r * 0.9, cy - r * 1.1, cx + r * 0.9, cy + r * 0.5), fill=(255, 245, 190), outline=accent, width=3)
        for k in range(3):
            d.rectangle((cx - r * 0.38, cy + r * (0.45 + k * 0.22), cx + r * 0.38, cy + r * (0.58 + k * 0.22)), fill=(190, 190, 195))


def _art(key, size, bg, bg2, brand, name, sub="", motif=None, accent=(255, 210, 40), fg=(255, 255, 255), nutri=True):
    """Emballage générique : dégradé, pastille de marque, illustration, nom, poids, code-barres, Nutri-Score (alimentaire)."""
    def draw(img, d):
        w, h = img.size
        _grad(d, w, h, bg, bg2)
        d.rounded_rectangle((w * 0.08, h * 0.04, w * 0.92, h * 0.17), radius=int(h * 0.05), fill=(255, 255, 255))
        _text(d, (w * 0.1, h * 0.045, w * 0.9, h * 0.165), brand, bg, int(h * 0.09))
        if motif:
            _motif(d, motif, w, h, accent)
        _text(d, (w * 0.05, h * 0.68, w * 0.95, h * 0.82), name, fg, int(h * 0.1))
        if sub:
            _text(d, (w * 0.05, h * 0.82, w * 0.7, h * 0.93), sub, fg, int(h * 0.06), bold=False)
        for k in range(14):                                       # code-barres
            x = w * 0.74 + k * w * 0.014
            d.rectangle((x, h * 0.86, x + (2 if k % 3 else 1), h * 0.95), fill=(20, 20, 20))
        cols = [(0, 140, 70), (130, 190, 40), (250, 200, 0), (240, 130, 30), (220, 50, 30)] if nutri else []
        for k, c in enumerate(cols):                              # Nutri-Score
            x = w * 0.08 + k * w * 0.07
            d.rectangle((x, h * 0.955, x + w * 0.065, h * 0.99), fill=c)
    return _pack(key, size, draw)


# --- produits frais --------------------------------------------------------
def T_lait():
    return _art("frais_lait", (160, 256), (240, 244, 252), (205, 222, 245), "Prés d'Azur", "LAIT", "demi-écrémé 1 L", "spots",
                fg=(20, 60, 140))


def T_yaourt(flavor, col):
    return _art(f"frais_yaourt_{flavor}", (256, 128), col, tuple(int(c * 0.8) for c in col), "Douceur", flavor.upper(),
                "4 x 125 g", "fruit", accent=(255, 255, 255))


def T_fromage(name, col):
    return _art(f"frais_fromage_{name}", (256, 160), (250, 240, 200), (232, 205, 140), "Le Vieux Moulin", name.upper(), "250 g",
                "cheese", accent=col, fg=(110, 60, 20))


def T_beurre():
    return _art("frais_beurre", (256, 128), (240, 200, 60), (210, 160, 30), "Normandine", "BEURRE DOUX", "250 g", "wave",
                accent=(255, 240, 180), fg=(70, 40, 10))


def T_jambon():
    return _art("frais_jambon", (256, 160), (250, 250, 250), (225, 225, 230), "Maison Fabre", "JAMBON BLANC", "4 tranches",
                "slices", accent=(240, 160, 165), fg=(170, 30, 40))


def T_oeufs():
    return _art("frais_oeufs", (256, 128), (150, 110, 70), (120, 85, 50), "Ferme du Col", "12 ŒUFS", "plein air", "eggs")


def T_jus(name, c0, accent):
    return _art(f"frais_jus_{name}", (128, 256), c0, tuple(int(c * 0.75) for c in c0), "Soleil", f"PUR JUS {name.upper()}", "1 L",
                "fruit", accent=accent)


def T_dessert(name, col):
    return _art(f"frais_dessert_{name}", (256, 128), col, tuple(int(c * 0.7) for c in col), "Gourmandise", name.upper(), "4 x 100 g",
                "wave", accent=(250, 240, 220))


def T_pizza():
    return _art("frais_pizza", (256, 256), (180, 25, 25), (120, 10, 10), "Bella Napoli", "MARGHERITA", "fraîche 400 g", "fruit",
                accent=(240, 200, 80))


def T_salade():
    return _art("frais_salade", (192, 256), (120, 190, 80), (60, 140, 50), "Jardin Bio", "SALADE", "prête à l'emploi", "leaf")


def T_prix():
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(255, 255, 255))
        d.rectangle((0, 0, w * 0.32, h), fill=(255, 214, 0))
        _text(d, (0, 0, w * 0.32, h), "PROMO", (180, 20, 20), int(h * 0.36))
        _text(d, (w * 0.34, 0, w, h), "1,29 €", (20, 20, 30), int(h * 0.7))
    return _pack("frais_prix", (256, 64), draw)


# --- épicerie ---------------------------------------------------------------
EPICERIE = [
    ("cereales", (150, 220), (230, 120, 20), (200, 70, 10), "Croc'Matin", "CÉRÉALES", "375 g", "bowl", (240, 180, 60)),
    ("muesli", (150, 220), (90, 140, 60), (50, 100, 40), "Croc'Matin", "MUESLI", "500 g", "bowl", (200, 150, 90)),
    ("pates", (150, 220), (20, 70, 150), (10, 40, 100), "Pasta Bella", "PENNE", "500 g", "pasta", (240, 200, 90)),
    ("spaghetti", (110, 256), (200, 30, 40), (150, 15, 25), "Pasta Bella", "SPAGHETTI", "500 g", "pasta", (245, 210, 110)),
    ("biscuits", (220, 150), (120, 60, 30), (80, 35, 15), "Délices", "BISCUITS MIEL", "300 g", "wave", (240, 190, 70)),
    ("chips", (180, 230), (250, 200, 20), (230, 140, 0), "Crousti'Chips", "CHIPS NATURE", "150 g", "chips", (250, 225, 120)),
    ("riz", (150, 220), (240, 240, 240), (210, 210, 215), "Riz d'Or", "RIZ BASMATI", "1 kg", "wave", (230, 180, 40)),
    ("cafe", (150, 200), (60, 30, 20), (30, 15, 10), "Café Noir", "MOULU", "250 g", "wave", (200, 150, 90)),
]
CANS = [("petits_pois", (60, 140, 50), (120, 200, 80)), ("tomates", (190, 30, 30), (240, 80, 60)),
        ("haricots", (40, 100, 60), (90, 170, 90)), ("mais", (230, 190, 30), (250, 230, 90))]
JARS = [("confiture", (180, 20, 40), (230, 60, 80)), ("miel", (230, 160, 20), (250, 200, 60)), ("sauce", (200, 40, 20), (240, 90, 50))]
SODAS = [("cola", (150, 10, 10), (230, 30, 30)), ("limonade", (60, 160, 220), (200, 240, 255)), ("orange", (240, 120, 10), (255, 190, 60))]


# --- droguerie / bazar --------------------------------------------------------
BAZAR = {
    "lessive": [((40, 90, 190), (20, 50, 130), "Lavéclat", "LESSIVE", "40 lavages", (120, 200, 255)),
                ((230, 120, 20), (190, 70, 10), "Lavéclat", "LESSIVE COULEURS", "30 lavages", (255, 220, 120)),
                ((40, 150, 90), (20, 100, 60), "Lavéclat", "LESSIVE ÉCO", "35 lavages", (190, 250, 200))],
    "rouleaux": [((235, 240, 250), (190, 205, 230), "Douceur+", "PAPIER TOILETTE", "6 rouleaux", (120, 160, 220)),
                 ((250, 235, 240), (230, 190, 205), "Douceur+", "ESSUIE-TOUT", "4 rouleaux", (220, 120, 150))],
    "eponge": [((60, 150, 60), (30, 100, 40), "Maison Net", "ÉPONGES", "x 3", (40, 120, 40)),
               ((40, 110, 200), (20, 70, 150), "Maison Net", "ÉPONGES INOX", "x 2", (170, 175, 185))],
    "ampoule": [((250, 250, 250), (215, 220, 230), "Lumiled", "AMPOULE LED", "E27 · 9 W", (240, 180, 20)),
                ((30, 40, 60), (15, 20, 35), "Lumiled", "AMPOULE LED", "GU10 · 5 W", (250, 200, 40))],
    "spray": [((240, 240, 245), (200, 215, 235), "Maison Net", "NETTOYANT", "500 ml", (60, 140, 220)),
              ((250, 240, 200), (240, 210, 120), "Maison Net", "DÉGRAISSANT", "500 ml", (220, 140, 20))],
}
BAZAR_SIZE = {"lessive": (200, 256), "rouleaux": (256, 256), "eponge": (256, 160), "ampoule": (128, 224), "spray": (256, 128)}
BAZAR_MOTIF = {"lessive": "bubbles", "rouleaux": "rolls", "eponge": "sponge", "ampoule": "bulb", "spray": "bubbles"}


def _bazar_tex(kind, variant):
    lst = BAZAR[kind]
    c0, c1, brand, name, sub, acc = lst[variant % len(lst)]
    fg = (20, 40, 90) if sum(c0) > 600 else (255, 255, 255)
    return _art(f"bazar_{kind}_{variant % len(lst)}", BAZAR_SIZE[kind], c0, c1, brand, name, sub, BAZAR_MOTIF[kind],
                accent=acc, fg=fg, nutri=False), c0


def _epicerie_tex(i):
    k, size, c0, c1, brand, name, sub, motif, acc = EPICERIE[i % len(EPICERIE)]
    return _art("epi_" + k, size, c0, c1, brand, name, sub, motif, accent=acc), size


def _can_tex(name, c0, accent):
    return _art("conserve_" + name, (256, 128), c0, tuple(int(c * 0.75) for c in c0), "Potager", name.replace("_", " ").upper(),
                "400 g", "fruit", accent=accent)


def _jar_tex(name, c0, accent):
    return _art("bocal_" + name, (256, 128), (250, 245, 230), (230, 220, 200), "Mamie Rose", name.upper(), "370 g", "fruit",
                accent=accent, fg=c0)


def _soda_tex(name, c0, accent):
    return _art("soda_" + name, (256, 128), c0, tuple(int(c * 0.7) for c in c0), "Fizz", name.upper(), "1,5 L", "wave", accent=accent)


# =============================================================================
# Produits modelés (repère _Frame : façade vers +z local, y = dessus de l'étagère)
# =============================================================================
def _span(w, step):
    n = max(1, int(w // step))
    return [(-w / 2 + step * (k + 0.5)) * (w / (n * step)) for k in range(n)]


def milk(f, w):
    tex = T_lait()
    for lx in _span(w, 0.1):
        for lz in (-0.12, 0.0, 0.12):
            prof = [(0.0, 0.034), (0.01, 0.038), (0.17, 0.038), (0.2, 0.03), (0.235, 0.016), (0.25, 0.016)]
            f.lathe("papier", lx, lz, prof, (0.97, 0.97, 0.98), seg=14)
            f.cyl("metal", lx, 0.25, lz, 0.018, 0.02, (0.15, 0.35, 0.8), seg=10)
        # étiquette enroulée autour de la bouteille de devant (une vignette plate traversait le flacon arrondi)
        cx, cz = _local(f.x, f.z, f.rot, lx, 0.12)
        band = [_ring(cx, cz, f.y + y, 0.0395, 0.0395, f.rot + 90.0, 2.0, seg=14) for y in (0.04, 0.16)]
        f.b.loft(tex, band, (1, 1, 1), tile=(2 * math.pi * 0.0395, 0.12))


def yogurt(f, w, flavor, col):
    tex = T_yaourt(flavor, col)
    foil = tuple(min(1.0, c / 255 * 1.1) for c in col)
    for lx in _span(w, 0.15):
        for lz in (-0.1, 0.06):
            f.box("papier", lx, 0.0, lz, 0.135, 0.05, 0.135, (0.92, 0.9, 0.85), front_tex=tex)    # étui carton
            for dx in (-0.033, 0.033):
                for dz in (-0.033, 0.033):
                    f.lathe("papier", lx + dx, lz + dz, [(0.05, 0.026), (0.115, 0.031), (0.118, 0.031)], (0.98, 0.98, 0.98), seg=12)
                    f.cyl("metal", lx + dx, 0.118, lz + dz, 0.032, 0.003, foil, seg=12)


def cheese(f, w, k):
    names = (("Camembert", (240, 220, 160)), ("Emmental", (250, 220, 90)), ("Comté", (240, 200, 90)), ("Chèvre", (250, 250, 240)))
    name, col = names[k % len(names)]
    tex = T_fromage(name, col)
    if name == "Camembert":
        for lx in _span(w, 0.13):
            for lz in (-0.1, 0.05):
                for j in range(2):
                    cx, cz = _local(f.x, f.z, f.rot, lx, lz)
                    rings = [_ring(cx, cz, f.y + y, 0.056, 0.056, f.rot + 90.0, 2.0, seg=18) for y in (j * 0.045, j * 0.045 + 0.04)]
                    f.b.loft(tex, rings, (1, 1, 1), tile=(2 * math.pi * 0.056, 0.04))
                    f.b.cap("papier", rings[1], (0, 1, 0), (0.92, 0.84, 0.62))
    else:
        for lx in _span(w, 0.14):
            for lz in (-0.1, 0.04):
                f.box("papier", lx, 0.0, lz, 0.12, 0.06, 0.09, tuple(c / 255 for c in col), front_tex=tex)
                f.box("papier", lx, 0.06, lz, 0.12, 0.06, 0.09, tuple(c / 255 for c in col), front_tex=tex)


def butter_eggs(f, w):
    tb, te = T_beurre(), T_oeufs()
    half = w / 2
    for lx in _span(half, 0.1):
        for lz in (-0.1, 0.0, 0.1):
            f.box("papier", lx - half / 2, 0.0, lz, 0.085, 0.045, 0.085, (0.94, 0.8, 0.3), front_tex=tb)
    for lx in _span(half, 0.15):
        for j in range(2):
            ly = j * 0.07
            f.box("papier", lx + half / 2, ly, -0.02, 0.14, 0.06, 0.26, (0.62, 0.48, 0.32), front_tex=te)
            for a in (-0.035, 0.035):
                for b_ in (-0.09, 0.0, 0.09):
                    cx, cz = _local(f.x, f.z, f.rot, lx + half / 2 + a, -0.02 + b_)
                    f.b.sphere("papier", cx, f.y + ly + 0.062, cz, 0.024, (0.66, 0.52, 0.36), lat=3, lon=6, sy=0.6)


def ham(f, w):
    tex = T_jambon()
    for lx in _span(w, 0.17):
        for j in range(3):
            f.box("papier", lx, j * 0.026, -0.03 + j * 0.01, 0.16, 0.024, 0.22, (0.93, 0.93, 0.95), front_tex=tex)
            f.top("papier", lx, j * 0.026 + 0.026, -0.03 + j * 0.01, 0.13, 0.17, (0.95, 0.66, 0.68))


def juice(f, w, k):
    kinds = (("orange", (250, 150, 20), (255, 200, 60)), ("pomme", (120, 190, 60), (220, 40, 40)), ("multifruit", (200, 60, 120), (250, 180, 40)))
    name, c0, acc = kinds[k % len(kinds)]
    tex = T_jus(name, c0, acc)
    side = tuple(c / 255 for c in c0)
    for lx in _span(w, 0.085):
        for lz in (-0.1, 0.0, 0.1):
            f.box("papier", lx, 0.0, lz, 0.072, 0.19, 0.072, side, front_tex=tex if lz > 0.05 else None)
            p = [f.p(lx - 0.036, 0.19, lz - 0.036), f.p(lx + 0.036, 0.19, lz - 0.036), f.p(lx + 0.036, 0.19, lz + 0.036),
                 f.p(lx - 0.036, 0.19, lz + 0.036), f.p(lx - 0.036, 0.23, lz), f.p(lx + 0.036, 0.23, lz)]
            nf = (math.sin(math.radians(f.rot)), 0.7, math.cos(math.radians(f.rot)))
            nb = (-nf[0], 0.7, -nf[2])
            f.b.quad("papier", p[3], p[2], p[5], p[4], nf, side)                  # toit avant
            f.b.quad("papier", p[0], p[1], p[5], p[4], nb, side)                  # toit arrière
        f.cyl("metal", lx + 0.02, 0.2, 0.08, 0.012, 0.02, (0.95, 0.95, 0.95), seg=8)


def dessert(f, w, k):
    kinds = (("chocolat", (110, 60, 30)), ("vanille", (240, 220, 160)), ("caramel", (200, 120, 40)))
    name, col = kinds[k % len(kinds)]
    tex = T_dessert(name, col)
    for lx in _span(w, 0.15):
        for lz in (-0.08, 0.07):
            f.box("papier", lx, 0.0, lz, 0.14, 0.04, 0.14, (0.9, 0.88, 0.82), front_tex=tex)
            for dx in (-0.034, 0.034):
                for dz in (-0.034, 0.034):
                    f.lathe("papier", lx + dx, lz + dz, [(0.04, 0.024), (0.09, 0.03), (0.092, 0.03)], (0.98, 0.98, 0.97), seg=12)
                    f.cyl("metal", lx + dx, 0.092, lz + dz, 0.031, 0.003, tuple(c / 255 for c in col), seg=12)


def pizza(f, w):
    tex = T_pizza()
    for lx in _span(w, 0.3):
        for j in range(4):
            f.box("papier", lx, j * 0.04, 0.0, 0.28, 0.038, 0.28, (0.92, 0.9, 0.86), front_tex=tex if j == 3 else None)
        f.top(tex, lx, 0.161, 0.0, 0.27, 0.27)


def salad(f, w):
    tex = T_salade()
    for lx in _span(w, 0.16):
        for lz in (-0.08, 0.06):
            f.box("papier", lx, 0.0, lz, 0.15, 0.2, 0.06, (0.75, 0.9, 0.7), front_tex=tex)
            f.box("papier", lx, 0.2, lz, 0.14, 0.02, 0.04, (0.6, 0.8, 0.55))


FRIDGE_PLAN = [  # catégorie de chaque module, de gauche à droite
    "lait", "yaourt", "yaourt", "dessert", "fromage", "fromage", "beurre_oeufs", "jambon",
    "jambon", "jus", "jus", "pizza", "salade", "lait", "yaourt", "fromage",
]
HEADERS = {"lait": "PRODUITS LAITIERS", "yaourt": "YAOURTS", "dessert": "DESSERTS", "fromage": "FROMAGES",
           "beurre_oeufs": "BEURRE & ŒUFS", "jambon": "CHARCUTERIE", "jus": "JUS FRAIS", "pizza": "TRAITEUR", "salade": "SALADES"}
YOG = (("fraise", (220, 70, 100)), ("vanille", (240, 200, 120)), ("nature", (70, 130, 200)), ("myrtille", (110, 80, 170)), ("pêche", (240, 150, 90)))


def _fill(f, w, cat, shelf_i, unit_i):
    k = shelf_i + unit_i
    if cat == "lait":
        milk(f, w) if shelf_i % 2 == 0 else yogurt(f, w, *YOG[k % len(YOG)])
    elif cat == "yaourt":
        yogurt(f, w, *YOG[k % len(YOG)])
    elif cat == "dessert":
        dessert(f, w, k)
    elif cat == "fromage":
        cheese(f, w, k)
    elif cat == "beurre_oeufs":
        butter_eggs(f, w)
    elif cat == "jambon":
        ham(f, w)
    elif cat == "jus":
        juice(f, w, k)
    elif cat == "pizza":
        pizza(f, w) if shelf_i < 3 else dessert(f, w, k)
    elif cat == "salade":
        salad(f, w)


# =============================================================================
# Mur réfrigéré
# =============================================================================
def build_fridges(b, be, x0, x1, z_back, z_front):
    """Modules réfrigérés à portes vitrées entre x0 et x1, du mur (z_back) à la façade vitrée (z_front, vers +z).

    Retourne [(texte, x)] : enseignes de catégorie à poser au-dessus de chaque groupe de modules."""
    n = max(1, int(round((x1 - x0) / 1.25)))
    uw = (x1 - x0) / n
    H_BASE, H_TOP, H_CAN = 0.3, 2.08, 2.42
    shelves = (0.34, 0.68, 1.02, 1.36, 1.7)
    zi0, zi1 = z_back + 0.08, z_front - 0.07
    tag = T_prix()
    b.colliders.append((x0, 0.0, z_back, x1, H_CAN, z_front + 0.06))
    headers = []
    last = None
    for i in range(n):
        ux0, ux1 = x0 + i * uw, x0 + (i + 1) * uw
        cx = (ux0 + ux1) / 2
        cat = FRIDGE_PLAN[i % len(FRIDGE_PLAN)]
        if cat != last:
            headers.append((HEADERS[cat], cx))
            last = cat
        # caisson : fond blanc, cloisons, plafond, socle ventilé, auvent
        b.box("platre", ux0, H_BASE, z_back, ux1, H_TOP, z_back + 0.08, WHITE)
        if i == 0:
            # joue d'extrémité 1 cm plus large que le caisson (auvent, socle, plafond ne sont plus coplanaires avec elle)
            b.box("metal", ux0 - 0.01, 0.0, z_back, ux0 + 0.04, H_CAN + 0.005, z_front + 0.08, ALU)
        else:
            b.box("metal", ux0, 0.0, z_back, ux0 + 0.04, H_CAN, z_front, ALU)
        b.box("platre", ux0, H_TOP, z_back, ux1, H_TOP + 0.04, z_front, WHITE)
        b.box("metal", ux0, 0.0, z_back, ux1, H_BASE, z_front - 0.02, DARK)
        for k in range(4):
            yy = 0.06 + k * 0.055
            b.box("metal", ux0 + 0.08, yy, z_front - 0.025, ux1 - 0.08, yy + 0.022, z_front - 0.015, (0.32, 0.33, 0.36))
        b.box("metal", ux0, H_TOP + 0.04, z_back, ux1, H_CAN, z_front + 0.06, (0.1, 0.24, 0.58))         # auvent bleu
        b.box("metal", ux0, H_CAN - 0.02, z_back, ux1, H_CAN, z_front + 0.07, WHITE)
        be.box("neon", ux0 + 0.05, H_TOP - 0.02, z_front - 0.12, ux1 - 0.05, H_TOP, z_front - 0.09, (0.85, 0.93, 1.0))
        for ex in (ux0 + 0.05, ux1 - 0.07):                                        # rampes LED verticales
            be.box("neon", ex, H_BASE + 0.04, z_front - 0.1, ex + 0.015, H_TOP - 0.04, z_front - 0.085, (0.8, 0.9, 1.0))
        # étagères, rails de prix, produits
        for s_i, sy in enumerate(shelves):
            b.box("metal", ux0 + 0.04, sy - 0.018, zi0, ux1, sy, zi1, (0.7, 0.72, 0.76))
            b.box("metal", ux0 + 0.04, sy - 0.05, zi1 - 0.01, ux1, sy, zi1, WHITE)          # rail de prix
            for tx in (cx - uw * 0.25, cx + uw * 0.25):
                b.quad(tag, (tx + 0.06, sy - 0.046, zi1 + 0.002), (tx - 0.06, sy - 0.046, zi1 + 0.002),
                       (tx - 0.06, sy - 0.016, zi1 + 0.002), (tx + 0.06, sy - 0.016, zi1 + 0.002), (0, 0, 1), (1, 1, 1),
                       tile=(0.12, 0.03))
            f = _Frame(b, cx + 0.02, sy, (zi0 + zi1) / 2 - 0.02, 0.0)
            _fill(f, uw - 0.14, cat, s_i, i)
        # bac du bas (pas d'étagère au-dessus du socle)
        f = _Frame(b, cx + 0.02, H_BASE, (zi0 + zi1) / 2 - 0.02, 0.0)
        _fill(f, uw - 0.14, cat, 5, i)
        # portes vitrées : cadres alu, verre, poignées chromées
        dw = (uw - 0.04) / 2
        for d_i in range(2):
            dx0 = ux0 + 0.04 + d_i * dw
            dx1 = dx0 + dw
            zf = z_front
            b.box("metal", dx0, H_BASE, zf - 0.01, dx0 + 0.035, H_TOP, zf + 0.03, ALU)
            b.box("metal", dx1 - 0.035, H_BASE, zf - 0.01, dx1, H_TOP, zf + 0.03, ALU)
            b.box("metal", dx0, H_TOP - 0.05, zf - 0.01, dx1, H_TOP, zf + 0.03, ALU)
            b.box("metal", dx0, H_BASE, zf - 0.01, dx1, H_BASE + 0.06, zf + 0.03, ALU)
            b.box("vitre", dx0 + 0.035, H_BASE + 0.06, zf + 0.005, dx1 - 0.035, H_TOP - 0.05, zf + 0.012, (0.82, 0.9, 0.96))
            hx = dx1 - 0.08 if d_i == 0 else dx0 + 0.06
            b.box("metal", hx, 0.75, zf + 0.06, hx + 0.022, 1.55, zf + 0.082, CHROME)
            for hy in (0.8, 1.48):
                b.box("metal", hx + 0.004, hy, zf + 0.03, hx + 0.018, hy + 0.025, zf + 0.06, CHROME)
    b.box("metal", x1 - 0.04, 0.0, z_back, x1 + 0.01, H_CAN + 0.005, z_front + 0.08, ALU)    # joue d'extrémité droite
    return headers


# =============================================================================
# Épicerie des gondoles
# =============================================================================
def _item(f, kind, variant, lz):
    """Un article posé sur le plateau (base en y = 0 du repère), façade vers +z local. Retourne sa largeur."""
    if kind == "box":
        tex, size = _epicerie_tex(variant)
        w = 0.12 if size[0] < size[1] else 0.19
        h = 0.3 if size[1] >= 220 else 0.18
        f.box("papier", 0.0, 0.0, lz, w, h, 0.06, (0.9, 0.88, 0.85), front_tex=tex)
        return w
    if kind == "bag":
        tex, _ = _epicerie_tex(5)
        f.box("papier", 0.0, 0.0, lz, 0.17, 0.25, 0.05, (0.98, 0.8, 0.2), front_tex=tex)
        f.box("papier", 0.0, 0.25, lz, 0.16, 0.022, 0.02, (0.98, 0.8, 0.2))
        return 0.17
    if kind == "can":
        name, c0, acc = CANS[variant % len(CANS)]
        tex = _can_tex(name, c0, acc)
        cx, cz = _local(f.x, f.z, f.rot, 0.0, lz)
        for s_ in range(2):                                          # deux boîtes empilées
            rings = [_ring(cx, cz, f.y + s_ * 0.103 + h, 0.037, 0.037, f.rot + 90.0, 2.0, seg=16) for h in (0.0, 0.1)]
            f.b.loft(tex, rings, (1, 1, 1), tile=(2 * math.pi * 0.037, 0.1))
            f.b.cap("metal", rings[1], (0, 1, 0), CHROME)
        return 0.078
    if kind == "jar":
        name, c0, acc = JARS[variant % len(JARS)]
        tex = _jar_tex(name, c0, acc)
        fill = tuple(c / 255 * 0.8 for c in c0)
        f.lathe("vitre", 0.0, lz, [(0.0, 0.034), (0.01, 0.036), (0.1, 0.036), (0.11, 0.03)], (0.85, 0.9, 0.92), seg=14)
        f.lathe("papier", 0.0, lz, [(0.005, 0.033), (0.095, 0.033)], fill, seg=14)
        f.cyl("metal", 0.0, 0.11, lz, 0.032, 0.018, (0.85, 0.75, 0.2) if variant % 2 else CHROME, seg=14)
        cx, cz = _local(f.x, f.z, f.rot, 0.0, lz)
        band = [_ring(cx, cz, f.y + h, 0.0375, 0.0375, f.rot + 90.0, 2.0, seg=14) for h in (0.025, 0.075)]
        f.b.loft(tex, band, (1, 1, 1), tile=(2 * math.pi * 0.0375, 0.05))
        return 0.076
    if kind in ("lessive", "rouleaux", "eponge", "ampoule"):
        tex, c0 = _bazar_tex(kind, variant)
        side = tuple(c / 255 for c in c0)
        w, h, d = {"lessive": (0.2, 0.28, 0.11), "rouleaux": (0.22, 0.22, 0.11), "eponge": (0.13, 0.075, 0.05),
                   "ampoule": (0.07, 0.13, 0.07)}[kind]
        f.box("papier", 0.0, 0.0, lz, w, h, d, side, front_tex=tex)
        if kind == "lessive":                                       # poignée de transport sur le dessus
            f.box("papier", 0.0, h, lz, 0.08, 0.025, 0.02, (0.92, 0.92, 0.94))
        elif kind == "eponge":                                      # deux sachets empilés
            f.box("papier", 0.0, h, lz, w, h, d, side, front_tex=tex)
        return w
    if kind == "spray":
        tex, c0 = _bazar_tex(kind, variant)
        body = tuple(c / 255 for c in c0)
        f.lathe("papier", 0.0, lz, [(0.0, 0.03), (0.01, 0.034), (0.17, 0.034), (0.2, 0.016), (0.215, 0.014)], body, seg=16)
        cx, cz = _local(f.x, f.z, f.rot, 0.0, lz)
        band = [_ring(cx, cz, f.y + h, 0.0355, 0.0355, f.rot + 90.0, 2.0, seg=16) for h in (0.04, 0.15)]
        f.b.loft(tex, band, (1, 1, 1), tile=(2 * math.pi * 0.0355, 0.11))
        f.box("papier", 0.0, 0.215, lz, 0.032, 0.045, 0.03, (0.95, 0.95, 0.95))       # tête de pulvérisation
        f.box("papier", 0.0, 0.235, lz + 0.03, 0.022, 0.018, 0.035, (0.95, 0.95, 0.95))  # buse
        f.box("papier", 0.0, 0.17, lz + 0.03, 0.012, 0.05, 0.012, (0.2, 0.5, 0.9))       # gâchette
        return 0.072
    # bouteille
    name, c0, acc = SODAS[variant % len(SODAS)]
    tex = _soda_tex(name, c0, acc)
    glass = tuple(min(1.0, c / 255 + 0.3) for c in c0)
    _bottle(f, 0.0, lz, 0.3, 0.034, glass, tex, (0.9, 0.1, 0.1) if name == "cola" else (0.2, 0.5, 0.9))
    return 0.072


# rayonnage par hauteur : léger en haut, conserves et bocaux au milieu, bouteilles et gros paquets en bas
LEVEL_KINDS = {
    "epicerie": {0: ("bottle", "box", "bag"), 1: ("can", "jar", "box"), 2: ("box", "jar", "can"), 3: ("box", "bag")},
    "boissons": {0: ("bottle",), 1: ("bottle", "can"), 2: ("bottle",), 3: ("box",)},
    # droguerie du rayon bazar : gros volumes en bas, petits articles à hauteur des yeux
    "bazar": {0: ("lessive", "rouleaux"), 1: ("eponge", "spray", "ampoule"), 2: ("ampoule", "eponge", "spray"), 3: ("rouleaux", "lessive")},
}
DEPTH_ROWS = {"box": (0.025, -0.045), "bag": (0.03, -0.035), "can": (0.045, -0.04), "jar": (0.045, -0.04), "bottle": (0.048, -0.034),
              "lessive": (0.025,), "rouleaux": (0.025,), "eponge": (0.03, -0.04), "ampoule": (0.045, -0.04), "spray": (0.048, -0.034)}


def shelf_food(b, x, y, z0, z1, side, aisle, level, rng):
    """Garnit un plateau de gondole (le long de z, de z0 à z1) ; façade vers +x (side=1) ou -x (side=-1).

    Comme en magasin : chaque produit forme un bloc de 3 à 5 « facings » identiques alignés au bord du plateau,
    avec une rangée de réserve derrière ; les familles de produits dépendent de la hauteur de l'étagère."""
    rot = 90.0 if side > 0 else -90.0
    kinds = LEVEL_KINDS.get(aisle, LEVEL_KINDS["epicerie"]).get(level, ("box",))
    z = z0 + 0.04
    run = 0
    while z < z1 - 0.12:
        kind = kinds[(run + level) % len(kinds)] if run else rng.choice(kinds)
        variant = rng.randrange(8)
        n = rng.randint(3, 5)
        for _ in range(n):
            # largeur de l'article (mesurée en le construisant dans un builder jetable)
            probe = _Frame(_Null(), 0.0, 0.0, 0.0, rot)
            w = _item(probe, kind, variant, 0.0)
            if z + w > z1 - 0.04:
                break
            cz = z + w / 2
            for lz in DEPTH_ROWS[kind]:
                _item(_Frame(b, x, y, cz, rot), kind, variant, lz)
            z += w + 0.008
        z += 0.035                                    # petit vide entre deux produits
        run += 1


class _Null:
    """MeshBuilder factice : sert à connaître la largeur d'un article sans rien dessiner."""

    def __getattr__(self, name):
        return lambda *a, **k: None


# =============================================================================
# Fruits et légumes
# =============================================================================
PRODUCE = [
    # (modèle Poly Haven, couleur du tas, taille d'un fruit (m), nom, prix)
    ("food_apple_01", (0.72, 0.12, 0.1), 0.08, "Pommes", "2,49 €/kg"),
    ("lemon", (0.95, 0.82, 0.15), 0.075, "Citrons", "2,99 €/kg"),
    ("food_lime_01", (0.35, 0.62, 0.15), 0.06, "Citrons verts", "0,39 € pièce"),
    ("food_avocado_01", (0.18, 0.28, 0.1), 0.1, "Avocats", "0,99 € pièce"),
    ("food_kiwi_01", (0.45, 0.32, 0.18), 0.07, "Kiwis", "0,35 € pièce"),
    ("food_pears_asian_01", (0.8, 0.72, 0.3), 0.09, "Poires", "2,79 €/kg"),
    ("food_pomegranate_01", (0.6, 0.08, 0.12), 0.1, "Grenades", "1,49 € pièce"),
    ("yellow_onion", (0.72, 0.5, 0.22), 0.08, "Oignons", "1,59 €/kg"),
    ("sweet_potato", (0.62, 0.32, 0.2), 0.16, "Patates douces", "2,99 €/kg"),
    ("food_ginger_01", (0.75, 0.62, 0.42), 0.12, "Gingembre", "6,90 €/kg"),
    ("bananas", (0.95, 0.82, 0.25), 0.16, "Bananes", "1,99 €/kg"),
    ("food_lychee_01", (0.72, 0.2, 0.22), 0.04, "Litchis", "5,90 €/kg"),
    # sans modèle 3D (tas modelés seulement)
    ("tomate", (0.85, 0.14, 0.1), 0.07, "Tomates", "2,89 €/kg"),
    ("orange", (0.98, 0.52, 0.08), 0.08, "Oranges", "2,29 €/kg"),
    ("pomme_de_terre", (0.66, 0.5, 0.32), 0.07, "Pommes de terre", "1,29 €/kg"),
]


def _price_card(name, price):
    def draw(img, d):
        w, h = img.size
        d.rectangle((0, 0, w, h), fill=(28, 30, 28))
        d.rectangle((3, 3, w - 4, h - 4), outline=(200, 170, 110), width=3)
        _text(d, (0, 4, w, h * 0.55), name, (245, 245, 235), int(h * 0.34))
        _text(d, (0, h * 0.5, w, h - 4), price, (255, 214, 60), int(h * 0.36), bold=False)
    return _pack("ardoise_" + name, (220, 110), draw)


def produce_crate(b, cx, y, cz, item, rng, rot=0.0, w=0.5, d=0.36, real=4):
    """Cagette en bois garnie : tas de fruits modelés + quelques vrais modèles 3D par-dessus."""
    model, col, size, _, _ = item
    wood = (0.62, 0.45, 0.28)
    for (sx, sz, ex, ez) in ((0, -d / 2, w, 0.02), (0, d / 2, w, 0.02), (-w / 2, 0, 0.02, d), (w / 2, 0, 0.02, d)):
        x0, z0 = cx + sx - ex / 2, cz + sz - ez / 2
        for k in range(2):
            b.box("bois_meuble", x0, y + 0.02 + k * 0.07, z0, x0 + ex, y + 0.07 + k * 0.07, z0 + ez, wood)
    b.box("bois_meuble", cx - w / 2, y, cz - d / 2, cx + w / 2, y + 0.02, cz + d / 2, wood)
    r = size * 0.5
    nx, nz = max(2, int(w / size)), max(2, int(d / size))
    for i in range(nx):
        for j in range(nz):
            px = cx - w / 2 + (i + 0.5) * w / nx
            pz = cz - d / 2 + (j + 0.5) * d / nz
            tint = tuple(max(0.0, min(1.0, c * rng.uniform(0.85, 1.12))) for c in col)
            b.sphere("peau", px, y + 0.02 + r * 0.9, pz, r * 0.95, tint, lat=6, lon=10, sy=0.92)
            if (i + j) % 2 == 0:
                b.sphere("peau", px + r * 0.4, y + 0.02 + r * 2.3, pz - r * 0.3, r * 0.95, tint, lat=6, lon=10, sy=0.92)
    for k in range(real):
        px = cx + rng.uniform(-w / 2 + size, w / 2 - size)
        pz = cz + rng.uniform(-d / 2 + size, d / 2 - size)
        b.model(model, px, pz, y + 0.02 + r * 2.6, rng.uniform(0, 360), size=(size, size, size))


def produce_stand(b, cx, cz, rng, items, rot_front=0.0):
    """Étal en gradins (2 rangées de cagettes inclinées vers l'allée) + ardoises de prix. Façade vers +z."""
    W, D = 2.2, 1.0
    wood = (0.42, 0.27, 0.16)
    b.box("bois_meuble", cx - W / 2, 0.0, cz - D / 2, cx + W / 2, 0.55, cz + D / 2, wood, collide=True)
    b.box("bois_meuble", cx - W / 2, 0.55, cz - D / 2, cx + W / 2, 0.85, cz, wood)
    cards = []
    for row, (yy, zz) in enumerate(((0.85, cz - D / 4), (0.55, cz + D / 4))):
        for k in range(4):
            item = items[(row * 4 + k) % len(items)]
            x = cx - W / 2 + 0.28 + k * 0.55
            produce_crate(b, x, yy, zz, item, rng, real=5 if row == 0 else 6)
            if row == 1:
                cards.append((_price_card(item[3], item[4]), x, zz + 0.2))
    for tex, x, z in cards:
        b.quad(tex, (x + 0.12, 0.6, z + 0.01), (x - 0.12, 0.6, z + 0.01), (x - 0.12, 0.72, z + 0.01), (x + 0.12, 0.72, z + 0.01),
               (0, 0, 1), (1, 1, 1), tile=(0.24, 0.12))
