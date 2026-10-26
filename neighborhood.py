"""Le quartier du Mont-Boron autour du 17 rue des Lilas (Nice), explorable avant d'entrer dans la maison.

Contenu :
  * rue des Lilas (deux voies, trottoirs, passages piétons) et boulevard du Mont-Boron en croisement,
    feux tricolores fonctionnels, lampadaires, abribus « Lignes d'Azur », barrières de fin de zone ;
  * villas niçoises (enduits ocre / rose, tuiles, persiennes, fenêtres éclairées), jardins, palmiers ;
  * voitures des voisins garées, circulation (2 voitures qui roulent, s'arrêtent au feu et devant le joueur) ;
  * restaurant « Chez Nino » (terrasse, comptoir, spécialités niçoises) ;
  * supérette « Carrefour City » : rayons, produits à prendre (E), portique antivol, vigile,
    caisses automatiques avec carte fidélité (voir shop.py / fidelite.py) ;
  * voiture de police (gyrophares) et deux agents, piétons qui marchent, discutent, attendent le bus.

Toute la géométrie statique est fusionnée par texture (peu d'appels de rendu). Le quartier est désactivé
dès que la porte d'entrée de la maison est verrouillée.
"""
import math
import random

from ursina import Entity, Vec3, camera, color, destroy

import game_data as gd
from character_model import CharacterModel
from house_generator import CAVE_STAIRWELL, Surface, rect_minus
from interaction_system import Interactable
from lighting_system import LightSource
import products
import fresh_aisle
import bianchi_house
from room_builder import MeshBuilder
from shop import (CATALOG, SHOP_NAME, RESTO_NAME, Basket, SelfCheckout, RestaurantCounter, eur, primeur_article)
from fidelite import Loyalty
from sound_engine import engine as sound
from ui_widgets import label, rect, rgb

# --- plan du quartier (mètres) ------------------------------------------------
X_MIN, X_MAX, Z_MIN, Z_MAX = -70.0, 110.0, -60.0, 30.0
ROAD_Z0, ROAD_Z1 = -16.0, -7.4            # rue des Lilas
LANE_E, LANE_W = -13.8, -9.6              # voies (vers l'est / vers l'ouest)
BLVD_X0, BLVD_X1 = 46.0, 54.0             # boulevard du Mont-Boron
SHOP = (10.0, -36.0, 32.0, -21.0)         # x0, z0, x1, z1 (façade côté rue en z1)
SHOP_DOOR_X = 21.0
RESTO = (-14.0, -30.0, 0.0, -23.0)
RESTO_DOOR_X = -7.0
SHOP_H = 3.6

DAY = "13/10"                     # vendredi 13 octobre (date de la partie, cf. intro et téléphone)

# hauteur de voix (Hz) de chaque habitant : < 160 = voix d'homme
NPC_VOICES = {"Mme Bianchi": 215, "Karim": 118, "Jean-Mi": 105, "Lucie": 225, "Théo": 122, "Nino": 98, "Sandrine": 210,
              "Moussa": 100, "Brigadier Rossi": 110, "Gardien Martin": 128, "Inès": 230}

# apparence de chaque habitant (corps, âge, tenue, coiffure...) — clé = nom du PNJ
NPC_LOOKS = {
    "Mme Bianchi": dict(body="f", age="âgé", outfit="manteau", hair_style="chignon", glasses=True,
                        jacket=(0.42, 0.12, 0.16), pants=(0.2, 0.18, 0.2), shoes=(0.08, 0.06, 0.05)),
    "Karim": dict(body="m", outfit="survetement", hair_style="rase", beard="barbe",
                  jacket=(0.1, 0.12, 0.2), pants=(0.1, 0.12, 0.2), shoes=(0.9, 0.9, 0.9)),
    "Jean-Mi": dict(body="m", age="adulte", outfit="gilet", hair_style="court", hair=(0.55, 0.53, 0.5), glasses=True,
                    belly=True, beard="moustache", jacket=(0.36, 0.3, 0.22), pants=(0.25, 0.25, 0.28)),
    "Lucie": dict(body="f", outfit="robe", hair_style="long", hair=(0.35, 0.18, 0.1),
                  jacket=(0.62, 0.08, 0.14), shoes=(0.08, 0.05, 0.06)),
    "Théo": dict(body="m", outfit="chemise", hair_style="court", beard="barbe",
                 jacket=(0.2, 0.38, 0.32), pants=(0.16, 0.2, 0.32)),
    "Nino": dict(body="m", age="âgé", outfit="cuisinier", hair_style="court", beard="moustache", belly=True,
                 jacket=(0.95, 0.95, 0.93), pants=(0.15, 0.15, 0.17)),
    "Sandrine": dict(body="f", outfit="polo", hair_style="queue", hair=(0.5, 0.33, 0.18),
                     jacket=(0.1, 0.27, 0.68), pants=(0.12, 0.13, 0.16)),
    "Moussa": dict(body="m", outfit="securite", hair_style="rase", skin=(0.32, 0.2, 0.14), hair=(0.05, 0.04, 0.04),
                   jacket=(0.08, 0.08, 0.09), pants=(0.08, 0.08, 0.09)),
    "Brigadier Rossi": dict(body="m", outfit="uniforme", hair_style="court", beard="moustache",
                            jacket=(0.12, 0.15, 0.32), pants=(0.12, 0.14, 0.28)),
    "Gardien Martin": dict(body="m", outfit="uniforme", hair_style="rase",
                           jacket=(0.12, 0.15, 0.32), pants=(0.12, 0.14, 0.28)),
    "Inès": dict(body="f", outfit="doudoune", hair_style="long", hair=(0.08, 0.06, 0.05),
                 jacket=(0.36, 0.22, 0.5), pants=(0.14, 0.16, 0.26), shoes=(0.92, 0.92, 0.92)),
}


