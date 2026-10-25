"""Interface utilisateur : chargement, menu principal, HUD, pause, documents, game over, fins.

Tout est construit avec des entités Ursina rattachées à `camera.ui`.
"""
import random

from ursina import Entity, Text, Button, color, camera, Vec3, invoke, destroy

import config
import game_data as gd
from sound_engine import engine as sound
from texture_generator import textures
from ui_widgets import label, rect, button, clear, rgb, star, Toast, text_scale


class LoadingScreen:
    def __init__(self):
        self.root = Entity(parent=camera.ui, z=-20)
        rect(self.root, 0, 0, 2.4, 1.3, color.black, z=1)
        self.title = label(self.root, gd.CINEMATIC_CAPTIONS["titre"], 0, 0.1, 4.0, color.white, z=0)
        rect(self.root, 0, -0.1, 0.62, 0.018, rgb(40, 40, 44), z=0)
        self.bar = rect(self.root, -0.31, -0.1, 0.001, 0.012, rgb(220, 220, 225), z=-0.01)
        self.bar.origin = (-0.5, 0)
        self.text = label(self.root, "Génération des assets...", 0, -0.15, 0.8, color.gray, z=0)
        self.tip = label(self.root, random.choice(gd.LOADING_TIPS), 0, -0.4, 0.8, rgb(150, 150, 160), z=0)
        self.value = 0.0

    def set(self, frac, text=None):
        self.value = frac
        self.bar.scale_x = max(0.001, 0.62 * frac)
        if text:
            self.text.text = text

    def hide(self):
        self.root.enabled = False

    def show(self):
        self.root.enabled = True


