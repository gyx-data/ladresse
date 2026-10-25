"""Machine à états du jeu : chargement, menu, cinématique, gameplay, pause, mort, fins.

Le `GameManager` possède tous les systèmes et fait le lien entre eux (quêtes, assistance,
téléphone, entité, événements de la maison, interface...).
"""
import math
import random

from ursina import Entity, Vec2, Vec3, camera, mouse, scene, color, invoke, window, application, destroy

import config
import game_data as gd
from config import settings
from assistance_system import AssistanceSystem
from cinematic_engine import CinematicEngine
from effects import EffectsManager, PhotoSystem, SkyDome, FlashlightCone
from entity_ai import EntityAI
from house_events import HouseEvents
from house_generator import House
from interaction_system import InteractionSystem
from intro_cinematic import build_intro, PLAYER_START

OUTSIDE_START = (11.2, 0.0, -10.4)      # à côté de la voiture garée, rue des Lilas
from inventory import Inventory, InventoryPanel
from jumpscare_system import JumpscareSystem
from lighting_system import LightingManager, LightSource
from neighborhood import Neighborhood
from achievements import Achievements
from room_builder import MeshBuilder
from particle_system import ParticleManager
from phone_system import PhoneUI
from player import Player
from quest_system import QuestSystem
from save_system import SaveSystem
from settings_menu import SettingsMenu, apply_settings
from shaders import shader_state
from sound_engine import engine as sound
from texture_generator import textures
from timers import TimerQueue
from ui_manager import UIManager, LoadingScreen
from ui_widgets import rect, label, rgb
from world_state import WorldState


