"""Effets visuels : post-traitement (vignette, grain, aberration, distorsion, teinte, flash),
hallucinations de stress, effet « photo » (image figée + éléments cachés révélés).
"""
import math
import random

from ursina import Entity, Vec3, Vec2, camera, color, invoke, destroy

from shaders import shader_state
from sound_engine import engine as sound
from texture_generator import textures
from config import settings


class EffectsManager:
    def __init__(self, game):
        self.game = game
        self.flash_v = 0.0
        self.flash_decay = 4.0
        self.fade_v = 0.0
        self.fade_target = 0.0
        self.fade_speed = 0.0
        self.distort_burst_v = 0.0
        self.chroma_burst_v = 0.0
        self.tint = Vec3(1, 1, 1)
        self.tint_target = Vec3(1, 1, 1)
        self.custom_tint = None
        self.pulse = 0.0
        self.base_vignette = 0.28
        self.extra_vignette = 0.0
        self.grain_mult = 1.0
        self.time = 0.0
        self.disabled = False
        self.chase_pulse = False
        self.hall = HallucinationManager(game)
        self.menu_mode = False

    def flash(self, intensity=1.0, duration=0.25):
        if settings["reduire_jumpscares"]:
            intensity *= 0.35
        self.flash_v = max(self.flash_v, intensity)
        self.flash_decay = intensity / max(0.02, duration)

    def fade_to(self, value, duration=1.0):
        self.fade_target = value
        self.fade_speed = abs(value - self.fade_v) / max(0.01, duration)

    def set_fade(self, value):
        self.fade_v = self.fade_target = value

    def distort_burst(self, amount, duration=0.4):
        self.distort_burst_v = max(self.distort_burst_v, amount)

    def chroma_burst(self, amount):
        self.chroma_burst_v = max(self.chroma_burst_v, amount)

    def set_tint(self, rgb_tuple, instant=False):
        """Teinte personnalisée (None pour revenir à la normale)."""
        self.custom_tint = None if rgb_tuple is None else Vec3(*rgb_tuple)
        if instant:
            self.tint = Vec3(*(rgb_tuple or (1, 1, 1)))

    def update(self, dt):
        self.time += dt
        g = self.game
        p = g.player
        s = shader_state
        s.time = self.time
        # flash et fondu
        if self.flash_v > 0:
            self.flash_v = max(0.0, self.flash_v - self.flash_decay * dt)
        if self.fade_v != self.fade_target:
            d = self.fade_speed * dt
            if abs(self.fade_target - self.fade_v) <= d:
                self.fade_v = self.fade_target
            else:
                self.fade_v += math.copysign(d, self.fade_target - self.fade_v)
        self.distort_burst_v = max(0.0, self.distort_burst_v - dt * 2.5)
        self.chroma_burst_v = max(0.0, self.chroma_burst_v - dt * 2.0)
        self.tint += (self.tint_target - self.tint) * min(1.0, dt * 2.0)
        # grandeurs dérivées
        stress = p.stress / 100.0 if not self.menu_mode else 0.0
        prox = getattr(p, "proximity", 0.0) if not self.menu_mode else 0.0
        ent_d = g.entity.dist_to_player if (g.entity and g.entity.visible and not self.menu_mode) else 99.0
        vignette = self.base_vignette + stress * 0.65 + self.extra_vignette
        pulse = 0.0
        if g.entity and g.entity.state == "chase" and g.entity.active and not self.menu_mode:
            bpm = max(110.0, 62 + p.stress * 0.85 + 18)
            pulse = 0.5 + 0.5 * math.sin(self.time * bpm / 60.0 * 2 * math.pi)
            vignette += 0.12
        chroma = 0.12 + stress * 0.5 + prox * 0.5 + self.chroma_burst_v
        distort = max(0.0, 1.0 - ent_d / 5.0) * (1.0 if ent_d < 5.0 else 0.0) + self.distort_burst_v
        zone = p.zone if not self.menu_mode else "dehors"
        if zone in ("sous_sol", "escalier_cave") and not self.menu_mode:
            self.tint_target = Vec3(0.78, 0.92, 1.12)
        else:
            self.tint_target = self.custom_tint if self.custom_tint is not None else Vec3(1, 1, 1)
        enabled = 1.0 if (settings["postprocess"] and not self.disabled) else 0.0
        reduce = 0.5 if settings["reduire_jumpscares"] else 1.0
        s.post.update(dict(
            vignette=min(1.0, vignette), vig_pulse=pulse, grain=0.32 * self.grain_mult, chroma=min(1.6, chroma),
            distort=min(1.0, distort) * reduce, tint=self.tint, flash=self.flash_v, fade=self.fade_v, enabled=enabled,
        ))
        s.cb_mode = settings["daltonien"]
        self.hall.update(dt)


