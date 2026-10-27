"""Chez Mme Bianchi, 11 rue des Lilas : la villa voisine, explorable pendant la balade dans le quartier.

La voisine sait. Elle a observé le 17 pendant des années depuis la pièce du haut (jumelles sur trépied braquées sur
la maison de Garnier, mur de polaroïds), elle a gardé chaque sac QuickEats qu'on lui a livré sans jamais l'ouvrir,
et elle a tracé une ligne de sel devant SA porte. La porte est entrouverte (elle « laisse toujours ouvert pour le chat »).

Repère : lot nord de la rue des Lilas, façade côté rue en z = Z0 (vers -z), porte au centre (x = DOOR_X).
Rez-de-chaussée : entrée et couloir (escalier), salon (ouest, avant), cuisine (est, avant, fenêtre sur le 17),
salle à manger (ouest, fond), salle de bain (est, fond).
Étage : palier, chambre (ouest, avant), débarras (ouest, fond), pièce d'observation (est, avant, fenêtre sur le 17),
pièce des sacs (est, fond).

La coque extérieure est construite par nb._villa(..., explorable=True) (sans collision, ni face est : la face est
est construite ici, percée des fenêtres de la cuisine et de la pièce d'observation). Tout objet posé l'est sur un
support réel (sol, plateau d'un meuble dont la hauteur est connue), jamais à une hauteur approximative.
"""
import math

from lighting_system import LightSource
from house_generator import rect_minus
from room_builder import (TILE, PHOTO_SCALE, sofa, armchair, table, chair, bookshelf, bed, wardrobe, counter, carton,
                          crate, pleated_panel, covered_furniture, rod, lathe, toilet, sink, bathtub, fridge_body,
                          coat_rack, candle, delivery_bag, painting, floor_decal, stairs_mesh, shelving_unit, DARKWOOD)

X0, X1, Z0, Z1, H = -32.0, -20.0, -2.4, 7.6, 7.0
DOOR_X = (X0 + X1) / 2
F = 0.6                     # sol du rez-de-chaussée (dessus du soubassement en pierre)
CEIL = F + 2.75             # plafond du rez-de-chaussée
F2 = 3.55                   # sol de l'étage (dalle de 20 cm)
CEIL2 = F2 + 2.85           # plafond de l'étage (sous la corniche à H - 0.26)
T = 0.18                    # épaisseur des murs extérieurs (doublage intérieur)
TP = 0.14                   # épaisseur des cloisons
XI0, XI1, ZI0, ZI1 = X0 + T, X1 - T, Z0 + T, Z1 - T
HALL_X0, HALL_X1 = DOOR_X - 1.4, DOOR_X + 1.4
BACK_Z = 3.0                # cloison entre les pièces de devant et celles du fond (aux deux niveaux)
# escalier droit contre la cloison est du couloir, montant vers le fond (+z)
SX1 = HALL_X1 - TP / 2
SX0 = SX1 - 1.0
SZ0, SZ1 = 1.2, 5.6
STEPS = 16
WALL_TEX, WALL_COL = "crepi_rose", (0.9, 0.88, 0.85)      # enduit de la coque (même lot dans neighborhood.py)

# fenêtres de la façade (mêmes emplacements que nb._villa) : bord gauche en x, à 1,0 m et 4,0 m du sol extérieur
FRONT_WIN_X = (-31.0, -28.4, -25.8, -23.2)
WIN_W, WIN_H = 0.9, 1.4
# fenêtres du pignon est, vers le 17 : (z centre, largeur, y bas, y haut)
EAST_WIN = ((0.0, 1.0, F + 0.95, F + 2.15), (0.0, 1.0, F2 + 0.8, F2 + 2.0))

NOTEBOOK = [
    "LE 17\n\n3 mars\nEncore un livreur devant chez Garnier. Il ne sonne pas. Il reste sous le lampadaire jusqu'à "
    "l'aube. Garnier n'ouvre pas. Il a raison.",
    "19 mars\n\nQuand il tape sur son téléphone, une lumière bleue sort de sous la porte du 17. "
    "Les messages que Garnier reçoit à ce moment-là ne viennent pas de QuickEats.",
    "2 avril\n\nIl a demandé le code du portail à Garnier. Toute la nuit. Garnier a fini par le donner.\n"
    "Le lendemain, la porte du 17 était ouverte et la maison sentait le froid.",
    "11 avril\n\nIl m'a regardée. Il sait que je regarde. Ce soir je ne regarde pas.",
    "(dernière page, écriture tremblée)\n\nIls disent qu'on peut revenir en arrière quand on se trompe. "
    "Une fois, deux fois. Pas toujours. Ne compte pas dessus.",
]
PHONE = [
    "Téléphone de Mme Bianchi — notifications (l'an dernier)\n\n"
    "QuickEats · 23:12  Votre commande est confirmée.\n"
    "QuickEats · 23:40  Votre livreur est arrivé.\n"
    "Votre livreur · 23:41  C'est quoi le code ?\n"
    "Votre livreur · 23:58  Je sais que vous êtes réveillée.\n"
    "QuickEats · 00:14  Votre commande a été annulée il y a 40 minutes.\n"
    "Votre livreur · 02:03  Votre adresse a été ajoutée à mes favoris.",
]
FRIDGE_NOTE = ("Sur le frigo, au feutre rouge :\n\n« PAS DE COMMANDE APRÈS 23 H. JAMAIS.\n"
               "S'IL DEMANDE LE CODE : NE RÉPONDS PAS. »")


# -----------------------------------------------------------------------------------------------------------------
# Murs
# -----------------------------------------------------------------------------------------------------------------
def _lining(b, tex, axis, plane, inward, a0, a1, y0, y1, holes=(), col=(1, 1, 1), depth=T):
    """Face intérieure d'un mur extérieur : un plan (z = plane si axis == 'x', x = plane sinon) tourné vers
    `inward` (+1 / -1), percé de `holes` = (a0, y0, a1, y1), avec tableaux en plâtre jusqu'à la face extérieure.
    Une seule face (le dos est contre la coque) : pas de faces confondues avec l'enduit extérieur."""
    tu = TILE.get(tex, 1.0) * PHOTO_SCALE.get(tex, 1.0)
    tu = tu[0] if isinstance(tu, (tuple, list)) else tu

    def pt(a, y, off=0.0):
        p = plane - inward * off
        return (a, y, p) if axis == "x" else (p, y, a)

    nrm = (0, 0, inward) if axis == "x" else (inward, 0, 0)
    parts = [(a0, y0, a1, y1)]
    for hole in holes:
        parts = [q for p in parts for q in rect_minus(p, hole)]
    for (ua, va, ub, vb) in parts:
        if ub - ua < 1e-4 or vb - va < 1e-4:
            continue
        b.quad(tex, pt(ua, va), pt(ub, va), pt(ub, vb), pt(ua, vb), nrm, col, uv_off=((ua - a0) / tu, (va - y0) / tu))
    for (ha, hy0, hb, hy1) in holes:
        # tableaux : appui (vers le haut), linteau (vers le bas), jambages (vers le centre de la baie)
        rv = (0.93, 0.91, 0.87)
        b.quad("platre", pt(ha, hy0), pt(hb, hy0), pt(hb, hy0, depth), pt(ha, hy0, depth), (0, 1, 0), rv)
        b.quad("platre", pt(ha, hy1), pt(hb, hy1), pt(hb, hy1, depth), pt(ha, hy1, depth), (0, -1, 0), rv)
        side = (1, 0, 0) if axis == "x" else (0, 0, 1)
        b.quad("platre", pt(ha, hy0), pt(ha, hy0, depth), pt(ha, hy1, depth), pt(ha, hy1), side, rv)
        b.quad("platre", pt(hb, hy0), pt(hb, hy0, depth), pt(hb, hy1, depth), pt(hb, hy1),
               tuple(-c for c in side), rv)
    # collisions : le mur entier moins les portes (les fenêtres restent bloquantes)
    solid = [(a0, y0, a1, y1)]
    for hole in holes:
        if hole[1] <= y0 + 0.01:
            solid = [q for p in solid for q in rect_minus(p, hole)]
    for (ua, va, ub, vb) in solid:
        p0, p1 = sorted((plane, plane - inward * depth))
        if axis == "x":
            b.colliders.append((ua, va, p0, ub, vb, p1))
        else:
            b.colliders.append((p0, va, ua, p1, vb, ub))


