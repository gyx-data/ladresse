"""Génération procédurale de toutes les textures (Pillow + numpy).

Aucune image externe : murs, sols, meubles, icônes du téléphone, décalcomanies...
Les textures sont mises en cache en PNG dans le dossier temporaire.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config

_REGISTRY = {}      # nom -> (fonction, taille)


def register(name, size=256):
    def deco(fn):
        _REGISTRY[name] = (fn, size)
        return fn
    return deco


# ---------------------------------------------------------------------------
# Outils de bruit
# ---------------------------------------------------------------------------
def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def value_noise(size, cells_x, cells_y, rng):
    """Bruit de valeur lissé et répétable (tileable). Retourne un tableau [0,1]."""
    g = rng.random((cells_y, cells_x))
    xs = np.linspace(0, cells_x, size, endpoint=False)
    ys = np.linspace(0, cells_y, size, endpoint=False)
    x0 = xs.astype(int)
    y0 = ys.astype(int)
    fx = _smooth(xs - x0)[None, :]
    fy = _smooth(ys - y0)[:, None]
    x1 = (x0 + 1) % cells_x
    y1 = (y0 + 1) % cells_y
    a = g[np.ix_(y0, x0)]
    b = g[np.ix_(y0, x1)]
    c = g[np.ix_(y1, x0)]
    d = g[np.ix_(y1, x1)]
    top = a * (1 - fx) + b * fx
    bot = c * (1 - fx) + d * fx
    return top * (1 - fy) + bot * fy


def fbm(size, rng, base=4, octaves=5, persistence=0.5, stretch=(1, 1)):
    total = np.zeros((size, size))
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        cx = max(1, int(base * (2 ** o) * stretch[0]))
        cy = max(1, int(base * (2 ** o) * stretch[1]))
        total += amp * value_noise(size, cx, cy, rng)
        norm += amp
        amp *= persistence
    return total / norm


def lerp_color(n, c0, c1):
    c0 = np.array(c0, dtype=float)
    c1 = np.array(c1, dtype=float)
    return c0[None, None, :] * (1 - n[..., None]) + c1[None, None, :] * n[..., None]


def to_img(arr, mode="RGB"):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode)


def stain(size, rng, strength=0.5, base=3):
    """Taches d'humidité : tableau [0,1] (1 = tache)."""
    n = fbm(size, rng, base=base, octaves=4)
    n = np.clip((n - 0.55) * 4.0, 0, 1)
    return n * strength


def _font(px, bold=False):
    try:
        from ursina import application
        name = "OpenSans-Bold.ttf" if bold else "OpenSans-Regular.ttf"
        p = os.path.join(str(application.package_folder), "fonts", name)
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
        p = os.path.join(str(application.package_folder), "fonts", "OpenSans-Regular.ttf")
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    except Exception:
        pass
    try:
        return ImageFont.load_default(px)
    except TypeError:
        return ImageFont.load_default()


def _tile_wrap(img):
    """Contrôle de continuité : rien à faire (le bruit est déjà répétable)."""
    return img


# ---------------------------------------------------------------------------
# Murs et plafonds
# ---------------------------------------------------------------------------
@register("crepi", 512)
def tex_crepi(rng):
    """Enduit niçois ocre jaune, délavé, fissuré, avec coulures de pluie et soubassement sali."""
    s = 512
    n = fbm(s, rng, base=24, octaves=4, persistence=0.6)
    coarse = fbm(s, rng, base=3, octaves=3)
    streaks = fbm(s, rng, base=6, octaves=3, stretch=(1.0, 0.15))
    base = lerp_color(n, (150, 108, 62), (206, 160, 98))
    base *= (0.78 + 0.32 * coarse)[..., None]
    base *= (1.0 - 0.38 * np.clip((streaks - 0.5) * 3, 0, 1))[..., None]
    # écaillage : plaques plus claires où l'enduit est tombé
    flakes = np.clip((fbm(s, rng, base=10, octaves=3) - 0.68) * 6, 0, 1)
    base = base * (1 - flakes[..., None] * 0.5) + np.array((176, 166, 150))[None, None, :] * flakes[..., None] * 0.5
    img = to_img(base)
    d = ImageDraw.Draw(img)
    for _ in range(7):
        x, y = rng.integers(0, s), rng.integers(0, s)
        pts = [(x, y)]
        for _ in range(rng.integers(8, 20)):
            x += rng.integers(-14, 15)
            y += rng.integers(4, 22)
            pts.append((x % s, y % s) if abs(x) < s else (x, y))
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) < 60 and abs(a[1] - b[1]) < 60:
                d.line([a, b], fill=(70, 50, 34), width=int(rng.integers(1, 3)))
    return img


@register("crepi_rose", 512)
def tex_crepi_rose(rng):
    """Variante rose/terre de Sienne pour les villas voisines."""
    s = 512
    n = fbm(s, rng, base=20, octaves=4, persistence=0.6)
    coarse = fbm(s, rng, base=3, octaves=3)
    base = lerp_color(n, (150, 82, 70), (204, 132, 112))
    base *= (0.8 + 0.3 * coarse)[..., None]
    return to_img(base)


@register("tuiles", 512)
def tex_tiles_roof(rng):
    """Tuiles canal provençales : rangées ondulées terre cuite, mousse et lichen."""
    s = 512
    arr = np.zeros((s, s, 3))
    rows, cols = 8, 8
    rh, cw = s // rows, s // cols
    xx = np.arange(s)[None, :]
    yy = np.arange(s)[:, None]
    lx = (xx % cw) / cw
    ly = (yy % rh) / rh
    # profil d'une tuile canal : bombé (cos) + ombre sous le recouvrement
    bump = np.cos((lx - 0.5) * np.pi) ** 0.8
    shade = 0.55 + 0.45 * bump
    shade = shade * (0.65 + 0.35 * np.clip(ly * 1.6, 0, 1))
    tint = np.zeros((s, s))
    for r in range(rows):
        for c in range(cols):
            tint[r * rh:(r + 1) * rh, c * cw:(c + 1) * cw] = rng.uniform(-0.12, 0.12)
    noise = fbm(s, rng, base=32, octaves=3)
    col0 = np.array((150, 64, 38), dtype=float)
    col1 = np.array((198, 104, 62), dtype=float)
    t = np.clip(0.5 + tint + (noise - 0.5) * 0.4, 0, 1)
    arr = col0[None, None, :] * (1 - t[..., None]) + col1[None, None, :] * t[..., None]
    arr *= shade[..., None]
    moss = np.clip((fbm(s, rng, base=5, octaves=4) - 0.62) * 4, 0, 1)
    arr = arr * (1 - moss[..., None] * 0.6) + np.array((70, 76, 40))[None, None, :] * moss[..., None] * 0.6
    return to_img(arr)


