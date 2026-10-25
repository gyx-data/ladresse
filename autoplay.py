"""Partie automatique de vérification (variable d'environnement LADRESSE_AUTOPLAY=1).

Lance le vrai jeu (fenêtre, rendu, sons), démarre une partie dans le quartier, se déplace, passe en vue
troisième personne, achète des articles à la caisse automatique, ouvre le téléphone et l'inventaire,
entre dans la maison, puis quitte. Captures d'écran et rapport dans %APPDATA%/LADRESSE/autoplay/.
Code de sortie 0 si aucune erreur n'a été journalisée.
"""
import os
import time
import traceback

import config

OUT = os.path.join(config.app_data_dir(), "autoplay")
log_lines = []
errors = []


def _log(msg):
    log_lines.append(time.strftime("%H:%M:%S ") + msg)


def _shot(name):
    try:
        from ursina import application
        application.base.screenshot(os.path.join(OUT, name + ".png"), defaultFilename=False)
        _log("capture " + name)
    except Exception as e:
        _log(f"capture {name} impossible : {e}")


def scenario(game):
    from ursina import held_keys
    from config import settings
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    while game.mode == "loading":
        if time.time() - t0 > 240:
            errors.append("chargement trop long")
            return
        yield
    for _ in range(30):
        yield
    _shot("01_menu")
    settings["quartier"] = True
    game.ui.menu.hide()
    game._stop_menu()
    game.reset_game_objects()
    game._fresh_world()
    game.player.revive()
    game.begin_play(fresh=True)
    for _ in range(40):
        yield
    _shot("02_quartier")
    p = game.player
    held_keys["w"] = 1
    for _ in range(60):
        yield
    held_keys["w"] = 0
    _log(f"déplacement : {p.pos}")
    settings["vue"] = "Troisième personne"
    for _ in range(30):
        yield
    _shot("03_troisieme_personne")
    settings["vue"] = "Première personne"
    nb = game.neighborhood
    from shop import CATALOG_BY_ID
    p.place((14.85, 0.0, -27.0), 90.0, 10.0)
    for _ in range(20):
        yield
    _shot("04_magasin")
    nb.take(CATALOG_BY_ID["piles"])
    nb.take(CATALOG_BY_ID["eau"])
    nb.checkout.open(nb._on_paid)
    nb.checkout._scan_all()
    nb.checkout._scan_card()
    for _ in range(15):
        yield
    _shot("05_caisse")
    nb.checkout._pay()
    nb.checkout._do_pay()
    nb.checkout.close()
    game.phone.open()
    for _ in range(30):
        yield
    _shot("06_telephone")
    game.phone.close()
    game.inv_panel.show()
    for _ in range(10):
        yield
    _shot("07_inventaire")
    game.inv_panel.hide()
    p.place((7.0, 0.0, -1.2), 0.0, 0.0)
    held_keys["w"] = 1
    for _ in range(80):
        yield
        if not nb.outside_phase:
            break
    held_keys["w"] = 0
    for _ in range(30):
        yield
    _shot("08_maison")
    _log(f"dans la maison : {not nb.outside_phase}, zone {p.zone}")
    if nb.outside_phase:
        errors.append("entrée dans la maison non détectée")
    _log(f"durée totale {time.time() - t0:.1f} s")


def install(game, app):
    import crash_handler
    gen = scenario(game)
    state = {"done": False}
    start_errors = len(getattr(crash_handler, "_seen", {}))

    def tick():
        if state["done"]:
            return
        try:
            next(gen)
        except StopIteration:
            state["done"] = True
            finish(crash_handler, start_errors)
        except Exception:
            errors.append(traceback.format_exc())
            state["done"] = True
            finish(crash_handler, start_errors)
    return tick


def finish(crash_handler, start_errors):
    seen = getattr(crash_handler, "_seen", {})
    if len(seen) > start_errors:
        errors.append(f"{len(seen) - start_errors} erreur(s) dans crash.log : " + "; ".join(list(seen)[:3]))
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "rapport.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
        f.write("\n\nRÉSULTAT : " + ("OK" if not errors else "ÉCHEC\n" + "\n".join(errors)) + "\n")
    os._exit(0 if not errors else 1)