def _window_inside(b, axis, plane, inward, a0, a1, y0, y1, depth=T, curtains=True):
    """Vitre (deux faces, transparente) au milieu du tableau, petit bois, rideaux de dentelle et tringle."""
    mid = plane - inward * depth * 0.55

    def pt(a, y, p):
        return (a, y, p) if axis == "x" else (p, y, a)

    nrm = (0, 0, inward) if axis == "x" else (inward, 0, 0)
    for n in (nrm, tuple(-c for c in nrm)):
        b.quad("vitre", pt(a0, y0, mid), pt(a1, y0, mid), pt(a1, y1, mid), pt(a0, y1, mid), n, (0.75, 0.8, 0.85))
    am = (a0 + a1) / 2
    for (u0, u1, v0, v1) in ((am - 0.02, am + 0.02, y0, y1), (a0, a1, (y0 + y1) / 2 - 0.02, (y0 + y1) / 2 + 0.02)):
        p0, p1 = sorted((mid - 0.015, mid + 0.015))
        if axis == "x":
            b.box("bois_meuble", u0, v0, p0, u1, v1, p1, (0.92, 0.9, 0.86))
        else:
            b.box("bois_meuble", p0, v0, u0, p1, v1, u1, (0.92, 0.9, 0.86))
    if not curtains:
        return
    front = plane + inward * 0.06
    top = y1 + 0.18
    if axis == "x":
        rod(b, "metal", (a0 - 0.35, top, front), (a1 + 0.35, top, front), 0.012, col=(0.35, 0.3, 0.22), caps=True)
        for c in (a0 - 0.12, a1 + 0.12):
            pleated_panel(b, "rideau", c, y0 - 0.25, front, 0.42, top - y0 + 0.23, axis="x", depth=0.025, folds=5,
                          col=(0.95, 0.93, 0.86))
    else:
        rod(b, "metal", (front, top, a0 - 0.35), (front, top, a1 + 0.35), 0.012, col=(0.35, 0.3, 0.22), caps=True)
        for c in (a0 - 0.12, a1 + 0.12):
            pleated_panel(b, "rideau", front, y0 - 0.25, c, 0.42, top - y0 + 0.23, axis="z", depth=0.025, folds=5,
                          col=(0.95, 0.93, 0.86))


def _skirting(b, axis, plane, inward, a0, a1, y, gaps=()):
    """Plinthe en bois le long d'un mur, interrompue aux portes."""
    segs = [(a0, a1)]
    for (g0, g1) in gaps:
        segs = [s for (s0, s1) in segs for s in ((s0, min(s1, g0)), (max(s0, g1), s1)) if s[1] - s[0] > 0.02]
    for (s0, s1) in segs:
        p0, p1 = sorted((plane, plane + inward * 0.018))
        if axis == "x":
            b.box("bois_meuble", s0, y, p0, s1, y + 0.1, p1, (0.42, 0.3, 0.2), skip=("-y",))
        else:
            b.box("bois_meuble", p0, y, s0, p1, y + 0.1, s1, (0.42, 0.3, 0.2), skip=("-y",))


def _east_facade(b, be, rng):
    """Pignon est (côté 17) : enduit percé des deux fenêtres, encadrements, appuis, persiennes ouvertes."""
    tu = TILE.get(WALL_TEX, 1.0) * PHOTO_SCALE.get(WALL_TEX, 1.0)
    holes = []
    for (zc, w, ya, yb) in EAST_WIN:
        za, zb = zc - w / 2, zc + w / 2
        holes.append((za, ya, zb, yb))
        for (u0, u1, v0, v1) in ((za - 0.08, za, ya - 0.02, yb), (zb, zb + 0.08, ya - 0.02, yb), (za - 0.08, zb + 0.08, yb, yb + 0.12)):
            b.box("crepi", X1 - 0.025, v0, u0, X1 + 0.07, v1, u1, (0.97, 0.96, 0.93))
            holes.append((u0, v0, u1, v1))
        b.box("beton", X1 - 0.025, ya - 0.1, za - 0.12, X1 + 0.14, ya - 0.02, zb + 0.12, (0.75, 0.73, 0.7))
        holes.append((za - 0.12, ya - 0.1, zb + 0.12, ya - 0.02))
        for s0 in (za - 0.54, zb + 0.1):
            b.box("volet", X1 - 0.025, ya - 0.02, s0, X1 + 0.05, yb + 0.02, s0 + 0.44, (0.85, 0.95, 0.9))
            holes.append((s0, ya - 0.02, s0 + 0.44, yb + 0.02))
    parts = [(Z0, 0.6, Z1, H - 0.26)]
    for hole in holes:
        parts = [q for p in parts for q in rect_minus(p, hole)]
    for (za, ya, zb, yb) in parts:
        if zb - za < 1e-4 or yb - ya < 1e-4:
            continue
        b.quad(WALL_TEX, (X1, ya, za), (X1, ya, zb), (X1, yb, zb), (X1, yb, za), (1, 0, 0), WALL_COL,
               uv_off=((za - Z0) / tu, ya / tu))


