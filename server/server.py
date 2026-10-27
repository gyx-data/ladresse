"""Serveur multijoueur de L'ADRESSE.

Tourne sur Pterodactyl (Python 3.8+, aucune dépendance) :  ``python server.py``
IP publique : 5.180.34.43 | Port : 27326 (TCP pour les messages, UDP pour les positions)

Toutes les parties tournent SUR CE SERVEUR (une instance de coop_game.RoomGame par salon, une seule boucle
de jeu à 20 ticks/s pour tous les salons). Le serveur :
  * gère les salons : créer (nom, limite de joueurs, mot de passe facultatif), lister, rejoindre, quitter ;
  * fait tourner la partie de chaque salon (IA du livreur, minuteries, messages d'assistance, morts, victoire) ;
    elle continue même si son créateur s'en va ;
  * fait suivre les positions de joueur à joueur (UDP, repli TCP si l'UDP est bloqué) ;
  * protège le serveur : limites de débit, de taille, de connexions, délais d'inactivité.
Seules les règles du multijoueur (coop_*.py) vivent ici : les autres mises à jour du jeu ne touchent pas le serveur.

Protocole : JSON, un message par ligne (TCP) ou par datagramme (UDP). Voir LISEZMOI_SERVEUR.md.
"""
import itertools
import json
import os
import queue
import secrets
import signal
import socket
import sys
import threading
import time
import unicodedata

import server_config as cfg
import coop_rules
from coop_game import RoomGame

_log_lock = threading.Lock()
_log_file = None


def log(*a):
    """Journal console + fichier (server.log, rotation à 2 Mo)."""
    global _log_file
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + " ".join(str(x) for x in a)
    with _log_lock:
        try:
            print(line, flush=True)
        except (UnicodeEncodeError, UnicodeDecodeError):
            enc = getattr(sys.stdout, "encoding", None) or "ascii"
            print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)
        except (OSError, ValueError):
            pass
        try:
            if _log_file is None:
                path = cfg.LOG_FILE
                if os.path.exists(path) and os.path.getsize(path) > 2 * 1024 * 1024:
                    os.replace(path, path + ".old")
                _log_file = open(path, "a", encoding="utf-8")
            _log_file.write(line + "\n")
            _log_file.flush()
        except OSError:
            pass


def clean_text(text, limit, default=""):
    text = "".join(ch for ch in str(text) if unicodedata.category(ch)[0] != "C").strip()
    return " ".join(text.split())[:limit] or default


def clean_name(name, taken):
    """Pseudo affichable : 1 à 16 caractères, unique dans le salon."""
    name = clean_text(name, 16, "Joueur")
    base, n = name, 2
    while name.lower() in taken:
        suffix = f"#{n}"
        name = base[:16 - len(suffix)] + suffix
        n += 1
    return name


