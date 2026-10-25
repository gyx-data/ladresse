"""Typographie de L'ADRESSE : choix des polices, titres stylisés, pages manuscrites.

Polices libres embarquées (dossier fonts/ : Inter, DejaVu, Liberation — licences OFL / libres) utilisées en
priorité pour un rendu identique sur tous les PC ; repli sur les polices du système puis celles d'Ursina.
Les titres, journaux, lettres et reçus sont rendus avec Pillow (effets de grain, de rayures,
d'encre, de décalage chromatique) puis utilisés comme textures.
"""
import hashlib
import math
import os

import numpy as np

import config
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


WIN_FONTS = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
import sys as _sys
BUNDLED_DIR = os.path.join(getattr(_sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "fonts")
LINUX_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts", os.path.expanduser("~/.fonts"), "/Library/Fonts", "/System/Library/Fonts"]

CANDIDATES = {
    # (clair, gras)
    "sans": [("Inter-Regular.otf", "Inter-Bold.otf"), ("segoeui.ttf", "segoeuib.ttf"), ("Carlito-Regular.ttf", "Carlito-Bold.ttf"),
             ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"), ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf")],
    "serif": [("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"), ("georgia.ttf", "georgiab.ttf"), ("pala.ttf", "palab.ttf"),
              ("times.ttf", "timesbd.ttf"), ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf")],
    "mono": [("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"), ("consola.ttf", "consolab.ttf"), ("cour.ttf", "courbd.ttf"),
             ("LiberationMono-Regular.ttf", "LiberationMono-Bold.ttf")],
    "hand": [("Inkfree.ttf", "Inkfree.ttf"), ("segoesc.ttf", "segoescb.ttf"), ("LHANDW.TTF", "LHANDW.TTF"),
             ("DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf"), ("LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf")],
    "title": [("DejaVuSerif-Bold.ttf", "DejaVuSerif-Bold.ttf"), ("georgiab.ttf", "georgiab.ttf"), ("palab.ttf", "palab.ttf"),
              ("timesbd.ttf", "timesbd.ttf"), ("LiberationSerif-Bold.ttf", "LiberationSerif-Bold.ttf")],
}

_index = None
_cache = {}


def _build_index():
    global _index
    if _index is not None:
        return _index
    _index = {}
    dirs = [BUNDLED_DIR, WIN_FONTS] + LINUX_DIRS
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith((".ttf", ".otf")):
                    _index.setdefault(f.lower(), os.path.join(root, f))
    return _index


def _bundled(mono=False):
    try:
        import ursina
        base = os.path.join(os.path.dirname(ursina.__file__), "fonts")
        name = "VeraMono.ttf" if mono else "OpenSans-Regular.ttf"
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return None


def find_font(kind="sans", bold=False):
    """Chemin de la meilleure police disponible pour ce type."""
    key = (kind, bold)
    if key in _cache:
        return _cache[key]
    idx = _build_index()
    path = None
    for pair in CANDIDATES.get(kind, CANDIDATES["sans"]):
        name = pair[1 if bold else 0].lower()
        if name in idx:
            path = idx[name]
            break
    if path is None:
        path = _bundled(mono=(kind == "mono"))
    _cache[key] = path
    return path


def pil_font(kind="sans", px=24, bold=False):
    key = ("pil", kind, px, bold)
    if key in _cache:
        return _cache[key]
    path = find_font(kind, bold)
    try:
        f = ImageFont.truetype(path, px) if path else ImageFont.load_default(px)
    except Exception:
        try:
            f = ImageFont.load_default(px)
        except TypeError:
            f = ImageFont.load_default()
    _cache[key] = f
    return f


def apply_ui_font():
    """Règle la police par défaut des textes Ursina (sans-serif lisible).

    Ursina cherche les polices par nom dans ses dossiers : on copie la police choisie dans le cache
    et on ajoute ce dossier aux dossiers de polices.
    """
    try:
        import shutil
        from pathlib import Path
        from ursina import Text, application
        src = find_font("sans")
        if not src:
            return
        ext = os.path.splitext(src)[1].lower()
        dst_dir = config.cache_dir("fonts")
        dst = os.path.join(dst_dir, "ladresse_ui" + ext)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
        application.fonts_folder = Path(dst_dir)
        Text.default_font = "ladresse_ui" + ext
        Text.default_resolution = 1080 * Text.size * 1.5
    except Exception:
        pass


def text_width(text, kind="sans", px=24, bold=False):
    f = pil_font(kind, px, bold)
    try:
        return f.getlength(text)
    except AttributeError:
        return f.getsize(text)[0]


# ---------------------------------------------------------------------------
# Titres stylisés
# ---------------------------------------------------------------------------
def _noise(size, rng, scale=8):
    w, h = size
    small = rng.random((max(2, h // scale), max(2, w // scale)))
    im = Image.fromarray((small * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    return np.array(im).astype(float) / 255.0


def render_title(text, px=180, kind="title", color=(236, 232, 224), glow=(150, 30, 30), seed=3, pad=60, subtitle=None,
                 sub_px=34, drip=True, glitch=True):
    """Titre cinématographique : lettres rongées, lueur sourde, décalage chromatique, rayures, coulures."""
    rng = np.random.default_rng(seed)
    f = pil_font(kind, px, True)
    probe = Image.new("L", (10, 10))
    d0 = ImageDraw.Draw(probe)
    l, t, r, b = d0.textbbox((0, 0), text, font=f)
    w, h = r - l + pad * 2, b - t + pad * 2 + (sub_px + 40 if subtitle else 0)
    base = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(base)
    d.text((pad - l, pad - t), text, font=f, fill=255)
    mask = np.array(base).astype(float) / 255.0
    # érosion irrégulière des bords
    n = _noise((w, h), rng, 5)
    mask = np.clip(mask - np.clip((n - 0.8) * 3.0, 0, 1) * 0.7, 0, 1)
    # fines rayures verticales (pellicule)
    for _ in range(int(w / 60)):
        x = int(rng.integers(0, w))
        mask[:, x:x + 1] *= rng.uniform(0.5, 0.9)
    mask_img = Image.fromarray((mask * 255).astype(np.uint8), "L")
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # lueur
    halo = mask_img.filter(ImageFilter.GaussianBlur(px * 0.16))
    halo_arr = np.array(halo).astype(float) / 255.0 * 0.9
    glow_img = np.zeros((h, w, 4), dtype=np.uint8)
    glow_img[..., 0], glow_img[..., 1], glow_img[..., 2] = glow
    glow_img[..., 3] = np.clip(halo_arr * 200, 0, 255).astype(np.uint8)
    out = Image.alpha_composite(out, Image.fromarray(glow_img, "RGBA"))
    # canaux décalés
    if glitch:
        for dx, col in ((-4, (200, 40, 40)), (4, (50, 90, 200))):
            sh = ImageChops.offset(mask_img, dx, 0)
            layer = Image.new("RGBA", (w, h), col + (0,))
            layer.putalpha(sh.point(lambda v: int(v * 0.45)))
            out = Image.alpha_composite(out, layer)
    # texte principal avec dégradé vertical + grain
    grad = np.linspace(1.0, 0.72, h)[:, None] * np.ones((1, w))
    col_arr = np.zeros((h, w, 4), dtype=np.uint8)
    for i in range(3):
        col_arr[..., i] = np.clip(color[i] * grad * (0.9 + 0.1 * n), 0, 255).astype(np.uint8)
    col_arr[..., 3] = (mask * 255).astype(np.uint8)
    out = Image.alpha_composite(out, Image.fromarray(col_arr, "RGBA"))
    d = ImageDraw.Draw(out)
    # coulures sombres sous certaines lettres
    if drip:
        for _ in range(5):
            x = int(rng.integers(pad, w - pad))
            col = mask[:, x]
            ys = np.where(col > 0.5)[0]
            if len(ys):
                y0 = int(ys.max())
                ln = int(rng.integers(12, int(px * 0.5)))
                d.rectangle([x - 1, y0, x + 1, y0 + ln], fill=(120, 18, 18, 220))
                d.ellipse([x - 3, y0 + ln - 2, x + 3, y0 + ln + 5], fill=(120, 18, 18, 220))
    if subtitle:
        sf = pil_font("serif", sub_px)
        tw = d.textlength(subtitle, font=sf)
        d.text(((w - tw) / 2, h - pad - sub_px), subtitle, font=sf, fill=(190, 186, 178, 235))
    return out


def render_label(text, px=40, kind="sans", bold=False, color=(255, 255, 255), shadow=True, pad=8, letter_spacing=0):
    """Texte simple en texture (ombre portée, espacement de lettres)."""
    f = pil_font(kind, px, bold)
    probe = ImageDraw.Draw(Image.new("L", (4, 4)))
    if letter_spacing:
        w = sum(probe.textlength(c, font=f) + letter_spacing for c in text)
        h = int(px * 1.5)
    else:
        l, t, r, b = probe.textbbox((0, 0), text, font=f)
        w, h = r - l, b - t + int(px * 0.4)
    img = Image.new("RGBA", (int(w) + pad * 2 + 4, int(h) + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        xx = pad
        if letter_spacing:
            for c in text:
                sd.text((xx + 2, pad + 2), c, font=f, fill=(0, 0, 0, 200))
                xx += sd.textlength(c, font=f) + letter_spacing
        else:
            sd.text((pad + 2, pad + 2), text, font=f, fill=(0, 0, 0, 200))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(2)))
        d = ImageDraw.Draw(img)
    if letter_spacing:
        for c in text:
            d.text((x, pad), c, font=f, fill=color + (255,))
            x += d.textlength(c, font=f) + letter_spacing
    else:
        d.text((pad, pad), text, font=f, fill=color + (255,))
    return img


# ---------------------------------------------------------------------------
# Papier : lettres manuscrites, reçus, journaux
# ---------------------------------------------------------------------------
def _paper_base(size, rng, tint=(228, 214, 182), stains=5, lines=False, margin=True):
    w, h = size
    n = _noise(size, rng, 12)
    n2 = _noise(size, rng, 3)
    base = np.zeros((h, w, 3))
    for i in range(3):
        base[..., i] = tint[i] * (0.93 + 0.07 * n + 0.03 * n2)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    for _ in range(stains):
        cx, cy = int(rng.integers(0, w)), int(rng.integers(0, h))
        r = int(rng.integers(30, 110))
        st = Image.new("RGBA", (r * 2, r * 2), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.ellipse([2, 2, r * 2 - 2, r * 2 - 2], outline=(120, 80, 36, 70), width=3)
        sd.ellipse([8, 8, r * 2 - 8, r * 2 - 8], fill=(150, 108, 54, 26))
        img.alpha_composite(st.filter(ImageFilter.GaussianBlur(2)), (cx - r, cy - r)) if (0 <= cx - r and 0 <= cy - r and cx + r <= w and cy + r <= h) else None
    if lines:
        for y in range(120, h - 40, 42):
            d.line([(30, y), (w - 30, y)], fill=(90, 120, 170, 70), width=1)
    if margin:
        d.line([(86, 0), (86, h)], fill=(200, 80, 80, 55), width=1)
    # plis
    d.line([(0, h // 3), (w, h // 3 + 3)], fill=(0, 0, 0, 12), width=1)
    d.line([(0, h // 3 + 3), (w, h // 3 + 6)], fill=(255, 255, 255, 30), width=1)
    d.line([(w // 2, 0), (w // 2 + 3, h)], fill=(0, 0, 0, 8), width=1)
    # bords vieillis
    edge = np.zeros((h, w))
    yy, xx = np.mgrid[:h, :w]
    dist = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / 40.0
    edge = np.clip(1 - dist, 0, 1) * (0.45 + 0.5 * n2)
    arr = np.array(img).astype(float)
    arr[..., :3] *= (1 - 0.35 * edge[..., None])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def handwriting_page(text, size=(760, 980), ink=(34, 30, 52), px=34, seed=None, lines=True, tint=(228, 214, 182),
                     line_gap=1.45, jitter=1.0, title=None, tape=True):
    """Page manuscrite : chaque mot a sa propre inclinaison/ligne de base, ratures avec ~~...~~."""
    key = hashlib.md5((text + str(size) + str(ink) + str(px) + str(seed) + str(title)).encode("utf-8")).hexdigest()[:10]
    ck = ("hw", key)
    if ck in _cache:
        return _cache[ck]
    rng = np.random.default_rng(seed if seed is not None else int(key, 16) % (2 ** 31))
    w, h = size
    page = _paper_base(size, rng, tint=tint, lines=lines)
    font = pil_font("hand", px)
    tfont = pil_font("hand", int(px * 1.25), True)
    d = ImageDraw.Draw(page, "RGBA")
    y = 70
    x0 = 104
    if title:
        tw = d.textlength(title, font=tfont)
        d.text(((w - tw) / 2 + 20, 40), title, font=tfont, fill=ink + (230,))
        d.line([((w - tw) / 2 + 14, 40 + px * 1.45), ((w + tw) / 2 + 26, 40 + px * 1.45 + 3)], fill=ink + (170,), width=2)
        y = 40 + int(px * 2.0)
    lh = px * line_gap
    max_w = w - x0 - 56
    paragraphs = text.split("\n")
    for para in paragraphs:
        if not para.strip():
            y += lh * 0.6
            continue
        words = para.split(" ")
        line = []
        cur_w = 0.0

        def flush(line, y):
            x = x0 + rng.uniform(-3, 5) * jitter
            slope = rng.uniform(-0.012, 0.012) * jitter
            for (wd, struck) in line:
                wd_w = d.textlength(wd + " ", font=font)
                layer = Image.new("RGBA", (int(wd_w) + 24, int(px * 2)), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                cx = 8
                for ch in wd:
                    jy = rng.uniform(-2.0, 2.0) * jitter
                    ang = rng.uniform(-4, 4) * jitter
                    gl = Image.new("RGBA", (int(px * 1.4), int(px * 1.8)), (0, 0, 0, 0))
                    ImageDraw.Draw(gl).text((6, 6 + jy), ch, font=font, fill=ink + (int(rng.uniform(190, 245)),))
                    gl = gl.rotate(ang, resample=Image.BICUBIC, center=(px * 0.5, px * 0.8))
                    layer.alpha_composite(gl, (int(cx - 6), 0)) if cx - 6 >= 0 else layer.paste(gl, (0, 0), gl)
                    cx += d.textlength(ch, font=font) * rng.uniform(0.96, 1.04)
                if struck:
                    ld.line([(6, px * 0.78), (cx + 2, px * 0.74)], fill=(150, 30, 30, 220), width=3)
                page.alpha_composite(layer, (int(x), int(y - 6 + (x - x0) * slope))) if (int(x) >= 0 and y - 6 >= 0) else None
                x += wd_w
        struck_mode = False
        for wd in words:
            s = False
            if wd.startswith("~~"):
                struck_mode = True
                wd = wd[2:]
            if wd.endswith("~~"):
                s = True
                wd = wd[:-2]
                cur_struck = True
            else:
                cur_struck = struck_mode
            ww = d.textlength(wd + " ", font=font)
            if cur_w + ww > max_w and line:
                flush(line, y)
                y += lh
                line, cur_w = [], 0.0
            line.append((wd, cur_struck))
            cur_w += ww
            if s:
                struck_mode = False
        if line:
            flush(line, y)
            y += lh
        if y > h - 60:
            break
    # taches d'encre
    for _ in range(int(rng.integers(2, 5))):
        cx, cy = int(rng.integers(100, w - 40)), int(rng.integers(100, h - 40))
        r = int(rng.integers(2, 6))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ink + (140,))
    if tape:
        for (tx, ty, rot) in ((w // 2 - 50, -8, -3), ):
            t = Image.new("RGBA", (120, 40), (230, 220, 170, 150))
            t = t.rotate(rot, expand=True)
            page.alpha_composite(t, (tx, max(0, ty)))
    _cache[ck] = page
    return page


def typed_page(text, size=(700, 900), px=22, seed=5):
    """Reçu / formulaire dactylographié (police monospace, encre grise, bords déchirés)."""
    rng = np.random.default_rng(seed)
    w, h = size
    page = _paper_base(size, rng, tint=(236, 232, 220), lines=False, margin=False)
    d = ImageDraw.Draw(page, "RGBA")
    font = pil_font("mono", px)
    y = 50
    for ln in text.split("\n"):
        wrapped = _wrap_px(d, ln, font, w - 100)
        for sub in wrapped:
            d.text((48 + rng.uniform(-1, 1), y + rng.uniform(-1, 1)), sub, font=font, fill=(44, 44, 50, int(rng.uniform(200, 245))))
            y += px * 1.35
        if not wrapped:
            y += px * 0.8
        if y > h - 50:
            break
    # bord supérieur dentelé
    arr = np.array(page)
    for x in range(0, w, 6):
        hh = int(rng.integers(2, 9))
        arr[:hh, x:x + 6, 3] = 0
    return Image.fromarray(arr, "RGBA")


def newspaper_page(headlines, size=(700, 900), seed=2):
    rng = np.random.default_rng(seed)
    w, h = size
    page = _paper_base(size, rng, tint=(214, 210, 196), lines=False, margin=False)
    d = ImageDraw.Draw(page, "RGBA")
    big = pil_font("title", 54, True)
    d.text((w // 2, 60), "NICE-MATIN", font=big, fill=(20, 20, 22, 240), anchor="mm")
    d.line([(40, 100), (w - 40, 100)], fill=(20, 20, 22, 220), width=3)
    d.line([(40, 106), (w - 40, 106)], fill=(20, 20, 22, 180), width=1)
    y = 130
    hf = pil_font("title", 26, True)
    pil_font("serif", 15)
    for hl in headlines:
        for sub in _wrap_px(d, hl, hf, w - 90):
            d.text((45, y), sub, font=hf, fill=(24, 24, 26, 240))
            y += 32
        # faux texte en colonnes
        for col in range(2):
            cx = 45 + col * (w - 90) // 2 + (12 if col else 0)
            cy = y + 4
            for _ in range(4):
                lw = int(rng.uniform(0.6, 0.98) * ((w - 100) // 2 - 12))
                d.rectangle([cx, cy, cx + lw, cy + 3], fill=(70, 70, 74, 170))
                cy += 9
        y += 56
        d.line([(45, y - 8), (w - 45, y - 8)], fill=(40, 40, 44, 120), width=1)
        if y > h - 120:
            break
    return page


def _wrap_px(draw, text, font, width):
    out, cur = [], ""
    for wd in text.split(" "):
        test = (cur + " " + wd).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                out.append(cur)
            cur = wd
    if cur:
        out.append(cur)
    return out


def phone_note_image(lines, size=(420, 220), seed=1):
    """Petit écran de téléphone fissuré (téléphone de Garnier) : texte clair sur fond sombre fissuré."""
    rng = np.random.default_rng(seed)
    w, h = size
    img = Image.new("RGBA", size, (10, 14, 20, 255))
    d = ImageDraw.Draw(img)
    f = pil_font("sans", 19)
    y = 16
    for ln in lines:
        for sub in _wrap_px(d, ln, f, w - 40):
            d.text((20, y), sub, font=f, fill=(210, 224, 240, 255))
            y += 26
        y += 6
    cx, cy = int(w * 0.7), int(h * 0.3)
    for k in range(9):
        a = k * math.pi / 4.5 + rng.uniform(-0.2, 0.2)
        rr = rng.uniform(80, 240)
        d.line([(cx, cy), (cx + math.cos(a) * rr, cy + math.sin(a) * rr)], fill=(220, 230, 240, 150), width=1)
    return img