# -----------------------------------------------------------------------------------------------------------------
# Construction
# -----------------------------------------------------------------------------------------------------------------
def build(nb, b, be, rng):
    """Intérieur de la villa sur deux niveaux."""
    cols = b.colliders
    e = 0.012                                   # retrait des doublages par rapport à la coque
    _east_facade(b, be, rng)

    # --- doublages des murs extérieurs, pièce par pièce (papier peint propre à chaque pièce) -----------------
    door = (DOOR_X - 0.5, F, DOOR_X + 0.5, F + 2.1)
    back_door = (DOOR_X - 0.45, F, DOOR_X + 0.45, F + 2.0)
    gwin = [(x, 1.0, x + WIN_W, 1.0 + WIN_H) for x in FRONT_WIN_X if abs(x + 0.45 - DOOR_X) >= 1.0]
    uwin = [(x, 4.0, x + WIN_W, 4.0 + WIN_H) for x in FRONT_WIN_X]
    ewin = [(zc - w / 2, ya, zc + w / 2, yb) for (zc, w, ya, yb) in EAST_WIN]
    zf, zb_, xw, xe = Z0 + T, Z1 - T, X0 + T, X1 - T            # plans intérieurs
    d = T - e
    rooms_x = ((XI0, HALL_X0 - TP / 2), (HALL_X0 - TP / 2, HALL_X1 + TP / 2), (HALL_X1 + TP / 2, XI1))
    ground_tex = (("papier_peint", (0.95, 0.88, 0.78)), ("papier_couloir", (0.9, 0.85, 0.76)), ("platre", (0.96, 0.92, 0.82)))
    back_tex = (("papier_peint", (0.78, 0.86, 0.8)), ("papier_couloir", (0.9, 0.85, 0.76)), ("carrelage", (0.92, 0.94, 0.95)))
    up_front = (("papier_chambre", (1.0, 0.92, 0.9)), ("papier_couloir", (0.86, 0.82, 0.76)), ("papier_peint", (0.8, 0.78, 0.72)))
    up_back = (("platre", (0.82, 0.8, 0.76)), ("papier_couloir", (0.86, 0.82, 0.76)), ("platre", (0.74, 0.72, 0.68)))
    for (a0, a1), (tg, cg), (tb, cb), (tu_, cu), (tv, cv) in zip(rooms_x, ground_tex, back_tex, up_front, up_back):
        _lining(b, tg, "x", zf, 1, a0, a1, F, F2, [h for h in gwin + [door] if h[0] < a1 and h[2] > a0], cg, d)
        _lining(b, tu_, "x", zf, 1, a0, a1, F2, CEIL2, [h for h in uwin if h[0] < a1 and h[2] > a0], cu, d)
        _lining(b, tb, "x", zb_, -1, a0, a1, F, F2, [back_door] if a0 < DOOR_X < a1 else [], cb, d)
        _lining(b, tv, "x", zb_, -1, a0, a1, F2, CEIL2, [], cv, d)
    for (z0_, z1_), (tg, cg), (tb, cb) in (((ZI0, BACK_Z - TP / 2), ground_tex[0], up_front[0]),
                                           ((BACK_Z + TP / 2, ZI1), back_tex[0], up_back[0])):
        _lining(b, tg, "z", xw, 1, z0_, z1_, F, F2, [], cg, d)
        _lining(b, tb, "z", xw, 1, z0_, z1_, F2, CEIL2, [], cb, d)
    _lining(b, ground_tex[2][0], "z", xe, -1, ZI0, BACK_Z - TP / 2, F, F2, [ewin[0]], ground_tex[2][1], d)
    _lining(b, up_front[2][0], "z", xe, -1, ZI0, BACK_Z - TP / 2, F2, CEIL2, [ewin[1]], up_front[2][1], d)
    _lining(b, back_tex[2][0], "z", xe, -1, BACK_Z + TP / 2, ZI1, F, F2, [], back_tex[2][1], d)
    _lining(b, up_back[2][0], "z", xe, -1, BACK_Z + TP / 2, ZI1, F2, CEIL2, [], up_back[2][1], d)
    for (x, y, _, y1) in gwin + uwin:
        _window_inside(b, "x", zf, 1, x, x + WIN_W, y, y1, d)
    for (za, ya, zb, yb) in ewin:
        _window_inside(b, "z", xe, -1, za, zb, ya, yb, d)

    # --- cloisons (deux faces, une texture par pièce) -----------------------------------------------------------
    def part(axis, a0, a1, fixed, y0, y1, doors, t_neg, t_pos, c_neg=(1, 1, 1), c_pos=(1, 1, 1)):
        b.wall_openings(axis, a0, a1, fixed, y0, y1, [(c, w, 0.0, 2.05) for (c, w) in doors], thick=TP,
                        tex_neg=t_neg, tex_pos=t_pos, col_neg=c_neg, col_pos=c_pos)

    g = {k: v for k, v in zip(("salon", "couloir", "cuisine"), ground_tex)}
    gb = {k: v for k, v in zip(("salle", "couloir", "bain"), back_tex)}
    u = {k: v for k, v in zip(("chambre", "palier", "obs"), up_front)}
    ub = {k: v for k, v in zip(("debarras", "palier", "sacs"), up_back)}
    # rez-de-chaussée (jusqu'à la dalle de l'étage : pas de jour entre les deux niveaux dans la trémie)
    part("z", ZI0, BACK_Z, HALL_X0, F, F2, [(-0.8, 0.9)], g["salon"][0], g["couloir"][0], g["salon"][1], g["couloir"][1])
    part("z", BACK_Z, ZI1, HALL_X0, F, F2, [(4.3, 0.9)], gb["salle"][0], gb["couloir"][0], gb["salle"][1], gb["couloir"][1])
    part("z", ZI0, BACK_Z, HALL_X1, F, F2, [(-0.8, 0.9)], g["couloir"][0], g["cuisine"][0], g["couloir"][1], g["cuisine"][1])
    part("z", BACK_Z, ZI1, HALL_X1, F, F2, [(6.55, 0.8)], gb["couloir"][0], gb["bain"][0], gb["couloir"][1], gb["bain"][1])
    part("x", XI0, HALL_X0 - TP / 2, BACK_Z, F, F2, [(-30.4, 0.9)], g["salon"][0], gb["salle"][0], g["salon"][1], gb["salle"][1])
    part("x", HALL_X1 + TP / 2, XI1, BACK_Z, F, F2, [], g["cuisine"][0], gb["bain"][0], g["cuisine"][1], gb["bain"][1])
    # étage
    part("z", ZI0, BACK_Z, HALL_X0, F2, CEIL2, [(-0.6, 0.9)], u["chambre"][0], u["palier"][0], u["chambre"][1], u["palier"][1])
    part("z", BACK_Z, ZI1, HALL_X0, F2, CEIL2, [(4.6, 0.9)], ub["debarras"][0], ub["palier"][0], ub["debarras"][1], ub["palier"][1])
    part("z", ZI0, BACK_Z, HALL_X1, F2, CEIL2, [(0.0, 0.9)], u["palier"][0], u["obs"][0], u["palier"][1], u["obs"][1])
    part("z", BACK_Z, ZI1, HALL_X1, F2, CEIL2, [(6.6, 0.8)], ub["palier"][0], ub["sacs"][0], ub["palier"][1], ub["sacs"][1])
    part("x", XI0, HALL_X0 - TP / 2, BACK_Z, F2, CEIL2, [], u["chambre"][0], ub["debarras"][0], u["chambre"][1], ub["debarras"][1])
    part("x", HALL_X1 + TP / 2, XI1, BACK_Z, F2, CEIL2, [], u["obs"][0], ub["sacs"][0], u["obs"][1], ub["sacs"][1])
    # chambranles en bois autour des portes intérieures
    for (axis, fixed, c, w, y0) in (("z", HALL_X0, -0.8, 0.9, F), ("z", HALL_X0, 4.3, 0.9, F), ("z", HALL_X1, -0.8, 0.9, F),
                                    ("z", HALL_X1, 6.55, 0.8, F), ("x", BACK_Z, -30.4, 0.9, F), ("z", HALL_X0, -0.6, 0.9, F2),
                                    ("z", HALL_X0, 4.6, 0.9, F2), ("z", HALL_X1, 0.0, 0.9, F2), ("z", HALL_X1, 6.6, 0.8, F2)):
        _door_trim(b, axis, fixed, c, w, y0)

    # --- sols, plafonds, trémie ---------------------------------------------------------------------------------
    hole = (SX0, SZ0, SX1, SZ1)
    ground_floors = (((XI0, ZI0, HALL_X0, BACK_Z), "parquet", (0.72, 0.55, 0.4)),
                     ((HALL_X0, ZI0, HALL_X1, ZI1), "carrelage", (0.86, 0.56, 0.42)),       # tomettes
                     ((HALL_X1, ZI0, XI1, BACK_Z), "carrelage", (0.9, 0.86, 0.8)),
                     ((XI0, BACK_Z, HALL_X0, ZI1), "parquet", (0.62, 0.46, 0.32)),
                     ((HALL_X1, BACK_Z, XI1, ZI1), "carrelage", (0.95, 0.96, 0.96)))
    for (x0, z0, x1, z1), tex, col in ground_floors:
        b.quad(tex, (x0, F, z0), (x1, F, z0), (x1, F, z1), (x0, F, z1), (0, 1, 0), col, tile=0.6 if tex == "carrelage" else None)
    up_floors = (((XI0, ZI0, HALL_X0, BACK_Z), "moquette", (0.55, 0.32, 0.3)),
                 ((HALL_X0, ZI0, HALL_X1, ZI1), "parquet", (0.6, 0.45, 0.32)),
                 ((HALL_X1, ZI0, XI1, BACK_Z), "parquet", (0.55, 0.42, 0.3)),
                 ((XI0, BACK_Z, HALL_X0, ZI1), "parquet", (0.5, 0.4, 0.3)),
                 ((HALL_X1, BACK_Z, XI1, ZI1), "parquet", (0.48, 0.38, 0.28)))
    for rect, tex, col in up_floors:
        for (x0, z0, x1, z1) in rect_minus(rect, hole):
            b.quad(tex, (x0, F2, z0), (x1, F2, z0), (x1, F2, z1), (x0, F2, z1), (0, 1, 0), col)
    for (x0, z0, x1, z1) in rect_minus((XI0, ZI0, XI1, ZI1), hole):
        b.quad("plafond", (x0, CEIL, z0), (x1, CEIL, z0), (x1, CEIL, z1), (x0, CEIL, z1), (0, -1, 0), (0.92, 0.9, 0.86), tile=1.2)
    b.quad("plafond", (XI0, CEIL2, ZI0), (XI1, CEIL2, ZI0), (XI1, CEIL2, ZI1), (XI0, CEIL2, ZI1), (0, -1, 0), (0.9, 0.88, 0.84), tile=1.2)
    # chants de la trémie (épaisseur de la dalle)
    rv = (0.9, 0.88, 0.84)
    b.quad("platre", (SX0, CEIL, SZ0), (SX1, CEIL, SZ0), (SX1, F2, SZ0), (SX0, F2, SZ0), (0, 0, 1), rv)
    b.quad("platre", (SX1, CEIL, SZ1), (SX0, CEIL, SZ1), (SX0, F2, SZ1), (SX1, F2, SZ1), (0, 0, -1), rv)
    b.quad("platre", (SX0, CEIL, SZ1), (SX0, CEIL, SZ0), (SX0, F2, SZ0), (SX0, F2, SZ1), (1, 0, 0), rv)

    # --- escalier : marches, limon, main courante, garde-corps de la trémie --------------------------------------
    stairs_mesh(b, SX0, SX1, SZ0, SZ1, F, F2, STEPS, col=(0.62, 0.45, 0.3))
    for k in range(STEPS):                                     # nez de marche
        z = SZ0 + (SZ1 - SZ0) * k / STEPS
        y = F + (F2 - F) * (k + 1) / STEPS
        b.box("bois_meuble", SX0, y - 0.03, z - 0.025, SX1, y + 0.005, z + 0.01, (0.45, 0.3, 0.18))
    run = SZ1 - SZ0
    slope = (F2 - F) / run
    # limon côté couloir (planche inclinée qui cache le profil en escalier sous les marches)
    b.quad("bois_meuble", (SX0 - 0.03, F, SZ0), (SX0 - 0.03, F + 0.25, SZ0), (SX0 - 0.03, F2 + 0.05, SZ1),
           (SX0 - 0.03, F, SZ1), (-1, 0, 0), (0.48, 0.34, 0.22))
    # placard sous l'escalier
    pz0, pz1 = 4.3, 5.05
    b.quad("porte", (SX0 - 0.045, F, pz1), (SX0 - 0.045, F, pz0), (SX0 - 0.045, F + 1.75, pz0), (SX0 - 0.045, F + 1.75, pz1),
           (-1, 0, 0), (0.7, 0.55, 0.42), tile=(0.75, 1.75))
    b.sphere("metal", SX0 - 0.06, F + 0.95, pz0 + 0.08, 0.025, (0.75, 0.65, 0.35), lat=4, lon=8)
    # main courante et balustres (rez-de-chaussée -> étage), puis garde-corps autour de la trémie à l'étage
    hx = SX0 - 0.04
    rod(b, "bois_meuble", (hx, F + 0.92, SZ0 + 0.1), (hx, F2 + 0.92, SZ1), 0.03, col=(0.4, 0.26, 0.15), caps=True)
    b.cyl("bois_meuble", hx, F, SZ0 + 0.1, 0.05, 1.0, 8, (0.4, 0.26, 0.15))                       # poteau de départ
    k = 0
    while True:
        z = SZ0 + 0.35 + k * 0.28
        if z > SZ1 - 0.05:
            break
        yb = F + (z - SZ0) * slope
        rod(b, "bois_meuble", (hx, yb, z), (hx, yb + 0.92, z), 0.015, col=(0.45, 0.3, 0.18))
        k += 1
    # garde-corps de l'étage : le long de la trémie (x = SX0) et en tête (z = SZ0)
    rod(b, "bois_meuble", (hx, F2 + 0.92, SZ1), (hx, F2 + 0.92, SZ0), 0.03, col=(0.4, 0.26, 0.15), caps=True)
    rod(b, "bois_meuble", (hx, F2 + 0.92, SZ0), (SX1, F2 + 0.92, SZ0), 0.03, col=(0.4, 0.26, 0.15), caps=True)
    for i in range(int((SZ1 - SZ0) / 0.14)):
        z = SZ0 + 0.07 + i * 0.14
        rod(b, "bois_meuble", (hx, F2, z), (hx, F2 + 0.92, z), 0.012, col=(0.45, 0.3, 0.18))
    for i in range(int((SX1 - SX0) / 0.14)):
        x = SX0 + 0.07 + i * 0.14
        rod(b, "bois_meuble", (x, F2, SZ0), (x, F2 + 0.92, SZ0), 0.012, col=(0.45, 0.3, 0.18))
    b.cyl("bois_meuble", hx, F2, SZ0, 0.045, 1.0, 8, (0.4, 0.26, 0.15))
    # collisions : flanc de l'escalier (du sol au garde-corps), tête de trémie à l'étage, fond de l'escalier
    cols.append((SX0 - 0.06, F, SZ0 + 0.45, SX0, F2 + 1.0, SZ1))
    cols.append((SX0, F2 - 0.1, SZ0 - 0.04, SX1, F2 + 1.0, SZ0 + 0.02))
    cols.append((SX0 - 0.06, F2 - 0.1, SZ0 - 0.04, SX0, F2 + 1.0, SZ0 + 0.5))
    cols.append((SX0, F, SZ1 - 0.06, SX1, F2 - 0.45, SZ1))

    _ground_floor(nb, b, be, rng)
    _upper_floor(nb, b, be, rng)


