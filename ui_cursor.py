"""Curseur de souris d'ambiance : pointe blanche effilée qui respire, traînée fantôme,
anneau rotatif au survol d'un élément cliquable, écrasement au clic.

Remplace le curseur du système dès que la souris est libre (menus, téléphone, documents).
Dessiné avec Pillow au lancement : aucun fichier externe.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter
from ursina import Entity, Button, camera, mouse, time, color, Vec3

import ui_theme as theme

S = 128                 # taille des textures (px)
SIZE = 0.034            # taille à l'écran (unités d'interface)
TIP = (14, 10)          # position de la pointe dans la texture (px)


def _pointer_img():
    # silhouette : flèche longue et fine, encoche asymétrique (griffe)
    pts = [(14, 10), (14, 104), (38, 80), (56, 118), (70, 111), (52, 75), (88, 73)]
    k = 4
    big = Image.new("RGBA", (S * k, S * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.polygon([(x * k, y * k) for x, y in pts], fill=(255, 255, 255, 255))
    img = big.resize((S, S), Image.LANCZOS)
    # ombre très légère : la pointe reste lisible sur le papier clair
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.putalpha(img.split()[3].point(lambda v: int(v * 0.55)))
    shadow = shadow.transform((S, S), Image.AFFINE, (1, 0, -2, 0, 1, -3)).filter(ImageFilter.GaussianBlur(2.2))
    return Image.alpha_composite(shadow, img)


def _glow_img():
    base = _pointer_img().split()[3]
    glow = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    glow.putalpha(base.filter(ImageFilter.GaussianBlur(7)).point(lambda v: min(255, int(v * 1.6))))
    return glow


def _ring_img():
    k = 4
    big = Image.new("RGBA", (S * k, S * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    m = 10 * k
    for a0 in (0, 120, 240):           # trois arcs : cercle « brisé »
        d.arc([m, m, S * k - m, S * k - m], a0, a0 + 78, fill=(255, 255, 255, 235), width=5 * k)
    return big.resize((S, S), Image.LANCZOS)


class HorrorCursor(Entity):
    """Entité mise à jour à chaque image (type non ignoré par l'optimisation de main.py)."""

    def __init__(self):
        super().__init__(parent=camera.ui, z=-99)
        tp = theme._tex(_pointer_img())
        self.ghosts = []
        for i in range(4):
            g = Entity(parent=self, model="quad", texture=tp, scale=SIZE, color=color.rgba(1, 1, 1, 0.0), z=0.02 + i * 0.001)
            self.ghosts.append([g, Vec3(0, 0, 0)])
        self.glow = Entity(parent=self, model="quad", texture=theme._tex(_glow_img()), scale=SIZE, z=0.01)
        self.ring = Entity(parent=self, model="quad", texture=theme._tex(_ring_img()), scale=SIZE * 0.9, z=0.005,
                           color=color.rgba(1, 1, 1, 0))
        self.pointer = Entity(parent=self, model="quad", texture=tp, scale=SIZE, z=0)
        self.t = 0.0
        self.hover = 0.0
        self.press = 0.0
        self.flicker = 0.0
        self.active = None

    @staticmethod
    def _offset(scale):
        # décale le quad pour que la pointe dessinée tombe exactement sur la position de la souris
        return Vec3(scale * (0.5 - TIP[0] / S), scale * (TIP[1] / S - 0.5), 0)

    def _clickable(self):
        e = mouse.hovered_entity
        return isinstance(e, Button) and (getattr(e, "on_click", None) is not None or hasattr(e, "toggle"))

    def update(self):
        free = not mouse.locked
        if free != self.active:
            self.active = free
            for c in self.children:
                c.enabled = free
            if free:                           # la traînée repart de la souris, pas de l'ancienne position
                start = Vec3(mouse.x, mouse.y, 0) + self._offset(SIZE)
                for gp in self.ghosts:
                    gp[1] = Vec3(start)
        if not free:
            return
        if mouse.visible:                      # le curseur système reste caché derrière le nôtre
            mouse.visible = False
        dt = min(time.dt, 0.05)
        self.t += dt
        target = 1.0 if self._clickable() else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 12)
        if mouse.left:
            self.press = 1.0
        self.press = max(0.0, self.press - dt * 5)
        # rares saccades
        if self.flicker <= 0 and random.random() < dt * 0.25:
            self.flicker = 0.12
        self.flicker = max(0.0, self.flicker - dt)
        p = Vec3(mouse.x, mouse.y, 0)
        k = (1.0 + 0.14 * self.hover) * (1.0 - 0.18 * self.press)
        sc = SIZE * k
        self.pointer.scale = sc
        self.pointer.position = p + self._offset(sc)
        self.pointer.rotation_z = -6 * self.hover
        a = 0.3 if self.flicker > 0.06 else 1.0
        self.pointer.color = color.rgba(1, 1, 1, a)
        breath = 0.32 + 0.22 * math.sin(self.t * 2.4) + 0.3 * self.hover
        self.glow.scale = sc * 1.05
        self.glow.position = self.pointer.position
        self.glow.color = color.rgba(1, 1, 1, breath * a)
        self.ring.position = p
        self.ring.rotation_z = self.t * 140
        self.ring.scale = SIZE * (0.75 + 0.15 * self.hover + 0.25 * self.press)
        self.ring.color = color.rgba(1, 1, 1, 0.85 * self.hover)
        # traînée fantôme : chaque copie suit la précédente avec retard
        prev = self.pointer.position
        for i, gp in enumerate(self.ghosts):
            g, pos = gp
            pos += (prev - pos) * min(1.0, dt * (22 - i * 4))
            gp[1] = pos
            g.position = pos
            g.scale = sc * (1 - 0.05 * (i + 1))
            speed = (prev - pos).length()
            g.color = color.rgba(1, 1, 1, min(0.28, speed * 6) * (1 - i * 0.22))
            prev = pos
