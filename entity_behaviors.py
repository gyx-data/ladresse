"""Comportements propres à chaque type de Livreur (selon le repas commandé).

* Le Silencieux  : immobile quand on le regarde, se rapproche dès qu'on détourne les yeux.
* Le Rampant     : quatre pattes, rapide, se cache sous les meubles, marche au plafond.
* Le Multiple    : trois silhouettes, deux illusions, le vrai est dans la direction de fuite.
* L'Imposteur    : livreur presque normal, parle, visage flou quand on le regarde en face.
"""
import math
import random

from ursina import Entity, Vec3

import game_data as gd
from config import LEVEL_Y
from entity_ai import EntityPuppet
from sound_engine import engine as sound
from texture_generator import textures
from shaders import horror_shader


class Behavior:
    kind = "base"
    speeds = {"patrol": 1.0, "alert": 1.5, "chase": 2.4}
    allow_ambush = True
    puppet_kind = "humanoide"

    def __init__(self, ai):
        self.ai = ai

    # --- construction -----------------------------------------------------
    def build_puppets(self, ai):
        return [EntityPuppet(self.puppet_kind, ai.world_root)]

    def on_spawn(self, ai):
        pass

    def on_despawn(self, ai):
        pass

    def on_arrival(self, ai):
        pass

    def on_activate(self, ai):
        pass

    def on_state(self, ai, prev, new):
        pass

    def on_dwell(self, ai, dt):
        pass

    def on_patrol_arrival(self, ai):
        pass

    def on_hear(self, ai, noise):
        pass

    def hearing_for(self, kind):
        return 1.0

    def can_see(self, ai):
        return True

    # --- boucle -----------------------------------------------------------
    def on_step(self, ai):
        sound.play_at("pas_entite", ai.pos, 1.0, ref=4.0)
        # un pas sur deux : la semelle droite racle le sol (le Livreur boite)
        self._step_n = getattr(self, "_step_n", 0) + 1
        if self._step_n % 2 == 0 and self.puppet_kind == "humanoide":
            sound.play_at("livreur_raclement", ai.pos, 0.7, pitch=random.uniform(0.9, 1.1), ref=3.5)

    def update(self, ai, dt):
        return False

    def update_visuals(self, ai, dt):
        p = self.ai.puppets[0]
        p.set_pos(ai.pos, ai.yaw)
        p.animate(dt, ai.cur_speed, ai.moving, ai.state)

    def check_kill(self, ai):
        pl = ai.game.player
        if pl.dead or ai.game.state.flag("ending_started"):
            return False
        dxz = math.hypot(ai.pos[0] - pl.pos[0], ai.pos[2] - pl.pos[2])
        return dxz < 0.95 and abs(ai.pos[1] - pl.pos[1]) < 1.3

    def kill(self, ai):
        ai.game.kill_player("entity_contact", kind=ai.kind)


