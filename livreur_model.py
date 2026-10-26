"""Le Livreur « déformé » : modèle articulé lissé (lofts), animations et effets.

Silhouette trop grande (~2,05 m), voûtée, dans un uniforme QuickEats délavé et taché ; cou trop long,
peau grise, joues creuses, orbites noires avec deux points de lumière ; bras qui descendent aux genoux,
doigts trop longs ; sac isotherme sur le dos.

Animations : démarche boiteuse (jambe droite qui traîne), bras ballants en pendule, respiration lourde,
tics de la tête au repos, balayage du regard en recherche, course penchée bras tendus en poursuite,
mâchoire qui s'ouvre, regard qui suit le joueur (`look_target`).
Effets : yeux lumineux selon l'état (et clignotement), saccades « image sautée » en poursuite,
ombre douce au sol.

Repère local : y = haut, +z = avant, pieds en y = 0.
"""
import math
import random

from ursina import Entity, Vec3

from room_builder import MeshBuilder, _ring

JACKET = (0.56, 0.27, 0.1)           # orange QuickEats délavé, sali
JACKET_DARK = (0.34, 0.16, 0.06)
PANTS = (0.13, 0.135, 0.16)
SKIN = (0.34, 0.33, 0.31)            # gris cadavérique
SKIN_DARK = (0.22, 0.21, 0.2)
SHOE = (0.09, 0.08, 0.08)
BLACK = (0.02, 0.02, 0.025)
STAIN = (0.22, 0.12, 0.08)


def _mesh(parent, fn, emit=0.04):
    b = MeshBuilder("livreur")
    fn(b)
    return b.build(parent=parent, emit=emit)


def _tube(b, tex, col, profile, n=2.3, seg=14, caps=True):
    """Volume lisse le long de y : profile = [(y, demi-largeur x, demi-profondeur z, décalage z), ...] de bas en haut."""
    rings = [_ring(0.0, 0.0, y, hw, hd, 0.0, n, seg, 0.0, oz) for (y, hw, hd, oz) in profile]
    b.loft(tex, rings, col)
    if caps:
        b.cap(tex, rings[0], (0, -1, 0), col)
        b.cap(tex, rings[-1], (0, 1, 0), col)


class _Joint:
    def __init__(self, parent, pos):
        self.pivot = Entity(parent=parent, position=pos)


