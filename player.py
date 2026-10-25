"""Contrôleur du joueur : déplacement, sprint, saut, accroupi, lampe torche, stamina, stress,
tremblement de caméra, bruit émis, pas, respiration, battement de cœur.

Deux vues : première personne (mains + lampe) et troisième personne « caméra d'épaule »
(personnage animé visible, caméra amortie qui évite de traverser les murs et les plafonds).
"""
import math
import random

from ursina import Entity, Vec3, camera, held_keys, mouse, color

import config
import game_data as gd
from character_model import CharacterModel
from lighting_system import Flashlight
from sound_engine import engine as sound
from config import settings, LEVEL_Y

EYE_STAND = 1.62
EYE_CROUCH = 1.0
LEVEL_CEIL = {-1: 2.55, 0: 2.95, 1: 2.95, 2: 3.6}      # hauteur sous plafond approximative par niveau
SHOULDER = {"Droite": 0.55, "Centre": 0.0, "Gauche": -0.55}


def key_down(action):
    """Vrai si la touche associée à l'action est maintenue (gère ZQSD/WASD)."""
    k = settings.key(action)
    if held_keys[k]:
        return True
    alt = config.ALT_KEYS.get(action)
    if alt and k == config.DEFAULT_KEYS[action] and held_keys[alt]:
        return True
    return False


