"""Système de téléphone in-game : interface, écran d'accueil, notifications, appels,
applications Messages / Appareil photo / Lampe / Appels. QuickEats et la banque sont dans
delivery_app.py et bank_app.py.
"""
import math

from ursina import Entity, color, camera, mouse, curve

import config
import game_data as gd
from sound_engine import engine as sound
from texture_generator import textures
from ui_widgets import label, rect, button, clear, rgb, Toast

SW, SH = 0.40, 0.78           # taille de l'écran
PHONE_Y = -0.03


class Message:
    def __init__(self, sender, text, time_str, mine=False):
        self.sender, self.text, self.time, self.mine = sender, text, time_str, mine


class PhoneModel:
    """Données du téléphone (messages, historique d'appels, batterie, signal)."""

    def __init__(self, state):
        self.state = state
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
        self.call_log = [("Maman", "hier 12:03", False), ("Mme Duval", "hier 17:40", False)]
        self.battery = 100.0
        self.signal = 1
        self.torch_on = False
        self.dead = False

    def add_message(self, conv, sender, text, mine=False):
        c = self.conversations[conv]
        t = self.state.clock_string()
        c["msgs"].append(Message(sender, text, t, mine))
        if not mine:
            c["unread"] += 1
        self.state.messages.append((conv, sender, text, t))
        return c

    def drain(self, dt, quickeats=False, call=False, open_=False):
        rate = config.PHONE_DRAIN
        if quickeats:
            rate = config.PHONE_DRAIN_QUICKEATS
        if call:
            rate = config.PHONE_DRAIN_CALL
        if self.torch_on:
            rate += 0.1
        self.battery = max(0.0, self.battery - rate * dt)
        self.state.player_battery_phone = self.battery
        if self.battery <= 0:
            self.dead = True

    def charge(self, amount):
        self.battery = min(100.0, self.battery + amount)
        if self.battery > 0:
            self.dead = False


# ---------------------------------------------------------------------------
# Applications simples
# ---------------------------------------------------------------------------
class App:
    name = "app"
    title = "App"

    def __init__(self, phone):
        self.phone = phone
        self.game = phone.game
        self.root = Entity(parent=phone.screen_area, enabled=False)

    def on_open(self):
        pass

    def on_close(self):
        pass

    def update(self, dt):
        pass

    def on_key(self, key):
        pass