def _door_trim(b, axis, fixed, c, w, y0, hgt=2.05):
    """Chambranle (montants + traverse) des deux côtés d'une baie de cloison."""
    col = (0.88, 0.85, 0.78)
    for s in (-1, 1):
        f0, f1 = sorted((fixed + s * TP / 2, fixed + s * (TP / 2 + 0.015)))
        for (a0, a1, v0, v1) in ((c - w / 2 - 0.07, c - w / 2, y0, y0 + hgt + 0.07), (c + w / 2, c + w / 2 + 0.07, y0, y0 + hgt + 0.07),
                                 (c - w / 2, c + w / 2, y0 + hgt, y0 + hgt + 0.07)):
            if axis == "x":
                b.box("bois_meuble", a0, v0, f0, a1, v1, f1, col)
            else:
                b.box("bois_meuble", f0, v0, a0, f1, v1, a1, col)


def _hanging_lamp(nb, b, be, x, z, ceil, drop, name, kind="static", intensity=1.3, rng_=6.0, shade=(0.85, 0.8, 0.6)):
    """Suspension : fil, abat-jour en tôle émaillée, ampoule ; lumière dans l'abat-jour."""
    y = ceil - drop
    rod(b, "metal", (x, ceil, z), (x, y + 0.16, z), 0.006, col=(0.15, 0.15, 0.15))
    b.cyl("metal", x, ceil - 0.03, z, 0.05, 0.03, 10, (0.85, 0.85, 0.8))
    lathe(b, "email", x, z, y, [(0.0, 0.22, 0.22), (0.05, 0.2, 0.2), (0.12, 0.12, 0.12), (0.16, 0.04, 0.04)], shade, seg=20)
    be.sphere("neon", x, y + 0.06, z, 0.045, (1.0, 0.82, 0.55), lat=4, lon=8)
    nb.lights.append(LightSource((x, y - 0.05, z), (1.0, 0.78, 0.55), intensity, rng_, kind=kind, name=name))


