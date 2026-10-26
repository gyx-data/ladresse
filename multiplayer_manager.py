"""Mode multijoueur : liste des parties, création de salon, salon d'attente, joueurs distants, synchronisation.

Architecture : toutes les parties tournent sur le serveur (5.180.34.43:27326, voir server/coop_game.py) ;
elles continuent même si leur créateur s'en va. Les positions vont directement d'un joueur aux autres
(un seul passage par le serveur) et sont lissées par interpolation.

Les morts deviennent spectateurs ; sur les photos, les autres joueurs apparaissent « faux » (paranoïa) ;
chacun reçoit des messages d'assistance contradictoires.
"""
import collections
import random
import time

from ursina import Entity, Vec3, camera, color, destroy, invoke
from ursina.prefabs.input_field import InputField

import config
import game_data as gd
from config import settings
from multiplayer_client import NetClient
from character_model import CharacterModel, Nametag
from sound_engine import engine as sound
from ui_widgets import label, rect, button, clear, rgb, panel, image
import illustrations as ill

BONE = (226, 218, 204)
MUTED = (140, 132, 124)
BLOOD = (176, 22, 20)
OK_GREEN = (110, 170, 120)
ROWS = 6
ROOM_MAX_CHOICES = (2, 3, 4, 5, 6, 8)
# mêmes couleurs que server/coop_rules.JACKET_COLORS (ordre d'arrivée dans le salon)
JACKET_COLORS = [(0.75, 0.2, 0.2), (0.2, 0.45, 0.8), (0.2, 0.65, 0.3), (0.85, 0.7, 0.15),
                 (0.55, 0.25, 0.7), (0.9, 0.45, 0.15), (0.2, 0.7, 0.7), (0.85, 0.85, 0.85)]


def _lerp_angle(a, b, t):
    d = (b - a + 180.0) % 360.0 - 180.0
    return a + d * t


