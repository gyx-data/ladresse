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
    _ceiling_fixtures(house)
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
    # cadre photo au mur (mur est, entre l'angle et la porte)
    rb.painting(b, 5.9, 1.7, 1.2, 0.7, 0.5, "-x", tex="portrait")
    rb.painting(b, 3.1, 1.75, 5.9, 1.1, 0.72, "-z", tex="paysage")                          # marine au-dessus du canapé
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
    _fridge(b, y0)
    house.parts["frigo_porte"] = hinged(house, 0, (4.85, 11.17), 0.7, 1.75, 0.06, (1, 0), (0, -1), "email", (1, 1, 1))
    _fridge_door(house.parts["frigo_porte"])
    A["frigo"] = Vec3(5.2, 1.0, 11.0)
    point(house, "frigo", (5.2, 1.0, 11.0), "Ouvrir", 0, radius=0.9)
    # papier magnétique (adresse) : sur la face avant de la porte, il suit la porte quand on l'ouvre
    hidden_paper = text_paper("17 rue des Lilas\n06300 Nice", 256, 24, 11)
    ptex = textures.from_pil(hidden_paper)
    pe = Entity(parent=house.parts["frigo_porte"].pivot, model="quad", texture=ptex, shader=horror_shader,
                position=(0.5, 1.45, -0.036), scale=(0.2, 0.2))
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
    # quête « Rayé des favoris » : lignes de sel devant les entrées (activées une fois l'adresse supprimée)
    for (pid, pos) in (("sel_porte", (7.0, 0.3, 0.6)), ("sel_salon", (1.5, 0.3, 0.6)), ("sel_bureau", (15.35, 0.3, 2.2))):
        point(house, pid, pos, "Tracer une ligne de sel", 0, radius=0.9, enabled=False)
    # tiroirs
    house.parts["tiroir_cuisine"] = SlidingPart(house.level_roots[0], (0.45, 0.65, 10.2), (0.5, 0.18, 0.5), "bois_meuble", (0.7, 0.65, 0.6), travel=(0.35, 0, 0))
    point(house, "tiroirs", (0.7, 0.8, 10.2), "Ouvrir le tiroir", 0, radius=0.9)
    # griffures sur le sol
    rb.floor_decal(b, "taches", 2.0, y0, 9.5, 2.2, 2.2, 15, (0.6, 0.6, 0.6))
    A["frigo_hum"] = Vec3(5.2, 1.0, 11.5)
    A["frigo_mouches"] = Vec3(5.2, 0.95, 11.3)

    # ---------------- Bureau -------------------------------------------
    rb.table(b, 12.0, 3.6, y0, 1.6, 0.75, 0.75)
    rb.chair(b, 12.0, 2.9, y0, 0)
    _filing_cabinet(b, 15.2, 15.9, 2.5, 3.5, y0)
    point(house, "recus", (15.1, 0.9, 3.0), "Fouiller le classeur", 0, radius=0.9)
    rb.bookshelf(b, 9.0, 4.15, 11.0, 4.4, y0, 2.0, rng, face="-z")
    b.obox("papier", 12.0, y0 + 0.75, 3.6, 0.5, 0.04, 0.35, 5, (0.9, 0.9, 0.85))
    b.cyl("metal", 12.6, y0 + 0.75, 3.7, 0.05, 0.03, 8, (0.3, 0.3, 0.3))
    point(house, "pile_bureau", (12.6, 0.85, 3.7), "Prendre la pile", 0, radius=0.8)
    rb.carton(b, 15.2, 0.9, y0, 0.5)
    rb.carton(b, 14.6, 0.9, y0, 0.4, 20)

    # ---------------- Cage d'escalier ----------------------------------
    rb.table(b, 11.4, 11.4, y0, 0.9, 0.4, 0.8)
    _dead_flowers(b, 11.4, 11.4, y0 + 0.8)
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
    # étagère de 2 m : tablettes tous les 45 cm (la 2e, à 0,60-0,63, porte le sac de 40 cm sans qu'il traverse
    # la tablette du dessus ; l'ancienne planche ajoutée en double à cette hauteur s'interpénétrait avec elle)
    rb.shelving_unit(b, 12.2, 11.2, 14.0, 11.8, y0, height=2.0)
    rb.delivery_bag(b, 13.0, 11.5, y0 + 0.632, 0, torn=False)
    point(house, "sac_propre", (13.0, 1.0, 11.2), "Examiner le sac", 0, radius=0.9)
    rb.crate(b, 12.7, 9.3, y0)
    rb.crate(b, 13.3, 9.2, y0, 0.4, 25)
    _ironing_board(b, 15.9, 9.55, y0)


