"""Modèle de personnage articulé et animé (vue à la troisième personne, coéquipiers, habitants du quartier).

Le personnage est construit en géométrie procédurale (MeshBuilder). Chaque habitant a son propre profil :
  * corps : « m » (épaules larges, hanches étroites) ou « f » (épaules plus fines, taille marquée, hanches,
    poitrine, mains et pieds plus petits, un peu moins grande) ;
  * âge : « jeune », « adulte », « âgé » (cheveux gris, dos légèrement voûté) ;
  * tenue : sweat à capuche, survêtement, chemise, manteau, gilet, robe, jupe longue, veste de cuisinier,
    agent de sécurité, polo de magasin, doudoune, uniforme ;
  * coiffure : courte, rasée, chauve, longue, queue de cheval, chignon, bouclée ; barbe / moustache, lunettes.
Chaque membre a sa propre articulation (hanches, genoux, épaules, coudes, cou) pour la marche, la course,
l'accroupissement, la respiration, la visée de la lampe torche et la pose de mort.

Repère local : y = haut, +z = avant du personnage, pieds en y = 0.
"""
import math

from ursina import Entity, color, destroy

from room_builder import MeshBuilder

SKIN_TONES = [(0.86, 0.68, 0.56), (0.72, 0.52, 0.40), (0.55, 0.38, 0.28), (0.93, 0.78, 0.66)]
HAIR_COLS = [(0.10, 0.08, 0.07), (0.28, 0.18, 0.10), (0.06, 0.06, 0.06), (0.45, 0.32, 0.18)]
GREY_HAIR = (0.72, 0.71, 0.69)

BODIES = {
    # largeurs (m) : épaules, poitrine, taille, bassin ; jambes, bras ; écart des hanches et des épaules ; échelle
    "m": dict(shoulder=0.46, chest=0.40, waist=0.38, hips=0.34, thigh=0.15, shin=0.13, arm=0.11, fore=0.10,
              hip_x=0.095, sh_x=0.25, scale=1.0, head=0.11, depth=0.23, hand=0.08, foot=0.26),
    "f": dict(shoulder=0.38, chest=0.35, waist=0.29, hips=0.37, thigh=0.135, shin=0.11, arm=0.085, fore=0.078,
              hip_x=0.09, sh_x=0.205, scale=0.95, head=0.104, depth=0.2, hand=0.068, foot=0.22),
}


def _mesh(parent, build_fn, emit=0.05):
    b = MeshBuilder("perso")
    build_fn(b)
    ents = b.build(parent=parent, emit=emit)
    return ents