class MainMenu:
    """Écran titre : la maison sous la pluie, éclairs, silhouette à la fenêtre du grenier."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-3, enabled=False)
        self.title_pos = Vec3(0, 0.27, 0)
        self.title = label(self.root, config.GAME_TITLE, 0, 0.27, 6.0, color.white, z=0)
        self.sub = label(self.root, config.GAME_SUBTITLE, 0, 0.17, 1.6, rgb(190, 190, 200), z=0)
        self.buttons = []
        self.page = "main"
        self.lobby = None
        self._build_main()
        self.t = 0.0
        self.idle = 0.0
        self.next_lightning = random.uniform(6, 12)
        self.thunder_at = None
        self.window_glow = []
        self.glow_t = 0.0
        self.sil = None
        self.ver = label(self.root, f"v{config.VERSION}", 0.85, -0.47, 0.6, color.gray, origin=(0.5, 0), z=0)

    def _build_main(self):
        for b in self.buttons:
            destroy(b)
        self.buttons = []
        has_save = self.game.saves.exists()
        items = [("Nouvelle Partie", self.game.new_game, True),
                 ("Continuer", self.game.continue_game, has_save),
                 ("Multijoueur", self.game.show_multiplayer, True),
                 ("Paramètres", self.game.show_settings, True),
                 ("Quitter", self.game.quit_game, True)]
        y = 0.02
        for text, cb, enabled in items:
            col = rgb(12, 12, 14, 200) if enabled else rgb(12, 12, 14, 120)
            b = button(self.root, text, 0, y, 0.42, 0.06, cb if enabled else None, col,
                       color.white if enabled else rgb(90, 90, 96), size=1.0)
            if not enabled:
                b.highlight_color = col
            self.buttons.append(b)
            y -= 0.075

    def show(self):
        self.root.enabled = True
        self._build_main()
        self.t = 0.0
        self.idle = 0.0
        self.game.set_mouse(free=True)

    def hide(self):
        self.root.enabled = False

    def update(self, dt):
        if not self.root.enabled:
            return
        self.t += dt
        self.idle += dt
        # titre légèrement tremblant (0,5 px par frame)
        j = 0.5 / 1080.0
        self.title.position = Vec3(random.uniform(-j, j) * 2, 0.27 + random.uniform(-j, j) * 2, 0)
        # éclairs
        self.next_lightning -= dt
        if self.next_lightning <= 0:
            self.next_lightning = random.uniform(9, 18)
            self.game.effects.flash(0.55, 0.35)
            self.thunder_at = self.t + random.uniform(0.6, 2.2)
        if self.thunder_at is not None and self.t >= self.thunder_at:
            sound.play("tonnerre", 0.8, channel="music")
            self.thunder_at = None
        # après 30 s d'inactivité : lumières qui s'allument derrière les fenêtres
        if self.idle > 30.0:
            self.idle = 0.0
            self.game.menu_window_flicker()


class PauseMenu:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-12, enabled=False)
        rect(self.root, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 190), z=1)
        label(self.root, "PAUSE", 0, 0.25, 3.0, color.white, z=0)
        self.items = []
        y = 0.1
        for text, cb in (("Reprendre", game.resume), ("Paramètres", game.show_settings), ("Menu principal", game.confirm_main_menu), ("Quitter", game.quit_game)):
            button(self.root, text, 0, y, 0.4, 0.06, cb, rgb(20, 20, 24, 235), size=1.0)
            y -= 0.08
        self.hint = label(self.root, "Les parties solo sont sauvegardées automatiquement aux changements d'acte.", 0, -0.32, 0.6, color.gray, z=0)

    def show(self):
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False


class DocumentViewer:
    """Visionneuse de documents (carnet, relevé, plan, Polaroïds...)."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-13, enabled=False)
        rect(self.root, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 170), z=1)
        self.paper = rect(self.root, 0, 0, 0.72, 0.86, color.white, z=0.5, texture=textures.get("papier"))
        self.paper.color = rgb(255, 250, 235)
        self.title = label(self.root, "", 0, 0.37, 1.1, rgb(60, 40, 30), z=-0.1)
        self.body = Text(parent=self.root, text=" ", position=(-0.31, 0.3, -0.1), origin=(-0.5, 0.5), scale=1.0 * text_scale(),
                         color=rgb(40, 30, 25), wordwrap=40)
        self.page_label = label(self.root, "", 0, -0.39, 0.7, rgb(90, 70, 60), z=-0.1)
        self.prev = button(self.root, "‹", -0.28, -0.39, 0.06, 0.05, self.prev_page, rgb(90, 70, 55, 220), size=1.0, z=-0.1)
        self.next = button(self.root, "›", 0.28, -0.39, 0.06, 0.05, self.next_page, rgb(90, 70, 55, 220), size=1.0, z=-0.1)
        self.close_btn = button(self.root, "Fermer [E]", 0.0, -0.46, 0.2, 0.05, self.close, rgb(60, 40, 30, 230), size=0.8, z=-0.1)
        self.pages = []
        self.idx = 0
        self.on_close = None
        self.visible = False

    def open(self, title, pages, on_close=None):
        self.pages = pages if isinstance(pages, list) else [pages]
        self.idx = 0
        self.title.text = title
        self.on_close = on_close
        self.visible = True
        self.root.enabled = True
        self._render()
        sound.play("papier", 0.8)
        self.game.set_mouse(free=True)

    def _render(self):
        self.body.text = self.pages[self.idx]
        n = len(self.pages)
        self.page_label.text = f"Page {self.idx + 1}/{n}" if n > 1 else ""
        self.prev.enabled = n > 1 and self.idx > 0
        self.next.enabled = n > 1 and self.idx < n - 1

    def prev_page(self):
        if self.idx > 0:
            self.idx -= 1
            sound.play("papier", 0.5)
            self._render()

    def next_page(self):
        if self.idx < len(self.pages) - 1:
            self.idx += 1
            sound.play("papier", 0.5)
            self._render()

    def close(self):
        if not self.visible:
            return
        self.visible = False
        self.root.enabled = False
        cb, self.on_close = self.on_close, None
        self.game.set_mouse(free=False)
        if cb:
            cb()

    def on_key(self, key):
        if not self.visible:
            return
        if key in ("e", "escape"):
            self.close()
        elif key in ("right arrow", "d"):
            self.next_page()
        elif key in ("left arrow", "a"):
            self.prev_page()


