"""Partie multijoueur exécutée SUR LE SERVEUR : une instance par salon.

Déroulé de la partie, IA du livreur, minuteries, messages d'assistance contradictoires, morts, victoire.
Le serveur appelle `step(dt)` pour tous les salons depuis une seule boucle à TICK_RATE ticks/s et
transmet les messages des joueurs via `receive()`. Les envois passent par `sender.to(cibles, message, udp)`.
"""
import math
import random
import time
import unicodedata

import coop_rules as cfg
from coop_state import GameState, EntityState, dist3


class PeerLink:
    """Lien vers un joueur : ps.conn.send(...) envoie à ce joueur seulement."""

    def __init__(self, game, pid):
        self.game, self.pid = game, pid

    def send(self, obj):
        self.game.sender.to([self.pid], obj)


class RoomGame:
    def __init__(self, sender, max_players=cfg.MAX_PLAYERS):
        self.sender = sender            # objet du serveur : sender.to(cibles, message, udp=False)
        self.state = GameState(max_players)
        self.owner = None               # créateur du salon (seul à pouvoir lancer)
        self.last_tcp_entity = 0.0
        self.errors = []

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def broadcast(self, obj, exclude=None, udp=False):
        targets = [pid for pid in self.state.players if pid != exclude]
        if targets:
            self.sender.to("all" if exclude is None else targets, obj, udp=udp)

    def broadcast_udp(self, obj, exclude=None):
        self.broadcast(obj, exclude, udp=True)

    def receive(self, pid, msg):
        if isinstance(msg, dict):
            try:
                self.handle(pid, msg)
            except Exception as e:          # message malformé : ignoré
                self.errors.append(repr(e))

    # ------------------------------------------------------------------
    # Membres du salon
    # ------------------------------------------------------------------
    def sync_members(self, roster, owner):
        """roster : [{id, name}] dans l'ordre d'arrivée."""
        s = self.state
        self.owner = owner
        ids = [p["id"] for p in roster]
        for pid in list(s.players):
            if pid not in ids:
                self._remove(pid)
        if s.phase == "lobby":
            for p in roster:
                if p["id"] not in s.players:
                    s.add_player(p["id"], p.get("name", "Joueur"), PeerLink(self, p["id"]))
        s.host = owner

    @property
    def phase(self):
        return self.state.phase

    def _remove(self, pid):
        s = self.state
        if pid not in s.players:
            return
        name = s.players[pid].name
        s.remove_player(pid)
        if s.phase not in ("lobby", "over"):
            self.broadcast(dict(type="player_left", id=pid, name=name))
            self._check_end()

    def step(self, dt):
        try:
            self._tick(min(0.25, dt))
        except Exception as e:
            self.errors.append(repr(e))

    # ------------------------------------------------------------------
    # Messages des joueurs
    # ------------------------------------------------------------------
    def handle(self, pid, msg):
        s = self.state
        ps = s.players.get(pid)
        if ps is None:
            return
        t = msg.get("type")
        if t == "start":
            if pid == self.owner and s.phase == "lobby":
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
            if isinstance(pos, list) and len(pos) == 3:
                r = max(0.0, min(15.0, float(msg.get("radius", 4.0))))
                s.noises.append((pos, r, s.t, ps.id))
                ps.noise = r
                ps.noise_t = s.t
        elif t == "death":
            self._kill(ps, str(msg.get("cause", "entity_contact"))[:32])

    def _on_move(self, ps, msg):
        # les positions sont diffusées directement de joueur à joueur ; l'hôte s'en sert pour l'IA et l'anti-triche
        pos = msg.get("pos")
        if not isinstance(pos, (list, tuple)) or len(pos) != 3:
            return
        try:
            pos = [float(v) for v in pos]
            rot = [float(v) for v in (msg.get("rot") or ps.rot)][:2]
        except (TypeError, ValueError):
            return
        if not all(math.isfinite(v) and abs(v) < cfg.WORLD_LIMIT for v in pos) or not all(math.isfinite(v) for v in rot):
            return
        now = time.time()
        dt = max(0.02, now - ps.last_move)
        if dist3(ps.pos, pos) > cfg.MAX_SPEED * dt + cfg.SPEED_TOLERANCE and ps.alive and self.state.phase != "lobby" \
                and now - getattr(ps, "_corrected", 0) > 1.0:
            ps._corrected = now
            ps.conn.send(dict(type="correct", pos=ps.pos))
            return
        ps.pos = pos
        ps.rot = rot
        ps.last_move = now

    def _on_interact(self, ps, msg):
        target = str(msg.get("target", ""))[:64]
        if target.startswith("door_"):
            did = target[5:]
            cur = self.state.doors.get(did, False)
            new = bool(msg.get("open", not cur))
            self.state.doors[did] = new
            self.broadcast(dict(type="door_state", door_id=did, open=new, by=ps.id))
        else:
            self.broadcast(dict(type="interact", target=target, by=ps.id), exclude=ps.id)

    def _on_chat(self, ps, msg):
        text = "".join(ch for ch in str(msg.get("message", "")) if unicodedata.category(ch)[0] != "C").strip()[:200]
        if not text:
            return
        if not ps.alive and random.random() < 0.3:
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
        s.entity = EntityState(kind, addr.startswith(cfg.NIGHTMARE_ADDRESS))
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
            ps.pos = [7.0 + (ps.slot - 1.5) * 0.4, 0.0, 0.8]
            ps.last_move = time.time()
        self.broadcast(dict(type="start", players=[p.info() for p in s.players.values()]))

    def _ev_cancel(self):
        self.broadcast(dict(type="game_event", event="order_cancelled"))
        self.state.schedule(cfg.CONTACT_DELAY - cfg.FIRST_CANCEL_DELAY, self._ev_contact)

    def _ev_contact(self):
        s = self.state
        s.schedule(90.0, self._ev_delivery_start)
        self.broadcast(dict(type="game_event", event="assistance_contact"))
        self.broadcast(dict(type="assistance_msg", pair_id=0, option="-",
                            text="Bonjour. Nous avons constaté un problème avec votre commande. Veuillez ne pas quitter les lieux."))

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
        for k in range(3):
            s.schedule(60 + k * 110 + random.uniform(0, 30), self._send_paranoia)

    def _send_pair(self, pair_id, idx):
        s = self.state
        for ps in s.players.values():
            opt, text = s.assistance_for(ps.id, pair_id)[idx]
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
        if remaining == 60:
            for _ in range(3):
                self.broadcast(dict(type="event", name="knock"))
        elif remaining == 30:
            ent = s.entity
            if ent is not None:
                ent.active = True
                ent.visible = True
                ent.speed_mult *= 0.6
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

    def _tick(self, dt):
        s = self.state
        if s.phase in ("lobby", "over"):
            return
        s.t += dt
        for (_, fn, args) in s.due():
            try:
                fn(*args)
            except Exception as e:
                self.errors.append(repr(e))
        s.noises = [n for n in s.noises if s.t - n[2] < 1.0]
        for ps in s.players.values():
            if s.t - ps.noise_t > 1.0:
                ps.noise = 0.0
        ent = s.entity
        if ent is not None and ent.active:
            killed = ent.update(dt, list(s.players.values()), s.noises)
            snap = ent.snapshot()
            snap["s"] = int(s.t * cfg.TICK_RATE)
            self.broadcast_udp(snap)
            if s.t - self.last_tcp_entity > 0.5:          # filet de sécurité si des paquets UDP se perdent
                self.last_tcp_entity = s.t
                self.broadcast(snap)
            if killed is not None and s.phase == "survival":
                self._kill(killed, "entity_contact")
        if s.phase == "survival" and s.t_release is not None and s.t - s.t_release > cfg.SURVIVAL_SECONDS * cfg.TIME_SCALE:
            if s.alive_players():
                s.phase = "over"
                s.winner = True
                self.broadcast(dict(type="game_over", result="win"))
