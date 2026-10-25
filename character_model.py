"""Modèle de personnage articulé et animé (vue à la troisième personne, coéquipiers en coopératif).

Le personnage est construit entièrement en géométrie procédurale (MeshBuilder) : chaussures,
jean, sweat à capuche avec cordons et poche ventrale, mains, tête avec cheveux, yeux, nez et
oreilles. Chaque membre a sa propre articulation (hanches, genoux, épaules, coudes, cou) pour
permettre un cycle de marche/course, l'accroupissement, la respiration au repos, la visée de la
lampe torche (bras droit et tête suivent le regard) et une pose de mort.

Repère local : y = haut, +z = avant du personnage, pieds en y = 0.
"""
import math

from ursina import Entity, Vec3, color, destroy

from room_builder import MeshBuilder

SKIN_TONES = [(0.86, 0.68, 0.56), (0.72, 0.52, 0.40), (0.55, 0.38, 0.28), (0.93, 0.78, 0.66)]
HAIR_COLS = [(0.10, 0.08, 0.07), (0.28, 0.18, 0.10), (0.06, 0.06, 0.06), (0.45, 0.32, 0.18)]


def _mesh(parent, build_fn, emit=0.05):
    b = MeshBuilder("perso")
    build_fn(b)
    ents = b.build(parent=parent, emit=emit)
    return ents


class _Limb:
    """Articulation : un pivot (Entity vide) avec des enfants géométriques."""

    def __init__(self, parent, pos):
        self.pivot = Entity(parent=parent, position=pos)

    @property
    def rx(self):
        return self.pivot.rotation_x

    @rx.setter
    def rx(self, v):
        self.pivot.rotation_x = v