def _filing_cabinet(b, x0, x1, z0, z1, y0, h=1.3):
    """Classeur métallique vert administration (façade vers -x) : trois tiroirs en relief, poignées,
    porte-étiquettes, serrure, tôle cabossée."""
    olive, dark = (0.42, 0.48, 0.42), (0.2, 0.22, 0.2)
    b.box("metal", x0 + 0.02, y0 + 0.04, z0, x1, y0 + h, z1, olive, collide=True)
    b.box("metal", x0, y0, z0 + 0.02, x1, y0 + 0.05, z1 - 0.02, dark)                       # socle
    b.box("metal", x0 + 0.01, y0 + h - 0.015, z0 - 0.005, x1 + 0.005, y0 + h, z1 + 0.005, (0.38, 0.44, 0.38))
    dh = (h - 0.1) / 3
    for k in range(3):
        ya, yb = y0 + 0.07 + k * dh, y0 + 0.07 + (k + 1) * dh - 0.02
        out = 0.012 if k != 1 else 0.05                                                     # tiroir du milieu entrouvert
        b.box("metal", x0 - out, ya, z0 + 0.03, x0 + 0.02, yb, z1 - 0.03, (0.45, 0.51, 0.45))
        b.box("metal", x0 - out - 0.004, ya + dh * 0.62, z0 + 0.4, x0 - out, ya + dh * 0.62 + 0.07, z1 - 0.4,
              (0.7, 0.68, 0.6))                                                              # porte-étiquette
        b.box("papier", x0 - out - 0.006, ya + dh * 0.62 + 0.012, z0 + 0.42, x0 - out - 0.004, ya + dh * 0.62 + 0.058,
              z1 - 0.42, (0.9, 0.86, 0.74))
        hy = ya + dh * 0.42
        rb.rod(b, "metal", (x0 - out - 0.035, hy, z0 + 0.38), (x0 - out - 0.035, hy, z1 - 0.38), 0.008, col=(0.78, 0.78, 0.8))
        for zz in (z0 + 0.38, z1 - 0.38):
            rb.rod(b, "metal", (x0 - out, hy, zz), (x0 - out - 0.035, hy, zz), 0.007, col=(0.7, 0.7, 0.72))
        if k == 1:
            b.box("papier", x0 - out + 0.01, yb - 0.01, z0 + 0.1, x0 + 0.02, yb + 0.03, z1 - 0.12, (0.86, 0.82, 0.7))  # dossiers
    b.cyl("metal", x0 - 0.01, y0 + h - 0.12, z1 - 0.12, 0.015, 0.02, 10, (0.75, 0.7, 0.4))   # serrure
    b.sphere("metal", x0 + 0.005, y0 + 0.5, z0 + 0.15, 0.06, (0.36, 0.42, 0.36), lat=4, lon=8, sx=0.25)   # bosse


def _dead_flowers(b, cx, cz, y):
    """Vase en faïence et bouquet fané : tiges courbées, têtes tombantes, pétales sur la table."""
    rb.lathe(b, "email", cx, cz, y, [(0.0, 0.05, 0.05), (0.06, 0.075, 0.075), (0.16, 0.06, 0.06), (0.22, 0.035, 0.035),
                                     (0.25, 0.045, 0.045)], (0.72, 0.78, 0.82), n=2.0, seg=16)
    b.cap("email", rb._ring(cx, cz, y + 0.24, 0.035, 0.035, 0.0, 2.0, seg=16), (0, 1, 0), (0.2, 0.18, 0.12))
    for k in range(7):
        a = k * 2 * math.pi / 7 + 0.4
        lean = 0.06 + 0.05 * (k % 3)
        top = (cx + math.cos(a) * lean, y + 0.42 + 0.06 * (k % 2), cz + math.sin(a) * lean)
        droop = (top[0] + math.cos(a) * 0.07, top[1] - 0.09, top[2] + math.sin(a) * 0.07)
        rb.rod(b, "etoffe", (cx, y + 0.2, cz), top, 0.004, col=(0.3, 0.3, 0.16))
        rb.rod(b, "etoffe", top, droop, 0.0035, col=(0.32, 0.28, 0.15))
        b.sphere("etoffe", droop[0], droop[1] - 0.012, droop[2], 0.024, (0.36, 0.2, 0.17), lat=4, lon=7, sy=0.7)
    for k in range(6):
        a = k * 1.9
        b.obox("etoffe", cx + math.cos(a) * (0.12 + 0.03 * k), y + 0.002, cz + math.sin(a) * 0.1, 0.03, 0.002, 0.02, k * 37,
               (0.4, 0.22, 0.18))


def _crowbar(b, y0):
    """Pied de biche rouge appuyé contre les cartons : tige hexagonale, crosse recourbée, panne fendue."""
    red, steel = (0.55, 0.12, 0.1), (0.45, 0.45, 0.48)
    p0, p1 = (4.0, y0 + 0.02, 11.3), (4.12, y0 + 0.66, 11.58)
    rb.rod(b, "metal", p0, p1, 0.013, col=red, seg=6)
    prev = p1
    for k in range(1, 7):                                                    # crosse : demi-cercle vers -z
        a = math.pi * k / 6
        q = (4.12 + 0.01 * k, y0 + 0.66 + math.sin(a) * 0.07, 11.58 - (1 - math.cos(a)) * 0.07)
        rb.rod(b, "metal", prev, q, 0.013, col=red, seg=6)
        prev = q
    rb.rod(b, "metal", p0, (3.97, y0 + 0.01, 11.24), 0.011, 0.006, col=steel, seg=6)        # panne


def _dresser_radio(b, y0):
    """Commode à trois tiroirs et vieux poste de radio TSF en bois (façade vers +z) : toile de haut-parleur,
    cadran éclairé, boutons en bakélite."""
    wood, dark = (0.55, 0.45, 0.36), (0.32, 0.25, 0.2)
    b.box("bois_meuble", 13.02, y0 + 0.08, 1.7, 13.98, y0 + 0.78, 2.28, wood, collide=True)
    b.box("bois_meuble", 12.98, y0 + 0.78, 1.66, 14.02, y0 + 0.82, 2.32, dark)                 # plateau
    for k in range(3):
        ya = y0 + 0.12 + k * 0.22
        b.box("bois_meuble", 13.06, ya, 2.28, 13.94, ya + 0.19, 2.3, (0.6, 0.5, 0.4))
        for kx in (13.3, 13.7):
            b.sphere("metal", kx, ya + 0.1, 2.31, 0.016, (0.7, 0.58, 0.3), lat=4, lon=8)
    for fx in (13.06, 13.94):
        for fz in (1.74, 2.24):
            b.cyl("bois_meuble", fx, y0, fz, 0.03, 0.08, 8, dark)
    # poste : caisse au dessus arrondi
    rb.rounded_box(b, "bois_meuble", 13.5, 2.0, y0 + 0.82, 0.6, 0.36, 0.3, 0, (0.5, 0.33, 0.2), n=3.0, bevel=0.06)
    b.box("etoffe", 13.24, y0 + 0.9, 2.149, 13.62, y0 + 1.12, 2.152, (0.45, 0.36, 0.24))         # toile
    for k in range(5):
        xk = 13.27 + k * 0.08
        b.box("bois_meuble", xk, y0 + 0.9, 2.152, xk + 0.018, y0 + 1.12, 2.16, (0.4, 0.26, 0.16))  # lamelles
    b.box("neon", 13.65, y0 + 1.04, 2.149, 13.76, y0 + 1.11, 2.153, (0.55, 0.45, 0.25))           # cadran
    b.box("metal", 13.7, y0 + 1.045, 2.153, 13.703, y0 + 1.105, 2.156, (0.2, 0.1, 0.08))
    for kx in (13.67, 13.74):
        rb.rod(b, "metal", (kx, y0 + 0.95, 2.15), (kx, y0 + 0.95, 2.18), 0.022, col=(0.14, 0.11, 0.09), seg=10, caps=True)


