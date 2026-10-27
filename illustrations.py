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
    if name.startswith("primeur_"):
        # fruit/légume de l'étal : trois fruits ronds de sa couleur (reflet + queue + feuille)
        import inventory
        col = tuple(int(c * 255) for c in inventory.ITEM_DEFS.get(name, ("", "", (0.8, 0.3, 0.2), True))[2])
        dark = tuple(int(c * 0.7) for c in col)
        for (x, y, r) in ((.36, .62, .2), (.64, .62, .2), (.5, .4, .21)):
            d.ellipse([_s(S * (x - r)), _s(S * (y - r)), _s(S * (x + r)), _s(S * (y + r))], fill=col, outline=dark, width=_s(S * .02))
            d.ellipse([_s(S * (x - r * .55)), _s(S * (y - r * .6)), _s(S * (x - r * .1)), _s(S * (y - r * .25))], fill=(255, 255, 255, 90))
        d.line([(_s(S * .5), _s(S * .2)), (_s(S * .53), _s(S * .1))], fill=(90, 60, 30), width=_s(S * .03))
        d.ellipse([_s(S * .53), _s(S * .08), _s(S * .7), _s(S * .16)], fill=(70, 140, 50))
    elif name == "pile":
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


# ---------------------------------------------------------------------------
# Téléphone : coque, fond d'écran, icônes d'applis, pictogrammes (interface du téléphone)
# ---------------------------------------------------------------------------
def _vgrad(w, h, top, bot):
    """Image RGBA en dégradé vertical (couleurs RGB ou RGBA)."""
    top = tuple(top) + ((255,) if len(top) == 3 else ())
    bot = tuple(bot) + ((255,) if len(bot) == 3 else ())
    a = np.linspace(0, 1, h)[:, None, None]
    arr = (np.array(top, float) * (1 - a) + np.array(bot, float) * a) * np.ones((1, w, 1))
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def _mask_rr(w, h, r, box=None):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle(box or [0, 0, w - 1, h - 1], radius=r, fill=255)
    return m


@cached
def phone_frame(w=464, h=874, sw=432, sh=842, radius=58, screen_radius=40):
    """Coque du téléphone vue de face : cadre titane, bordure noire, trou transparent à la place de l'écran
    (coins arrondis) — posée DEVANT le contenu de l'écran pour en arrondir les angles."""
    S = 3
    W, H = w * S, h * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = 3 * S                                         # marge pour les boutons latéraux
    # boutons latéraux (volume à gauche, verrouillage à droite)
    for (y0, y1) in ((.2, .25), (.28, .36), (.38, .46)):
        d.rounded_rectangle([0, int(H * y0), m + 4 * S, int(H * y1)], radius=2 * S, fill=(58, 60, 68))
    d.rounded_rectangle([W - m - 4 * S, int(H * .3), W - 1, int(H * .42)], radius=2 * S, fill=(58, 60, 68))
    # cadre métallique (dégradé + liseré clair)
    body = _vgrad(W - 2 * m, H - 2 * m, (92, 94, 104), (40, 41, 48))
    img.paste(body, (m, m), _mask_rr(W - 2 * m, H - 2 * m, radius * S))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([m, m, W - m - 1, H - m - 1], radius=radius * S, outline=(150, 152, 164), width=int(1.4 * S))
    # verre noir
    g = 4 * S
    d.rounded_rectangle([m + g, m + g, W - m - g - 1, H - m - g - 1], radius=(radius - 4) * S, fill=(4, 4, 6))
    # trou de l'écran
    sx0 = (W - sw * S) // 2
    sy0 = (H - sh * S) // 2
    hole = _mask_rr(W, H, screen_radius * S, [sx0, sy0, sx0 + sw * S - 1, sy0 + sh * S - 1])
    a = np.array(img.split()[3]).astype(np.int16) - np.array(hole).astype(np.int16)
    img.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L"))
    return img.resize((w, h), Image.LANCZOS)


