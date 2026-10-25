"""Application bancaire « BNR Banque » (fausse banque) : solde, transactions, appel."""
from ursina import color

import game_data as gd
from phone_system import App, SW
from ui_widgets import label, rect, button, clear, rgb

BLUE = rgb(26, 70, 180)


def fmt_eur(v, signed=False):
    s = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
    sign = "-" if v < 0 else ("+" if signed else "")
    return f"{sign}{s} €"


class BankApp(App):
    name = "banque"
    title = "Ma Banque"

    def __init__(self, phone):
        super().__init__(phone)
        self.logged = False

    def on_open(self):
        self.render()

    def render(self):
        clear(self.root)
        game = self.phone.game
        st = game.state
        rect(self.root, 0, 0.32, SW, 0.06, BLUE)
        label(self.root, "BNR Banque", -0.17, 0.32, 1.1, color.white, origin=(-0.5, 0))
        label(self.root, "Connecté", 0.17, 0.32, 0.4, rgb(180, 220, 255), origin=(0.5, 0))
        rect(self.root, 0, 0.22, SW - 0.03, 0.11, rgb(24, 40, 90))
        label(self.root, "Compte courant", -0.18, 0.25, 0.5, rgb(170, 190, 240), origin=(-0.5, 0), z=-0.03)
        from shop import bank_balance
        label(self.root, fmt_eur(bank_balance(st)), -0.18, 0.21, 1.5, color.white, origin=(-0.5, 0), z=-0.03)
        label(self.root, "Solde disponible", -0.18, 0.18, 0.4, rgb(170, 190, 240), origin=(-0.5, 0), z=-0.03)
        label(self.root, "Dernières opérations", -0.18, 0.13, 0.6, color.white, origin=(-0.5, 0))
        y = 0.095
        rows = []
        refused = st.flags.get("refused_orders", [])
        for r in reversed(refused):
            rows.append((r[0], r[1], r[2], True))
        for r in reversed(st.flags.get("purchases", [])):
            rows.append((r[0], r[1], r[2], False))
        for name, amount, date in gd.BANK_TRANSACTIONS:
            rows.append((name, amount, date, False))
        for name, amount, date, bad in rows[:8]:
            rect(self.root, 0, y, SW - 0.03, 0.05, rgb(30, 30, 36))
            label(self.root, name[:26], -0.18, y + 0.01, 0.5, color.white, origin=(-0.5, 0), z=-0.03)
            label(self.root, date, -0.18, y - 0.014, 0.35, color.gray, origin=(-0.5, 0), z=-0.03)
            if bad:
                label(self.root, fmt_eur(amount), 0.17, y + 0.008, 0.55, rgb(255, 80, 80), origin=(0.5, 0), z=-0.03)
                label(self.root, "REFUSÉE", 0.17, y - 0.014, 0.4, rgb(255, 80, 80), origin=(0.5, 0), z=-0.03)
            else:
                col = rgb(110, 220, 130) if amount > 0 else color.white
                label(self.root, fmt_eur(amount, True), 0.17, y, 0.55, col, origin=(0.5, 0), z=-0.03)
            y -= 0.055
        button(self.root, "Contacter ma banque", 0, -0.33, SW - 0.06, 0.055, self.call, BLUE, color.white, size=0.7)

    def call(self):
        self.phone.calls.start("Ma banque", "Ma banque")
