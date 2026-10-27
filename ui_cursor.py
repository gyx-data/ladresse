"""Curseur de souris : flèche blanche aux bords arrondis, fin liseré gris et ombre douce
(lisible sur fond noir comme sur le papier clair). Légèrement agrandi au survol d'un élément cliquable,
écrasé au clic, halo blanc discret au survol.

Remplace le curseur du système dès que la souris est libre (menus, téléphone, documents).
Dessiné avec Pillow au lancement : aucun fichier externe.
"""
from PIL import Image, ImageDraw, ImageFilter
from ursina import Entity, Button, camera, mouse, time, color, Vec3

import ui_theme as theme

S = 128                 # taille des textures (px)
SIZE = 0.032            # taille à l'écran (unités d'interface)
TIP = (20, 14)          # position de la pointe dans la texture (px)

# flèche classique (pointe en haut à gauche, queue en bas à droite)
_ARROW = [(20, 14), (20, 98), (41, 78), (55, 110), (71, 103), (58, 72), (87, 72)]


def _rounded_mask(k=8, radius=4.5):
    """Silhouette aux coins arrondis : polygone flouté puis seuillé (arrondit les angles saillants et rentrants)."""
    big = Image.new("L", (S * k, S * k), 0)
    ImageDraw.Draw(big).polygon([(x * k, y * k) for x, y in _ARROW], fill=255)
    big = big.filter(ImageFilter.GaussianBlur(radius * k)).point(lambda v: 255 if v >= 128 else 0)
    return big.resize((S, S), Image.LANCZOS)


def _pointer_img():
    mask = _rounded_mask()
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # ombre portée douce
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.putalpha(mask.point(lambda v: int(v * 0.45)))
    shadow = shadow.transform((S, S), Image.AFFINE, (1, 0, -2, 0, 1, -3)).filter(ImageFilter.GaussianBlur(3))
    out = Image.alpha_composite(out, shadow)
    # liseré gris très fin
    edge = Image.new("RGBA", (S, S), (70, 70, 74, 0))
    edge.putalpha(mask.filter(ImageFilter.MaxFilter(3)))
    out = Image.alpha_composite(out, edge)
    # remplissage blanc pur
    fill = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    fill.putalpha(mask)
    return Image.alpha_composite(out, fill)


def _glow_img():
    glow = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    glow.putalpha(_rounded_mask().filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(8)))
    return glow


class HorrorCursor(Entity):
    """Entité mise à jour à chaque image (type non ignoré par l'optimisation de main.py)."""

    def __init__(self):
        super().__init__(parent=camera.ui, z=-99)
        self.glow = Entity(parent=self, model="quad", texture=theme._tex(_glow_img()), scale=SIZE, z=0.01,
                           color=color.rgba(1, 1, 1, 0))
        self.pointer = Entity(parent=self, model="quad", texture=theme._tex(_pointer_img()), scale=SIZE, z=0)
        self.hover = 0.0
        self.press = 0.0
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
        if not free:
            return
        if mouse.visible:                      # le curseur système reste caché derrière le nôtre
            mouse.visible = False
        dt = min(time.dt, 0.05)
        target = 1.0 if self._clickable() else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14)
        if mouse.left:
            self.press = 1.0
        self.press = max(0.0, self.press - dt * 6)
        sc = SIZE * (1.0 + 0.1 * self.hover) * (1.0 - 0.12 * self.press)
        p = Vec3(mouse.x, mouse.y, 0)
        self.pointer.scale = sc
        self.pointer.position = p + self._offset(sc)
        self.glow.scale = sc
        self.glow.position = self.pointer.position
        self.glow.color = color.rgba(1, 1, 1, 0.35 * self.hover)
