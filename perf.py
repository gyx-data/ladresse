"""Optimisations moteur, sans effet visible (installées par main.py avant la création de la fenêtre).

* Boucle d'update d'Ursina : la boucle d'origine passe chaque image sur TOUTES les entités de la scène (~2 600 : décors,
  pièces, interface) pour savoir si elles ont une méthode update, alors qu'une dizaine seulement en ont une. On garde la
  même logique, mais sur la liste des entités concernées, recalculée dès que le nombre d'entités change et toutes les
  REFRESH images (une méthode update ajoutée après coup est prise en compte en moins d'un quart de seconde).
* Minuterie Windows à 1 ms : le limiteur d'images de Panda3D dort par tranches de 15,6 ms par défaut, ce qui donnait
  ~55 i/s au lieu de 60 avec la limite par défaut.
"""
import sys

REFRESH = 15


def install_timer_resolution():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


def install_fast_update():
    """Remplace Ursina._update (à appeler avant Ursina()) par une version qui ne parcourt que les entités utiles."""
    try:
        import __main__
        from ursina import application, scene, time, mouse
        from ursina import main as umain
        from direct.task import Task
    except Exception:
        return
    audio = getattr(umain, "_audio_manager", None)
    cache = {"n": -1, "frames": REFRESH, "list": []}

    def wants_update(e):
        if hasattr(e, "update") and callable(e.update):
            return True
        if getattr(e, "scripts", None):
            return True
        sh = e.shader
        return sh is not None and bool(getattr(sh, "continuous_input", None))

    def candidates():
        ents = scene.entities
        cache["frames"] += 1
        if len(ents) != cache["n"] or cache["frames"] >= REFRESH:
            cache["n"] = len(ents)
            cache["frames"] = 0
            cache["list"] = [e for e in ents if wants_update(e)]
        return cache["list"]

    def _update(self, task=None):
        if application.calculate_dt:
            time.dt_unscaled = globalClock.getDt()          # noqa: F821 (fourni par Panda3D)
            time.dt = time.dt_unscaled * application.time_scale
        mouse.update()

        if hasattr(__main__, "update") and __main__.update and not application.paused:
            __main__.update()

        for seq in application.sequences:
            seq.update()

        if scene._entities_marked_for_removal:
            scene.entities = [e for e in scene.entities if e not in scene._entities_marked_for_removal]
            scene._entities_marked_for_removal.clear()
            cache["n"] = -1

        removed = scene._entities_marked_for_removal
        for e in candidates():
            if removed and e in removed:
                continue
            if not e:
                continue
            if not e.enabled or e.ignore:
                continue
            if application.paused and e.ignore_paused is False:
                continue
            if e.has_disabled_ancestor():
                continue

            if hasattr(e, "update") and callable(e.update):
                e.update()
            if not e:
                continue

            if hasattr(e, "scripts"):
                for script in e.scripts:
                    if script.enabled and hasattr(script, "update") and callable(script.update):
                        script.update()
            if not e:
                continue

            if e.shader and hasattr(e.shader, "continuous_input"):
                for key, value in e.shader.continuous_input.items():
                    e.set_shader_input(key, value())

        mgr = audio if audio is not None else getattr(umain, "_audio_manager", None)
        if mgr is not None:
            mgr.update()
        return Task.cont

    # « Ursina » est un mandataire @singleton : la vraie classe est dans la fermeture de son __new__
    real = None
    for cell in getattr(getattr(umain.Ursina, "__new__", None), "__closure__", None) or ():
        obj = cell.cell_contents
        if isinstance(obj, type) and hasattr(obj, "_update"):
            real = obj
    if real is None and hasattr(umain.Ursina, "_update"):
        real = umain.Ursina
    if real is not None:
        real._update = _update


def install():
    install_timer_resolution()
    install_fast_update()
