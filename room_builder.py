"""Construction de la géométrie : constructeur de maillages + bibliothèque de meubles.

Toute la géométrie statique est accumulée dans un :class:`MeshBuilder` puis fusionnée
en un seul maillage par texture (peu d'appels de rendu). Les UV sont calculées en
mètres réels pour que les textures aient la même échelle partout.

Convention de repère : x = est, y = haut, z = nord. La façade (porte d'entrée) est en z = 0.
"""
import math
import random

from ursina import Entity, Mesh, Vec3
from panda3d.core import TransparencyAttrib

import models
from shaders import horror_shader
from texture_generator import textures, photo_meta

# Taille (en mètres) couverte par une répétition de chaque texture
TILE = {
    "etoffe": 0.5, "peau": 0.5, "veste_livreur": 0.45, "peau_morte": 0.3, "jean_sale": 0.4, "crepi": 2.5, "crepi_rose": 2.5, "tuiles": 1.6, "palmier_tronc": 1.0, "palme": 1.0, "geranium": 0.6, "papier_peint": 1.4, "papier_chambre": 1.4, "papier_couloir": 1.4,
    "platre": 2.0, "plafond": 2.0, "parquet": 2.0, "carrelage": 1.0, "moquette": 1.5,
    "beton": 2.0, "asphalte": 3.0, "herbe": 2.0, "porte": 1.0, "planches": 1.0,
    "volet": 1.0, "bois_meuble": 1.0, "tissu": 1.0, "marbre": 1.0, "email": 1.0,
    "metal": 1.0, "papier": 1.0, "drap": 1.0, "rideau": 1.0, "eau_noire": 1.0,
    "miroir": 1.0, "miroir_brise": 1.0, "vitre": 1.0, "neon": 1.0, "ecran_noir": 1.0,
}
# Textures photo : la répétition suit leur taille réelle. Les `tile` explicites (réglés pour la version procédurale)
# sont mis à l'échelle dans le même rapport.
PHOTO_SCALE = {k: v["size_m"][0] / TILE.get(k, 1.0) for k, v in photo_meta().items() if v.get("mode", "replace") == "replace"}
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


_PRODUCT_LABEL_TEXTURES = {}


