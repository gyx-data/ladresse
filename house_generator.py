"""Génération procédurale de la maison (rez-de-chaussée, 1er étage, grenier + sous-sol).

Structure fixe pour le gameplay, géométrie construite à partir de rectangles :
murs avec ouvertures, sols avec trous d'escalier, escaliers (rampes de marche),
portes articulées, fenêtres condamnées, éclairage, extérieur (rue, voiture, lampadaire).

La classe :class:`House` fournit aussi les services physiques utilisés par le joueur et
l'IA : collisions, hauteur du sol, lancer de rayons, occlusion sonore, pièces, grille de
navigation et A*.
"""
import heapq
import math
import random

from ursina import Entity, Vec3

import config
from config import LEVEL_Y
from lighting_system import LightSource
from room_builder import MeshBuilder, HingedPart, stairs_mesh
import room_builder as rb

WALL_H = 3.0          # hauteur de mur d'un niveau (jusqu'au sol suivant)
CEIL_H = 2.8          # plafond visible
ATTIC_WALL_H = 2.4
RIDGE_H = 4.3         # hauteur du faîtage au-dessus du sol du grenier
DOOR_W = config.DOOR_W
DOOR_H = config.DOOR_H
WIN_SILL, WIN_TOP, WIN_W = 0.9, 2.0, 1.1


# ---------------------------------------------------------------------------
# Description des pièces
# ---------------------------------------------------------------------------
class Room:
    def __init__(self, rid, name, level, x0, z0, x1, z1, floor, wall, ceil="plafond"):
        self.id = rid
        self.name = name
        self.level = level
        self.x0, self.z0, self.x1, self.z1 = x0, z0, x1, z1
        self.floor = floor
        self.wall = wall
        self.ceil = ceil
        self.visited = False

    def contains(self, x, z):
        return self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1

    @property
    def center(self):
        return ((self.x0 + self.x1) / 2, (self.z0 + self.z1) / 2)


def _rooms():
    R = Room
    rooms = [
        # --- Rez-de-chaussée
        R("couloir0", "Couloir", 0, 6, 0, 8, 12, "carrelage", "papier_couloir"),
        R("salon", "Salon", 0, 0, 0, 6, 6, "parquet", "papier_peint"),
        R("cuisine", "Cuisine", 0, 0, 6, 6, 12, "carrelage", "papier_peint"),
        R("bureau", "Bureau", 0, 8, 0, 16, 4.5, "parquet", "papier_chambre"),
        R("hall0", "Cage d'escalier", 0, 8, 4.5, 12, 12, "carrelage", "papier_couloir"),
        R("sdb0", "Salle de bain", 0, 12, 4.5, 16, 8.5, "carrelage", "platre"),
        R("buanderie", "Buanderie", 0, 12, 8.5, 16, 12, "beton", "platre"),
        R("cave_acces", "Escalier de la cave", 0, 6.1, 12.0, 7.9, 16.2, "beton", "beton", "beton"),
        # --- Premier étage
        R("couloir1", "Couloir", 1, 6, 0, 8, 12, "moquette", "papier_couloir"),
        R("palier", "Palier", 1, 8, 4.5, 12, 12, "moquette", "papier_couloir"),
        R("branche", "Couloir", 1, 12, 4.5, 16, 6.5, "moquette", "papier_couloir"),
        R("master", "Chambre de M. Garnier", 1, 0, 0, 6, 6, "parquet", "papier_chambre"),
        R("amis", "Chambre d'amis", 1, 0, 6, 6, 10, "parquet", "papier_peint"),
        R("placard", "Placard", 1, 0, 10, 6, 12, "parquet", "platre"),
        R("condamnee", "Chambre condamnée", 1, 8, 0, 16, 4.5, "parquet", "platre"),
        R("sdb1", "Salle de bain", 1, 12, 6.5, 16, 12, "carrelage", "platre"),
        # --- Grenier
        R("grenier", "Grenier", 2, 0, 0, 16, 12, "parquet", "planches", "planches"),
        # --- Sous-sol
        R("sous_sol", "Sous-sol", -1, 3, 16.2, 11, 24.2, "beton", "beton", "beton"),
    ]
    return {r.id: r for r in rooms}


# Trous de plancher : (niveau du plancher percé, x0, z0, x1, z1)
HOLES = [
    (1, 8.4, 5.0, 9.8, 9.4),      # volée RDC -> 1er
    (2, 9.9, 5.6, 10.9, 10.0),    # volée 1er -> grenier
]

# Escaliers : rampes de marche
STAIRS = [
    dict(id="rdc_1", lo=0, hi=1, x0=8.4, x1=9.8, za=5.0, zb=9.4, ya=0.0, yb=3.0, steps=16),
    dict(id="1_grenier", lo=1, hi=2, x0=9.9, x1=10.9, za=10.0, zb=5.6, ya=3.0, yb=6.0, steps=16),
    dict(id="cave", lo=-1, hi=0, x0=6.1, x1=7.9, za=16.14, zb=12.3, ya=-3.0, yb=0.0, steps=16),
]

# Fenêtres : (niveau, axe, position fixe, centre, état) état = 'volet' | 'planches' | 'verre'
WINDOWS = [
    (0, "x", 0.0, 1.5, "volet"),       # salon, façade
    (0, "x", 0.0, 12.0, "volet"),      # bureau, façade
    (0, "z", 0.0, 4.5, "volet"),       # salon, ouest
    (0, "x", 12.0, 3.0, "planches"),   # cuisine, nord (côté ouest)
    (0, "z", 0.0, 9.0, "planches"),    # cuisine au-dessus de l'évier
    (0, "z", 16.0, 2.2, "volet"),      # bureau, est
    (0, "z", 16.0, 6.5, "planches"),   # sdb
    (0, "x", 12.0, 10.0, "planches"),  # hall nord
    (1, "x", 0.0, 2.0, "volet"),       # master
    (1, "x", 0.0, 7.0, "volet"),       # couloir
    (1, "x", 0.0, 12.0, "planches"),   # condamnée
    (1, "z", 0.0, 3.0, "volet"),       # master ouest
    (1, "z", 0.0, 8.0, "volet"),       # chambre d'amis
    (1, "x", 12.0, 7.0, "volet"),      # couloir nord
    (1, "x", 12.0, 14.0, "planches"),  # sdb1
    (1, "z", 16.0, 5.5, "volet"),      # bout du couloir
    (2, "x", 0.0, 8.0, "verre"),       # lucarne côté rue
    (2, "x", 0.0, 3.0, "volet"),
    (2, "x", 12.0, 8.0, "volet"),
]

# Portes : id, niveau, axe, position fixe, centre, battant ('normal', 'front', ...), swing, hinge direction
DOORS = [
    ("front", 0, "x", 0.0, 7.0, "front", 1),
    ("salon", 0, "z", 6.0, 3.0, "normal", -1),
    ("cuisine", 0, "z", 6.0, 9.0, "normal", -1),
    ("bureau", 0, "z", 8.0, 2.2, "normal", 1),
    ("sdb0", 0, "z", 12.0, 6.5, "normal", -1),
    ("buanderie", 0, "z", 12.0, 10.2, "normal", -1),
    ("cave", 0, "x", 12.0, 7.0, "cave", -1),
    ("master", 1, "z", 6.0, 3.0, "normal", -1),
    ("amis", 1, "z", 6.0, 8.0, "normal", -1),
    ("placard", 1, "z", 6.0, 11.0, "normal", -1),
    ("condamnee", 1, "x", 4.5, 13.0, "condamnee", 1),
    ("sdb1", 1, "x", 6.5, 14.0, "normal", 1),
]

ARCHWAYS = [(0, "x", 6.0, 3.0, 1.5)]      # salon <-> cuisine (passage sans porte)