def _ground_floor(nb, b, be, rng):
    cols = b.colliders
    # --- entrée -------------------------------------------------------------------------------------------------
    b.box("moquette", DOOR_X - 0.45, F, ZI0 + 0.15, DOOR_X + 0.45, F + 0.012, ZI0 + 0.75, (0.4, 0.28, 0.2), skip=("-y",))
    floor_decal(b, "sel", DOOR_X, F + 0.012, ZI0 + 0.06, 1.0, 0.1, col=(1, 1, 1), off=0.002)          # ligne de sel
    coat_rack(b, HALL_X0 + 0.35, ZI0 + 0.4, F)
    # banc à chaussures contre la cloison est
    bx0, bx1 = HALL_X1 - TP / 2 - 0.36, HALL_X1 - TP / 2
    b.box("bois_meuble", bx0, F, ZI0 + 0.1, bx1, F + 0.42, ZI0 + 0.95, (0.42, 0.28, 0.16), collide=True)
    for k in range(3):
        sz = ZI0 + 0.2 + k * 0.26
        for s in (0, 1):
            b.obox("cuir", bx0 + 0.1 + s * 0.13, F + 0.42, sz + 0.05, 0.1, 0.07, 0.24, 0.0, (0.16, 0.11, 0.08))
    # console et téléphone fixe à cadran, miroir voilé au-dessus
    cx0 = HALL_X0 + TP / 2
    b.box("bois_meuble", cx0, F + 0.78, 0.35, cx0 + 0.32, F + 0.82, 1.05, (0.38, 0.24, 0.14))
    for zz in (0.4, 1.0):
        b.box("bois_meuble", cx0 + 0.24, F, zz - 0.02, cx0 + 0.28, F + 0.78, zz + 0.02, (0.35, 0.22, 0.12))
    cols.append((cx0, F, 0.35, cx0 + 0.32, F + 0.82, 1.05))
    _rotary_phone(b, cx0 + 0.16, 0.7, F + 0.82)
    painting(b, cx0, F + 1.6, 0.7, 0.5, 0.7, "+x", tex="miroir")
    pleated_panel(b, "drap", cx0 + 0.05, F + 1.15, 0.7, 0.62, 0.85, axis="z", depth=0.015, folds=4, col=(0.93, 0.92, 0.88))
    # crucifix au-dessus de la porte de la salle à manger
    _crucifix(b, "+x", HALL_X0 + TP / 2, F + 2.4, 4.3)
    # porte du jardin (fond du couloir), trois verrous tirés
    zb_ = ZI1 + 0.04
    b.quad("porte", (DOOR_X + 0.45, F, zb_ - 0.045), (DOOR_X - 0.45, F, zb_ - 0.045), (DOOR_X - 0.45, F + 2.0, zb_ - 0.045),
           (DOOR_X + 0.45, F + 2.0, zb_ - 0.045), (0, 0, -1), (0.62, 0.5, 0.4), tile=(0.9, 2.0))
    for yy in (0.5, 1.05, 1.6):
        b.box("metal", DOOR_X + 0.22, F + yy, zb_ - 0.07, DOOR_X + 0.4, F + yy + 0.04, zb_ - 0.045, (0.3, 0.3, 0.32))
    cols.append((DOOR_X - 0.5, F, ZI1 - 0.06, DOOR_X + 0.5, F + 2.1, Z1))             # porte du jardin fermée
    # suspension du couloir
    _hanging_lamp(nb, b, be, DOOR_X - 0.5, -0.4, CEIL, 0.55, "bianchi_couloir", intensity=1.0, rng_=5.0)

    # --- salon (ouest, avant) -----------------------------------------------------------------------------------
    sx0, sx1, sz0, sz1 = XI0, HALL_X0 - TP / 2, ZI0, BACK_Z - TP / 2
    scx = -29.25                                   # entre les deux fenêtres de la façade
    floor_decal(b, "moquette", scx, F, 0.35, 2.8, 2.2, col=(0.55, 0.2, 0.17), off=0.004)            # tapis
    sofa(b, scx, sz1 - 0.55, 180.0, F)                                                             # face à la télé
    table(b, scx, 0.45, F, 1.0, 0.55, h=0.45)                                                       # table basse
    b.box("papier", scx - 0.3, F + 0.45, 0.32, scx - 0.02, F + 0.47, 0.6, (0.75, 0.7, 0.62))          # magazines
    b.box("papier", scx - 0.28, F + 0.47, 0.34, scx - 0.04, F + 0.485, 0.58, (0.85, 0.3, 0.25))
    lathe(b, "email", scx + 0.25, 0.45, F + 0.45, [(0.0, 0.06, 0.06), (0.03, 0.075, 0.075), (0.035, 0.06, 0.06)],
          (0.55, 0.62, 0.7), seg=14)                                                                 # cendrier
    # meuble télé + téléviseur posé dessus
    tz0, tz1 = sz0 + 0.02, sz0 + 0.5
    b.box("bois_meuble", scx - 0.75, F, tz0, scx + 0.75, F + 0.55, tz1, (0.34, 0.22, 0.13), collide=True)
    for s in (-1, 1):
        b.box("bois_meuble", scx + s * 0.37 - 0.33, F + 0.08, tz1, scx + s * 0.37 + 0.33, F + 0.5, tz1 + 0.012, (0.4, 0.27, 0.16))
        b.sphere("metal", scx + s * 0.08, F + 0.3, tz1 + 0.025, 0.018, (0.7, 0.6, 0.35), lat=4, lon=8)
    if not b.model("Television_01", scx, (tz0 + tz1) / 2, F + 0.55, 0.0, (0.7, None, 0.45)):
        b.box("ecran_noir", scx - 0.3, F + 0.55, tz0 + 0.05, scx + 0.3, F + 1.0, tz1 - 0.05, (0.15, 0.15, 0.15))
    armchair(b, sx1 - 0.55, 0.9, 200.0, F)                                        # (fauteuil : vers +z à 0°)
    bookshelf(b, sx0, -0.9, sx0 + 0.45, 0.9, F, height=1.9, rng=rng, face="+x")                    # vaisselier
    b.model("potted_plant_02", sx0 + 0.35, sz0 + 0.35, F, 0.0, (0.5, None, 0.5))
    cols.append((sx0 + 0.1, F, sz0 + 0.1, sx0 + 0.6, F + 0.8, sz0 + 0.6))
    painting(b, sx0, F + 1.65, 1.6, 0.3, 0.24, "+x", tex="portrait")                              # photo des voisins
    _floor_lamp(nb, b, be, sx0 + 0.35, sz1 - 0.35, "bianchi_salon")

    # --- cuisine (est, avant) -----------------------------------------------------------------------------------
    kx0, kx1, kz0, kz1 = HALL_X1 + TP / 2, XI1, ZI0, BACK_Z - TP / 2
    counter(b, kx0 + 0.6, kz1 - 0.6, kx1 - 0.85, kz1, F)                                           # plans de travail
    top = F + 0.9
    rod(b, "metal", (kx0 + 1.6, top, kz1 - 0.08), (kx0 + 1.6, top + 0.28, kz1 - 0.08), 0.014, col=(0.8, 0.8, 0.82))
    rod(b, "metal", (kx0 + 1.6, top + 0.28, kz1 - 0.08), (kx0 + 1.6, top + 0.28, kz1 - 0.26), 0.012, col=(0.8, 0.8, 0.82))
    for k in range(4):                                                                             # pile d'assiettes
        b.cyl("email", kx0 + 0.95, top + k * 0.018, kz1 - 0.3, 0.12, 0.016, 14, (0.95, 0.94, 0.9))
    lathe(b, "metal", kx0 + 2.3, kz1 - 0.3, top, [(0.0, 0.1, 0.1), (0.14, 0.11, 0.11), (0.15, 0.1, 0.1)], (0.55, 0.55, 0.58), seg=14)
    # placards hauts
    b.box("bois_meuble", kx0 + 0.6, F + 1.5, kz1 - 0.35, kx1 - 0.85, F + 2.2, kz1, (0.6, 0.55, 0.5), collide=True)
    # frigo (porte vers -z) et mot au feutre rouge
    fx, fz = kx1 - 0.42, kz1 - 0.38
    fridge_body(b, fx, fz, F, 180.0)
    b.box("email", fx - 0.33, F + 0.1, fz - 0.365, fx + 0.33, F + 1.65, fz - 0.35, (0.97, 0.96, 0.9))
    b.box("metal", fx + 0.24, F + 0.9, fz - 0.4, fx + 0.27, F + 1.3, fz - 0.365, (0.75, 0.75, 0.78))
    b.box("papier", fx - 0.22, F + 1.2, fz - 0.372, fx + 0.05, F + 1.5, fz - 0.365, (0.98, 0.95, 0.65))
    b.sphere("metal", fx - 0.085, F + 1.49, fz - 0.375, 0.015, (0.85, 0.15, 0.12), lat=4, lon=6)
    # table sous la fenêtre (vue sur le 17), deux chaises, téléphone, tasse froide, sac QuickEats tiède
    tx, tz = kx1 - 1.2, 0.0
    table(b, tx, tz, F, 0.8, 1.1, h=0.75)
    chair(b, tx - 0.62, tz - 0.25, F, 270.0)
    chair(b, tx - 0.62, tz + 0.3, F, 255.0)
    t_top = F + 0.75
    b.box("ecran_noir", tx - 0.25, t_top, tz - 0.42, tx - 0.17, t_top + 0.01, tz - 0.27, (0.12, 0.12, 0.14))   # son portable
    lathe(b, "email", tx - 0.05, tz - 0.3, t_top, [(0.0, 0.035, 0.035), (0.08, 0.042, 0.042)], (0.92, 0.9, 0.85), seg=12)
    b.cap("eau_noire", [(tx - 0.05 + 0.038 * math.cos(a), t_top + 0.065, tz - 0.3 + 0.038 * math.sin(a))
                        for a in [2 * math.pi * i / 12 for i in range(12)]], (0, 1, 0), (0.35, 0.22, 0.12))
    delivery_bag(b, tx + 0.05, tz + 0.22, t_top, 15.0, torn=False)
    b.box("papier", tx - 0.25, t_top, tz + 0.05, tx - 0.12, t_top + 0.003, tz + 0.2, (0.97, 0.97, 0.95))       # ticket
    # gamelle du chat (pleine) au pied du frigo
    lathe(b, "email", kx1 - 0.6, kz1 - 0.95, F, [(0.0, 0.08, 0.08), (0.045, 0.1, 0.1)], (0.85, 0.2, 0.18), seg=16)
    b.cap("etoffe", [(kx1 - 0.6 + 0.085 * math.cos(a), F + 0.04, kz1 - 0.95 + 0.085 * math.sin(a))
                     for a in [2 * math.pi * i / 14 for i in range(14)]], (0, 1, 0), (0.45, 0.3, 0.2))
    # calendrier arrêté au 13 octobre
    painting(b, kx0, F + 1.55, 1.5, 0.32, 0.42, "+x", tex="papier")
    _hanging_lamp(nb, b, be, tx, tz, CEIL, 0.75, "bianchi_cuisine", kind="flicker", intensity=1.4, rng_=6.5)

    # --- salle à manger (ouest, fond) ---------------------------------------------------------------------------
    dx0, dx1, dz0, dz1 = XI0, HALL_X0 - TP / 2, BACK_Z + TP / 2, ZI1
    dcx, dcz = (dx0 + dx1) / 2 + 0.2, (dz0 + dz1) / 2 + 0.2
    table(b, dcx, dcz, F, 1.6, 0.9, h=0.76)
    d_top = F + 0.76
    # (chaise peinte : assise vers -z à 0°, rotation horaire vue de dessus)
    for (ox, oz, rot) in ((-0.45, -0.65, 180.0), (0.45, -0.65, 180.0), (-0.45, 0.65, 0.0), (0.45, 0.65, 0.0)):
        chair(b, dcx + ox, dcz + oz, F, rot)
    for ox in (-0.45, 0.45):                                                                       # deux couverts
        b.cyl("email", dcx + ox, d_top, dcz - 0.22, 0.12, 0.015, 16, (0.95, 0.94, 0.9))
        b.box("metal", dcx + ox - 0.17, d_top, dcz - 0.3, dcx + ox - 0.15, d_top + 0.004, dcz - 0.12, (0.8, 0.8, 0.82))
        b.box("metal", dcx + ox + 0.15, d_top, dcz - 0.3, dcx + ox + 0.17, d_top + 0.004, dcz - 0.12, (0.8, 0.8, 0.82))
    candle(b, dcx, dcz, d_top)
    bookshelf(b, dx0, dz0 + 0.4, dx0 + 0.45, dz1 - 0.6, F, height=2.0, rng=rng, face="+x")
    painting(b, dcx, F + 1.75, dz1, 1.0, 0.7, "-z", tex="paysage")
    if b.model("Chandelier_01", dcx, dcz, CEIL - 0.6, 0.0, (0.7, 0.6, 0.7), stretch=True):
        pass
    else:
        _hanging_lamp(nb, b, be, dcx, dcz, CEIL, 0.6, "bianchi_salle", intensity=0.0)

    # --- salle de bain (est, fond) ------------------------------------------------------------------------------
    wx0, wx1, wz0, wz1 = HALL_X1 + TP / 2, XI1, BACK_Z + TP / 2, ZI1
    bathtub(b, wx1 - 0.42, (wz0 + wz1) / 2 + 0.2, F, 90.0, water=True)
    toilet(b, wx0 + 1.2, wz1 - 0.32, F, 180.0)
    sink(b, wx0 + 2.1, wz1 - 0.26, F, 180.0)
    painting(b, wx0 + 2.1, F + 1.5, wz1, 0.5, 0.65, "-z", tex="miroir")
    pleated_panel(b, "drap", wx0 + 2.1, F + 1.1, wz1 - 0.05, 0.62, 0.8, axis="x", depth=0.015, folds=4, col=(0.93, 0.92, 0.88))
    b.box("tissu", wx0 + 0.05, F + 1.3, wz0 + 0.2, wx0 + 0.09, F + 1.32, wz0 + 0.7, (0.6, 0.6, 0.62))     # porte-serviette
    b.box("etoffe", wx0 + 0.09, F + 0.85, wz0 + 0.25, wx0 + 0.11, F + 1.31, wz0 + 0.65, (0.75, 0.82, 0.88))


