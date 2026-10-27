"""Thème d'interface : panneaux arrondis texturés, boutons animés, curseurs, touches de clavier.

Toutes les textures sont dessinées avec Pillow à la résolution exacte de l'élément (1 unité d'interface =
1080 px), mises en cache par taille/style, afin que les coins arrondis restent nets quelle que soit la
proportion du bouton.
"""

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import typography as T

PX = 1080.0                  # pixels par unité d'interface (hauteur d'écran = 1)
SS = 3

STYLES = {
    # fond (haut, bas), contour, texte, survol (haut, bas), rayon relatif, ombre
    # Palette horreur : noir charbon, os, sang séché. Coins presque droits, grain, lueur rouge au survol.
    "dark":    dict(top=(18, 14, 15, 228), bot=(7, 5, 6, 238), border=(62, 42, 42, 255), text=(222, 214, 200), hover_top=(46, 10, 12, 242), hover_bot=(16, 3, 4, 248), hover_border=(170, 24, 22, 255), radius=0.06),
    "ghost":   dict(top=(0, 0, 0, 0), bot=(0, 0, 0, 0), border=(0, 0, 0, 0), text=(200, 192, 180), hover_top=(110, 8, 10, 46), hover_bot=(50, 0, 0, 22), hover_border=(150, 20, 20, 255), radius=0.06),
    "primary": dict(top=(118, 12, 14, 255), bot=(52, 3, 5, 255), border=(168, 30, 28, 255), text=(238, 230, 216), hover_top=(150, 18, 18, 255), hover_bot=(70, 5, 7, 255), hover_border=(226, 64, 54, 255), radius=0.06),
    "success": dict(top=(60, 190, 100, 255), bot=(30, 138, 66, 255), border=(130, 230, 160, 255), text=(255, 255, 255), hover_top=(84, 212, 124, 255), hover_bot=(40, 156, 78, 255), hover_border=(190, 250, 210, 255), radius=0.3),
    "danger":  dict(top=(88, 6, 8, 255), bot=(34, 1, 2, 255), border=(150, 22, 20, 255), text=(240, 222, 210), hover_top=(124, 10, 12, 255), hover_bot=(50, 2, 3, 255), hover_border=(220, 50, 44, 255), radius=0.06),
    "toggle_on": dict(top=(130, 14, 16, 255), bot=(70, 5, 7, 255), border=(190, 40, 34, 255), text=(240, 232, 220), hover_top=(150, 18, 18, 255), hover_bot=(80, 6, 8, 255), hover_border=(226, 64, 54, 255), radius=0.5),
    "phone":   dict(top=(48, 50, 60, 255), bot=(34, 36, 44, 255), border=(70, 74, 90, 255), text=(240, 240, 246), hover_top=(66, 70, 84, 255), hover_bot=(46, 50, 62, 255), hover_border=(130, 150, 220, 255), radius=0.3),
    "key":     dict(top=(44, 40, 40, 255), bot=(20, 18, 18, 255), border=(120, 110, 104, 255), text=(232, 224, 210), hover_top=(60, 30, 30, 255), hover_bot=(28, 12, 12, 255), hover_border=(190, 50, 44, 255), radius=0.14),
    "paper":   dict(top=(230, 216, 184, 255), bot=(204, 186, 150, 255), border=(120, 92, 60, 255), text=(40, 30, 24), hover_top=(244, 230, 198, 255), hover_bot=(218, 200, 164, 255), hover_border=(160, 60, 40, 255), radius=0.18),
    "blue":    dict(top=(60, 120, 240, 255), bot=(26, 70, 190, 255), border=(150, 190, 255, 255), text=(255, 255, 255), hover_top=(84, 142, 255, 255), hover_bot=(36, 86, 210, 255), hover_border=(200, 220, 255, 255), radius=0.3),
    "card":    dict(top=(24, 19, 20, 245), bot=(12, 9, 10, 250), border=(56, 40, 40, 255), text=(226, 218, 204), hover_top=(40, 16, 17, 250), hover_bot=(18, 6, 7, 252), hover_border=(160, 26, 24, 255), radius=0.06),
    "panel":   dict(top=(13, 10, 11, 240), bot=(4, 3, 4, 246), border=(56, 36, 36, 255), text=(226, 218, 204), hover_top=(13, 10, 11, 240), hover_bot=(4, 3, 4, 246), hover_border=(56, 36, 36, 255), radius=0.02),
}