def _product_label_texture(label_text):
    """Retourne une petite étiquette texturée, partagée entre les produits identiques."""
    if label_text in _PRODUCT_LABEL_TEXTURES:
        return _PRODUCT_LABEL_TEXTURES[label_text]
    name = f"_marque_produit_{label_text}"

    from PIL import Image, ImageDraw
    import typography as T

    img = Image.new("RGBA", (256, 96), (248, 244, 225, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((2, 2, 253, 93), outline=(80, 78, 68, 255), width=4)
    font = T.pil_font("sans", 46, True)
    while T.text_width(label_text, "sans", font.size, True) > 232 and font.size > 16:
        font = T.pil_font("sans", font.size - 2, True)
    draw.text((128, 48), label_text, font=font, fill=(34, 35, 38, 255), anchor="mm")
    textures.images[name] = img
    _PRODUCT_LABEL_TEXTURES[label_text] = name
    return name


class MeshBuilder:
    """Accumule des quads/triangles groupés par texture."""

    def __init__(self, name="static"):
        self.name = name
        self.groups = {}
        self.colliders = []     # (x0, y0, z0, x1, y1, z1)
        self.entities = []
        self.models = []        # modèles 3D à instancier au build (voir model())

    def model(self, name, cx, cz, y0, rot=0.0, size=None, stretch=False, pitch=0.0, free_yaw=False):
        """Réserve un modèle 3D (models.py) posé au build. Faux si le modèle est absent : l'appelant
        construit alors la version en boîtes."""
        if not models.available(name):
            return False
        self.models.append((name, cx, cz, y0, rot, size, stretch, pitch, free_yaw))
        return True

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
        if tex in PHOTO_SCALE:
            t = tuple(v * PHOTO_SCALE[tex] for v in t) if isinstance(t, (tuple, list)) else t * PHOTO_SCALE[tex]
        tu, tv = t if isinstance(t, (tuple, list)) else (t, t)
        du = _len(_sub(p1, p0)) / tu
        dv = _len(_sub(p3, p0)) / tv
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
        if tex in PHOTO_SCALE:
            t = tuple(v * PHOTO_SCALE[tex] for v in t) if isinstance(t, (tuple, list)) else t * PHOTO_SCALE[tex]
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

    def product_box(self, cx, y0, cz, w, h, d, col, label_text=None):
        """Ajoute un emballage papier avec une face avant imprimée et sa marque."""
        self.obox("papier", cx, y0, cz, w, h, d, 0, col)

        front_z = cz + d / 2 + 0.001
        margin_x = min(w * 0.06, 0.012)
        margin_y = min(h * 0.04, 0.012)
        x0, x1 = cx - w / 2 + margin_x, cx + w / 2 - margin_x
        y0_panel, y1_panel = y0 + margin_y, y0 + h - margin_y
        self.quad("emballage", (x0, y0_panel, front_z), (x1, y0_panel, front_z),
                  (x1, y1_panel, front_z), (x0, y1_panel, front_z), (0, 0, 1), (1, 1, 1),
                  tile=(x1 - x0, y1_panel - y0_panel))

        brightness = 0.299 * col[0] + 0.587 * col[1] + 0.114 * col[2]
        band = (0.08, 0.18, 0.46) if brightness > 0.58 else (0.96, 0.78, 0.12)
        band_z = front_z + 0.001
        band_y0, band_y1 = y0 + h * 0.73, y0 + h * 0.96
        self.quad("papier", (x0, band_y0, band_z), (x1, band_y0, band_z),
                  (x1, band_y1, band_z), (x0, band_y1, band_z),
                  (0, 0, 1), band, tile=(x1 - x0, band_y1 - band_y0))

        if label_text:
            label_h = max(0.025, h * 0.25)
            label_w = max(0.04, (x1 - x0) * 0.88)
            label_x0, label_x1 = cx - label_w / 2, cx + label_w / 2
            label_y0 = y0 + h * 0.43 - label_h / 2
            label_z = front_z + 0.002
            self.quad(_product_label_texture(label_text),
                      (label_x0, label_y0, label_z), (label_x1, label_y0, label_z),
                      (label_x1, label_y0 + label_h, label_z), (label_x0, label_y0 + label_h, label_z),
                      (0, 0, 1), (1, 1, 1), tile=(label_w, label_h))

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

    # --- surfaces lisses (sanitaires) --------------------------------------
    def loft(self, tex, rings, col=(1, 1, 1), outward=True, tile=None):
        """Surface lisse reliant des anneaux fermés de même nombre de points (profil de bas en haut).

        Normales par sommet (différences centrées) : rendu arrondi sans facettes. outward : normales vers
        l'extérieur des anneaux (paroi extérieure) ou vers leur axe (paroi intérieure d'une vasque).
        """
        g = self._grp(tex)
        t = tile or TILE.get(tex, 1.0)
        if tex in PHOTO_SCALE:
            t = t * PHOTO_SCALE[tex]
        tu, tv = t if isinstance(t, (tuple, list)) else (t, t)      # (périmètre, hauteur) : étiquette enroulée
        a = col if len(col) == 4 else (col[0], col[1], col[2], 1.0)
        R, S = len(rings), len(rings[0])
        centers = [tuple(sum(p[k] for p in ring) / S for k in range(3)) for ring in rings]
        normals, uvs = [], []
        vacc = 0.0
        for i in range(R):
            if i:
                vacc += _len(_sub(rings[i][0], rings[i - 1][0]))
            row_n, row_uv, uacc = [], [], 0.0
            for j in range(S):
                du = _sub(rings[i][(j + 1) % S], rings[i][(j - 1) % S])
                dv = _sub(rings[min(i + 1, R - 1)][j], rings[max(i - 1, 0)][j])
                n = _norm(_cross(dv, du))
                radial = _norm(_sub(rings[i][j], centers[i]))
                if abs(_dot(n, radial)) < 0.25:
                    if n[1] < 0:                       # surface quasi horizontale (rebord) : vers le haut
                        n = (-n[0], -n[1], -n[2])
                elif (_dot(n, radial) < 0) == outward:
                    n = (-n[0], -n[1], -n[2])
                if j:
                    uacc += _len(_sub(rings[i][j], rings[i][j - 1]))
                row_n.append(n)
                row_uv.append((uacc / tu, vacc / tv))
            normals.append(row_n)
            uvs.append(row_uv)
        for i in range(R - 1):
            for j in range(S):
                jn = (j + 1) % S
                quad = [(i, j), (i, jn), (i + 1, jn), (i + 1, j)]
                pts = [rings[r][c] for r, c in quad]
                nav = _norm(tuple(sum(normals[r][c][k] for r, c in quad) for k in range(3)))
                front = _dot(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])), nav) < 0
                for idx in ((0, 1, 2, 0, 2, 3) if front else (0, 2, 1, 0, 3, 2)):
                    r, c = quad[idx]
                    uv = uvs[r][c] if not (c == 0 and idx in (1, 2)) else (uvs[r][S - 1][0] + _len(_sub(rings[r][0], rings[r][S - 1])) / tu, uvs[r][c][1])
                    g["v"].append(rings[r][c])
                    g["u"].append(uv)
                    g["n"].append(normals[r][c])
                    g["c"].append(a)

    def cap(self, tex, ring, normal, col=(1, 1, 1), tile=None):
        """Disque plat fermant un anneau (fond de vasque, dessous de baignoire...)."""
        c = tuple(sum(p[k] for p in ring) / len(ring) for k in range(3))
        for j in range(len(ring)):
            self.tri(tex, c, ring[j], ring[(j + 1) % len(ring)], normal, col, tile)

    # --- végétation méditerranéenne ----------------------------------------
    def leaf(self, tex, p0, p1, p2, p3, col=(1, 1, 1)):
        """Quad visible des deux côtés (feuilles, palmes)."""
        n = _norm(_cross(_sub(p1, p0), _sub(p3, p0)))
        self.quad(tex, p0, p1, p2, p3, n, col)
        self.quad(tex, p0, p1, p2, p3, (-n[0], -n[1], -n[2]), col)

    def palm(self, cx, cz, h=6.0, lean=(0.6, 0.2), seed=0, fronds=9, col=(0.9, 0.9, 0.9)):
        """Palmier : tronc courbe en segments + couronne de palmes retombantes."""
        rnd = random.Random(seed)
        segs = 7
        x, y, z = cx, 0.0, cz
        r = 0.24
        for i in range(segs):
            t = (i + 1) / segs
            nx = cx + lean[0] * t * t
            nz = cz + lean[1] * t * t
            seg_h = h / segs
            self.cyl("palmier_tronc", (x + nx) / 2, y, (z + nz) / 2, r, seg_h + 0.02, 7, col, cap=False)
            x, z = nx, nz
            y += seg_h
            r *= 0.94
        top = (x, y, z)
        self.sphere("palmier_tronc", x, y, z, 0.32, (0.7, 0.62, 0.5), lat=4, lon=7)
        for k in range(fronds):
            a = 2 * math.pi * k / fronds + rnd.uniform(-0.2, 0.2)
            L = rnd.uniform(2.0, 2.8)
            w = 0.34
            droop = rnd.uniform(0.6, 1.3)
            dx, dz = math.cos(a), math.sin(a)
            px_, pz_ = -dz * w, dx * w
            mid = (top[0] + dx * L * 0.55, top[1] + 0.35, top[2] + dz * L * 0.55)
            tip = (top[0] + dx * L, top[1] - droop, top[2] + dz * L)
            leafc = (0.55 + rnd.uniform(-0.1, 0.1), 0.7, 0.5)
            self.leaf("palme", (top[0] + px_ * 0.3, top[1], top[2] + pz_ * 0.3), (top[0] - px_ * 0.3, top[1], top[2] - pz_ * 0.3),
                      (mid[0] - px_, mid[1], mid[2] - pz_), (mid[0] + px_, mid[1], mid[2] + pz_), leafc)
            self.leaf("palme", (mid[0] + px_, mid[1], mid[2] + pz_), (mid[0] - px_, mid[1], mid[2] - pz_),
                      (tip[0] - px_ * 0.2, tip[1], tip[2] - pz_ * 0.2), (tip[0] + px_ * 0.2, tip[1], tip[2] + pz_ * 0.2), leafc)
        self.colliders.append((cx - 0.3, 0, cz - 0.3, cx + 0.3, h, cz + 0.3))
        return top

    def cypress(self, cx, cz, h=7.0, r=0.7, col=(0.35, 0.45, 0.32)):
        """Cyprès de Provence : fuseau sombre."""
        self.sphere("herbe", cx, h * 0.5, cz, r, col, lat=7, lon=9, sy=h / (2 * r))
        self.cyl("bois_meuble", cx, 0.0, cz, 0.12, 0.6, 6, (0.3, 0.25, 0.2), cap=False)
        self.colliders.append((cx - r * 0.6, 0, cz - r * 0.6, cx + r * 0.6, h, cz + r * 0.6))

    def agave(self, cx, cz, size=0.8, seed=0, col=(0.55, 0.68, 0.6)):
        """Agave : rosette de feuilles pointues."""
        rnd = random.Random(seed)
        for k in range(11):
            a = 2 * math.pi * k / 11 + rnd.uniform(-0.15, 0.15)
            L = size * rnd.uniform(0.7, 1.1)
            up = rnd.uniform(0.4, 0.9)
            dx, dz = math.cos(a), math.sin(a)
            w = 0.09 * size / 0.8
            tip = (cx + dx * L, up * L, cz + dz * L)
            self.leaf("palme", (cx - dz * w, 0.02, cz + dx * w), (cx + dz * w, 0.02, cz - dx * w), tip, tip, col)

    def flower_pot(self, cx, y0, cz, r=0.17, h=0.3):
        """Pot en terre cuite avec géraniums rouges."""
        self.cyl("tuiles", cx, y0, cz, r, h, 9, (0.95, 0.75, 0.65))
        self.geraniums(cx, y0 + h, cz, r * 1.7, r * 1.7, seed=int(abs(cx * 13 + cz * 7)))

    def geraniums(self, cx, y0, cz, w, d, seed=0, col=(0.88, 0.12, 0.14)):
        """Touffe de géraniums : feuillage arrondi vert foncé + ombelles de fleurs sur tiges, au-dessus de (cx, y0, cz)."""
        rnd = random.Random(seed)
        n_leaf = max(3, int(w * d * 60))
        for _ in range(n_leaf):                                       # feuilles rondes un peu aplaties
            x, z = cx + rnd.uniform(-w / 2, w / 2) * 0.85, cz + rnd.uniform(-d / 2, d / 2) * 0.85
            g = rnd.uniform(0.75, 1.1)
            self.sphere("etoffe", x, y0 + rnd.uniform(0.03, 0.08), z, rnd.uniform(0.045, 0.065),
                        (0.11 * g, 0.25 * g, 0.08 * g), lat=4, lon=7, sy=0.45)
        n_fl = max(2, int(w * d * 28))
        for _ in range(n_fl):                                         # ombelles : petites fleurs groupées
            x, z = cx + rnd.uniform(-w / 2, w / 2) * 0.7, cz + rnd.uniform(-d / 2, d / 2) * 0.7
            top = y0 + rnd.uniform(0.15, 0.22)
            self.box("etoffe", x - 0.004, y0 + 0.04, z - 0.004, x + 0.004, top, z + 0.004, (0.2, 0.36, 0.14))
            tint = rnd.uniform(0.85, 1.1)
            c = (min(1.0, col[0] * tint), col[1] * tint, col[2] * tint)
            for k in range(6):
                a = k * 1.047 + rnd.uniform(-0.3, 0.3)
                self.sphere("etoffe", x + math.cos(a) * 0.022, top + rnd.uniform(-0.006, 0.01), z + math.sin(a) * 0.022,
                            0.014, c, lat=3, lon=5)
            self.sphere("etoffe", x, top + 0.012, z, 0.014, c, lat=3, lon=5)

    def persienne(self, axis, fixed, a0, a1, y0, y1, outward=-1, col=(0.32, 0.5, 0.42)):
        """Volet persienne vert provençal plaqué contre la façade (côté extérieur)."""
        off = fixed + outward * 0.13
        if axis == "x":
            self.box("volet", a0, y0, min(off, off + outward * 0.04), a1, y1, max(off, off + outward * 0.04), col)
        else:
            self.box("volet", min(off, off + outward * 0.04), y0, a0, max(off, off + outward * 0.04), y1, a1, col)

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
        if self.models:
            holder = Entity(parent=parent, name="modeles", shader=shader)
            holder.set_shader_input("emit", float(emit))
            for (name, cx, cz, y0, rot, size, stretch, pitch, free_yaw) in self.models:
                models.place(name, holder, cx, cz, y0, rot, size, stretch, pitch, free_yaw, shaded=False)
            try:
                # décors immobiles : les géométries passent sous un nœud Panda simple (les Entity Ursina portent
                # des étiquettes Python qui empêchent la fusion) puis sont regroupées par texture
                plain = holder.attachNewNode("fusion")
                for gnp in holder.findAllMatches("**/+GeomNode"):
                    gnp.wrtReparentTo(plain)
                plain.flattenStrong()
            except Exception:
                pass
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


