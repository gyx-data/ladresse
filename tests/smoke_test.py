"""Test de fumée de L'ADRESSE (nécessite un affichage ; sous Linux : xvfb-run -a python tests/smoke_test.py).

Démarre le vrai jeu, saute la cinématique, exerce toutes les interactions, le téléphone, la
chronologie de l'assistance (accélérée), l'IA des 4 entités, la sauvegarde, les fins, et le
serveur multijoueur avec un second client simulé. Affiche « SMOKE TEST OK » en cas de succès.
"""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "server"))
os.chdir(ROOT)
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="ladresse_test_")
os.environ["LADRESSE_TIME_SCALE"] = "0.04"

import main as M                                   # crée la fenêtre et le GameManager
from ursina import application, Vec3
from main import app, game
import config                                      # noqa: E402
config.settings["pause_auto"] = False                # la fenêtre de test perd souvent le focus

failures = []


def check(cond, label):
    print(("  OK   " if cond else "  FAIL ") + label, flush=True)
    if not cond:
        failures.append(label)


def wait(n):
    for _ in range(n):
        yield


def start_game(outside=False):
    from config import settings
    settings["quartier"] = outside
    game.ui.menu.hide()
    game._stop_menu()
    game.reset_game_objects()
    game._fresh_world()
    game.player.revive()
    game.mode = "cinematic"
    game.begin_play(fresh=True)


def tp(x, y, z, yaw=0.0, pitch=0.0):
    game.player.place((x, y, z), yaw, pitch)


def close_ui():
    if game.ui.docs.visible:
        game.ui.docs.close()
    if game.ui.choice.visible:
        game.ui.choice.yes.on_click()


def neighborhood_tests():
    """Quartier : phase extérieure, PNJ, supérette, carte fidélité, antivol, entrée dans la maison."""
    from shop import CATALOG_BY_ID, bank_balance
    from fidelite import Loyalty
    start_game(outside=True)
    yield from wait(10)
    nb, p = game.neighborhood, game.player
    check(nb is not None and nb.outside_phase and p.zone == "dehors", "nouvelle partie : départ dans le quartier (dehors)")
    check(len(nb.npcs) >= 10 and len(nb.traffic) >= 2, f"{len(nb.npcs)} PNJ et {len(nb.traffic)} voitures en circulation")
    check(nb.loyalty.active == "9531700001", "carte fidélité par défaut 9531700001")
    # trajet jusqu'au magasin : le sol existe partout (pas de chute)
    tp(21.0, 0.0, -19.0, 180.0)
    yield from wait(10)
    check(abs(p.pos[1]) < 0.2, "sol praticable dans la rue")
    tp(14.85, 0.0, -27.0, 90.0)
    yield from wait(5)
    check(p.zone == "magasin", "zone magasin détectée")
    bal0 = bank_balance(game.state)
    nb.take(CATALOG_BY_ID["piles"])
    nb.take(CATALOG_BY_ID["eau"])
    # antivol : sortir sans payer ramène dans le magasin
    tp(21.0, 0.0, -22.0, 0.0)
    yield from wait(3)
    tp(21.0, 0.0, -20.4, 0.0)
    yield from wait(5)
    check(nb.theft_warnings == 1 and p.pos[2] < -21.5, "portique antivol : retour dans le magasin")
    co = nb.checkout
    co.open(nb._on_paid)
    co._scan_all()
    co._create_card()
    new_card = co.card
    check(new_card == "9531700002", f"nouvelle carte numérotée 9531700002 ({new_card})")
    co._pay()
    co._do_pay()
    yield from wait(3)
    check(game.state.has("pile", 2) and game.state.has("eau"), "articles payés ajoutés à l'inventaire")
    check(abs((bal0 - bank_balance(game.state)) - (4.49 + 0.69)) < 0.01, "prix carte appliqués et débit bancaire")
    check(Loyalty(nb.loyalty.path).card("9531700002")["points"] == 5, "points fidélité enregistrés sur disque")
    check("Carte fidélité 9531 700 002" in co.ticket_text(), "ticket de caisse avec la carte")
    co.close()
    check(nb.basket.count == 0 and not nb.ui.enabled, "panier vidé après paiement")
    # étal de primeur devant la vitrine : une cagette se prend comme un article, et partir sans payer ramène à l'étal
    stall = [it for it in game.interactions.items.values() if it.id.startswith("primeur_")]
    check(len(stall) == 8 * 2, f"{len(stall)} cagettes achetables (deux étals devant la vitrine)")
    tp(14.0, 0.0, -18.6, 180.0)
    yield from wait(3)
    stall[0].on_use(stall[0])
    art = CATALOG_BY_ID[nb.basket.as_lines()[0][0].id]
    check(nb.basket.count == 1 and art.shelf == "primeur" and abs(nb.basket.total - art.price) < 0.01,
          f"fruit de l'étal au panier ({art.name}, {art.price:.2f} €)")
    w0 = nb.theft_warnings
    tp(14.0, 0.0, -12.0, 0.0)
    yield from wait(3)
    check(nb.theft_warnings == w0 + 1 and p.pos[2] < -17.0, "partir avec les fruits sans payer : ramené à l'étal")
    nb._drop_basket()
    # restaurant
    h0 = p.health = 50.0
    nb.counter.open()
    nb.counter._order("pan_bagnat")
    nb.counter.close()
    check(p.health > h0, "repas chez Nino : santé rendue")
    # PNJ : parler
    n0 = game.state.stats.get("discussions", 0)
    nb.npcs[0].talk()
    check(game.state.stats.get("discussions", 0) == n0 + 1, "dialogue avec un PNJ")
    # entrée dans la maison
    tp(7.0, 0.0, -1.2, 0.0)
    from ursina import held_keys
    held_keys["w"] = 1
    for _ in range(60):
        yield
        if not nb.outside_phase:
            break
    held_keys["w"] = 0
    check(not nb.outside_phase and game.state.flag("play_started"), "entrer dans la maison lance la nuit")
    game.timers.clear()


