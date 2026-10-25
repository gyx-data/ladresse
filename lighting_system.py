"""Éclairage dynamique : lampe torche, néons, bougies, ambiance par zone.

Les lumières sont évaluées par le shader du monde (projecteur de lampe torche +
jusqu'à 8 lumières ponctuelles choisies parmi les plus proches de la caméra).
"""
import math
import random

from ursina import Vec3

import config
from shaders import shader_state

# Ambiance par zone : (densité de fog, couleur fog, couleur ambiante, multiplicateur lampe)
ZONES = {
    "rdc": (0.115, (0.0, 0.0, 0.0), (0.040, 0.045, 0.065), 1.0),
    "etage": (0.090, (0.01, 0.01, 0.015), (0.045, 0.048, 0.065), 1.0),
    "grenier": (0.140, (0.015, 0.015, 0.02), (0.030, 0.034, 0.05), 0.85),
    "sous_sol": (0.210, (0.0, 0.01, 0.03), (0.020, 0.030, 0.055), 0.95),
    "escalier_cave": (0.19, (0.0, 0.01, 0.03), (0.02, 0.028, 0.05), 0.95),
    "dehors": (0.040, (0.03, 0.035, 0.06), (0.17, 0.19, 0.30), 1.0),
    "bureau": (0.030, (0.035, 0.04, 0.055), (0.19, 0.20, 0.24), 1.0),
    "voiture": (0.040, (0.0, 0.0, 0.012), (0.06, 0.06, 0.09), 1.0),
    "cine_phone": (0.12, (0.0, 0.0, 0.0), (0.05, 0.05, 0.07), 1.0),
}


# Lumière lunaire (extérieur uniquement)
SUN = {"dehors": (0.62, 0.70, 1.0), "voiture": (0.02, 0.02, 0.035), "bureau": (0.0, 0.0, 0.0)}


class LightSource:
    """Lumière ponctuelle de la scène."""

    def __init__(self, pos, color=(1, 1, 1), intensity=1.0, range=6.0, kind="static",
                 enabled=True, name=""):
        self.pos = Vec3(*pos)
        self.color = color
        self.base_intensity = intensity
        self.range = range
        self.kind = kind            # static | neon | candle | flicker | tv | lamp
        self.enabled = enabled
        self.name = name
        self._t = random.random() * 100.0
        self._neon_on = True
        self._neon_timer = random.uniform(0.2, 1.5)
        self.dead = False           # néon définitivement éteint
        self.on_buzz = None         # callback appelé à chaque allumage du néon
        self.boost = 1.0

    def intensity(self):
        if not self.enabled or self.dead:
            return 0.0
        if self.kind == "neon":
            return self.base_intensity * (1.0 if self._neon_on else 0.0) * self.boost
        if self.kind == "candle":
            return self.base_intensity * (0.8 + 0.2 * math.sin(self._t * 9.0) * math.sin(self._t * 5.3 + 1.0)
                                          + 0.08 * math.sin(self._t * 23.0)) * self.boost
        if self.kind == "tv":
            return self.base_intensity * (0.7 + 0.3 * random.random()) * self.boost
        if self.kind == "flicker":
            return self.base_intensity * (0.4 + 0.6 * (0.5 + 0.5 * math.sin(self._t * 31.0) * math.sin(self._t * 7.0))) * self.boost
        return self.base_intensity * self.boost

    def update(self, dt):
        self._t += dt
        if self.kind == "neon" and self.enabled and not self.dead:
            self._neon_timer -= dt
            if self._neon_timer <= 0:
                self._neon_on = not self._neon_on
                # motif irrégulier : intervalles de 0.1 s à 2 s
                if self._neon_on:
                    self._neon_timer = random.choice([random.uniform(0.1, 0.4), random.uniform(0.5, 2.0)])
                    if self.on_buzz:
                        self.on_buzz(self)
                else:
                    self._neon_timer = random.choice([random.uniform(0.05, 0.25), random.uniform(0.2, 0.9)])

    @property
    def is_lit(self):
        return self.intensity() > 0.02