class MessagesApp(App):
    name = "messages"
    title = "Messages"

    def __init__(self, phone):
        super().__init__(phone)
        self.page = "list"
        self.conv = None
        self.scroll = 0
        self.compose = ""
        self.composing = False
        self.toast = None

    def on_open(self):
        self.render()

    def render(self):
        clear(self.root)
        m = self.phone.model
        if self.page == "list":
            rect(self.root, 0, 0.30, SW, 0.06, rgb(24, 24, 28))
            label(self.root, "Messages", -0.17, 0.3, 1.0, color.white, origin=(-0.5, 0))
            y = 0.2
            for cid, c in m.conversations.items():
                if c.get("hidden") and not self.game.is_multiplayer:
                    continue
                last = c["msgs"][-1].text if c["msgs"] else ""
                last = (last[:34] + "...") if len(last) > 34 else last
                button(self.root, "", 0, y, SW - 0.02, 0.1, lambda cid=cid: self.open_conv(cid), rgb(34, 34, 40, 235))
                label(self.root, c["name"], -0.17, y + 0.022, 0.8, color.white, origin=(-0.5, 0), z=-0.05)
                label(self.root, last, -0.17, y - 0.02, 0.5, color.gray, origin=(-0.5, 0), z=-0.05)
                if c["unread"]:
                    rect(self.root, 0.165, y + 0.02, 0.035, 0.035, rgb(60, 190, 80), z=-0.05)
                    label(self.root, str(c["unread"]), 0.165, y + 0.02, 0.5, color.white, z=-0.06)
                y -= 0.115
        else:
            c = m.conversations[self.conv]
            rect(self.root, 0, 0.30, SW, 0.06, rgb(24, 24, 28))
            button(self.root, "‹", -0.17, 0.3, 0.05, 0.045, self.back, rgb(50, 50, 56), size=0.9)
            label(self.root, c["name"], -0.1, 0.3, 0.9, color.white, origin=(-0.5, 0))
            # bulles : on affiche les dernières qui tiennent
            msgs = c["msgs"]
            layout = []
            for msg in msgs:
                lines = _wrap(msg.text, 27)
                h = 0.04 + 0.024 * len(lines)
                layout.append((msg, lines, h))
            total = 0.0
            visible = []
            limit = 0.58
            for item in reversed(layout[:len(layout) - self.scroll] if self.scroll else layout):
                if total + item[2] + 0.015 > limit:
                    break
                visible.append(item)
                total += item[2] + 0.015
            y = 0.25
            for msg, lines, h in reversed(visible):
                x0 = 0.18 - 0.28 if not msg.mine else 0.02
                bgc = rgb(52, 120, 64) if msg.mine else rgb(58, 58, 66)
                rect(self.root, x0 + 0.13, y - h / 2, 0.27, h, bgc)
                for i, ln in enumerate(lines):
                    label(self.root, ln, x0 + 0.005, y - 0.022 - i * 0.024, 0.52, color.white, origin=(-0.5, 0), z=-0.03)
                label(self.root, msg.time, x0 + (0.255 if msg.mine else 0.255), y - h + 0.012, 0.32, rgb(200, 200, 200), origin=(0.5, 0), z=-0.03)
                y -= h + 0.015
            if self.scroll < len(layout) - 1:
                button(self.root, "^", 0.17, 0.25, 0.04, 0.04, lambda: self._scroll(1), rgb(60, 60, 66), size=0.7)
            if self.scroll > 0:
                button(self.root, "v", 0.17, -0.25, 0.04, 0.04, lambda: self._scroll(-1), rgb(60, 60, 66), size=0.7)
            # zone de saisie
            rect(self.root, 0, -0.31, SW - 0.02, 0.06, rgb(30, 30, 36))
            txt = self.compose if self.composing else "Écrire un message..."
            label(self.root, txt[-34:], -0.17, -0.31, 0.55, color.white if self.composing else color.gray, origin=(-0.5, 0))
            button(self.root, "", 0, -0.31, SW - 0.14, 0.06, self.start_compose, rgb(30, 30, 36, 1))
            button(self.root, "Envoyer", 0.145, -0.31, 0.09, 0.05, self.send, rgb(52, 130, 70), size=0.55)

    def _scroll(self, d):
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
        self.game.on_conversation_opened(cid)

    def back(self):
        self.page = "list"
        self.composing = False
        self.render()

    def start_compose(self):
        self.composing = True
        self.render()

    def send(self):
        text = self.compose.strip()
        if self.conv == "chat" and self.game.is_multiplayer:
            if text:
                self.game.send_chat(text)
                self.compose = ""
                sound.play("envoi", 0.8, channel="voice")
                self.render()
            return
        sound.play("erreur", 0.8, channel="voice")
        self.phone.toast("Échec de l'envoi. Aucun signal.")
        self.compose = ""
        self.render()

    def on_key(self, key):
        if not self.composing:
            return
        if key == "backspace":
            self.compose = self.compose[:-1]
        elif key == "enter":
            self.send()
            return
        elif key == "space":
            self.compose += " "
        elif len(key) == 1:
            self.compose += key
        self.render()


class CameraApp(App):
    name = "camera"
    title = "Appareil photo"

    def on_open(self):
        # Le viseur plein écran est géré par le game manager
        self.phone.close()
        self.game.enter_camera_mode()


