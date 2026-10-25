"""Gestion du mode coopératif : lobby, joueurs distants, synchronisation de l'état.

2 à 4 joueurs explorent la même maison. Chacun reçoit des messages d'assistance différents
(et contradictoires entre eux) ; les photos montrent les autres joueurs « faux » (yeux
rouges, sourire déformé) pour semer la paranoïa ; les morts deviennent spectateurs.
"""
import random

from ursina import Entity, Vec3, camera, color, destroy
from ursina.prefabs.input_field import InputField

import config
import game_data as gd
from config import settings
from multiplayer_client import NetClient
from character_model import CharacterModel, Nametag
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb, panel, image
import illustrations as ill


class RemoteAvatar:
    """Autre joueur : personnage articulé (sweat à sa couleur), pseudo flottant, lampe torche,
    interpolation de position/orientation et animation de marche déduite de la vitesse."""

    def __init__(self, pid, name, jacket, seed=0):
        self.id = pid
        self.name = name
        self.root = Entity()
        self.target = Vec3(7, 0, 1)
        self.yaw_target = 0.0
        self.pitch = 0.0
        self.alive = True
        self.step_dist = 0.0
        self.last = Vec3(7, 0, 1)
        self.speed = 0.0
        self.last_update = 0.0
        self.torch_on = True
        jc = tuple(jacket)
        self.model = CharacterModel(parent=self.root, jacket=jc, pants=(0.32, 0.36, 0.5), seed=seed + 2, emit=0.12)
        self.tag = Nametag(self.root, name, jc)
        # visage « faux » visible seulement sur les photos : yeux rouges, sourire déformé
        self.fake = Entity(parent=self.model.head, enabled=False, position=(0, 0.12, 0.112))
        for x in (-0.04, 0.04):
            Entity(parent=self.fake, model="quad", color=color.rgb32(255, 20, 20), position=(x, 0.015, 0), scale=0.028, double_sided=True)
        Entity(parent=self.fake, model="quad", color=color.rgb32(20, 0, 0), position=(0, -0.09, 0), scale=(0.09, 0.03), double_sided=True)

    def set_target(self, pos, rot):
        self.target = Vec3(*pos)
        self.pitch = rot[0] if len(rot) > 0 else 0.0
        self.yaw_target = rot[1] if len(rot) > 1 else 0.0

    def update(self, dt):
        cur = self.root.position
        if not self.alive:
            self.model.animate(dt)
            return
        # téléportation si l'écart est énorme (correction serveur, réapparition)
        if (self.target - cur).length() > 6.0:
            self.root.position = self.target
            cur = self.target
        new = cur + (self.target - cur) * min(1.0, dt * 12.0)
        moved = (Vec3(new[0], 0, new[2]) - Vec3(cur[0], 0, cur[2])).length()
        self.root.position = new
        inst = moved / max(dt, 1e-4)
        self.speed += (inst - self.speed) * min(1.0, dt * 8.0)
        d = (self.yaw_target - self.root.rotation_y + 180) % 360 - 180
        self.root.rotation_y += d * min(1.0, dt * 10.0)
        self.model.animate(dt, self.speed, 0.0, self.pitch, self.speed > 4.2, self.torch_on)

    def die(self):
        self.alive = False
        self.model.die()
        self.tag.set_visible(False)

    def destroy(self):
        destroy(self.root)


