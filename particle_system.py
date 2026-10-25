"""Particules : poussière dans le faisceau de la lampe, insectes près des fenêtres,
brume au sous-sol, pluie (vue par les fenêtres non condamnées), cendres de la cheminée.
"""
import math
import random

from ursina import Entity, Vec3, color

import config
from texture_generator import textures
from config import settings


def _quad(texture_name, scale, col=color.white):
    e = Entity(model="quad", texture=textures.get(texture_name), scale=scale, billboard=True, color=col)
    try:
        from panda3d.core import TransparencyAttrib
        e.setTransparency(TransparencyAttrib.M_alpha)
        e.set_depth_write(False)
    except Exception:
        pass
    return e


class DustField:
    """Poussière : visible uniquement dans le faisceau de la lampe torche."""

    def __init__(self, count=70):
        self.count = count
        self.parts = []
        self.parent = Entity(name="poussiere")
        rnd = random.Random(3)
        for i in range(count):
            e = _quad("poussiere", rnd.uniform(0.012, 0.03))
            e.parent = self.parent
            self.parts.append(dict(e=e, off=Vec3(rnd.uniform(-5, 5), rnd.uniform(-1.2, 1.5), rnd.uniform(-5, 5)),
                                   vel=Vec3(rnd.uniform(-0.04, 0.04), rnd.uniform(-0.02, 0.03), rnd.uniform(-0.04, 0.04)),
                                   ph=rnd.uniform(0, 6.28)))
        self.center = Vec3(0, 0, 0)

    def update(self, dt, player, extra_light=None):
        if not settings["particules"]:
            self.parent.enabled = False
            return
        self.parent.enabled = True
        c = player.eye_pos
        fwd = player.forward
        on = player.flashlight.on and player.flashlight.battery > 0
        for p in self.parts:
            p["off"] += p["vel"] * dt
            # bruit brownien léger
            p["off"] += Vec3(math.sin(p["ph"] + player.time * 0.5), math.sin(p["ph"] * 1.7 + player.time * 0.4), math.cos(p["ph"] + player.time * 0.6)) * 0.002
            off = p["off"]
            # enroulement autour du joueur (toujours dans une boîte de 10 m)
            for ax in (0, 2):
                if off[ax] > 5:
                    off[ax] -= 10
                elif off[ax] < -5:
                    off[ax] += 10
            if off[1] > 1.6:
                off[1] = -1.2
            elif off[1] < -1.3:
                off[1] = 1.5
            p["off"] = off
            pos = c + off
            to = pos - c
            d = to.length()
            a = 0.0
            if on and d > 0.2:
                cosang = to.normalized().dot(fwd)
                if cosang > 0.8 and d < 12:
                    a = min(1.0, (cosang - 0.8) / 0.12) * max(0.0, 1.0 - d / 12.0) * 0.8
            p["e"].world_position = pos
            p["e"].alpha = a
            p["e"].enabled = a > 0.01


class RainField:
    """Pluie : lignes verticales rapides, autour d'un centre fixe (extérieur)."""

    def __init__(self, center=(8, 4, -4), size=(24, 10, 12), count=140):
        self.center = Vec3(*center)
        self.size = size
        self.parts = []
        self.parent = Entity(name="pluie")
        rnd = random.Random(8)
        for i in range(count):
            e = Entity(parent=self.parent, model="quad", texture=textures.get("goutte"), scale=(0.02, 0.45),
                       color=color.rgba32(190, 200, 225, 120))
            e.billboard = False
            try:
                from panda3d.core import TransparencyAttrib
                e.setTransparency(TransparencyAttrib.M_alpha)
                e.set_depth_write(False)
                e.set_light_off()
            except Exception:
                pass
            self.parts.append([Vec3(rnd.uniform(-size[0] / 2, size[0] / 2), rnd.uniform(0, size[1]), rnd.uniform(-size[2] / 2, size[2] / 2)), e,
                               rnd.uniform(10, 14)])
        self.enabled = True

    def update(self, dt, cam_pos=None):
        if not settings["particules"]:
            self.parent.enabled = False
            return
        self.parent.enabled = self.enabled
        if not self.enabled:
            return
        for p in self.parts:
            p[0] = Vec3(p[0][0], p[0][1] - p[2] * dt, p[0][2])
            if p[0][1] < 0:
                p[0] = Vec3(p[0][0], self.size[1], p[0][2])
            p[1].position = self.center + p[0] - Vec3(0, self.size[1] / 2, 0) + Vec3(0, 4, 0)
            if cam_pos is not None:
                # orientation vers la caméra (axe vertical seulement)
                dx, dz = cam_pos[0] - p[1].x, cam_pos[2] - p[1].z
                p[1].rotation_y = math.degrees(math.atan2(dx, dz)) + 180