class ChoiceDialog:
    """Petite boîte de dialogue à deux choix (ex. ouvrir le congélateur ?)."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-14, enabled=False)
        rect(self.root, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 160), z=1)
        rect(self.root, 0, 0, 0.7, 0.3, rgb(14, 14, 18, 245), z=0.5)
        self.text = label(self.root, "", 0, 0.07, 0.9, color.white, wrap=40, z=-0.1)
        self.yes = button(self.root, "Oui", -0.14, -0.07, 0.2, 0.06, None, rgb(60, 30, 30), size=0.9, z=-0.1)
        self.no = button(self.root, "Non", 0.14, -0.07, 0.2, 0.06, None, rgb(30, 50, 40), size=0.9, z=-0.1)
        self.visible = False

    def ask(self, question, on_yes, on_no, yes="Oui", no="Non"):
        self.text.text = question
        self.yes.text_entity.text = yes
        self.no.text_entity.text = no
        self.yes.on_click = lambda: self._answer(on_yes)
        self.no.on_click = lambda: self._answer(on_no)
        self.visible = True
        self.root.enabled = True
        self.game.set_mouse(free=True)

    def _answer(self, cb):
        self.visible = False
        self.root.enabled = False
        self.game.set_mouse(free=False)
        if cb:
            cb()


class RatingScreen:
    """« Notez votre livreur » : il faut mettre 5 étoiles."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-15, enabled=False)
        rect(self.root, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 235), z=1)
        self.text = label(self.root, "", 0, 0.2, 1.6, color.white, z=0, wrap=36)
        self.stars = []
        self.cb = None
        self.fill = 0

    def show(self, text, on_done):
        clear(self.root)
        rect(self.root, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 235), z=1)
        self.text = label(self.root, text, 0, 0.2, 1.4, color.white, z=0, wrap=36)
        self.fill = 0
        self.stars = []
        self.cb = on_done
        for i in range(5):
            b = Button(parent=self.root, model="quad", color=rgb(0, 0, 0, 1), position=(-0.2 + i * 0.1, -0.02, -0.1), scale=(0.09, 0.09),
                       highlight_color=rgb(255, 255, 255, 20))
            b.on_click = self._clicked
            s = star(self.root, -0.2 + i * 0.1, -0.02, 0.08, rgb(70, 70, 76), z=-0.05)
            self.stars.append(s)
        label(self.root, "Choisissez une note", 0, -0.12, 0.7, color.gray, z=-0.1)
        self.root.enabled = True
        self.game.set_mouse(free=True)

    def _clicked(self):
        # quelle que soit l'étoile cliquée, la note est de 5
        for i, s in enumerate(self.stars):
            invoke(self._fill, i, delay=i * 0.18)
        invoke(self._done, delay=1.6)

    def _fill(self, i):
        self.stars[i].color = color.rgb32(255, 200, 40)
        sound.play("etoile", 0.7, pitch=1.0 + i * 0.1)

    def _done(self):
        self.root.enabled = False
        cb, self.cb = self.cb, None
        if cb:
            cb()


class GameOverScreen:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-16, enabled=False)
        self.bg = rect(self.root, 0, 0, 2.4, 1.3, color.black, z=1)
        self.items = Entity(parent=self.root)

    def show(self, first_death=False):
        clear(self.items)
        self.root.enabled = True
        self.game.set_mouse(free=True)
        sound.play("impact", 0.9, channel="sfx")
        self.items.enabled = False
        invoke(self._reveal, first_death, delay=2.2)

    def _reveal(self, first_death):
        self.items.enabled = True
        label(self.items, gd.GAMEOVER_TITLE, 0, 0.16, 3.2, color.white, z=0)
        label(self.items, gd.GAMEOVER_RATING, -0.04, 0.03, 1.0, rgb(180, 180, 185), z=0)
        for i in range(5):
            star(self.items, 0.16 + i * 0.035, 0.03, 0.03, color.rgb32(255, 200, 40) if i == 0 else rgb(60, 60, 66), z=0)
        button(self.items, "Réessayer", -0.14, -0.12, 0.24, 0.07, self.game.retry, rgb(30, 30, 34, 240), size=1.0)
        button(self.items, "Menu principal", 0.14, -0.12, 0.24, 0.07, self.game.to_main_menu, rgb(30, 30, 34, 240), size=1.0)
        if first_death:
            label(self.items, gd.GAMEOVER_TIP, 0, -0.38, 0.75, rgb(200, 190, 150), z=0, wrap=70)

    def hide(self):
        self.root.enabled = False


