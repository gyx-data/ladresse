"""Serveur multijoueur principal de L'ADRESSE.

Tourne sur un serveur Pterodactyl (Python 3.11, aucune dépendance) :  ``python server.py``
IP publique : 5.180.34.43 | Port : 27303 (TCP pour les messages d'état, UDP pour les positions)

* 2 à 4 joueurs dans la même maison ;
* tick rate : 20 ticks/s ;
* IA de l'entité côté serveur, messages d'assistance distribués individuellement,
  mort / spectateur, validation des positions (anti-triche basique).

Protocole : JSON, un message par ligne (TCP) ou par datagramme (UDP).
"""
import json
import random
import socket
import sys
import threading
import time

import server_config as cfg
from game_state import GameState, EntityState, dist3


def log(*a):
    print(time.strftime("[%H:%M:%S]"), *a, flush=True)


class Connection:
    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.lock = threading.Lock()
        self.pid = None
        self.alive = True
        self.buf = b""

    def send(self, obj):
        if not self.alive:
            return False
        data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            with self.lock:
                self.sock.sendall(data)
            return True
        except OSError:
            self.alive = False
            return False

    def close(self):
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass


class GameServer:
    def __init__(self, host=cfg.HOST, port=cfg.PORT):
        self.host, self.port = host, port
        self.state = GameState()
        self.lock = threading.RLock()
        self.conns = []
        self.running = False
        self.tcp = None
        self.udp = None
        self.last_tcp_entity = 0.0
        self._last_tick = time.time()

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------
    def start(self):
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp.bind((self.host, self.port))
        self.tcp.listen(8)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind((self.host, self.port))
        self.udp.settimeout(0.5)
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()
        log(f"L'ADRESSE — serveur démarré sur {self.host}:{self.port} (TCP+UDP), {cfg.TICK_RATE} ticks/s")
        self._tick_loop()

    def stop(self):
        self.running = False
        for c in list(self.conns):
            c.close()
        for s in (self.tcp, self.udp):
            try:
                s.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Réseau
    # ------------------------------------------------------------------
    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self.tcp.accept()
            except OSError:
                break
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn = Connection(sock, addr)
            self.conns.append(conn)
            threading.Thread(target=self._client_loop, args=(conn,), daemon=True).start()

    def _client_loop(self, conn):
        log("connexion de", conn.addr)
        try:
            while self.running and conn.alive:
                try:
                    chunk = conn.sock.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                conn.buf += chunk
                while b"\n" in conn.buf:
                    line, conn.buf = conn.buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except ValueError:
                        continue
                    with self.lock:
                        self.handle(conn, msg)
        finally:
            with self.lock:
                self._disconnect(conn)

    def _udp_loop(self):
        while self.running:
            try:
                data, addr = self.udp.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            with self.lock:
                pid = msg.get("id")
                ps = self.state.players.get(pid)
                if ps is None:
                    continue
                ps.udp_addr = addr
                if msg.get("type") == "move":
                    self._on_move(ps, msg)

    def _disconnect(self, conn):
        if conn in self.conns:
            self.conns.remove(conn)
        conn.close()
        if conn.pid is not None and conn.pid in self.state.players:
            name = self.state.players[conn.pid].name
            self.state.remove_player(conn.pid)
            log(f"{name} s'est déconnecté")
            self.broadcast(self._lobby_msg())
            self._check_end()
            if not self.state.players:
                self.state = GameState()      # salle vide : on remet la partie à zéro

    def broadcast(self, obj, exclude=None):
        for ps in list(self.state.players.values()):
            if ps.id != exclude:
                ps.conn.send(obj)

    def broadcast_udp(self, obj, exclude=None):
        data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        for ps in list(self.state.players.values()):
            if ps.id == exclude:
                continue
            if ps.udp_addr is not None:
                try:
                    self.udp.sendto(data, ps.udp_addr)
                except OSError:
                    pass

    def _lobby_msg(self):
        s = self.state
        return dict(type="lobby", players=[p.info() for p in s.players.values()], host=s.host, phase=s.phase)

    # ------------------------------------------------------------------
    # Messages clients
    # ------------------------------------------------------------------
    def handle(self, conn, msg):
        s = self.state
        t = msg.get("type")
        if t == "connect":
            if conn.pid is not None:
                return
            if s.phase != "lobby":
                conn.send(dict(type="error", message="Partie déjà en cours."))
                return
            ps = s.add_player(str(msg.get("name", "Joueur")), conn)
            if ps is None:
                conn.send(dict(type="error", message="Serveur plein (4 joueurs maximum)."))
                return
            conn.pid = ps.id
            log(f"{ps.name} (id {ps.id}) a rejoint le lobby")
            conn.send(dict(type="welcome", id=ps.id, players=[p.info() for p in s.players.values()], host=s.host))
            self.broadcast(self._lobby_msg())
            return
        ps = s.players.get(conn.pid)
        if ps is None:
            return
        if t == "start":
            if ps.id == s.host and s.phase == "lobby" and len(s.players) >= 1:
                self._start_game()
        elif t == "move":
            self._on_move(ps, msg)
        elif t == "interact":
            self._on_interact(ps, msg)
        elif t == "chat":
            self._on_chat(ps, msg)
        elif t == "order":
            self._on_order(ps, msg)
        elif t == "choice":
            ps.choices[msg.get("pair_id")] = msg.get("choice")
        elif t == "noise":
            pos = msg.get("pos", ps.pos)
            s.noises.append((pos, float(msg.get("radius", 4.0)), s.t, ps.id))
            ps.noise = min(15.0, float(msg.get("radius", 4.0)))
            ps.noise_t = s.t
        elif t == "death":
            self._kill(ps, msg.get("cause", "entity_contact"))
        elif t == "ping":
            conn.send(dict(type="pong", t=msg.get("t")))

    def _on_move(self, ps, msg):
        pos = msg.get("pos")
        if not pos or len(pos) != 3:
            return
        now = time.time()
        dt = max(0.02, now - ps.last_move)
        d = dist3(ps.pos, pos)
        # anti-triche basique : vitesse plausible
        if d > cfg.MAX_SPEED * dt + cfg.SPEED_TOLERANCE and ps.alive and self.state.phase != "lobby":
            ps.conn.send(dict(type="correct", pos=ps.pos))
            return
        ps.pos = [float(pos[0]), float(pos[1]), float(pos[2])]
        ps.rot = msg.get("rot", ps.rot)
        ps.last_move = now
        out = dict(type="player_move", id=ps.id, pos=[round(v, 2) for v in ps.pos], rot=[round(v, 1) for v in ps.rot])
        self.broadcast_udp(out, exclude=ps.id)

    def _on_interact(self, ps, msg):
        target = str(msg.get("target", ""))
        if target.startswith("door_"):
            did = target[5:]
            cur = self.state.doors.get(did, False)
            new = bool(msg.get("open", not cur))
            self.state.doors[did] = new
            self.broadcast(dict(type="door_state", door_id=did, open=new, by=ps.id))
        else:
            self.broadcast(dict(type="interact", target=target, by=ps.id), exclude=ps.id)

    def _on_chat(self, ps, msg):
        text = str(msg.get("message", ""))[:200]
        if not text:
            return
        if not ps.alive and random.random() < 0.3:
            # l'entité intercepte et modifie les messages des morts
            words = text.split()
            random.shuffle(words)
            text = " ".join(words) + " ... il est derrière toi"
        self.broadcast(dict(type="chat", id=ps.id, name=ps.name, message=text, dead=not ps.alive))

    def _on_order(self, ps, msg):
        s = self.state
        meal = str(msg.get("meal", ""))
        addr = str(msg.get("address", "")).lower().strip()
        if s.phase != "explore" or meal not in cfg.MEALS:
            return
        if not any(addr.startswith(a) for a in cfg.ADDRESSES_OK):
            ps.conn.send(dict(type="order_result", ok=False, message="Adresse non reconnue"))
            return
        s.meal = meal
        s.address = addr
        s.phase = "ordered"
        kind = cfg.MEALS[meal]
        nightmare = addr.startswith(cfg.NIGHTMARE_ADDRESS)
        s.entity = EntityState(kind, nightmare)
        log(f"{ps.name} a commandé {meal} -> entité {kind}{' (cauchemar)' if nightmare else ''}")
        self.broadcast(dict(type="order_result", ok=True, meal=meal, entity=kind, by=ps.id))
        s.schedule(cfg.FIRST_CANCEL_DELAY, self._ev_cancel)

    # ------------------------------------------------------------------
    # Déroulé de la partie
    # ------------------------------------------------------------------
    def _start_game(self):
        s = self.state
        s.phase = "explore"
        s.t = 0.0
        for ps in s.players.values():
            ps.alive = True
            ps.pos = [7.0 + (ps.id - 2.5) * 0.4, 0.0, 0.8]
        log("la partie commence")
        self.broadcast(dict(type="start", players=[p.info() for p in s.players.values()]))

    def _ev_cancel(self):
        self.broadcast(dict(type="game_event", event="order_cancelled"))
        self.state.schedule(cfg.CONTACT_DELAY - cfg.FIRST_CANCEL_DELAY, self._ev_contact)

    def _ev_contact(self):
        s = self.state
        s.schedule(90.0, self._ev_delivery_start)
        self.broadcast(dict(type="game_event", event="assistance_contact"))
        for ps in s.players.values():
            ps.conn.send(dict(type="assistance_msg", text="Bonjour. Nous avons constaté un problème avec votre commande. Veuillez ne pas quitter les lieux.", pair_id=0, option="-"))

    def _ev_delivery_start(self):
        s = self.state
        s.phase = "countdown"
        s.t_delivery = s.t
        self.broadcast(dict(type="game_event", event="delivery_started", countdown=int(cfg.DELIVERY_SECONDS)))
        for pid_, (ta, tb) in cfg.PAIR_SCHEDULE.items():
            s.schedule(ta, self._send_pair, pid_, 0)
            s.schedule(tb, self._send_pair, pid_, 1)
        for remaining in (120, 60, 30, 0):
            s.schedule(cfg.DELIVERY_SECONDS - remaining, self._ev_countdown, remaining)
        # messages de paranoïa individuels
        for k in range(3):
            s.schedule(60 + k * 110 + random.uniform(0, 30), self._send_paranoia)

    def _send_pair(self, pair_id, idx):
        s = self.state
        for ps in s.players.values():
            order = s.assistance_for(ps.id, pair_id)
            opt, text = order[idx]
            ps.conn.send(dict(type="assistance_msg", text=text, pair_id=pair_id, option=opt))

    def _send_paranoia(self):
        s = self.state
        for ps in s.players.values():
            text = s.paranoia_for(ps.id)
            if text:
                ps.conn.send(dict(type="assistance_msg", text=text, pair_id=0, option="-"))

    def _ev_countdown(self, remaining):
        s = self.state
        self.broadcast(dict(type="game_event", event="delivery_arriving", countdown=remaining))
        if remaining == 120:
            pass
        elif remaining == 60:
            for _ in range(3):
                self.broadcast(dict(type="event", name="knock"))
        elif remaining == 30:
            ent = s.entity
            if ent is not None:
                ent.active = True
                ent.visible = True
                ent.speed_mult *= 0.6          # arrivée lente
        elif remaining == 0:
            ent = s.entity
            if ent is not None:
                ent.speed_mult /= 0.6
            s.phase = "survival"
            s.t_release = s.t
            self.broadcast(dict(type="game_event", event="delivery_done", countdown=0))
            for pid_, (ta, tb) in cfg.PAIR_SCHEDULE_AFTER_RELEASE.items():
                s.schedule(ta, self._send_pair, pid_, 0)
                s.schedule(tb, self._send_pair, pid_, 1)

    def _kill(self, ps, cause):
        if not ps.alive:
            return
        ps.alive = False
        log(f"{ps.name} est mort ({cause})")
        self.broadcast(dict(type="player_death", id=ps.id, cause=cause))
        self.broadcast(dict(type="event", name="jumpscare", target=ps.id))
        self._check_end()

    def _check_end(self):
        s = self.state
        if s.phase in ("lobby", "over") or not s.players:
            return
        if s.phase in ("survival", "countdown") and not s.alive_players():
            s.phase = "over"
            s.winner = False
            self.broadcast(dict(type="game_over", result="lose"))
            log("tous les joueurs sont morts")

    # ------------------------------------------------------------------
    # Boucle de tick
    # ------------------------------------------------------------------
    def _tick_loop(self):
        try:
            while self.running:
                t0 = time.time()
                dt = min(0.25, t0 - self._last_tick)
                self._last_tick = t0
                with self.lock:
                    self._tick(dt)
                sleep = cfg.TICK_DT - (time.time() - t0)
                if sleep > 0:
                    time.sleep(sleep)
        except KeyboardInterrupt:
            log("arrêt du serveur")
        finally:
            self.stop()

    def _tick(self, dt):
        s = self.state
        if s.phase in ("lobby", "over"):
            return
        s.t += dt
        for (_, fn, args) in s.due():
            try:
                fn(*args)
            except Exception as e:                    # un événement raté ne doit pas tuer le serveur
                log("erreur d'événement :", e)
        s.noises = [n for n in s.noises if s.t - n[2] < 1.0]
        for ps in s.players.values():
            if s.t - ps.noise_t > 1.0:
                ps.noise = 0.0
        ent = s.entity
        if ent is not None and ent.active:
            if s.phase == "survival" and s.t_release is not None and ent.state == "patrol" and not ent.path:
                pass
            killed = ent.update(dt, list(s.players.values()), s.noises)
            snap = ent.snapshot()
            self.broadcast_udp(snap)
            if s.t - self.last_tcp_entity > 0.5:
                self.last_tcp_entity = s.t
                self.broadcast(snap)
            if killed is not None and s.phase == "survival":
                self._kill(killed, "entity_contact")
        # victoire : au moins un joueur survit jusqu'à la fin du délai de survie
        if s.phase == "survival" and s.t_release is not None and s.t - s.t_release > cfg.SURVIVAL_SECONDS * cfg.TIME_SCALE:
            if s.alive_players():
                s.phase = "over"
                s.winner = True
                self.broadcast(dict(type="game_over", result="win"))
                log("victoire : au moins un joueur a survécu")


def main():
    host = cfg.HOST
    port = cfg.PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = GameServer(host, port)
    try:
        server.start()
    except OSError as e:
        log("impossible de démarrer le serveur :", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
