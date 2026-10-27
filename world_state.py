"""État global de la partie (drapeaux, inventaire, choix, statistiques).

Un seul objet `WorldState` est partagé par tous les systèmes (quêtes, assistance,
sauvegarde, fins...). Il est entièrement sérialisable en JSON.
"""
import game_data as gd

# Actes : 0 intro, 1 exploration, 2 commande & annulation, 3 attente du livreur,
# 4 survie, 5 sous-sol, 6 fin
ACT_NAMES = {0: "Introduction", 1: "Exploration", 2: "Annulation", 3: "Attente du livreur",
             4: "Survie", 5: "Sous-sol", 6: "Fin"}


class WorldState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.act = 0
        self.flags = {}
        self.docs = set()
        self.items = {}
        self.opened = set()            # objets déjà fouillés / ouverts
        self.rooms_visited = set()
        self.meal = None
        self.address = None            # 'bonne' | 'piege' | 'erreur'
        self.entity_type = None
        self.order_attempts = 0
        self.order_failed = 0
        self.pair_choice = {}          # id -> 'A' | 'B'
        self.pair_good = {}            # id -> bool
        self.messages = []             # (contact, texte, heure)
        self.stats = dict(play_time=0.0, photos=0, photos_reveal=0, deaths=0, choices=0)
        self.photo_log = []
        self.phone_used = False
        self.freezer_opened = False
        self.clock = 21 * 60 + 40      # minutes depuis minuit (heure in-game)
        self.player_pos = None
        self.player_yaw = 0.0
        self.player_battery_phone = 100.0
        self.player_battery_light = 100.0
        self.player_health = 100.0
        self.ending = None
        self.first_death = True
        self.entity_state = None

    # --- drapeaux ----------------------------------------------------------
    def flag(self, name, default=False):
        return self.flags.get(name, default)

    def set(self, name, value=True):
        self.flags[name] = value

    # --- inventaire --------------------------------------------------------
    def add_item(self, item, n=1):
        self.items[item] = self.items.get(item, 0) + n

    def has(self, item, n=1):
        return self.items.get(item, 0) >= n

    def remove_item(self, item, n=1):
        if self.has(item, n):
            self.items[item] -= n
            if self.items[item] <= 0:
                del self.items[item]
            return True
        return False

    # --- documents ---------------------------------------------------------
    def add_doc(self, doc_id):
        new = doc_id not in self.docs
        self.docs.add(doc_id)
        return new

    @property
    def docs_required_found(self):
        return sum(1 for d in gd.REQUIRED_DOCS if d in self.docs)

    @property
    def all_docs(self):
        return all(d in self.docs for d in gd.REQUIRED_DOCS)

    # --- choix de l'assistance ---------------------------------------------
    def record_choice(self, pair_id, choice, truth):
        self.pair_choice[pair_id] = choice
        self.pair_good[pair_id] = (choice == truth)
        self.stats["choices"] += 1

    @property
    def bad_choices(self):
        return sum(1 for v in self.pair_good.values() if not v)

    @property
    def good_choices(self):
        return sum(1 for v in self.pair_good.values() if v)

    # --- horloge in-game ---------------------------------------------------
    def clock_string(self):
        m = int(self.clock) % (24 * 60)
        return f"{m // 60:02d}:{m % 60:02d}"

    # --- sérialisation -----------------------------------------------------
    def to_dict(self):
        return dict(
            act=self.act, flags=self.flags, docs=sorted(self.docs), items=self.items,
            opened=sorted(self.opened), rooms_visited=sorted(self.rooms_visited),
            meal=self.meal, address=self.address, entity_type=self.entity_type,
            order_attempts=self.order_attempts, order_failed=self.order_failed,
            pair_choice={str(k): v for k, v in self.pair_choice.items()},
            pair_good={str(k): v for k, v in self.pair_good.items()},
            messages=self.messages, stats=self.stats, phone_used=self.phone_used,
            freezer_opened=self.freezer_opened, clock=self.clock,
            player_pos=self.player_pos, player_yaw=self.player_yaw,
            player_battery_phone=self.player_battery_phone,
            player_battery_light=self.player_battery_light,
            player_health=self.player_health, first_death=self.first_death,
            entity_state=self.entity_state,
        )

    def from_dict(self, d):
        self.reset()
        self.act = d.get("act", 1)
        self.flags = d.get("flags", {})
        self.docs = set(d.get("docs", []))
        self.items = d.get("items", {})
        self.opened = set(d.get("opened", []))
        self.rooms_visited = set(d.get("rooms_visited", []))
        self.meal = d.get("meal")
        self.address = d.get("address")
        self.entity_type = d.get("entity_type")
        self.order_attempts = d.get("order_attempts", 0)
        self.order_failed = d.get("order_failed", 0)
        self.pair_choice = {int(k): v for k, v in d.get("pair_choice", {}).items()}
        self.pair_good = {int(k): v for k, v in d.get("pair_good", {}).items()}
        self.messages = [tuple(m) for m in d.get("messages", [])]
        self.stats.update(d.get("stats", {}))
        self.phone_used = d.get("phone_used", False)
        self.freezer_opened = d.get("freezer_opened", False)
        self.clock = d.get("clock", self.clock)
        self.player_pos = d.get("player_pos")
        self.player_yaw = d.get("player_yaw", 0.0)
        self.player_battery_phone = d.get("player_battery_phone", 100.0)
        self.player_battery_light = d.get("player_battery_light", 100.0)
        self.player_health = d.get("player_health", 100.0)
        self.first_death = d.get("first_death", True)
        self.entity_state = d.get("entity_state")
