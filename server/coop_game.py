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
from coop_state import GameState, EntityState, dist3, nearest_waypoint


class PeerLink:
    """Lien vers un joueur : ps.conn.send(...) envoie à ce joueur seulement."""

    def __init__(self, game, pid):
        self.game, self.pid = game, pid

    def send(self, obj):
        self.game.sender.to([self.pid], obj)


class RoomGame:
    def __init__(self, sender, max_players=cfg.MAX_PLAYERS, mode=cfg.DEFAULT_MODE):
        self.sender = sender            # objet du serveur : sender.to(cibles, message, udp=False)
        self.state = GameState(max_players, mode=mode)
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
            self._check_all_inside()          # le dernier joueur resté dehors est parti : la nuit peut commencer

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
        elif t == "enter_house":
            self._on_enter_house(ps)
        elif t == "door_opened":
            if msg.get("door", "entree") in ("entree", "front", "porte"):
                self._kill(ps, "porte")
        elif t == "code_given":
            ps.code_given = True
            if s.phase == "survival":
                s.schedule(3.0, self._kill, ps, "code")
        elif t == "quest_done":
            self._on_quest_done(ps, msg)

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
        if self.state.phase not in ("lobby", "outside"):
            ps.inside = (-0.5 <= pos[0] <= 16.5 and -0.5 <= pos[2] <= 12.5)

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
        s.entity = EntityState(kind, addr.startswith(cfg.NIGHTMARE_ADDRESS) or s.mode == "cauchemar")
        self.broadcast(dict(type="order_result", ok=True, meal=meal, entity=kind, by=ps.id))
        s.schedule(cfg.FIRST_CANCEL_DELAY, self._ev_cancel)

    def _on_quest_done(self, ps, msg):
        s = self.state
        if s.phase in ("lobby", "over"):
            return
        q = str(msg.get("quest", "")).strip()
        if q not in cfg.QUEST_IDS:
            return
        s.quests_done.add(q)
        self.broadcast(dict(type="quest_done", quest=q, by=ps.id, done=sorted(s.quests_done)), exclude=ps.id)
        if all(qid in s.quests_done for qid in cfg.QUEST_IDS):
            alive_ids = [p.id for p in s.alive_players()]
            s.phase = "over"
            s.winner = True
            if alive_ids:
                self.sender.to(alive_ids, dict(type="win", ending="adresse_retiree"))

    # ------------------------------------------------------------------
    # Déroulé de la partie
    # ------------------------------------------------------------------
    def _start_game(self):
        s = self.state
        outside = cfg.OUTSIDE_START
        s.phase = "outside" if outside else "explore"
        s.t = 0.0
        s.quests_done.clear()
        s.traitre = random.choice(list(s.players)) if (s.mode == "traitre" and s.players) else None
        ox, oy, oz = cfg.OUTSIDE_SPAWN
        for ps in s.players.values():
            ps.alive = True
            ps.inside = not outside
            ps.code_given = False
            ps.pos = [ox + (ps.slot - 1.5) * 0.8, oy, oz] if outside else [7.0 + (ps.slot - 1.5) * 0.4, 0.0, 0.8]
            ps.last_move = time.time()
        self.broadcast(dict(type="mode", mode=s.mode, traitre=s.traitre))
        self.broadcast(dict(type="start", players=[p.info() for p in s.players.values()], outside=outside,
                            spawn=[list(p.pos) for p in s.players.values()], mode=s.mode, traitre=s.traitre))
        if s.mode == "traitre" and s.traitre is not None:
            s.schedule(random.uniform(60.0, 90.0), self._send_traitor_order)

    def _send_traitor_order(self):
        s = self.state
        if s.phase in ("lobby", "over") or s.mode != "traitre":
            return
        ps = s.players.get(s.traitre)
        if ps is not None and ps.alive:
            idx = getattr(s, "_ordre_idx", 0)
            text = cfg.TRAITOR_ORDERS[idx % len(cfg.TRAITOR_ORDERS)]
            s._ordre_idx = idx + 1
            ps.conn.send(dict(type="ordre", text=text))
        s.schedule(random.uniform(60.0, 90.0), self._send_traitor_order)

    def _on_enter_house(self, ps):
        """Quartier partagé : un joueur franchit la porte. La nuit commence quand tous les vivants sont dedans."""
        s = self.state
        if s.phase != "outside" or ps.inside:
            return
        ps.inside = True
        if ps.pos[2] < 0.0:
            ps.pos = [7.0 + (ps.slot - 1.5) * 0.4, 0.0, 1.0]
            ps.last_move = time.time()
        self._check_all_inside()

    def _check_all_inside(self):
        s = self.state
        if s.phase != "outside":
            return
        alive = s.alive_players()
        inside = [p for p in alive if p.inside]
        self.broadcast(dict(type="game_event", event="player_inside", inside=len(inside), total=len(alive),
                            ids=[p.id for p in inside]))
        if alive and len(inside) == len(alive):
            s.phase = "explore"
            s.t = 0.0
            s.pending.clear()
            if s.mode == "traitre" and s.traitre is not None:
                s.schedule(random.uniform(60.0, 90.0), self._send_traitor_order)
            self.broadcast(dict(type="game_event", event="night_start"))

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

    def _is_outside(self, ps):
        x, _, z = ps.pos
        return (not ps.inside) or x < -0.5 or x > 16.5 or z < -0.5 or z > 12.5

    def _same_room(self, a, b):
        if abs(a.pos[1] - b.pos[1]) > 1.8:
            return False
        return nearest_waypoint(a.pos) == nearest_waypoint(b.pos) or dist3(a.pos, b.pos) <= 4.5

    def _ev_countdown(self, remaining):
        s = self.state
        if s.phase == "over":
            return
        self.broadcast(dict(type="game_event", event="delivery_arriving", countdown=remaining))
        # le joueur qui a donné le code du portail est emporté au prochain passage du livreur
        for p in list(s.alive_players()):
            if getattr(p, "code_given", False):
                self._kill(p, "code")
        if s.phase == "over":
            return
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
            if not all(qid in s.quests_done for qid in cfg.QUEST_IDS):
                alive = s.alive_players()
                outside_victims = [p for p in alive if self._is_outside(p)]
                inside_alive = [p for p in alive if not self._is_outside(p)]
                alone_victims = []
                if len(inside_alive) > 1:
                    for p in inside_alive:
                        if not any(self._same_room(p, q) for q in inside_alive if q.id != p.id):
                            alone_victims.append(p)
                for p in outside_victims + alone_victims:
                    if p.alive and s.phase != "over":
                        self._kill(p, "dehors" if p in outside_victims else "isole")
            if s.phase == "over" or not s.alive_players():
                return
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
        if not ps.alive or self.state.phase == "over":
            return
        ps.alive = False
        self.broadcast(dict(type="player_death", id=ps.id, cause=cause))
        self.broadcast(dict(type="event", name="jumpscare", target=ps.id))
        self._check_end(killed=ps)

    def _check_end(self, killed=None):
        s = self.state
        if s.phase in ("lobby", "over") or not s.players:
            return
        alive = s.alive_players()
        if killed is not None:
            if s.mode == "solo_survie" and alive:
                s.phase = "over"
                s.winner = True
                self.sender.to([p.id for p in alive], dict(type="win", ending="solo_survie"))
                self.sender.to([p.id for p in s.players.values() if not p.alive], dict(type="game_over", result="lose"))
                return
            if s.mode == "traitre" and s.traitre is not None and killed.id != s.traitre:
                s.phase = "over"
                s.winner = "traitre"
                if s.traitre in s.players:
                    self.sender.to([s.traitre], dict(type="win", ending="traitre"))
                others = [pid for pid in s.players if pid != s.traitre]
                if others:
                    self.sender.to(others, dict(type="game_over", result="lose"))
                return
        if not alive:
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
