"""Supérette du quartier : catalogue, panier, caisse automatique avec carte fidélité, ticket de caisse,
et comptoir du restaurant niçois.

Le paiement débite le compte BNR (visible ensuite dans l'application bancaire du téléphone).
"""
import random

from ursina import Entity, camera, color, invoke
from ursina.prefabs.input_field import InputField

import game_data as gd
from fidelite import Loyalty, GARNIER_CARD, valid_format, POINTS_PER_VOUCHER
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb, panel

SHOP_NAME = "Carrefour City"
SHOP_FULL = "CARREFOUR CITY — NICE MONT-BORON"
RESTO_NAME = "Chez Nino"
SHOP_BLUE = rgb(18, 72, 160)
SHOP_RED = rgb(214, 36, 46)


def eur(v):
    return f"{v:,.2f} €".replace(",", " ").replace(".", ",")


class Article:
    def __init__(self, aid, name, short, price, card_price=None, item=None, item_qty=1, col=(0.8, 0.8, 0.8), shelf="",
                 desc=""):
        self.id = aid
        self.name = name
        self.short = short
        self.price = price
        self.card_price = card_price
        self.item = item            # objet d'inventaire obtenu (None = simple course)
        self.item_qty = item_qty
        self.col = col
        self.shelf = shelf
        self.desc = desc


CATALOG = [
    Article("piles", "Piles alcalines AA x4", "PILES AA X4", 5.49, 4.49, "pile", 2, (0.95, 0.78, 0.1), "bazar",
            "Recharge la lampe ou le téléphone (2 utilisations)."),
    Article("batterie", "Batterie externe 5000 mAh", "BATT EXT 5000", 14.99, 12.99, "batterie_externe", 1, (0.2, 0.2, 0.24), "bazar",
            "Recharge le téléphone à 80 %."),
    Article("bougies", "Bougies chauffe-plat x10", "BOUGIES X10", 2.99, None, "bougie", 3, (0.95, 0.95, 0.92), "bazar",
            "Pose une petite lumière pendant 2 minutes."),
    Article("pansements", "Pansements assortis x20", "PANSEMENTS", 3.49, None, "pansement", 2, (0.9, 0.7, 0.6), "bazar",
            "Rend 35 points de santé."),
    Article("sel", "Gros sel de mer 1 kg", "GROS SEL 1KG", 1.15, 0.95, "sel", 1, (0.85, 0.88, 0.95), "epicerie",
            "Du gros sel. On ne sait jamais."),
    Article("barre", "Barre chocolat-caramel", "BARRE CHOCO", 1.20, None, "barre", 1, (0.45, 0.22, 0.12), "epicerie",
            "Réconfortant : -25 de stress."),
    Article("eau", "Eau de source 50 cl", "EAU SOURCE 50CL", 0.89, 0.69, "eau", 1, (0.55, 0.75, 0.95), "frais",
            "Récupère toute l'endurance."),
    Article("energisant", "Boisson énergisante 25 cl", "BOISSON ENERG", 1.79, 1.49, "energisant", 1, (0.2, 0.6, 0.9), "frais",
            "Endurance quasi illimitée pendant 60 s."),
    Article("journal", "Nice-Matin du jour", "NICE MATIN", 1.60, None, "journal", 1, (0.92, 0.92, 0.9), "presse",
            "Les nouvelles du quartier."),
    Article("pates", "Pâtes coquillettes 500 g", "COQUILLETTES", 0.95, None, None, 1, (0.95, 0.85, 0.4), "epicerie"),
    Article("lait", "Lait demi-écrémé 1 L", "LAIT DEMI-ECR", 1.09, None, None, 1, (0.95, 0.95, 0.98), "frais"),
    Article("baguette", "Baguette tradition", "BAGUETTE TRAD", 1.25, None, None, 1, (0.85, 0.65, 0.35), "epicerie"),
    Article("cafe", "Café moulu 250 g", "CAFE MOULU", 3.79, 3.29, None, 1, (0.35, 0.22, 0.15), "epicerie"),
    Article("pizza_surg", "Pizza surgelée 4 fromages", "PIZZA 4 FROM", 3.99, None, None, 1, (0.85, 0.3, 0.2), "frais"),
    Article("socca_pack", "Socca prête à cuire", "SOCCA", 2.90, 2.49, None, 1, (0.9, 0.75, 0.4), "frais"),
    Article("huile", "Huile d'olive de Nice AOP 50 cl", "HUILE OLIVE AOP", 12.90, 10.90, None, 1, (0.55, 0.6, 0.2), "epicerie"),
]
CATALOG_BY_ID = {a.id: a for a in CATALOG}