def _txt_tex(text, px=96, fg=(255, 255, 255), bg=None, pad=18, bold=True, kind="sans"):
    """Texture d'enseigne (texte rendu avec Pillow)."""
    from PIL import Image, ImageDraw
    import typography as T
    from texture_generator import textures
    f = T.pil_font(kind, px, bold)
    w = int(T.text_width(text, kind, px, bold)) + pad * 2
    h = int(px * 1.35) + pad
    img = Image.new("RGBA", (w, h), bg if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((w / 2, h / 2), text, font=f, fill=fg + (255,), anchor="mm")
    return textures.from_pil(img), w / h


def sign(parent, text, pos, height, rot_y=0.0, fg=(255, 255, 255), bg=None, px=96, kind="sans"):
    tex, aspect = _txt_tex(text, px, fg, bg, kind=kind)
    e = Entity(parent=parent, model="quad", texture=tex, position=pos, rotation_y=rot_y,
               scale=(height * aspect, height), double_sided=True)
    return e


def car_mesh(b, cx, cz, col, along_x=True, police=False, y=0.0, kind=None):
    """Voiture modelée (voir car_builder.py) : citadine, berline ou utilitaire."""
    import car_builder
    if kind is None:
        kind = "berline" if police else car_builder.KINDS[int(abs(col[0] * 97 + col[1] * 53 + col[2] * 29)) % 3]
    return car_builder.build(b, cx, cz, col, along_x, kind, police, y)


def car_lights(be, cx, cz, along_x=True, front_sign=1, y=0.0, kind="berline"):
    """Phares avant (blancs) et feux arrière (rouges) dans un builder émissif."""
    import car_builder
    car_builder.lights(be, cx, cz, along_x, front_sign, y, kind)


# =============================================================================
# PNJ
# =============================================================================
class NPC:
    def __init__(self, hood, name, pos, lines, jacket, pants=(0.3, 0.32, 0.4), path=None, speed=1.3, pose="idle",
                 yaw=0.0, f0=140, seed=0, hat=None, talk_cb=None, look=None):
        self.hood = hood
        self.name = name
        self.lines = list(lines)
        self.line_i = 0
        self.path = path or []
        self.idx = 0
        self.speed = speed
        self.pose = pose
        self.f0 = f0
        self.talk_cb = talk_cb
        self.root = Entity(parent=hood.npc_root, position=pos, rotation_y=yaw)
        look = dict(look or {})
        jacket = look.pop("jacket", jacket)
        pants = look.pop("pants", pants)
        self.model = CharacterModel(parent=self.root, jacket=jacket, pants=pants, flashlight=False, seed=seed, emit=0.1,
                                    logo=False, **look)
        if hat == "police":
            b = MeshBuilder("kepi")
            b.cyl("etoffe", 0, 0.2, 0, 0.12, 0.08, 10, (0.1, 0.12, 0.25))
            b.obox("etoffe", 0, 0.2, 0.1, 0.18, 0.02, 0.1, 0, (0.06, 0.06, 0.1))
            b.cyl("etoffe", 0, 0.235, 0, 0.122, 0.02, 10, (0.85, 0.85, 0.9), cap=False)
            b.build(parent=self.model.head, emit=0.1)
            # gilet « POLICE » (bande réfléchissante)
            vb = MeshBuilder("gilet")
            vb.obox("etoffe", 0, 0.3, 0, 0.42, 0.05, 0.25, 0, (0.85, 0.85, 0.9))
            vb.build(parent=self.model.torso, emit=0.25)
        elif hat == "bonnet":
            b = MeshBuilder("bonnet")
            b.sphere("tricot", 0, 0.2, -0.01, 0.12, (0.6, 0.15, 0.15), lat=4, lon=8, sy=0.8)
            b.build(parent=self.model.head, emit=0.1)
        self.yaw = yaw
        self.wait = 0.0
        self.talk_t = 0.0
        self.speed_now = 0.0
        self.it = hood.game.interactions.add(Interactable(f"pnj_{name}", (pos[0], 1.5, pos[2]), f"Parler — {name}",
                                                          self.talk, 0, radius=0.45, reach=2.6))

    @property
    def pos(self):
        return self.root.position

    def talk(self, it=None):
        g = self.hood.game
        if self.talk_cb is not None and self.talk_cb():
            return
        line = self.lines[self.line_i % len(self.lines)]
        self.line_i += 1
        sound.speak(line, f0=self.f0, speed=1.0, pos=self.pos + Vec3(0, 1.6, 0), volume=0.9, channel="voice", speaker=self.name)
        self.talk_t = 4.0
        g.state.stats["discussions"] = g.state.stats.get("discussions", 0) + 1

    def apply(self, dt, x, z, yaw, spd):
        """Multijoueur (joueurs invités) : position venue du créateur du salon, lissée."""
        k = min(1.0, dt * 10.0)
        self.root.x += (x - self.root.x) * k
        self.root.z += (z - self.root.z) * k
        dy = (yaw - self.root.rotation_y + 180) % 360 - 180
        self.root.rotation_y += dy * k
        self.speed_now += (spd - self.speed_now) * min(1.0, dt * 8.0)
        self.model.animate(dt, self.speed_now, 0.62 if self.pose == "sit" else 0.0, 0.0, self.speed > 2.5, False)
        self.it.pos = self.pos + Vec3(0, 1.45 if self.pose != "sit" else 1.1, 0)

    def update(self, dt, player_pos):
        to_p = Vec3(player_pos[0] - self.pos[0], 0, player_pos[2] - self.pos[2])
        dist_p = to_p.length()
        target_yaw = self.yaw
        moving = False
        if self.talk_t > 0:
            self.talk_t -= dt
            target_yaw = math.degrees(math.atan2(to_p[0], to_p[2]))
        elif self.path and self.pose == "walk":
            tx, tz = self.path[self.idx]
            d = Vec3(tx - self.pos[0], 0, tz - self.pos[2])
            if d.length() < 0.35:
                self.idx = (self.idx + 1) % len(self.path)
                if random.random() < 0.15:
                    self.wait = random.uniform(1.5, 4.0)
            elif self.wait > 0:
                self.wait -= dt
            else:
                dirv = d.normalized()
                # politesse : s'arrête si le joueur est juste devant
                blocked = dist_p < 1.3 and to_p.normalized().dot(dirv) > 0.5
                if not blocked:
                    step = min(d.length(), self.speed * dt)
                    self.root.position += dirv * step
                    moving = True
                target_yaw = math.degrees(math.atan2(dirv[0], dirv[2]))
        elif dist_p < 4.0 and self.pose == "idle":
            target_yaw = self.yaw + max(-60, min(60, ((math.degrees(math.atan2(to_p[0], to_p[2])) - self.yaw + 180) % 360 - 180)))
        dy = (target_yaw - self.root.rotation_y + 180) % 360 - 180
        self.root.rotation_y += dy * min(1.0, dt * 6.0)
        sp = self.speed if moving else 0.0
        self.speed_now += (sp - self.speed_now) * min(1.0, dt * 8.0)
        self.model.animate(dt, self.speed_now, 0.62 if self.pose == "sit" else 0.0, 0.0, self.speed > 2.5, False)
        self.it.pos = self.pos + Vec3(0, 1.45 if self.pose != "sit" else 1.1, 0)


# =============================================================================
# Circulation
# =============================================================================
class TrafficCar:
    def __init__(self, hood, lane_z, direction, col, start_x, cid):
        self.hood = hood
        self.dir = direction            # +1 vers l'est, -1 vers l'ouest
        self.lane = lane_z
        self.x = start_x
        self.speed = 0.0
        self.max_speed = random.uniform(7.5, 9.5)
        self.id = cid
        self.honked = 0.0
        self.root = Entity(parent=hood.dyn_root, position=(start_x, 0, lane_z), rotation_y=0 if direction > 0 else 180)
        import car_builder
        kind = car_builder.KINDS[int(cid.rsplit("_", 1)[-1]) % len(car_builder.KINDS)] if cid[-1:].isdigit() else "berline"
        b = MeshBuilder("voiture")
        car_mesh(b, 0, 0, col, True, kind=kind)
        b.build(parent=self.root, emit=0.05)
        be = MeshBuilder("phares")
        car_lights(be, 0, 0, True, 1, kind=kind)
        be.build(parent=self.root, emit=1.0)
        self.light = LightSource((start_x, 0.8, lane_z), (1.0, 0.92, 0.75), 1.4, 11.0, kind="static", name=f"phares_{cid}")
        hood.lights.append(self.light)

    def update(self, dt, player_pos):
        h = self.hood
        want = self.max_speed
        # feu rouge (ligne d'arrêt avant le carrefour)
        stop_x = BLVD_X0 - 3.0 if self.dir > 0 else BLVD_X1 + 3.0
        ahead_stop = (stop_x - self.x) * self.dir
        if h.light_state != "vert" and 0 < ahead_stop < 14:
            want = min(want, max(0.0, (ahead_stop - 0.5) * 1.2))
        # joueur sur la voie devant la voiture (en multijoueur : n'importe lequel des joueurs)
        for pp in getattr(h, "all_players", None) or [player_pos]:
            dxp = (pp[0] - self.x) * self.dir
            if abs(pp[2] - self.lane) < 1.7 and 0 < dxp < 9.0:
                want = min(want, max(0.0, (dxp - 3.2) * 1.4))
                if dxp < 6.0 and self.honked <= 0:
                    sound.play_at("klaxon", Vec3(self.x, 1.0, self.lane), 0.8, ref=6.0)
                    self.honked = 6.0
        # voiture devant (même voie)
        for o in h.traffic:
            if o is not self and o.dir == self.dir:
                gap = (o.x - self.x) * self.dir
                if 0 < gap < 12:
                    want = min(want, max(0.0, (gap - 6.0) * 1.0))
        self.honked -= dt
        acc = 3.5 if want > self.speed else 9.0
        self.speed += max(-acc * dt, min(acc * dt, want - self.speed))
        self.x += self.speed * self.dir * dt
        if self.dir > 0 and self.x > X_MAX + 8:
            self.x = X_MIN - 8
        elif self.dir < 0 and self.x < X_MIN - 8:
            self.x = X_MAX + 8
        self.root.x = self.x
        self.light.pos = Vec3(self.x + self.dir * 3.0, 0.7, self.lane)
        h.house.dyn_colliders[self.id] = (self.x - 2.1, 0.0, self.lane - 0.9, self.x + 2.1, 1.5, self.lane + 0.9)


# =============================================================================
# Quartier
# =============================================================================
class Neighborhood:
    def __init__(self, game):
        self.game = game
        self.house = game.house
        self.root = Entity(name="quartier")
        self.npc_root = Entity(parent=self.root, name="pnj")
        self.dyn_root = Entity(parent=self.root, name="dynamique")
        self.ui = Entity(parent=camera.ui, z=-2, enabled=False)
        self.lights = []
        self.npcs = []
        self.traffic = []
        self.active = False
        self.outside_phase = False
        self.basket = Basket()
        self.loyalty = Loyalty()
        self.checkout = SelfCheckout(game, self.basket, self.loyalty)
        self.counter = RestaurantCounter(game)
        self.light_t = 0.0
        self.light_state = "vert"
        self.siren_done = False
        self.was_in_shop = False
        self.theft_warnings = 0
        self.t = 0.0
        self._build()
        self._register_zones()
        self.root.enabled = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self):
        rng = random.Random(1717)
        b = MeshBuilder("quartier")
        be = MeshBuilder("quartier_emissif")
        h = self.house
        cols = b.colliders
        # --- chaussées (hors zone déjà posée par la maison : x -30..46) ---
        for (x0, x1) in ((X_MIN - 10, -30.0), (46.0, X_MAX + 10)):
            b.quad("asphalte", (x0, -0.04, ROAD_Z0), (x1, -0.04, ROAD_Z0), (x1, -0.04, ROAD_Z1), (x0, -0.04, ROAD_Z1), (0, 1, 0), (1, 1, 1), tile=3.0)
        for (z0, z1) in ((Z_MIN - 10, ROAD_Z0), (ROAD_Z1, Z_MAX + 10)):
            b.quad("asphalte", (BLVD_X0, -0.039, z0), (BLVD_X1, -0.039, z0), (BLVD_X1, -0.039, z1), (BLVD_X0, -0.039, z1), (0, 1, 0), (1, 1, 1), tile=3.0)
        # marquages : ligne centrale discontinue, passages piétons, lignes d'arrêt
        x = X_MIN
        while x < X_MAX:
            if not (BLVD_X0 - 4 < x < BLVD_X1 + 1):
                b.box("platre", x, -0.035, -11.76, x + 2.0, -0.03, -11.64, (0.95, 0.92, 0.7))
            x += 5.0
        for k in range(7):
            zz = ROAD_Z0 + 0.6 + k * 1.2
            b.box("platre", BLVD_X0 - 3.2, -0.035, zz, BLVD_X0 - 0.4, -0.03, zz + 0.6, (0.95, 0.95, 0.95))
            xx = BLVD_X0 + 0.6 + k * 1.1
            if xx < BLVD_X1 - 0.4:
                b.box("platre", xx, -0.035, ROAD_Z0 - 3.0, xx + 0.55, -0.03, ROAD_Z0 - 0.4, (0.95, 0.95, 0.95))
        for k in range(7):   # passage piéton devant la supérette
            xx = 19.0 + k * 0.6
            b.box("platre", xx, -0.035, ROAD_Z0 + 0.4, xx + 0.32, -0.03, ROAD_Z1 - 0.4, (0.95, 0.95, 0.95))
        # trottoirs (bordure + dalles)
        def sidewalk(x0, z0, x1, z1):
            b.box("beton", x0, -0.04, z0, x1, 0.04, z1, (0.72, 0.7, 0.66))
        sidewalk(X_MIN - 10, ROAD_Z0 - 2.4, BLVD_X0, ROAD_Z0)
        sidewalk(BLVD_X1, ROAD_Z0 - 2.4, X_MAX + 10, ROAD_Z0)
        sidewalk(X_MIN - 10, ROAD_Z1, -14.0, ROAD_Z1 + 1.4)
        sidewalk(30.0, ROAD_Z1, BLVD_X0, ROAD_Z1 + 1.4)
        sidewalk(BLVD_X1, ROAD_Z1, X_MAX + 10, ROAD_Z1 + 1.4)
        for (z0, z1) in ((Z_MIN - 10, ROAD_Z0 - 2.4), (ROAD_Z1 + 1.4, Z_MAX + 10)):
            sidewalk(BLVD_X0 - 1.4, z0, BLVD_X0, z1)
            sidewalk(BLVD_X1, z0, BLVD_X1 + 1.4, z1)
        # sol des îlots (jardins / cours) côté sud et extrémités nord
        for (x0, z0, x1, z1, tex, c) in (
            (X_MIN - 10, Z_MIN - 10, BLVD_X0 - 1.4, ROAD_Z0 - 2.4, "herbe", (0.55, 0.62, 0.5)),
            (BLVD_X1 + 1.4, Z_MIN - 10, X_MAX + 10, ROAD_Z0 - 2.4, "herbe", (0.55, 0.62, 0.5)),
            (X_MIN - 10, ROAD_Z1 + 1.4, -14.0, Z_MAX + 10, "herbe", (0.55, 0.62, 0.5)),
            (30.0, ROAD_Z1 + 1.4, BLVD_X0 - 1.4, Z_MAX + 10, "herbe", (0.55, 0.62, 0.5)),
            (BLVD_X1 + 1.4, ROAD_Z1 + 1.4, X_MAX + 10, Z_MAX + 10, "herbe", (0.55, 0.62, 0.5)),
        ):
            b.quad(tex, (x0, -0.05, z0), (x1, -0.05, z0), (x1, -0.05, z1), (x0, -0.05, z1), (0, 1, 0), c, tile=2.0)
        # parvis pavé devant la supérette et le restaurant
        b.box("carrelage", -16.0, -0.045, ROAD_Z0 - 9.0, 36.0, 0.02, ROAD_Z0 - 2.4, (0.62, 0.58, 0.52), tile=0.8)
        # --- bâtiments ---
        self._build_shop(b, be, rng)
        self._build_resto(b, be, rng)
        self._build_villas(b, be, rng)
        # --- mobilier urbain ---
        self._street_lamps(b, be)
        self._street_furniture(b)
        self._bus_stop(b, be)
        self._traffic_light(b, be)
        self._barriers(b, be)
        # végétation de bord de route
        for k in range(16):
            x = X_MIN + 6 + k * 11.3
            if abs(x - SHOP_DOOR_X) < 14 or abs(x - RESTO_DOOR_X) < 10 or BLVD_X0 - 3 < x < BLVD_X1 + 3:
                continue
            b.palm(x, ROAD_Z0 - 1.8, rng.uniform(5.5, 7.5), (rng.uniform(-0.6, 0.6), rng.uniform(-0.5, 0.2)), seed=k + 40, fronds=8)
        # voitures des voisins garées le long des trottoirs
        car_cols = [(0.6, 0.08, 0.08), (0.12, 0.2, 0.42), (0.85, 0.85, 0.86), (0.12, 0.12, 0.13), (0.3, 0.42, 0.3),
                    (0.75, 0.6, 0.15), (0.45, 0.45, 0.5), (0.2, 0.3, 0.55)]
        parked = [(-22.0, -8.3), (-38.0, -8.3), (36.0, -8.3), (64.0, -8.3), (-50.0, -15.1), (-27.0, -15.1), (4.0, -15.1),
                  (70.0, -15.1), (90.0, -8.3)]
        for i, (px_, pz_) in enumerate(parked):
            # quelques voitures sous bâche (modèle 3D), les autres modelées (citadine / berline / utilitaire)
            if i not in (2, 6) or not b.model("covered_car", px_, pz_, 0.0, 0.0, (4.1, 1.5, 1.8), free_yaw=True):
                car_mesh(b, px_, pz_, car_cols[i % len(car_cols)], True)
            cols.append((px_ - 2.1, 0, pz_ - 0.9, px_ + 2.1, 1.5, pz_ + 0.9))
        # scooter de livraison abandonné (référence au livreur disparu)
        b.obox("metal", -3.0, 0.2, ROAD_Z0 - 1.2, 1.6, 0.5, 0.5, 20, (0.95, 0.45, 0.08))
        b.obox("metal", -2.6, 0.7, ROAD_Z0 - 1.1, 0.5, 0.45, 0.5, 20, (0.95, 0.45, 0.08))
        # voiture de police (boulevard, à l'angle)
        self.police_pos = Vec3(BLVD_X0 + 2.0, 0, ROAD_Z0 - 8.0)
        car_mesh(b, self.police_pos[0], self.police_pos[2], (1, 1, 1), along_x=False, police=True)
        cols.append((self.police_pos[0] - 0.9, 0, self.police_pos[2] - 2.1, self.police_pos[0] + 0.9, 1.5, self.police_pos[2] + 2.1))
        self.gyro = []
        for k, c in enumerate(((0.15, 0.3, 1.0), (1.0, 0.1, 0.1))):
            gb = MeshBuilder(f"gyro{k}")
            gb.obox("neon", self.police_pos[0] + (k - 0.5) * 0.5, 1.33, self.police_pos[2] + 0.1, 0.42, 0.12, 0.22, 0, c)
            e = gb.build(parent=self.root, emit=1.0)
            self.gyro.append(e)
        self.gyro_lights = [LightSource(self.police_pos + Vec3(-0.6, 1.8, 0), (0.2, 0.35, 1.0), 1.8, 10.0, name="gyro_bleu"),
                            LightSource(self.police_pos + Vec3(0.6, 1.8, 0), (1.0, 0.15, 0.1), 1.4, 9.0, name="gyro_rouge")]
        self.lights.extend(self.gyro_lights)
        # lettrage lisible des deux côtés (le quad est vu de face côté extérieur)
        sign(self.root, "POLICE", (self.police_pos[0] + 0.9, 0.72, self.police_pos[2]), 0.22, -90, (20, 40, 140))
        sign(self.root, "POLICE", (self.police_pos[0] - 0.9, 0.72, self.police_pos[2]), 0.22, 90, (20, 40, 140))
        # limites de la zone (murs invisibles)
        for c in ((X_MIN - 1, -1, Z_MIN - 1, X_MIN, 6, Z_MAX + 1), (X_MAX, -1, Z_MIN - 1, X_MAX + 1, 6, Z_MAX + 1),
                  (X_MIN - 1, -1, Z_MIN - 1, X_MAX + 1, 6, Z_MIN), (X_MIN - 1, -1, Z_MAX, X_MAX + 1, 6, Z_MAX + 1)):
            cols.append(c)
        self.static = b.build(parent=self.root, emit=0.0)
        be.build(parent=self.root, emit=1.0)
        # enregistre colliders et sol dans la maison (physique commune)
        h.colliders.extend(cols)
        h._index_colliders()
        for r in rect_minus((X_MIN - 2, Z_MIN - 2, X_MAX + 2, Z_MAX + 2), CAVE_STAIRWELL):
            h.surfaces.append(Surface(*r, 0.0, level=0))
        h.surfaces.extend(bianchi_house.surfaces(Surface))
        for l in self.lights:
            h.lights.append(l)
        self._spawn_npcs()
        self._spawn_traffic()
        self._shop_interactables()

    def _primeur_stand(self, b, cx, cz, rng, items):
        """Étal de primeur (fresh_aisle.produce_stand) dont chaque cagette se prend au panier."""
        fresh_aisle.produce_stand(b, cx, cz, rng, items)
        # mêmes positions que dans produce_stand : 2 rangées de 4
        for row, (yy, zz) in enumerate(((0.85, cz - 0.25), (0.55, cz + 0.25))):
            for k in range(4):
                self.primeur_points.append((primeur_article(items[(row * 4 + k) % len(items)]),
                                            Vec3(cx - 1.1 + 0.28 + k * 0.55, yy + 0.12, zz)))

    def _build_shop(self, b, be, rng):
        self.primeur_points = []
        x0, z0, x1, z1 = SHOP
        H = SHOP_H
        # murs (façade vitrée côté rue, porte automatique au centre)
        b.box("platre", x0, 0, z0, x1, H + 0.8, z0 + 0.25, (0.92, 0.93, 0.95), collide=True)
        b.box("platre", x0, 0, z0, x0 + 0.25, H + 0.8, z1, (0.92, 0.93, 0.95), collide=True)
        b.box("platre", x1 - 0.25, 0, z0, x1, H + 0.8, z1, (0.92, 0.93, 0.95), collide=True)
        d0, d1 = SHOP_DOOR_X - 1.3, SHOP_DOOR_X + 1.3
        for (a0, a1) in ((x0, d0), (d1, x1)):
            b.box("beton", a0, 0, z1 - 0.2, a1, 0.5, z1, (0.4, 0.42, 0.46), collide=True)
            b.box("vitre", a0 + 0.05, 0.5, z1 - 0.12, a1 - 0.05, H, z1 - 0.08, (0.6, 0.7, 0.8), collide=True)
            x = a0
            while x <= a1:
                b.box("metal", x - 0.04, 0.5, z1 - 0.16, x + 0.04, H, z1 - 0.04, (0.3, 0.32, 0.36))
                x += 2.0
        # bandeau et liseré dépassent d'1 cm des murs latéraux (faces non coplanaires : pas de scintillement)
        b.box("platre", x0 - 0.01, H, z1 - 0.3, x1 + 0.01, H + 0.8, z1 + 0.02, (0.04, 0.12, 0.45))   # bandeau bleu Carrefour
        b.box("platre", x0 - 0.015, H - 0.05, z1 - 0.32, x1 + 0.015, H + 0.02, z1 + 0.04, (0.82, 0.08, 0.12))  # liseré rouge
        # toit
        b.box("beton", x0, H + 0.8, z0, x1, H + 0.9, z1, (0.4, 0.4, 0.42))
        # sol / plafond intérieurs
        b.box("carrelage", x0 + 0.25, -0.02, z0 + 0.25, x1 - 0.25, 0.03, z1 - 0.2, (0.95, 0.95, 0.97), tile=0.6)
        b.quad("plafond", (x0, H - 0.005, z0), (x1, H - 0.005, z0), (x1, H - 0.005, z1), (x0, H - 0.005, z1), (0, -1, 0),
               (0.95, 0.95, 0.95), tile=1.2)
        # éclairage néon (rangées)
        self.shop_lights = []
        for k, zz in enumerate((-33.0, -28.5, -24.0)):
            for xx in (14.0, 21.0, 28.0):
                be.box("neon", xx - 1.6, H - 0.08, zz - 0.12, xx + 1.6, H - 0.02, zz + 0.12, (1.0, 1.0, 0.96))
            l = LightSource((21.0, H - 0.4, zz), (0.95, 0.97, 1.0), 2.4, 14.0, kind="static", name=f"magasin_{k}")
            self.lights.append(l)
            self.shop_lights.append(l)
        # rayons (gondoles) : 4 allées le long de z
        self.shelf_slots = {}
        product_labels = ("Crousti'Chips", "Eau Pure", "Pasta Bella", "Choco Max", "Café Noir", "Savon Doux",
                          "Biscuits Miel", "Lait des Alpes", "Jus Soleil", "Tropi'Fruits")
        product_index = 0
        aisle_x = [14.0, 18.5, 23.5, 28.0]
        shelves = ["bazar", "epicerie", "presse", "epicerie"]
        for i, ax in enumerate(aisle_x):
            sz0, sz1 = -33.0, -26.0
            b.box("metal", ax - 0.45, 0, sz0, ax + 0.45, 1.85, sz1, (0.85, 0.86, 0.9), collide=True)
            for lvl in range(4):
                yy = 0.25 + lvl * 0.42
                for side in (-1, 1):
                    b.box("metal", ax + side * 0.45, yy, sz0, ax + side * 0.62, yy + 0.03, sz1, (0.75, 0.76, 0.8))
                    if i > 0:
                        # présentoirs des articles achetables (niveau 1) : on laisse la place libre devant eux
                        stands = [sz0 + 1.2 + k * 2.3 for k in range(3)] if lvl == 1 else []
                        z = sz0
                        for zs in stands + [sz1]:
                            fresh_aisle.shelf_food(b, ax + side * 0.535, yy + 0.03, z, zs - (0.3 if zs != sz1 else 0.0), side,
                                                   "boissons" if i == 2 else "epicerie", lvl, rng)
                            z = zs + 0.3
                        continue
                    z = sz0 + 0.1
                    while z < sz1 - 0.2:
                        d = rng.uniform(0.17, 0.3)
                        if z + d > sz1 - 0.08:
                            break
                        w = rng.uniform(0.14, 0.22)
                        hgt = rng.uniform(0.18, 0.34)
                        c = rng.choice([(0.85, 0.2, 0.2), (0.2, 0.4, 0.8), (0.95, 0.8, 0.2), (0.3, 0.6, 0.3), (0.9, 0.9, 0.88),
                                        (0.55, 0.3, 0.15), (0.95, 0.5, 0.1)])
                        b.product_box(ax + side * 0.535, yy + 0.03, z + d / 2, w, hgt, d, c,
                                      product_labels[product_index % len(product_labels)])
                        product_index += 1
                        z += d + 0.03
            # panneau d'allée suspendu
            sign(self.root, ["BAZAR / PILES", "ÉPICERIE", "PRESSE / BOISSONS", "ÉPICERIE FINE"][i], (ax, H - 0.55, sz1 + 0.6), 0.22,
                 180, (255, 255, 255), (18, 72, 160, 255), px=64)
            self.shelf_slots[shelves[i]] = self.shelf_slots.get(shelves[i], []) + [(ax, sz0, sz1)]
        # panneau suspendu au-dessus de l'entrée
        for xx in (19.5, 22.5):
            b.box("metal", xx - 0.025, H - 0.48, -22.28, xx + 0.025, H - 0.04, -22.2, (0.28, 0.3, 0.33))
        b.box("metal", 18.8, 2.82, -22.3, 23.2, 3.2, -22.18, (0.06, 0.12, 0.24))
        sign(self.root, "← FRAIS   ÉPICERIE →", (21.0, 3.01, -22.16), 0.26, 180,
             (255, 255, 255), (18, 72, 160, 255), px=76)
        # mur réfrigéré : modules à portes vitrées garnis de produits frais modelés (fresh_aisle.py)
        fb = MeshBuilder("rayon_frais")
        fbe = MeshBuilder("rayon_frais_led")
        headers = fresh_aisle.build_fridges(fb, fbe, x0 + 1.0, x1 - 1.0, z0 + 0.25, z0 + 1.0)
        fb.build(parent=self.root, emit=0.18)
        fbe.build(parent=self.root, emit=1.0)
        b.colliders.extend(fb.colliders)                 # collisions du meuble (enregistrées avec celles du quartier)
        for text, hx in headers:
            sign(self.root, text, (hx + 0.6, 2.27, z0 + 1.075), 0.13, 180, (255, 255, 255), px=56)
        sign(self.root, "FRAIS", (21.0, 2.7, z0 + 0.28), 0.4, 180, (255, 255, 255), (18, 72, 160, 255), px=72)
        # affiches promotionnelles au-dessus du frigo
        for xx, text, bg in ((14.5, "2+1 GRATUIT", (214, 36, 46, 255)),
                             (21.0, "NOUVEAU", (18, 72, 160, 255)),
                             (27.5, "BIO & LOCAL", (46, 139, 87, 255))):
            sign(self.root, text, (xx, 3.22, z0 + 0.28), 0.24, 180, (255, 255, 255), bg, px=64)
        # caisses automatiques (2 bornes) + caisse fermée + portiques
        self.kiosks = [Vec3(12.6, 0, -23.2), Vec3(15.0, 0, -23.2)]
        for k in self.kiosks:
            b.box("metal", k[0] - 0.4, 0, k[2] - 0.35, k[0] + 0.4, 0.9, k[2] + 0.35, (0.85, 0.86, 0.9), collide=True)
            b.box("metal", k[0] - 0.05, 0.9, k[2] - 0.05, k[0] + 0.05, 1.5, k[2] + 0.05, (0.3, 0.3, 0.33))
            b.obox("ecran_noir", k[0], 1.3, k[2] + 0.1, 0.5, 0.36, 0.05, 0, (1, 1, 1))
            be.box("neon", k[0] - 0.22, 1.33, k[2] + 0.13, k[0] + 0.22, 1.62, k[2] + 0.14, (0.35, 0.6, 1.0))
            be.box("neon", k[0] - 0.4, 0.9, k[2] - 0.35, k[0] + 0.4, 0.93, k[2] + 0.35, (0.2, 0.9, 0.4))
        sign(self.root, "CAISSES AUTOMATIQUES", (13.8, 2.6, -23.5), 0.22, 180, (255, 255, 255), (214, 36, 46, 255), px=60)
        # repères de file jaune au sol devant les bornes
        for zz in (-24.95, -24.65, -24.35):
            b.box("carrelage", 11.8, 0.035, zz, 15.8, 0.048, zz + 0.045, (1.0, 0.82, 0.08), tile=0.5)
        b.box("bois_meuble", 17.6, 0, -24.4, 18.6, 0.95, -22.0, (0.7, 0.72, 0.78), collide=True)
        b.model("CashRegister_01", 18.1, -22.6, 0.95, 0.0, (0.5, None, 0.5))
        b.model("WetFloorSign_01", 16.3, -28.0, 0.0, 30.0, (None, 0.62, None))
        sign(self.root, "CAISSE FERMÉE", (18.1, 1.25, -23.2), 0.12, 0, (255, 255, 255), (214, 36, 46, 255), px=48)
        for gx in (SHOP_DOOR_X - 1.15, SHOP_DOOR_X + 1.15):
            b.box("metal", gx - 0.05, 0, z1 - 1.1, gx + 0.05, 1.5, z1 - 0.7, (0.8, 0.82, 0.88), collide=True)
        # enseigne lumineuse Carrefour City
        enseigne = sign(self.root, SHOP_NAME, (SHOP_DOOR_X, H + 0.42, z1 + 0.06), 0.55, 180,
                        (255, 255, 255), bg=(10, 30, 115, 255), px=110)
        # horaires et promos sur la vitrine
        sign(self.root, "Ouvert 7j/7 · 7h – 23h", (SHOP_DOOR_X + 6.5, 2.6, z1 + 0.04), 0.2, 180,
             (255, 255, 255), (214, 36, 46, 230), px=48)
        sign(self.root, "PROMO CARTE : -1 € sur les piles", (SHOP_DOOR_X - 6.5, 2.6, z1 + 0.04), 0.2, 180,
             (255, 255, 255), (18, 72, 160, 230), px=48)
        # logo Carrefour (croix rouge/bleu), collé à gauche de l'enseigne vue depuis la rue (+x)
        self._carrefour_logo(SHOP_DOOR_X + enseigne.scale_x / 2 + 0.45, H + 0.42, z1 + 0.06)
        # affiches promo dans les vitrines
        sign(self.root, "FRUITS & LÉGUMES  FRAIS", (x0 + 4.0, 1.8, z1 + 0.02), 0.18, 180,
             (255, 255, 255), (46, 139, 87, 230), px=48)
        sign(self.root, "- 30 %  SUR LE BIO", (x1 - 4.0, 1.8, z1 + 0.02), 0.18, 180,
             (255, 255, 255), (214, 36, 46, 230), px=48)
        self.lights.append(LightSource((SHOP_DOOR_X, 3.0, z1 + 1.5), (0.6, 0.7, 1.0), 1.5, 9.0, name="enseigne"))
        # portes coulissantes (animées)
        self.door_panels = []
        for s in (-1, 1):
            db = MeshBuilder("porte_auto")
            db.box("vitre", -0.65, 0, -0.03, 0.65, 2.5, 0.03, (0.65, 0.75, 0.85))
            db.box("metal", -0.65, 2.45, -0.04, 0.65, 2.55, 0.04, (0.3, 0.32, 0.36))
            root = Entity(parent=self.root, position=(SHOP_DOOR_X + s * 0.65, 0, z1 - 0.1))
            db.build(parent=root)
            self.door_panels.append((root, s))
        self.door_open = 0.0
        b.box("metal", d0 - 0.1, 2.5, z1 - 0.2, d1 + 0.1, H, z1, (0.3, 0.32, 0.36))      # linteau (assorti aux montants)

        # --- éléments extérieurs ---
        # tapis d'entrée
        b.box("moquette", SHOP_DOOR_X - 1.6, 0.01, z1 + 0.18, SHOP_DOOR_X + 1.6, 0.04, z1 + 1.25,
              (0.16, 0.17, 0.19), tile=1.0)
        # étals de primeur en gradins devant la vitrine gauche (cagettes posées dessus, ardoises de prix côté rue)
        for stand_i, cx in enumerate((12.9, 15.15)):            # accolés : pas de recoin entre les deux
            cz = z1 + 0.78
            # 15 sortes pour 16 cagettes : une seule revient (en bout d'étal)
            items = [fresh_aisle.PRODUCE[(stand_i * 8 + k) % len(fresh_aisle.PRODUCE)] for k in range(8)]
            self._primeur_stand(b, cx, cz, rng, items)
            for sx in (cx - 1.06, cx + 1.06):                   # pieds en métal qui dépassent sous le plateau
                b.box("metal", sx - 0.03, 0.0, cz + 0.44, sx + 0.03, 0.06, cz + 0.5, (0.2, 0.2, 0.22))
            # bloc de collision sur toute l'emprise (cagettes comprises) : on ne peut ni entrer ni grimper dessus
            b.colliders.append((cx - 1.12, 0.0, cz - 0.52, cx + 1.12, 1.0, cz + 0.52))
        # distributeur de sacs
        b.box("metal", 23.35, 0, z1 + 0.32, 23.82, 0.88, z1 + 0.62, (0.48, 0.5, 0.54), collide=True)
        b.box("ecran_noir", 23.43, 0.56, z1 + 0.63, 23.74, 0.74, z1 + 0.65, (0.8, 0.84, 0.88))
        # cartouche OUVERT lumineux
        b.box("metal", SHOP_DOOR_X - 1.1, 2.68, z1 + 0.16, SHOP_DOOR_X + 1.1, 3.18, z1 + 0.22, (0.08, 0.12, 0.1))
        be.box("neon", SHOP_DOOR_X - 0.96, 2.76, z1 + 0.225, SHOP_DOOR_X + 0.96, 3.1, z1 + 0.24,
               (0.2, 1.0, 0.38))
        sign(self.root, "OUVERT", (SHOP_DOOR_X, 2.93, z1 + 0.25), 0.25, 180, (255, 255, 255), px=82)

    def _carrefour_logo(self, x, y, z):
        """Logo Carrefour simplifié (losange rouge/bleu) sur la façade."""
        from PIL import Image, ImageDraw
        from texture_generator import textures
        sz = 200
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = sz // 2
        r = int(sz * 0.44)
        d.ellipse([c - r, c - r, c + r, c + r], fill=(255, 255, 255, 255))
        # flèche gauche (rouge)
        pts_r = [(c - r * 0.15, c), (c - r * 0.7, c - r * 0.5), (c - r * 0.7, c + r * 0.5)]
        d.polygon(pts_r, fill=(214, 36, 46, 255))
        # flèche droite (bleue)
        pts_b = [(c + r * 0.15, c), (c + r * 0.7, c - r * 0.5), (c + r * 0.7, c + r * 0.5)]
        d.polygon(pts_b, fill=(10, 30, 115, 255))
        tex = textures.from_pil(img)
        Entity(parent=self.root, model="quad", texture=tex, position=(x, y, z),
               rotation_y=180, scale=(0.62, 0.62), double_sided=True)

    def _build_resto(self, b, be, rng):
        x0, z0, x1, z1 = RESTO
        H = 3.3
        warm = (0.95, 0.72, 0.5)
        b.box("crepi_rose", x0, 0, z0, x1, H + 0.4, z0 + 0.25, (0.9, 0.85, 0.82), collide=True)
        b.box("crepi_rose", x0, 0, z0, x0 + 0.25, H + 0.4, z1, (0.9, 0.85, 0.82), collide=True)
        b.box("crepi_rose", x1 - 0.25, 0, z0, x1, H + 0.4, z1, (0.9, 0.85, 0.82), collide=True)
        d0, d1 = RESTO_DOOR_X - 0.8, RESTO_DOOR_X + 0.8
        for (a0, a1) in ((x0 + 0.25, d0), (d1, x1 - 0.25)):        # entre les murs latéraux (pas de faces superposées)
            b.box("crepi_rose", a0, 0, z1 - 0.25, a1, 0.8, z1, (0.9, 0.85, 0.82), collide=True)
            b.box("vitre", a0 + 0.1, 0.8, z1 - 0.15, a1 - 0.1, 2.5, z1 - 0.1, (0.85, 0.7, 0.5), collide=True)
            b.box("crepi_rose", a0, 2.5, z1 - 0.25, a1, H + 0.4, z1, (0.9, 0.85, 0.82))
        b.box("crepi_rose", d0, 2.4, z1 - 0.25, d1, H + 0.4, z1, (0.9, 0.85, 0.82))
        # toit de tuiles + store banne rayé
        b.quad("tuiles", (x0 - 0.3, H + 0.4, z0 - 0.3), (x1 + 0.3, H + 0.4, z0 - 0.3), (x1 + 0.3, H + 1.6, (z0 + z1) / 2),
               (x0 - 0.3, H + 1.6, (z0 + z1) / 2), (0, 0.8, -0.6), (0.9, 0.85, 0.8))
        b.quad("tuiles", (x0 - 0.3, H + 1.6, (z0 + z1) / 2), (x1 + 0.3, H + 1.6, (z0 + z1) / 2), (x1 + 0.3, H + 0.4, z1 + 0.3),
               (x0 - 0.3, H + 0.4, z1 + 0.3), (0, 0.8, 0.6), (0.9, 0.85, 0.8))
        for k in range(14):
            xa = x0 + k * (x1 - x0) / 14
            c = (0.75, 0.1, 0.1) if k % 2 == 0 else (0.95, 0.92, 0.85)
            b.leaf("etoffe", (xa, 2.75, z1), (xa + (x1 - x0) / 14, 2.75, z1), (xa + (x1 - x0) / 14, 2.25, z1 + 1.9), (xa, 2.25, z1 + 1.9), c)
        # intérieur : sol damier, comptoir, four à bois, tables
        b.box("carrelage", x0 + 0.25, -0.02, z0 + 0.25, x1 - 0.25, 0.03, z1 - 0.25, (0.85, 0.8, 0.72), tile=0.5)
        b.quad("plafond", (x0, H, z0), (x1, H, z0), (x1, H, z1), (x0, H, z1), (0, -1, 0), (0.8, 0.7, 0.6))
        b.box("bois_meuble", x0 + 1.0, 0, z0 + 1.2, x0 + 7.0, 1.05, z0 + 1.9, (0.55, 0.35, 0.22), collide=True)   # comptoir
        b.box("marbre", x0 + 0.95, 1.05, z0 + 1.15, x0 + 7.05, 1.1, z0 + 1.95, (1, 1, 1))
        b.box("crepi", x1 - 3.6, 0, z0 + 0.25, x1 - 1.0, 2.2, z0 + 1.6, (0.75, 0.55, 0.45), collide=True)       # four
        b.sphere("crepi", x1 - 2.3, 2.1, z0 + 0.9, 1.0, (0.7, 0.5, 0.42), sy=0.6)
        be.box("neon", x1 - 2.8, 0.7, z0 + 1.6, x1 - 1.8, 1.2, z0 + 1.62, (1.0, 0.45, 0.1))
        self.lights.append(LightSource((x1 - 2.3, 1.0, z0 + 2.4), (1.0, 0.5, 0.2), 1.6, 6.0, kind="candle", name="four"))
        self.lights.append(LightSource(((x0 + x1) / 2, H - 0.5, (z0 + z1) / 2), warm, 1.8, 10.0, kind="static", name="resto"))
        for (tx, tz) in ((x0 + 3.0, z1 - 2.0), (x0 + 6.5, z1 - 2.0), (x1 - 4.0, z1 - 2.4)):
            self._table(b, tx, tz)
        # terrasse
        for (tx, tz) in ((x0 + 2.0, z1 + 1.6), (x0 + 5.2, z1 + 1.6), (x1 - 2.0, z1 + 1.6)):
            self._table(b, tx, tz)
        for k in range(4):
            be.sphere("neon", x0 + 1.5 + k * 3.6, 2.5, z1 + 0.6, 0.06, (1.0, 0.85, 0.5), lat=3, lon=5)
        self.lights.append(LightSource(((x0 + x1) / 2, 2.4, z1 + 1.2), warm, 1.5, 9.0, kind="candle", name="terrasse"))
        sign(self.root, RESTO_NAME, (RESTO_DOOR_X, 3.25, z1 + 0.03), 0.48, 180, (255, 214, 150), kind="serif", px=110)
        sign(self.root, "Socca · Pan bagnat · Pissaladière", (RESTO_DOOR_X + 4.2, 3.25, z1 + 0.03), 0.16, 180, (255, 236, 200), px=48)
        b.box("bois_meuble", x0 + 0.6, 0, z1 + 0.15, x0 + 1.3, 1.1, z1 + 0.3, (0.3, 0.2, 0.12))
        sign(self.root, "MENU du soir", (x0 + 0.95, 0.85, z1 + 0.32), 0.12, 180, (255, 255, 255), (30, 30, 30, 255), px=40)
        self.counter_pos = Vec3(x0 + 4.0, 1.2, z0 + 2.3)

    def _table(self, b, tx, tz):
        # ensemble table + 2 chaises à taille réelle (1,72 x 0,74 m, 0,86 m de haut), tourné dans le sens de la façade
        if b.model("outdoor_table_chair_set_01", tx, tz, 0.0, 90.0):
            b.colliders.append((tx - 0.86, 0, tz - 0.37, tx + 0.86, 0.86, tz + 0.37))
            return
        b.cyl("metal", tx, 0, tz, 0.05, 0.72, 6, (0.25, 0.25, 0.27))
        b.cyl("marbre", tx, 0.72, tz, 0.42, 0.04, 10, (1, 1, 1))
        for (cx, cz) in ((tx - 0.62, tz), (tx + 0.62, tz)):
            b.box("bois_meuble", cx - 0.2, 0.42, cz - 0.2, cx + 0.2, 0.46, cz + 0.2, (0.6, 0.4, 0.25))
            for (lx, lz) in ((-0.17, -0.17), (0.17, -0.17), (-0.17, 0.17), (0.17, 0.17)):
                b.box("metal", cx + lx - 0.015, 0, cz + lz - 0.015, cx + lx + 0.015, 0.42, cz + lz + 0.015, (0.2, 0.2, 0.2))
        b.colliders.append((tx - 0.45, 0, tz - 0.45, tx + 0.45, 0.8, tz + 0.45))

    def _villa(self, b, be, x0, z0, w, d, h, tex, rng, street_side, explorable=False):
        """Villa niçoise : enduit, soubassement en pierre, corniche, toit de tuiles, cheminée, fenêtres en relief
        (encadrements, appuis, persiennes ouvertes), balcon en fer forgé à l'étage, porte avec marche et applique."""
        x1, z1 = x0 + w, z0 + d
        wall = (0.9, 0.88, 0.85)
        # la face côté rue est construite plus bas, percée derrière fenêtres / volets / porte (anti z-fighting)
        # villa explorable : coque sans collision (les murs intérieurs portent les collisions), porte ouverte
        # (pignon est construit par bianchi_house, percé de ses fenêtres)
        b.box(tex, x0, 0, z0, x1, h, z1, wall, collide=not explorable,
              skip=(("-z",) if street_side < 0 else ("+z",)) + (("+x",) if explorable else ()))
        zm = (z0 + z1) / 2
        rc = (0.85, 0.78, 0.74)
        # toit à deux pans débordant + génoises (corniche) + cheminée
        b.quad("tuiles", (x0 - 0.4, h, z0 - 0.4), (x1 + 0.4, h, z0 - 0.4), (x1 + 0.4, h + 1.8, zm), (x0 - 0.4, h + 1.8, zm), (0, 0.8, -0.6), rc)
        b.quad("tuiles", (x0 - 0.4, h + 1.8, zm), (x1 + 0.4, h + 1.8, zm), (x1 + 0.4, h, z1 + 0.4), (x0 - 0.4, h, z1 + 0.4), (0, 0.8, 0.6), rc)
        for xs in (x0, x1):
            nrm = (-1, 0, 0) if xs == x0 else (1, 0, 0)
            b.tri(tex, (xs, h, z0), (xs, h, z1), (xs, h + 1.8, zm), nrm, (0.85, 0.83, 0.8))
        for k, (dz, hh) in enumerate(((0.0, 0.16), (0.1, 0.12))):
            b.box("crepi", x0 - 0.12 - dz, h - hh - k * 0.14, z0 - 0.12 - dz, x1 + 0.12 + dz, h - k * 0.14, z1 + 0.12 + dz, (0.96, 0.94, 0.9))
        cx = x0 + w * rng.uniform(0.2, 0.8)
        b.box(tex, cx - 0.35, h + 0.6, zm - 0.3, cx + 0.35, h + 2.6, zm + 0.3, (0.82, 0.8, 0.77), collide=False)
        b.box("beton", cx - 0.42, h + 2.6, zm - 0.37, cx + 0.42, h + 2.72, zm + 0.37, (0.5, 0.48, 0.46))
        # soubassement en pierre (légèrement en saillie)
        b.box("beton", x0 - 0.03, 0, z0 - 0.03, x1 + 0.03, 0.6, z1 + 0.03, (0.62, 0.6, 0.57))
        # descentes d'eau aux angles côté rue
        fz_wall = z0 if street_side < 0 else z1
        for xs in (x0 + 0.08, x1 - 0.08):
            b.cyl("metal", xs, 0.0, fz_wall + street_side * 0.06, 0.04, h, 8, (0.42, 0.4, 0.38))
        out = -1 if street_side < 0 else 1                 # vers la rue
        fz = fz_wall + out * 0.005
        nrm = (0, 0, out)
        floors = 2 if h > 5 else 1
        door_x = x0 + w * 0.5

        def zz(a, b_):
            return (min(fz + out * a, fz + out * b_), max(fz + out * a, fz + out * b_))

        # Anti z-fighting : le mur côté rue n'est pas dessiné derrière les éléments de fenêtre (le tampon de
        # profondeur ne sépare pas des faces à quelques mm / cm de distance vues de loin). Chaque élément est
        # « encastré » (il part de 2 cm dans le mur) et le mur est percé derrière lui (holes, en x / y).
        holes = []
        back = -0.025                                       # = 2 cm à l'intérieur du plan du mur
        for fl in range(floors):
            y = 1.0 + fl * 3.0
            xx = x0 + 1.0
            while xx < x1 - 1.4:
                if fl == 0 and abs(xx + 0.45 - door_x) < 1.0:     # la porte d'entrée est là
                    xx += 2.6
                    continue
                lit = rng.random() < 0.3
                # vitre (éclairée ou sombre) dans le plan du mur, en deux carreaux de part et d'autre du meneau
                # (opaque : le mur est percé derrière, il n'y a donc plus de face superposée)
                for (u0, u1) in ((xx, xx + 0.43), (xx + 0.47, xx + 0.9)):
                    pts = ((u0, y, fz_wall), (u1, y, fz_wall), (u1, y + 1.4, fz_wall), (u0, y + 1.4, fz_wall))
                    if lit:
                        be.quad("neon", *pts, nrm, (1.0, 0.72, 0.42))
                    else:
                        b.quad("miroir", *pts, nrm, (0.62, 0.66, 0.7))
                holes.append((xx, y, xx + 0.9, y + 1.4))
                a, c = zz(back, 0.07)
                for (u0, u1, v0, v1) in ((xx - 0.08, xx, y - 0.02, y + 1.4), (xx + 0.9, xx + 0.98, y - 0.02, y + 1.4),
                                         (xx - 0.08, xx + 0.98, y + 1.4, y + 1.52)):
                    b.box("crepi", u0, v0, a, u1, v1, c, (0.97, 0.96, 0.93))         # encadrement (sans recouvrement)
                    holes.append((u0, v0, u1, v1))
                a, c = zz(back, 0.14)
                b.box("beton", xx - 0.12, y - 0.1, a, xx + 1.02, y - 0.02, c, (0.75, 0.73, 0.7))   # appui de fenêtre
                holes.append((xx - 0.12, y - 0.1, xx + 1.02, y - 0.02))
                a, c = zz(back, 0.012)
                b.box("metal", xx + 0.43, y, a, xx + 0.47, y + 1.4, c, (0.25, 0.25, 0.25))   # meneau
                # persiennes ouvertes de part et d'autre, en relief
                a, c = zz(back, 0.05)
                for sx in (xx - 0.54, xx + 1.04):
                    b.box("volet", sx, y - 0.02, a, sx + 0.44, y + 1.42, c, (0.85, 0.95, 0.9))
                    holes.append((sx, y - 0.02, sx + 0.44, y + 1.42))
                xx += 2.6
        # balcon en fer forgé au centre de l'étage
        if floors == 2:
            bx0, bx1, by = door_x - 1.1, door_x + 1.1, 3.95
            a, c = zz(0.0, 0.75)
            b.box("beton", bx0, by - 0.12, a, bx1, by, c, (0.7, 0.68, 0.65))
            rz = fz + out * 0.72
            b.box("metal", bx0, by + 0.9, rz - 0.02, bx1, by + 0.94, rz + 0.02, (0.12, 0.12, 0.13))
            k = 0
            while bx0 + k * 0.12 <= bx1:
                b.box("metal", bx0 + k * 0.12, by, rz - 0.01, bx0 + k * 0.12 + 0.02, by + 0.9, rz + 0.01, (0.12, 0.12, 0.13))
                k += 1
            for xs in (bx0, bx1 - 0.02):
                a2, c2 = zz(0.0, 0.73)
                b.box("metal", xs, by + 0.9, a2, xs + 0.02, by + 0.94, c2, (0.12, 0.12, 0.13))
        # porte d'entrée : encadrement, marche, applique. La porte est dans le plan du mur (percé derrière) et ne
        # commence qu'au-dessus du soubassement en pierre, qui la masquait (faces à 2 cm l'une de l'autre).
        yd = 0.6
        if not explorable:
            b.quad("porte", (door_x - 0.5, yd, fz_wall), (door_x + 0.5, yd, fz_wall), (door_x + 0.5, 2.25, fz_wall),
                   (door_x - 0.5, 2.25, fz_wall), nrm, (0.75, 0.6, 0.5), tile=(1.0, 2.1), uv_off=(0.0, (yd - 0.15) / 2.1))
        else:
            # porte entrouverte vers l'intérieur (battant pivoté de 70° autour de son gond gauche)
            ang = math.radians(70.0)
            hx, hz = door_x - 0.5, fz_wall - out * 0.03
            cx_, cz_ = hx + 0.5 * math.cos(ang), hz - out * 0.5 * math.sin(ang)
            b.obox("porte", cx_, yd, cz_, 1.0, 2.1, 0.05, -70.0 if out < 0 else 70.0, (0.75, 0.6, 0.5))
        dtop = 2.7 if explorable else 2.25                  # porte à hauteur d'homme quand on peut entrer
        holes.append((door_x - 0.5, yd, door_x + 0.5, dtop))
        a, c = zz(back, 0.1)
        for (u0, u1, v0, v1) in ((door_x - 0.62, door_x - 0.5, 0.15, dtop), (door_x + 0.5, door_x + 0.62, 0.15, dtop),
                                 (door_x - 0.62, door_x + 0.62, dtop, dtop + 0.15)):
            b.box("crepi", u0, v0, a, u1, v1, c, (0.97, 0.96, 0.93))
            holes.append((u0, v0, u1, v1))
        # face du mur côté rue, privée des trous ; ni sous le soubassement (y < 0.6) ni sous la corniche (y > h - 0.26),
        # qui sont en saillie de 3 / 12 cm devant elle. UV identiques à celles de b.box (texture continue).
        from room_builder import TILE, PHOTO_SCALE
        tu = TILE.get(tex, 1.0) * PHOTO_SCALE.get(tex, 1.0)
        parts = [(x0, 0.6, x1, h - 0.26)]
        for hole in holes:
            parts = [q for p in parts for q in rect_minus(p, hole)]
        for (xa, ya, xb, yb) in parts:
            if xb - xa < 1e-4 or yb - ya < 1e-4:
                continue
            if out < 0:
                b.quad(tex, (xa, ya, z0), (xb, ya, z0), (xb, yb, z0), (xa, yb, z0), nrm, wall, uv_off=((xa - x0) / tu, ya / tu))
            else:
                b.quad(tex, (xb, ya, z1), (xa, ya, z1), (xa, yb, z1), (xb, yb, z1), nrm, wall, uv_off=((x1 - xb) / tu, ya / tu))
        a, c = zz(0.0, 0.45)
        b.box("beton", door_x - 0.8, 0, a, door_x + 0.8, 0.15, c, (0.6, 0.58, 0.55))
        lx, ly, lz = door_x + 0.85, dtop - 0.1, fz + out * 0.12
        b.box("metal", lx - 0.05, ly - 0.12, min(fz, lz), lx + 0.05, ly + 0.12, max(fz, lz), (0.15, 0.15, 0.15))
        be.sphere("neon", lx, ly - 0.05, lz + out * 0.03, 0.06, (1.0, 0.8, 0.5), lat=4, lon=8)

    def _build_villas(self, b, be, rng):
        lots_south = [(-66, 14, 10, 7, "crepi"), (-50, 12, 9, 6, "crepi_rose"), (-34, 10, 10, 7, "crepi"),
                      (58, 12, 10, 6, "crepi_rose"), (74, 13, 11, 7, "crepi"), (92, 12, 10, 6, "crepi_rose")]
        for (x, w, d, h, tex) in lots_south:
            z1 = ROAD_Z0 - 6.0
            self._villa(b, be, x, z1 - d, w, d, h, tex, rng, +1)
            self._fence(b, x - 1, x + w + 1, ROAD_Z0 - 2.45, rng)
        lots_north = [(-66, 12, 9, 7, "crepi_rose"), (-50, 11, 9, 6, "crepi"), (-32, 12, 10, 7, "crepi_rose"),
                      (58, 12, 9, 6, "crepi"), (74, 12, 10, 7, "crepi_rose"), (92, 12, 9, 6, "crepi")]
        for (x, w, d, h, tex) in lots_north:
            z0 = ROAD_Z1 + 5.0
            if x == bianchi_house.X0:
                # chez Mme Bianchi (11 rue des Lilas) : explorable, portillon ouvert dans la clôture
                self._villa(b, be, x, z0, w, d, h, tex, rng, -1, explorable=True)
                bianchi_house.build(self, b, be, rng)
                dx = bianchi_house.DOOR_X
                self._fence(b, x - 1, dx - 0.7, ROAD_Z1 + 1.45, rng)
                self._fence(b, dx + 0.7, x + w + 1, ROAD_Z1 + 1.45, rng)
                for px_ in (dx - 0.8, dx + 0.8):
                    b.box("crepi", px_ - 0.12, 0, ROAD_Z1 + 1.33, px_ + 0.12, 1.5, ROAD_Z1 + 1.57, (0.85, 0.8, 0.74), collide=True)
                continue
            self._villa(b, be, x, z0, w, d, h, tex, rng, -1)
            self._fence(b, x - 1, x + w + 1, ROAD_Z1 + 1.45, rng)
        for k in range(10):
            x = rng.uniform(X_MIN + 4, X_MAX - 4)
            if abs(x - 7) < 22 or BLVD_X0 - 4 < x < BLVD_X1 + 4:
                continue
            z = rng.choice([rng.uniform(ROAD_Z1 + 2.5, ROAD_Z1 + 4.5), rng.uniform(ROAD_Z0 - 5.5, ROAD_Z0 - 3.5)])
            b.cypress(x, z, rng.uniform(5, 8), 0.6)

    def _fence(self, b, xa, xb, z, rng):
        b.box("crepi", xa, 0, z - 0.1, xb, 0.55, z + 0.1, (0.82, 0.78, 0.72), collide=True)
        x = xa + 0.1
        while x < xb:
            b.box("metal", x, 0.55, z - 0.02, x + 0.03, 1.35, z + 0.02, (0.18, 0.2, 0.18))
            x += 0.24
        b.box("metal", xa, 1.25, z - 0.02, xb, 1.29, z + 0.02, (0.18, 0.2, 0.18))

    def _street_lamps(self, b, be):
        k = 0
        x = X_MIN + 8
        while x < X_MAX - 4:
            side = -1 if k % 2 == 0 else 1
            z = ROAD_Z0 - 0.4 if side < 0 else ROAD_Z1 + 0.4
            if abs(x - 3.2) > 6 and b.model("street_lamp_01", x, z, 0.0, 0.0, (None, 4.6, None)):
                be.sphere("neon", x, 4.32, z, 0.1, (1.0, 0.82, 0.5))
                self.lights.append(LightSource((x, 4.2, z), (1.0, 0.78, 0.48), 1.6, 13.0, kind="static", name="lampadaire"))
                b.colliders.append((x - 0.15, 0, z - 0.15, x + 0.15, 5.0, z + 0.15))
            elif abs(x - 3.2) > 6:      # le lampadaire devant la maison existe déjà
                b.cyl("metal", x, 0, z, 0.07, 5.2, 6, (0.3, 0.32, 0.35))
                b.box("metal", x - 0.05, 5.1, z, x + 0.05, 5.2, z - side * 0.9, (0.3, 0.32, 0.35))
                be.box("neon", x - 0.2, 5.0, min(z - side * 0.6, z - side * 1.0), x + 0.2, 5.08, max(z - side * 0.6, z - side * 1.0),
                       (1.0, 0.82, 0.5))
                self.lights.append(LightSource((x, 4.8, z - side * 0.8), (1.0, 0.78, 0.48), 1.6, 13.0, kind="static", name="lampadaire"))
                b.colliders.append((x - 0.12, 0, z - 0.12, x + 0.12, 5.0, z + 0.12))
            x += 17.0
            k += 1

    def _street_furniture(self, b):
        """Poubelles le long des trottoirs (modèles 3D uniquement)."""
        z_n, z_s = ROAD_Z1 + 0.35, ROAD_Z0 - 0.35
        for (x, z) in ((-40.0, z_n), (-6.0, z_n), (26.0, z_n), (62.0, z_n), (-33.0, z_s), (8.0, z_s), (36.0, z_s), (75.0, z_s)):
            if b.model("metal_trash_can", x, z, 0.0, 0.0, (None, 0.95, None)):
                b.colliders.append((x - 0.25, 0, z - 0.25, x + 0.25, 1.0, z + 0.25))

    def _bus_stop(self, b, be):
        x, z = -24.0, ROAD_Z0 - 1.9
        b.box("metal", x - 2.0, 0, z - 0.45, x + 2.0, 0.06, z + 0.45, (0.3, 0.32, 0.35))
        b.box("metal", x - 2.0, 2.4, z - 0.6, x + 2.0, 2.5, z + 0.6, (0.3, 0.32, 0.35))
        b.box("vitre", x - 2.0, 0.1, z - 0.6, x + 2.0, 2.4, z - 0.55, (0.6, 0.7, 0.8), collide=True)
        b.box("vitre", x - 2.0, 0.1, z - 0.6, x - 1.95, 2.4, z + 0.5, (0.6, 0.7, 0.8), collide=True)
        b.box("bois_meuble", x - 1.4, 0.42, z - 0.5, x + 1.4, 0.48, z - 0.1, (0.6, 0.45, 0.3))
        be.box("neon", x + 0.6, 0.6, z - 0.54, x + 1.8, 2.2, z - 0.5, (0.95, 0.95, 1.0))
        sign(self.root, "Lignes d'Azur — 33  Mont-Boron", (x, 2.65, z + 0.6), 0.2, 180, (255, 255, 255), (0, 120, 150, 255), px=48)
        sign(self.root, "Prochain bus : 27 min", (x - 0.8, 2.1, z - 0.5), 0.1, 180, (255, 200, 60), (10, 10, 10, 255), px=40)

    def _traffic_light(self, b, be):
        self.tl_pos = [Vec3(BLVD_X0 - 0.6, 0, ROAD_Z0 - 0.6), Vec3(BLVD_X1 + 0.6, 0, ROAD_Z1 + 0.6)]
        self.tl_lamps = []
        for p in self.tl_pos:
            b.cyl("metal", p[0], 0, p[2], 0.06, 3.0, 6, (0.2, 0.22, 0.2))
            b.box("metal", p[0] - 0.15, 2.2, p[2] - 0.12, p[0] + 0.15, 3.1, p[2] + 0.12, (0.1, 0.1, 0.1))
            lamps = {}
            for k, (name, c) in enumerate((("rouge", (1, 0.1, 0.05)), ("orange", (1, 0.6, 0.0)), ("vert", (0.1, 1, 0.3)))):
                lb = MeshBuilder("feu")
                lb.box("neon", p[0] - 0.1, 2.95 - k * 0.28, p[2] - 0.135, p[0] + 0.1, 3.05 - k * 0.28 - 0.05, p[2] + 0.135, c)
                lamps[name] = lb.build(parent=self.root, emit=1.0)
            self.tl_lamps.append(lamps)
            b.colliders.append((p[0] - 0.1, 0, p[2] - 0.1, p[0] + 0.1, 3.0, p[2] + 0.1))

    def _barriers(self, b, be):
        for (x, z, along_x) in ((X_MIN + 1.5, -11.7, False), (X_MAX - 1.5, -11.7, False), ((BLVD_X0 + BLVD_X1) / 2, Z_MIN + 1.5, True),
                                ((BLVD_X0 + BLVD_X1) / 2, Z_MAX - 1.5, True)):
            for k in range(-2, 3):
                cx, cz = (x + k * 1.8, z) if along_x else (x, z + k * 1.8)
                if b.model("concrete_road_barrier", cx, cz, 0.0, 0.0 if along_x else 90.0, (1.7, 0.8, 0.5), free_yaw=True):
                    be.sphere("neon", cx, 0.86, cz, 0.06, (1.0, 0.5, 0.0), lat=3, lon=5)
                    continue
                b.obox("platre", cx, 0.5, cz, 1.6 if along_x else 0.12, 0.3, 0.12 if along_x else 1.6, 0, (0.9, 0.2, 0.15))
                b.obox("metal", cx, 0.0, cz, 0.1, 0.5, 0.1, 0, (0.3, 0.3, 0.3))
                be.sphere("neon", cx, 0.9, cz, 0.06, (1.0, 0.5, 0.0), lat=3, lon=5)
            sign(self.root, "ROUTE BARRÉE — DÉVIATION", (x, 1.4, z), 0.25, 90 if not along_x else 0, (255, 255, 255), (200, 30, 20, 255), px=48)

    # ------------------------------------------------------------------
    # PNJ, circulation, interactions
    # ------------------------------------------------------------------
    def _spawn_npcs(self):
        Z_N = ROAD_Z1 + 0.7         # trottoir nord
        Z_S = ROAD_Z0 - 1.2         # trottoir sud
        L = gd.NPC_LINES if hasattr(gd, "NPC_LINES") else {}
        specs = [
            dict(name="Mme Bianchi", pos=(-20, 0, Z_N), path=[(-40, Z_N), (-16, Z_N)], speed=0.75, pose="walk",
                 jacket=(0.55, 0.35, 0.45), pants=(0.25, 0.22, 0.25), seed=3),
            dict(name="Karim", pos=(30, 0, Z_S), path=[(-60, Z_S), (40, Z_S), (40, Z_S + 0.6), (-60, Z_S + 0.6)], speed=3.2, pose="walk",
                 jacket=(0.85, 0.85, 0.2), pants=(0.15, 0.15, 0.18), seed=5),
            dict(name="Jean-Mi", pos=(60, 0, Z_N), path=[(100, Z_N), (56, Z_N), (56, Z_S), (100, Z_S)], speed=1.2, pose="walk",
                 jacket=(0.2, 0.35, 0.6), seed=6, hat="bonnet"),
            dict(name="Lucie", pos=(-12.62, 0, RESTO[3] + 1.6), pose="sit", yaw=90, jacket=(0.75, 0.25, 0.3), seed=7),
            dict(name="Théo", pos=(-11.38, 0, RESTO[3] + 1.6), pose="sit", yaw=-90, jacket=(0.25, 0.45, 0.3), seed=8),
            dict(name="Nino", pos=(RESTO[0] + 4.0, 0, RESTO[1] + 0.8), pose="idle", yaw=0, jacket=(0.92, 0.92, 0.9), pants=(0.2, 0.2, 0.22), seed=9),
            dict(name="Sandrine", pos=(18.1, 0, -24.9), pose="idle", yaw=0, jacket=(0.15, 0.3, 0.65), seed=10),
            dict(name="Moussa", pos=(SHOP_DOOR_X + 2.2, 0, SHOP[3] - 1.6), pose="idle", yaw=180, jacket=(0.1, 0.1, 0.12), pants=(0.1, 0.1, 0.12), seed=11),
            dict(name="Brigadier Rossi", pos=(self.police_pos[0] - 1.8, 0, self.police_pos[2] - 1.0), pose="idle", yaw=60,
                 jacket=(0.12, 0.15, 0.32), pants=(0.12, 0.14, 0.28), seed=12, hat="police"),
            dict(name="Gardien Martin", pos=(self.police_pos[0] - 1.2, 0, self.police_pos[2] + 0.4), pose="idle", yaw=-120,
                 jacket=(0.12, 0.15, 0.32), pants=(0.12, 0.14, 0.28), seed=13, hat="police"),
            dict(name="Inès", pos=(-24.5, 0, ROAD_Z0 - 2.2), pose="idle", yaw=180, jacket=(0.45, 0.3, 0.6), seed=14),
        ]
        for s in specs:
            lines = L.get(s["name"], ["Bonsoir."])
            talk_cb = self._talk_nino if s["name"] == "Nino" else None
            self.npcs.append(NPC(self, s["name"], s["pos"], lines, s["jacket"], s.get("pants", (0.3, 0.32, 0.4)), s.get("path"),
                                 s.get("speed", 1.3), s.get("pose", "idle"), s.get("yaw", 0.0), NPC_VOICES.get(s["name"], 140), s.get("seed", 0),
                                 s.get("hat"), talk_cb, NPC_LOOKS.get(s["name"])))

    def _talk_nino(self):
        self.counter.open()
        sound.speak("Bonsoir ! Qu'est-ce que je vous sers ?", f0=NPC_VOICES["Nino"], pos=self.counter_pos, speaker="Nino")
        return True

    def _spawn_traffic(self):
        self.traffic = [TrafficCar(self, LANE_E, 1, (0.8, 0.8, 0.82), -40.0, "trafic_0"),
                        TrafficCar(self, LANE_W, -1, (0.15, 0.25, 0.5), 80.0, "trafic_1"),
                        TrafficCar(self, LANE_E, 1, (0.55, 0.1, 0.1), 70.0, "trafic_2")]

    def _shop_interactables(self):
        g = self.game
        ia = g.interactions
        # emplacement : (point d'interaction, centre du présentoir, orientation de la façade)
        slots = {"bazar": [], "epicerie": [], "frais": [], "presse": []}
        for shelf, lst in self.shelf_slots.items():
            for (ax, sz0, sz1) in lst:
                for side in (-1, 1):
                    for k in range(3):
                        zz = sz0 + 1.2 + k * 2.3
                        slots[shelf].append((Vec3(ax + side * 0.85, 1.15, zz), Vec3(ax + side * 0.6, 0.72, zz), 90.0 if side > 0 else 270.0))
        for k in range(8):
            xx = 12.5 + k * 2.4
            slots["frais"].append((Vec3(xx, 1.2, SHOP[1] + 1.7), Vec3(xx, 0.95, SHOP[1] + 1.32), 0.0))
        used = {k: 0 for k in slots}
        self.product_points = []
        pb = MeshBuilder("produits")          # tous les présentoirs dans un seul maillage par texture
        for art in CATALOG:
            lst = slots.get(art.shelf) or slots["epicerie"]
            p, stand, rot = lst[used.get(art.shelf, 0) % len(lst)]
            used[art.shelf] = used.get(art.shelf, 0) + 1
            # présentoir + produits modélisés avec leur emballage (products.py)
            products.build(pb, art.id, stand[0], stand[1], stand[2], rot, floor=(art.shelf == "frais"))
            # étiquette prix sur le rebord avant du présentoir (lisible depuis l'allée)
            fx, fz = math.sin(math.radians(rot)), math.cos(math.radians(rot))
            sign(self.root, eur(art.card_price if art.card_price else art.price),
                 (stand[0] + fx * 0.137, stand[1] - 0.005, stand[2] + fz * 0.137), 0.045, rot + 180.0,
                 (20, 20, 20), (255, 220, 40, 255), px=40)
            ia.add(Interactable(f"produit_{art.id}", p, (lambda a=art: f"Prendre : {a.name} — {eur(a.price)}"
                                                          + (f" (carte : {eur(a.card_price)})" if a.card_price else "")),
                                (lambda it, a=art: self.take(a)), 0, radius=0.3, reach=2.0))
            self.product_points.append((art, p))
        pb.build(parent=self.root, emit=0.15)
        # cagettes de l'étal de primeur devant la vitrine : prises au panier, payées à la caisse automatique
        for i, (art, p) in enumerate(self.primeur_points):
            ia.add(Interactable(f"primeur_{i}", p, (lambda a=art: f"Prendre : {a.name} — {eur(a.price)}"),
                                (lambda it, a=art: self.take(a)), 0, radius=0.24, reach=2.0))
        for i, k in enumerate(self.kiosks):
            ia.add(Interactable(f"caisse_auto_{i}", (k[0], 1.3, k[2] + 0.2), "Utiliser la caisse automatique",
                                lambda it: self.checkout.open(self._on_paid), 0, radius=0.4, reach=2.2))
        ia.add(Interactable("reposer_panier", (SHOP_DOOR_X - 2.6, 1.0, SHOP[3] - 1.2), lambda: "Reposer tous les articles" if self.basket.count else None,
                            lambda it: self._drop_basket(), 0, radius=0.5, reach=2.2))
        ia.add(Interactable("comptoir_nino", self.counter_pos, "Commander au comptoir — Chez Nino", lambda it: self.counter.open(),
                            0, radius=0.6, reach=2.4))
        # boîte aux lettres de la maison : petit détail d'ambiance
        bianchi_house.interactables(self, ia, Interactable)
        ia.add(Interactable("boite_lettres", (8.4, 1.1, -5.9), "Regarder la boîte aux lettres",
                            lambda it: g.say("« R. GARNIER ». Débordante de prospectus... et d'avis de passage QuickEats."), 0,
                            radius=0.3, reach=2.0))
        b = MeshBuilder("bal")
        # boîte aux lettres sur pied : caisson, toit arrondi, fente, porte-étiquette, prospectus qui dépassent
        b.box("metal", 8.37, 0.0, -5.93, 8.43, 0.9, -5.87, (0.2, 0.2, 0.2))
        b.box("metal", 8.18, 0.9, -6.08, 8.62, 1.28, -5.82, (0.62, 0.48, 0.14))
        b.cyl("metal", 8.4, 1.28, -5.95, 0.13, 0.01, 12, (0.55, 0.42, 0.12))
        b.box("metal", 8.25, 1.17, -6.085, 8.55, 1.19, -6.08, (0.05, 0.05, 0.05))
        b.box("papier", 8.28, 1.16, -6.12, 8.5, 1.24, -6.085, (0.9, 0.88, 0.8))
        b.box("papier", 8.32, 1.0, -6.083, 8.48, 1.06, -6.081, (0.95, 0.95, 0.92))
        # jardinières en terre cuite devant les commerces et bancs publics sur le trottoir
        for (px, pz) in ((SHOP_DOOR_X - 2.4, SHOP[3] + 1.4), (SHOP_DOOR_X + 2.4, SHOP[3] + 1.4),
                         (RESTO_DOOR_X - 1.6, RESTO[3] + 2.6), (RESTO_DOOR_X + 1.6, RESTO[3] + 2.6)):
            b.box("crepi", px - 0.45, 0.0, pz - 0.25, px + 0.45, 0.45, pz + 0.25, (0.72, 0.4, 0.26))
            b.box("herbe", px - 0.4, 0.45, pz - 0.2, px + 0.4, 0.5, pz + 0.2, (0.25, 0.32, 0.2))
            b.geraniums(px, 0.48, pz, 0.8, 0.4, seed=int(px * 10))
            b.colliders.append((px - 0.45, 0, pz - 0.25, px + 0.45, 0.6, pz + 0.25))
        for bx in (-14.0, 30.0, 64.0):
            bz = ROAD_Z1 + 1.0
            for dx in (-0.7, 0.7):
                b.box("metal", bx + dx - 0.04, 0.0, bz - 0.2, bx + dx + 0.04, 0.42, bz + 0.2, (0.15, 0.16, 0.15))
            for k in range(3):
                b.box("planches", bx - 0.85, 0.42, bz - 0.22 + k * 0.15, bx + 0.85, 0.46, bz - 0.1 + k * 0.15, (0.55, 0.4, 0.28))
            b.box("planches", bx - 0.85, 0.5, bz + 0.2, bx + 0.85, 0.85, bz + 0.25, (0.55, 0.4, 0.28))
            b.colliders.append((bx - 0.9, 0, bz - 0.25, bx + 0.9, 0.85, bz + 0.27))
        b.build(parent=self.root, emit=0.05)
        # plaques émaillées niçoises : numéro du 17 et nom de la rue (lettres blanches sur fond bleu)
        sign(self.root, "17", (7.95, 2.25, -0.14), 0.16, 0, (255, 255, 255), (20, 60, 140, 255), px=72)
        sign(self.root, "RUE DES LILAS", (1.2, 2.7, -0.14), 0.2, 0, (255, 255, 255), (20, 60, 140, 255), px=60)
        sign(self.root, "BOULEVARD DU MONT-BORON", (BLVD_X0 - 0.15, 2.7, ROAD_Z0 - 2.6), 0.2, 270, (255, 255, 255), (20, 60, 140, 255), px=60)

    def _register_zones(self):
        x0, z0, x1, z1 = SHOP
        rx0, rz0, rx1, rz1 = RESTO
        self.house.extra_zones = [(x0, z0, x1, z1, "magasin"), (rx0, rz0, rx1, rz1, "resto"),
                                  (bianchi_house.X0, bianchi_house.Z0, bianchi_house.X1, bianchi_house.Z1, "villa")]

    # ------------------------------------------------------------------
    # Achats
    # ------------------------------------------------------------------
    def take(self, art):
        if self.basket.count >= 20:
            self.game.say("Mon panier est plein.")
            return
        self.basket.add(art.id)
        sound.play("papier", 0.5, pitch=1.4)
        self.game.ui.toast.show(f"Ajouté au panier : {art.name}", 1.8)
        self._refresh_ui()

    def on_basket_changed(self, aid, removed=False):
        self._refresh_ui()

    def _drop_basket(self):
        self.basket.clear()
        sound.play("papier", 0.5)
        self.game.say("J'ai reposé les articles.")
        self._refresh_ui()

    def _on_paid(self, lines, quote):
        self._refresh_ui()
        sound.play("caisse_ok", 0.7)
        self.game.inv_panel.refresh()
        self.game.state.set("courses_faites")

    def _refresh_ui(self):
        clear_ui = self.ui
        for c in list(clear_ui.children):
            destroy(c)
        if self.basket.count and self.active:
            rect(self.ui, 0.72, 0.42, 0.34, 0.07, rgb(10, 12, 18, 200), z=0.1, radius=0.25)
            rect(self.ui, 0.58, 0.42, 0.04, 0.04, rgb(214, 36, 46), z=0.05, radius=0.3)
            label(self.ui, f"Panier : {self.basket.count} article(s)", 0.61, 0.432, 0.7, color.white, origin=(-0.5, 0), z=0)
            label(self.ui, f"Total : {eur(self.basket.total)} — à payer en caisse", 0.61, 0.405, 0.5, rgb(200, 200, 210),
                  origin=(-0.5, 0), z=0)
            self.ui.enabled = True
        else:
            self.ui.enabled = False

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------
    def begin_outside(self):
        self.active = True
        self.outside_phase = True
        self.root.enabled = True
        self.basket.clear()
        self.theft_warnings = 0
        self._refresh_ui()
        self._start_ambience()

    def _start_ambience(self):
        self._stop_ambience()
        x0, z0, x1, z1 = SHOP
        rx0, rz0, rx1, rz1 = RESTO
        self.amb = {
            "ville": sound.loop("ambiance_ville", 0.55, channel="music", fade_in=2.0),
            "magasin": sound.loop("ambiance_magasin", 0.7, channel="sfx", pos=Vec3((x0 + x1) / 2, 1.5, (z0 + z1) / 2), ref=9.0),
            "resto": sound.loop("ambiance_resto", 0.8, channel="sfx", pos=Vec3((rx0 + rx1) / 2, 1.2, rz1 + 1.5), ref=6.0),
        }

    def _stop_ambience(self):
        for h in getattr(self, "amb", {}).values():
            if h is not None:
                try:
                    h.fade_to(0.0, 1.0, stop=True)
                except Exception:
                    pass
        self.amb = {}

    def deactivate(self):
        self._stop_ambience()
        self.active = False
        self.outside_phase = False
        self.root.enabled = False
        self.ui.enabled = False
        for t in self.traffic:
            self.house.dyn_colliders.pop(t.id, None)
        for l in self.lights:
            l.enabled = False
        if self.checkout.visible:
            self.checkout.close()
        if self.counter.visible:
            self.counter.close()

    def reactivate(self):
        for l in self.lights:
            l.enabled = True
        self.active = True
        self.root.enabled = True
        self._start_ambience()

    def objective(self):
        if self.basket.count:
            return "Passer en caisse (caisses automatiques) ou reposer les articles"
        return "Entrer au 17 rue des Lilas" + ("" if self.game.state.flag("courses_faites") else
                                              "   ·   facultatif : quelques courses au Carrefour City")

    def ui_visible(self):
        return self.checkout.visible or self.counter.visible

    def on_key(self, key):
        if self.checkout.visible:
            return self.checkout.on_key(key)
        if self.counter.visible:
            return self.counter.on_key(key)
        return False

    def update(self, dt):
        if not self.active:
            return
        self.t += dt
        g = self.game
        p = g.player
        pp = p.pos
        # feux tricolores (cycle 14 s vert / 3 s orange / 12 s rouge pour la rue des Lilas)
        self.light_t = (self.light_t + dt) % 29.0
        st = "vert" if self.light_t < 14 else "orange" if self.light_t < 17 else "rouge"
        if st != self.light_state:
            self.light_state = st
            for i, lamps in enumerate(self.tl_lamps):
                for name, ents in lamps.items():
                    for e in ents:
                        e.enabled = (name == st)
        # gyrophares
        ph = int(self.t * 3.0) % 2
        for k, ents in enumerate(self.gyro):
            for e in ents:
                e.enabled = (k == ph)
        self.gyro_lights[0].enabled = ph == 0
        self.gyro_lights[1].enabled = ph == 1
        near_police = (pp - self.police_pos).length() < 14
        if near_police and not self.siren_done:
            self.siren_done = True
            sound.play_at("sirene_courte", self.police_pos + Vec3(0, 1.4, 0), 0.7, ref=8.0)
        # portes automatiques
        dd = Vec3(pp[0] - SHOP_DOOR_X, 0, pp[2] - SHOP[3]).length()
        want = 1.0 if dd < 3.2 else 0.0
        if want > 0.5 and self.door_open < 0.05:
            sound.play_at("porte_auto", Vec3(SHOP_DOOR_X, 1.5, SHOP[3]), 0.6)
        self.door_open += (want - self.door_open) * min(1.0, dt * 4.0)
        for root, s in self.door_panels:
            root.x = SHOP_DOOR_X + s * (0.65 + 1.15 * self.door_open)
        # antivol : sortie du magasin avec des articles non payés
        x0, z0, x1, z1 = SHOP
        in_shop = x0 < pp[0] < x1 and z0 < pp[2] < z1 - 0.3
        on_front = x0 - 1.0 < pp[0] < x1 + 1.0 and z1 - 0.3 < pp[2] < z1 + 5.0     # trottoir devant le magasin
        left_door = self.was_in_shop and not in_shop and pp[2] > z1 - 0.6 and abs(pp[0] - SHOP_DOOR_X) < 2.5
        left_stall = not in_shop and not on_front and self.basket.unpaid
        if self.basket.unpaid and (left_door or left_stall):
            self.theft_warnings += 1
            sound.play_at("antivol", Vec3(SHOP_DOOR_X, 1.2, z1 - 0.9), 0.9, ref=6.0)
            line = ("Monsieur ! Le panier, ça se paie en caisse." if self.theft_warnings < 3 else
                    "Dernier avertissement. Je reprends les articles.")
            sound.speak(line, f0=NPC_VOICES["Moussa"], pos=Vec3(SHOP_DOOR_X + 2.2, 1.6, z1 - 1.6), speaker="Moussa")
            if self.theft_warnings >= 3:
                self.basket.clear()
                self._refresh_ui()
            if left_door:
                p.place((SHOP_DOOR_X, 0.0, z1 - 1.9), 180.0, p.pitch)
                in_shop = True
            else:                                       # ramené devant l'étal de primeur
                p.place((14.0, 0.0, z1 + 2.4), 180.0, p.pitch)
        self.was_in_shop = in_shop
        # PNJ et voitures
        mp = getattr(g, "mp", None)
        replica = g.is_multiplayer and mp is not None and not mp.client.is_host
        if replica:
            snap = getattr(self, "_snap", None)
            if snap is not None:
                for n, v in zip(self.npcs, snap.get("n", ())):
                    n.apply(dt, *v)
                for c, v in zip(self.traffic, snap.get("c", ())):
                    c.x += (v[0] - c.x) * min(1.0, dt * 10.0) if abs(v[0] - c.x) < 20 else (v[0] - c.x)
                    c.speed = v[1]
                    c.root.x = c.x
        else:
            self.all_players = [pp] + ([a.root.position for a in mp.avatars.values()] if g.is_multiplayer and mp else [])
            for n in self.npcs:
                d = (n.pos - pp).length()
                vis = d < 48
                if vis != n.root.enabled:            # bascule seulement au changement (stash/unstash coûteux)
                    n.root.enabled = vis
                if d < 70:
                    n.update(dt, pp)
            for c in self.traffic:
                c.update(dt, pp)
        # vue extérieure : tous les étages de la maison visibles depuis la rue
        outside = p.zone in ("dehors", "magasin", "resto", "villa")
        city = getattr(self, "amb", {}).get("ville")
        if city is not None:
            target = 1.0 if p.zone == "dehors" else 0.35 if outside else 0.12
            if abs(getattr(self, "_city_target", -1) - target) > 0.01:
                self._city_target = target
                city.fade_to(target, 0.8)
        if outside != getattr(self.house, "outside_view", False):
            self.house.outside_view = outside
            self.house.set_level_visibility(p.level)
        # entrée dans la maison
        if self.outside_phase and p.zone in ("rdc",) and p.pos[2] > 0.6:
            self.outside_phase = False
            if g.is_multiplayer and getattr(g, "mp", None) is not None:
                g.mp.client.send_enter_house()
                g.ui.say("En attente des autres joueurs...", 4.0)
            else:
                g.on_enter_house()

    # --- multijoueur : état du quartier partagé --------------------------------------------
    def snapshot(self, dt):
        """Créateur du salon : instantané PNJ / voitures / feux, ~8 fois par seconde (sinon None)."""
        self._snap_t = getattr(self, "_snap_t", 0.0) + dt
        if self._snap_t < 0.125:
            return None
        self._snap_t = 0.0
        return dict(type="hood",
                    n=[[round(n.root.x, 2), round(n.root.z, 2), round(n.root.rotation_y, 1), round(n.speed_now, 2)]
                       for n in self.npcs],
                    c=[[round(c.x, 2), round(c.speed, 2)] for c in self.traffic],
                    l=round(self.light_t, 2))

    def apply_snapshot(self, m):
        """Invités : reçoit l'état du créateur (appliqué en douceur à chaque image dans update)."""
        if isinstance(m.get("n"), list) and isinstance(m.get("c"), list):
            self._snap = m
            if isinstance(m.get("l"), (int, float)):
                self.light_t = float(m["l"])

    def destroy(self):
        self.deactivate()
        for t in self.traffic:
            self.house.dyn_colliders.pop(t.id, None)
        for e in (self.root, self.ui, self.checkout.root, self.counter.root):
            try:
                destroy(e)
            except Exception:
                pass