ROOM_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class Connection:
    """Connexion TCP d'un joueur. Envois via une file + thread d'écriture : un client lent ne bloque personne."""

    _ids = itertools.count(1)

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.id = next(Connection._ids)
        self.name = None
        self.room = None
        self.alive = True
        self.buf = b""
        self.q = queue.Queue(maxsize=cfg.SEND_QUEUE_MAX)
        self.last_recv = time.time()
        self.tokens = float(cfg.RATE_BURST)
        self.last_refill = time.time()
        self.flood_strikes = 0
        self.udp_token = secrets.token_hex(8)
        self.udp_addr = None
        self.udp_tokens = float(cfg.UDP_RATE_PER_SEC)
        self.udp_refill = time.time()
        self.fallback = {}
        self.writer = threading.Thread(target=self._writer, daemon=True)
        self.writer.start()

    def send(self, obj):
        if not self.alive:
            return False
        try:
            data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            self.q.put_nowait(data)
            return True
        except queue.Full:
            log(f"{self.addr} : file d'envoi saturée, déconnexion")
            self.close()
            return False
        except (TypeError, ValueError):
            return False

    def _writer(self):
        while self.alive:
            try:
                data = self.q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.sock.sendall(data)
            except OSError:
                self.alive = False
                break

    def allow(self):
        now = time.time()
        self.tokens = min(cfg.RATE_BURST, self.tokens + (now - self.last_refill) * cfg.RATE_PER_SEC)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        self.flood_strikes += 1
        return False

    def allow_udp(self):
        now = time.time()
        self.udp_tokens = min(cfg.UDP_RATE_PER_SEC, self.udp_tokens + (now - self.udp_refill) * cfg.UDP_RATE_PER_SEC)
        self.udp_refill = now
        if self.udp_tokens >= 1.0:
            self.udp_tokens -= 1.0
            return True
        return False

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class RoomSender:
    """Envois de la partie d'un salon vers ses joueurs (expéditeur 0 = le serveur)."""

    def __init__(self, server, room):
        self.server, self.room = server, room

    def to(self, targets, obj, udp=False):
        r = self.room
        members = list(r.members.values()) if targets == "all" else [r.members[i] for i in targets if i in r.members]
        if not members:
            return
        if not udp:
            msg = dict(type="from", **{"from": 0}, d=obj)
            for m in members:
                m.send(msg)
            return
        self.server._send_udp(members, 0, obj)


class Room:
    def __init__(self, code, name, host, max_players, password, game, mode=coop_rules.DEFAULT_MODE):
        self.code = code
        self.name = name
        self.host = host                  # id de connexion de l'hôte
        self.members = {}                 # id -> Connection (ordre d'arrivée)
        self.max = max_players
        self.password = password
        self.game = game                  # version du jeu de l'hôte (les joueurs doivent avoir la même)
        self.mode = mode if mode in coop_rules.MODES else coop_rules.DEFAULT_MODE
        self.phase = "lobby"              # lobby | playing
        self.created = time.time()
        self.sim = None                   # partie (RoomGame), créée par le serveur

    def host_name(self):
        c = self.members.get(self.host)
        return c.name if c is not None else "?"

    def info(self):
        return dict(id=self.code, name=self.name, host_name=self.host_name(), players=len(self.members), max=self.max,
                    phase=self.phase, locked=bool(self.password), game=self.game, mode=self.mode)

    def roster(self):
        return [dict(id=c.id, name=c.name) for c in self.members.values()]


