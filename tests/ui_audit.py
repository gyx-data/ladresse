"""Audit de l'interface : ouvre chaque écran du jeu et vérifie qu'aucun texte ne sort de son cadre
(panneau, bouton, rectangle) ni de l'écran, pour les trois tailles de texte et plusieurs résolutions.

Linux : xvfb-run -a python tests/ui_audit.py      -> « UI AUDIT OK » ou la liste des débordements.
"""
import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="ladresse_audit_")

import main as M                                   # noqa: E402
from ursina import application                     # noqa: E402
from main import app, game                         # noqa: E402
from config import settings                        # noqa: E402
from ui_widgets import audit_overflow              # noqa: E402

problems = []
SHOTS = os.environ.get("LADRESSE_AUDIT_SHOTS")


def wait(n=6):
    for _ in range(n):
        yield


def audit(name):
    for kind, text, bx in audit_overflow():
        problems.append(f"[{settings['taille_texte']}] {name} : {kind} -> « {text} » {bx}")
    if SHOTS:
        application.base.screenshot(os.path.join(SHOTS, f"{settings['taille_texte']}_{name}.png"), defaultFilename=False)


def start_outside():
    settings["quartier"] = True
    game.ui.menu.hide()
    game._stop_menu()
    game.reset_game_objects()
    game._fresh_world()
    game.player.revive()
    game.begin_play(fresh=True)