def _upper_floor(nb, b, be, rng):
    cols = b.colliders
    # --- palier : tapis, cadres retournés face au mur, ampoule nue ---------------------------------------------
    floor_decal(b, "moquette", (HALL_X0 + SX0) / 2, F2, 2.4, 1.0, 5.6, col=(0.35, 0.18, 0.16), off=0.004)
    for k, zz in enumerate((0.6, 2.2, 3.6, 5.8)):
        x = HALL_X0 + TP / 2
        b.box("bois_meuble", x, F2 + 1.35 + (k % 2) * 0.12, zz - 0.2, x + 0.025, F2 + 1.75 + (k % 2) * 0.12, zz + 0.2, (0.5, 0.42, 0.32))
        b.box("bois_meuble", x + 0.025, F2 + 1.37 + (k % 2) * 0.12, zz - 0.18, x + 0.03, F2 + 1.73 + (k % 2) * 0.12, zz + 0.18, (0.62, 0.55, 0.45))
    b.cyl("metal", DOOR_X - 0.4, CEIL2 - 0.05, 2.4, 0.04, 0.05, 8, (0.8, 0.8, 0.8))
    rod(b, "metal", (DOOR_X - 0.4, CEIL2 - 0.05, 2.4), (DOOR_X - 0.4, CEIL2 - 0.4, 2.4), 0.006, col=(0.1, 0.1, 0.1))
    be.sphere("neon", DOOR_X - 0.4, CEIL2 - 0.45, 2.4, 0.05, (1.0, 0.85, 0.6), lat=4, lon=8)
    nb.lights.append(LightSource((DOOR_X - 0.4, CEIL2 - 0.55, 2.4), (1.0, 0.8, 0.6), 0.8, 5.0, kind="flicker", name="bianchi_palier"))

    # --- chambre (ouest, avant) ---------------------------------------------------------------------------------
    cx0, cx1, cz0, cz1 = XI0, HALL_X0 - TP / 2, ZI0, BACK_Z - TP / 2
    bed(b, cx0 + 1.05, 1.5, 90.0, F2, w=1.4, l=2.0)
    table(b, cx0 + 0.3, 0.5, F2, 0.42, 0.4, h=0.55)                                                 # table de chevet
    n_top = F2 + 0.55
    candle(b, cx0 + 0.3, 0.4, n_top)
    lathe(b, "vitre", cx0 + 0.36, 0.6, n_top, [(0.0, 0.03, 0.03), (0.11, 0.035, 0.035)], (0.85, 0.9, 0.95), seg=10)
    wardrobe(b, cx1 - 1.45, cz1 - 0.6, cx1 - 0.15, cz1, F2, face="-z")
    chair(b, cx1 - 0.5, cz0 + 0.6, F2, 200.0)
    _crucifix(b, "+x", cx0, F2 + 1.75, 1.5)
    # lampe de chevet allumée
    lathe(b, "email", cx0 + 0.25, 0.65, n_top, [(0.0, 0.06, 0.06), (0.02, 0.05, 0.05), (0.22, 0.02, 0.02)], (0.8, 0.7, 0.55), seg=12)
    lathe(b, "tissu", cx0 + 0.25, 0.65, n_top + 0.2, [(0.0, 0.13, 0.13), (0.16, 0.08, 0.08)], (0.95, 0.85, 0.65), seg=16)
    be.sphere("neon", cx0 + 0.25, n_top + 0.26, 0.65, 0.035, (1.0, 0.8, 0.5), lat=4, lon=8)
    nb.lights.append(LightSource((cx0 + 0.4, n_top + 0.3, 0.65), (1.0, 0.75, 0.5), 0.9, 4.5, kind="static", name="bianchi_chambre"))

    # --- débarras (ouest, fond) : meubles bâchés, cartons empilés, caisse --------------------------------------
    rx0, rx1, rz0, rz1 = XI0, HALL_X0 - TP / 2, BACK_Z + TP / 2, ZI1
    covered_furniture(b, rx0 + 0.75, rz1 - 0.6, F2, 1.2, 0.8, 0.9)
    covered_furniture(b, rx0 + 0.55, rz0 + 0.9, F2, 0.8, 1.2, 1.4)
    for k, (bx, bz, n) in enumerate(((rx1 - 0.5, rz1 - 0.45, 3), (rx1 - 1.1, rz1 - 0.45, 2), (rx1 - 0.5, rz1 - 1.05, 1))):
        for j in range(n):
            carton(b, bx, bz, F2 + j * 0.45, 0.5, rot=(k * 17 + j * 9) % 20 - 10)
    crate(b, rx0 + 2.1, rz0 + 0.5, F2, 0.5, 12.0)
    b.box("papier", rx1 - 0.66, F2 + 1.35, rz1 - 0.62, rx1 - 0.36, F2 + 1.352, rz1 - 0.42, (0.98, 0.96, 0.85))   # « NE PAS OUVRIR »

    # --- pièce d'observation (est, avant) : trépied et jumelles, fauteuil, mur de polaroïds ----------------------
    ox0, ox1, oz0, oz1 = HALL_X1 + TP / 2, XI1, ZI0, BACK_Z - TP / 2
    armchair(b, ox1 - 1.3, 0.0, 90.0, F2)                                         # tourné vers la fenêtre
    _tripod_binoculars(b, ox1 - 0.55, 0.0, F2)
    table(b, ox1 - 1.25, -1.0, F2, 0.5, 0.45, h=0.6)
    s_top = F2 + 0.6
    b.box("cuir", ox1 - 1.38, s_top, -1.12, ox1 - 1.18, s_top + 0.025, -0.86, (0.28, 0.16, 0.1))       # carnet « Le 17 »
    lathe(b, "metal", ox1 - 1.08, -0.95, s_top, [(0.0, 0.035, 0.035), (0.24, 0.035, 0.035), (0.26, 0.025, 0.025)], (0.3, 0.35, 0.45), seg=12)
    # lampe de bureau (seule lumière de la pièce, basse)
    rod(b, "metal", (ox1 - 1.42, s_top, -1.15), (ox1 - 1.42, s_top + 0.35, -1.05), 0.01, col=(0.2, 0.2, 0.2))
    lathe(b, "metal", ox1 - 1.42, -1.05, s_top + 0.28, [(0.0, 0.07, 0.07), (0.08, 0.03, 0.03)], (0.2, 0.35, 0.25), seg=12)
    be.sphere("neon", ox1 - 1.42, s_top + 0.3, -1.05, 0.025, (1.0, 0.85, 0.6), lat=4, lon=8)
    nb.lights.append(LightSource((ox1 - 1.42, s_top + 0.2, -1.0), (1.0, 0.8, 0.55), 0.7, 3.5, kind="static", name="bianchi_obs"))
    _polaroid_wall(b, ox0 + 0.3, ox1 - 0.3, BACK_Z, F2 + 0.9, F2 + 2.2, rng)

    # --- pièce des sacs (est, fond) : tous les sacs QuickEats livrés, jamais ouverts ---------------------------
    px0, px1, pz0, pz1 = HALL_X1 + TP / 2, XI1, BACK_Z + TP / 2, ZI1
    shelving_unit(b, px1 - 0.45, pz0 + 0.2, px1, pz1 - 0.2, F2, face="-x", levels=4, height=1.9)
    for l in range(4):
        yy = F2 + 0.15 + l * (1.9 - 0.2) / 4 + 0.03
        z = pz0 + 0.45
        while z < pz1 - 0.45:
            delivery_bag(b, px1 - 0.22, z, yy, 90.0 + rng.uniform(-6, 6), torn=False)
            z += 0.45
    # (la porte est côté ouest, z 6,2 à 7,0 : rien devant)
    for (bx, bz, n) in ((px0 + 1.4, pz1 - 0.42, 4), (px0 + 1.88, pz1 - 0.42, 3), (px0 + 2.36, pz1 - 0.42, 3),
                        (px0 + 1.88, pz1 - 0.9, 2), (px0 + 2.36, pz1 - 0.9, 1), (px0 + 0.45, pz0 + 0.45, 3),
                        (px0 + 0.93, pz0 + 0.45, 2), (px0 + 0.45, pz0 + 0.93, 2), (px0 + 1.45, pz0 + 0.5, 1)):
        for j in range(n):
            delivery_bag(b, bx, bz, F2 + j * 0.4, rng.uniform(-12, 12), torn=False)
        cols.append((bx - 0.24, F2, bz - 0.24, bx + 0.24, F2 + n * 0.4, bz + 0.24))
    for k in range(9):                                                                             # tickets tombés
        b.obox("papier", px0 + 0.7 + rng.uniform(-0.4, 1.4), F2 + 0.002, pz0 + 1.2 + rng.uniform(-0.5, 1.0),
               0.08, 0.002, 0.16, rng.uniform(0, 180), (0.97, 0.97, 0.95))