def _dark(c, k=0.7):
    return tuple(v * k for v in c)


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
    """Humanoïde stylisé ~1,78 m (homme) / ~1,69 m (femme).

    jacket / pants : couleurs du haut et du bas (r, g, b) 0..1
    flashlight : ajoute une lampe torche dans la main droite (avec `beam_anchor` à son extrémité)
    """

    HEIGHT = 1.78

    def __init__(self, parent=None, jacket=(0.22, 0.24, 0.3), pants=(0.16, 0.2, 0.3), skin=None,
                 hair=None, flashlight=True, seed=0, emit=0.05, hood_up=False, body="m", age="adulte",
                 outfit="hoodie", hair_style=None, beard=None, glasses=False, logo=True, belly=False,
                 shoes=(0.12, 0.12, 0.13)):
        self.root = Entity(parent=parent, name="personnage")
        self.body = body if body in BODIES else "m"
        self.B = BODIES[self.body]
        self.age = age
        self.outfit = outfit
        self.jacket = tuple(jacket)
        self.pants = tuple(pants)
        self.skin = skin or SKIN_TONES[seed % len(SKIN_TONES)]
        self.hair = hair or (GREY_HAIR if age == "âgé" else HAIR_COLS[(seed // 2) % len(HAIR_COLS)])
        self.hair_style = hair_style or ("long" if self.body == "f" else "court")
        self.beard = beard
        self.glasses = glasses
        self.logo = logo
        self.belly = belly
        self.shoes = shoes
        self.emit = emit
        self.phase = 0.0
        self.time = 0.0
        self.crouch = 0.0
        self.aim_pitch = 0.0
        self.dead = False
        self.dead_t = 0.0
        self.hood_up = hood_up
        self.stoop = 7.0 if age == "âgé" else 0.0
        self.HEIGHT = 1.78 * self.B["scale"]
        self._build(flashlight)
        self.root.scale = self.B["scale"]

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self, flashlight):
        B = self.B
        jc, pc, sk, hc = self.jacket, self.pants, self.skin, self.hair
        dark_j = _dark(jc)
        out = self.outfit
        em = self.emit
        fem = self.body == "f"
        skirt = out in ("robe", "jupe_longue")
        top_tex = {"doudoune": "doudoune", "gilet": "tricot", "survetement": "etoffe"}.get(out, "etoffe")
        leg_tex = "jean" if out in ("hoodie", "chemise", "doudoune", "gilet", "manteau") else "etoffe"
        # robe / jupe : jambes en collants (peau légèrement foncée) sous la jupe
        leg_col = _dark(sk, 0.78) if skirt else pc
        shoe = self.shoes
        sole = (0.85, 0.85, 0.82)

        # bassin : pivot global du haut du corps (descend en accroupi)
        self.hips = Entity(parent=self.root, position=(0, 0.92, 0))

        def pelvis(b):
            b.obox(leg_tex, 0, -0.1, 0, B["hips"], 0.2, B["depth"] - 0.02, 0, leg_col if skirt else pc)
            if not skirt and out not in ("cuisinier",):
                b.obox("cuir", 0, 0.04, 0, B["hips"] + 0.01, 0.05, B["depth"] - 0.01, 0, (0.1, 0.08, 0.07))   # ceinture
                b.obox("jante", 0, 0.045, B["depth"] / 2 - 0.004, 0.045, 0.035, 0.01, 0, (0.8, 0.78, 0.7))  # boucle
            if out == "robe":
                b.obox("etoffe", 0, -0.24, 0, B["hips"] + 0.06, 0.34, B["depth"] + 0.04, 0, jc)
                b.obox("etoffe", 0, -0.3, 0, B["hips"] + 0.08, 0.1, B["depth"] + 0.06, 0, _dark(jc, 0.85))   # ourlet
            elif out == "jupe_longue":
                b.obox("etoffe", 0, -0.36, 0, B["hips"] + 0.06, 0.46, B["depth"] + 0.05, 0, pc)
                b.obox("etoffe", 0, -0.62, 0, B["hips"] + 0.13, 0.2, B["depth"] + 0.1, 0, pc)
            elif out == "manteau":
                b.obox("etoffe", 0, -0.27, 0, B["hips"] + 0.06, 0.34, B["depth"] + 0.05, 0, jc)       # pans du manteau
                b.obox("etoffe", 0, -0.3, B["depth"] / 2 + 0.03, 0.012, 0.32, 0.01, 0, dark_j)        # ouverture
            elif out == "cuisinier":
                b.obox("etoffe", 0, -0.3, B["depth"] / 2 + 0.01, B["hips"] - 0.04, 0.46, 0.02, 0, (0.96, 0.96, 0.94))  # tablier
        _mesh(self.hips, pelvis, em)

        # jambes : hanche -> genou -> pied
        self.legs = []
        for side in (-1, 1):
            hip = _Limb(self.hips, (side * B["hip_x"], -0.08, 0))
            _mesh(hip.pivot, lambda b: b.obox(leg_tex, 0, -0.44, 0, B["thigh"], 0.44, B["thigh"] + 0.01, 0, leg_col), em)
            knee = _Limb(hip.pivot, (0, -0.44, 0))

            def shin(b):
                b.obox(leg_tex, 0, -0.4, 0, B["shin"], 0.4, B["shin"] + 0.01, 0, leg_col)
                if not skirt:
                    b.obox(leg_tex, 0, -0.42, 0.0, B["shin"] + 0.005, 0.04, B["shin"] + 0.015, 0, _dark(pc, 0.8))   # revers
                if out == "survetement":
                    b.obox("etoffe", side * B["shin"] / 2, -0.2, 0, 0.012, 0.42, 0.06, 0, (0.95, 0.95, 0.95))
                b.obox("cuir", 0, -0.48, 0.03, B["shin"] + (0.0 if fem else 0.01), 0.08, B["foot"], 0, shoe)
                b.obox("cuir", 0, -0.5, 0.03, B["shin"] + 0.01, 0.025, B["foot"] + 0.01, 0, sole)
                if fem and skirt:
                    b.obox("cuir", 0, -0.53, -0.07, 0.03, 0.06, 0.03, 0, shoe)     # petit talon
            _mesh(knee.pivot, shin, em)
            self.legs.append((hip, knee))

        # torse
        self.torso = Entity(parent=self.hips, position=(0, 0.04, 0))

        def torso(b):
            d = B["depth"]
            b.obox(top_tex, 0, 0.0, 0, B["waist"], 0.26, d - 0.02, 0, jc)                    # taille
            b.obox(top_tex, 0, 0.22, 0, B["chest"], 0.28, d, 0, jc)                          # poitrine
            b.obox(top_tex, 0, 0.48, 0, B["shoulder"], 0.08, d + 0.02, 0, jc)                # épaules
            if fem:
                for x in (-0.068, 0.068):
                    b.sphere(top_tex, x, 0.35, d / 2 - 0.042, 0.058, jc, lat=6, lon=10, sy=0.9, sx=1.05)
            if self.belly:
                b.obox(top_tex, 0, 0.03, 0.025, B["waist"] + 0.05, 0.3, B["depth"] + 0.06, 0, jc)     # ventre
                b.obox(top_tex, 0, 0.08, 0.04, B["waist"] + 0.02, 0.2, B["depth"] + 0.1, 0, jc)
            if out == "hoodie":
                b.obox("etoffe", 0, 0.0, 0.0, B["waist"] + 0.02, 0.08, d + 0.02, 0, dark_j)        # bord-côte
                b.obox("etoffe", 0, 0.12, d / 2 + 0.002, 0.24, 0.13, 0.02, 0, dark_j)            # poche kangourou
                b.obox("etoffe", 0, 0.5, -0.12, 0.3, 0.12, 0.1, 0, dark_j)                       # capuche roulée
                for x in (-0.05, 0.05):
                    b.obox("peau", x, 0.33, d / 2 + 0.008, 0.012, 0.16, 0.012, 0, (0.9, 0.9, 0.88))
                if self.logo:
                    b.obox("neon", 0.1, 0.4, d / 2 + 0.007, 0.06, 0.04, 0.005, 0, (1.0, 0.55, 0.15))
            elif out == "survetement":
                b.obox("etoffe", 0, 0.05, d / 2 + 0.006, 0.012, 0.5, 0.008, 0, (0.85, 0.85, 0.85))  # fermeture éclair
                b.obox("etoffe", 0, 0.54, 0, 0.22, 0.06, d - 0.02, 0, dark_j)                    # col montant
                for x in (-1, 1):
                    b.obox("etoffe", x * (B["chest"] / 2 - 0.01), 0.28, 0, 0.012, 0.44, d + 0.005, 0, (0.95, 0.95, 0.95))
            elif out in ("chemise", "polo"):
                col_c = (0.95, 0.95, 0.93) if out == "chemise" else _dark(jc, 0.6)
                b.obox("etoffe", 0, 0.53, 0.04, 0.2, 0.05, d - 0.06, 0, col_c)                    # col
                for i in range(4 if out == "chemise" else 2):
                    b.obox("peau", 0, 0.42 - i * 0.1, d / 2 + 0.004, 0.012, 0.012, 0.006, 0, (0.92, 0.92, 0.9))
                if out == "polo":
                    b.obox("neon", -0.09, 0.4, d / 2 + 0.006, 0.07, 0.03, 0.004, 0, (0.95, 0.95, 0.95))   # badge
            elif out in ("manteau", "gilet"):
                for x in (-1, 1):                                                                  # revers
                    b.obox("etoffe", x * 0.06, 0.38, d / 2 + 0.006, 0.05, 0.2, 0.01, 0, dark_j)
                for i in range(3):
                    b.obox("cuir", 0.025, 0.28 - i * 0.11, d / 2 + 0.008, 0.02, 0.02, 0.006, 0, (0.18, 0.12, 0.08))
                b.obox("etoffe", 0, 0.47, d / 2 - 0.01, 0.1, 0.1, 0.02, 0, (0.92, 0.92, 0.9) if out == "manteau" else _dark(jc, 0.5))
            elif out == "cuisinier":
                for i in range(3):
                    for x in (-0.06, 0.06):
                        b.obox("peau", x, 0.4 - i * 0.1, d / 2 + 0.005, 0.016, 0.016, 0.006, 0, (0.3, 0.3, 0.32))
                b.obox("etoffe", 0, 0.54, 0.0, 0.24, 0.06, d - 0.04, 0, (0.95, 0.95, 0.94))
            elif out == "securite":
                b.obox("neon", 0, 0.32, -d / 2 - 0.005, 0.3, 0.06, 0.004, 0, (0.95, 0.85, 0.2))   # bande dos
                b.obox("jante", -0.1, 0.4, d / 2 + 0.006, 0.05, 0.05, 0.004, 0, (0.85, 0.8, 0.4))  # écusson
            elif out == "doudoune":
                b.obox("doudoune", 0, 0.55, 0, 0.26, 0.09, d - 0.02, 0, jc)                       # col montant
                b.obox("etoffe", 0, 0.25, d / 2 + 0.004, 0.012, 0.5, 0.006, 0, _dark(jc, 0.55))
            elif out == "robe":
                b.obox("peau", 0, 0.52, 0.06, 0.16, 0.06, d - 0.08, 0, sk)                        # décolleté
            elif out == "uniforme":
                b.obox("etoffe", 0, 0.53, 0.04, 0.2, 0.05, d - 0.06, 0, _dark(jc, 0.6))
                for x in (-0.09, 0.09):
                    b.obox("etoffe", x, 0.38, d / 2 + 0.006, 0.07, 0.06, 0.01, 0, _dark(jc, 0.8))  # poches
                b.obox("jante", 0.09, 0.44, d / 2 + 0.012, 0.03, 0.035, 0.004, 0, (0.85, 0.75, 0.3))   # insigne
        _mesh(self.torso, torso, em)

        # cou + tête
        self.neck = Entity(parent=self.torso, position=(0, 0.6, 0))
        self.head = Entity(parent=self.neck, position=(0, 0.0, 0))
        _mesh(self.head, self._head_mesh, em)

        # bras : épaule -> coude -> main
        self.arms = []
        sleeve_col = jc if out not in ("polo", "robe") else jc
        for side in (-1, 1):
            sh = _Limb(self.torso, (side * B["sh_x"], 0.48, 0))
            short = out in ("polo", "robe")

            def upper(b):
                b.obox(top_tex, 0, -0.3 if not short else -0.14, 0, B["arm"], 0.3 if not short else 0.14, B["arm"] + 0.01, 0, sleeve_col)
                if short:
                    b.obox("peau", 0, -0.3, 0, B["arm"] - 0.02, 0.16, B["arm"] - 0.01, 0, sk)
                if out == "survetement":
                    b.obox("etoffe", side * B["arm"] / 2, -0.3, 0, 0.01, 0.3, 0.05, 0, (0.95, 0.95, 0.95))
            _mesh(sh.pivot, upper, em)
            el = _Limb(sh.pivot, (0, -0.3, 0))

            def fore(b):
                if out in ("polo", "robe"):
                    b.obox("peau", 0, -0.26, 0, B["fore"] - 0.02, 0.26, B["fore"] - 0.01, 0, sk)
                else:
                    b.obox(top_tex, 0, -0.26, 0, B["fore"], 0.26, B["fore"] + 0.01, 0, sleeve_col)
                    b.obox(top_tex, 0, -0.27, 0, B["fore"] + 0.005, 0.04, B["fore"] + 0.015, 0, dark_j)    # poignet
                b.obox("peau", 0, -0.36, 0.0, B["hand"], 0.1, B["hand"] + 0.01, 0, sk)                     # main
                b.obox("peau", 0, -0.42, 0.012, B["hand"] - 0.012, 0.05, B["hand"] - 0.01, 0, _dark(sk, 0.96))   # doigts
            _mesh(el.pivot, fore, em)
            self.arms.append((sh, el))

        # lampe torche dans la main droite
        self.beam_anchor = None
        self.torch = None
        if flashlight:
            _, el = self.arms[1]
            self.torch = Entity(parent=el.pivot, position=(0, -0.37, 0.05))
            body_e = Entity(parent=self.torch, rotation_x=90)          # cylindres le long de +z
            def torch(b):
                b.cyl("metal", 0, -0.02, 0, 0.022, 0.15, 10, (0.1, 0.1, 0.12))                     # corps
                for i in range(4):                                                                  # grip
                    b.cyl("metal", 0, 0.0 + i * 0.022, 0, 0.0235, 0.008, 10, (0.05, 0.05, 0.06), cap=False)
                b.cyl("metal", 0, 0.13, 0, 0.03, 0.05, 12, (0.16, 0.16, 0.18))                     # tête évasée
                b.cyl("jante", 0, 0.178, 0, 0.032, 0.008, 12, (0.85, 0.85, 0.88))                  # bague chromée
            _mesh(body_e, torch, em)
            self.lens = Entity(parent=self.torch, model="circle", position=(0, 0.0, 0.188), scale=0.056,
                               color=color.rgb32(255, 240, 190), double_sided=True)
            self.beam_anchor = Entity(parent=self.torch, position=(0, 0.0, 0.2))

    def _head_mesh(self, b):
        B = self.B
        sk, hc = self.skin, self.hair
        fem = self.body == "f"
        r = B["head"]
        st = self.hair_style
        b.cyl("peau", 0, -0.06, 0, 0.05 if fem else 0.056, 0.1, 6, sk)
        b.sphere("peau", 0, 0.12, 0.0, r, sk, lat=6, lon=10, sy=1.16 if fem else 1.18, sx=0.92 if fem else 0.96)
        if not fem:
            b.obox("peau", 0, 0.03, 0.05, 0.13, 0.05, 0.08, 0, _dark(sk, 0.97))                # mâchoire
        # cheveux
        if st not in ("chauve",):
            thick = 0.006 if st == "rase" else 0.0
            cap_r = r + 0.003 if st == "rase" else r + 0.004
            b.sphere("etoffe", 0, 0.178 - thick, -0.016, cap_r, hc, lat=5, lon=10, sy=0.86 if st != "boucle" else 1.05, sx=1.0)
            if st == "boucle":
                for x, y, z in ((-0.08, 0.2, 0.0), (0.08, 0.2, 0.0), (0, 0.24, -0.04), (-0.06, 0.15, -0.08), (0.06, 0.15, -0.08)):
                    b.sphere("etoffe", x, y, z, 0.05, hc, lat=4, lon=6)
        if st == "long":
            b.obox("etoffe", 0, -0.12, -0.075, 0.23, 0.32, 0.07, 0, hc)                        # nappe dans le dos
            for x in (-0.1, 0.1):
                b.obox("etoffe", x, -0.06, -0.01, 0.04, 0.24, 0.1, 0, hc)                      # mèches de côté
            b.obox("etoffe", 0, 0.21, 0.085, 0.18, 0.04, 0.04, 0, hc)                          # frange
        elif st == "queue":
            b.sphere("etoffe", 0, 0.16, -0.12, 0.04, hc, lat=4, lon=6)
            b.obox("etoffe", 0, -0.02, -0.14, 0.05, 0.28, 0.05, 0, hc)
        elif st == "chignon":
            b.sphere("etoffe", 0, 0.24, -0.08, 0.055, hc, lat=4, lon=8)
        # visage
        for x in (-0.04, 0.04):
            b.obox("peau", x, 0.135, 0.095, 0.028, 0.014, 0.01, 0, (0.95, 0.95, 0.95))         # blanc de l'œil
            b.obox("metal", x, 0.135, 0.101, 0.012, 0.012, 0.006, 0, (0.08, 0.06, 0.05))        # iris
            b.obox("etoffe", x, 0.16, 0.098, 0.04, 0.008 if fem else 0.011, 0.012, 0, _dark(hc, 0.8) if st != "chauve" else _dark(sk, 0.6))
            if fem:
                b.obox("metal", x, 0.143, 0.1, 0.034, 0.004, 0.008, 0, (0.05, 0.04, 0.04))      # cils
        b.obox("peau", 0, 0.08, 0.098, 0.026 if fem else 0.03, 0.05, 0.04, 0, _dark(sk, 0.92))   # nez
        for x in (-r + 0.004, r - 0.004):
            b.obox("peau", x, 0.1, 0.0, 0.02, 0.05, 0.035, 0, _dark(sk, 0.9))                   # oreilles
        lips = (0.66, 0.24, 0.28) if fem else (0.55, 0.32, 0.3)
        b.obox("peau", 0, 0.03, 0.093, 0.048 if fem else 0.05, 0.012 if fem else 0.008, 0.012, 0, lips)
        if self.beard == "barbe":
            b.obox("etoffe", 0, -0.008, 0.078, 0.13, 0.05, 0.04, 0, _dark(hc, 0.9))           # barbe courte
            for x in (-0.062, 0.062):
                b.obox("etoffe", x, 0.02, 0.05, 0.02, 0.07, 0.06, 0, _dark(hc, 0.9))
        elif self.beard == "moustache":
            b.obox("etoffe", 0, 0.05, 0.1, 0.07, 0.016, 0.014, 0, _dark(hc, 0.9))
        if self.glasses:
            for x in (-0.04, 0.04):
                b.obox("metal", x, 0.135, 0.112, 0.045, 0.034, 0.006, 0, (0.1, 0.1, 0.1))
                b.obox("vitre", x, 0.135, 0.115, 0.037, 0.026, 0.004, 0, (0.75, 0.82, 0.88))
            b.obox("metal", 0, 0.14, 0.112, 0.03, 0.006, 0.006, 0, (0.1, 0.1, 0.1))
        if self.hood_up:
            b.sphere("etoffe", 0, 0.14, -0.02, r + 0.025, _dark(self.jacket), lat=5, lon=10, sy=1.15)
        if self.outfit == "cuisinier":
            b.cyl("etoffe", 0, 0.2, -0.01, r + 0.008, 0.14, 10, (0.97, 0.97, 0.96))             # toque
            b.sphere("etoffe", 0, 0.36, -0.01, r + 0.03, (0.97, 0.97, 0.96), lat=4, lon=10, sy=0.55)

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
        stride = 1.25 if sprint else (1.45 if self.body == "f" else 1.6)
        self.phase += speed * dt / stride * math.pi * 2.0
        moving = min(1.0, speed / 1.2)
        swing = (52 if sprint else 34) * moving
        if self.outfit in ("robe", "jupe_longue") and not sprint:
            swing *= 0.8                                       # foulée plus courte en jupe
        s = math.sin(self.phase)
        bob = abs(math.cos(self.phase)) * 0.035 * moving
        breathe = math.sin(self.time * 1.8) * 0.006 * (1 - moving)
        self.hips.y = 0.92 - 0.36 * c + bob
        self.torso.rotation_x = 8 * moving * (1.6 if sprint else 1.0) + 22 * c + self.stoop
        self.torso.y = 0.04 + breathe
        if self.body == "f":
            self.hips.rotation_y = s * 4.0 * moving             # léger balancement du bassin
        for i, (hip, knee) in enumerate(self.legs):
            ph = s if i == 0 else -s
            hip.rx = -ph * swing - 62 * c
            k = max(0.0, -math.cos(self.phase + (0 if i == 0 else math.pi))) * swing * 1.25
            knee.rx = k + 110 * c
            if airborne:
                hip.rx = -25 if i == 0 else 10
                knee.rx = 40
        sl, el = self.arms[0]
        sl.rx = s * swing * 0.9 - 6
        el.rx = -12 - 18 * moving
        sr, er = self.arms[1]
        if self.torch is not None and torch_on:
            target = -80 + aim_pitch * 0.85 - self.torso.rotation_x
            sr.rx += (target - sr.rx) * min(1.0, dt * 12.0)
            er.rx += (-12 - er.rx) * min(1.0, dt * 12.0)
            self.torch.rotation_x = aim_pitch - (sr.rx + er.rx + self.torso.rotation_x)
        else:
            sr.rx = -s * swing * 0.9 - 6
            er.rx = -12 - 18 * moving
            if self.torch is not None:
                self.torch.rotation_x = 0
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