class RemoteAvatar:
    """Autre joueur : personnage articulé, pseudo flottant, lampe torche.

    Mouvement fluide : les positions reçues sont mises en mémoire tampon avec leur heure d'arrivée et le
    personnage est affiché légèrement dans le passé (≈ 2 intervalles d'envoi), en interpolant entre deux
    positions connues. Paquets en retard ignorés (numéro de séquence), courte extrapolation si un paquet manque."""

    def __init__(self, pid, name, jacket, seed=0):
        self.id = pid
        self.name = name
        self.root = Entity()
        self.buf = collections.deque(maxlen=32)       # (t_arrivée, Vec3, pitch, yaw)
        self.last_seq = None
        self.interval = 0.05
        self.pitch = 0.0
        self.alive = True
        self.step_dist = 0.0
        self.last = Vec3(7, 0, 1)
        self.speed = 0.0
        self.torch_on = True
        jc = tuple(jacket)
        self.model = CharacterModel(parent=self.root, jacket=jc, pants=(0.32, 0.36, 0.5), seed=seed + 2, emit=0.12)
        self.tag = Nametag(self.root, name, jc)
        self.fake = Entity(parent=self.model.head, enabled=False, position=(0, 0.12, 0.112))
        for x in (-0.04, 0.04):
            Entity(parent=self.fake, model="quad", color=color.rgb32(255, 20, 20), position=(x, 0.015, 0), scale=0.028, double_sided=True)
        Entity(parent=self.fake, model="quad", color=color.rgb32(20, 0, 0), position=(0, -0.09, 0), scale=(0.09, 0.03), double_sided=True)

    def place(self, pos):
        self.root.position = Vec3(*pos)
        self.buf.clear()

    def push(self, pos, rot, seq=None):
        if seq is not None:
            if self.last_seq is not None and 0 < (self.last_seq - seq) % 1_000_000 < 500_000:
                return                                  # paquet en retard / dupliqué
            self.last_seq = seq
        now = time.perf_counter()
        p = Vec3(*pos)
        if self.buf:
            gap = now - self.buf[-1][0]
            if 0.005 < gap < 0.5:
                self.interval += (gap - self.interval) * 0.1
            if (p - self.buf[-1][1]).length() > 6.0:     # téléportation (correction, réapparition)
                self.buf.clear()
                self.root.position = p
        pitch = rot[0] if len(rot) > 0 else 0.0
        yaw = rot[1] if len(rot) > 1 else 0.0
        self.buf.append((now, p, pitch, yaw))

    def set_target(self, pos, rot):
        self.push(pos, rot)

    def _sample(self):
        if not self.buf:
            return None
        delay = max(0.06, min(0.25, self.interval * 2.0 + 0.02))
        rt = time.perf_counter() - delay
        b = self.buf
        if rt <= b[0][0]:
            return b[0][1], b[0][2], b[0][3]
        for i in range(len(b) - 1, 0, -1):
            a, c = b[i - 1], b[i]
            if a[0] <= rt <= c[0]:
                k = (rt - a[0]) / max(1e-6, c[0] - a[0])
                return a[1] + (c[1] - a[1]) * k, a[2] + (c[2] - a[2]) * k, _lerp_angle(a[3], c[3], k)
        # plus récent que le dernier paquet : extrapolation courte, puis arrêt
        last = b[-1]
        if len(b) >= 2:
            prev = b[-2]
            span = max(1e-3, last[0] - prev[0])
            ahead = min(rt - last[0], 0.15)
            vel = (last[1] - prev[1]) / span
            return last[1] + vel * ahead, last[2], last[3]
        return last[1], last[2], last[3]

    def update(self, dt):
        if not self.alive:
            self.model.animate(dt)
            return
        s = self._sample()
        cur = self.root.position
        if s is not None:
            pos, self.pitch, yaw = s
            moved = (Vec3(pos[0], 0, pos[2]) - Vec3(cur[0], 0, cur[2])).length()
            self.root.position = pos
            self.root.rotation_y = yaw
            inst = moved / max(dt, 1e-4)
            self.speed += (inst - self.speed) * min(1.0, dt * 8.0)
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
        self.players = {}           # id -> {id, name, color}
        self.host = None
        self.rooms = []
        self.room = None
        self.page = "browser"
        self.list_page = 0
        self.root = None
        self.body = None
        self.status = None
        self.status_dot = None
        self.ping_lbl = None
        self.field_name = None
        self.field_addr = None
        self.start_btn = None
        self.in_game = False
        self.dead = False
        self.spectate_id = None
        self.ping_t = 0.0
        self.refresh_t = 0.0
        self.last_move_pos = None
        self.over_ui = None
        self.fake_active = False
        self.lobby_open = False
        self._pending_status = None
        self._create_max = int(settings.get("mp_max", 4))
        self._join_target = None

    # ------------------------------------------------------------------
    @property
    def connected(self):
        return self.client.connected

    def disconnect(self):
        self.client.close()
        self._clear_avatars()
        self.in_game = False
        self.dead = False
        self.room = None
        if self.root is not None:
            self.root.enabled = False
        self.lobby_open = False

    def _clear_avatars(self):
        for a in self.avatars.values():
            a.destroy()
        self.avatars = {}

    def _set_status(self, text, ok=None):
        if self.status is not None and self.lobby_open:
            self.status.text = text
            if ok is not None and self.status_dot is not None:
                self.status_dot.color = rgb(*OK_GREEN) if ok else rgb(*BLOOD)

    # ------------------------------------------------------------------
    # Écran multijoueur
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
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 200), z=1)
        panel(r, 0, 0, 1.46, 0.88, "panel", z=0.9)
        label(r, "MULTIJOUEUR", -0.68, 0.385, 1.7, rgb(*BONE), origin=(-0.5, 0), z=0)
        rect(r, -0.5, 0.345, 0.36, 0.0022, rgb(*BLOOD), z=0)
        label(r, "PSEUDO", 0.24, 0.39, 0.5, rgb(*MUTED), origin=(-0.5, 0), z=0)
        self.field_name = InputField(default_value=settings["mp_pseudo"], parent=r, position=(0.5, 0.39, -0.05),
                                     scale=(0.2, 0.045), character_limit=16)
        # pastille blanche teintée ensuite (une texture déjà colorée ne se reteinte pas correctement)
        self.status_dot = rect(r, -0.68, 0.315, 0.014, 0.014, rgb(255, 255, 255), z=0, radius=0.5)
        self.status_dot.color = rgb(*BLOOD)
        self.status = label(r, "Déconnecté", -0.665, 0.315, 0.6, rgb(*MUTED), origin=(-0.5, 0), z=0, max_w=1.1)
        self.ping_lbl = label(r, "", 0.68, 0.315, 0.55, rgb(*MUTED), origin=(0.5, 0), z=0)
        self.body = Entity(parent=r)
        if self.client.room is not None:
            self.room = self.client.room
            self._render("room")
        else:
            self._render("browser")
        if self.connected and self.client.id is not None:
            self._set_status("Connecté au serveur", True)
            self.client.list_rooms()
        else:
            self._connect()
        g.set_mouse(free=True)

    def _render(self, page=None):
        if page is not None:
            self.page = page
        if self.body is None or not self.lobby_open:
            return
        clear(self.body)
        getattr(self, "_page_" + self.page)()

    # --- liste des parties ---------------------------------------------
    def _page_browser(self):
        b = self.body
        cols = ((-0.66, "PARTIE"), (-0.13, "HÔTE"), (0.13, "JOUEURS"), (0.27, "ÉTAT"))
        for x, t in cols:
            label(b, t, x, 0.255, 0.5, rgb(*MUTED), origin=(-0.5, 0), z=0)
        rooms = self.rooms
        pages = max(1, (len(rooms) + ROWS - 1) // ROWS)
        self.list_page = min(self.list_page, pages - 1)
        shown = rooms[self.list_page * ROWS:(self.list_page + 1) * ROWS]
        y = 0.2
        for room in shown:
            self._room_row(b, room, y)
            y -= 0.072
        if not rooms:
            label(b, "Aucune partie pour l'instant." if self.connected else "Connexion au serveur...", 0, 0.06, 0.95,
                  rgb(*BONE), z=0)
            if self.connected:
                label(b, "Créez la vôtre : vos amis la verront ici.", 0, 0.0, 0.65, rgb(*MUTED), z=0)
        if pages > 1:
            button(b, "‹", 0.5, -0.24, 0.05, 0.045, lambda: self._page_list(-1), style="dark", size=0.9)
            label(b, f"{self.list_page + 1} / {pages}", 0.585, -0.24, 0.6, rgb(*MUTED), z=0)
            button(b, "›", 0.67, -0.24, 0.05, 0.045, lambda: self._page_list(1), style="dark", size=0.9)
        # serveur (avancé)
        label(b, "SERVEUR", -0.68, -0.27, 0.45, rgb(*MUTED), origin=(-0.5, 0), z=0)
        self.field_addr = InputField(default_value=settings["mp_adresse"], parent=b, position=(-0.46, -0.27, -0.05),
                                     scale=(0.3, 0.04), character_limit=40)
        button(b, "Connexion", -0.22, -0.27, 0.14, 0.04, self._reconnect, style="dark", size=0.55)
        button(b, "Serveur local (LAN)", 0.0, -0.27, 0.2, 0.04, self.host_local, style="ghost", size=0.55)
        # actions
        button(b, "Retour", -0.6, -0.36, 0.17, 0.055, self.back, style="dark", size=0.75)
        button(b, "Actualiser", 0.22, -0.36, 0.2, 0.055, self._refresh, style="dark", size=0.75)
        button(b, "Créer une partie", 0.5, -0.36, 0.3, 0.06, lambda: self._render("create"), style="primary", size=0.85)

    def _room_row(self, b, room, y):
        rect(b, 0.0, y, 1.38, 0.062, rgb(255, 255, 255, 9), z=0.5)
        name = room.get("name", "?") + ("   · privée" if room.get("locked") else "")
        label(b, name, -0.66, y, 0.72, rgb(*BONE), origin=(-0.5, 0), z=0.2, max_w=0.5)
        label(b, room.get("host_name", "?"), -0.13, y, 0.62, rgb(*MUTED), origin=(-0.5, 0), z=0.2, max_w=0.24)
        n, mx = room.get("players", 0), room.get("max", 4)
        label(b, f"{n} / {mx}", 0.13, y, 0.65, rgb(*BONE) if n < mx else rgb(*BLOOD), origin=(-0.5, 0), z=0.2)
        reason = None
        if room.get("phase") != "lobby":
            reason = "En cours"
        elif n >= mx:
            reason = "Complète"
        elif room.get("game") != config.VERSION:
            reason = f"Version {room.get('game')}"
        label(b, reason or "En attente", 0.27, y, 0.6, rgb(*MUTED) if reason else rgb(*OK_GREEN), origin=(-0.5, 0), z=0.2,
              max_w=0.2)
        if reason is None:
            button(b, "Rejoindre", 0.6, y, 0.15, 0.046, lambda rm=room: self._join(rm), style="primary", size=0.62)

    def _page_list(self, d):
        self.list_page = max(0, self.list_page + d)
        self._render()

    def _refresh(self):
        if self.connected:
            self.client.list_rooms()
        else:
            self._connect()

    # --- création --------------------------------------------------------
    def _page_create(self):
        b = self.body
        label(b, "CRÉER UNE PARTIE", -0.4, 0.24, 1.1, rgb(*BONE), origin=(-0.5, 0), z=0)
        label(b, "Nom de la partie", -0.4, 0.15, 0.6, rgb(*MUTED), origin=(-0.5, 0), z=0)
        self.f_room = InputField(default_value=f"Partie de {self._pseudo()}", parent=b, position=(0.06, 0.11, -0.05),
                                 scale=(0.92, 0.05), character_limit=32)
        label(b, "Joueurs maximum", -0.4, 0.03, 0.6, rgb(*MUTED), origin=(-0.5, 0), z=0)
        button(b, "‹", -0.32, -0.02, 0.05, 0.05, lambda: self._step_max(-1), style="dark", size=0.9)
        self.max_lbl = label(b, str(self._create_max), -0.23, -0.02, 1.1, rgb(*BONE), z=0)
        button(b, "›", -0.14, -0.02, 0.05, 0.05, lambda: self._step_max(1), style="dark", size=0.9)
        label(b, "Conseillé : 2 à 4. Au-delà, la maison devient très peuplée.", -0.08, -0.02, 0.52, rgb(*MUTED),
              origin=(-0.5, 0), z=0, max_w=0.6)
        label(b, "Mot de passe (facultatif)", -0.4, -0.1, 0.6, rgb(*MUTED), origin=(-0.5, 0), z=0)
        self.f_pass = InputField(default_value="", parent=b, position=(-0.16, -0.14, -0.05), scale=(0.48, 0.05),
                                 character_limit=32)
        label(b, "La partie tourne sur le serveur : elle continue même si vous partez avant la fin.", 0, -0.22, 0.55,
              rgb(*MUTED), z=0, max_w=1.3)
        button(b, "Annuler", 0.2, -0.36, 0.18, 0.055, lambda: self._render("browser"), style="dark", size=0.75)
        button(b, "Créer", 0.5, -0.36, 0.3, 0.06, self._create, style="primary", size=0.9)

    def _step_max(self, d):
        ch = list(ROOM_MAX_CHOICES)
        i = ch.index(self._create_max) if self._create_max in ch else 2
        self._create_max = ch[max(0, min(len(ch) - 1, i + d))]
        self.max_lbl.text = str(self._create_max)

    def _create(self):
        if not self.connected:
            self._set_status("Pas de connexion au serveur.", False)
            return
        self._save_pseudo()
        settings["mp_max"] = self._create_max
        settings.save()
        self.client.create_room(self.f_room.text.strip(), self._create_max, self.f_pass.text.strip())
        self._set_status("Création de la partie...")

    # --- mot de passe -----------------------------------------------------
    def _join(self, room):
        self._save_pseudo()
        if room.get("locked"):
            self._join_target = room
            self._render("password")
            return
        self.client.join_room(room["id"])
        self._set_status(f"Connexion à « {room.get('name', '?')} »...")

    def _page_password(self):
        b = self.body
        room = self._join_target or {}
        label(b, f"« {room.get('name', '?')} » est privée", 0, 0.16, 1.0, rgb(*BONE), z=0, max_w=1.2)
        label(b, "Mot de passe", -0.3, 0.06, 0.6, rgb(*MUTED), origin=(-0.5, 0), z=0)
        self.f_join_pass = InputField(default_value="", parent=b, position=(0.0, 0.01, -0.05), scale=(0.6, 0.05),
                                      character_limit=32)
        button(b, "Annuler", 0.2, -0.36, 0.18, 0.055, lambda: self._render("browser"), style="dark", size=0.75)
        button(b, "Rejoindre", 0.5, -0.36, 0.3, 0.06, self._join_with_password, style="primary", size=0.9)

    def _join_with_password(self):
        room = self._join_target
        if room:
            self.client.join_room(room["id"], self.f_join_pass.text)
            self._set_status("Vérification du mot de passe...")

    # --- salon d'attente --------------------------------------------------
    def _page_room(self):
        b = self.body
        room = self.room or {}
        mx = room.get("max", 4)
        label(b, room.get("name", "Partie"), -0.66, 0.245, 1.1, rgb(*BONE), origin=(-0.5, 0), z=0, max_w=1.0)
        info = f"Code {room.get('id', '?')}   ·   {len(self.players)} / {mx} joueurs" + ("   ·   privée" if room.get("locked") else "")
        label(b, info, -0.66, 0.195, 0.58, rgb(*MUTED), origin=(-0.5, 0), z=0)
        is_host = self.client.is_host
        cols = 2 if mx > 4 else 1
        cw = 0.66 if cols == 2 else 0.9
        xs = (-0.33, 0.36) if cols == 2 else (0.0,)
        ids = list(self.players)
        for slot in range(mx):
            col, row = (slot % cols, slot // cols)
            x, y = xs[col], 0.11 - row * 0.085
            rect(b, x, y, cw, 0.072, rgb(255, 255, 255, 12 if slot < len(ids) else 4), z=0.5)
            if slot >= len(ids):
                label(b, "En attente d'un joueur…", x, y, 0.6, rgb(90, 86, 82), z=0.2)
                continue
            p = self.players[ids[slot]]
            c = p.get("color", [1, 1, 1])
            image(b, ill.avatar((int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)), 96), x - cw / 2 + 0.045, y, 0.055, 0.055, z=0.3)
            me = p["id"] == self.client.id
            label(b, p["name"] + ("  (vous)" if me else ""), x - cw / 2 + 0.09, y + 0.011, 0.75, rgb(*BONE),
                  origin=(-0.5, 0), z=0.2, max_w=cw - 0.3)
            label(b, "Créateur" if p["id"] == self.host else "Prêt", x - cw / 2 + 0.09, y - 0.019, 0.5,
                  rgb(*BLOOD) if p["id"] == self.host else rgb(*OK_GREEN), origin=(-0.5, 0), z=0.2)
            if is_host and not me:
                button(b, "Exclure", x + cw / 2 - 0.07, y, 0.11, 0.04, lambda pid=p["id"]: self._kick(pid), style="ghost", size=0.5)
        button(b, "Quitter le salon", -0.55, -0.36, 0.26, 0.055, self._leave_room, style="dark", size=0.72)
        if is_host:
            self.start_btn = button(b, "Lancer la partie", 0.5, -0.36, 0.3, 0.062, self.do_start, style="primary", size=0.9)
            label(b, "Vous avez créé la partie : lancez-la quand tout le monde est prêt.", 0.1, -0.27, 0.52, rgb(*MUTED), z=0)
        else:
            self.start_btn = None
            label(b, "En attente du lancement par le créateur…", 0.3, -0.36, 0.65, rgb(*MUTED), z=0)

    def _kick(self, pid):
        self.client.send(dict(type="kick", id=pid))

    def _leave_room(self):
        self.client.leave_room()
        self.room = None
        self.players = {}
        self._render("browser")
        self.client.list_rooms()

    # --- connexion ------------------------------------------------------------
    def _pseudo(self):
        f = self.field_name
        return (f.text.strip() if f is not None else "") or settings["mp_pseudo"] or "Joueur"

    def _save_pseudo(self):
        settings["mp_pseudo"] = self._pseudo()
        settings.save()

    def _parse_addr(self, text):
        text = (text or "").strip() or config.SERVER_NAME
        real = config.SERVER_ALIASES.get(text.lower(), text)       # nom affiché (« France 1 ») -> adresse réelle
        host, port = real, config.SERVER_PORT
        if ":" in real:
            host, p = real.rsplit(":", 1)
            try:
                port = int(p)
            except ValueError:
                port = config.SERVER_PORT
        return text, host, port

    def _connect(self, addr_text=None):
        if self.client.connected or self.client.connecting:
            return
        text, host, port = self._parse_addr(addr_text or settings["mp_adresse"])
        settings["mp_adresse"] = text
        shown = text if text.lower() in config.SERVER_ALIASES else f"{host}:{port}"
        self._set_status(f"Connexion à {shown}...")
        self.client.connect_async(host, port, self._pseudo(), self._on_connect_result)

    def _reconnect(self):
        text = self.field_addr.text if self.field_addr is not None else None
        self.client.close()
        self.rooms = []
        self._render("browser")
        self._connect(text)

    def _on_connect_result(self, ok, msg):
        self._pending_status = (msg, ok)

    def host_local(self):
        """Lance le serveur dans ce processus (partie en réseau local ou en ouvrant le port sur sa box)."""
        if getattr(self, "_local_server", None) is None:
            try:
                import importlib.util
                import os
                import sys
                base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
                sdir = os.path.join(base, "server")
                if sdir not in sys.path:
                    sys.path.append(sdir)
                os.environ.setdefault("LADRESSE_LOG", os.path.join(config.app_data_dir(), "server.log"))
                spec = importlib.util.spec_from_file_location("ladresse_relay", os.path.join(sdir, "server.py"))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                srv = mod.RelayServer("0.0.0.0", config.SERVER_PORT)
                srv.start(block=False)
                self._local_server = srv
            except Exception as e:
                self._set_status(f"Impossible de lancer le serveur local : {e}", False)
                return
        self.client.close()
        self.rooms = []
        self._render("browser")
        invoke(self._connect, f"127.0.0.1:{config.SERVER_PORT}", delay=0.3)

    def back(self):
        self.disconnect()
        if self.root is not None:
            self.root.enabled = False
        self.game.show_menu()

    def do_start(self):
        if self.client.is_host:
            self.client.send_start()

    def on_key(self, key):
        if key == "escape":
            if self.page in ("create", "password"):
                self._render("browser")
            elif self.page == "room":
                self._leave_room()
            else:
                self.back()

    def _refresh_players(self):
        if self.page == "room":
            self._render()

    # ------------------------------------------------------------------
    # Boucle
    # ------------------------------------------------------------------
    def update(self, dt):
        st = self._pending_status
        if st is not None:
            self._pending_status = None
            if not st[1]:
                self._set_status(st[0], False)
        for msg in self.client.poll():
            self.handle(msg)
        g = self.game
        if self.in_game and g.mode == "playing" and not self.dead:
            p = g.player
            self.client.send_move(p.pos, (p.pitch, p.yaw))
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
            if self.lobby_open and self.ping_lbl is not None:
                pg = self.client.ping
                udp = "" if self.client.udp_ok() else "  · UDP bloqué (repli TCP)"
                self.ping_lbl.text = (f"{int(pg)} ms" if pg else "") + udp
        if self.lobby_open and self.page == "browser" and self.connected:
            self.refresh_t -= dt
            if self.refresh_t <= 0:
                self.refresh_t = 3.0
                self.client.list_rooms()

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
    # Messages (relais + hôte)
    # ------------------------------------------------------------------
    def _roster(self, players):
        cols = JACKET_COLORS
        return {p["id"]: dict(id=p["id"], name=p.get("name", "?"), color=list(cols[i % len(cols)])) for i, p in enumerate(players)}

    def handle(self, m):
        g = self.game
        t = m.get("type")
        if t == "hello_ok":
            motd = m.get("motd", "")
            self._set_status("Connecté au serveur" + (f"  —  {motd}" if motd else ""), True)
            self.client.list_rooms()
            return
        if t == "rooms":
            self.rooms = m.get("rooms", [])
            if self.page == "browser":
                self._render()
            return
        if t == "room":
            before = set(self.players)
            self.room = m.get("room")
            self.host = m.get("host")
            self.players = self._roster(m.get("players", []))
            if self.in_game:
                for pid in before - set(self.players):
                    self._remove_avatar(pid)
            elif self.lobby_open:
                self._set_status("Dans le salon " + (self.room or {}).get("id", ""), True)
                self._render("room")
            return
        if t == "room_closed":
            reason = m.get("reason", "La partie a été fermée.")
            self.room = None
            self.players = {}
            if self.in_game:
                self._interrupted(reason)
            else:
                self._set_status(reason, False)
                self._render("browser")
            return
        if t == "left":
            return
        if t == "notice":
            if self.in_game:
                g.ui.say(m.get("message", ""), 6.0, "Serveur")
            else:
                self._set_status(m.get("message", ""))
            return
        if t == "error":
            code = m.get("code")
            self._set_status(m.get("message", "Erreur"), False)
            if code == "password" and self.page == "password":
                return
            if code in ("proto", "busy", "kicked"):
                self.client.close()
            elif self.page in ("password", "create"):
                self._render("browser")
            return
        if t == "disconnected":
            if self.in_game:
                self._interrupted("Connexion au serveur perdue.")
            else:
                self.room = None
                self._set_status("Connexion perdue.", False)
                self._render("browser")
            return
        if t == "start":
            self.players = {p["id"]: p for p in m.get("players", [])}
            self.start_game()
            return
        if not self.in_game:
            return
        if t == "move":
            a = self.avatars.get(m.get("_from"))
            if a is not None and isinstance(m.get("pos"), list) and len(m["pos"]) == 3:
                a.push(m["pos"], m.get("rot", [0, 0]), m.get("s"))
        elif t == "entity_update":
            seq = m.get("s")
            if seq is not None:
                last = getattr(self, "_entity_seq", -1)
                if seq < last and last - seq < 200:
                    return                       # instantané UDP arrivé en retard
                self._entity_seq = seq
            g.entity.remote_update(m)
        elif t == "assistance_msg":
            self._on_assistance(m)
        elif t == "game_event":
            self._on_event(m)
        elif t == "event":
            if m.get("name") == "knock":
                g.assistance._knock(0)
        elif t == "player_death":
            self._on_death(m)
        elif t == "player_left":
            self._remove_avatar(m.get("id"), m.get("name"))
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
        elif t == "game_over":
            self._game_over(m.get("result", "lose"))

    def _remove_avatar(self, pid, name=None):
        a = self.avatars.pop(pid, None)
        if a is not None:
            a.destroy()
            self.game.ui.say(f"{name or a.name} a quitté la partie.", 5.0)

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
        self._entity_seq = -1
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
        ids = list(self.players)
        n = max(1, len(ids))
        for idx, pid in enumerate(ids):
            spot = (7.0 + (idx - (n - 1) / 2) * 0.45, 0.0, 0.9)
            if pid == me:
                g.player.place(spot, 0.0, 0.0)
                continue
            p = self.players[pid]
            av = RemoteAvatar(pid, p["name"], p.get("color", [0.7, 0.2, 0.2]), seed=len(self.avatars))
            av.place(spot)
            self.avatars[pid] = av
        g.ui.say("Comparez vos messages d'assistance... si vous osez.", 6.0)
        g.phone.model.conversations["chat"]["hidden"] = False

    def _end_screen(self, title, title_col, sub, sub_col, show_players=True):
        g = self.game
        self.in_game = False
        if self.over_ui is not None:
            destroy(self.over_ui)
        g.mode = "gameover"
        g.player.frozen = True
        self.over_ui = Entity(parent=camera.ui, z=-20)
        rect(self.over_ui, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 235), z=1)
        panel(self.over_ui, 0, 0, 0.9, 0.6, "panel", z=0.8)
        label(self.over_ui, title, 0, 0.2, 2.2, title_col, z=0, max_w=0.84)
        label(self.over_ui, sub, 0, 0.12, 0.85, sub_col, z=0, max_w=0.84)
        y = 0.03
        if show_players:
            for pid, p in list(self.players.items())[:6]:
                alive = (pid == self.client.id and not self.dead) or (pid in self.avatars and self.avatars[pid].alive)
                c = p.get("color", [1, 1, 1])
                image(self.over_ui, ill.avatar((int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)), 96, dead=not alive), -0.2, y, 0.05, 0.05, z=0)
                label(self.over_ui, p.get("name", "?"), -0.16, y, 0.8, rgb(*BONE), origin=(-0.5, 0), z=0)
                label(self.over_ui, "survivant" if alive else "livré", 0.25, y, 0.7, rgb(*OK_GREEN) if alive else rgb(*BLOOD),
                      origin=(0.5, 0), z=0)
                y -= 0.045
        button(self.over_ui, "Menu principal", 0, -0.23, 0.3, 0.065, self._leave, style="primary", size=0.9, z=-0.1)
        g.set_mouse(free=True)

    def _game_over(self, result):
        if result == "win":
            self._end_screen("LIVRAISON REFUSÉE", rgb(*BONE), "Au moins un d'entre vous a survécu jusqu'à l'aube.", rgb(*MUTED))
        else:
            self._end_screen("LIVRAISON EFFECTUÉE", rgb(*BLOOD), "Personne n'a survécu.", rgb(200, 120, 120))

    def _interrupted(self, reason):
        self._end_screen("PARTIE INTERROMPUE", rgb(*BONE), reason, rgb(*MUTED), show_players=False)

    def _leave(self):
        if self.over_ui is not None:
            destroy(self.over_ui)
            self.over_ui = None
        self.client.leave_room()
        self.room = None
        self.game.to_main_menu()

    # ------------------------------------------------------------------
    # Spectateur : caméra suivant un joueur vivant
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
