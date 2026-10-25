"""Intelligence artificielle du Livreur : modèle 3D, pathfinding, détection, 5 états.

États : patrouille, alerte, poursuite, recherche (30 s), embuscade.
Détection : visuelle (cône + éclairage), sonore (bruits émis par le joueur, occlusion par les
murs), proximité (< 2 m). Les comportements propres à chaque type de livreur sont dans
`entity_behaviors.py`.
"""
import math
import random

from ursina import Entity, Vec3

import config

from house_generator import NavGrid
from room_builder import MeshBuilder
from shaders import shader_state
from sound_engine import engine as sound

STATES = ("patrol", "alert", "chase", "search", "ambush")
MUSIC_STATE = {"patrol": "patrol", "alert": "alert", "chase": "chase", "search": "search", "ambush": "ambush"}

BLACK = (0.045, 0.045, 0.05)


# ---------------------------------------------------------------------------
# Modèle 3D (primitives assemblées)
# ---------------------------------------------------------------------------
def _limb(parent, size, pos, col, tex="platre", emit=0.05, pivot_top=True):
    """Membre dont le pivot est en haut : renvoie le pivot."""
    sx, sy, sz = size
    pivot = Entity(parent=parent, position=pos)
    b = MeshBuilder("limb")
    b.box(tex, -sx / 2, -sy if pivot_top else -sy / 2, -sz / 2, sx / 2, 0 if pivot_top else sy / 2, sz / 2, col, 0.5)
    b.build(parent=pivot, emit=emit)
    return pivot


def _block(parent, size, pos, col, tex="platre", emit=0.05, tile=0.5, rot=(0, 0, 0)):
    sx, sy, sz = size
    root = Entity(parent=parent, position=pos, rotation=rot)
    b = MeshBuilder("blk")
    b.box(tex, -sx / 2, -sy / 2, -sz / 2, sx / 2, sy / 2, sz / 2, col, tile)
    b.build(parent=root, emit=emit)
    return root


def _ball(parent, r, pos, col, sy=1.0, tex="platre", emit=0.05):
    root = Entity(parent=parent, position=pos)
    b = MeshBuilder("ball")
    b.sphere(tex, 0, 0, 0, r, col, lat=7, lon=10, sy=sy)
    b.build(parent=root, emit=emit)
    return root


