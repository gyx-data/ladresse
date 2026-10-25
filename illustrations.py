"""Illustrations vectorielles dessinées avec Pillow (supersampling x4) : plats QuickEats, icônes du HUD,
objets d'inventaire, avatars des joueurs, carte de suivi, coque du téléphone, etc.

Tout est généré à la demande et mis en cache en mémoire.
"""
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import typography as T

SS = 4
_cache = {}


def _canvas(size):
    w, h = size
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _finish(img, size):
    return img.resize(size, Image.LANCZOS)


def cached(fn):
    def wrap(*a, **k):
        key = (fn.__name__, a, tuple(sorted(k.items())))
        if key not in _cache:
            _cache[key] = fn(*a, **k)
        return _cache[key]
    wrap.__name__ = fn.__name__
    return wrap


def _s(v):
    return int(v * SS)


def _shade(img, strength=0.35):
    """Ombrage doux bas-droite (volume)."""
    w, h = img.size
    yy, xx = np.mgrid[:h, :w]
    g = ((xx / w) * 0.4 + (yy / h) * 0.6)
    a = np.array(img).astype(float)
    k = 1 - strength * g
    a[..., :3] *= k[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _shadow(img, offset=(0, 6), blur=8, alpha=110):
    w, h = img.size
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(img.split()[3].point(lambda v: int(v * alpha / 255)))
    sh = ImageChops.offset(sh, offset[0], offset[1]).filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(sh, img)


# ---------------------------------------------------------------------------
# Plats QuickEats
# ---------------------------------------------------------------------------
@cached
def food_burger(size=256):
    img, d = _canvas((size, size))
    S = size
    _s(S / 2)
    # pain du bas
    d.rounded_rectangle([_s(S * .16), _s(S * .66), _s(S * .84), _s(S * .8)], radius=_s(S * .06), fill=(214, 150, 70))
    # steak
    d.rounded_rectangle([_s(S * .12), _s(S * .54), _s(S * .88), _s(S * .66)], radius=_s(S * .06), fill=(96, 52, 34))
    # fromage
    d.polygon([(_s(S * .14), _s(S * .52)), (_s(S * .86), _s(S * .52)), (_s(S * .78), _s(S * .62)), (_s(S * .66), _s(S * .55)), (_s(S * .5), _s(S * .64)),
               (_s(S * .34), _s(S * .55)), (_s(S * .22), _s(S * .62))], fill=(250, 196, 40))
    # salade
    for i in range(7):
        x = S * (0.14 + i * 0.12)
        d.ellipse([_s(x), _s(S * .44), _s(x + S * .16), _s(S * .56)], fill=(96, 176, 70))
    # tomate
    d.rounded_rectangle([_s(S * .18), _s(S * .5), _s(S * .82), _s(S * .55)], radius=_s(S * .02), fill=(214, 60, 48))
    # pain du haut
    d.pieslice([_s(S * .12), _s(S * .14), _s(S * .88), _s(S * .62)], 180, 360, fill=(228, 160, 76))
    d.pieslice([_s(S * .12), _s(S * .14), _s(S * .88), _s(S * .62)], 180, 360, outline=(170, 110, 46), width=_s(2))
    for (x, y) in ((.32, .3), (.46, .24), (.6, .3), (.5, .36), (.38, .38), (.66, .38)):
        d.ellipse([_s(S * x), _s(S * y), _s(S * x + 9), _s(S * y + 5)], fill=(250, 232, 180))
    img = _shadow(_shade(img, .25), (0, _s(5)), _s(7))
    return _finish(img, (size, size))


@cached
def food_pizza(size=256):
    img, d = _canvas((size, size))
    S = size
    c = _s(S / 2)
    r = _s(S * .42)
    d.ellipse([c - r, c - r, c + r, c + r], fill=(218, 160, 78))
    r2 = r - _s(S * .04)
    d.ellipse([c - r2, c - r2, c + r2, c + r2], fill=(234, 90, 50))
    r3 = r2 - _s(S * .02)
    d.ellipse([c - r3, c - r3, c + r3, c + r3], fill=(252, 214, 96))
    import random
    rnd = random.Random(4)
    for _ in range(26):
        a = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0, r3 * .85)
        x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
        col = rnd.choice([(255, 244, 200), (240, 190, 70), (255, 250, 230)])
        d.ellipse([x - _s(8), y - _s(6), x + _s(8), y + _s(6)], fill=col)
    for k in range(6):
        a = k * math.pi / 3 + .2
        d.line([(c, c), (c + math.cos(a) * r, c + math.sin(a) * r)], fill=(190, 130, 60), width=_s(2))
    img = _shadow(_shade(img, .2), (0, _s(5)), _s(7))
    return _finish(img, (size, size))


