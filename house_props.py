"""Mobilier, décoration, objets interactifs et éléments cachés de la maison.

Ce module est purement déclaratif : il ajoute de la géométrie aux constructeurs de
niveaux, crée les pièces articulées (portes de meuble, tiroirs, planches, drap...) et
enregistre dans `house.points` les points d'interaction. Le comportement (callbacks) est
branché par `house_events.py`.
"""
import math
import random

from ursina import Entity, Vec3

import room_builder as rb
from config import LEVEL_Y
from lighting_system import LightSource
from room_builder import HingedPart, MeshBuilder, SlidingPart, make_part
from shaders import horror_shader
from texture_generator import textures, text_paper


def hinged(house, level, hinge, w, h, t, direction, toward, tex="bois_meuble", col=(1, 1, 1),
           y0=None):
    """Pièce articulée dont l'axe vertical est en `hinge` (x, z).

    direction : vecteur (x, z) le long duquel le battant fermé s'étend depuis la charnière.
    toward : vecteur (x, z) vers lequel l'extrémité libre doit s'ouvrir.
    """
    dx, dz = direction
    if abs(dx) > abs(dz):
        rot0 = 0.0 if dx > 0 else 180.0
    else:
        rot0 = -90.0 if dz > 0 else 90.0
    a = math.radians(90.0)
    r = (dx * math.cos(a) + dz * math.sin(a), -dx * math.sin(a) + dz * math.cos(a))
    angle = 90.0 if (r[0] * toward[0] + r[1] * toward[1]) > 0 else -90.0
    yy = LEVEL_Y[level] if y0 is None else y0
    return HingedPart(house.level_roots[level], (hinge[0], yy, hinge[1]), (w, h, t), tex=tex, col=col,
                      open_angle=angle * 1.05, side="+x", rot_y=rot0)


def point(house, pid, pos, prompt, level, radius=0.7, **kw):
    """Enregistre un point d'interaction."""
    d = dict(id=pid, pos=Vec3(*pos), prompt=prompt, level=level, radius=radius)
    d.update(kw)
    house.points.append(d)
    return d


def hidden_entity(house, level, tex, pos, size, rot_y=0.0, name="", col=(1, 1, 1)):
    """Quad (texture transparente) désactivé, révélé seulement sur les photos."""
    b = MeshBuilder("reveal")
    sx, sy = size
    b.quad(tex, (-sx / 2, -sy / 2, 0), (sx / 2, -sy / 2, 0), (sx / 2, sy / 2, 0), (-sx / 2, sy / 2, 0), (0, 0, 1), col, tile=max(sx, sy))
    b.quad(tex, (sx / 2, -sy / 2, 0), (-sx / 2, -sy / 2, 0), (-sx / 2, sy / 2, 0), (sx / 2, sy / 2, 0), (0, 0, -1), col, tile=max(sx, sy))
    root = Entity(position=pos, rotation_y=rot_y, parent=house.level_roots[level], enabled=False)
    for e in b.build(parent=root, emit=0.35):
        pass
    house.reveals[name] = dict(entity=root, pos=Vec3(*pos), level=level)
    return root


def populate_house(house):
    house.points = []
    house.parts = {}
    house.reveals = {}
    house.pickups = {}
    house.photo_frames = []
    house.statics = {}
    rng = random.Random(77)
    _rdc(house, rng)
    _etage(house, rng)
    _grenier(house, rng)
    _sous_sol(house, rng)
    _lights(house)