def _ocollider(b, cx, y0, cz, sx, sy, sz, rot=0.0):
    """Collider d'une boîte orientée (même emprise que obox(..., collide=True)), sans géométrie."""
    ca, sa = abs(math.cos(math.radians(rot))), abs(math.sin(math.radians(rot)))
    ex, ez = (ca * sx + sa * sz) / 2, (sa * sx + ca * sz) / 2
    b.colliders.append((cx - ex, y0, cz - ez, cx + ex, y0 + sy, cz + ez))


def sofa(b, cx, cz, rot, y0, length=2.0, depth=0.9):
    if b.model("sofa_03", cx, cz, y0, rot):                      # taille réelle : 2,73 x 0,93 m
        _ocollider(b, cx, y0, cz, 2.7, 0.42, 0.92, rot)
        return
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
    if b.model("GreenChair_01", cx, cz, y0, rot):                # taille réelle : 0,67 x 0,66 m, 1,06 m de haut
        _ocollider(b, cx, y0, cz, 0.67, 0.42, 0.66, rot)
        return
    sofa(b, cx, cz, rot, y0, length=0.95, depth=0.9)


def table(b, cx, cz, y0, sx, sz, h=0.75, tex="bois_meuble", col=WOOD, rot=0.0, collide=True):
    if h <= 0.5:
        name = "gothic_coffee_table"
    elif sx <= 0.5 and sz <= 0.5:
        name = "painted_wooden_nightstand"
    elif sx >= 1.0 and sz >= 0.7:
        name = "dining_table"
    else:
        name = "WoodenTable_01"
    if b.model(name, cx, cz, y0, rot, (sx, h, sz), stretch=True, free_yaw=True):
        if collide:
            _ocollider(b, cx, y0, cz, sx, h, sz, rot)
        return
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
    if b.model("painted_wooden_chair_01", cx, cz, y0, rot, pitch=90.0 if fallen else 0.0):   # taille réelle (0,96 m)
        if fallen:
            b.colliders.append((cx - 0.45, y0, cz - 0.3, cx + 0.45, y0 + 0.45, cz + 0.3))
        else:
            b.colliders.append((cx - 0.22, y0, cz - 0.22, cx + 0.22, y0 + 0.9, cz + 0.22))
        return
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
    rot = {"+z": 0.0, "+x": 90.0, "-z": 180.0, "-x": 270.0}[face]
    along_x = face in ("+z", "-z")
    w, d = (x1 - x0, z1 - z0) if along_x else (z1 - z0, x1 - x0)
    if b.model("vintage_cabinet_01", (x0 + x1) / 2, (z0 + z1) / 2, y0, rot, (w, height, d), stretch=True):
        b.colliders.append((x0, y0, z0, x1, y0 + height, z1))
        return
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
    if b.model("GothicBed_01", cx, cz, y0, rot, (w, None, l), stretch=True):
        _ocollider(b, cx, y0, cz, w, 0.3, l, rot)
        return
    b.obox("bois_meuble", cx, y0, cz, w, 0.3, l, rot, DARKWOOD, collide=True)
    b.obox("drap", cx, y0 + 0.3, cz, w - 0.1, 0.18, l - 0.1, rot, col_sheet)
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    # tête de lit
    ox, oz = 0.0, -(l / 2)
    b.obox("bois_meuble", cx + ox * ca + oz * sa, y0, cz - ox * sa + oz * ca, w, 1.0, 0.08, rot, DARKWOOD)
    for s in (-0.25, 0.25):
        ox, oz = s * w, -(l / 2) + 0.28
        b.obox("drap", cx + ox * ca + oz * sa, y0 + 0.48, cz - ox * sa + oz * ca, 0.5, 0.12, 0.32, rot, (1, 1, 0.95))