@cached
def food_sushi(size=256):
    img, d = _canvas((size, size))
    S = size
    d.rounded_rectangle([_s(S * .08), _s(S * .62), _s(S * .92), _s(S * .8)], radius=_s(S * .05), fill=(60, 40, 30))
    for k, (x, col) in enumerate(((.12, (240, 110, 90)), (.38, (250, 160, 90)), (.64, (240, 110, 90)))):
        xx = S * x
        d.rounded_rectangle([_s(xx), _s(S * .5), _s(xx + S * .24), _s(S * .66)], radius=_s(S * .05), fill=(250, 248, 240))
        d.rounded_rectangle([_s(xx - 2), _s(S * .38), _s(xx + S * .26), _s(S * .54)], radius=_s(S * .06), fill=col)
        d.line([(_s(xx + 6), _s(S * .43)), (_s(xx + S * .2), _s(S * .5))], fill=(255, 220, 200), width=_s(2))
    # maki
    for k, x in enumerate((.2, .5, .78)):
        c = (_s(S * x), _s(S * .26))
        d.ellipse([c[0] - _s(S * .09), c[1] - _s(S * .09), c[0] + _s(S * .09), c[1] + _s(S * .09)], fill=(30, 40, 34))
        d.ellipse([c[0] - _s(S * .065), c[1] - _s(S * .065), c[0] + _s(S * .065), c[1] + _s(S * .065)], fill=(250, 248, 240))
        d.ellipse([c[0] - _s(S * .025), c[1] - _s(S * .025), c[0] + _s(S * .025), c[1] + _s(S * .025)], fill=(236, 100, 80))
    # baguettes
    d.line([(_s(S * .72), _s(S * .06)), (_s(S * .92), _s(S * .5))], fill=(190, 140, 90), width=_s(5))
    d.line([(_s(S * .8), _s(S * .04)), (_s(S * .97), _s(S * .46))], fill=(170, 120, 78), width=_s(5))
    img = _shadow(_shade(img, .2), (0, _s(5)), _s(7))
    return _finish(img, (size, size))


@cached
def food_kebab(size=256):
    img, d = _canvas((size, size))
    S = size
    # pain pita
    d.polygon([(_s(S * .16), _s(S * .32)), (_s(S * .84), _s(S * .26)), (_s(S * .76), _s(S * .88)), (_s(S * .24), _s(S * .88))], fill=(232, 190, 120))
    d.polygon([(_s(S * .22), _s(S * .36)), (_s(S * .78), _s(S * .3)), (_s(S * .72), _s(S * .8)), (_s(S * .28), _s(S * .8))], fill=(242, 214, 160))
    import random
    rnd = random.Random(9)
    for _ in range(14):
        x, y = rnd.uniform(.26, .74), rnd.uniform(.3, .6)
        d.ellipse([_s(S * x), _s(S * y), _s(S * x + 18), _s(S * y + 11)], fill=rnd.choice([(150, 90, 56), (120, 70, 44), (170, 110, 70)]))
    for i in range(5):
        x = .28 + i * .09
        d.ellipse([_s(S * x), _s(S * .28), _s(S * x + 28), _s(S * .4)], fill=(110, 180, 80))
    d.ellipse([_s(S * .4), _s(S * .34), _s(S * .5), _s(S * .42)], fill=(220, 70, 56))
    d.ellipse([_s(S * .56), _s(S * .36), _s(S * .66), _s(S * .44)], fill=(220, 70, 56))
    # frites
    for k in range(7):
        x = .1 + k * .035
        d.rectangle([_s(S * x), _s(S * .5), _s(S * x + 9), _s(S * .8)], fill=(250, 200, 70))
    img = _shadow(_shade(img, .2), (0, _s(5)), _s(7))
    return _finish(img, (size, size))