def scenario():
    while game.mode == "loading":
        yield
    check(game.mode == "menu", "démarrage : le menu principal s'affiche")
    yield from wait(5)
    yield from neighborhood_tests()
    start_game()
    yield from wait(5)
    p, ia = game.player, game.interactions
    check(len(ia.items) > 40, f"{len(ia.items)} objets interactifs")

    # --- déplacements et collisions ---
    from ursina import held_keys
    # durée de marche fixe (1,2 s à ~2,6 m/s) et non un nombre d'images : indépendant de la fréquence d'affichage
    held_keys["w"] = 1
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 1.2:
        yield
    held_keys["w"] = 0
    check(p.pos[2] > 3.0 and 6.0 < p.pos[0] < 8.0, "marche dans le couloir sans traverser les murs")

    # --- toutes les interactions ---
    game.state.add_item("pied_de_biche")
    game.state.add_item("cle_tiroir")
    game.state.add_item("sel")
    done = 0
    for iid, it in list(ia.items.items()):
        if iid.startswith("door_"):
            continue
        try:
            tp(it.pos[0], it.pos[1] - 1.0, it.pos[2] - 0.8, 0)
            it.enabled = True
            it.on_use(it)
            done += 1
        except Exception:
            traceback.print_exc()
            failures.append("handler " + iid)
        yield from wait(1)
        close_ui()
    check(done >= 30, f"{done} interactions exécutées sans erreur")
    for _ in range(3):
        ia.items["planches"].on_use(ia.items["planches"])
        yield
    check(game.state.flag("planks_removed"), "les trois planches de la porte du sous-sol sont arrachées")

    # --- téléphone : commande QuickEats ---
    game.phone.open()
    yield from wait(5)
    qe = game.phone.apps["quickeats"]
    game.phone.open_app("quickeats")
    qe.field_text = "1 rue inconnue"
    qe.validate()
    check(qe.address_key is None, "adresse inconnue refusée")
    qe.field_text = "23 avenue du Grand Champ"
    qe.validate()
    check(qe.address_key is None, "adresse non desservie refusée")
    qe.field_text = "17 rue des Lilas"
    qe.validate()
    check(qe.address_key == "bonne", "bonne adresse acceptée")
    qe.choose("burger")
    qe.confirm()
    qe.loading_t = 5.0
    yield from wait(3)
    check(game.state.entity_type == "imposteur", "le repas détermine l'entité (burger → Imposteur)")
    game.phone.close()

    # --- annulation : le livreur ne vient pas tant que le joueur n'a pas enquêté ---
    for _ in range(40):
        game.timers.update(1.0)
    yield
    check(game.state.flag("order_cancelled") and game.quests.is_active("comprendre"), "commande annulée → objectif « Comprendre »")
    for _ in range(600):
        game.timers.update(1.0)
        game.assistance.update(0.05)
    yield
    check(game.assistance.phase == 1, "sans vérifier la banque, l'assistance ne se manifeste pas (pas de livreur)")
    check("application bancaire" in game.quests.current_objective(), "objectif HUD : vérifier l'application bancaire")
    check("application bancaire" in str(game.ui.hud.obj.text), "bandeau d'objectif du HUD à jour après l'annulation")
    game.phone.open()
    yield from wait(3)
    game.phone.open_app("banque")
    yield from wait(3)
    game.phone.apps["banque"].call()
    yield from wait(2)
    game.phone.calls.hang_up()
    game.phone.open_app("quickeats")
    qe.confirm()
    qe.loading_t = 5.0
    yield from wait(3)
    check(game.state.order_failed == 1 and game.quests.investigation_done(), "banque vérifiée, banque appelée, nouvelle commande refusée")
    game.phone.close()

    # --- chronologie de l'assistance (accélérée) ---
    n = 0
    while game.assistance.phase < 5 and n < 2000:
        game.timers.update(1.0)
        game.assistance.update(0.05)
        n += 1
        if n % 150 == 0:
            yield
    check(game.assistance.phase == 5, "la chronologie arrive jusqu'à « Livraison effectuée »")
    check(game.entity.active and game.entity.kind == "imposteur", "l'entité est lâchée dans la maison")
    check(len(game.state.pair_good) >= 3, f"{len(game.state.pair_good)} paires évaluées")
    sv = game.quests.quests["survivre"]
    check(all(f"p{i}" in sv.done_steps for i in (1, 2, 3)) and "sous-sol" in game.quests.current_objective(),
          "objectifs : paires 1-3 comptées, objectif du sous-sol après la livraison")
    game.entity.set_visible(True)

    # --- IA : pathfinding et poursuite ---
    for kind in ("imposteur", "silencieux", "rampant", "multiple"):
        game.player.revive()
        game.mode = "playing"
        game.entity.spawn(kind, (7, 0, 9.0))
        game.entity.activate()
        game.entity.killing = True            # pas de mort pendant ce test
        tp(7, 0, 2.0, 0, 3)
        for _ in range(25):
            game.entity.update(0.1)
        path = game.entity.current_nav().find_path(Vec3(7, 0, 9), Vec3(3, 3, 3), 0, 1)
        check(len(path) > 2, f"{kind} : chemin trouvé entre deux étages ({len(path)} points)")
        yield

    # --- difficulté : contact encaissé, mort puis réessayer ---
    from config import settings as _settings
    _settings["difficulte"] = "Normal"
    game.entity.despawn()
    game.player.revive()
    game.mode = "playing"
    game.kill_player("entity_contact", kind="rampant")
    for _ in range(300):                      # la frayeur dure ~1 s : on attend sa fin plutôt qu'un nombre d'images fixe
        yield
        if not game.player.frozen and game.mode == "playing":
            break
    check(not game.player.dead and game.mode == "playing" and not game.player.frozen and 40 < game.player.health < 60,
          f"Normal : le premier contact blesse sans tuer (vie {game.player.health:.0f})")
    game.kill_player("entity_contact", kind="rampant")
    for _ in range(40):
        yield
    check(game.mode == "gameover", "la mort mène à l'écran « Livraison effectuée. »")
    game.save_checkpoint("test")
    check(game.saves.exists(), "sauvegarde automatique écrite")
    game.retry()
    yield from wait(10)
    check(game.mode == "playing", "« Réessayer » recharge la dernière sauvegarde")
    check(game.player.health == 100.0, "vie pleine après « Réessayer »")
    _settings["difficulte"] = "Cauchemar"
    game.save_checkpoint("test")
    game.player.revive()
    game.kill_player("entity_contact", kind="rampant")
    for _ in range(40):
        yield
    check(game.mode == "gameover" and not game.saves.exists(), "Cauchemar : un contact tue et efface la sauvegarde")
    game.ui.gameover.hide()
    _settings["difficulte"] = "Normal"

    # --- fins ---
    for code in ("A", "B", "C", "D"):
        game.ending_active = False
        game.state.flags.pop("ending_started", None)
        game.mode = "playing"
        game.trigger_ending(code)
        for _ in range(20):
            yield
        if code == "B":
            game.ui.rating._clicked()
            for _ in range(100):
                yield
        for _ in range(20):
            game.ui.ending.t = 100
            yield
        game.ui.ending.stop()
        game.ui.rating.root.enabled = False
    check(True, "les quatre fins s'enchaînent")

    # --- multijoueur : serveur (parties) + ce jeu + second joueur simulé ---
    import server as S
    srv = S.RelayServer("127.0.0.1", 27997)
    srv.start(block=False)
    time.sleep(0.3)
    game.ending_active = False
    game.ui.ending.stop()
    game.state.flags.pop("ending_started", None)
    game.mode = "menu"
    config.settings["mp_adresse"] = "127.0.0.1:27997"
    config.settings["mp_pseudo"] = "Hote"
    game.show_multiplayer()
    mp = game.mp
    for _ in range(60):
        if mp.client.id is not None:
            break
        yield
    mp.client.create_room("Smoke", 4)
    for _ in range(20):
        yield
    code = (mp.room or {}).get("id")
    sock = socket.create_connection(("127.0.0.1", 27997))
    sock.sendall((json.dumps({"type": "hello", "name": "Bob", "proto": "4.0"}) + "\n").encode())
    sock.sendall((json.dumps({"type": "join", "room": code, "game": config.VERSION}) + "\n").encode())
    for _ in range(30):
        yield
    check(mp.client.is_host and len(mp.players) == 2, "salon multijoueur : créateur + un joueur")
    mp.do_start()
    for _ in range(40):
        yield
    check(mp.in_game and len(mp.avatars) == 1, "partie lancée sur le serveur, avatar du second joueur créé")
    sock.sendall((json.dumps({"type": "to", "to": "all", "d": {"type": "move", "pos": [7.5, 0.0, 2.0], "rot": [0, 90], "s": 1}}) + "\n").encode())
    for _ in range(40):
        yield
    av = next(iter(mp.avatars.values()), None)
    check(av is not None and abs(av.root.position[2] - 2.0) < 0.3, "position du second joueur reçue et interpolée")
    sock.close()
    for _ in range(20):
        yield
    check(not mp.avatars, "départ du second joueur pris en compte")
    game.phone.open()
    srv.stop()
    for _ in range(30):
        yield
    check(not mp.in_game and game.mode == "gameover" and not game.phone.is_open,
          "coupure du serveur : « Partie interrompue », téléphone rangé")
    mp.disconnect()
    game.to_main_menu()
    yield from wait(5)
    print("SMOKE TEST " + ("OK" if not failures else "ÉCHEC : " + ", ".join(failures)), flush=True)


gen = scenario()


def update():
    try:
        M.update()
        next(gen)
    except StopIteration:
        application.quit()
    except Exception:
        traceback.print_exc()
        failures.append("exception")
        application.quit()


def input(key):
    M.input(key)


if __name__ == "__main__":
    app.run()
    sys.exit(1 if failures else 0)