class EndingScreen:
    """Séquence de fin : texte chronométré, générique, statistiques."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-17, enabled=False)
        self.bg = rect(self.root, 0, 0, 2.4, 1.3, color.black, z=1)
        self.items = Entity(parent=self.root)
        self.steps = []
        self.t = 0.0
        self.idx = -1
        self.active = False
        self.title_lbl = None

    def start(self, code):
        e = gd.ENDINGS[code]
        self.code = code
        self.root.enabled = True
        clear(self.items)
        self.bg.color = color.black
        self.steps = []
        for line in e["lines"]:
            self.steps.append(("line", line, 3.0 + len(line) / 38.0))
        self.steps.append(("title", f"{e['title']}  —  {e['kind']}", 4.0))
        self.steps.append(("post", e["post"], 4.5))
        self.steps.append(("credits", "", 0))
        self.idx = -1
        self.t = 0.0
        self.cur = None
        self.active = True
        self.game.set_mouse(free=True)
        if code == "A":
            self.bg.color = rgb(30, 18, 12)
        self._advance()

    def _advance(self):
        self.idx += 1
        clear(self.items)
        if self.idx >= len(self.steps):
            return
        kind, text, dur = self.steps[self.idx]
        self.t = 0.0
        self.dur = dur
        self.kind = kind
        if kind == "credits":
            self._start_credits()
            return
        size = 1.3 if kind == "line" else 2.2 if kind == "title" else 1.1
        col = color.white if kind != "post" else rgb(200, 190, 160)
        self.cur = label(self.items, text, 0, 0.0, size, col, wrap=62, z=0)
        self.cur.color = color.rgba32(255, 255, 255, 0) if kind != "post" else rgb(200, 190, 160, 0)
        if kind == "title":
            sound.play("sourd_mort", 0.5)

    def _start_credits(self):
        st = self.game.state
        self.credit_items = []
        y = -0.6
        for text, gap in gd.CREDITS:
            if text:
                lb = label(self.items, text, 0, y, 2.6 if text == config.GAME_TITLE else 1.2, color.white, z=0)
                self.credit_items.append(lb)
            y -= 0.12 + gap * 0.05
        stats = st.stats
        m, s = divmod(int(stats["play_time"]), 60)
        rows = [f"Temps de jeu : {m} min {s:02d} s", f"Photos prises : {stats['photos']}", f"Morts : {stats['deaths']}",
                f"Choix de l'assistance : {st.good_choices} bons / {st.bad_choices} mauvais"]
        y -= 0.1
        for r in rows:
            self.credit_items.append(label(self.items, r, 0, y, 1.0, rgb(200, 200, 205), z=0))
            y -= 0.08
        self.credit_end_y = y
        self.credit_t = 0.0

    def update(self, dt):
        if not self.active:
            return
        self.t += dt
        if self.idx >= len(self.steps):
            return
        if self.kind == "credits":
            # défilement
            for lb in self.credit_items:
                lb.y += dt * 0.07
            if self.credit_items and self.credit_items[-1].y > 0.5 and not getattr(self, "_buttons", False):
                self._buttons = True
                label(self.items, config.GAME_TITLE, 0, 0.18, 4.5, color.white, z=0)
                button(self.items, "Menu principal", 0, -0.05, 0.36, 0.07, self.game.to_main_menu, rgb(20, 20, 24, 240), size=1.0)
            return
        a = min(1.0, self.t / 0.8, max(0.0, (self.dur - self.t) / 0.8))
        if self.cur is not None:
            self.cur.color = self._with_alpha(self.cur.color, a)
        if self.t >= self.dur:
            self._advance()

    @staticmethod
    def _with_alpha(col, a):
        return color.rgba32(int(col[0] * 255), int(col[1] * 255), int(col[2] * 255), int(a * 255))

    def stop(self):
        self.active = False
        self.root.enabled = False
        self._buttons = False


class HUD:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-1, enabled=False)
        r = self.root
        # objectif (haut gauche)
        self.obj = Text(parent=r, text=" ", position=(-0.86, 0.46), origin=(-0.5, 0.5), scale=0.95 * text_scale(), color=rgb(255, 255, 255, 170))
        # lampe torche (bas droite)
        self.fl_icon = rect(r, 0.78, -0.43, 0.025, 0.04, rgb(210, 200, 150, 190))
        rect(r, 0.78, -0.43 - 0.03, 0.05, 0.012, rgb(40, 40, 40, 180))
        self.fl_bar = rect(r, 0.755, -0.46, 0.05, 0.008, rgb(220, 220, 140, 220))
        self.fl_bar.origin = (-0.5, 0)
        self.fl_bar.x = 0.755
        # téléphone (bas gauche)
        self.ph_icon = rect(r, -0.8, -0.43, 0.03, 0.05, rgb(180, 200, 255, 190))
        rect(r, -0.8, -0.46, 0.05, 0.012, rgb(40, 40, 40, 180))
        self.ph_bar = rect(r, -0.825, -0.46, 0.05, 0.008, rgb(130, 200, 255, 220))
        self.ph_bar.origin = (-0.5, 0)
        self.ph_bar.x = -0.825
        # réticule
        self.reticle = rect(r, 0, 0, 0.004, 0.004, rgb(255, 255, 255, 140))
        # invite d'interaction
        self.prompt = label(r, "", 0, -0.06, 1.0, color.white, z=-0.1)
        # sous-titres / pensées
        self.sub = label(r, "", 0, -0.36, 1.0, color.white, wrap=70, z=-0.1)
        self.sub_bg = rect(r, 0, -0.36, 1.1, 0.06, rgb(0, 0, 0, 0), z=0.1)
        self.sub_t = 0.0
        self.quest_note = label(r, "", 0, 0.4, 1.0, rgb(255, 230, 160), z=-0.1)
        self.quest_t = 0.0
        self.tips = label(r, "", 0, -0.2, 0.8, rgb(200, 200, 205), wrap=80, z=-0.1)
        self.tips_t = 0.0
        self.stamina_bar = rect(r, 0, -0.47, 0.001, 0.004, rgb(255, 255, 255, 90))
        self.vol_icon = None
        self.hint_line = None

    def show(self):
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False

    def set_objective(self, text):
        self.obj.text = text

    def say(self, text, duration=3.5, speaker=None):
        self.sub.text = (f"{speaker} : " if speaker else "") + text
        self.sub_t = duration
        self.sub.color = color.white

    def quest(self, text, duration=4.0):
        self.quest_note.text = text
        self.quest_t = duration

    def tip(self, text, duration=8.0):
        self.tips.text = text
        self.tips_t = duration

    def update(self, dt, game):
        p = game.player
        self.fl_bar.scale_x = max(0.001, 0.05 * p.flashlight.battery / 100.0)
        self.fl_bar.color = rgb(220, 220, 140, 220) if p.flashlight.battery > 20 else rgb(240, 120, 70, 230)
        self.fl_icon.color = rgb(255, 245, 190, 230) if p.flashlight.on else rgb(120, 115, 90, 150)
        b = game.phone.model.battery
        self.ph_bar.scale_x = max(0.001, 0.05 * b / 100.0)
        self.ph_bar.color = rgb(130, 200, 255, 220) if b > 20 else rgb(240, 90, 80, 230)
        # la stamina est un trait discret sous le réticule quand elle est entamée
        if p.stamina < 99:
            self.stamina_bar.scale_x = 0.12 * p.stamina / 100.0
            self.stamina_bar.enabled = True
        else:
            self.stamina_bar.enabled = False
        if self.sub_t > 0:
            self.sub_t -= dt
            a = min(1.0, self.sub_t / 0.5)
            self.sub.color = color.rgba32(255, 255, 255, int(255 * a))
            self.sub_bg.color = rgb(0, 0, 0, int(110 * a))
            if self.sub_t <= 0:
                self.sub.text = ""
        if self.quest_t > 0:
            self.quest_t -= dt
            a = min(1.0, self.quest_t / 0.6, (4.0 - self.quest_t) / 0.4 + 0.0)
            self.quest_note.color = rgb(255, 230, 160, int(255 * max(0.0, min(1.0, a))))
            if self.quest_t <= 0:
                self.quest_note.text = ""
        if self.tips_t > 0:
            self.tips_t -= dt
            if self.tips_t <= 0:
                self.tips.text = ""
        # invite
        target = game.interactions.target
        if target is not None and not game.phone.is_open and not game.paused:
            pr = target.current_prompt()
            self.prompt.text = f"[E] {pr}" if pr else ""
            self.reticle.scale = 0.007
        else:
            self.prompt.text = ""
            self.reticle.scale = 0.004


class UIManager:
    """Façade regroupant toutes les interfaces."""

    def __init__(self, game):
        self.game = game
        self.loading = None
        self.menu = MainMenu(game)
        self.hud = HUD(game)
        self.pause = PauseMenu(game)
        self.docs = DocumentViewer(game)
        self.choice = ChoiceDialog(game)
        self.rating = RatingScreen(game)
        self.gameover = GameOverScreen(game)
        self.ending = EndingScreen(game)
        self.toast = Toast()
        self.fade_overlay = None

    # --- raccourcis -----------------------------------------------------
    def say(self, text, duration=3.5, speaker=None):
        self.hud.say(text, duration, speaker)

    def notify_quest(self, text):
        self.hud.quest(text)

    def refresh_objective(self):
        self.hud.set_objective(self.game.quests.current_objective())

    def update(self, dt):
        self.menu.update(dt)
        self.ending.update(dt)
        self.toast.update(dt)
        if self.hud.root.enabled:
            self.hud.update(dt, self.game)
