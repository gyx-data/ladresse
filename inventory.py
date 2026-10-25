"""Inventaire du joueur : objets, documents trouvés, panneau Tab."""
from ursina import Entity, color, camera

import game_data as gd
import illustrations as ill
from ui_widgets import button, label, rect, panel, image, clear, rgb

ITEM_DEFS = {
    "pile": ("Pile", "Recharge la lampe torche ou le téléphone.", (0.9, 0.8, 0.2), True),
    "cle_tiroir": ("Petite clé", "Une petite clé en laiton. Elle ouvre un tiroir.", (0.85, 0.7, 0.3), False),
    "pied_de_biche": ("Pied de biche", "Lourd. Idéal pour arracher des planches.", (0.5, 0.5, 0.55), False),
    "sel": ("Salière", "Du gros sel. Peut-être utile.", (0.9, 0.9, 0.9), True),
    "tisonnier": ("Tisonnier", "Inutile comme arme.", (0.3, 0.3, 0.3), False),
    "trousseau": ("Trousseau de clés", "Elles n'ouvrent rien ici.", (0.6, 0.6, 0.5), False),
    "adresse_bonne": ("Papier : adresse", "17 rue des Lilas, 06300 Nice", (0.9, 0.85, 0.7), False),
    "adresse_piege": ("Papier : adresse barrée", "4 impasse du Calvaire, 06300 (barrée)", (0.9, 0.7, 0.6), False),
    "adresse_erreur": ("Papier : petite annonce", "23 avenue du Grand Champ", (0.8, 0.8, 0.75), False),
    "numero_barre": ("Papier : numéro barré", "Un numéro de téléphone barré plusieurs fois.", (0.85, 0.85, 0.8), False),
    "batterie_externe": ("Batterie externe", "Recharge le téléphone à 80 %.", (0.25, 0.25, 0.3), True),
    "bougie": ("Bougie chauffe-plat", "Une petite flamme pendant deux minutes.", (0.95, 0.9, 0.8), True),
    "pansement": ("Pansements", "Rend 35 points de santé.", (0.9, 0.7, 0.6), True),
    "barre": ("Barre chocolatée", "Réconfortant. -25 de stress.", (0.5, 0.28, 0.15), True),
    "eau": ("Bouteille d'eau", "Récupère toute l'endurance.", (0.55, 0.75, 0.95), True),
    "energisant": ("Boisson énergisante", "Endurance quasi illimitée pendant 60 s.", (0.2, 0.6, 0.9), True),
    "journal": ("Nice-Matin", "Le journal du jour.", (0.92, 0.92, 0.9), True),
    "courses": ("Sac de courses", "Des courses ordinaires. Ça rassure.", (0.9, 0.4, 0.3), False),
}


class Inventory:
    """Vue sur les objets de WorldState + utilitaires."""

    def __init__(self, state):
        self.state = state

    def add(self, item, n=1):
        self.state.add_item(item, n)

    def has(self, item, n=1):
        return self.state.has(item, n)

    def remove(self, item, n=1):
        return self.state.remove_item(item, n)

    def items(self):
        return [(k, v) for k, v in self.state.items.items() if k in ITEM_DEFS]