class HallucinationManager:
    """Ombres aux coins de l'écran sous stress élevé."""

    def __init__(self, game):
        self.game = game
        self.timer = random.uniform(8, 14)
        self.ents = []

    def update(self, dt):
        p = self.game.player
        for e in list(self.ents):
            e["t"] += dt
            a = math.sin(min(1.0, e["t"] / e["dur"]) * math.pi) * e["max"]
            e["ent"].alpha = max(0.0, a)
            if e["t"] >= e["dur"]:
                destroy(e["ent"])
                self.ents.remove(e)
        if self.game.menu_active or p.dead:
            return
        if p.stress > 60:
            self.timer -= dt * (0.5 + p.stress / 100.0)
            if self.timer <= 0:
                self.timer = random.uniform(8, 16)
                self.spawn()

    def spawn(self):
        side = random.choice([-1, 1])
        x = side * random.uniform(0.62, 0.8)
        ent = Entity(parent=camera.ui, model="quad", texture=textures.get("silhouette"), position=(x, random.uniform(-0.1, 0.1), 5),
                     scale=(0.45, 0.8), color=color.rgba32(255, 255, 255, 0))
        ent.alpha = 0
        self.ents.append(dict(ent=ent, t=0.0, dur=random.uniform(0.9, 1.6), max=0.55))
        if random.random() < 0.4:
            sound.play("chuchotements", 0.25, pitch=1.3, channel="sfx")


class PhotoSystem:
    """Appareil photo : flash, image figée 0,5 s, éléments cachés révélés."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, enabled=False, z=-8)
        self.quad = Entity(parent=self.root, model="quad", scale=(1.78, 1.0), z=0)
        self.border = Entity(parent=self.root, model="quad", scale=(1.84, 1.06), color=color.white, z=0.1)
        self.caption = None
        self.busy = False
        self.taken = 0

    def take(self, flash=True):
        """Prend une photo avec ce que le joueur regarde."""
        if self.busy:
            return
        g = self.game
        p = g.player
        self.busy = True
        sound.play("obturateur", 1.0)
        if flash:
            g.effects.flash(1.0, 0.18)
        # éléments cachés dans le champ de vision
        revealed = self._find_reveals()
        for name, info in revealed:
            info["entity"].enabled = True
        invoke(self._capture, revealed, delay=0.06)

    def _find_reveals(self):
        g = self.game
        p = g.player
        out = []
        for name, info in g.house.reveals.items():
            lvl = info["level"]
            if lvl != p.level:
                continue
            to = (info["pos"] + Vec3(0, 0.8, 0)) - p.eye_pos
            d = to.length()
            if d > 7.5 or d < 0.2:
                continue
            if to.normalized().dot(p.forward) < 0.82:
                continue
            if g.house.wall_count(p.eye_pos, info["pos"] + Vec3(0, 0.8, 0)) > 0:
                continue
            if not g.reveal_allowed(name):
                continue
            out.append((name, info))
        # multijoueur : les autres joueurs apparaissent « faux » sur la photo
        return out

    def _capture(self, revealed):
        from ursina import application
        base = application.base
        try:
            tex = base.win.getScreenshot()
            self._set_panda_texture(tex)
        except Exception:
            pass
        g = self.game
        g.state.stats["photos"] += 1
        found = [n for n, _ in revealed]
        for name, info in revealed:
            g.on_photo_reveal(name)
        g.on_photo_taken(found)
        # affichage
        self.root.enabled = True
        self.root.alpha = 1
        if found:
            g.say("Qu'est-ce que... c'était pas là tout à l'heure.")
        invoke(self._end, revealed, delay=0.5)

    def _set_panda_texture(self, ptex):
        from ursina import Texture as UTex
        t = UTex(ptex) if not isinstance(ptex, str) else ptex
        self.quad.texture = t
        # le screenshot Panda est inversé verticalement
        self.quad.texture_scale = Vec2(1, -1)
        self.quad.texture_offset = Vec2(0, 1)

    def _end(self, revealed):
        for name, info in revealed:
            info["entity"].enabled = False
        self.root.enabled = False
        self.busy = False


class SkyDome:
    """Dôme de ciel nocturne (nuages sombres, étoiles) qui suit la caméra."""

    def __init__(self):
        self.e = Entity(model="sky_dome", texture=textures.get("ciel"), scale=130, double_sided=True, eternal=True)
        try:
            self.e.setBin("background", 0)
            self.e.set_depth_write(False)
            self.e.set_light_off()
        except Exception:
            pass
        self.e.color = color.rgb32(150, 150, 170)

    def update(self):
        self.e.position = camera.world_position

    def set_enabled(self, v):
        self.e.enabled = v
