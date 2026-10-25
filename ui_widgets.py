"""Petite boîte à outils d'interface (Ursina UI) partagée par le téléphone, les menus, etc."""
import math

from ursina import Entity, Text, Button, Mesh, color, camera, Vec3, curve

import config

# Position/échelle de texte : tient compte de l'option « Taille des textes »


def text_scale():
    return config.TEXT_SCALE.get(config.settings["taille_texte"], 1.0)


def rgb(r, g, b, a=255):
    return color.rgba32(r, g, b, a)


def label(parent, text, x=0.0, y=0.0, size=1.0, col=color.white, origin=(0, 0), wrap=None, z=-0.01,
          scale_text=True, bold=False, align=None):
    kw = {}
    if wrap:
        kw["wordwrap"] = wrap
    t = Text(parent=parent, text=text if text else " ", position=(x, y, z), origin=origin,
             scale=size * (text_scale() if scale_text else 1.0), color=col, **kw)
    if align == "center":
        t.origin = (0, 0)
    return t


def rect(parent, x, y, w, h, col=color.black, z=0.0, texture=None, rotation=0.0):
    e = Entity(parent=parent, model="quad", position=(x, y, z), scale=(w, h), color=col, rotation_z=rotation)
    if texture is not None:
        e.texture = texture
    return e


def button(parent, text, x, y, w, h, on_click=None, col=None, text_col=color.white, size=0.8, z=-0.02,
           highlight=None, press=None):
    col = col if col is not None else rgb(40, 40, 46, 235)
    kw = {}
    if text:
        kw = dict(text=text, text_color=text_col, text_size=size * text_scale())
    b = Button(parent=parent, model="quad", position=(x, y, z), scale=(w, h), color=col,
               highlight_color=highlight or col.tint(0.12), pressed_color=press or col.tint(-0.1), **kw)
    if on_click:
        b.on_click = on_click
    return b


def clear(entity):
    for c in list(entity.children):
        c.disable()
        c.parent = None
        try:
            from ursina import destroy
            destroy(c)
        except Exception:
            pass


def star(parent, x, y, size, col=color.rgb32(255, 200, 40), z=-0.02):
    """Étoile à 5 branches (mesh)."""
    verts = [Vec3(0, 0, 0)]
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = 0.5 if i % 2 == 0 else 0.22
        verts.append(Vec3(math.cos(a) * r, math.sin(a) * r, 0))
    tris = []
    for i in range(10):
        tris.extend([0, 1 + i, 1 + (i + 1) % 10])
    m = Mesh(vertices=verts, triangles=tris, mode="triangle")
    return Entity(parent=parent, model=m, position=(x, y, z), scale=size, color=col)


class Toast:
    """Message court affiché en bas de l'écran (ou d'un parent)."""

    def __init__(self, parent=None, y=-0.42):
        self.root = Entity(parent=parent or camera.ui, z=-5)
        self.bg = rect(self.root, 0, y, 0.7, 0.07, rgb(0, 0, 0, 200))
        self.text = label(self.root, "", 0, y, 0.9, color.white)
        self.root.enabled = False
        self.timer = 0.0

    def show(self, message, duration=2.5, col=color.white):
        self.text.text = message
        self.text.color = col
        self.root.enabled = True
        self.timer = duration

    def update(self, dt):
        if self.timer > 0:
            self.timer -= dt
            if self.timer <= 0:
                self.root.enabled = False


def fade_in(entity, duration=0.4):
    entity.alpha = 0
    entity.animate("alpha", 1, duration=duration, curve=curve.linear)