class InventoryPanel:
    """Panneau d'inventaire (Tab) : grille paginée d'objets avec icône, description et bouton « Utiliser »,
    liste des documents trouvés à droite."""

    W, H = 1.34, 0.86
    PER_PAGE = 12

    def __init__(self, inventory, game):
        self.inventory = inventory
        self.game = game
        self.root = Entity(parent=camera.ui, enabled=False, z=-1)
        self.visible = False
        self.rows = []
        self.page = 0
        self._icons = {}
        self._build()

    def _build(self):
        r = self.root
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 150), z=0.9)
        panel(r, 0, 0, self.W, self.H, "panel", z=0.8)
        label(r, "INVENTAIRE", -self.W / 2 + 0.05, self.H / 2 - 0.05, 1.5, color.white, origin=(-0.5, 0), z=0.5)
        label(r, "DOCUMENTS", 0.2, self.H / 2 - 0.12, 0.6, rgb(190, 40, 36), origin=(-0.5, 0), z=0.5)
        label(r, "OBJETS", -self.W / 2 + 0.05, self.H / 2 - 0.12, 0.6, rgb(190, 40, 36), origin=(-0.5, 0), z=0.5)
        rect(r, 0.17, -0.02, 0.002, self.H - 0.2, rgb(80, 70, 70), z=0.5)
        self.body = Entity(parent=r, z=0.3)
        label(r, f"[{settings_key('inventaire')}] Fermer", self.W / 2 - 0.05, -self.H / 2 + 0.04, 0.6, color.gray, origin=(0.5, 0), z=0.5)

    def _icon(self, item, col):
        if item not in self._icons:
            try:
                img = ill.item_icon(item, 96)
            except Exception:
                img = None
            self._icons[item] = img
        return self._icons[item]

    def refresh(self):
        clear(self.body)
        b = self.body
        items = self.inventory.items()
        pages = max(1, (len(items) + self.PER_PAGE - 1) // self.PER_PAGE)
        self.page = max(0, min(self.page, pages - 1))
        shown = items[self.page * self.PER_PAGE:(self.page + 1) * self.PER_PAGE]
        x0, y0 = -self.W / 2 + 0.05, self.H / 2 - 0.2
        cw, rh = 0.39, 0.098
        for i, (item, count) in enumerate(shown):
            name, desc, col, usable = ITEM_DEFS[item]
            cx = x0 + (i % 2) * (cw + 0.012)
            cy = y0 - (i // 2) * rh
            rect(b, cx + cw / 2, cy, cw, rh - 0.01, rgb(255, 255, 255, 10), z=0.2, radius=0.15)
            img = self._icon(item, col)
            if img is not None:
                image(b, img, cx + 0.04, cy, 0.056, 0.056, z=0.1)
            else:
                rect(b, cx + 0.04, cy, 0.04, 0.04, rgb(*[int(c * 255) for c in col]), z=0.1, radius=0.3)
            right = cx + cw - (0.1 if usable else 0.01)
            label(b, f"{name}  x{count}" if count > 1 else name, cx + 0.078, cy + 0.016, 0.72, color.white, origin=(-0.5, 0), z=0,
                  max_w=right - (cx + 0.078) - 0.008)
            label(b, desc, cx + 0.078, cy - 0.016, 0.5, rgb(160, 158, 154), origin=(-0.5, 0), z=0, wrap=44,
                  max_w=right - (cx + 0.078) - 0.008, max_h=0.04)
            if usable:
                button(b, "Utiliser", cx + cw - 0.052, cy, 0.088, 0.04, (lambda it=item: self.game.use_item(it)), style="primary",
                       size=0.55, z=0)
        if not items:
            label(b, "(vide)", x0 + 0.2, y0, 0.8, color.gray, z=0)
        if pages > 1:
            yb = -self.H / 2 + 0.06
            button(b, "‹", x0 + 0.03, yb, 0.045, 0.04, lambda: self._turn(-1), style="dark", size=0.8, z=0)
            label(b, f"{self.page + 1} / {pages}", x0 + 0.11, yb, 0.6, rgb(170, 168, 164), z=0)
            button(b, "›", x0 + 0.19, yb, 0.045, 0.04, lambda: self._turn(1), style="dark", size=0.8, z=0)
        # documents
        y = self.H / 2 - 0.19
        for doc in gd.DOC_TITLES:
            if doc in self.inventory.state.docs:
                button(b, gd.DOC_TITLES[doc], 0.42, y, 0.42, 0.045, (lambda d=doc: self.game.reread_doc(d)), style="paper", size=0.62, z=0)
                y -= 0.054
                if y < -self.H / 2 + 0.14:
                    break
        found = self.inventory.state.docs_required_found
        label(b, f"Documents de Garnier : {found}/{len(gd.REQUIRED_DOCS)}", 0.2, -self.H / 2 + 0.1, 0.62, rgb(200, 186, 150),
              origin=(-0.5, 0), z=0, max_w=0.42)

    def _turn(self, d):
        self.page += d
        self.refresh()

    def show(self):
        self.visible = True
        self.root.enabled = True
        self.page = 0
        self.refresh()

    def hide(self):
        self.visible = False
        self.root.enabled = False

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()
        return self.visible


def settings_key(action):
    from config import settings
    return settings.key(action).upper()
