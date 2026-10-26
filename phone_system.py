"""Système de téléphone in-game : interface, écran d'accueil, notifications, appels,
applications Messages / Appareil photo / Lampe / Appels. QuickEats et la banque sont dans
delivery_app.py et bank_app.py.

Interface « smartphone sombre » : coque en titane (illustrations.phone_frame posée devant l'écran pour en
arrondir les coins), barre d'état (heure, îlot, réseau, batterie), fond d'écran nocturne, widget météo,
grille d'applis + dock, bannières de notification, appels plein écran, écran figé / batterie vide.

Performances : un écran n'est reconstruit que lorsque son contenu change (navigation, nouveau message...) ;
les textes animés (heure, batterie, chrono d'appel, saisie) ne sont réassignés que si leur valeur change.
La saisie de texte passe par les frappes clavier (`text_input`) : elle respecte la disposition AZERTY.
"""
import math
import os
import random

from ursina import Entity, Text, color, camera, mouse, curve, held_keys, invoke

import config
import game_data as gd
import illustrations as ill
import ui_theme as theme
from sound_engine import engine as sound
from texture_generator import textures
from ui_widgets import rect, clear, rgb, fit_text, text_scale, text_box, StyledButton

SW, SH = 0.40, 0.78           # taille de l'écran
PHONE_Y = -0.03
BODY_W, BODY_H = SW + 0.03, SH + 0.03

# Palette (thème sombre)
BG = rgb(11, 12, 16)
BAR = rgb(18, 19, 25)
CARD = rgb(27, 29, 36)
CARD2 = rgb(38, 40, 49)
LINE = rgb(46, 49, 60)
TXT = rgb(243, 244, 248)
SUB = rgb(152, 156, 170)
DIM = rgb(102, 106, 120)
GREEN = rgb(52, 199, 89)
RED = rgb(255, 69, 58)
BLUE = rgb(10, 132, 255)
ORANGE = rgb(255, 122, 26)
AMBER = rgb(255, 204, 92)

CONTACT_COLORS = {"duval": (175, 82, 222), "maman": (255, 149, 0), "support": (255, 112, 8), "chat": (52, 120, 246)}


# ---------------------------------------------------------------------------
# Styles de boutons propres au téléphone (aplats nets, sans grain d'ambiance)
# ---------------------------------------------------------------------------
def _style(name, top, bot, border, text, h_top, h_bot, h_border, radius):
    theme.STYLES[name] = dict(top=top, bot=bot, border=border, text=text, hover_top=h_top, hover_bot=h_bot,
                              hover_border=h_border, radius=radius)