class GameManager:
    def __init__(self, app):
        self.app = app
        self.state = WorldState()
        self.timers = TimerQueue()
        self.saves = SaveSystem()
        self.mode = "loading"          # loading | menu | lobby | cinematic | playing | gameover | ending
        self.paused = False
        self.playtime = 0.0
        self.is_multiplayer = False
        self.mp = None
        self.neighborhood = None
        self.camera_mode = False
        self.house = None
        self.player = None
        self.entity = None
        self.events = None
        self.countdown_flicker = False
        self._flicker_t = 0.0
        self._death_kind = None
        self.loading = LoadingScreen()
        self._boot_gen = self._boot()
        self._frame = 0
        self.menu_t = 0.0
        self._menu_cam = None
        self.glow_quads = []
        self.menu_silhouette = None
        self.phone_light = None
        self.last_notification_t = 0.0
        self.viewfinder = None
        self.ending_d_t = None
        self.ending_active = False
        self._level_shown = None
        self.settings_menu = None

    # ------------------------------------------------------------------
    @property
    def menu_active(self):
        return self.mode in ("menu", "lobby", "loading")

    @property
    def net(self):
        return self.mp.client if (self.mp is not None and self.mp.connected) else None

    # ------------------------------------------------------------------
    # Chargement (génération procédurale des assets, découpée par frames)
    # ------------------------------------------------------------------
    def _boot(self):
        self.loading.set(0.0, "Génération des textures...")
        yield
        for i, total, name in textures.iter_generate():
            self.loading.set(0.25 * i / total, f"Textures : {name}")
            if i % 4 == 0:
                yield
        for i, total, name in sound.iter_generate():
            self.loading.set(0.25 + 0.15 * i / total, f"Sons : {name}")
            if i % 8 == 0:
                yield
        sound.subtitle_cb = self._subtitle
        self.loading.set(0.42, "Construction de la maison...")
        yield
        self._build_world(initial=True)
        self.loading.set(0.85, "Mise en place des systèmes...")
        yield
        self._build_systems()
        shader_state.enable_post(tuple(window.size))
        shader_state.push()
        self.loading.set(1.0, "Terminé")
        yield
        self.loading.hide()
        self.show_menu()

    def _build_world(self, initial=False):
        """Construit (ou reconstruit) la maison et tout ce qui en dépend."""
        if self.house is not None:
            self._destroy_world()
        self.house = House()
        for _ in self.house.build():
            pass
        self.house.on_door_sound = self._door_sound
        sound.occluder = lambda a, b: self.house.wall_count(a, b)

    def _destroy_world(self):
        try:
            if self.events:
                self.events.stop_ambience()
        except Exception:
            pass
        h = self.house
        for root in list(h.level_roots.values()) + [h.exterior_root]:
            try:
                destroy(root)
            except Exception:
                pass
        for e in getattr(self, "_extra_world", []):
            try:
                destroy(e)
            except Exception:
                pass
        self._extra_world = []

    def _build_systems(self):
        self.lighting = LightingManager()
        self.lighting.lights = self.house.lights
        self.effects = EffectsManager(self)
        self.inventory = Inventory(self.state)
        self.interactions = InteractionSystem(self.house)
        self.player = Player(self.house, self.state)
        self.player.on_death = self._on_death
        self.player.on_zone_change = lambda z: self.events.on_zone_change(z) if self.events else None
        self.ui = UIManager(self)
        self.inv_panel = InventoryPanel(self.inventory, self)
        self.quests = QuestSystem(self)
        self.assistance = AssistanceSystem(self)
        self.phone = PhoneUI(self)
        self.entity = EntityAI(self)
        self.jumpscare = JumpscareSystem(self)
        self.photo = PhotoSystem(self)
        self.cine = CinematicEngine(self)
        self.events = HouseEvents(self)
        self.events.setup()
        self.particles = ParticleManager(self)
        self.sky = SkyDome()
        self.fl_cone = FlashlightCone(self.player.cone_anchor)
        self.settings_menu = SettingsMenu(self)
        self.achievements = Achievements(self)
        self.phone_light = LightSource((0, 0, 0), (0.7, 0.8, 1.0), 0.0, 4.5, kind="static", enabled=False, name="telephone")
        self.house.lights.append(self.phone_light)
        self.viewfinder = self._build_viewfinder()
        self.player.fov = settings["fov"]
        apply_settings(self)
        self._build_menu_extras()

    def _build_viewfinder(self):
        root = Entity(parent=camera.ui, z=-7, enabled=False)
        for (x, y, rz) in ((-0.75, 0.4, 0), (0.75, 0.4, 90), (0.75, -0.4, 180), (-0.75, -0.4, 270)):
            rect(root, x, y, 0.12, 0.006, rgb(255, 255, 255, 220), z=0)
            rect(root, x + (0.057 if x < 0 else -0.057), y + (-0.057 if y > 0 else 0.057), 0.006, 0.12, rgb(255, 255, 255, 220), z=0)
        label(root, "Clic gauche / [E] : photo      [T] : quitter", 0, -0.45, 0.8, rgb(255, 255, 255, 200), z=0)
        rect(root, 0, 0, 0.012, 0.012, rgb(255, 80, 80, 200), z=0)
        label(root, "REC", -0.72, 0.43, 0.7, rgb(255, 60, 60), z=0)
        return root

    def _build_menu_extras(self):
        # silhouette derrière la fenêtre du grenier (à peine visible)
        b = __import__("room_builder").MeshBuilder("sil_menu")
        b.quad("silhouette", (-0.35, 0, 0), (0.35, 0, 0), (0.35, 1.5, 0), (-0.35, 1.5, 0), (0, 0, -1), (0.5, 0.5, 0.55), tile=1.5)
        self.menu_silhouette = Entity(position=(8.0, 6.55, 0.45))
        for e in b.build(parent=self.menu_silhouette, emit=0.0):
            pass
        self.menu_silhouette.enabled = False
        # lueurs de fenêtres (menu)
        wins = [(1.5, 1.4, -0.16), (12.0, 1.4, -0.16), (2.0, 4.4, -0.16), (7.0, 4.4, -0.16)]
        for (x, y, z) in wins:
            e = Entity(model="quad", position=(x, y, z), scale=(1.0, 1.0), color=color.rgba32(255, 200, 120, 0), rotation_y=0)
            e.enabled = False
            self.glow_quads.append(e)
        self._extra_world = list(self.glow_quads) + [self.menu_silhouette]

    # ------------------------------------------------------------------
    # Menu principal (maison sous la pluie)
    # ------------------------------------------------------------------
    def show_menu(self):
        self.mode = "menu"
        self.loading.hide()
        self.ending_active = False
        self.paused = False
        self.timers.clear()
        sound.stop_all()
        self.ui.hud.hide()
        self.ui.pause.hide()
        self.ui.gameover.hide()
        self.ui.ending.stop()
        self.viewfinder.enabled = False
        self.phone.close()
        self.player.detach_camera()
        self.entity.despawn()
        self.effects.menu_mode = True
        self.effects.set_fade(0.0)
        self.effects.set_tint(None)
        self.lighting.lights = self.house.lights
        self.lighting.set_zone("dehors", instant=True)
        self.house.set_level_visibility(0)
        camera.parent = scene
        camera.fov = 52
        camera.clip_plane_far = 160
        self.particles.rain.enabled = True
        self.particles.dust.parent.enabled = False
        lamp = self.house.anchors["lamp_light"]
        lamp.kind = "flicker"
        lamp.enabled = True
        self.menu_silhouette.enabled = True
        self.player.flashlight.on = False
        self.lighting.ambient_boost = 0.0
        self.ui.menu.show()
        self.menu_loops = [sound.loop("pluie", 0.5, channel="music", fade_in=2.0),
                           sound.loop("drone", 0.35, channel="music", fade_in=3.0),
                           sound.loop("vent", 0.2, channel="music", fade_in=3.0)]
        self.menu_t = 0.0
        self.set_mouse(free=True)

    def menu_window_flicker(self):
        """Les lumières de la maison s'allument et s'éteignent brièvement."""
        for q in self.glow_quads:
            q.enabled = True
        seq = [(0.0, 150), (0.25, 0), (0.45, 120), (0.7, 0)]
        for t, a in seq:
            invoke(self._set_glow, a, delay=t)
        invoke(self._glow_off, delay=0.9)
        sound.play("craquement_bois", 0.3, channel="music")

    def _set_glow(self, a):
        for q in self.glow_quads:
            q.color = color.rgba32(255, 190, 110, a)

    def _glow_off(self):
        for q in self.glow_quads:
            q.enabled = False

    def _update_menu(self, dt):
        self.menu_t += dt
        t = self.menu_t
        x = 8.0 + math.sin(t * 0.08) * 6.5
        camera.world_position = Vec3(x, 2.6 + math.sin(t * 0.13) * 0.3, -21.0)
        camera.look_at(Vec3(8.0 + math.sin(t * 0.08) * 1.5, 4.6, 0.0))
        self.sky.set_enabled(True)
        self.sky.update()
        shader_state.cam_pos = camera.world_position
        shader_state.fl_params = [0.8, 0.9, 0.0, 10]
        self.lighting.update(dt, camera.world_position)
        self.effects.update(dt)
        self.particles.rain.center = Vec3(8, 4, -5)
        self.particles.rain.update(dt, camera.world_position)
        self.ui.update(dt)
        sound.set_listener(camera.world_position, camera.world_rotation_y)
        sound.update(dt)
        # la silhouette de la fenêtre du grenier apparaît par intermittence
        self.menu_silhouette.enabled = (math.sin(t * 0.35) > -0.2)

    # ------------------------------------------------------------------
    # Nouvelle partie / continuer
    # ------------------------------------------------------------------
    def reset_game_objects(self):
        self.state.reset()
        self.quests.reset()
        self.assistance.reset()
        self.timers.clear()
        self.playtime = 0.0
        self.countdown_flicker = False
        self.ending_d_t = None
        self.inv_panel.hide()

    def _fresh_world(self):
        """Reconstruit toute la maison et les systèmes qui la référencent."""
        if self.neighborhood is not None:
            self.neighborhood.destroy()
            self.neighborhood = None
        self.phone.close()
        self.entity.despawn()
        self._build_world()
        self.interactions = InteractionSystem(self.house)
        self.player.house = self.house
        self.lighting.lights = self.house.lights
        self.house.lights.append(self.phone_light)
        self.entity = EntityAI(self)
        self.events = HouseEvents(self)
        self.events.setup()
        self.particles = ParticleManager(self)
        self._build_menu_extras()
        self.house.on_door_sound = self._door_sound

    def new_game(self):
        self._stop_menu()
        self.reset_game_objects()
        self._fresh_world()
        self.player.revive()
        self.player.stress = 0
        self.player.flashlight.battery = 100.0
        self.player.flashlight.on = False
        self.phone.model.battery = 100.0
        self.phone.model.dead = False
        self.mode = "cinematic"
        self.effects.menu_mode = False
        self.house.anchors["lamp_light"].kind = "flicker"
        self.ui.menu.hide()
        self.cine.play(build_intro(self), on_done=lambda: self.begin_play(fresh=True))

    def continue_game(self):
        try:
            self._continue_game()
        except Exception:
            import crash_handler
            crash_handler.log_exception("continue_game")
            self.say("Sauvegarde illisible : nouvelle partie.", 4.0)
            self.new_game()

    def _continue_game(self):
        data = self.saves.load()
        if data is None:
            return
        self._stop_menu()
        self.reset_game_objects()
        self._fresh_world()
        self.state.from_dict(data["state"])
        self.quests.from_dict(data.get("quests", {}))
        self.playtime = data.get("playtime", 0.0)
        self.assistance.restore(data.get("assistance", {}))
        self.player.revive()
        self.player.flashlight.battery = self.state.player_battery_light
        self.phone.model.battery = self.state.player_battery_phone
        self.phone.model.dead = self.phone.model.battery <= 0
        for did, op in data.get("doors", {}).items():
            d = self.house.doors.get(did)
            if d is not None and op:
                d.open(silent=True)
        # messages
        for conv, sender, text, t in self.state.messages:
            if conv in self.phone.model.conversations:
                self.phone.model.conversations[conv]["msgs"].append(__import__("phone_system").Message(sender, text, t))
        self.events.apply_saved_state()
        self.ui.menu.hide()
        self.mode = "cinematic"
        self.effects.menu_mode = False
        self.begin_play(fresh=False, data=data)

    def _stop_menu(self):
        for h in getattr(self, "menu_loops", []):
            if h:
                h.stop()
        self.menu_loops = []
        sound.stop_all()
        self.menu_silhouette.enabled = False

    def begin_play(self, fresh=True, data=None):
        """Le joueur prend le contrôle."""
        self.mode = "playing"
        self.paused = False
        self.camera_mode = False
        self.player.force_first_person = 0
        self.ui.menu.hide()
        p = self.player
        self.effects.menu_mode = False
        self.effects.set_fade(0.0)
        self.effects.grain_mult = 1.0
        self.house.exterior_root.enabled = False
        self.house.set_level_visibility(0)
        self.cine.root.enabled = False
        self.lighting.lights = self.house.lights
        self.lighting.ambient_boost = 0.0
        outside = fresh and not self.is_multiplayer and settings.get("quartier", True)
        if self.neighborhood is not None:
            self.neighborhood.destroy()
            self.neighborhood = None
        if outside:
            self.neighborhood = Neighborhood(self)
            self.neighborhood.begin_outside()
        if fresh:
            start = OUTSIDE_START if outside else PLAYER_START
            p.place(start, -12.0 if outside else 0.0, 0.0)
            p.flashlight.on = not outside
            self.state.act = 1
            self.state.player_pos = list(start)
        else:
            pos = self.state.player_pos or list(PLAYER_START)
            p.place(pos, self.state.player_yaw, 0.0)
            p.flashlight.on = False
        p.dead = False
        p.frozen = False
        p.attach_camera()
        self.entity.despawn()
        self.house.doors["front"].locked = bool(self.state.flag("front_locked"))
        self.ui.hud.show()
        self.ui.refresh_objective()
        self.events.start_ambience()
        self.lighting.set_zone(self.house.zone_at(p.pos[0], p.pos[2], p.pos[1]), instant=True)
        p.zone = None
        self.set_mouse(free=False)
        if outside:
            self.house.doors["front"].open(silent=True)
            self.house.outside_view = True
            self.house.set_level_visibility(0)
            self.ui.refresh_objective()
            self.timers.after(1.5, self.say, gd.LINE_OUTSIDE_START)
            self.timers.after(6.0, self.ui.hud.tip, gd.TUTORIAL_HINTS[0], 9.0)
            self.timers.after(16.0, self.ui.hud.tip, gd.OUTSIDE_HINT, 9.0)
        elif fresh:
            self._start_house_timeline()
        else:
            self._restore_runtime(data)
        shader_state.push()

    def on_enter_house(self):
        """Le joueur franchit la porte du 17 rue des Lilas : la nuit commence vraiment."""
        self.playtime = 0.0
        self.ui.refresh_objective()
        self._start_house_timeline(entered=True)

    def _start_house_timeline(self, entered=False):
        if True:
            self.quests.on_event("game_started")
            self.timers.after(5.0, lambda: self.house.doors["front"].close(0.6, slam=False))
            self.timers.after(1.5, self.say, gd.LINE_START)
            if not entered:
                self.timers.after(6.0, self.ui.hud.tip, gd.TUTORIAL_HINTS[0], 9.0)
            self.timers.after(16.0, self.ui.hud.tip, gd.TUTORIAL_HINTS[1], 9.0)
            self.timers.after(300.0, self.events.lock_front_door)
            self.timers.after(540.0, self._force_hunger)
            self.state.set("play_started")
            self.save_checkpoint("debut")

    def _restore_runtime(self, data):
        """Reprise d'une sauvegarde : rétablit l'entité, le chrono et les événements."""
        st = self.state
        if st.act >= 4 and data and data.get("entity"):
            self.entity.restore(data["entity"])
        if st.act >= 3 and self.assistance.phase in (3, 4):
            self.house.anchors["neon_light"].dead = False
        if st.act >= 2:
            if st.act >= 3:
                self.events.deform_portraits()
        if st.act >= 4 and not st.flag("act_cond_open"):
            self.timers.after(30.0, self.events.open_condemned_door)
        if not st.flag("front_locked") and st.act <= 1:
            self.timers.after(120.0, self.events.lock_front_door)
        self.quests.on_event("room_entered")
        self.say("...")

    # ------------------------------------------------------------------
    # Sauvegarde, actes
    # ------------------------------------------------------------------
    def save_checkpoint(self, tag):
        if self.is_multiplayer:
            return
        self.saves.save(self, tag)

    def set_act(self, n):
        if n > self.state.act:
            self.state.act = n
        if n >= 3 and not self.events.deformed:
            self.events.deform_portraits()

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------
    def set_mouse(self, free):
        mouse.locked = not free
        mouse.visible = free

    def say(self, text, duration=None, speaker=None):
        d = duration if duration is not None else max(3.0, 1.5 + len(text) / 16.0)
        self.ui.say(text, d, speaker)

    def _subtitle(self, text, speaker=None):
        if self.ui is not None:
            self.ui.say(text, max(2.5, 1.2 + len(text) / 16.0), speaker)

    def front_door_pos(self):
        return Vec3(7.0, 1.0, 0.0)

    def _door_sound(self, door, name):
        sound.play_at(name, door.pos, 0.9, ref=5.0)

    # ------------------------------------------------------------------
    # Pause / menus
    # ------------------------------------------------------------------
    def toggle_pause(self):
        if self.mode != "playing":
            return
        if self.paused:
            self.resume()
        else:
            self.paused = True
            self.ui.pause.show()
            self.set_mouse(free=True)
            self.player.frozen = True

    def resume(self):
        self.paused = False
        self.ui.pause.hide()
        self.player.frozen = False
        if not self.phone.is_open:
            self.set_mouse(free=False)

    def show_settings(self):
        if self.mode == "menu":
            self.ui.menu.hide()
        self.ui.pause.hide()

        def back():
            if self.mode == "menu":
                self.ui.menu.show()
            elif self.paused:
                self.ui.pause.show()
        self.settings_menu.open(back)

    def confirm_main_menu(self):
        self.ui.pause.hide()
        self.ui.choice.ask("Retourner au menu principal ?\nLa progression est sauvegardée automatiquement aux changements d'acte.",
                           self.to_main_menu, lambda: self.ui.pause.show(), "Quitter la partie", "Annuler")

    def to_main_menu(self):
        if self.neighborhood is not None:
            self.neighborhood.deactivate()
            self.house.outside_view = False
        if self.mp is not None:
            self.mp.disconnect()
        self.is_multiplayer = False
        self.ui.gameover.hide()
        self.ui.ending.stop()
        self.ui.docs.root.enabled = False
        self.ui.rating.root.enabled = False
        self.ui.choice.root.enabled = False
        self.player.frozen = False
        self.player.dead = False
        self.cine.root.enabled = False
        self.events.stop_ambience()
        self.show_menu()

    def quit_game(self):
        settings.save()
        application.quit()

    def retry(self):
        self.ui.gameover.hide()
        if self.is_multiplayer:
            self.to_main_menu()
            return
        if self.saves.exists():
            self.continue_game()
        else:
            self.new_game()

    # ------------------------------------------------------------------
    # Entrées
    # ------------------------------------------------------------------
    def on_input(self, key):
        if self.mode == "loading":
            return
        s = self.settings_menu
        if s is not None and s.visible:
            s.on_key(key)
            if key == "escape" and s.waiting_for is None:
                s.close()
            return
        if self.ui.docs.visible:
            self.ui.docs.on_key(key)
            return
        if self.mode == "lobby" and self.mp is not None:
            self.mp.on_key(key)
            return
        if self.mode in ("menu", "gameover", "ending"):
            return
        if self.mode == "cinematic":
            return
        if self.mode != "playing":
            return
        if key == "escape":
            if self.camera_mode:
                self.exit_camera_mode()
            elif self.inv_panel.visible:
                self.inv_panel.hide()
                self.set_mouse(free=False)
            elif self.phone.is_open:
                self.phone.close()
            else:
                self.toggle_pause()
            return
        if self.paused or self.player.dead:
            return
        if self.neighborhood is not None and self.neighborhood.ui_visible():
            self.neighborhood.on_key(key)
            return
        if self.ui.choice.visible or self.ui.rating.root.enabled:
            return
        if self.phone.is_open:
            if key == settings.key("telephone"):
                if not (self.phone.current == "messages" and self.phone.apps["messages"].composing) and \
                        not (self.phone.current == "quickeats" and self.phone.apps["quickeats"].page == "address") and \
                        not (self.phone.current == "appels" and self.phone.apps["appels"].page == "keypad"):
                    self.phone.close()
                    return
            self.phone.on_key(key)
            return
        if self.camera_mode:
            if key in ("left mouse down", settings.key("interagir")):
                self.photo.take()
            elif key == settings.key("telephone"):
                self.exit_camera_mode()
            return
        if self.player.frozen:
            return
        res = self.player.on_key(key)
        if isinstance(res, str) and res.startswith("vue:"):
            self.ui.say(res[4:], 1.6)
        if key == settings.key("interagir"):
            self.interact()
        elif key == settings.key("telephone"):
            self.phone.open()
        elif key == settings.key("inventaire"):
            if self.inv_panel.toggle():
                self.set_mouse(free=True)
            else:
                self.set_mouse(free=False)

    def interact(self):
        if self.interactions.target is not None:
            self.interactions.use()

    # --- appareil photo --------------------------------------------------
    def enter_camera_mode(self):
        self.camera_mode = True
        self.player.force_first_person += 1
        self.viewfinder.enabled = True
        self.player.speed_mult = 0.6
        self.set_mouse(free=False)
        self.state.set("camera_used")

    def exit_camera_mode(self):
        if self.camera_mode:
            self.player.force_first_person = max(0, self.player.force_first_person - 1)
        self.camera_mode = False
        self.viewfinder.enabled = False
        self.player.speed_mult = 1.0

    def reveal_allowed(self, name):
        return True

    def on_photo_reveal(self, name):
        if name == "mur_message":
            pass

    def on_photo_taken(self, found):
        st = self.state
        if found:
            st.stats["photos_reveal"] += 1
            if "mur_message" in found and "mur" not in st.docs:
                st.add_doc("mur")
                self.quests.on_event("doc_found")
                self.timers.after(0.8, lambda: self.ui.docs.open("Message sous le papier peint", [gd.WALL_MESSAGE_PHOTO]))
            if "fauteuil" in found:
                self.timers.after(0.9, self.say, "Une silhouette assise dans le fauteuil... sur la photo seulement.")
            if "empreintes" in found:
                self.timers.after(0.9, self.say, "Des empreintes de pas noires, partout dans le couloir.")
            self.player.add_stress(10)
        else:
            self.say(gd.LINE_PHOTO_NOTHING)
        self.quests.on_event("photo_taken")

    # ------------------------------------------------------------------
    # Événements du téléphone
    # ------------------------------------------------------------------
    def on_phone_opened(self):
        self.quests.on_event("phone_opened")
        self.inv_panel.hide()
        self.state.phone_used = True

    def on_phone_closed(self):
        if not (self.ui.docs.visible or self.paused or self.inv_panel.visible):
            self.set_mouse(free=False)

    def on_phone_notification(self):
        self.player.add_stress(2.0)

    def on_conversation_opened(self, cid):
        pass

    def on_order_confirmed(self, meal, address_key):
        st = self.state
        st.meal = meal
        st.address = address_key
        st.entity_type = gd.MEALS[meal]["entity"]
        self.quests.on_event("order_confirmed")
        self.set_act(2)
        if self.net:
            self.net.send_order(meal, gd.ADDRESSES[address_key]["label"])
        else:
            self.timers.after(30.0, self.cancel_order)

    def cancel_order(self):
        st = self.state
        meal = gd.MEALS[st.meal]
        refused = st.flags.setdefault("refused_orders", [])
        refused.append(("QuickEats", -meal["price"], "12/10"))
        st.set("order_cancelled")
        self.phone.notify("QuickEats", gd.FIRST_CANCEL, "icone_quickeats", target=("banque",))
        self.phone.model.add_message("support", gd.CONTACT_SUPPORT, gd.FIRST_CANCEL, mine=False)
        self.quests.on_event("first_cancel")
        self.assistance.on_first_cancel()
        self.save_checkpoint("annulation")

    def on_order_failed(self, n):
        self.quests.on_event("order_failed")
        if n >= 4:
            self.player.add_stress(10)

    # ------------------------------------------------------------------
    # Progression de l'histoire
    # ------------------------------------------------------------------
    def on_exploration_done(self):
        self.timers.after(4.0, self._hungry)

    def _force_hunger(self):
        if not self.state.flag("hungry") and self.state.act == 1:
            self.quests.complete("explorer")
            self._hungry()

    def _hungry(self):
        if self.state.flag("hungry"):
            return
        self.state.set("hungry")
        sound.speak(gd.LINE_HUNGRY, f0=100, speed=0.9, whisper=True, volume=0.8, channel="voice", speaker=gd.PLAYER_FIRST)
        self.quests.start("commander")
        self.ui.hud.tip("Appuyez sur T pour sortir le téléphone.", 7.0)

    def on_countdown_start(self):
        self.countdown_flicker = True
        self.save_checkpoint("livreur_arrive")
        sound.music.set_state("countdown", stinger=False)
        self.house.anchors["neon_light"].dead = False
        self.house.anchors["neon_light"].enabled = True

    def on_entity_enters(self):
        """30 s avant la fin : porte d'entrée, pas lents sur le carrelage."""
        st = self.state
        door = self.house.doors["front"]
        door.locked = False
        self.countdown_flicker = True
        sound.play_at("porte_ouvre", self.front_door_pos(), 1.0, ref=8.0)
        door.open(3.0, silent=True)
        kind = st.entity_type or "imposteur"
        self.entity.spawn(kind, Vec3(7.0, 0.0, 1.0), nightmare=(st.address == "piege"))
        self.entity.begin_arrival(Vec3(7.0, 0.0, 0.9), 0.0)
        self.house.anchors["neon_light"].dead = True          # le néon s'éteint pour de bon
        self.timers.after(5.0, lambda: (door.close(0.6, slam=True), setattr(door, "locked", True)))
        self.player.add_stress(15)

    def on_delivery_done(self):
        """0 s : livraison effectuée. L'entité est lâchée dans la maison."""
        self.countdown_flicker = False
        self.set_act(4)
        door = self.house.doors["front"]
        door.locked = True
        self.entity.activate()
        self.phone.apps["quickeats"].force_close()
        self.phone.freeze(10.0)
        self.effects.flash(0.4, 0.5)
        sound.play("stinger_alerte", 0.7)
        sound.music.set_state("patrol", stinger=False)
        self.timers.after(45.0, self.events.open_condemned_door)
        self.save_checkpoint("livraison")
        self.ui.refresh_objective()

    def on_choice_made(self, pid, choice, truth):
        pass

    def on_descend(self):
        self.set_act(5)
        self.save_checkpoint("sous_sol")
        if self.entity.active:
            self.entity.dormant = True
            self.entity.set_visible(False)
            sound.music.set_state("ambush", stinger=False)

    def draw_salt_circle(self, pos):
        self.events.draw_salt_circle(pos)

    def use_item(self, item):
        st = self.state
        if item == "pile":
            fl = self.player.flashlight
            if fl.battery <= self.phone.model.battery:
                fl.add_battery(45.0)
                self.say("J'ai changé la pile de la lampe torche.")
            else:
                self.phone.model.charge(45.0)
                self.say("Un peu de batterie pour le téléphone.")
            st.remove_item("pile")
            sound.play("piles_ok", 0.8)
        elif item == "sel":
            if self.assistance.use_salt():
                pass
        elif item == "batterie_externe":
            self.phone.model.charge(80.0)
            st.remove_item(item)
            self.say("Le téléphone se recharge.")
            sound.play("piles_ok", 0.8)
        elif item == "pansement":
            self.player.health = min(100.0, self.player.health + 35.0)
            st.remove_item(item)
            self.say("Ça ira mieux.")
        elif item == "barre":
            self.player.relieve_stress(25.0)
            st.remove_item(item)
            self.say("Du sucre. Ça calme un peu.")
        elif item == "eau":
            self.player.stamina = 100.0
            self.player.relieve_stress(5.0)
            st.remove_item(item)
        elif item == "energisant":
            self.player.energy_t = 60.0
            self.player.stamina = 100.0
            st.remove_item(item)
            self.say("Le cœur s'emballe. J'ai de l'énergie pour un moment.")
        elif item == "bougie":
            st.remove_item(item)
            self._place_candle()
        elif item == "journal":
            self.inv_panel.hide()
            self.ui.docs.open("Nice-Matin", ["\n\n".join(gd.NEWSPAPER_HEADLINES)])
            return
        self.inv_panel.refresh()

    def _place_candle(self):
        p = self.player
        pos = p.pos + Vec3(p.forward[0] * 0.6, 0.05, p.forward[2] * 0.6)
        b = MeshBuilder("bougie")
        b.cyl("platre", pos[0], pos[1], pos[2], 0.04, 0.03, 8, (0.95, 0.95, 0.9))
        b.sphere("neon", pos[0], pos[1] + 0.06, pos[2], 0.012, (1.0, 0.7, 0.3), lat=3, lon=5, sy=1.8)
        ents = b.build(parent=self.house.level_roots.get(p.level), emit=1.0)
        light = LightSource((pos[0], pos[1] + 0.25, pos[2]), (1.0, 0.62, 0.3), 1.1, 4.5, kind="candle", name="bougie")
        self.house.lights.append(light)
        sound.play("briquet", 0.6)
        self.say("Une petite flamme. C'est mieux que rien.")

        def _out():
            light.enabled = False
            for e in ents:
                destroy(e)
            if light in self.house.lights:
                self.house.lights.remove(light)
        self.timers.after(120.0, _out)

    def reread_doc(self, doc):
        pages = {
            "carnet": list(gd.NOTEBOOK_PAGES), "releve": [gd.BANK_STATEMENT_TEXT], "polaroids": list(gd.POLAROID_PAGES),
            "plan": [gd.PLAN_TEXT], "mur": [gd.WALL_MESSAGE_PHOTO], "tel_garnier": ["\n\n".join(gd.GARNIER_PHONE_TEXT)],
            "recus": [gd.RECEIPTS_TEXT], "journaux": ["\n\n".join(gd.NEWSPAPER_HEADLINES)], "note_frigo": [gd.NOTE_FRIGO],
            "note_sdb": [gd.NOTE_SDB],
        }.get(doc, ["(illisible)"])
        self.inv_panel.hide()
        self.ui.docs.open(gd.DOC_TITLES.get(doc, "Document"), pages)

    def send_chat(self, text):
        if self.net:
            self.net.send_chat(text)

    # ------------------------------------------------------------------
    # Mort, fins
    # ------------------------------------------------------------------
    def kill_player(self, cause="entity_contact", kind=None, already_scared=False):
        if self.player.dead:
            return
        self._death_kind = (kind, already_scared, cause)
        self.player.kill(cause)

    def _on_death(self, cause):
        kind, scared, cause = self._death_kind or (None, False, cause)
        self.state.stats["deaths"] += 1
        sound.set_heart(0)
        sound.set_breath(None)
        self.phone.close()
        self.entity.killing = True
        if self.net:
            self.net.send_death(cause)
        if cause == "door_open":
            kind = "porte"
        done = self._mp_spectate if self.is_multiplayer else self.show_game_over
        if scared:
            done()
        else:
            self.jumpscare.trigger(kind or "generic", on_done=done)

    def _mp_spectate(self):
        """Multijoueur : le joueur mort devient spectateur."""
        self.effects.set_fade(0.0)
        self.player.frozen = False
        if self.mp is not None:
            self.mp.dead = True
            self.mp.spectate_id = None
            if hasattr(self.mp, "_spec_init"):
                del self.mp._spec_init
        self.ui.say("Livraison effectuée. Vous êtes spectateur.", 5.0)

    def show_game_over(self):
        self.mode = "gameover"
        self.effects.fade_to(1.0, 0.1)
        sound.music.reset()
        first = self.state.first_death
        self.state.first_death = False
        self.ui.hud.hide()
        self.ui.gameover.show(first_death=first)
        self.player.frozen = True

    def final_event(self):
        """Événement final du sous-sol (après lecture du message)."""
        st = self.state
        self.quests.on_event("final")
        code = "C" if (st.address == "piege" and st.freezer_opened) else "B"
        self.trigger_ending(code)

    def ending_d_note(self):
        self.ui.docs.open("Note sous la porte", [gd.NOTE_DOOR_END_D], lambda: self.trigger_ending("D"))

    def trigger_ending(self, code):
        if self.ending_active:
            return
        self.ending_active = True
        st = self.state
        st.set("ending_started")
        st.ending = code
        self.mode = "ending"
        self.ui.hud.hide()
        self.entity.set_visible(False)
        self.player.frozen = True
        self.phone.close()
        self.set_mouse(free=True)
        sound.music.reset()
        for h in list(self.events.handles.values()):
            if h:
                h.fade_to(0.0, 2.0, stop=True)
        self.effects.fade_to(1.0, 1.5)

        def go():
            self.effects.set_fade(0.0)
            if code == "B":
                self.ui.rating.show("Notez votre livreur", lambda: self.ui.ending.start("B"))
            else:
                self.ui.ending.start(code)
        invoke(go, delay=1.7)

    def _check_ending_a(self):
        """Fin A : remonter du sous-sol sans avoir ouvert le congélateur, tous bons choix + tous les documents."""
        st = self.state
        p = self.player
        if not st.flag("descended") or st.freezer_opened or self.ending_active:
            return
        if p.zone == "escalier_cave" and p.pos[1] > -0.5:
            if st.bad_choices == 0 and st.all_docs and len(st.pair_good) >= 5:
                self.entity.despawn()
                self.house.doors["front"].locked = False
                self.trigger_ending("A")
            elif self.entity.active and self.entity.dormant:
                self.entity.dormant = False
                self.entity.set_visible(True)
                self.entity.pos = Vec3(7.0, 0.0, 9.5)
                self.entity.set_state("search")
                self.say("Ce n'est pas fini...")

    # ------------------------------------------------------------------
    # Multijoueur (délégué)
    # ------------------------------------------------------------------
    def show_multiplayer(self):
        from multiplayer_manager import MultiplayerManager
        if self.mp is None:
            self.mp = MultiplayerManager(self)
        self.mp.show_lobby()

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------
    def update(self, dt):
        try:
            self._update(dt)
        finally:
            shader_state.push()

    def _update(self, dt):
        dt = min(dt, 0.1)
        if getattr(self, "achievements", None) is not None and self.mode != "loading":
            self.achievements.update(dt)
        if self.mode == "loading":
            import time as _t
            t0 = _t.time()
            while _t.time() - t0 < 0.03:
                try:
                    next(self._boot_gen)
                except StopIteration:
                    break
            return
        self._frame += 1
        if self.mode in ("menu", "lobby"):
            self._update_menu(dt)
            if self.mp is not None:
                self.mp.update(dt)
            return
        if self.mode == "cinematic":
            self.cine.update(dt)
            self._cine_world(dt)
            return
        if self.mode in ("gameover", "ending"):
            self.ui.update(dt)
            self.effects.update(dt)
            sound.update(dt)
            return
        # --- jeu ---
        if self.paused:
            self.ui.update(dt)
            return
        if self._frame % 10 == 0 and settings.get("pause_auto", True) and not self.is_multiplayer:
            try:
                win = application.base.win
                if win is not None and not win.getProperties().getForeground():
                    self.toggle_pause()
                    return
            except Exception:
                pass
        self._update_playing(dt)

    def _cine_world(self, dt):
        self.sky.update()
        self.lighting.update(dt, camera.world_position)
        self.effects.update(dt)
        sound.set_listener(camera.world_position, camera.world_rotation_y)
        sound.update(dt)
        shader_state.cam_pos = camera.world_position
        self.ui.update(dt)

    def _update_playing(self, dt):
        st = self.state
        p = self.player
        self.timers.update(dt)
        self.playtime += dt
        st.stats["play_time"] += dt
        st.clock += dt * config.GAME_MINUTES_PER_REAL_MINUTE / 60.0
        # photos / téléphone / lampe
        if self.phone.model.torch_on and not self.phone.model.dead:
            self.phone_light.enabled = True
            self.phone_light.base_intensity = 0.55
            self.phone_light.pos = p.eye_pos + p.forward * 0.5 + Vec3(0, -0.1, 0)
        elif self.phone.is_open and not self.phone.model.dead:
            self.phone_light.enabled = True
            self.phone_light.base_intensity = 0.22
            self.phone_light.pos = p.eye_pos + p.forward * 0.4 + Vec3(0, -0.15, 0)
        else:
            self.phone_light.enabled = False
        p.update(dt)
        eye = p.eye_pos
        zone_mult = self.lighting.zone_mult
        p.flashlight.mult = zone_mult
        p.flashlight.update(dt, p.light_origin(), p.forward)
        # éclairage perçu par le joueur (pour la détection)
        lvl = 0.0
        for l in self.house.lights:
            if l.is_lit and l is not self.phone_light:
                d = (l.pos - eye).length()
                if d < l.range:
                    lvl += l.intensity() * (1 - d / l.range) ** 2
        p.light_level = min(1.0, lvl)
        cam_pos = camera.world_position
        shader_state.cam_pos = cam_pos
        self.lighting.update(dt, cam_pos)
        self.sky.update()
        self.fl_cone.update(p.flashlight, self.phone.is_open)
        self.events.update(dt)
        if self.neighborhood is not None:
            self.neighborhood.update(dt)
        self.assistance.update(dt)
        self.entity.update(dt)
        self.phone.update(dt)
        self.interactions.find_target(eye, p.forward)
        self.particles.update(dt)
        self.jumpscare.update(dt)
        self.jumpscare.update_bag(dt)
        self._countdown_effects(dt)
        self._room_tracking()
        self._level_visibility()
        self._check_ending_a()
        self._check_ending_d(dt)
        # proximité de l'entité : cœur plus rapide
        prox = getattr(p, "proximity", 0.0)
        if self.entity.active and self.entity.visible and prox > 0.25:
            sound.set_heart(max(60 + prox * 90, 0))
        self.effects.update(dt)
        self.ui.update(dt)
        sound.update(dt)
        if self.net:
            self.mp.update(dt)
        if self._frame % 20 == 0:
            shader_state.post_res = tuple(window.size)
            camera.set_shader_input("res", Vec2(window.size[0], window.size[1]))

    def _countdown_effects(self, dt):
        if not self.countdown_flicker:
            return
        self._flicker_t -= dt
        if self._flicker_t <= 0:
            self._flicker_t = random.uniform(0.15, 1.2)
            self.effects.flash(0.08, 0.1)
            self.player.flashlight.blackout = True
            invoke(setattr, self.player.flashlight, "blackout", False, delay=random.uniform(0.05, 0.2))
            neon = self.house.anchors["neon_light"]
            neon.boost = random.choice([0.0, 1.0, 2.5])
            if random.random() < 0.3:
                sound.play("craquement_bois", 0.3)

    def _room_tracking(self):
        p = self.player
        if p.room is not None and p.room.id not in self.state.rooms_visited:
            self.state.rooms_visited.add(p.room.id)
        if self._frame % 30 == 0:
            self.quests.on_event("room_entered")

    def _level_visibility(self):
        lvl = self.player.level
        if lvl != self._level_shown:
            self._level_shown = lvl
            self.house.set_level_visibility(lvl)

    def _check_ending_d(self, dt):
        st = self.state
        if self.ending_d_t is None and not st.phone_used and self.playtime >= 1200.0 and st.act <= 1 and not self.ending_active:
            self.ending_d_t = 0.0
            self.say("La maison est étrangement calme...", 5.0)
        if self.ending_d_t is not None and not self.ending_active:
            self.ending_d_t += dt
            for k, h in list(self.events.handles.items()):
                if h:
                    h.fade_to(max(0.0, 1.0 - self.ending_d_t / 60.0), 1.0)
            if self.ending_d_t > 62 and not self.events.note_door_spawned:
                self.ui.say("L'entité n'a pas été invitée.", 7.0)
                self.events.spawn_door_note()
                sound.play("sourd_mort", 0.5)