# ---------------------------------------------------------------------------
# Le Silencieux
# ---------------------------------------------------------------------------
class Silencieux(Behavior):
    kind = "silencieux"
    speeds = {"patrol": 0.9, "alert": 1.2, "chase": 1.6}
    allow_ambush = False

    def on_spawn(self, ai):
        ai.hear_mult = 0.0                     # chasse à la vue, pas au son
        ai.sight_range_base = 8.0
        self.gaze = 0.0
        self.unseen = 0.0
        self.tp_timer = random.uniform(4.0, 7.0)
        self.last_yaw = 0.0
        self.turn_rate = 0.0

    def on_step(self, ai):
        pass                                   # aucun bruit de pas

    def _seen_by_player(self, ai):
        pl = ai.game.player
        to = (ai.pos + Vec3(0, 1.3, 0)) - pl.eye_pos
        dist = to.length()
        if dist > 22 or dist < 0.01:
            return False
        if to.normalized().dot(pl.forward) < 0.74:          # hors du champ de vision
            return False
        if ai.house.wall_count(pl.eye_pos, ai.pos + Vec3(0, 1.3, 0)) > 0:
            return False
        lit = dist < 4.5 or (pl.flashlight.on and to.normalized().dot(pl.forward) > 0.82 and dist < 16)
        return lit or pl.phone_open and dist < 3

    def update(self, ai, dt):
        if ai.arriving:
            return False
        pl = ai.game.player
        # vitesse de rotation du joueur
        dyaw = abs((pl.yaw - self.last_yaw + 180) % 360 - 180) / max(dt, 1e-3)
        self.last_yaw = pl.yaw
        self.turn_rate = self.turn_rate * 0.8 + dyaw * 0.2
        seen = self._seen_by_player(ai)
        d = ai.dist_to_player
        # musique selon la distance
        if d < 6:
            ai.set_state("chase")
        elif d < 14:
            ai.set_state("alert")
        else:
            ai.set_state("patrol")
        if seen:
            self.unseen = 0.0
            self.gaze += dt
            ai.moving = False
            ai.cur_speed = 0.0
            # fixe le joueur du regard
            ai.yaw = math.degrees(math.atan2(pl.pos[0] - ai.pos[0], pl.pos[2] - ai.pos[2]))
            if self.gaze > 10.0:
                # marche très lentement vers le joueur
                dx, dz = pl.pos[0] - ai.pos[0], pl.pos[2] - ai.pos[2]
                dist = math.hypot(dx, dz)
                if dist > 1.3:
                    step = 0.55 * dt * ai.speed_mult
                    nx, nz = ai.pos[0] + dx / dist * step, ai.pos[2] + dz / dist * step
                    if not ai.house.blocked(nx, nz, ai.pos[1], 0.25, 1.6):
                        ai.pos = Vec3(nx, ai.pos[1], nz)
                        ai._snap_y()
                        ai.moving = True
                        ai.cur_speed = 0.55
            return True
        self.gaze = max(0.0, self.gaze - dt * 2.0)
        self.unseen += dt
        ai.moving = False
        # contact : le joueur se retourne et tombe nez à nez
        if d < 3.4 and self.unseen > 0.5 and self.turn_rate > 100.0 and ai.visible:
            self._ambush_kill(ai)
            return True
        if d < 1.3 and self.unseen > 0.3:
            self._ambush_kill(ai)
            return True
        # téléportation vers le joueur dès qu'il détourne le regard
        self.tp_timer -= dt
        if self.tp_timer <= 0 and self.unseen > 0.8 and d > 2.8:
            self.tp_timer = random.uniform(4.0, 7.0) / max(0.6, ai.speed_mult)
            self._teleport_closer(ai)
        return True

    def _teleport_closer(self, ai):
        pl = ai.game.player
        lvl = pl.level
        target_d = max(2.6, ai.dist_to_player * 0.74)
        best = None
        cells = [k for k in ai.nav.cells if k[0] == lvl]
        random.shuffle(cells)
        for k in cells[:250]:
            x, z = k[1] * ai.nav.cell, k[2] * ai.nav.cell
            d = math.hypot(x - pl.pos[0], z - pl.pos[2])
            if abs(d - target_d) > 1.2:
                continue
            p = ai.nav.node_pos3(k)
            to = (p + Vec3(0, 1.3, 0)) - pl.eye_pos
            if to.length() > 0.1 and to.normalized().dot(pl.forward) > 0.72 and ai.house.wall_count(pl.eye_pos, p + Vec3(0, 1.3, 0)) == 0:
                continue                         # dans le champ de vision : pas de téléportation visible
            best = p
            break
        if best is not None:
            ai.pos = best
            ai.yaw = math.degrees(math.atan2(pl.pos[0] - best[0], pl.pos[2] - best[2]))
            ai.set_visible(True)

    def _ambush_kill(self, ai):
        pl = ai.game.player
        f = pl.forward
        ai.pos = Vec3(pl.pos[0] + f[0] * 1.2, pl.pos[1], pl.pos[2] + f[2] * 1.2)
        ai._snap_y()
        ai.yaw = math.degrees(math.atan2(-f[0], -f[2]))
        ai.killing = True
        ai.game.kill_player("entity_contact", kind="silencieux")

    def check_kill(self, ai):
        return False