def _plan_tube(b, cx, cz, y):
    """Tube à plans en carton couché sur la table, bouchons noirs."""
    a = math.radians(30)
    dx, dz = math.sin(a) * 0.4, math.cos(a) * 0.4
    p0, p1 = (cx - dx, y + 0.045, cz - dz), (cx + dx, y + 0.045, cz + dz)
    rb.rod(b, "papier", p0, p1, 0.04, col=(0.68, 0.58, 0.44), seg=14)
    for (p, s) in ((p0, -1), (p1, 1)):
        rb.rod(b, "metal", p, (p[0] + s * math.sin(a) * 0.03, p[1], p[2] + s * math.cos(a) * 0.03), 0.043,
               col=(0.08, 0.08, 0.09), seg=14, caps=True)


def _basement_pipes(b, y0):
    """Tuyauterie au plafond du sous-sol : conduites rondes en fonte, colliers de fixation, coudes."""
    for k in range(3):
        z = 17.05 + k * 2.5
        r = 0.06 if k != 1 else 0.045
        col = (0.36, 0.33, 0.3) if k != 1 else (0.5, 0.36, 0.26)
        rb.rod(b, "metal", (3.2, y0 + 2.12, z), (10.8, y0 + 2.12, z), r, col=col, seg=12, caps=True)
        for xb in (3.8, 5.6, 7.4, 9.2, 10.4):
            rb.rod(b, "metal", (xb, y0 + 2.12 - r - 0.01, z), (xb, y0 + 3.0, z), 0.008, col=(0.25, 0.25, 0.26))     # tige jusqu'au plafond
            rb.rod(b, "metal", (xb - 0.02, y0 + 2.12, z), (xb + 0.02, y0 + 2.12, z), r + 0.012, col=(0.28, 0.28, 0.3), seg=12,
                   caps=True)
        rb.rod(b, "metal", (3.2, y0 + 2.12, z), (3.2, y0 + 3.0, z), r, col=col, seg=12)              # remonte dans le plafond


def _pillow(b, cx, y, cz, w, d, h, col, yaw=0.0):
    """Oreiller gonflé : bords fins et pincés, milieu bombé (largeur w le long de z, profondeur d le long de x)."""
    rings = []
    for (fy, fw) in ((0.0, 0.93), (0.12, 0.99), (0.3, 1.0), (0.55, 0.94), (0.78, 0.78), (0.93, 0.52), (1.0, 0.18)):
        rings.append(rb._ring(cx, cz, y + h * fy, d / 2 * fw, w / 2 * fw, yaw, 3.2, seg=24))
    b.loft("drap", rings, col)
    b.cap("drap", rings[-1], (0, 1, 0), col)
    b.cap("drap", rings[0], (0, -1, 0), col)


def _sheet_lump(b, y, cz):
    """Drap tendu sur une forme allongée (tête vers la tête de lit en x bas) : sections en demi-ellipse."""
    prof = [(0.82, 0.02, 0.05), (0.9, 0.1, 0.12), (1.02, 0.13, 0.15), (1.12, 0.09, 0.12), (1.25, 0.16, 0.27),
            (1.45, 0.17, 0.27), (1.65, 0.15, 0.24), (1.85, 0.12, 0.22), (2.05, 0.09, 0.2), (2.2, 0.08, 0.17),
            (2.3, 0.03, 0.08)]
    rings = []
    for (x, hgt, wid) in prof:
        ring = []
        for k in range(17):
            a = math.pi * k / 16
            ring.append((x, y + 0.01 + hgt * math.sin(a) ** 0.8, cz + (wid + 0.06) * math.cos(a)))
        ring.append((x, y + 0.005, cz - wid * 0.6))
        ring.append((x, y + 0.005, cz + wid * 0.6))
        rings.append(ring)
    b.loft("drap", rings, (0.9, 0.87, 0.82))


