"""Application bancaire « BNR Banque » (fausse banque) : solde, transactions, appel."""
import game_data as gd
from phone_system import App, SW, BG, CARD, LINE, TXT, SUB, DIM, GREEN, RED, txt, pic, btn, ptex, ellipsize
from ui_widgets import rect, clear, rgb, text_box

BLUE = rgb(26, 70, 180)
CARD_BLUE = rgb(34, 84, 214)
ROW_COLORS = [(88, 86, 214), (255, 149, 0), (52, 170, 220), (255, 55, 95), (48, 176, 120), (175, 82, 222), (90, 120, 160)]


def fmt_eur(v, signed=False):
    s = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
    sign = "-" if v < 0 else ("+" if signed else "")
    return f"{sign}{s} €"


class BankApp(App):
    name = "banque"
    title = "Ma Banque"
    PER_PAGE = 6
    toast_y = -0.25            # au-dessus du bouton « Contacter ma banque »

    def __init__(self, phone):
        super().__init__(phone)
        self.reset()

    def reset(self):
        self.logged = False
        self.offset = 0
        self._seen = None

    def on_open(self):
        self.offset = 0
        self.render()

    def _rows(self):
        st = self.phone.game.state
        rows = []
        for r in reversed(st.flags.get("refused_orders", [])):
            rows.append((r[0], r[1], r[2], True))
        for r in reversed(st.flags.get("purchases", [])):
            rows.append((r[0], r[1], r[2], False))
        for name, amount, date in gd.BANK_TRANSACTIONS:
            rows.append((name, amount, date, False))
        return rows

    def _signature(self):
        st = self.phone.game.state
        return (len(st.flags.get("refused_orders", [])), len(st.flags.get("purchases", [])))

    def render(self):
        clear(self.root)
        game = self.phone.game
        st = game.state
        self._seen = self._signature()
        self.background()
        pic(self.root, ptex("app_icon", "banque", 96), -0.162, 0.306, 0.034)
        txt(self.root, gd.BANK_NAME, -0.137, 0.306, 0.9, TXT, bold=True, max_w=0.2)
        rect(self.root, 0.112, 0.306, 0.009, 0.009, GREEN, z=0.0, radius=0.5)
        txt(self.root, "Connecté", 0.178, 0.306, 0.36, SUB, (0.5, 0), max_w=0.055)
        # carte du compte courant
        from shop import bank_balance
        y = 0.2
        rect(self.root, 0, y, SW - 0.036, 0.13, CARD_BLUE, z=0.0, radius=0.13)
        txt(self.root, f"Bonjour {gd.PLAYER_FIRST} · Compte courant", -0.162, y + 0.044, 0.36, rgb(214, 226, 255), max_w=0.3)
        txt(self.root, fmt_eur(bank_balance(st)), -0.162, y + 0.008, 1.2, TXT, bold=True, max_w=0.32)
        txt(self.root, "Solde disponible", -0.162, y - 0.03, 0.34, rgb(214, 226, 255))
        pic(self.root, ptex("glyph", "card", 48, (214, 226, 255)), 0.06, y - 0.044, 0.018)
        txt(self.root, gd.BANK_CARD, 0.162, y - 0.044, 0.36, TXT, (0.5, 0))
        refused = st.flags.get("refused_orders", [])
        y = 0.105
        if refused:
            # le solde est largement suffisant... et pourtant le paiement a été refusé
            rect(self.root, 0, y, SW - 0.036, 0.062, rgb(70, 22, 26), z=0.0, radius=0.22)
            pic(self.root, ptex("status_badge", "cross", 96), -0.15, y, 0.044)
            n = len(refused)
            txt(self.root, f"{n} paiement{'s' if n > 1 else ''} refusé{'s' if n > 1 else ''} ce soir", -0.12, y + 0.011, 0.44, TXT,
                bold=True, max_w=0.29)
            txt(self.root, "Motif communiqué : fonds insuffisants", -0.12, y - 0.013, 0.34, rgb(255, 170, 160), max_w=0.29)
            y -= 0.06
            self.game.quests.on_event("bank_checked")
        txt(self.root, "Dernières opérations", -0.178, y - 0.003, 0.48, TXT, bold=True)
        rows = self._rows()
        self.offset = max(0, min(self.offset, len(rows) - self.PER_PAGE))
        per = self.PER_PAGE if not refused else self.PER_PAGE - 1
        ry = y - 0.045
        for i, (name, amount, date, bad) in enumerate(rows[self.offset:self.offset + per]):
            col = ROW_COLORS[sum(map(ord, name)) % len(ROW_COLORS)] if not bad else (200, 50, 50)
            rect(self.root, -0.16, ry, 0.034, 0.034, rgb(*col), z=0.0, radius=0.5)
            txt(self.root, name.strip()[:1].upper(), -0.16, ry, 0.42, TXT, (0, 0), True)
            txt(self.root, ellipsize(name, 28), -0.134, ry + 0.009, 0.4, TXT, bold=True, max_w=0.2)
            txt(self.root, date + (" · Refusée" if bad else ""), -0.134, ry - 0.011, 0.32, RED if bad else SUB, max_w=0.2)
            if bad:
                t = txt(self.root, fmt_eur(amount), 0.178, ry, 0.42, RED, (0.5, 0), True)
                b = text_box(t, self.root)
                w = (b[2] - b[0]) if b else 0.06
                rect(self.root, 0.178 - w / 2, ry, w + 0.004, 0.0018, RED, z=-0.02)      # montant barré : non débité
            else:
                txt(self.root, fmt_eur(amount, True), 0.178, ry, 0.42, GREEN if amount > 0 else TXT, (0.5, 0), amount > 0)
            rect(self.root, 0.02, ry - 0.024, SW - 0.08, 0.0014, LINE, z=0.0)
            ry -= 0.05
        if self.offset + per < len(rows):
            txt(self.root, "Molette : opérations plus anciennes", 0, ry + 0.012, 0.3, DIM, (0, 0))
        btn(self.root, "Contacter ma banque", 0, -0.31, SW - 0.036, 0.048, self.call, "ph_blue", 0.52, bold=True)

    def update(self, dt):
        if self._signature() != self._seen:
            self.render()                      # paiement refusé / achat pendant que l'appli est ouverte

    def on_key(self, key):
        if key in ("scroll up", "scroll down"):
            old = self.offset
            self.offset = max(0, self.offset + (1 if key == "scroll down" else -1))
            self.render() if self.offset != old else None

    def call(self):
        self.phone.calls.start("Ma banque", "Ma banque")
