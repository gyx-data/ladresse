"""Interface utilisateur : chargement, menu principal, HUD, pause, documents, game over, fins.

Tout est construit avec des entités Ursina rattachées à `camera.ui`.
"""
import random

from PIL import Image

from ursina import Entity, Text, Button, color, camera, Vec3, invoke, destroy

import config
import game_data as gd
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb, star, Toast, text_scale, panel, image, ProgressBar
import illustrations as ill
import typography as T
import ui_theme as theme


_TITLE_CACHE = {}


def title_image(text, px=170, glow=(150, 30, 30), subtitle=None, seed=3):
    key = (text, px, glow, subtitle, seed)
    if key not in _TITLE_CACHE:
        _TITLE_CACHE[key] = T.render_title(text, px, glow=glow, subtitle=subtitle, seed=seed)
    return _TITLE_CACHE[key]


def title_entity(parent, text, x, y, height, glow=(150, 30, 30), subtitle=None, z=0.0, seed=3):
    img = title_image(text, 170, glow, subtitle, seed)
    return image(parent, img, x, y, height * img.width / img.height, height, z)


class LoadingScreen:
    def __init__(self):
        self.root = Entity(parent=camera.ui, z=-20)
        rect(self.root, 0, 0, 2.6, 1.4, color.black, z=1)
        try:
            self.title = title_entity(self.root, config.GAME_TITLE, 0, 0.12, 0.2, z=0)
        except Exception:
            self.title = label(self.root, config.GAME_TITLE, 0, 0.1, 4.0, color.white, z=0)
        self.bar = ProgressBar(self.root, 0, -0.08, 0.6, 0.014)
        self.text = label(self.root, "Génération des assets...", 0, -0.13, 0.75, rgb(150, 148, 145), z=0)
        self.tip = label(self.root, random.choice(gd.LOADING_TIPS), 0, -0.4, 0.75, rgb(130, 128, 125), z=0)
        self.value = 0.0

    def set(self, frac, text=None):
        self.value = frac
        self.bar.set(frac)
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
        # dégradé latéral pour la lisibilité du menu (à gauche)
        grad = Image.new("RGBA", (256, 4), (0, 0, 0, 0))
        for x in range(256):
            a = int(225 * max(0.0, 1.0 - x / 256.0) ** 1.4)
            for yy in range(4):
                grad.putpixel((x, yy), (4, 3, 4, a))
        image(self.root, grad, -0.55, 0, 1.5, 1.2, z=1)
        self.title_pos = Vec3(-0.5, 0.27, 0)
        try:
            self.title = title_entity(self.root, config.GAME_TITLE, -0.47, 0.29, 0.14, z=0)
        except Exception:
            self.title = label(self.root, config.GAME_TITLE, -0.5, 0.29, 6.0, color.white, z=0)
        self.sub = label(self.root, config.GAME_SUBTITLE.upper() + "  ·  NICE", -0.5, 0.17, 0.95, rgb(200, 150, 130), z=0)
        rect(self.root, -0.5, 0.135, 0.36, 0.002, rgb(150, 40, 34), z=0)
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
        self.ver = label(self.root, f"v{config.VERSION}  ·  F5 : vue 3e personne  ·  Échap : pause", 0.86, -0.47, 0.55,
                         rgb(120, 118, 115), origin=(0.5, 0), z=0)

    def _build_main(self):
        for b in self.buttons:
            destroy(b)
        self.buttons = []
        has_save = self.game.saves.exists()
        items = [("Nouvelle partie", self.game.new_game, True, "primary"),
                 ("Continuer", self.game.continue_game, has_save, "dark"),
                 ("Coopératif en ligne", self.game.show_multiplayer, True, "dark"),
                 ("Paramètres", self.game.show_settings, True, "dark"),
                 ("Succès", self.show_achievements, True, "dark"),
                 ("Crédits", self.show_credits, True, "dark"),
                 ("Quitter", self.game.quit_game, True, "ghost")]
        y = 0.05
        for text, cb, enabled, style in items:
            b = button(self.root, text, -0.5, y, 0.36, 0.058, cb if enabled else None, style=style if enabled else "card",
                       text_col=None if enabled else rgb(100, 100, 106), size=0.9)
            if not enabled:
                b.highlight_color = b.color
            self.buttons.append(b)
            y -= 0.072

    def show_achievements(self):
        self.game.achievements.open_screen()

    def show_credits(self):
        lines = [t for t, _ in gd.CREDITS if t]
        self.game.ui.docs.open("Crédits", ["\n".join(lines)])

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
        # titre légèrement tremblant
        j = 0.6 / 1080.0
        self.title.position = Vec3(-0.47 + random.uniform(-j, j) * 2, 0.29 + random.uniform(-j, j) * 2, 0)
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
        rect(self.root, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 170), z=1)
        panel(self.root, 0, 0, 0.56, 0.7, "panel", z=0.8)
        label(self.root, "PAUSE", 0, 0.28, 2.2, color.white, z=0)
        rect(self.root, 0, 0.235, 0.2, 0.003, rgb(170, 50, 40), z=0)
        self.items = []
        y = 0.14
        for text, cb, style in (("Reprendre", game.resume, "primary"), ("Paramètres", game.show_settings, "dark"),
                                ("Menu principal", game.confirm_main_menu, "dark"), ("Quitter le jeu", game.quit_game, "ghost")):
            self.items.append(button(self.root, text, 0, y, 0.4, 0.06, cb, style=style, size=0.9))
            y -= 0.078
        self.info = label(self.root, "", 0, -0.2, 0.65, rgb(200, 196, 190), z=0, wrap=48)
        self.hint = label(self.root, "Sauvegarde automatique à chaque étape importante.", 0, -0.3, 0.55, rgb(130, 128, 125), z=0)

    def show(self):
        g = self.game
        m, s_ = divmod(int(g.state.stats.get("play_time", 0)), 60)
        obj = g.ui.hud.obj.text.strip() or "—"
        self.info.text = f"Objectif : {obj}\nTemps de jeu : {m} min {s_:02d} s   ·   Vue : {config.settings['vue']}"
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False