class TorchApp(App):
    name = "lampe"
    title = "Lampe"

    def __init__(self, phone):
        super().__init__(phone)
        self.btn = None

    def on_open(self):
        self.render()

    def render(self):
        clear(self.root)
        on = self.phone.model.torch_on
        rect(self.root, 0, 0, SW, SH, rgb(18, 18, 22))
        label(self.root, "Lampe du téléphone", 0, 0.28, 0.95, color.white)
        button(self.root, "ALLUMÉE" if on else "ÉTEINTE", 0, 0.0, 0.22, 0.22, self.toggle,
                   rgb(240, 200, 40) if on else rgb(60, 60, 66), color.black if on else color.white, size=0.9)
        label(self.root, "Éclairage faible d'appoint", 0, -0.2, 0.55, color.gray)

    def toggle(self):
        self.phone.model.torch_on = not self.phone.model.torch_on
        sound.play("tic_interrupteur", 0.6)
        self.render()


class CallsApp(App):
    name = "appels"
    title = "Appels"

    def __init__(self, phone):
        super().__init__(phone)
        self.number = ""
        self.page = "keypad"

    def on_open(self):
        self.render()

    def render(self):
        clear(self.root)
        m = self.phone.model
        rect(self.root, 0, 0.30, SW, 0.06, rgb(24, 24, 28))
        label(self.root, "Appels", -0.17, 0.3, 1.0, color.white, origin=(-0.5, 0))
        button(self.root, "Clavier", 0.02, 0.3, 0.1, 0.04, lambda: self._page("keypad"), rgb(50, 50, 56), size=0.5)
        button(self.root, "Récents", 0.13, 0.3, 0.1, 0.04, lambda: self._page("recent"), rgb(50, 50, 56), size=0.5)
        if self.page == "recent":
            y = 0.2
            for name, when, out in m.call_log[-7:][::-1]:
                rect(self.root, 0, y, SW - 0.02, 0.07, rgb(34, 34, 40))
                label(self.root, name, -0.17, y + 0.012, 0.75, color.white, origin=(-0.5, 0), z=-0.03)
                label(self.root, ("Sortant — " if out else "Entrant — ") + when, -0.17, y - 0.02, 0.45, color.gray, origin=(-0.5, 0), z=-0.03)
                button(self.root, "Appeler", 0.14, y, 0.09, 0.04, lambda n=name: self.call_name(n), rgb(40, 140, 60), size=0.45)
                y -= 0.08
            # contacts
            label(self.root, "Contacts", -0.17, y - 0.02, 0.6, rgb(200, 190, 150), origin=(-0.5, 0))
            y -= 0.07
            for name in ("Ma banque", "Mme Duval", "Maman"):
                button(self.root, name, 0, y, SW - 0.04, 0.05, lambda n=name: self.call_name(n), rgb(44, 44, 52), size=0.6)
                y -= 0.058
        else:
            rect(self.root, 0, 0.2, SW - 0.04, 0.07, rgb(14, 14, 18))
            label(self.root, self.number or "Composer un numéro", 0, 0.2, 0.9, color.white if self.number else color.gray)
            keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"]
            for i, k in enumerate(keys):
                x = -0.11 + (i % 3) * 0.11
                y = 0.1 - (i // 3) * 0.095
                button(self.root, k, x, y, 0.09, 0.08, lambda k=k: self.press(k), rgb(46, 46, 54), size=0.9)
            button(self.root, "Appeler", 0.0, -0.3, 0.2, 0.06, self.dial, rgb(40, 160, 70), size=0.8)
            button(self.root, "‹", 0.15, -0.3, 0.06, 0.06, self.erase, rgb(90, 50, 50), size=0.8)

    def _page(self, p):
        self.page = p
        self.render()

    def press(self, k):
        if len(self.number) < 14:
            self.number += k
            sound.play("tap", 0.8, channel="voice")
        self.render()

    def erase(self):
        self.number = self.number[:-1]
        self.render()

    def dial(self):
        n = self.number.replace(" ", "")
        if not n:
            return
        self.phone.calls.start(n, n)

    def call_name(self, name):
        self.phone.calls.start(name, name)

    def on_key(self, key):
        if self.page != "keypad":
            return
        if key.isdigit() and len(key) == 1:
            self.press(key)
        elif key == "backspace":
            self.erase()
        elif key == "enter":
            self.dial()


# ---------------------------------------------------------------------------
# Gestion des appels
# ---------------------------------------------------------------------------
class CallManager:
    """Machine à états des appels (sonnerie, attente, messages, silence)."""

    def __init__(self, phone):
        self.phone = phone
        self.active = False
        self.stage = None
        self.t = 0.0
        self.name = ""
        self.handles = []
        self.script = []
        self.root = Entity(parent=phone.screen_area, enabled=False, z=-0.5)
        self.timer_text = None
        self.elapsed = 0.0
        self._pending_end = None

    def start(self, number, name):
        if self.active:
            return
        low = number.lower()
        bank_numbers = ("ma banque", "bnr banque", "0800123456", "0955550012", "3200")
        pretty = name
        if low in ("ma banque",) or low.replace(" ", "") in bank_numbers:
            kind = "bank"
            pretty = "BNR Banque"
        elif low in ("mme duval",):
            kind = "nosignal"
            pretty = "Mme Duval"
        elif low in ("maman",):
            kind = "nosignal"
            pretty = "Maman"
        else:
            kind = "dead"
        self.phone.model.call_log.append((pretty, self.phone.game.state.clock_string(), True))
        self.name = pretty
        self.active = True
        self.elapsed = 0.0
        self.t = 0.0
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
        self.stage = None
        self._next_stage()

    def _build_ui(self):
        clear(self.root)
        self.root.enabled = True
        rect(self.root, 0, 0, SW, SH, rgb(14, 16, 22), z=0)
        label(self.root, "Appel en cours", 0, 0.25, 0.7, color.gray, z=-0.02)
        label(self.root, self.name, 0, 0.18, 1.2, color.white, z=-0.02)
        self.timer_text = label(self.root, "00:00", 0, 0.1, 0.9, rgb(200, 200, 200), z=-0.02)
        self.status_text = label(self.root, "Sonnerie...", 0, 0.0, 0.7, rgb(150, 190, 150), z=-0.02)
        button(self.root, "Raccrocher", 0, -0.25, 0.22, 0.07, self.hang_up, rgb(190, 40, 40), size=0.8, z=-0.03)

    def _stop_handles(self):
        for h in self.handles:
            if h:
                h.stop()
        self.handles = []

    def _next_stage(self):
        self._stop_handles()
        if not self.script:
            self.hang_up(silent=True)
            return
        self.stage = self.script.pop(0)
        kind = self.stage[0]
        self.t = 0.0
        if kind == "ring":
            self.status_text.text = "Sonnerie..."
            self.handles.append(sound.loop("sonnerie", 0.8, channel="voice"))
            self.stage_dur = self.stage[1]
        elif kind == "hold":
            self.status_text.text = "En attente..."
            self.handles.append(sound.loop("musique_attente", 0.9, channel="voice"))
            self.stage_dur = self.stage[1]
        elif kind == "voice":
            self.status_text.text = "..."
            txt = self.stage[1]
            degraded = self.stage[2]
            h = sound.speak(txt, f0=190, speed=0.9, whisper=False, volume=0.9, channel="voice",
                            distort=degraded, subtitle=True, speaker=self.name)
            self.handles.append(h)
            self.stage_dur = 2.2 + 0.075 * len(txt)
            self.status_text.text = txt[:40]
        elif kind == "beep":
            sound.play("bip_fin", 0.9, channel="voice")
            self.stage_dur = self.stage[1]
            self.status_text.text = "Appel terminé"
        elif kind == "breath":
            self.status_text.text = ""
            self.handles.append(sound.play("respiration_saccadee", 0.9, 0.7, channel="voice"))
            self.stage_dur = self.stage[1]
        elif kind == "silence":
            self.status_text.text = "..."
            self.stage_dur = self.stage[1]
        elif kind == "end":
            self.hang_up(silent=True)

    def hang_up(self, silent=False):
        if not self.active:
            return
        self.active = False
        self._stop_handles()
        self.root.enabled = False
        if not silent:
            sound.play("bip_fin", 0.6, channel="voice")
        self.phone.game.quests.on_event("call_ended", kind=self.kind)

    def update(self, dt):
        if not self.active:
            return
        self.elapsed += dt
        self.t += dt
        m, s = divmod(int(self.elapsed), 60)
        self.timer_text.text = f"{m:02d}:{s:02d}"
        if self.stage and self.t >= self.stage_dur:
            self._next_stage()
        self.phone.model.drain(dt, call=True)


def _wrap(text, width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------------------
# Téléphone (interface)
# ---------------------------------------------------------------------------
class PhoneUI:
    ICONS = [
        ("quickeats", "QuickEats", "icone_quickeats"),
        ("banque", "Ma Banque", "icone_banque"),
        ("messages", "Messages", "icone_messages"),
        ("camera", "Appareil photo", "icone_camera"),
        ("lampe", "Lampe", "icone_lampe"),
        ("appels", "Appels", "icone_appels"),
    ]

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
        self.root = Entity(parent=camera.ui, enabled=False, z=-2)
        self.root.y = -1.0
        self._build_frame()
        self.calls = CallManager(self)
        self._toast = Toast(parent=self.screen_area, y=-0.28)
        self._toast.root.z = -0.8
        self._build_notification()
        self._build_apps()
        self.show_home()

    # --- construction -----------------------------------------------------
    def _build_frame(self):
        r = self.root
        self.frame = rect(r, 0, 0, SW + 0.04, SH + 0.07, rgb(10, 10, 12), z=0.1)
        rect(r, 0, 0, SW + 0.025, SH + 0.05, rgb(34, 34, 40), z=0.09)
        self.glow = rect(r, 0, 0, SW + 0.1, SH + 0.14, rgb(110, 150, 255, 26), z=0.3)
        self.screen_area = Entity(parent=r, z=0)
        self.screen_bg = rect(self.screen_area, 0, 0, SW, SH, rgb(8, 8, 12), z=0.05)
        self.status = Entity(parent=self.screen_area, z=-0.4)
        rect(self.status, 0, 0.365, SW, 0.032, rgb(0, 0, 0, 160), z=0)
        self.time_text = label(self.status, "21:40", -0.18, 0.365, 0.6, color.white, origin=(-0.5, 0))
        # signal 1/5
        self.signal_bars = []
        for i in range(5):
            h = 0.008 + i * 0.004
            self.signal_bars.append(rect(self.status, 0.04 + i * 0.012, 0.357 + h / 2, 0.008, h,
                                         color.white if i < 1 else rgb(90, 90, 96), z=-0.01))
        self.battery_bg = rect(self.status, 0.16, 0.365, 0.045, 0.016, rgb(90, 90, 96), z=-0.01)
        self.battery_fill = rect(self.status, 0.1385, 0.365, 0.042, 0.012, rgb(110, 220, 120), z=-0.02)
        self.battery_fill.origin = (-0.5, 0)
        self.battery_text = label(self.status, "100%", 0.115, 0.365, 0.4, color.white, origin=(0.5, 0))
        # barre d'accueil
        self.nav = Entity(parent=self.screen_area, z=-0.4)
        rect(self.nav, 0, -0.375, SW, 0.03, rgb(0, 0, 0, 170), z=0)
        button(self.nav, "", 0, -0.375, 0.12, 0.02, self.show_home, rgb(200, 200, 205, 200), size=0.5, z=-0.02)
        button(self.nav, "‹", -0.16, -0.375, 0.05, 0.026, self.back, rgb(60, 60, 66, 200), size=0.55, z=-0.02)
        self.home = Entity(parent=self.screen_area, z=0.02)
        self._build_home()

    def _build_home(self):
        wp = rect(self.home, 0, 0, SW, SH, color.white, z=0.04, texture=textures.get("fond_telephone"))
        wp.color = rgb(255, 255, 255)
        self.clock_big = label(self.home, "21:40", 0, 0.24, 2.2, color.white, z=-0.1)
        self.date_text = label(self.home, "vendredi 13 octobre", 0, 0.185, 0.6, rgb(240, 230, 220), z=-0.1)
        for i, (aid, name, tex) in enumerate(self.ICONS):
            col, row = i % 3, i // 3
            x = -0.12 + col * 0.12
            y = 0.04 - row * 0.15
            b = button(self.home, "", x, y, 0.085, 0.085, (lambda a=aid: self.open_app(a)), rgb(255, 255, 255, 255), z=-0.1)
            b.texture = textures.get(tex)
            b.color = rgb(255, 255, 255)
            b.highlight_color = rgb(255, 255, 255)
            b.pressed_color = rgb(200, 200, 200)
            label(self.home, name if len(name) < 12 else "Photo", x, y - 0.058, 0.42, color.white, z=-0.1)
            if aid == "messages":
                self.msg_badge = rect(self.home, x + 0.04, y + 0.04, 0.03, 0.03, rgb(230, 50, 50), z=-0.12)
                self.msg_badge_text = label(self.home, "0", x + 0.04, y + 0.04, 0.45, color.white, z=-0.13)
            if aid == "quickeats":
                self.qe_badge = rect(self.home, x + 0.04, y + 0.04, 0.03, 0.03, rgb(230, 50, 50), z=-0.12)
                self.qe_badge.enabled = False

    def _build_apps(self):
        from delivery_app import DeliveryApp
        from bank_app import BankApp
        self.apps["quickeats"] = DeliveryApp(self)
        self.apps["banque"] = BankApp(self)
        self.apps["messages"] = MessagesApp(self)
        self.apps["camera"] = CameraApp(self)
        self.apps["lampe"] = TorchApp(self)
        self.apps["appels"] = CallsApp(self)

    def _build_notification(self):
        self.notif = Entity(parent=camera.ui, z=-4, enabled=False)
        self.notif_bg = button(self.notif, "", 0, 0.435, 0.5, 0.075, self.on_notif_click, rgb(24, 24, 30, 240), size=0.5)
        self.notif_icon = rect(self.notif, -0.21, 0.435, 0.05, 0.05, color.white, z=-0.05)
        self.notif_title = label(self.notif, "", -0.175, 0.452, 0.6, color.white, origin=(-0.5, 0), z=-0.06)
        self.notif_text = label(self.notif, "", -0.175, 0.42, 0.5, rgb(200, 200, 205), origin=(-0.5, 0), z=-0.06)

    # --- ouverture / fermeture -------------------------------------------
    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def open(self):
        if self.is_open:
            return
        if self.model.dead:
            self.game.say("Le téléphone est éteint.")
            return
        self.is_open = True
        self.game.state.phone_used = True
        self.game.on_phone_opened()
        self.root.enabled = True
        self.root.y = -0.9
        self.root.animate_y(PHONE_Y, duration=0.28, curve=curve.out_cubic)
        sound.play("tic_interrupteur", 0.5)
        self.game.player.phone_open = True
        mouse.locked = False
        mouse.visible = True
        if self.current is None:
            self.show_home()
        self.refresh_status()

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        if self.current is not None and self.current in self.apps:
            self.apps[self.current].on_close()
        self.root.animate_y(-0.9, duration=0.2, curve=curve.in_cubic)
        from ursina import invoke
        invoke(self._hide_root, delay=0.21)
        self.game.player.phone_open = False
        self.game.on_phone_closed()

    def _hide_root(self):
        if not self.is_open:
            self.root.enabled = False

    def show_home(self):
        if self.current is not None and self.current in self.apps:
            self.apps[self.current].on_close()
            self.apps[self.current].root.enabled = False
        self.current = None
        self.home.enabled = True
        self.refresh_status()

    def back(self):
        if self.current is not None:
            app = self.apps[self.current]
            if hasattr(app, "go_back") and app.go_back():
                return
        self.show_home()

    def open_app(self, aid):
        if self.frozen:
            return
        if self.current is not None:
            self.apps[self.current].root.enabled = False
        self.current = aid
        self.home.enabled = False
        app = self.apps[aid]
        app.root.enabled = True
        sound.play("tap", 0.8)
        self.game.quests.on_event("app_opened", app=aid)
        app.on_open()

    # --- notifications ----------------------------------------------------
    def notify(self, title, text, icon="icone_messages", target=None, sound_on=True):
        self.notif_queue.append(dict(title=title, text=text, icon=icon, target=target))
        if sound_on:
            sound.play("vibration", 0.9, channel="voice")
            sound.play("notification", 0.8, channel="voice")
            self.vibrate_t = 0.6
            self.game.on_phone_notification()

    def _show_next_notif(self):
        if not self.notif_queue:
            return
        d = self.notif_queue.pop(0)
        self.notif_data = d
        self.notif_title.text = d["title"]
        t = d["text"]
        self.notif_text.text = (t[:60] + "...") if len(t) > 60 else t
        self.notif_icon.texture = textures.get(d["icon"])
        self.notif_icon.color = color.white
        self.notif.enabled = True
        self.notif.y = 0.2
        self.notif.animate_y(0.0, duration=0.25, curve=curve.out_cubic)
        self.notif_t = 4.5

    def on_notif_click(self):
        d = self.notif_data
        if d is None:
            return
        self.notif.enabled = False
        self.notif_t = 0
        if not self.is_open:
            self.open()
        tgt = d.get("target")
        if tgt:
            self.open_app(tgt[0])
            if len(tgt) > 1 and hasattr(self.apps[tgt[0]], "open_conv"):
                self.apps[tgt[0]].open_conv(tgt[1])

    # --- divers ----------------------------------------------------------
    def toast(self, text, duration=2.4):
        self._toast.show(text, duration)

    def freeze(self, seconds):
        self.frozen = True
        self.frozen_until = seconds
        self.show_home()
        if not hasattr(self, "_freeze_overlay"):
            self._freeze_overlay = rect(self.screen_area, 0, 0, SW, SH, rgb(0, 0, 0, 255), z=-0.7)
        self._freeze_overlay.enabled = True

    def refresh_status(self):
        self.time_text.text = self.game.state.clock_string()
        self.clock_big.text = self.game.state.clock_string()
        b = self.model.battery
        self.battery_fill.scale_x = max(0.001, 0.042 * b / 100.0)
        self.battery_fill.color = rgb(110, 220, 120) if b > 25 else rgb(230, 70, 60)
        self.battery_text.text = f"{int(b)}%"
        unread = sum(c["unread"] for c in self.model.conversations.values())
        self.msg_badge.enabled = unread > 0
        self.msg_badge_text.enabled = unread > 0
        self.msg_badge_text.text = str(unread)

    def on_key(self, key):
        if self.is_open and self.current is not None:
            self.apps[self.current].on_key(key)

    def update(self, dt):
        self.calls.update(dt)
        if self.frozen:
            self.frozen_until -= dt
            if self.frozen_until <= 0:
                self.frozen = False
                self._freeze_overlay.enabled = False
        # batterie
        qe_open = self.is_open and self.current == "quickeats"
        if not self.calls.active:
            self.model.drain(dt, quickeats=qe_open)
        if self.model.dead and self.is_open:
            self.close()
        # notifications
        if self.notif_t > 0:
            self.notif_t -= dt
            if self.notif_t <= 0:
                self.notif.enabled = False
        elif self.notif_queue and not self.model.dead:
            self._show_next_notif()
        # vibration : l'objet tremble
        if self.vibrate_t > 0:
            self.vibrate_t -= dt
            if self.is_open:
                self.root.x = math.sin(self.game.player.time * 90.0) * 0.004
        else:
            self.root.x = 0.0
        if self.is_open:
            self.glow.alpha = 0.1 + 0.03 * math.sin(self.game.player.time * 3)
            self.refresh_status_light(dt)
            if self.current is not None:
                self.apps[self.current].update(dt)

    _status_t = 0.0

    def refresh_status_light(self, dt):
        self._status_t -= dt
        if self._status_t <= 0:
            self._status_t = 0.5
            self.refresh_status()