# ---------------------------------------------------------------------------
# Le Rampant
# ---------------------------------------------------------------------------
class Rampant(Behavior):
    kind = "rampant"
    speeds = {"patrol": 1.8, "alert": 2.8, "chase": 5.0}
    puppet_kind = "rampant"
    HIDE_SPOTS = [(1.35, 3.0, 3.0), (14.0, 3.0, 10.9), (14.4, 0.0, 5.35), (3.1, 0.0, 5.45), (1.0, 3.0, 7.4), (7.2, 6.0, 10.8)]

    def on_spawn(self, ai):
        ai.hear_mult = 1.3
        ai.fov_deg = 75.0
        self.sound_t = random.uniform(1.0, 2.5)
        self.ceil = False
        self.ceil_cool = 8.0
        self.hidden = False
        self.prints = []
        self.print_dist = 0.0
        self.ceil_target = None

    def on_despawn(self, ai):
        for e in self.prints:
            try:
                e.disable()
            except Exception:
                pass

    def on_step(self, ai):
        pass

    def on_state(self, ai, prev, new):
        if new == "ambush":
            self._hide(ai)
        elif prev == "ambush":
            self.hidden = False
        if new == "chase":
            sound.play_at("respiration_saccadee", ai.pos, 1.0, ref=5.0)

    def _hide(self, ai):
        pl = ai.game.player
        best, bd = None, 1e9
        for s in self.HIDE_SPOTS:
            d = math.hypot(s[0] - pl.pos[0], s[2] - pl.pos[2]) + abs(s[1] - pl.pos[1]) * 4
            if 4 < d < bd:
                best, bd = s, d
        if best is not None:
            ai._goto(Vec3(*best))
            self.hide_spot = Vec3(*best)
        self.hidden = True

    def update(self, ai, dt):
        pl = ai.game.player
        # bruitages organiques
        if ai.moving or ai.state == "chase":
            self.sound_t -= dt
            if self.sound_t <= 0:
                self.sound_t = random.uniform(1.0, 2.6)
                sound.play_at(random.choice(["glissement_humide", "os_craquent"]), ai.pos, 0.9, ref=4.5)
        if ai.arriving:
            return False
        # embusqué sous un meuble : bondit si le joueur approche
        if ai.state == "ambush" and not ai.path and self.hidden:
            if ai.dist_to_player < 2.8 and ai.house.wall_count(pl.eye_pos, ai.pos + Vec3(0, 0.5, 0)) == 0:
                self.hidden = False
                ai.set_state("chase")
                pl.shake(0.4, 0.3)
                sound.play_at("respiration_saccadee", ai.pos, 1.0)
        # marche au plafond
        self.ceil_cool -= dt
        if self.ceil:
            return self._ceiling(ai, dt)
        if ai.state == "chase" and ai.sees_player and self.ceil_cool <= 0 and ai.dist_to_player < 9.0 and ai.dist_to_player > 3.0 and random.random() < dt * 0.4:
            room = ai.house.room_at(ai.pos[0], ai.pos[2], ai.pos[1] + 0.2)
            proom = ai.house.room_at(pl.pos[0], pl.pos[2], pl.pos[1] + 0.2)
            if room is not None and room is proom and room.level >= 0 and room.id != "grenier":
                self._start_ceiling(ai, room)
        return False

    def _start_ceiling(self, ai, room):
        self.ceil = True
        self.ceil_room = room
        self.ceil_y = LEVEL_Y[room.level] + 2.55
        self.print_dist = 0.0
        ai.moving = True
        sound.play_at("os_craquent", ai.pos, 1.0)

    def _ceiling(self, ai, dt):
        pl = ai.game.player
        r = self.ceil_room
        dx, dz = pl.pos[0] - ai.pos[0], pl.pos[2] - ai.pos[2]
        dist = math.hypot(dx, dz)
        speed = 4.4 * ai.speed_mult
        step = speed * dt
        if dist > 1.2:
            nx = min(r.x1 - 0.3, max(r.x0 + 0.3, ai.pos[0] + dx / dist * step))
            nz = min(r.z1 - 0.3, max(r.z0 + 0.3, ai.pos[2] + dz / dist * step))
            self.print_dist += step
            if self.print_dist > 0.9:
                self.print_dist = 0.0
                self._print(nx, nz)
            ai.pos = Vec3(nx, ai.pos[1], nz)
            ai.yaw = math.degrees(math.atan2(dx, dz))
            ai.moving = True
            ai.cur_speed = speed
        else:
            # saute sur le joueur depuis le plafond
            self.ceil = False
            self.ceil_cool = 14.0
            ai.pos = Vec3(pl.pos[0], pl.pos[1], pl.pos[2] - 0.3)
            ai.killing = True
            ai.game.kill_player("entity_contact", kind="rampant")
        if not ai.sees_player and ai.dist_to_player > 11:
            self.ceil = False
            self.ceil_cool = 10.0
            ai._snap_y()
        return True

    def _print(self, x, z):
        e = Entity(parent=ai_root(self.ai), model="quad", texture=textures.get("mains"), shader=horror_shader,
                   position=(x, self.ceil_y - 0.01, z), rotation_x=-90, scale=(0.6, 0.6), double_sided=True)
        e.set_shader_input("emit", 0.0)
        e.setTransparency(True)
        self.prints.append(e)
        if len(self.prints) > 24:
            old = self.prints.pop(0)
            old.disable()

    def update_visuals(self, ai, dt):
        p = ai.puppets[0]
        y = ai.pos[1]
        roll = 0.0
        if self.ceil:
            y = self.ceil_y - 0.45
            roll = 180.0
        elif self.hidden and not ai.path:
            y -= 0.28
        p.root.position = Vec3(ai.pos[0], y, ai.pos[2])
        p.root.rotation = Vec3(0, ai.yaw, roll)
        p.animate(dt, ai.cur_speed, ai.moving, ai.state)