class CharacterModel:
    """Humanoïde stylisé ~1,78 m.

    jacket : couleur du sweat (r, g, b) 0..1
    flashlight : ajoute une lampe torche dans la main droite (avec `beam_anchor` à son extrémité)
    """

    HEIGHT = 1.78

    def __init__(self, parent=None, jacket=(0.22, 0.24, 0.3), pants=(0.16, 0.2, 0.3), skin=None,
                 hair=None, flashlight=True, seed=0, emit=0.05, hood_up=False):
        self.root = Entity(parent=parent, name="personnage")
        self.jacket = tuple(jacket)
        self.pants = tuple(pants)
        self.skin = skin or SKIN_TONES[seed % len(SKIN_TONES)]
        self.hair = hair or HAIR_COLS[(seed // 2) % len(HAIR_COLS)]
        self.emit = emit
        self.phase = 0.0
        self.time = 0.0
        self.crouch = 0.0
        self.aim_pitch = 0.0
        self.dead = False
        self.dead_t = 0.0
        self.hood_up = hood_up
        self._build(flashlight)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self, flashlight):
        jc, pc, sk, hc = self.jacket, self.pants, self.skin, self.hair
        dark_j = tuple(c * 0.7 for c in jc)
        shoe = (0.12, 0.12, 0.13)
        sole = (0.85, 0.85, 0.82)
        em = self.emit
        # bassin : pivot global du haut du corps (descend en accroupi)
        self.hips = Entity(parent=self.root, position=(0, 0.92, 0))
        _mesh(self.hips, lambda b: (
            b.obox("etoffe", 0, -0.1, 0, 0.34, 0.2, 0.2, 0, pc),
            b.obox("etoffe", 0, 0.04, 0, 0.35, 0.05, 0.21, 0, (0.1, 0.08, 0.07)),   # ceinture
        ), em)
        # jambes : hanche -> genou -> pied
        self.legs = []
        for side in (-1, 1):
            hip = _Limb(self.hips, (side * 0.095, -0.08, 0))
            _mesh(hip.pivot, lambda b: b.obox("etoffe", 0, -0.44, 0, 0.15, 0.44, 0.16, 0, pc), em)
            knee = _Limb(hip.pivot, (0, -0.44, 0))
            def shin(b, pc=pc):
                b.obox("etoffe", 0, -0.4, 0, 0.13, 0.4, 0.14, 0, pc)
                b.obox("etoffe", 0, -0.42, 0.04, 0.13, 0.04, 0.12, 0, tuple(c * 0.8 for c in pc))   # revers
                b.obox("metal", 0, -0.48, 0.04, 0.13, 0.08, 0.26, 0, shoe)
                b.obox("peau", 0, -0.5, 0.04, 0.14, 0.025, 0.27, 0, sole)
            _mesh(knee.pivot, shin, em)
            self.legs.append((hip, knee))
        # torse (sweat à capuche)
        self.torso = Entity(parent=self.hips, position=(0, 0.04, 0))
        def torso(b):
            b.obox("etoffe", 0, 0.0, 0, 0.4, 0.56, 0.23, 0, jc)
            b.obox("etoffe", 0, 0.0, 0.0, 0.42, 0.08, 0.25, 0, dark_j)                 # bord-côte
            b.obox("etoffe", 0, 0.12, 0.112, 0.24, 0.13, 0.02, 0, dark_j)              # poche kangourou
            b.obox("etoffe", 0, 0.5, 0, 0.46, 0.08, 0.25, 0, jc)                       # épaules
            # capuche roulée derrière le cou
            b.obox("etoffe", 0, 0.5, -0.12, 0.3, 0.12, 0.1, 0, dark_j)
            for x in (-0.05, 0.05):                                                   # cordons
                b.obox("peau", x, 0.33, 0.118, 0.012, 0.16, 0.012, 0, (0.9, 0.9, 0.88))
            # petit logo réfléchissant QuickEats sur la poitrine
            b.obox("neon", 0.1, 0.4, 0.117, 0.06, 0.04, 0.005, 0, (1.0, 0.55, 0.15))
        _mesh(self.torso, torso, em)
        # cou + tête
        self.neck = Entity(parent=self.torso, position=(0, 0.6, 0))
        def head(b):
            b.cyl("peau", 0, -0.06, 0, 0.055, 0.1, 6, sk)
            b.sphere("peau", 0, 0.12, 0.0, 0.11, sk, lat=6, lon=10, sy=1.18, sx=0.95)
            b.sphere("etoffe", 0, 0.17, -0.012, 0.113, hc, lat=5, lon=10, sy=1.0, sx=1.0)         # cheveux
            b.obox("peau", 0, 0.08, 0.1, 0.03, 0.05, 0.04, 0, tuple(c * 0.92 for c in sk))   # nez
            for x in (-0.106, 0.106):
                b.obox("peau", x, 0.1, 0.0, 0.02, 0.05, 0.035, 0, tuple(c * 0.9 for c in sk))  # oreilles
            for x in (-0.04, 0.04):
                b.obox("peau", x, 0.135, 0.098, 0.028, 0.014, 0.01, 0, (0.95, 0.95, 0.95))
                b.obox("metal", x, 0.135, 0.104, 0.012, 0.012, 0.006, 0, (0.08, 0.06, 0.05))
                b.obox("etoffe", x, 0.16, 0.1, 0.04, 0.01, 0.012, 0, hc)                       # sourcils
            b.obox("peau", 0, 0.03, 0.095, 0.05, 0.008, 0.01, 0, (0.55, 0.32, 0.3))         # bouche
            if self.hood_up:
                b.sphere("etoffe", 0, 0.14, -0.02, 0.135, dark_j, lat=5, lon=10, sy=1.15)
        self.head = Entity(parent=self.neck, position=(0, 0.0, 0))
        _mesh(self.head, head, em)
        # bras : épaule -> coude -> main
        self.arms = []
        for side in (-1, 1):
            sh = _Limb(self.torso, (side * 0.25, 0.48, 0))
            _mesh(sh.pivot, lambda b: b.obox("etoffe", 0, -0.3, 0, 0.11, 0.3, 0.12, 0, jc), em)
            el = _Limb(sh.pivot, (0, -0.3, 0))
            def fore(b):
                b.obox("etoffe", 0, -0.26, 0, 0.1, 0.26, 0.11, 0, jc)
                b.obox("etoffe", 0, -0.27, 0, 0.105, 0.04, 0.115, 0, dark_j)
                b.obox("peau", 0, -0.36, 0.0, 0.08, 0.1, 0.09, 0, sk)
            _mesh(el.pivot, fore, em)
            self.arms.append((sh, el))
        # lampe torche dans la main droite
        self.beam_anchor = None
        self.torch = None
        if flashlight:
            _, el = self.arms[1]
            self.torch = Entity(parent=el.pivot, position=(0, -0.37, 0.05))
            def torch(b):
                b.obox("metal", 0, -0.02, 0.05, 0.045, 0.045, 0.2, 0, (0.12, 0.12, 0.14))
                b.obox("metal", 0, -0.025, 0.16, 0.06, 0.055, 0.04, 0, (0.2, 0.2, 0.22))
            _mesh(self.torch, torch, em)
            self.lens = Entity(parent=self.torch, model="quad", position=(0, 0.002, 0.182), scale=0.045,
                               color=color.rgb32(255, 236, 170), double_sided=True)
            # orientée vers l'avant (local +z) quel que soit l'angle du bras (corrigé dans update)
            self.beam_anchor = Entity(parent=self.torch, position=(0, 0.002, 0.19))

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def animate(self, dt, speed=0.0, crouch=0.0, aim_pitch=0.0, sprint=False, torch_on=True, airborne=False):
        """Cycle de marche (vitesse en m/s), accroupi 0..1, regard vertical (degrés, + = vers le bas)."""
        self.time += dt
        if self.dead:
            self._dead_pose(dt)
            return
        self.crouch += (crouch - self.crouch) * min(1.0, dt * 10.0)
        c = self.crouch
        # phase de pas proportionnelle à la distance parcourue
        stride = 1.25 if sprint else 1.6
        self.phase += speed * dt / stride * math.pi * 2.0
        moving = min(1.0, speed / 1.2)
        swing = (52 if sprint else 34) * moving
        s = math.sin(self.phase)
        # hanches : accroupi = descendre et plier les genoux
        bob = abs(math.cos(self.phase)) * 0.035 * moving
        breathe = math.sin(self.time * 1.8) * 0.006 * (1 - moving)
        self.hips.y = 0.92 - 0.36 * c + bob
        self.torso.rotation_x = 8 * moving * (1.6 if sprint else 1.0) + 22 * c
        self.torso.y = 0.04 + breathe
        for i, (hip, knee) in enumerate(self.legs):
            ph = s if i == 0 else -s
            hip.rx = -ph * swing - 62 * c
            k = max(0.0, -math.cos(self.phase + (0 if i == 0 else math.pi))) * swing * 1.25
            knee.rx = k + 110 * c
            if airborne:
                hip.rx = -25 if i == 0 else 10
                knee.rx = 40
        # bras : gauche balance, droit vise avec la lampe
        sl, el = self.arms[0]
        sl.rx = s * swing * 0.9 - 6
        el.rx = -12 - 18 * moving
        sr, er = self.arms[1]
        if self.torch is not None and torch_on:
            # visée : le bras droit pointe vers l'avant et suit le regard
            target = -80 + aim_pitch * 0.85 - self.torso.rotation_x
            sr.rx += (target - sr.rx) * min(1.0, dt * 12.0)
            er.rx += (-12 - er.rx) * min(1.0, dt * 12.0)
            # corrige l'orientation de la lampe pour qu'elle reste parallèle au regard
            self.torch.rotation_x = aim_pitch - (sr.rx + er.rx + self.torso.rotation_x)
        else:
            sr.rx = -s * swing * 0.9 - 6
            er.rx = -12 - 18 * moving
            if self.torch is not None:
                self.torch.rotation_x = 0
        # tête : suit le regard (limité), compense l'inclinaison du torse
        self.neck.rotation_x = max(-50, min(50, aim_pitch * 0.6)) - self.torso.rotation_x * 0.6
        if self.torch is not None:
            self.lens.enabled = torch_on

    def _dead_pose(self, dt):
        self.dead_t = min(1.0, self.dead_t + dt * 2.5)
        t = self.dead_t
        self.root.rotation_x = -88 * t
        self.root.rotation_z = 8 * t
        self.hips.y = 0.92 - 0.75 * t
        for i, (hip, knee) in enumerate(self.legs):
            hip.rx = (-10 if i else 15) * t
            knee.rx = 25 * t
        for i, (sh, el) in enumerate(self.arms):
            sh.rx = (-150 if i else -30) * t
            el.rx = -20 * t

    def die(self):
        self.dead = True
        self.dead_t = 0.0

    def revive(self):
        self.dead = False
        self.dead_t = 0.0
        self.root.rotation_x = 0
        self.root.rotation_z = 0

    # ------------------------------------------------------------------
    @property
    def enabled(self):
        return self.root.enabled

    @enabled.setter
    def enabled(self, v):
        self.root.enabled = v

    def beam_world(self, fallback_pos, fallback_dir):
        """Position monde de l'extrémité de la lampe (pour la lumière du shader)."""
        if self.beam_anchor is None or not self.root.enabled:
            return fallback_pos
        try:
            return self.beam_anchor.world_position
        except Exception:
            return fallback_pos

    def destroy(self):
        destroy(self.root)


class Nametag:
    """Pseudo flottant au-dessus d'un personnage (toujours face caméra)."""

    def __init__(self, parent, name, col=(1, 1, 1), y=2.05):
        from ursina import Text
        self.root = Entity(parent=parent, position=(0, y, 0), billboard=True)
        self.bg = Entity(parent=self.root, model="quad", color=color.rgba32(10, 10, 14, 150),
                         scale=(0.07 * max(3, len(name)) + 0.1, 0.16), z=0.01)
        self.dot = Entity(parent=self.root, model="quad", color=color.rgb(*col), scale=0.07,
                          x=-(0.07 * max(3, len(name)) + 0.1) / 2 + 0.07)
        self.text = Text(parent=self.root, text=name, origin=(0, 0), scale=4.0, color=color.white, z=-0.01, x=0.03)
        for e in (self.bg, self.dot):
            try:
                e.set_light_off()
            except Exception:
                pass

    def set_visible(self, v):
        self.root.enabled = v