class RelayServer:
    def __init__(self, host=cfg.HOST, port=cfg.PORT):
        self.host, self.port = host, port
        self.lock = threading.RLock()
        self.conns = {}
        self.rooms = {}
        self.running = False
        self.tcp = None
        self.udp = None
        self.stats = dict(tcp_in=0, udp_in=0, udp_out=0, ticks=0, tick_ms=0.0)

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------
    def start(self, block=True):
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp.bind((self.host, self.port))
        self.tcp.listen(32)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind((self.host, self.port))
        self.udp.settimeout(0.5)
        if hasattr(socket, "SIO_UDP_CONNRESET"):
            try:
                self.udp.ioctl(socket.SIO_UDP_CONNRESET, False)
            except (OSError, ValueError):
                pass
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()
        log(f"L'ADRESSE — serveur démarré sur {self.host}:{self.port} (TCP+UDP), protocole {cfg.PROTOCOL_VERSION}, "
            f"{cfg.MAX_ROOMS} salons max, {cfg.MAX_ROOM_PLAYERS} joueurs max par salon, {coop_rules.TICK_RATE} ticks/s")
        for err in getattr(cfg, "CONFIG_ERRORS", []):
            log("configuration :", err)
        if block:
            self._tick_loop()
        else:
            threading.Thread(target=self._tick_loop, daemon=True).start()

    def stop(self):
        self.running = False
        time.sleep(0.3)
        with self.lock:
            conns = list(self.conns.values())
        for c in conns:
            c.close()
        for s in (self.tcp, self.udp):
            try:
                s.close()
            except Exception:
                pass

    def _tick_loop(self):
        """Une seule boucle fait avancer toutes les parties (pas un thread par salon)."""
        last = time.perf_counter()
        try:
            while self.running:
                t0 = time.perf_counter()
                dt = t0 - last
                last = t0
                with self.lock:
                    for r in list(self.rooms.values()):
                        if r.sim is None:
                            continue
                        r.sim.step(dt)
                        if r.phase == "lobby" and r.sim.phase != "lobby":
                            r.phase = "playing"           # la partie a commencé : plus de nouveaux joueurs
                            self._broadcast_room(r)
                        if r.sim.errors:
                            for e in r.sim.errors[:3]:
                                log(f"salon {r.code} : erreur de partie {e}")
                            r.sim.errors.clear()
                spent = time.perf_counter() - t0
                self.stats["ticks"] += 1
                self.stats["tick_ms"] = self.stats["tick_ms"] * 0.95 + spent * 1000 * 0.05
                sleep = coop_rules.TICK_DT - spent
                if sleep > 0:
                    time.sleep(sleep)
        except KeyboardInterrupt:
            log("arrêt du serveur")
        finally:
            self.stop()

    # ------------------------------------------------------------------
    # TCP
    # ------------------------------------------------------------------
    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self.tcp.accept()
            except OSError:
                break
            with self.lock:
                per_ip = sum(1 for c in self.conns.values() if c.addr[0] == addr[0])
                too_many = len(self.conns) >= cfg.MAX_CONNECTIONS or per_ip >= cfg.MAX_PER_IP
            if too_many:
                log("connexion refusée (limite atteinte) :", addr)
                try:
                    sock.sendall(b'{"type":"error","code":"busy","message":"Serveur occup\\u00e9, r\\u00e9essayez plus tard."}\n')
                    sock.close()
                except OSError:
                    pass
                continue
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(1.0)
            conn = Connection(sock, addr)
            with self.lock:
                self.conns[conn.id] = conn
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True).start()

    def _client_loop(self, conn):
        try:
            while self.running and conn.alive:
                try:
                    chunk = conn.sock.recv(16384)
                except socket.timeout:
                    if time.time() - conn.last_recv > cfg.CLIENT_TIMEOUT:
                        log(conn.addr, ": délai dépassé (aucun message)")
                        break
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                conn.last_recv = time.time()
                conn.buf += chunk
                if len(conn.buf) > cfg.MAX_LINE and b"\n" not in conn.buf:
                    log(conn.addr, ": message trop long, déconnexion")
                    break
                while b"\n" in conn.buf:
                    line, conn.buf = conn.buf.split(b"\n", 1)
                    if not line.strip() or len(line) > cfg.MAX_LINE:
                        continue
                    if not conn.allow():
                        if conn.flood_strikes > cfg.FLOOD_KICK:
                            log(conn.addr, ": flood, déconnexion")
                            conn.alive = False
                            break
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if not isinstance(msg, dict):
                        continue
                    self.stats["tcp_in"] += 1
                    with self.lock:
                        try:
                            self.handle(conn, msg)
                        except Exception as e:
                            log("erreur de traitement", msg.get("type"), ":", repr(e))
        finally:
            with self.lock:
                self._disconnect(conn)

    def _disconnect(self, conn):
        if self.conns.pop(conn.id, None) is None:
            return
        conn.close()
        if conn.room is not None:
            self._leave_room(conn, quiet=True)
        if conn.name:
            log(f"{conn.name} (#{conn.id}) s'est déconnecté")

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    def _err(self, conn, code, message):
        conn.send(dict(type="error", code=code, message=message))

    def handle(self, conn, msg):
        t = msg.get("type")
        if t == "ping":
            conn.send(dict(type="pong", t=msg.get("t"), rooms=len(self.rooms)))
            return
        if t == "hello":
            ver = str(msg.get("proto", ""))
            if ver != cfg.PROTOCOL_VERSION:
                self._err(conn, "proto", f"Version réseau incompatible (serveur {cfg.PROTOCOL_VERSION}). Mettez le jeu à jour.")
                return
            conn.name = clean_text(msg.get("name", ""), 16, "Joueur")
            conn.send(dict(type="hello_ok", id=conn.id, tok=conn.udp_token, motd=cfg.MOTD, proto=cfg.PROTOCOL_VERSION,
                           max_players=cfg.MAX_ROOM_PLAYERS))
            log(f"{conn.name} (#{conn.id}) connecté depuis {conn.addr[0]}")
            return
        if conn.name is None:
            self._err(conn, "hello", "Présentez-vous d'abord (hello).")
            return
        if t == "list":
            rooms = sorted(self.rooms.values(), key=lambda r: (r.phase != "lobby", -len(r.members), r.created))
            conn.send(dict(type="rooms", rooms=[r.info() for r in rooms]))
        elif t == "create":
            self._create(conn, msg)
        elif t == "join":
            self._join(conn, msg)
        elif t == "leave":
            if conn.room is not None:
                self._leave_room(conn)
            conn.send(dict(type="left"))
        elif t == "kick":
            r = conn.room
            target = self.conns.get(msg.get("id"))
            if r is not None and r.host == conn.id and target is not None and target.room is r and target is not conn:
                target.send(dict(type="room_closed", reason="Vous avez été exclu par l'hôte."))
                self._leave_room(target, quiet=True)
        elif t == "to":
            self._relay_tcp(conn, msg.get("to"), msg.get("d"))

    def _create(self, conn, msg):
        if conn.room is not None:
            self._leave_room(conn)
        if len(self.rooms) >= cfg.MAX_ROOMS:
            self._err(conn, "rooms_full", "Trop de parties en cours sur le serveur. Réessayez dans un instant.")
            return
        mine = sum(1 for r in self.rooms.values() if r.members.get(r.host) is not None and r.members[r.host].addr[0] == conn.addr[0])
        if mine >= cfg.MAX_ROOMS_PER_IP:
            self._err(conn, "rooms_ip", "Trop de parties créées depuis cette connexion.")
            return
        try:
            mx = int(msg.get("max", 4))
        except (TypeError, ValueError):
            mx = 4
        mx = max(1, min(cfg.MAX_ROOM_PLAYERS, mx))
        name = clean_text(msg.get("name", ""), 32, f"Partie de {conn.name}")
        password = str(msg.get("password", "") or "")[:32]
        game = clean_text(msg.get("game", ""), 20, "?")
        mode = str(msg.get("mode", coop_rules.DEFAULT_MODE) or coop_rules.DEFAULT_MODE).strip().lower()
        if mode not in coop_rules.MODES:
            mode = coop_rules.DEFAULT_MODE
        code = None
        while code is None or code in self.rooms:
            code = "".join(secrets.choice(ROOM_CHARS) for _ in range(5))
        r = Room(code, name, conn.id, mx, password, game, mode=mode)
        r.sim = RoomGame(RoomSender(self, r), mx, mode=mode)
        self.rooms[code] = r
        r.members[conn.id] = conn
        conn.room = r
        log(f"salon {code} « {name} » créé par {conn.name} ({mx} joueurs max, mode {mode}, jeu {game}{', privé' if password else ''})")
        self._broadcast_room(r)

    def _join(self, conn, msg):
        code = str(msg.get("room", "")).strip().upper()[:8]
        r = self.rooms.get(code)
        if r is None:
            self._err(conn, "gone", "Cette partie n'existe plus.")
            return
        if conn.room is r:
            self._broadcast_room(r)
            return
        if r.phase != "lobby":
            self._err(conn, "started", "La partie a déjà commencé.")
            return
        if len(r.members) >= r.max:
            self._err(conn, "full", f"Partie complète ({r.max} joueurs).")
            return
        if r.password and str(msg.get("password", "")) != r.password:
            self._err(conn, "password", "Mot de passe incorrect.")
            return
        game = clean_text(msg.get("game", ""), 20, "?")
        if game != r.game:
            self._err(conn, "version", f"Version du jeu différente (hôte : {r.game}, vous : {game}).")
            return
        if conn.room is not None:
            self._leave_room(conn)
        conn.name = clean_name(conn.name, {c.name.lower() for c in r.members.values()})
        r.members[conn.id] = conn
        conn.room = r
        log(f"{conn.name} a rejoint le salon {r.code}")
        self._broadcast_room(r)

    def _leave_room(self, conn, quiet=False):
        r = conn.room
        conn.room = None
        if r is None:
            return
        r.members.pop(conn.id, None)
        if not r.members:
            self.rooms.pop(r.code, None)
            log(f"salon {r.code} fermé (vide)")
            return
        if r.host == conn.id:
            # la partie tourne sur le serveur : elle continue, un autre joueur devient le créateur
            r.host = next(iter(r.members))
            log(f"salon {r.code} : {r.host_name()} devient le créateur")
        self._broadcast_room(r)

    def _broadcast_room(self, r):
        info, roster = r.info(), r.roster()
        if r.sim is not None:
            r.sim.sync_members(roster, r.host)
        for m in list(r.members.values()):
            m.send(dict(type="room", room=info, players=roster, host=r.host, you=m.id))

    # ------------------------------------------------------------------
    # Relais des paquets
    # ------------------------------------------------------------------
    def _targets(self, src, to):
        r = src.room
        if r is None:
            return []
        if to in ("all", "others", None):
            return [m for m in r.members.values() if m is not src]
        if to == "host":
            return []
        ids = to if isinstance(to, list) else [to]
        out = []
        for i in ids[:64]:
            m = r.members.get(i) if isinstance(i, int) else None
            if m is not None and m is not src:
                out.append(m)
        return out

    def _relay_tcp(self, src, to, d):
        if not isinstance(d, dict) or src.room is None:
            return
        sim = src.room.sim
        if to == "host":                     # message de jeu : traité par la partie du salon
            if sim is not None:
                sim.receive(src.id, d)
            return
        if sim is not None and d.get("type") == "move":
            sim.receive(src.id, d)           # la partie suit les positions (IA, anti-triche)
        out = dict(type="from", **{"from": src.id}, d=d)
        for m in self._targets(src, to):
            m.send(out)

    def _udp_loop(self):
        while self.running:
            try:
                data, addr = self.udp.recvfrom(4096)
            except socket.timeout:
                continue
            except ConnectionResetError:
                continue
            except OSError:
                if not self.running:
                    break
                time.sleep(0.05)
                continue
            if len(data) > 1400:
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            if not isinstance(msg, dict):
                continue
            self.stats["udp_in"] += 1
            with self.lock:
                try:
                    self._on_udp(msg, addr)
                except Exception as e:
                    log("erreur UDP :", repr(e))

    def _on_udp(self, msg, addr):
        src = self.conns.get(msg.get("i"))
        # anti-usurpation : jeton de session et même IP que la connexion TCP
        if src is None or msg.get("k") != src.udp_token or addr[0] != src.addr[0]:
            return
        src.udp_addr = addr
        if msg.get("h"):
            try:
                self.udp.sendto(b'{"ack":1}', addr)
            except OSError:
                pass
            return
        d = msg.get("d")
        if not isinstance(d, dict) or not src.allow_udp() or src.room is None:
            return
        sim = src.room.sim
        to = msg.get("to")
        if sim is not None and (to == "host" or d.get("type") == "move"):
            sim.receive(src.id, d)
        targets = self._targets(src, to)
        if targets:
            self._send_udp(targets, src.id, d)

    def _send_udp(self, targets, sender_id, d):
        """UDP vers chaque cible ; repli TCP (fréquence limitée) pour celles dont l'UDP est bloqué."""
        data = json.dumps({"f": sender_id, "d": d}, separators=(",", ":")).encode("utf-8")
        now = time.time()
        key = (sender_id, d.get("type"))
        for m in targets:
            if m.udp_addr is not None and now - m.last_recv < cfg.CLIENT_TIMEOUT:
                try:
                    self.udp.sendto(data, m.udp_addr)
                    self.stats["udp_out"] += 1
                    continue
                except OSError:
                    pass
            # UDP bloqué chez ce joueur : repli TCP, à fréquence limitée
            if now - m.fallback.get(key, 0.0) >= 1.0 / cfg.UDP_FALLBACK_HZ:
                m.fallback[key] = now
                m.send(dict(type="from", **{"from": sender_id}, d=d))


