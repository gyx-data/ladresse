"""Chez Mme Bianchi, 11 rue des Lilas : la villa voisine, explorable pendant la balade dans le quartier.

La voisine sait. Elle a observé le 17 pendant des années depuis sa cuisine (jumelles braquées sur la maison de
Garnier), elle ne commande plus après 23 h, et elle a tracé une ligne de sel devant SA porte. Ses affaires donnent
des indices sur les règles du livreur ; la porte est entrouverte (elle « laisse toujours ouvert pour le chat »).

Repère : lot nord de la rue des Lilas, façade côté rue en z = Z0 (vers -z), porte au centre (x = DOOR_X).
Rez-de-chaussée explorable : entrée, salon (ouest), cuisine (est, fenêtre sur le 17), chambre au fond ;
l'escalier vers l'étage est condamné par des cartons.
"""
import math

from lighting_system import LightSource

X0, X1, Z0, Z1, H = -32.0, -20.0, -2.4, 7.6, 7.0
DOOR_X = (X0 + X1) / 2
F = 0.6                     # sol intérieur (dessus du soubassement en pierre)
CEIL = F + 2.75
T = 0.18                    # épaisseur des murs intérieurs
WALL = (0.82, 0.76, 0.66)              # vieux papier peint jauni
HALL_X0, HALL_X1 = DOOR_X - 1.4, DOOR_X + 1.4
BACK_Z = 3.0                # cloison entre l'avant (entrée, salon, cuisine) et la chambre du fond

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


def _windows_inside(b, rng):
    """Fenêtres vues de l'intérieur sur le mur côté rue (mêmes emplacements que la façade)."""
    z = Z0 + T + 0.002
    xx = X0 + 1.0
    while xx < X1 - 1.4:
        if abs(xx + 0.45 - DOOR_X) < 1.0:
            xx += 2.6
            continue
        b.quad("miroir", (xx + 0.9, 1.0, z), (xx, 1.0, z), (xx, 2.4, z), (xx + 0.9, 2.4, z), (0, 0, 1), (0.35, 0.38, 0.42))
        b.box("bois_meuble", xx - 0.06, 0.98, Z0 + T, xx + 0.96, 1.04, Z0 + T + 0.16, (0.78, 0.74, 0.68))     # appui
        b.box("bois_meuble", xx + 0.43, 1.0, Z0 + T, xx + 0.47, 2.4, Z0 + T + 0.03, (0.75, 0.72, 0.66))       # meneau
        # rideaux de dentelle
        b.box("rideau", xx - 0.2, 0.95, Z0 + T + 0.05, xx + 0.15, 2.6, Z0 + T + 0.07, (0.9, 0.88, 0.8))
        b.box("rideau", xx + 0.75, 0.95, Z0 + T + 0.05, xx + 1.1, 2.6, Z0 + T + 0.07, (0.9, 0.88, 0.8))
        xx += 2.6