def primeur_article(item):
    """Article du panier pour une cagette de l'étal de primeur (fresh_aisle.PRODUCE) : même prix que l'ardoise.
    Enregistré à part du CATALOG (pas de présentoir en rayon) mais payé à la caisse comme le reste."""
    model, col, _size, nom, prix = item
    aid = "primeur_" + model
    if aid not in CATALOG_BY_ID:
        piece = "pièce" in prix
        price = float(prix.split("€")[0].strip().replace(",", "."))
        name = f"{nom} — {'à la pièce' if piece else '1 kg'}"
        short = (nom.upper() + (" PCE" if piece else " 1KG"))[:20]
        CATALOG_BY_ID[aid] = Article(aid, name, short, price, None, aid, 1, col, "primeur")
        # objet d'inventaire du même nom (se mange depuis le panneau Tab, voir GameManager.use_item)
        import inventory
        inventory.ITEM_DEFS[aid] = (nom, ("À la pièce" if piece else "1 kg") + ", de l'étal du Carrefour. Ça se mange.",
                                    col, True)
    return CATALOG_BY_ID[aid]


def _register_primeur():
    import fresh_aisle
    for item in fresh_aisle.PRODUCE:
        primeur_article(item)


_register_primeur()          # dès l'import : les fruits d'une sauvegarde s'affichent dans l'inventaire

# annonces vocales de la caisse automatique
KIOSK_LINES = {
    "bienvenue": "Bonjour et bienvenue. Veuillez scanner votre premier article.",
    "vide": "Votre panier est vide.",
    "carte": "Carte fidélité reconnue.",
    "inconnu": "Article inattendu dans la zone d'ensachage. Veuillez patienter, un conseiller va venir vous aider.",
    "payer": "Veuillez présenter votre carte bancaire.",
    "merci": "Paiement accepté. Merci de votre visite, et à bientôt.",
    "refus": "Paiement refusé.",
    "garnier": "Bonjour, monsieur Garnier. Cela faisait longtemps.",
    "nouvelle_carte": "Votre nouvelle carte fidélité est créée.",
}


def kiosk_say(key):
    try:
        sound.speak(KIOSK_LINES[key], f0=215, speed=1.0, volume=0.75, channel="voice", subtitle=False, speaker="Caisse")
    except Exception:
        pass


RESTO_MENU = [
    ("socca", "Socca (part)", 3.50, 15, 12, "Galette de pois chiche brûlante, poivrée."),
    ("pan_bagnat", "Pan bagnat", 6.90, 30, 15, "Thon, œuf, radis, olives, huile d'olive."),
    ("pissaladiere", "Pissaladière", 4.20, 20, 12, "Oignons confits, anchois, olives noires."),
    ("pizza", "Part de pizza Margherita", 3.80, 20, 10, "Au feu de bois."),
    ("cafe", "Café serré", 1.80, 0, 20, "Petit noir au comptoir."),
]


class Basket:
    def __init__(self):
        self.lines = {}             # id -> qty
        self.scanned = {}           # id -> qty passés en caisse

    def add(self, aid, n=1):
        self.lines[aid] = min(9, self.lines.get(aid, 0) + n)

    def remove(self, aid, n=1):
        q = self.lines.get(aid, 0) - n
        if q <= 0:
            self.lines.pop(aid, None)
        else:
            self.lines[aid] = q
        if self.scanned.get(aid, 0) > self.lines.get(aid, 0):
            self.scanned[aid] = self.lines.get(aid, 0)

    def clear(self):
        self.lines.clear()
        self.scanned.clear()

    @property
    def count(self):
        return sum(self.lines.values())

    @property
    def total(self):
        return sum(CATALOG_BY_ID[a].price * q for a, q in self.lines.items())

    @property
    def unpaid(self):
        return self.count > 0

    def as_lines(self, only_scanned=False):
        src = self.scanned if only_scanned else self.lines
        return [(CATALOG_BY_ID[a], q) for a, q in src.items() if q > 0]


def bank_balance(state):
    return round(gd.BANK_BALANCE + sum(p[1] for p in state.flags.get("purchases", [])), 2)


