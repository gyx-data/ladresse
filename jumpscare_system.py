"""Jumpscares : visuel + audio synchronisés.

Séquence : flash blanc (0,05 s) → image du jumpscare (0,5 s) → écran noir + bruit sourd.
« Réduire les jumpscares » atténue les flashes et le volume des stingers.
"""
import math
import random

from ursina import Entity, camera, color, invoke, destroy

from config import settings
from sound_engine import engine as sound
from texture_generator import textures
from ui_widgets import rgb


class JumpscareSystem:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-9, enabled=False)
        self.bg = Entity(parent=self.root, model="quad", scale=(2.2, 1.2), color=color.black, z=1)
        self.items = []
        self.active = False
        self.t = 0.0
        self.shake_amp = 0.0
        self.kind = None
        self.on_done = None
        self.duration = 0.5

    def _clear(self):
        for e in self.items:
            destroy(e)
        self.items = []

    def _add(self, tex, pos, scale, col=color.white, rot=0.0):
        e = Entity(parent=self.root, model="quad", texture=textures.get(tex) if tex else None, position=pos, scale=scale,
                   color=col, rotation_z=rot, z=0)
        try:
            from panda3d.core import TransparencyAttrib
            e.setTransparency(TransparencyAttrib.M_alpha)
        except Exception:
            pass
        self.items.append(e)
        return e

    def trigger(self, kind="generic", on_done=None):
        """Lance le jumpscare. kind : silencieux | rampant | multiple | imposteur | porte | generic."""
        if self.active:
            return
        self.active = True
        self.kind = kind
        self.on_done = on_done
        self.t = 0.0
        reduce = settings["reduire_jumpscares"]
        g = self.game
        g.player.frozen = True
        g.effects.flash(1.0, 0.05 if not reduce else 0.2)
        g.effects.chroma_burst(1.5)
        g.effects.distort_burst(0.6)
        g.player.shake(1.0, 0.6)
        vol = 0.5 if reduce else 1.0
        sound.play("stinger_jumpscare", vol, channel="sfx")
        sound.play("cri", 0.7 * vol, channel="sfx")
        self._clear()
        self.root.enabled = True
        self.bg.color = color.rgba32(0, 0, 0, 0)
        self.duration = 0.5 if not reduce else 0.35
        if kind == "silencieux":
            self._add("silhouette", (0, -0.05), (1.5, 1.5), rgb(20, 20, 24))
            self._add("silhouette", (0, 0.25), (0.9, 0.9), rgb(8, 8, 10))
        elif kind == "rampant":
            self._add("silhouette", (0, 0.35), (1.9, 1.0), rgb(10, 8, 8), rot=180)
            self._add("mains", (0, 0.1), (1.3, 1.3), rgb(255, 255, 255))
        elif kind == "multiple":
            self._add("silhouette", (-0.5, -0.05), (0.9, 1.2), rgb(12, 12, 14))
            self._add("silhouette", (0.5, -0.05), (0.9, 1.2), rgb(12, 12, 14))
            self._add("silhouette", (0, 0), (1.3, 1.6), rgb(4, 4, 6))
        elif kind == "imposteur":
            self._add("visage_flou", (0, 0.05), (1.3, 1.3), color.white)
        elif kind == "porte":
            self._add(None, (0, 0), (0.9, 1.15), rgb(70, 40, 24))
            self._add(None, (0, 0), (0.75, 1.05), rgb(2, 2, 2))
            self._add("silhouette", (0, -0.05), (0.8, 1.0), rgb(12, 12, 14))
        else:
            self._add("silhouette", (0, 0), (1.4, 1.4), rgb(10, 10, 12))
        invoke(self._finish, delay=self.duration + 0.05)

    def update(self, dt):
        if not self.active:
            return
        self.t += dt
        for e in self.items:
            e.x += random.uniform(-0.006, 0.006)
            e.y += random.uniform(-0.006, 0.006)
            e.scale *= 1.0 + dt * 0.5

    def _finish(self):
        self._clear()
        self.root.enabled = False
        self.active = False
        sound.play("sourd_mort", 0.9, channel="sfx")
        cb, self.on_done = self.on_done, None
        if cb:
            cb()

    # --- L'Imposteur : le sac s'ouvre sur un noir infini ---------------------
    def bag_sequence(self, ai, on_done=None):
        g = self.game
        p = g.player
        g.player.frozen = True
        g.player.phone_open = False
        if g.phone.is_open:
            g.phone.close()
        self.bag_t = 0.0
        self._bag_done = on_done
        self._bag_ai = ai
        # le joueur regarde le sac
        dx, dz = ai.pos[0] - p.pos[0], ai.pos[2] - p.pos[2]
        self._bag_yaw = math.degrees(math.atan2(dx, dz))
        self._bag_start_yaw = p.yaw
        self._bag_active = True
        if hasattr(ai.puppets[0], "bag_front"):
            ai.puppets[0].bag_front.enabled = True
        self.bag_circle = Entity(parent=camera.ui, model="circle", color=color.black, scale=0.0, z=-8)

    def update_bag(self, dt):
        if not getattr(self, "_bag_active", False):
            return
        self.bag_t += dt
        p = self.game.player
        t = min(1.0, self.bag_t / 0.8)
        dy = (self._bag_yaw - self._bag_start_yaw + 180) % 360 - 180
        p.yaw = self._bag_start_yaw + dy * t
        p.pitch += (22.0 - p.pitch) * min(1.0, dt * 4.0)
        ai = self._bag_ai
        if self.bag_t > 1.6:
            self.bag_circle.scale = (self.bag_t - 1.6) * 3.2
            self.bag_circle.scale = (self.bag_circle.scale_x, self.bag_circle.scale_x)
        if self.bag_t > 3.0:
            self._bag_active = False
            destroy(self.bag_circle)
            if hasattr(ai.puppets[0], "bag_front"):
                ai.puppets[0].bag_front.enabled = False
            cb, self._bag_done = self._bag_done, None
            self.trigger("imposteur", on_done=cb)
