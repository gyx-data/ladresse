"""Menu des paramètres : graphismes, audio, contrôles (remapping), caméra, jeu, accessibilité.

Interface « thème » : panneau arrondi, onglets, curseurs déplaçables, interrupteurs, sélecteurs ‹ ›.
Toutes les valeurs sont appliquées immédiatement et sauvegardées à la fermeture.
"""
from ursina import Entity, color, camera, window, application

import config
import typography as T
from config import settings
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb, panel, UISlider, UIToggle

TABS = ["Graphismes", "Audio", "Contrôles", "Caméra", "Jeu", "Accessibilité"]

GRAPHICS = [
    ("Qualité de l'éclairage", "ombres", ["Basse", "Moyenne", "Haute"]),
    ("Distance de brouillard", "fog", ["Près", "Moyen", "Loin"]),
    ("Particules et faisceau", "particules", None),
    ("Post-processing", "postprocess", None),
    ("Résolution", "resolution", ["720p", "1080p", "1440p", "Natif"]),
    ("Plein écran", "plein_ecran", None),
    ("Synchronisation verticale", "vsync", None),
    ("Images par seconde max", "fps_max", ["30", "60", "120", "144", "Illimité"]),
]

AUDIO = [
    ("Volume principal", "vol_main"),
    ("Musique / ambiance", "vol_music"),
    ("Effets", "vol_sfx"),
    ("Voix / téléphone", "vol_voice"),
]

CAMERA = [
    ("Vue", "vue", ["Première personne", "Troisième personne"]),
    ("Épaule (3e personne)", "cam_epaule", ["Droite", "Centre", "Gauche"]),
    ("Caméra amortie", "cam_lissage", None),
    ("Balancement de la tête", "bob_camera", None),
]

GAMEPLAY = [
    ("Explorer le quartier au début", "quartier", None),
    ("Didacticiel (aide à l'écran + voix)", "didacticiel", None),
    ("Pause auto (perte de focus)", "pause_auto", None),
    ("Afficher les FPS", "afficher_fps", None),
]

