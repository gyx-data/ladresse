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
    "dark":    dict(top=(34, 34, 40, 235), bot=(18, 18, 22, 240), border=(78, 78, 90, 255), text=(236, 234, 228), hover_top=(58, 54, 52, 245), hover_bot=(32, 28, 28, 250), hover_border=(176, 70, 60, 255), radius=0.28),
    "ghost":   dict(top=(0, 0, 0, 0), bot=(0, 0, 0, 0), border=(0, 0, 0, 0), text=(214, 212, 206), hover_top=(255, 255, 255, 22), hover_bot=(255, 255, 255, 10), hover_border=(200, 80, 70, 255), radius=0.3),
    "primary": dict(top=(255, 140, 40, 255), bot=(226, 84, 10, 255), border=(255, 190, 120, 255), text=(255, 255, 255), hover_top=(255, 166, 70, 255), hover_bot=(240, 100, 24, 255), hover_border=(255, 220, 160, 255), radius=0.3),
    "success": dict(top=(60, 190, 100, 255), bot=(30, 138, 66, 255), border=(130, 230, 160, 255), text=(255, 255, 255), hover_top=(84, 212, 124, 255), hover_bot=(40, 156, 78, 255), hover_border=(190, 250, 210, 255), radius=0.3),
    "danger":  dict(top=(204, 52, 52, 255), bot=(140, 24, 28, 255), border=(240, 120, 110, 255), text=(255, 255, 255), hover_top=(226, 72, 70, 255), hover_bot=(160, 34, 36, 255), hover_border=(255, 170, 160, 255), radius=0.3),
    "phone":   dict(top=(48, 50, 60, 255), bot=(34, 36, 44, 255), border=(70, 74, 90, 255), text=(240, 240, 246), hover_top=(66, 70, 84, 255), hover_bot=(46, 50, 62, 255), hover_border=(130, 150, 220, 255), radius=0.3),
    "key":     dict(top=(70, 70, 78, 255), bot=(40, 40, 46, 255), border=(150, 150, 160, 255), text=(250, 250, 250), hover_top=(86, 86, 96, 255), hover_bot=(52, 52, 60, 255), hover_border=(220, 220, 230, 255), radius=0.22),
    "paper":   dict(top=(230, 216, 184, 255), bot=(204, 186, 150, 255), border=(120, 92, 60, 255), text=(40, 30, 24), hover_top=(244, 230, 198, 255), hover_bot=(218, 200, 164, 255), hover_border=(160, 60, 40, 255), radius=0.18),
    "blue":    dict(top=(60, 120, 240, 255), bot=(26, 70, 190, 255), border=(150, 190, 255, 255), text=(255, 255, 255), hover_top=(84, 142, 255, 255), hover_bot=(36, 86, 210, 255), hover_border=(200, 220, 255, 255), radius=0.3),
    "card":    dict(top=(40, 42, 52, 255), bot=(30, 32, 40, 255), border=(58, 62, 78, 255), text=(240, 240, 246), hover_top=(52, 56, 70, 255), hover_bot=(38, 42, 54, 255), hover_border=(110, 130, 200, 255), radius=0.12),
    "panel":   dict(top=(18, 18, 22, 235), bot=(10, 10, 14, 240), border=(70, 66, 74, 255), text=(236, 234, 228), hover_top=(18, 18, 22, 235), hover_bot=(10, 10, 14, 240), hover_border=(70, 66, 74, 255), radius=0.05),
}

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
    pad = 10 if shadow and style not in ("ghost",) else 2
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    top = st["hover_top"] if state in ("hover", "pressed") else st["top"]
    bot = st["hover_bot"] if state in ("hover", "pressed") else st["bot"]
    border = st["hover_border"] if state in ("hover", "pressed") else st["border"]
    r = int((radius if radius is not None else st["radius"]) * min(w, h) * SS)
    r = max(2, min(r, min(w, h) * SS // 2))
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    box = [pad * SS, pad * SS, W - pad * SS - 1, H - pad * SS - 1]
    md.rounded_rectangle(box, radius=r, fill=255)
    # dégradé vertical
    g = np.linspace(0, 1, H)[:, None, None]
    c0, c1 = np.array(top, dtype=float), np.array(bot, dtype=float)
    if state == "pressed":
        c0, c1 = c1, c0
    arr = (c0 * (1 - g) + c1 * g) * np.ones((1, W, 1))
    body = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow and style not in ("ghost",):
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sh.putalpha(mask.point(lambda v: int(v * 0.55)))
        sh = ImageChops.offset(sh, 0, 4 * SS).filter(ImageFilter.GaussianBlur(5 * SS))
        out = Image.alpha_composite(out, sh)
    body.putalpha(ImageChops.multiply(mask, body.split()[3]))
    out = Image.alpha_composite(out, body)
    d = ImageDraw.Draw(out)
    if border[3] > 0:
        d.rounded_rectangle(box, radius=r, outline=border, width=max(1, int(1.6 * SS)))
    # reflet interne en haut
    if style in ("dark", "primary", "success", "danger", "blue", "phone", "key"):
        hl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hl)
        hd.rounded_rectangle([box[0] + 3 * SS, box[1] + 2 * SS, box[2] - 3 * SS, box[1] + (box[3] - box[1]) * 0.45], radius=r, fill=(255, 255, 255, 22))
        hl.putalpha(ImageChops.multiply(hl.split()[3], mask))
        out = Image.alpha_composite(out, hl)
    if glow and state == "hover":
        gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(gl).rounded_rectangle(box, radius=r, outline=glow + (230,), width=3 * SS)
        out = Image.alpha_composite(out, gl.filter(ImageFilter.GaussianBlur(3 * SS)))
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