class Surface:
    """Surface praticable : plate (ya = yb) ou rampe le long de z."""

    def __init__(self, x0, z0, x1, z1, ya, yb=None, za=None, zb=None, level=0):
        self.x0, self.z0, self.x1, self.z1 = min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)
        self.ya = ya
        self.yb = ya if yb is None else yb
        self.za = za
        self.zb = zb
        self.level = level

    def height(self, x, z):
        if self.za is None or self.yb == self.ya:
            return self.ya
        t = (z - self.za) / (self.zb - self.za)
        t = max(0.0, min(1.0, t))
        return self.ya + (self.yb - self.ya) * t


def rect_minus(rect, hole):
    """Retourne la liste de rectangles couvrant rect privé de hole."""
    x0, z0, x1, z1 = rect
    hx0, hz0, hx1, hz1 = hole
    if hx0 >= x1 or hx1 <= x0 or hz0 >= z1 or hz1 <= z0:
        return [rect]
    out = []
    if hz0 > z0:
        out.append((x0, z0, x1, hz0))
    if hz1 < z1:
        out.append((x0, hz1, x1, z1))
    mz0, mz1 = max(z0, hz0), min(z1, hz1)
    if hx0 > x0:
        out.append((x0, mz0, hx0, mz1))
    if hx1 < x1:
        out.append((hx1, mz0, x1, mz1))
    return out


class Door:
    """Porte articulée avec collision dynamique."""

    def __init__(self, house, did, level, axis, fixed, center, kind, swing, parent):
        self.house = house
        self.id = did
        self.level = level
        self.axis = axis
        self.fixed = fixed
        self.center = center
        self.kind = kind
        self.locked = kind in ("locked_amis", "condamnee", "cave")
        self.is_open = False
        self.busy = False
        self.y0 = LEVEL_Y[level]
        w = DOOR_W
        # direction du battant fermé
        d = (1.0, 0.0) if axis == "x" else (0.0, 1.0)
        rot0 = 0.0 if axis == "x" else -90.0
        hx = center - w / 2 if axis == "x" else fixed
        hz = fixed if axis == "x" else center - w / 2
        n = (0.0, 1.0) if axis == "x" else (1.0, 0.0)
        n = (n[0] * swing, n[1] * swing)
        # choix du signe de rotation pour que l'extrémité libre aille vers n
        def rot(v, deg):
            a = math.radians(deg)
            return (v[0] * math.cos(a) + v[1] * math.sin(a), -v[0] * math.sin(a) + v[1] * math.cos(a))
        r = rot(d, 90.0)
        angle = 90.0 if (r[0] * n[0] + r[1] * n[1]) > 0 else -90.0
        self.open_angle = angle
        tex = "porte_griffes" if kind in ("condamnee",) else "porte"
        self.part = HingedPart(parent, (hx, self.y0, hz), (w, DOOR_H, 0.05), tex=tex, open_angle=angle,
                               side="+x", rot_y=rot0, tile=1.0)
        # position du seuil (pour ouvrir / AI / son)
        if axis == "x":
            self.pos = Vec3(center, self.y0 + 1.0, fixed)
            self.aabb = (center - w / 2, self.y0, fixed - 0.12, center + w / 2, self.y0 + DOOR_H, fixed + 0.12)
        else:
            self.pos = Vec3(fixed, self.y0 + 1.0, center)
            self.aabb = (fixed - 0.12, self.y0, center - w / 2, fixed + 0.12, self.y0 + DOOR_H, center + w / 2)
        self.normal = n
        self.ai_passable = kind not in ("condamnee", "cave", "front", "front_locked")
        house.dyn_colliders[did] = self.aabb

    def _remove_collider(self):
        self.house.dyn_colliders.pop(self.id, None)

    def _add_collider(self):
        self.house.dyn_colliders[self.id] = self.aabb

    def open(self, duration=0.8, silent=False):
        if self.is_open:
            return
        self.is_open = True
        self._remove_collider()
        self.part.set_open(True, duration)
        if not silent and self.house.on_door_sound:
            self.house.on_door_sound(self, "porte_ouvre")

    def close(self, duration=0.6, silent=False, slam=False):
        if not self.is_open:
            return
        self.is_open = False
        self.part.set_open(False, duration)
        from ursina import invoke as _invoke
        _invoke(self._finish_close, delay=duration)
        if not silent and self.house.on_door_sound:
            self.house.on_door_sound(self, "porte_claque" if slam else "porte_ferme")

    def _finish_close(self):
        if not self.is_open:
            self._add_collider()

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()


