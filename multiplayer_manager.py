"""Gestion du mode coopératif : lobby, joueurs distants, synchronisation de l'état.

2 à 4 joueurs explorent la même maison. Chacun reçoit des messages d'assistance différents
(et contradictoires entre eux) ; les photos montrent les autres joueurs « faux » (yeux
rouges, sourire déformé) pour semer la paranoïa ; les morts deviennent spectateurs.
"""
import math
import random

from ursina import Entity, Vec3, camera, color, destroy
from ursina.prefabs.input_field import InputField

import config
import game_data as gd
from config import settings
from multiplayer_client import NetClient
from room_builder import MeshBuilder
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb


class RemoteAvatar:
    """Modèle simple d'un autre joueur : capsule, tête sphérique, bras cylindriques, veste colorée."""

    def __init__(self, pid, name, jacket):
        self.id = pid
        self.name = name
        self.root = Entity()
        self.target = Vec3(7, 0, 1)
        self.yaw_target = 0.0
        self.alive = True
        self.phase = 0.0
        self.step_dist = 0.0
        self.last = Vec3(7, 0, 1)
        jc = tuple(jacket)
        b = MeshBuilder("avatar")
        b.cyl("tissu", 0, 0.0, 0, 0.17, 0.85, 8, (0.12, 0.13, 0.2))                   # jambes
        b.cyl("tissu", 0, 0.8, 0, 0.21, 0.7, 8, jc)                                  # torse / veste
        b.sphere("platre", 0, 1.68, 0, 0.12, (0.8, 0.62, 0.52), sy=1.1)             # tête
        for e in b.build(parent=self.root, emit=0.06):
            pass
        self.arm_l = Entity(parent=self.root, position=(-0.26, 1.45, 0))
        self.arm_r = Entity(parent=self.root, position=(0.26, 1.45, 0))
        for arm in (self.arm_l, self.arm_r):
            ab = MeshBuilder("bras")
            ab.cyl("tissu", 0, -0.6, 0, 0.055, 0.6, 6, jc)
            for e in ab.build(parent=arm, emit=0.06):
                pass
        # visage « faux » visible seulement sur les photos : yeux rouges, sourire déformé
        self.fake = Entity(parent=self.root, enabled=False, position=(0, 1.7, 0.1))
        for x in (-0.05, 0.05):
            Entity(parent=self.fake, model="quad", color=color.rgb32(255, 20, 20), position=(x, 0.02, 0), scale=0.03, double_sided=True)
        Entity(parent=self.fake, model="quad", color=color.rgb32(20, 0, 0), position=(0, -0.04, 0), scale=(0.1, 0.035), double_sided=True)

    def set_target(self, pos, rot):
        self.target = Vec3(*pos)
        self.yaw_target = rot[1] if len(rot) > 1 else 0.0

    def update(self, dt):
        if not self.alive:
            return
        cur = self.root.position
        new = cur + (self.target - cur) * min(1.0, dt * 12.0)
        moved = (new - cur).length()
        self.root.position = new
        d = (self.yaw_target - self.root.rotation_y + 180) % 360 - 180
        self.root.rotation_y += d * min(1.0, dt * 10.0)
        if moved > 0.002:
            self.phase += moved * 7.0
            self.arm_l.rotation_x = math.sin(self.phase) * 28
            self.arm_r.rotation_x = -math.sin(self.phase) * 28
        else:
            self.arm_l.rotation_x *= 0.9
            self.arm_r.rotation_x *= 0.9

    def die(self):
        self.alive = False
        self.root.rotation_x = -88
        self.root.y = self.root.y + 0.15

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
        rect(r, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 170), z=1)
        label(r, "MULTIJOUEUR COOPÉRATIF", 0, 0.4, 2.4, color.white, z=0)
        label(r, "Adresse du serveur", -0.3, 0.27, 0.8, color.gray, origin=(-0.5, 0), z=0)
        self.field_addr = InputField(default_value=settings["mp_adresse"], parent=r, position=(0.0, 0.22), scale=(0.62, 0.05), character_limit=40)
        label(r, "Pseudo", -0.3, 0.15, 0.8, color.gray, origin=(-0.5, 0), z=0)
        self.field_name = InputField(default_value=settings["mp_pseudo"], parent=r, position=(0.0, 0.1), scale=(0.62, 0.05), character_limit=16)
        self.connect_btn = button(r, "Se connecter", 0, 0.01, 0.3, 0.06, self.do_connect, rgb(30, 70, 40, 240), size=1.0, z=-0.1)
        self.status = label(r, "Déconnecté", 0, -0.06, 0.8, rgb(200, 190, 150), z=0)
        label(r, "Joueurs dans le lobby", -0.3, -0.13, 0.8, color.gray, origin=(-0.5, 0), z=0)
        self.list_root = Entity(parent=r)
        self.start_btn = button(r, "Lancer la partie", 0.0, -0.36, 0.34, 0.06, self.do_start, rgb(70, 40, 30, 240), size=1.0, z=-0.1)
        self.start_btn.enabled = False
        button(r, "Retour", 0.0, -0.45, 0.24, 0.05, self.back, rgb(30, 30, 36, 240), size=0.9, z=-0.1)
        if self.connected:
            self.status.text = "Connecté"
            self._refresh_players()
        g.set_mouse(free=True)

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
        y = -0.19
        for p in self.players.values():
            tag = "  (hôte)" if p["id"] == self.host else ""
            me = "  <- vous" if p["id"] == self.client.id else ""
            c = p.get("color", [1, 1, 1])
            rect(self.list_root, -0.33, y, 0.025, 0.025, rgb(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)), z=-0.05)
            label(self.list_root, p["name"] + tag + me, -0.29, y, 0.9, color.white, origin=(-0.5, 0), z=-0.05)
            y -= 0.05
        is_host = self.client.id is not None and self.client.id == self.host
        self.start_btn.enabled = is_host
        if not is_host and self.connected:
            label(self.list_root, "En attente de l'hôte...", 0, -0.37, 0.8, color.gray, z=-0.05)

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
            if m.get("option") == "B" or (m.get("option") == "A" and False):
                pass

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
            av = RemoteAvatar(pid, p["name"], p.get("color", [0.7, 0.2, 0.2]))
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
        rect(self.over_ui, 0, 0, 2.4, 1.3, rgb(0, 0, 0, 235), z=1)
        if result == "win":
            label(self.over_ui, "Au moins un d'entre vous a survécu.", 0, 0.1, 1.8, color.white, z=0)
            label(self.over_ui, "Livraison refusée.", 0, 0.0, 1.2, rgb(200, 190, 150), z=0)
        else:
            label(self.over_ui, "Livraison effectuée.", 0, 0.1, 3.0, color.white, z=0)
            label(self.over_ui, "Personne n'a survécu.", 0, 0.0, 1.2, rgb(200, 120, 120), z=0)
        button(self.over_ui, "Menu principal", 0, -0.15, 0.3, 0.07, self._leave, rgb(30, 30, 34, 240), size=1.0, z=-0.1)
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
