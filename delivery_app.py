"""Application « QuickEats » (clone d'UberEats in-game) : adresse, menus, paiement, suivi."""
import math
import re
import unicodedata

from ursina import color

import game_data as gd
import illustrations as ill
from phone_system import (App, SW, SH, BG, CARD, CARD2, LINE, TXT, SUB, DIM, GREEN, RED, ORANGE,
                          txt, set_txt, pic, btn, hit, ptex, px, ellipsize)
from sound_engine import engine as sound
from ui_widgets import rect, clear, rgb, star

DARK = rgb(20, 20, 24)
CAT_FOOD = {"Pizza": "pizza", "Burger": "burger", "Asiatique": "sushi", "Kebab": "kebab", "Desserts": "dessert"}
MEAL_FOOD = {"kebab": "kebab", "pizza": "pizza", "sushi": "sushi", "burger": "burger"}
SAVED_ADDRESSES = [("adresse_bonne", "17 rue des Lilas"), ("adresse_piege", "4 impasse du Calvaire"),
                   ("adresse_erreur", "23 avenue du Grand Champ")]


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


def euros(v):
    return f"{v:.2f} €".replace(".", ",")


class DeliveryApp(App):
    name = "quickeats"
    title = "QuickEats"

    KEY_ROWS = ["1234567890", "azertyuiop", "qsdfghjklm", "wxcvbn,'-"]
    MAX_LEN = 40

    def __init__(self, phone):
        super().__init__(phone)
        self.reset()

    def reset(self):
        self.page = "home"
        self.cat = None
        self.meal = None
        self.address_text = ""
        self.address_key = None
        self.field_text = ""
        self.loading_t = 0.0
        self.error_text = ""
        self._result_seen = False
        self.tip_cb = None
        self.tip_sent = None
        # reprise d'une sauvegarde : l'adresse de la commande déjà passée reste affichée
        key = getattr(self.phone.game.state, "address", None)
        if key in ("bonne", "piege") and key in gd.ADDRESSES:
            self.address_key = key
            self.address_text = gd.ADDRESSES[key]["label"]
        self._clear_refs()

    def _clear_refs(self):
        self.spinner = None
        self.map_dot = None
        self.field_label = None
        self.caret = None
        self.msg_label = None
        self.eta_label = None
        self.status_label = None
        self._eta_sec = None

    @property
    def typing(self):
        return self.page == "address"

    @property
    def toast_y(self):
        return 0.188 if self.page == "address" else -0.35          # adresse : sous le champ, pas sur le clavier

    # ---------------------------------------------------------------
    def on_open(self):
        # écran de résultat (confirmée / impossible) déjà vu : on revient à l'accueil, qui montre l'état réel de la
        # commande (sinon « Commande confirmée ! » restait affiché après l'annulation, « Commande impossible »
        # pendant que le livreur est en chemin)
        if self.page in ("confirmed", "error") and self._result_seen:
            self.page = "home"
        self.render()

    def go_back(self):
        if self.page == "tip":
            return True                       # le pourboire ne se ferme pas
        if self.page in ("home", "loading"):
            return self.page == "loading"
        order = {"address": "home", "menu": "home", "checkout": "menu", "error": "home", "confirmed": "home", "tracking": "home"}
        self.page = order.get(self.page, "home")
        self.render()
        return True

    def _visible(self):
        return self.phone.is_open and self.phone.current == self.name

    def _brand(self, back=False, title=None):
        """En-tête : logo QuickEats (ou titre de page + chevron de retour)."""
        if back:
            self.header(title or "QuickEats", back=self.go_back, accent=ORANGE, size=0.85)
            return
        pic(self.root, ptex("app_icon", "quickeats", 96), -0.162, 0.306, 0.034)
        txt(self.root, "QuickEats", -0.137, 0.306, 0.95, TXT, bold=True)

    def render(self):
        clear(self.root)
        self._clear_refs()
        self.background()
        fn = getattr(self, "_page_" + self.page, None)
        if fn is None:
            self.page = "home"
            fn = self._page_home
        fn()

    def _goto(self, page):
        self.page = page
        self.render()

    # ---------------------------------------------------------------
    def _order_state(self):
        """('suivi'|'prepa'|'annulee'|'livree'|None, titre, détail)"""
        st = self.phone.game.state
        a = self.phone.game.assistance
        if a.tracking_available():
            return "suivi", "Commande en cours", "Arrivée dans " + self._eta_str()
        if a.phase >= 5:
            return "livree", "Commande livrée", "Livraison effectuée."
        if st.flag("order_cancelled"):
            return "annulee", "Commande annulée", "Paiement refusé — fonds insuffisants"
        if st.flag("order_placed"):
            return "prepa", "Commande confirmée", "En préparation au restaurant…"
        return None, "", ""

    def _eta_str(self):
        rem = self.phone.game.assistance.eta_seconds()
        if rem is None:
            return "—"
        m, s = divmod(int(max(0, rem)), 60)
        return f"{m}:{s:02d}"

    def _page_home(self):
        self._brand()
        # adresse de livraison
        y = 0.252
        rect(self.root, 0, y, SW - 0.036, 0.05, CARD, z=0.0, radius=0.3)
        pic(self.root, ptex("glyph", "pin", 48, (255, 122, 26)), -0.162, y, 0.022)
        txt(self.root, "Livrer à", -0.142, y + 0.01, 0.34, SUB)
        if self.address_text:
            txt(self.root, self.address_text, -0.142, y - 0.009, 0.46, TXT, bold=True, max_w=0.28)
        else:
            txt(self.root, "Choisir une adresse", -0.142, y - 0.009, 0.46, ORANGE, bold=True, max_w=0.28)
        pic(self.root, ptex("glyph", "next", 48, (130, 134, 148)), 0.165, y, 0.018)
        hit(self.root, 0, y, SW - 0.036, 0.05, lambda: self._goto("address"))
        txt(self.root, f"Bonsoir, {gd.PLAYER_FIRST} !", -0.178, 0.196, 0.72, TXT, bold=True, max_w=0.35)
        txt(self.root, "Qu'est-ce qui vous ferait plaisir ?", -0.178, 0.165, 0.42, SUB, max_w=0.35)
        rect(self.root, 0, 0.122, SW - 0.036, 0.036, CARD, z=0.0, radius=0.5)
        pic(self.root, ptex("glyph", "search", 48, (130, 134, 148)), -0.162, 0.122, 0.018)
        txt(self.root, "Restaurants, plats…", -0.145, 0.122, 0.42, DIM)
        hit(self.root, 0, 0.122, SW - 0.036, 0.036, lambda: self.phone.toast("Recherche indisponible."))
        # catégories
        for i, cat in enumerate(gd.CATEGORIES):
            x = -0.152 + i * 0.076
            pic(self.root, ptex("round_food", CAT_FOOD.get(cat, "burger"), 128), x, 0.058, 0.058)
            txt(self.root, cat, x, 0.016, 0.33, TXT, (0, 0), max_w=0.072)
            hit(self.root, x, 0.045, 0.072, 0.09, lambda c=cat: self.pick_category(c))
        # bandeau promo
        y = -0.07
        rect(self.root, 0, y, SW - 0.036, 0.075, ORANGE, z=0.0, radius=0.2)
        txt(self.root, "Livraison offerte", -0.165, y + 0.014, 0.56, TXT, bold=True, max_w=0.24)
        txt(self.root, "Ce soir seulement, avant 23 h.", -0.165, y - 0.014, 0.38, rgb(255, 236, 220), max_w=0.24)
        pic(self.root, ptex("round_food", "burger", 128, (255, 150, 70)), 0.13, y, 0.062)
        hit(self.root, 0, y, SW - 0.036, 0.075, lambda: self.pick_category(None))
        btn(self.root, "Voir tous les menus", 0, -0.152, SW - 0.036, 0.044, lambda: self.pick_category(None), "ph_card", 0.48)
        # état de la commande
        kind, title, detail = self._order_state()
        self._home_kind = kind
        if kind:
            y = -0.25
            col = {"suivi": GREEN, "prepa": ORANGE, "annulee": RED, "livree": DIM}[kind]
            rect(self.root, 0, y, SW - 0.036, 0.07, CARD, z=0.0, radius=0.22)
            rect(self.root, -0.176, y, 0.006, 0.044, col, z=-0.005, radius=0.5)
            badge_kind = {"suivi": "clock", "prepa": "clock", "annulee": "cross", "livree": "check"}[kind]
            pic(self.root, ptex("status_badge", badge_kind, 96), -0.142, y, 0.05)
            txt(self.root, title, -0.11, y + 0.012, 0.48, TXT, bold=True, max_w=0.22)
            self.eta_label = txt(self.root, detail, -0.11, y - 0.013, 0.38, col if kind != "livree" else SUB, max_w=0.24)
            if kind == "suivi":
                txt(self.root, "Suivre", 0.15, y, 0.42, GREEN, (0.5, 0), True)
                pic(self.root, ptex("glyph", "next", 48, (52, 199, 89)), 0.166, y, 0.016)
                hit(self.root, 0, y, SW - 0.036, 0.07, lambda: self._goto("tracking"))
                self._eta_sec = None

    def pick_category(self, cat):
        self.cat = cat
        self._goto("menu")

    # ---------------------------------------------------------------
    def _page_address(self):
        self._brand(True, "Adresse de livraison")
        y = 0.24
        rect(self.root, 0, y, SW - 0.036, 0.046, rgb(240, 241, 245), z=0.0, radius=0.3)
        pic(self.root, ptex("glyph", "pin", 48, (255, 122, 26)), -0.162, y, 0.02)
        self.field_label = txt(self.root, self.field_text[-30:], -0.145, y, 0.5, rgb(20, 20, 24), max_w=0.315, z=-0.02)
        self.placeholder = txt(self.root, "Numéro et rue, ville", -0.145, y, 0.46, rgb(150, 150, 158), z=-0.02)
        self.caret = rect(self.root, -0.145, y, 0.0022, 0.024, ORANGE, z=-0.03)
        self.msg_label = txt(self.root, " ", -0.178, 0.203, 0.38, RED, max_w=0.36)
        self._update_field()
        # adresses trouvées (papiers de l'inventaire)
        have = [(k, t) for k, t in SAVED_ADDRESSES if self.phone.game.state.has(k)]
        if have:
            txt(self.root, "Adresses trouvées", -0.178, 0.17, 0.36, ORANGE, bold=True)
            yy = 0.138
            for k, t in have:
                btn(self.root, t, 0, yy, SW - 0.036, 0.034, (lambda t=t: self.fill(t)), "ph_card", 0.42)
                yy -= 0.04
        # clavier AZERTY
        ky = -0.02
        for row in self.KEY_ROWS:
            n = len(row)
            for i, ch in enumerate(row):
                x = (i - (n - 1) / 2) * 0.0372
                btn(self.root, ch, x, ky, 0.034, 0.044, (lambda c=ch: self.type_char(c)), "ph_kbd", 0.5, tap=False)
            ky -= 0.051
        btn(self.root, "espace", -0.035, ky, 0.2, 0.044, lambda: self.type_char(" "), "ph_kbd", 0.42, tap=False)
        btn(self.root, "", 0.115, ky, 0.08, 0.044, self.backspace, "ph_kbd", tap=False)
        pic(self.root, ptex("glyph", "backspace", 64), 0.115, ky, 0.026, z=-0.05)
        btn(self.root, "Valider l'adresse", 0, ky - 0.068, SW - 0.036, 0.05, self.validate, "ph_orange", 0.55, bold=True)

    def fill(self, text):
        self.field_text = text
        self._update_field()

    def type_char(self, c):
        if len(self.field_text) < self.MAX_LEN:
            self.field_text += c
            sound.play("tap", 0.5, channel="voice")
            self._update_field()

    def backspace(self):
        if self.field_text:
            self.field_text = self.field_text[:-1]
            sound.play("tap", 0.4, channel="voice")
            self._update_field()

    def _update_field(self):
        """Saisie : seul le texte du champ change (pas de reconstruction de la page)."""
        if self.page != "address" or self.field_label is None:
            return
        set_txt(self.field_label, self.field_text[-30:])
        empty = not self.field_text
        if self.placeholder.enabled != empty:
            self.placeholder.enabled = empty
        from ui_widgets import text_box
        b = text_box(self.field_label, self.root) if not empty else None
        self.caret.x = (b[2] + 0.003) if b else -0.145

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
        if self.msg_label is not None and self.page == "address":
            set_txt(self.msg_label, text)
        self.phone.toast(text)

    # ---------------------------------------------------------------
    def _page_menu(self):
        self._brand(True, self.cat or "Tous les menus")
        meals = [(k, m) for k, m in gd.MEALS.items() if self.cat is None or m["category"] == self.cat]
        if not meals:
            pic(self.root, ptex("round_food", CAT_FOOD.get(self.cat, "dessert"), 128), 0, 0.09, 0.1)
            txt(self.root, "Aucun restaurant ouvert", 0, 0.0, 0.58, TXT, (0, 0), True)
            txt(self.root, "pour cette catégorie à cette heure-ci.", 0, -0.03, 0.42, SUB, (0, 0))
            btn(self.root, "Voir tous les menus", 0, -0.11, 0.24, 0.044, lambda: self.pick_category(None), "ph_orange", 0.46, bold=True)
            return
        # cartes adaptées au nombre de menus : la liste tient toujours dans l'écran du téléphone
        top, bottom = 0.27, -0.355
        step = min(0.155, (top - bottom) / max(1, len(meals)))
        ch = step - 0.012
        y = top - step / 2
        for k, m in meals:
            rect(self.root, 0, y, SW - 0.036, ch, CARD, z=0.0, radius=0.14)
            im = min(0.095, ch - 0.03)
            pic(self.root, ptex("rounded_food", MEAL_FOOD.get(k, "burger"), 150), -0.182 + 0.016 + im / 2, y, im)
            tx = -0.182 + 0.03 + im
            mw = 0.17 - tx
            txt(self.root, m["name"], tx, y + 0.034 * ch / 0.143, 0.48, TXT, bold=True, max_w=mw + 0.04, max_h=0.022)
            txt(self.root, m["desc"], tx, y + 0.012 * ch / 0.143, 0.37, SUB, max_w=mw + 0.04, max_h=0.018)
            txt(self.root, euros(m["price"]), tx, y - 0.014 * ch / 0.143, 0.46, ORANGE, bold=True, max_w=0.09)
            txt(self.root, "Intensité", tx, y - 0.038 * ch / 0.143, 0.3, DIM)
            for s_ in range(5):
                star(self.root, tx + 0.05 + s_ * 0.0145, y - 0.038 * ch / 0.143, 0.013,
                     color.rgb32(255, 190, 40) if s_ < m["stars"] else rgb(70, 72, 82))
            hit(self.root, 0, y, SW - 0.036, ch, (lambda k=k: self.choose(k)), z=-0.03)
            btn(self.root, "Choisir", 0.137, y - 0.03 * ch / 0.143, 0.068, 0.032, (lambda k=k: self.choose(k)), "ph_orange", 0.4,
                z=-0.05, bold=True)
            y -= step

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
        if self.meal not in gd.MEALS:
            self.page = "home"
            self.render()
            return
        self._brand(True, "Votre commande")
        m = gd.MEALS[self.meal]
        y = 0.21
        rect(self.root, 0, y, SW - 0.036, 0.09, CARD, z=0.0, radius=0.2)
        pic(self.root, ptex("rounded_food", MEAL_FOOD.get(self.meal, "burger"), 150), -0.138, y, 0.07)
        txt(self.root, m["name"], -0.094, y + 0.016, 0.5, TXT, bold=True, max_w=0.19)
        txt(self.root, m["desc"], -0.094, y - 0.01, 0.38, SUB, max_w=0.19)
        txt(self.root, euros(m["price"]), 0.17, y + 0.016, 0.46, TXT, (0.5, 0), True)
        txt(self.root, "x 1", 0.17, y - 0.01, 0.36, SUB, (0.5, 0))
        rows = [("pin", "Livraison", self.address_text or "—"), ("card", "Paiement", gd.BANK_CARD)]
        y = 0.115
        for g, lbl, val in rows:
            rect(self.root, 0, y, SW - 0.036, 0.056, CARD, z=0.0, radius=0.24)
            pic(self.root, ptex("glyph", g, 48, (255, 122, 26)), -0.16, y, 0.022)
            txt(self.root, lbl, -0.138, y + 0.01, 0.34, SUB)
            txt(self.root, val, -0.138, y - 0.01, 0.46, TXT, bold=True, max_w=0.28)
            y -= 0.064
        hit(self.root, 0, 0.051, SW - 0.036, 0.056, lambda: self.phone.toast("Aucun autre moyen de paiement enregistré."))
        y = -0.03
        for lbl, val, strong in (("Sous-total", euros(m["price"]), False), ("Frais de livraison", "Offerts", False),
                                 ("Total", euros(m["price"]), True)):
            txt(self.root, lbl, -0.178, y, 0.5 if strong else 0.42, TXT if strong else SUB, bold=strong)
            txt(self.root, val, 0.178, y, 0.5 if strong else 0.42, TXT if strong else (GREEN if val == "Offerts" else SUB), (0.5, 0), strong)
            y -= 0.032
        rect(self.root, 0, -0.078, SW - 0.036, 0.0016, LINE, z=0.0)
        btn(self.root, f"Commander · {euros(m['price'])}", 0, -0.255, SW - 0.036, 0.056, self.confirm, "ph_green", 0.56, bold=True)
        txt(self.root, "En confirmant, vous acceptez les conditions de livraison.", 0, -0.3, 0.3, DIM, (0, 0), max_w=SW - 0.05)

    def confirm(self):
        game = self.phone.game
        st = game.state
        nb = getattr(game, "neighborhood", None)
        if nb is not None and nb.outside_phase:
            self.phone.toast("Commande possible une fois arrivé à l'adresse (17 rue des Lilas).")
            return
        if game.assistance.tracking_available():
            self.phone.toast("Votre livreur est déjà en chemin.")
            return
        if st.flag("order_placed") and not st.flag("order_cancelled"):
            self.phone.toast("Une commande est déjà en cours.")
            return
        st.order_attempts += 1
        sound.play("paiement", 0.8, channel="voice")
        self.page = "loading"
        self.loading_t = 0.0
        self.render()

    # ---------------------------------------------------------------
    def _page_loading(self):
        self._brand()
        self.spinner = pic(self.root, ptex("spinner_ring", 128), 0, 0.07, 0.1)
        txt(self.root, "Traitement du paiement…", 0, -0.035, 0.6, TXT, (0, 0), True, max_w=SW - 0.05)
        txt(self.root, "Paiement sécurisé · " + gd.BANK_CARD, 0, -0.07, 0.4, SUB, (0, 0))

    def tick(self, dt):
        # le paiement se termine même si le joueur a rangé le téléphone ou changé d'appli
        if self.page == "loading":
            self.loading_t += dt
            if self.loading_t > 3.0:
                self._finish_loading()

    def _finish_loading(self):
        game = self.phone.game
        st = game.state
        first = not st.flag("order_placed")
        if first:
            st.set("order_placed", True)
            self.page = "confirmed"
            if self._visible():
                self.render()
            sound.play("etoile", 0.7, channel="voice")
            game.on_order_confirmed(self.meal, self.address_key)
        else:
            idx = min(st.order_failed, len(gd.ORDER_ERRORS) - 1)
            self.error_text = gd.ORDER_ERRORS[idx]
            st.order_failed += 1
            self.page = "error"
            if self._visible():
                self.render()
            sound.play("erreur", 0.8, channel="voice")
            game.on_order_failed(st.order_failed)

    def _page_confirmed(self):
        self._result_seen = self._visible()
        self._brand()
        pic(self.root, ptex("status_badge", "check", 192), 0, 0.12, 0.15)
        txt(self.root, "Commande confirmée !", 0, 0.015, 0.75, TXT, (0, 0), True, max_w=SW - 0.04)
        txt(self.root, "Votre livreur prépare votre repas…", 0, -0.025, 0.44, SUB, (0, 0), max_w=SW - 0.05)
        btn(self.root, "Retour à l'accueil", 0, -0.2, 0.24, 0.048, lambda: self._goto("home"), "ph_card", 0.46)

    def _page_error(self):
        self._result_seen = self._visible()
        self._brand()
        pic(self.root, ptex("status_badge", "cross", 192), 0, 0.12, 0.15)
        txt(self.root, "Commande impossible", 0, 0.015, 0.72, TXT, (0, 0), True, max_w=SW - 0.04)
        txt(self.root, self.error_text, 0, -0.04, 0.44, rgb(255, 140, 130), (0, 0), wrap=34, max_w=SW - 0.05, max_h=0.07)
        btn(self.root, "Retour à l'accueil", 0, -0.2, 0.24, 0.048, lambda: self._goto("home"), "ph_card", 0.46)

    # ---------------------------------------------------------------
    # Pourboire (le livreur est à la porte)
    # ---------------------------------------------------------------
    def open_tip(self, callback):
        self.tip_cb = callback
        self.tip_sent = None
        self.page = "tip"
        if self._visible():
            self.render()

    def close_tip(self):
        self.tip_cb = None
        if self.page == "tip":
            self.page = "home"
            if self._visible():
                self.render()

    def _tip(self, choice):
        if self.tip_sent is not None or self.tip_cb is None:
            return
        self.tip_sent = choice
        cb = self.tip_cb
        self.render()
        cb(choice)

    def _page_tip(self):
        self._brand(False)
        y = 0.2
        rect(self.root, 0, y, SW - 0.036, 0.12, CARD, z=0.0, radius=0.16)
        rect(self.root, -0.135, y, 0.07, 0.07, rgb(28, 30, 36), z=-0.005, radius=0.5)
        txt(self.root, "?", -0.135, y, 0.8, DIM, (0, 0), True, z=-0.01)
        txt(self.root, "Votre livreur", -0.09, y + 0.022, 0.5, TXT, bold=True)
        txt(self.root, "est à votre porte", -0.09, y - 0.002, 0.42, SUB)
        txt(self.root, "Livreur partenaire · ★★★★★", -0.09, y - 0.028, 0.34, DIM)
        txt(self.root, "Ajouter un pourboire ?", 0, 0.095, 0.62, TXT, (0, 0), True, max_w=SW - 0.05)
        txt(self.root, "100 % du pourboire revient à votre livreur.", 0, 0.065, 0.34, SUB, (0, 0), max_w=SW - 0.05)
        if self.tip_sent is None:
            btn(self.root, "2 €", -0.09, -0.0, 0.16, 0.06, lambda: self._tip("2"), "ph_card", 0.6, bold=True)
            btn(self.root, "5 €", 0.09, -0.0, 0.16, 0.06, lambda: self._tip("5"), "ph_card", 0.6, bold=True)
            # le troisième bouton : on ne l'a jamais vu dans l'appli
            btn(self.root, "Me laisser entrer", 0, -0.085, SW - 0.036, 0.06, lambda: self._tip("entrer"), "ph_red", 0.5, bold=True)
            txt(self.root, "Vous pouvez aussi ne rien choisir.", 0, -0.15, 0.34, DIM, (0, 0), max_w=SW - 0.05)
        else:
            lbl = {"2": "Pourboire de 2 € envoyé.", "5": "Pourboire de 5 € envoyé.", "entrer": "Merci."}[self.tip_sent]
            txt(self.root, lbl, 0, -0.02, 0.55, GREEN if self.tip_sent != "entrer" else RED, (0, 0), True, max_w=SW - 0.05)

    # ---------------------------------------------------------------
    MAP_W, MAP_H, MAP_Y = SW - 0.036, 0.25, 0.125

    def _map_pos(self, fx, fy):
        return (-self.MAP_W / 2 + fx * self.MAP_W, self.MAP_Y + self.MAP_H / 2 - fy * self.MAP_H)

    def _page_tracking(self):
        self._brand(True, "Suivi de commande")
        pic(self.root, ptex("map_card", px(self.MAP_W), px(self.MAP_H), 26), 0, self.MAP_Y, self.MAP_W, self.MAP_H, z=0.0)
        hx, hy = self._map_pos(*ill.MAP_ROUTE[-1])
        pic(self.root, ptex("glyph", "pin", 64, (255, 122, 26)), hx, hy + 0.016, 0.034, z=-0.02)
        txt(self.root, "17 rue des Lilas", hx - 0.01, hy - 0.018, 0.32, TXT, (0.5, 0), True, z=-0.02)
        self.map_halo = rect(self.root, 0, 0, 0.03, 0.03, rgb(52, 199, 89, 80), z=-0.03, radius=0.5)
        self.map_dot = rect(self.root, 0, 0, 0.017, 0.017, rgb(255, 255, 255), z=-0.035, radius=0.5)
        rect(self.map_dot, 0, 0, 0.7, 0.7, GREEN, z=-0.01, radius=0.5)
        self.eta_label = txt(self.root, " ", -0.178, -0.033, 0.8, TXT, bold=True, max_w=0.36)
        self.status_label = txt(self.root, " ", -0.178, -0.066, 0.42, SUB, max_w=0.36)
        self.progress = []
        for i in range(4):
            self.progress.append(rect(self.root, -0.137 + i * 0.0913, -0.1, 0.086, 0.007, CARD2, z=0.0, radius=0.5))
        y = -0.2
        rect(self.root, 0, y, SW - 0.036, 0.08, CARD, z=0.0, radius=0.22)
        rect(self.root, -0.145, y, 0.05, 0.05, rgb(60, 62, 72), z=-0.005, radius=0.5)
        txt(self.root, "?", -0.145, y, 0.6, SUB, (0, 0), True, z=-0.01)
        txt(self.root, "Votre livreur", -0.11, y + 0.012, 0.5, TXT, bold=True)
        txt(self.root, "Livreur partenaire · 5,0 ★", -0.11, y - 0.013, 0.37, SUB)
        btn(self.root, "", 0.15, y, 0.046, 0.046, lambda: self.phone.toast("Votre livreur ne peut pas être joint."), "ph_green")
        pic(self.root, ptex("glyph", "phone", 48), 0.15, y, 0.022, z=-0.05)
        self._prog_n = -1
        self._update_tracking(force=True)

    def _route_point(self, t):
        pts = [self._map_pos(*p) for p in ill.MAP_ROUTE]
        segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        d = max(0.0, min(1.0, t)) * sum(segs)
        for i, L in enumerate(segs):
            if d <= L or i == len(segs) - 1:
                u = 0 if L <= 0 else min(1.0, d / L)
                return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u
            d -= L

    def _update_tracking(self, force=False):
        a = self.phone.game.assistance
        remaining, phase = a.eta_seconds(), a.phase
        total = a.total()
        t = 1.0 - max(0.0, min(1.0, remaining / total)) if remaining is not None else 0.0
        t = 1.0 if phase >= 4 else min(t, 0.86)          # devant la porte : le point ne bouge plus
        x, y = self._route_point(t)
        self.map_dot.position = (x, y, -0.035)
        self.map_halo.position = (x, y, -0.03)
        sec = None if remaining is None else int(max(0, remaining))
        if force or sec != self._eta_sec:
            self._eta_sec = sec
            if phase >= 5:
                set_txt(self.eta_label, "Livrée")
            elif sec is not None:
                m, s = divmod(sec, 60)
                set_txt(self.eta_label, f"Arrivée dans {m}:{s:02d}")
            set_txt(self.status_label, a.status_text)
            n = 4 if phase >= 5 else 3 if phase >= 4 else 2 if t > 0.4 else 1
            if n != self._prog_n:
                self._prog_n = n
                for i, r in enumerate(self.progress):
                    r.color = GREEN if i < n else CARD2

    def update(self, dt):
        if self.page == "loading" and self.spinner is not None:
            self.spinner.rotation_z += dt * 360
        elif self.page == "tracking" and self.map_dot is not None:
            self._update_tracking()
            k = 1 + 0.35 * (0.5 + 0.5 * math.sin(self.phone.game.player.time * 5))
            self.map_halo.scale = (0.03 * k, 0.03 * k)
        elif self.page == "address" and self.caret is not None:
            on = int(self.phone.game.player.time * 2.2) % 2 == 0
            if self.caret.enabled != on:
                self.caret.enabled = on
        elif self.page == "confirmed" and self.phone.game.state.flag("order_cancelled"):
            self._goto("home")                 # annulée pendant que l'écran de confirmation est affiché
        elif self.page == "home":
            if self._order_state()[0] != getattr(self, "_home_kind", None):
                self.render()                  # commande annulée / reprise / livrée pendant que l'écran est affiché
                return
            if self.eta_label is None or not self.phone.game.assistance.tracking_available():
                return
            rem = self.phone.game.assistance.eta_seconds()
            sec = int(max(0, rem or 0))
            if sec != self._eta_sec:
                self._eta_sec = sec
                set_txt(self.eta_label, "Arrivée dans " + self._eta_str())

    def on_key(self, key):
        if self.page != "address":
            return
        if key in ("backspace", "backspace hold"):
            self.backspace()
        elif key == "enter":
            self.validate()

    def text_input(self, ch):
        """Frappe clavier réelle (AZERTY, accents) dans le champ d'adresse."""
        if self.page != "address":
            return
        if ch.isalnum() or ch in " ,'-’":
            self.type_char("'" if ch == "’" else ch)

    def force_close(self):
        """Fermeture automatique (livraison effectuée)."""
        self.page = "home"