class House:
    """La maison : géométrie, physique simplifiée et navigation."""

    def __init__(self):
        self.rooms = _rooms()
        self.colliders = []                # statiques : (x0,y0,z0,x1,y1,z1)
        self.dyn_colliders = {}            # id -> aabb (portes fermées...)
        self.nav_blockers = {}             # id -> (x0,z0,x1,z1,level)
        self.surfaces = []
        self.doors = {}
        self.lights = []
        self.anchors = {}                  # entités / positions nommées
        self.level_roots = {}
        self.builders = {}
        self.exterior_root = None
        self.on_door_sound = None
        self._cgrid = {}
        self.window_info = []              # pour le brouillard / lumière extérieure
        self.glass_colliders = []          # vitres : bloquent la caméra 3e personne (pas le joueur)
        self.nav = None
        self.built = False
        self.rng = random.Random(1961)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def build(self, with_exterior=True):
        """Construit toute la géométrie. Générateur : yield (fraction, libellé)."""
        self._make_roots()
        yield 0.02, "Fondations"
        for lvl in (0, 1, 2, -1):
            self._build_level(lvl)
            yield 0.1 + 0.15 * (lvl + 1 if lvl >= 0 else 0), f"Niveau {lvl}"
        self._build_stairs()
        yield 0.55, "Escaliers"
        self._build_roof()
        yield 0.62, "Toit"
        from house_props import populate_house
        populate_house(self)
        yield 0.8, "Mobilier"
        for lvl, b in self.builders.items():
            b.build(parent=self.level_roots[lvl])
            self.colliders.extend(b.colliders)
            yield 0.85, "Maillages"
        if with_exterior:
            self._build_exterior()
        self._index_colliders()
        yield 0.95, "Navigation"
        self.nav = NavGrid(self)
        self.built = True
        yield 1.0, "Terminé"

    def _make_roots(self):
        for lvl in (-1, 0, 1, 2):
            self.level_roots[lvl] = Entity(name=f"niveau_{lvl}")
            self.builders[lvl] = MeshBuilder(f"niveau_{lvl}")
        self.exterior_root = Entity(name="exterieur")

    def b(self, lvl):
        return self.builders[lvl]

    # --- murs ---------------------------------------------------------
    def _room_tex(self, rid):
        if rid == "EXT":
            return "crepi"
        if rid == "VOID":
            return "beton"
        return self.rooms[rid].wall

    def _wall(self, lvl, axis, fixed, a0, a1, neg, pos, openings=(), height=None, thick=0.2):
        b = self.b(lvl)
        y0 = LEVEL_Y[lvl]
        h = height if height is not None else WALL_H
        tneg, tpos = self._room_tex(neg), self._room_tex(pos)
        cneg = (0.75, 0.75, 0.75) if neg == "EXT" else (1, 1, 1)
        cpos = (0.75, 0.75, 0.75) if pos == "EXT" else (1, 1, 1)
        b.wall_openings(axis, a0, a1, fixed, y0, y0 + h, list(openings), thick,
                        tex_neg=tneg, tex_pos=tpos, col_neg=cneg, col_pos=cpos)

    def _openings_for(self, lvl, axis, fixed, a0, a1):
        ops = []
        for (dl, dax, dfix, dc, kind, sw) in [(d[1], d[2], d[3], d[4], d[5], d[6]) for d in DOORS]:
            if dl == lvl and dax == axis and abs(dfix - fixed) < 1e-6 and a0 <= dc <= a1:
                ops.append((dc, DOOR_W, 0.0, DOOR_H))
        for (al, ax, afix, ac, aw) in ARCHWAYS:
            if al == lvl and ax == axis and abs(afix - fixed) < 1e-6 and a0 <= ac <= a1:
                ops.append((ac, aw, 0.0, DOOR_H + 0.1))
        for (wl, wax, wfix, wc, st) in WINDOWS:
            if wl == lvl and wax == axis and abs(wfix - fixed) < 1e-6 and a0 <= wc <= a1:
                ops.append((wc, WIN_W, WIN_SILL, WIN_TOP))
        return ops

    def _build_level(self, lvl):
        if lvl == 0:
            self._walls_level0()
        elif lvl == 1:
            self._walls_level1()
        elif lvl == 2:
            self._walls_attic()
        else:
            self._walls_basement()
        self._floors_and_ceilings(lvl)
        self._windows(lvl)
        self._doors(lvl)

    def _wr(self, lvl, axis, fixed, a0, a1, neg, pos):
        self._wall(lvl, axis, fixed, a0, a1, neg, pos, self._openings_for(lvl, axis, fixed, a0, a1))

    def _walls_level0(self):
        L = 0
        # Façade sud (z=0) : neg = dehors, pos = intérieur
        self._wr(L, "x", 0.0, 0, 6, "EXT", "salon")
        self._wr(L, "x", 0.0, 6, 8, "EXT", "couloir0")
        self._wr(L, "x", 0.0, 8, 16, "EXT", "bureau")
        # Nord (z=12)
        self._wr(L, "x", 12.0, 0, 6, "cuisine", "EXT")
        self._wr(L, "x", 12.0, 6, 8, "couloir0", "EXT")
        self._wr(L, "x", 12.0, 8, 12, "hall0", "EXT")
        self._wr(L, "x", 12.0, 12, 16, "buanderie", "EXT")
        # Ouest (x=0)
        self._wr(L, "z", 0.0, 0, 6, "EXT", "salon")
        self._wr(L, "z", 0.0, 6, 12, "EXT", "cuisine")
        # Est (x=16)
        self._wr(L, "z", 16.0, 0, 4.5, "bureau", "EXT")
        self._wr(L, "z", 16.0, 4.5, 8.5, "sdb0", "EXT")
        self._wr(L, "z", 16.0, 8.5, 12, "buanderie", "EXT")
        # Intérieur
        self._wr(L, "z", 6.0, 0, 6, "salon", "couloir0")
        self._wr(L, "z", 6.0, 6, 12, "cuisine", "couloir0")
        self._wr(L, "x", 6.0, 0, 6, "salon", "cuisine")
        self._wr(L, "z", 8.0, 0, 4.5, "couloir0", "bureau")
        self._wr(L, "x", 4.5, 8, 12, "bureau", "hall0")
        self._wr(L, "x", 4.5, 12, 16, "bureau", "sdb0")
        self._wr(L, "z", 12.0, 4.5, 8.5, "hall0", "sdb0")
        self._wr(L, "z", 12.0, 8.5, 12, "hall0", "buanderie")
        self._wr(L, "x", 8.5, 12, 16, "sdb0", "buanderie")
        # Fond du couloir : porte vers la cave (annexe)
        # (le mur nord du couloir est déjà posé ci-dessus ; ouverture 'cave' gérée par DOORS)

    def _walls_level1(self):
        L = 1
        # Sud
        self._wr(L, "x", 0.0, 0, 6, "EXT", "master")
        self._wr(L, "x", 0.0, 6, 8, "EXT", "couloir1")
        self._wr(L, "x", 0.0, 8, 16, "EXT", "condamnee")
        # Nord
        self._wr(L, "x", 12.0, 0, 6, "placard", "EXT")
        self._wr(L, "x", 12.0, 6, 8, "couloir1", "EXT")
        self._wr(L, "x", 12.0, 8, 12, "palier", "EXT")
        self._wr(L, "x", 12.0, 12, 16, "sdb1", "EXT")
        # Ouest
        self._wr(L, "z", 0.0, 0, 6, "EXT", "master")
        self._wr(L, "z", 0.0, 6, 10, "EXT", "amis")
        self._wr(L, "z", 0.0, 10, 12, "EXT", "placard")
        # Est
        self._wr(L, "z", 16.0, 0, 4.5, "condamnee", "EXT")
        self._wr(L, "z", 16.0, 4.5, 6.5, "branche", "EXT")
        self._wr(L, "z", 16.0, 6.5, 12, "sdb1", "EXT")
        # Intérieur
        self._wr(L, "z", 6.0, 0, 6, "master", "couloir1")
        self._wr(L, "z", 6.0, 6, 10, "amis", "couloir1")
        self._wr(L, "z", 6.0, 10, 12, "placard", "couloir1")
        self._wr(L, "x", 6.0, 0, 6, "master", "amis")
        self._wr(L, "x", 10.0, 0, 6, "amis", "placard")
        self._wr(L, "z", 8.0, 0, 4.5, "couloir1", "condamnee")
        self._wr(L, "x", 4.5, 8, 12, "condamnee", "palier")
        self._wr(L, "x", 4.5, 12, 16, "condamnee", "branche")
        self._wr(L, "x", 6.5, 12, 16, "branche", "sdb1")
        self._wr(L, "z", 12.0, 6.5, 12, "palier", "sdb1")

    def _walls_attic(self):
        L = 2
        h = ATTIC_WALL_H
        b = self.b(L)
        y0 = LEVEL_Y[2]
        # murs bas nord/sud
        self._wall(L, "x", 0.0, 0, 16, "EXT", "grenier", self._openings_for(L, "x", 0.0, 0, 16), height=h)
        self._wall(L, "x", 12.0, 0, 16, "grenier", "EXT", self._openings_for(L, "x", 12.0, 0, 16), height=h)
        # pignons (ouest / est)
        for fixed, neg, pos in ((0.0, "EXT", "grenier"), (16.0, "grenier", "EXT")):
            self._wall(L, "z", fixed, 0, 12, neg, pos, [], height=h)
            tneg, tpos = self._room_tex(neg), self._room_tex(pos)
            x0, x1 = fixed - 0.1, fixed + 0.1
            ridge = y0 + RIDGE_H
            b.tri(tneg, (x0, y0 + h, 0), (x0, y0 + h, 12), (x0, ridge, 6), (-1, 0, 0), (1, 1, 1))
            b.tri(tpos, (x1, y0 + h, 0), (x1, y0 + h, 12), (x1, ridge, 6), (1, 0, 0), (1, 1, 1))
        # poutres
        for x in (2, 5, 8, 11, 14):
            b.box("bois_meuble", x - 0.07, y0 + h - 0.1, 0.1, x + 0.07, y0 + h + 0.05, 11.9, rb.DARKWOOD, skip=("-y",))
            b.box("bois_meuble", x - 0.07, y0 + h, 5.93, x + 0.07, y0 + RIDGE_H - 0.02, 6.07, rb.DARKWOOD)
        b.box("bois_meuble", 0.1, y0 + RIDGE_H - 0.1, 5.92, 15.9, y0 + RIDGE_H, 6.08, rb.DARKWOOD)

    def _walls_basement(self):
        L = -1
        y0 = LEVEL_Y[-1]
        h = config.BASEMENT_CEIL_H
        b = self.b(L)
        x0, x1, z0, z1 = 3.0, 11.0, 16.2, 24.2
        t = 0.2
        # murs de la pièce : le mur sud a une ouverture pour l'escalier (x 6.1-7.9)
        b.wall("x", x0, 6.1, z0, y0, y0 + h, t, tex_neg="beton", tex_pos="beton", cap_tex="beton")
        b.wall("x", 7.9, x1, z0, y0, y0 + h, t, tex_neg="beton", tex_pos="beton", cap_tex="beton")
        b.wall("x", x0, x1, z1, y0, y0 + h, t, tex_neg="beton", tex_pos="beton", cap_tex="beton")
        b.wall("z", z0, z1, x0, y0, y0 + h, t, tex_neg="beton", tex_pos="beton", cap_tex="beton")
        b.wall("z", z0, z1, x1, y0, y0 + h, t, tex_neg="beton", tex_pos="beton", cap_tex="beton")
        # cage d'escalier (annexe de la cave)
        sx0, sx1 = 6.1, 7.9
        zt, zb = 12.0, 16.2
        top_y = 2.8
        # murs latéraux inclinés (suivent la pente du plafond) : on utilise des boîtes verticales par tronçons
        steps = 10
        for i in range(steps):
            za = zt + (zb - zt) * i / steps
            zb2 = zt + (zb - zt) * (i + 1) / steps
            yc = top_y + (y0 + h - top_y) * (i + 0.5) / steps
            ylo = y0
            for xw, face in ((sx0, "+x"), (sx1, "-x")):
                b.box("beton", xw - 0.1, ylo - 0.05, za, xw + 0.1, yc + 0.0, zb2, (0.9, 0.9, 0.9), collide=True,
                      skip=("-y",))
        # plafond incliné de l'escalier
        b.quad("beton", (sx0, top_y, zt + 0.1), (sx1, top_y, zt + 0.1), (sx1, y0 + h, zb), (sx0, y0 + h, zb), (0, -1, 0),
               (0.8, 0.8, 0.8))
        # palier plat au sommet de l'escalier de la cave
        self.surfaces.append(Surface(6.1, 12.0, 7.9, 12.3, 0.0, level=0))

    # --- sols / plafonds ----------------------------------------------
    def _floors_and_ceilings(self, lvl):
        b = self.b(lvl)
        y0 = LEVEL_Y[lvl]
        for room in self.rooms.values():
            if room.level != lvl:
                continue
            if room.id == "cave_acces":
                continue
            rect = (room.x0, room.z0, room.x1, room.z1)
            # sol (trous éventuels)
            parts = [rect]
            for (hl, hx0, hz0, hx1, hz1) in HOLES:
                if hl == lvl:
                    parts = [q for p in parts for q in rect_minus(p, (hx0, hz0, hx1, hz1))]
            floor_col = (1, 1, 1)
            for (px0, pz0, px1, pz1) in parts:
                b.quad(room.floor, (px0, y0, pz0), (px1, y0, pz0), (px1, y0, pz1), (px0, y0, pz1), (0, 1, 0), floor_col)
                self.surfaces.append(Surface(px0, pz0, px1, pz1, y0, level=lvl))
            # plafond (sauf au grenier : sous-face de la toiture)
            if lvl == 2:
                continue
            ch = CEIL_H if lvl >= 0 else config.BASEMENT_CEIL_H
            cparts = [rect]
            for (hl, hx0, hz0, hx1, hz1) in HOLES:
                if hl == lvl + 1:
                    cparts = [q for p in cparts for q in rect_minus(p, (hx0, hz0, hx1, hz1))]
            for (px0, pz0, px1, pz1) in cparts:
                b.quad(room.ceil, (px0, y0 + ch, pz0), (px1, y0 + ch, pz0), (px1, y0 + ch, pz1), (px0, y0 + ch, pz1),
                       (0, -1, 0), (0.95, 0.95, 0.95))
        # tranches des trous de plancher
        for (hl, hx0, hz0, hx1, hz1) in HOLES:
            if hl == lvl + 1:
                yb = y0 + CEIL_H
                yt = y0 + WALL_H
                for (ax, az, bx, bz, n) in (
                    (hx0, hz0, hx1, hz0, (0, 0, 1)), (hx1, hz1, hx0, hz1, (0, 0, -1)),
                    (hx0, hz1, hx0, hz0, (1, 0, 0)), (hx1, hz0, hx1, hz1, (-1, 0, 0)),
                ):
                    b.quad("platre", (ax, yb, az), (bx, yb, bz), (bx, yt, bz), (ax, yt, az), n, (0.9, 0.9, 0.9))

    # --- fenêtres ------------------------------------------------------
    def _windows(self, lvl):
        b = self.b(lvl)
        y0 = LEVEL_Y[lvl]
        for (wl, ax, fixed, c, state) in WINDOWS:
            if wl != lvl:
                continue
            ys, ye = y0 + WIN_SILL, y0 + WIN_TOP
            hw = WIN_W / 2
            # sens intérieur / extérieur
            if ax == "x":
                inward = 1 if fixed < 6 else -1      # sud : intérieur = +z ; nord : intérieur = -z
                out = -inward
                # vitre
                zc = fixed
                b.quad("vitre", (c - hw, ys, zc), (c + hw, ys, zc), (c + hw, ye, zc), (c - hw, ye, zc), (0, 0, inward))
                b.quad("vitre", (c + hw, ys, zc), (c - hw, ys, zc), (c - hw, ye, zc), (c + hw, ye, zc), (0, 0, out))
                # cadre
                for (xa, xb) in ((c - hw - 0.04, c - hw), (c + hw, c + hw + 0.04)):
                    b.box("bois_meuble", xa, ys - 0.04, zc - 0.07, xb, ye + 0.04, zc + 0.07, (0.55, 0.5, 0.45))
                b.box("bois_meuble", c - hw - 0.04, ys - 0.05, zc - 0.1, c + hw + 0.04, ys, zc + 0.1, (0.55, 0.5, 0.45))
                b.box("bois_meuble", c - hw - 0.04, ye, zc - 0.07, c + hw + 0.04, ye + 0.04, zc + 0.07, (0.55, 0.5, 0.45))
                b.box("bois_meuble", c - 0.02, ys, zc - 0.05, c + 0.02, ye, zc + 0.05, (0.55, 0.5, 0.45))
                if state == "volet":
                    zo = zc + out * 0.12
                    b.box("volet", c - hw - 0.05, ys - 0.06, min(zo, zo + out * 0.04), c + hw + 0.05, ye + 0.06,
                          max(zo, zo + out * 0.04), (0.9, 0.9, 0.9))
                elif state == "planches":
                    for k in range(5):
                        yy = ys + 0.05 + k * (ye - ys - 0.1) / 5
                        zi = zc + inward * (0.08 + 0.01 * (k % 2))
                        b.box("planches", c - hw - 0.12, yy, min(zi, zi + inward * 0.03), c + hw + 0.12, yy + 0.2,
                              max(zi, zi + inward * 0.03), (0.85, 0.8, 0.75))
                else:
                    pass
                self.window_info.append((lvl, ax, fixed, c, state))
                self.glass_colliders.append((c - hw, ys, zc - 0.05, c + hw, ye, zc + 0.05))
            else:
                inward = 1 if fixed < 8 else -1
                out = -inward
                xc = fixed
                b.quad("vitre", (xc, ys, c + hw), (xc, ys, c - hw), (xc, ye, c - hw), (xc, ye, c + hw), (inward, 0, 0))
                b.quad("vitre", (xc, ys, c - hw), (xc, ys, c + hw), (xc, ye, c + hw), (xc, ye, c - hw), (out, 0, 0))
                for (za, zb) in ((c - hw - 0.04, c - hw), (c + hw, c + hw + 0.04)):
                    b.box("bois_meuble", xc - 0.07, ys - 0.04, za, xc + 0.07, ye + 0.04, zb, (0.55, 0.5, 0.45))
                b.box("bois_meuble", xc - 0.1, ys - 0.05, c - hw - 0.04, xc + 0.1, ys, c + hw + 0.04, (0.55, 0.5, 0.45))
                b.box("bois_meuble", xc - 0.07, ye, c - hw - 0.04, xc + 0.07, ye + 0.04, c + hw + 0.04, (0.55, 0.5, 0.45))
                if state == "volet":
                    xo = xc + out * 0.12
                    b.box("volet", min(xo, xo + out * 0.04), ys - 0.06, c - hw - 0.05, max(xo, xo + out * 0.04), ye + 0.06,
                          c + hw + 0.05, (0.9, 0.9, 0.9))
                elif state == "planches":
                    for k in range(5):
                        yy = ys + 0.05 + k * (ye - ys - 0.1) / 5
                        xi = xc + inward * (0.08 + 0.01 * (k % 2))
                        b.box("planches", min(xi, xi + inward * 0.03), yy, c - hw - 0.12, max(xi, xi + inward * 0.03),
                              yy + 0.2, c + hw + 0.12, (0.85, 0.8, 0.75))
                self.window_info.append((lvl, ax, fixed, c, state))
                self.glass_colliders.append((xc - 0.05, ys, c - hw, xc + 0.05, ye, c + hw))

    # --- portes --------------------------------------------------------
    def _doors(self, lvl):
        for (did, dl, axis, fixed, center, kind, swing) in DOORS:
            if dl != lvl:
                continue
            door = Door(self, did, dl, axis, fixed, center, kind, swing, self.level_roots[lvl])
            self.doors[did] = door

    # --- escaliers -----------------------------------------------------
    def _build_stairs(self):
        for st in STAIRS:
            lvl = st["lo"] if st["id"] != "cave" else -1
            owner = st["hi"] if st["id"] != "cave" else -1
            b = self.b(owner if st["id"] != "cave" else -1)
            stairs_mesh(b, st["x0"], st["x1"], st["za"], st["zb"], st["ya"], st["yb"], st["steps"])
            self.surfaces.append(Surface(st["x0"], st["za"], st["x1"], st["zb"], st["ya"], st["yb"], st["za"], st["zb"], level=lvl))
            lo, hi = sorted((st["za"], st["zb"]))
            # rambardes latérales (collision) sur toute la longueur
            y_lo = min(st["ya"], st["yb"])
            y_hi = max(st["ya"], st["yb"])
            for xw in (st["x0"], st["x1"]):
                self.b(owner).colliders.append((xw - 0.05, y_lo - 0.1, lo, xw + 0.05, y_hi + 1.2, hi))
            # fermeture côté bas (z) : mur invisible, et côté haut ouvert
            if st["id"] == "rdc_1":
                self.b(1).colliders.append((st["x0"], 3.0, st["za"] - 0.05, st["x1"], 4.2, st["za"] + 0.05))
                self._balustrade(self.b(1), st["x0"], st["x1"], st["za"], 3.0, axis="x")
                self._balustrade(self.b(1), st["za"], st["zb"], st["x0"], 3.0, axis="z")
                self._balustrade(self.b(1), st["za"], st["zb"], st["x1"], 3.0, axis="z")
                self.b(1).colliders.append((st["x0"] - 0.05, 3.0, st["za"], st["x0"] + 0.05, 4.2, st["zb"]))
                self.b(1).colliders.append((st["x1"] - 0.05, 3.0, st["za"], st["x1"] + 0.05, 4.2, st["zb"]))
            elif st["id"] == "1_grenier":
                self.b(2).colliders.append((st["x0"], 6.0, st["za"] - 0.05, st["x1"], 7.2, st["za"] + 0.05))
                self._balustrade(self.b(2), st["x0"], st["x1"], st["za"], 6.0, axis="x")
                self._balustrade(self.b(2), st["zb"], st["za"], st["x0"], 6.0, axis="z")
                self._balustrade(self.b(2), st["zb"], st["za"], st["x1"], 6.0, axis="z")
                self.b(2).colliders.append((st["x0"] - 0.05, 6.0, st["zb"], st["x0"] + 0.05, 7.2, st["za"]))
                self.b(2).colliders.append((st["x1"] - 0.05, 6.0, st["zb"], st["x1"] + 0.05, 7.2, st["za"]))
        # murs porteurs sous les escaliers (RDC) : volume plein
        # z-start reculé pour ne pas bloquer l'entrée de l'escalier
        self.b(0).colliders.append((8.4, 0.0, 6.5, 9.8, 1.0, 9.4))

    def _balustrade(self, b, a0, a1, fixed, y, axis="x"):
        lo, hi = min(a0, a1), max(a0, a1)
        n = max(2, int((hi - lo) / 0.25))
        for i in range(n + 1):
            p = lo + (hi - lo) * i / n
            if axis == "x":
                b.box("bois_meuble", p - 0.015, y, fixed - 0.015, p + 0.015, y + 0.9, fixed + 0.015, rb.DARKWOOD)
            else:
                b.box("bois_meuble", fixed - 0.015, y, p - 0.015, fixed + 0.015, y + 0.9, p + 0.015, rb.DARKWOOD)
        if axis == "x":
            b.box("bois_meuble", lo, y + 0.9, fixed - 0.04, hi, y + 0.95, fixed + 0.04, rb.DARKWOOD)
        else:
            b.box("bois_meuble", fixed - 0.04, y + 0.9, lo, fixed + 0.04, y + 0.95, hi, rb.DARKWOOD)

    # --- toit ----------------------------------------------------------
    def _build_roof(self):
        b = self.b(2)
        y0 = LEVEL_Y[2]
        yw = y0 + ATTIC_WALL_H
        yr = y0 + RIDGE_H
        ov = 0.45
        # versant sud (z=0 -> 6)
        n_s = (0.0, 0.47, -0.88)
        n_n = (0.0, 0.47, 0.88)
        ts = "tuiles"
        cs = (0.85, 0.8, 0.78)
        for (za, ya_, zb, yb_, n_out, n_in) in (
            (-ov, yw - 0.12, 6.0, yr, (0, 0.9, -0.43), (0, -0.9, 0.43)),
            (12 + ov, yw - 0.12, 6.0, yr, (0, 0.9, 0.43), (0, -0.9, -0.43)),
        ):
            p0 = (-ov, ya_, za)
            p1 = (16 + ov, ya_, za)
            p2 = (16 + ov, yb_, zb)
            p3 = (-ov, yb_, zb)
            b.quad(ts, p0, p1, p2, p3, n_out, cs, tile=1.6)
            q0 = (0.1, ya_ + 0.02 + (0.12 if True else 0), 0.0 if za < 6 else 12.0)
            q1 = (15.9, q0[1], q0[2])
            q2 = (15.9, yb_ - 0.02, zb)
            q3 = (0.1, yb_ - 0.02, zb)
            b.quad("planches", q0, q1, q2, q3, n_in, (0.8, 0.75, 0.7), tile=1.2)
        # génoise provençale (double rang de tuiles sous l'avant-toit) et faîtage
        for zf, sgn in ((0.0, -1), (12.0, 1)):
            for k in range(2):
                zz = zf + sgn * (0.05 + 0.12 * k)
                b.box("tuiles", -0.25, yw - 0.32 + k * 0.12, min(zz, zz + sgn * 0.12), 16.25, yw - 0.2 + k * 0.12,
                      max(zz, zz + sgn * 0.12), (0.9, 0.78, 0.7))
        b.box("tuiles", -ov, yr - 0.04, 5.85, 16 + ov, yr + 0.14, 6.15, (0.75, 0.6, 0.55))
        del n_s, n_n

    # --- extérieur -----------------------------------------------------
    def _build_exterior(self):
        b = MeshBuilder("exterieur")
        # sol : jardin, trottoir, route (côté sud, z < 0)
        b.quad("herbe", (-14, -0.03, -6.0), (30, -0.03, -6.0), (30, -0.03, 0.0), (-14, -0.03, 0.0), (0, 1, 0), (0.7, 0.75, 0.7), tile=2.0)
        b.quad("beton", (-14, -0.02, -7.4), (30, -0.02, -7.4), (30, -0.02, -6.0), (-14, -0.02, -6.0), (0, 1, 0), (0.8, 0.8, 0.8), tile=2.0)
        b.quad("asphalte", (-30, -0.04, -16), (46, -0.04, -16), (46, -0.04, -7.4), (-30, -0.04, -7.4), (0, 1, 0), (1, 1, 1), tile=3.0)
        # arrière et côtés (autour de l'annexe de la cave)
        b.quad("herbe", (-14, -0.03, 0), (0, -0.03, 0), (0, -0.03, 12), (-14, -0.03, 12), (0, 1, 0), (0.7, 0.75, 0.7), tile=2.0)
        b.quad("herbe", (16, -0.03, 0), (30, -0.03, 0), (30, -0.03, 12), (16, -0.03, 12), (0, 1, 0), (0.7, 0.75, 0.7), tile=2.0)
        b.quad("herbe", (-14, -0.03, 12), (6.1, -0.03, 12), (6.1, -0.03, 40), (-14, -0.03, 40), (0, 1, 0), (0.7, 0.75, 0.7), tile=2.0)
        b.quad("herbe", (7.9, -0.03, 12), (30, -0.03, 12), (30, -0.03, 40), (7.9, -0.03, 40), (0, 1, 0), (0.7, 0.75, 0.7), tile=2.0)
        b.quad("herbe", (6.1, -0.03, 16.2), (7.9, -0.03, 16.2), (7.9, -0.03, 40), (6.1, -0.03, 40), (0, 1, 0), (0.7, 0.75, 0.7), tile=2.0)
        # allée jusqu'à la porte
        b.quad("beton", (6.4, -0.02, -6.0), (7.6, -0.02, -6.0), (7.6, -0.02, 0.0), (6.4, -0.02, 0.0), (0, 1, 0), (0.85, 0.85, 0.85), tile=1.0)
        # marche de porte
        b.box("beton", 6.4, 0.0, -0.6, 7.6, 0.12, 0.0, (0.8, 0.8, 0.8))
        # pots de géraniums de part et d'autre de l'entrée
        b.flower_pot(6.15, 0.0, -0.4)
        b.flower_pot(7.85, 0.0, -0.4, 0.14, 0.26)
        # muret en pierre crépie + grille en fer forgé (clôture niçoise)
        for (xa, xb) in ((-10.0, 6.4), (7.6, 28.0)):
            b.box("crepi", xa, 0.0, -6.06, xb, 0.55, -5.86, (0.82, 0.78, 0.72), collide=True)
            b.box("beton", xa - 0.02, 0.55, -6.1, xb + 0.02, 0.62, -5.82, (0.8, 0.78, 0.74))
            x = xa + 0.1
            while x < xb - 0.05:
                b.box("metal", x, 0.62, -5.99, x + 0.03, 1.45 - 0.06 * (int(x * 3) % 2), -5.95, (0.2, 0.22, 0.2))
                x += 0.22
            b.box("metal", xa, 1.3, -5.99, xb, 1.34, -5.95, (0.2, 0.22, 0.2))
        for px_ in (6.3, 7.7):
            b.box("crepi", px_ - 0.18, 0.0, -6.15, px_ + 0.18, 1.7, -5.8, (0.85, 0.8, 0.74), collide=True)
            b.box("beton", px_ - 0.22, 1.7, -6.19, px_ + 0.22, 1.8, -5.76, (0.8, 0.78, 0.74))
        # végétation méditerranéenne : palmiers, cyprès, agaves, lauriers
        rng = random.Random(7)
        b.palm(-3.5, -3.2, 6.5, (0.8, -0.3), seed=1)
        b.palm(19.5, -3.6, 7.2, (-0.6, -0.4), seed=2)
        b.palm(-6.0, 7.0, 5.8, (0.4, 0.5), seed=3)
        for (cx_, cz_, ch) in ((12.5, -3.0, 6.0), (14.0, -3.3, 6.8), (24.0, 6.0, 7.5), (-9.0, 16.0, 7.0), (14.0, 20.0, 6.4)):
            b.cypress(cx_, cz_, ch)
        for (ax_, az_, sz) in ((2.0, -1.5, 0.8), (4.0, -2.4, 0.6), (9.5, -1.2, 0.9), (17.0, -1.6, 0.7), (-1.0, -4.5, 0.75)):
            b.agave(ax_, az_, sz, seed=int(ax_ * 10))
        for (lx, lz) in ((-8, -2), (22, -2), (-3, 15), (20, 15)):
            b.sphere("herbe", lx, 0.9, lz, 1.1, (0.32, 0.42, 0.3), lat=5, lon=8, sy=0.8)
        # villas voisines : enduits ocre/rose, toits de tuiles
        for (nx, nw, nh, tex) in ((-26, 12, 8, "crepi_rose"), (-10, 7, 6, "crepi"), (28, 9, 7, "crepi_rose"), (40, 10, 9, "crepi")):
            for (z0, z1, dark) in ((10.0, 22.0, 0.42),):
                x0, x1 = (nx, nx + nw) if z0 > 0 else (nx - 1, nx + nw + 3)
                hh = nh if z0 > 0 else nh + 2
                b.box(tex, x0, 0.0, z0, x1, hh, z1, (dark, dark * 0.95, dark * 0.9))
                zm = (z0 + z1) / 2
                b.quad("tuiles", (x0 - 0.3, hh, z0 - 0.3), (x1 + 0.3, hh, z0 - 0.3), (x1 + 0.3, hh + 1.6, zm), (x0 - 0.3, hh + 1.6, zm),
                       (0, 0.8, -0.6), (dark, dark * 0.9, dark * 0.85))
                b.quad("tuiles", (x0 - 0.3, hh + 1.6, zm), (x1 + 0.3, hh + 1.6, zm), (x1 + 0.3, hh, z1 + 0.3), (x0 - 0.3, hh, z1 + 0.3),
                       (0, 0.8, 0.6), (dark, dark * 0.9, dark * 0.85))
                # fenêtres éclairées (quelques-unes seulement)
                for wx in range(int(x0) + 1, int(x1) - 1, 3):
                    lit = rng.random() < 0.25
                    fz = z0 - 0.02 if z0 > 0 else z1 + 0.02
                    nrm = (0, 0, -1) if z0 > 0 else (0, 0, 1)
                    b.quad("neon" if lit else "volet", (wx, 2.0, fz), (wx + 0.9, 2.0, fz), (wx + 0.9, 3.3, fz), (wx, 3.3, fz), nrm,
                           (0.9, 0.7, 0.4) if lit else (dark + 0.2, dark + 0.25, dark + 0.2))
        # lampadaire
        b.cyl("metal", 3.2, 0.0, -7.0, 0.07, 5.0, 6, (0.35, 0.36, 0.4))
        b.box("metal", 3.0, 4.95, -7.1, 3.9, 5.05, -6.9, (0.35, 0.36, 0.4))
        b.box("neon", 3.35, 4.88, -7.08, 3.85, 4.95, -6.92, (1.0, 0.85, 0.55))
        self.anchors["lamp_pos"] = Vec3(3.6, 4.8, -7.0)
        # voiture garée
        self._car(b, 9.5, -9.4)
        self.anchors["car_pos"] = Vec3(9.5, 0.0, -9.4)
        b.build(parent=self.exterior_root)
        self.builders["exterieur"] = b
        # lumières extérieures
        lamp = LightSource((3.6, 4.7, -7.0), (1.0, 0.8, 0.5), 1.6, 12.0, kind="flicker", name="lampadaire")
        self.anchors["lamp_light"] = lamp
        self.lights.append(lamp)

    def _car(self, b, cx, cz):
        col = (0.16, 0.18, 0.22)
        b.obox("metal", cx, 0.35, cz, 4.1, 0.65, 1.75, 0, col)
        b.obox("metal", cx - 0.2, 1.0, cz, 2.2, 0.55, 1.6, 0, col)
        b.obox("vitre", cx - 0.2, 1.02, cz, 2.18, 0.5, 1.62, 0, (0.4, 0.45, 0.5))
        for wx in (-1.3, 1.3):
            for wz in (-0.9, 0.9):
                b.cyl("beton", cx + wx, 0.0, cz + wz, 0.33, 0.28, 8, (0.1, 0.1, 0.1), cap=True)
        b.colliders.append((cx - 2.1, 0, cz - 0.9, cx + 2.1, 1.5, cz + 0.9))

    # ------------------------------------------------------------------
    # Services physiques
    # ------------------------------------------------------------------
    def _index_colliders(self):
        self._cgrid = {}
        for c in self.colliders:
            ix0, ix1 = int(math.floor(c[0] / 2.0)), int(math.floor(c[3] / 2.0))
            iz0, iz1 = int(math.floor(c[2] / 2.0)), int(math.floor(c[5] / 2.0))
            for ix in range(ix0, ix1 + 1):
                for iz in range(iz0, iz1 + 1):
                    self._cgrid.setdefault((ix, iz), []).append(c)

    def _near(self, x, z, r):
        ix0, ix1 = int(math.floor((x - r) / 2.0)), int(math.floor((x + r) / 2.0))
        iz0, iz1 = int(math.floor((z - r) / 2.0)), int(math.floor((z + r) / 2.0))
        seen = set()
        for ix in range(ix0, ix1 + 1):
            for iz in range(iz0, iz1 + 1):
                for c in self._cgrid.get((ix, iz), ()):
                    if id(c) not in seen:
                        seen.add(id(c))
                        yield c
        for c in self.dyn_colliders.values():
            yield c

    def blocked(self, x, z, y, radius, height, step=0.35):
        """Vrai si un cylindre (x,z,rayon, y..y+height) touche un collider."""
        top = y + height
        for c in self._near(x, z, radius + 0.2):
            if c[4] <= y + step or c[1] >= top:
                continue
            cx = max(c[0], min(x, c[3]))
            cz = max(c[2], min(z, c[5]))
            if (cx - x) ** 2 + (cz - z) ** 2 < radius * radius:
                return True
        return False

    def move(self, x, z, dx, dz, y, radius=config.PLAYER_RADIUS, height=config.PLAYER_HEIGHT):
        """Déplacement avec glissement le long des murs."""
        nx = x + dx
        if not self.blocked(nx, z, y, radius, height):
            x = nx
        nz = z + dz
        if not self.blocked(x, nz, y, radius, height):
            z = nz
        return x, z

    def ground_height(self, x, z, y, step=0.55):
        """Hauteur de sol sous (x,z) : surface la plus haute pas plus haute que y+step."""
        best = None
        for s in self.surfaces:
            if s.x0 <= x <= s.x1 and s.z0 <= z <= s.z1:
                h = s.height(x, z)
                if h <= y + step and (best is None or h > best):
                    best = h
        return best

    def level_at(self, y):
        if y < -1.5:
            return -1
        if y < 2.5:
            return 0
        if y < 5.5:
            return 1
        return 2

    def zone_at(self, x, z, y):
        lvl = self.level_at(y)
        if lvl == 0:
            for (x0, z0, x1, z1, name) in getattr(self, "extra_zones", ()):
                if x0 <= x <= x1 and z0 <= z <= z1:
                    return name
        if lvl == 0 and z > 12.0 and 6.0 <= x <= 8.0:
            return "escalier_cave"
        if lvl == 0 and (x < -0.3 or x > 16.3 or z < -0.3 or z > 12.3):
            return "dehors"
        if lvl == 0:
            return "rdc"
        if lvl == 1:
            return "etage"
        if lvl == 2:
            return "grenier"
        return "sous_sol"

    def room_at(self, x, z, y):
        lvl = self.level_at(y)
        for r in self.rooms.values():
            if r.level == lvl and r.contains(x, z):
                return r
        return None

    def ray_blocked(self, a, b, y_a=None, samples=None):
        """Test de visibilité segment a->b (Vec3) contre les murs (hauteur ~1.2 m)."""
        return self.wall_count(a, b) > 0

    def wall_count(self, a, b):
        """Nombre de murs/colliders hauts entre a et b (utilisé pour l'occlusion)."""
        ax, ay, az = a[0], a[1], a[2]
        bx, by, bz = b[0], b[1], b[2]
        dx, dz = bx - ax, bz - az
        dist = math.hypot(dx, dz)
        if dist < 0.01:
            return 0
        n = int(dist / 0.35) + 1
        count = 0
        last = None
        for i in range(1, n):
            t = i / n
            x, z, y = ax + dx * t, az + dz * t, ay + (by - ay) * t
            hit = None
            for c in self._near(x, z, 0.1):
                if c[1] > y + 0.4 or c[4] < y - 0.4:
                    continue
                if c[4] - c[1] < 1.2:
                    continue
                if c[0] <= x <= c[3] and c[2] <= z <= c[5]:
                    hit = c
                    break
            if hit is not None and hit is not last:
                count += 1
            last = hit
        # niveaux différents : plafond/plancher
        if abs(ay - by) > 2.0:
            count += 2
        return count

    def nearest_door(self, pos, max_dist=1.2):
        best, bd = None, max_dist
        for d in self.doors.values():
            if abs(d.pos[1] - pos[1]) > 2.0:
                continue
            dist = math.hypot(d.pos[0] - pos[0], d.pos[2] - pos[2])
            if dist < bd:
                best, bd = d, dist
        return best

    def set_level_visibility(self, level):
        if getattr(self, "outside_view", False):
            for root in self.level_roots.values():
                root.enabled = True
            if self.exterior_root:
                self.exterior_root.enabled = True
            return
        for lvl, root in self.level_roots.items():
            if lvl == -1:
                root.enabled = level in (-1, 0)
            elif lvl == 2:
                root.enabled = level in (1, 2)
            elif lvl == 0:
                root.enabled = level in (-1, 0, 1)
            else:
                root.enabled = level in (0, 1, 2)
        if self.exterior_root:
            self.exterior_root.enabled = level >= 0


