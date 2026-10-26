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


def _show(e, v):
    """Active/désactive une entité seulement si l'état change (stash/unstash coûtent cher à chaque image)."""
    if e.enabled != v:
        e.enabled = v


class DustField:
    """Poussière : visible uniquement dans le faisceau de la lampe torche (calcul vectorisé)."""

    def __init__(self, count=70):
        import numpy as np
        self.count = count
        self.parent = Entity(name="poussiere")
        rnd = random.Random(3)
        self.ents = []
        for i in range(count):
            e = _quad("poussiere", rnd.uniform(0.012, 0.03))
            e.parent = self.parent
            e.enabled = False
            self.ents.append(e)
        self.off = np.array([[rnd.uniform(-5, 5), rnd.uniform(-1.2, 1.5), rnd.uniform(-5, 5)] for _ in range(count)])
        self.vel = np.array([[rnd.uniform(-0.04, 0.04), rnd.uniform(-0.02, 0.03), rnd.uniform(-0.04, 0.04)] for _ in range(count)])
        self.ph = np.array([rnd.uniform(0, 6.28) for _ in range(count)])
        self.vis = [False] * count
        self.center = Vec3(0, 0, 0)

    def update(self, dt, player, extra_light=None):
        import numpy as np
        if not settings["particules"]:
            _show(self.parent, False)
            return
        _show(self.parent, True)
        c = player.eye_pos
        fwd = player.forward
        on = player.flashlight.on and player.flashlight.battery > 0
        t = player.time
        off = self.off
        off += self.vel * dt
        off += np.stack([np.sin(self.ph + t * 0.5), np.sin(self.ph * 1.7 + t * 0.4), np.cos(self.ph + t * 0.6)], axis=1) * 0.002
        for ax in (0, 2):
            off[:, ax] = np.where(off[:, ax] > 5, off[:, ax] - 10, np.where(off[:, ax] < -5, off[:, ax] + 10, off[:, ax]))
        off[:, 1] = np.where(off[:, 1] > 1.6, -1.2, np.where(off[:, 1] < -1.3, 1.5, off[:, 1]))
        if on:
            d = np.linalg.norm(off, axis=1)
            cosang = (off @ np.array([fwd[0], fwd[1], fwd[2]])) / np.maximum(d, 1e-6)
            a = np.where((d > 0.2) & (cosang > 0.8) & (d < 12),
                         np.minimum(1.0, (cosang - 0.8) / 0.12) * np.maximum(0.0, 1.0 - d / 12.0) * 0.8, 0.0)
        else:
            a = np.zeros(self.count)
        render = self.parent.getTop()
        cx, cy, cz = c[0], c[1], c[2]
        for i, e in enumerate(self.ents):
            v = a[i] > 0.01
            if v != self.vis[i]:
                self.vis[i] = v
                e.enabled = v
            if v:
                e.setPos(render, cx + off[i, 0], cy + off[i, 1], cz + off[i, 2])
                e.setAlphaScale(float(a[i]))


class RainField:
    """Pluie : gouttes (deux quads croisés, visibles sous tous les angles) réunies en UN maillage, dupliqué
    en deux couches empilées qui défilent vers le bas en boucle. 2 objets à dessiner au lieu de `count`,
    et plus aucune boucle Python par goutte à chaque image."""

    def __init__(self, center=(8, 4, -4), size=(24, 10, 12), count=140):
        from ursina import Mesh
        self.center = Vec3(*center)
        self.size = size
        self.parent = Entity(name="pluie")
        rnd = random.Random(8)
        verts, uvs, tris = [], [], []
        hw, hh = 0.01, 0.225
        for i in range(count):
            x, y, z = rnd.uniform(-size[0] / 2, size[0] / 2), rnd.uniform(0, size[1]), rnd.uniform(-size[2] / 2, size[2] / 2)
            for (ax, az) in ((hw, 0.0), (0.0, hw)):
                k = len(verts)
                verts += [Vec3(x - ax, y - hh, z - az), Vec3(x + ax, y - hh, z + az), Vec3(x + ax, y + hh, z + az), Vec3(x - ax, y + hh, z - az)]
                uvs += [(0, 0), (1, 0), (1, 1), (0, 1)]
                tris += [k, k + 1, k + 2, k, k + 2, k + 3]
        mesh = Mesh(vertices=verts, uvs=uvs, triangles=tris, static=True)
        self.layers = []
        for j in range(2):
            e = Entity(parent=self.parent, model=mesh, texture=textures.get("goutte"), color=color.rgba32(190, 200, 225, 120),
                       double_sided=True)
            try:
                from panda3d.core import TransparencyAttrib
                e.setTransparency(TransparencyAttrib.M_alpha)
                e.set_depth_write(False)
                e.set_light_off()
            except Exception:
                pass
            self.layers.append(e)
        self.speed = 12.0
        self.offset = 0.0
        self.enabled = True

    def update(self, dt, cam_pos=None):
        if not settings["particules"]:
            _show(self.parent, False)
            return
        _show(self.parent, self.enabled)
        if not self.enabled:
            return
        h = self.size[1]
        self.offset = (self.offset + self.speed * dt) % h
        base = self.center + Vec3(0, 4 - h / 2, 0)
        self.layers[0].position = base + Vec3(0, -self.offset, 0)
        self.layers[1].position = base + Vec3(0, h - self.offset, 0)


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
            _show(self.parent, False)
            return
        _show(self.parent, True)
        for s in self.spots:
            d = (s["c"] - player.pos).length()
            vis = d < 8 and abs(s["c"][1] - player.pos[1]) < 3.5
            _show(s["e"], vis)
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
        _show(self.parent, False)

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
        _show(self.mist.parent, zone in ("sous_sol", "escalier_cave") and bool(settings["particules"]))
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