def _uniform(b, cx, cz, y0):
    """Uniforme de gardien de nuit sur un cintre en bois accroché à la tringle : veste bleu nuit, écusson,
    bande nominative « R. GARNIER », casquette posée sur l'étagère."""
    navy = (0.14, 0.16, 0.24)
    ty = y0 + 1.66
    rb.rod(b, "metal", (cx, ty + 0.015, cz), (cx, ty - 0.06, cz), 0.004, col=(0.7, 0.7, 0.72))       # crochet
    rb.rod(b, "bois_meuble", (cx - 0.21, ty - 0.13, cz), (cx, ty - 0.06, cz), 0.011, col=(0.62, 0.48, 0.32))
    rb.rod(b, "bois_meuble", (cx + 0.21, ty - 0.13, cz), (cx, ty - 0.06, cz), 0.011, col=(0.62, 0.48, 0.32))
    body = [(1.535, 0.05, 0.035), (1.505, 0.15, 0.06), (1.47, 0.21, 0.085), (1.36, 0.215, 0.1), (1.1, 0.2, 0.1),
            (0.95, 0.205, 0.095), (0.88, 0.21, 0.09)]
    rb.lathe(b, "etoffe", cx, cz, y0, body, navy, n=2.4, seg=18)
    b.cap("etoffe", rb._ring(cx, cz, y0 + 0.88, 0.21, 0.09, 0.0, 2.4, seg=18), (0, -1, 0), (0.05, 0.05, 0.07))
    for sx in (-1, 1):
        rb.lathe(b, "etoffe", cx, cz + 0.01, y0, [(1.46, 0.055, 0.06, sx * 0.2), (1.2, 0.05, 0.055, sx * 0.215),
                                                  (0.98, 0.05, 0.05, sx * 0.22)], (0.12, 0.14, 0.21), n=2.0, seg=10)
    zf = cz + 0.101
    b.box("metal", cx - 0.004, y0 + 0.92, zf, cx + 0.004, y0 + 1.48, zf + 0.004, (0.75, 0.68, 0.4))  # boutonnage
    b.box("etoffe", cx - 0.17, y0 + 1.3, zf - 0.004, cx - 0.06, y0 + 1.42, zf + 0.004, (0.72, 0.6, 0.25))  # écusson
    b.box("papier", cx + 0.05, y0 + 1.36, zf - 0.004, cx + 0.18, y0 + 1.395, zf + 0.004, (0.92, 0.9, 0.84))  # nom
    rb.lathe(b, "etoffe", cx + 0.55, cz - 0.02, y0 + 1.805, [(0.0, 0.11, 0.12), (0.06, 0.105, 0.115), (0.09, 0.07, 0.08)],
             navy, n=2.0, seg=16)                                                             # casquette
    b.obox("etoffe", cx + 0.55, y0 + 1.805, cz + 0.12, 0.17, 0.012, 0.09, 0, (0.06, 0.06, 0.08))   # visière


class _Drawer:
    """Tiroir qui coulisse hors de son caisson (racine animée, contenu en enfant)."""

    def __init__(self, root, travel):
        self.root = root
        self.closed = Vec3(*root.position)
        self.travel = Vec3(*travel)
        self.is_open = False

    def set_open(self, state, duration=0.4):
        self.is_open = state
        self.root.animate_position(self.closed + (self.travel if state else Vec3(0, 0, 0)), duration=duration)


def _desk_drawer(house, b, cx, zf, y):
    """Caisson sous le plateau du bureau (façade en z = zf, vers -z) et tiroir creux qui en sort de 30 cm."""
    w, h, d = 0.56, 0.15, 0.42
    wood, dark = (0.62, 0.52, 0.42), (0.36, 0.3, 0.25)
    b.box("bois_meuble", cx - w / 2 - 0.02, y - 0.02, zf, cx + w / 2 + 0.02, y, zf + d + 0.02, dark)       # caisson
    b.box("bois_meuble", cx - w / 2 - 0.02, y, zf, cx - w / 2, y + h + 0.03, zf + d + 0.02, dark)
    b.box("bois_meuble", cx + w / 2, y, zf, cx + w / 2 + 0.02, y + h + 0.03, zf + d + 0.02, dark)
    b.box("bois_meuble", cx - w / 2, y, zf + d, cx + w / 2, y + h + 0.03, zf + d + 0.02, dark)
    root = Entity(parent=house.level_roots[1], position=(cx, y, zf))
    db = MeshBuilder("tiroir")
    db.box("bois_meuble", -w / 2 - 0.015, -0.005, -0.022, w / 2 + 0.015, h + 0.01, 0.0, wood)              # façade
    db.box("bois_meuble", -w / 2 + 0.01, 0.0, 0.0, w / 2 - 0.01, 0.012, d - 0.02, dark)                   # fond
    for sx in (-1, 1):
        db.box("bois_meuble", sx * (w / 2 - 0.01) - 0.006, 0.0, 0.0, sx * (w / 2 - 0.01) + 0.006, h - 0.02, d - 0.02, wood)
    db.box("bois_meuble", -w / 2 + 0.01, 0.0, d - 0.032, w / 2 - 0.01, h - 0.02, d - 0.02, wood)
    db.sphere("metal", 0.0, h / 2, -0.04, 0.018, (0.7, 0.58, 0.3), lat=4, lon=8, sy=0.8)                  # bouton
    db.box("metal", -0.03, h / 2 + 0.03, -0.025, 0.03, h / 2 + 0.05, -0.021, (0.25, 0.22, 0.18))         # serrure
    for e in db.build(parent=root):
        pass
    return _Drawer(root, (0, 0, -0.3))