ACCESS = [
    ("Réduire les jumpscares", "reduire_jumpscares", None),
    ("Sous-titres", "sous_titres", None),
    ("Mode daltonien", "daltonien", ["Normal", "Protanopie", "Deutéranopie", "Tritanopie"]),
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
    try:
        window.fps_counter.enabled = bool(settings.get("afficher_fps", False))
    except Exception:
        pass
    if game is not None and getattr(game, "player", None) is not None:
        game.player.fov = settings["fov"]
        game.lighting.max_point_lights = {"Basse": 4, "Moyenne": 6, "Haute": 8}.get(settings["ombres"], 6)
    settings.save()


class SettingsMenu:
    W, H = 1.32, 0.86

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
        r = self.root
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 200), z=2)
        panel(r, 0, 0, self.W, self.H, "panel", z=1.5)
        label(r, "PARAMÈTRES", -self.W / 2 + 0.05, self.H / 2 - 0.05, 2.4, rgb(226, 218, 204), origin=(-0.5, 0), z=1, font=T.F_HORROR)
        rect(r, 0, self.H / 2 - 0.135, self.W - 0.06, 0.002, rgb(80, 70, 70), z=1)
        self.tab_buttons = []
        tw = (self.W - 0.08) / len(TABS)
        for i, t in enumerate(TABS):
            b = button(r, t, -self.W / 2 + 0.04 + tw * (i + 0.5), self.H / 2 - 0.1, tw - 0.012, 0.046, (lambda i=i: self.set_tab(i)),
                       style="ghost", size=0.62, z=0.9)
            self.tab_buttons.append(b)
        self.tab_marker = rect(r, 0, self.H / 2 - 0.128, tw - 0.03, 0.005, rgb(170, 22, 20), z=0.8, radius=0.5)
        self.tw = tw
        self.body = Entity(parent=r, z=0.5)
        button(r, "Retour", self.W / 2 - 0.13, -self.H / 2 + 0.05, 0.2, 0.055, self.close, style="primary", size=0.8, z=0.9)
        button(r, "Valeurs par défaut", -self.W / 2 + 0.16, -self.H / 2 + 0.05, 0.26, 0.05, self.reset, style="dark", size=0.65, z=0.9)

    def open(self, on_close=None):
        self.visible = True
        self.on_close = on_close
        self.root.enabled = True
        self.set_tab(self.tab)
        self.game.set_mouse(free=True)
        sound.play("ui_open", 0.5, channel="voice")

    def close(self):
        self.visible = False
        self.root.enabled = False
        self.waiting_for = None
        apply_settings(self.game)
        if self.on_close:
            cb, self.on_close = self.on_close, None
            cb()

    def reset(self):
        keep = {k: settings.get(k) for k in ("mp_adresse", "mp_pseudo")}
        settings.reset()
        settings.data.update(keep)
        self.set_tab(self.tab)
        apply_settings(self.game)

    def set_tab(self, i):
        self.tab = i
        for j, b in enumerate(self.tab_buttons):
            b.text_entity.color = color.white if j == i else rgb(150, 148, 145)
        self.tab_marker.x = -self.W / 2 + 0.04 + self.tw * (i + 0.5)
        clear(self.body)
        [self._graphics, self._audio, self._controls, self._camera, self._gameplay, self._access][i]()

    # --- lignes ----------------------------------------------------------
    def _row_bg(self, y):
        rect(self.body, 0, y, self.W - 0.1, 0.056, rgb(255, 255, 255, 8), z=0.1, radius=0.2)

    def _cycle_row(self, y, name, key, options, on_change=None):
        self._row_bg(y)
        label(self.body, name, -self.W / 2 + 0.07, y, 0.82, rgb(226, 218, 204), origin=(-0.5, 0), font=T.F_TYPE)
        if options is None:
            def tog(v):
                settings[key] = v
                if on_change:
                    on_change(v)
            UIToggle(self.body, self.W / 2 - 0.12, y, bool(settings.get(key, False)), tog)
            return
        val = label(self.body, fmt(settings.get(key)), self.W / 2 - 0.2, y, 0.8, rgb(226, 218, 204), z=-0.02, font=T.F_TYPE)

        def step(d):
            c = settings.get(key)
            idx = options.index(c) if c in options else 0
            settings[key] = options[(idx + d) % len(options)]
            val.text = fmt(settings[key])
            sound.play("ui_click", 0.5, channel="voice")
            if on_change:
                on_change(settings[key])
        button(self.body, "‹", self.W / 2 - 0.36, y, 0.04, 0.04, lambda: step(-1), style="dark", size=0.8)
        button(self.body, "›", self.W / 2 - 0.05, y, 0.04, 0.04, lambda: step(1), style="dark", size=0.8)

    def _slider_row(self, y, name, key, lo, hi, step_v, suffix="", on_change=None):
        self._row_bg(y)
        label(self.body, name, -self.W / 2 + 0.07, y, 0.82, rgb(226, 218, 204), origin=(-0.5, 0), font=T.F_TYPE)
        val = label(self.body, f"{settings[key]}{suffix}", self.W / 2 - 0.06, y, 0.8, rgb(226, 218, 204), origin=(0.5, 0), z=-0.02, font=T.F_TYPE)

        def change(v):
            if isinstance(settings[key], float):
                v = round(float(v), 2)
            settings[key] = v
            val.text = f"{v}{suffix}"
            if on_change:
                on_change(v)
        UISlider(self.body, self.W / 2 - 0.33, y, 0.36, lo, hi, settings[key], change, step_v)

    # --- onglets ---------------------------------------------------------
    def _rows(self, rows, y=0.24, gap=0.066):
        for name, key, opts in rows:
            self._cycle_row(y, name, key, opts)
            y -= gap
        return y

    def _graphics(self):
        y = self._rows(GRAPHICS)
        label(self.body, "Le brouillard fait partie de l'ambiance : « Près » est le plus angoissant.", 0, y - 0.01, 0.6, color.gray)

    def _audio(self):
        y = 0.24
        for name, key in AUDIO:
            self._slider_row(y, name, key, 0, 100, 5, " %", on_change=lambda v: sound.apply_volumes() if hasattr(sound, "apply_volumes") else None)
            y -= 0.075
        self._cycle_row(y, "Voix réelles du système (redémarrage)", "voix_reelles", None)
        try:
            from tts import tts
            st = tts.status
        except Exception:
            st = "indisponible"
        label(self.body, "Moteur vocal : " + st, 0, y - 0.06, 0.55, color.gray, max_w=self.W - 0.12)
        label(self.body, "Astuce Windows : Paramètres > Heure et langue > Voix > ajouter une voix française.", 0, y - 0.1, 0.52,
              rgb(120, 118, 115), max_w=self.W - 0.12)

    def _controls(self):
        self._slider_row(0.26, "Sensibilité de la souris", "sensibilite", 1, 30, 1)
        self._cycle_row(0.195, "Inverser l'axe Y", "inverser_y", None)
        label(self.body, "Touches — cliquez puis appuyez sur la nouvelle touche (Échap pour annuler)", -self.W / 2 + 0.07, 0.13, 0.62,
              color.gray, origin=(-0.5, 0))
        y = 0.08
        for i, (act, name) in enumerate(config.KEY_LABELS.items()):
            x = -self.W / 2 + 0.07 + (i % 2) * (self.W / 2 - 0.02)
            yy = y - (i // 2) * 0.054
            label(self.body, name, x, yy, 0.64, rgb(226, 218, 204), origin=(-0.5, 0), font=T.F_TYPE)
            b = button(self.body, settings.key(act).upper(), x + self.W / 2 - 0.18, yy, 0.15, 0.042, None, style="key", size=0.58)
            b.on_click = (lambda a=act, b=b: self.start_remap(a, b))

    def _camera(self):
        def fov(v):
            self.game.player.fov = v

        def view(v):
            self.game.player.cam_dist = 0.0
        self._slider_row(0.26, "Champ de vision (FOV)", "fov", 60, 110, 1, "°", on_change=fov)
        self._slider_row(0.194, "Distance caméra 3e personne", "cam_distance", 1.2, 4.5, 0.1, " m")
        y = 0.128
        for name, key, opts in CAMERA:
            self._cycle_row(y, name, key, opts, on_change=view if key == "vue" else None)
            y -= 0.066
        label(self.body, f"Touche {settings.key('vue').upper()} : basculer à tout moment entre 1re et 3e personne.",
              0, y - 0.01, 0.62, color.gray)

    def _gameplay(self):
        y = self._rows(GAMEPLAY)
        d = settings["difficulte"]
        label(self.body, f"Difficulté : {d}  ·  {config.DIFFICULTY_TEXT.get(d, ('',))[0]}", 0, y - 0.01, 0.62, color.gray)
        label(self.body, "Elle se choisit au lancement d'une nouvelle partie et reste la même jusqu'à la fin.", 0, y - 0.06,
              0.55, rgb(120, 118, 115))

    def _access(self):
        y = self._rows(ACCESS)
        label(self.body, "« Réduire les jumpscares » atténue les flashs et le volume des stingers.", 0, y - 0.01, 0.6, color.gray)

    # --- remapping ---------------------------------------------------------
    def start_remap(self, action, btn):
        self.waiting_for = (action, btn)
        btn.text_entity.text = "..."

    def on_key(self, key):
        if self.waiting_for is None or key in ("left mouse down", "left mouse up", "right mouse down", "right mouse up",
                                               "scroll up", "scroll down") or key.endswith(" up"):
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
