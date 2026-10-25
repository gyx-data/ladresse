"""Inventaire du joueur : objets, documents trouvés, panneau Tab."""
from ursina import Entity, Text, color, camera

import game_data as gd
from ui_widgets import button

ITEM_DEFS = {
    "pile": ("Pile", "Recharge la lampe torche ou le téléphone.", (0.9, 0.8, 0.2), True),
    "cle_tiroir": ("Petite clé", "Une petite clé en laiton. Elle ouvre un tiroir.", (0.85, 0.7, 0.3), False),
    "pied_de_biche": ("Pied de biche", "Lourd. Idéal pour arracher des planches.", (0.5, 0.5, 0.55), False),
    "sel": ("Salière", "Du gros sel. Peut-être utile.", (0.9, 0.9, 0.9), True),
    "tisonnier": ("Tisonnier", "Inutile comme arme.", (0.3, 0.3, 0.3), False),
    "trousseau": ("Trousseau de clés", "Elles n'ouvrent rien ici.", (0.6, 0.6, 0.5), False),
    "adresse_bonne": ("Papier : adresse", "17 rue des Lilas, 69120 Vaulx-en-Velin", (0.9, 0.85, 0.7), False),
    "adresse_piege": ("Papier : adresse barrée", "4 impasse du Calvaire, 69120 (barrée)", (0.9, 0.7, 0.6), False),
    "adresse_erreur": ("Papier : petite annonce", "23 avenue du Grand Champ", (0.8, 0.8, 0.75), False),
    "numero_barre": ("Papier : numéro barré", "Un numéro de téléphone barré plusieurs fois.", (0.85, 0.85, 0.8), False),
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
    """Panneau d'inventaire (Tab)."""

    def __init__(self, inventory, game):
        self.inventory = inventory
        self.game = game
        self.root = Entity(parent=camera.ui, enabled=False, z=-1)
        self.visible = False
        self.rows = []
        self._build()

    def _build(self):
        Entity(parent=self.root, model="quad", color=color.rgba32(0, 0, 0, 215), scale=(1.1, 0.78), z=0.5)
        Text(parent=self.root, text="INVENTAIRE", position=(-0.5, 0.34), scale=1.4, color=color.white)
        Text(parent=self.root, text="Documents", position=(0.08, 0.30), scale=1.0, color=color.rgb32(200, 190, 150))
        self.body = Entity(parent=self.root)
        self.hint = Text(parent=self.root, text="[Tab] Fermer", position=(-0.5, -0.34), scale=0.8, color=color.gray)

    def refresh(self):
        for e in list(self.body.children):
            e.disable()
            e.parent = None
        y = 0.25
        for item, count in self.inventory.items():
            name, desc, col, usable = ITEM_DEFS[item]
            Entity(parent=self.body, model="quad", color=color.rgb32(*[int(c * 255) for c in col]), scale=(0.03, 0.03),
                   position=(-0.5, y))
            Text(parent=self.body, text=f"{name} x{count}" if count > 1 else name, position=(-0.47, y + 0.012), scale=0.9, color=color.white)
            Text(parent=self.body, text=desc, position=(-0.47, y - 0.012), scale=0.6, color=color.gray)
            if usable:
                button(self.body, "Utiliser", -0.12, y, 0.1, 0.035, (lambda it=item: self.game.use_item(it)),
                       color.rgba32(60, 60, 60, 220), color.white, size=0.7)
            y -= 0.065
        if y > 0.24:
            Text(parent=self.body, text="(vide)", position=(-0.5, 0.25), scale=0.9, color=color.gray)
        # documents
        y = 0.25
        for doc in gd.DOC_TITLES:
            if doc in self.inventory.state.docs:
                button(self.body, gd.DOC_TITLES[doc], 0.3, y, 0.4, 0.04, (lambda d=doc: self.game.reread_doc(d)),
                       color.rgba32(40, 40, 40, 220), color.rgb32(220, 210, 170), size=0.7)
                y -= 0.055
        found = self.inventory.state.docs_required_found
        Text(parent=self.body, text=f"Documents de Garnier : {found}/{len(gd.REQUIRED_DOCS)}", position=(0.08, -0.3), scale=0.8,
             color=color.rgb32(180, 170, 140))

    def show(self):
        self.visible = True
        self.root.enabled = True
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