def bank_debit(state, label_, amount):
    hh = int(state.clock // 60) % 24
    mm = int(state.clock % 60)
    state.flags.setdefault("purchases", []).append([label_, -round(amount, 2), f"13/10 {hh:02d}:{mm:02d}"])


class SelfCheckout:
    """Borne de caisse automatique (interface plein écran stylisée)."""

    W, H = 1.36, 0.82

    def __init__(self, game, basket, loyalty):
        self.game = game
        self.basket = basket
        self.loyalty = loyalty
        self.root = Entity(parent=camera.ui, z=-18, enabled=False)
        self.visible = False
        self.card = None            # numéro de carte scannée pour cette transaction
        self.page = "scan"
        self.field = None
        self.msg = ""
        self.unknown_item_done = False
        self.on_paid = None

    # ------------------------------------------------------------------
    def open(self, on_paid=None):
        self.on_paid = on_paid
        self.visible = True
        self.root.enabled = True
        self.page = "scan" if self.basket.count else "empty"
        self.card = None
        self.msg = ""
        self.game.set_mouse(free=True)
        sound.play("caisse_voix_bip", 0.6)
        kiosk_say("bienvenue" if self.basket.count else "vide")
        self.render()

    def close(self):
        self.visible = False
        self.root.enabled = False
        if self.field is not None:
            self.field = None
        clear(self.root)
        self.game.set_mouse(free=False)

    def on_key(self, key):
        if key == "escape":
            self.close()
            return True
        if self.page == "card_entry" and key == "enter":
            self._validate_card()
            return True
        return self.page == "card_entry"

    # ------------------------------------------------------------------
    def _frame(self, title):
        r = self.root
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 150), z=2)
        panel(r, 0, 0, self.W + 0.04, self.H + 0.04, "dark", z=1.5)
        rect(r, 0, 0, self.W, self.H, rgb(244, 246, 250), z=1.2, radius=0.03)
        rect(r, 0, self.H / 2 - 0.045, self.W, 0.09, SHOP_BLUE, z=1.1, radius=0.03)
        rect(r, 0, self.H / 2 - 0.085, self.W, 0.012, SHOP_RED, z=1.0)
        label(r, SHOP_NAME, -self.W / 2 + 0.04, self.H / 2 - 0.045, 1.5, color.white, origin=(-0.5, 0), z=0.9)
        label(r, title, self.W / 2 - 0.04, self.H / 2 - 0.045, 0.85, rgb(210, 225, 255), origin=(0.5, 0), z=0.9)
        button(r, "Fermer  [Échap]", self.W / 2 - 0.12, -self.H / 2 + 0.045, 0.2, 0.05, self.close, style="ghost",
               text_col=rgb(90, 90, 100), size=0.6, z=0.5)

    def render(self):
        clear(self.root)
        getattr(self, "_page_" + self.page)()

    def _page_empty(self):
        self._frame("Caisse automatique n°2")
        label(self.root, "Votre panier est vide.", 0, 0.08, 1.6, rgb(40, 40, 50), z=0.5)
        label(self.root, "Prenez des articles dans les rayons (touche E), puis revenez scanner.", 0, 0.0, 0.8,
              rgb(90, 90, 100), z=0.5)
        self._card_box(0, -0.16)

    def _page_scan(self):
        self._frame("Scannez vos articles")
        r = self.root
        lines = self.basket.as_lines()
        # liste à gauche
        x0, y = -self.W / 2 + 0.05, self.H / 2 - 0.14
        label(r, "ARTICLE", x0, y, 0.6, rgb(120, 120, 130), origin=(-0.5, 0), z=0.5)
        label(r, "QTÉ", 0.04, y, 0.6, rgb(120, 120, 130), z=0.5)
        label(r, "PRIX", 0.16, y, 0.6, rgb(120, 120, 130), origin=(0.5, 0), z=0.5)
        y -= 0.05
        for art, q in lines[:9]:
            sc = self.basket.scanned.get(art.id, 0)
            done = sc >= q
            rect(r, -0.12, y, 0.6, 0.046, rgb(232, 236, 244) if not done else rgb(222, 244, 228), z=0.8, radius=0.2)
            rect(r, x0 + 0.012, y, 0.018, 0.03, rgb(int(art.col[0] * 255), int(art.col[1] * 255), int(art.col[2] * 255)), z=0.6,
                 radius=0.3)
            label(r, art.name, x0 + 0.035, y, 0.7, rgb(30, 30, 40), origin=(-0.5, 0), z=0.5)
            label(r, f"{sc}/{q}", 0.04, y, 0.7, rgb(30, 120, 60) if done else rgb(160, 80, 30), z=0.5)
            price = art.price * q
            label(r, eur(price), 0.16, y, 0.7, rgb(30, 30, 40), origin=(0.5, 0), z=0.5)
            if art.card_price is not None:
                label(r, "PRIX CARTE", -0.03, y, 0.45, SHOP_RED, origin=(0.5, 0), z=0.5)
            button(r, "–", 0.215, y, 0.036, 0.036, (lambda a=art.id: self._remove(a)), style="danger", size=0.8, z=0.4)
            y -= 0.052
        if len(lines) > 9:
            label(r, f"... et {len(lines) - 9} autre(s) article(s)", x0, y, 0.6, rgb(100, 100, 110), origin=(-0.5, 0), z=0.5)
        # colonne droite : actions + totaux
        cx = 0.47
        all_scanned = all(self.basket.scanned.get(a.id, 0) >= q for a, q in lines)
        button(r, "Scanner un article", cx, 0.2, 0.34, 0.07, self._scan_one, style="blue", size=0.85, z=0.4)
        button(r, "Tout scanner", cx, 0.12, 0.34, 0.06, self._scan_all, style="dark", size=0.8, z=0.4)
        self._card_box(cx, -0.02)
        q = self.loyalty.quote(self.basket.as_lines(True), self.card)
        yy = -0.13
        for name, v, col in (("Sous-total", q["subtotal"], rgb(40, 40, 50)), ("Remises carte", -q["discount"], SHOP_RED),
                             ("Bon fidélité", -q["voucher"], SHOP_RED)):
            if v or name == "Sous-total":
                label(r, name, cx - 0.16, yy, 0.65, col, origin=(-0.5, 0), z=0.5)
                label(r, eur(v), cx + 0.16, yy, 0.65, col, origin=(0.5, 0), z=0.5)
                yy -= 0.035
        label(r, "TOTAL", cx - 0.16, yy - 0.01, 1.0, rgb(20, 20, 30), origin=(-0.5, 0), z=0.5)
        label(r, eur(q["total"]), cx + 0.16, yy - 0.01, 1.2, rgb(20, 20, 30), origin=(0.5, 0), z=0.5)
        pay = button(r, "Payer" if all_scanned else "Scannez tous les articles", cx, -0.3, 0.34, 0.07,
                     self._pay if all_scanned else None, style="success" if all_scanned else "card", size=0.85, z=0.4)
        if not all_scanned:
            pay.highlight_color = pay.color
        if self.msg:
            label(r, self.msg, -0.09, -self.H / 2 + 0.05, 0.62, rgb(170, 60, 40), z=0.5)

    def _card_box(self, x, y):
        r = self.root
        rect(r, x, y, 0.36, 0.11, rgb(255, 255, 255), z=0.8, radius=0.12)
        rect(r, x - 0.15, y, 0.04, 0.07, SHOP_RED, z=0.6, radius=0.2)
        if self.card:
            c = self.loyalty.card(self.card)
            label(r, "Carte fidélité", x - 0.12, y + 0.03, 0.55, rgb(110, 110, 120), origin=(-0.5, 0), z=0.5)
            label(r, Loyalty.pretty(self.card), x - 0.12, y + 0.0, 0.8, rgb(20, 20, 30), origin=(-0.5, 0), z=0.5)
            label(r, f"{c['holder']} — {c['points']} pts", x - 0.12, y - 0.032, 0.5, rgb(90, 90, 100), origin=(-0.5, 0), z=0.5)
            button(r, "×", x + 0.155, y + 0.03, 0.03, 0.03, self._unset_card, style="ghost", text_col=rgb(120, 120, 130), size=0.7,
                   z=0.4)
        else:
            label(r, "Avez-vous la carte fidélité ?", x - 0.12, y + 0.03, 0.55, rgb(60, 60, 70), origin=(-0.5, 0), z=0.5)
            button(r, "Scanner ma carte", x - 0.035, y - 0.015, 0.16, 0.042, self._scan_card, style="primary", size=0.5, z=0.4)
            button(r, "Saisir n°", x + 0.08, y - 0.015, 0.075, 0.042, self._enter_card, style="dark", size=0.5, z=0.4)
            button(r, "Créer", x + 0.143, y - 0.015, 0.05, 0.042, self._create_card, style="dark", size=0.45, z=0.4)

    def _page_card_entry(self):
        self._frame("Carte fidélité")
        r = self.root
        label(r, "Saisissez le numéro de votre carte fidélité (10 chiffres)", 0, 0.16, 0.9, rgb(40, 40, 50), z=0.5)
        self.field = InputField(parent=r, default_value=self.loyalty.active, position=(0, 0.06, 0.3), scale=(0.5, 0.06),
                                character_limit=12, limit_content_to="0123456789 ")
        self.field.active = True
        button(r, "Valider  [Entrée]", 0.12, -0.06, 0.24, 0.06, self._validate_card, style="success", size=0.75, z=0.4)
        button(r, "Annuler", -0.12, -0.06, 0.2, 0.06, self._back_scan, style="dark", size=0.75, z=0.4)
        if self.msg:
            label(r, self.msg, 0, -0.16, 0.7, rgb(190, 50, 40), z=0.5)
        label(r, "Votre carte par défaut : " + Loyalty.pretty(self.loyalty.active), 0, -0.26, 0.6, rgb(120, 120, 130), z=0.5)

    def _page_garnier(self):
        self._frame("Carte fidélité")
        r = self.root
        c = self.loyalty.card(GARNIER_CARD)
        label(r, "Bonjour M. GARNIER.", 0, 0.18, 1.8, rgb(30, 30, 40), z=0.5)
        label(r, "Cela faisait longtemps. Votre cagnotte : " + str(c["points"]) + " points.", 0, 0.1, 0.8, rgb(80, 80, 90), z=0.5)
        y = 0.02
        label(r, "Vos derniers achats :", 0, y, 0.7, rgb(120, 120, 130), z=0.5)
        for d, desc, tot in c["history"][:3]:
            y -= 0.045
            label(r, f"{d}   {desc}   {eur(tot)}", 0, y, 0.62, rgb(40, 40, 50), z=0.5)
        label(r, "Cette carte est bloquée : titulaire décédé.", 0, y - 0.08, 0.75, SHOP_RED, z=0.5)
        button(r, "Retour", 0, -0.28, 0.2, 0.06, self._back_scan, style="dark", size=0.75, z=0.4)
        self.game.player.add_stress(8)

    def _page_pay(self):
        self._frame("Paiement")
        r = self.root
        q = self.loyalty.quote(self.basket.as_lines(True), self.card)
        label(r, "Montant à régler", 0, 0.2, 0.9, rgb(90, 90, 100), z=0.5)
        label(r, eur(q["total"]), 0, 0.12, 2.6, rgb(20, 20, 30), z=0.5)
        rect(r, 0, -0.04, 0.22, 0.15, rgb(30, 30, 36), z=0.8, radius=0.1)
        label(r, ")))", 0, -0.04, 1.6, rgb(120, 220, 140), z=0.5)
        label(r, "Approchez votre carte bancaire du lecteur", 0, -0.16, 0.8, rgb(60, 60, 70), z=0.5)
        label(r, f"Carte Visa •••• 4721 — solde disponible {eur(bank_balance(self.game.state))}", 0, -0.21, 0.55,
              rgb(120, 120, 130), z=0.5)
        button(r, "Payer sans contact", 0, -0.29, 0.3, 0.065, self._do_pay, style="success", size=0.8, z=0.4)

    def _page_done(self):
        self._frame("Merci de votre visite")
        r = self.root
        label(r, "Paiement accepté", 0, 0.16, 2.0, rgb(30, 130, 60), z=0.5)
        label(r, "N'oubliez pas vos articles et votre ticket.", 0, 0.07, 0.85, rgb(80, 80, 90), z=0.5)
        if self.last_points is not None:
            label(r, f"Carte {Loyalty.pretty(self.card)} : +{self.last_quote['points']} points — cagnotte {self.last_points} pts",
                  0, 0.0, 0.7, SHOP_RED, z=0.5)
        button(r, "Voir le ticket", -0.12, -0.12, 0.22, 0.065, self._show_ticket, style="blue", size=0.75, z=0.4)
        button(r, "Terminer", 0.12, -0.12, 0.2, 0.065, self.close, style="success", size=0.75, z=0.4)

    # ------------------------------------------------------------------
    def _remove(self, aid):
        self.basket.remove(aid)
        self.game.neighborhood.on_basket_changed(aid, removed=True)
        sound.play("ui_click", 0.5)
        self.page = "scan" if self.basket.count else "empty"
        self.render()

    def _scan_one(self):
        for art, q in self.basket.as_lines():
            if self.basket.scanned.get(art.id, 0) < q:
                # gag réaliste (une fois) : « article non reconnu »
                if not self.unknown_item_done and random.random() < 0.35:
                    self.unknown_item_done = True
                    self.msg = "Article inattendu dans la zone d'ensachage. Un conseiller va venir vous aider..."
                    sound.play("antivol", 0.35)
                    kiosk_say("inconnu")
                    self.render()
                    invoke(self._clear_msg, delay=2.5)
                    return
                self.basket.scanned[art.id] = self.basket.scanned.get(art.id, 0) + 1
                sound.play("scan_bip", 0.7)
                self.msg = ""
                self.render()
                return

    def _clear_msg(self):
        if self.visible and self.page == "scan":
            self.msg = "Merci, le conseiller a validé votre article."
            self.render()

    def _scan_all(self):
        n = 0
        for art, q in self.basket.as_lines():
            while self.basket.scanned.get(art.id, 0) < q:
                self.basket.scanned[art.id] = self.basket.scanned.get(art.id, 0) + 1
                invoke(sound.play, "scan_bip", 0.6, delay=n * 0.22)
                n += 1
        self.render()

    def _scan_card(self):
        self.card = self.loyalty.active
        sound.play("scan_bip", 0.7, pitch=1.2)
        kiosk_say("carte")
        self.msg = ""
        self.render()

    def _enter_card(self):
        self.page = "card_entry"
        self.msg = ""
        self.render()

    def _create_card(self):
        n = self.loyalty.create(gd.PLAYER_FIRST.upper() if hasattr(gd, "PLAYER_FIRST") else "CLIENT")
        self.card = n
        sound.play("caisse_ok", 0.6)
        kiosk_say("nouvelle_carte")
        self.msg = f"Nouvelle carte créée : {Loyalty.pretty(n)} (devient votre carte par défaut)."
        self.render()

    def _unset_card(self):
        self.card = None
        self.render()

    def _validate_card(self):
        num = (self.field.text if self.field else "").replace(" ", "")
        if num == GARNIER_CARD:
            self.page = "garnier"
            kiosk_say("garnier")
            self.render()
            return
        if not valid_format(num):
            self.msg = "Numéro invalide : 10 chiffres commençant par 95317."
            sound.play("antivol", 0.25)
            self.render()
            return
        if not self.loyalty.exists(num):
            self.msg = "Carte inconnue. Vous pouvez créer une nouvelle carte."
            sound.play("antivol", 0.25)
            self.render()
            return
        self.card = num
        self.loyalty.set_active(num)
        self.msg = ""
        self._back_scan()

    def _back_scan(self):
        self.page = "scan" if self.basket.count else "empty"
        self.render()

    def _pay(self):
        self.page = "pay"
        kiosk_say("payer")
        self.render()

    def _do_pay(self):
        st = self.game.state
        lines = self.basket.as_lines(True)
        q = self.loyalty.quote(lines, self.card)
        if bank_balance(st) < q["total"]:
            kiosk_say("refus")
            self.msg = "Paiement refusé."
            self.page = "scan"
            self.render()
            return
        sound.play("paiement_nfc", 0.7)
        bank_debit(st, SHOP_FULL.title()[:26], q["total"])
        self.last_quote = q
        self.last_points = self.loyalty.commit(lines, self.card, q) if self.card else None
        self.last_lines = lines
        self.last_card = self.card
        for art, n in lines:
            if art.item:
                self.game.inventory.add(art.item, art.item_qty * n)
            else:
                self.game.inventory.add("courses", n)
        st.flags["shop_paid_total"] = round(st.flags.get("shop_paid_total", 0.0) + q["total"], 2)
        st.stats["achats"] = st.stats.get("achats", 0) + 1
        kiosk_say("merci")
        self.basket.clear()
        self.page = "done"
        self.render()
        if self.on_paid:
            self.on_paid(lines, q)

    def _show_ticket(self):
        self.close()
        self.game.ui.docs.open("Ticket de caisse", [self.ticket_text()])

    def ticket_text(self):
        q = self.last_quote
        st = self.game.state
        hh, mm = int(st.clock // 60) % 24, int(st.clock % 60)
        out = [SHOP_FULL, "Bd du Mont-Boron, 06300 Nice", "Tél. 04 93 00 00 00", "", f"13/10   {hh:02d}:{mm:02d}   Caisse auto 02", "-" * 34]
        for art, n in self.last_lines:
            out.append(f"{art.short:<20}{n:>2} x {art.price:5.2f}".replace(".", ","))
            if art.card_price is not None and self.last_card:
                out.append(f"   Remise carte        -{(art.price - art.card_price) * n:5.2f}".replace(".", ","))
        out.append("-" * 34)
        if q["voucher"]:
            out.append(f"BON FIDELITE {POINTS_PER_VOUCHER} PTS       -{q['voucher']:5.2f}".replace(".", ","))
        out.append(f"TOTAL                 {q['total']:7.2f} EUR".replace(".", ","))
        out.append("CB SANS CONTACT  VISA ****4721")
        if self.last_card:
            out += ["", f"Carte fidélité {Loyalty.pretty(self.last_card)}", f"Points gagnés : {q['points']}",
                    f"Cagnotte : {self.last_points} pts"]
        out += ["", "Merci de votre visite, à bientôt !", "Ouvert 7j/7 de 7h à 23h"]
        return "\n".join(out)


class RestaurantCounter:
    """Comptoir de « Chez Nino » : on choisit un plat, on paie, on mange (santé / stress)."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-18, enabled=False)
        self.visible = False

    def open(self):
        self.visible = True
        self.root.enabled = True
        self.game.set_mouse(free=True)
        self.render()

    def close(self):
        self.visible = False
        self.root.enabled = False
        clear(self.root)
        self.game.set_mouse(free=False)

    def on_key(self, key):
        if key == "escape":
            self.close()
        return True

    def render(self, msg=""):
        clear(self.root)
        r = self.root
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 150), z=2)
        panel(r, 0, 0, 0.94, 0.74, "paper", z=1.5)
        label(r, RESTO_NAME.upper(), 0, 0.3, 2.4, rgb(150, 30, 26), z=0.5)
        label(r, "Spécialités niçoises — depuis 1962", 0, 0.24, 0.8, rgb(90, 70, 50), z=0.5)
        y = 0.16
        for mid, name, price, heal, calm, desc in RESTO_MENU:
            label(r, name, -0.4, y + 0.012, 0.95, rgb(40, 30, 24), origin=(-0.5, 0), z=0.5)
            label(r, desc, -0.4, y - 0.022, 0.55, rgb(110, 90, 70), origin=(-0.5, 0), z=0.5)
            label(r, eur(price), 0.2, y, 0.9, rgb(40, 30, 24), origin=(0.5, 0), z=0.5)
            button(r, "Commander", 0.33, y, 0.15, 0.05, (lambda m=mid: self._order(m)), style="danger", size=0.6, z=0.4)
            y -= 0.075
        label(r, msg or f"Solde BNR : {eur(bank_balance(self.game.state))}", 0, -0.25, 0.7, rgb(90, 70, 50), z=0.5)
        button(r, "Partir  [Échap]", 0, -0.31, 0.2, 0.05, self.close, style="dark", size=0.65, z=0.4)

    def _order(self, mid):
        g = self.game
        item = next(m for m in RESTO_MENU if m[0] == mid)
        _, name, price, heal, calm, _ = item
        if bank_balance(g.state) < price:
            self.render("Paiement refusé.")
            return
        bank_debit(g.state, (RESTO_NAME + " — Nice")[:26], price)
        sound.play("paiement_nfc", 0.6)
        p = g.player
        p.health = min(100.0, p.health + heal)
        p.relieve_stress(calm)
        if mid == "cafe":
            p.stamina = 100.0
        g.state.stats["repas"] = g.state.stats.get("repas", 0) + 1
        lines = {"socca": "Brûlant. Exactement comme il faut.", "pan_bagnat": "Le vrai, sans salade. Nino ne rigole pas avec ça.",
                 "pissaladiere": "Les anchois, c'est non négociable.", "pizza": "Un peu trop cuite. Parfaite.",
                 "cafe": "Ça réveille."}
        self.render(f"{name} : {lines.get(mid, 'Merci !')}")