class DocumentViewer:
    """Visionneuse de documents : chaque page est rendue comme un vrai papier (manuscrit, dactylographié,
    coupure de journal) avec Pillow, puis affichée en grand ; navigation ‹ › / flèches."""

    PW, PH = 0.62, 0.8

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-13, enabled=False)
        rect(self.root, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 190), z=1)
        self.page_ent = None
        self.title = label(self.root, "", 0, 0.45, 1.0, rgb(230, 220, 200), z=-0.1)
        self.page_label = label(self.root, "", 0, -0.44, 0.65, rgb(170, 160, 150), z=-0.1)
        self.prev = button(self.root, "‹", -0.38, 0, 0.06, 0.08, self.prev_page, style="dark", size=1.2, z=-0.1)
        self.next = button(self.root, "›", 0.38, 0, 0.06, 0.08, self.next_page, style="dark", size=1.2, z=-0.1)
        self.close_btn = button(self.root, f"Fermer  [{config.settings.key('interagir').upper()}]", 0.62, -0.44, 0.2, 0.05, self.close,
                                style="primary", size=0.7, z=-0.1)
        self.pages = []
        self.idx = 0
        self.on_close = None
        self.visible = False
        self._cache = {}

    def open(self, title, pages, on_close=None):
        self.pages = pages if isinstance(pages, list) else [pages]
        self.pages = [p if (isinstance(p, str) and p.strip()) else "..." for p in self.pages]
        self.idx = 0
        self.title.text = title
        self.kind = self._kind(title)
        self.on_close = on_close
        self.visible = True
        self.root.enabled = True
        self._render()
        sound.play("papier", 0.8)
        self.game.set_mouse(free=True)

    @staticmethod
    def _kind(title):
        t = title.lower()
        if "ticket" in t or "relevé" in t or "reçu" in t or "historique" in t or "crédits" in t:
            return "typed"
        if "journal" in t or "nice-matin" in t or "journaux" in t:
            return "news"
        return "hand"

    def _page_image(self, text):
        key = (self.kind, text, self.title.text)
        if key not in self._cache:
            try:
                if self.kind == "typed":
                    img = T.typed_page(text, (700, 900), 22)
                elif self.kind == "news":
                    img = T.newspaper_page([l for l in text.split("\n") if l.strip()], (700, 900))
                else:
                    img = T.handwriting_page(text, (760, 980), px=32, seed=len(text) % 97)
            except Exception:
                img = None
            if len(self._cache) > 24:
                self._cache.clear()
            self._cache[key] = img
        return self._cache[key]

    def _render(self):
        text = self.pages[self.idx]
        if self.page_ent is not None:
            destroy(self.page_ent)
            self.page_ent = None
        img = self._page_image(text)
        if img is not None:
            h = self.PH
            w = h * img.width / img.height
            self.page_ent = image(self.root, img, 0, 0, w, h, z=0.5)
        else:       # repli texte brut
            self.page_ent = Entity(parent=self.root)
            panel(self.page_ent, 0, 0, self.PW, self.PH, "paper", z=0.5)
            Text(parent=self.page_ent, text=text, position=(-0.27, 0.36, -0.1), origin=(-0.5, 0.5), scale=0.95 * text_scale(),
                 color=rgb(40, 30, 25), wordwrap=40)
        n = len(self.pages)
        self.page_label.text = f"Page {self.idx + 1} / {n}" if n > 1 else ""
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
        self.game.set_mouse(free=self.game.mode != "playing")
        if cb:
            cb()

    def on_key(self, key):
        if not self.visible:
            return
        if key in (config.settings.key("interagir"), "escape"):
            self.close()
        elif key in ("right arrow", "d"):
            self.next_page()
        elif key in ("left arrow", "a", "q"):
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
        self.bg = rect(self.root, 0, 0, 2.6, 1.4, color.black, z=1)
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
        try:
            title_entity(self.items, gd.GAMEOVER_TITLE.upper(), 0, 0.2, 0.15, glow=(170, 20, 20), seed=9, z=0)
        except Exception:
            label(self.items, gd.GAMEOVER_TITLE, 0, 0.18, 3.2, color.white, z=0)
        label(self.items, gd.GAMEOVER_RATING, -0.08, 0.05, 0.95, rgb(190, 186, 182), z=0)
        for i in range(5):
            star(self.items, 0.12 + i * 0.038, 0.05, 0.032, color.rgb32(255, 200, 40) if i == 0 else rgb(60, 60, 66), z=0)
        button(self.items, "Réessayer", -0.13, -0.1, 0.24, 0.065, self.game.retry, style="primary", size=0.9)
        button(self.items, "Menu principal", 0.13, -0.1, 0.24, 0.065, self.game.to_main_menu, style="dark", size=0.9)
        st = self.game.state.stats
        m, s_ = divmod(int(st.get("play_time", 0)), 60)
        label(self.items, f"Survécu {m} min {s_:02d} s  ·  {st.get('photos', 0)} photo(s)  ·  morts : {st.get('deaths', 0)}", 0, -0.2,
              0.62, rgb(140, 138, 134), z=0)
        if first_death:
            label(self.items, gd.GAMEOVER_TIP, 0, -0.38, 0.72, rgb(220, 196, 150), z=0, wrap=70)

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
    """Interface en jeu : objectif, batteries (icônes), invite d'interaction avec touche, sous-titres,
    endurance / santé, notifications de quête."""

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-1, enabled=False)
        r = self.root
        ts = text_scale()
        # objectif (haut gauche) : pastille + texte
        self.obj_bar = rect(r, -0.865, 0.448, 0.005, 0.032, rgb(226, 90, 60, 230), z=0.05, radius=0.5)
        self.obj_title = label(r, "OBJECTIF", -0.852, 0.458, 0.5, rgb(226, 120, 90, 230), origin=(-0.5, 0), z=0)
        self.obj = Text(parent=r, text=" ", position=(-0.852, 0.447), origin=(-0.5, 0.5), scale=0.82 * ts, color=rgb(255, 255, 255, 215))
        # téléphone (bas gauche) et lampe (bas droite) : icône + jauge
        self.ph_img_on = ill.icon_phone(96, True)
        self.ph_icon = image(r, self.ph_img_on, -0.83, -0.425, 0.05, 0.05, z=0)
        self.ph_bar = ProgressBar(r, -0.76, -0.425, 0.09, 0.012, (120, 190, 255))
        self.ph_pct = label(r, "100 %", -0.76, -0.45, 0.45, rgb(180, 190, 210), z=0)
        self.fl_tex_on = theme._tex(ill.icon_flashlight(96, True))
        self.fl_tex_off = theme._tex(ill.icon_flashlight(96, False))
        self.fl_icon = Entity(parent=r, model="quad", texture=self.fl_tex_on, position=(0.83, -0.425, 0), scale=0.055)
        self.fl_bar = ProgressBar(r, 0.755, -0.425, 0.09, 0.012, (240, 220, 140))
        self.fl_pct = label(r, "100 %", 0.755, -0.45, 0.45, rgb(210, 200, 170), z=0)
        # réticule
        self.reticle = rect(r, 0, 0, 0.005, 0.005, rgb(255, 255, 255, 150), radius=0.5)
        # invite d'interaction : touche + texte sur pilule
        self.prompt_root = Entity(parent=r, y=-0.075, enabled=False)
        self.prompt_bg = panel(self.prompt_root, 0, 0, 0.3, 0.05, "panel", z=0.05, radius=0.5)
        kt, kw = theme.keycap_texture(config.settings.key("interagir").upper(), 64)
        self.prompt_key = Entity(parent=self.prompt_root, model="quad", texture=kt, scale=0.042, x=-0.13, z=0)
        self.prompt = label(self.prompt_root, "", -0.1, 0, 0.8, color.white, origin=(-0.5, 0), z=-0.01)
        # sous-titres / pensées
        self.sub_bg = rect(r, 0, -0.33, 1.1, 0.062, rgb(0, 0, 0, 0), z=0.1, radius=0.25)
        self.sub = label(r, "", 0, -0.33, 0.92, color.white, wrap=72, z=-0.1)
        self.sub_t = 0.0
        # notification de quête (bandeau haut centre)
        self.quest_root = Entity(parent=r, y=0.38, enabled=False)
        panel(self.quest_root, 0, 0, 0.62, 0.06, "panel", z=0.05, radius=0.4)
        rect(self.quest_root, -0.29, 0, 0.006, 0.036, rgb(255, 200, 90), z=0, radius=0.5)
        self.quest_note = label(self.quest_root, "", 0, 0, 0.85, rgb(255, 230, 160), z=-0.1)
        self.quest_t = 0.0
        self.tips = label(r, "", 0, -0.2, 0.72, rgb(205, 205, 210), wrap=80, z=-0.1)
        self.tips_t = 0.0
        # endurance / santé (sous le réticule)
        self.stamina = ProgressBar(r, 0, -0.47, 0.16, 0.007, (235, 235, 235))
        self.health = ProgressBar(r, 0, -0.455, 0.16, 0.007, (220, 60, 50))
        self.vol_icon = None
        self.hint_line = None
        self._last_key = None

    def show(self):
        self.root.enabled = True

    def hide(self):
        self.root.enabled = False

    def set_objective(self, text):
        self.obj.text = text or " "
        self.obj_bar.enabled = bool(text)
        self.obj_title.enabled = bool(text)

    def say(self, text, duration=3.5, speaker=None):
        self.sub.text = (f"{speaker} : " if speaker else "") + text
        self.sub_t = duration
        self.sub.color = color.white
        w = min(1.4, 0.08 + len(self.sub.text) * 0.0105)
        self.sub_bg.scale_x = w

    def quest(self, text, duration=4.0):
        self.quest_note.text = text
        self.quest_t = duration
        self.quest_root.enabled = True
        sound.play("ui_open", 0.35, channel="voice")

    def tip(self, text, duration=8.0):
        self.tips.text = text
        self.tips_t = duration

    def update(self, dt, game):
        p = game.player
        fb = p.flashlight.battery
        self.fl_bar.set(fb / 100.0)
        self.fl_pct.text = f"{int(fb)} %"
        self.fl_bar.fill.color = color.rgb32(240, 220, 140) if fb > 20 else color.rgb32(240, 110, 70)
        self.fl_icon.texture = self.fl_tex_on if p.flashlight.on else self.fl_tex_off
        b = game.phone.model.battery
        self.ph_bar.set(b / 100.0)
        self.ph_pct.text = f"{int(b)} %"
        self.ph_bar.fill.color = color.rgb32(120, 190, 255) if b > 20 else color.rgb32(240, 90, 80)
        # endurance : visible seulement quand entamée ; santé : seulement si blessé
        self.stamina.enabled = p.stamina < 99
        if self.stamina.enabled:
            self.stamina.set(p.stamina / 100.0)
            self.stamina.fill.color = color.rgb32(235, 235, 235) if getattr(p, "energy_t", 0) <= 0 else color.rgb32(90, 200, 255)
        self.health.enabled = p.health < 99
        if self.health.enabled:
            self.health.set(p.health / 100.0)
        if self.sub_t > 0:
            self.sub_t -= dt
            a = min(1.0, self.sub_t / 0.5)
            self.sub.color = color.rgba32(255, 255, 255, int(255 * a))
            self.sub_bg.color = rgb(0, 0, 0, int(140 * a))
            if self.sub_t <= 0:
                self.sub.text = ""
        if self.quest_t > 0:
            self.quest_t -= dt
            a = max(0.0, min(1.0, self.quest_t / 0.6))
            self.quest_note.color = rgb(255, 230, 160, int(255 * a))
            if self.quest_t <= 0:
                self.quest_note.text = ""
                self.quest_root.enabled = False
        if self.tips_t > 0:
            self.tips_t -= dt
            if self.tips_t <= 0:
                self.tips.text = ""
        # invite
        target = game.interactions.target
        pr = target.current_prompt() if (target is not None and not game.phone.is_open and not game.paused) else None
        if pr:
            k = config.settings.key("interagir").upper()
            if k != self._last_key:
                self._last_key = k
                self.prompt_key.texture = theme.keycap_texture(k, 64)[0]
            if self.prompt.text != pr:
                self.prompt.text = pr
                w = 0.1 + len(pr) * 0.0098
                self.prompt_root.x = 0
                self.prompt_key.x = -w / 2 + 0.03
                self.prompt.x = -w / 2 + 0.06
                destroy(self.prompt_bg)
                self.prompt_bg = panel(self.prompt_root, 0, 0, w, 0.05, "panel", z=0.05, radius=0.5)
            self.prompt_root.enabled = True
            self.reticle.scale = 0.008
        else:
            self.prompt_root.enabled = False
            self.prompt.text = ""
            self.reticle.scale = 0.005


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
        nb = getattr(self.game, "neighborhood", None)
        if nb is not None and nb.outside_phase:
            self.hud.set_objective(nb.objective())
            return
        self.hud.set_objective(self.game.quests.current_objective())

    def update(self, dt):
        self.menu.update(dt)
        self.ending.update(dt)
        self.toast.update(dt)
        if self.hud.root.enabled:
            self.hud.update(dt, self.game)
