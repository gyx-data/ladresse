"""Menu des paramètres : graphismes, audio, contrôles (remapping), accessibilité."""
from ursina import Entity, color, camera, window, application

import config
from config import settings
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb

TABS = ["Graphismes", "Audio", "Contrôles", "Accessibilité"]

GRAPHICS = [
    ("Qualité des ombres", "ombres", ["Basse", "Moyenne", "Haute"]),
    ("Distance de fog", "fog", ["Près", "Moyen", "Loin"]),
    ("Particules", "particules", [True, False]),
    ("Post-processing", "postprocess", [True, False]),
    ("Résolution", "resolution", ["720p", "1080p", "1440p", "Natif"]),
    ("Plein écran", "plein_ecran", [True, False]),
    ("VSync", "vsync", [True, False]),
    ("FPS max", "fps_max", ["30", "60", "120", "Illimité"]),
]

AUDIO = [
    ("Volume principal", "vol_main"),
    ("Volume musique / ambiance", "vol_music"),
    ("Volume effets", "vol_sfx"),
    ("Volume voix / téléphone", "vol_voice"),
]

ACCESS = [
    ("Réduire les jumpscares", "reduire_jumpscares", [True, False]),
    ("Daltonien", "daltonien", ["Normal", "Protanopie", "Deutéranopie", "Tritanopie"]),
    ("Taille des textes", "taille_texte", ["Petit", "Moyen", "Grand"]),
]


def fmt(v):
    if v is True:
        return "Oui"
    if v is False:
        return "Non"
    return str(v)


def apply_settings(game=None):
    """Applique les paramètres au moteur (fenêtre, FPS, FOV...)."""
    try:
        res = settings["resolution"]
        if res in config.RESOLUTIONS and not settings["plein_ecran"]:
            window.size = config.RESOLUTIONS[res]
        window.fullscreen = bool(settings["plein_ecran"])
    except Exception:
        pass
    try:
        from panda3d.core import ClockObject, AntialiasAttrib
        base = application.base
        fps = settings["fps_max"]
        if fps == "Illimité":
            base.clock.setMode(ClockObject.MNormal)
        else:
            base.clock.setMode(ClockObject.MLimited)
            base.clock.setFrameRate(int(fps))
        base.render.setAntialias(AntialiasAttrib.MAuto if settings["msaa"] else 0)
        window.vsync = bool(settings["vsync"])
    except Exception:
        pass
    if game is not None and getattr(game, "player", None) is not None:
        game.player.fov = settings["fov"]
        game.lighting.max_point_lights = {"Basse": 3, "Moyenne": 6, "Haute": 8}.get(settings["ombres"], 6)
    settings.save()


