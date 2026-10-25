"""Moteur de cinématiques : pistes de caméra, plans successifs, sous-titres, bandes noires, fondus.

Un plan (`Shot`) construit sa propre mise en scène (géométrie, lumières, sons), pilote la
caméra via une `CameraTrack` et se nettoie à la fin. Le moteur enchaîne les plans avec des
fondus au noir et permet de passer la séquence (Échap / Espace maintenus).
"""

from ursina import Entity, Vec3, camera, color, Text, scene, destroy



def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class CameraTrack:
    """Interpolation de mouvements de caméra par images-clés.

    keys : liste de (t, (x,y,z), (pitch,yaw,roll), fov).
    """

    def __init__(self, keys, ease=True):
        self.keys = sorted(keys, key=lambda k: k[0])
        self.ease = ease

    def at(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return Vec3(*ks[0][1]), Vec3(*ks[0][2]), ks[0][3]
        if t >= ks[-1][0]:
            return Vec3(*ks[-1][1]), Vec3(*ks[-1][2]), ks[-1][3]
        for a, b in zip(ks, ks[1:]):
            if a[0] <= t <= b[0]:
                u = (t - a[0]) / max(1e-6, b[0] - a[0])
                if self.ease:
                    u = smooth(u)
                pa, pb = Vec3(*a[1]), Vec3(*b[1])
                ra, rb = Vec3(*a[2]), Vec3(*b[2])
                return pa + (pb - pa) * u, ra + (rb - ra) * u, a[3] + (b[3] - a[3]) * u
        return Vec3(*ks[-1][1]), Vec3(*ks[-1][2]), ks[-1][3]


class Shot:
    """Plan de cinématique (à surcharger)."""
    duration = 5.0
    fade_in = 0.8
    fade_out = 0.8
    zone = "rdc"
    show_house = False

    def __init__(self, game):
        self.game = game
        self.t = 0.0
        self.track = None
        self.events = []      # (temps, callable)
        self._fired = set()
        self.lights = []
        self.nodes = []       # entités à détruire

    def setup(self):
        pass

    def teardown(self):
        for n in self.nodes:
            try:
                destroy(n)
            except Exception:
                pass
        self.nodes = []

    def update(self, dt):
        pass

    def fire_events(self):
        for i, (tt, fn) in enumerate(self.events):
            if self.t >= tt and i not in self._fired:
                self._fired.add(i)
                fn()


class CinematicEngine:
    def __init__(self, game):
        self.game = game
        self.shots = []
        self.index = -1
        self.shot = None
        self.playing = False
        self.on_done = None
        self.skip_hold = 0.0
        self.root = Entity(parent=camera.ui, z=-6, enabled=False)
        self.bar_top = Entity(parent=self.root, model="quad", color=color.black, scale=(2.4, 0.14), position=(0, 0.5 - 0.07 + 0.0), z=0)
        self.bar_bot = Entity(parent=self.root, model="quad", color=color.black, scale=(2.4, 0.14), position=(0, -0.5 + 0.07), z=0)
        self.caption = Text(parent=self.root, text="", origin=(0, 0), position=(0, -0.32), scale=1.6, color=color.rgba32(255, 255, 255, 0), z=-1)
        self.caption2 = Text(parent=self.root, text="", origin=(0, 0), position=(0, -0.37), scale=1.1, color=color.rgba32(255, 255, 255, 0), z=-1)
        self.title = Text(parent=self.root, text="", origin=(0, 0), position=(0, 0.02), scale=5.0, color=color.rgba32(255, 255, 255, 0), z=-1)
        self.hint = Text(parent=self.root, text="Maintenez Échap pour passer", origin=(0.5, 0.5), position=(0.82, -0.44), scale=0.7,
                         color=color.rgba32(200, 200, 200, 120), z=-1)
        self._cap = []         # [(texte, t0, t1, ligne)]
        self.clock = 0.0
        self._skipping = False
        self.cine_lights = []

    # --- légendes -------------------------------------------------------
    def add_caption(self, text, t0, t1, line=1):
        self._cap.append((text, t0, t1, line))

    def show_title(self, text, duration=2.0):
        self.title.text = text
        self.title_t = (self.clock, duration)

    # --- lecture --------------------------------------------------------
    def play(self, shots, on_done=None):
        self.shots = shots
        self.index = -1
        self.on_done = on_done
        self.playing = True
        self.root.enabled = True
        self._skipping = False
        self.game.player.frozen = True
        self.game.player.detach_camera()
        camera.parent = scene
        self.game.effects.set_fade(1.0)
        self._next()

    def _next(self):
        if self.shot is not None:
            self.shot.teardown()
            self.cine_lights = []
            self.game.lighting.lights = self.cine_lights
        self.index += 1
        if self.index >= len(self.shots):
            self._finish()
            return
        self.shot = self.shots[self.index]
        self.shot.t = 0.0
        self._cap = []
        self.cine_lights = self.shot.lights
        self.game.lighting.lights = self.cine_lights
        self.game.lighting.set_zone(self.shot.zone, instant=True)
        self.game.house.set_level_visibility(0 if self.shot.show_house else 9)
        self.game.house.exterior_root.enabled = self.shot.show_house
        self.shot.setup()
        self.game.effects.fade_to(0.0, self.shot.fade_in)
        camera.clip_plane_far = 160

    def _finish(self):
        self.playing = False
        self.root.enabled = False
        self.shot = None
        self._skipping = False
        cb, self.on_done = self.on_done, None
        if cb:
            cb()

    def skip(self):
        if not self.playing:
            return
        if self.shot is not None:
            self.shot.teardown()
        self.shot = None
        self.index = len(self.shots)
        self._finish()

    def update(self, dt):
        if not self.playing:
            return
        from ursina import held_keys
        if held_keys["escape"] or held_keys["space"]:
            self.skip_hold += dt
            self.hint.color = color.rgba32(255, 255, 255, 220)
            if self.skip_hold > 1.2:
                self.skip()
                return
        else:
            self.skip_hold = max(0.0, self.skip_hold - dt * 2)
            self.hint.color = color.rgba32(200, 200, 200, 110)
        self.clock += dt
        s = self.shot
        if s is None:
            return
        s.t += dt
        s.fire_events()
        s.update(dt)
        # caméra
        if s.track is not None:
            pos, rot, fov = s.track.at(s.t)
            camera.world_position = pos
            camera.world_rotation = rot
            camera.fov = fov
        # sous-titres
        self._update_captions(s.t)
        # fondu de sortie
        remaining = s.duration - s.t
        if remaining <= s.fade_out and self.game.effects.fade_target != 1.0 and self.index < len(self.shots) - 1:
            self.game.effects.fade_to(1.0, max(0.05, remaining))
        if s.t >= s.duration:
            self._next()

    def _update_captions(self, t):
        for (text, t0, t1, line) in self._cap:
            pass
        lines = {1: ("", 0.0), 2: ("", 0.0)}
        for (text, t0, t1, line) in self._cap:
            if t0 <= t <= t1:
                a = min(1.0, (t - t0) / 0.8, (t1 - t) / 0.8)
                lines[line] = (text, max(0.0, a))
        self.caption.text = lines[1][0]
        self.caption.color = color.rgba32(255, 255, 255, int(255 * lines[1][1]))
        self.caption2.text = lines[2][0]
        self.caption2.color = color.rgba32(210, 210, 215, int(255 * lines[2][1]))
        tt = getattr(self, "title_t", None)
        if tt is not None:
            u = (self.clock - tt[0]) / tt[1]
            if 0 <= u <= 1:
                self.title.color = color.rgba32(255, 255, 255, int(255 * min(1.0, u * 6, (1 - u) * 6)))
            else:
                self.title.color = color.rgba32(255, 255, 255, 0)