def ai_root(ai):
    return ai.world_root


# ---------------------------------------------------------------------------
# Le Multiple
# ---------------------------------------------------------------------------
class Multiple(Behavior):
    kind = "multiple"
    speeds = {"patrol": 1.2, "alert": 1.9, "chase": 3.3}

    def build_puppets(self, ai):
        real = EntityPuppet("humanoide", ai.world_root)
        g1 = EntityPuppet("humanoide", ai.world_root, ghost=True)
        g2 = EntityPuppet("humanoide", ai.world_root, ghost=True)
        return [real, g1, g2]

    def on_spawn(self, ai):
        ai.hear_mult = 1.1
        self.ghosts = [dict(active=False, pos=Vec3(0, -50, 0), t=0.0, yaw=0.0, respawn=random.uniform(4, 9)) for _ in range(2)]
        self.away_t = 0.0
        self.redirect_cool = 10.0
        self.whisper = []
        self.last_ghost_dist = {}
        for g in ai.puppets[1:]:
            g.root.enabled = False

    def on_despawn(self, ai):
        for h in self.whisper:
            if h:
                h.stop()
        self.whisper = []

    def on_activate(self, ai):
        for i, g in enumerate(self.ghosts):
            g["respawn"] = 3.0 + i * 3.0
        self.whisper = [sound.loop("chuchotements", 0.5, channel="sfx", pos=ai.pos, ref=3.0)]

    def on_state(self, ai, prev, new):
        if new == "chase" and prev != "chase":
            # les trois convergent
            for g in self.ghosts:
                if not g["active"]:
                    self._spawn_ghost(ai, g, 3.0, 6.0)

    def _spawn_ghost(self, ai, g, rmin, rmax):
        pl = ai.game.player
        center = pl.pos if ai.state == "chase" else ai.pos
        p = ai._cell_near(center, rmin, rmax, pl.level)
        if p is None:
            return
        g["active"] = True
        g["pos"] = p
        g["t"] = 0.0

    def _flash_ghost(self, ai, g, idx):
        g["active"] = False
        g["respawn"] = random.uniform(10, 16)
        sound.play_at("flash_clone", g["pos"], 1.0)
        ai.game.effects.flash(0.12, 0.25)
        ai.puppets[1 + idx].root.enabled = False

    def update(self, ai, dt):
        pl = ai.game.player
        # chuchotements suivent le vrai
        if self.whisper and self.whisper[0] is not None:
            self.whisper[0].pos = ai.pos
        if ai.arriving:
            return False
        beam = pl.forward
        for i, g in enumerate(self.ghosts):
            if not g["active"]:
                g["respawn"] -= dt
                if g["respawn"] <= 0 and ai.state in ("patrol", "alert", "chase", "search") and ai.visible:
                    self._spawn_ghost(ai, g, 5.0, 11.0)
                    g["respawn"] = random.uniform(6, 12)
                continue
            g["t"] += dt
            to = g["pos"] - pl.pos
            dist = math.hypot(to[0], to[2])
            speed = 1.7 if ai.state != "chase" else ai.behavior.speeds["chase"] * ai.speed_mult * 0.95
            if dist > 0.5:
                g["pos"] = Vec3(g["pos"][0] - to[0] / dist * speed * dt, g["pos"][1], g["pos"][2] - to[2] / dist * speed * dt)
                g["yaw"] = math.degrees(math.atan2(-to[0], -to[2]))
            # touchés par la lumière : disparaissent dans un flash
            eye_to = (g["pos"] + Vec3(0, 1.2, 0)) - pl.eye_pos
            if pl.flashlight.on and eye_to.length() < 11 and eye_to.normalized().dot(beam) > 0.93 and ai.house.wall_count(pl.eye_pos, g["pos"] + Vec3(0, 1.2, 0)) == 0:
                self._flash_ghost(ai, g, i)
                continue
            if dist < 0.95:
                pl.add_stress(22)
                pl.shake(0.4, 0.3)
                self._flash_ghost(ai, g, i)
                continue
            if g["t"] > 14.0:
                g["active"] = False
                g["respawn"] = random.uniform(5, 10)
                ai.puppets[1 + i].root.enabled = False
        # fuite d'un clone : le vrai attend dans la direction de fuite
        self.redirect_cool -= dt
        away = False
        for g in self.ghosts:
            if g["active"]:
                to_g = g["pos"] - pl.pos
                d = math.hypot(to_g[0], to_g[2])
                if d < 8.0 and pl.speed > 1.2 and d > 0.1:
                    vel = Vec3(pl.vel[0], 0, pl.vel[2])
                    if vel.length() > 0.1 and vel.normalized().dot(Vec3(to_g[0], 0, to_g[2]).normalized()) < -0.5:
                        away = True
        self.away_t = self.away_t + dt if away else max(0.0, self.away_t - dt)
        if self.away_t > 2.0 and self.redirect_cool <= 0:
            self.redirect_cool = 25.0
            self.away_t = 0.0
            vel = Vec3(pl.vel[0], 0, pl.vel[2]).normalized()
            for _ in range(10):
                d = random.uniform(6.0, 9.0)
                c = pl.pos + vel * d
                k = ai.nav._nearest_cell(pl.level, c[0], c[2], 2)
                if k is not None:
                    q = ai.nav.node_pos3(k)
                    if ai.house.wall_count(pl.eye_pos, q + Vec3(0, 1.3, 0)) == 0 or random.random() < 0.3:
                        ai.pos = q
                        ai.path = []
                        ai.set_state("chase")
                        ai.last_seen_pos = Vec3(*pl.pos)
                        ai.last_seen_t = pl.time
                        sound.play_at("chuchotements", q, 0.9)
                        break
        return False

    def update_visuals(self, ai, dt):
        real = ai.puppets[0]
        real.set_pos(ai.pos, ai.yaw)
        real.animate(dt, ai.cur_speed, ai.moving, ai.state)
        for i, g in enumerate(self.ghosts):
            pup = ai.puppets[1 + i]
            if g["active"]:
                pup.root.enabled = True
                pup.set_pos(g["pos"], g["yaw"])
                # mouvements moins « organiques » : cadence régulière et raide
                pup.animate(dt, 1.6, True, ai.state)
            else:
                pup.root.enabled = False

    def check_kill(self, ai):
        return super().check_kill(ai)