class LightingManager:
    """Sélectionne les 8 lumières ponctuelles les plus pertinentes et gère l'ambiance."""

    def __init__(self):
        self.lights = []
        self.zone = "rdc"
        self._fog_density = shader_state.fog_density
        self._fog_color = Vec3(0, 0, 0)
        self._ambient = Vec3(*ZONES["rdc"][2])
        self._sun = Vec3(0, 0, 0)
        self.zone_mult = 1.0
        self.fog_scale = 1.0
        self.ambient_boost = 0.0      # augmenté pour les caméras de cinématique / menu
        self.blackout = False
        self.max_point_lights = 6

    def add(self, light):
        self.lights.append(light)
        return light

    def clear(self):
        self.lights = []

    def set_zone(self, zone, instant=False):
        if zone not in ZONES:
            return
        self.zone = zone
        if instant:
            d, fc, am, mult = ZONES[zone]
            self._fog_density = d
            self._fog_color = Vec3(*fc)
            self._ambient = Vec3(*am)
            self._sun = Vec3(*SUN.get(zone, (0, 0, 0)))
            self.zone_mult = mult

    def update(self, dt, cam_pos):
        d, fc, am, mult = ZONES[self.zone]
        fog_user = config.FOG_DENSITY.get(config.settings["fog"], 0.11) / 0.11
        k = min(1.0, dt * 1.5)
        self._fog_density += (d * fog_user * self.fog_scale - self._fog_density) * k
        self._fog_color += (Vec3(*fc) - self._fog_color) * k
        self._ambient += (Vec3(*am) - self._ambient) * k
        self.zone_mult += (mult - self.zone_mult) * k
        shader_state.fog_density = self._fog_density
        shader_state.fog_color = self._fog_color
        self._sun += (Vec3(*SUN.get(self.zone, (0, 0, 0))) - self._sun) * k
        shader_state.sun_col = self._sun
        shader_state.ambient = self._ambient + Vec3(1, 1, 1) * self.ambient_boost
        # Lumières ponctuelles
        scored = []
        for l in self.lights:
            l.update(dt)
            inten = l.intensity()
            if inten <= 0.01:
                continue
            dist = (l.pos - cam_pos).length()
            if dist > l.range + 12:
                continue
            scored.append((dist - l.range * 0.5, l, inten))
        scored.sort(key=lambda s: s[0])
        chosen = []
        for _, l, inten in scored[:self.max_point_lights]:
            chosen.append((l.pos, l.color, inten, l.range))
        shader_state.set_point_lights(chosen)


class Flashlight:
    """Lampe torche : projecteur lié à la caméra, faisceau réglable, batterie."""

    def __init__(self):
        self.on = False
        self.battery = 100.0
        self.zoom = 0.5            # 0 = large, 1 = concentré
        self.mult = 1.0            # multiplicateur de zone
        self.dead_timer = 0.0
        self._flicker_t = 0.0
        self.shake = 0.0
        self.blackout = False      # coupée par un événement
        self.last_intensity = 0.0
        self.on_toggle = None

    def toggle(self):
        if self.battery <= 0:
            self.on = False
            return
        self.on = not self.on
        if self.on_toggle:
            self.on_toggle(self.on)

    def force_off(self):
        self.on = False

    def add_battery(self, amount):
        self.battery = min(100.0, self.battery + amount)

    def adjust_zoom(self, delta):
        self.zoom = max(0.0, min(1.0, self.zoom + delta))

    def update(self, dt, cam_pos, cam_forward):
        if self.on:
            self.battery = max(0.0, self.battery - config.FLASHLIGHT_DRAIN * dt)
            if self.battery <= 0:
                self.on = False
                self.dead_timer = 4.0
                if self.on_toggle:
                    self.on_toggle(False)
        if self.dead_timer > 0:
            self.dead_timer -= dt
        low = self.battery < 20.0
        crit = self.battery < 8.0
        inten = 0.0
        if self.on and not self.blackout:
            inten = 1.0
            self._flicker_t += dt
            if crit:
                # clignotement aléatoire
                inten *= 0.25 + 0.75 * (1.0 if math.sin(self._flicker_t * 37.0) * math.sin(self._flicker_t * 11.0) > -0.4 else 0.0)
            elif low:
                inten *= 0.8 + 0.2 * math.sin(self._flicker_t * 13.0)
        # Faisceau : large (cos externe bas) <-> concentré
        outer = 0.74 + 0.20 * self.zoom       # cos
        inner = outer + 0.09
        rng = 12.0 + 8.0 * self.zoom
        if low:
            shrink = 0.5 + 0.5 * (self.battery / 20.0)
            outer = min(0.97, 1 - (1 - outer) * shrink)
            inner = min(0.99, outer + 0.05)
            rng *= (0.55 + 0.45 * shrink)
        strength = (2.6 - 0.7 * self.zoom) * inten * self.mult
        # Couleur : blanc chaud -> jaune-orangé quand la batterie faiblit
        t = 1.0 - max(0.0, min(1.0, self.battery / 35.0))
        col = Vec3(1.0, 0.97 - 0.30 * t, 0.88 - 0.62 * t)
        shader_state.fl_pos = cam_pos + cam_forward * 0.1
        shader_state.fl_dir = cam_forward
        shader_state.fl_color = col
        shader_state.fl_params = [outer, inner, strength, rng]
        self.last_intensity = inten
        return inten