def rounded_box(b, tex, cx, cz, y0, w, h, d, rot=0.0, col=(1, 1, 1), n=10.0, bevel=0.02):
    """Boîte aux arêtes verticales et supérieures arrondies (électroménager) : flancs lissés, dessus biseauté."""
    rings = [_ring(cx, cz, y0, w / 2, d / 2, rot, n),
             _ring(cx, cz, y0 + h - bevel, w / 2, d / 2, rot, n),
             _ring(cx, cz, y0 + h - bevel * 0.3, w / 2 - bevel * 0.6, d / 2 - bevel * 0.6, rot, n),
             _ring(cx, cz, y0 + h, w / 2 - bevel, d / 2 - bevel, rot, n)]
    b.loft(tex, rings, col)
    b.cap(tex, rings[-1], (0, 1, 0), col)
    return rings


def _front(b, tex, cx, cz, rot, lx, ly, w, h, lz, col):
    """Panneau vertical tourné vers +z local, centre bas (lx, ly), à la profondeur lz."""
    n = (math.sin(math.radians(rot)), 0.0, math.cos(math.radians(rot)))
    pa, pb = _local(cx, cz, rot, lx + w / 2, lz), _local(cx, cz, rot, lx - w / 2, lz)
    b.quad(tex, (pa[0], ly, pa[1]), (pb[0], ly, pb[1]), (pb[0], ly + h, pb[1]), (pa[0], ly + h, pa[1]), n, col, tile=(w, h))


def _knob(b, cx, cz, rot, lx, ly, lz, r=0.022, col=(0.8, 0.8, 0.82)):
    kx, kz = _local(cx, cz, rot, lx, lz)
    b.sphere("metal", kx, ly, kz, r, col, lat=5, lon=10, sy=0.7)


def wardrobe(b, x0, z0, x1, z1, y0, face="+x", height=2.1, hollow=False):
    """Armoire ancienne : caisse (portes animées à part), socle mouluré, corniche, pieds tournés.

    hollow : caisse vide (façade vers +z) avec fond, flancs, plancher, plafond, étagère haute et tringle."""
    if not hollow:
        b.box("bois_meuble", x0 + 0.03, y0 + 0.1, z0, x1 - 0.03, y0 + height - 0.08, z1, DARKWOOD, collide=True)
    else:
        t, inner = 0.025, (0.42, 0.36, 0.3)
        xa, xb, ya, yb = x0 + 0.03, x1 - 0.03, y0 + 0.1, y0 + height - 0.08
        b.box("bois_meuble", xa, ya, z0, xb, yb, z0 + t, inner)                                # fond
        b.box("bois_meuble", xa, ya, z0, xa + t, yb, z1, DARKWOOD)                             # flancs
        b.box("bois_meuble", xb - t, ya, z0, xb, yb, z1, DARKWOOD)
        b.box("bois_meuble", xa, ya, z0, xb, ya + t, z1, inner)                                # plancher / plafond
        b.box("bois_meuble", xa, yb - t, z0, xb, yb, z1, DARKWOOD)
        b.box("bois_meuble", xa + t, y0 + 1.78, z0 + t, xb - t, y0 + 1.8, z1 - 0.03, inner)    # étagère haute
        rod(b, "metal", (xa + t, y0 + 1.66, (z0 + z1) / 2), (xb - t, y0 + 1.66, (z0 + z1) / 2), 0.012,
            col=(0.75, 0.72, 0.66))                                                            # tringle
        b.colliders.append((x0, y0, z0, x1, y0 + height, z1))
    b.box("bois_meuble", x0, y0 + 0.06, z0 - 0.01, x1, y0 + 0.14, z1 + 0.025, (0.45, 0.4, 0.36))
    b.box("bois_meuble", x0 - 0.04, y0 + height - 0.08, z0 - 0.02, x1 + 0.04, y0 + height, z1 + 0.05, (0.45, 0.4, 0.36))
    b.box("bois_meuble", x0 - 0.02, y0 + height - 0.12, z0 - 0.01, x1 + 0.02, y0 + height - 0.08, z1 + 0.03, (0.5, 0.45, 0.4))
    for fx in (x0 + 0.08, x1 - 0.08):
        for fz in (z0 + 0.08, z1 - 0.06):
            b.loft("bois_meuble", [_ring(fx, fz, y0 + yy, r, r, 0.0, 2.0, seg=12) for (yy, r) in
                                   ((0.0, 0.03), (0.02, 0.045), (0.05, 0.035), (0.06, 0.05))], (0.4, 0.35, 0.3))


def counter(b, x0, z0, x1, z1, y0, h=0.9):
    """Meuble bas de cuisine : caisson sur socle en retrait, portes à cadre et poignées, plan de travail en marbre."""
    wood = (0.6, 0.55, 0.5)
    b.box("bois_meuble", x0, y0 + 0.1, z0, x1, y0 + h - 0.04, z1, wood, collide=True)
    # façade = côté pièce (meubles adossés au mur x = 0 ou z = 12 de la cuisine)
    if x1 - x0 < z1 - z0:
        face, a0, a1, fixed = "+x", z0, z1, x1
        b.box("beton", x0, y0, z0, x1 - 0.06, y0 + 0.1, z1, (0.25, 0.24, 0.23))
    else:
        face, a0, a1, fixed = "-z", x0, x1, z0
        b.box("beton", x0, y0, z0 + 0.06, x1, y0 + 0.1, z1, (0.25, 0.24, 0.23))
    n_doors = max(1, round((a1 - a0) / 0.6))
    dw = (a1 - a0) / n_doors
    for k in range(n_doors):
        c = a0 + dw * (k + 0.5)
        for (dy0, dy1, t, cc) in ((y0 + 0.13, y0 + h - 0.08, 0.012, (0.66, 0.6, 0.54)),
                                  (y0 + 0.2, y0 + h - 0.15, 0.018, (0.58, 0.53, 0.47))):
            inset = 0.02 if t < 0.015 else 0.08
            if face == "+x":
                b.box("bois_meuble", fixed, dy0, c - dw / 2 + inset, fixed + t, dy1, c + dw / 2 - inset, cc)
            else:
                b.box("bois_meuble", c - dw / 2 + inset, dy0, fixed - t, c + dw / 2 - inset, dy1, fixed, cc)
        hx, hz = (fixed + 0.03, c + dw / 2 - 0.07) if face == "+x" else (c + dw / 2 - 0.07, fixed - 0.03)
        b.cyl("metal", hx, y0 + h - 0.34, hz, 0.008, 0.14, 8, (0.8, 0.8, 0.82))
    b.box("marbre", x0 - 0.02, y0 + h - 0.04, z0 - 0.02, x1 + 0.02, y0 + h, z1 + 0.02, (1, 1, 1))