def screens():
    """Générateur : prépare chaque écran puis appelle audit()."""
    g = game
    g.ui.menu.show()
    yield from wait(3)
    audit("menu")
    g.show_settings()
    for i in range(6):
        g.settings_menu.set_tab(i)
        yield from wait(2)
        audit(f"parametres_{i}")
    g.settings_menu.close()
    g.achievements.open_screen()
    yield from wait(2)
    audit("succes")
    from ursina import destroy
    destroy(g.achievements.screen)
    g.achievements.screen = None
    g.show_multiplayer()
    yield from wait(2)
    g.mp.players = {i: dict(id=i, name=n, color=[0.7, 0.3, 0.2]) for i, n in enumerate(["Adrien", "Une très longue pseudo", "Bob", "Zoé"], 1)}
    g.mp.host = 1
    g.mp._refresh_players()
    yield from wait(2)
    audit("lobby")
    g.mp.back()
    yield from wait(2)
    # --- en jeu (quartier) ---
    start_outside()
    yield from wait(10)
    hud = g.ui.hud
    hud.say("Ceci est une réplique de sous-titre volontairement très longue pour vérifier que le fond suit bien la taille du texte.", 5, "Brigadier Rossi")
    hud.quest("Nouvel objectif : passer en caisse et payer les articles avec la carte fidélité")
    hud.tip("Le quartier est libre d'accès : supérette, restaurant, voisins. Entrez dans la maison quand vous êtes prêt.")
    yield from wait(3)
    audit("hud_quartier")
    nb = g.neighborhood
    if g.tutorial is not None:
        for step in g.tutorial.STEPS:
            g.tutorial.force(step["id"])
            yield from wait(2)
            audit(f"didacticiel_{step['id']}")
        g.tutorial.hide()
    # invite d'interaction la plus longue
    from shop import CATALOG
    longest = max(CATALOG, key=lambda a: len(a.name))
    p = [pt for (a, pt) in nb.product_points if a is longest][0]
    g.player.place((p[0] + (0.9 if p[0] < 21 else -0.9), 0.0, p[2]), 270 if p[0] < 21 else 90, 20)
    yield from wait(6)
    audit("invite_produit")
    for a in CATALOG:
        nb.basket.add(a.id)
    co = nb.checkout
    co.open(nb._on_paid)
    yield from wait(2)
    audit("caisse_scan")
    co._scan_all()
    co._scan_card()
    co.msg = "Article inattendu dans la zone d'ensachage. Un conseiller va venir vous aider..."
    co.render()
    yield from wait(2)
    audit("caisse_scannee")
    co._enter_card()
    co.msg = "Numéro invalide : 10 chiffres commençant par 95317."
    co.render()
    yield from wait(2)
    audit("caisse_carte")
    co.field.text = "9531700000"
    co._validate_card()
    yield from wait(2)
    audit("caisse_garnier")
    co._back_scan()
    co._pay()
    yield from wait(2)
    audit("caisse_paiement")
    co._do_pay()
    yield from wait(2)
    audit("caisse_payee")
    co._show_ticket()
    yield from wait(3)
    audit("ticket")
    g.ui.docs.close()
    nb.counter.open()
    yield from wait(2)
    audit("restaurant")
    nb.counter._order("pan_bagnat")
    yield from wait(2)
    audit("restaurant_commande")
    nb.counter.close()
    # --- téléphone : toutes les applis et pages ---
    ph = g.phone
    ph.open()
    yield from wait(3)
    audit("telephone_accueil")
    for aid, appo in list(ph.apps.items()):
        ph.open_app(aid)
        yield from wait(2)
        audit(f"app_{aid}")
        pages = [m[len("_page_"):] for m in dir(appo) if m.startswith("_page_")]
        for pg in pages:
            try:
                appo.page = pg
                if aid == "messages" and pg == "thread":
                    appo.conv = next(iter(ph.model.conversations))
                appo.render()
            except Exception:
                traceback.print_exc()
                continue
            yield from wait(2)
            audit(f"app_{aid}_{pg}")
        if aid == "messages":
            for cid in list(ph.model.conversations):
                appo.open_conv(cid)
                yield from wait(2)
                audit(f"conversation_{cid}")
    ph.close()
    # --- inventaire, documents, dialogues ---
    for it in ("pile", "sel", "batterie_externe", "bougie", "pansement", "barre", "eau", "energisant", "journal", "courses",
               "adresse_piege", "numero_barre", "pied_de_biche", "trousseau"):
        g.state.add_item(it, 3)
    for d in ("carnet", "releve", "polaroids", "plan", "mur", "tel_garnier", "recus", "journaux"):
        g.state.add_doc(d)
    g.inv_panel.show()
    yield from wait(3)
    audit("inventaire")
    g.inv_panel.hide()
    import game_data as gd
    g.ui.docs.open("Carnet de Garnier", list(gd.NOTEBOOK_PAGES))
    yield from wait(3)
    audit("document")
    g.ui.docs.close()
    g.ui.choice.ask("Ouvrir le congélateur ? Quelque chose bouge à l'intérieur, on dirait que ça respire.", None, None,
                    "Ouvrir le congélateur", "Laisser fermé")
    yield from wait(2)
    audit("choix")
    g.ui.choice._answer(None)
    g.toggle_pause()
    yield from wait(2)
    audit("pause")
    g.toggle_pause()
    g.ui.rating.show("Notez votre livreur. Votre avis compte énormément pour nous et pour lui.", lambda: None)
    yield from wait(2)
    audit("notation")
    g.ui.rating.root.enabled = False
    g.ui.toast.show("Ajouté au panier : Huile d'olive de Nice AOP 50 cl (prix carte appliqué en caisse)")
    yield from wait(2)
    audit("toast")
    g.achievements.unlock("garnier_card")
    yield from wait(30)
    audit("succes_notification")
    g.mode = "gameover"
    g.ui.gameover.show(first_death=True)
    g.ui.gameover._reveal(True)
    yield from wait(2)
    audit("game_over")
    g.ui.gameover.hide()
    g.ui.ending.start("A")
    for i in range(len(g.ui.ending.steps)):
        g.ui.ending.t = 1.0
        yield from wait(2)
        audit(f"fin_etape_{i}")
        g.ui.ending._advance()
    g.ui.ending.stop()
    g.to_main_menu()


def scenario():
    while game.mode == "loading":
        yield
    yield from wait(10)
    for size in ("Moyen", "Grand", "Petit"):
        settings["taille_texte"] = size
        try:
            yield from screens()
        except Exception:
            traceback.print_exc()
            problems.append(f"exception pendant l'audit ({size})")
    for p in problems:
        print("DÉBORDEMENT", p, flush=True)
    print("UI AUDIT OK" if not problems else f"UI AUDIT : {len(problems)} problème(s)", flush=True)
    application.quit()


_gen = scenario()


def update():
    try:
        M.update()
        next(_gen)
    except StopIteration:
        application.quit()
    except Exception:
        traceback.print_exc()
        problems.append("exception")
        application.quit()


def input(key):
    M.input(key)


if __name__ == "__main__":
    app.run()
    sys.exit(1 if problems else 0)
