"""Client réseau du mode coopératif (TCP pour les messages d'état, UDP pour les positions).

Protocole JSON, un message par ligne :
  client -> serveur : connect, move, interact, chat, order, choice, noise, death, start
  serveur -> client : welcome, lobby, start, player_move, entity_update, assistance_msg, event,
                      player_death, door_state, game_event, chat, order_result, game_over
"""
import json
import queue
import socket
import threading
import time


PROTOCOL_VERSION = "2.0"      # doit correspondre à server_config.PROTOCOL_VERSION (version majeure)

class NetClient:
    def __init__(self):
        self.sock = None
        self.udp = None
        self.addr = None
        self.connected = False
        self.id = None
        self.name = ""
        self.inbox = queue.Queue()
        self._buf = b""
        self._stop = False
        self.last_move_sent = 0.0
        self.ping = 0.0
        self.error = None
        self.connecting = False

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
        self.addr = (host, port)
        self.name = name
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.tok = None
        self._buf = b""
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.settimeout(0.2)
        self.connected = True
        threading.Thread(target=self._tcp_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()
        self.send(dict(type="connect", name=name, version=PROTOCOL_VERSION))

    def close(self):
        self._stop = True
        self.connected = False
        for s in (self.sock, self.udp):
            try:
                if s:
                    s.close()
            except OSError:
                pass
        self.sock = None
        self.udp = None

    # ------------------------------------------------------------------
    def _tcp_loop(self):
        while not self._stop and self.sock is not None:
            try:
                data = self.sock.recv(4096)
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
                except ValueError:
                    continue
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") == "welcome":
                    self.id = msg.get("id")
                    self.tok = msg.get("tok")
                    self.send_udp(dict(type="hello", id=self.id))
                elif msg.get("type") == "pong":
                    self.ping = (time.time() - msg.get("t", time.time())) * 1000.0
                self.inbox.put(msg)
        if not self._stop:
            self.connected = False
            self.inbox.put(dict(type="disconnected"))

    def _udp_loop(self):
        while not self._stop and self.udp is not None:
            try:
                data, _ = self.udp.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if isinstance(msg, dict) and self.inbox.qsize() < 2000:
                self.inbox.put(msg)

    # ------------------------------------------------------------------
    def send(self, obj):
        if not self.connected or self.sock is None:
            return False
        try:
            self.sock.sendall((json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            return True
        except OSError:
            self.connected = False
            return False

    def send_udp(self, obj):
        if self.udp is None or self.addr is None:
            return
        if getattr(self, "tok", None) and "tok" not in obj:
            obj = dict(obj, tok=self.tok)
        try:
            self.udp.sendto(json.dumps(obj, separators=(",", ":")).encode("utf-8"), self.addr)
        except OSError:
            pass

    def poll(self):
        out = []
        while True:
            try:
                out.append(self.inbox.get_nowait())
            except queue.Empty:
                break
        return out

    # --- messages ---------------------------------------------------------
    def send_move(self, pos, rot, rate=20.0):
        now = time.time()
        if now - self.last_move_sent < 1.0 / rate:
            return
        self.last_move_sent = now
        if self.id is not None:
            self.send_udp(dict(type="move", id=self.id, pos=[round(float(v), 3) for v in pos], rot=[round(float(v), 1) for v in rot]))

    def send_chat(self, text):
        self.send(dict(type="chat", message=text))

    def send_order(self, meal, address):
        self.send(dict(type="order", meal=meal, address=address))

    def send_choice(self, pair_id, choice):
        self.send(dict(type="choice", pair_id=pair_id, choice=choice))

    def send_interact(self, target, **kw):
        d = dict(type="interact", target=target)
        d.update(kw)
        self.send(d)

    def send_death(self, cause="entity_contact"):
        self.send(dict(type="death", cause=cause))

    def send_noise(self, pos, radius):
        self.send(dict(type="noise", pos=[float(pos[0]), float(pos[1]), float(pos[2])], radius=float(radius)))

    def send_start(self):
        self.send(dict(type="start"))

    def send_ping(self):
        self.send(dict(type="ping", t=time.time()))