def _toy_chest(b, cx, cz, y0):
    """Coffre à jouets en bois peint bleu pâle, couvercle légèrement entrouvert, hochet posé dessus, ourson à côté."""
    paint = (0.55, 0.66, 0.74)
    b.obox("bois_meuble", cx, y0, cz, 0.85, 0.46, 0.5, 0, paint, collide=True)
    b.obox("bois_meuble", cx, y0 + 0.46, cz - 0.01, 0.89, 0.05, 0.54, -4, (0.5, 0.6, 0.68))
    b.obox("bois_meuble", cx, y0 + 0.18, cz - 0.255, 0.7, 0.03, 0.01, 0, (0.85, 0.75, 0.4))   # liseré peint
    top = y0 + 0.51
    hx, hz = cx - 0.15, cz - 0.05
    b.sphere("email", hx + 0.07, top + 0.04, hz, 0.04, (0.92, 0.7, 0.72), lat=6, lon=10)        # hochet : boule
    rb.rod(b, "email", (hx + 0.04, top + 0.015, hz), (hx - 0.08, top + 0.012, hz + 0.02), 0.009, col=(0.95, 0.94, 0.9))
    rb.rod(b, "email", (hx - 0.08, top + 0.012, hz + 0.02), (hx - 0.11, top + 0.013, hz + 0.035), 0.016, col=(0.95, 0.85, 0.5))
    bx, bz = cx + 0.62, cz + 0.02                                                                # ourson
    b.sphere("etoffe", bx, y0 + 0.13, bz, 0.12, (0.52, 0.38, 0.26), lat=6, lon=10, sy=1.1)
    b.sphere("etoffe", bx, y0 + 0.33, bz - 0.01, 0.085, (0.55, 0.4, 0.28), lat=6, lon=10)
    for sx in (-1, 1):
        b.sphere("etoffe", bx + sx * 0.06, y0 + 0.4, bz, 0.03, (0.5, 0.36, 0.24), lat=4, lon=8)
        b.sphere("etoffe", bx + sx * 0.1, y0 + 0.05, bz - 0.06, 0.045, (0.5, 0.36, 0.24), lat=4, lon=8)
    b.sphere("email", bx - 0.03, y0 + 0.345, bz - 0.085, 0.008, (0.05, 0.05, 0.05), lat=3, lon=6)
    b.sphere("email", bx + 0.03, y0 + 0.345, bz - 0.085, 0.008, (0.05, 0.05, 0.05), lat=3, lon=6)


def _brooms(b, y0):
    """Placard : balai et serpillière appuyés au mur du fond, seau en zinc."""
    rb.rod(b, "bois_meuble", (4.55, y0 + 0.12, 11.78), (4.63, y0 + 1.35, 11.9), 0.014, col=(0.7, 0.55, 0.38))
    b.obox("bois_meuble", 4.55, y0, 11.76, 0.32, 0.05, 0.07, 0, (0.45, 0.32, 0.2))
    b.obox("etoffe", 4.55, y0, 11.76, 0.3, 0.035, 0.065, 0, (0.55, 0.45, 0.25))
    rb.rod(b, "bois_meuble", (4.2, y0 + 0.25, 11.62), (4.3, y0 + 1.3, 11.88), 0.013, col=(0.66, 0.6, 0.5))
    rb.lathe(b, "metal", 4.18, 11.6, y0, [(0.0, 0.12, 0.12), (0.28, 0.15, 0.15), (0.285, 0.155, 0.155)], (0.6, 0.62, 0.62),
             n=2.0, seg=16)
    rb.lathe(b, "etoffe", 4.18, 11.6, y0 + 0.24, [(0.0, 0.1, 0.1), (0.06, 0.06, 0.06)], (0.6, 0.58, 0.5), n=2.0, seg=10)
    b.colliders.append((3.95, y0, 11.4, 4.75, y0 + 0.4, 11.95))


