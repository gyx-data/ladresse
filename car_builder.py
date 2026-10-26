"""Voitures du quartier : carrosserie modelée à partir d'un profil latéral extrudé.

Trois silhouettes (citadine, berline, utilitaire) : capot incliné, pare-brise et lunette arrière en pente,
habitacle plus étroit que la caisse, montants, vitres latérales, passages de roue, roues rondes (pneu sculpté,
flanc, jante brossée, moyeu), pare-chocs, calandre, lignes de portes, poignées, rétroviseurs, plaques.
Les feux sont construits à part (builder émissif) avec `lights()`.

Repère de la voiture : u = longueur (+u = avant), v = hauteur, w = largeur. `along_x` : u suit l'axe x
du monde (sinon l'axe z).
"""
import math

L = 4.1          # longueur commune (collisions, places de parking)
W = 1.76         # largeur
WHEEL_R = 0.31
WHEEL_U = 1.32
SILL = 0.26      # bas de caisse

PROFILES = {
    # caisse (bas de caisse -> ligne de ceinture), habitacle (ceinture -> toit)
    "citadine": dict(
        body=[(-L / 2, 0.36), (-L / 2, 0.84), (-L / 2 + 0.12, 0.9), (0.95, 0.9), (1.6, 0.8), (L / 2, 0.66), (L / 2, 0.34)],
        cabin=[(-L / 2 + 0.12, 0.9), (-L / 2 + 0.3, 1.42), (0.35, 1.45), (0.95, 0.9)],
        pillar_b=-0.3),
    "berline": dict(
        body=[(-L / 2, 0.34), (-L / 2, 0.74), (-L / 2 + 0.5, 0.84), (-0.85, 0.88), (0.95, 0.88), (1.72, 0.78), (L / 2, 0.66), (L / 2, 0.32)],
        cabin=[(-0.85, 0.88), (-0.45, 1.36), (0.42, 1.38), (0.95, 0.88)],
        pillar_b=-0.02),
    "utilitaire": dict(
        body=[(-L / 2, 0.34), (-L / 2, 1.0), (1.05, 1.0), (1.6, 0.86), (L / 2, 0.74), (L / 2, 0.34)],
        cabin=[(-L / 2, 1.0), (-L / 2, 1.9), (0.62, 1.92), (1.05, 1.0)],
        pillar_b=0.2, panel_van=True),
}
KINDS = ("citadine", "berline", "utilitaire")

GLASS = (0.13, 0.16, 0.2)       # verre teinté opaque (texture « carrosserie » : reflet du ciel)
TRIM = (0.06, 0.06, 0.07)
CHROME = (0.85, 0.86, 0.9)


class _Frame:
    """Conversion repère voiture (u, v, w) -> monde."""

    def __init__(self, cx, cy, cz, along_x):
        self.cx, self.cy, self.cz, self.ax = cx, cy, cz, along_x

    def p(self, u, v, w):
        return (self.cx + u, self.cy + v, self.cz + w) if self.ax else (self.cx + w, self.cy + v, self.cz + u)

    def n(self, nu, nv, nw):
        return (nu, nv, nw) if self.ax else (nw, nv, nu)


def _unit(a, b):
    l = math.hypot(a, b) or 1.0
    return a / l, b / l


def _extrude(b, f, prof, half_w, tex, col, tile, top_tex=None, top_col=None, bottom=None):
    """Extrude un profil (u croissant, v = haut) entre w = -half_w et +half_w."""
    base = bottom if bottom is not None else min(v for _, v in prof)
    for side in (-1, 1):                      # flancs
        w = side * half_w
        for (u0, v0), (u1, v1) in zip(prof, prof[1:]):
            if abs(u1 - u0) < 1e-6:
                continue
            b.quad(tex, f.p(u0, base, w), f.p(u1, base, w), f.p(u1, v1, w), f.p(u0, v0, w), f.n(0, 0, side), col, tile=tile)
    for (u0, v0), (u1, v1) in zip(prof, prof[1:]):   # dessus (et faces avant / arrière verticales)
        nu, nv = _unit(-(v1 - v0), (u1 - u0))
        if abs(u1 - u0) < 1e-6:
            nu, nv = (1.0 if u0 > 0 else -1.0), 0.0
        b.quad(top_tex or tex, f.p(u0, v0, -half_w), f.p(u1, v1, -half_w), f.p(u1, v1, half_w), f.p(u0, v0, half_w),
               f.n(nu, nv, 0), top_col or col, tile=tile)