@register("palmier_tronc", 256)
def tex_palm_trunk(rng):
    """Écorce de palmier en écailles (bases de palmes coupées)."""
    s = 256
    arr = lerp_color(fbm(s, rng, base=12, octaves=3), (78, 62, 44), (128, 104, 76))
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for y in range(0, s, 22):
        off = 11 if (y // 22) % 2 else 0
        for x in range(-22 + off, s + 22, 44):
            d.arc([x, y - 6, x + 44, y + 24], 200, 340, fill=(48, 36, 26), width=3)
    return img


@register("palme", 256)
def tex_palm_leaf(rng):
    """Palme vert sombre avec nervure centrale (utilisée sur des quads)."""
    s = 256
    img = Image.new("RGB", (s, s), (40, 62, 34))
    d = ImageDraw.Draw(img)
    for x in range(0, s, 6):
        c = int(rng.integers(30, 70))
        d.line([(x, 0), (x + 3, s)], fill=(c, c + 30, c - 10), width=3)
    d.line([(0, s // 2), (s, s // 2)], fill=(110, 120, 70), width=6)
    return img.filter(ImageFilter.GaussianBlur(0.8))


@register("geranium", 128)
def tex_geranium(rng):
    s = 128
    img = Image.new("RGB", (s, s), (40, 70, 34))
    d = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rng.integers(0, s), rng.integers(0, s)
        r = int(rng.integers(3, 7))
        c = (int(rng.integers(170, 230)), int(rng.integers(20, 50)), int(rng.integers(30, 60)))
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return img


def _flower(d, cx, cy, r, petal, center):
    for k in range(6):
        a = k * math.pi / 3
        px, py = cx + math.cos(a) * r * 0.9, cy + math.sin(a) * r * 0.9
        d.ellipse([px - r * 0.55, py - r * 0.55, px + r * 0.55, py + r * 0.55], fill=petal)
    d.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=center)


def make_wallpaper(rng, base_col, motif_col, leaf_col, tear=0.62, size=512):
    s = size
    base = np.zeros((s, s, 3)) + np.array(base_col)[None, None, :]
    xs = np.arange(s)[None, :]
    stripes = 0.5 + 0.5 * np.sin(xs * 2 * math.pi / 64.0)
    base *= (0.94 + 0.06 * stripes)[..., None]
    img = to_img(base)
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    step = 128
    for ix in range(s // step):
        for iy in range(s // step):
            cx = ix * step + 64
            cy = iy * step + 64
            ox = (iy % 2) * 0
            _flower(d, cx + ox, cy, 18, motif_col + (255,), (230, 215, 160, 255))
            for k in (-1, 1):
                d.ellipse([cx + k * 36 - 8, cy + 40 - 5, cx + k * 36 + 8, cy + 40 + 5], fill=leaf_col + (255,))
            d.ellipse([cx - 3, cy + 62, cx + 3, cy + 68], fill=motif_col + (255,))
    fade = fbm(s, rng, base=4, octaves=3)
    alpha = np.array(layer.split()[3]).astype(float) * (0.35 + 0.65 * np.clip((fade - 0.2) * 1.6, 0, 1))
    layer.putalpha(to_img(alpha, "L"))
    img.paste(layer, (0, 0), layer)
    arr = np.array(img).astype(float)
    # Vieillissement et taches
    n = fbm(s, rng, base=8, octaves=5)
    arr *= (0.78 + 0.35 * n)[..., None]
    st = stain(s, rng, 0.55, base=3)
    arr = arr * (1 - st[..., None]) + np.array((110, 78, 40))[None, None, :] * st[..., None] * 0.9
    # Papier arraché : plâtre apparent
    t = fbm(s, rng, base=3, octaves=4, persistence=0.55)
    yy = np.linspace(0, 1, s)[:, None]
    t = t + 0.18 * (yy - 0.5)
    mask = (t > tear).astype(float)
    mask_img = to_img(mask * 255, "L").filter(ImageFilter.GaussianBlur(1.5))
    m = np.array(mask_img).astype(float) / 255.0
    edge = np.clip(np.array(mask_img.filter(ImageFilter.GaussianBlur(4))).astype(float) / 255.0 - m, 0, 1)
    plaster = lerp_color(fbm(s, rng, base=20, octaves=3), (150, 146, 138), (190, 186, 176))
    arr = arr * (1 - m[..., None]) + plaster * m[..., None]
    arr *= (1.0 - 0.5 * np.clip(edge * 3, 0, 1))[..., None]
    return to_img(arr)


@register("papier_peint", 512)
def tex_wallpaper(rng):
    return make_wallpaper(rng, (186, 164, 104), (150, 92, 76), (110, 125, 85))


@register("papier_chambre", 512)
def tex_wallpaper_bed(rng):
    return make_wallpaper(rng, (150, 160, 130), (170, 130, 110), (90, 110, 80), tear=0.66)


@register("papier_couloir", 512)
def tex_wallpaper_corr(rng):
    return make_wallpaper(rng, (170, 150, 120), (120, 80, 70), (100, 105, 80), tear=0.64)


@register("platre", 256)
def tex_plaster(rng):
    n = fbm(256, rng, base=10, octaves=5)
    arr = lerp_color(n, (140, 136, 128), (196, 192, 184))
    return to_img(arr)


@register("plafond", 256)
def tex_ceiling(rng):
    s = 256
    n = fbm(s, rng, base=12, octaves=4)
    arr = lerp_color(n, (190, 186, 172), (226, 222, 208))
    for _ in range(4):
        cx, cy = rng.integers(0, s, 2)
        r = rng.integers(20, 55)
        yy, xx = np.ogrid[:s, :s]
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        ring = np.clip(1 - np.abs(dist - r) / 6.0, 0, 1) * 0.55
        fill = np.clip(1 - dist / r, 0, 1) * 0.25
        k = (ring + fill)[..., None]
        arr = arr * (1 - k) + np.array((140, 100, 52))[None, None, :] * k
    return to_img(arr)


# ---------------------------------------------------------------------------
# Sols
# ---------------------------------------------------------------------------
@register("parquet", 512)
def tex_parquet(rng):
    s = 512
    plank_h = 32
    arr = np.zeros((s, s, 3))
    grain = fbm(s, rng, base=3, octaves=4, stretch=(0.08, 1.0))
    fine = fbm(s, rng, base=10, octaves=3, stretch=(0.05, 1.0))
    for i in range(s // plank_h):
        tint = rng.uniform(0.7, 1.15)
        y0, y1 = i * plank_h, (i + 1) * plank_h
        offset = rng.integers(0, s)
        seg = np.roll(grain[y0:y1], offset, axis=1)
        fseg = np.roll(fine[y0:y1], offset, axis=1)
        col = lerp_color(seg * 0.6 + fseg * 0.4, (52, 32, 18), (92, 60, 34)) * tint
        arr[y0:y1] = col
        arr[y0:y0 + 2] *= 0.35
        # joints d'about
        jx = rng.integers(0, s)
        arr[y0:y1, jx:jx + 2] *= 0.35
    arr *= (0.8 + 0.3 * fbm(s, rng, base=4, octaves=3))[..., None]
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for _ in range(25):
        x, y = rng.integers(0, s, 2)
        d.line([(x, y), (x + rng.integers(10, 60), y + rng.integers(-3, 4))], fill=(30, 20, 12), width=1)
    return img


@register("carrelage", 256)
def tex_tiles(rng):
    s = 256
    tile = s // 2
    arr = np.zeros((s, s, 3))
    for ix in range(2):
        for iy in range(2):
            light = (ix + iy) % 2 == 0
            c = (205, 200, 188) if light else (34, 32, 32)
            arr[iy * tile:(iy + 1) * tile, ix * tile:(ix + 1) * tile] = c
    dirt = fbm(s, rng, base=8, octaves=5)
    arr *= (0.55 + 0.6 * dirt)[..., None]
    st = stain(s, rng, 0.45, base=4)
    arr = arr * (1 - st[..., None]) + np.array((70, 55, 35))[None, None, :] * st[..., None]
    arr[:2, :] *= 0.3
    arr[:, :2] *= 0.3
    arr[tile - 1:tile + 1, :] *= 0.3
    arr[:, tile - 1:tile + 1] *= 0.3
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for _ in range(3):
        x, y = rng.integers(0, s, 2)
        pts = [(x, y)]
        for _ in range(6):
            x += rng.integers(-12, 13)
            y += rng.integers(-12, 13)
            pts.append((x, y))
        d.line(pts, fill=(20, 20, 20), width=1)
    return img


@register("moquette", 256)
def tex_carpet(rng):
    s = 256
    fine = rng.random((s, s))
    n = fbm(s, rng, base=6, octaves=4)
    arr = lerp_color(n, (92, 20, 22), (140, 46, 40))
    arr *= (0.8 + 0.3 * fine)[..., None]
    wear = np.clip((fbm(s, rng, base=3, octaves=3) - 0.55) * 4, 0, 1)
    arr = arr * (1 - wear[..., None] * 0.5) + np.array((110, 90, 80))[None, None, :] * wear[..., None] * 0.5
    return to_img(arr)


@register("beton", 256)
def tex_concrete(rng):
    s = 256
    n = fbm(s, rng, base=10, octaves=6, persistence=0.6)
    arr = lerp_color(n, (70, 70, 72), (122, 122, 120))
    pits = (rng.random((s, s)) > 0.996).astype(float)
    pits = np.array(Image.fromarray((pits * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255.0
    arr *= (1 - np.clip(pits * 6, 0, 0.6))[..., None]
    st = stain(s, rng, 0.7, base=3)
    arr = arr * (1 - st[..., None]) + np.array((22, 20, 20))[None, None, :] * st[..., None]
    return to_img(arr)


@register("asphalte", 256)
def tex_asphalt(rng):
    s = 256
    n = rng.random((s, s))
    m = fbm(s, rng, base=8, octaves=4)
    arr = lerp_color(m * 0.5 + n * 0.5, (30, 30, 32), (72, 72, 74))
    return to_img(arr)


@register("herbe", 256)
def tex_grass(rng):
    s = 256
    n = fbm(s, rng, base=16, octaves=5)
    blades = rng.random((s, s))
    arr = lerp_color(n * 0.7 + blades * 0.3, (18, 34, 14), (60, 84, 36))
    return to_img(arr)


# ---------------------------------------------------------------------------
# Bois, portes, planches, fenêtres
# ---------------------------------------------------------------------------
@register("porte", 256)
def tex_door(rng):
    s = 256
    g = fbm(s, rng, base=4, octaves=4, stretch=(0.2, 1.0))
    arr = lerp_color(g, (46, 26, 14), (86, 50, 28))
    arr *= (0.8 + 0.4 * fbm(s, rng, base=12, octaves=3, stretch=(0.1, 1.0)))[..., None]
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for (x0, y0, x1, y1) in ((30, 22, 226, 110), (30, 140, 226, 238)):
        d.rectangle([x0, y0, x1, y1], outline=(28, 15, 8), width=4)
        d.rectangle([x0 + 4, y0 + 4, x1 - 4, y1 - 4], outline=(104, 64, 36), width=1)
    d.ellipse([210, 126, 224, 140], fill=(150, 130, 70))
    return img


@register("porte_griffes", 256)
def tex_door_scratched(rng):
    img = tex_door(rng)
    d = ImageDraw.Draw(img)
    for k in range(5):
        x = 70 + k * 14 + int(rng.integers(-3, 4))
        d.line([(x, 60), (x + int(rng.integers(-10, 10)), 200)], fill=(176, 140, 96), width=2)
        d.line([(x + 1, 62), (x + 1 + int(rng.integers(-8, 8)), 190)], fill=(20, 10, 6), width=1)
    return img


@register("planches", 256)
def tex_planks(rng):
    s = 256
    arr = np.zeros((s, s, 3))
    h = s // 4
    g = fbm(s, rng, base=4, octaves=4, stretch=(1.0, 0.1))
    for i in range(4):
        tint = rng.uniform(0.7, 1.1)
        seg = g[i * h:(i + 1) * h]
        arr[i * h:(i + 1) * h] = lerp_color(seg, (60, 50, 40), (110, 92, 70)) * tint
        arr[i * h:i * h + 3] *= 0.3
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for i in range(4):
        for x in (12, s - 14):
            y = i * h + h // 2
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(60, 58, 56), outline=(20, 20, 20))
    return img


@register("volet", 256)
def tex_shutter(rng):
    """Persienne niçoise vert amande délavé : lames inclinées, peinture écaillée sur bois gris."""
    s = 256
    n = fbm(s, rng, base=8, octaves=4)
    arr = lerp_color(n, (62, 104, 88), (104, 146, 122)).astype(float)
    yy = (np.arange(s) % 16) / 16.0
    louver = 0.55 + 0.45 * np.clip(yy * 1.4, 0, 1)
    arr *= louver[:, None, None]
    arr[:, :10] *= 0.75
    arr[:, -10:] *= 0.75
    arr[:, s // 2 - 4:s // 2 + 4] *= 0.6
    peel = np.clip((fbm(s, rng, base=5, octaves=3) - 0.6) * 5, 0, 1)
    arr = arr * (1 - peel[..., None]) + np.array((112, 100, 84))[None, None, :] * peel[..., None]
    return to_img(arr)


@register("vitre", 128)
def tex_glass(rng):
    s = 128
    n = fbm(s, rng, base=6, octaves=4)
    rgb = lerp_color(n, (40, 48, 52), (86, 96, 98))
    alpha = (90 + 80 * n)
    arr = np.dstack([rgb, alpha])
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    for _ in range(6):
        x, y = rng.integers(0, s, 2)
        d.line([(x, y), (x + rng.integers(-30, 30), y + rng.integers(10, 40))], fill=(150, 160, 160, 120), width=1)
    return img


@register("bois_meuble", 256)
def tex_furniture_wood(rng):
    s = 256
    g = fbm(s, rng, base=3, octaves=5, stretch=(0.1, 1.0))
    arr = lerp_color(g, (82, 52, 30), (130, 88, 52))
    arr *= (0.85 + 0.3 * fbm(s, rng, base=14, octaves=3))[..., None]
    return to_img(arr)


@register("etoffe", 128)
def tex_cloth_neutral(rng):
    """Tissu neutre clair (teinté par la couleur de sommet) : vêtements des personnages."""
    s = 128
    n = fbm(s, rng, base=8, octaves=3)
    arr = lerp_color(n, (196, 196, 196), (236, 236, 236))
    yy, xx = np.mgrid[:s, :s]
    weave = 0.5 + 0.25 * np.sin(xx * 2.2) + 0.25 * np.sin(yy * 2.2)
    arr *= (0.86 + 0.14 * weave)[..., None]
    return to_img(arr)


@register("jean", 128)
def tex_denim(rng):
    """Toile de jean neutre (sergé diagonal), teintée par la couleur du vêtement."""
    s = 128
    n = fbm(s, rng, base=10, octaves=3)
    yy, xx = np.mgrid[:s, :s]
    twill = 0.5 + 0.5 * np.sin((xx + yy) * 1.6)
    arr = lerp_color(n * 0.5 + twill * 0.5, (176, 180, 186), (238, 238, 240))
    fade = fbm(s, rng, base=3, octaves=2)
    arr *= (0.92 + 0.12 * fade)[..., None]
    return to_img(arr)


@register("tricot", 128)
def tex_knit(rng):
    """Maille tricotée (pulls, gilets, bonnets) : rangées de petits V."""
    s = 128
    yy, xx = np.mgrid[:s, :s]
    v = np.abs(((xx % 8) - 4)) * 0.6 + (yy % 6)
    knit = 0.5 + 0.5 * np.sin(v * 1.05)
    n = fbm(s, rng, base=8, octaves=2)
    arr = lerp_color(knit * 0.7 + n * 0.3, (170, 170, 170), (240, 240, 240))
    return to_img(arr)


@register("cuir", 128)
def tex_leather(rng):
    """Cuir (chaussures, ceintures, blousons) : grain fin et légère brillance."""
    s = 128
    n = fbm(s, rng, base=16, octaves=4, persistence=0.6)
    cells = fbm(s, rng, base=24, octaves=1)
    arr = lerp_color(n * 0.6 + cells * 0.4, (150, 150, 150), (230, 230, 230))
    yy = np.mgrid[:s, :s][0]
    arr *= (0.95 + 0.1 * np.exp(-((yy - s * 0.3) / (s * 0.12)) ** 2))[..., None]
    return to_img(arr)


@register("doudoune", 128)
def tex_puffer(rng):
    """Doudoune matelassée : bandes horizontales gonflées et coutures."""
    s = 128
    yy = np.mgrid[:s, :s][0].astype(float)
    band = (yy % 32) / 32.0
    puff = np.sin(band * np.pi) ** 0.6
    arr = lerp_color(puff, (120, 120, 124), (245, 245, 248))
    seam = (yy % 32) < 2
    arr[seam] *= 0.55
    n = fbm(s, rng, base=6, octaves=2)
    arr *= (0.95 + 0.08 * n)[..., None]
    return to_img(arr)


@register("carrosserie", 256)
def tex_car_paint(rng):
    """Peinture de carrosserie : vernis lisse, reflet du ciel en haut, paillettes discrètes."""
    s = 256
    yy, xx = np.mgrid[:s, :s].astype(float)
    sky = 0.86 + 0.14 * np.clip(1.0 - yy / (s * 0.55), 0, 1)
    streak = 0.06 * np.exp(-((yy - s * 0.32) / (s * 0.04)) ** 2)
    flakes = (rng.random((s, s)) > 0.985) * 0.06
    v = np.clip(sky + streak + flakes, 0, 1.1)
    arr = np.dstack([v * 236, v * 238, v * 242])
    return to_img(arr)


@register("pneu", 128)
def tex_tire(rng):
    """Gomme de pneu : sculptures en chevrons sur fond très sombre (couleur de sommet claire)."""
    s = 128
    yy, xx = np.mgrid[:s, :s]
    chev = ((xx + np.abs((yy % 16) - 8)) % 12) < 5
    arr = np.full((s, s, 3), 34.0)
    arr[chev] = 22.0
    n = fbm(s, rng, base=10, octaves=2)
    arr *= (0.9 + 0.2 * n)[..., None]
    return to_img(arr)


@register("jante", 128)
def tex_rim(rng):
    """Alliage brossé (jantes, chromes)."""
    s = 128
    n = fbm(s, rng, base=4, octaves=2, stretch=(1, 12))
    yy = np.mgrid[:s, :s][0]
    arr = lerp_color(n, (170, 172, 178), (250, 250, 252))
    arr *= (0.9 + 0.12 * np.sin(yy / s * np.pi * 3))[..., None]
    return to_img(arr)


@register("peau", 64)
def tex_skin(rng):
    s = 64
    n = fbm(s, rng, base=4, octaves=3)
    return to_img(lerp_color(n, (228, 222, 218), (250, 246, 242)))


@register("tissu", 256)
def tex_fabric(rng):
    s = 256
    n = fbm(s, rng, base=6, octaves=4)
    arr = lerp_color(n, (88, 22, 32), (128, 44, 52))
    yy, xx = np.mgrid[:s, :s]
    weave = 0.5 + 0.25 * np.sin(xx * 1.6) + 0.25 * np.sin(yy * 1.6)
    arr *= (0.75 + 0.3 * weave)[..., None]
    wear = np.clip((fbm(s, rng, base=3, octaves=3) - 0.55) * 4, 0, 1)
    arr = arr * (1 - 0.4 * wear[..., None]) + np.array((120, 96, 80))[None, None, :] * 0.4 * wear[..., None]
    return to_img(arr)


@register("marbre", 256)
def tex_marble(rng):
    s = 256
    n = fbm(s, rng, base=3, octaves=5)
    yy, xx = np.mgrid[:s, :s]
    veins = np.abs(np.sin((xx + yy) * 0.04 + n * 9.0))
    veins = np.clip(1 - veins * 4, 0, 1)
    arr = lerp_color(n, (180, 176, 168), (214, 210, 202))
    arr = arr * (1 - 0.5 * veins[..., None]) + np.array((90, 90, 96))[None, None, :] * 0.5 * veins[..., None]
    dirt = fbm(s, rng, base=8, octaves=4)
    arr *= (0.65 + 0.4 * dirt)[..., None]
    return to_img(arr)


@register("email", 256)
def tex_enamel(rng):
    s = 256
    n = fbm(s, rng, base=6, octaves=4)
    arr = lerp_color(n, (176, 172, 156), (212, 208, 190))
    st = stain(s, rng, 0.35, base=4)
    arr = arr * (1 - st[..., None]) + np.array((140, 110, 60))[None, None, :] * st[..., None]
    return to_img(arr)


@register("metal", 256)
def tex_metal(rng):
    s = 256
    n = fbm(s, rng, base=6, octaves=4, stretch=(0.2, 1.0))
    arr = lerp_color(n, (78, 80, 84), (128, 130, 134))
    arr *= (0.9 + 0.1 * fbm(s, rng, base=40, octaves=2, stretch=(0.02, 1.0)))[..., None]     # brossage
    rust = np.clip((fbm(s, rng, base=5, octaves=4) - 0.7) * 3, 0, 1) * 0.6                # rouille légère, par endroits
    arr = arr * (1 - rust[..., None]) + np.array((120, 64, 30))[None, None, :] * rust[..., None]
    return to_img(arr)


@register("papier", 256)
def tex_paper(rng):
    s = 256
    n = fbm(s, rng, base=8, octaves=5)
    arr = lerp_color(n, (206, 192, 160), (232, 222, 196))
    st = stain(s, rng, 0.45, base=3)
    arr = arr * (1 - st[..., None]) + np.array((150, 112, 60))[None, None, :] * st[..., None]
    return to_img(arr)


@register("emballage", 256)
def tex_packaging(rng):
    """Emballage crème avec bandeau, faux texte et code-barres stylisé."""
    s = 256
    n = fbm(s, rng, base=12, octaves=4, persistence=0.52)
    arr = lerp_color(n, (238, 232, 215), (255, 251, 239))
    img = to_img(arr)
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, s, 64), fill=(38, 104, 116))
    draw.rectangle((0, 58, s, 64), fill=(222, 177, 77))

    for y in (91, 105, 119, 133, 147, 161):
        right = int(rng.integers(146, 229))
        draw.rounded_rectangle((24, y, right, y + 3), radius=1, fill=(104, 101, 91))

    x = 35
    while x < 222:
        width = int(rng.integers(1, 5))
        top = int(rng.integers(190, 199))
        draw.rectangle((x, top, x + width - 1, 239), fill=(24, 24, 25))
        x += width + int(rng.integers(1, 4))
    return img


@register("drap", 256)
def tex_sheet(rng):
    s = 256
    n = fbm(s, rng, base=3, octaves=5)
    folds = 0.5 + 0.5 * np.sin(np.linspace(0, 14, s)[None, :] + n * 6)
    arr = lerp_color(folds * 0.7 + n * 0.3, (150, 146, 136), (222, 218, 206))
    st = stain(s, rng, 0.4, base=4)
    arr = arr * (1 - st[..., None]) + np.array((140, 120, 80))[None, None, :] * st[..., None]
    return to_img(arr)


@register("rideau", 128)
def tex_curtain(rng):
    s = 128
    n = fbm(s, rng, base=4, octaves=3)
    yy, xx = np.mgrid[:s, :s]
    pattern = (np.sin(xx * 0.5) * np.sin(yy * 0.5) > 0.6).astype(float)
    arr = lerp_color(n, (150, 170, 160), (190, 205, 195))
    arr = arr * (1 - 0.25 * pattern[..., None]) + np.array((110, 140, 150))[None, None, :] * 0.25 * pattern[..., None]
    return to_img(arr)


@register("eau_noire", 128)
def tex_black_water(rng):
    s = 128
    n = fbm(s, rng, base=6, octaves=4)
    arr = lerp_color(n, (6, 8, 8), (24, 30, 28))
    return to_img(arr)


@register("miroir", 128)
def tex_mirror(rng):
    s = 128
    yy = np.linspace(0, 1, s)[:, None] * np.ones((1, s))
    n = fbm(s, rng, base=4, octaves=3)
    arr = lerp_color(0.5 * yy + 0.5 * n, (62, 72, 84), (22, 28, 34))
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    d.line([(0, 90), (128, 30)], fill=(180, 190, 200), width=1)
    return img


@register("miroir_brise", 128)
def tex_mirror_broken(rng):
    img = tex_mirror(rng)
    d = ImageDraw.Draw(img)
    cx, cy = 64, 50
    for k in range(9):
        a = k * math.pi / 4.5 + rng.uniform(-0.2, 0.2)
        r = rng.uniform(40, 80)
        d.line([(cx, cy), (cx + math.cos(a) * r, cy + math.sin(a) * r)], fill=(210, 215, 220), width=1)
    for r in (14, 28, 44):
        d.arc([cx - r, cy - r, cx + r, cy + r], 0, 300, fill=(190, 195, 200), width=1)
    return img


@register("neon", 64)
def tex_neon(rng):
    arr = np.zeros((64, 64, 3)) + np.array((236, 244, 255))[None, None, :]
    return to_img(arr)


@register("ecran_noir", 64)
def tex_screen_off(rng):
    n = fbm(64, rng, base=4, octaves=2)
    return to_img(lerp_color(n, (8, 10, 12), (22, 26, 28)))


@register("tv_statique_0", 128)
def tex_static0(rng):
    return to_img(np.repeat(rng.random((128, 128, 1)) * 255, 3, axis=2))


@register("tv_statique_1", 128)
def tex_static1(rng):
    return to_img(np.repeat(rng.random((128, 128, 1)) * 255, 3, axis=2))


@register("tv_statique_2", 128)
def tex_static2(rng):
    return to_img(np.repeat(rng.random((128, 128, 1)) * 255, 3, axis=2))


@register("ciel", 512)
def tex_sky(rng):
    s = 512
    yy = np.linspace(0, 1, s)[:, None] * np.ones((1, s))
    n = fbm(s, rng, base=3, octaves=6, persistence=0.55, stretch=(1.0, 0.6))
    arr = lerp_color(yy, (4, 6, 14), (26, 30, 46))
    clouds = np.clip((n - 0.45) * 2.2, 0, 1)
    arr = arr * (1 - clouds[..., None] * 0.8) + np.array((34, 38, 52))[None, None, :] * clouds[..., None] * 0.8
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rng.integers(0, s), rng.integers(0, int(s * 0.5))
        c = int(rng.integers(120, 220))
        d.point((x, y), fill=(c, c, c))
    return img


# ---------------------------------------------------------------------------
# Objets spécifiques
# ---------------------------------------------------------------------------
@register("sac_quickeats", 256)
def tex_bag(rng):
    s = 256
    img = Image.new("RGB", (s, s), (255, 112, 8))
    arr = np.array(img).astype(float)
    arr *= (0.92 + 0.12 * fbm(s, rng, base=10, octaves=3))[..., None]
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 70, 216, 210], radius=16, outline=(255, 255, 255), width=8)
    d.arc([80, 30, 176, 110], 190, 350, fill=(255, 255, 255), width=8)
    f = _font(34, True)
    d.text((s // 2, 150), "QuickEats", fill=(255, 255, 255), font=f, anchor="mm")
    return img


@register("fond_telephone", 256)
def tex_phone_wallpaper(rng):
    s = 256
    yy = np.linspace(0, 1, s)[:, None] * np.ones((1, s))
    arr = lerp_color(yy, (255, 150, 60), (92, 40, 140))
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    d.ellipse([88, 100, 168, 180], fill=(255, 214, 120))
    return img.filter(ImageFilter.GaussianBlur(1.2))


@register("paysage", 256)
def tex_paysage(rng):
    """Vieille marine à l'huile (baie au couchant, cyprès, village perché), vernis jauni et craquelé."""
    s = 256
    yy = np.linspace(0, 1, s)[:, None] * np.ones((1, s))
    xx = np.ones((s, 1)) * np.linspace(0, 1, s)[None, :]
    sky_top, sky_low = np.array((92, 112, 138)), np.array((214, 168, 112))
    t = np.clip(yy / 0.52, 0, 1)[..., None]
    arr = sky_top * (1 - t) + sky_low * t
    hills = 0.5 + 0.06 * np.sin(xx * 7.0 + 1.3) + 0.03 * np.sin(xx * 19.0)
    arr = np.where((yy > hills)[..., None], np.array((70, 84, 74)) * (0.8 + 0.4 * (yy - hills)[..., None]), arr)
    sea = yy > 0.62
    glint = (np.exp(-((xx - 0.72) / 0.07) ** 2) * np.clip(1 - (yy - 0.62) * 3, 0, 1))[..., None]   # reflet du soleil
    arr = np.where(sea[..., None], np.array((44, 72, 96)) + np.array((150, 112, 70)) * glint, arr)
    shore = (yy > 0.86 + 0.04 * np.sin(xx * 5.0))
    arr = np.where(shore[..., None], np.array((150, 128, 92)), arr)
    arr *= (0.86 + 0.24 * fbm(s, rng, base=10, octaves=4, stretch=(2, 1)))[..., None]       # touches de pinceau
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    d.ellipse([176, 98, 194, 116], fill=(240, 200, 130))                                    # soleil bas
    for (x, h) in ((30, 70), (44, 54), (210, 64)):                                           # cyprès
        d.polygon([(x, 150 - h), (x - 7, 150), (x + 7, 150)], fill=(34, 46, 34))
    for k in range(9):                                                                       # village perché
        x0 = 70 + k * 9 + int(rng.integers(0, 4))
        hh = int(rng.integers(8, 16))
        d.rectangle([x0, 124 - hh, x0 + 7, 128], fill=(196, 160 - k * 4, 118))
        d.polygon([(x0 - 1, 124 - hh), (x0 + 3, 120 - hh), (x0 + 8, 124 - hh)], fill=(150, 74, 52))
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    arr = np.array(img).astype(float)
    crack = fbm(s, rng, base=24, octaves=2)
    arr *= (1 - 0.25 * (np.abs(crack - 0.5) < 0.012))[..., None]                            # craquelures du vernis
    arr = arr * np.array((1.0, 0.94, 0.78)) * 0.92                                          # vernis jauni
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s - 1, s - 1], outline=(40, 26, 14), width=6)
    return img


@register("portrait", 256)
def tex_portrait(rng):
    return _portrait(rng, False)


@register("portrait_deforme", 256)
def tex_portrait_bad(rng):
    return _portrait(rng, True)


def _portrait(rng, bad):
    """Portrait de famille à l'huile (père, mère, enfant) sur fond sombre, vernis jauni et craquelé.

    bad : même tableau, mais les visages ont fondu : orbites noires, bouches étirées, coulures de peinture."""
    S = 512                                                    # dessiné en 2x puis réduit (bords lissés)
    yy = np.linspace(-1, 1, S)[:, None] * np.ones((1, S))
    xx = np.ones((S, 1)) * np.linspace(-1, 1, S)[None, :]
    vign = np.clip(1.0 - 0.55 * (xx ** 2 + (yy * 0.9) ** 2), 0, 1)[..., None]
    arr = np.array((58, 52, 38)) * (0.35 + 0.75 * vign)
    arr *= (0.85 + 0.3 * fbm(S, rng, base=5, octaves=4))[..., None]
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    skin = (206, 168, 136)
    # (centre x, haut de tête y, rayon tête, couleur vêtement, cheveux)
    people = [(160, 120, 46, (38, 40, 52), (46, 34, 26)),          # père
              (352, 140, 42, (92, 36, 40), (78, 50, 30)),           # mère
              (256, 236, 34, (60, 74, 96), (120, 86, 44))]          # enfant
    for (cx, top, r, cloth, hair) in people:
        # buste et épaules
        d.rounded_rectangle([cx - r * 1.9, top + r * 2.05, cx + r * 1.9, S + 40], radius=int(r * 0.95), fill=cloth)
        d.line([cx, top + r * 2.9, cx, S], fill=tuple(int(c * 0.7) for c in cloth), width=3)       # boutonnage
        d.polygon([(cx - r * 0.45, top + r * 2.0), (cx + r * 0.45, top + r * 2.0), (cx, top + r * 2.9)], fill=(222, 214, 196))
        d.rectangle([cx - r * 0.38, top + r * 1.6, cx + r * 0.38, top + r * 2.3], fill=tuple(int(c * 0.85) for c in skin))
        # tête, cheveux, oreilles
        d.ellipse([cx - r * 1.08, top - r * 0.08, cx + r * 1.08, top + r * 1.55], fill=hair)
        d.ellipse([cx - r * 1.12, top + r * 0.55, cx - r * 0.82, top + r * 1.05], fill=tuple(int(c * 0.9) for c in skin))
        d.ellipse([cx + r * 0.82, top + r * 0.55, cx + r * 1.12, top + r * 1.05], fill=tuple(int(c * 0.9) for c in skin))
        d.ellipse([cx - r * 0.9, top + r * 0.25, cx + r * 0.9, top + r * 1.9], fill=skin)
        d.chord([cx - r * 0.95, top - r * 0.05, cx + r * 0.95, top + r * 1.0], 180, 360, fill=hair)
        ey = top + r * 0.95
        if not bad:
            for sx in (-1, 1):
                ex = cx + sx * r * 0.36
                d.ellipse([ex - r * 0.2, ey - r * 0.1, ex + r * 0.2, ey + r * 0.1], fill=(236, 228, 214))
                d.ellipse([ex - r * 0.09, ey - r * 0.09, ex + r * 0.09, ey + r * 0.09], fill=(52, 40, 32))
                d.line([ex - r * 0.25, ey - r * 0.24, ex + r * 0.2, ey - r * 0.28], fill=tuple(int(c * 0.7) for c in hair), width=4)
            d.line([cx, ey + r * 0.05, cx - r * 0.1, ey + r * 0.45], fill=(170, 128, 104), width=3)
            d.arc([cx - r * 0.3, ey + r * 0.45, cx + r * 0.3, ey + r * 0.75], 15, 165, fill=(140, 70, 64), width=4)
        else:
            for sx in (-1, 1):
                ex = cx + sx * r * 0.36
                d.ellipse([ex - r * 0.24, ey - r * 0.2, ex + r * 0.24, ey + r * 0.26], fill=(14, 10, 10))
                for k in range(3):                                         # larmes de peinture noire
                    dx = int(rng.integers(-6, 7))
                    d.line([ex + dx, ey + r * 0.2, ex + dx, ey + r * (0.7 + 1.4 * rng.random())], fill=(20, 14, 14),
                           width=int(rng.integers(2, 6)))
            d.ellipse([cx - r * 0.32, ey + r * 0.35, cx + r * 0.32, ey + r * 1.15], fill=(18, 10, 10))
    img = img.filter(ImageFilter.GaussianBlur(2.2 if not bad else 3.4))     # touche « huile » fondue
    arr = np.array(img).astype(float)
    if bad:
        rows = (np.sin(np.arange(S) / 9.0) * 6 + np.sin(np.arange(S) / 2.3) * 2).astype(int)
        for y in range(S):                                                       # visages qui glissent
            arr[y] = np.roll(arr[y], rows[y], axis=0)
        arr *= np.array((0.95, 0.86, 0.84))
    arr *= (0.9 + 0.2 * fbm(S, rng, base=40, octaves=2))[..., None]               # grain de la toile
    crack = fbm(S, rng, base=28, octaves=2)
    arr *= (1 - 0.3 * (np.abs(crack - 0.5) < 0.008))[..., None]                   # craquelures
    arr = arr * np.array((1.0, 0.93, 0.76)) * 0.94                                # vernis jauni
    img = to_img(arr).resize((256, 256), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 255, 255], outline=(40, 26, 14), width=5)
    d.rectangle([5, 5, 250, 250], outline=(118, 92, 46), width=2)                 # filet doré
    return img


def _rgba(size):
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def _face(rng, blurred):
    s = 128
    skin = (214, 170, 140)
    img = Image.new("RGB", (s, s), skin)
    arr = np.array(img).astype(float) * (0.9 + 0.15 * fbm(s, rng, base=6, octaves=3))[..., None]
    img = to_img(arr)
    d = ImageDraw.Draw(img)
    # yeux, nez, bouche (un peu trop écartés / trop grands)
    d.ellipse([22, 44, 46, 62], fill=(250, 250, 250), outline=(60, 40, 30))
    d.ellipse([82, 44, 106, 62], fill=(250, 250, 250), outline=(60, 40, 30))
    d.ellipse([30, 48, 40, 58], fill=(30, 30, 30))
    d.ellipse([90, 48, 100, 58], fill=(30, 30, 30))
    d.polygon([(64, 60), (56, 84), (72, 84)], fill=(190, 140, 112))
    d.arc([36, 82, 92, 112], 10, 170, fill=(110, 40, 40), width=4)
    if blurred:
        img = img.filter(ImageFilter.GaussianBlur(5))
        a = np.array(img).astype(float)
        yy = np.arange(s)[:, None]
        a = np.roll(a, 7, axis=1) * 0.5 + a * 0.5
        a[:, :, :] *= (0.55 + 0.45 * np.abs(np.sin(yy / 9.0)))[..., None]
        a[40:96, 24:104] *= 0.35
        img = to_img(a)
    return img


@register("visage_normal", 128)
def tex_face(rng):
    return _face(rng, False)


@register("visage_flou", 128)
def tex_face_blur(rng):
    return _face(rng, True)


@register("silhouette", 256)
def tex_silhouette(rng):
    s = 256
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    d.ellipse([100, 14, 156, 78], fill=(4, 4, 6, 255))
    d.rounded_rectangle([82, 74, 174, 190], radius=26, fill=(4, 4, 6, 255))
    d.rectangle([88, 180, 120, 250], fill=(4, 4, 6, 255))
    d.rectangle([134, 180, 166, 250], fill=(4, 4, 6, 255))
    d.rectangle([60, 80, 88, 210], fill=(4, 4, 6, 255))
    d.rectangle([168, 80, 196, 210], fill=(4, 4, 6, 255))
    return img.filter(ImageFilter.GaussianBlur(2.0))


@register("empreintes", 256)
def tex_footprints(rng):
    s = 256
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    for i in range(6):
        x = 100 + (i % 2) * 52
        y = 20 + i * 40
        d.ellipse([x, y, x + 28, y + 14], fill=(12, 8, 8, 200))
        d.ellipse([x + 2, y + 18, x + 26, y + 36], fill=(12, 8, 8, 200))
    return img.filter(ImageFilter.GaussianBlur(1.4))


@register("mains", 256)
def tex_handprints(rng):
    s = 256
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    for i in range(5):
        cx = 40 + (i % 3) * 80 + int(rng.integers(-10, 10))
        cy = 50 + (i // 3) * 110 + int(rng.integers(-10, 10))
        d.ellipse([cx - 16, cy, cx + 16, cy + 34], fill=(8, 6, 6, 220))
        for k in range(5):
            fx = cx - 14 + k * 7
            d.ellipse([fx, cy - 22 + abs(k - 2) * 5, fx + 7, cy + 4], fill=(8, 6, 6, 220))
    return img.filter(ImageFilter.GaussianBlur(1.6))


@register("griffures", 256)
def tex_scratches(rng):
    s = 256
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    for _ in range(5):
        x = int(rng.integers(30, 220))
        y0 = int(rng.integers(10, 60))
        for k in range(4):
            xx = x + k * 7
            pts = [(xx, y0), (xx + int(rng.integers(-6, 6)), y0 + 100), (xx + int(rng.integers(-10, 10)), y0 + 190)]
            d.line(pts, fill=(168, 126, 86, 240), width=2)
            d.line([(a + 1, b) for a, b in pts], fill=(10, 6, 4, 230), width=1)
    return img


@register("taches", 256)
def tex_dark_stains(rng):
    s = 256
    n = fbm(s, rng, base=4, octaves=5)
    a = np.clip((n - 0.52) * 5, 0, 1) * 200
    arr = np.dstack([np.full((s, s), 10), np.full((s, s), 6), np.full((s, s), 6), a])
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


@register("sel", 256)
def tex_salt_circle(rng):
    s = 256
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    for _ in range(2200):
        a = rng.uniform(0, 2 * math.pi)
        r = 112 + rng.normal(0, 3.2)
        x = s / 2 + math.cos(a) * r
        y = s / 2 + math.sin(a) * r
        c = int(rng.integers(200, 255))
        d.ellipse([x - 1.3, y - 1.3, x + 1.3, y + 1.3], fill=(c, c, c, 240))
    return img


@register("sel_brise", 256)
def tex_salt_broken(rng):
    img = tex_salt_circle(rng)
    d = ImageDraw.Draw(img)
    d.pieslice([-40, -40, 296, 296], 20, 62, fill=(0, 0, 0, 0))
    arr = np.array(img)
    mask = np.zeros((256, 256), dtype=bool)
    yy, xx = np.mgrid[:256, :256]
    ang = (np.degrees(np.arctan2(yy - 128, xx - 128)) + 360) % 360
    mask = (ang > 20) & (ang < 62)
    arr[mask, 3] = 0
    return Image.fromarray(arr, "RGBA")


@register("cercle_sombre", 256)
def tex_dark_circle(rng):
    s = 256
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    d.ellipse([10, 10, s - 10, s - 10], outline=(12, 8, 8, 235), width=11)
    for k in range(12):
        a = k * math.pi / 6
        x = s / 2 + math.cos(a) * 112
        y = s / 2 + math.sin(a) * 112
        d.line([(x - 8, y - 8), (x + 8, y + 8)], fill=(12, 8, 8, 235), width=4)
        d.line([(x - 8, y + 8), (x + 8, y - 8)], fill=(12, 8, 8, 235), width=4)
    return img.filter(ImageFilter.GaussianBlur(1.1))


@register("lueur", 128)
def tex_glow(rng):
    s = 128
    yy, xx = np.mgrid[:s, :s]
    d = np.sqrt((xx - 64) ** 2 + (yy - 64) ** 2) / 64.0
    a = np.clip(1 - d, 0, 1) ** 2 * 255
    arr = np.dstack([np.full((s, s), 255), np.full((s, s), 255), np.full((s, s), 255), a])
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


@register("poussiere", 32)
def tex_dust(rng):
    s = 32
    yy, xx = np.mgrid[:s, :s]
    d = np.sqrt((xx - 16) ** 2 + (yy - 16) ** 2) / 16.0
    a = np.clip(1 - d, 0, 1) ** 1.5 * 255
    arr = np.dstack([np.full((s, s), 255), np.full((s, s), 255), np.full((s, s), 255), a])
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


@register("goutte", 32)
def tex_rain(rng):
    s = 32
    img = _rgba(s)
    d = ImageDraw.Draw(img)
    d.line([(16, 2), (16, 30)], fill=(200, 210, 230, 200), width=1)
    return img


# ---------------------------------------------------------------------------
# Icônes du téléphone (rectangles arrondis avec symboles)
# ---------------------------------------------------------------------------
def _icon_base(size, color):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=size // 4, fill=color + (255,))
    return img, d


def make_icon(name, size=128):
    s = size
    white = (255, 255, 255)
    if name == "quickeats":
        img, d = _icon_base(s, (255, 112, 8))
        d.rounded_rectangle([s * .28, s * .38, s * .72, s * .76], radius=8, outline=white, width=7)
        d.arc([s * .38, s * .2, s * .62, s * .5], 190, 350, fill=white, width=7)
    elif name == "banque":
        img, d = _icon_base(s, (30, 76, 190))
        f = _font(int(s * 0.62), True)
        d.text((s / 2, s / 2 + 2), "€", fill=white, font=f, anchor="mm")
    elif name == "messages":
        img, d = _icon_base(s, (52, 190, 80))
        d.rounded_rectangle([s * .2, s * .24, s * .8, s * .64], radius=14, fill=white)
        d.polygon([(s * .32, s * .6), (s * .28, s * .8), (s * .5, s * .62)], fill=white)
    elif name == "camera":
        img, d = _icon_base(s, (110, 110, 118))
        d.rounded_rectangle([s * .18, s * .3, s * .82, s * .74], radius=10, fill=(40, 40, 46))
        d.ellipse([s * .34, s * .36, s * .66, s * .68], outline=white, width=6)
        d.ellipse([s * .43, s * .45, s * .57, s * .59], fill=(120, 170, 230))
        d.rectangle([s * .58, s * .24, s * .74, s * .32], fill=(40, 40, 46))
    elif name == "lampe":
        img, d = _icon_base(s, (240, 190, 30))
        d.ellipse([s * .3, s * .18, s * .7, s * .58], fill=white)
        d.rectangle([s * .42, s * .56, s * .58, s * .72], fill=(70, 70, 76))
        d.rectangle([s * .44, s * .74, s * .56, s * .8], fill=(70, 70, 76))
    elif name == "appels":
        img, d = _icon_base(s, (38, 168, 70))
        d.arc([s * .22, s * .22, s * .78, s * .78], 205, 335, fill=white, width=16)
        d.ellipse([s * .2, s * .5, s * .34, s * .64], fill=white)
        d.ellipse([s * .66, s * .5, s * .8, s * .64], fill=white)
    else:
        img, d = _icon_base(s, (80, 80, 90))
    return img


@register("icone_quickeats", 128)
def _i1(rng):
    return make_icon("quickeats")


@register("icone_banque", 128)
def _i2(rng):
    return make_icon("banque")


@register("icone_messages", 128)
def _i3(rng):
    return make_icon("messages")


@register("icone_camera", 128)
def _i4(rng):
    return make_icon("camera")


@register("icone_lampe", 128)
def _i5(rng):
    return make_icon("lampe")


@register("icone_appels", 128)
def _i6(rng):
    return make_icon("appels")


def text_paper(text, size=256, font_px=20, paper_seed=7, crossed=False, color=(30, 24, 20)):
    """Génère une feuille de papier avec du texte manuscrit (pour les notes in-world)."""
    rng = np.random.default_rng(paper_seed)
    img = tex_paper(rng).resize((size, size))
    d = ImageDraw.Draw(img)
    f = _font(font_px)
    lines = _wrap(text, f, size - 24, d)
    y = 12
    for line in lines:
        d.text((12, y), line, fill=color, font=f)
        if crossed:
            w = d.textlength(line, font=f)
            d.line([(10, y + font_px * 0.6), (12 + w, y + font_px * 0.6)], fill=(120, 20, 20), width=2)
        y += int(font_px * 1.25)
    return img


def _wrap(text, font, width, draw):
    out = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if draw.textlength(test, font=font) <= width:
                cur = test
            else:
                if cur:
                    out.append(cur)
                cur = w
        out.append(cur)
    return out


def text_image(text, size=(512, 128), font_px=48, color=(255, 255, 255), bg=(0, 0, 0, 0), bold=False):
    img = Image.new("RGBA", size, bg)
    d = ImageDraw.Draw(img)
    d.text((size[0] // 2, size[1] // 2), text, fill=color, font=_font(font_px, bold), anchor="mm")
    return img


def make_icon_ico(path):
    """Icône du jeu (maison sombre + point lumineux) au format .ico."""
    s = 256
    img = Image.new("RGBA", (s, s), (6, 6, 10, 255))
    d = ImageDraw.Draw(img)
    d.polygon([(30, 130), (128, 40), (226, 130)], fill=(32, 32, 38, 255))
    d.rectangle([52, 130, 204, 224], fill=(26, 26, 32, 255))
    d.rectangle([116, 168, 140, 224], fill=(8, 8, 10, 255))
    d.ellipse([172, 146, 192, 166], fill=(255, 226, 150, 255))
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([150, 124, 214, 188], fill=(255, 210, 120, 110))
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, glow)
    img.save(path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    return path


# ---------------------------------------------------------------------------
# Bibliothèque
# ---------------------------------------------------------------------------
def _smooth_texture(tex):
    """Filtrage trilinéaire + anisotrope (Ursina ne règle que le filtre de réduction en 'mipmap')."""
    try:
        from panda3d.core import SamplerState
        tex.filtering = "mipmap"
        tex._texture.setMagfilter(SamplerState.FT_linear)
        tex._texture.setAnisotropicDegree(4)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Textures photo (Poly Haven, CC0) : voir fetch_textures.py
# ---------------------------------------------------------------------------
_PHOTO_META = None


def _fingerprint(name, fn):
    """Empreinte du code qui produit la texture et de sa photo éventuelle (voir config.code_fingerprint)."""
    extra, funcs = "", [fn]
    meta = photo_meta().get(name)
    if meta is not None:
        try:
            st = os.stat(os.path.join(config.resource_path("textures"), name + ".jpg"))
            extra = f"{st.st_size}:{meta.get('mode')}:{meta.get('source')}"
        except OSError:
            pass
        funcs.append(_photo_texture)
    return config.code_fingerprint(*funcs, extra=extra)


def photo_meta():
    """nom -> métadonnées (dont size_m = taille réelle couverte) des textures photo présentes dans textures/."""
    global _PHOTO_META
    if _PHOTO_META is None:
        _PHOTO_META = {}
        folder = config.resource_path("textures")
        try:
            import json
            with open(os.path.join(folder, "textures.json"), encoding="utf-8") as f:
                meta = json.load(f)
            _PHOTO_META = {k: v for k, v in meta.items() if os.path.exists(os.path.join(folder, k + ".jpg"))}
        except (OSError, ValueError):
            pass
    return _PHOTO_META


def _photo_texture(name, procedural):
    """Remplace la texture procédurale par la photo, recolorée vers la teinte moyenne de la version procédurale
    (les couleurs de sommet et l'éclairage du jeu ont été réglés sur ces teintes : les variantes de papier peint
    en tirent aussi leurs couleurs)."""
    photo = Image.open(os.path.join(config.resource_path("textures"), name + ".jpg")).convert("RGB")
    arr = np.asarray(photo).astype(float)
    if photo_meta()[name].get("mode") == "detail":
        # garde le dessin procédural (agrandi à la taille de la photo) et lui applique le grain photographique
        base = np.asarray(procedural.convert("RGB").resize(photo.size, Image.BICUBIC)).astype(float)
        lum = arr.mean(axis=2)
        detail = lum / max(lum.mean(), 1.0)
        return to_img(base * (1.0 + 0.85 * (detail - 1.0))[..., None])
    target = np.asarray(procedural.convert("RGB").resize((128, 128))).reshape(-1, 3).astype(float).mean(axis=0)
    mean = arr.reshape(-1, 3).mean(axis=0)
    arr *= (target / np.maximum(mean, 1.0))[None, None, :]
    return to_img(arr)


def _scratch_marks(img, rng):
    """Griffures profondes (bois clair arraché + ombre) sur la moitié basse d'une texture de porte."""
    img = img.convert("RGB")
    d = ImageDraw.Draw(img)
    w, h = img.size
    for group in range(3):
        gx, gy = int(rng.integers(int(w * 0.1), int(w * 0.35))), int(rng.integers(int(h * 0.45), int(h * 0.7)))
        for k in range(4):
            x = gx + k * int(w * 0.018) + int(rng.integers(-3, 4))
            dx, ln = int(rng.integers(-25, 25)), int(rng.integers(int(h * 0.15), int(h * 0.3)))
            d.line([(x, gy), (x + dx, gy + ln)], fill=(176, 140, 96), width=5)
            d.line([(x + 3, gy + 2), (x + dx + 3, gy + ln - 4)], fill=(25, 14, 8), width=2)
    return img


class TextureLibrary:
    """Génère (ou charge depuis le cache) toutes les textures."""

    def __init__(self):
        self.images = {}
        self.textures = {}
        self.cache = config.cache_dir("tex")

    @property
    def names(self):
        return list(_REGISTRY.keys())

    def iter_generate(self):
        """Générateur : yield (index, total, nom) après chaque texture."""
        total = len(_REGISTRY)
        current = set()
        for i, (name, (fn, size)) in enumerate(_REGISTRY.items()):
            # l'empreinte du code de génération (et de la photo) est dans le nom : une texture modifiée par une mise
            # à jour est régénérée au lieu de reprendre l'ancienne image du cache
            path = os.path.join(self.cache, f"{name}_{_fingerprint(name, fn)}.png")
            img = None
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    img.load()
                except Exception:
                    img = None
            if img is None:
                seed = sum(ord(c) * (k + 1) for k, c in enumerate(name)) + 1337
                rng = np.random.default_rng(seed)
                img = fn(rng)
                if name in photo_meta():
                    img = _photo_texture(name, img)
                    if name == "porte_griffes":
                        img = _scratch_marks(img, rng)
                mode = "RGBA" if img.mode == "RGBA" else "RGB"
                img = img.convert(mode)
                try:
                    img.save(path)
                except OSError:
                    pass
            self.images[name] = img
            current.add(os.path.basename(path))
            yield i + 1, total, name
        try:                                                   # anciennes versions de textures : on fait le ménage
            for f in os.listdir(self.cache):
                if f.endswith(".png") and f not in current:
                    os.remove(os.path.join(self.cache, f))
        except OSError:
            pass

    def generate_all(self):
        for _ in self.iter_generate():
            pass

    def pil(self, name):
        return self.images[name]

    def get(self, name):
        """Retourne une Texture Ursina (créée à la demande)."""
        if name in self.textures:
            return self.textures[name]
        from ursina import Texture
        img = self.images.get(name)
        if img is None:
            return None
        tex = Texture(img)
        _smooth_texture(tex)
        self.textures[name] = tex
        return tex

    def from_pil(self, img):
        from ursina import Texture
        tex = Texture(img)
        _smooth_texture(tex)
        return tex


textures = TextureLibrary()