def _fridge(b, y0, x0=4.85, x1=5.55, z0=11.2, z1=11.9, h=1.75):
    """Réfrigérateur années 60 creux (façade vers -z) : caisse émaillée, clayettes, bac à légumes, freezer givré,
    et tout ce qui pourrit dedans depuis des semaines."""
    cream, liner = (0.97, 0.96, 0.9), (0.86, 0.87, 0.84)
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    t = 0.04
    b.box("email", x0, y0 + 0.06, z0, x0 + t, y0 + h - 0.09, z1, cream)                     # flancs
    b.box("email", x1 - t, y0 + 0.06, z0, x1, y0 + h - 0.09, z1, cream)
    b.box("email", x0, y0 + 0.06, z1 - t, x1, y0 + h - 0.09, z1, liner)                     # fond
    b.box("email", x0, y0 + 0.06, z0, x1, y0 + 0.16, z1, liner)                             # plancher
    rb.rounded_box(b, "email", cx, cz, y0 + h - 0.12, x1 - x0, 0.12, z1 - z0, 180, cream, n=8.0, bevel=0.05)
    b.box("email", x0 + t, y0 + h - 0.13, z0 + 0.01, x1 - t, y0 + h - 0.09, z1 - t, liner)  # plafond intérieur
    for sx in (x0 + 0.06, x1 - 0.06):
        for sz in (z0 + 0.06, z1 - 0.06):
            b.cyl("metal", sx, y0, sz, 0.025, 0.06, 8, (0.3, 0.3, 0.32))
    b.box("metal", x0 + 0.05, y0 + 0.07, z0 - 0.003, x1 - 0.05, y0 + 0.13, z0, (0.25, 0.25, 0.27))   # grille
    # freezer givré en haut, clayettes grillagées, bac à légumes
    b.box("metal", x0 + t, y0 + 1.36, z0 + 0.06, x1 - t, y0 + 1.6, z1 - t, (0.82, 0.88, 0.93))
    b.box("metal", x0 + t + 0.02, y0 + 1.37, z0 + 0.05, x1 - t - 0.02, y0 + 1.59, z0 + 0.06, (0.7, 0.74, 0.78))
    for ys in (0.56, 0.96, 1.3):
        b.box("metal", x0 + t, y0 + ys, z0 + 0.04, x1 - t, y0 + ys + 0.012, z1 - t, (0.78, 0.78, 0.8))
        b.box("metal", x0 + t, y0 + ys + 0.012, z0 + 0.04, x1 - t, y0 + ys + 0.03, z0 + 0.05, (0.7, 0.7, 0.72))
    b.box("email", x0 + t + 0.01, y0 + 0.16, z0 + 0.05, x1 - t - 0.01, y0 + 0.38, z0 + 0.065, (0.55, 0.68, 0.72))   # bac
    mold, mold2 = (0.6, 0.68, 0.42), (0.86, 0.88, 0.8)

    def fuzz(x, y, z, r, n=4, seed=0):
        for k in range(n):
            a = seed * 1.7 + k * 2.1
            b.sphere("etoffe", x + math.cos(a) * r * 0.9, y, z + math.sin(a) * r * 0.9, r * (0.5 + 0.2 * (k % 2)),
                     mold if k % 2 else mold2, lat=3, lon=6, sy=0.45)
    # bac : salade noircie et carottes ramollies
    for (lx, lz) in ((5.0, 11.45), (5.12, 11.6), (4.98, 11.68)):
        b.sphere("etoffe", lx, y0 + 0.23, lz, 0.075, (0.3, 0.32, 0.12), lat=4, lon=7, sy=0.7)
    for k in range(3):
        b.obox("etoffe", 5.33 + k * 0.04, y0 + 0.17, 11.55, 0.025, 0.025, 0.2, 10 + k * 12, (0.62, 0.36, 0.16))
    # 1re clayette : l'assiette moisie (avec la note), une carcasse de poulet
    y1 = y0 + 0.572
    b.cyl("email", 5.05, y1, 11.45, 0.15, 0.015, 16, (0.92, 0.92, 0.9))
    b.sphere("etoffe", 5.05, y1 + 0.03, 11.45, 0.1, (0.42, 0.44, 0.26), lat=4, lon=8, sy=0.35)
    fuzz(5.05, y1 + 0.05, 11.45, 0.06, 5, 1)
    b.obox("papier", 5.08, y1 + 0.065, 11.4, 0.2, 0.004, 0.14, 20, (0.85, 0.83, 0.74))      # la note
    b.sphere("etoffe", 5.36, y1 + 0.06, 11.6, 0.09, (0.62, 0.55, 0.36), lat=5, lon=9, sy=0.7)
    fuzz(5.36, y1 + 0.11, 11.6, 0.05, 4, 2)
    # 2e clayette : bocaux couverts de moisissure, fromage, brique de lait gonflée
    y2 = y0 + 0.972
    for k, (jx, col) in enumerate(((4.98, (0.45, 0.16, 0.12)), (5.1, (0.5, 0.42, 0.18)))):
        b.cyl("email", jx, y2, 11.7, 0.045, 0.12, 12, col)
        b.cyl("metal", jx, y2 + 0.12, 11.7, 0.047, 0.02, 12, (0.7, 0.62, 0.3))
        fuzz(jx, y2 + 0.145, 11.7, 0.03, 3, 3 + k)
    b.obox("etoffe", 5.3, y2, 11.45, 0.16, 0.07, 0.1, 25, (0.86, 0.76, 0.38))
    fuzz(5.3, y2 + 0.075, 11.45, 0.04, 4, 5)
    b.obox("papier", 5.42, y2, 11.68, 0.085, 0.21, 0.085, -8, (0.92, 0.94, 0.98))
    b.obox("papier", 5.42, y2 + 0.07, 11.68, 0.092, 0.08, 0.092, -8, (0.3, 0.45, 0.75))     # bandeau, carton gonflé
    # 3e clayette : boîte d'œufs, boîte en plastique au contenu verdâtre
    y3 = y0 + 1.312
    b.obox("papier", 5.05, y3, 11.55, 0.26, 0.055, 0.11, 0, (0.62, 0.6, 0.55))
    for k in range(4):
        b.sphere("email", 4.95 + k * 0.065, y3 + 0.06, 11.55, 0.022, (0.86, 0.8, 0.7), lat=4, lon=6, sy=1.25)
    b.obox("email", 5.36, y3, 11.6, 0.18, 0.025, 0.14, 0, (0.55, 0.62, 0.38))
    b.obox("email", 5.36, y3 + 0.025, 11.6, 0.19, 0.012, 0.15, 0, (0.75, 0.8, 0.85))
    b.colliders.append((x0, y0, z0, x1, y0 + h, z1))


def _fridge_door(part):
    """Contre-porte du frigo (balconnets, bouteilles) et poignée chromée, attachées au battant."""
    b = MeshBuilder("frigo_porte")
    w = 0.7
    b.box("email", 0.04, 0.12, 0.03, w - 0.04, 1.63, 0.05, (0.86, 0.87, 0.84))               # contre-porte
    for yb in (0.45, 0.95, 1.38):
        b.box("email", 0.06, yb, 0.05, w - 0.06, yb + 0.012, 0.13, (0.88, 0.88, 0.86))
        b.box("email", 0.06, yb, 0.12, w - 0.06, yb + 0.07, 0.13, (0.8, 0.82, 0.8))
    for (bx, by, r, hh, col) in ((0.14, 0.462, 0.03, 0.26, (0.18, 0.3, 0.16)), (0.26, 0.462, 0.028, 0.2, (0.62, 0.1, 0.08)),
                                 (0.4, 0.962, 0.035, 0.22, (0.9, 0.9, 0.86)), (0.54, 0.962, 0.025, 0.14, (0.5, 0.3, 0.12))):
        b.cyl("email", bx, by, 0.09, r, hh, 10, col)
        b.cyl("metal", bx, by + hh, 0.09, r * 0.45, 0.04, 8, (0.3, 0.3, 0.3))
    for (y_a, y_b) in ((0.75, 0.8), (1.25, 1.3)):                                           # poignée
        b.box("metal", w - 0.1, y_a, -0.07, w - 0.07, y_b, -0.03, (0.8, 0.8, 0.82))
    b.box("metal", w - 0.1, 0.78, -0.08, w - 0.07, 1.27, -0.06, (0.85, 0.85, 0.88))
    b.sphere("email", 0.5, 1.565, -0.045, 0.014, (0.75, 0.12, 0.1), lat=3, lon=6, sy=0.6)     # aimant
    for e in b.build(parent=part.pivot):
        pass