# ---------------------------------------------------------------------------
# Rez-de-chaussée
# ---------------------------------------------------------------------------
def _rdc(house, rng):
    b = house.b(0)
    y0 = 0.0
    A = house.anchors

    # ---------------- Couloir -----------------------------------------
    rb.coat_rack(b, 6.42, 1.7, y0)
    point(house, "manteau", (6.45, 1.1, 1.7), "Fouiller", 0, radius=0.9)
    rb.painting(b, 7.9, 1.5, 3.8, 0.8, 1.3, "-x", tex="miroir")
    # drap plissé qui retombe sur le miroir (retiré par le joueur)
    sheet = Entity(parent=house.level_roots[0], position=(7.84, 0.62, 3.8))
    sb = MeshBuilder("drap_miroir")
    rb.pleated_panel(sb, "drap", 0.0, 0.0, 0.0, 1.0, 1.65, axis="z", depth=0.025, folds=5, col=(0.95, 0.94, 0.9))
    for e in sb.build(parent=sheet):
        pass
    house.parts["drap_miroir"] = sheet
    A["miroir"] = Vec3(7.8, 1.5, 3.8)
    point(house, "miroir", (7.7, 1.4, 3.8), "Retirer le drap", 0, radius=0.9)
    # plaquette de porte d'entrée : verrou
    b.box("metal", 7.4, 1.05, 0.1, 7.5, 1.2, 0.2, (0.5, 0.5, 0.5))
    # empreintes révélées en photo
    hidden = Entity(parent=house.level_roots[0], enabled=False)
    fb = MeshBuilder("empreintes")
    rb.floor_decal(fb, "empreintes", 7.0, 0.0, 6.0, 1.2, 5.0, 0.0, (1, 1, 1), off=0.02)
    for e in fb.build(parent=hidden, emit=0.2):
        pass
    house.reveals["empreintes"] = dict(entity=hidden, pos=Vec3(7.0, 0.1, 6.0), level=0)
    # Porte du sous-sol : planches clouées + cadenas + griffures
    for i, (yy, rz) in enumerate(((0.55, 3.0), (1.05, -2.0), (1.6, 4.0))):
        house.parts[f"planche_{i}"] = make_part(house.level_roots[0], "planches", (1.35, 0.2, 0.05), (7.0, yy, 11.86), (0.9, 0.85, 0.8), 1.0)
        house.parts[f"planche_{i}"].rotation_z = rz
    house.parts["cadenas"] = make_part(house.level_roots[0], "metal", (0.12, 0.16, 0.05), (7.0, 1.05, 11.8), (0.75, 0.75, 0.75), 1.0)
    rb.wall_decal(b, "griffures", 7.0, 1.1, 11.89, 1.2, 1.9, "-z", off=0.0)
    point(house, "planches", (7.0, 1.1, 11.6), "Examiner la porte", 0, radius=1.0)
    # couloir : tableau / horloge arrêtée
    if not b.model("wall_clock", 6.13, 4.6, 1.9, 90.0, (0.4, 0.4, None)):
        b.box("metal", 6.1, 1.9, 4.4, 6.14, 2.3, 4.8, (0.4, 0.38, 0.35))

    # ---------------- Salon --------------------------------------------
    rb.armchair(b, 1.6, 4.5, 270, y0)
    A["fauteuil"] = Vec3(1.6, 0.6, 4.5)
    rb.sofa(b, 3.1, 5.4, 180, y0)
    rb.table(b, 3.1, 4.1, y0, 1.1, 0.55, 0.42)
    b.obox("papier", 3.1, y0 + 0.42, 4.1, 0.45, 0.06, 0.32, 12, (0.85, 0.82, 0.75))
    point(house, "journaux", (3.1, 0.5, 4.1), "Lire", 0, radius=0.8)
    # meuble télé + CRT
    b.box("bois_meuble", 3.6, y0, 0.15, 4.8, y0 + 0.55, 0.65, (0.6, 0.55, 0.5), collide=True)
    if b.model("Television_01", 4.2, 0.38, y0 + 0.55, 0.0, (0.75, None, 0.58)):
        b.colliders.append((3.78, y0 + 0.55, 0.2, 4.62, y0 + 1.2, 0.62))
        # écran du modèle (mesuré sur sa vue de face : 69 % x 69 %, décalé vers la gauche du poste)
        screen_pos, screen_size = (4.283, y0 + 0.867, 0.675), (0.51, 0.39)
    else:
        b.box("metal", 3.78, y0 + 0.55, 0.2, 4.62, y0 + 1.2, 0.62, (0.18, 0.18, 0.18), collide=True)
        screen_pos, screen_size = (4.2, 0.88, 0.635), (0.62, 0.5)
    A["tv_screen_pos"] = Vec3(*screen_pos)
    tv = Entity(parent=house.level_roots[0], model="quad", texture=textures.get("ecran_noir"), shader=horror_shader,
                position=screen_pos, scale=screen_size, rotation_y=180, double_sided=True)
    tv.set_shader_input("emit", 0.0)
    house.parts["tv_screen"] = tv
    point(house, "tv", (4.2, 0.9, 0.9), "Éteindre", 0, radius=0.8, enabled=False)
    rb.bookshelf(b, 5.6, 4.0, 5.88, 5.7, y0, 2.1, rng, face="-x")
    # cheminée
    b.box("bois_meuble", 0.1, y0, 1.0, 0.55, y0 + 1.25, 1.3, (0.6, 0.58, 0.55), collide=True)
    b.box("bois_meuble", 0.1, y0, 2.1, 0.55, y0 + 1.25, 2.4, (0.6, 0.58, 0.55), collide=True)
    b.box("bois_meuble", 0.1, y0 + 1.25, 0.9, 0.6, y0 + 1.4, 2.5, (0.5, 0.48, 0.45))
    b.box("beton", 0.1, y0, 1.3, 0.3, y0 + 1.1, 2.1, (0.15, 0.14, 0.14))
    b.box("beton", 0.3, y0, 1.3, 0.55, y0 + 0.06, 2.1, (0.5, 0.5, 0.5))     # cendres
    b.obox("metal", 0.9, y0, 1.7, 0.04, 0.04, 0.7, 20, (0.2, 0.2, 0.2))    # tisonnier
    point(house, "tisonnier", (0.9, 0.1, 1.7), "Ramasser", 0, radius=0.9)
    rb.bookshelf  # (déjà utilisé)
    # cadre photo au mur (mur est, entre l'angle et la porte : le mur nord est l'arche vers la cuisine)
    rb.painting(b, 5.9, 1.7, 1.2, 0.7, 0.5, "-x", tex="portrait")
    # reveals : silhouette dans le fauteuil
    hidden_entity(house, 0, "silhouette", (1.75, 0.85, 4.5), (0.8, 1.5), rot_y=-90, name="fauteuil")

    # ---------------- Cuisine ------------------------------------------
    # plan de travail en L
    rb.counter(b, 0.1, 7.2, 0.7, 8.6, y0)
    rb.counter(b, 0.1, 9.4, 0.7, 11.9, y0)
    rb.counter(b, 0.7, 11.3, 3.4, 11.9, y0)
    # évier inox encastré : meuble sous évier, plan de travail découpé autour du bac
    b.box("bois_meuble", 0.1, y0, 8.6, 0.7, y0 + 0.86, 9.4, (0.6, 0.55, 0.5), collide=True, skip=("+y",))
    for (x0_, z0_, x1_, z1_) in ((0.08, 8.58, 0.16, 9.42), (0.56, 8.58, 0.72, 9.42), (0.16, 8.58, 0.56, 8.64), (0.16, 9.36, 0.56, 9.42)):
        b.box("marbre", x0_, y0 + 0.86, z0_, x1_, y0 + 0.9, z1_, (1, 1, 1))
    b.loft("metal", [rb._ring(0.36, 9.0, y0 + 0.902, 0.205, 0.365, 0.0, 8.0), rb._ring(0.36, 9.0, y0 + 0.902, 0.185, 0.345, 0.0, 6.0)],
           (0.8, 0.8, 0.82), outward=False)
    floor = rb._basin(b, "metal", 0.36, 9.0, 0.0, y0 + 0.902, (0.185, 0.345), (0.185, 0.345), 0.2, (0.72, 0.72, 0.75),
                      n_out=6.0, n_in=6.0, bulge=(1.0, 0.99, 0.97, 0.94, 0.9))
    b.cap("metal", rb._ring(0.36, 9.0, floor[0][1] + 0.002, 0.03, 0.03, 0.0, 2.0, seg=12), (0, 1, 0), (0.2, 0.2, 0.22))
    b.cyl("metal", 0.14, y0 + 0.9, 9.0, 0.02, 0.32, 12, (0.85, 0.85, 0.88))                   # robinet col de cygne
    b.obox("metal", 0.23, y0 + 1.19, 9.0, 0.19, 0.028, 0.028, 0.0, (0.85, 0.85, 0.88))
    for zz in (8.88, 9.12):
        b.cyl("metal", 0.14, y0 + 0.9, zz, 0.02, 0.06, 10, (0.85, 0.85, 0.88))
    A["robinet"] = Vec3(0.25, 1.2, 9.03)
    # réfrigérateur (corps + porte articulée + intérieur)
    rb.fridge_body(b, 5.2, 11.55, y0, 180, 0.7, 0.7, 1.75)
    b.quad("platre", (4.88, 0.05, 11.19), (5.52, 0.05, 11.19), (5.52, 1.7, 11.19), (4.88, 1.7, 11.19), (0, 0, -1), (0.25, 0.27, 0.28))
    b.obox("email", 5.2, 0.6, 11.4, 0.34, 0.03, 0.34, 0, (0.45, 0.5, 0.35))                   # assiette moisie
    b.obox("papier", 5.2, 0.63, 11.4, 0.2, 0.02, 0.16, 20, (0.8, 0.8, 0.7))                   # note
    house.parts["frigo_porte"] = hinged(house, 0, (4.85, 11.17), 0.7, 1.75, 0.06, (1, 0), (0, -1), "email", (1, 1, 1))
    A["frigo"] = Vec3(5.2, 1.0, 11.0)
    point(house, "frigo", (5.2, 1.0, 11.0), "Ouvrir", 0, radius=0.9)
    # papier magnétique (adresse)
    hidden_paper = text_paper("17 rue des Lilas\n06300 Nice", 256, 24, 11)
    ptex = textures.from_pil(hidden_paper)
    pe = Entity(parent=house.level_roots[0], model="quad", texture=ptex, shader=horror_shader, position=(5.35, 1.45, 11.12),
                scale=(0.2, 0.2), rotation_y=180, double_sided=True)
    pe.set_shader_input("emit", 0.0)
    house.parts["papier_adresse"] = pe
    point(house, "adresse_frigo", (5.35, 1.45, 11.0), "Lire le papier", 0, radius=0.7)
    # four
    # cuisinière émaillée : caisse arrondie, cavité, bandeau à manettes, plaques, dosseret
    rb.rounded_box(b, "email", 4.0, 11.525, y0, 0.8, 0.9, 0.75, 180, (0.93, 0.92, 0.86), n=10.0, bevel=0.02)
    b.colliders.append((3.6, y0, 11.15, 4.4, y0 + 0.9, 11.9))
    b.box("beton", 3.65, y0 + 0.15, 11.13, 4.35, y0 + 0.65, 11.16, (0.04, 0.04, 0.04))
    b.box("metal", 3.62, y0 + 0.72, 11.13, 4.38, y0 + 0.86, 11.15, (0.78, 0.78, 0.8))
    for k in range(4):
        b.sphere("metal", 3.72 + k * 0.17, y0 + 0.79, 11.12, 0.025, (0.15, 0.15, 0.15), lat=5, lon=10, sy=0.8)
    for (px, pz, r) in ((3.8, 11.35, 0.09), (4.2, 11.35, 0.07), (3.8, 11.7, 0.07), (4.2, 11.7, 0.09)):
        b.cyl("metal", px, y0 + 0.9, pz, r, 0.012, 16, (0.12, 0.12, 0.13))
    b.box("email", 3.6, y0 + 0.9, 11.84, 4.4, y0 + 1.02, 11.9, (0.93, 0.92, 0.86))
    house.parts["four_porte"] = hinged(house, 0, (3.65, 11.1), 0.7, 0.5, 0.05, (1, 0), (0, -1), "metal", (0.65, 0.65, 0.68), y0=0.15)
    point(house, "four", (4.0, 0.5, 11.0), "Ouvrir", 0, radius=0.9)
    # table et chaises
    rb.table(b, 3.2, 8.4, y0, 1.2, 0.8, 0.75)
    rb.chair(b, 3.2, 7.3, y0, 0)
    rb.chair(b, 3.8, 9.3, y0, 0, fallen=True)
    b.cyl("email", 3.0, y0 + 0.75, 8.35, 0.025, 0.09, 6, (0.95, 0.95, 0.95))                    # salière
    point(house, "sel", (3.0, 0.85, 8.35), "Ramasser le sel", 0, radius=0.8)
    # tiroirs
    house.parts["tiroir_cuisine"] = SlidingPart(house.level_roots[0], (0.45, 0.65, 10.2), (0.5, 0.18, 0.5), "bois_meuble", (0.7, 0.65, 0.6), travel=(0.35, 0, 0))
    point(house, "tiroirs", (0.7, 0.8, 10.2), "Ouvrir le tiroir", 0, radius=0.9)
    # griffures sur le sol
    rb.floor_decal(b, "taches", 2.0, y0, 9.5, 2.2, 2.2, 15, (0.6, 0.6, 0.6))
    A["frigo_hum"] = Vec3(5.2, 1.0, 11.5)

    # ---------------- Bureau -------------------------------------------
    rb.table(b, 12.0, 3.6, y0, 1.6, 0.75, 0.75)
    rb.chair(b, 12.0, 2.9, y0, 0)
    b.box("metal", 15.2, y0, 2.5, 15.9, y0 + 1.3, 3.5, (0.45, 0.5, 0.45), collide=True)
    for k in range(3):
        b.box("metal", 15.15, y0 + 0.1 + k * 0.4, 2.6, 15.2, y0 + 0.4 + k * 0.4, 3.4, (0.35, 0.4, 0.35))
    point(house, "recus", (15.1, 0.9, 3.0), "Fouiller le classeur", 0, radius=0.9)
    rb.bookshelf(b, 9.0, 4.15, 11.0, 4.4, y0, 2.0, rng, face="-z")
    b.obox("papier", 12.0, y0 + 0.75, 3.6, 0.5, 0.04, 0.35, 5, (0.9, 0.9, 0.85))
    b.cyl("metal", 12.6, y0 + 0.75, 3.7, 0.05, 0.03, 8, (0.3, 0.3, 0.3))
    point(house, "pile_bureau", (12.6, 0.85, 3.7), "Prendre la pile", 0, radius=0.8)
    rb.carton(b, 15.2, 0.9, y0, 0.5)
    rb.carton(b, 14.6, 0.9, y0, 0.4, 20)

    # ---------------- Cage d'escalier ----------------------------------
    rb.table(b, 11.4, 11.4, y0, 0.9, 0.4, 0.8)
    b.cyl("email", 11.4, y0 + 0.8, 11.4, 0.07, 0.25, 8, (0.8, 0.8, 0.75))
    b.box("herbe", 11.34, y0 + 1.05, 11.34, 11.46, y0 + 1.3, 11.46, (0.25, 0.22, 0.15))     # fleurs mortes
    rb.painting(b, 8.9, 1.7, 11.9, 0.8, 0.6, "-z", tex="portrait")     # à côté de la fenêtre condamnée (x 10)
    rb.carton(b, 11.5, 5.2, y0, 0.45)

    # ---------------- Salle de bain RDC --------------------------------
    rb.toilet(b, 15.5, 7.8, y0, 270)
    rb.sink(b, 15.55, 6.5, y0, 270)
    rb.painting(b, 15.88, 1.55, 6.5, 0.55, 0.7, "-x", tex="miroir_brise")
    rb.wall_decal(b, "griffures", 15.85, 1.2, 8.2, 0.7, 1.0, "-x", off=0.01, col=(0.7, 0.7, 0.7)) if False else None
    rb.bathtub(b, 14.4, 5.35, y0, 0, 1.6, 0.75)
    # rideau de douche plissé (coulisse de 1,25 m en x quand on le tire) sous une tringle chromée
    b.obox("metal", 14.85, y0 + 2.31, 5.78, 2.1, 0.025, 0.025, 0, (0.85, 0.85, 0.88))
    curtain = Entity(parent=house.level_roots[0], position=(14.4, y0 + 0.66, 5.78))
    cb_ = MeshBuilder("rideau")
    rb.pleated_panel(cb_, "rideau", 0.0, 0.0, 0.0, 1.7, 1.62, axis="x", depth=0.045, folds=9, col=(1, 1, 1))
    for e in cb_.build(parent=curtain):
        pass
    house.parts["rideau"] = curtain
    A["rideau"] = Vec3(14.4, 1.2, 5.78)
    point(house, "rideau", (14.4, 1.2, 5.9), "Tirer le rideau", 0, radius=1.0)
    point(house, "miroir_brise", (15.6, 1.5, 6.5), "Regarder le miroir brisé", 0, radius=0.9)
    b.box("beton", 15.47, y0 + 0.735, 6.42, 15.6, y0 + 0.75, 6.55, (0.7, 0.75, 0.8))         # éclat au fond de la vasque
    A["tuyauterie"] = Vec3(13.0, 1.0, 5.0)

    # ---------------- Buanderie ---------------------------------------
    rb.washing_machine(b, 15.3, 11.3, y0, 180)                     # hublot côté pièce (le mur est en z = 12)
    rb.shelving_unit(b, 12.2, 11.2, 14.0, 11.8, y0)
    b.box("planches", 12.3, y0 + 0.6, 11.3, 13.9, y0 + 0.63, 11.7, (0.8, 0.75, 0.7))
    rb.delivery_bag(b, 13.0, 11.5, y0 + 0.63, 0, torn=False)
    point(house, "sac_propre", (13.0, 1.0, 11.2), "Examiner le sac", 0, radius=0.9)
    rb.crate(b, 12.7, 9.3, y0)
    rb.crate(b, 13.3, 9.2, y0, 0.4, 25)
    b.obox("metal", 15.2, y0, 9.5, 0.5, 0.9, 0.04, 40, (0.6, 0.6, 0.6))                      # planche à repasser