class InsectField:
    """Petits points noirs près des fenêtres (zone limitée)."""

    def __init__(self, positions):
        self.spots = []
        self.parent = Entity(name="insectes")
        rnd = random.Random(9)
        for (px, py, pz) in positions:
            for k in range(4):
                e = Entity(parent=self.parent, model="quad", color=color.rgba32(5, 5, 5, 230), scale=0.012, billboard=True)
                self.spots.append(dict(e=e, c=Vec3(px, py, pz), a=rnd.uniform(0, 6.28), r=rnd.uniform(0.08, 0.3), s=rnd.uniform(6, 14)))
        self.active_level = 0

    def update(self, dt, player):
        if not settings["particules"]:
            self.parent.enabled = False
            return
        self.parent.enabled = True
        for s in self.spots:
            d = (s["c"] - player.pos).length()
            vis = d < 8 and abs(s["c"][1] - player.pos[1]) < 3.5
            s["e"].enabled = vis
            if vis:
                s["a"] += dt * s["s"]
                s["e"].world_position = s["c"] + Vec3(math.cos(s["a"]) * s["r"], math.sin(s["a"] * 1.3) * s["r"] * 0.7, math.sin(s["a"] * 0.7) * s["r"])


class MistField:
    """Brume au sol du sous-sol : particules grises lentes."""

    def __init__(self, center, size=(7, 7), y=-2.8, count=26):
        self.parent = Entity(name="brume")
        self.parts = []
        rnd = random.Random(12)
        for i in range(count):
            e = _quad("lueur", rnd.uniform(1.2, 2.4), color.rgba32(120, 130, 150, 30))
            e.billboard = False
            e.rotation_x = 90
            e.parent = self.parent
            e.position = Vec3(center[0] + rnd.uniform(-size[0] / 2, size[0] / 2), y + rnd.uniform(0.05, 0.3), center[1] + rnd.uniform(-size[1] / 2, size[1] / 2))
            self.parts.append((e, rnd.uniform(0, 6.28), rnd.uniform(0.05, 0.12)))
        self.parent.enabled = False

    def update(self, dt, t):
        if not self.parent.enabled:
            return
        for e, ph, sp in self.parts:
            e.x += math.sin(t * sp + ph) * dt * 0.1
            e.z += math.cos(t * sp * 0.8 + ph) * dt * 0.1


class ParticleManager:
    """Regroupe tous les systèmes et les active selon la zone."""

    def __init__(self, game):
        self.game = game
        self.dust = DustField()
        self.rain = RainField()
        self.mist = MistField((7.0, 20.2))
        windows = []
        for (lvl, ax, fixed, c, state) in game.house.window_info:
            y = config.LEVEL_Y[lvl] + 1.4
            if ax == "x":
                windows.append((c, y, fixed + (0.3 if fixed < 6 else -0.3)))
            else:
                windows.append((fixed + (0.3 if fixed < 8 else -0.3), y, c))
        self.insects = InsectField(windows[:8])
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        p = self.game.player
        self.dust.update(dt, p)
        zone = p.zone
        self.mist.parent.enabled = zone in ("sous_sol", "escalier_cave") and settings["particules"]
        self.mist.update(dt, self.t)
        self.insects.update(dt, p)
        # pluie : visible uniquement par les fenêtres non condamnées (grenier) ou dehors
        self.rain.enabled = p.level >= 1 or zone == "dehors"
        self.rain.update(dt, p.eye_pos)

    def hide_all(self):
        self.dust.parent.enabled = False
        self.rain.parent.enabled = False
        self.insects.parent.enabled = False
        self.mist.parent.enabled = False
