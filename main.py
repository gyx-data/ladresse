"""L'ADRESSE — jeu d'horreur 3D en première personne (Ursina Engine).

Point d'entrée : `python main.py` (ou LADRESSE.exe une fois compilé avec build.py).
Tous les assets (textures, sons, modèles) sont générés de manière procédurale au lancement.
"""
import os
import sys

# Les chemins relatifs (assets Ursina embarqués, etc.) doivent partir du dossier du jeu.
if getattr(sys, "frozen", False):
    os.chdir(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)))
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mode --windowed (PyInstaller) : pas de console, sys.stdout/sys.stderr valent None.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from panda3d.core import loadPrcFileData

import config
from config import settings

# Anti-aliasing MSAA (4x par défaut) et réglages Panda3D, à définir avant la création de la fenêtre.
msaa = int(settings["msaa"] or 0)
if msaa:
    loadPrcFileData("", f"framebuffer-multisample 1\nmultisamples {msaa}")
loadPrcFileData("", "notify-level-audio error\nnotify-level-display error\nnotify-level-glgsg error")
loadPrcFileData("", "sync-video 1" if settings["vsync"] else "sync-video 0")

from ursina import Ursina, window, camera, color, time as utime


def _icon_path():
    """Génère l'icône du jeu (maison sombre + point lumineux) au besoin."""
    try:
        from texture_generator import make_icon_ico
        path = os.path.join(config.cache_dir(), "icon.ico")
        if not os.path.exists(path):
            make_icon_ico(path)
        return path
    except Exception:
        return None


def create_app():
    kwargs = dict(title=config.GAME_TITLE, borderless=False, fullscreen=bool(settings["plein_ecran"]),
                  vsync=bool(settings["vsync"]), development_mode=False, show_ursina_splash=False)
    icon = _icon_path()
    if icon:
        kwargs["icon"] = icon
    if not settings["plein_ecran"]:
        res = config.RESOLUTIONS.get(settings["resolution"], (1280, 720))
        kwargs["size"] = res
    app = Ursina(**kwargs)
    window.title = config.GAME_TITLE
    window.color = color.black
    for name in ("exit_button", "fps_counter", "cog_button", "entity_counter", "collider_counter"):
        try:
            getattr(window, name).enabled = False
        except Exception:
            pass
    camera.clip_plane_far = 120
    return app


def _optimize_ursina():
    """Ursina parcourt toutes les entités à chaque frame (update/input). Les entités « plain » et les
    textes n'ont pas besoin de ça (tout est piloté par GameManager) : on les ignore pour gagner
    plusieurs millisecondes par frame. Les boutons et champs de saisie restent actifs."""
    from ursina import Entity
    from ursina.shaders import unlit_shader
    Entity.default_shader = unlit_shader
    original = Entity.__init__

    def fast_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        if type(self).__name__ in ("Entity", "Text"):
            self.ignore = True
    Entity.__init__ = fast_init


app = create_app()
_optimize_ursina()
import typography
typography.apply_ui_font()

import crash_handler
crash_handler.install()

from game_manager import GameManager

game = GameManager(app)


def update():
    try:
        game.update(utime.dt)
    except Exception:
        # une erreur ponctuelle ne doit pas fermer le jeu : elle est journalisée (crash.log)
        crash_handler.log_exception("update")


def input(key):
    try:
        game.on_input(key)
    except Exception:
        crash_handler.log_exception("input " + str(key))


if __name__ == "__main__":
    app.run()