def carton(b, cx, cz, y0, size=0.5, rot=0.0, col=(0.7, 0.55, 0.35)):
    if b.model("cardboard_box_01", cx, cz, y0, rot, (size, size * 0.9, size), stretch=True, free_yaw=True):
        _ocollider(b, cx, y0, cz, size, size * 0.9, size, rot)
        return
    b.obox("papier", cx, y0, cz, size, size * 0.9, size, rot, col, collide=True)
    b.obox("papier", cx, y0 + size * 0.9, cz, size * 0.96, 0.02, 0.06, rot, (0.55, 0.45, 0.3))


def pleated_panel(b, tex, cx, y0, cz, width, height, axis="x", depth=0.04, folds=8, col=(1, 1, 1), seg=48, hem=0.03):
    """Tissu suspendu plissé (rideau, drap) centré sur (cx, cz), plis le long de `axis`, visible des deux côtés."""
    pts = []
    for k in range(seg + 1):
        t = k / seg
        a = -width / 2 + width * t
        off = depth * math.sin(t * folds * 2 * math.pi)
        pts.append((a, off, hem * math.sin(t * folds * 3.1 + 1.0)))
    for k in range(seg):
        (a0, o0, h0), (a1, o1, h1) = pts[k], pts[k + 1]
        if axis == "x":
            p0, p1 = (cx + a0, y0 + h0, cz + o0), (cx + a1, y0 + h1, cz + o1)
            q0, q1 = (cx + a0, y0 + height, cz + o0), (cx + a1, y0 + height, cz + o1)
            n = _norm((-(o1 - o0), 0, a1 - a0))
        else:
            p0, p1 = (cx + o0, y0 + h0, cz + a0), (cx + o1, y0 + h1, cz + a1)
            q0, q1 = (cx + o0, y0 + height, cz + a0), (cx + o1, y0 + height, cz + a1)
            n = _norm((a1 - a0, 0, -(o1 - o0)))
        b.quad(tex, p0, p1, q1, q0, n, col, tile=(width / seg * 2, height))
        b.quad(tex, p0, p1, q1, q0, (-n[0], -n[1], -n[2]), col, tile=(width / seg * 2, height))


def covered_furniture(b, cx, cz, y0, sx, sz, h):
    """Meuble recouvert d'un drap : dessus arrondi, drap qui retombe en ondulant jusqu'au sol."""
    seg = 40

    def ring(y, scale, wave):
        out = []
        for k, (x, _, z) in enumerate(_ring(0.0, 0.0, 0.0, sx / 2 * scale, sz / 2 * scale, 0.0, 5.0, seg=seg)):
            w = 1.0 + wave * math.sin(k * 2 * math.pi * 7 / seg + 0.6) + wave * 0.5 * math.sin(k * 2 * math.pi * 3 / seg)
            out.append((cx + x * w, y, cz + z * w))
        return out

    rings = [ring(y0, 1.1, 0.035), ring(y0 + h * 0.25, 1.05, 0.025), ring(y0 + h * 0.7, 1.0, 0.012), ring(y0 + h * 0.97, 0.99, 0.005),
             ring(y0 + h + 0.03, 0.9, 0.0), ring(y0 + h + 0.05, 0.6, 0.0)]
    b.loft("drap", rings, (0.95, 0.94, 0.9))
    b.cap("drap", rings[-1], (0, 1, 0), (0.95, 0.94, 0.9))
    b.colliders.append((cx - sx / 2, y0, cz - sz / 2, cx + sx / 2, y0 + h, cz + sz / 2))


def _ring(cx, cz, y, hw, hd, rot=0.0, n=2.6, seg=32, ox=0.0, oz=0.0):
    """Anneau en super-ellipse |x/hw|^n + |z/hd|^n = 1 (rectangle arrondi pour n grand), centré sur (ox, oz)
    dans le repère local de l'objet, puis tourné de `rot` et placé en (cx, cz)."""
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    pts = []
    for k in range(seg):
        t = 2 * math.pi * k / seg
        c, s_ = math.cos(t), math.sin(t)
        lx = ox + hw * math.copysign(abs(c) ** (2.0 / n), c)
        lz = oz + hd * math.copysign(abs(s_) ** (2.0 / n), s_)
        pts.append((cx + lx * ca + lz * sa, y, cz - lx * sa + lz * ca))
    return pts


def rod(b, tex, p0, p1, r0, r1=None, col=(1, 1, 1), seg=8, caps=False):
    """Tube lisse (manche, tige, barreau) de p0 à p1, rayon r0 -> r1 ; caps : bouts fermés."""
    r1 = r0 if r1 is None else r1
    ax = _norm(_sub(p1, p0))
    ref = (0.0, 1.0, 0.0) if abs(ax[1]) < 0.9 else (1.0, 0.0, 0.0)
    u = _norm(_cross(ax, ref))
    v = _cross(ax, u)
    rings = []
    for (p, r) in ((p0, r0), (p1, r1)):
        rings.append([tuple(p[i] + r * (math.cos(a) * u[i] + math.sin(a) * v[i]) for i in range(3))
                      for a in [2 * math.pi * k / seg for k in range(seg)]])
    b.loft(tex, rings, col)
    if caps:
        b.cap(tex, rings[0], tuple(-c for c in ax), col)
        b.cap(tex, rings[1], ax, col)


def lathe(b, tex, cx, cz, y0, profile, col=(1, 1, 1), n=2.0, seg=16, rot=0.0):
    """Surface de révolution lissée (super-ellipses empilées) : profile = [(y, demi-largeur, demi-profondeur[, dx])]."""
    rings = []
    for pr in profile:
        dx = pr[3] if len(pr) > 3 else 0.0
        rings.append(_ring(cx, cz, y0 + pr[0], pr[1], pr[2], rot, n, seg, ox=dx))
    b.loft(tex, rings, col)


def _local(cx, cz, rot, lx, lz):
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return cx + lx * ca + lz * sa, cz - lx * sa + lz * ca


ENAMEL = (1.0, 1.0, 0.96)
CHROME = (0.85, 0.85, 0.88)