def _wheel(b, f, u, w_side, seg=14):
    """Roue : bande de roulement, flanc et jante sur la face extérieure."""
    r, rr, hub = WHEEL_R, WHEEL_R * 0.62, WHEEL_R * 0.18
    wi, wo = w_side * (W / 2 - 0.24), w_side * (W / 2 + 0.005)
    vc = WHEEL_R
    pts = [(u + r * math.cos(2 * math.pi * k / seg), vc + r * math.sin(2 * math.pi * k / seg)) for k in range(seg + 1)]
    for k in range(seg):
        (u0, v0), (u1, v1) = pts[k], pts[k + 1]
        a = 2 * math.pi * (k + 0.5) / seg
        b.quad("pneu", f.p(u0, v0, wi), f.p(u1, v1, wi), f.p(u1, v1, wo), f.p(u0, v0, wo), f.n(math.cos(a), math.sin(a), 0),
               (1, 1, 1), tile=(0.3, 0.3))
    n_out = f.n(0, 0, w_side)
    for k in range(seg):                      # flanc du pneu (anneau) puis jante (disque) puis moyeu
        a0, a1 = 2 * math.pi * k / seg, 2 * math.pi * (k + 1) / seg
        o0, o1 = (u + r * math.cos(a0), vc + r * math.sin(a0)), (u + r * math.cos(a1), vc + r * math.sin(a1))
        i0, i1 = (u + rr * math.cos(a0), vc + rr * math.sin(a0)), (u + rr * math.cos(a1), vc + rr * math.sin(a1))
        b.quad("pneu", f.p(*i0, wo), f.p(*i1, wo), f.p(*o1, wo), f.p(*o0, wo), n_out, (1, 1, 1), tile=(0.3, 0.3))
        b.tri("jante", f.p(u, vc, wo + w_side * 0.012), f.p(*i0, wo + w_side * 0.004), f.p(*i1, wo + w_side * 0.004), n_out,
              (0.78, 0.79, 0.82), tile=0.4)
        if k % 2 == 0:                        # rayons sombres
            m0 = (u + rr * 0.92 * math.cos(a0), vc + rr * 0.92 * math.sin(a0))
            m1 = (u + hub * math.cos(a1), vc + hub * math.sin(a1))
            b.tri("metal", f.p(u, vc, wo + w_side * 0.014), f.p(*m0, wo + w_side * 0.013), f.p(*m1, wo + w_side * 0.013),
                  n_out, (0.18, 0.18, 0.2), tile=0.4)


def _arch(b, f, u, w_side, seg=10):
    """Passage de roue sombre sur le flanc."""
    r = WHEEL_R + 0.06
    w = w_side * (W / 2 + 0.003)
    for k in range(seg):
        a0, a1 = math.pi * k / seg, math.pi * (k + 1) / seg
        b.tri("metal", f.p(u, WHEEL_R, w), f.p(u + r * math.cos(a0), WHEEL_R + r * math.sin(a0), w),
              f.p(u + r * math.cos(a1), WHEEL_R + r * math.sin(a1), w), f.n(0, 0, w_side), TRIM)


def _box(b, f, u, v, w, su, sv, sw, tex, col):
    """Petite boîte alignée sur le repère voiture."""
    x, y, z = f.p(u, v, w)
    sx, sz = (su, sw) if f.ax else (sw, su)
    b.box(tex, x - sx / 2, y, z - sz / 2, x + sx / 2, y + sv, z + sz / 2, col)