def _ironing_board(b, wall_x, cz, y0, length=1.22, lean=13.0):
    """Planche à repasser repliée, adossée au mur est (x = wall_x) : plateau en goutte housse grise, pieds repliés."""
    a = math.radians(lean)
    up, out = (math.sin(a), math.cos(a)), (-math.cos(a), math.sin(a))      # (x, y) : le long du plateau / vers la pièce
    bx = wall_x - 0.035 - length * math.sin(a)                                 # pied du plateau, le haut touche le mur

    def p(u, v, w):
        return (bx + u * up[0] + w * out[0], y0 + 0.03 + u * up[1] + w * out[1], cz + v)

    def hw(u):                                         # demi-largeur : talon arrondi en bas, nez pointu en haut
        t = u / length
        if t < 0.08:
            return 0.17 * math.sqrt(max(0.0, 1 - ((0.08 - t) / 0.08) ** 2))
        if t > 0.62:
            return 0.17 * math.sqrt(max(0.0, 1 - ((t - 0.62) / 0.38) ** 2)) ** 1.25
        return 0.17
    us = [length * k / 23 for k in range(24)]
    outline = [(u, hw(u)) for u in us] + [(u, -hw(u)) for u in reversed(us)]
    outline = [q for i, q in enumerate(outline) if q != outline[i - 1]]          # sans doublons (pointes, bouclage)
    for (w0, w1, tex, col) in ((0.0, 0.008, "metal", (0.75, 0.75, 0.77)), (0.008, 0.03, "etoffe", (0.5, 0.56, 0.66))):
        b.loft(tex, [[p(u, v, w0) for (u, v) in outline], [p(u, v, w1) for (u, v) in outline]], col)
    b.cap("etoffe", [p(u, v, 0.03) for (u, v) in outline], (out[0], out[1], 0.0), (0.5, 0.56, 0.66))
    # pieds repliés derrière le plateau (tubes chromés), dépassant un peu sous le talon
    for v in (-0.12, 0.12):
        b.loft("metal", [[p(u, v + 0.012 * math.cos(2 * math.pi * k / 8), -0.016 + 0.012 * math.sin(2 * math.pi * k / 8))
                          for k in range(8)] for u in (-0.03, length * 0.9)], (0.78, 0.78, 0.8))
    b.colliders.append((bx - 0.08, y0, cz - 0.18, wall_x, y0 + 1.15, cz + 0.18))


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
    _brooms(b, y0)
    b.cyl("metal", 0.35, y0 + 0.93, 11.65, 0.05, 0.03, 8, (0.3, 0.3, 0.3))                    # pile posée sur l'étagère
    point(house, "pile_placard", (0.7, y0 + 1.0, 11.5), "Fouiller le placard", 1, radius=1.3)

    # ---------------- Chambre principale -------------------------------
    rb.bed(b, 1.35, 3.0, 90, y0)
    for pz in (2.62, 3.38):                                            # deux gros oreillers contre la tête de lit
        _pillow(b, 0.68, y0 + 0.5, pz, 0.62, 0.4, 0.16, (0.93, 0.91, 0.86), yaw=(pz - 3.0) * 6)
    # amas d'oreillers sous le drap, à la forme vaguement humaine (tête côté tête de lit, x bas)
    lump = Entity(parent=house.level_roots[1])
    lb = MeshBuilder("forme_lit")
    _sheet_lump(lb, y0 + 0.5, 3.0)
    for e in lb.build(parent=lump):
        pass
    house.parts["oreillers"] = lump
    point(house, "lit", (1.5, y0 + 0.7, 3.0), "Soulever les draps", 1, radius=1.1)
    point(house, "dessous_lit", (2.9, y0 + 0.2, 3.0), "Regarder sous le lit", 1, radius=0.9)
    rb.table(b, 0.45, 4.15, y0, 0.45, 0.45, 0.55)
    rb.table(b, 0.45, 1.85, y0, 0.45, 0.45, 0.55)
    b.obox("papier", 0.45, y0 + 0.55, 4.15, 0.18, 0.025, 0.24, 15, (0.25, 0.2, 0.15))       # carnet
    point(house, "carnet", (0.5, y0 + 0.6, 4.15), "Ouvrir le carnet", 1, radius=0.8)
    rb.wardrobe(b, 3.4, 0.15, 5.5, 0.75, y0, hollow=True)
    _uniform(b, 4.45, 0.45, y0)
    house.parts["armoire_g"] = hinged(house, 1, (3.4, 0.76), 1.05, 2.0, 0.04, (1, 0), (0, 1), "bois_meuble", (0.65, 0.6, 0.55))
    house.parts["armoire_d"] = hinged(house, 1, (5.5, 0.76), 1.05, 2.0, 0.04, (-1, 0), (0, 1), "bois_meuble", (0.65, 0.6, 0.55))
    point(house, "armoire", (4.45, y0 + 1.1, 1.2), "Ouvrir l'armoire", 1, radius=1.1)
    point(house, "volets_master", (2.0, y0 + 1.5, 0.5), "Ouvrir les volets", 1, radius=1.0)
    hidden_entity(house, 1, "papier", (3.0, y0 + 1.7, 5.88), (0.9, 0.6), rot_y=180, name="mur_message", col=(1.0, 0.9, 0.85))
    rb.painting(b, 5.9, y0 + 1.7, 1.3, 0.5, 0.65, "-x", tex="portrait")     # à côté de la porte (z 3)
    b.box("tissu", 1.0, y0, 0.9, 2.6, y0 + 0.02, 1.9, (0.4, 0.15, 0.12))                     # tapis

    # ---------------- Chambre d'amis ------------------------------------
    rb.bed(b, 1.2, 7.45, 90, y0, w=1.3, l=2.05, col_sheet=(0.75, 0.8, 0.7))
    _pillow(b, 0.58, y0 + 0.5, 7.45, 0.55, 0.36, 0.14, (0.86, 0.9, 0.84))
    rb.table(b, 3.4, 9.55, y0, 1.3, 0.55, 0.75)
    rb.chair(b, 3.4, 8.9, y0, 0)
    drawer = _desk_drawer(house, b, 3.4, 9.28, y0 + 0.53)
    house.parts["tiroir_bureau"] = drawer
    point(house, "tiroir_amis", (3.4, y0 + 0.62, 9.15), "Ouvrir le tiroir", 1, radius=0.9)
    # vieux portable (caché dans le tiroir : il sort avec lui)
    house.parts["tel_garnier"] = make_part(drawer.root, "metal", (0.07, 0.015, 0.14), (0.05, 0.035, 0.22), (0.12, 0.12, 0.14))
    house.parts["tel_garnier"].enabled = False
    point(house, "tel_garnier", (3.45, y0 + 0.6, 9.2), "Prendre le téléphone", 1, radius=0.8, enabled=False)
    rb.bookshelf(b, 5.55, 6.5, 5.88, 8.0, y0, 1.9, rng, face="-x") if False else None
    _toy_chest(b, 3.75, 6.47, y0)                                     # contre le mur sud, loin du battant de la porte
    point(house, "jouet", (3.6, y0 + 0.6, 6.55), "Examiner", 1, radius=0.9)
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
    # porte à miroir (l'ancienne porte émaillée unie ressemblait à une plaque blanche posée sur le mur)
    house.parts["pharmacie"] = hinged(house, 1, (px0 - 0.012, pz0), 0.5, 0.7, 0.02, (0, 1), (-1, 0), "miroir", (1, 1, 1), y0=py0)
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
    _crowbar(b, y0)
    point(house, "pied_de_biche", (4.1, y0 + 0.5, 11.5), "Ramasser le pied de biche", 2, radius=1.0)
    # poste de radio
    _dresser_radio(b, y0)
    A["radio"] = Vec3(13.5, y0 + 0.95, 2.0)
    point(house, "radio", (13.5, y0 + 1.0, 2.0), "Allumer la radio", 2, radius=1.0)
    # tube de plan
    _plan_tube(b, 8.0, 9.0, y0 + 0.6)
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
    # trappe à peine en saillie (2,4 cm) dans un cadre sombre, anneau de tirage en fer : plus l'estrade de 5 cm d'avant
    b.box("bois_meuble", 2.96, y0, 0.16, 4.64, y0 + 0.012, 1.04, rb.DARKWOOD)
    b.box("planches", 3.0, y0 + 0.012, 0.2, 4.6, y0 + 0.024, 1.0, (0.62, 0.58, 0.54))
    b.box("metal", 3.75, y0 + 0.024, 0.86, 3.85, y0 + 0.03, 0.94, (0.22, 0.2, 0.18))
    rb.rod(b, "metal", (3.72, y0 + 0.034, 0.9), (3.88, y0 + 0.034, 0.9), 0.008, col=(0.25, 0.23, 0.2))


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
    # étagères de 2,1 m : 47,5 cm entre tablettes, les sacs (40 cm) posés sur chaque tablette ne traversent plus
    # celle du dessus et ne flottent plus au-dessus de la leur
    for k in range(3):
        sx = 3.4 + k * 2.45
        rb.shelving_unit(b, sx, 23.2, sx + 2.1, 23.8, y0, levels=4, height=2.1)
        for lv in range(4):
            top = y0 + 0.15 + lv * (2.1 - 0.2) / 4 + 0.03
            for j in range(4):
                rb.delivery_bag(b, sx + 0.35 + j * 0.45, 23.5, top + 0.002, rng.uniform(-8, 8), torn=True)
    # taches sur les murs
    rb.wall_decal(b, "taches", 5.0, 1.2 + y0, 16.35, 3.0, 2.0, "+z", off=0.0, col=(1, 1, 1))
    rb.wall_decal(b, "taches", 10.8, 1.2 + y0, 20.0, 4.0, 2.0, "-x", off=0.0)
    rb.wall_decal(b, "taches", 3.2, 1.2 + y0, 19.0, 3.0, 2.0, "+x", off=0.0)
    rb.wall_decal(b, "griffures", 3.2, 0.9 + y0, 21.5, 1.6, 1.5, "+x", off=0.01)
    # tuyaux au plafond
    _basement_pipes(b, y0)
    house.anchors["basement_center"] = Vec3(cx, y0 + 1.0, cz)