class MultiplayerManager:
    def __init__(self, game):
        self.game = game
        self.client = NetClient()
        self.avatars = {}
        self.players = {}
        self.host = None
        self.root = None
        self.status = None
        self.field_addr = None
        self.field_name = None
        self.list_labels = []
        self.start_btn = None
        self.in_game = False
        self.dead = False
        self.spectate_id = None
        self.ping_t = 0.0
        self.footstep_t = {}
        self.last_move_pos = None
        self.over_ui = None
        self.fake_active = False
        self.lobby_open = False
        self._result = None

    # ------------------------------------------------------------------
    @property
    def connected(self):
        return self.client.connected

    def disconnect(self):
        self.client.close()
        self._clear_avatars()
        self.in_game = False
        self.dead = False
        if self.root is not None:
            self.root.enabled = False
        self.lobby_open = False

    def _clear_avatars(self):
        for a in self.avatars.values():
            a.destroy()
        self.avatars = {}

    # ------------------------------------------------------------------
    # Lobby
    # ------------------------------------------------------------------
    def show_lobby(self):
        g = self.game
        g.mode = "lobby"
        g.ui.menu.hide()
        self.lobby_open = True
        if self.root is not None:
            destroy(self.root)
        self.root = Entity(parent=camera.ui, z=-5)
        r = self.root
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 190), z=1)
        panel(r, 0, 0, 1.3, 0.84, "panel", z=0.9)
        label(r, "COOPÉRATIF EN LIGNE", -0.6, 0.37, 1.6, color.white, origin=(-0.5, 0), z=0)
        label(r, "2 à 4 joueurs · chacun reçoit SES messages d'assistance… et ils se contredisent.", -0.6, 0.325, 0.62,
              rgb(170, 166, 160), origin=(-0.5, 0), z=0)
        # colonne gauche : connexion
        x = -0.34
        label(r, "ADRESSE DU SERVEUR", x - 0.26, 0.25, 0.55, rgb(226, 120, 90), origin=(-0.5, 0), z=0)
        self.field_addr = InputField(default_value=settings["mp_adresse"], parent=r, position=(x, 0.21, -0.05), scale=(0.52, 0.05),
                                     character_limit=40)
        label(r, "PSEUDO", x - 0.26, 0.15, 0.55, rgb(226, 120, 90), origin=(-0.5, 0), z=0)
        self.field_name = InputField(default_value=settings["mp_pseudo"], parent=r, position=(x, 0.11, -0.05), scale=(0.52, 0.05),
                                     character_limit=16)
        self.connect_btn = button(r, "Se connecter", x - 0.13, 0.03, 0.25, 0.055, self.do_connect, style="success", size=0.8, z=-0.1)
        button(r, "Héberger une partie", x + 0.13, 0.03, 0.25, 0.055, self.host_local, style="blue", size=0.7, z=-0.1)
        self.status_dot = rect(r, x - 0.25, -0.04, 0.016, 0.016, rgb(200, 60, 50), z=0, radius=0.5)
        self.status = label(r, "Déconnecté", x - 0.23, -0.04, 0.7, rgb(210, 200, 170), origin=(-0.5, 0), z=0)
        self.ping_lbl = label(r, "", x + 0.26, -0.04, 0.6, rgb(150, 150, 156), origin=(0.5, 0), z=0)
        tips = ("Serveur officiel : " + f"{config.SERVER_HOST}:{config.SERVER_PORT}",
                "« Héberger » lance un serveur sur ce PC (port " + str(config.SERVER_PORT) + ") : vos amis entrent votre IP.",
                "Pensez à ouvrir le port TCP + UDP sur votre box pour jouer par Internet.")
        y = -0.12
        for t in tips:
            label(r, t, x - 0.26, y, 0.5, rgb(130, 128, 125), origin=(-0.5, 0), z=0, wrap=60)
            y -= 0.045
        # colonne droite : joueurs
        label(r, "JOUEURS DANS LE LOBBY", 0.08, 0.25, 0.55, rgb(226, 120, 90), origin=(-0.5, 0), z=0)
        self.count_lbl = label(r, "0 / 4", 0.58, 0.25, 0.55, rgb(150, 150, 156), origin=(0.5, 0), z=0)
        self.list_root = Entity(parent=r)
        self.start_btn = button(r, "Lancer la partie", 0.33, -0.3, 0.32, 0.06, self.do_start, style="primary", size=0.85, z=-0.1)
        self.start_btn.enabled = False
        button(r, "Retour", -0.52, -0.36, 0.18, 0.05, self.back, style="dark", size=0.75, z=-0.1)
        if self.connected:
            self.status.text = "Connecté"
            self._refresh_players()
        else:
            self._refresh_players()
        g.set_mouse(free=True)

    def host_local(self):
        """Lance le serveur dédié dans ce processus (thread) puis s'y connecte."""
        if getattr(self, "_local_server", None) is None:
            try:
                import importlib.util
                import os
                import sys
                import threading
                base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
                sdir = os.path.join(base, "server")
                if sdir not in sys.path:
                    sys.path.append(sdir)
                os.environ.setdefault("LADRESSE_LOG", os.path.join(config.app_data_dir(), "server.log"))
                spec = importlib.util.spec_from_file_location("ladresse_server", os.path.join(sdir, "server.py"))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                srv = mod.GameServer("0.0.0.0", config.SERVER_PORT)
                threading.Thread(target=srv.start, daemon=True).start()
                self._local_server = srv
            except Exception as e:
                self.status.text = f"Impossible d'héberger : {e}"
                return
        self.field_addr.text = f"127.0.0.1:{config.SERVER_PORT}"
        self.status.text = "Serveur local lancé, connexion..."
        from ursina import invoke
        invoke(self.do_connect, delay=0.6)

    def back(self):
        self.disconnect()
        if self.root is not None:
            self.root.enabled = False
        self.game.show_menu()

    def do_connect(self):
        if self.client.connected or self.client.connecting:
            return
        text = self.field_addr.text.strip() or f"{config.SERVER_HOST}:{config.SERVER_PORT}"
        name = self.field_name.text.strip() or "Joueur"
        host, port = text, config.SERVER_PORT
        if ":" in text:
            host, p = text.rsplit(":", 1)
            try:
                port = int(p)
            except ValueError:
                port = config.SERVER_PORT
        settings["mp_adresse"] = text
        settings["mp_pseudo"] = name
        settings.save()
        self.status.text = f"Connexion à {host}:{port}..."
        self.client.connect_async(host, port, name, self._on_connect_result)

    def _on_connect_result(self, ok, msg):
        self._pending_status = msg

    def do_start(self):
        if self.client.id == self.host:
            self.client.send_start()

    def on_key(self, key):
        if key == "escape":
            self.back()

    def _refresh_players(self):
        if not self.lobby_open or self.root is None:
            return
        clear(self.list_root)
        y = 0.18
        for p in self.players.values():
            c = p.get("color", [1, 1, 1])
            col = (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
            me = p["id"] == self.client.id
            rect(self.list_root, 0.33, y, 0.52, 0.075, rgb(255, 255, 255, 22 if me else 10), z=0.5, radius=0.18)
            image(self.list_root, ill.avatar(col, 96), 0.12, y, 0.06, 0.06, z=0.3)
            label(self.list_root, p["name"] + ("  (vous)" if me else ""), 0.17, y + 0.012, 0.8, color.white, origin=(-0.5, 0), z=0.2)
            label(self.list_root, "Hôte" if p["id"] == self.host else "Prêt", 0.17, y - 0.018, 0.5,
                  rgb(240, 190, 90) if p["id"] == self.host else rgb(120, 200, 140), origin=(-0.5, 0), z=0.2)
            if p["id"] == self.host:
                image(self.list_root, ill.icon_crown(48), 0.56, y, 0.035, 0.035, z=0.2)
            y -= 0.088
        for _ in range(len(self.players), 4):
            rect(self.list_root, 0.33, y, 0.52, 0.075, rgb(255, 255, 255, 5), z=0.5, radius=0.18)
            label(self.list_root, "En attente d'un joueur…", 0.33, y, 0.62, rgb(110, 110, 116), z=0.2)
            y -= 0.088
        self.count_lbl.text = f"{len(self.players)} / 4"
        is_host = self.client.id is not None and self.client.id == self.host
        self.start_btn.enabled = is_host
        self.status_dot.color = rgb(80, 200, 110) if self.connected else rgb(200, 60, 50)
        if not is_host and self.connected:
            label(self.list_root, "En attente du lancement par l'hôte…", 0.33, -0.3, 0.62, rgb(150, 150, 156), z=-0.05)

    # ------------------------------------------------------------------
    # Boucle
    # ------------------------------------------------------------------
    def update(self, dt):
        st = getattr(self, "_pending_status", None)
        if st is not None:
            self._pending_status = None
            if self.status is not None and self.lobby_open:
                self.status.text = st
        for msg in self.client.poll():
            self.handle(msg)
        g = self.game
        if self.in_game and g.mode == "playing" and not self.dead:
            p = g.player
            self.client.send_move(p.pos, (p.pitch, p.yaw))
            # bruit émis (pour le ciblage de l'entité)
            if p.noises and p.noises[-1]["t"] > getattr(self, "_last_noise_t", -1):
                n = p.noises[-1]
                self._last_noise_t = n["t"]
                self.client.send_noise(n["pos"], n["radius"])
        if self.in_game:
            for a in self.avatars.values():
                a.update(dt)
                self._avatar_steps(a, dt)
            if self.dead:
                self._spectate(dt)
        self.ping_t -= dt
        if self.ping_t <= 0 and self.connected:
            self.ping_t = 4.0
            self.client.send_ping()
            if self.lobby_open and self.root is not None and getattr(self, "ping_lbl", None) is not None:
                pg = getattr(self.client, "ping", None)
                self.ping_lbl.text = f"{int(pg)} ms" if pg else ""
                self.status_dot.color = rgb(80, 200, 110)

    def _avatar_steps(self, a, dt):
        if not a.alive:
            return
        d = (a.root.position - a.last).length()
        a.last = Vec3(*a.root.position)
        a.step_dist += d
        if a.step_dist > 1.6:
            a.step_dist = 0.0
            sound.play_at("pas_parquet_%d" % random.randint(0, 2), a.root.position, 0.45, ref=3.5)

    # ------------------------------------------------------------------
    # Messages serveur
    # ------------------------------------------------------------------
    def handle(self, m):
        g = self.game
        t = m.get("type")
        if t in ("welcome", "lobby"):
            self.players = {p["id"]: p for p in m.get("players", [])}
            self.host = m.get("host", self.host)
            self._refresh_players()
        elif t == "error":
            if self.status is not None:
                self.status.text = m.get("message", "Erreur")
            self.client.close()
        elif t == "disconnected":
            if self.in_game:
                g.ui.say("Connexion au serveur perdue.", 6.0)
            elif self.status is not None and self.lobby_open:
                self.status.text = "Connexion perdue."
        elif t == "start":
            self.players = {p["id"]: p for p in m.get("players", [])}
            self.start_game()
        elif not self.in_game:
            return
        elif t == "player_move":
            a = self.avatars.get(m.get("id"))
            if a is not None:
                a.set_target(m["pos"], m.get("rot", [0, 0]))
        elif t == "entity_update":
            g.entity.remote_update(m)
        elif t == "assistance_msg":
            self._on_assistance(m)
        elif t == "game_event":
            self._on_event(m)
        elif t == "event":
            name = m.get("name")
            if name == "knock":
                g.assistance._knock(0)
            elif name == "jumpscare" and m.get("target") == self.client.id:
                pass
        elif t == "player_death":
            self._on_death(m)
        elif t == "door_state":
            d = g.house.doors.get(m.get("door_id"))
            if d is not None and m.get("by") != self.client.id:
                (d.open if m.get("open") else d.close)(silent=False)
        elif t == "chat":
            self._on_chat(m)
        elif t == "order_result":
            if m.get("ok"):
                g.state.entity_type = m.get("entity")
                g.state.meal = m.get("meal")
                g.state.set("order_placed")
            else:
                g.phone.toast(m.get("message", "Erreur"))
        elif t == "correct":
            g.player.place(m["pos"], g.player.yaw, g.player.pitch)
        elif t == "interact":
            pass
        elif t == "game_over":
            self._game_over(m.get("result", "lose"))

    def _on_assistance(self, m):
        a = self.game.assistance
        pid = m.get("pair_id", 0)
        if pid == 0:
            a.send(m["text"])
        else:
            a.remote_option(pid, m.get("option", "A"), m["text"])

    def _on_event(self, m):
        g = self.game
        ev = m.get("event")
        a = g.assistance
        if ev == "order_cancelled":
            if not g.state.flag("order_cancelled"):
                if g.state.meal is None:
                    g.state.meal = "burger"
                g.cancel_order()
        elif ev == "delivery_started":
            a.remote = True
            a.start_delivery()
        elif ev == "delivery_arriving":
            rem = m.get("countdown", 0)
            texts = {120: gd.ASSIST_PHASE4[0], 60: gd.ASSIST_PHASE4[1], 30: gd.ASSIST_PHASE4[2], 0: gd.ASSIST_PHASE4[3]}
            if rem in texts:
                a._phase4(rem, texts[rem][1], texts[rem][2])

    def _on_chat(self, m):
        g = self.game
        phone = g.phone
        text = m.get("message", "")
        name = m.get("name", "?")
        mine = m.get("id") == self.client.id
        phone.model.add_message("chat", name, text, mine=mine)
        if not mine:
            phone.notify(name, text, "icone_messages", target=("messages", "chat"))
        app = phone.apps["messages"]
        if phone.is_open and phone.current == "messages" and app.page == "thread" and app.conv == "chat":
            app.render()

    def _on_death(self, m):
        g = self.game
        pid = m.get("id")
        if pid == self.client.id:
            if not g.player.dead:
                g.kill_player(m.get("cause", "entity_contact"), kind=g.state.entity_type)
            self.dead = True
            alive = [i for i, a in self.avatars.items() if a.alive]
            self.spectate_id = alive[0] if alive else None
        else:
            a = self.avatars.get(pid)
            if a is not None:
                a.die()
            g.ui.say(f"{self.players.get(pid, {}).get('name', 'Un joueur')} a été livré.", 5.0)
            sound.play("cri", 0.35, pitch=0.8)
            g.player.add_stress(20)

    # ------------------------------------------------------------------
    # Partie
    # ------------------------------------------------------------------
    def start_game(self):
        g = self.game
        self.lobby_open = False
        if self.root is not None:
            self.root.enabled = False
        self._clear_avatars()
        g.is_multiplayer = True
        self.in_game = True
        self.dead = False
        self.spectate_id = None
        g.ui.menu.hide()
        g._stop_menu()
        g.reset_game_objects()
        g._fresh_world()
        g.assistance.remote = True
        g.player.revive()
        g.player.hide_model = False
        self.__dict__.pop("_spec_init", None)
        g.player.flashlight.battery = 100.0
        g.phone.model.battery = 100.0
        g.entity.remote = True
        g.begin_play(fresh=True)
        g.state.act = 1
        me = self.client.id
        idx = list(self.players).index(me) if me in self.players else 0
        g.player.place((7.0 + (idx - 1.5) * 0.45, 0.0, 0.9), 0.0, 0.0)
        for pid, p in self.players.items():
            if pid == me:
                continue
            av = RemoteAvatar(pid, p["name"], p.get("color", [0.7, 0.2, 0.2]), seed=len(self.avatars))
            av.root.position = Vec3(7.0, 0.0, 0.9)
            av.target = Vec3(7.0, 0.0, 0.9)
            self.avatars[pid] = av
        g.ui.say("Mode coopératif — comparez vos messages d'assistance... si vous osez.", 6.0)
        g.phone.model.conversations["chat"]["hidden"] = False

    def _game_over(self, result):
        g = self.game
        self.in_game = False
        if self.over_ui is not None:
            destroy(self.over_ui)
        g.mode = "gameover"
        g.player.frozen = True
        self.over_ui = Entity(parent=camera.ui, z=-20)
        rect(self.over_ui, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 235), z=1)
        panel(self.over_ui, 0, 0, 0.9, 0.6, "panel", z=0.8)
        if result == "win":
            label(self.over_ui, "LIVRAISON REFUSÉE", 0, 0.2, 2.2, color.white, z=0)
            label(self.over_ui, "Au moins un d'entre vous a survécu jusqu'à l'aube.", 0, 0.12, 0.85, rgb(200, 190, 150), z=0)
        else:
            label(self.over_ui, "LIVRAISON EFFECTUÉE", 0, 0.2, 2.2, rgb(230, 80, 70), z=0)
            label(self.over_ui, "Personne n'a survécu.", 0, 0.12, 0.85, rgb(200, 120, 120), z=0)
        y = 0.03
        for pid, p in self.players.items():
            alive = (pid == self.client.id and not self.dead) or (pid in self.avatars and self.avatars[pid].alive)
            c = p.get("color", [1, 1, 1])
            image(self.over_ui, ill.avatar((int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)), 96, dead=not alive), -0.2, y, 0.05, 0.05, z=0)
            label(self.over_ui, p.get("name", "?"), -0.16, y, 0.8, color.white, origin=(-0.5, 0), z=0)
            label(self.over_ui, "survivant" if alive else "livré", 0.25, y, 0.7, rgb(120, 200, 140) if alive else rgb(220, 90, 80),
                  origin=(0.5, 0), z=0)
            y -= 0.06
        button(self.over_ui, "Menu principal", 0, -0.23, 0.3, 0.065, self._leave, style="primary", size=0.9, z=-0.1)
        g.set_mouse(free=True)

    def _leave(self):
        if self.over_ui is not None:
            destroy(self.over_ui)
            self.over_ui = None
        self.game.to_main_menu()

    # ------------------------------------------------------------------
    # Spectateur : caméra suivant un joueur vivant (liberté de regard limitée)
    # ------------------------------------------------------------------
    def _spectate(self, dt):
        g = self.game
        alive = [i for i, a in self.avatars.items() if a.alive]
        if not alive:
            return
        if self.spectate_id not in alive:
            self.spectate_id = alive[0]
        a = self.avatars[self.spectate_id]
        p = g.player
        p.pos = Vec3(a.root.position[0], a.root.position[1], a.root.position[2])
        p.dead = False
        p.frozen = False
        p.look_enabled = True
        p.move_enabled = False
        p.hide_model = True
        if not hasattr(self, "_spec_init"):
            self._spec_init = True
            g.ui.hud.show()
            g.ui.gameover.hide()
            g.mode = "playing"
            g.jumpscare.active = False
            g.ui.say("Vous êtes spectateur. Vos messages peuvent être interceptés par l'entité.", 6.0)

    # ------------------------------------------------------------------
    # Photos : les autres joueurs apparaissent « faux » (paranoïa)
    # ------------------------------------------------------------------
    def photo_fake(self, state):
        for a in self.avatars.values():
            a.fake.enabled = state and a.alive