# ---------------------------------------------------------------------------
# Premier étage
# ---------------------------------------------------------------------------
def _etage(house, rng):
    b = house.b(1)
    y0 = LEVEL_Y[1]
    A = house.anchors

    # ---------------- Couloir ------------------------------------------
    # néon au plafond
    A["neon_pos"] = Vec3(7.0, y0 + 2.72, 3.5)
    nb = MeshBuilder("neon")
    nb.box("neon", 6.55, y0 + 2.7, 3.4, 7.45, y0 + 2.76, 3.6, (1, 1, 1))
    house.parts["neon_tube"] = nb.build(parent=house.level_roots[1], emit=1.0)[0]
    b.box("metal", 6.5, y0 + 2.76, 3.35, 7.5, y0 + 2.8, 3.65, (0.4, 0.4, 0.4))            # platine fixée au plafond, tube dessous
    # photos de famille
    frames = []
    # mur x=8 seulement le long de la chambre condamnée (z < 4.5) : au-delà, le couloir donne sur le palier
    for z in (0.6, 1.4, 2.2, 3.0, 3.8):
        rb.painting(b, 7.9, y0 + 1.65, z, 0.42, 0.55, "-x", tex="portrait")
        frames.append((7.9, y0 + 1.65, z))
    house.photo_frames = frames
    # placard : étagères et produits
    for k in range(4):
        b.box("planches", 0.15, y0 + 0.4 + k * 0.5, 10.2, 0.55, y0 + 0.43 + k * 0.5, 11.8, (0.8, 0.75, 0.7), collide=False)
    b.box("planches", 0.15, y0, 10.2, 0.55, y0 + 2.0, 11.8, (0.5, 0.5, 0.5), collide=True, skip=("+x",))
    for k in range(10):
        b.cyl("email", rng.uniform(0.25, 0.45), y0 + 0.43 + (k % 4) * 0.5, 10.4 + k * 0.13, 0.05, 0.22, 6,
              rng.choice([(0.7, 0.3, 0.3), (0.3, 0.5, 0.7), (0.8, 0.8, 0.8)]))
    b.obox("metal", 5.3, y0, 10.7, 0.3, 1.2, 0.04, 70, (0.5, 0.45, 0.35), collide=False)     # balais
    b.cyl("metal", 0.35, y0 + 0.93, 11.65, 0.05, 0.03, 8, (0.3, 0.3, 0.3))                    # pile posée sur l'étagère
    point(house, "pile_placard", (0.7, y0 + 1.0, 11.5), "Fouiller le placard", 1, radius=1.3)

    # ---------------- Chambre principale -------------------------------
    rb.bed(b, 1.35, 3.0, 90, y0)
    # amas d'oreillers sous le drap, à la forme vaguement humaine (tête côté tête de lit, x bas)
    lump = Entity(parent=house.level_roots[1])
    lb = MeshBuilder("forme_lit")
    for k in range(9):
        lx = 0.8 + k * 0.17
        r = 0.13 + 0.09 * math.sin(math.pi * (k + 0.5) / 9)          # plus épais au milieu (le « torse »)
        lb.sphere("drap", lx, y0 + 0.57, 3.0 + 0.03 * math.sin(k * 1.7), r, (0.9, 0.87, 0.82), lat=12, lon=20, sy=0.38)
    for e in lb.build(parent=lump):
        pass
    house.parts["oreillers"] = lump
    point(house, "lit", (1.5, y0 + 0.7, 3.0), "Soulever les draps", 1, radius=1.1)
    point(house, "dessous_lit", (2.9, y0 + 0.2, 3.0), "Regarder sous le lit", 1, radius=0.9)
    rb.table(b, 0.45, 4.15, y0, 0.45, 0.45, 0.55)
    rb.table(b, 0.45, 1.85, y0, 0.45, 0.45, 0.55)
    b.obox("papier", 0.45, y0 + 0.55, 4.15, 0.18, 0.025, 0.24, 15, (0.25, 0.2, 0.15))       # carnet
    point(house, "carnet", (0.5, y0 + 0.6, 4.15), "Ouvrir le carnet", 1, radius=0.8)
    rb.wardrobe(b, 3.4, 0.15, 5.5, 0.75, y0)
    house.parts["armoire_g"] = hinged(house, 1, (3.4, 0.76), 1.05, 2.0, 0.04, (1, 0), (0, 1), "bois_meuble", (0.65, 0.6, 0.55))
    house.parts["armoire_d"] = hinged(house, 1, (5.5, 0.76), 1.05, 2.0, 0.04, (-1, 0), (0, 1), "bois_meuble", (0.65, 0.6, 0.55))
    point(house, "armoire", (4.45, y0 + 1.1, 1.2), "Ouvrir l'armoire", 1, radius=1.1)
    point(house, "volets_master", (2.0, y0 + 1.5, 0.5), "Ouvrir les volets", 1, radius=1.0)
    b.obox("tissu", 4.45, y0 + 0.7, 0.62, 0.5, 1.1, 0.04, 0, (0.18, 0.2, 0.28))             # uniforme dans l'armoire
    hidden_entity(house, 1, "papier", (3.0, y0 + 1.7, 5.88), (0.9, 0.6), rot_y=180, name="mur_message", col=(1.0, 0.9, 0.85))
    rb.painting(b, 5.9, y0 + 1.7, 1.3, 0.5, 0.65, "-x", tex="portrait")     # à côté de la porte (z 3)
    b.box("tissu", 1.0, y0, 0.9, 2.6, y0 + 0.02, 1.9, (0.4, 0.15, 0.12))                     # tapis

    # ---------------- Chambre d'amis ------------------------------------
    rb.bed(b, 1.1, 7.4, 90, y0, w=0.95, l=1.9, col_sheet=(0.75, 0.8, 0.7))
    rb.table(b, 3.4, 9.55, y0, 1.3, 0.55, 0.75)
    rb.chair(b, 3.4, 8.9, y0, 0)
    house.parts["tiroir_bureau"] = SlidingPart(house.level_roots[1], (3.4, y0 + 0.62, 9.3), (0.5, 0.1, 0.4), "bois_meuble", (0.7, 0.65, 0.6), travel=(0, 0, -0.3))
    point(house, "tiroir_amis", (3.4, y0 + 0.75, 9.1), "Ouvrir le tiroir", 1, radius=0.9)
    # vieux portable (caché dans le tiroir)
    house.parts["tel_garnier"] = make_part(house.level_roots[1], "metal", (0.07, 0.015, 0.14), (3.4, y0 + 0.63, 9.45), (0.12, 0.12, 0.14))
    house.parts["tel_garnier"].enabled = False
    point(house, "tel_garnier", (3.4, y0 + 0.7, 9.35), "Prendre le téléphone", 1, radius=0.8, enabled=False)
    rb.bookshelf(b, 5.55, 6.5, 5.88, 8.0, y0, 1.9, rng, face="-x") if False else None
    b.obox("tissu", 5.0, y0, 7.4, 0.9, 0.5, 0.6, 0, (0.4, 0.3, 0.25), collide=True)          # coffre à jouets
    point(house, "jouet", (5.0, y0 + 0.55, 7.4), "Examiner", 1, radius=0.9)
    A["berceuse"] = Vec3(2.5, y0 + 1.2, 8.0)

    # ---------------- Chambre condamnée --------------------------------
    cb = b
    cb.box("metal", 11.97, y0 + 2.2, 2.22, 12.03, y0 + 2.8, 2.28, (0.5, 0.5, 0.5))          # tige du crochet
    cb.cyl("metal", 12.0, y0 + 2.05, 2.25, 0.06, 0.18, 6, (0.5, 0.5, 0.5))
    rb.floor_decal(b, "sel", 12.0, y0, 2.25, 2.0, 2.0, 0.0, (1, 1, 1))
    point(house, "sel_condamnee", (12.0, y0 + 0.1, 2.25), "Toucher le sel", 1, radius=1.0)
    A["condamnee_centre"] = Vec3(12.0, y0 + 1.0, 2.25)

    # ---------------- Salle de bain 1er ---------------------------------
    rb.bathtub(b, 14.0, 10.9, y0, 0, 1.6, 0.75, water=True)
    rb.sink(b, 15.55, 8.0, y0, 270)
    rb.toilet(b, 15.5, 9.6, y0, 270) if False else None
    rb.painting(b, 15.88, y0 + 1.55, 8.0, 0.55, 0.7, "-x", tex="miroir")
    # armoire à pharmacie murale : caisson creux (fond, côtés, dessus, dessous, 2 étagères), porte sur la façade
    px0, px1, pz0, pz1, py0, py1 = 15.62, 15.9, 10.2, 10.7, y0 + 1.3, y0 + 2.0
    white = (0.86, 0.86, 0.84)
    b.box("email", px1 - 0.02, py0, pz0, px1, py1, pz1, white)                                  # fond
    b.box("email", px0, py0, pz0, px1, py1, pz0 + 0.02, white)                                  # côtés
    b.box("email", px0, py0, pz1 - 0.02, px1, py1, pz1, white)
    b.box("email", px0, py1 - 0.02, pz0, px1, py1, pz1, white)                                  # dessus / dessous
    b.box("email", px0, py0, pz0, px1, py0 + 0.02, pz1, white)
    for sy in (py0 + 0.24, py0 + 0.47):                                                          # étagères
        b.box("email", px0 + 0.02, sy, pz0 + 0.02, px1 - 0.02, sy + 0.015, pz1 - 0.02, white)
    for k, (zz, hh, c) in enumerate(((10.3, 0.12, (0.55, 0.3, 0.15)), (10.42, 0.09, (0.85, 0.85, 0.85)), (10.58, 0.14, (0.3, 0.45, 0.6)))):
        b.cyl("vitre" if k == 0 else "email", 15.78, py0 + 0.02, zz, 0.03, hh, 8, c)              # flacons
    b.obox("papier", 15.76, py0 + 0.255, 10.5, 0.08, 0.05, 0.14, 0, (0.9, 0.88, 0.82))          # boîte de médicaments
    house.parts["pharmacie"] = hinged(house, 1, (px0 - 0.012, pz0), 0.5, 0.7, 0.02, (0, 1), (-1, 0), "email", white, y0=py0)
    point(house, "pharmacie", (15.5, y0 + 1.6, 10.4), "Ouvrir l'armoire à pharmacie", 1, radius=1.0)
    A["eau_baignoire"] = Vec3(14.0, y0 + 0.6, 11.3)
    A["miroir1"] = Vec3(15.85, y0 + 1.55, 8.0)

    # ---------------- Palier -------------------------------------------
    rb.table(b, 11.4, 11.4, y0, 0.8, 0.4, 0.8)
    b.obox("papier", 11.4, y0 + 0.8, 11.4, 0.2, 0.04, 0.16, 0, (0.8, 0.78, 0.7))


