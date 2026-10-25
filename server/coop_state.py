"""État d'une partie multijoueur, tenu par le SERVEUR : joueurs, portes,
entité (IA simplifiée sur graphe de points de passage), messages d'assistance individuels.

Pur Python, sans Ursina : une instance par salon, sur le serveur (coop_game.py).
"""
import heapq
import math
import random
import time

import coop_rules as cfg

# ---------------------------------------------------------------------------
# Graphe de navigation simplifié de la maison (niveau, position)
# ---------------------------------------------------------------------------
WAYPOINTS = {
    # rez-de-chaussée
    "entree": (7.0, 0.0, 1.0), "couloir_s": (7.0, 0.0, 4.0), "couloir_n": (7.0, 0.0, 8.0), "couloir_fond": (7.0, 0.0, 10.8),
    "salon": (3.0, 0.0, 3.0), "cuisine": (3.0, 0.0, 9.0), "bureau": (12.0, 0.0, 2.3), "hall": (10.5, 0.0, 6.5),
    "pied_escalier": (9.1, 0.0, 4.6), "hall_n": (10.0, 0.0, 10.5), "sdb0": (14.0, 0.0, 6.5), "buanderie": (14.0, 0.0, 10.2),
    # premier étage
    "c1_s": (7.0, 3.0, 2.0), "c1_m": (7.0, 3.0, 6.0), "c1_n": (7.0, 3.0, 10.0), "master": (3.0, 3.0, 3.0), "amis": (3.0, 3.0, 8.0),
    "placard": (3.0, 3.0, 11.0), "palier": (9.5, 3.0, 10.5), "tete_escalier": (9.1, 3.0, 9.8), "branche": (14.0, 3.0, 5.5),
    "sdb1": (14.0, 3.0, 9.5), "pied_grenier": (10.4, 3.0, 10.4),
    # grenier
    "g_haut": (10.4, 6.0, 5.0), "g_centre": (8.0, 6.0, 4.0), "g_ouest": (3.0, 6.0, 6.0), "g_est": (13.0, 6.0, 6.5), "g_nord": (8.0, 6.0, 9.0),
}

EDGES = [
    ("entree", "couloir_s"), ("couloir_s", "couloir_n"), ("couloir_n", "couloir_fond"), ("couloir_s", "salon"), ("couloir_n", "cuisine"),
    ("couloir_s", "bureau"), ("couloir_s", "pied_escalier"), ("couloir_n", "hall"), ("pied_escalier", "hall"), ("hall", "hall_n"),
    ("hall", "sdb0"), ("hall_n", "buanderie"), ("salon", "cuisine"), ("pied_escalier", "tete_escalier"),
    ("tete_escalier", "palier"), ("palier", "c1_n"), ("c1_n", "c1_m"), ("c1_m", "c1_s"), ("c1_s", "master"), ("c1_m", "amis"),
    ("c1_n", "placard"), ("palier", "branche"), ("branche", "sdb1"), ("palier", "pied_grenier"), ("pied_grenier", "g_haut"),
    ("g_haut", "g_centre"), ("g_centre", "g_ouest"), ("g_centre", "g_est"), ("g_centre", "g_nord"),
]

ADJ = {}
for a, b in EDGES:
    ADJ.setdefault(a, []).append(b)
    ADJ.setdefault(b, []).append(a)