# ---------------------------------------------------------------------------
# Navigation (grille + A*)
# ---------------------------------------------------------------------------
class NavGrid:
    """Grille de navigation par niveau + liens d'escalier, A* simplifié."""

    CELL = 0.3

    def __init__(self, house, radius=0.26):
        self.house = house
        self.radius = radius
        self.cell = NavGrid.CELL
        self.cells = {}            # (lvl, ix, iz) -> True si libre
        self.links = {}            # nœud -> [(nœud, coût)]
        self.stair_enabled = {"cave": False, "rdc_1": True, "1_grenier": True}
        self._build()

    def key(self, lvl, x, z):
        return (lvl, int(round(x / self.cell)), int(round(z / self.cell)))

    def pos(self, node):
        return node[1] * self.cell, node[2] * self.cell

    def _build(self):
        h = self.house
        c = self.cell
        for lvl in (0, 1, 2, -1):
            y0 = LEVEL_Y[lvl]
            rooms = [r for r in h.rooms.values() if r.level == lvl]
            for r in rooms:
                if r.id == "cave_acces":
                    continue
                ix0, ix1 = int(math.ceil(r.x0 / c)), int(math.floor(r.x1 / c))
                iz0, iz1 = int(math.ceil(r.z0 / c)), int(math.floor(r.z1 / c))
                for ix in range(ix0, ix1 + 1):
                    for iz in range(iz0, iz1 + 1):
                        x, z = ix * c, iz * c
                        gh = h.ground_height(x, z, y0 + 0.1, 0.2)
                        if gh is None or abs(gh - y0) > 0.15:
                            continue
                        if lvl == 2 and not self._attic_ok(x, z):
                            continue
                        if not h.blocked_static(x, z, y0, self.radius, 1.6):
                            self.cells[(lvl, ix, iz)] = True
        # passages hors des rectangles de pièce (portes, couloirs entre pièces)
        for lvl in (0, 1):
            y0 = LEVEL_Y[lvl]
            for ix in range(-1, int(16 / c) + 2):
                for iz in range(-1, int(12 / c) + 2):
                    k = (lvl, ix, iz)
                    if k in self.cells:
                        continue
                    x, z = ix * c, iz * c
                    if not (0.2 < x < 15.8 and 0.2 < z < 11.8):
                        continue
                    gh = h.ground_height(x, z, y0 + 0.1, 0.2)
                    if gh is None or abs(gh - y0) > 0.15:
                        continue
                    if not h.blocked_static(x, z, y0, self.radius, 1.6):
                        self.cells[k] = True
        self._link_stairs()

    def _attic_ok(self, x, z):
        return 0.5 < z < 11.5

    def _link_stairs(self):
        c = self.cell
        for st in STAIRS:
            sid = st["id"]
            lo, hi = st["lo"], st["hi"]
            xm = (st["x0"] + st["x1"]) / 2
            n = int(abs(st["zb"] - st["za"]) / c)
            chain = []
            for i in range(n + 1):
                t = i / n
                z = st["za"] + (st["zb"] - st["za"]) * t
                chain.append((("stair", sid, i), xm, z, st["ya"] + (st["yb"] - st["ya"]) * t))
            # liaison : bas
            bottom_lvl = lo
            top_lvl = hi
            dz = 1 if st["zb"] > st["za"] else -1
            bnode = self._nearest_cell(bottom_lvl, xm, st["za"] - dz * 0.5)
            tnode = self._nearest_cell(top_lvl, xm, st["zb"] + dz * 0.5)
            if bnode is None or tnode is None:
                continue
            prev = bnode
            for (node, x, z, y) in chain:
                self.cells[node] = True
                self.links.setdefault(prev, []).append((node, c * 1.2, sid))
                self.links.setdefault(node, []).append((prev, c * 1.2, sid))
                prev = node
            self.links.setdefault(prev, []).append((tnode, c * 1.2, sid))
            self.links.setdefault(tnode, []).append((prev, c * 1.2, sid))
            self.stair_coords = getattr(self, "stair_coords", {})
            self.stair_coords[sid] = chain

    def _nearest_cell(self, lvl, x, z, rad=6):
        k0 = self.key(lvl, x, z)
        best, bd = None, 1e9
        for dx in range(-rad, rad + 1):
            for dz in range(-rad, rad + 1):
                k = (lvl, k0[1] + dx, k0[2] + dz)
                if k in self.cells:
                    d = dx * dx + dz * dz
                    if d < bd:
                        best, bd = k, d
        return best

    def node_pos3(self, node):
        if node[0] == "stair":
            for (n, x, z, y) in self.stair_coords[node[1]]:
                if n == node:
                    return Vec3(x, y, z)
        lvl, ix, iz = node
        return Vec3(ix * self.cell, LEVEL_Y[lvl], iz * self.cell)

    def neighbors(self, node, allow):
        if node[0] == "stair":
            out = []
            for (n, cost, sid) in self.links.get(node, ()):
                if allow(sid):
                    out.append((n, cost))
            return out
        lvl, ix, iz = node
        out = []
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                if dx == 0 and dz == 0:
                    continue
                k = (lvl, ix + dx, iz + dz)
                if k not in self.cells:
                    continue
                if dx != 0 and dz != 0:
                    if (lvl, ix + dx, iz) not in self.cells or (lvl, ix, iz + dz) not in self.cells:
                        continue
                cost = self.cell * (1.414 if dx and dz else 1.0)
                if self._blocked_dyn(k):
                    continue
                out.append((k, cost))
        for (n, cost, sid) in self.links.get(node, ()):
            if allow(sid):
                out.append((n, cost))
        return out

    def _blocked_dyn(self, k):
        for (x0, z0, x1, z1, lvl) in self.house.nav_blockers.values():
            if k[0] == lvl:
                x, z = k[1] * self.cell, k[2] * self.cell
                if x0 <= x <= x1 and z0 <= z <= z1:
                    return True
        return False

    def find_path(self, start3, goal3, start_level, goal_level, allow_stairs=None, max_nodes=9000):
        """A* : retourne une liste de Vec3 (chemin) ou []."""
        allow = allow_stairs or (lambda sid: self.stair_enabled.get(sid, True))
        s = self._nearest_cell(start_level, start3[0], start3[2])
        g = self._nearest_cell(goal_level, goal3[0], goal3[2])
        if s is None or g is None:
            return []
        gp = self.node_pos3(g)

        def hcost(n):
            p = self.node_pos3(n)
            return abs(p[0] - gp[0]) + abs(p[2] - gp[2]) + abs(p[1] - gp[1]) * 1.5

        openh = [(hcost(s), 0.0, s)]
        came = {}
        gscore = {s: 0.0}
        closed = set()
        count = 0
        while openh and count < max_nodes:
            _, gs, cur = heapq.heappop(openh)
            if cur in closed:
                continue
            closed.add(cur)
            count += 1
            if cur == g:
                path = [cur]
                while cur in came:
                    cur = came[cur]
                    path.append(cur)
                path.reverse()
                return self._smooth([self.node_pos3(n) for n in path], path)
            for (n, cost) in self.neighbors(cur, allow):
                ng = gs + cost
                if ng < gscore.get(n, 1e9):
                    gscore[n] = ng
                    came[n] = cur
                    heapq.heappush(openh, (ng + hcost(n), ng, n))
        return []

    def _smooth(self, pts, nodes):
        """Supprime les points intermédiaires alignés (même niveau, ligne de vue libre)."""
        if len(pts) <= 2:
            return pts
        out = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1:
                if nodes[i][0] != "stair" and nodes[j][0] != "stair" and nodes[i][0] == nodes[j][0] and self._los(nodes[i], nodes[j]):
                    break
                j -= 1
            out.append(pts[j])
            i = j
        return out

    def _los(self, a, b):
        ax, az = a[1], a[2]
        bx, bz = b[1], b[2]
        n = int(max(abs(bx - ax), abs(bz - az))) + 1
        for i in range(1, n):
            t = i / n
            k = (a[0], int(round(ax + (bx - ax) * t)), int(round(az + (bz - az) * t)))
            if k not in self.cells or self._blocked_dyn(k):
                return False
        return True

    def random_cell(self, level, rng=random):
        cells = [k for k in self.cells if k[0] == level]
        return self.node_pos3(rng.choice(cells)) if cells else None

    def cells_in_room(self, room):
        out = []
        for k in self.cells:
            if k[0] == room.level:
                x, z = k[1] * self.cell, k[2] * self.cell
                if room.contains(x, z):
                    out.append(self.node_pos3(k))
        return out


def _blocked_static(self, x, z, y, radius, height, step=0.35):
    top = y + height
    ix0, ix1 = int(math.floor((x - radius) / 2.0)), int(math.floor((x + radius) / 2.0))
    iz0, iz1 = int(math.floor((z - radius) / 2.0)), int(math.floor((z + radius) / 2.0))
    for ix in range(ix0, ix1 + 1):
        for iz in range(iz0, iz1 + 1):
            for c in self._cgrid.get((ix, iz), ()):
                if c[4] <= y + step or c[1] >= top:
                    continue
                cx = max(c[0], min(x, c[3]))
                cz = max(c[2], min(z, c[5]))
                if (cx - x) ** 2 + (cz - z) ** 2 < radius * radius:
                    return True
    return False


House.blocked_static = _blocked_static