class EntityPuppet:
    """Modèle animé d'une silhouette. kind : humanoïde | rampant | imposteur."""

    def __init__(self, kind="humanoide", parent=None, ghost=False):
        self.kind = kind
        self.ghost = ghost
        self.root = Entity(parent=parent)
        self.parts = {}
        self.phase = 0.0
        self.face = None
        self.face_blur = False
        self.head = None
        self.head_turn = 0.0
        self.crouch = 0.0
        if kind == "rampant":
            self._build_crawler()
        elif kind == "imposteur":
            self._build_impostor()
        else:
            self._build_humanoid()
        self.set_ghost(ghost)

    # --- constructions ------------------------------------------------
    def _build_humanoid(self):
        r = self.root
        col = BLACK
        self.parts["torso"] = _block(r, (0.30, 0.72, 0.17), (0, 1.22, 0), col)           # torse étroit
        self.head = _ball(r, 0.15, (0, 1.82, 0.0), col, sy=1.25)                          # tête un peu grosse, ovale
        self.parts["arm_l"] = _limb(r, (0.055, 1.0, 0.055), (-0.2, 1.55, 0), col)         # bras jusqu'aux genoux
        self.parts["arm_r"] = _limb(r, (0.055, 1.0, 0.055), (0.2, 1.55, 0), col)
        self.parts["leg_l"] = _limb(r, (0.1, 0.88, 0.1), (-0.09, 0.88, 0), col)
        self.parts["leg_r"] = _limb(r, (0.1, 0.88, 0.1), (0.09, 0.88, 0), col)
        self.parts["bag"] = _block(r, (0.29, 0.46, 0.22), (0, 1.3, -0.2), (1, 1, 1), "sac_quickeats", 0.15, 0.45)

    def _build_impostor(self):
        r = self.root
        jacket = (1.0, 0.55, 0.2)
        self.parts["torso"] = _block(r, (0.46, 0.62, 0.26), (0, 1.25, 0), jacket, "sac_quickeats", 0.18, 0.7)
        skin = (0.85, 0.66, 0.55)
        self.head = _ball(r, 0.115, (0, 1.68, 0), skin, sy=1.15, tex="platre", emit=0.1)
        self.face = Entity(parent=self.head, model="quad", position=(0, 0, 0.115), scale=(0.2, 0.22), double_sided=True)
        from texture_generator import textures
        from shaders import horror_shader
        self.face.shader = horror_shader
        self.face.texture = textures.get("visage_normal")
        self.face.set_shader_input("emit", 0.12)
        self.face.rotation_y = 0
        self.face.setTwoSided(True)
        cap = _block(self.head, (0.26, 0.05, 0.3), (0, 0.11, 0.03), (1.0, 0.45, 0.1), "sac_quickeats", 0.15, 0.4)
        del cap
        self.parts["arm_l"] = _limb(r, (0.1, 0.62, 0.1), (-0.3, 1.5, 0), jacket, "sac_quickeats", 0.15)
        self.parts["arm_r"] = _limb(r, (0.1, 0.62, 0.1), (0.3, 1.5, 0), jacket, "sac_quickeats", 0.15)
        self.parts["leg_l"] = _limb(r, (0.15, 0.94, 0.15), (-0.11, 0.94, 0), (0.1, 0.12, 0.25), "tissu", 0.05)
        self.parts["leg_r"] = _limb(r, (0.15, 0.94, 0.15), (0.11, 0.94, 0), (0.1, 0.12, 0.25), "tissu", 0.05)
        self.parts["bag"] = _block(r, (0.42, 0.46, 0.24), (0, 1.3, -0.25), (1, 1, 1), "sac_quickeats", 0.2, 0.45)
        self.bag_front = _block(r, (0.42, 0.46, 0.24), (0, 0.9, 0.4), (1, 1, 1), "sac_quickeats", 0.2, 0.45)
        self.bag_front.enabled = False

    def _build_crawler(self):
        r = self.root
        col = BLACK
        self.parts["torso"] = _block(r, (0.34, 0.26, 0.85), (0, 0.5, 0), col)
        self.head = _ball(r, 0.14, (0, 0.5, 0.58), col, sy=1.1)
        self.parts["arm_l"] = _limb(r, (0.06, 0.55, 0.06), (-0.22, 0.55, 0.3), col)
        self.parts["arm_r"] = _limb(r, (0.06, 0.55, 0.06), (0.22, 0.55, 0.3), col)
        self.parts["leg_l"] = _limb(r, (0.07, 0.55, 0.07), (-0.2, 0.5, -0.32), col)
        self.parts["leg_r"] = _limb(r, (0.07, 0.55, 0.07), (0.2, 0.5, -0.32), col)
        self.parts["bag"] = _block(r, (0.4, 0.14, 0.4), (0, 0.72, -0.1), (1, 1, 1), "sac_quickeats", 0.15, 0.45)

    # --- état -------------------------------------------------------------
    def set_ghost(self, ghost):
        self.ghost = ghost
        for e in self._all_entities():
            if ghost:
                e.alpha = 0.45
                try:
                    from panda3d.core import TransparencyAttrib
                    e.setTransparency(TransparencyAttrib.M_alpha)
                except Exception:
                    pass
            else:
                e.alpha = 1.0

    def _all_entities(self):
        out = []

        def rec(e):
            out.append(e)
            for c in e.children:
                rec(c)
        rec(self.root)
        return out[1:]

    def set_pos(self, pos, yaw):
        self.root.position = pos
        self.root.rotation_y = yaw

    def animate(self, dt, speed, moving, state="patrol"):
        if not moving:
            speed = 0.0
        self.phase += dt * speed * 3.6
        amp = min(40.0, 12.0 + speed * 9.0) if moving else 0.0
        ph = self.phase
        if self.kind == "rampant":
            self.parts["arm_l"].rotation_x = math.sin(ph) * amp
            self.parts["arm_r"].rotation_x = -math.sin(ph) * amp
            self.parts["leg_l"].rotation_x = -math.sin(ph) * amp
            self.parts["leg_r"].rotation_x = math.sin(ph) * amp
            self.parts["torso"].y = 0.5 + abs(math.sin(ph)) * 0.04
            return
        # démarche légèrement désynchronisée : la jambe droite précède le corps
        self.parts["leg_l"].rotation_x = math.sin(ph) * amp
        self.parts["leg_r"].rotation_x = -math.sin(ph + 0.55) * amp
        arm = 0.35 if self.kind != "imposteur" else 0.6
        self.parts["arm_l"].rotation_x = -math.sin(ph) * amp * arm
        self.parts["arm_r"].rotation_x = math.sin(ph) * amp * arm
        if self.head is not None and self.kind != "imposteur":
            self.head.rotation_z = math.sin(ph * 0.5) * 3
        # tête qui se tourne trop vite (imposteur)
        if self.head is not None and self.kind == "imposteur":
            self.head.rotation_y += (self.head_turn - self.head.rotation_y) * min(1.0, dt * 14.0)

    def set_face_blur(self, blur):
        if self.face is not None and blur != self.face_blur:
            from texture_generator import textures
            self.face_blur = blur
            self.face.texture = textures.get("visage_flou" if blur else "visage_normal")

    def destroy(self):
        from ursina import destroy
        destroy(self.root)