def _ceiling_fixtures(house):
    """Luminaires au plafond (éteints : l'électricité est coupée) : lustre ancien dans les pièces de vie,
    ampoule nue sur douille au bout de son fil ailleurs. Le couloir de l'étage garde son néon."""
    import config as _cfg
    chandeliers = {"salon", "master", "cuisine"}
    skip = {"couloir1", "cave_acces", "placard", "grenier"}
    for r in house.rooms.values():
        if r.id in skip or r.level not in (-1, 0, 1):
            continue
        b = house.b(r.level)
        cx, cz = r.center
        ceil = LEVEL_Y[r.level] + (_cfg.BASEMENT_CEIL_H if r.level == -1 else 2.8)
        if r.id in chandeliers:
            b.model("Chandelier_01", cx, cz, ceil - 0.8, 0.0, (None, 0.8, None))
        else:
            drop = 0.5 if r.level >= 0 else 0.3
            b.cyl("metal", cx, ceil - drop, cz, 0.006, drop, 6, (0.08, 0.08, 0.08))        # fil électrique
            b.cyl("metal", cx, ceil - 0.01, cz, 0.045, 0.01, 12, (0.85, 0.84, 0.8))       # rosace
            b.model("pull_chain_light_socket", cx, cz, ceil - drop - 0.17, 0.0, (None, 0.17, None))


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
