"""Construction de la géométrie : constructeur de maillages + bibliothèque de meubles.

Toute la géométrie statique est accumulée dans un :class:`MeshBuilder` puis fusionnée
en un seul maillage par texture (peu d'appels de rendu). Les UV sont calculées en
mètres réels pour que les textures aient la même échelle partout.

Convention de repère : x = est, y = haut, z = nord. La façade (porte d'entrée) est en z = 0.
"""
import math

from ursina import Entity, Mesh, Vec3
from panda3d.core import TransparencyAttrib

from shaders import horror_shader
from texture_generator import textures

# Taille (en mètres) couverte par une répétition de chaque texture
TILE = {
    "crepi": 2.5, "papier_peint": 1.4, "papier_chambre": 1.4, "papier_couloir": 1.4,
    "platre": 2.0, "plafond": 2.0, "parquet": 2.0, "carrelage": 1.0, "moquette": 1.5,
    "beton": 2.0, "asphalte": 3.0, "herbe": 2.0, "porte": 1.0, "planches": 1.0,
    "volet": 1.0, "bois_meuble": 1.0, "tissu": 1.0, "marbre": 1.0, "email": 1.0,
    "metal": 1.0, "papier": 1.0, "drap": 1.0, "rideau": 1.0, "eau_noire": 1.0,
    "miroir": 1.0, "miroir_brise": 1.0, "vitre": 1.0, "neon": 1.0, "ecran_noir": 1.0,
}
TRANSPARENT = {"vitre", "empreintes", "mains", "griffures", "taches", "sel", "sel_brise",
               "cercle_sombre", "silhouette", "lueur", "poussiere", "goutte"}


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a):
    return math.sqrt(_dot(a, a))


def _norm(a):
    l = _len(a)
    return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-9 else (0.0, 1.0, 0.0)


