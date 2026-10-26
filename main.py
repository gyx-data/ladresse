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
    sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
# Console Windows (cp1252 / cp850) : un caractère non encodable ne doit jamais lever d'exception
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

def _close_splash():
    """Ferme l'écran de démarrage PyInstaller (sinon il resterait affiché par-dessus le jeu)."""
    try:
        import pyi_splash
        pyi_splash.close()
    except Exception:
        pass


if "--selftest" in sys.argv:
    _close_splash()
    import selftest
    sys.exit(selftest.run())

from panda3d.core import loadPrcFileData

import config
from config import settings

# Anti-aliasing MSAA (4x par défaut) et réglages Panda3D, à définir avant la création de la fenêtre.
msaa = int(settings["msaa"] or 0)
if msaa:
    loadPrcFileData("", f"framebuffer-multisample 1\nmultisamples {msaa}")
loadPrcFileData("", "notify-level-audio error\nnotify-level-display error\nnotify-level-glgsg error")
loadPrcFileData("", "sync-video 1" if settings["vsync"] else "sync-video 0")
# tampon de profondeur 24 bits (le tampon de post-traitement en demandait « au moins 1 », souvent 16 bits) :
# plus de scintillement entre surfaces proches (tableaux, vitres, décalcomanies) vues de loin
loadPrcFileData("", "depth-bits 24")
# les états de rendu (transformations, attributs) inutilisés sont ramassés par quarts à chaque image au lieu d'être
# tous parcourus à chaque image (~1 ms par image avec les passants animés) ; la mémoire est libérée pareil
loadPrcFileData("", "garbage-collect-states-rate 0.25")

from ursina import Ursina, window, camera, color, time as utime
from ursina import text as _ursina_text

# Ursina retrouve la police par un glob récursif dans tout le dossier du jeu à CHAQUE texte créé (≈ 7 ms par libellé :
# une caisse automatique = 50 textes = 0,4 s de gel à chaque clic). Le chemin trouvé ne change pas : on le garde.
_FONT_PATHS = {}
_search_for_file = _ursina_text._search_for_file


def _cached_search_for_file(name, folders, file_types=None):
    key = (name, tuple(str(f) for f in folders), file_types)
    if key not in _FONT_PATHS:
        _FONT_PATHS[key] = _search_for_file(name, folders, file_types)
    return _FONT_PATHS[key]


_ursina_text._search_for_file = _cached_search_for_file


class _CachedFontPool:
    """FontPool qui garde ses polices : Ursina rallonge le chemin des modèles à chaque texte et le FontPool de Panda
    refait alors une recherche de plus en plus longue (≈ 6 ms par libellé)."""
    _pool = _ursina_text.FontPool
    _fonts = {}

    @classmethod
    def load_font(cls, name):
        if name not in cls._fonts:
            cls._fonts[name] = cls._pool.load_font(name)
        return cls._fonts[name]


_ursina_text.FontPool = _CachedFontPool


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
    if os.environ.get("LADRESSE_TESTS_INVISIBLES"):
        # tests automatiques : fenêtre placée hors de l'écran, en arrière-plan, et priorité basse, pour ne pas gêner
        # la personne qui travaille sur la machine (un tampon hors écran ne supporte pas les réglages de fenêtre)
        kwargs["position"] = (-6000, -6000)
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
        except Exception:
            pass
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


import perf                     # boucle d'update allégée, minuterie Windows précise (perf.py)
perf.install()
app = create_app()


def _hide_test_window(task=None):
    """Tests automatiques : la fenêtre reste hors de l'écran et en arrière-plan (Ursina la recentre en démarrant)."""
    from panda3d.core import WindowProperties
    wp = WindowProperties()
    wp.setOrigin(-6000, -6000)
    wp.setForeground(False)
    wp.setZOrder(WindowProperties.Z_bottom)
    app.win.requestProperties(wp)
    return task.again if task is not None else None


if os.environ.get("LADRESSE_TESTS_INVISIBLES"):
    _hide_test_window()
    app.taskMgr.doMethodLater(0.5, _hide_test_window, "fenetre_tests")
_close_splash()
_optimize_ursina()
import typography
typography.apply_ui_font()

import crash_handler
crash_handler.install()

from game_manager import GameManager

game = GameManager(app)
_autoplay = None
if os.environ.get("LADRESSE_AUTOPLAY") == "1":
    import autoplay
    _autoplay = autoplay.install(game, app)


def update():
    try:
        game.update(utime.dt)
    except Exception:
        # une erreur ponctuelle ne doit pas fermer le jeu : elle est journalisée (crash.log)
        crash_handler.log_exception("update")
    if _autoplay is not None:
        _autoplay()


def input(key):
    try:
        game.on_input(key)
    except Exception:
        crash_handler.log_exception("input " + str(key))


if __name__ == "__main__":
    app.run()