def build(nb, b, be, rng):
    """Intérieur de la villa (la façade est construite par nb._villa(..., explorable=True))."""
    cols = b.colliders
    xi0, xi1, zi0, zi1 = X0 + T, X1 - T, Z0 + T, Z1 - T
    # murs périphériques intérieurs (le mur côté rue est percé à la porte)
    e = 0.012
    b.box("papier_peint", X0 + e, F, Z0 + e, xi0, CEIL, Z1 - e, WALL, collide=True)
    b.box("papier_peint", xi1, F, Z0 + e, X1 - e, CEIL, Z1 - e, WALL, collide=True)
    b.box("papier_peint", X0 + e, F, zi1, X1 - e, CEIL, Z1 - e, WALL, collide=True)
    b.box("papier_peint", X0 + e, F, Z0 + e, DOOR_X - 0.55, CEIL, zi0, WALL, collide=True)
    b.box("papier_peint", DOOR_X + 0.55, F, Z0 + e, X1 - e, CEIL, zi0, WALL, collide=True)
    b.box("papier_peint", DOOR_X - 0.55, F + 2.25, Z0 + e, DOOR_X + 0.55, CEIL, zi0, WALL)
    # sol, plinthes, plafond
    b.box("carrelage", xi0, F - 0.02, zi0, xi1, F + 0.004, zi1, (0.86, 0.8, 0.72), tile=0.5)
    b.quad("plafond", (xi0, CEIL, zi0), (xi1, CEIL, zi0), (xi1, CEIL, zi1), (xi0, CEIL, zi1), (0, -1, 0), (0.92, 0.9, 0.86), tile=1.2)
    # marches devant la porte
    for k, y in enumerate((0.2, 0.4)):
        b.box("beton", DOOR_X - 0.7, 0.0, Z0 - 0.75 + k * 0.3, DOOR_X + 0.7, y, Z0, (0.7, 0.68, 0.65))
    # cloisons : couloir d'entrée (portes vers salon et cuisine), cloison du fond (porte vers la chambre)
    for xw in (HALL_X0, HALL_X1):
        b.box("papier_peint", xw - T / 2, F, zi0, xw + T / 2, CEIL, 0.6, WALL, collide=True)
        b.box("papier_peint", xw - T / 2, F, 1.6, xw + T / 2, CEIL, BACK_Z, WALL, collide=True)
        b.box("papier_peint", xw - T / 2, F + 2.15, 0.6, xw + T / 2, CEIL, 1.6, WALL)
    b.box("papier_peint", xi0, F, BACK_Z, DOOR_X - 0.5, CEIL, BACK_Z + T, WALL, collide=True)
    b.box("papier_peint", DOOR_X + 0.5, F, BACK_Z, xi1, CEIL, BACK_Z + T, WALL, collide=True)
    b.box("papier_peint", DOOR_X - 0.5, F + 2.15, BACK_Z, DOOR_X + 0.5, CEIL, BACK_Z + T, WALL)
    # plinthes en bois le long des murs
    for (a0, a1, z) in ((xi0, HALL_X0 - T / 2, zi0), (HALL_X1 + T / 2, xi1, zi0), (xi0, xi1, zi1)):
        b.box("bois_meuble", a0, F, z - 0.01 if z > 0 else z, a1, F + 0.1, z + 0.02 if z < 0 else z, (0.45, 0.3, 0.18))
    _windows_inside(b, rng)
    # fenêtre de la cuisine sur le 17 (mur est) : vitre, appui, et vitre extérieure
    wz0, wz1 = -0.6, 0.6
    b.quad("miroir", (xi1 - 0.002, F + 0.9, wz0), (xi1 - 0.002, F + 0.9, wz1), (xi1 - 0.002, F + 2.1, wz1),
           (xi1 - 0.002, F + 2.1, wz0), (-1, 0, 0), (0.3, 0.33, 0.38))
    b.box("bois_meuble", xi1 - 0.2, F + 0.86, wz0 - 0.08, xi1, F + 0.92, wz1 + 0.08, (0.78, 0.74, 0.68))
    b.quad("miroir", (X1 + 0.004, F + 0.9, wz1), (X1 + 0.004, F + 0.9, wz0), (X1 + 0.004, F + 2.1, wz0),
           (X1 + 0.004, F + 2.1, wz1), (1, 0, 0), (0.4, 0.44, 0.5))
    b.box("crepi", X1, F + 2.1, wz0 - 0.1, X1 + 0.06, F + 2.2, wz1 + 0.1, (0.97, 0.96, 0.93))

    # --- entrée : porte-manteau, miroir voilé, ligne de sel, crucifix ---------------------------------------
    b.box("bois_meuble", DOOR_X + 0.9, F, -1.4, DOOR_X + 1.2, F + 1.8, -1.3, (0.4, 0.26, 0.15))
    for k in range(3):
        b.sphere("etoffe", DOOR_X + 1.0, F + 1.45 - k * 0.05, -1.2 + k * 0.25, 0.16, ((0.35, 0.2, 0.2), (0.2, 0.22, 0.3), (0.5, 0.45, 0.4))[k],
                 lat=4, lon=6, sy=1.8)
    b.box("drap", DOOR_X - 1.32, F + 1.1, -0.4, DOOR_X - 1.29, F + 1.9, 0.3, (0.9, 0.88, 0.84))                  # miroir voilé
    b.box("sel", DOOR_X - 0.5, F + 0.001, zi0 + 0.05, DOOR_X + 0.5, F + 0.012, zi0 + 0.11, (0.97, 0.97, 0.95))   # ligne de sel
    b.box("bois_meuble", DOOR_X - 0.02, F + 2.0, 2.97, DOOR_X + 0.02, F + 2.3, 2.99, (0.25, 0.15, 0.08))
    b.box("bois_meuble", DOOR_X - 0.09, F + 2.17, 2.97, DOOR_X + 0.09, F + 2.21, 2.99, (0.25, 0.15, 0.08))
    for k in range(4):                                                                                       # chaussures
        b.box("cuir", DOOR_X + 0.75 + (k % 2) * 0.16, F, -1.9 + (k // 2) * 0.32, DOOR_X + 0.87 + (k % 2) * 0.16, F + 0.08,
              -1.65 + (k // 2) * 0.32, (0.15, 0.1, 0.08))

    # --- salon (ouest) ---------------------------------------------------------------------------------------
    sx = (xi0 + HALL_X0) / 2
    b.box("moquette", xi0 + 0.3, F + 0.001, -1.6, HALL_X0 - 0.3, F + 0.01, 2.2, (0.45, 0.18, 0.15), tile=1.0)   # tapis
    if not b.model("sofa_03", sx, 2.45, F, 180.0, (2.0, None, 0.9)):
        b.box("etoffe", sx - 1.0, F, 2.0, sx + 1.0, F + 0.8, 2.85, (0.4, 0.3, 0.25), collide=True)
    cols.append((sx - 1.0, F, 2.0, sx + 1.0, F + 0.8, 2.85))
    b.box("bois_meuble", sx - 0.7, F, -2.0, sx + 0.7, F + 0.6, -1.6, (0.35, 0.22, 0.12), collide=True)          # meuble télé
    if not b.model("Television_01", sx, -1.8, F + 0.6, 0.0, (0.75, None, 0.4)):
        b.box("ecran_noir", sx - 0.35, F + 0.6, -1.95, sx + 0.35, F + 1.1, -1.7, (0.1, 0.1, 0.1))
    if not b.model("GreenChair_01", HALL_X0 - 0.9, 0.2, F, 270.0, (0.8, None, 0.8)):
        b.box("etoffe", HALL_X0 - 1.3, F, -0.2, HALL_X0 - 0.5, F + 0.9, 0.6, (0.3, 0.4, 0.3))
    cols.append((HALL_X0 - 1.3, F, -0.2, HALL_X0 - 0.5, F + 0.9, 0.6))
    b.model("potted_plant_02", xi0 + 0.35, -1.75, F, 0.0, (0.5, None, 0.5))
    b.box("bois_meuble", xi0 + 0.05, F, 0.2, xi0 + 0.45, F + 1.6, 1.6, (0.3, 0.2, 0.12), collide=True)          # vaisselier
    for k in range(6):
        b.cyl("email", xi0 + 0.3, F + 0.75 + (k // 3) * 0.4, 0.45 + (k % 3) * 0.4, 0.09, 0.015, 12, (0.95, 0.94, 0.9))
    # photo encadrée (Mme Bianchi et M. Garnier)
    b.box("bois_meuble", xi0 + 0.01, F + 1.65, 0.75, xi0 + 0.03, F + 1.95, 1.05, (0.5, 0.36, 0.16))
    b.quad("portrait", (xi0 + 0.035, F + 1.68, 1.02), (xi0 + 0.035, F + 1.68, 0.78), (xi0 + 0.035, F + 1.92, 0.78),
           (xi0 + 0.035, F + 1.92, 1.02), (1, 0, 0), (0.9, 0.85, 0.75))

    # --- cuisine (est) : table, frigo, sac QuickEats, jumelles à la fenêtre --------------------------------------
    kx = (HALL_X1 + xi1) / 2
    if not b.model("WoodenTable_01", kx - 0.2, 1.3, F, 0.0, (1.2, None, 0.8)):
        b.box("bois_meuble", kx - 0.8, F, 0.9, kx + 0.4, F + 0.75, 1.7, (0.45, 0.3, 0.18))
    cols.append((kx - 0.8, F, 0.9, kx + 0.4, F + 0.75, 1.7))
    for cz, rot in ((0.6, 0.0), (2.0, 180.0)):
        b.model("painted_wooden_chair_01", kx - 0.2, cz, F, rot, (0.45, None, 0.45))
    b.cyl("email", kx - 0.4, F + 0.76, 1.2, 0.045, 0.08, 12, (0.95, 0.94, 0.9))                                # tasse froide
    b.box("ecran_noir", kx - 0.58, F + 0.755, 0.88, kx - 0.42, F + 0.765, 1.02, (0.1, 0.1, 0.12))              # son téléphone
    b.box("papier", kx - 0.05, F + 0.76, 1.15, kx + 0.25, F + 1.06, 1.45, (0.95, 0.5, 0.15))                    # sac QuickEats
    b.box("metal", kx + 0.05, F + 0.76, 1.42, kx + 0.15, F + 0.79, 1.46, (0.95, 0.95, 0.95))                   # ticket
    b.box("metal", xi1 - 0.75, F, 2.3, xi1 - 0.05, F + 1.85, 2.95, (0.9, 0.9, 0.88), collide=True)            # frigo
    b.box("metal", xi1 - 0.75, F + 1.1, 2.28, xi1 - 0.72, F + 1.6, 2.3, (0.7, 0.7, 0.72))
    b.box("papier", xi1 - 0.6, F + 1.3, 2.29, xi1 - 0.35, F + 1.55, 2.3, (0.98, 0.95, 0.6))                    # mot sur le frigo
    b.box("bois_meuble", xi1 - 0.65, F, -2.0, xi1 - 0.05, F + 0.9, 0.0, (0.75, 0.68, 0.55), collide=True)        # plan de travail
    b.box("marbre", xi1 - 0.68, F + 0.9, -2.03, xi1 - 0.02, F + 0.94, 0.03, (0.85, 0.83, 0.8))
    # jumelles sur l'appui de la fenêtre, braquées sur le 17 (vers +x) + carnet
    b.cyl("metal", xi1 - 0.12, F + 0.92, -0.08, 0.03, 0.05, 10, (0.12, 0.12, 0.13))
    b.cyl("metal", xi1 - 0.12, F + 0.92, 0.04, 0.03, 0.05, 10, (0.12, 0.12, 0.13))
    b.box("papier", xi1 - 0.18, F + 0.92, 0.18, xi1 - 0.04, F + 0.94, 0.38, (0.25, 0.15, 0.1))
    b.cyl("email", xi1 - 0.6, F + 0.0, 2.0, 0.08, 0.04, 12, (0.9, 0.25, 0.2))                                   # gamelle du chat
    # --- chambre (fond) : lit, armoire, escalier condamné par des cartons ------------------------------------------
    if not b.model("GothicBed_01", X0 + 2.3, 5.2, F, 90.0, (2.0, None, 1.6)):
        b.box("drap", X0 + 1.2, F, 4.3, X0 + 3.3, F + 0.6, 6.1, (0.85, 0.82, 0.75))
    cols.append((X0 + 1.2, F, 4.3, X0 + 3.4, F + 0.7, 6.1))
    if not b.model("vintage_cabinet_01", X1 - 1.0, zi1 - 0.35, F, 180.0, (1.2, None, 0.55)):
        b.box("bois_meuble", X1 - 1.6, F, zi1 - 0.6, X1 - 0.4, F + 1.9, zi1, (0.35, 0.22, 0.12))
    cols.append((X1 - 1.6, F, zi1 - 0.6, X1 - 0.4, F + 1.9, zi1))
    # escalier (vers l'étage) barré : marches + cartons empilés
    for k in range(6):
        b.box("bois_meuble", DOOR_X + 0.8, F + k * 0.18, 4.0 + k * 0.28, DOOR_X + 1.8, F + (k + 1) * 0.18, 4.28 + k * 0.28,
              (0.5, 0.34, 0.2))
    for k in range(4):
        if not b.model("cardboard_box_01", DOOR_X + 1.3, 4.3 + (k % 2) * 0.1, F + k * 0.45, 20.0 * k, (0.8, 0.45, 0.6)):
            b.box("papier", DOOR_X + 0.9, F + k * 0.45, 4.0, DOOR_X + 1.7, F + (k + 1) * 0.45, 4.6, (0.6, 0.45, 0.3))
    cols.append((DOOR_X + 0.8, F, 3.9, DOOR_X + 1.8, CEIL, 6.0))
    b.model("wall_clock", X0 + 0.3, 5.2, F + 1.9, 90.0, (0.05, 0.35, 0.35))
    # lampes laissées allumées (salon, cuisine)
    for (lx, lz, name) in ((sx, 0.5, "bianchi_salon"), (kx, 0.8, "bianchi_cuisine")):
        b.cyl("metal", lx, CEIL - 0.6, lz, 0.01, 0.6, 6, (0.2, 0.2, 0.2))
        be.sphere("neon", lx, CEIL - 0.65, lz, 0.09, (1.0, 0.8, 0.55))
        nb.lights.append(LightSource((lx, CEIL - 0.7, lz), (1.0, 0.78, 0.55), 1.4, 6.5, kind="flicker" if lx == kx else "static",
                                     name=name))


def surfaces(Surface):
    """Sol intérieur (sur le soubassement) et marches."""
    return [Surface(X0 + T, Z0 + T, X1 - T, Z1 - T, F, level=0),
            Surface(DOOR_X - 0.55, Z0 - 0.02, DOOR_X + 0.55, Z0 + T + 0.02, F, level=0),
            Surface(DOOR_X - 0.7, Z0 - 0.75, DOOR_X + 0.7, Z0 - 0.45, 0.2, level=0),
            Surface(DOOR_X - 0.7, Z0 - 0.45, DOOR_X + 0.7, Z0, 0.4, level=0)]


def interactables(nb, ia, Interactable):
    g = nb.game
    xi1 = X1 - T

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

    kx = (HALL_X1 + xi1) / 2
    items = [
        ("bianchi_sel", (DOOR_X, F + 0.3, Z0 + T + 0.2), "Regarder le seuil",
         say("Une ligne de gros sel, intacte, en travers de la porte. Devant SA porte. Pas autour d'elle.")),
        ("bianchi_carnet", (xi1 - 0.12, F + 1.0, 0.28), "Lire le carnet « Le 17 »",
         doc("Carnet de Mme Bianchi", NOTEBOOK, "carnet_bianchi")),
        ("bianchi_jumelles", (xi1 - 0.12, F + 1.0, -0.02), "Regarder dans les jumelles",
         say("Les jumelles sont réglées sur la porte du 17. Quelqu'un a regardé cette maison pendant des années.", 8)),
        ("bianchi_frigo", (xi1 - 0.45, F + 1.4, 2.25), "Lire le mot sur le frigo", doc("Mot sur le frigo", [FRIDGE_NOTE])),
        ("bianchi_sac", (kx + 0.1, F + 0.95, 1.3), "Regarder le sac QuickEats",
         say("Un sac QuickEats jamais ouvert. Le ticket date de l'an dernier... et le sac est encore tiède.", 14)),
        ("bianchi_telephone", (kx - 0.5, F + 0.8, 0.95), "Regarder son téléphone",
         doc("Téléphone de Mme Bianchi", PHONE, "telephone_bianchi")),
        ("bianchi_photo", (X0 + T + 0.05, F + 1.8, 0.9), "Regarder la photo",
         say("« Fête des voisins, 1998. » Mme Bianchi et M. Garnier, bras dessus bras dessous. Ils souriaient.")),
        ("bianchi_tele", ((X0 + T + HALL_X0) / 2, F + 0.9, -1.75), "Allumer la télévision", tv),
        ("bianchi_escalier", (DOOR_X + 1.3, F + 1.0, 3.6), "Monter",
         say("L'escalier est bloqué par des cartons. Sur l'un d'eux : « NE PAS MONTER — 13/10 ».")),
        ("bianchi_gamelle", (xi1 - 0.6, F + 0.2, 2.0), "Regarder la gamelle",
         say("La gamelle du chat est pleine. Pas de chat.")),
    ]
    # le téléphone de la voisine est posé sur la table, à côté de la tasse
    for iid, pos, prompt, fn in items:
        ia.add(Interactable(iid, pos, prompt, fn, 0, radius=0.35, reach=2.0))