def _rot_y(p, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (p[0] * c + p[2] * s, p[1], -p[0] * s + p[2] * c)


class MeshBuilder:
    """Accumule des quads/triangles groupés par texture."""

    def __init__(self, name="static"):
        self.name = name
        self.groups = {}
        self.colliders = []     # (x0, y0, z0, x1, y1, z1)
        self.entities = []

    # --- primitives --------------------------------------------------------
    def _grp(self, tex):
        g = self.groups.get(tex)
        if g is None:
            g = {"v": [], "u": [], "n": [], "c": []}
            self.groups[tex] = g
        return g

    def quad(self, tex, p0, p1, p2, p3, normal, col=(1, 1, 1), tile=None, uv_off=(0.0, 0.0)):
        """Quad p0..p3 ; p0->p1 = axe u, p0->p3 = axe v. `normal` = normale voulue."""
        g = self._grp(tex)
        t = tile or TILE.get(tex, 1.0)
        du = _len(_sub(p1, p0)) / t
        dv = _len(_sub(p3, p0)) / t
        uv = [(uv_off[0], uv_off[1]), (uv_off[0] + du, uv_off[1]),
              (uv_off[0] + du, uv_off[1] + dv), (uv_off[0], uv_off[1] + dv)]
        pts = [p0, p1, p2, p3]
        front = _dot(_cross(_sub(p1, p0), _sub(p2, p0)), normal) < 0
        order = (0, 1, 2, 0, 2, 3) if front else (0, 2, 1, 0, 3, 2)
        a = col if len(col) == 4 else (col[0], col[1], col[2], 1.0)
        for i in order:
            g["v"].append(pts[i])
            g["u"].append(uv[i])
            g["n"].append(normal)
            g["c"].append(a)

    def tri(self, tex, p0, p1, p2, normal, col=(1, 1, 1), tile=None):
        g = self._grp(tex)
        t = tile or TILE.get(tex, 1.0)
        pts = [p0, p1, p2]
        front = _dot(_cross(_sub(p1, p0), _sub(p2, p0)), normal) < 0
        order = (0, 1, 2) if front else (0, 2, 1)
        a = col if len(col) == 4 else (col[0], col[1], col[2], 1.0)
        # UV planaires
        n = normal
        for i in order:
            p = pts[i]
            if abs(n[1]) > 0.7:
                uv = (p[0] / t, p[2] / t)
            elif abs(n[0]) > 0.7:
                uv = (p[2] / t, p[1] / t)
            else:
                uv = (p[0] / t, p[1] / t)
            g["v"].append(p)
            g["u"].append(uv)
            g["n"].append(normal)
            g["c"].append(a)

    # --- boîtes ------------------------------------------------------------
    def box(self, tex, x0, y0, z0, x1, y1, z1, col=(1, 1, 1), tile=None, collide=False,
            skip=(), tex_top=None, tex_bottom=None, tex_sides=None):
        """Boîte alignée sur les axes. skip : ensemble parmi {'+x','-x','+y','-y','+z','-z'}."""
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if z1 < z0:
            z0, z1 = z1, z0
        ts = tex_sides or tex
        tt = tex_top or tex
        tb = tex_bottom or tex
        if "+y" not in skip:
            self.quad(tt, (x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (0, 1, 0), col, tile)
        if "-y" not in skip:
            self.quad(tb, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0), col, tile)
        if "-z" not in skip:
            self.quad(ts, (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (0, 0, -1), col, tile)
        if "+z" not in skip:
            self.quad(ts, (x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (0, 0, 1), col, tile)
        if "-x" not in skip:
            self.quad(ts, (x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (-1, 0, 0), col, tile)
        if "+x" not in skip:
            self.quad(ts, (x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0), (1, 0, 0), col, tile)
        if collide:
            self.colliders.append((x0, y0, z0, x1, y1, z1))

    def obox(self, tex, cx, y0, cz, sx, sy, sz, rot=0.0, col=(1, 1, 1), tile=None,
             collide=False, skip=()):
        """Boîte orientée (rotation autour de Y en degrés). (cx, cz) = centre au sol."""
        if rot % 90 == 0 and int(rot) % 180 == 0:
            self.box(tex, cx - sx / 2, y0, cz - sz / 2, cx + sx / 2, y0 + sy, cz + sz / 2, col, tile, collide, skip)
            return
        if rot % 90 == 0:
            self.box(tex, cx - sz / 2, y0, cz - sx / 2, cx + sz / 2, y0 + sy, cz + sx / 2, col, tile, collide, skip)
            return
        hx, hz = sx / 2, sz / 2
        loc = [(-hx, 0, -hz), (hx, 0, -hz), (hx, 0, hz), (-hx, 0, hz)]
        pts = []
        for (lx, _, lz) in loc:
            r = _rot_y((lx, 0, lz), rot)
            pts.append((cx + r[0], cz + r[2]))
        y1 = y0 + sy
        b = [(p[0], y0, p[1]) for p in pts]
        t = [(p[0], y1, p[1]) for p in pts]
        self.quad(tex, t[0], t[1], t[2], t[3], (0, 1, 0), col, tile)
        if "-y" not in skip:
            self.quad(tex, b[0], b[1], b[2], b[3], (0, -1, 0), col, tile)
        for i in range(4):
            j = (i + 1) % 4
            e = _sub(b[j], b[i])
            n = _norm((-e[2], 0, e[0]))
            # la normale doit pointer vers l'extérieur
            mid = ((b[i][0] + b[j][0]) / 2 - cx, 0, (b[i][2] + b[j][2]) / 2 - cz)
            if _dot(n, mid) < 0:
                n = (-n[0], 0, -n[2])
            self.quad(tex, b[i], b[j], t[j], t[i], n, col, tile)
        if collide:
            xs = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            self.colliders.append((min(xs), y0, min(zs), max(xs), y1, max(zs)))

    def cyl(self, tex, cx, y0, cz, r, h, seg=8, col=(1, 1, 1), tile=None, collide=False, cap=True):
        pts = [(cx + math.cos(2 * math.pi * i / seg) * r, cz + math.sin(2 * math.pi * i / seg) * r) for i in range(seg)]
        y1 = y0 + h
        for i in range(seg):
            j = (i + 1) % seg
            a, bq = pts[i], pts[j]
            mid = ((a[0] + bq[0]) / 2 - cx, 0, (a[1] + bq[1]) / 2 - cz)
            n = _norm(mid)
            self.quad(tex, (a[0], y0, a[1]), (bq[0], y0, bq[1]), (bq[0], y1, bq[1]), (a[0], y1, a[1]), n, col, tile)
            if cap:
                self.tri(tex, (cx, y1, cz), (a[0], y1, a[1]), (bq[0], y1, bq[1]), (0, 1, 0), col, tile)
        if collide:
            self.colliders.append((cx - r, y0, cz - r, cx + r, y1, cz + r))

    def sphere(self, tex, cx, cy, cz, r, col=(1, 1, 1), lat=6, lon=10, sy=1.0, sx=1.0, tile=None):
        def pt(a, b):
            return (cx + math.cos(b) * math.sin(a) * r * sx, cy + math.cos(a) * r * sy, cz + math.sin(b) * math.sin(a) * r * sx)
        for i in range(lat):
            a0 = math.pi * i / lat
            a1 = math.pi * (i + 1) / lat
            for j in range(lon):
                b0 = 2 * math.pi * j / lon
                b1 = 2 * math.pi * (j + 1) / lon
                p00, p01, p10, p11 = pt(a0, b0), pt(a0, b1), pt(a1, b0), pt(a1, b1)
                n = _norm(((p00[0] + p11[0]) / 2 - cx, (p00[1] + p11[1]) / 2 - cy, (p00[2] + p11[2]) / 2 - cz))
                if i == 0:
                    self.tri(tex, p00, p11, p10, n, col, tile)
                elif i == lat - 1:
                    self.tri(tex, p00, p01, p10, n, col, tile)
                else:
                    self.quad(tex, p00, p01, p11, p10, n, col, tile)

    # --- murs --------------------------------------------------------------
    def wall(self, axis, a0, a1, fixed, y0, y1, thick=0.2, tex_neg="papier_peint", tex_pos="papier_peint",
             col_neg=(1, 1, 1), col_pos=(1, 1, 1), cap_tex="platre", collide=True,
             cap_a=True, cap_b=True, cap_bottom=False, cap_top=True):
        """Mur plein le long de `axis` ('x' ou 'z') de a0 à a1, centré sur `fixed`.

        tex_neg = face côté coordonnée perpendiculaire inférieure, tex_pos = côté supérieur.
        """
        h = thick / 2
        if axis == "x":
            z0, z1 = fixed - h, fixed + h
            self.quad(tex_neg, (a0, y0, z0), (a1, y0, z0), (a1, y1, z0), (a0, y1, z0), (0, 0, -1), col_neg)
            self.quad(tex_pos, (a1, y0, z1), (a0, y0, z1), (a0, y1, z1), (a1, y1, z1), (0, 0, 1), col_pos)
            if cap_top:
                self.quad(cap_tex, (a0, y1, z0), (a1, y1, z0), (a1, y1, z1), (a0, y1, z1), (0, 1, 0), (0.9, 0.9, 0.9))
            if cap_bottom:
                self.quad(cap_tex, (a0, y0, z0), (a1, y0, z0), (a1, y0, z1), (a0, y0, z1), (0, -1, 0), (0.9, 0.9, 0.9))
            if cap_a:
                self.quad(cap_tex, (a0, y0, z1), (a0, y0, z0), (a0, y1, z0), (a0, y1, z1), (-1, 0, 0), (0.9, 0.9, 0.9))
            if cap_b:
                self.quad(cap_tex, (a1, y0, z0), (a1, y0, z1), (a1, y1, z1), (a1, y1, z0), (1, 0, 0), (0.9, 0.9, 0.9))
            if collide:
                self.colliders.append((a0, y0, z0, a1, y1, z1))
        else:
            x0, x1 = fixed - h, fixed + h
            self.quad(tex_neg, (x0, y0, a1), (x0, y0, a0), (x0, y1, a0), (x0, y1, a1), (-1, 0, 0), col_neg)
            self.quad(tex_pos, (x1, y0, a0), (x1, y0, a1), (x1, y1, a1), (x1, y1, a0), (1, 0, 0), col_pos)
            if cap_top:
                self.quad(cap_tex, (x0, y1, a0), (x1, y1, a0), (x1, y1, a1), (x0, y1, a1), (0, 1, 0), (0.9, 0.9, 0.9))
            if cap_bottom:
                self.quad(cap_tex, (x0, y0, a0), (x1, y0, a0), (x1, y0, a1), (x0, y0, a1), (0, -1, 0), (0.9, 0.9, 0.9))
            if cap_a:
                self.quad(cap_tex, (x0, y0, a0), (x1, y0, a0), (x1, y1, a0), (x0, y1, a0), (0, 0, -1), (0.9, 0.9, 0.9))
            if cap_b:
                self.quad(cap_tex, (x1, y0, a1), (x0, y0, a1), (x0, y1, a1), (x1, y1, a1), (0, 0, 1), (0.9, 0.9, 0.9))
            if collide:
                self.colliders.append((x0, y0, a0, x1, y1, a1))

    def wall_openings(self, axis, a0, a1, fixed, y0, y1, openings, thick=0.2, **kw):
        """Mur avec ouvertures. openings : liste de (centre, largeur, bas, haut) relatifs à y0.

        Une porte a bas = 0 ; une fenêtre a un rebord > 0.
        """
        ops = sorted(openings, key=lambda o: o[0])
        cursor = a0
        for (c, w, lo, hi) in ops:
            s, e = c - w / 2, c + w / 2
            if s > cursor + 1e-4:
                self.wall(axis, cursor, s, fixed, y0, y1, thick, cap_a=True, cap_b=True, **kw)
            if lo > 0:
                self.wall(axis, s, e, fixed, y0, y0 + lo, thick, cap_a=False, cap_b=False, **kw)
            if hi < (y1 - y0) - 1e-4:
                self.wall(axis, s, e, fixed, y0 + hi, y1, thick, cap_a=False, cap_b=False, cap_bottom=True, **kw)
            cursor = e
        if cursor < a1 - 1e-4:
            self.wall(axis, cursor, a1, fixed, y0, y1, thick, cap_a=True, cap_b=True, **kw)

    def build(self, parent=None, shader=horror_shader, emit=0.0):
        """Crée les entités Ursina (une par texture)."""
        ents = []
        for tex, g in self.groups.items():
            if not g["v"]:
                continue
            m = Mesh(vertices=g["v"], uvs=g["u"], normals=g["n"], colors=g["c"], static=True)
            e = Entity(model=m, texture=textures.get(tex), shader=shader, parent=parent)
            e.set_shader_input("emit", float(emit))
            if tex in TRANSPARENT:
                e.setTransparency(TransparencyAttrib.M_alpha)
                e.set_depth_write(False)
                e.set_bin("fixed", 20)
            ents.append(e)
        self.entities = ents
        return ents


# ---------------------------------------------------------------------------
# Entités animées
# ---------------------------------------------------------------------------
def make_part(parent, tex, size, pos, col=(1, 1, 1), tile=1.0, emit=0.0):
    """Petite boîte indépendante (volets mobiles, portes d'armoire, ...).

    Retourne l'entité dont l'origine est au centre de la boîte.
    """
    b = MeshBuilder("part")
    sx, sy, sz = size
    b.box(tex, -sx / 2, -sy / 2, -sz / 2, sx / 2, sy / 2, sz / 2, col, tile)
    ents = b.build(parent=None, emit=emit)
    root = Entity(parent=parent, position=pos)
    for e in ents:
        e.parent = root
    return root


class HingedPart:
    """Pièce articulée autour d'un axe vertical (porte, volet d'armoire...).

    Le pivot est au bord de la pièce. open_angle en degrés (positif/négatif = sens).
    """

    def __init__(self, parent, hinge_pos, size, tex="porte", col=(1, 1, 1), open_angle=-100.0,
                 side="+x", rot_y=0.0, tile=1.0, tex_back=None):
        """size = (largeur le long de `side`, hauteur, épaisseur)."""
        self.pivot = Entity(parent=parent, position=hinge_pos, rotation_y=rot_y)
        w, h, t = size
        b = MeshBuilder("hinged")
        if side == "+x":
            b.box(tex, 0, 0, -t / 2, w, h, t / 2, col, tile)
        else:
            b.box(tex, -w, 0, -t / 2, 0, h, t / 2, col, tile)
        for e in b.build(parent=self.pivot):
            pass
        self.rot_y0 = rot_y
        self.open_angle = open_angle
        self.is_open = False
        self.size = size
        self.hinge = hinge_pos

    def set_open(self, state, duration=0.7, instant=False):
        self.is_open = state
        target = self.rot_y0 + (self.open_angle if state else 0.0)
        if instant:
            self.pivot.rotation_y = target
        else:
            self.pivot.animate("rotation_y", target, duration=duration, curve=_curve())


def _curve():
    from ursina import curve
    return curve.in_out_sine


class SlidingPart:
    """Tiroir : glisse sur un axe local."""

    def __init__(self, parent, pos, size, tex="bois_meuble", col=(1, 1, 1), travel=(0, 0, 0.35)):
        self.root = make_part(parent, tex, size, pos, col)
        self.closed = Vec3(*pos)
        self.travel = Vec3(*travel)
        self.is_open = False

    def set_open(self, state, duration=0.4):
        self.is_open = state
        target = self.closed + (self.travel if state else Vec3(0, 0, 0))
        self.root.animate_position(target, duration=duration)


# ---------------------------------------------------------------------------
# Bibliothèque de meubles (statiques). Chaque fonction ajoute au MeshBuilder.
# y0 = altitude du sol de la pièce.
# ---------------------------------------------------------------------------
WOOD = (0.85, 0.8, 0.75)
DARKWOOD = (0.55, 0.5, 0.45)


def sofa(b, cx, cz, rot, y0, length=2.0, depth=0.9):
    b.obox("tissu", cx, y0, cz, length, 0.42, depth, rot, (1, 1, 1), collide=True)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    # dossier (côté -z local)
    off = (0.0, -(depth / 2 - 0.12))
    wx = cx + off[0] * ca + off[1] * sa
    wz = cz - off[0] * sa + off[1] * ca
    b.obox("tissu", wx, y0 + 0.42, wz, length, 0.5, 0.24, rot, (0.9, 0.9, 0.9))
    for s in (-1, 1):
        ox = s * (length / 2 - 0.12)
        ax = cx + ox * ca
        az = cz - ox * sa
        b.obox("tissu", ax, y0 + 0.42, az, 0.24, 0.26, depth, rot, (0.85, 0.85, 0.85))
    for s in (-0.5, 0.5):
        ox = s * (length / 2 - 0.1)
        px = cx + ox * ca + 0.05 * sa
        pz = cz - ox * sa + 0.05 * ca
        b.obox("tissu", px, y0 + 0.42, pz, length / 2 - 0.3, 0.14, depth - 0.3, rot, (1.05, 1.05, 1.05))


def armchair(b, cx, cz, rot, y0):
    sofa(b, cx, cz, rot, y0, length=0.95, depth=0.9)


def table(b, cx, cz, y0, sx, sz, h=0.75, tex="bois_meuble", col=WOOD, rot=0.0, collide=True):
    b.obox(tex, cx, y0 + h - 0.05, cz, sx, 0.05, sz, rot, col, collide=False)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for lx in (-1, 1):
        for lz in (-1, 1):
            ox, oz = lx * (sx / 2 - 0.06), lz * (sz / 2 - 0.06)
            px = cx + ox * ca + oz * sa
            pz = cz - ox * sa + oz * ca
            b.obox(tex, px, y0, pz, 0.05, h - 0.05, 0.05, rot, col)
    if collide:
        b.obox(tex, cx, y0, cz, sx, h, sz, rot, col, collide=True, skip=("+x", "-x", "+y", "-y", "+z", "-z"))


def chair(b, cx, cz, y0, rot=0.0, fallen=False, col=WOOD):
    if fallen:
        b.obox("bois_meuble", cx, y0, cz, 0.42, 0.42, 0.05, rot, col)               # assise couchée
        b.obox("bois_meuble", cx + 0.2, y0, cz, 0.05, 0.45, 0.42, rot + 90, col)
        b.obox("bois_meuble", cx, y0 + 0.05, cz + 0.25, 0.05, 0.42, 0.05, rot, col)
        b.colliders.append((cx - 0.45, y0, cz - 0.3, cx + 0.45, y0 + 0.45, cz + 0.3))
        return
    b.obox("bois_meuble", cx, y0 + 0.42, cz, 0.42, 0.05, 0.42, rot, col)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    for lx in (-1, 1):
        for lz in (-1, 1):
            ox, oz = lx * 0.18, lz * 0.18
            b.obox("bois_meuble", cx + ox * ca + oz * sa, y0, cz - ox * sa + oz * ca, 0.04, 0.42, 0.04, rot, col)
    ox, oz = 0.0, -0.19
    b.obox("bois_meuble", cx + ox * ca + oz * sa, y0 + 0.47, cz - ox * sa + oz * ca, 0.42, 0.45, 0.04, rot, col)
    b.colliders.append((cx - 0.22, y0, cz - 0.22, cx + 0.22, y0 + 0.9, cz + 0.22))


def bookshelf(b, x0, z0, x1, z1, y0, height=2.1, rng=None, face="+x"):
    """Bibliothèque contre un mur. (x0,z0)-(x1,z1) = emprise. face = direction d'ouverture."""
    import random
    r = rng or random.Random(5)
    b.box("bois_meuble", x0, y0, z0, x1, y0 + height, z1, DARKWOOD, collide=True,
          skip=("+x",) if face == "+x" else ("-x",) if face == "-x" else ("+z",) if face == "+z" else ("-z",))
    shelves = 5
    thick = 0.03
    for s in range(shelves):
        yy = y0 + 0.2 + s * (height - 0.3) / shelves
        if face in ("+x", "-x"):
            fx = x1 if face == "+x" else x0
            d = 0.28 if face == "+x" else -0.28
            xa, xb = sorted((fx - d, fx))
            b.box("bois_meuble", xa, yy, z0 + 0.03, xb, yy + thick, z1 - 0.03, WOOD)
            z = z0 + 0.06
            while z < z1 - 0.1:
                w = r.uniform(0.03, 0.07)
                hgt = r.uniform(0.18, 0.28)
                cc = r.choice([(0.5, 0.2, 0.2), (0.2, 0.3, 0.45), (0.3, 0.4, 0.25), (0.55, 0.45, 0.25), (0.25, 0.22, 0.2)])
                b.box("papier", xa + 0.02, yy + thick, z, xb - 0.04, yy + thick + hgt, z + w, cc)
                z += w + 0.004
                if r.random() < 0.08:
                    z += 0.15
        else:
            fz = z1 if face == "+z" else z0
            d = 0.28 if face == "+z" else -0.28
            za, zb = sorted((fz - d, fz))
            b.box("bois_meuble", x0 + 0.03, yy, za, x1 - 0.03, yy + thick, zb, WOOD)
            x = x0 + 0.06
            while x < x1 - 0.1:
                w = r.uniform(0.03, 0.07)
                hgt = r.uniform(0.18, 0.28)
                cc = r.choice([(0.5, 0.2, 0.2), (0.2, 0.3, 0.45), (0.3, 0.4, 0.25), (0.55, 0.45, 0.25), (0.25, 0.22, 0.2)])
                b.box("papier", x, yy + thick, za + 0.02, x + w, yy + thick + hgt, zb - 0.04, cc)
                x += w + 0.004


def bed(b, cx, cz, rot, y0, w=1.6, l=2.0, col_sheet=(0.95, 0.9, 0.7)):
    b.obox("bois_meuble", cx, y0, cz, w, 0.3, l, rot, DARKWOOD, collide=True)
    b.obox("drap", cx, y0 + 0.3, cz, w - 0.1, 0.18, l - 0.1, rot, col_sheet)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    # tête de lit
    ox, oz = 0.0, -(l / 2)
    b.obox("bois_meuble", cx + ox * ca + oz * sa, y0, cz - ox * sa + oz * ca, w, 1.0, 0.08, rot, DARKWOOD)
    for s in (-0.25, 0.25):
        ox, oz = s * w, -(l / 2) + 0.28
        b.obox("drap", cx + ox * ca + oz * sa, y0 + 0.48, cz - ox * sa + oz * ca, 0.5, 0.12, 0.32, rot, (1, 1, 0.95))


def wardrobe(b, x0, z0, x1, z1, y0, face="+x", height=2.1):
    b.box("bois_meuble", x0, y0, z0, x1, y0 + height, z1, DARKWOOD, collide=True)


def counter(b, x0, z0, x1, z1, y0, h=0.9):
    b.box("bois_meuble", x0, y0, z0, x1, y0 + h - 0.04, z1, (0.6, 0.55, 0.5), collide=True)
    b.box("marbre", x0 - 0.02, y0 + h - 0.04, z0 - 0.02, x1 + 0.02, y0 + h, z1 + 0.02, (1, 1, 1))


def carton(b, cx, cz, y0, size=0.5, rot=0.0, col=(0.7, 0.55, 0.35)):
    b.obox("papier", cx, y0, cz, size, size * 0.9, size, rot, col, collide=True)
    b.obox("papier", cx, y0 + size * 0.9, cz, size * 0.96, 0.02, 0.06, rot, (0.55, 0.45, 0.3))


def covered_furniture(b, cx, cz, y0, sx, sz, h):
    """Meuble recouvert d'un drap."""
    b.obox("drap", cx, y0, cz, sx, h, sz, 0.0, (1, 1, 1), collide=True)
    b.obox("drap", cx, y0 + h, cz, sx * 0.9, 0.06, sz * 0.9, 0.0, (0.9, 0.9, 0.9))


def toilet(b, cx, cz, y0, rot):
    b.obox("email", cx, y0, cz, 0.38, 0.4, 0.5, rot, (1, 1, 0.95), collide=True)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    ox, oz = 0.0, -0.3
    b.obox("email", cx + ox * ca + oz * sa, y0 + 0.4, cz - ox * sa + oz * ca, 0.4, 0.4, 0.18, rot, (1, 1, 0.95))


def sink(b, cx, cz, y0, rot, h=0.85):
    b.obox("email", cx, y0 + h - 0.12, cz, 0.55, 0.12, 0.42, rot, (1, 1, 0.95), collide=False)
    b.obox("email", cx, y0, cz, 0.12, h - 0.12, 0.12, rot, (1, 1, 0.95), collide=True)
    b.obox("metal", cx, y0 + h, cz, 0.04, 0.16, 0.04, rot, (1, 1, 1))


def bathtub(b, cx, cz, y0, rot, l=1.6, w=0.75, water=False):
    b.obox("email", cx, y0 + 0.08, cz, l, 0.5, w, rot, (1, 1, 0.95), collide=True)
    if water:
        b.obox("eau_noire", cx, y0 + 0.55, cz, l - 0.12, 0.01, w - 0.12, rot, (1, 1, 1))


def fridge_body(b, cx, cz, y0, rot=0.0, w=0.7, d=0.7, h=1.7):
    b.obox("email", cx, y0, cz, w, h, d, rot, (1, 1, 1), collide=True)


def candle(b, cx, cz, y0, col=(0.9, 0.85, 0.7)):
    b.cyl("papier", cx, y0, cz, 0.03, 0.2, 6, col, cap=True)
    b.cyl("platre", cx, y0, cz, 0.06, 0.015, 8, (0.5, 0.5, 0.5))


def coat_rack(b, cx, cz, y0):
    b.cyl("bois_meuble", cx, y0, cz, 0.03, 1.7, 6, DARKWOOD)
    b.cyl("bois_meuble", cx, y0, cz, 0.22, 0.04, 8, DARKWOOD)
    for k in range(4):
        a = k * math.pi / 2
        b.obox("metal", cx + math.cos(a) * 0.08, y0 + 1.6, cz + math.sin(a) * 0.08, 0.14, 0.03, 0.03, -math.degrees(a), (0.6, 0.6, 0.6))
    # vieux manteau
    b.obox("tissu", cx, y0 + 0.8, cz, 0.45, 0.8, 0.14, 0.0, (0.35, 0.3, 0.28))
    b.obox("tissu", cx, y0 + 1.55, cz, 0.32, 0.12, 0.12, 0.0, (0.3, 0.26, 0.24))
    b.colliders.append((cx - 0.25, y0, cz - 0.25, cx + 0.25, y0 + 1.8, cz + 0.25))


def mannequin(b, cx, cz, y0, rot=0.0):
    b.cyl("tissu", cx, y0, cz, 0.18, 0.04, 8, (0.35, 0.3, 0.3))
    b.cyl("metal", cx, y0, cz, 0.02, 0.9, 6, (0.5, 0.5, 0.5))
    b.obox("tissu", cx, y0 + 0.85, cz, 0.36, 0.55, 0.2, rot, (0.78, 0.7, 0.6))
    b.sphere("tissu", cx, y0 + 1.55, cz, 0.1, (0.78, 0.7, 0.6), sy=1.3)
    b.colliders.append((cx - 0.25, y0, cz - 0.2, cx + 0.25, y0 + 1.7, cz + 0.2))


def washing_machine(b, cx, cz, y0, rot=0.0):
    b.obox("email", cx, y0, cz, 0.6, 0.85, 0.6, rot, (1, 1, 1), collide=True)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    ox, oz = 0.0, 0.31
    b.obox("metal", cx + ox * ca + oz * sa, y0 + 0.2, cz - ox * sa + oz * ca, 0.34, 0.34, 0.03, rot, (0.4, 0.45, 0.5))


def crate(b, cx, cz, y0, size=0.45, rot=0.0):
    b.obox("planches", cx, y0, cz, size, size * 0.8, size, rot, (0.9, 0.85, 0.8), collide=True)


def delivery_bag(b, cx, cz, y0, rot=0.0, torn=True):
    b.obox("sac_quickeats", cx, y0, cz, 0.4, 0.4, 0.28, rot, (0.7, 0.7, 0.7) if torn else (1, 1, 1))


def shelving_unit(b, x0, z0, x1, z1, y0, face="+x", levels=4, height=1.9):
    for post in ((x0, z0), (x0, z1 - 0.05), (x1 - 0.05, z0), (x1 - 0.05, z1 - 0.05)):
        b.box("metal", post[0], y0, post[1], post[0] + 0.05, y0 + height, post[1] + 0.05, (0.7, 0.7, 0.7))
    for l in range(levels):
        yy = y0 + 0.15 + l * (height - 0.2) / levels
        b.box("planches", x0, yy, z0, x1, yy + 0.03, z1, (0.8, 0.75, 0.7))
    b.colliders.append((x0, y0, z0, x1, y0 + height, z1))


def freezer(b, cx, cz, y0):
    """Congélateur horizontal (le couvercle est une entité animée séparée)."""
    b.box("email", cx - 0.9, y0, cz - 0.45, cx + 0.9, y0 + 0.82, cz + 0.45, (0.95, 0.95, 0.95), collide=True, skip=("+y",))
    # intérieur sombre
    b.box("email", cx - 0.82, y0 + 0.78, cz - 0.37, cx + 0.82, y0 + 0.82, cz + 0.37, (0.25, 0.28, 0.3), skip=("-y", "+x", "-x", "+z", "-z"))


def painting(b, x, y, z, w, h, facing, tex="portrait", thick=0.03):
    """Cadre accroché à un mur. facing = '+x','-x','+z','-z' (direction de la face visible)."""
    if facing == "+z":
        b.box("bois_meuble", x - w / 2 - 0.03, y - h / 2 - 0.03, z, x + w / 2 + 0.03, y + h / 2 + 0.03, z + thick, DARKWOOD)
        b.quad(tex, (x - w / 2, y - h / 2, z + thick + 0.002), (x + w / 2, y - h / 2, z + thick + 0.002),
               (x + w / 2, y + h / 2, z + thick + 0.002), (x - w / 2, y + h / 2, z + thick + 0.002), (0, 0, 1), (1, 1, 1), tile=max(w, h))
    elif facing == "-z":
        b.box("bois_meuble", x - w / 2 - 0.03, y - h / 2 - 0.03, z - thick, x + w / 2 + 0.03, y + h / 2 + 0.03, z, DARKWOOD)
        b.quad(tex, (x + w / 2, y - h / 2, z - thick - 0.002), (x - w / 2, y - h / 2, z - thick - 0.002),
               (x - w / 2, y + h / 2, z - thick - 0.002), (x + w / 2, y + h / 2, z - thick - 0.002), (0, 0, -1), (1, 1, 1), tile=max(w, h))
    elif facing == "+x":
        b.box("bois_meuble", x, y - h / 2 - 0.03, z - w / 2 - 0.03, x + thick, y + h / 2 + 0.03, z + w / 2 + 0.03, DARKWOOD)
        b.quad(tex, (x + thick + 0.002, y - h / 2, z - w / 2), (x + thick + 0.002, y - h / 2, z + w / 2),
               (x + thick + 0.002, y + h / 2, z + w / 2), (x + thick + 0.002, y + h / 2, z - w / 2), (1, 0, 0), (1, 1, 1), tile=max(w, h))
    else:
        b.box("bois_meuble", x - thick, y - h / 2 - 0.03, z - w / 2 - 0.03, x, y + h / 2 + 0.03, z + w / 2 + 0.03, DARKWOOD)
        b.quad(tex, (x - thick - 0.002, y - h / 2, z + w / 2), (x - thick - 0.002, y - h / 2, z - w / 2),
               (x - thick - 0.002, y + h / 2, z - w / 2), (x - thick - 0.002, y + h / 2, z + w / 2), (-1, 0, 0), (1, 1, 1), tile=max(w, h))


def wall_decal(b, tex, x, y, z, w, h, facing, off=0.012, col=(1, 1, 1)):
    """Décalcomanie plaquée sur un mur (texture transparente)."""
    if facing == "+z":
        zz = z + off
        b.quad(tex, (x - w / 2, y - h / 2, zz), (x + w / 2, y - h / 2, zz), (x + w / 2, y + h / 2, zz), (x - w / 2, y + h / 2, zz), (0, 0, 1), col, tile=max(w, h))
    elif facing == "-z":
        zz = z - off
        b.quad(tex, (x + w / 2, y - h / 2, zz), (x - w / 2, y - h / 2, zz), (x - w / 2, y + h / 2, zz), (x + w / 2, y + h / 2, zz), (0, 0, -1), col, tile=max(w, h))
    elif facing == "+x":
        xx = x + off
        b.quad(tex, (xx, y - h / 2, z - w / 2), (xx, y - h / 2, z + w / 2), (xx, y + h / 2, z + w / 2), (xx, y + h / 2, z - w / 2), (1, 0, 0), col, tile=max(w, h))
    else:
        xx = x - off
        b.quad(tex, (xx, y - h / 2, z + w / 2), (xx, y - h / 2, z - w / 2), (xx, y + h / 2, z - w / 2), (xx, y + h / 2, z + w / 2), (-1, 0, 0), col, tile=max(w, h))


def floor_decal(b, tex, cx, y, cz, sx, sz, rot=0.0, col=(1, 1, 1), off=0.012):
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def p(lx, lz):
        return (cx + lx * ca + lz * sa, y + off, cz - lx * sa + lz * ca)
    hx, hz = sx / 2, sz / 2
    b.quad(tex, p(-hx, -hz), p(hx, -hz), p(hx, hz), p(-hx, hz), (0, 1, 0), col, tile=max(sx, sz))


def ceiling_decal(b, tex, cx, y, cz, sx, sz, rot=0.0, col=(1, 1, 1), off=0.012):
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def p(lx, lz):
        return (cx + lx * ca + lz * sa, y - off, cz - lx * sa + lz * ca)
    hx, hz = sx / 2, sz / 2
    b.quad(tex, p(-hx, -hz), p(hx, -hz), p(hx, hz), p(-hx, hz), (0, -1, 0), col, tile=max(sx, sz))


def stairs_mesh(b, x0, x1, z_start, z_end, y_start, y_end, steps, axis="z", tex="bois_meuble", col=WOOD):
    """Marches pleines montant de z_start à z_end (ou l'inverse), entre x0 et x1."""
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        za = z_start + (z_end - z_start) * t0
        zb = z_start + (z_end - z_start) * t1
        top = y_start + (y_end - y_start) * t1
        base = min(y_start, y_end) - 0.0
        lo, hi = min(za, zb), max(za, zb)
        tint = 0.85 + 0.15 * ((i % 3) / 2.0)
        c = (col[0] * tint, col[1] * tint, col[2] * tint)
        b.box(tex, x0, base, lo, x1, top, hi, c)