# ---------------------------------------------------------------------------
# Grenier
# ---------------------------------------------------------------------------
def _grenier(house, rng):
    b = house.b(2)
    y0 = LEVEL_Y[2]
    A = house.anchors
    # cartons empilés
    for (cx, cz, s) in ((4.0, 11.2, 0.6), (4.7, 11.3, 0.55), (3.3, 11.3, 0.5), (4.3, 10.6, 0.6), (4.35, 10.65, 0.5),
                        (13.6, 10.9, 0.6), (14.4, 10.6, 0.55), (13.9, 10.0, 0.5), (1.2, 2.0, 0.6), (1.2, 2.7, 0.55),
                        (6.5, 1.3, 0.55), (7.2, 1.2, 0.6)):
        rb.carton(b, cx, cz, y0, s, rng.uniform(-15, 15))
    rb.carton(b, 4.3, 10.6, y0 + 0.5, 0.45, 8)
    # meubles couverts
    rb.covered_furniture(b, 11.0, 2.2, y0, 1.6, 0.8, 1.0)
    rb.covered_furniture(b, 2.5, 6.2, y0, 0.9, 0.9, 1.4)
    rb.covered_furniture(b, 13.5, 6.5, y0, 1.2, 0.7, 0.8)
    rb.covered_furniture(b, 7.2, 10.8, y0, 1.0, 1.0, 1.1)
    # mannequin de couture
    rb.mannequin(b, 1.6, 10.6, y0, 30)
    house.anchors["mannequin"] = Vec3(1.6, y0 + 1.0, 10.6)
    # pied de biche derrière les cartons
    b.obox("metal", 4.1, y0, 11.55, 0.04, 0.6, 0.04, 20, (0.3, 0.3, 0.32))
    b.obox("metal", 4.1, y0 + 0.5, 11.5, 0.04, 0.05, 0.25, 20, (0.3, 0.3, 0.32))
    point(house, "pied_de_biche", (4.1, y0 + 0.5, 11.5), "Ramasser le pied de biche", 2, radius=1.0)
    # poste de radio
    b.box("bois_meuble", 13.0, y0, 1.7, 14.0, y0 + 0.8, 2.3, (0.6, 0.55, 0.5), collide=True)
    b.box("bois_meuble", 13.2, y0 + 0.8, 1.8, 13.8, y0 + 1.1, 2.2, (0.45, 0.35, 0.28))
    b.box("metal", 13.25, y0 + 0.83, 2.18, 13.75, y0 + 1.07, 2.21, (0.15, 0.15, 0.15))
    A["radio"] = Vec3(13.5, y0 + 0.95, 2.0)
    point(house, "radio", (13.5, y0 + 1.0, 2.0), "Allumer la radio", 2, radius=1.0)
    # tube de plan
    b.obox("papier", 8.0, y0 + 0.62, 9.0, 0.08, 0.08, 0.8, 30, (0.7, 0.62, 0.5))
    rb.table(b, 8.0, 9.0, y0, 1.0, 0.7, 0.6)
    point(house, "plan", (8.0, y0 + 0.8, 9.0), "Examiner le tube", 2, radius=1.0)
    # polaroïds au sol
    for k in range(5):
        b.obox("papier", 5.2 + rng.uniform(-0.5, 0.6), y0 + 0.012 + k * 0.001, 4.6 + rng.uniform(-0.5, 0.6), 0.14, 0.004, 0.17,
               rng.uniform(0, 180), (0.95, 0.95, 0.9))
    point(house, "polaroids", (5.3, y0 + 0.1, 4.6), "Ramasser les Polaroïds", 2, radius=1.0)
    # pile (batterie) dans une caisse
    rb.crate(b, 14.8, 4.2, y0, 0.5)
    point(house, "pile_grenier", (14.8, y0 + 0.5, 4.2), "Fouiller la caisse", 2, radius=0.9)
    # lucarne : point de vue
    point(house, "lucarne", (8.0, y0 + 1.5, 0.6), "Regarder dehors", 2, radius=1.0)
    A["lucarne"] = Vec3(8.0, y0 + 1.5, 0.1)
    # silhouette figée (photo)
    hidden_entity(house, 2, "silhouette", (14.7, y0 + 0.9, 8.4), (0.9, 1.7), rot_y=0, name="grenier_entite")
    # trappe : hall d'accès (décor)
    b.box("planches", 3.0, y0, 0.2, 4.6, y0 + 0.05, 1.0, (0.7, 0.65, 0.6))