def _basin(b, tex, cx, cz, rot, rim_y, outer, inner, depth, col, n_out=2.6, n_in=2.6, ox=0.0, oz=0.0, bulge=None, floor=True):
    """Vasque creuse : bord plat (anneau extérieur -> intérieur) puis paroi intérieure jusqu'au fond, fond plat.
    outer/inner = (demi-largeur, demi-profondeur). bulge : profil intérieur (fractions de l'ouverture, de haut en bas)."""
    (ow, od), (iw, idp) = outer, inner
    b.loft(tex, [_ring(cx, cz, rim_y, ow, od, rot, n_out, ox=ox, oz=oz), _ring(cx, cz, rim_y, iw, idp, rot, n_in, ox=ox, oz=oz)],
           col, outward=False)
    prof = bulge or (1.0, 0.97, 0.9, 0.78, 0.6)
    rings = [_ring(cx, cz, rim_y - depth * k / (len(prof) - 1), iw * f, idp * f, rot, n_in, ox=ox, oz=oz) for k, f in enumerate(prof)]
    b.loft(tex, rings[::-1], col, outward=False)
    if floor:
        b.cap(tex, rings[-1], (0, 1, 0), col)
    return rings[-1]


def toilet(b, cx, cz, y0, rot):
    """WC : pied et cuvette arrondis, abattant, réservoir aux angles arrondis (façade vers +z local)."""
    # pied -> cuvette (s'évase et avance vers l'avant)
    prof = ((0.0, 0.11, 0.15, -0.02), (0.12, 0.12, 0.17, 0.0), (0.26, 0.16, 0.22, 0.03), (0.36, 0.185, 0.25, 0.04), (0.4, 0.19, 0.255, 0.04))
    b.loft("email", [_ring(cx, cz, y0 + y, hw, hd, rot, 2.2, oz=oz) for (y, hw, hd, oz) in prof], ENAMEL)
    _basin(b, "email", cx, cz, rot, y0 + 0.4, (0.19, 0.255), (0.14, 0.2), 0.2, ENAMEL, n_out=2.2, n_in=2.0, oz=0.04,
           bulge=(1.0, 0.92, 0.75, 0.5, 0.3))
    b.cap("eau_noire", _ring(cx, cz, y0 + 0.27, 0.075, 0.1, rot, 2.0, oz=0.06), (0, 1, 0), (0.6, 0.65, 0.6))
    # abattant (anneau épais) posé sur la cuvette
    seat_o = [_ring(cx, cz, y0 + yy, 0.195, 0.26, rot, 2.2, oz=0.04) for yy in (0.405, 0.43)]
    b.loft("email", seat_o, (0.95, 0.95, 0.92))
    _basin(b, "email", cx, cz, rot, y0 + 0.43, (0.195, 0.26), (0.13, 0.18), 0.025, (0.95, 0.95, 0.92), n_out=2.2, n_in=2.0, oz=0.05,
           bulge=(1.0, 1.0), floor=False)
    # réservoir (arrière, -z local)
    tank = [_ring(cx, cz, y0 + yy, 0.2, 0.09, rot, 6.0, oz=-0.26) for yy in (0.4, 0.42, 0.74, 0.76)]
    b.loft("email", tank, ENAMEL)
    lid = [_ring(cx, cz, y0 + yy, 0.215, 0.1, rot, 6.0, oz=-0.26) for yy in (0.76, 0.79)]
    b.loft("email", lid, ENAMEL)
    b.cap("email", lid[-1], (0, 1, 0), ENAMEL)
    bx, bz = _local(cx, cz, rot, 0.0, -0.26)
    b.cyl("metal", bx, y0 + 0.79, bz, 0.025, 0.012, 12, CHROME)
    _ocollider(b, cx, y0, cz, 0.38, 0.4, 0.5, rot)


def sink(b, cx, cz, y0, rot, h=0.85):
    """Lavabo sur colonne : vasque creuse, colonne galbée, robinet chromé (dos du lavabo vers -z local)."""
    # colonne
    col_prof = ((0.0, 0.11), (0.03, 0.1), (0.2, 0.075), (h - 0.3, 0.07), (h - 0.17, 0.09))
    b.loft("email", [_ring(cx, cz, y0 + y, r, r * 0.85, rot, 2.0, seg=24, oz=-0.04) for (y, r) in col_prof], ENAMEL)
    # vasque : dessous bombé puis bord
    under = [_ring(cx, cz, y0 + h - dy, 0.275 * f, 0.21 * f, rot, 2.4) for (dy, f) in ((0.17, 0.45), (0.12, 0.8), (0.06, 0.97), (0.0, 1.0))]
    b.loft("email", under, ENAMEL)
    b.cap("email", under[0], (0, -1, 0), ENAMEL)
    floor = _basin(b, "email", cx, cz, rot, y0 + h, (0.275, 0.21), (0.22, 0.15), 0.12, ENAMEL, n_out=2.4, n_in=2.2, oz=0.01)
    b.cap("metal", _ring(cx, cz, floor[0][1] + 0.002, 0.022, 0.022, rot, 2.0, seg=12, oz=0.01), (0, 1, 0), (0.25, 0.25, 0.27))
    # robinet : pied, col de cygne, deux croisillons
    fx, fz = _local(cx, cz, rot, 0.0, -0.17)
    b.cyl("metal", fx, y0 + h, fz, 0.018, 0.14, 12, CHROME)
    sx, sz = _local(cx, cz, rot, 0.0, -0.11)
    b.obox("metal", sx, y0 + h + 0.12, sz, 0.026, 0.026, 0.13, rot, CHROME)
    for side in (-1, 1):
        hx, hz = _local(cx, cz, rot, side * 0.08, -0.17)
        b.cyl("metal", hx, y0 + h, hz, 0.02, 0.05, 10, CHROME)
        b.sphere("metal", hx, y0 + h + 0.055, hz, 0.02, CHROME, lat=4, lon=8)
    _ocollider(b, cx, y0, cz, 0.12, h - 0.12, 0.12, rot)


def bathtub(b, cx, cz, y0, rot, l=1.6, w=0.75, water=False):
    """Baignoire ancienne à pieds de lion : coque ovale galbée, bord roulé, intérieur creux, robinetterie."""
    hl, hw = l / 2, w / 2
    rim = y0 + 0.62
    shell = [_ring(cx, cz, y0 + y, hl * f, hw * g, rot, 2.6, seg=40)
             for (y, f, g) in ((0.14, 0.84, 0.78), (0.18, 0.9, 0.86), (0.3, 0.96, 0.95), (0.45, 0.99, 0.99), (0.58, 1.0, 1.0), (0.62, 1.01, 1.01))]
    b.loft("email", shell, ENAMEL)
    b.cap("email", shell[0], (0, -1, 0), ENAMEL)
    _basin(b, "email", cx, cz, rot, rim, (hl * 1.01, hw * 1.01), (hl - 0.07, hw - 0.07), 0.44, ENAMEL,
           bulge=(1.0, 0.98, 0.95, 0.88, 0.75))
    # pieds de lion (fonte)
    for sx in (-1, 1):
        for sz in (-1, 1):
            fx, fz = _local(cx, cz, rot, sx * (hl - 0.2), sz * (hw - 0.14))
            b.sphere("metal", fx, y0 + 0.07, fz, 0.07, (0.35, 0.32, 0.28), lat=6, lon=10, sy=1.1)
            b.cyl("metal", fx, y0, fz, 0.05, 0.03, 10, (0.3, 0.28, 0.25))
    # robinetterie côté -x local
    tx, tz = _local(cx, cz, rot, -hl + 0.05, 0.0)
    b.cyl("metal", tx, rim, tz, 0.02, 0.16, 12, CHROME)
    spx, spz = _local(cx, cz, rot, -hl + 0.12, 0.0)
    b.obox("metal", spx, rim + 0.13, spz, 0.15, 0.028, 0.028, rot, CHROME)
    for s_ in (-1, 1):
        hx, hz = _local(cx, cz, rot, -hl + 0.05, s_ * 0.1)
        b.cyl("metal", hx, rim, hz, 0.018, 0.06, 10, CHROME)
    if water:
        b.cap("eau_noire", _ring(cx, cz, y0 + 0.5, hl - 0.1, hw - 0.1, rot, 2.6, seg=40), (0, 1, 0), (1, 1, 1))
    _ocollider(b, cx, y0 + 0.08, cz, l, 0.5, w, rot)


