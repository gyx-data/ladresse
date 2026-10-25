"""Cinématique d'introduction (Acte 0) : bureaux → SMS → trajet en voiture → arrivée.

Durées : plan 1 = 25 s, plan 2 = 25 s, plan 3 = 40 s, plan 4 = 30 s (≈ 2 minutes).
Aucun contrôle pour le joueur : tout est scripté. À la fin, la caméra rejoint exactement la
position de départ du joueur dans le couloir, lampe torche allumée.
"""
import math
import random

from PIL import Image, ImageDraw
from ursina import Entity, Vec3, camera, color, destroy, Mesh

import game_data as gd
from cinematic_engine import CameraTrack, Shot, smooth
from lighting_system import LightSource
from room_builder import MeshBuilder
import room_builder as rb
from shaders import horror_shader
from sound_engine import engine as sound
from texture_generator import _font, textures

PLAYER_START = (7.0, 0.0, 0.8)


# ---------------------------------------------------------------------------
# Écran de téléphone dynamique (texture PIL mise à jour)
# ---------------------------------------------------------------------------
class PhoneScreenTexture:
    W, H = 360, 720

    def __init__(self):
        from ursina import Texture
        self.img = Image.new("RGBA", (self.W, self.H), (10, 12, 18, 255))
        self.tex = Texture(self.img)
        self.font = _font(19)
        self.font_s = _font(14)
        self.font_b = _font(22, True)
        self._last = None

    def render(self, msgs, typing, contact="Mme Duval", clock="21:03", gps=None):
        """msgs : [(mine, texte, heure)], typing : (mine, texte_partiel) ou None."""
        key = (len(msgs), typing, gps)
        if key == self._last:
            return
        self._last = key
        W, H = self.W, self.H
        img = Image.new("RGBA", (W, H), (12, 14, 20, 255))
        d = ImageDraw.Draw(img)
        if gps:
            d.rectangle([0, 0, W, H], fill=(24, 30, 42, 255))
            for i in range(0, W, 60):
                d.line([(i, 0), (i + 40, H)], fill=(44, 52, 66, 255), width=4)
            for j in range(0, H, 90):
                d.line([(0, j), (W, j + 30)], fill=(44, 52, 66, 255), width=4)
            d.polygon([(W // 2, H // 2 + 60), (W // 2 - 22, H // 2 + 120), (W // 2 + 22, H // 2 + 120)], fill=(70, 160, 255, 255))
            d.rectangle([0, 0, W, 130], fill=(16, 20, 30, 255))
            d.text((20, 18), "Navigation", fill=(150, 170, 200, 255), font=self.font_s)
            d.text((20, 44), gps, fill=(255, 255, 255, 255), font=self.font_b)
            d.text((20, 84), "Vaulx-en-Velin", fill=(170, 190, 220, 255), font=self.font)
            self._push(img)
            return
        d.rectangle([0, 0, W, 90], fill=(24, 26, 34, 255))
        d.text((16, 14), clock, fill=(255, 255, 255, 255), font=self.font_s)
        d.text((W // 2, 56), contact, fill=(255, 255, 255, 255), font=self.font_b, anchor="mm")
        items = list(msgs)
        if typing is not None:
            items.append((typing[0], typing[1], ""))
        # mise en page
        layouts = []
        maxw = 250
        for mine, text, tm in items:
            lines = self._wrap(d, text, maxw)
            h = 16 + 24 * max(1, len(lines))
            layouts.append((mine, lines, h, tm))
        total = sum(h + 12 for _, _, h, _ in layouts)
        y = 110 - max(0, total - (H - 130))
        for mine, lines, h, tm in layouts:
            x0 = W - 28 - maxw - 18 if mine else 18
            col = (46, 120, 66, 255) if mine else (56, 58, 68, 255)
            if y + h > 90:
                d.rounded_rectangle([x0, y, x0 + maxw + 18, y + h], radius=16, fill=col)
                for i, ln in enumerate(lines):
                    d.text((x0 + 10, y + 8 + i * 24), ln, fill=(255, 255, 255, 255), font=self.font)
            y += h + 12
        self._push(img)

    def _wrap(self, d, text, width):
        out, cur = [], ""
        for w in text.split(" "):
            test = (cur + " " + w).strip()
            if d.textlength(test, font=self.font) <= width:
                cur = test
            else:
                if cur:
                    out.append(cur)
                cur = w
        out.append(cur)
        return out

    def _push(self, img):
        self.img = img
        try:
            self.tex._texture.setRamImageAs(img.transpose(Image.FLIP_TOP_BOTTOM).tobytes(), "RGBA")
        except Exception:
            pass


def _build(builder, parent=None, emit=0.0):
    return builder.build(parent=parent, emit=emit)


# ---------------------------------------------------------------------------
# Plan 1 : bureaux Clairvue Immobilier (0:00 – 0:25)
# ---------------------------------------------------------------------------
class OfficeShot(Shot):
    duration = 25.0
    zone = "bureau"
    fade_in = 1.5

    def setup(self):
        g = self.game
        ox = 200.0
        b = MeshBuilder("bureau")
        W, D, H = 18.0, 9.0, 3.0
        b.quad("beton", (ox, 0, 0), (ox + W, 0, 0), (ox + W, 0, D), (ox, 0, D), (0, 1, 0), (0.55, 0.57, 0.6), tile=1.5)
        b.quad("plafond", (ox, H, 0), (ox + W, H, 0), (ox + W, H, D), (ox, H, D), (0, -1, 0), (0.85, 0.87, 0.9))
        for (a0, a1, f, n_neg, n_pos) in ((ox, ox + W, 0.0, None, None), (ox, ox + W, D, None, None)):
            pass
        b.wall("x", ox, ox + W, 0.0, 0, H, 0.2, tex_neg="platre", tex_pos="platre", col_pos=(0.9, 0.92, 0.95), collide=False)
        b.wall("x", ox, ox + W, D, 0, H, 0.2, tex_neg="platre", tex_pos="platre", col_neg=(0.9, 0.92, 0.95), collide=False)
        b.wall("z", 0, D, ox, 0, H, 0.2, tex_neg="platre", tex_pos="platre", col_pos=(0.9, 0.92, 0.95), collide=False)
        b.wall("z", 0, D, ox + W, 0, H, 0.2, tex_neg="platre", tex_pos="platre", col_neg=(0.9, 0.92, 0.95), collide=False)
        # baies vitrées (nuit) au fond
        for k in range(5):
            wx = ox + 1.5 + k * 3.4
            b.quad("vitre", (wx, 0.8, D - 0.08), (wx + 2.6, 0.8, D - 0.08), (wx + 2.6, 2.6, D - 0.08), (wx, 2.6, D - 0.08), (0, 0, -1), (1, 1, 1))
        # bureaux alignés
        screens = MeshBuilder("ecrans")
        for row, zc in enumerate((2.0, 6.6)):
            for k in range(4):
                cx = ox + 3.0 + k * 3.8
                rb.table(b, cx, zc, 0.0, 1.6, 0.8, 0.74, "bois_meuble", (0.9, 0.88, 0.85), collide=False)
                rb.chair(b, cx, zc - 0.8 if row == 0 else zc + 0.8, 0.0, 0 if row == 0 else 180, col=(0.25, 0.27, 0.3))
                # écran éteint (noir) ; l'écran du fond est allumé en bleu
                sc = (0.02, 0.02, 0.025)
                dirn = -1 if row == 0 else 1
                b.box("metal", cx - 0.28, 0.76, zc + 0.15 * dirn - 0.02, cx + 0.28, 1.2, zc + 0.15 * dirn + 0.02, sc)
                b.box("metal", cx - 0.03, 0.74, zc + 0.15 * dirn - 0.03, cx + 0.03, 0.8, zc + 0.15 * dirn + 0.03, (0.1, 0.1, 0.1))
        # écran allumé au fond (bleu)
        cx = ox + 3.0 + 3 * 3.8
        screens.box("neon", cx - 0.26, 0.78, 6.6 + 0.12 - 0.01, cx + 0.26, 1.18, 6.6 + 0.12 + 0.005, (0.35, 0.55, 1.0))
        # plantes
        for (px, pz) in ((ox + 0.8, 0.8), (ox + 17.2, 0.9), (ox + 8.5, 4.4), (ox + 0.9, 8.2)):
            b.cyl("bois_meuble", px, 0, pz, 0.22, 0.45, 8, (0.6, 0.3, 0.2))
            b.sphere("herbe", px, 0.95, pz, 0.4, (0.35, 0.6, 0.35), sy=1.3)
        # machine à café
        b.box("metal", ox + 16.5, 0.0, 8.0, ox + 17.2, 1.3, 8.6, (0.25, 0.25, 0.28))
        b.box("neon", ox + 16.6, 0.9, 7.98, ox + 16.9, 1.0, 8.0, (1.0, 0.4, 0.2))
        # luminaires néon (tubes)
        tubes = MeshBuilder("tubes")
        lights = []
        for k in range(5):
            tx = ox + 2.0 + k * 3.7
            for tz in (2.2, 6.4):
                tubes.box("neon", tx - 0.6, H - 0.06, tz - 0.05, tx + 0.6, H - 0.01, tz + 0.05, (0.9, 0.95, 1.0))
        for (tx, tz) in ((ox + 4.0, 2.2), (ox + 9.5, 6.4), (ox + 14.0, 2.2), (ox + 7.0, 4.5)):
            lights.append(LightSource((tx, H - 0.3, tz), (0.78, 0.86, 1.0), 1.5, 8.0, kind="static"))
        lights.append(LightSource((cx, 1.0, 6.2), (0.4, 0.6, 1.0), 1.8, 4.5, kind="static"))
        self.lights.extend(lights)
        # le néon du bout vacille
        self.lights[1].kind = "flicker"
        root = Entity()
        for e in b.build(parent=root):
            pass
        for e in tubes.build(parent=root, emit=1.0):
            pass
        for e in screens.build(parent=root, emit=1.0):
            pass
        self.nodes.append(root)
        # caméra : travelling lent dans l'allée
        self.track = CameraTrack([
            (0.0, (ox + 1.0, 1.55, 4.4), (3, 82, 0), 64),
            (12.0, (ox + 7.0, 1.52, 4.5), (2, 92, 0), 62),
            (25.0, (ox + 15.0, 1.5, 4.6), (4, 100, 0), 60),
        ], ease=False)
        g.lighting.ambient_boost = 0.0
        self.amb = sound.loop("bureau_ambiance", 0.5, channel="music", fade_in=2.0)
        self.neon = sound.loop("neon", 0.45, channel="sfx", fade_in=2.0)
        for t in (2.0, 6.0, 10.0):
            self.events.append((t, lambda: sound.play("clavier", 0.4, channel="sfx")))
        self.events.append((14.5, lambda: self._silence()))
        g.cine.add_caption(gd.CINEMATIC_CAPTIONS["bureau"][0], 2.0, 11.0, 1)
        g.cine.add_caption(gd.CINEMATIC_CAPTIONS["bureau"][1], 4.5, 12.5, 2)

    def _silence(self):
        if self.amb:
            self.amb.fade_to(0.15, 0.4)

    def update(self, dt):
        # léger balancement de caméra (steadicam)
        camera.rotation_z = math.sin(self.t * 0.6) * 0.4

    def teardown(self):
        for h in (self.amb, self.neon):
            if h:
                h.fade_to(0.0, 2.0, stop=True)
        camera.rotation_z = 0
        super().teardown()


# ---------------------------------------------------------------------------
# Plan 2 : le SMS (0:25 – 0:50)
# ---------------------------------------------------------------------------
class PhoneShot(Shot):
    duration = 25.0
    zone = "cine_phone"
    fade_in = 0.6
    fade_out = 1.0

    def setup(self):
        g = self.game
        ox = 400.0
        b = MeshBuilder("bureau_tel")
        b.box("bois_meuble", ox - 1.2, -0.05, -1.0, ox + 1.2, 0.0, 1.0, (0.7, 0.62, 0.55), tile=0.8)
        # stylo, trombones, tasse
        b.obox("metal", ox - 0.22, 0.0, 0.05, 0.14, 0.008, 0.008, 30, (0.1, 0.1, 0.3))
        b.cyl("email", ox + 0.25, 0.0, 0.17, 0.045, 0.1, 10, (0.9, 0.9, 0.85))
        b.box("papier", ox - 0.35, 0.0, -0.25, ox - 0.05, 0.004, -0.02, (0.9, 0.9, 0.85))
        # le téléphone
        b.box("metal", ox - 0.040, 0.0, -0.085, ox + 0.040, 0.009, 0.085, (0.05, 0.05, 0.06))
        root = Entity()
        for e in b.build(parent=root):
            pass
        self.nodes.append(root)
        # écran
        self.screen = PhoneScreenTexture()
        scr = Entity(parent=root, model="quad", position=(ox, 0.0105, 0.0), rotation_x=-90, scale=(0.072, 0.15),
                     texture=self.screen.tex, shader=horror_shader, double_sided=True)
        scr.set_shader_input("emit", 1.0)
        scr.rotation_z = 0
        self.nodes.append(scr)
        self.lights.append(LightSource((ox, 0.12, 0.0), (0.5, 0.65, 1.0), 1.6, 1.6, kind="static"))
        self.lights.append(LightSource((ox - 0.6, 0.6, 0.5), (1.0, 0.85, 0.6), 0.35, 2.5, kind="static"))
        self.track = CameraTrack([
            (0.0, (ox + 0.0, 0.36, -0.28), (62, 0, 0), 38),
            (6.0, (ox + 0.02, 0.28, -0.20), (66, 0, 0), 34),
            (25.0, (ox + 0.0, 0.2, -0.1), (74, 0, 0), 30),
        ])
        # timeline des messages
        self.msgs = []
        self.script = []
        t = 1.5
        for (tm, who, text, mine) in gd.INTRO_SMS:
            dur = max(1.0, len(text) / 34.0)
            self.script.append((t, tm, mine, text, dur))
            t += dur + (1.8 if not mine else 1.2)
        self.events.append((0.4, self._vibrate))
        self.amb = sound.loop("bureau_ambiance", 0.2, channel="music", fade_in=1.0)

    def _vibrate(self):
        sound.play("vibration", 1.0)
        self.vibr = 0.8

    def update(self, dt):
        # tremblement de l'écran à la réception
        v = getattr(self, "vibr", 0.0)
        if v > 0:
            self.vibr = v - dt
            camera.x += math.sin(self.t * 120) * 0.0006
        typing = None
        shown = []
        for (t0, tm, mine, text, dur) in self.script:
            if self.t >= t0 + dur:
                shown.append((mine, text, tm))
            elif self.t >= t0:
                n = int(len(text) * (self.t - t0) / dur)
                typing = (mine, text[:n])
                if int((self.t - t0) * 30) % 2 == 0 and n < len(text) and not mine:
                    pass
                break
        # le premier message déclenche une notification sonore
        if not getattr(self, "_notif", False) and self.t >= 1.5:
            self._notif = True
            sound.play("notification", 0.7)
        clock = "21:03"
        for (t0, tm, mine, text, dur) in self.script:
            if self.t >= t0:
                clock = tm
        self.screen.render(shown, typing, clock=clock)

    def teardown(self):
        if getattr(self, "amb", None):
            self.amb.fade_to(0.0, 0.5, stop=True)
        super().teardown()


# ---------------------------------------------------------------------------
# Plan 3 : trajet en voiture (0:50 – 1:30)
# ---------------------------------------------------------------------------
class CarShot(Shot):
    duration = 40.0
    zone = "voiture"
    fade_in = 1.0

    def setup(self):
        g = self.game
        self.ox = -400.0
        ox = self.ox
        b = MeshBuilder("route")
        L = 760.0
        b.quad("asphalte", (ox - 3.2, 0, -50), (ox + 3.2, 0, -50), (ox + 3.2, 0, L), (ox - 3.2, 0, L), (0, 1, 0), (0.8, 0.8, 0.85), tile=3.0)
        b.quad("herbe", (ox + 3.2, -0.02, -50), (ox + 60, -0.02, -50), (ox + 60, -0.02, L), (ox + 3.2, -0.02, L), (0, 1, 0), (0.5, 0.55, 0.5), tile=3.0)
        b.quad("herbe", (ox - 60, -0.02, -50), (ox - 3.2, -0.02, -50), (ox - 3.2, -0.02, L), (ox - 60, -0.02, L), (0, 1, 0), (0.5, 0.55, 0.5), tile=3.0)
        # marquage central discontinu
        z = -40.0
        while z < L:
            b.box("platre", ox - 0.06, 0.005, z, ox + 0.06, 0.012, z + 2.0, (1.0, 0.95, 0.7))
            z += 6.0
        # arbres et bâtiments de bord de route
        rnd = random.Random(11)
        z = 0.0
        while z < L:
            side = rnd.choice([-1, 1])
            x = ox + side * rnd.uniform(5, 14)
            h = rnd.uniform(4, 7)
            b.cyl("bois_meuble", x, 0, z, 0.2, h, 6, (0.3, 0.27, 0.25))
            b.sphere("herbe", x, h, z, rnd.uniform(1.2, 2.0), (0.12, 0.2, 0.12), sy=1.2)
            if rnd.random() < 0.25:
                b.box("crepi", ox + side * rnd.uniform(12, 20), 0, z + 3, ox + side * rnd.uniform(24, 34), rnd.uniform(5, 8), z + 12, (0.3, 0.3, 0.33))
            z += rnd.uniform(9, 18)
        # lampadaires : de plus en plus espacés
        lamp_z = []
        z, gap = 18.0, 24.0
        while z < L:
            lamp_z.append(z)
            z += gap
            gap *= 1.22
        lamps = MeshBuilder("lampadaires")
        for lz in lamp_z:
            b.cyl("metal", ox + 3.6, 0, lz, 0.07, 5.5, 6, (0.3, 0.3, 0.34))
            b.box("metal", ox + 2.6, 5.45, lz - 0.1, ox + 3.7, 5.55, lz + 0.1, (0.3, 0.3, 0.34))
            lamps.box("neon", ox + 2.5, 5.38, lz - 0.1, ox + 3.0, 5.45, lz + 0.1, (1.0, 0.7, 0.35))
        root = Entity()
        for e in b.build(parent=root):
            pass
        for e in lamps.build(parent=root, emit=1.0):
            pass
        self.nodes.append(root)
        self.lamp_z = lamp_z
        self.lamp_lights = [LightSource((ox + 2.7, 5.2, lamp_z[i]), (1.0, 0.65, 0.3), 2.2, 22.0, kind="static") for i in range(len(lamp_z))]
        self.lights.extend(self.lamp_lights)
        # caméra : trajet à vitesse variable (ralentit en s'enfonçant dans la nuit)
        self.cam_z = -20.0
        self.speed = 16.0
        # habitacle (enfant de la caméra)
        self.cab = Entity()
        self.nodes.append(self.cab)
        cb = MeshBuilder("habitacle")
        dark = (0.22, 0.22, 0.25)
        # tableau de bord
        cb.box("platre", -0.9, -0.62, 0.55, 0.9, -0.28, 1.15, dark)
        cb.box("platre", -0.9, -0.28, 0.9, 0.9, -0.2, 1.15, (0.14, 0.14, 0.16))
        # volant (couronne octogonale) incliné
        wheel = Entity(parent=self.cab, position=(-0.3, -0.38, 0.62), rotation=(-62, 0, 0))
        wb = MeshBuilder("volant")
        for k in range(10):
            a0 = 2 * math.pi * k / 10
            a1 = 2 * math.pi * (k + 1) / 10
            r = 0.19
            x0, y0 = math.cos(a0) * r, math.sin(a0) * r
            x1, y1 = math.cos(a1) * r, math.sin(a1) * r
            cxm, cym = (x0 + x1) / 2, (y0 + y1) / 2
            ang = -math.degrees(math.atan2(y1 - y0, x1 - x0))
            wb.obox("tissu", cxm, 0, cym, 0.065, 0.025, 0.04, ang + 90, (0.03, 0.03, 0.03))
        wb.box("tissu", -0.015, 0.0, -0.17, 0.015, 0.02, 0.17, (0.03, 0.03, 0.03))
        wb.box("tissu", -0.17, 0.0, -0.015, 0.17, 0.02, 0.015, (0.03, 0.03, 0.03))
        for e in wb.build(parent=wheel):
            pass
        # les mains d'Adrien (pas de visage)
        hands = MeshBuilder("mains")
        skin = (0.75, 0.58, 0.48)
        hands.box("platre", -0.52, -0.5, 0.52, -0.42, -0.43, 0.64, skin)
        hands.box("platre", -0.12, -0.5, 0.52, -0.02, -0.43, 0.64, skin)
        hands.box("tissu", -0.56, -0.58, 0.28, -0.46, -0.44, 0.52, (0.2, 0.22, 0.3))
        hands.box("tissu", -0.07, -0.58, 0.28, 0.03, -0.44, 0.52, (0.2, 0.22, 0.3))
        for e in hands.build(parent=self.cab, emit=0.05):
            pass
        for e in cb.build(parent=self.cab, emit=0.0):
            pass
        # pare-brise : montant et rétroviseur
        mir = MeshBuilder("retro")
        mir.box("metal", 0.12, 0.38, 0.5, 0.42, 0.5, 0.52, (0.05, 0.05, 0.06))
        for e in mir.build(parent=self.cab):
            pass
        # téléphone / GPS sur le tableau de bord (à droite)
        self.gps = PhoneScreenTexture()
        self.gps.render([], None, gps="17 rue des Lilas")
        gpsb = MeshBuilder("gps")
        gpsb.box("metal", 0.42, -0.34, 0.72, 0.55, -0.12, 0.74, (0.04, 0.04, 0.04))
        for e in gpsb.build(parent=self.cab):
            pass
        gscreen = Entity(parent=self.cab, model="quad", texture=self.gps.tex, position=(0.485, -0.23, 0.7195), scale=(0.115, 0.2), shader=horror_shader,
                         rotation_x=-6, double_sided=True)
        gscreen.set_shader_input("emit", 0.6)
        gscreen.rotation_y = 180
        self.gps_screen = gscreen
        self.lights.append(LightSource((0.4, -0.2, 0.7), (0.5, 0.65, 1.0), 0.0, 1.2, kind="static"))
        self.gps_light = self.lights[-1]
        self.dash_light = LightSource((0, 0, 0), (1.0, 0.6, 0.3), 1.7, 3.2, kind="static")
        self.lights.append(self.dash_light)
        # essuie-glace
        wip = Entity(parent=self.cab, position=(-0.1, -0.2, 1.05))
        wb2 = MeshBuilder("essuie")
        wb2.box("metal", 0, 0, -0.01, 0.8, 0.02, 0.01, (0.02, 0.02, 0.02))
        for e in wb2.build(parent=wip):
            pass
        self.wiper = wip
        self.cab.enabled = True
        # son
        self.eng = sound.loop("moteur", 0.5, channel="sfx", fade_in=2.0)
        self.rain = sound.loop("pluie_pare_brise", 0.5, channel="sfx", fade_in=2.0)
        self.events.append((6.0, self._radio_on))
        self.events.append((20.5, self._radio_cut))
        self.events.append((27.0, self._voice))
        self.events.append((31.0, self._gps))
        g.cine.add_caption(gd.CINEMATIC_CAPTIONS["voiture"][0], 30.0, 38.5, 1)
        self.rad = None
        # pluie visible (gouttes sur le pare-brise)
        self.drops = []
        for i in range(34):
            e = Entity(parent=self.cab, model="circle", color=color.rgba32(190, 205, 230, 70), scale=0.006,
                       position=(random.uniform(-0.8, 0.8), random.uniform(-0.1, 0.45), 0.9))
            self.drops.append(e)

    def _radio_on(self):
        self.rad = sound.play("radio_melodie", 0.55, channel="music")

    def _radio_cut(self):
        sound.play("radio_gresillement", 0.5, channel="sfx")
        if self.rad is not None:
            self.rad.stop()

    def _voice(self):
        sound.play("voix_inversee", 0.7, channel="sfx")

    def _gps(self):
        sound.play("gps_bip", 0.5)
        self.gps_light.base_intensity = 1.0

    def update(self, dt):
        # avance (la cabine est collée à la caméra)
        t = self.t
        self.speed = 16.0 - 6.0 * smooth(t / 40.0)
        self.cam_z += self.speed * dt
        ox = self.ox
        sway = math.sin(t * 0.7) * 0.03
        camera.world_position = Vec3(ox + 1.35 + sway * 0.2, 1.18 + math.sin(t * 9.0) * 0.004, self.cam_z)
        camera.world_rotation = Vec3(1.5, 0.0 + sway * 4, math.sin(t * 0.5) * 0.2)
        camera.fov = 70
        self.track = None
        self.cab.world_position = camera.world_position
        self.cab.world_rotation = camera.world_rotation
        self.dash_light.pos = camera.world_position + Vec3(0.0, -0.25, 0.5)
        self.gps_light.pos = camera.world_position + Vec3(0.45, -0.2, 0.7)
        # sa cabine voit le monde à travers son pare-brise : on garde ses lumières proches
        self.wiper.rotation_z = -20 + 25 * (0.5 + 0.5 * math.sin(t * 2.4))
        for d in self.drops:
            d.y -= dt * 0.02
            if d.y < -0.12:
                d.y = 0.45
                d.x = random.uniform(-0.8, 0.8)
        # le moteur ralentit un peu
        # volume du moteur constant ; autoradio : grésillements
        self.game.player.pos = Vec3(*PLAYER_START)

    def teardown(self):
        for h in (self.eng, self.rain):
            if h:
                h.fade_to(0.0, 1.0, stop=True)
        super().teardown()


# ---------------------------------------------------------------------------
# Plan 4 : arrivée (1:30 – 2:00)
# ---------------------------------------------------------------------------
class ArrivalShot(Shot):
    duration = 33.0
    zone = "dehors"
    show_house = True
    fade_in = 1.2
    fade_out = 0.3

    def setup(self):
        g = self.game
        house = g.house
        lamp = house.anchors["lamp_light"]
        self.lights.append(lamp)
        lamp.enabled = True
        # le lampadaire clignote
        lamp.kind = "flicker"
        self.lamp = lamp
        # Adrien (pieds seulement)
        self.feet = Entity()
        fb = MeshBuilder("pieds")
        fb.box("tissu", -0.07, 0.0, -0.1, 0.07, 0.12, 0.17, (0.08, 0.08, 0.09))
        fb.box("tissu", -0.065, 0.12, -0.05, 0.065, 0.7, 0.06, (0.12, 0.13, 0.22))
        self.foot_l = Entity(parent=self.feet)
        self.foot_r = Entity(parent=self.feet)
        for e in fb.build(parent=self.foot_l):
            pass
        for e in fb.build(parent=self.foot_r):
            pass
        self.foot_l.x, self.foot_r.x = -0.12, 0.12
        self.nodes.append(self.feet)
        self.feet.position = Vec3(11.4, 0.0, -9.0)
        # trajet des pieds : portière de la voiture -> allée -> porche
        self.path = [Vec3(11.4, 0, -9.0), Vec3(8.5, 0, -7.2), Vec3(7.0, 0, -6.0), Vec3(7.0, 0, -0.9)]
        self.pseg = 0
        self.walk_t = 0.0
        self.walk_started = False
        # sons d'ambiance
        self.cri = sound.loop("grillons", 0.35, channel="music", fade_in=2.0)
        self.vent = sound.loop("vent", 0.4, channel="music", fade_in=2.0)
        self.buzz = sound.loop("neon", 0.25, channel="sfx", pos=house.anchors["lamp_pos"], ref=8.0)
        self.events.append((4.0, lambda: sound.play("porte_ouvre", 0.25, pitch=0.7, channel="sfx")))
        self.events.append((9.0, self._start_walk))
        self.events.append((17.0, self._keys))
        self.events.append((20.5, self._open_door))
        self.events.append((26.0, self._dark))
        self.events.append((27.2, self._click))
        self.events.append((28.5, self._title))
        door = house.doors["front"]
        self.door = door
        self.track = CameraTrack([
            (0.0, (13.5, 1.9, -14.0), (6, -26, 0), 58),
            (9.0, (11.0, 1.8, -12.0), (7, -20, 0), 52),
            (9.1, (10.2, 0.28, -10.3), (-2, -38, 0), 62),     # plongée basse derrière les pieds
            (15.5, (8.0, 0.28, -6.5), (-2, -12, 0), 62),
            (17.0, (6.9, 0.5, -3.2), (2, -4, 0), 62),
            (17.1, (6.6, 0.55, -1.7), (18, 28, 0), 40),       # le pot de fleurs, la clé
            (20.4, (6.55, 0.6, -1.6), (22, 30, 0), 36),
            (20.5, (7.0, 1.55, -2.2), (0, 0, 0), 68),
            (26.0, (7.0, 1.6, 0.0), (0, 0, 0), 68),
            (33.0, (PLAYER_START[0], 1.62, PLAYER_START[2]), (0, 0, 0), 75),
        ])
        g.cine.add_caption("", 0, 1, 1)

    def _start_walk(self):
        self.walk_started = True

    def _keys(self):
        sound.play("cles", 0.9, channel="sfx")

    def _open_door(self):
        self.door.open(2.8, silent=True)
        sound.play("porte_ouvre", 1.0, channel="sfx")

    def _dark(self):
        self.game.effects.fade_to(1.0, 1.0)

    def _click(self):
        self.game.player.flashlight.on = True
        sound.play("clic_lampe", 1.0)
        self.game.effects.set_fade(0.0)
        self.game.house.set_level_visibility(0)
        self.game.house.exterior_root.enabled = False
        self.game.lighting.set_zone("rdc", instant=True)
        self.flash_on = True
        camera.position = Vec3(PLAYER_START[0], 1.62, PLAYER_START[2])

    def _title(self):
        self.game.cine.show_title(gd.CINEMATIC_CAPTIONS["titre"], 2.0)

    def update(self, dt):
        # marche des pieds
        if self.walk_started and self.pseg < len(self.path) - 1:
            a, b = self.path[self.pseg], self.path[self.pseg + 1]
            seg = (b - a)
            L = seg.length()
            self.walk_t += dt * 1.45 / max(L, 0.01)
            if self.walk_t >= 1.0:
                self.pseg += 1
                self.walk_t = 0.0
            else:
                pos = a + seg * self.walk_t
                self.feet.position = pos
                self.feet.rotation_y = math.degrees(math.atan2(seg[0], seg[2]))
                ph = self.t * 6.0
                self.foot_l.z = math.sin(ph) * 0.2
                self.foot_r.z = -math.sin(ph) * 0.2
                self.foot_l.y = max(0.0, math.cos(ph)) * 0.05
                self.foot_r.y = max(0.0, -math.cos(ph)) * 0.05
                if int(self.t * 3) % 3 == 0 and not getattr(self, "_stepped", False):
                    self._stepped = True
                    sound.play("pas_beton_%d" % random.randint(0, 2), 0.4)
                elif int(self.t * 3) % 3 != 0:
                    self._stepped = False
        if self.t < 26.0:
            self.game.effects.grain_mult = 1.0
        # lampe torche après l'entrée
        if getattr(self, "flash_on", False):
            p = self.game.player
            pos, rot, fov = self.track.at(self.t)
            fwd = Vec3(math.sin(math.radians(rot[1])), 0, math.cos(math.radians(rot[1])))
            p.flashlight.update(dt, pos, fwd)
        # la porte s'ouvre : lumière du couloir invisible (noir total)
        if self.t > 21.0 and self.t < 26.0:
            self.game.lighting.ambient_boost = 0.0

    def teardown(self):
        for h in (self.cri, self.vent, self.buzz):
            if h:
                h.stop()
        self.lamp.kind = "flicker"
        super().teardown()


def build_intro(game):
    return [OfficeShot(game), PhoneShot(game), CarShot(game), ArrivalShot(game)]
