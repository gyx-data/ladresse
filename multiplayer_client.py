"""Client réseau du mode multijoueur, branché sur le serveur RELAIS (TCP : messages fiables, UDP : positions).

Le relais gère les salons et fait suivre les paquets ; la partie elle-même tourne chez l'hôte du salon
(coop_host.HostSession). Ce client :
  * parle au relais : hello, list, create, join, leave, room_state ;
  * envoie les messages de jeu à l'hôte (ou les livre directement si l'on EST l'hôte) ;
  * reçoit les messages de l'hôte et les positions des autres joueurs, et les range dans `inbox`
    sous leur forme habituelle (type="start", "entity_update", "move"... + "_from").
"""
import json
import queue
import socket
import threading
import time

import config

PROTOCOL_VERSION = "3.0"      # protocole du relais (server_config.PROTOCOL_VERSION, version majeure)
SEND_RATE = 20.0              # positions envoyées par seconde
KEEPALIVE = 0.5               # renvoi de la position même immobile (s)


class NetClient:
    def __init__(self):
        self.sock = None
        self.udp = None
        self.addr = None
        self.connected = False
        self.connecting = False
        self.id = None
        self.tok = None
        self.name = ""
        self.inbox = queue.Queue()
        self._buf = b""
        self._stop = False
        self._send_lock = threading.Lock()
        self.ping = 0.0
        self.error = None
        self.room = None              # infos du salon (dict) ou None
        self.host_id = None
        self.host_session = None      # HostSession si l'on est l'hôte
        self.last_udp = 0.0
        self.hello_t = None
        self.last_move_sent = 0.0
        self._last_move = None
        self._seq = 0

    @property
    def is_host(self):
        return self.room is not None and self.id is not None and self.host_id == self.id

    # ------------------------------------------------------------------
    # Connexion au relais
    # ------------------------------------------------------------------
    def connect_async(self, host, port, name, callback):
        """Connexion dans un thread (l'interface ne se fige pas). callback(ok, message)."""
        if self.connecting:
            return
        self.connecting = True

        def run():
            try:
                self.connect(host, port, name)
                callback(True, "Connecté")
            except Exception as e:
                self.close()
                callback(False, f"Connexion impossible : {e}")
            finally:
                self.connecting = False
        threading.Thread(target=run, daemon=True).start()

    def connect(self, host, port, name, timeout=5.0):
        self._stop = False
        self.addr = (socket.gethostbyname(host), int(port))
        self.name = name
        self.sock = socket.create_connection(self.addr, timeout=timeout)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._buf = b""
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.settimeout(0.2)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            try:
                self.udp.ioctl(socket.SIO_UDP_CONNRESET, False)
            except (OSError, ValueError):
                pass
        self.connected = True
        threading.Thread(target=self._tcp_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()
        self.send(dict(type="hello", name=name, proto=PROTOCOL_VERSION, game=config.VERSION))

    def close(self):
        self._stop = True
        self.connected = False
        self.stop_hosting()
        self.room = None
        self.host_id = None
        for s in (self.sock, self.udp):
            try:
                if s:
                    s.close()
            except OSError:
                pass
        self.sock = None
        self.udp = None
        self.id = None

    # ------------------------------------------------------------------
    # Salons
    # ------------------------------------------------------------------
    def list_rooms(self):
        self.send(dict(type="list"))

    def create_room(self, name, max_players, password=""):
        self.send(dict(type="create", name=name, max=int(max_players), password=password, game=config.VERSION))

    def join_room(self, code, password=""):
        self.send(dict(type="join", room=code, password=password, game=config.VERSION))

    def leave_room(self):
        self.stop_hosting()
        if self.room is not None:
            self.send(dict(type="leave"))
        self.room = None
        self.host_id = None

    def set_room_phase(self, phase):
        self.send(dict(type="room_state", phase=phase))

    def start_hosting(self, max_players):
        if self.host_session is None:
            from coop_host import HostSession
            self.host_session = HostSession(self, max_players)
        return self.host_session

    def stop_hosting(self):
        if self.host_session is not None:
            self.host_session.stop()
            self.host_session = None

    # ------------------------------------------------------------------
    # Réception
    # ------------------------------------------------------------------
    def _tcp_loop(self):
        while not self._stop and self.sock is not None:
            try:
                data = self.sock.recv(16384)
            except OSError:
                break
            if not data:
                break
            self._buf += data
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                if isinstance(msg, dict):
                    self._on_tcp(msg)
        if not self._stop:
            self.connected = False
            self.stop_hosting()
            self.inbox.put(dict(type="disconnected"))

    def _on_tcp(self, msg):
        t = msg.get("type")
        if t == "from":
            self._deliver(msg.get("from"), msg.get("d"))
            return
        if t == "hello_ok":
            self.id = msg.get("id")
            self.tok = msg.get("tok")
            self.hello_t = time.time()
            self.last_udp = 0.0
            self._udp_hello()
        elif t == "pong":
            try:
                self.ping = (time.time() - float(msg.get("t"))) * 1000.0
            except (TypeError, ValueError):
                pass
        elif t == "room":
            self.room = msg.get("room")
            self.host_id = msg.get("host")
            if self.is_host:
                hs = self.start_hosting((self.room or {}).get("max", 4))
                hs.sync_members(msg.get("players", []))
            else:
                self.stop_hosting()
        elif t in ("room_closed", "left"):
            self.stop_hosting()
            self.room = None
            self.host_id = None
        self.inbox.put(msg)

    def _deliver(self, sender, d):
        """Message de jeu venant d'un autre joueur (via le relais)."""
        if not isinstance(d, dict) or sender == self.id:
            return
        kind = d.get("type")
        if self.is_host:
            if self.host_session is not None:
                self.host_session.receive(sender, d)
            if kind == "move":
                self.inbox.put(dict(d, _from=sender))
        elif sender == self.host_id or kind == "move":
            # seuls l'hôte (état de la partie) et les positions des joueurs sont acceptés
            if self.inbox.qsize() < 4000:
                self.inbox.put(dict(d, _from=sender))

    def deliver_local(self, obj):
        """Message de l'hôte destiné à soi-même (pas d'aller-retour réseau)."""
        self.inbox.put(dict(obj, _from=self.id))

    def _udp_loop(self):
        while not self._stop and self.udp is not None:
            try:
                data, _ = self.udp.recvfrom(4096)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except OSError:
                if self._stop:
                    break
                time.sleep(0.05)
                continue
            self.last_udp = time.time()
            try:
                msg = json.loads(data.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(msg, dict) and "f" in msg:
                self._deliver(msg.get("f"), msg.get("d"))

    # ------------------------------------------------------------------
    # Envoi
    # ------------------------------------------------------------------
    def send(self, obj):
        if not self.connected or self.sock is None:
            return False
        data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self._send_lock:          # l'hôte envoie aussi depuis son thread de partie
                self.sock.sendall(data)
            return True
        except OSError:
            self.connected = False
            return False

    def _udp_send(self, obj):
        if self.udp is None or self.addr is None or self.id is None:
            return
        try:
            self.udp.sendto(json.dumps(obj, separators=(",", ":")).encode("utf-8"), self.addr)
        except OSError:
            pass

    def _udp_hello(self):
        self._udp_send(dict(i=self.id, k=self.tok, h=1))

    def udp_ok(self):
        """UDP opérationnel ? (un paquet reçu depuis moins de 3 s, ou tout début de session)."""
        if self.hello_t is None:
            return False
        now = time.time()
        return (self.last_udp > 0 and now - self.last_udp < 3.0) or now - self.hello_t < 3.0

    def relay(self, to, d, udp=False):
        """Fait suivre `d` aux joueurs `to` ("all", "host", id ou liste d'ids) via le relais."""
        if udp and self.udp_ok():
            self._udp_send(dict(i=self.id, k=self.tok, to=to, d=d))
        else:
            self.send(dict(type="to", to=to, d=d))

    def _to_host(self, d):
        if self.is_host and self.host_session is not None:
            self.host_session.receive(self.id, d)
        else:
            self.relay("host", d)

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        return out

    # --- messages de jeu --------------------------------------------------
    def send_move(self, pos, rot, rate=SEND_RATE):
        now = time.time()
        if now - self.last_move_sent < 1.0 / rate or self.id is None or self.room is None:
            return
        p = [round(float(v), 3) for v in pos]
        r = [round(float(v), 1) for v in rot]
        if self._last_move == (p, r) and now - self.last_move_sent < KEEPALIVE:
            return                         # immobile : pas besoin d'inonder le réseau
        self.last_move_sent = now
        self._last_move = (p, r)
        self._seq = (self._seq + 1) % 1_000_000
        d = dict(type="move", pos=p, rot=r, s=self._seq)
        if self.is_host and self.host_session is not None:
            self.host_session.receive(self.id, d)
        # diffusion directe à tous les joueurs (un seul passage par le relais) ; repli TCP limité à 10 Hz
        if self.udp_ok():
            self._udp_send(dict(i=self.id, k=self.tok, to="all", d=d))
        elif now - getattr(self, "_last_tcp_move", 0.0) >= 0.1:
            self._last_tcp_move = now
            self.send(dict(type="to", to="all", d=d))

    def send_chat(self, text):
        self._to_host(dict(type="chat", message=text))

    def send_order(self, meal, address):
        self._to_host(dict(type="order", meal=meal, address=address))

    def send_choice(self, pair_id, choice):
        self._to_host(dict(type="choice", pair_id=pair_id, choice=choice))

    def send_interact(self, target, **kw):
        d = dict(type="interact", target=target)
        d.update(kw)
        self._to_host(d)

    def send_death(self, cause="entity_contact"):
        self._to_host(dict(type="death", cause=cause))

    def send_noise(self, pos, radius):
        self._to_host(dict(type="noise", pos=[float(pos[0]), float(pos[1]), float(pos[2])], radius=float(radius)))

    def send_start(self):
        if self.is_host:
            self.set_room_phase("playing")
            self._to_host(dict(type="start"))

    def send_ping(self):
        self.send(dict(type="ping", t=time.time()))
        if self.id is not None:
            self._udp_hello()              # garde le passage UDP ouvert (NAT) et le vérifie