# Styles « propres » des applis du téléphone (marque QuickEats, alertes) : l'appareil reste réaliste
STYLES["brand"] = dict(top=(255, 140, 40, 255), bot=(226, 84, 10, 255), border=(255, 190, 120, 255), text=(255, 255, 255), hover_top=(255, 166, 70, 255), hover_bot=(240, 100, 24, 255), hover_border=(255, 220, 160, 255), radius=0.3)
STYLES["alert"] = dict(top=(204, 52, 52, 255), bot=(140, 24, 28, 255), border=(240, 120, 110, 255), text=(255, 255, 255), hover_top=(226, 72, 70, 255), hover_bot=(160, 34, 36, 255), hover_border=(255, 170, 160, 255), radius=0.3)

# styles d'ambiance : grain, rayures et lueur rouge au survol ; les autres (téléphone, borne...) restent « propres »
GRIM = ("dark", "ghost", "primary", "danger", "card", "panel", "toggle_on", "key")
GLOSSY = ("success", "blue", "phone", "brand", "alert")
HOVER_GLOW = (190, 18, 16)

_cache = {}


def _tex(img):
    from texture_generator import textures
    return textures.from_pil(img)


def rounded_rect_image(w, h, style="dark", state="normal", radius=None, shadow=True, glow=None):
    """PIL RGBA d'un rectangle arrondi dégradé avec contour, reflet supérieur et ombre portée."""
    st = STYLES[style]
    key = (w, h, style, state, radius, shadow, glow)
    if key in _cache:
        return _cache[key]
    w = max(8, int(w))
    h = max(8, int(h))
    # suréchantillonnage adapté à la taille : x3 pour les boutons (coins nets), x1 pour les grands panneaux plein
    # écran (un panneau de caisse en x3 = 12 millions de pixels, 3 s de génération à la première ouverture)
    ss = SS if w * h <= 200_000 else (2 if w * h <= 500_000 else 1)
    pad = 10 if shadow and style not in ("ghost",) else 2
    W, H = (w + pad * 2) * ss, (h + pad * 2) * ss
    top = st["hover_top"] if state in ("hover", "pressed") else st["top"]
    bot = st["hover_bot"] if state in ("hover", "pressed") else st["bot"]
    border = st["hover_border"] if state in ("hover", "pressed") else st["border"]
    r = int((radius if radius is not None else st["radius"]) * min(w, h) * ss)
    r = max(2, min(r, min(w, h) * ss // 2))
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    box = [pad * ss, pad * ss, W - pad * ss - 1, H - pad * ss - 1]
    md.rounded_rectangle(box, radius=r, fill=255)
    # dégradé vertical
    g = np.linspace(0, 1, H)[:, None, None]
    c0, c1 = np.array(top, dtype=float), np.array(bot, dtype=float)
    if state == "pressed":
        c0, c1 = c1, c0
    arr = (c0 * (1 - g) + c1 * g) * np.ones((1, W, 1))
    if style in GRIM:
        rng = np.random.default_rng((w * 7919 + h * 104729) % (2 ** 32))
        grain = rng.normal(1.0, 0.07, (H, W))
        # taches sombres diffuses (crasse) et éraflures horizontales plus claires
        blot = np.array(Image.fromarray((rng.random((max(2, H // 40), max(2, W // 40))) * 255).astype(np.uint8))
                        .resize((W, H), Image.BICUBIC)).astype(float) / 255.0
        grain *= 1.0 - 0.22 * np.clip(blot - 0.45, 0, 1) * 2
        for _ in range(max(1, W // 120)):
            yy = int(rng.integers(0, H))
            x0 = int(rng.integers(0, W))
            grain[yy:yy + ss, x0:x0 + int(rng.integers(W // 10, W // 3))] *= 1.25
        arr[..., :3] *= grain[..., None]
    body = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow and style not in ("ghost",):
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(mask.point(lambda v: int(v * 0.55)))
        sh = ImageChops.offset(sh, 0, 4 * ss).filter(ImageFilter.GaussianBlur(5 * ss))
        out = Image.alpha_composite(out, sh)
    body.putalpha(ImageChops.multiply(mask, body.split()[3]))
    out = Image.alpha_composite(out, body)
    d = ImageDraw.Draw(out)
    if border[3] > 0:
        d.rounded_rectangle(box, radius=r, outline=border, width=max(1, int(1.6 * ss)))
    # reflet interne en haut
    if glow is None and style in GRIM and style != "panel":
        glow = HOVER_GLOW
    if style in GLOSSY:
        hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl)
        hd.rounded_rectangle([box[0] + 3 * ss, box[1] + 2 * ss, box[2] - 3 * ss, box[1] + (box[3] - box[1]) * 0.45], radius=r, fill=(255, 255, 255, 22))
        hl.putalpha(ImageChops.multiply(hl.split()[3], mask))
        out = Image.alpha_composite(out, hl)
    if glow and state == "hover":
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(gl).rounded_rectangle(box, radius=r, outline=glow + (230,), width=3 * ss)
        out = Image.alpha_composite(out, gl.filter(ImageFilter.GaussianBlur(3 * ss)))
    img = out.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)
    _cache[key] = (img, pad)
    return _cache[key]


def get_texture(w, h, style="dark", state="normal", radius=None, shadow=True, glow=None):
    """Texture Ursina mise en cache (clé = taille en pixels, style, état)."""
    key = ("tex", int(w), int(h), style, state, radius, shadow, glow)
    if key not in _cache:
        img, pad = rounded_rect_image(w, h, style, state, radius, shadow, glow)
        _cache[key] = (_tex(img), pad)
    return _cache[key]


def px(units):
    return max(8, int(round(units * PX)))


def make_panel(parent, x, y, w, h, style="panel", z=0.0, radius=None, shadow=True, state="normal"):
    """Panneau arrondi (quad texturé) centré en (x, y), taille (w, h) en unités d'interface."""
    from ursina import Entity
    tex, pad = get_texture(px(w), px(h), style, state, radius, shadow)
    ext_w, ext_h = w + 2 * pad / PX, h + 2 * pad / PX
    e = Entity(parent=parent, model="quad", texture=tex, position=(x, y, z), scale=(ext_w, ext_h))
    e.panel_inner = (w, h)
    return e


def keycap_texture(label, size=64):
    key = ("keycap", label, size)
    if key in _cache:
        return _cache[key]
    img = rounded_rect_image(size, size, "key", "normal", 0.22, True)[0].copy()
    d = ImageDraw.Draw(img)
    f = T.pil_font("sans", int(size * (0.5 if len(label) == 1 else 0.3)), True)
    d.text((img.width / 2, img.height / 2 - 1), label, font=f, fill=(250, 250, 250, 255), anchor="mm")
    _cache[key] = (_tex(img), img.width)
    return _cache[key]


def text_image_texture(text, px_size, kind="sans", bold=False, color=(255, 255, 255), **kw):
    key = ("txt", text, px_size, kind, bold, color, tuple(sorted(kw.items())))
    if key not in _cache:
        img = T.render_label(text, px_size, kind, bold, color, **kw)
        _cache[key] = (_tex(img), img.size)
    return _cache[key]


def make_slider_textures(w, h):
    track, pad = get_texture(px(w), px(h), "dark", "normal", 0.5, False)
    return track, pad


def play_ui_sound(name):
    try:
        from sound_engine import engine
        engine.play(name, 0.55, channel="voice")
    except Exception:
        pass
