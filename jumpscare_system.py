"""Jumpscares : visuel + audio synchronisés.

Séquence : flash blanc (0,05 s) → le Livreur (modèle 3D animé, livreur_model.py) se jette sur la caméra
→ écran noir + bruit sourd. Le Rampant et l'Imposteur gardent leurs images.
« Réduire les jumpscares » atténue les flashes et le volume des stingers.
"""
import math
import random

from ursina import Entity, camera, color, invoke, destroy

from config import settings
from sound_engine import engine as sound
from texture_generator import textures
from ui_widgets import rgb


class JumpscareSystem:
    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-9, enabled=False)
        self.bg = Entity(parent=self.root, model="quad", scale=(2.2, 1.2), color=color.black, z=1)
        self.items = []
        self.active = False
        self.t = 0.0
        self.shake_amp = 0.0
        self.kind = None
        self.on_done = None
        self.duration = 0.5
        self.lunging = False
        self.lunge = None                  # modèle 3D du livreur, construit une fois (pas d'à-coup au moment du cri)
        self.lunge_bg = None
        self.extra = []
        try:
            self._build_lunge()
        except Exception:
            self.lunge = None

    # --- le Livreur qui se jette sur la caméra -------------------------------
    def _build_lunge(self):
        """Modèle 3D accroché à la caméra. Un fond noir écrit sa profondeur sans test (il efface celle du décor)
        puis le modèle est dessiné par-dessus : jamais caché par un mur, même collé à la caméra."""
        from livreur_model import LivreurModel
        self.lunge_root = Entity(parent=camera, enabled=False)
        self.lunge_bg = Entity(parent=self.lunge_root, model="quad", color=color.rgb32(4, 3, 3), position=(0, 0, 2.2),
                               scale=(9, 6))
        self.lunge_bg.set_bin("fixed", 40)
        self.lunge_bg.set_depth_test(False)
        self.lunge_bg.set_depth_write(True)
        self.lunge_bg.set_light_off()
        self.lunge = LivreurModel(self.lunge_root)
        if self.lunge.shadow is not None:
            self.lunge.shadow.enabled = False
        self.lunge.root.rotation_y = 180                  # face à la caméra
        for np_ in self.lunge.root.find_all_matches("**/+GeomNode"):
            np_.set_bin("fixed", 41)
        # deux silhouettes de plus pour « Les Multiples » (mêmes modèles, plus loin, dans l'ombre)
        for x in (-1.0, 1.0):
            m = LivreurModel(self.lunge_root)
            if m.shadow is not None:
                m.shadow.enabled = False
            m.root.rotation_y = 180 + math.degrees(math.atan2(x, 2.4))    # tournés vers la caméra
            m.root.position = (x, -1.85, 2.4)
            m.root.setColorScale(0.35, 0.35, 0.38, 1)
            for np_ in m.root.find_all_matches("**/+GeomNode"):
                np_.set_bin("fixed", 41)
            m.root.enabled = False
            self.extra.append(m)

    def _place_lunge(self, dist):
        """Recale le modèle pour que sa tête soit au centre de l'écran, à `dist` mètres de la caméra."""
        m = self.lunge
        hp = m.head.get_pos(self.lunge_root)
        cur = m.root.position
        target = (0.0, -0.02, dist)
        m.root.position = (cur[0] + target[0] - hp[0], cur[1] + target[1] - (hp[1] + 0.13), cur[2] + target[2] - hp[2])

    def _clear(self):
        for e in self.items:
            destroy(e)
        self.items = []

    def _add(self, tex, pos, scale, col=color.white, rot=0.0):
        e = Entity(parent=self.root, model="quad", texture=textures.get(tex) if tex else None, position=pos, scale=scale,
                   color=col, rotation_z=rot, z=0)
        try:
            from panda3d.core import TransparencyAttrib
            e.setTransparency(TransparencyAttrib.M_alpha)
        except Exception:
            pass
        self.items.append(e)
        return e

    def trigger(self, kind="generic", on_done=None, fatal=True):
        """Lance le jumpscare. kind : silencieux | rampant | multiple | imposteur | porte | generic.

        fatal=False : contact encaissé (difficulté) : pas de bruit sourd de mort à la fin."""
        if self.active:
            return
        self.active = True
        self.fatal = fatal
        self.kind = kind
        self.on_done = on_done
        self.t = 0.0
        reduce = settings["reduire_jumpscares"]
        g = self.game
        g.player.frozen = True
        g.ui.hud.hide()                          # rien ne doit s'afficher par-dessus le visage
        g.effects.flash(1.0, 0.05 if not reduce else 0.2)
        g.effects.chroma_burst(1.5)
        g.effects.distort_burst(0.6)
        g.player.shake(1.0, 0.6)
        vol = 0.5 if reduce else 1.0
        sound.play("stinger_jumpscare", vol, channel="sfx")
        sound.play("cri", 0.7 * vol, channel="sfx")
        self._clear()
        self.root.enabled = True
        self.bg.color = color.rgba32(0, 0, 0, 0)
        self.duration = 0.5 if not reduce else 0.35
        self.lunging = self.lunge is not None and kind in ("silencieux", "multiple", "porte", "generic", "base")
        if self.lunging:
            self.duration = 0.85 if not reduce else 0.5
            self.lunge_root.enabled = True
            self.lunge.root.position = (0, 0, 0)
            self.lunge.state = "chase"
            self.lunge.mouth_open = 1.0
            self.lunge.eye_level = 1.0
            self.lunge.look_target = camera.world_position              # le visage fixe le joueur
            for _ in range(20):                              # pose de poursuite, regard sur le joueur, dès la 1re image
                self.lunge.animate(1 / 30, 3.0, True, "chase")
            self._place_lunge(1.6 if not reduce else 2.2)
            for m in self.extra:
                m.root.enabled = kind == "multiple"
        elif kind == "rampant":
            self._add("silhouette", (0, 0.35), (1.9, 1.0), rgb(10, 8, 8), rot=180)
            self._add("mains", (0, 0.1), (1.3, 1.3), rgb(255, 255, 255))
        elif kind == "multiple":
            self._add("silhouette", (-0.5, -0.05), (0.9, 1.2), rgb(12, 12, 14))
            self._add("silhouette", (0.5, -0.05), (0.9, 1.2), rgb(12, 12, 14))
            self._add("silhouette", (0, 0), (1.3, 1.6), rgb(4, 4, 6))
        elif kind == "imposteur":
            self._add("visage_flou", (0, 0.05), (1.3, 1.3), color.white)
        elif kind == "porte":
            self._add(None, (0, 0), (0.9, 1.15), rgb(70, 40, 24))
            self._add(None, (0, 0), (0.75, 1.05), rgb(2, 2, 2))
            self._add("silhouette", (0, -0.05), (0.8, 1.0), rgb(12, 12, 14))
        else:
            self._add("silhouette", (0, 0), (1.4, 1.4), rgb(10, 10, 12))
        invoke(self._finish, delay=self.duration + 0.05)

    def update(self, dt):
        if not self.active:
            return
        self.t += dt
        if self.lunging:
            m = self.lunge
            reduce = settings["reduire_jumpscares"]
            m.look_target = camera.world_position
            m.animate(dt, 3.0, True, "chase")
            m.mouth.scale_y = 3.4 + math.sin(self.t * 38) * 0.5            # mâchoire grande ouverte, qui tremble
            m.head.rotation_z += random.uniform(-9, 9)                     # tête qui tressaute
            # la tête fonce sur la caméra (0,12 s) puis reste collée en tremblant
            k = min(1.0, self.t / 0.12)
            far, near = (1.8, 0.5) if not reduce else (2.4, 0.9)
            self._place_lunge(far + (near - far) * (1 - (1 - k) ** 3))
            if self.t > 0.12:
                m.root.x += random.uniform(-0.012, 0.012)
                m.root.y += random.uniform(-0.012, 0.012)
            for e in m.eyes:
                e.scale = 2.2 if random.random() > 0.15 else 0.4
            for x in self.extra:
                if x.root.enabled:
                    x.look_target = camera.world_position
                    x.animate(dt, 1.5, True, "chase")
        for e in self.items:
            e.x += random.uniform(-0.006, 0.006)
            e.y += random.uniform(-0.006, 0.006)
            e.scale *= 1.0 + dt * 0.5

    def _finish(self):
        self._clear()
        if self.lunge is not None:
            self.lunge_root.enabled = False
            self.lunging = False
        self.root.enabled = False
        self.active = False
        if getattr(self, "fatal", True):
            sound.play("sourd_mort", 0.9, channel="sfx")
        cb, self.on_done = self.on_done, None
        if cb:
            cb()

    # --- L'Imposteur : le sac s'ouvre sur un noir infini ---------------------
    def bag_sequence(self, ai, on_done=None):
        g = self.game
        p = g.player
        g.player.frozen = True
        g.player.phone_open = False
        if g.phone.is_open:
            g.phone.close()
        self.bag_t = 0.0
        self._bag_done = on_done
        self._bag_ai = ai
        # le joueur regarde le sac
        dx, dz = ai.pos[0] - p.pos[0], ai.pos[2] - p.pos[2]
        self._bag_yaw = math.degrees(math.atan2(dx, dz))
        self._bag_start_yaw = p.yaw
        self._bag_active = True
        if hasattr(ai.puppets[0], "bag_front"):
            ai.puppets[0].bag_front.enabled = True
        self.bag_circle = Entity(parent=camera.ui, model="circle", color=color.black, scale=0.0, z=-8)

    def update_bag(self, dt):
        if not getattr(self, "_bag_active", False):
            return
        self.bag_t += dt
        p = self.game.player
        t = min(1.0, self.bag_t / 0.8)
        dy = (self._bag_yaw - self._bag_start_yaw + 180) % 360 - 180
        p.yaw = self._bag_start_yaw + dy * t
        p.pitch += (22.0 - p.pitch) * min(1.0, dt * 4.0)
        ai = self._bag_ai
        if self.bag_t > 1.6:
            self.bag_circle.scale = (self.bag_t - 1.6) * 3.2
            self.bag_circle.scale = (self.bag_circle.scale_x, self.bag_circle.scale_x)
        if self.bag_t > 3.0:
            self._bag_active = False
            destroy(self.bag_circle)
            if hasattr(ai.puppets[0], "bag_front"):
                ai.puppets[0].bag_front.enabled = False
            cb, self._bag_done = self._bag_done, None
            self.trigger("imposteur", on_done=cb)