class Player:
    def __init__(self, house, state):
        self.house = house
        self.state = state
        self.pos = Vec3(7.0, 0.0, 0.8)
        self.yaw = 0.0
        self.pitch = 0.0
        self.vy = 0.0
        self.vel = Vec3(0, 0, 0)
        self.on_ground = True
        self.health = 100.0
        self.stamina = 100.0
        self.stamina_delay = 0.0
        self.stress = 0.0
        self.crouching = False
        self.crouch_t = 0.0
        self.sprinting = False
        self.sprint_locked = False
        self.moving = False
        self.speed = 0.0
        self.dead = False
        self.on_death = None
        self.frozen = False            # cinématique, jumpscare...
        self.look_enabled = True
        self.move_enabled = True
        self.phone_open = False
        self.flashlight = Flashlight()
        self.flashlight.on_toggle = self._on_flash_toggle
        self.bob_phase = 0.0
        self.step_dist = 0.0
        self.last_stair_step = -1
        self.shake_amp = 0.0           # secousse ponctuelle (jumpscare...)
        self.shake_time = 0.0
        self.flash_shake = 0.0         # tremblement de la lampe (sous-sol)
        self.noise_radius = 0.0
        self.noises = []               # événements sonores pour l'IA : dict(pos, radius, t)
        self.talk_times = []
        self.room = None
        self.murmur_timer = random.uniform(20, 35)
        self.breath_until = 0.0
        self.speed_mult = 1.0
        self.light_level = 0.0         # estimation de l'éclairage sur le joueur (pour l'IA)
        self.fov = settings["fov"]
        self.time = 0.0
        self.surface = "carrelage"
        self.pitch_offset = 0.0
        self.sink_jump = 0.0
        self.head = Entity(name="tete")
        self.rig = Entity(name="joueur")
        self.head.parent = self.rig
        self.on_zone_change = None
        self.zone = None
        self.stairs_id = None
        self.dark_stress = True
        self.hide_model = False        # spectateur en coopératif
        self.force_first_person = 0    # >0 : vue 1re personne imposée (appareil photo, cachette...)
        self.cam_attached = False
        self.cam_dist = 0.0            # distance effective (après collision), lissée
        self.cam_side = SHOULDER.get(settings["cam_epaule"], 0.42)
        self._build_viewmodel()
        self.model = CharacterModel(parent=self.rig, jacket=(0.42, 0.62, 0.52), pants=(0.34, 0.4, 0.58),
                                    skin=(0.84, 0.66, 0.54), hair=(0.12, 0.09, 0.07), flashlight=True, seed=1, emit=0.38)
        self.model.enabled = False
        # point d'ancrage du faisceau visible (cône) : main en 1re personne, lampe du modèle en 3e
        self.cone_anchor = Entity(parent=self.vm, position=(0.12, -0.1, 0.25))

    # ------------------------------------------------------------------
    # Modèle visible (mains + lampe torche)
    # ------------------------------------------------------------------
    def _build_viewmodel(self):
        self.vm = Entity(parent=camera, position=(0, 0, 0))
        self.vm.enabled = False
        self.hand_flash = Entity(parent=self.vm, position=(0.26, -0.24, 0.5), rotation=(-4, -6, 0))
        Entity(parent=self.hand_flash, model="cube", color=color.rgb32(30, 30, 34), scale=(0.055, 0.055, 0.2))
        Entity(parent=self.hand_flash, model="cube", color=color.rgb32(220, 200, 120), scale=(0.07, 0.07, 0.03), z=0.1)
        Entity(parent=self.hand_flash, model="cube", color=color.rgb32(150, 110, 90), scale=(0.075, 0.065, 0.08), z=-0.06, y=-0.01)
        Entity(parent=self.hand_flash, model="cube", color=color.rgb32(70, 60, 60), scale=(0.1, 0.09, 0.4), z=-0.34, y=-0.1)
        self.hand_phone = Entity(parent=self.vm, position=(0.0, -0.6, 0.5))
        self.flash_hand_y = -0.24

    def attach_camera(self):
        camera.parent = self.head
        camera.position = Vec3(0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)
        camera.fov = self.fov
        camera.clip_plane_near = 0.05
        camera.clip_plane_far = 90
        self.vm.parent = camera
        self.vm.enabled = True
        self.cam_attached = True
        self.cam_dist = 0.0
        self._apply_view()

    def detach_camera(self):
        self.vm.enabled = False
        self.cam_attached = False
        self.model.enabled = False

    # ------------------------------------------------------------------
    # Vue 1re / 3e personne
    # ------------------------------------------------------------------
    @property
    def third_person(self):
        return (settings["vue"] == "Troisième personne" and self.force_first_person <= 0
                and not self.frozen and not self.hide_model and self.cam_attached)

    def toggle_view(self):
        settings["vue"] = "Première personne" if settings["vue"] == "Troisième personne" else "Troisième personne"
        settings.save()
        self.cam_dist = 0.0
        self._apply_view()
        return settings["vue"]

    def _apply_view(self):
        tps = self.third_person
        self.model.enabled = tps
        self.vm.enabled = self.cam_attached and not tps
        anchor_parent = self.model.beam_anchor if tps else self.vm
        if self.cone_anchor.parent is not anchor_parent:
            self.cone_anchor.parent = anchor_parent
            self.cone_anchor.position = Vec3(0, 0, 0) if tps else Vec3(0.12, -0.1, 0.25)
            self.cone_anchor.rotation = Vec3(0, 0, 0)
        self._tps_state = tps

    def light_origin(self):
        """Origine du faisceau pour l'éclairage : lampe du personnage en 3e personne, sinon les yeux."""
        if self.third_person and self.model.enabled:
            try:
                return self.model.beam_anchor.world_position
            except Exception:
                pass
        return self.eye_pos

    def _segment_clear(self, a, b, pad=0.18):
        """Fraction t (0..1) jusqu'à laquelle le segment a->b est libre (murs, meubles, portes)."""
        h = self.house
        best = 1.0
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        mx, mz = (a[0] + b[0]) / 2, (a[2] + b[2]) / 2
        reach = math.hypot(dx, dz) / 2 + 0.6
        for c in list(h._near(mx, mz, reach)) + getattr(h, "glass_colliders", []):
            x0, y0, z0, x1, y1, z1 = c[0] - pad, c[1] - pad, c[2] - pad, c[3] + pad, c[4] + pad, c[5] + pad
            # le joueur peut être collé à un meuble bas : on ignore les colliders qui contiennent l'origine
            if x0 <= a[0] <= x1 and y0 <= a[1] <= y1 and z0 <= a[2] <= z1:
                continue
            tmin, tmax = 0.0, best
            ok = True
            for o, d, lo, hi in ((a[0], dx, x0, x1), (a[1], dy, y0, y1), (a[2], dz, z0, z1)):
                if abs(d) < 1e-9:
                    if o < lo or o > hi:
                        ok = False
                        break
                else:
                    t0, t1 = (lo - o) / d, (hi - o) / d
                    if t0 > t1:
                        t0, t1 = t1, t0
                    tmin, tmax = max(tmin, t0), min(tmax, t1)
                    if tmin > tmax:
                        ok = False
                        break
            if ok and tmin < best:
                best = max(0.0, tmin)
        return best

    def _third_person_camera(self, dt, bob_x, bob_y):
        """Caméra d'épaule façon GTA : derrière le personnage, décalée, amortie, sans traverser les murs."""
        side_target = SHOULDER.get(settings["cam_epaule"], 0.42)
        self.cam_side += (side_target - self.cam_side) * min(1.0, dt * 6.0)
        want = float(settings["cam_distance"]) * (0.8 if self.crouch_t > 0.5 else 1.0)
        if self.sprinting:
            want *= 1.12
        eye = self.eye_pos
        yr, pr = math.radians(self.yaw), math.radians(self.pitch)
        fwd = Vec3(math.sin(yr) * math.cos(pr), -math.sin(pr), math.cos(yr) * math.cos(pr))
        right = Vec3(math.cos(yr), 0, -math.sin(yr))
        up = Vec3(0, 1, 0)
        pivot = eye + right * self.cam_side + up * 0.18
        # le pivot d'épaule lui-même ne doit pas entrer dans un mur
        t_side = self._segment_clear(eye, pivot, 0.12)
        pivot = eye + (pivot - eye) * max(0.0, t_side - 0.05)
        target = pivot - fwd * want
        t = self._segment_clear(pivot, target, 0.16)
        dist = max(0.25, want * t - 0.08)
        # plafond / plancher du niveau courant
        lvl = self.house.level_at(self.pos[1])
        floor_y = LEVEL_Y[lvl] if lvl in LEVEL_Y else 0.0
        ceil_y = floor_y + LEVEL_CEIL.get(lvl, 2.9) - 0.2
        if lvl == 0 and self.zone == "dehors":
            ceil_y = floor_y + 30.0
        # rapproche plus vite qu'on ne recule (évite les clignotements à travers les murs)
        k = 18.0 if dist < self.cam_dist else (5.0 if settings["cam_lissage"] else 30.0)
        self.cam_dist += (dist - self.cam_dist) * min(1.0, dt * k)
        cam = pivot - fwd * self.cam_dist
        cam = Vec3(cam[0], max(floor_y + 0.25, min(ceil_y, cam[1])), cam[2])
        camera.world_position = cam + right * bob_x + Vec3(0, bob_y, 0)
        # le personnage devient translucide si la caméra est trop près (dans un couloir étroit)
        near = self.cam_dist < 0.95
        if near != getattr(self, "_model_hidden", False):
            self._model_hidden = near
            for e in self.model.root.children:
                e.enabled = not near
        return cam

    # ------------------------------------------------------------------
    # État
    # ------------------------------------------------------------------
    def place(self, pos, yaw=0.0, pitch=0.0):
        self.pos = Vec3(*pos)
        self.yaw = yaw
        self.pitch = pitch
        self.vy = 0
        self.vel = Vec3(0, 0, 0)
        self._sync()

    def _sync(self):
        self.rig.position = self.pos
        self.rig.rotation_y = self.yaw
        eye = EYE_STAND + (EYE_CROUCH - EYE_STAND) * self.crouch_t
        self.head.position = Vec3(0, eye, 0)
        self.head.rotation_x = self.pitch

    @property
    def eye_pos(self):
        eye = EYE_STAND + (EYE_CROUCH - EYE_STAND) * self.crouch_t
        return Vec3(self.pos[0], self.pos[1] + eye, self.pos[2])

    @property
    def forward(self):
        yr, pr = math.radians(self.yaw), math.radians(self.pitch)
        return Vec3(math.sin(yr) * math.cos(pr), -math.sin(pr), math.cos(yr) * math.cos(pr))

    @property
    def level(self):
        return self.house.level_at(self.pos[1])

    def add_stress(self, amount):
        self.stress = min(100.0, self.stress + amount)

    def relieve_stress(self, amount):
        self.stress = max(0.0, self.stress - amount)

    def shake(self, amplitude, duration=0.5):
        self.shake_amp = max(self.shake_amp, amplitude)
        self.shake_time = max(self.shake_time, duration)

    def damage(self, amount, cause="entity_contact"):
        if self.dead:
            return
        self.health = max(0.0, self.health - amount)
        self.shake(0.8, 0.5)
        self.add_stress(25)
        if self.health <= 0:
            self.kill(cause)

    def kill(self, cause="entity_contact"):
        if self.dead:
            return
        self.dead = True
        if self.on_death:
            self.on_death(cause)

    def revive(self):
        self.model.revive()
        self.dead = False
        self.health = 100.0
        self.stress = 20.0
        self.stamina = 100.0
        self.frozen = False

    def emit_noise(self, radius, pos=None, kind="step"):
        p = Vec3(*(pos if pos is not None else self.pos))
        self.noises.append(dict(pos=p, radius=radius, t=self.time, kind=kind))

    def _on_flash_toggle(self, on):
        sound.play("clic_lampe", 0.8)
        self.emit_noise(1.0, kind="click")

    # ------------------------------------------------------------------
    # Entrées ponctuelles (appelées par le game manager)
    # ------------------------------------------------------------------
    def on_key(self, key):
        if self.frozen or self.dead:
            return
        if key == settings.key("lampe"):
            self.flashlight.toggle()
        elif key == "scroll up":
            self.flashlight.adjust_zoom(0.1)
        elif key == "scroll down":
            self.flashlight.adjust_zoom(-0.1)
        elif key == settings.key("parler"):
            self.speak()
        elif key == settings.key("vue"):
            mode = self.toggle_view()
            return "vue:" + mode

    def speak(self):
        """Le joueur parle à voix haute (utile pour certaines paires d'assistance)."""
        line = random.choice(["Y'a quelqu'un ?", "Je suis là !", "Qui est là ?", "Parlez-moi..."])
        sound.speak(line, f0=105, speed=1.0, whisper=False, volume=0.8, channel="voice", speaker=gd.PLAYER_FIRST)
        self.emit_noise(13.0, kind="voix")
        self.talk_times.append(self.time)

    def recent_talk(self, window_s):
        return sum(1 for t in self.talk_times if self.time - t <= window_s)

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        if self.dead:
            return
        self._look(dt)
        self._move(dt)
        self._vitals(dt)
        self._effects(dt)
        self._viewmodel(dt)
        self._sync()
        self.noises = [n for n in self.noises if self.time - n["t"] < 2.5]
        sound.set_listener(self.eye_pos, self.yaw)

    def _look(self, dt):
        if self.frozen or not self.look_enabled or not mouse.locked:
            return
        sens = settings["sensibilite"] / 10.0 * 40.0
        inv = -1 if settings["inverser_y"] else 1
        dx, dy = mouse.velocity[0], mouse.velocity[1]
        self.yaw += dx * sens
        self.pitch -= dy * sens * inv
        self.pitch = max(-88.0, min(88.0, self.pitch))

    def _move(self, dt):
        h = self.house
        want_x = want_z = 0.0
        can = self.move_enabled and not self.frozen
        if can:
            if key_down("avancer"):
                want_z += 1
            if key_down("reculer"):
                want_z -= 1
            if key_down("droite"):
                want_x += 1
            if key_down("gauche"):
                want_x -= 1
        crouch_key = key_down("accroupir") and can
        if crouch_key != self.crouching:
            self.crouching = crouch_key
        target_c = 1.0 if self.crouching else 0.0
        self.crouch_t += (target_c - self.crouch_t) * min(1.0, dt * 9.0)
        moving = (want_x != 0 or want_z != 0)
        if self.stamina <= 0:
            self.sprint_locked = True
        elif self.stamina > 20:
            self.sprint_locked = False
        self.sprinting = bool(can and moving and held_keys["left shift"] and want_z > 0 and not self.crouching
                              and not self.phone_open and not self.sprint_locked)
        speed = config.SPRINT_SPEED if self.sprinting else config.WALK_SPEED
        if self.crouching:
            speed = config.CROUCH_SPEED
        if self.phone_open:
            speed *= 0.55
        speed *= self.speed_mult
        if self.stamina <= 0:
            speed *= 0.7
        if moving:
            n = math.hypot(want_x, want_z)
            want_x, want_z = want_x / n, want_z / n
        yr = math.radians(self.yaw)
        fx, fz = math.sin(yr), math.cos(yr)
        rx, rz = math.cos(yr), -math.sin(yr)
        tvx = (fx * want_z + rx * want_x) * speed
        tvz = (fz * want_z + rz * want_x) * speed
        acc = min(1.0, dt * 11.0)
        self.vel = Vec3(self.vel[0] + (tvx - self.vel[0]) * acc, 0, self.vel[2] + (tvz - self.vel[2]) * acc)
        self.speed = math.hypot(self.vel[0], self.vel[2])
        self.moving = self.speed > 0.4
        # collision horizontale
        height = config.PLAYER_CROUCH_HEIGHT if self.crouch_t > 0.5 else config.PLAYER_HEIGHT
        nx, nz = h.move(self.pos[0], self.pos[2], self.vel[0] * dt, self.vel[2] * dt, self.pos[1],
                        config.PLAYER_RADIUS, height)
        moved = math.hypot(nx - self.pos[0], nz - self.pos[2])
        x, z = nx, nz
        # saut
        if can and held_keys[settings.key("sauter")] and self.on_ground and not self.crouching:
            self.vy = config.JUMP_SPEED
            self.on_ground = False
            self.emit_noise(4.0, kind="saut")
        # gravité et sol
        y = self.pos[1]
        ground = h.ground_height(x, z, y, 0.55)
        if self.on_ground:
            if ground is None:
                self.on_ground = False
            else:
                # suit les rampes d'escalier en douceur
                dy = ground - y
                y += max(-0.08 - abs(self.speed) * dt * 2.0, min(0.08 + abs(self.speed) * dt * 2.0, dy)) if abs(dy) > 0.002 else dy
                self.vy = 0.0
                if ground - y > 0.2:
                    y = ground
        if not self.on_ground:
            self.vy -= config.GRAVITY * dt
            y += self.vy * dt
            if ground is not None and y <= ground and self.vy <= 0:
                if self.vy < -3.0:
                    self.emit_noise(6.0, kind="atterrissage")
                    sound.play(f"pas_{self.surface}_1", 1.0, 0.7)
                    self.shake(0.3, 0.2)
                y = ground
                self.on_ground = True
                self.vy = 0
            if y < -40:
                y = 0.0
                x, z = 7.0, 0.8
                self.on_ground = True
        self.pos = Vec3(x, y, z)
        # bruits de pas
        if self.on_ground and moved > 1e-4:
            self.step_dist += moved
            step_len = 1.25 if self.sprinting else 1.6 if not self.crouching else 1.2
            if self.step_dist >= step_len:
                self.step_dist = 0.0
                self._footstep()
            self.bob_phase += moved * (2.3 if self.sprinting else 2.0)
        # zone / pièce
        room = h.room_at(x, z, y)
        if room is not self.room:
            self.room = room
            if room is not None:
                self.state.rooms_visited.add(room.id)
                room.visited = True
        zone = h.zone_at(x, z, y)
        if zone != self.zone:
            self.zone = zone
            if self.on_zone_change:
                self.on_zone_change(zone)
        self._surface(room)
        # niveau d'escalier
        self.stairs_id = None
        for s in h.surfaces:
            if s.za is not None and s.yb != s.ya and s.x0 <= x <= s.x1 and min(s.za, s.zb) <= z <= max(s.za, s.zb) and abs(s.height(x, z) - y) < 0.3:
                self.stairs_id = s
                break

    def _surface(self, room):
        if room is None:
            self.surface = "beton"
            return
        f = room.floor
        self.surface = {"parquet": "parquet", "carrelage": "carrelage", "beton": "beton", "moquette": "moquette"}.get(f, "parquet")

    def _footstep(self):
        vol = 0.55 if self.sprinting else 0.28 if not self.crouching else 0.12
        rad = 8.5 if self.sprinting else 3.6 if not self.crouching else 1.2
        surf = self.surface
        i = random.randint(0, 2)
        pitch = random.uniform(0.92, 1.08)
        if self.stairs_id is not None:
            surf_name = "escalier"
            idx = int(max(0.0, min(1.0, (self.pos[1] - min(self.stairs_id.ya, self.stairs_id.yb)) /
                                  max(0.01, abs(self.stairs_id.yb - self.stairs_id.ya)))) * 16)
            if self.stairs_id.ya == 3.0 and self.stairs_id.yb == 6.0 and idx in (3, 7):
                sound.play("pas_escalier_fort", 0.9)
                self.emit_noise(15.0, kind="escalier")
                return
            sound.play(f"pas_{surf_name}_{i}", vol, pitch)
            self.emit_noise(max(rad, 4.0), kind="escalier")
            return
        sound.play(f"pas_{surf}_{i}", vol, pitch)
        # sur parquet : plus de bruit
        if surf == "parquet":
            rad *= 1.25
        self.emit_noise(rad, kind="pas")

    def _vitals(self, dt):
        # stamina
        if self.sprinting and self.moving:
            self.stamina = max(0.0, self.stamina - config.STAMINA_DRAIN * dt)
            self.stamina_delay = 1.2
        else:
            self.stamina_delay = max(0.0, self.stamina_delay - dt)
            if self.stamina_delay <= 0:
                self.stamina = min(100.0, self.stamina + config.STAMINA_REGEN * dt)
        # stress : décroît lentement, augmente dans le noir complet
        dark = not self.flashlight.on and self.light_level < 0.15
        if dark and self.dark_stress and self.state.act >= 1 and not self.phone_open:
            self.add_stress(1.6 * dt)
        decay = 0.9 if self.stress > 40 else 1.4
        if not dark:
            self.stress = max(0.0, self.stress - decay * dt)
        if self.flashlight.dead_timer > 0:
            self.add_stress(5.0 * dt)
        # batteries
        self.state.player_battery_light = self.flashlight.battery
        # respiration / battement de coeur
        heavy = self.stamina < 15 or (self.sprinting and self.stamina < 60) or self.stress > 70
        if heavy:
            sound.set_breath("heavy")
        elif self.stress > 35:
            sound.set_breath("calm")
        else:
            sound.set_breath(None)
        bpm = 0.0
        if self.stress > 30 or self.sprinting:
            bpm = 62 + self.stress * 0.85 + (18 if self.sprinting else 0)
        sound.set_heart(bpm)
        # murmures du joueur sous stress
        if self.stress > 55 and not self.frozen:
            self.murmur_timer -= dt
            if self.murmur_timer <= 0:
                self.murmur_timer = random.uniform(22, 40)
                sound.speak(random.choice(gd.MURMURS_STRESS), f0=100, speed=0.9, whisper=True, volume=0.7,
                            channel="voice", speaker=gd.PLAYER_FIRST)
        # lampe : zone, tremblement
        self.state.player_pos = [self.pos[0], self.pos[1], self.pos[2]]
        self.state.player_yaw = self.yaw

    def _effects(self, dt):
        # secousse de caméra : stress (léger), course (moyen), ponctuelle (fort)
        t = self.time
        amp = self.stress / 100.0 * 0.6
        if self.sprinting:
            amp += 0.35
        if self.stamina <= 0:
            amp += 0.3
        if self.shake_time > 0:
            self.shake_time -= dt
            amp += self.shake_amp * 2.5
            if self.shake_time <= 0:
                self.shake_amp = 0.0
        rx = (math.sin(t * 17.0) * 0.5 + math.sin(t * 7.3) * 0.5) * amp
        ry = (math.sin(t * 13.1 + 1.0) * 0.5 + math.sin(t * 5.1) * 0.5) * amp
        rz = math.sin(t * 9.0) * amp * 0.5
        bob_amp = 0.0
        if self.on_ground and self.moving and not self.phone_open:
            bob_amp = 0.032 if self.sprinting else 0.018 if not self.crouching else 0.01
        if not settings["bob_camera"]:
            bob_amp *= 0.25
        bob_y = math.sin(self.bob_phase * 2.0) * bob_amp
        bob_x = math.sin(self.bob_phase) * bob_amp * 0.6
        if self.third_person != getattr(self, "_tps_state", None):
            self._apply_view()
        if self.third_person:
            self._third_person_camera(dt, bob_x * 0.5, bob_y * 0.5)
            camera.rotation = Vec3(rx * 0.6, ry * 0.6, rz * 0.4)
            self.model.animate(dt, self.speed, self.crouch_t, self.pitch, self.sprinting,
                               self.flashlight.on and not self.phone_open, not self.on_ground)
        else:
            camera.position = Vec3(bob_x, bob_y, 0)
            camera.rotation = Vec3(rx, ry, rz)
        # FOV : léger élargissement en course
        target_fov = self.fov + (6 if self.sprinting else 0) - self.stress * 0.05
        camera.fov += (target_fov - camera.fov) * min(1.0, dt * 6.0)

    def _viewmodel(self, dt):
        t = self.time
        sway_x = math.sin(self.bob_phase) * 0.006 if self.moving else math.sin(t * 1.3) * 0.0015
        sway_y = abs(math.sin(self.bob_phase)) * 0.008 if self.moving else math.sin(t * 1.1) * 0.0015
        tremble = self.flash_shake * math.sin(t * 40.0) * 0.01
        target_y = -0.24 if not self.phone_open else -0.7
        self.flash_hand_y += (target_y - self.flash_hand_y) * min(1.0, dt * 8.0)
        self.hand_flash.position = Vec3(0.26 + sway_x + tremble, self.flash_hand_y + sway_y, 0.5)
        if self.third_person:
            self.vm.enabled = False

    # ------------------------------------------------------------------
    # Utilitaires pour l'IA
    # ------------------------------------------------------------------
    def visibility(self):
        """0..1 : à quel point le joueur est visible dans l'obscurité."""
        v = 0.25
        if self.flashlight.on:
            v += 0.55
        if self.phone_open:
            v += 0.15
        if self.moving:
            v += 0.1
        if self.crouching:
            v *= 0.6
        return min(1.0, v + self.light_level * 0.4)