# ---------------------------------------------------------------------------
# Sous-sol
# ---------------------------------------------------------------------------
def _sous_sol(house, rng):
    b = house.b(-1)
    y0 = LEVEL_Y[-1]
    A = house.anchors
    cx, cz = 7.0, 20.2
    # cercle sombre autour du congélateur
    rb.floor_decal(b, "cercle_sombre", cx, y0, cz, 5.0, 5.0, 0.0, (1, 1, 1))
    rb.freezer(b, cx, cz, y0)
    house.parts["congelateur_couvercle"] = hinged(house, -1, (cx - 0.9, cz - 0.45), 1.8, 0.06, 0.9, (1, 0), (0, 0), "email", (0.95, 0.95, 0.95), y0=y0 + 0.82)
    # le couvercle est une boîte plate articulée (axe horizontal) : on le remplace par une pièce simple
    lid = house.parts["congelateur_couvercle"]
    lid.pivot.enabled = False
    lid_root = Entity(parent=house.level_roots[-1], position=(cx - 0.9, y0 + 0.82, cz))
    lid_b = MeshBuilder("lid")
    lid_b.box("email", 0, 0, -0.45, 1.8, 0.07, 0.45, (0.95, 0.95, 0.95))
    lid_b.build(parent=lid_root)
    house.parts["congelateur_lid"] = lid_root
    A["congelateur"] = Vec3(cx, y0 + 0.9, cz)
    point(house, "congelateur", (cx, y0 + 0.9, cz - 0.6), "Ouvrir le congélateur", -1, radius=1.3)
    # téléphone au fond du congélateur
    house.parts["tel_fond"] = make_part(house.level_roots[-1], "metal", (0.08, 0.015, 0.16), (cx, y0 + 0.2, cz), (0.1, 0.1, 0.12))
    house.parts["tel_fond"].enabled = False
    # vieux tonneaux dans les angles (loin de l'escalier, x 6.1-7.9)
    for (bx, bz, br) in ((3.6, 16.8, 0), (10.4, 16.8, 40), (10.35, 17.55, 75)):
        if b.model("Barrel_01", bx, bz, y0, br, (None, 0.9, None)):
            b.colliders.append((bx - 0.32, y0, bz - 0.32, bx + 0.32, y0 + 0.9, bz + 0.32))
    # bougies
    house.candle_pos = []
    for k in range(6):
        a = math.radians(30 + k * 60)
        px, pz = cx + math.cos(a) * 2.0, cz + math.sin(a) * 2.0
        rb.candle(b, px, pz, y0)
        house.candle_pos.append(Vec3(px, y0 + 0.28, pz))
    # étagères avec sacs de livraison déchirés
    for k in range(3):
        sx = 3.4 + k * 2.45
        rb.shelving_unit(b, sx, 23.2, sx + 2.1, 23.8, y0, levels=4, height=1.9)
        for lv in range(4):
            for j in range(4):
                rb.delivery_bag(b, sx + 0.35 + j * 0.45, 23.5, y0 + 0.18 + lv * 0.43, rng.uniform(-8, 8), torn=True)
    # taches sur les murs
    rb.wall_decal(b, "taches", 5.0, 1.2 + y0, 16.35, 3.0, 2.0, "+z", off=0.0, col=(1, 1, 1))
    rb.wall_decal(b, "taches", 10.8, 1.2 + y0, 20.0, 4.0, 2.0, "-x", off=0.0)
    rb.wall_decal(b, "taches", 3.2, 1.2 + y0, 19.0, 3.0, 2.0, "+x", off=0.0)
    rb.wall_decal(b, "griffures", 3.2, 0.9 + y0, 21.5, 1.6, 1.5, "+x", off=0.01)
    # tuyaux au plafond
    for k in range(3):
        b.box("metal", 3.2, y0 + 2.05, 17.0 + k * 2.5, 10.8, y0 + 2.2, 17.1 + k * 2.5, (0.4, 0.4, 0.42))
    house.anchors["basement_center"] = Vec3(cx, y0 + 1.0, cz)


def _lights(house):
    A = house.anchors
    neon = LightSource(A["neon_pos"], (0.85, 0.92, 1.0), 1.5, 7.0, kind="neon", name="neon1")
    house.lights.append(neon)
    A["neon_light"] = neon
    tv = LightSource((4.2, 1.0, 1.2), (0.7, 0.8, 1.0), 1.2, 5.0, kind="tv", enabled=False, name="tv")
    house.lights.append(tv)
    A["tv_light"] = tv
    house.candles = []
    for p in house.candle_pos:
        l = LightSource(p, (1.0, 0.6, 0.25), 1.1, 5.0, kind="candle", enabled=False, name="bougie")
        house.lights.append(l)
        house.candles.append(l)
    fridge = LightSource((5.2, 1.0, 10.9), (1.0, 0.95, 0.85), 0.9, 2.8, kind="static", enabled=False, name="frigo")
    house.lights.append(fridge)
    A["frigo_light"] = fridge