class LivreurModel:
    HEIGHT = 2.05

    def __init__(self, parent=None):
        self.root = Entity(parent=parent, name="livreur")
        self.body = Entity(parent=self.root)                 # porte tout le corps (saccades sans bouger l'IA)
        self.time = random.uniform(0, 10)
        self.phase = 0.0
        self.look_target = None
        self.state = "patrol"
        self.twitch_t = random.uniform(2.0, 5.0)
        self.twitch = 0.0
        self.twitch_dir = 1.0
        self.glitch_t = 0.0
        self.glitch_hold = 0.0
        self.mouth_open = 0.0
        self.eye_level = 0.5
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self):
        self._shadow()
        self.hips = Entity(parent=self.body, position=(0, 1.0, 0))

        def pelvis(b):
            _tube(b, "jean_sale", PANTS, [(-0.14, 0.15, 0.1, 0), (-0.04, 0.17, 0.11, 0), (0.08, 0.165, 0.105, 0)])
            _tube(b, "cuir", (0.08, 0.07, 0.06), [(0.04, 0.172, 0.112, 0), (0.09, 0.172, 0.112, 0)], caps=False)   # ceinture
            b.obox("jante", 0, 0.05, 0.11, 0.05, 0.035, 0.01, 0, (0.7, 0.68, 0.6))
        _mesh(self.hips, pelvis)

        # jambes : hanche -> genou -> cheville
        self.legs = []
        for side in (-1, 1):
            hip = _Joint(self.hips, (side * 0.095, -0.08, 0))

            def thigh(b):
                _tube(b, "jean_sale", PANTS, [(-0.47, 0.058, 0.062, 0.0), (-0.3, 0.068, 0.072, 0.005), (-0.08, 0.08, 0.085, 0.0),
                                         (0.02, 0.078, 0.08, 0.0)])
            _mesh(hip.pivot, thigh)
            knee = _Joint(hip.pivot, (0, -0.46, 0))

            def shin(b):
                _tube(b, "jean_sale", PANTS, [(-0.42, 0.052, 0.055, 0.0), (-0.25, 0.058, 0.064, -0.005), (-0.05, 0.062, 0.066, 0.0),
                                         (0.03, 0.064, 0.066, 0.0)])
                _tube(b, "jean_sale", (0.12, 0.13, 0.15), [(-0.44, 0.06, 0.063, 0), (-0.4, 0.06, 0.063, 0)], caps=False)   # revers
            _mesh(knee.pivot, shin)
            ankle = _Joint(knee.pivot, (0, -0.44, 0))

            def foot(b):
                _tube(b, "cuir", SHOE, [(-0.075, 0.055, 0.15, 0.05), (-0.03, 0.058, 0.15, 0.05), (0.0, 0.05, 0.1, 0.02),
                                        (0.04, 0.045, 0.06, 0.0)], n=2.2)
                _tube(b, "cuir", (0.75, 0.73, 0.68), [(-0.085, 0.058, 0.152, 0.05), (-0.07, 0.058, 0.152, 0.05)], caps=True)  # semelle
            _mesh(ankle.pivot, foot)
            self.legs.append((hip, knee, ankle))

        # torse (voûté) : pivot à la taille
        self.torso = Entity(parent=self.hips, position=(0, 0.06, 0))

        def torso(b):
            prof = [(0.0, 0.16, 0.105, 0), (0.16, 0.168, 0.11, 0), (0.32, 0.19, 0.12, 0), (0.46, 0.215, 0.122, -0.005),
                    (0.55, 0.225, 0.115, -0.01), (0.61, 0.19, 0.1, -0.015), (0.66, 0.09, 0.075, -0.01)]
            _tube(b, "veste_livreur", JACKET, prof, n=2.4, seg=18)
            # bas de veste élastique, bande réfléchissante, col montant, fermeture éclair
            _tube(b, "veste_livreur", JACKET_DARK, [(-0.02, 0.165, 0.11, 0), (0.05, 0.165, 0.11, 0)], n=2.4, seg=18, caps=False)
            _tube(b, "veste_livreur", (0.55, 0.55, 0.5), [(0.27, 0.187, 0.119, 0), (0.31, 0.19, 0.121, 0)], n=2.4, seg=18, caps=False)
            _tube(b, "veste_livreur", JACKET_DARK, [(0.62, 0.1, 0.085, -0.01), (0.72, 0.085, 0.075, -0.005)], n=2.4, seg=14, caps=False)
            b.obox("metal", 0, 0.02, 0.118, 0.012, 0.62, 0.008, 0, (0.15, 0.15, 0.16))
            b.obox("neon", 0.1, 0.42, 0.122, 0.07, 0.035, 0.006, 0, (1.0, 0.7, 0.3))          # logo QuickEats (poitrine)
            # taches sombres (sang séché ? sauce ?) et déchirure sur le flanc
            for (x, y, z, w, h) in ((-0.08, 0.2, 0.118, 0.07, 0.05), (0.06, 0.1, 0.113, 0.05, 0.08), (-0.12, 0.38, 0.12, 0.04, 0.03)):
                b.obox("veste_livreur", x, y, z, w, h, 0.004, 0, STAIN)
            b.obox("veste_livreur", 0.19, 0.18, 0.0, 0.004, 0.09, 0.06, 0, (0.3, 0.29, 0.28))
            # bretelles du sac
            for x in (-0.11, 0.11):
                b.obox("cuir", x, 0.3, 0.121, 0.035, 0.34, 0.006, 0, (0.12, 0.12, 0.13))
                b.obox("cuir", x, 0.58, 0.0, 0.035, 0.012, 0.24, 0, (0.12, 0.12, 0.13))
            # sac isotherme sur le dos
            b.obox("sac_quickeats", 0, 0.12, -0.24, 0.4, 0.5, 0.24, 0, (0.68, 0.62, 0.56))     # sac sale, délavé
            b.obox("veste_livreur", 0, 0.62, -0.24, 0.41, 0.03, 0.25, 0, JACKET_DARK)
        _mesh(self.torso, torso)

        # cou trop long + tête
        self.neck = Entity(parent=self.torso, position=(0, 0.66, -0.01))

        def neck(b):
            _tube(b, "peau_morte", SKIN, [(-0.04, 0.055, 0.055, 0), (0.08, 0.042, 0.045, 0.01), (0.17, 0.045, 0.048, 0.02)], seg=12)
            b.obox("peau_morte", 0, 0.07, 0.04, 0.02, 0.03, 0.012, 0, SKIN_DARK)                     # pomme d'Adam
        _mesh(self.neck, neck)
        self.head = Entity(parent=self.neck, position=(0, 0.17, 0.02))

        def head(b):
            prof = [(-0.03, 0.04, 0.045, 0.035), (0.0, 0.06, 0.07, 0.03), (0.04, 0.072, 0.088, 0.02), (0.09, 0.08, 0.1, 0.01),
                    (0.15, 0.09, 0.108, 0.0), (0.21, 0.088, 0.104, -0.005), (0.26, 0.072, 0.088, -0.01), (0.295, 0.04, 0.05, -0.012),
                    (0.305, 0.01, 0.012, -0.012)]
            _tube(b, "peau_morte", SKIN, prof, n=2.0, seg=16, caps=False)
            # joues creusées, arcades saillantes, nez fin, oreilles
            from character_model import _ellipsoid
            for x in (-1, 1):
                # joues creusées (ombre), arcades saillantes, oreilles décollées
                b.loft("peau_morte", [_ring(x * 0.058, 0.0, 0.08 + dy, 0.012 * f, 0.03 * f, 0.0, 2.0, 10, 0.0, 0.06)
                                for dy, f in ((-0.035, 0.3), (-0.02, 0.9), (0.0, 1.0), (0.02, 0.9), (0.035, 0.3))], SKIN_DARK)
                b.loft("peau_morte", [_ring(x * 0.038, 0.0, 0.175 + dy, 0.026 * f, 0.012 * f, 0.0, 2.0, 10, 0.0, 0.094)
                                for dy, f in ((-0.01, 0.4), (-0.005, 1.0), (0.005, 1.0), (0.01, 0.4))], SKIN)
                b.loft("peau_morte", [_ring(x * 0.09, 0.0, 0.14 + dy, 0.008 * f, 0.022 * f, 0.0, 2.0, 10, 0.0, -0.005)
                                for dy, f in ((-0.035, 0.3), (-0.02, 0.9), (0.01, 1.0), (0.032, 0.4))], SKIN_DARK)
            # nez long et fin (arête + narines)
            b.loft("peau_morte", [_ring(0.0, 0.0, 0.1 + dy, 0.012 * f, 0.016 * f, 0.0, 2.0, 10, 0.0, 0.106 + oz)
                            for dy, f, oz in ((0.0, 0.7, 0.004), (0.02, 1.0, 0.004), (0.045, 0.75, 0.0), (0.065, 0.45, -0.006))], SKIN)
            # crasse et marbrures sur la peau
            for (x, y, z, r) in ((-0.05, 0.22, 0.085, 0.02), (0.06, 0.07, 0.07, 0.018), (0.02, 0.0, 0.07, 0.015)):
                _ellipsoid(b, "peau_morte", (0.18, 0.15, 0.13), y, r, sx=1.0, sy=1.0, sz=0.35, cz=z, lat=5, seg=8, cx=x)
            # orbites vides (noires et profondes)
            for x in (-0.037, 0.037):
                b.sphere("platre", x, 0.15, 0.086, 0.023, BLACK, lat=6, lon=10, sy=1.3)
            # casquette QuickEats : calotte + visière + bouton
            _tube(b, "veste_livreur", JACKET, [(0.2, 0.094, 0.11, -0.005), (0.25, 0.09, 0.106, -0.01), (0.29, 0.07, 0.085, -0.015),
                                        (0.315, 0.035, 0.045, -0.015), (0.322, 0.005, 0.006, -0.015)], n=2.0, seg=16, caps=False)
            b.obox("veste_livreur", 0, 0.205, 0.15, 0.17, 0.012, 0.11, 0, JACKET_DARK)
            b.sphere("veste_livreur", 0, 0.322, -0.015, 0.012, JACKET_DARK, lat=3, lon=6)
            b.obox("neon", 0, 0.245, 0.104, 0.06, 0.025, 0.006, 0, (1.0, 0.75, 0.35))
        _mesh(self.head, head)
        # bouche trop large (s'ouvre en poursuite) : entité à part pour animer son ouverture
        self.mouth = Entity(parent=self.head, position=(0, 0.055, 0.094))
        _mesh(self.mouth, lambda b: (b.obox("platre", 0, -0.01, 0, 0.08, 0.018, 0.03, 0, BLACK),
                                     b.obox("platre", 0, -0.002, 0.006, 0.074, 0.004, 0.02, 0, (0.45, 0.42, 0.34))), emit=0.0)
        # points lumineux au fond des orbites (non éclairés : visibles dans le noir)
        self.eyes = []
        for x in (-0.037, 0.037):
            e = Entity(parent=self.head, position=(x, 0.15, 0.112))
            _mesh(e, lambda b: b.sphere("neon", 0, 0, 0, 0.0055, (1.0, 0.93, 0.8), lat=5, lon=8), emit=1.0)
            try:
                e.set_light_off()
            except Exception:
                pass
            self.eyes.append(e)

        # bras trop longs : épaule -> coude -> poignet -> doigts
        self.arms = []
        for side in (-1, 1):
            sh = _Joint(self.torso, (side * 0.235, 0.56, -0.01))

            def upper(b):
                _tube(b, "veste_livreur", JACKET, [(-0.37, 0.046, 0.048, 0), (-0.2, 0.052, 0.054, 0), (-0.02, 0.06, 0.062, 0),
                                            (0.03, 0.058, 0.06, 0)])
            _mesh(sh.pivot, upper)
            el = _Joint(sh.pivot, (0, -0.37, 0))

            def fore(b):
                _tube(b, "veste_livreur", JACKET, [(-0.3, 0.038, 0.04, 0), (-0.15, 0.042, 0.045, 0), (0.02, 0.047, 0.05, 0)])
                _tube(b, "veste_livreur", JACKET_DARK, [(-0.32, 0.04, 0.042, 0), (-0.28, 0.04, 0.042, 0)], caps=False)   # poignet
                _tube(b, "peau_morte", SKIN, [(-0.42, 0.024, 0.026, 0), (-0.31, 0.028, 0.03, 0)], seg=10)              # poignet maigre
            _mesh(el.pivot, fore)
            wr = _Joint(el.pivot, (0, -0.42, 0))

            def hand(b):
                b.obox("peau_morte", 0, -0.09, 0, 0.022, 0.1, 0.075, 0, SKIN)                        # paume (de profil)
                b.obox("peau_morte", -side * 0.0, -0.06, 0.045, 0.02, 0.06, 0.02, 0, SKIN_DARK)      # pouce
            _mesh(wr.pivot, hand)
            fingers = Entity(parent=wr.pivot, position=(0, -0.14, 0))

            def fing(b):
                for k, z in enumerate((-0.027, -0.009, 0.009, 0.027)):
                    ln = 0.15 if k in (1, 2) else 0.12                                         # doigts démesurés
                    b.obox("peau_morte", 0, -ln, z, 0.014, ln, 0.013, 0, SKIN)
                    b.obox("peau_morte", 0, -ln - 0.004, z, 0.012, 0.008, 0.011, 0, (0.3, 0.27, 0.25))   # ongles sales
            _mesh(fingers, fing)
            self.arms.append((sh, el, wr, fingers))

    def _shadow(self):
        """Ombre douce au sol (texture radiale générée une fois)."""
        try:
            from PIL import Image, ImageDraw, ImageFilter
            from texture_generator import textures
            if not hasattr(LivreurModel, "_shadow_tex"):
                img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
                ImageDraw.Draw(img).ellipse([10, 10, 54, 54], fill=(0, 0, 0, 170))
                LivreurModel._shadow_tex = textures.from_pil(img.filter(ImageFilter.GaussianBlur(7)))
            self.shadow = Entity(parent=self.root, model="quad", texture=LivreurModel._shadow_tex, rotation_x=90,
                                 position=(0, 0.015, 0), scale=(0.9, 0.9), double_sided=True)
            from panda3d.core import TransparencyAttrib
            self.shadow.setTransparency(TransparencyAttrib.M_alpha)
            self.shadow.set_depth_write(False)
            self.shadow.set_light_off()
        except Exception:
            self.shadow = None

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------
    def animate(self, dt, speed, moving, state="patrol"):
        dt = min(dt, 0.1)
        self.time += dt
        self.state = state
        t = self.time
        if not moving:
            speed = 0.0
        chase = state == "chase"
        stride = 1.9 if chase else 1.35
        self.phase += speed * dt / stride * math.pi * 2.0
        mv = min(1.0, speed / 1.0)
        s = math.sin(self.phase)
        swing = (46 if chase else 30) * mv
        # respiration lourde (épaules qui se soulèvent), plus rapide en poursuite
        br = math.sin(t * (3.2 if chase else 1.4))
        bob = abs(math.cos(self.phase)) * 0.04 * mv
        limp = max(0.0, math.sin(self.phase)) * 0.035 * mv                    # le corps plonge sur la jambe droite
        self.hips.y = 1.0 + bob - limp
        self.hips.rotation_z = math.sin(self.phase) * 4.0 * mv                 # boiterie : bassin qui bascule
        lean = 14.0 + (16.0 if chase else 0.0) * mv
        self.torso.rotation_x = lean + br * 1.5
        self.torso.rotation_z = -self.hips.rotation_z * 0.6
        # jambes (la droite traîne : genou raide, pied qui racle)
        for i, (hip, knee, ankle) in enumerate(self.legs):
            ph = s if i == 0 else -s
            stiff = 0.45 if i == 1 else 1.0
            hip.pivot.rotation_x = -ph * swing
            k = max(0.0, -math.cos(self.phase + (0 if i == 0 else math.pi))) * swing * 1.3 * stiff
            knee.pivot.rotation_x = k + 4
            ankle.pivot.rotation_x = -k * 0.3 + (8 if i == 1 else 0) * mv
        # bras : pendule ballant, avant-bras en retard ; poursuite = bras tendus vers le joueur
        for i, (sh, el, wr, fingers) in enumerate(self.arms):
            ph = -s if i == 0 else s
            lag = math.sin(self.phase - 0.9) * (1 if i == 0 else -1)
            sway = math.sin(t * 0.9 + i * 1.7) * 3.0
            if chase and mv > 0.2:
                # bras tendus vers le joueur, presque à l'horizontale : le torse penché (+lean) entraîne déjà les épaules
                # vers l'arrière, d'où le -lean
                target_sh = -lean - 80 + math.sin(self.phase + i * math.pi) * 10
                target_el = -10 + math.sin(t * 9 + i) * 4
                curl = 10 + math.sin(t * 12 + i * 2) * 12                      # doigts qui s'agitent
            else:
                target_sh = ph * swing * 0.45 - 4 + sway                           # ballants, mains devant les cuisses
                target_el = -6 - lag * swing * 0.35
                curl = 22 + math.sin(t * 0.7 + i) * 6
            k = min(1.0, dt * 9.0)
            sh.pivot.rotation_x += (target_sh - sh.pivot.rotation_x) * k
            sh.pivot.rotation_z = (i * 2 - 1) * (4 + br * 1.2)
            el.pivot.rotation_x += (target_el - el.pivot.rotation_x) * k
            wr.pivot.rotation_x = -8 + math.sin(t * 1.3 + i) * 4
            fingers.rotation_x += (-curl - fingers.rotation_x) * k
        # tête : regard vers le joueur, balayage en recherche, tics au repos
        yaw_t, pitch_t = 0.0, -lean * 0.8
        if self.look_target is not None:
            try:
                hp = self.head.world_position
                d = Vec3(self.look_target) - hp
                # vers le repère du corps
                ry = math.radians(self.root.world_rotation_y)
                lx = d[0] * math.cos(ry) - d[2] * math.sin(ry)
                lz = d[0] * math.sin(ry) + d[2] * math.cos(ry)
                yaw_t = max(-75.0, min(75.0, math.degrees(math.atan2(lx, lz))))
                pitch_t = max(-35.0, min(40.0, math.degrees(math.atan2(-d[1], math.hypot(lx, lz))))) - lean
            except Exception:
                pass
        elif state in ("search", "alert"):
            yaw_t = math.sin(t * 1.1) * 55.0
        self.twitch_t -= dt
        if self.twitch_t <= 0:
            self.twitch_t = random.uniform(0.9, 2.2) if chase else random.uniform(2.5, 6.0)
            self.twitch = 1.0
            self.twitch_dir = random.choice((-1.0, 1.0))
        self.twitch = max(0.0, self.twitch - dt * 3.5)
        tw = math.sin(min(1.0, self.twitch) * math.pi) * 30.0 * self.twitch_dir
        jit = (random.uniform(-3, 3) if chase else 0.0)
        hk = min(1.0, dt * (14.0 if chase else 5.0))
        self.neck.rotation_y += (yaw_t * 0.4 - self.neck.rotation_y) * hk
        self.head.rotation_y += (yaw_t * 0.6 - self.head.rotation_y) * hk
        self.head.rotation_x += (pitch_t - self.head.rotation_x) * hk
        self.head.rotation_z = math.sin(t * 0.6) * 6.0 + tw + jit
        # mâchoire
        target_m = 1.0 if chase else (0.35 if state in ("alert", "search") else 0.1)
        self.mouth_open += (target_m - self.mouth_open) * min(1.0, dt * 4.0)
        self.mouth.scale_y = 1.0 + self.mouth_open * 1.8 + (math.sin(t * 20) * 0.25 if chase else 0.0)
        # yeux : intensité selon l'état, clignotement nerveux
        target_e = {"patrol": 0.45, "alert": 0.8, "search": 0.7, "ambush": 0.15, "chase": 1.0}.get(state, 0.5)
        self.eye_level += (target_e - self.eye_level) * min(1.0, dt * 3.0)
        flick = 1.0 if random.random() > (0.08 if chase else 0.02) else 0.15
        es = 0.6 + self.eye_level * 0.9
        for e in self.eyes:
            e.scale = es * flick
        # saccades « image sautée » en poursuite : le corps est déplacé une fraction de seconde
        self.glitch_t -= dt
        self.glitch_hold -= dt
        if chase and self.glitch_t <= 0:
            self.glitch_t = random.uniform(0.35, 1.1)
            self.glitch_hold = 0.07
            self.body.position = (random.uniform(-0.08, 0.08), 0, random.uniform(-0.05, 0.12))
        elif self.glitch_hold <= 0:
            self.body.position = (0, 0, 0)