def fridge_body(b, cx, cz, y0, rot=0.0, w=0.7, d=0.7, h=1.7):
    """Réfrigérateur années 60 : caisse aux angles arrondis, dessus bombé, grille et pieds (porte animée à part)."""
    rounded_box(b, "email", cx, cz, y0 + 0.05, w, h - 0.05, d, rot, (0.97, 0.96, 0.9), n=8.0, bevel=0.06)
    for sx in (-1, 1):
        for sz in (-1, 1):
            fx, fz = _local(cx, cz, rot, sx * (w / 2 - 0.06), sz * (d / 2 - 0.06))
            b.cyl("metal", fx, y0, fz, 0.025, 0.05, 8, (0.3, 0.3, 0.32))
    _front(b, "metal", cx, cz, rot, 0.0, y0 + 0.06, w - 0.1, 0.06, d / 2 + 0.003, (0.25, 0.25, 0.27))
    _ocollider(b, cx, y0, cz, w, h, d, rot)


def candle(b, cx, cz, y0, col=(0.9, 0.85, 0.7)):
    b.cyl("papier", cx, y0, cz, 0.03, 0.2, 6, col, cap=True)
    b.cyl("platre", cx, y0, cz, 0.06, 0.015, 8, (0.5, 0.5, 0.5))


def coat_rack(b, cx, cz, y0):
    b.cyl("bois_meuble", cx, y0, cz, 0.03, 1.7, 6, DARKWOOD)
    b.cyl("bois_meuble", cx, y0, cz, 0.22, 0.04, 8, DARKWOOD)
    for k in range(4):
        a = k * math.pi / 2
        b.obox("metal", cx + math.cos(a) * 0.08, y0 + 1.6, cz + math.sin(a) * 0.08, 0.14, 0.03, 0.03, -math.degrees(a), (0.6, 0.6, 0.6))
    # vieux pardessus en laine pendu à une patère : épaules affaissées, pans évasés, manches qui pendent
    wool = (0.3, 0.25, 0.21)
    hx = cx + 0.1
    body = [(1.6, 0.05, 0.035), (1.555, 0.13, 0.06), (1.5, 0.2, 0.085), (1.38, 0.21, 0.1), (1.15, 0.19, 0.1),
            (0.9, 0.21, 0.1), (0.68, 0.24, 0.1), (0.58, 0.25, 0.095)]
    lathe(b, "etoffe", hx, cz, y0, body, wool, n=2.3, seg=18)
    b.cap("etoffe", _ring(hx, cz, y0 + 0.58, 0.24, 0.09, 0.0, 2.3, seg=18), (0, -1, 0), (0.08, 0.07, 0.06))
    for sx in (-1, 1):
        sleeve = [(1.48, 0.055, 0.06, sx * 0.19), (1.2, 0.05, 0.055, sx * 0.21), (0.92, 0.055, 0.055, sx * 0.215)]
        lathe(b, "etoffe", hx, cz + 0.015, y0, sleeve, (wool[0] * 0.9, wool[1] * 0.9, wool[2] * 0.9), n=2.0, seg=10)
    lathe(b, "etoffe", hx, cz + 0.045, y0, [(1.6, 0.07, 0.03), (1.5, 0.12, 0.04), (1.38, 0.05, 0.02)],
          (0.24, 0.2, 0.17), n=2.0, seg=12)                                     # col relevé
    b.colliders.append((cx - 0.25, y0, cz - 0.25, cx + 0.25, y0 + 1.8, cz + 0.25))


def mannequin(b, cx, cz, y0, rot=0.0):
    """Mannequin de couture : buste galbé en toile écrue sur pied tripode, tête ovoïde lisse."""
    lathe(b, "metal", cx, cz, y0, [(0.0, 0.2, 0.2), (0.03, 0.2, 0.2), (0.05, 0.05, 0.05)], (0.25, 0.22, 0.2), n=2.0, seg=16)
    b.cyl("metal", cx, y0 + 0.04, cz, 0.018, 0.86, 8, (0.55, 0.52, 0.48))
    linen = (0.78, 0.7, 0.6)
    torso = [(0.86, 0.04, 0.04), (0.9, 0.15, 0.1), (0.98, 0.17, 0.11), (1.1, 0.13, 0.09), (1.24, 0.16, 0.11),
             (1.33, 0.175, 0.115), (1.42, 0.18, 0.1), (1.47, 0.12, 0.07), (1.5, 0.045, 0.045), (1.56, 0.04, 0.04)]
    lathe(b, "etoffe", cx, cz, y0, torso, linen, n=2.2, seg=20, rot=rot)
    b.cap("etoffe", _ring(cx, cz, y0 + 0.86, 0.04, 0.04, rot, 2.0, seg=20), (0, -1, 0), linen)
    head = []
    for k in range(15):                                  # ovoïde : pôles arrondis (rayon en sin^0.55)
        a = math.pi * k / 14
        r = max(0.004, math.sin(a) ** 0.55)
        head.append((1.66 - 0.13 * math.cos(a), 0.095 * r, 0.11 * r))
    lathe(b, "etoffe", cx, cz, y0, head, (0.82, 0.76, 0.68), n=2.0, seg=16, rot=rot)
    b.colliders.append((cx - 0.25, y0, cz - 0.2, cx + 0.25, y0 + 1.7, cz + 0.2))