@cached
def phone_glow(w=600, h=1010, inner=(464, 874), col=(140, 170, 255)):
    """Halo lumineux de l'écran dans le noir + ombre portée (posé derrière la coque)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x0, y0 = (w - inner[0]) // 2, (h - inner[1]) // 2
    ImageDraw.Draw(img).rounded_rectangle([x0 - 6, y0 - 6, x0 + inner[0] + 6, y0 + inner[1] + 6], radius=70, fill=col + (70,))
    img = img.filter(ImageFilter.GaussianBlur(26))
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x0 + 8, y0 + 22, x0 + inner[0] - 8, y0 + inner[1] + 14], radius=60, fill=(0, 0, 0, 170))
    return Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(14)))


@cached
def phone_wallpaper(w=432, h=842):
    """Fond d'écran : nuit sur le Mont-Boron, lune voilée, une maison isolée avec une seule fenêtre allumée."""
    rng = np.random.default_rng(1713)
    yy = np.linspace(0, 1, h)[:, None]
    xx = np.linspace(0, 1, w)[None, :]
    top, mid, bot = np.array((10, 14, 30.)), np.array((30, 24, 50.)), np.array((8, 7, 12.))
    t = (yy * np.ones((1, w)))[..., None]
    arr = np.where(t < .55, top * (1 - t / .55) + mid * (t / .55), mid * (1 - (t - .55) / .45) + bot * ((t - .55) / .45))
    # halo de lune
    mx, my = .76, .56                    # lune basse, sous les icônes (l'horloge reste lisible)
    dist = np.sqrt(((xx - mx) * w / h) ** 2 + (yy - my) ** 2)
    arr = arr + (np.exp(-(dist / .16) ** 2) * 70)[..., None] * np.array((.75, .8, 1.0))
    # nuages : bruit basse fréquence étiré
    n = rng.random((12, 6))
    cl = np.array(Image.fromarray((n * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)).astype(float) / 255
    band = np.exp(-((yy - .3) / .14) ** 2)
    arr *= (1 - .35 * np.clip(cl - .45, 0, 1) * 2 * band)[..., None]
    # étoiles
    for _ in range(70):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, int(h * .45)))
        arr[y, x] = np.minimum(255, arr[y, x] + rng.uniform(40, 120))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    d = ImageDraw.Draw(img)
    moon = Image.new("L", (w, h), 0)
    ImageDraw.Draw(moon).ellipse([w * mx - 20, h * my - 20, w * mx + 20, h * my + 20], fill=255)
    ImageDraw.Draw(moon).ellipse([w * mx - 11, h * my - 25, w * mx + 27, h * my + 13], fill=0)      # croissant
    img.paste((226, 228, 236, 255), (0, 0), moon.filter(ImageFilter.GaussianBlur(0.6)))
    # collines
    pts = [(0, h)]
    for i in range(0, w + 8, 8):
        pts.append((i, h * (.66 - .05 * math.sin(i / w * 3.1 + .4) - .02 * math.sin(i / w * 11))))
    pts.append((w, h))
    d.polygon(pts, fill=(14, 13, 22))
    # la maison (pignon) et sa fenêtre allumée
    hx, hy = w * .3, h * .62
    d.polygon([(hx - 34, hy), (hx, hy - 30), (hx + 34, hy)], fill=(6, 6, 10))
    d.rectangle([hx - 28, hy, hx + 28, hy + 40], fill=(6, 6, 10))
    d.rectangle([hx + 6, hy + 10, hx + 16, hy + 22], fill=(255, 196, 110))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([hx - 9, hy - 7, hx + 31, hy + 39], fill=(255, 170, 80, 60))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(img)
    pts = [(0, h)]
    for i in range(0, w + 8, 8):
        pts.append((i, h * (.74 - .03 * math.sin(i / w * 5 + 1.7))))
    pts.append((w, h))
    d.polygon(pts, fill=(5, 5, 8))
    # grain
    a = np.array(img).astype(float)
    a[..., :3] *= rng.normal(1.0, .035, (h, w))[..., None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def _glyph_draw(img, name, S, c, x0=0.0, y0=0.0):
    """Dessine le pictogramme `name` dans le carré (x0, y0, côté S) de l'image, couleur c (RGBA)."""
    d = ImageDraw.Draw(img)

    def P(x, y):
        return (x0 + x * S, y0 + y * S)

    def B(a, b, cc, dd):
        return [x0 + a * S, y0 + b * S, x0 + cc * S, y0 + dd * S]
    lw = max(1, int(S * .09))
    clear = (0, 0, 0, 0)
    if name == "back":
        d.line([P(.62, .2), P(.32, .5), P(.62, .8)], fill=c, width=lw, joint="curve")
    elif name == "next":
        d.line([P(.38, .2), P(.68, .5), P(.38, .8)], fill=c, width=lw, joint="curve")
    elif name == "send":
        d.line([P(.5, .8), P(.5, .26)], fill=c, width=lw)
        d.line([P(.26, .48), P(.5, .24), P(.74, .48)], fill=c, width=lw, joint="curve")
    elif name in ("phone", "hangup"):
        lay = Image.new("RGBA", img.size, clear)
        ld = ImageDraw.Draw(lay)
        ld.arc(B(.14, .26, .86, .98), 200, 340, fill=c, width=int(S * .15))
        ld.rounded_rectangle(B(.08, .5, .32, .68), radius=int(S * .07), fill=c)
        ld.rounded_rectangle(B(.68, .5, .92, .68), radius=int(S * .07), fill=c)
        if name == "phone":
            lay = lay.rotate(135, resample=Image.BICUBIC, center=P(.5, .5))
        img.alpha_composite(lay)
    elif name == "backspace":
        d.polygon([P(.06, .5), P(.3, .22), P(.92, .22), P(.92, .78), P(.3, .78)], outline=c, width=lw)
        d.line([P(.46, .37), P(.72, .63)], fill=c, width=lw)
        d.line([P(.72, .37), P(.46, .63)], fill=c, width=lw)
    elif name == "search":
        d.ellipse(B(.14, .14, .62, .62), outline=c, width=lw)
        d.line([P(.56, .56), P(.84, .84)], fill=c, width=int(lw * 1.3))
    elif name == "pin":
        d.ellipse(B(.22, .08, .78, .62), fill=c)
        d.polygon([P(.27, .46), P(.5, .94), P(.73, .46)], fill=c)
        d.ellipse(B(.39, .24, .61, .46), fill=clear)
    elif name == "check":
        d.line([P(.18, .52), P(.42, .76), P(.84, .28)], fill=c, width=int(lw * 1.4), joint="curve")
    elif name == "cross":
        d.line([P(.24, .24), P(.76, .76)], fill=c, width=int(lw * 1.4))
        d.line([P(.76, .24), P(.24, .76)], fill=c, width=int(lw * 1.4))
    elif name == "bag":
        d.rounded_rectangle(B(.18, .36, .82, .88), radius=int(S * .09), outline=c, width=int(lw * 1.2))
        d.arc(B(.34, .12, .66, .52), 180, 360, fill=c, width=int(lw * 1.2))
    elif name == "card":
        d.rounded_rectangle(B(.08, .22, .92, .78), radius=int(S * .08), outline=c, width=lw)
        d.rectangle(B(.08, .34, .92, .45), fill=c)
    elif name == "torch":
        d.polygon([P(.26, .08), P(.74, .08), P(.64, .4), P(.36, .4)], fill=c)
        d.rounded_rectangle(B(.36, .42, .64, .92), radius=int(S * .05), fill=c)
        d.ellipse(B(.44, .54, .56, .66), fill=clear)
    elif name == "rain":
        d.ellipse(B(.12, .28, .5, .62), fill=c)
        d.ellipse(B(.32, .14, .78, .56), fill=c)
        d.rounded_rectangle(B(.12, .42, .88, .62), radius=int(S * .1), fill=c)
        for x in (.3, .5, .7):
            d.line([P(x, .72), P(x - .07, .9)], fill=c, width=lw)
    elif name == "battery_dead":
        d.rounded_rectangle(B(.08, .3, .82, .7), radius=int(S * .08), outline=c, width=lw)
        d.rectangle(B(.85, .42, .92, .58), fill=c)
        d.rectangle(B(.15, .37, .23, .63), fill=c)
    elif name == "speaker":
        d.polygon([P(.14, .38), P(.32, .38), P(.54, .18), P(.54, .82), P(.32, .62), P(.14, .62)], fill=c)
        d.arc(B(.46, .3, .78, .7), -50, 50, fill=c, width=lw)
    elif name == "mute":
        d.rounded_rectangle(B(.38, .12, .62, .58), radius=int(S * .12), fill=c)
        d.arc(B(.26, .3, .74, .72), 0, 180, fill=c, width=lw)
        d.line([P(.5, .72), P(.5, .86)], fill=c, width=lw)
    elif name == "keypad":
        for i in range(3):
            for j in range(3):
                d.ellipse(B(.2 + i * .23, .14 + j * .23, .34 + i * .23, .28 + j * .23), fill=c)
        d.ellipse(B(.43, .83, .57, .97), fill=c)


@cached
def glyph(name, size=64, col=(255, 255, 255)):
    """Pictogramme vectoriel (chevrons, combiné, envoyer, effacer, loupe, épingle...)."""
    img = Image.new("RGBA", (size * SS, size * SS), (0, 0, 0, 0))
    _glyph_draw(img, name, size * SS, tuple(col) + ((255,) if len(col) == 3 else ()))
    return _finish(img, (size, size))


APP_ICON_COLORS = {
    "quickeats": ((255, 150, 50), (232, 70, 18), "bag"),
    "banque": ((70, 128, 255), (22, 52, 170), None),
    "messages": ((96, 226, 120), (30, 168, 74), None),
    "appels": ((92, 224, 116), (28, 160, 66), "phone"),
    "camera": ((170, 174, 186), (88, 92, 104), None),
    "lampe": ((64, 66, 78), (24, 25, 30), "torch"),
    "systeme": ((126, 130, 142), (72, 74, 86), "battery_dead"),
}


@cached
def app_icon(name, size=160):
    """Icône d'appli « squircle » : dégradé, reflet, pictogramme blanc."""
    top, bot, gname = APP_ICON_COLORS.get(name, ((120, 120, 130), (60, 60, 70), None))
    S = size * SS
    mask = _mask_rr(S, S, int(S * .235))
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(_vgrad(S, S, top, bot), (0, 0), mask)
    w = (255, 255, 255, 255)
    if name == "lampe":
        beam = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(beam).polygon([(S * .36, S * .32), (S * .64, S * .32), (S * .92, S * .0), (S * .08, S * .0)], fill=(255, 220, 120, 90))
        beam = beam.filter(ImageFilter.GaussianBlur(S * .03))
        beam.putalpha(ImageChops.multiply(beam.split()[3], mask))
        out = Image.alpha_composite(out, beam)
    if gname:
        col = (255, 212, 96, 255) if name == "lampe" else w
        k = .54 if name != "lampe" else .5
        _glyph_draw(out, gname, S * k, col, S * (1 - k) / 2, S * (1 - k) / 2 + (S * .06 if name == "lampe" else 0))
    d = ImageDraw.Draw(out)
    if name == "banque":
        d.polygon([(S * .18, S * .38), (S * .5, S * .18), (S * .82, S * .38)], fill=w)
        for x in (.28, .43, .57, .72):
            d.rectangle([S * (x - .045), S * .43, S * (x + .045), S * .69], fill=w)
        d.rectangle([S * .18, S * .73, S * .82, S * .8], fill=w)
    elif name == "messages":
        d.ellipse([S * .15, S * .2, S * .85, S * .72], fill=w)
        d.polygon([(S * .26, S * .6), (S * .18, S * .84), (S * .44, S * .68)], fill=w)
    elif name == "camera":
        d.rounded_rectangle([S * .14, S * .3, S * .86, S * .76], radius=int(S * .08), fill=(34, 36, 44))
        d.rounded_rectangle([S * .36, S * .22, S * .58, S * .33], radius=int(S * .03), fill=(34, 36, 44))
        d.ellipse([S * .33, S * .35, S * .67, S * .69], fill=(206, 210, 222))
        d.ellipse([S * .39, S * .41, S * .61, S * .63], fill=(28, 38, 70))
        d.ellipse([S * .44, S * .44, S * .51, S * .51], fill=(170, 200, 255))
        d.ellipse([S * .73, S * .36, S * .79, S * .42], fill=(255, 196, 70))
    # reflet doux en haut
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([-S * .3, -S * .75, S * 1.3, S * .42], fill=(255, 255, 255, 28))
    hl.putalpha(ImageChops.multiply(hl.split()[3], mask))
    out = Image.alpha_composite(out, hl)
    return out.resize((size, size), Image.LANCZOS)


@cached
def round_food(kind="burger", size=128, bg=(48, 40, 36)):
    """Vignette ronde d'un plat QuickEats (catégories)."""
    S = size * SS
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse([0, 0, S - 1, S - 1], fill=bg + (255,))
    food = FOODS.get(kind)
    if food is not None:
        out.alpha_composite(food(256).resize((int(S * .78), int(S * .78)), Image.LANCZOS), (int(S * .11), int(S * .11)))
    return out.resize((size, size), Image.LANCZOS)


@cached
def rounded_food(kind="burger", size=150, bg=(54, 42, 34)):
    """Photo de plat dans un cadre arrondi (cartes du menu QuickEats)."""
    S = size * 2
    img = _vgrad(S, S, tuple(min(255, c + 26) for c in bg), bg)
    food = FOODS.get(kind)
    if food is not None:
        s = int(S * .9)
        img.alpha_composite(food(256).resize((s, s), Image.LANCZOS), ((S - s) // 2, (S - s) // 2))
    img.putalpha(_mask_rr(S, S, int(S * .22)))
    return img.resize((size, size), Image.LANCZOS)


@cached
def map_card(w=400, h=300, radius=26):
    """Plan de suivi arrondi (rues, parc) avec l'itinéraire du livreur jusqu'au 17 rue des Lilas."""
    base = map_texture(420, 420).resize((w, w), Image.LANCZOS).crop((0, 0, w, h)).convert("RGBA")
    d = ImageDraw.Draw(base)
    d.line(MAP_ROUTE_PX(w, h), fill=(255, 140, 40, 255), width=6, joint="curve")
    base.putalpha(_mask_rr(w, h, radius))
    return base


def MAP_ROUTE_PX(w, h):
    """Itinéraire du livreur sur la carte (pixels), partagé avec l'appli pour placer le point mobile."""
    return [(w * x, h * y) for x, y in MAP_ROUTE]


MAP_ROUTE = [(.02, .245), (.35, .245), (.35, .689), (.85, .689)]     # le long des rues du plan


@cached
def spinner_ring(size=96, col=(255, 122, 26)):
    img, d = _canvas((size, size))
    S = size * SS
    d.arc([S * .08, S * .08, S * .92, S * .92], 0, 360, fill=(255, 255, 255, 40), width=int(S * .08))
    d.arc([S * .08, S * .08, S * .92, S * .92], -90, 30, fill=col + (255,), width=int(S * .08))
    return _finish(img, (size, size))


@cached
def status_badge(kind="check", size=160):
    """Grand rond de statut (validé vert / erreur rouge / attente orange) avec halo."""
    col = {"check": (52, 199, 89), "cross": (230, 58, 58), "clock": (255, 140, 40)}[kind]
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([S * .06, S * .06, S * .94, S * .94], fill=col + (80,))
    img = img.filter(ImageFilter.GaussianBlur(S * .04))
    d = ImageDraw.Draw(img)
    d.ellipse([S * .18, S * .18, S * .82, S * .82], fill=col + (255,))
    if kind == "clock":
        d.line([(S * .5, S * .5), (S * .5, S * .31)], fill=(255, 255, 255), width=int(S * .05))
        d.line([(S * .5, S * .5), (S * .64, S * .58)], fill=(255, 255, 255), width=int(S * .05))
    else:
        _glyph_draw(img, kind, S * .44, (255, 255, 255, 255), S * .28, S * .28)
    return img.resize((size, size), Image.LANCZOS)


@cached
def soft_circle(size=128, col=(255, 214, 120), alpha=200):
    """Disque flou (halo de la lampe, lueurs)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([size * .2, size * .2, size * .8, size * .8], fill=col + (alpha,))
    return img.filter(ImageFilter.GaussianBlur(size * .1))
