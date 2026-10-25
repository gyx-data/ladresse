"""Application « QuickEats » (clone d'UberEats in-game) : adresse, menus, paiement, suivi."""
import math
import re
import unicodedata

from ursina import color

import game_data as gd
from phone_system import App, SW
from sound_engine import engine as sound
from texture_generator import textures
from ui_widgets import label, rect, button, clear, rgb, star

ORANGE = rgb(255, 112, 8)
DARK = rgb(20, 20, 24)


def normalize(text):
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def validate_address(text):
    """Retourne 'bonne' | 'piege' | 'erreur' | None."""
    n = normalize(text)
    if not n:
        return None
    for key, d in gd.ADDRESSES.items():
        for alias in [d["label"]] + d["aliases"]:
            a = normalize(alias)
            if n == a or (len(n) >= 12 and n.startswith(a)):
                return key
    return None


class DeliveryApp(App):
    name = "quickeats"
    title = "QuickEats"

    KEY_ROWS = ["1234567890", "azertyuiop", "qsdfghjklm", "wxcvbn,'-"]

    def __init__(self, phone):
        super().__init__(phone)
        self.page = "home"
        self.cat = None
        self.meal = None
        self.address_text = ""
        self.address_key = None
        self.field_text = ""
        self.loading_t = 0.0
        self.loading_target = None
        self.error_text = ""
        self.spinner = None
        self.msg = ""
        self.map_dot = None
        self.map_labels = {}

    # ---------------------------------------------------------------
    def on_open(self):
        if self.page in ("loading",):
            self.page = "home"
        self.render()

    def go_back(self):
        if self.page in ("home", "tracking") and self.page == "home":
            return False
        if self.page in ("loading",):
            return True
        order = {"address": "home", "menu": "home", "checkout": "menu", "error": "home", "confirmed": "home", "tracking": "home"}
        self.page = order.get(self.page, "home")
        self.render()
        return True

    def _header(self, back=False):
        rect(self.root, 0, 0.32, SW, 0.06, ORANGE)
        label(self.root, "QuickEats", -0.12 if back else -0.17, 0.32, 1.1, color.white, origin=(-0.5, 0))
        e = rect(self.root, 0.15, 0.32, 0.045, 0.045, color.white, z=-0.02, texture=textures.get("icone_quickeats"))
        e.color = color.white

    def render(self):
        clear(self.root)
        self.spinner = None
        self.map_dot = None
        fn = getattr(self, "_page_" + self.page)
        fn()

    # ---------------------------------------------------------------
    def _page_home(self):
        self._header()
        st = self.phone.game.state
        addr_label = self.address_text or "Entrer une adresse de livraison"
        rect(self.root, 0, 0.25, SW - 0.03, 0.06, rgb(30, 30, 36))
        label(self.root, "Livrer à", -0.18, 0.262, 0.4, rgb(255, 160, 80), origin=(-0.5, 0), z=-0.03)
        label(self.root, addr_label[:36], -0.18, 0.24, 0.58, color.white if self.address_text else color.gray, origin=(-0.5, 0), z=-0.03)
        button(self.root, "", 0, 0.25, SW - 0.03, 0.06, lambda: self._goto("address"), rgb(30, 30, 36, 1), z=-0.04)
        label(self.root, f"Bonsoir, {gd.PLAYER_FIRST} !", -0.18, 0.18, 0.9, color.white, origin=(-0.5, 0))
        label(self.root, "Qu'est-ce qui vous ferait plaisir ?", -0.18, 0.15, 0.55, rgb(200, 200, 205), origin=(-0.5, 0))
        rect(self.root, 0, 0.1, SW - 0.03, 0.04, rgb(236, 236, 240))
        label(self.root, "Rechercher un restaurant ou un plat", -0.17, 0.1, 0.45, rgb(110, 110, 116), origin=(-0.5, 0), z=-0.03)
        button(self.root, "", 0, 0.1, SW - 0.03, 0.04, lambda: self.phone.toast("Recherche indisponible."), rgb(255, 255, 255, 1), z=-0.04)
        label(self.root, "Catégories", -0.18, 0.045, 0.6, color.white, origin=(-0.5, 0))
        for i, cat in enumerate(gd.CATEGORIES):
            x = -0.115 + (i % 3) * 0.115
            y = -0.01 - (i // 3) * 0.075
            button(self.root, cat, x, y, 0.105, 0.06, (lambda c=cat: self.pick_category(c)), rgb(60, 40, 28), rgb(255, 190, 120), size=0.55)
        button(self.root, "Voir tous les menus", 0, -0.18, SW - 0.06, 0.055, lambda: self.pick_category(None), ORANGE, color.white, size=0.7)
        game = self.phone.game
        if game.assistance.tracking_available():
            button(self.root, "Commande en cours — Suivre", 0, -0.26, SW - 0.06, 0.055, lambda: self._goto("tracking"),
                   rgb(40, 150, 70), color.white, size=0.65)
        elif st.flag("order_cancelled"):
            label(self.root, "Aucune commande en cours.", 0, -0.27, 0.45, color.gray)

    def _goto(self, page):
        self.page = page
        self.render()
        sound.play("tap", 0.6, channel="voice")

    def pick_category(self, cat):
        self.cat = cat
        self._goto("menu")

    # ---------------------------------------------------------------
    def _page_address(self):
        self._header(True)
        button(self.root, "‹", -0.17, 0.32, 0.045, 0.04, self.go_back, rgb(200, 90, 20), size=0.8, z=-0.04)
        label(self.root, "Adresse de livraison", -0.18, 0.25, 0.8, color.white, origin=(-0.5, 0))
        rect(self.root, 0, 0.19, SW - 0.03, 0.055, rgb(236, 236, 240))
        txt = self.field_text + ("|" if int(self.phone.game.player.time * 2) % 2 == 0 else "")
        self.field_label = label(self.root, txt[-34:], -0.18, 0.19, 0.6, color.black, origin=(-0.5, 0), z=-0.03)
        # adresses trouvées (papiers de l'inventaire)
        y = 0.125
        saved = [("adresse_bonne", "17 rue des Lilas"), ("adresse_piege", "4 impasse du Calvaire"), ("adresse_erreur", "23 avenue du Grand Champ")]
        have = [(k, t) for k, t in saved if self.phone.game.state.has(k)]
        if have:
            label(self.root, "Adresses trouvées", -0.18, y, 0.45, rgb(255, 160, 80), origin=(-0.5, 0))
            y -= 0.035
            for k, t in have:
                button(self.root, t, 0, y, SW - 0.04, 0.04, (lambda t=t: self.fill(t)), rgb(60, 40, 28), rgb(255, 210, 160), size=0.55)
                y -= 0.045
        # clavier
        ky = -0.04
        for row in self.KEY_ROWS:
            n = len(row)
            for i, ch in enumerate(row):
                x = (i - (n - 1) / 2) * 0.037
                button(self.root, ch, x, ky, 0.034, 0.045, (lambda c=ch: self.type_char(c)), rgb(50, 50, 58), size=0.6)
            ky -= 0.052
        button(self.root, "espace", -0.04, ky, 0.15, 0.045, lambda: self.type_char(" "), rgb(50, 50, 58), size=0.55)
        button(self.root, "×", 0.09, ky, 0.07, 0.045, self.backspace, rgb(100, 50, 50), size=0.6)
        button(self.root, "Valider l'adresse", 0, ky - 0.065, SW - 0.06, 0.055, self.validate, ORANGE, color.white, size=0.7)
        self.msg_label = label(self.root, "", 0, ky - 0.12, 0.5, rgb(255, 110, 110))

    def fill(self, text):
        self.field_text = text
        self.render()

    def type_char(self, c):
        if len(self.field_text) < 40:
            self.field_text += c
            sound.play("tap", 0.5, channel="voice")
            self._update_field()

    def backspace(self):
        self.field_text = self.field_text[:-1]
        self._update_field()

    def _update_field(self):
        if self.page == "address" and hasattr(self, "field_label"):
            self.field_label.text = self.field_text[-34:] + "|"

    def validate(self):
        game = self.phone.game
        key = validate_address(self.field_text)
        if not self.field_text.strip():
            self._error(gd.ORDER_NO_ADDRESS)
        elif key is None:
            self._error(gd.ORDER_UNKNOWN_ADDRESS)
        elif key == "erreur":
            self._error(gd.ORDER_UNSERVED_ADDRESS)
        else:
            self.address_key = key
            self.address_text = gd.ADDRESSES[key]["label"]
            sound.play("etoile", 0.5, channel="voice")
            game.quests.on_event("address_entered", key=key)
            self.page = "home"
            self.render()

    def _error(self, text):
        sound.play("erreur", 0.7, channel="voice")
        if hasattr(self, "msg_label") and self.page == "address":
            self.msg_label.text = text
        self.phone.toast(text)

    # ---------------------------------------------------------------
    def _page_menu(self):
        self._header(True)
        button(self.root, "‹", -0.17, 0.32, 0.045, 0.04, self.go_back, rgb(200, 90, 20), size=0.8, z=-0.04)
        label(self.root, self.cat or "Tous les menus", -0.18, 0.26, 0.85, color.white, origin=(-0.5, 0))
        meals = [(k, m) for k, m in gd.MEALS.items() if self.cat is None or m["category"] == self.cat]
        if not meals:
            label(self.root, "Aucun restaurant disponible\npour cette catégorie.", 0, 0.0, 0.6, color.gray)
            return
        y = 0.16
        for k, m in meals:
            rect(self.root, 0, y - 0.03, SW - 0.03, 0.17, rgb(30, 30, 36))
            rect(self.root, -0.135, y - 0.03, 0.09, 0.09, rgb(*[int(c * 255) for c in m["color"]]), z=-0.02)
            label(self.root, m["name"], -0.075, y + 0.02, 0.7, color.white, origin=(-0.5, 0), z=-0.03)
            label(self.root, m["desc"], -0.075, y - 0.005, 0.5, rgb(200, 200, 205), origin=(-0.5, 0), z=-0.03)
            label(self.root, f"{m['price']:.2f} €".replace(".", ","), -0.075, y - 0.03, 0.65, rgb(255, 170, 90), origin=(-0.5, 0), z=-0.03)
            label(self.root, "Intensité", -0.075, y - 0.058, 0.35, rgb(160, 160, 166), origin=(-0.5, 0), z=-0.03)
            for s in range(5):
                star(self.root, -0.02 + s * 0.017, y - 0.058, 0.015, color.rgb32(255, 190, 40) if s < m["stars"] else rgb(70, 70, 76))
            button(self.root, "Choisir", 0.125, y - 0.03, 0.07, 0.04, (lambda k=k: self.choose(k)), ORANGE, color.white, size=0.5, z=-0.04)
            y -= 0.19

    def choose(self, key):
        game = self.phone.game
        if not self.address_key:
            self._error(gd.ORDER_NO_ADDRESS)
            return
        self.meal = key
        game.quests.on_event("meal_chosen", meal=key)
        self._goto("checkout")

    # ---------------------------------------------------------------
    def _page_checkout(self):
        self._header(True)
        button(self.root, "‹", -0.17, 0.32, 0.045, 0.04, self.go_back, rgb(200, 90, 20), size=0.8, z=-0.04)
        m = gd.MEALS[self.meal]
        label(self.root, "Paiement", -0.18, 0.25, 0.85, color.white, origin=(-0.5, 0))
        rect(self.root, 0, 0.12, SW - 0.03, 0.17, rgb(30, 30, 36))
        label(self.root, m["name"], -0.18, 0.17, 0.75, color.white, origin=(-0.5, 0), z=-0.03)
        label(self.root, m["desc"], -0.18, 0.14, 0.5, rgb(200, 200, 205), origin=(-0.5, 0), z=-0.03)
        label(self.root, "Livraison : " + self.address_text, -0.18, 0.105, 0.45, rgb(200, 200, 205), origin=(-0.5, 0), z=-0.03)
        label(self.root, f"Total  {m['price']:.2f} €".replace(".", ","), -0.18, 0.065, 0.8, rgb(255, 170, 90), origin=(-0.5, 0), z=-0.03)
        label(self.root, "Moyen de paiement", -0.18, -0.01, 0.5, rgb(160, 160, 166), origin=(-0.5, 0))
        rect(self.root, 0, -0.06, SW - 0.03, 0.06, rgb(30, 50, 100))
        label(self.root, "Carte Visa  ••••  4721", -0.17, -0.06, 0.65, color.white, origin=(-0.5, 0), z=-0.03)
        price = f"{m['price']:.2f}€".replace(".", ",")
        button(self.root, f"Payer {price} — Carte Visa •••• 4721", 0, -0.17, SW - 0.04, 0.06, None, rgb(40, 40, 46), rgb(190, 190, 195), size=0.45)
        button(self.root, "CONFIRMER", 0, -0.25, SW - 0.04, 0.075, self.confirm, rgb(40, 160, 70), color.white, size=0.95)

    def confirm(self):
        game = self.phone.game
        st = game.state
        st.order_attempts += 1
        sound.play("paiement", 0.8, channel="voice")
        self.page = "loading"
        self.loading_t = 0.0
        self.render()

    # ---------------------------------------------------------------
    def _page_loading(self):
        self._header()
        self.spinner = rect(self.root, 0, 0.05, 0.06, 0.06, ORANGE, z=-0.02)
        label(self.root, "Traitement du paiement...", 0, -0.05, 0.7, color.white)

    def _finish_loading(self):
        game = self.phone.game
        st = game.state
        first = (st.order_attempts == 1 and not st.flag("order_placed"))
        if first:
            st.set("order_placed", True)
            self.page = "confirmed"
            self.render()
            sound.play("etoile", 0.7, channel="voice")
            game.on_order_confirmed(self.meal, self.address_key)
        else:
            idx = min(st.order_failed, len(gd.ORDER_ERRORS) - 1)
            self.error_text = gd.ORDER_ERRORS[idx]
            st.order_failed += 1
            self.page = "error"
            self.render()
            sound.play("erreur", 0.8, channel="voice")
            game.on_order_failed(st.order_failed)

    def _page_confirmed(self):
        self._header()
        rect(self.root, 0, 0.1, 0.12, 0.12, rgb(40, 170, 80), z=-0.02)
        label(self.root, "OK", 0, 0.1, 1.5, color.white, z=-0.04)
        label(self.root, gd.ORDER_CONFIRMED, 0, -0.04, 0.75, color.white, wrap=30)
        button(self.root, "Retour", 0, -0.2, 0.2, 0.06, lambda: self._goto("home"), rgb(60, 60, 66), size=0.7)

    def _page_error(self):
        self._header()
        rect(self.root, 0, 0.1, 0.12, 0.12, rgb(200, 50, 50), z=-0.02)
        label(self.root, "X", 0, 0.1, 1.6, color.white, z=-0.04)
        label(self.root, self.error_text, 0, -0.05, 0.7, rgb(255, 130, 130), wrap=30)
        button(self.root, "Retour", 0, -0.2, 0.2, 0.06, lambda: self._goto("home"), rgb(60, 60, 66), size=0.7)

    # ---------------------------------------------------------------
    def _page_tracking(self):
        self._header(True)
        button(self.root, "‹", -0.17, 0.32, 0.045, 0.04, self.go_back, rgb(200, 90, 20), size=0.8, z=-0.04)
        label(self.root, "Suivi de commande", -0.18, 0.26, 0.85, color.white, origin=(-0.5, 0))
        rect(self.root, 0, 0.02, SW - 0.03, 0.4, rgb(34, 38, 44))
        # routes
        rect(self.root, -0.02, 0.02, 0.012, 0.4, rgb(70, 74, 82), z=-0.01)
        rect(self.root, 0.0, -0.04, SW - 0.03, 0.012, rgb(70, 74, 82), z=-0.01)
        rect(self.root, 0.1, 0.02, 0.01, 0.4, rgb(58, 62, 70), z=-0.01)
        rect(self.root, 0.0, 0.12, SW - 0.03, 0.01, rgb(58, 62, 70), z=-0.01)
        rect(self.root, 0.0, -0.04, 0.03, 0.03, rgb(255, 112, 8), z=-0.03)         # la maison
        label(self.root, "17 rue des Lilas", 0.0, -0.075, 0.38, color.white, z=-0.04)
        self.map_dot = rect(self.root, -0.16, 0.18, 0.025, 0.025, rgb(60, 220, 120), z=-0.04)
        self.map_dot.rotation_z = 45
        self.eta_label = label(self.root, "", 0, -0.22, 0.9, color.white)
        self.status_label = label(self.root, "", 0, -0.27, 0.55, rgb(200, 200, 205), wrap=34)
        self._update_tracking()

    def _update_tracking(self):
        a = self.phone.game.assistance
        remaining, phase = a.eta_seconds(), a.phase
        total = a.total()
        t = 1.0 - max(0.0, min(1.0, remaining / total)) if remaining is not None else 0.0
        if phase >= 4:
            # le livreur ne bouge plus : devant la porte
            x, y = 0.0, -0.1
        else:
            t = min(t, 0.82)
            # trajet en deux segments
            if t < 0.5:
                u = t / 0.5
                x, y = -0.16 + 0.14 * u, 0.18 - 0.06 * u
            else:
                u = (t - 0.5) / 0.32
                x, y = -0.02 + 0.02 * u, 0.12 + (-0.1 - 0.12) * u
        self.map_dot.position = (x, y, -0.04)
        if remaining is not None:
            m, s = divmod(int(max(0, remaining)), 60)
            self.eta_label.text = f"Arrivée dans {m}:{s:02d}"
        self.status_label.text = a.status_text

    def update(self, dt):
        if self.page == "loading":
            self.loading_t += dt
            if self.spinner is not None:
                self.spinner.rotation_z += dt * 300
            if self.loading_t > 3.0:
                self._finish_loading()
        elif self.page == "tracking" and self.map_dot is not None:
            self._update_tracking()
            self.map_dot.scale = 0.025 * (1 + 0.15 * math.sin(self.phone.game.player.time * 6))
        elif self.page == "address" and hasattr(self, "field_label"):
            self._update_field()

    def on_key(self, key):
        if self.page != "address":
            return
        if key == "backspace":
            self.backspace()
        elif key == "space":
            self.type_char(" ")
        elif key == "enter":
            self.validate()
        elif len(key) == 1 and (key.isalnum() or key in ",'-"):
            self.type_char(key)

    def force_close(self):
        """Fermeture automatique (livraison effectuée)."""
        self.page = "home"