def _floor_lamp(nb, b, be, x, z, name):
    b.cyl("metal", x, F, z, 0.16, 0.025, 14, (0.25, 0.22, 0.18))
    rod(b, "metal", (x, F + 0.02, z), (x, F + 1.45, z), 0.012, col=(0.3, 0.26, 0.2))
    lathe(b, "tissu", x, z, F + 1.35, [(0.0, 0.22, 0.22), (0.3, 0.13, 0.13)], (0.95, 0.82, 0.6), seg=18)
    be.sphere("neon", x, F + 1.42, z, 0.04, (1.0, 0.8, 0.5), lat=4, lon=8)
    b.colliders.append((x - 0.2, F, z - 0.2, x + 0.2, F + 1.7, z + 0.2))
    nb.lights.append(LightSource((x, F + 1.3, z), (1.0, 0.75, 0.5), 1.2, 6.0, kind="static", name=name))


def _rotary_phone(b, x, z, y):
    """Téléphone fixe à cadran posé sur un plateau (y = dessus du plateau)."""
    lathe(b, "email", x, z, y, [(0.0, 0.1, 0.12), (0.07, 0.085, 0.1), (0.09, 0.05, 0.07)], (0.12, 0.1, 0.1), n=3.0, seg=16)
    b.cyl("email", x, y + 0.075, z + 0.02, 0.045, 0.012, 14, (0.85, 0.83, 0.78))
    rod(b, "email", (x, y + 0.115, z - 0.1), (x, y + 0.115, z + 0.1), 0.02, col=(0.12, 0.1, 0.1), caps=True)


def _crucifix(b, facing, x, y, z):
    col = (0.25, 0.15, 0.08)
    if facing == "+x":
        b.box("bois_meuble", x, y - 0.2, z - 0.02, x + 0.025, y + 0.15, z + 0.02, col)
        b.box("bois_meuble", x, y + 0.02, z - 0.1, x + 0.025, y + 0.06, z + 0.1, col)


def _tripod_binoculars(b, x, z, y0):
    """Trépied posé au sol, jumelles horizontales braquées vers +x (le 17)."""
    head = y0 + 1.32
    for a in (0.0, 2.1, 4.2):
        rod(b, "metal", (x + 0.32 * math.cos(a), y0, z + 0.32 * math.sin(a)), (x, head, z), 0.012, col=(0.15, 0.15, 0.16))
    b.cyl("metal", x, head, z, 0.035, 0.05, 10, (0.1, 0.1, 0.11))
    for s in (-1, 1):
        rod(b, "metal", (x - 0.12, head + 0.09, z + s * 0.045), (x + 0.1, head + 0.09, z + s * 0.045), 0.032,
            col=(0.12, 0.12, 0.13), caps=True)
        rod(b, "metal", (x + 0.1, head + 0.09, z + s * 0.045), (x + 0.14, head + 0.09, z + s * 0.045), 0.038,
            col=(0.08, 0.08, 0.09), caps=True)
    b.box("metal", x - 0.05, head + 0.05, z - 0.03, x + 0.05, head + 0.1, z + 0.03, (0.12, 0.12, 0.13))
    b.colliders.append((x - 0.3, y0, z - 0.3, x + 0.3, head + 0.2, z + 0.3))