def washing_machine(b, cx, cz, y0, rot=0.0):
    """Lave-linge à hublot (façade vers +z local) : caisse arrondie, bandeau de commandes, hublot chromé, plinthe."""
    rounded_box(b, "email", cx, cz, y0, 0.6, 0.85, 0.6, rot, (0.95, 0.95, 0.93), n=10.0, bevel=0.025)
    fz = 0.301
    _front(b, "metal", cx, cz, rot, 0.0, y0 + 0.73, 0.56, 0.1, fz, (0.78, 0.78, 0.8))
    _front(b, "ecran_noir", cx, cz, rot, -0.06, y0 + 0.755, 0.14, 0.05, fz + 0.002, (1, 1, 1))
    _knob(b, cx, cz, rot, 0.18, y0 + 0.78, fz + 0.01, 0.03)
    for k in range(3):
        _knob(b, cx, cz, rot, 0.06 + k * 0.035, y0 + 0.77, fz + 0.005, 0.009, (0.3, 0.3, 0.32))
    _front(b, "metal", cx, cz, rot, 0.0, y0 + 0.02, 0.56, 0.08, fz, (0.6, 0.6, 0.62))

    def disc(r, dz):
        out = []
        for (x, _, z) in _ring(0, 0, 0, r, r, 0.0, 2.0, seg=28):
            px, pz = _local(cx, cz, rot, x, fz + dz)
            out.append((px, y0 + 0.4 + z, pz))
        return out
    b.loft("metal", [disc(0.2, 0.0), disc(0.2, 0.025), disc(0.17, 0.035)], (0.82, 0.82, 0.85))
    b.loft("vitre", [disc(0.17, 0.035), disc(0.12, 0.05)], (0.35, 0.4, 0.45))
    b.cap("vitre", disc(0.12, 0.05), (math.sin(math.radians(rot)), 0, math.cos(math.radians(rot))), (0.3, 0.35, 0.4))
    _ocollider(b, cx, y0, cz, 0.6, 0.85, 0.6, rot)


def crate(b, cx, cz, y0, size=0.45, rot=0.0):
    if b.model("wooden_crate_01", cx, cz, y0, rot, (size, size * 0.8, size), stretch=True, free_yaw=True):
        _ocollider(b, cx, y0, cz, size, size * 0.8, size, rot)
        return
    b.obox("planches", cx, y0, cz, size, size * 0.8, size, rot, (0.9, 0.85, 0.8), collide=True)


def delivery_bag(b, cx, cz, y0, rot=0.0, torn=True):
    b.obox("sac_quickeats", cx, y0, cz, 0.4, 0.4, 0.28, rot, (0.7, 0.7, 0.7) if torn else (1, 1, 1))


def shelving_unit(b, x0, z0, x1, z1, y0, face="+x", levels=4, height=1.9):
    # montants débordant de 4 mm autour des tablettes : sinon les chants des planches sont coplanaires
    # avec les faces des montants et scintillent (z-fighting)
    e = 0.004
    for post in ((x0, z0), (x0, z1 - 0.05), (x1 - 0.05, z0), (x1 - 0.05, z1 - 0.05)):
        b.box("metal", post[0] - e, y0, post[1] - e, post[0] + 0.05 + e, y0 + height, post[1] + 0.05 + e, (0.7, 0.7, 0.7))
    for l in range(levels):
        yy = y0 + 0.15 + l * (height - 0.2) / levels
        b.box("planches", x0, yy, z0, x1, yy + 0.03, z1, (0.8, 0.75, 0.7))
    b.colliders.append((x0, y0, z0, x1, y0 + height, z1))


def freezer(b, cx, cz, y0):
    """Congélateur horizontal (le couvercle est une entité animée séparée)."""
    shell = [_ring(cx, cz, y0 + yy, 0.9, 0.45, 0.0, 10.0) for yy in (0.04, 0.82)]
    b.loft("email", shell, (0.95, 0.95, 0.93))
    b.cap("email", shell[0], (0, -1, 0), (0.9, 0.9, 0.88))
    _basin(b, "email", cx, cz, 0.0, y0 + 0.82, (0.9, 0.45), (0.82, 0.37), 0.72, (0.62, 0.66, 0.68), n_out=10.0, n_in=10.0,
           bulge=(1.0, 0.99, 0.98, 0.97, 0.96))
    b.box("beton", cx - 0.88, y0, cz - 0.43, cx + 0.88, y0 + 0.04, cz + 0.43, (0.2, 0.2, 0.2))
    b.box("metal", cx - 0.12, y0 + 0.72, cz - 0.47, cx + 0.12, y0 + 0.76, cz - 0.45, (0.75, 0.75, 0.78))
    for k in range(6):
        b.box("metal", cx + 0.5 + k * 0.05, y0 + 0.08, cz - 0.452, cx + 0.52 + k * 0.05, y0 + 0.25, cz - 0.45, (0.3, 0.3, 0.32))
    b.colliders.append((cx - 0.9, y0, cz - 0.45, cx + 0.9, y0 + 0.82, cz + 0.45))


def painting(b, x, y, z, w, h, facing, tex="portrait", thick=0.03):
    """Cadre accroché à un mur. facing = '+x','-x','+z','-z' (direction de la face visible)."""
    if facing == "+z":
        b.box("bois_meuble", x - w / 2 - 0.03, y - h / 2 - 0.03, z, x + w / 2 + 0.03, y + h / 2 + 0.03, z + thick, DARKWOOD)
        # vu depuis +z (regard vers -z), la droite de l'écran est -x : u part de x + w/2 (sinon image en miroir)
        b.quad(tex, (x + w / 2, y - h / 2, z + thick + 0.002), (x - w / 2, y - h / 2, z + thick + 0.002),
               (x - w / 2, y + h / 2, z + thick + 0.002), (x + w / 2, y + h / 2, z + thick + 0.002), (0, 0, 1), (1, 1, 1), tile=(w, h))
    elif facing == "-z":
        b.box("bois_meuble", x - w / 2 - 0.03, y - h / 2 - 0.03, z - thick, x + w / 2 + 0.03, y + h / 2 + 0.03, z, DARKWOOD)
        b.quad(tex, (x - w / 2, y - h / 2, z - thick - 0.002), (x + w / 2, y - h / 2, z - thick - 0.002),
               (x + w / 2, y + h / 2, z - thick - 0.002), (x - w / 2, y + h / 2, z - thick - 0.002), (0, 0, -1), (1, 1, 1), tile=(w, h))
    elif facing == "+x":
        b.box("bois_meuble", x, y - h / 2 - 0.03, z - w / 2 - 0.03, x + thick, y + h / 2 + 0.03, z + w / 2 + 0.03, DARKWOOD)
        b.quad(tex, (x + thick + 0.002, y - h / 2, z - w / 2), (x + thick + 0.002, y - h / 2, z + w / 2),
               (x + thick + 0.002, y + h / 2, z + w / 2), (x + thick + 0.002, y + h / 2, z - w / 2), (1, 0, 0), (1, 1, 1), tile=(w, h))
    else:
        b.box("bois_meuble", x - thick, y - h / 2 - 0.03, z - w / 2 - 0.03, x, y + h / 2 + 0.03, z + w / 2 + 0.03, DARKWOOD)
        b.quad(tex, (x - thick - 0.002, y - h / 2, z + w / 2), (x - thick - 0.002, y - h / 2, z - w / 2),
               (x - thick - 0.002, y + h / 2, z - w / 2), (x - thick - 0.002, y + h / 2, z + w / 2), (-1, 0, 0), (1, 1, 1), tile=(w, h))


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