# ---------------------------------------------------------------------------
# IA
# ---------------------------------------------------------------------------
class EntityAI:
    def __init__(self, game):
        self.game = game
        self.house = game.house
        self.nav = game.house.nav
        self.nav_small = None
        self.kind = None
        self.behavior = None
        self.puppets = []
        self.active = False
        self.arriving = False          # entre dans la maison, pas encore dangereux
        self.dormant = False           # le joueur est au sous-sol
        self.visible = False
        self.state = "patrol"
        self.pos = Vec3(7, 0, 1.0)
        self.yaw = 0.0
        self.path = []
        self.path_goal = None
        self.repath_t = 0.0
        self.speed_mult = 1.0
        self.detection_mult = 1.0
        self.release_near_player = False
        self.aggression = 0.0
        self.stall_t = 0.0
        self.state_t = 0.0
        self.dwell_t = 0.0
        self.last_seen_pos = None
        self.last_seen_t = -99.0
        self.search_t = 0.0
        self.ambush_wait = 0.0
        self.ambush_timer = random.uniform(60, 110)
        self.door_wait = 0.0
        self.door_target = None
        self.sees_player = False
        self.dist_to_player = 99.0
        self.ward_pos = None
        self.ward_radius = 0.0
        self.step_dist = 0.0
        self.noise_seen_t = -1.0
        self.moving = False
        self.cur_speed = 0.0
        self.room_cache = {}
        self.visited_rooms = []
        self.tick_t = 0.0
        self.killing = False
        self.nightmare = False
        self.rng = random.Random(5)
        self.hear_mult = 1.0
        self.sight_range_base = 7.0
        self.fov_deg = 62.0
        self.disabled_rooms = {"condamnee", "cave_acces", "sous_sol"}
        self.world_root = Entity(name="entite")
        self.remote = False
        self.light_attracted = False

    # ------------------------------------------------------------------
    # Mise en place
    # ------------------------------------------------------------------
    def spawn(self, kind, pos, nightmare=False):
        from entity_behaviors import make_behavior
        self.despawn()
        self.kind = kind
        self.nightmare = nightmare
        self.behavior = make_behavior(kind, self)
        self.puppets = self.behavior.build_puppets(self)
        self.pos = Vec3(*pos)
        if nightmare:
            self.speed_mult *= 1.3
            self.detection_mult *= 1.4
            self.aggression += 0.2
        self.behavior.on_spawn(self)
        self.active = False
        self.set_visible(False)

    def despawn(self):
        for p in self.puppets:
            p.destroy()
        self.puppets = []
        if self.behavior is not None:
            self.behavior.on_despawn(self)
        self.behavior = None
        self.active = False
        self.set_visible(False)

    def set_visible(self, v):
        self.visible = v
        for p in self.puppets:
            p.root.enabled = v

    def begin_arrival(self, pos, yaw=0.0):
        """30 s avant la fin : l'entité entre dans la maison (lente, pas encore dangereuse)."""
        self.pos = Vec3(*pos)
        self.yaw = yaw
        self.arriving = True
        self.active = True
        self.state = "patrol"
        self.set_visible(True)
        self.path = []
        self.behavior.on_arrival(self)

    def activate(self):
        """0 s : livraison effectuée, la survie commence."""
        self.arriving = False
        self.active = True
        self.set_visible(True)
        if self.release_near_player and self.game.player.level == 0:
            # mauvais choix de l'étage : elle surgit près du joueur
            near = self._cell_near(self.game.player.pos, 7.0, 11.0, self.game.player.level)
            if near is not None:
                self.pos = near
        self.set_state("patrol")
        self.behavior.on_activate(self)

    def set_ward(self, pos, radius):
        self.ward_pos = None if pos is None else Vec3(*pos)
        self.ward_radius = radius

    def stall(self, seconds):
        self.stall_t = max(self.stall_t, seconds)

    def alert_to(self, pos, level=None):
        if not self.active or self.arriving or self.dormant:
            return
        if self.state in ("chase",):
            return
        self.last_seen_pos = Vec3(*pos)
        self.set_state("alert")
        self._goto(pos, level)

    def set_state(self, state):
        if state == self.state and self.state_t > 0.05:
            return
        prev = self.state
        self.state = state
        self.state_t = 0.0
        if state == "search":
            self.search_t = 30.0
        if state == "ambush":
            self.ambush_wait = 0.0
        sound.music.set_state(MUSIC_STATE.get(state, "patrol"))
        self.behavior.on_state(self, prev, state)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def current_nav(self):
        if self.kind == "rampant":
            if self.nav_small is None:
                self.nav_small = NavGrid(self.house, radius=0.12)
                self.nav_small.stair_enabled = self.nav.stair_enabled
            return self.nav_small
        return self.nav

    def level(self):
        return self.house.level_at(self.pos[1] + 0.3)

    def _goto(self, pos, level=None):
        pos = Vec3(*pos)
        lvl = self.house.level_at(pos[1] + 0.3) if level is None else level
        nav = self.current_nav()
        path = nav.find_path(self.pos, pos, self.level(), lvl)
        self.path = path[1:] if len(path) > 1 else path
        self.path_goal = pos
        self.repath_t = 0.0
        return bool(path)

    def _cell_near(self, pos, rmin, rmax, level, dark=True, avoid_view=None):
        nav = self.nav
        cells = [k for k in nav.cells if k[0] == level and k[0] != "stair"]
        self.rng.shuffle(cells)
        for k in cells[:400]:
            x, z = k[1] * nav.cell, k[2] * nav.cell
            d = math.hypot(x - pos[0], z - pos[2])
            if rmin <= d <= rmax:
                p = nav.node_pos3(k)
                if avoid_view is not None and avoid_view(p):
                    continue
                return p
        return None

    def _room_target(self, prefer_level=None):
        h = self.house
        rooms = [r for r in h.rooms.values() if r.id not in self.disabled_rooms]
        weights = []
        for r in rooms:
            w = 1.0
            if prefer_level is not None and r.level == prefer_level:
                w += 3.0
            if r.id in self.visited_rooms[-4:]:
                w *= 0.25
            # préfère les chemins sombres, évite les zones éclairées (sauf mauvais choix sur les lumières)
            lit = any(l.is_lit and l.kind in ("neon", "tv", "candle") and r.level == h.level_at(l.pos[1]) and r.contains(l.pos[0], l.pos[2])
                      for l in h.lights)
            if lit:
                w *= 2.5 if self.light_attracted else 0.3
            weights.append(w)
        room = self.rng.choices(rooms, weights)[0]
        cells = self.room_cache.get(room.id)
        if cells is None:
            cells = self.current_nav().cells_in_room(room)
            self.room_cache[room.id] = cells
        if not cells:
            return None, room
        return self.rng.choice(cells), room

    # ------------------------------------------------------------------
    # Boucle
    # ------------------------------------------------------------------
    def update(self, dt):
        if not self.active or self.behavior is None:
            self._update_visuals(dt)
            return
        game = self.game
        p = game.player
        self.state_t += dt
        self.dist_to_player = math.hypot(self.pos[0] - p.pos[0], self.pos[2] - p.pos[2]) + abs(self.pos[1] - p.pos[1]) * 2.0
        if self.remote:
            self._remote_step(dt)
            return
        if game.state.flag("ending_started"):
            return
        # dormante : le joueur est au sous-sol
        if self.dormant:
            self._update_visuals(dt)
            return
        if self.stall_t > 0:
            self.stall_t -= dt
            self.moving = False
            self._update_visuals(dt)
            return
        self.tick_t -= dt
        if self.tick_t <= 0 and not self.arriving:
            self.tick_t = 0.1
            self._perceive()
        handled = self.behavior.update(self, dt)
        if not handled:
            self._state_logic(dt)
        self._update_visuals(dt)
        self._effects(dt)
        if not self.arriving and not self.killing:
            self._check_kill()

    # --- multijoueur : entité pilotée par le serveur ---------------------
    def remote_update(self, m):
        kind = m.get("kind")
        if kind and kind != self.kind:
            self.spawn(kind, m["pos"])
            self.active = True
        if self.behavior is None:
            return
        self.remote = True
        self.active = True
        pos = Vec3(*m["pos"])
        self._remote_target = pos
        self.yaw = m.get("yaw", self.yaw)
        new_state = m.get("state", self.state)
        if new_state != self.state:
            self.set_state(new_state)
        self.cur_speed = m.get("speed", 0.0)
        self.moving = self.cur_speed > 0.05
        vis = bool(m.get("visible", True))
        if vis != self.visible:
            self.set_visible(vis)
        ghosts = m.get("ghosts", [])
        b = self.behavior
        if hasattr(b, "ghosts"):
            for i, g in enumerate(b.ghosts):
                if i < len(ghosts):
                    g["active"] = True
                    g["pos"] = Vec3(*ghosts[i])
                    g["yaw"] = self.yaw
                else:
                    g["active"] = False

    def _remote_step(self, dt):
        tgt = getattr(self, "_remote_target", None)
        if tgt is not None:
            self.pos = self.pos + (tgt - self.pos) * min(1.0, dt * 8.0)
        self._update_visuals(dt)
        self._effects(dt)

    # --- états ----------------------------------------------------------
    def _speed_for(self, state):
        base = self.behavior.speeds.get(state, 1.0)
        s = base * self.speed_mult * (1.0 + self.aggression * 0.4 if state == "chase" else 1.0) * config.diff("entity")
        if self.arriving:
            s *= 0.6
        return s

    def _state_logic(self, dt):
        st = self.state
        if self.arriving:
            self._wander(dt)
            return
        if st == "patrol":
            self._patrol(dt)
        elif st == "alert":
            self._alert(dt)
        elif st == "chase":
            self._chase(dt)
        elif st == "search":
            self._search(dt)
        elif st == "ambush":
            self._ambush(dt)

    def _wander(self, dt):
        """Marche lente à l'arrivée : du seuil vers le centre de la maison."""
        if not self.path:
            tgt, _ = self._room_target(0)
            if tgt is not None:
                self._goto(tgt)
        self._follow(dt, self._speed_for("patrol"))

    def _patrol(self, dt):
        if self.dwell_t > 0:
            self.dwell_t -= dt
            self.moving = False
            self.behavior.on_dwell(self, dt)
            return
        self.ambush_timer -= dt
        if self.ambush_timer <= 0 and self.behavior.allow_ambush:
            self.ambush_timer = random.uniform(70, 130)
            if random.random() < 0.55:
                self.set_state("ambush")
                self._pick_ambush()
                return
        if not self.path:
            tgt, room = self._room_target(self.game.player.level)
            if tgt is None:
                self.dwell_t = 1.0
                return
            self.visited_rooms.append(room.id)
            if not self._goto(tgt):
                self.dwell_t = 1.0
            return
        arrived = self._follow(dt, self._speed_for("patrol"))
        if arrived:
            self.dwell_t = random.uniform(2.0, 6.0)
            self.behavior.on_patrol_arrival(self)

    def _alert(self, dt):
        arrived = self._follow(dt, self._speed_for("alert"))
        if arrived or not self.path:
            self.set_state("search")

    def _chase(self, dt):
        p = self.game.player
        self.repath_t -= dt
        if self.sees_player:
            self.last_seen_pos = Vec3(*p.pos)
            self.last_seen_t = self.game.player.time
        if self.repath_t <= 0:
            self.repath_t = 0.4
            tgt = p.pos if (self.sees_player or self.dist_to_player < 12) else (self.last_seen_pos or p.pos)
            if self.path_goal is None or (Vec3(*tgt) - self.path_goal).length() > 1.2 or not self.path:
                self._goto(tgt, p.level if self.sees_player else None)
        self._follow(dt, self._speed_for("chase"))
        lost = (self.game.player.time - self.last_seen_t) > 4.0
        if lost and self.dist_to_player > 5.0:
            self.set_state("search")

    def _search(self, dt):
        self.search_t -= dt
        if self.dwell_t > 0:
            self.dwell_t -= dt
            self.moving = False
            return
        if self.search_t <= 0:
            if random.random() < 0.3 and self.behavior.allow_ambush:
                self.set_state("ambush")
                self._pick_ambush()
            else:
                self.set_state("patrol")
                self.path = []
            return
        if not self.path:
            base = self.last_seen_pos or self.pos
            tgt = self._cell_near(base, 0.0, 6.0, self.level())
            if tgt is not None:
                self._goto(tgt)
            self.dwell_t = random.uniform(0.8, 2.0)
            return
        arrived = self._follow(dt, self._speed_for("alert") * 0.9)
        if arrived:
            self.dwell_t = random.uniform(1.0, 2.5)

    def _pick_ambush(self):
        p = self.game.player
        fwd = p.forward
        lvl = p.level
        target = None
        for _ in range(12):
            ang = math.atan2(fwd[0], fwd[2]) + random.uniform(-0.8, 0.8)
            dist = random.uniform(6.0, 10.0)
            c = Vec3(p.pos[0] + math.sin(ang) * dist, p.pos[1], p.pos[2] + math.cos(ang) * dist)
            k = self.nav._nearest_cell(lvl, c[0], c[2], 3)
            if k is None:
                continue
            q = self.nav.node_pos3(k)
            if self.house.wall_count(p.eye_pos, q + Vec3(0, 1.4, 0)) > 0:
                target = q
                break
        if target is None:
            target = self._cell_near(p.pos, 5.0, 10.0, lvl)
        if target is not None:
            self._goto(target)
        else:
            self.set_state("patrol")

    def _ambush(self, dt):
        if self.path:
            self._follow(dt, self._speed_for("alert"))
            return
        self.moving = False
        self.ambush_wait += dt
        if self.sees_player and self.dist_to_player < 4.5:
            self.set_state("chase")
            return
        if self.ambush_wait > random.uniform(9, 16):
            self.set_state("patrol")

    # --- déplacement ----------------------------------------------------
    def _follow(self, dt, speed):
        """Suit self.path. Retourne True à l'arrivée."""
        self.moving = False
        if self.door_wait > 0:
            self.door_wait -= dt
            if self.door_wait <= 0 and self.door_target is not None:
                if not self.door_target.is_open:
                    self.door_target.open(1.0)
                    self.game.player.emit_noise(5.0, self.door_target.pos, "porte")
                self.door_target = None
            return False
        if not self.path:
            return True
        tgt = self.path[0]
        dx, dz = tgt[0] - self.pos[0], tgt[2] - self.pos[2]
        dist = math.hypot(dx, dz)
        step = speed * dt
        if dist < max(0.12, step):
            self.pos = Vec3(tgt[0], self.pos[1], tgt[2])
            self._snap_y()
            self.path.pop(0)
            return not self.path
        nx, nz = self.pos[0] + dx / dist * step, self.pos[2] + dz / dist * step
        # portes fermées sur le chemin
        door = self.house.nearest_door(Vec3(nx + dx / dist * 0.55, self.pos[1] + 1, nz + dz / dist * 0.55), 0.85)
        if door is not None and not door.is_open:
            if door.ai_passable:
                self.door_target = door
                self.door_wait = 1.0
                sound.play_at("poignee", door.pos, 0.8)
                return False
            else:
                self.path = []
                return True
        # cercle de sel
        if self.ward_pos is not None and self.ward_radius > 0:
            if math.hypot(nx - self.ward_pos[0], nz - self.ward_pos[2]) < self.ward_radius:
                self.moving = False
                self.path = []
                return True
        self.yaw = math.degrees(math.atan2(dx, dz))
        self.pos = Vec3(nx, self.pos[1], nz)
        self._snap_y()
        self.moving = True
        self.cur_speed = speed
        self._footsteps(step)
        return False

    def _snap_y(self):
        g = self.house.ground_height(self.pos[0], self.pos[2], self.pos[1] + 0.5, 0.6)
        if g is not None:
            self.pos = Vec3(self.pos[0], g, self.pos[2])

    def _footsteps(self, step):
        self.step_dist += step
        if self.step_dist >= 1.15:
            self.step_dist = 0.0
            self.behavior.on_step(self)

    # --- perception -----------------------------------------------------
    def _perceive(self):
        p = self.game.player
        house = self.house
        eye_e = self.pos + Vec3(0, 1.5, 0)
        eye_p = p.eye_pos
        dy = abs(self.pos[1] - p.pos[1])
        dxz = math.hypot(self.pos[0] - p.pos[0], self.pos[2] - p.pos[2])
        same_level = dy < 2.2
        sees = False
        if same_level and not p.dead:
            los = house.wall_count(eye_e, eye_p) == 0
            if dxz < 2.0 * math.sqrt(self.detection_mult) and (los or dxz < 1.2):
                sees = True
            elif los:
                vis = min(1.0, p.visibility() * self.detection_mult)
                reach = self.sight_range_base + 14.0 * vis
                if self.state == "chase":
                    reach *= 1.4
                ang = self._angle_to(p.pos)
                fov = 180.0 if self.state == "chase" else self.fov_deg
                # lampe torche dirigée vers l'entité : elle nous voit aussi
                if p.flashlight.on:
                    to_e = (self.pos + Vec3(0, 1.0, 0) - eye_p)
                    if to_e.length() > 0.1 and to_e.normalized().dot(p.forward) > 0.86:
                        reach = max(reach, 16.0)
                        fov = 180.0
                if dxz < reach and ang < fov and self.behavior.can_see(self):
                    sees = True
        self.sees_player = sees
        if sees and self.state != "chase":
            self.noise_seen_t = self.game.player.time
            self.set_state("chase")
            self.last_seen_pos = Vec3(*p.pos)
            self.last_seen_t = p.time
        # ouïe
        mult = self.hear_mult * self.detection_mult
        if mult > 0:
            for n in p.noises:
                key = (round(n["t"], 3), n["kind"])
                if key == getattr(self, "_last_noise", None):
                    continue
                if abs(n["t"] - p.time) > 0.25:
                    continue
                npos = n["pos"]
                if abs(npos[1] - self.pos[1]) > 4.0 and n["kind"] not in ("voix",):
                    continue
                walls = house.wall_count(eye_e, Vec3(npos[0], npos[1] + 1.0, npos[2]))
                eff = n["radius"] * (0.55 ** walls) * mult * self.behavior.hearing_for(n["kind"])
                d = math.hypot(npos[0] - self.pos[0], npos[2] - self.pos[2])
                if d < eff and self.state not in ("chase",):
                    self._last_noise = key
                    self.behavior.on_hear(self, n)
                    self.alert_to(npos)
                    break

    def _angle_to(self, pos):
        dx, dz = pos[0] - self.pos[0], pos[2] - self.pos[2]
        a = math.degrees(math.atan2(dx, dz))
        return abs((a - self.yaw + 180) % 360 - 180)

    # --- effets sur le joueur / rendu -----------------------------------
    def _effects(self, dt):
        p = self.game.player
        d = self.dist_to_player
        prox = max(0.0, 1.0 - d / 14.0)
        p.proximity = prox
        if prox > 0 and self.visible and self.sees_player and d < 9.0:
            p.add_stress(7.0 * prox * dt)
        elif prox > 0.2 and d < 10.0:
            p.add_stress(2.5 * prox * dt)
        shader_state.ent_pos = Vec3(self.pos[0], self.pos[1] + 1.0, self.pos[2]) if self.visible else Vec3(0, -500, 0)
        shader_state.ent_distort = max(0.0, 1.0 - d / 5.0) if self.visible else 0.0

    def _update_visuals(self, dt):
        if not self.visible:
            return
        self.behavior.update_visuals(self, dt)

    def _check_kill(self):
        if self.state != "chase" or self.arriving or self.dormant:
            return
        if self.behavior.check_kill(self):
            self.killing = True
            self.behavior.kill(self)

    def reset_after_death(self):
        self.killing = False
        self.path = []
        self.set_state("patrol")
        self.dwell_t = 3.0
        self.dormant = False

    # ------------------------------------------------------------------
    def serialize(self):
        return dict(kind=self.kind, pos=[self.pos[0], self.pos[1], self.pos[2]], state=self.state,
                    active=self.active, speed_mult=self.speed_mult, detection_mult=self.detection_mult,
                    nightmare=self.nightmare)

    def restore(self, d):
        if not d or not d.get("kind"):
            return
        self.spawn(d["kind"], d["pos"], False)
        self.speed_mult = d.get("speed_mult", 1.0)
        self.detection_mult = d.get("detection_mult", 1.0)
        self.nightmare = d.get("nightmare", False)
        if d.get("active"):
            self.activate()