class SettingsMenu:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-18, enabled=False)
        self.tab = 0
        self.body = None
        self.waiting_for = None
        self.on_close = None
        self.visible = False
        self._build()

    def _build(self):
        rect(self.root, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 225), z=1)
        label(self.root, "PARAMÈTRES", 0, 0.42, 2.2, color.white, z=0)
        x = -0.42
        self.tab_buttons = []
        for i, t in enumerate(TABS):
            b = button(self.root, t, x + i * 0.28, 0.34, 0.26, 0.05, (lambda i=i: self.set_tab(i)), rgb(30, 30, 34, 235), size=0.8)
            self.tab_buttons.append(b)
        self.body = Entity(parent=self.root)
        button(self.root, "Retour", 0, -0.44, 0.24, 0.06, self.close, rgb(40, 40, 46, 240), size=1.0)
        button(self.root, "Valeurs par défaut", 0.4, -0.44, 0.28, 0.06, self.reset, rgb(70, 30, 30, 240), size=0.8)

    def open(self, on_close=None):
        self.visible = True
        self.on_close = on_close
        self.root.enabled = True
        self.set_tab(self.tab)
        self.game.set_mouse(free=True)

    def close(self):
        self.visible = False
        self.root.enabled = False
        self.waiting_for = None
        apply_settings(self.game)
        if self.on_close:
            cb, self.on_close = self.on_close, None
            cb()

    def reset(self):
        settings.reset()
        self.set_tab(self.tab)
        apply_settings(self.game)

    def set_tab(self, i):
        self.tab = i
        for j, b in enumerate(self.tab_buttons):
            b.color = rgb(70, 60, 40, 245) if j == i else rgb(30, 30, 34, 235)
        clear(self.body)
        [self._graphics, self._audio, self._controls, self._access][i]()

    # --- onglets --------------------------------------------------------
    def _cycle_row(self, y, name, key, options):
        label(self.body, name, -0.45, y, 0.9, color.white, origin=(-0.5, 0))
        cur = settings[key]
        val = label(self.body, fmt(cur), 0.28, y, 0.9, rgb(255, 220, 140), z=-0.02)

        def step(d):
            c = settings[key]
            idx = options.index(c) if c in options else 0
            settings[key] = options[(idx + d) % len(options)]
            val.text = fmt(settings[key])
            sound.play("tap", 0.5, channel="voice")
            if key in ("fog", "daltonien", "taille_texte"):
                pass
        button(self.body, "‹", 0.12, y, 0.04, 0.04, lambda: step(-1), rgb(50, 50, 56), size=0.8)
        button(self.body, "›", 0.44, y, 0.04, 0.04, lambda: step(1), rgb(50, 50, 56), size=0.8)

    def _graphics(self):
        y = 0.25
        for name, key, opts in GRAPHICS:
            self._cycle_row(y, name, key, opts)
            y -= 0.075
        label(self.body, "Le fog fait partie de l'ambiance : « Près » est le plus angoissant.", 0, -0.37, 0.6, color.gray)

    def _slider_row(self, y, name, key, lo, hi, step_v):
        label(self.body, name, -0.45, y, 0.9, color.white, origin=(-0.5, 0))
        rect(self.body, 0.26, y, 0.24, 0.012, rgb(50, 50, 56), z=-0.01)
        fill = rect(self.body, 0.14, y, 0.001, 0.012, rgb(255, 200, 100), z=-0.02)
        fill.origin = (-0.5, 0)
        fill.x = 0.14
        val = label(self.body, str(settings[key]), 0.46, y, 0.9, rgb(255, 220, 140), z=-0.02)

        def refresh():
            frac = (settings[key] - lo) / (hi - lo)
            fill.scale_x = max(0.001, 0.24 * frac)
            val.text = str(settings[key])

        def change(d):
            settings[key] = max(lo, min(hi, settings[key] + d * step_v))
            refresh()
            sound.play("tap", 0.6, channel="voice")
            if key == "fov":
                self.game.player.fov = settings["fov"]
        button(self.body, "-", 0.09, y, 0.04, 0.04, lambda: change(-1), rgb(50, 50, 56), size=0.9)
        button(self.body, "+", 0.43 - 0.02, y, 0.04, 0.04, lambda: change(1), rgb(50, 50, 56), size=0.9)
        refresh()

    def _audio(self):
        y = 0.22
        for name, key in AUDIO:
            self._slider_row(y, name, key, 0, 100, 5)
            y -= 0.09
        self._cycle_row(y - 0.02, "Sous-titres", "sous_titres", [True, False])

    def _controls(self):
        self._slider_row(0.26, "Sensibilité souris (1-20)", "sensibilite", 1, 20, 1)
        self._cycle_row(0.19, "Inverser Y", "inverser_y", [True, False])
        self._slider_row(0.12, "FOV (60-110)", "fov", 60, 110, 5)
        label(self.body, "Remapping des touches (cliquer puis appuyer sur la touche)", -0.45, 0.05, 0.7, color.gray, origin=(-0.5, 0))
        y = -0.01
        for i, (act, name) in enumerate(config.KEY_LABELS.items()):
            x = -0.45 + (i % 2) * 0.5
            yy = y - (i // 2) * 0.06
            label(self.body, name, x, yy, 0.7, color.white, origin=(-0.5, 0))
            b = button(self.body, settings.key(act).upper(), x + 0.32, yy, 0.14, 0.045, None, rgb(50, 50, 60), size=0.6)
            b.on_click = (lambda a=act, b=b: self.start_remap(a, b))

    def _access(self):
        y = 0.22
        for name, key, opts in ACCESS:
            self._cycle_row(y, name, key, opts)
            y -= 0.09
        label(self.body, "« Réduire les jumpscares » atténue les flashs et le volume des stingers.", 0, -0.2, 0.6, color.gray)

    def start_remap(self, action, btn):
        self.waiting_for = (action, btn)
        btn.text_entity.text = "..."

    def on_key(self, key):
        if self.waiting_for is None or key in ("left mouse down", "left mouse up", "right mouse down"):
            return
        act, btn = self.waiting_for
        self.waiting_for = None
        if key == "escape":
            btn.text_entity.text = settings.key(act).upper()
            return
        # évite les doublons : échange
        for other, k in list(settings["keys"].items()):
            if k == key and other != act:
                settings["keys"][other] = settings.key(act)
        settings["keys"][act] = key
        self.set_tab(2)