def build(b, cx, cz, col, along_x=True, kind="berline", police=False, y=0.0):
    """Ajoute une voiture au MeshBuilder `b` ; centre au sol (cx, cz)."""
    prof = PROFILES.get(kind, PROFILES["berline"])
    f = _Frame(cx, y, cz, along_x)
    body = (0.93, 0.93, 0.95) if police else col
    tile = (L, 1.6)
    # caisse
    _extrude(b, f, prof["body"], W / 2, "carrosserie", body, tile, bottom=SILL)
    b.quad("metal", f.p(-L / 2, SILL, -W / 2), f.p(L / 2, SILL, -W / 2), f.p(L / 2, SILL, W / 2), f.p(-L / 2, SILL, W / 2),
           f.n(0, -1, 0), TRIM)
    # habitacle : vitres (flancs + pare-brise + lunette) et toit peint
    cab = prof["cabin"]
    cw = W / 2 - 0.09
    v_belt = cab[0][1]
    for side in (-1, 1):
        w = side * cw
        for (u0, v0), (u1, v1) in zip(cab, cab[1:]):
            if abs(u1 - u0) < 1e-6:
                continue
            b.quad("carrosserie", f.p(u0, v_belt, w), f.p(u1, v_belt, w), f.p(u1, v1, w), f.p(u0, v0, w), f.n(0, 0, side), GLASS,
                   tile=tile)
        if prof.get("panel_van"):
            # utilitaire : flanc arrière tôlé (pas de vitres derrière les portes avant)
            u_end = prof["pillar_b"]
            top = cab[1][1] - 0.02
            b.quad("carrosserie", f.p(-L / 2, v_belt, w * 1.002), f.p(u_end, v_belt, w * 1.002), f.p(u_end, top, w * 1.002),
                   f.p(-L / 2, top, w * 1.002), f.n(0, 0, side), body, tile=tile)
        # montant central + bas des vitres (couleur caisse)
        ub = prof["pillar_b"]
        roof_v = max(v for _, v in cab) - 0.04
        b.quad("carrosserie", f.p(ub - 0.05, v_belt, w * 1.004), f.p(ub + 0.05, v_belt, w * 1.004), f.p(ub + 0.05, roof_v, w * 1.004),
               f.p(ub - 0.05, roof_v, w * 1.004), f.n(0, 0, side), TRIM if not police else body)
        # montants avant (pare-brise) et arrière (lunette), couleur caisse
        (ua0, va0), (ua1, va1) = cab[-2], cab[-1]
        b.quad("carrosserie", f.p(ua1 - 0.09, va1, w * 1.004), f.p(ua1, va1, w * 1.004), f.p(ua0, va0, w * 1.004),
               f.p(ua0 - 0.09, va0, w * 1.004), f.n(0, 0, side), body, tile=tile)
        (uc0, vc0), (uc1, vc1) = cab[0], cab[1]
        if abs(uc1 - uc0) > 1e-6:
            b.quad("carrosserie", f.p(uc0, vc0, w * 1.004), f.p(uc0 + 0.11, vc0, w * 1.004), f.p(uc1 + 0.11, vc1, w * 1.004),
                   f.p(uc1, vc1, w * 1.004), f.n(0, 0, side), body, tile=tile)
        # bandeau de toit au-dessus des vitres
        b.quad("carrosserie", f.p(cab[1][0], roof_v - 0.03, w * 1.004), f.p(cab[2][0], roof_v - 0.03, w * 1.004),
               f.p(cab[2][0], roof_v + 0.04, w * 1.004), f.p(cab[1][0], roof_v + 0.04, w * 1.004), f.n(0, 0, side), body, tile=tile)
    for (u0, v0), (u1, v1) in zip(cab, cab[1:]):
        nu, nv = _unit(-(v1 - v0), (u1 - u0))
        flat = abs(v1 - v0) < 0.1 and abs(u1 - u0) > 0.3
        c = body if flat else GLASS
        if abs(u1 - u0) < 1e-6:
            nu, nv = (1.0 if u0 > 0 else -1.0), 0.0
            c = body if kind == "utilitaire" else GLASS
        tex = "carrosserie"
        b.quad(tex, f.p(u0, v0, -cw), f.p(u1, v1, -cw), f.p(u1, v1, cw), f.p(u0, v0, cw), f.n(nu, nv, 0), c, tile=tile)
    # roues + passages de roue
    for su in (-1, 1):
        for sw in (-1, 1):
            _arch(b, f, su * WHEEL_U, sw)
            _wheel(b, f, su * WHEEL_U, sw)
    # pare-chocs, calandre, plaques
    front_v = prof["body"][-1][1]
    for s in (-1, 1):
        _box(b, f, s * (L / 2 + 0.03), SILL + 0.06, 0, 0.1, 0.16, W - 0.06, "metal", TRIM)
        _box(b, f, s * (L / 2 + 0.06), SILL + 0.2, 0, 0.012, 0.12, 0.52, "platre", (0.96, 0.96, 0.96))
        _box(b, f, s * (L / 2 + 0.067), SILL + 0.2, -0.24, 0.006, 0.12, 0.04, "metal", (0.1, 0.2, 0.7))   # bande bleue UE
    _box(b, f, L / 2 + 0.005, front_v + 0.02, 0, 0.02, 0.14, 0.7, "metal", (0.05, 0.05, 0.06))          # calandre
    _box(b, f, L / 2 + 0.012, front_v + 0.08, 0, 0.012, 0.02, 0.66, "jante", CHROME)
    # lignes de portes, poignées, rétroviseurs
    for side in (-1, 1):
        w = side * (W / 2 + 0.002)
        n = f.n(0, 0, side)
        doors = (prof["pillar_b"] - 0.02, prof["pillar_b"] + 0.95) if kind != "utilitaire" else (prof["pillar_b"] + 0.02, 1.0)
        for ud in doors:
            b.quad("metal", f.p(ud - 0.006, SILL + 0.08, w), f.p(ud + 0.006, SILL + 0.08, w), f.p(ud + 0.006, v_belt - 0.02, w),
                   f.p(ud - 0.006, v_belt - 0.02, w), n, TRIM)
        b.quad("metal", f.p(-L / 2 + 0.2, v_belt - 0.03, w), f.p(L / 2 - 0.4, v_belt - 0.03, w), f.p(L / 2 - 0.4, v_belt - 0.02, w),
               f.p(-L / 2 + 0.2, v_belt - 0.02, w), n, CHROME)
        for ud in doors:
            _box(b, f, ud - 0.25, v_belt - 0.16, side * (W / 2 + 0.01), 0.14, 0.03, 0.02, "jante", CHROME)
        mu = cab[-1][0] - 0.12
        _box(b, f, mu, v_belt + 0.02, side * (W / 2 + 0.06), 0.1, 0.1, 0.14, "carrosserie", body)
        _box(b, f, mu + 0.051, v_belt + 0.03, side * (W / 2 + 0.07), 0.004, 0.07, 0.1, "vitre", (0.55, 0.62, 0.7))
    if police:
        for side in (-1, 1):                  # bandes bleu / blanc / rouge
            w = side * (W / 2 + 0.004)
            for v0, v1, c in ((0.5, 0.62, (0.1, 0.2, 0.65)), (0.47, 0.5, (0.8, 0.1, 0.12))):
                b.quad("metal", f.p(-L / 2 + 0.05, v0, w), f.p(L / 2 - 0.05, v0, w), f.p(L / 2 - 0.05, v1, w),
                       f.p(-L / 2 + 0.05, v1, w), f.n(0, 0, side), c)
        roof_u = (cab[1][0] + cab[2][0]) / 2
        roof_v = max(v for _, v in cab)
        _box(b, f, roof_u, roof_v, 0, 0.3, 0.08, 1.1, "metal", (0.1, 0.1, 0.12))       # support de gyrophare
    return 0 if along_x else 90


def lights(be, cx, cz, along_x=True, front_sign=1, y=0.0, kind="berline"):
    """Phares avant (blancs, en amande) et feux arrière (rouges) dans un builder émissif."""
    f = _Frame(cx, y, cz, along_x)
    prof = PROFILES.get(kind, PROFILES["berline"])
    fv = prof["body"][-1][1] + 0.2
    rv = prof["body"][1][1] - 0.18
    for s, col, v in ((front_sign, (1.0, 0.96, 0.82), fv), (-front_sign, (0.95, 0.06, 0.05), rv)):
        for o in (-0.6, 0.6):
            _box(be, f, s * (L / 2 + 0.012), v, o, 0.02, 0.1, 0.3, "neon", col)