def console(server, stream=None):
    """Commandes d'administration (console Pterodactyl)."""
    for line in (stream if stream is not None else sys.stdin):
        cmd, _, arg = line.strip().partition(" ")
        cmd = cmd.lower()
        try:
            with server.lock:
                if cmd == "help":
                    log("commandes : list | rooms | kick <id> | close <salon> | say <texte> | stats | stop")
                elif cmd in ("list", "rooms"):
                    log(f"connexions={len(server.conns)} salons={len(server.rooms)}")
                    for r in server.rooms.values():
                        log(f"  [{r.code}] « {r.name} » {r.sim.phase if r.sim else r.phase} {len(r.members)}/{r.max} jeu {r.game}"
                            f"{' privé' if r.password else ''} — hôte {r.host_name()}")
                        for c in r.members.values():
                            log(f"      #{c.id} {c.name} {c.addr[0]} {'UDP' if c.udp_addr else 'TCP seul'}")
                    if cmd == "list":
                        idle = [c for c in server.conns.values() if c.room is None]
                        if idle:
                            log("  hors salon : " + ", ".join(f"#{c.id} {c.name or '?'}" for c in idle))
                elif cmd == "kick" and arg.isdigit():
                    c = server.conns.get(int(arg))
                    if c is not None:
                        server._err(c, "kicked", "Vous avez été exclu par l'administrateur.")
                        c.close()
                        log("exclu :", c.name)
                elif cmd == "close" and arg:
                    r = server.rooms.get(arg.strip().upper())
                    if r is not None:
                        for m in list(r.members.values()):
                            m.send(dict(type="room_closed", reason="Partie fermée par l'administrateur."))
                            m.room = None
                        server.rooms.pop(r.code, None)
                        log("salon fermé :", r.code)
                elif cmd == "say" and arg:
                    for c in list(server.conns.values()):
                        c.send(dict(type="notice", message=arg[:200]))
                elif cmd == "stats":
                    st = server.stats
                    log(f"messages TCP reçus {st['tcp_in']}, UDP reçus {st['udp_in']}, UDP envoyés {st['udp_out']}, "
                        f"ticks {st['ticks']}, tick moyen {st['tick_ms']:.2f} ms pour {len(server.rooms)} salon(s)")
                elif cmd in ("stop", "quit", "exit"):
                    server.running = False
                    return
                elif cmd:
                    log("commande inconnue (help)")
        except Exception as e:
            log("erreur console :", repr(e))


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(errors="replace")
        except Exception:
            pass
    port = cfg.PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            log("port invalide :", sys.argv[1])
            sys.exit(2)
    server = RelayServer(cfg.HOST, port)

    def _graceful(signum, frame):
        log(f"signal {signum} reçu : arrêt propre")
        try:
            with server.lock:
                for c in list(server.conns.values()):
                    c.send(dict(type="room_closed", reason="Le serveur redémarre. Reconnectez-vous dans un instant."))
        except Exception:
            pass
        server.running = False
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is not None:
            try:
                signal.signal(sig, _graceful)
            except (ValueError, OSError):
                pass
    if sys.stdin is not None and sys.stdin.isatty() or os.environ.get("LADRESSE_CONSOLE", "1") == "1":
        threading.Thread(target=console, args=(server,), daemon=True).start()
    try:
        server.start()
    except OSError as e:
        log("impossible de démarrer le serveur :", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