def _polaroid_wall(b, x0, x1, zw, y0, y1, rng):
    """Mur de polaroïds (cloison côté -z) reliés par des fils rouges : le 17, le lampadaire, la silhouette."""
    z = zw - TP / 2 - 0.004
    pins = []
    nx, ny = 8, 4
    for i in range(nx):
        for j in range(ny):
            if rng.random() < 0.15:
                continue
            cx = x0 + (x1 - x0) * (i + 0.5) / nx + rng.uniform(-0.06, 0.06)
            cy = y0 + (y1 - y0) * (j + 0.5) / ny + rng.uniform(-0.05, 0.05)
            w, h = 0.11, 0.13
            b.quad("papier", (cx + w / 2, cy - h / 2, z), (cx - w / 2, cy - h / 2, z), (cx - w / 2, cy + h / 2, z),
                   (cx + w / 2, cy + h / 2, z), (0, 0, -1), (0.96, 0.95, 0.9), tile=(w, h))
            pw = 0.09
            tex = "paysage" if (i + j) % 3 else "portrait"
            b.quad(tex, (cx + pw / 2, cy - 0.03, z - 0.001), (cx - pw / 2, cy - 0.03, z - 0.001), (cx - pw / 2, cy + 0.06, z - 0.001),
                   (cx + pw / 2, cy + 0.06, z - 0.001), (0, 0, -1), (0.35, 0.38, 0.45), tile=(pw, 0.09))
            if (i * 7 + j) % 2 == 0:
                b.quad("silhouette", (cx + 0.025, cy - 0.03, z - 0.002), (cx - 0.025, cy - 0.03, z - 0.002),
                       (cx - 0.025, cy + 0.05, z - 0.002), (cx + 0.025, cy + 0.05, z - 0.002), (0, 0, -1), (0.1, 0.1, 0.12))
            b.sphere("metal", cx, cy + 0.055, z - 0.006, 0.006, (0.85, 0.1, 0.1), lat=3, lon=6)
            pins.append((cx, cy + 0.055))
    for k in range(len(pins) - 1):
        if rng.random() < 0.45:
            (ax, ay), (bx, by) = pins[k], pins[rng.randrange(len(pins))]
            if (ax, ay) != (bx, by):
                rod(b, "metal", (ax, ay, z - 0.007), (bx, by, z - 0.007), 0.0025, col=(0.7, 0.05, 0.05), seg=4)


# -----------------------------------------------------------------------------------------------------------------
def surfaces(Surface):
    """Sols des deux niveaux (l'étage privé de la trémie), escalier, seuil et marches de l'entrée."""
    out = [Surface(XI0, ZI0, XI1, ZI1, F, level=0),
           Surface(SX0, SZ0, SX1, SZ1, F, F2, SZ0, SZ1, level=0),
           Surface(DOOR_X - 0.55, Z0 - 0.02, DOOR_X + 0.55, ZI0 + 0.02, F, level=0),
           Surface(DOOR_X - 0.7, Z0 - 0.75, DOOR_X + 0.7, Z0 - 0.45, 0.2, level=0),
           Surface(DOOR_X - 0.7, Z0 - 0.45, DOOR_X + 0.7, Z0, 0.4, level=0)]
    for r in rect_minus((XI0, ZI0, XI1, ZI1), (SX0, SZ0, SX1, SZ1)):
        out.append(Surface(*r, F2, level=1))
    return out


def interactables(nb, ia, Interactable):
    g = nb.game

    def doc(title, pages, doc_id=None):
        def use(it):
            if doc_id:
                g.state.add_doc(doc_id)
            g.ui.docs.open(title, list(pages))
        return use

    def say(text, stress=0):
        def use(it):
            g.say(text, 4.5)
            if stress:
                g.player.add_stress(stress)
        return use

    def tv(it):
        from sound_engine import engine as sound
        sound.play_at("neige_tv", it.pos, 0.8, ref=4.0)
        g.say("Neige sur la chaîne locale. Le son est coupé... mais on entend quand même quelque chose.", 4.0)
        g.player.add_stress(6)

    kx1 = XI1
    tx, tz = kx1 - 1.2, 0.0
    sx0 = XI0
    ox1 = XI1
    items = [
        ("bianchi_sel", (DOOR_X, F + 0.3, ZI0 + 0.2), "Regarder le seuil",
         say("Une ligne de gros sel, intacte, en travers de la porte. Devant SA porte. Pas autour d'elle.")),
        ("bianchi_frigo", (kx1 - 0.5, F + 1.35, BACK_Z - TP / 2 - 0.78), "Lire le mot sur le frigo",
         doc("Mot sur le frigo", [FRIDGE_NOTE])),
        ("bianchi_sac", (tx + 0.05, F + 0.95, tz + 0.22), "Regarder le sac QuickEats",
         say("Un sac QuickEats jamais ouvert. Le ticket date de l'an dernier... et le sac est encore tiède.", 14)),
        ("bianchi_telephone", (tx - 0.21, F + 0.8, tz - 0.35), "Regarder son téléphone",
         doc("Téléphone de Mme Bianchi", PHONE, "telephone_bianchi")),
        ("bianchi_photo", (sx0 + 0.05, F + 1.65, 1.6), "Regarder la photo",
         say("« Fête des voisins, 1998. » Mme Bianchi et M. Garnier, bras dessus bras dessous. Ils souriaient.")),
        ("bianchi_tele", (-29.25, F + 0.9, ZI0 + 0.3), "Allumer la télévision", tv),
        ("bianchi_gamelle", (kx1 - 0.6, F + 0.15, BACK_Z - TP / 2 - 0.95), "Regarder la gamelle",
         say("La gamelle du chat est pleine. Pas de chat.")),
        ("bianchi_placard", (SX0 - 0.1, F + 1.0, 4.68), "Ouvrir le placard sous l'escalier",
         say("Un collier de chat rouge, encore bouclé, accroché à un clou. Vide. Dessous, une ligne de sel.", 8)),
        ("bianchi_jardin", (DOOR_X, F + 1.1, ZI1 - 0.1), "Ouvrir la porte du jardin",
         say("Trois verrous, tous tirés de l'intérieur. Elle n'est jamais sortie par là.")),
        ("bianchi_cadres", (HALL_X0 + 0.15, F2 + 1.5, 2.2), "Retourner un cadre",
         say("Tous les cadres de l'étage sont tournés face au mur. Derrière celui-ci : la façade du 17, en photo.", 6)),
        ("bianchi_lit", (XI0 + 1.05, F2 + 0.6, 1.5), "Regarder sous l'oreiller",
         say("Sous l'oreiller, une liste de numéros de commande QuickEats. Tous rayés, sauf le dernier : le vôtre.", 12)),
        ("bianchi_carnet", (ox1 - 1.28, s_top_obs(), -1.0), "Lire le carnet « Le 17 »",
         doc("Carnet de Mme Bianchi", NOTEBOOK, "carnet_bianchi")),
        ("bianchi_jumelles", (ox1 - 0.55, F2 + 1.4, 0.0), "Regarder dans les jumelles",
         say("Les jumelles sont réglées sur la porte du 17. Quelqu'un a regardé cette maison pendant des années.", 8)),
        ("bianchi_mur", (ox1 - 1.6, F2 + 1.5, BACK_Z - TP / 2 - 0.1), "Regarder les polaroïds",
         say("Des dizaines de polaroïds du 17, pris d'ici. Sous le lampadaire, toujours la même silhouette. "
             "Les dates s'arrêtent à ce soir.", 12)),
        ("bianchi_sacs", (HALL_X1 + 1.2, F2 + 0.9, ZI1 - 1.0), "Regarder les sacs",
         say("Des dizaines de sacs QuickEats, jamais ouverts. Un par nuit où il est venu. "
             "Sur chaque ticket : 17 rue des Lilas.", 14)),
    ]
    for iid, pos, prompt, fn in items:
        ia.add(Interactable(iid, pos, prompt, fn, 0 if pos[1] < 2.5 else 1, radius=0.35, reach=2.0))


def s_top_obs():
    """Dessus de la petite table de la pièce d'observation (carnet)."""
    return F2 + 0.6 + 0.05