_style("ph_card", (34, 36, 44, 255), (29, 31, 38, 255), (50, 53, 64, 255), (243, 244, 248), (46, 49, 60, 255), (38, 40, 50, 255), (84, 92, 120, 255), .24)
_style("ph_key", (58, 60, 70, 255), (48, 50, 59, 255), (0, 0, 0, 0), (250, 250, 252), (82, 85, 98, 255), (68, 71, 83, 255), (0, 0, 0, 0), .5)
_style("ph_kbd", (70, 72, 82, 255), (58, 60, 69, 255), (0, 0, 0, 0), (250, 250, 252), (96, 99, 112, 255), (80, 83, 95, 255), (0, 0, 0, 0), .2)
_style("ph_orange", (255, 146, 52, 255), (244, 96, 20, 255), (0, 0, 0, 0), (255, 255, 255), (255, 166, 82, 255), (255, 114, 36, 255), (0, 0, 0, 0), .5)
_style("ph_blue", (64, 128, 255, 255), (30, 86, 226, 255), (0, 0, 0, 0), (255, 255, 255), (92, 150, 255, 255), (48, 104, 240, 255), (0, 0, 0, 0), .5)
_style("ph_green", (70, 214, 110, 255), (40, 176, 78, 255), (0, 0, 0, 0), (255, 255, 255), (96, 230, 132, 255), (52, 192, 92, 255), (0, 0, 0, 0), .5)
_style("ph_red", (255, 86, 76, 255), (222, 44, 40, 255), (0, 0, 0, 0), (255, 255, 255), (255, 112, 102, 255), (236, 60, 54, 255), (0, 0, 0, 0), .5)
_style("ph_amber", (255, 220, 120, 255), (250, 176, 50, 255), (0, 0, 0, 0), (30, 22, 8), (255, 232, 150, 255), (255, 192, 70, 255), (0, 0, 0, 0), .5)
_style("ph_gray", (62, 64, 74, 255), (52, 54, 63, 255), (0, 0, 0, 0), (200, 202, 210), (62, 64, 74, 255), (52, 54, 63, 255), (0, 0, 0, 0), .5)
_style("ph_hit", (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (243, 244, 248), (255, 255, 255, 16), (255, 255, 255, 10), (0, 0, 0, 0), .2)


def _bold_font():
    """Police grasse (Inter Bold) copiée à côté de la police d'interface pour les titres du téléphone."""
    try:
        import shutil
        import typography as T
        if not str(Text.default_font).startswith("ladresse_ui"):
            return None
        src = T.find_font("sans", True)
        if not src or src == T.find_font("sans", False):
            return None
        name = "ladresse_ui_bold" + os.path.splitext(src)[1].lower()
        dst = os.path.join(config.cache_dir("fonts"), name)
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
        return name
    except Exception:
        return None


BOLD = _bold_font()
_TEX = {}


def ptex(fn_name, *args):
    """Texture Ursina d'une illustration du téléphone (mise en cache : une seule texture par image)."""
    key = (fn_name, args)
    if key not in _TEX:
        _TEX[key] = theme._tex(getattr(ill, fn_name)(*args))
    return _TEX[key]


def px(u):
    return max(8, int(round(u * 1080)))


def txt(parent, text, x=0.0, y=0.0, size=0.6, col=TXT, origin=(-0.5, 0), bold=False, wrap=None, max_w=None, max_h=None, z=-0.01):
    """Texte du téléphone (police d'interface, grasse si demandé), réduit pour tenir dans max_w x max_h."""
    kw = {}
    if wrap:
        kw["wordwrap"] = wrap
    if bold and BOLD:
        kw["font"] = BOLD
    t = Text(parent=parent, text=text if text else " ", position=(x, y, z), origin=origin, scale=size * text_scale(), color=col, **kw)
    if max_w is not None or max_h is not None:
        t._fit = (max_w, max_h)
        fit_text(t, max_w, max_h)
    return t


def set_txt(t, text):
    """Change un texte seulement si sa valeur change (réassigner un Text Ursina est coûteux)."""
    text = text if text else " "
    if t.text != text:
        t.text = text
        fit = getattr(t, "_fit", None)
        if fit:
            fit_text(t, fit[0], fit[1])


def pic(parent, texture, x, y, w, h=None, z=-0.01, col=None):
    e = Entity(parent=parent, model="quad", texture=texture, position=(x, y, z), scale=(w, h if h is not None else w))
    if col is not None:
        e.color = col
    return e


def btn(parent, text, x, y, w, h, fn=None, style="ph_card", size=0.55, z=-0.02, text_col=None, bold=False, shadow=False,
        tap=True, radius=None):
    """Bouton du téléphone : aplat arrondi, petit « tap » au clic (pas de sons d'interface du menu)."""
    def click():
        if tap:
            sound.play("tap", 0.5, channel="voice")
        if fn:
            fn()
    b = StyledButton(parent, text, x, y, w, h, click, style, text_col, size, z, radius, shadow, None, False)
    if bold and BOLD and getattr(b, "text_entity", None) is not None:
        b.text_entity.font = BOLD
        b._fit_label()
    if style == "ph_hit":
        b.ui_box = None                      # zone cliquable invisible : pas un cadre pour l'ajustement des textes
    return b


def hit(parent, x, y, w, h, fn, z=-0.03, tap=True):
    return btn(parent, "", x, y, w, h, fn, "ph_hit", z=z, tap=tap)


def blocker(parent, z):
    """Zone invisible qui intercepte les clics (écran d'appel, écran figé : rien ne doit passer dessous)."""
    b = StyledButton(parent, "", 0, 0, SW, SH, None, "ph_hit", None, 0.5, z, None, False, None, False)
    b.texture = None
    b.color = rgb(0, 0, 0, 0)
    b.ui_box = None
    return b


def ellipsize(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[:max(1, n - 1)].rstrip() + "…"


def initials(name):
    parts = [p for p in name.replace(".", " ").split() if p[0].isalpha()]
    if not parts:
        return "?"
    if parts[0].lower() in ("mme", "m", "mr", "dr") and len(parts) > 1:
        parts = parts[1:]
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()


def avatar(parent, name, x, y, d, col, z=-0.01, size=None):
    rect(parent, x, y, d, d, rgb(*col), z=z, radius=0.5)
    return txt(parent, initials(name), x, y, size or d * 13, TXT, (0, 0), True, z=z - 0.01)


def badge(parent, n, x, y, z=-0.05):
    """Pastille rouge de notification (nombre)."""
    root = Entity(parent=parent, position=(x, y, z))
    rect(root, 0, 0, 0.026, 0.026, RED, radius=0.5)
    txt(root, str(n) if n < 10 else "9+", 0, 0.0005, 0.36, TXT, (0, 0), True, z=-0.01)
    return root


def _wrap(text, width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        while len(w) > width:
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(w[:width])
            w = w[width:]
        if not w:
            continue
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def _escape_down():
    try:
        return bool(held_keys["escape"])
    except Exception:
        return True


class Message:
    def __init__(self, sender, text, time_str, mine=False, failed=False):
        self.sender, self.text, self.time, self.mine, self.failed = sender, text, time_str, mine, failed


class PhoneModel:
    """Données du téléphone (messages, historique d'appels, batterie, signal)."""

    def __init__(self, state):
        self.state = state
        self.battery = 100.0
        self.signal = 1
        self.torch_on = False
        self.dead = False
        self.reset_from_state()

    def reset_from_state(self):
        """Conversations et journal d'appels d'une partie neuve, puis messages déjà reçus (sauvegarde)."""
        self.conversations = {
            "duval": dict(name=gd.CONTACT_DUVAL, msgs=[], unread=0),
            "maman": dict(name=gd.CONTACT_MAMAN, msgs=[], unread=0),
            "support": dict(name=gd.CONTACT_SUPPORT, msgs=[], unread=0),
            "chat": dict(name="Chat d'équipe", msgs=[], unread=0, hidden=True),
        }
        for (t, who, text, mine) in [(m[0], m[1], m[2], m[3]) for m in gd.INTRO_SMS]:
            self.conversations["duval"]["msgs"].append(Message(who, text, t, mine))
        for who, text, t in gd.MAMAN_MESSAGES:
            self.conversations["maman"]["msgs"].append(Message(who, text, t, who == "Adrien"))
        for m in self.state.messages:
            conv, sender, text, t = m[0], m[1], m[2], m[3]
            if conv in self.conversations:
                self.conversations[conv]["msgs"].append(Message(sender, text, t, sender == gd.PLAYER_FIRST))
        self.call_log = [("Maman", "hier 12:03", False), ("Mme Duval", "hier 17:40", False)]
        self.torch_on = False

    def add_message(self, conv, sender, text, mine=False):
        c = self.conversations[conv]
        t = self.state.clock_string()
        c["msgs"].append(Message(sender, text, t, mine))
        if not mine:
            c["unread"] += 1
        self.state.messages.append((conv, sender, text, t))
        return c

    def drain(self, dt, quickeats=False, call=False, open_=False):
        # rangé en veille : décharge très lente (l'écran éteint ne consomme presque rien)
        rate = config.PHONE_DRAIN if open_ else config.PHONE_DRAIN_IDLE
        if quickeats:
            rate = config.PHONE_DRAIN_QUICKEATS
        if call:
            rate = config.PHONE_DRAIN_CALL
        if self.torch_on:
            rate += 0.1
        self.battery = max(0.0, self.battery - rate * config.diff("phone") * dt)
        self.state.player_battery_phone = self.battery
        if self.battery <= 0:
            self.dead = True
            self.torch_on = False

    def charge(self, amount):
        self.battery = min(100.0, self.battery + amount)
        self.state.player_battery_phone = self.battery
        if self.battery > 0:
            self.dead = False


# ---------------------------------------------------------------------------
# Applications simples
# ---------------------------------------------------------------------------
class App:
    name = "app"
    title = "App"
    typing = False             # vrai quand l'appli capte le clavier (le joueur ne se déplace plus)
    toast_y = -0.35            # message éphémère : en bas, au-dessus de la barre d'accueil (sous les boutons principaux)

    def __init__(self, phone):
        self.phone = phone
        self.game = phone.game
        self.root = Entity(parent=phone.screen_area, enabled=False)

    def reset(self):
        """Nouvelle partie : état initial de l'appli."""

    def on_open(self):
        pass

    def on_close(self):
        pass

    def update(self, dt):
        pass

    def tick(self, dt):
        """Appelé à chaque image, téléphone ouvert ou non (traitements en arrière-plan)."""

    def on_key(self, key):
        pass

    def text_input(self, ch):
        pass

    # --- éléments communs -------------------------------------------------
    def background(self, col=BG):
        return rect(self.root, 0, 0, SW, SH, col, z=0.02)

    def header(self, title, back=None, accent=BLUE, size=1.05, sub=None):
        """Grand titre de page (sous la barre d'état), chevron de retour facultatif."""
        x = -0.178
        if back is not None:
            hit(self.root, -0.168, 0.306, 0.042, 0.042, back, z=-0.05)
            pic(self.root, ptex("glyph", "back", 64, (int(accent[0] * 255), int(accent[1] * 255), int(accent[2] * 255))), -0.168, 0.306, 0.03,
                z=-0.04)
            x = -0.14
        t = txt(self.root, title, x, 0.306, size, TXT, bold=True, max_w=0.31 if back is None else 0.28, max_h=0.04)
        if sub:
            txt(self.root, sub, x, 0.274, 0.42, SUB, max_w=0.3)
        return t


class MessagesApp(App):
    name = "messages"
    title = "Messages"
    MAX_LEN = 160

    def __init__(self, phone):
        super().__init__(phone)
        self.reset()
        self.field = None
        self.caret = None

    def reset(self):
        self.page = "list"
        self.conv = None
        self.scroll = 0
        self.compose = ""
        self.composing = False
        self.more_above = False

    @property
    def typing(self):
        return self.composing and self.page == "thread"

    @property
    def toast_y(self):
        return -0.262 if self.page == "thread" else -0.35          # conversation : au-dessus du champ de saisie

    def on_open(self):
        if self.page == "thread" and self.conv:
            self.phone.model.conversations[self.conv]["unread"] = 0
        self.render()

    def on_close(self):
        self.composing = False

    def visible_convs(self):
        m = self.phone.model
        return [(cid, c) for cid, c in m.conversations.items() if not (c.get("hidden") and not self.game.is_multiplayer)]

    def render(self):
        clear(self.root)
        self.field = self.caret = None
        if self.page == "list" or self.conv not in self.phone.model.conversations:
            self.page = "list"
            self._render_list()
        else:
            self._render_thread()

    # --- liste des conversations --------------------------------------------
    def _render_list(self):
        self.background()
        self.header("Messages", accent=GREEN)
        rect(self.root, 0, 0.255, SW - 0.036, 0.036, CARD, z=0.0, radius=0.32)
        pic(self.root, ptex("glyph", "search", 48, (130, 134, 148)), -0.163, 0.255, 0.018)
        txt(self.root, "Rechercher", -0.146, 0.255, 0.44, DIM)
        hit(self.root, 0, 0.255, SW - 0.036, 0.036, lambda: self.phone.toast("Recherche indisponible hors connexion."))
        y = 0.19
        for cid, c in self.visible_convs():
            last = c["msgs"][-1] if c["msgs"] else None
            preview = ("Vous : " if last is not None and last.mine else "") + (last.text if last else "Aucun message")
            if cid == "support":
                pic(self.root, ptex("app_icon", "quickeats", 96), -0.15, y, 0.05)
            else:
                avatar(self.root, c["name"], -0.15, y, 0.05, CONTACT_COLORS.get(cid, (90, 90, 100)))
            unread = c["unread"] > 0
            txt(self.root, c["name"], -0.113, y + 0.013, 0.5, TXT, bold=True, max_w=0.2)
            txt(self.root, ellipsize(preview, 38), -0.113, y - 0.013, 0.4, TXT if unread else SUB, max_w=0.25)
            if last is not None:
                txt(self.root, last.time, 0.178, y + 0.013, 0.36, BLUE if unread else DIM, (0.5, 0), max_w=0.07)
            if unread:
                b = Entity(parent=self.root, position=(0.166, y - 0.012, -0.02))
                rect(b, 0, 0, 0.024, 0.024, BLUE, radius=0.5)
                txt(b, str(min(9, c["unread"])), 0, 0.0005, 0.34, TXT, (0, 0), True)
            rect(self.root, 0.035, y - 0.036, SW - 0.11, 0.0016, LINE, z=0.0)
            hit(self.root, 0, y, SW - 0.02, 0.07, lambda cid=cid: self.open_conv(cid))
            y -= 0.074

    # --- conversation ----------------------------------------------------------
    def _render_thread(self):
        c = self.phone.model.conversations[self.conv]
        c["unread"] = 0                        # conversation affichée : ses nouveaux messages sont lus
        self.background()
        rect(self.root, 0, 0.3, SW, 0.09, BAR, z=0.0)
        rect(self.root, 0, 0.255, SW, 0.0016, LINE, z=-0.001)
        hit(self.root, -0.168, 0.3, 0.042, 0.042, self.back, z=-0.05)
        pic(self.root, ptex("glyph", "back", 64, (52, 199, 89)), -0.168, 0.3, 0.03, z=-0.04)
        if self.conv == "support":
            pic(self.root, ptex("app_icon", "quickeats", 96), 0, 0.31, 0.034)
        else:
            avatar(self.root, c["name"], 0, 0.31, 0.034, CONTACT_COLORS.get(self.conv, (90, 90, 100)), size=0.42)
        txt(self.root, c["name"], 0, 0.276, 0.4, TXT, (0, 0), True, max_w=0.26)
        self._render_bubbles(c["msgs"])
        self._render_compose()

    def _render_bubbles(self, msgs):
        ts = text_scale()
        size = 0.44
        probe = Text(parent=self.root, text="Ag\nAg", scale=size * ts, origin=(-0.5, 0.5), z=0.5, line_height=1.18)
        bx = text_box(probe, self.root)
        line_h = ((bx[3] - bx[1]) / 2.0) if bx else 0.014
        probe.enabled = False
        wrap_w = 30 if ts <= 1.0 else 24
        top, bottom = 0.235, -0.285
        group = self.conv == "chat"          # chat d'équipe : plusieurs interlocuteurs, chaque bulle porte son auteur
        name_h = 0.017
        layout = []
        for msg in msgs:
            lines = _wrap(msg.text, wrap_w)
            h = line_h * len(lines) + 0.034 + (name_h if group and not msg.mine else 0.0)
            layout.append((msg, lines, h))
        # les plus récents en bas ; `scroll` messages masqués sous le bas de l'écran
        end = len(layout) - self.scroll
        visible, total = [], 0.0
        i = end - 1
        while i >= 0:
            h = layout[i][2] + 0.012
            if total + h > top - bottom and visible:
                break
            visible.append(layout[i])
            total += h
            i -= 1
        self.more_above = i >= 0
        y = bottom + total
        for msg, lines, h in reversed(visible):
            t = Text(parent=self.root, text="\n".join(lines), scale=size * ts, origin=(-0.5, 0.5), color=TXT, z=-0.03,
                     line_height=1.18)
            b = text_box(t, self.root)
            w = min(0.27, max(0.07, (b[2] - b[0]) if b else 0.2) + 0.03)
            named = group and not msg.mine
            if named:
                w = max(w, min(0.27, 0.03 + 0.0062 * len(ellipsize(msg.sender, 18))))
            if msg.mine:
                x0 = 0.182 - w
                col = rgb(150, 40, 40) if msg.failed else rgb(36, 132, 72)
            else:
                x0 = -0.182
                col = CARD2
            yc = y - h / 2
            rect(self.root, x0 + w / 2, yc, w, h, col, z=-0.01, radius=min(0.45, 0.022 / h))
            t.position = (x0 + 0.015, y - 0.011 - (name_h if named else 0.0), -0.03)
            if named:
                txt(self.root, ellipsize(msg.sender, 18), x0 + 0.015, y - 0.017, 0.34, rgb(120, 170, 255), bold=True,
                    max_w=w - 0.03, z=-0.03)
            stamp = msg.time + ("  ·  Non distribué" if msg.failed else "")
            txt(self.root, stamp, x0 + w - 0.012, y - h + 0.011, 0.3, rgb(220, 220, 228, 170), (0.5, 0), z=-0.03,
                max_w=w - 0.02)
            y -= h + 0.012
        if self.more_above:
            btn(self.root, "Messages précédents", 0, 0.236, 0.17, 0.026, lambda: self._scroll(1), "ph_card", 0.36, z=-0.06)
        if self.scroll > 0:
            btn(self.root, "Récents", 0, -0.27, 0.11, 0.026, lambda: self._scroll(-self.scroll), "ph_card", 0.36, z=-0.06)

    def _render_compose(self):
        y = -0.322
        rect(self.root, 0, y, SW, 0.064, BAR, z=0.0)
        rect(self.root, -0.026, y, 0.3, 0.04, CARD2 if self.composing else CARD, z=-0.005, radius=0.5)
        if self.composing:
            self.field = txt(self.root, self.compose[-30:], -0.165, y, 0.46, TXT, max_w=0.27, z=-0.02)
            self.caret = rect(self.root, -0.165, y, 0.0022, 0.022, GREEN, z=-0.02)
            self._place_caret()
        else:
            txt(self.root, "Message", -0.165, y, 0.46, DIM, z=-0.02)
        hit(self.root, -0.026, y, 0.3, 0.04, self.start_compose, z=-0.03)
        ok = bool(self.compose.strip())
        btn(self.root, "", 0.155, y, 0.04, 0.04, self.send, "ph_green" if ok else "ph_gray", z=-0.03)
        pic(self.root, ptex("glyph", "send", 48), 0.155, y, 0.022, z=-0.05)

    def _place_caret(self):
        if self.field is None or self.caret is None:
            return
        b = text_box(self.field, self.root) if self.compose else None
        self.caret.x = (b[2] + 0.003) if b else -0.165

    def _refresh_field(self):
        """Saisie : met à jour le seul texte du champ (pas de reconstruction de l'écran)."""
        if self.field is None:
            self.render()
            return
        set_txt(self.field, self.compose[-30:])
        self._place_caret()

    def _scroll(self, d):
        if d > 0 and not self.more_above:
            return
        self.scroll = max(0, self.scroll + d)
        self.render()

    def open_conv(self, cid):
        self.conv = cid
        self.page = "thread"
        self.scroll = 0
        self.phone.model.conversations[cid]["unread"] = 0
        self.compose = ""
        self.composing = False
        self.render()
        self.phone.refresh_status(force=True)
        self.game.on_conversation_opened(cid)

    def back(self):
        self.page = "list"
        self.composing = False
        self.render()

    def go_back(self):
        if self.page == "thread":
            self.back()
            return True
        return False

    def start_compose(self):
        if not self.composing:
            self.composing = True
            self.render()

    def stop_compose(self):
        """Quitte la saisie (Échap) sans fermer la conversation.

        Le gestionnaire de jeu l'appelle aussi sur la touche du téléphone (T par défaut) : cette lettre doit
        pouvoir s'écrire dans le message (elle arrive par text_input), on ne quitte donc la saisie que sur Échap."""
        if not _escape_down() and len(str(config.settings.key("telephone"))) == 1:
            return
        if self.composing:
            self.composing = False
            self.render()

    def send(self):
        text = " ".join(self.compose.split())
        if not text:
            return
        if self.conv == "chat" and self.game.is_multiplayer:
            if self.game.net is not None:
                self.game.send_chat(text)
                self.compose = ""
                self.composing = False
                sound.play("envoi", 0.8, channel="voice")
                self.render()
            else:
                sound.play("erreur", 0.8, channel="voice")
                self.phone.toast("Connexion au serveur perdue.")
            return
        # aucun réseau : le message reste affiché, marqué « Non distribué »
        self.phone.model.conversations[self.conv]["msgs"].append(Message(gd.PLAYER_FIRST, text, self.game.state.clock_string(),
                                                                         True, True))
        sound.play("erreur", 0.8, channel="voice")
        self.phone.toast("Échec de l'envoi. Aucun signal.")
        self.compose = ""
        self.composing = False
        self.scroll = 0
        self.render()

    def on_key(self, key):
        if self.page == "thread":
            if key == "scroll up":
                self._scroll(1)
                return
            if key == "scroll down" and self.scroll > 0:
                self._scroll(-1)
                return
        if not self.composing:
            if key == "enter" and self.page == "thread":
                self.start_compose()
            return
        if key in ("backspace", "backspace hold"):
            if self.compose:
                self.compose = self.compose[:-1]
                self._refresh_field()
        elif key == "enter":
            self.send()

    def text_input(self, ch):
        if not self.typing or len(self.compose) >= self.MAX_LEN:
            return
        self.compose += ch
        if len(self.compose) == 1:
            self.render()                      # le bouton d'envoi devient actif
        else:
            self._refresh_field()

    def update(self, dt):
        if self.caret is not None:
            on = int(self.game.player.time * 2.2) % 2 == 0
            if self.caret.enabled != on:
                self.caret.enabled = on


class CameraApp(App):
    name = "camera"
    title = "Appareil photo"

    def on_open(self):
        # Le viseur plein écran est géré par le game manager. On revient à l'accueil d'abord : à la prochaine
        # ouverture, le téléphone n'affiche pas l'écran vide de cette appli.
        self.phone.show_home()
        self.phone.close()
        self.game.enter_camera_mode()


class TorchApp(App):
    name = "lampe"
    title = "Lampe"

    def on_open(self):
        self.render()

    def render(self):
        clear(self.root)
        on = self.phone.model.torch_on
        self.background(rgb(8, 8, 10) if not on else rgb(24, 20, 12))
        self.header("Lampe", accent=AMBER)
        if on:
            pic(self.root, ptex("soft_circle", 256, (255, 214, 120), 150), 0, 0.04, 0.42, z=0.0)
        btn(self.root, "", 0, 0.04, 0.16, 0.16, self.toggle, "ph_amber" if on else "ph_card", z=-0.02, tap=False)
        pic(self.root, ptex("glyph", "torch", 96, (40, 30, 10) if on else (235, 236, 242)), 0, 0.04, 0.07, z=-0.05)
        txt(self.root, "Allumée" if on else "Éteinte", 0, -0.09, 0.8, AMBER if on else TXT, (0, 0), True)
        txt(self.root, "Touchez pour " + ("éteindre" if on else "allumer"), 0, -0.125, 0.42, SUB, (0, 0))
        rect(self.root, 0, -0.25, SW - 0.04, 0.07, CARD, z=0.0, radius=0.25)
        txt(self.root, "Éclairage faible d'appoint. La lampe vide la batterie\nplus vite, même téléphone rangé.", 0, -0.25, 0.38,
            SUB, (0, 0), max_w=SW - 0.07)

    def toggle(self):
        if self.phone.model.dead:
            return
        self.phone.model.torch_on = not self.phone.model.torch_on
        sound.play("tic_interrupteur", 0.6)
        self.render()


class CallsApp(App):
    name = "appels"
    title = "Téléphone"
    KEYS = [("1", ""), ("2", "ABC"), ("3", "DEF"), ("4", "GHI"), ("5", "JKL"), ("6", "MNO"),
            ("7", "PQRS"), ("8", "TUV"), ("9", "WXYZ"), ("*", ""), ("0", "+"), ("#", "")]
    CONTACTS = [("BNR Banque", "Service client · 3200", "Ma banque", (40, 90, 220)),
                ("Mme Duval", "Clairvue Immobilier · 06 12 48 77 31", "Mme Duval", CONTACT_COLORS["duval"]),
                ("Maman", "Mobile · 06 71 22 09 54", "Maman", CONTACT_COLORS["maman"])]

    def __init__(self, phone):
        super().__init__(phone)
        self.number_text = None
        self.reset()

    def reset(self):
        self.number = ""
        self.page = "keypad"
        self.offset = 0

    @property
    def toast_y(self):
        return 0.18 if self.page == "keypad" else -0.35            # clavier : à la place du numéro, loin du bouton d'appel

    def on_open(self):
        self.render()

    def render(self):
        clear(self.root)
        self.number_text = None
        self.background()
        self.header({"keypad": "Clavier", "recent": "Récents", "contacts": "Contacts"}[self.page], accent=GREEN)
        # sélecteur de page
        rect(self.root, 0, 0.256, SW - 0.036, 0.034, CARD, z=0.0, radius=0.4)
        for i, (pid, lbl) in enumerate((("recent", "Récents"), ("contacts", "Contacts"), ("keypad", "Clavier"))):
            x = -0.122 + i * 0.122
            if pid == self.page:
                rect(self.root, x, 0.256, 0.118, 0.028, CARD2, z=-0.005, radius=0.4)
            txt(self.root, lbl, x, 0.256, 0.42, TXT if pid == self.page else SUB, (0, 0), pid == self.page, z=-0.02)
            hit(self.root, x, 0.256, 0.118, 0.03, lambda p=pid: self._page(p))
        getattr(self, "_render_" + self.page)()

    def _render_keypad(self):
        self.number_text = txt(self.root, self.number, 0, 0.18, 1.25, TXT, (0, 0), max_w=SW - 0.06)
        self.hint_text = txt(self.root, "Saisissez un numéro" if not self.number else " ", 0, 0.18, 0.46, DIM, (0, 0))
        for i, (k, letters) in enumerate(self.KEYS):
            x = -0.096 + (i % 3) * 0.096
            y = 0.085 - (i // 3) * 0.087
            btn(self.root, "", x, y, 0.074, 0.074, lambda k=k: self.press(k), "ph_key", z=-0.02, tap=False)
            txt(self.root, k, x, y + (0.007 if letters else 0), 0.95, TXT, (0, 0), z=-0.04)
            if letters:
                txt(self.root, letters, x, y - 0.019, 0.27, SUB, (0, 0), True, z=-0.04)
        btn(self.root, "", 0, -0.27, 0.074, 0.074, self.dial, "ph_green", z=-0.02)
        pic(self.root, ptex("glyph", "phone", 64), 0, -0.27, 0.036, z=-0.05)
        self.erase_btn = btn(self.root, "", 0.096, -0.27, 0.05, 0.05, self.erase, "ph_hit", z=-0.02)
        self.erase_icon = pic(self.root, ptex("glyph", "backspace", 64, (200, 202, 212)), 0.096, -0.27, 0.032, z=-0.05)
        self._sync_erase()

    def _sync_erase(self):
        on = bool(self.number)
        if self.erase_icon.enabled != on:
            self.erase_icon.enabled = on
            self.erase_btn.enabled = on

    def _render_recent(self):
        rows = self.phone.model.call_log[::-1]
        per = 8
        self.offset = max(0, min(self.offset, len(rows) - per))
        y = 0.2
        for name, when, out in rows[self.offset:self.offset + per]:
            txt(self.root, name, -0.178, y + 0.011, 0.5, TXT, bold=True, max_w=0.25)
            txt(self.root, ("Appel sortant" if out else "Appel entrant") + " · " + when, -0.178, y - 0.013, 0.38, SUB, max_w=0.26)
            pic(self.root, ptex("glyph", "phone", 48, (52, 199, 89)), 0.165, y, 0.02)
            rect(self.root, 0, y - 0.031, SW - 0.04, 0.0016, LINE, z=0.0)
            hit(self.root, 0, y, SW - 0.02, 0.058, lambda n=name: self.call_name(n))
            y -= 0.062
        if not rows:
            txt(self.root, "Aucun appel récent", 0, 0.1, 0.5, SUB, (0, 0))

    def _render_contacts(self):
        y = 0.19
        for name, sub, target, col in self.CONTACTS:
            avatar(self.root, name, -0.15, y, 0.05, col)
            txt(self.root, name, -0.113, y + 0.012, 0.52, TXT, bold=True, max_w=0.24)
            txt(self.root, sub, -0.113, y - 0.013, 0.37, SUB, max_w=0.25)
            pic(self.root, ptex("glyph", "phone", 48, (52, 199, 89)), 0.165, y, 0.02)
            rect(self.root, 0.035, y - 0.036, SW - 0.11, 0.0016, LINE, z=0.0)
            hit(self.root, 0, y, SW - 0.02, 0.07, lambda n=target: self.call_name(n))
            y -= 0.074

    def _page(self, p):
        if p != self.page:
            self.page = p
            self.offset = 0
            self.render()

    def press(self, k):
        if len(self.number) < 14:
            self.number += k
            sound.play("tap", 0.8, channel="voice")
            self._refresh_number()

    def erase(self):
        if self.number:
            self.number = self.number[:-1]
            self._refresh_number()

    def _refresh_number(self):
        if self.page != "keypad" or self.number_text is None:
            return
        set_txt(self.number_text, self.number)
        set_txt(self.hint_text, " " if self.number else "Saisissez un numéro")
        self._sync_erase()

    def dial(self):
        n = self.number.replace(" ", "")
        if not n:
            self.phone.toast("Saisissez d'abord un numéro.")
            return
        self.phone.calls.start(n, n)

    def call_name(self, name):
        self.phone.calls.start(name, name)

    def on_key(self, key):
        if self.page == "recent" and key in ("scroll up", "scroll down"):
            old = self.offset
            self.offset = max(0, self.offset + (1 if key == "scroll down" else -1))
            if self.offset != old:
                self.render()
            return
        if self.page != "keypad":
            return
        if len(key) == 1 and key.isdigit():
            self.press(key)
        elif key in ("backspace", "backspace hold"):
            self.erase()
        elif key == "enter":
            self.dial()


# ---------------------------------------------------------------------------
# Gestion des appels
# ---------------------------------------------------------------------------
class CallManager:
    """Machine à états des appels (sonnerie, attente, messages, silence) et écran d'appel."""
    EMERGENCY = ("112", "15", "17", "18", "114", "115", "119", "196")

    def __init__(self, phone):
        self.phone = phone
        self.active = False
        self.stage = None
        self.t = 0.0
        self.name = ""
        self.kind = None
        self.handles = []
        self.script = []
        self.root = Entity(parent=phone.screen_area, enabled=False, z=-0.2)
        self.timer_text = None
        self.status_text = None
        self.caption = None
        self.caption_bg = None
        self.elapsed = 0.0
        self.stage_dur = 0.0
        self._sec = -1

    def start(self, number, name):
        if self.active or self.phone.model.dead:
            return
        low = number.lower()
        bank_numbers = ("ma banque", "bnr banque", "0800123456", "0955550012", "3200")
        pretty = name
        if low in ("ma banque", "bnr banque") or low.replace(" ", "") in bank_numbers:
            kind = "bank"
            pretty = "BNR Banque"
        elif low in ("mme duval",):
            kind = "nosignal"
            pretty = "Mme Duval"
        elif low in ("maman",):
            kind = "nosignal"
            pretty = "Maman"
        elif low.replace(" ", "") in self.EMERGENCY:
            kind = "nosignal"
            pretty = "Urgences " + low.replace(" ", "")
        else:
            kind = "dead"
        self.phone.model.call_log.append((pretty, self.phone.game.state.clock_string(), True))
        self.name = pretty
        self.active = True
        self.elapsed = 0.0
        self.t = 0.0
        self._sec = -1
        self.kind = kind
        game = self.phone.game
        game.quests.on_event("call_started", kind=kind)
        st = game.state
        if kind == "bank":
            n = st.flags.get("bank_calls", 0)
            st.flags["bank_calls"] = n + 1
            if n == 0:
                self.script = [("ring", 6.0), ("hold", 20.0), ("voice", gd.BANK_CALL_ATTEMPTS[0][1], True), ("beep", 1.0), ("end", 0.0)]
            elif n == 1:
                self.script = [("ring", 2.5), ("voice", gd.BANK_CALL_ATTEMPTS[1][1], True), ("beep", 1.0), ("end", 0.0)]
            else:
                self.script = [("silence", 5.0), ("breath", 4.5), ("silence", 1.0), ("end", 0.0)]
        elif kind == "nosignal":
            self.script = [("silence", 1.5), ("voice", "Aucun signal.", False), ("beep", 0.8), ("end", 0.0)]
        else:
            self.script = [("silence", 1.0), ("voice", gd.BANK_CALL_ATTEMPTS[1][1], True), ("beep", 0.8), ("end", 0.0)]
        self._build_ui()
        self.phone.hide_toast()
        self.phone.set_content_visible(False)
        self.stage = None
        self._next_stage()

    def _build_ui(self):
        clear(self.root)
        r = self.root
        r.enabled = True
        pic(r, ptex("phone_wallpaper", px(SW), px(SH)), 0, 0, SW, SH, z=0.02)
        rect(r, 0, 0, SW, SH, rgb(6, 7, 12, 205), z=0.01)
        blocker(r, -0.005)
        if self.kind == "bank":
            pic(r, ptex("app_icon", "banque", 160), 0, 0.205, 0.1, z=-0.01)
        else:
            col = CONTACT_COLORS.get({"Maman": "maman", "Mme Duval": "duval"}.get(self.name, ""), (90, 92, 104))
            avatar(r, self.name if self.kind != "dead" else "?", 0, 0.205, 0.1, col, z=-0.01, size=1.25)
        txt(r, self.name, 0, 0.125, 0.95, TXT, (0, 0), True, max_w=SW - 0.05, z=-0.02)
        self.status_text = txt(r, "Appel…", 0, 0.088, 0.5, SUB, (0, 0), max_w=SW - 0.06, z=-0.02)
        self.timer_text = txt(r, " ", 0, 0.06, 0.5, SUB, (0, 0), z=-0.02)
        self.caption_bg = rect(r, 0, -0.05, SW - 0.05, 0.12, rgb(255, 255, 255, 20), z=-0.01, radius=0.18)
        self.caption = txt(r, " ", 0, -0.05, 0.44, TXT, (0, 0), wrap=36, max_w=SW - 0.08, max_h=0.105, z=-0.02)
        self.caption_bg.enabled = False
        btn(r, "", 0, -0.255, 0.078, 0.078, self.hang_up, "ph_red", z=-0.02, tap=False)
        pic(r, ptex("glyph", "hangup", 64), 0, -0.255, 0.04, z=-0.05)
        txt(r, "Raccrocher", 0, -0.31, 0.38, SUB, (0, 0), z=-0.02)

    def _stop_handles(self):
        for h in self.handles:
            if h:
                h.stop()
        self.handles = []

    def _caption(self, text):
        show = bool(text)
        if self.caption_bg.enabled != show:
            self.caption_bg.enabled = show
        set_txt(self.caption, text or " ")

    def _next_stage(self):
        self._stop_handles()
        if not self.script:
            self.hang_up(silent=True)
            return
        self.stage = self.script.pop(0)
        kind = self.stage[0]
        self.t = 0.0
        if kind == "ring":
            set_txt(self.status_text, "Sonnerie…")
            self.handles.append(sound.loop("sonnerie", 0.8, channel="voice"))
            self.stage_dur = self.stage[1]
        elif kind == "hold":
            set_txt(self.status_text, "En attente…")
            self._caption("♪ Musique d'attente")
            self.handles.append(sound.loop("musique_attente", 0.9, channel="voice"))
            self.stage_dur = self.stage[1]
        elif kind == "voice":
            set_txt(self.status_text, "En ligne")
            txt_ = self.stage[1]
            degraded = self.stage[2]
            # téléphone ouvert : la transcription est déjà sur l'écran d'appel ; le sous-titre du HUD masquerait le
            # bouton « Raccrocher » (il est affiché si le joueur range le téléphone pendant l'appel : voir subtitle_if_voice)
            h = sound.speak(txt_, f0=190, speed=0.9, whisper=False, volume=0.9, channel="voice",
                            distort=degraded, subtitle=not self.phone.is_open, speaker=self.name)
            self.handles.append(h)
            self.stage_dur = 2.2 + 0.075 * len(txt_)
            self._caption("« " + txt_ + " »")
        elif kind == "beep":
            sound.play("bip_fin", 0.9, channel="voice")
            self.stage_dur = self.stage[1]
            set_txt(self.status_text, "Appel terminé")
        elif kind == "breath":
            set_txt(self.status_text, "En ligne")
            self._caption("…")
            self.handles.append(sound.play("respiration_saccadee", 0.9, 0.7, channel="voice"))
            self.stage_dur = self.stage[1]
        elif kind == "silence":
            set_txt(self.status_text, "Appel…" if self.elapsed < 0.5 else "…")
            self.stage_dur = self.stage[1]
        elif kind == "end":
            self.hang_up(silent=True)

    def subtitle_if_voice(self):
        """Téléphone rangé pendant que l'interlocuteur parle : sa phrase passe en sous-titre du HUD."""
        if self.active and self.stage and self.stage[0] == "voice" and config.settings["sous_titres"]:
            self.phone.game._subtitle(self.stage[1], self.name)

    def hang_up(self, silent=False):
        if not self.active:
            return
        self.active = False
        self._stop_handles()
        self.root.enabled = False
        self.phone.hide_toast()
        self.phone.set_content_visible(True)
        if not silent:
            sound.play("bip_fin", 0.6, channel="voice")
        self.phone.game.quests.on_event("call_ended", kind=self.kind)

    def abort(self):
        """Coupure sans événement (nouvelle partie)."""
        if self.active:
            self.phone.set_content_visible(True)
        self.active = False
        self._stop_handles()
        self.script = []
        self.root.enabled = False

    def update(self, dt):
        if not self.active:
            return
        self.elapsed += dt
        self.t += dt
        sec = int(self.elapsed)
        if sec != self._sec:
            self._sec = sec
            m, s = divmod(sec, 60)
            set_txt(self.timer_text, f"{m:02d}:{s:02d}")
        if self.stage and self.t >= self.stage_dur:
            self._next_stage()
        if not self.active:
            return
        self.phone.model.drain(dt, call=True)
        if self.phone.model.dead:
            self.hang_up(silent=True)


class _PhoneInput(Entity):
    """Reçoit les frappes clavier « texte » (caractères réels, disposition AZERTY respectée, accents)."""

    def __init__(self, phone):
        super().__init__()
        self.phone = phone

    def text_input(self, key):
        self.phone.text_input(key)


# ---------------------------------------------------------------------------
# Téléphone (interface)
# ---------------------------------------------------------------------------
class PhoneUI:
    GRID = [("quickeats", "QuickEats"), ("banque", "Banque")]
    DOCK = [("appels", "Téléphone"), ("messages", "Messages"), ("camera", "Photo"), ("lampe", "Lampe")]
    NOTIF_ICONS = {"icone_quickeats": "quickeats", "icone_banque": "banque", "icone_messages": "messages",
                   "icone_appels": "appels", "icone_camera": "camera", "icone_lampe": "lampe", "systeme": "systeme"}

    def __init__(self, game):
        self.game = game
        self.model = PhoneModel(game.state)
        self.is_open = False
        self.frozen_until = 0.0
        self.frozen = False
        self.current = None
        self.apps = {}
        self.vibrate_t = 0.0
        self.notif_queue = []
        self.notif_t = 0.0
        self.notif_data = None
        self.dead_peek = 0.0
        self._status = {}
        self._status_t = 0.0
        self._glitch_t = 0.0
        self._low_warned = set()
        self._move_saved = None
        self._flags_ref = game.state.flags
        self.root = Entity(parent=camera.ui, enabled=False, z=-0.35)
        self.root.y = -1.0
        # textes du téléphone déjà calibrés (max_w) : pas d'ajustement automatique toutes les 4 images (coûteux,
        # et il rétrécissait à vie les textes pendant l'animation d'entrée, quand ils sortent de l'écran)
        self.root.audit_skip = True
        self._input = _PhoneInput(self)
        self._build_frame()
        self.calls = CallManager(self)
        self._build_toast()
        self._build_overlays()
        self._build_notification()
        self._build_apps()
        self.show_home()

    # --- construction -----------------------------------------------------
    def _build_frame(self):
        r = self.root
        gw, gh = BODY_W + 0.14, BODY_H + 0.14
        self.glow = pic(r, ptex("phone_glow", px(gw), px(gh), (px(BODY_W), px(BODY_H))), 0, 0, gw, gh, z=0.2)
        self.frame = pic(r, ptex("phone_frame", px(BODY_W), px(BODY_H), px(SW), px(SH), 58, 40), 0, 0, BODY_W, BODY_H, z=-0.45)
        self.screen_area = Entity(parent=r, z=0)
        self.screen_bg = rect(self.screen_area, 0, 0, SW, SH, rgb(0, 0, 0), z=0.1)
        self.home = Entity(parent=self.screen_area, z=0.05)
        self._build_home()
        self._build_status()
        # indicateur d'accueil (barre en bas) : retour à l'écran d'accueil
        self.nav = Entity(parent=self.screen_area, z=-0.26)
        self.home_bar = rect(self.nav, 0, -0.377, 0.12, 0.0055, rgb(255, 255, 255, 200), z=0, radius=0.5)
        hit(self.nav, 0, -0.374, 0.2, 0.026, self._home_button, z=-0.01, tap=False)

    def _build_status(self):
        s = self.status = Entity(parent=self.screen_area, z=-0.25)
        y = 0.368
        self.time_text = txt(s, "21:40", -0.122, y, 0.52, TXT, (0, 0), True)
        rect(s, 0, y, 0.094, 0.026, rgb(0, 0, 0), z=0, radius=0.5)                      # îlot de la caméra
        rect(s, 0.028, y, 0.009, 0.009, rgb(20, 24, 40), z=-0.005, radius=0.5)
        self.signal_bars = []
        for i in range(4):
            h = 0.006 + i * 0.003
            self.signal_bars.append(rect(s, 0.066 + i * 0.0085, y - 0.0075 + h / 2, 0.0055, h,
                                         TXT if i < self.model.signal else rgb(255, 255, 255, 70), z=0))
        self.battery_text = txt(s, "100", 0.137, y, 0.36, TXT, (0.5, 0), True)
        rect(s, 0.16, y, 0.034, 0.0165, rgb(255, 255, 255, 120), z=0, radius=0.3)
        rect(s, 0.16, y, 0.031, 0.0135, rgb(0, 0, 0), z=-0.002, radius=0.3)
        rect(s, 0.1785, y, 0.0025, 0.006, rgb(255, 255, 255, 120), z=0)
        self.battery_fill = rect(s, 0.1462, y, 0.0276, 0.0105, TXT, z=-0.004)
        self.battery_fill.origin = (-0.5, 0)

    def _build_home(self):
        h = self.home
        pic(h, ptex("phone_wallpaper", px(SW), px(SH)), 0, 0, SW, SH, z=0.04)
        self.date_text = txt(h, "vendredi 13 octobre", 0, 0.318, 0.55, rgb(235, 236, 245, 220), (0, 0), True)
        self.clock_big = txt(h, "21:40", 0, 0.255, 3.1, rgb(240, 242, 250, 235), (0, 0))
        # widget météo
        wy = 0.118
        rect(h, 0, wy, SW - 0.04, 0.1, rgb(255, 255, 255, 30), z=0.01, radius=0.22)
        txt(h, "Nice · Mont-Boron", -0.165, wy + 0.03, 0.42, TXT, bold=True, max_w=0.2)
        txt(h, "11°", -0.165, wy - 0.012, 1.6, TXT)
        pic(h, ptex("glyph", "rain", 64, (235, 238, 248)), 0.15, wy + 0.026, 0.03)
        txt(h, "Averses", 0.165, wy - 0.008, 0.42, TXT, (0.5, 0), True)
        txt(h, "Max 14°  Min 9°", 0.165, wy - 0.032, 0.36, rgb(220, 222, 232, 200), (0.5, 0))
        self.badges = {}
        self.icons = {}
        cols = [-0.135, -0.045, 0.045, 0.135]
        for i, (aid, name) in enumerate(self.GRID):
            self._app_icon(aid, name, cols[i], -0.0, True)
        rect(h, 0, -0.312, SW - 0.03, 0.092, rgb(255, 255, 255, 34), z=0.01, radius=0.3)
        for i, (aid, name) in enumerate(self.DOCK):
            self._app_icon(aid, name, cols[i], -0.312, False)

    def _app_icon(self, aid, name, x, y, with_label):
        icon = pic(self.home, ptex("app_icon", aid, 160), x, y, 0.07, z=-0.01)
        self.icons[aid] = icon
        hit(self.home, x, y, 0.075, 0.075, lambda a=aid: self.open_app(a), z=-0.03, tap=False)
        if with_label:
            txt(self.home, name, x, y - 0.051, 0.38, TXT, (0, 0), max_w=0.088)
        b = badge(self.home, 1, x + 0.031, y + 0.031)
        b.enabled = False
        self.badges[aid] = [b, 0]

    def _build_apps(self):
        from delivery_app import DeliveryApp
        from bank_app import BankApp
        self.apps["quickeats"] = DeliveryApp(self)
        self.apps["banque"] = BankApp(self)
        self.apps["messages"] = MessagesApp(self)
        self.apps["camera"] = CameraApp(self)
        self.apps["lampe"] = TorchApp(self)
        self.apps["appels"] = CallsApp(self)

    def _build_toast(self):
        self._toast = Entity(parent=self.screen_area, z=-0.3, enabled=False)
        rect(self._toast, 0, 0, SW - 0.05, 0.05, rgb(52, 54, 66, 250), z=0, radius=0.5)
        self._toast_text = txt(self._toast, " ", 0, 0, 0.44, TXT, (0, 0), max_w=SW - 0.09, max_h=0.042, z=-0.01)
        self._toast_t = 0.0
        # bande sombre sous les sous-titres du HUD quand ils passent devant l'écran du téléphone
        self._sub_strip = rect(self.screen_area, 0, -0.3, SW, 0.07, rgb(0, 0, 0, 185), z=-0.42)
        self._sub_strip.enabled = False

    def _build_overlays(self):
        # écran figé / parasité (livraison effectuée)
        f = self._freeze = Entity(parent=self.screen_area, z=-0.4, enabled=False)
        rect(f, 0, 0, SW, SH, rgb(0, 0, 0), z=0)
        self._glitch_bars = [rect(f, 0, 0, SW, 0.01, rgb(255, 255, 255, 40), z=-0.01) for _ in range(7)]
        self._glitch_text = txt(f, "Livraison effectuée.", 0, 0.0, 0.62, rgb(230, 60, 50), (0, 0), True, z=-0.02)
        blocker(f, -0.03)
        # batterie épuisée
        d = self._dead = Entity(parent=self.screen_area, z=-0.4, enabled=False)
        rect(d, 0, 0, SW, SH, rgb(0, 0, 0), z=0)
        pic(d, ptex("glyph", "battery_dead", 128, (230, 60, 50)), 0, 0.03, 0.1, z=-0.01)
        txt(d, "Batterie épuisée", 0, -0.04, 0.48, rgb(160, 160, 170), (0, 0), z=-0.01)
        blocker(d, -0.03)

    def _build_notification(self):
        n = self.notif = Entity(parent=camera.ui, z=-4, enabled=False)
        n.audit_skip = True
        rect(n, 0, 0, SW - 0.028, 0.082, rgb(34, 36, 45, 248), z=0, radius=0.26)
        self.notif_icon = pic(n, ptex("app_icon", "messages", 96), -0.15, 0, 0.044, z=-0.01)
        self.notif_title = txt(n, " ", -0.118, 0.022, 0.44, TXT, bold=True, max_w=0.2, z=-0.01)
        txt(n, "maintenant", 0.17, 0.022, 0.32, SUB, (0.5, 0), z=-0.01)
        self.notif_l1 = txt(n, " ", -0.118, -0.004, 0.4, rgb(220, 222, 230), max_w=0.29, z=-0.01)
        self.notif_l2 = txt(n, " ", -0.118, -0.026, 0.4, rgb(220, 222, 230), max_w=0.29, z=-0.01)
        hit(n, 0, 0, SW - 0.028, 0.082, self.on_notif_click, z=-0.02)

    # --- partie neuve -------------------------------------------------------
    def _sync_session(self):
        """Nouvelle partie / chargement / « Réessayer » : l'état du jeu a été remis à zéro → le téléphone aussi."""
        if self.game.state.flags is not self._flags_ref:
            self._flags_ref = self.game.state.flags
            self.reset()

    def reset(self):
        self.calls.abort()
        self.model.reset_from_state()
        self.model.dead = self.model.battery <= 0
        for app in self.apps.values():
            app.reset()
        self.notif_queue = []
        self.notif_t = 0.0
        self.notif.enabled = False
        self.frozen = False
        self._freeze.enabled = False
        self._toast.enabled = False
        self._low_warned = set()
        if self.current is not None:
            self.apps[self.current].root.enabled = False
        self.current = None
        self.home.enabled = True
        self._status = {}

    # --- ouverture / fermeture -------------------------------------------
    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self):
        self._sync_session()
        if self.is_open:
            return
        self.is_open = True
        self.root.enabled = True
        self.root.y = -0.95
        self.root.animate_y(PHONE_Y, duration=0.3, curve=curve.out_cubic)
        self.game.player.phone_open = True
        mouse.locked = False
        mouse.visible = True
        self._set_reticle(False)
        if self.model.dead:
            # écran noir et batterie vide un instant, puis le téléphone est rangé
            self._dead.enabled = True
            self.dead_peek = 1.4
            self.game.say("Le téléphone est éteint.")
            return
        self._dead.enabled = False
        if self.notif.enabled and self.frozen:
            # écran figé : la bannière en cours attendra la fin du gel
            if self.notif_data is not None:
                self.notif_queue.insert(0, self.notif_data)
            self._hide_notif()
        elif self.notif.enabled:
            # bannière déjà affichée en haut de l'écran : elle rejoint l'écran du téléphone
            self._place_notif(True)
        self.game.state.phone_used = True
        self.game.on_phone_opened()
        sound.play("tic_interrupteur", 0.5)
        if self.current is None:
            self.show_home()
        elif self.current in self.apps:
            self.apps[self.current].on_open()
        self.refresh_status(force=True)

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        self.dead_peek = 0.0
        self.calls.subtitle_if_voice()
        if self.current is not None and self.current in self.apps:
            self.apps[self.current].on_close()
        self._apply_typing(False)
        if self.notif.enabled:
            # bannière affichée dans l'écran : elle remonte en haut de l'écran de jeu (sinon elle flotterait seule)
            self._place_notif(False)
        self.root.animate_y(-0.95, duration=0.2, curve=curve.in_cubic)
        invoke(self._hide_root, delay=0.21)
        self.game.player.phone_open = False
        self._set_reticle(True)
        self.game.on_phone_closed()

    def _hide_root(self):
        if not self.is_open:
            self.root.enabled = False

    def _set_reticle(self, on):
        try:
            self.game.ui.hud.reticle.enabled = on
        except Exception:
            pass

    def show_home(self):
        self.hide_toast()
        if self.current is not None and self.current in self.apps:
            self.apps[self.current].on_close()
            self.apps[self.current].root.enabled = False
        self.current = None
        self.home.enabled = True
        if self.is_open:
            self.home.scale = 1.04
            self.home.animate_scale(1.0, duration=0.18, curve=curve.out_cubic)
        self.refresh_status(force=True)

    def _home_button(self):
        """Barre d'accueil (bas de l'écran) : sans effet pendant un appel ou quand l'écran est figé."""
        if not (self.calls.active or self.frozen or self.model.dead):
            self.show_home()

    def set_content_visible(self, on):
        """Écran d'accueil / appli courante (masqués pendant un appel)."""
        target = self.apps[self.current].root if self.current is not None else self.home
        if target.enabled != on:
            target.enabled = on

    def back(self):
        if self.calls.active or self.frozen:
            return
        if self.current is not None:
            app = self.apps[self.current]
            if hasattr(app, "go_back") and app.go_back():
                return
        self.show_home()

    def open_app(self, aid):
        if self.frozen or self.model.dead or self.calls.active or aid not in self.apps:
            return
        if self.current is not None and self.current != aid:
            self.apps[self.current].on_close()
            self.apps[self.current].root.enabled = False
        self.hide_toast()
        self.current = aid
        self.home.enabled = False
        app = self.apps[aid]
        app.root.enabled = True
        app.root.scale = 0.94
        app.root.animate_scale(1.0, duration=0.18, curve=curve.out_cubic)
        sound.play("tap", 0.8)
        self.game.quests.on_event("app_opened", app=aid)
        app.on_open()

    # --- notifications ----------------------------------------------------
    def notify(self, title, text, icon="icone_messages", target=None, sound_on=True, level=None):
        self._sync_session()
        self.notif_queue.append(dict(title=title, text=text, icon=icon, target=target, level=level))
        del self.notif_queue[:-4]
        if sound_on and not self.model.dead:          # un téléphone éteint ne vibre pas
            sound.play("vibration", 0.9, channel="voice")
            sound.play("notification", 0.8, channel="voice")
            self.vibrate_t = 0.6
            self.game.on_phone_notification()

    def _show_next_notif(self):
        if not self.notif_queue:
            return
        d = self.notif_queue.pop(0)
        if d.get("level") is not None and self.model.battery > d["level"] + 1:
            return                                   # alerte batterie périmée (téléphone rechargé entre-temps)
        self.notif_data = d
        set_txt(self.notif_title, d["title"])
        lines = _wrap(" ".join(d["text"].split()), 44)
        if len(lines) > 2:
            lines = [lines[0], ellipsize(lines[1] + " " + lines[2], 44)]
        set_txt(self.notif_l1, lines[0])
        set_txt(self.notif_l2, lines[1] if len(lines) > 1 else " ")
        icon = d["icon"]
        if icon in self.NOTIF_ICONS:
            self.notif_icon.texture = ptex("app_icon", self.NOTIF_ICONS[icon], 96)
        else:
            self.notif_icon.texture = textures.get(icon) if icon else ptex("app_icon", "systeme", 96)
        self.notif.enabled = True
        self.notif.y = (PHONE_Y + 0.3 if self.is_open else 0.447) + 0.12
        self._place_notif(self.is_open, 0.28)
        self.notif_t = 4.5

    def _place_notif(self, in_phone, duration=0.15):
        """Bannière dans l'écran du téléphone (ouvert) ou en haut de l'écran de jeu (rangé).

        Toujours par une animation : elle remplace celle d'arrivée en cours (une affectation directe de y serait
        écrasée par l'animation encore active et la bannière resterait au mauvais endroit)."""
        n = self.notif
        n.scale = 1.0 if in_phone else 1.05
        n.x = 0
        ty = PHONE_Y + 0.3 if in_phone else 0.447        # rangé : au-dessus du bandeau d'objectif du HUD
        n.animate_y(ty, duration=duration, curve=curve.out_cubic)

    def _hide_notif(self):
        self.notif_t = 0.0
        self.notif.enabled = False

    def on_notif_click(self):
        d = self.notif_data
        if d is None:
            return
        self.notif.enabled = False
        self.notif_t = 0
        if self.model.dead:
            return
        if not self.is_open:
            self.open()
            if not self.is_open:
                return
        if self.calls.active or self.frozen:
            return
        tgt = d.get("target")
        if tgt:
            self.open_app(tgt[0])
            if len(tgt) > 1 and hasattr(self.apps[tgt[0]], "open_conv"):
                self.apps[tgt[0]].open_conv(tgt[1])

    # --- divers ----------------------------------------------------------
    def toast(self, text, duration=2.4):
        set_txt(self._toast_text, text)
        self._toast.y = self._toast_y()
        self._toast.enabled = True
        self._toast_t = duration

    def _toast_y(self):
        """Hauteur du message éphémère : jamais devant les boutons de l'écran affiché (appel, raccrocher, valider...)."""
        if self.calls.active:
            return -0.17                     # entre la transcription et le bouton « Raccrocher »
        if self.current is None:
            return -0.215                    # au-dessus du dock
        return self.apps[self.current].toast_y

    def hide_toast(self):
        """Changement d'écran : le message éphémère de l'écran précédent disparaît."""
        self._toast_t = 0.0
        if self._toast.enabled:
            self._toast.enabled = False

    def freeze(self, seconds):
        self.frozen = True
        self.frozen_until = seconds
        self.show_home()
        self._freeze.enabled = True
        if self.is_open and self.notif.enabled:
            # écran figé : les bannières attendent la fin du gel (voir update)
            if self.notif_data is not None:
                self.notif_queue.insert(0, self.notif_data)
            self._hide_notif()

    def _update_freeze(self, dt):
        self.frozen_until -= dt
        if self.frozen_until <= 0:
            self.frozen = False
            self._freeze.enabled = False
            return
        if not self.is_open:
            return
        self._glitch_t -= dt
        if self._glitch_t > 0:
            return
        self._glitch_t = 0.07
        for b in self._glitch_bars:
            b.y = random.uniform(-SH / 2 + 0.02, SH / 2 - 0.02)
            b.scale_y = random.uniform(0.002, 0.03)
            b.scale_x = random.uniform(0.2, 1.0) * SW
            b.x = random.uniform(-1, 1) * (SW - b.scale_x) / 2
            b.color = rgb(random.choice((255, 200, 120)), random.randint(20, 90), random.randint(20, 90), random.randint(20, 110))
        show = random.random() < 0.55
        if self._glitch_text.enabled != show:
            self._glitch_text.enabled = show
        self._glitch_text.x = random.uniform(-0.006, 0.006)

    def refresh_status(self, force=False):
        """Barre d'état et pastilles. Chaque texte n'est réassigné que si sa valeur a changé."""
        st = self._status
        if force:
            st.clear()
        clock = self.game.state.clock_string()
        if st.get("clock") != clock:
            st["clock"] = clock
            set_txt(self.time_text, clock)
            set_txt(self.clock_big, clock)
        b = int(math.ceil(self.model.battery))
        if st.get("bat") != b:
            st["bat"] = b
            self.battery_fill.scale_x = max(0.001, 0.0276 * b / 100.0)
            self.battery_fill.color = TXT if b > 20 else RED
            set_txt(self.battery_text, str(b))
        unread = sum(c["unread"] for c in self.model.conversations.values() if not (c.get("hidden") and not self.game.is_multiplayer))
        self._set_badge("messages", unread)
        self._set_badge("banque", 1 if self._bank_alert() else 0)

    def _bank_alert(self):
        """Pastille sur l'appli banque : un paiement a été refusé et le joueur n'a pas encore vérifié son compte."""
        st = self.game.state
        q = self.game.quests.quests.get("comprendre")
        return bool(st.flag("order_cancelled") and q is not None and not q.complete and "bank" not in q.done_steps)

    def _set_badge(self, aid, n):
        b = self.badges.get(aid)
        if b is None or b[1] == n:
            return
        b[1] = n
        b[0].enabled = n > 0
        if n > 0:
            set_txt(b[0].children[1], str(n) if n < 10 else "9+")

    def on_key(self, key):
        if not self.is_open or self.model.dead:
            return
        if key == "right mouse down":
            self.back()
            return
        if self.calls.active or self.frozen:
            return
        if self.current is not None:
            self.apps[self.current].on_key(key)

    def text_input(self, ch):
        if not self.is_open or self.current is None or self.calls.active or self.frozen or self.model.dead:
            return
        if self.game.paused:
            return
        self.apps[self.current].text_input(ch)

    def _apply_typing(self, typing):
        """Pendant une saisie (adresse, message), les touches ZQSD écrivent au lieu de faire marcher le joueur."""
        p = self.game.player
        if typing and self._move_saved is None:
            self._move_saved = p.move_enabled
            p.move_enabled = False
        elif not typing and self._move_saved is not None:
            p.move_enabled = self._move_saved
            self._move_saved = None

    def update(self, dt):
        self._sync_session()
        if self._toast_t > 0:
            self._toast_t -= dt
            if self._toast_t <= 0:
                self._toast.enabled = False
        self.calls.update(dt)
        for app in self.apps.values():
            app.tick(dt)
        if self.frozen:
            self._update_freeze(dt)
        # batterie
        qe_open = self.is_open and self.current == "quickeats"
        was_dead = self.model.dead
        if not self.calls.active and not was_dead:
            # viseur de l'appareil photo : écran allumé, même consommation que téléphone sorti
            self.model.drain(dt, quickeats=qe_open, open_=self.is_open or self.game.camera_mode)
        if self.model.dead and not was_dead:
            self._on_battery_dead()
        b = self.model.battery
        for lvl in (20, 10):
            if b <= lvl and lvl not in self._low_warned and not self.model.dead:
                self._low_warned.add(lvl)
                self.notify("Batterie faible", f"Il reste {lvl} % de batterie.", "systeme", sound_on=True, level=lvl)
            elif b > lvl + 5:
                self._low_warned.discard(lvl)
        if self.is_open and self.model.dead:
            if not self._dead.enabled:
                self._dead.enabled = True
                self.dead_peek = 1.2
            self.dead_peek -= dt
            if self.dead_peek <= 0:
                self.close()
        elif self._dead.enabled and not self.model.dead:
            self._dead.enabled = False
        # notifications
        if self.notif_t > 0:
            self.notif_t -= dt
            if self.notif_t <= 0:
                self.notif.enabled = False
        elif self.notif_queue and not self.model.dead and not (self.frozen and self.is_open):
            self._show_next_notif()
        # vibration : l'objet tremble
        if self.vibrate_t > 0:
            self.vibrate_t -= dt
            if self.is_open:
                self.root.x = math.sin(self.game.player.time * 90.0) * 0.004
        elif self.root.x != 0.0:
            self.root.x = 0.0
        typing = bool(self.is_open and self.current is not None and self.apps[self.current].typing and not self.calls.active)
        self._apply_typing(typing)
        if self.is_open:
            self._update_sub_strip()
            self.glow.alpha = 0.85 + 0.15 * math.sin(self.game.player.time * 2.2)
            self._status_t -= dt
            if self._status_t <= 0:
                self._status_t = 0.5
                self.refresh_status()
            if self.current is not None and not self.model.dead:
                self.apps[self.current].update(dt)

    def _update_sub_strip(self):
        try:
            hud = self.game.ui.hud
            # le HUD place ses sous-titres à côté du téléphone quand il est sorti : la bande ne sert que s'ils
            # passent encore devant l'écran
            on = hud.sub_t > 0 and bool(str(hud.sub.text).strip()) and not getattr(hud, "_sub_side", False)
        except Exception:
            return
        if on:
            # bande à la taille du sous-titre (et non toute la largeur de l'écran : elle assombrissait à moitié le
            # dock ou les boutons pour un simple « ... »), avec le même fondu que le fond du sous-titre du HUD
            bg = hud.sub_bg
            self._sub_strip.y = bg.y - self.root.y
            self._sub_strip.scale = (min(SW, float(bg.scale_x)), float(bg.scale_y))
            self._sub_strip.color = rgb(0, 0, 0, int(200 * max(0.0, min(1.0, hud.sub_t / 0.5))))
        if self._sub_strip.enabled != on:
            self._sub_strip.enabled = on

    def _on_battery_dead(self):
        self._hide_notif()                     # écran éteint : la bannière en cours disparaît aussi
        self.calls.hang_up(silent=True)
        if self.game.camera_mode:
            self.game.exit_camera_mode()          # plus d'écran, plus de viseur
            self.game.say("Le téléphone est éteint.", voice=False)
        self.model.torch_on = False
        if self.current == "lampe" and self.is_open:
            self.apps["lampe"].render()