@cached
def food_dessert(size=256):
    img, d = _canvas((size, size))
    S = size
    d.polygon([(_s(S * .22), _s(S * .4)), (_s(S * .78), _s(S * .4)), (_s(S * .66), _s(S * .88)), (_s(S * .34), _s(S * .88))], fill=(230, 240, 246))
    d.polygon([(_s(S * .24), _s(S * .46)), (_s(S * .76), _s(S * .46)), (_s(S * .7), _s(S * .62)), (_s(S * .3), _s(S * .62))], fill=(110, 60, 40))
    for (x, y, col) in ((.32, .28, (250, 240, 220)), (.5, .22, (250, 200, 210)), (.66, .3, (250, 240, 220))):
        d.ellipse([_s(S * (x - .13)), _s(S * y), _s(S * (x + .13)), _s(S * (y + .24))], fill=col)
    d.ellipse([_s(S * .45), _s(S * .12), _s(S * .55), _s(S * .22)], fill=(200, 30, 50))
    img = _shadow(_shade(img, .2), (0, _s(5)), _s(7))
    return _finish(img, (size, size))


FOODS = {"burger": food_burger, "pizza": food_pizza, "sushi": food_sushi, "kebab": food_kebab, "dessert": food_dessert}


# ---------------------------------------------------------------------------
# Icônes de HUD et d'inventaire
# ---------------------------------------------------------------------------
@cached
def icon_flashlight(size=96, on=True):
    img, d = _canvas((size, size))
    S = size
    # corps incliné
    layer, ld = _canvas((size, size))
    ld.rounded_rectangle([_s(S * .22), _s(S * .4), _s(S * .66), _s(S * .62)], radius=_s(S * .05), fill=(70, 72, 80))
    ld.rounded_rectangle([_s(S * .62), _s(S * .34), _s(S * .82), _s(S * .68)], radius=_s(S * .06), fill=(210, 200, 160) if on else (120, 118, 100))
    ld.rectangle([_s(S * .34), _s(S * .4), _s(S * .38), _s(S * .62)], fill=(40, 40, 46))
    ld.rectangle([_s(S * .46), _s(S * .4), _s(S * .5), _s(S * .62)], fill=(40, 40, 46))
    layer = layer.rotate(25, resample=Image.BICUBIC, center=(_s(S / 2), _s(S / 2)))
    img = Image.alpha_composite(img, layer)
    if on:
        beam = Image.new("RGBA", img.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(beam)
        bd.polygon([(_s(S * .74), _s(S * .62)), (_s(S * 1.0), _s(S * .5)), (_s(S * 1.0), _s(S * .98))], fill=(255, 240, 180, 120))
        img = Image.alpha_composite(img, beam.filter(ImageFilter.GaussianBlur(_s(2))))
    return _finish(img, (size, size))


@cached
def icon_phone(size=96, glow=False):
    img, d = _canvas((size, size))
    S = size
    d.rounded_rectangle([_s(S * .3), _s(S * .12), _s(S * .7), _s(S * .88)], radius=_s(S * .08), fill=(40, 42, 50), outline=(150, 152, 165), width=_s(3))
    d.rounded_rectangle([_s(S * .34), _s(S * .2), _s(S * .66), _s(S * .78)], radius=_s(S * .03), fill=(90, 130, 220) if glow else (28, 34, 52))
    d.ellipse([_s(S * .47), _s(S * .8), _s(S * .53), _s(S * .86)], fill=(150, 152, 165))
    return _finish(img, (size, size))


@cached
def icon_camera(size=96):
    img, d = _canvas((size, size))
    S = size
    d.rounded_rectangle([_s(S * .12), _s(S * .28), _s(S * .88), _s(S * .8)], radius=_s(S * .08), fill=(200, 202, 210))
    d.rectangle([_s(S * .32), _s(S * .2), _s(S * .5), _s(S * .3)], fill=(200, 202, 210))
    d.ellipse([_s(S * .32), _s(S * .36), _s(S * .68), _s(S * .72)], fill=(40, 44, 56))
    d.ellipse([_s(S * .39), _s(S * .43), _s(S * .61), _s(S * .65)], fill=(100, 150, 230))
    d.ellipse([_s(S * .47), _s(S * .46), _s(S * .53), _s(S * .52)], fill=(230, 245, 255))
    return _finish(img, (size, size))


@cached
def icon_battery(size=96, level=1.0):
    img, d = _canvas((size, size))
    S = size
    col = (120, 224, 130) if level > .5 else (240, 190, 70) if level > .2 else (240, 80, 70)
    d.rounded_rectangle([_s(S * .14), _s(S * .32), _s(S * .8), _s(S * .68)], radius=_s(S * .06), outline=(220, 222, 230), width=_s(3))
    d.rectangle([_s(S * .82), _s(S * .42), _s(S * .88), _s(S * .58)], fill=(220, 222, 230))
    fw = (S * .62) * max(0.03, level)
    d.rounded_rectangle([_s(S * .18), _s(S * .36), _s(S * .18 + fw), _s(S * .64)], radius=_s(S * .03), fill=col)
    return _finish(img, (size, size))


@cached
def icon_crown(size=48):
    img, d = _canvas((size, size))
    S = size
    d.polygon([(_s(S * .1), _s(S * .72)), (_s(S * .14), _s(S * .3)), (_s(S * .34), _s(S * .5)), (_s(S * .5), _s(S * .22)), (_s(S * .66), _s(S * .5)),
               (_s(S * .86), _s(S * .3)), (_s(S * .9), _s(S * .72))], fill=(250, 200, 60))
    d.rectangle([_s(S * .1), _s(S * .72), _s(S * .9), _s(S * .82)], fill=(220, 160, 30))
    return _finish(img, (size, size))


@cached
def icon_skull(size=48):
    img, d = _canvas((size, size))
    S = size
    d.ellipse([_s(S * .2), _s(S * .12), _s(S * .8), _s(S * .66)], fill=(224, 224, 230))
    d.rectangle([_s(S * .32), _s(S * .56), _s(S * .68), _s(S * .82)], fill=(224, 224, 230))
    d.ellipse([_s(S * .3), _s(S * .34), _s(S * .46), _s(S * .5)], fill=(20, 20, 26))
    d.ellipse([_s(S * .54), _s(S * .34), _s(S * .7), _s(S * .5)], fill=(20, 20, 26))
    for x in (.4, .5, .6):
        d.line([(_s(S * x), _s(S * .66)), (_s(S * x), _s(S * .8))], fill=(20, 20, 26), width=_s(2))
    return _finish(img, (size, size))


@cached
def icon_chat(size=48):
    img, d = _canvas((size, size))
    S = size
    d.rounded_rectangle([_s(S * .1), _s(S * .16), _s(S * .9), _s(S * .66)], radius=_s(S * .12), fill=(60, 190, 100))
    d.polygon([(_s(S * .26), _s(S * .62)), (_s(S * .2), _s(S * .88)), (_s(S * .46), _s(S * .64))], fill=(60, 190, 100))
    for x in (.3, .5, .7):
        d.ellipse([_s(S * x - 4), _s(S * .4 - 4), _s(S * x + 4), _s(S * .4 + 4)], fill=(255, 255, 255))
    return _finish(img, (size, size))


@cached
def icon_signal(size=48, bars=1):
    img, d = _canvas((size, size))
    S = size
    for i in range(5):
        h = S * (.18 + i * .13)
        col = (240, 240, 245) if i < bars else (90, 92, 104)
        d.rounded_rectangle([_s(S * (.14 + i * .15)), _s(S * .86 - h), _s(S * (.14 + i * .15 + .1)), _s(S * .86)], radius=_s(2), fill=col)
    return _finish(img, (size, size))


@cached
def item_icon(name, size=96):
    img, d = _canvas((size, size))
    S = size
    if name == "pile":
        d.rounded_rectangle([_s(S * .3), _s(S * .22), _s(S * .7), _s(S * .88)], radius=_s(S * .06), fill=(240, 196, 40))
        d.rectangle([_s(S * .42), _s(S * .12), _s(S * .58), _s(S * .22)], fill=(200, 200, 205))
        d.rectangle([_s(S * .3), _s(S * .5), _s(S * .7), _s(S * .62)], fill=(40, 40, 46))
        d.polygon([(_s(S * .54), _s(S * .28)), (_s(S * .44), _s(S * .46)), (_s(S * .5), _s(S * .46)), (_s(S * .46), _s(S * .6))], fill=(40, 40, 46))
    elif name == "cle_tiroir":
        d.ellipse([_s(S * .14), _s(S * .22), _s(S * .42), _s(S * .5)], outline=(220, 180, 70), width=_s(S * .07))
        d.rectangle([_s(S * .4), _s(S * .33), _s(S * .88), _s(S * .4)], fill=(220, 180, 70))
        d.rectangle([_s(S * .72), _s(S * .4), _s(S * .78), _s(S * .54)], fill=(220, 180, 70))
        d.rectangle([_s(S * .82), _s(S * .4), _s(S * .88), _s(S * .5)], fill=(220, 180, 70))
    elif name == "pied_de_biche":
        d.line([(_s(S * .18), _s(S * .84)), (_s(S * .7), _s(S * .24))], fill=(110, 116, 130), width=_s(S * .09))
        d.arc([_s(S * .56), _s(S * .06), _s(S * .88), _s(S * .38)], 200, 360, fill=(110, 116, 130), width=_s(S * .09))
        d.polygon([(_s(S * .1), _s(S * .8)), (_s(S * .22), _s(S * .94)), (_s(S * .26), _s(S * .8))], fill=(90, 96, 110))
    elif name == "sel":
        d.rounded_rectangle([_s(S * .32), _s(S * .3), _s(S * .68), _s(S * .88)], radius=_s(S * .08), fill=(240, 244, 250))
        d.rounded_rectangle([_s(S * .3), _s(S * .16), _s(S * .7), _s(S * .32)], radius=_s(S * .06), fill=(190, 196, 206))
        for (x, y) in ((.42, .1), (.5, .06), (.58, .1)):
            d.ellipse([_s(S * x - 3), _s(S * y - 3), _s(S * x + 3), _s(S * y + 3)], fill=(240, 244, 250))
        d.rectangle([_s(S * .36), _s(S * .5), _s(S * .64), _s(S * .66)], fill=(120, 150, 210))
    elif name == "tisonnier":
        d.line([(_s(S * .2), _s(S * .86)), (_s(S * .76), _s(S * .2))], fill=(54, 54, 60), width=_s(S * .07))
        d.polygon([(_s(S * .72), _s(S * .24)), (_s(S * .92), _s(S * .1)), (_s(S * .86), _s(S * .34))], fill=(54, 54, 60))
    elif name == "trousseau":
        d.ellipse([_s(S * .3), _s(S * .1), _s(S * .7), _s(S * .5)], outline=(190, 192, 200), width=_s(S * .05))
        for k, col in enumerate(((220, 180, 70), (190, 192, 200), (200, 150, 60))):
            a = 20 + k * 40
            layer, ld = _canvas((size, size))
            ld.rectangle([_s(S * .46), _s(S * .46), _s(S * .54), _s(S * .88)], fill=col)
            ld.ellipse([_s(S * .4), _s(S * .8), _s(S * .6), _s(S * .94)], fill=col)
            layer = layer.rotate(a - 40, resample=Image.BICUBIC, center=(_s(S * .5), _s(S * .45)))
            img = Image.alpha_composite(img, layer)
            d = ImageDraw.Draw(img)
    else:   # papiers
        d.polygon([(_s(S * .22), _s(S * .14)), (_s(S * .72), _s(S * .1)), (_s(S * .78), _s(S * .86)), (_s(S * .26), _s(S * .9))], fill=(236, 226, 196))
        for i in range(5):
            y = .26 + i * .12
            d.line([(_s(S * .32), _s(S * y)), (_s(S * .66), _s(S * (y - .01)))], fill=(90, 80, 70), width=_s(2))
        if name == "numero_barre":
            d.line([(_s(S * .26), _s(S * .24)), (_s(S * .74), _s(S * .7))], fill=(190, 40, 40), width=_s(4))
    img = _shadow(img, (0, _s(3)), _s(4), 120)
    return _finish(img, (size, size))


@cached
def avatar(color=(200, 60, 60), size=96, dead=False):
    img, d = _canvas((size, size))
    S = size
    bg = (36, 38, 46) if not dead else (30, 20, 22)
    d.ellipse([_s(S * .04), _s(S * .04), _s(S * .96), _s(S * .96)], fill=bg, outline=tuple(int(c * .8) for c in color), width=_s(S * .045))
    skin = (210, 170, 140) if not dead else (140, 130, 130)
    # épaules / veste
    d.pieslice([_s(S * .14), _s(S * .58), _s(S * .86), _s(S * 1.3)], 180, 360, fill=color)
    d.ellipse([_s(S * .34), _s(S * .22), _s(S * .66), _s(S * .58)], fill=skin)
    if dead:
        d.line([(_s(S * .4), _s(S * .36)), (_s(S * .46), _s(S * .44))], fill=(20, 20, 20), width=_s(3))
        d.line([(_s(S * .46), _s(S * .36)), (_s(S * .4), _s(S * .44))], fill=(20, 20, 20), width=_s(3))
        d.line([(_s(S * .54), _s(S * .36)), (_s(S * .6), _s(S * .44))], fill=(20, 20, 20), width=_s(3))
        d.line([(_s(S * .6), _s(S * .36)), (_s(S * .54), _s(S * .44))], fill=(20, 20, 20), width=_s(3))
    # masque circulaire
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([_s(S * .04), _s(S * .04), _s(S * .96), _s(S * .96)], fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return _finish(out, (size, size))


@cached
def quickeats_logo(size=(300, 90)):
    w, h = size
    img, d = _canvas(size)
    d.rounded_rectangle([_s(4), _s(4), _s(h - 4), _s(h - 4)], radius=_s(h * .24), fill=(255, 112, 8))
    d.rounded_rectangle([_s(h * .26), _s(h * .38), _s(h * .7), _s(h * .74)], radius=_s(8), outline=(255, 255, 255), width=_s(5))
    d.arc([_s(h * .34), _s(h * .2), _s(h * .62), _s(h * .5)], 190, 350, fill=(255, 255, 255), width=_s(5))
    img = _finish(img, size)
    txt = T.render_label("QuickEats", int(h * .5), "sans", True, (255, 255, 255), shadow=False, pad=0)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(img, (0, 0))
    out.alpha_composite(txt, (int(h * 1.0), int((h - txt.height) / 2)))
    return out


# ---------------------------------------------------------------------------
# Coque du téléphone et carte de suivi
# ---------------------------------------------------------------------------
@cached
def phone_body(w=640, h=1250):
    """Coque noire arrondie avec cadre brillant, encoche caméra, boutons latéraux et reflet de vitre."""
    img, d = _canvas((w, h))
    W, H = w * SS, h * SS
    d.rounded_rectangle([_s(14), _s(8), W - _s(14), H - _s(8)], radius=_s(80), fill=(18, 18, 22), outline=(86, 88, 100), width=_s(5))
    d.rounded_rectangle([_s(26), _s(20), W - _s(26), H - _s(20)], radius=_s(70), fill=(6, 6, 8), outline=(30, 31, 38), width=_s(3))
    # boutons latéraux
    d.rounded_rectangle([_s(6), _s(h * .22), _s(16), _s(h * .32)], radius=_s(4), fill=(70, 72, 84))
    d.rounded_rectangle([W - _s(16), _s(h * .28), W - _s(6), _s(h * .42)], radius=_s(4), fill=(70, 72, 84))
    # caméra frontale
    d.ellipse([W // 2 - _s(10), _s(46), W // 2 + _s(10), _s(66)], fill=(24, 30, 44), outline=(60, 70, 96), width=_s(2))
    d.rounded_rectangle([W // 2 - _s(60), _s(50), W // 2 - _s(24), _s(58)], radius=_s(4), fill=(30, 32, 40))
    img = _finish(img, (w, h))
    # reflet diagonal sur la vitre
    gl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    gd.polygon([(w * .1, 0), (w * .5, 0), (w * .06, h * .5), (0, h * .5)], fill=(255, 255, 255, 14))
    return Image.alpha_composite(img, gl)


@cached
def map_texture(w=420, h=420):
    """Plan de quartier nocturne pour l'écran de suivi QuickEats (rues, îlots, parc, itinéraire)."""
    rng = np.random.default_rng(12)
    img, d = _canvas((w, h))
    W, H = w * SS, h * SS
    d.rectangle([0, 0, W, H], fill=(28, 32, 40))
    # îlots de bâtiments
    for gx in range(0, w, 70):
        for gy in range(0, h, 70):
            x0, y0 = gx + 14, gy + 14
            for _ in range(3):
                bx = x0 + int(rng.integers(0, 24))
                by = y0 + int(rng.integers(0, 24))
                bw, bh = int(rng.integers(14, 30)), int(rng.integers(14, 30))
                c = int(rng.integers(40, 58))
                d.rectangle([_s(bx), _s(by), _s(bx + bw), _s(by + bh)], fill=(c, c + 4, c + 12))
    # parc
    d.rounded_rectangle([_s(w * .62), _s(h * .08), _s(w * .94), _s(h * .34)], radius=_s(10), fill=(32, 58, 44))
    # rues
    for k in range(0, w, 70):
        d.rectangle([_s(k + 1), 0, _s(k + 13), H], fill=(52, 56, 66))
        d.line([(_s(k + 7), 0), (_s(k + 7), H)], fill=(72, 76, 88), width=_s(1))
    for k in range(0, h, 70):
        d.rectangle([0, _s(k + 1), W, _s(k + 13)], fill=(52, 56, 66))
        d.line([(0, _s(k + 7)), (W, _s(k + 7))], fill=(72, 76, 88), width=_s(1))
    # grande avenue en diagonale
    d.line([(0, _s(h * .86)), (W, _s(h * .14))], fill=(64, 68, 80), width=_s(16))
    return _finish(img, (w, h))


@cached
def app_banner(kind="quickeats", w=640, h=120):
    img, d = _canvas((w, h))
    W, H = w * SS, h * SS
    cols = {"quickeats": ((255, 130, 20), (230, 70, 10)), "bank": ((40, 90, 210), (16, 40, 140)),
            "messages": ((50, 60, 70), (28, 32, 40)), "calls": ((36, 40, 48), (22, 24, 30))}[kind]
    a = np.linspace(0, 1, H)[:, None, None]
    c0, c1 = np.array(cols[0]), np.array(cols[1])
    arr = (c0 * (1 - a) + c1 * a) * np.ones((1, W, 1))
    base = Image.fromarray(arr.astype(np.uint8), "RGB").convert("RGBA")
    return base.resize((w, h), Image.LANCZOS)