# ---------------------------------------------------------------------------
# L'Imposteur
# ---------------------------------------------------------------------------
class Imposteur(Behavior):
    kind = "imposteur"
    speeds = {"patrol": 1.1, "alert": 1.6, "chase": 2.4}
    allow_ambush = False
    puppet_kind = "imposteur"

    def on_spawn(self, ai):
        ai.hear_mult = 1.0
        ai.fov_deg = 85.0
        self.talk_t = random.uniform(6, 12)
        self.head_t = random.uniform(5, 10)
        self.head_hold = 0.0
        self.pose = "normal"
        self.pose_t = 0.0
        self.kill_phase = 0

    def hearing_for(self, kind):
        return 2.4 if kind == "voix" else 1.0

    def on_hear(self, ai, noise):
        if noise["kind"] == "voix":
            sound.speak("Il y a quelqu'un ?", f0=112, speed=0.95, pos=ai.pos, volume=1.0, channel="sfx", speaker="Livreur")
            ai.set_state("alert")

    def on_step(self, ai):
        sound.play_at("pas_carrelage_1", ai.pos, 0.9, ref=4.0)

    def on_arrival(self, ai):
        self.talk_t = 3.0

    def on_dwell(self, ai, dt):
        # tient une position anormale : face au mur ou accroupi dans un coin
        if self.pose == "normal" and self.pose_t <= 0:
            r = random.random()
            if r < 0.4:
                self.pose = "mur"
                ai.yaw = round(ai.yaw / 90.0) * 90.0
            elif r < 0.65:
                self.pose = "accroupi"
            self.pose_t = ai.dwell_t

    def on_patrol_arrival(self, ai):
        self.pose = "normal"
        self.pose_t = 0.0

    def update(self, ai, dt):
        pl = ai.game.player
        # reprise de la pose normale
        if self.pose != "normal":
            self.pose_t -= dt
            if ai.moving or ai.state in ("chase",):
                self.pose = "normal"
        # il parle
        if ai.state in ("patrol", "alert", "search") and ai.visible:
            self.talk_t -= dt
            if self.talk_t <= 0 and ai.dist_to_player < 22:
                self.talk_t = random.uniform(12, 20)
                line = random.choice(gd.IMPOSTOR_LINES)
                sound.speak(line, f0=112, speed=0.95, pos=ai.pos + Vec3(0, 1.5, 0), volume=1.0, channel="sfx", speaker="Livreur")
        # la tête se tourne à 90° trop vite
        self.head_t -= dt
        if self.head_hold > 0:
            self.head_hold -= dt
            if self.head_hold <= 0:
                ai.puppets[0].head_turn = 0.0
        elif self.head_t <= 0 and ai.dist_to_player < 14:
            self.head_t = random.uniform(5, 11)
            ai.puppets[0].head_turn = random.choice([-90.0, 90.0])
            self.head_hold = random.uniform(0.6, 1.4)
        # visage flou en regard direct, normal en vision périphérique
        to = (ai.pos + Vec3(0, 1.65, 0)) - pl.eye_pos
        direct = False
        if to.length() < 16 and to.length() > 0.1:
            direct = to.normalized().dot(pl.forward) > 0.955 and ai.house.wall_count(pl.eye_pos, ai.pos + Vec3(0, 1.6, 0)) == 0
        ai.puppets[0].set_face_blur(direct)
        return False

    def update_visuals(self, ai, dt):
        p = ai.puppets[0]
        crouch = (self.pose == "accroupi" and not ai.moving)
        p.root.position = ai.pos
        p.root.rotation_y = ai.yaw
        p.root.scale_y = 0.55 if crouch else 1.0
        p.animate(dt, ai.cur_speed, ai.moving, ai.state)

    def check_kill(self, ai):
        pl = ai.game.player
        if pl.dead or self.kill_phase:
            return False
        dxz = math.hypot(ai.pos[0] - pl.pos[0], ai.pos[2] - pl.pos[2])
        return dxz < 1.9 and abs(ai.pos[1] - pl.pos[1]) < 1.3

    def kill(self, ai):
        self.kill_phase = 1
        ai.game.jumpscare.bag_sequence(ai, on_done=lambda: ai.game.kill_player("entity_contact", kind="imposteur", already_scared=True))
        sound.speak("Bonsoir ! J'ai votre commande !", f0=112, speed=0.95, pos=ai.pos, volume=1.0, channel="sfx", speaker="Livreur")


def make_behavior(kind, ai):
    return {"silencieux": Silencieux, "rampant": Rampant, "multiple": Multiple, "imposteur": Imposteur}.get(kind, Imposteur)(ai)