def dist3(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def nearest_waypoint(pos):
    best, bd = None, 1e9
    for name, p in WAYPOINTS.items():
        d = math.hypot(p[0] - pos[0], p[2] - pos[2]) + abs(p[1] - pos[1]) * 5.0
        if d < bd:
            best, bd = name, d
    return best


def find_path(start, goal):
    """Dijkstra sur le graphe des points de passage. Retourne une liste de noms."""
    if start == goal:
        return [start]
    h = [(0.0, start)]
    came, g = {}, {start: 0.0}
    while h:
        d, cur = heapq.heappop(h)
        if cur == goal:
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            return path[::-1]
        for n in ADJ.get(cur, ()):
            nd = d + dist3(WAYPOINTS[cur], WAYPOINTS[n])
            if nd < g.get(n, 1e9):
                g[n] = nd
                came[n] = cur
                heapq.heappush(h, (nd, n))
    return [start]


class PlayerState:
    def __init__(self, pid, name, conn, slot=0):
        self.id = pid
        self.slot = slot              # rang d'arrivée : couleur, ordre des messages d'assistance
        self.name = name
        self.conn = conn
        self.pos = [7.0, 0.0, 0.8]
        self.rot = [0.0, 0.0]
        self.alive = True
        self.last_move = time.time()
        self.udp_addr = None
        self.color = cfg.JACKET_COLORS[slot % len(cfg.JACKET_COLORS)]
        self.noise = 0.0
        self.noise_t = 0.0
        self.choices = {}
        self.messages_sent = 0
        self.ready = False

    def info(self):
        return dict(id=self.id, name=self.name, color=list(self.color), alive=self.alive)


class EntityState:
    """Le Livreur côté serveur : patrouille, alerte, poursuite sur graphe de points de passage."""

    SPEEDS = {
        "silencieux": (0.9, 1.3, 1.7), "rampant": (1.8, 2.8, 5.0), "multiple": (1.2, 1.9, 3.3), "imposteur": (1.1, 1.6, 2.4),
    }

    def __init__(self, kind, nightmare=False):
        self.kind = kind
        self.nightmare = nightmare
        self.pos = list(WAYPOINTS["entree"])
        self.yaw = 0.0
        self.state = "patrol"
        self.active = False
        self.visible = False
        self.path = []
        self.target_pid = None
        self.speed_mult = 1.3 if nightmare else 1.0
        self.detect_mult = 1.4 if nightmare else 1.0
        self.dwell = 0.0
        self.tp_t = random.uniform(6, 10)
        self.search_t = 0.0
        self.ghosts = []
        self.ghost_t = 3.0
        self.last_wp = "entree"

    def speed(self):
        p, a, c = self.SPEEDS.get(self.kind, (1.1, 1.6, 2.4))
        base = {"patrol": p, "alert": a, "chase": c, "search": a * 0.9}.get(self.state, p)
        return base * self.speed_mult

    def update(self, dt, players, noises):
        if not self.active:
            return None
        alive = [p for p in players if p.alive]
        if not alive:
            return None
        killed = None
        # cible : joueur le plus bruyant ou le plus isolé
        target = self._pick_target(alive)
        self.target_pid = target.id if target else None
        # détection
        for p in alive:
            d = dist3(self.pos, p.pos)
            same_level = abs(self.pos[1] - p.pos[1]) < 2.2
            if same_level and d < 2.2 * self.detect_mult:
                self._to_chase(p)
            elif same_level and d < 9.0 * self.detect_mult and self._line_of_sight(p):
                self._to_chase(p)
        for (npos, radius, t, who) in noises:
            d = math.hypot(npos[0] - self.pos[0], npos[2] - self.pos[2])
            if d < radius * self.detect_mult and self.state not in ("chase",) and self.kind != "silencieux":
                self.state = "alert"
                self.path = find_path(nearest_waypoint(self.pos), nearest_waypoint(npos))
        # comportement par état
        if self.state == "chase" and target is not None:
            goal = nearest_waypoint(target.pos)
            if not self.path or self.path[-1] != goal:
                self.path = find_path(nearest_waypoint(self.pos), goal)
            self._follow(dt, target)
            if self._lost(target):
                self.state = "search"
                self.search_t = 25.0
        elif self.state in ("alert", "search"):
            self.search_t -= dt
            self._follow(dt, None)
            if not self.path:
                self.state = "patrol" if self.search_t <= 0 else "search"
                if self.state == "search" and random.random() < 0.02:
                    self._new_patrol()
        else:
            if self.dwell > 0:
                self.dwell -= dt
            else:
                if not self.path:
                    self._new_patrol()
                self._follow(dt, None)
        # téléportation du Silencieux
        if self.kind == "silencieux" and target is not None:
            self.tp_t -= dt
            if self.tp_t <= 0:
                self.tp_t = random.uniform(5, 9)
                self._teleport_toward(target)
        # clones du Multiple
        if self.kind == "multiple":
            self.ghost_t -= dt
            if self.ghost_t <= 0:
                self.ghost_t = random.uniform(5, 9)
                self.ghosts = []
                for _ in range(2):
                    wp = random.choice(list(WAYPOINTS))
                    p = WAYPOINTS[wp]
                    if target is not None and abs(p[1] - target.pos[1]) < 1.0:
                        self.ghosts.append(list(p))
        # contact mortel
        for p in alive:
            if abs(self.pos[1] - p.pos[1]) < 1.6 and math.hypot(self.pos[0] - p.pos[0], self.pos[2] - p.pos[2]) < 1.05 and self.state == "chase":
                killed = p
                break
        return killed

    # --- aides ------------------------------------------------------------
    def _pick_target(self, alive):
        best, bs = None, -1.0
        for p in alive:
            score = p.noise * 2.0
            others = [q for q in alive if q is not p]
            if others:
                score += min(dist3(p.pos, q.pos) for q in others) * 0.3
            score -= dist3(self.pos, p.pos) * 0.1
            if best is None or score > bs:
                best, bs = p, score
        return best

    def _line_of_sight(self, p):
        a, b = nearest_waypoint(self.pos), nearest_waypoint(p.pos)
        return a == b or b in ADJ.get(a, ())

    def _to_chase(self, p):
        if self.state != "chase":
            self.state = "chase"
        self.target_pid = p.id

    def _lost(self, p):
        if abs(self.pos[1] - p.pos[1]) > 2.5 and dist3(self.pos, p.pos) > 10:
            return True
        return dist3(self.pos, p.pos) > 16.0

    def _new_patrol(self):
        names = [n for n in WAYPOINTS]
        goal = random.choice(names)
        self.path = find_path(nearest_waypoint(self.pos), goal)
        self.dwell = random.uniform(1.5, 5.0)

    def _follow(self, dt, chase_target):
        if not self.path:
            return
        step = self.speed() * dt
        while self.path and step > 0:
            wp = WAYPOINTS[self.path[0]]
            dx, dy, dz = wp[0] - self.pos[0], wp[1] - self.pos[1], wp[2] - self.pos[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d <= step:
                self.pos = list(wp)
                step -= d
                self.last_wp = self.path.pop(0)
            else:
                self.pos = [self.pos[0] + dx / d * step, self.pos[1] + dy / d * step, self.pos[2] + dz / d * step]
                self.yaw = math.degrees(math.atan2(dx, dz))
                step = 0
        if chase_target is not None and not self.path:
            # dernier mètre : droit sur le joueur
            dx, dz = chase_target.pos[0] - self.pos[0], chase_target.pos[2] - self.pos[2]
            d = math.hypot(dx, dz)
            if d > 0.05 and abs(chase_target.pos[1] - self.pos[1]) < 1.8:
                s = min(d, self.speed() * dt)
                self.pos[0] += dx / d * s
                self.pos[2] += dz / d * s
                self.yaw = math.degrees(math.atan2(dx, dz))

    def _teleport_toward(self, target):
        goal = nearest_waypoint(target.pos)
        path = find_path(nearest_waypoint(self.pos), goal)
        if len(path) > 2:
            wp = WAYPOINTS[path[len(path) // 2]]
            self.pos = list(wp)
            self.path = path[len(path) // 2:]

    def snapshot(self):
        return dict(type="entity_update", pos=[round(v, 2) for v in self.pos], yaw=round(self.yaw, 1), state=self.state,
                    kind=self.kind, visible=self.visible, speed=round(self.speed(), 2) if self.path else 0.0,
                    ghosts=[[round(v, 2) for v in g] for g in self.ghosts])


class GameState:
    """Partie en cours : lobby → exploration → commande → attente → survie."""

    def __init__(self, max_players=None):
        self.max_players = max_players or cfg.MAX_PLAYERS
        self.players = {}
        self.host = None
        self.phase = "lobby"     # lobby | explore | ordered | countdown | survival | over
        self.t = 0.0
        self.doors = {}
        self.entity = None
        self.meal = None
        self.address = None
        self.timeline = []        # (temps, fonction(args))
        self.noises = []
        self.t_release = None
        self.pending = []
        self.countdown_started = False
        self.winner = None

    # --- joueurs --------------------------------------------------------
    def add_player(self, pid, name, conn):
        """pid = identifiant attribué par le relais (unique dans le salon)."""
        if pid in self.players:
            return self.players[pid]
        if len(self.players) >= self.max_players:
            return None
        used = {p.slot for p in self.players.values()}
        slot = next(i for i in range(len(self.players) + 1) if i not in used)
        ps = PlayerState(pid, name[:16] or "Joueur", conn, slot)
        self.players[pid] = ps
        if self.host is None:
            self.host = pid
        return ps

    def remove_player(self, pid):
        self.players.pop(pid, None)
        if self.host == pid:
            self.host = next(iter(self.players), None)

    def alive_players(self):
        return [p for p in self.players.values() if p.alive]

    # --- programmation ---------------------------------------------------
    def schedule(self, delay, fn, *args):
        self.pending.append((self.t + delay * cfg.TIME_SCALE, fn, args))

    def due(self):
        out = [e for e in self.pending if e[0] <= self.t]
        self.pending = [e for e in self.pending if e[0] > self.t]
        return out

    # --- messages d'assistance différenciés ------------------------------
    def assistance_for(self, pid, pair_id):
        """Retourne la liste ordonnée [(option, texte)] pour ce joueur (contradictoires entre eux)."""
        a, b = cfg.PAIRS[pair_id]
        order = [("A", a), ("B", b)]
        # un joueur sur deux reçoit les options dans l'ordre inverse
        ps = self.players.get(pid)
        if ((ps.slot if ps else pid) + pair_id) % 2 == 0:
            order.reverse()
        return order

    def paranoia_for(self, pid):
        others = [p for p in self.players.values() if p.id != pid]
        if not others:
            return None
        other = random.choice(others)
        return random.choice(cfg.PARANOIA).format(autre=other.name)
