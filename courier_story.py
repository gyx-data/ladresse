"""Le livreur pendant l'attente (solo) : il écrit, il attend sous le lampadaire, il se trompe de porte.

Inspiré d'une légende urbaine (« ton livreur est arrivé... ») mais raconté dans l'histoire du jeu :
  * il écrit dans sa propre conversation (« Votre livreur ») et demande le code du portail du 17 :
    le lui donner, c'est l'inviter ;
  * depuis la lucarne du grenier on le voit sous le lampadaire, bien trop grand, téléphone allumé ;
  * il passe chez la voisine, Mme Bianchi (11 rue des Lilas) : coups, un cri, puis « Mauvaise adresse » ;
  * RÈGLE : quand il écrit, son téléphone s'allume — devant le 17, la lumière bleue passe sous la porte.
    Chaque faux message de « l'assistance » s'accompagne de cette lumière ;
  * le pourboire : à la porte, QuickEats réclame un pourboire (2 €, 5 € et un troisième bouton) ; deux messages
    de l'assistance se contredisent, la lumière dit lequel vient de lui ;
  * on rembobine : une mort pendant la nuit de livraison fait rembobiner la cassette jusqu'au dernier point
    de sauvegarde et grave une règle dans le carnet « Règles ».
Les étapes sont indexées sur le temps écoulé depuis « votre livreur est en chemin » et mémorisées dans les drapeaux
de la partie : un point de sauvegarde rechargé rejoue exactement ce qui restait à venir.
"""
import json
import math
import os
import random

from ursina import Entity, Vec3, camera, color, destroy

import config
import game_data as gd
from lighting_system import LightSource
from sound_engine import engine as sound
from ui_widgets import label, rect, rgb
import typography as T

CONV = "livreur"
NAME = "Votre livreur"
GATE_CODE = "1704"
LAMP = Vec3(3.2, 0.0, -7.0)
BIANCHI_DOOR = Vec3(-26.0, 1.2, -2.7)

# temps (s) depuis « en chemin », avant l'échelle de l'adresse piège
T_ARRIVE = 70.0
T_ASK = 74.0
T_ASSIST_CODE = 98.0
T_INSIST = (108.0, 150.0)
T_LEAVE_LAMP = 196.0
T_VOISINE = 202.0
T_AT_DOOR = 252.0
T_TIP = gd.DELIVERY_TOTAL_SECONDS - 60 + 7.0
T_TIP_END = gd.DELIVERY_TOTAL_SECONDS - 60 + 27.0

RULES = {
    "lumiere": "Quand il écrit, son téléphone s'allume. Si une lumière bleue passe sous la porte, le message vient de lui.",
    "contradiction": "La vraie assistance ne change jamais d'avis. Deux messages qui se contredisent : l'un des deux est à lui.",
    "code": "Ne lui donne jamais le code. Un portail ouvert est une invitation.",
    "porte": "Quand il frappe, on n'ouvre pas. Jamais.",
}
REWIND_LIMIT = {"Facile": 99, "Normal": 99, "Difficile": 2, "Cauchemar": 0}

TIP_TRUTHS = {
    "rien": "Ne choisissez aucun pourboire. Laissez l'application ouverte, il repartira.",
    "5": "Laissez un pourboire de 5 €. Exactement 5 €. Puis attendez.",
}


def _glow_texture():
    """Halo de la lumière qui passe sous la porte : fort contre le seuil, qui s'étale et s'éteint vers la pièce."""
    from PIL import Image
    import numpy as np
    from texture_generator import textures
    key = "_lueur_porte"
    if key not in textures.images:
        w, h = 256, 128
        yy, xx = np.mgrid[0:h, 0:w].astype(float)
        u = (xx / (w - 1) - 0.5) * 2.0                   # -1..1 le long du seuil
        v = yy / (h - 1)                                  # 0 = contre la porte, 1 = dans la pièce
        spread = 0.55 + 0.45 * v                          # le faisceau s'élargit en s'éloignant
        a = np.clip(1.0 - (np.abs(u) / spread) ** 2.2, 0, 1) * np.exp(-v * 3.2) * (1.0 - np.exp(-(v + 0.02) * 40))
        img = np.zeros((h, w, 4), dtype=np.uint8)
        img[..., :3] = 255
        img[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
        textures.images[key] = Image.fromarray(img[::-1], "RGBA")
    return textures.get(key)


def _rules_path():
    return os.path.join(config.app_data_dir(), "regles.json")


class CourierStory:
    def __init__(self, game):
        self.game = game
        self.learned = self._load_rules()
        self.courier = None
        self.glow_door = None
        self.glow_light = None
        self.phone_light = None
        self.phone_quad = None
        self._house = None
        self.glow_t = 0.0
        self.look_t = 0.0
        self.tip_choice = None
        self.overlay = None
        self.reset()

    # ------------------------------------------------------------------
    # Mémoire des règles (gardée d'une partie et d'un rembobinage à l'autre)
    # ------------------------------------------------------------------
    def _load_rules(self):
        try:
            with open(_rules_path(), encoding="utf-8") as f:
                data = json.load(f)
            return [r for r in data if r in RULES]
        except (OSError, ValueError, TypeError):
            return []

    def _save_rules(self):
        try:
            with open(_rules_path(), "w", encoding="utf-8") as f:
                json.dump(self.learned, f)
        except OSError:
            pass

    def rule_pages(self):
        if not self.learned:
            return ["Aucune règle pour l'instant.\n\nCertaines choses ne s'apprennent qu'une fois mort."]
        return ["\n\n".join(f"RÈGLE N°{i + 1}\n{RULES[r]}" for i, r in enumerate(self.learned))]

    # ------------------------------------------------------------------
    @property
    def st(self):
        return self.game.state

    def flag(self, k):
        return self.st.flag("courier_" + k)

    def set(self, k, v=True):
        self.st.set("courier_" + k, v)

    def reset(self):
        self.glow_t = 0.0
        self.look_t = 0.0
        self.spot_t = 0.0
        self.tip_choice = None

    def active(self):
        g = self.game
        return not g.is_multiplayer and g.net is None and g.mode == "playing"

    def elapsed(self):
        a = self.game.assistance
        if a.t0 is None or a.remote:
            return None
        return (a.now() - a.t0) / max(0.1, a.ts)

    # ------------------------------------------------------------------
    # Monde : livreur sous le lampadaire, lumière sous la porte
    # ------------------------------------------------------------------
    def _ensure_world(self):
        h = self.game.house
        if h is self._house:
            return
        from livreur_model import LivreurModel
        root = h.exterior_root or Entity()
        self.courier = LivreurModel(parent=root)
        self.courier.root.position = LAMP + Vec3(0.55, 0, -0.35)
        self.courier.root.rotation_y = 0.0
        self.courier.root.scale = 1.6                     # ~3,3 m : bien trop grand
        self.courier.root.enabled = False
        wrist = self.courier.arms[1][2] if getattr(self.courier, "arms", None) else self.courier.root
        wrist = getattr(wrist, "pivot", None) or getattr(wrist, "node", None) or wrist      # articulation -> son pivot
        self.phone_quad = Entity(parent=wrist, model="quad", position=(0.0, -0.12, 0.08), scale=(0.07, 0.13),
                                 color=color.rgb(0.45, 0.7, 1.0), double_sided=True)
        self.phone_light = LightSource(tuple(LAMP + Vec3(0.9, 2.2, 0.0)), (0.35, 0.6, 1.0), 0.0, 5.0, kind="static",
                                       name="tel_livreur")
        h.lights.append(self.phone_light)
        # lumière bleue sous la porte d'entrée (côté couloir)
        lvl0 = h.level_roots.get(0) if hasattr(h, "level_roots") else None
        self.glow_door = Entity(parent=lvl0, model="quad", texture=_glow_texture(), position=(7.0, 0.012, 0.42), rotation_x=90,
                                scale=(1.6, 0.85), color=color.rgba(0.3, 0.55, 1.0, 0.0))
        try:
            from panda3d.core import ColorBlendAttrib, TransparencyAttrib
            self.glow_door.setTransparency(TransparencyAttrib.M_alpha)
            self.glow_door.set_depth_write(False)
            self.glow_door.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_incoming_alpha,
                                                           ColorBlendAttrib.O_one))           # lumière : additive
        except Exception:
            pass
        self.glow_light = LightSource((7.0, 0.15, 0.45), (0.3, 0.55, 1.0), 0.0, 3.6, kind="static", name="lumiere_porte")
        h.lights.append(self.glow_light)
        self._house = h

    def where(self):
        e = self.elapsed()
        if e is None or e < T_ARRIVE:
            return None
        if e < T_LEAVE_LAMP:
            return "lampadaire"
        if e < T_AT_DOOR:
            return "voisine"
        return "porte"

    def glow(self, dur=4.0):
        """Son téléphone s'allume (il écrit)."""
        self.glow_t = max(self.glow_t, dur)
        if self.where() == "porte":
            sound.play_at("clavier", self.game.front_door_pos() + Vec3(0, -0.6, -0.4), 0.35, ref=2.5)

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------
    def say(self, text, glow=True):
        ph = self.game.phone
        conv = ph.model.conversations.get(CONV)
        if conv is None:
            return
        conv["hidden"] = False
        ph.model.add_message(CONV, NAME, text)
        ph.notify(NAME, text, "icone_messages", target=("messages", CONV))
        sound.play("vibration", 0.7, channel="voice")
        app = ph.apps.get("messages")
        if ph.is_open and ph.current == "messages" and app is not None and (app.page == "list" or app.conv == CONV):
            app.render()
        if glow:
            self.glow()

    def on_assistance_option(self, pid, opt):
        """Chaque faux message de l'assistance (celui qui contredit la vérité) allume son téléphone."""
        if not self.active():
            return
        try:
            fake = opt != self.game.assistance.truth(pid)
        except Exception:
            fake = False
        if fake:
            self.glow(5.0)

    def on_player_reply(self, text):
        """Réponse tapée dans sa conversation (elle part même sans réseau)."""
        st = self.st
        digits = "".join(c for c in text if c.isdigit())
        if self.flag("code_given"):
            self.game.timers.after(2.5, self.say, "Je sais.")
            return
        if GATE_CODE in digits:
            self.set("code_given")
            self.game.timers.after(2.0, self.say, "Merci.")
            self.game.timers.after(4.5, self._gate_beep)
            self.game.quests.on_event("courier_code")
        elif digits:
            self.game.timers.after(2.5, self.say, "Ce n'est pas le bon code, Adrien.")
        else:
            self.game.timers.after(2.5, self.say, "Le code.")
        st.set("courier_replied", True)

    def _gate_beep(self):
        sound.play_at("digicode", Vec3(7.7, 1.3, -6.2), 1.0, ref=7.0)
        self.game.player.add_stress(15)
        self.game.say("Le portail... il vient d'entrer dans le jardin.", 4.0)

    # ------------------------------------------------------------------
    # Déroulé
    # ------------------------------------------------------------------
    def update(self, dt):
        g = self.game
        if g.is_multiplayer or g.house is None:
            return
        self._ensure_world()
        e = self.elapsed()
        w = self.where()
        # livreur visible sous le lampadaire (vu depuis la lucarne du grenier)
        show = w == "lampadaire" and g.assistance.phase < 5
        if self.courier is not None and self.courier.root.enabled != show:
            self.courier.root.enabled = show
        if show:
            self.courier.animate(dt, 0.0, False, "patrol")
            self._lucarne_check(dt)
        # lumière : téléphone (lampadaire) ou sous la porte
        self.glow_t = max(0.0, self.glow_t - dt)
        k = 0.0
        if self.glow_t > 0:
            k = min(1.0, self.glow_t / 0.6) * (0.75 + 0.25 * math.sin(g.playtime * 23.0))
        self.spot_t = max(0.0, self.spot_t - dt)
        if self.phone_light is not None:
            # quand on le fixe, l'écran de son téléphone éclaire son visage
            self.phone_light.base_intensity = ((0.5 + 2.2 * k) + (3.5 if self.spot_t > 0 else 0.0)) if show else 0.0
            self.phone_quad.color = color.rgb(0.25 + 0.4 * k, 0.4 + 0.5 * k, 0.6 + 0.4 * k)
        door = w == "porte" and g.assistance.phase < 5
        if self.glow_light is not None:
            self.glow_light.base_intensity = 2.6 * k if door else 0.0
            self.glow_door.color = color.rgba(0.3, 0.55, 1.0, 0.85 * k if door else 0.0)
        if e is None or not self.active():
            return
        self._beats(e)

    def _beats(self, e):
        g = self.game
        a = g.assistance
        if e >= T_ARRIVE - 5 and not self.flag("cp_code"):
            self.set("cp_code")
            g.save_checkpoint("livreur_portail")
        if e >= T_ARRIVE and not self.flag("arrive"):
            self.set("arrive")
            a.status_text = "Votre livreur est arrivé."
            self.say("Bonsoir. Je suis devant le portail.")
        if e >= T_ASK and not self.flag("ask"):
            self.set("ask")
            self.say("C'est quoi le code ?")
        if e >= T_ASSIST_CODE and not self.flag("assist_code"):
            self.set("assist_code")
            a.send("Rappel de sécurité : nos livreurs ne demandent jamais de code d'accès. Ne répondez à aucune demande.")
        for i, t in enumerate(T_INSIST):
            if e >= t and not self.flag(f"insist{i}") and not self.st.flag("courier_replied"):
                self.set(f"insist{i}")
                self.say(("Je sais que tu es réveillé, Adrien.", "J'ai tout mon temps.")[i])
        if e >= T_VOISINE - 8 and not self.flag("cp_voisine"):
            self.set("cp_voisine")
            g.save_checkpoint("livreur_voisine")
        if e >= T_VOISINE and not self.flag("voisine"):
            self.set("voisine")
            self._neighbour()
        if e >= T_AT_DOOR and not self.flag("at_door"):
            self.set("at_door")
            a.status_text = "Votre livreur est devant votre porte."
            self.say("Je suis devant ta porte.")
        if e >= T_TIP and not self.flag("tip"):
            self.set("tip")
            self._start_tip()
        if e >= T_TIP_END and not self.flag("tip_done"):
            self.set("tip_done")
            self._end_tip()

    # --- la lucarne -----------------------------------------------------------
    def look_out(self):
        """« Regarder dehors » pendant qu'il attend : le regard se colle à la vitre et zoome sur lui."""
        g = self.game
        p = g.player
        head = self.courier.root.world_position + Vec3(0, 2.6, 0)
        to = head - p.eye_pos
        p.yaw = math.degrees(math.atan2(to[0], to[2]))
        p.pitch = max(-80.0, min(80.0, -math.degrees(math.atan2(to[1], math.hypot(to[0], to[2])))))
        p.zoom_fov = 18.0
        p.look_enabled = False
        self.spot_t = 5.0
        g.timers.after(5.0, self._end_look)
        if not self.flag("seen"):
            self._lucarne_check(0.0, forced=True)

    def _end_look(self):
        p = self.game.player
        p.zoom_fov = None
        p.look_enabled = True

    def _lucarne_check(self, dt, forced=False):
        g = self.game
        p = g.player
        if p.level != 2 or self.flag("seen"):
            return
        if forced:
            self.look_t = 2.0
        head = self.courier.root.world_position + Vec3(0, 3.0, 0)
        to = head - p.eye_pos
        if not forced and (to.length() > 20 or to.normalized().dot(p.forward) < 0.93):
            self.look_t = max(0.0, self.look_t - dt)
            return
        self.look_t += dt
        if self.look_t > 1.2:
            self.set("seen")
            sound.play("stinger_alerte", 0.5)
            p.add_stress(22)
            p.shake(0.2, 0.25)
            g.say("Sous le lampadaire... il est immense. Et il me regarde.", 4.5)
            self.say("Je te vois.")

    # --- la voisine -------------------------------------------------------
    def _neighbour(self):
        g = self.game
        g.assistance.status_text = "Livraison en cours — 11 rue des Lilas."
        for i, t in enumerate((0.0, 2.2, 4.4)):
            g.timers.after(t, sound.play_at, "coups_porte", BIANCHI_DOOR, 0.9, ref=14.0)
        g.timers.after(9.0, sound.play_at, "cri", BIANCHI_DOOR, 1.0, ref=18.0)
        g.timers.after(9.5, g.player.add_stress, 18)
        g.timers.after(13.0, g.say, "C'était chez Mme Bianchi... la voisine.", 4.0)
        g.timers.after(26.0, self.say, "Excusez le retard. Mauvaise adresse.", False)
        g.timers.after(38.0, g.assistance.send,
                       "Une livraison a eu lieu au 11 rue des Lilas. Restez à l'intérieur. N'ouvrez à personne.")
        self.st.set("bianchi_taken", True)
        nb = getattr(g, "neighborhood", None)
        if nb is not None:
            for n in getattr(nb, "npcs", []):
                if n.name == "Mme Bianchi":
                    n.root.enabled = False

    # --- le pourboire ---------------------------------------------------------
    def _start_tip(self):
        g = self.game
        truth = random.choice(("rien", "5"))
        self.set("tip_truth", truth)
        self.tip_choice = None
        app = g.phone.apps.get("quickeats")
        if app is not None and hasattr(app, "open_tip"):
            app.open_tip(self.on_tip)
        g.phone.notify("QuickEats", "Votre livreur est à votre porte. Ajouter un pourboire ?", "icone_quickeats", target=("quickeats",))
        fake = "5" if truth == "rien" else "rien"
        first, second = random.sample([truth, fake], 2)
        for delay, which in ((3.0, first), (9.0, second)):
            g.timers.after(delay, self._tip_message, which, which == fake)

    def _tip_message(self, which, fake):
        self.game.assistance.send(TIP_TRUTHS[which])
        if fake:
            self.glow(5.0)

    def on_tip(self, choice):
        """choice : '2' | '5' | 'entrer'."""
        if self.flag("tip_done") or self.tip_choice is not None:
            return
        self.tip_choice = choice
        sound.play("paiement", 0.7, channel="voice")
        if choice == "entrer":
            self.set("tip_done")
            self.game.timers.after(1.2, self.game.kill_player, "pourboire", "porte")

    def _end_tip(self):
        g = self.game
        truth = self.st.flag("courier_tip_truth") or "rien"
        choice = self.tip_choice
        if choice == "entrer" or g.player.dead:
            return
        ok = (truth == "rien" and choice is None) or (truth == "5" and choice == "5")
        app = g.phone.apps.get("quickeats")
        if app is not None and hasattr(app, "close_tip"):
            app.close_tip()
        if not ok:
            g.kill_player("pourboire", "porte")
            return
        self.say("Merci pour votre commande.", False)
        g.timers.after(3.0, self.say, "Votre adresse a été ajoutée à mes favoris.", False)
        g.player.relieve_stress(15)
        self.st.set("courier_favoris", True)
        if self.flag("code_given"):
            g.entity.speed_mult *= 1.12
            g.entity.detection_mult *= 1.15

    # ------------------------------------------------------------------
    # On rembobine
    # ------------------------------------------------------------------
    def can_rewind(self, cause):
        g = self.game
        if g.is_multiplayer or config.diff("permadeath") or not g.saves.exists():
            return False
        if g.state.act not in (3, 4):
            return False
        used = int(g.state.flags.get("rewinds", 0) or 0)
        return used < REWIND_LIMIT.get(config.settings.get("difficulte", "Normal"), 99)

    def _rule_for(self, cause):
        order = ["lumiere", "contradiction", "code", "porte"]
        if cause == "door_open":
            pick = "porte"
        elif cause == "pourboire":
            pick = "contradiction" if "contradiction" not in self.learned else "lumiere"
        elif self.flag("code_given") and "code" not in self.learned:
            pick = "code"
        else:
            pick = next((r for r in order if r not in self.learned), random.choice(order))
        return pick

    def rewind(self, cause):
        """Après la frayeur : la cassette rembobine, retour au dernier point de sauvegarde, une règle est gravée."""
        g = self.game
        rule = self._rule_for(cause)
        rewinds = int(g.state.flags.get("rewinds", 0) or 0) + 1
        self._build_overlay()
        sound.play("rembobinage", 0.9, channel="sfx")
        self.overlay_t = 0.0
        self.overlay_rule = rule
        self.overlay_rewinds = rewinds
        self.overlay_phase = "rewind"

    def _build_overlay(self):
        if self.overlay is not None:
            destroy(self.overlay)
        o = Entity(parent=camera.ui, z=-40)
        self.overlay = o
        rect(o, 0, 0, 2.6, 1.4, rgb(4, 4, 8, 235), z=1)
        self.scan = []
        for i in range(14):
            self.scan.append(rect(o, 0, -0.5 + i * 0.075, 2.6, 0.006, rgb(220, 220, 255, 40), z=0.5))
        self.ov_title = label(o, "<<  REMBOBINAGE", -0.78, 0.4, 2.0, rgb(230, 230, 240), origin=(-0.5, 0), z=0, font=T.F_TYPE)
        self.ov_time = label(o, "02:47:00", 0.78, 0.4, 1.4, rgb(230, 230, 240), origin=(0.5, 0), z=0, font=T.F_TYPE)
        self.ov_text = label(o, "", 0, -0.02, 1.0, rgb(220, 214, 200), z=0, wrap=46, max_w=1.3, font=T.F_TYPE)

    def update_overlay(self, dt):
        """Appelé même hors partie (pendant le rechargement)."""
        if self.overlay is None:
            return
        self.overlay_t += dt
        t = self.overlay_t
        for i, s in enumerate(self.scan):
            s.y = ((-0.5 + i * 0.075 + t * (2.4 if self.overlay_phase == "rewind" else 0.2)) % 1.05) - 0.52
        if self.overlay_phase == "rewind":
            secs = max(0, int(2 * 3600 + 47 * 60 - t * 1600))
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            self.ov_time.text = f"{h:02d}:{m:02d}:{s:02d}"
            if t > 2.8:
                self.overlay_phase = "load"
                g = self.game
                g.continue_game()
                g.player.health = 100.0
                g.state.flags["rewinds"] = self.overlay_rewinds
                rule = self.overlay_rule
                if rule not in self.learned:
                    self.learned.append(rule)
                    self._save_rules()
                g.state.add_doc("regles")
                n = self.learned.index(rule) + 1
                self.ov_title.text = f"RÈGLE N°{n}"
                self.ov_time.text = ""
                self.ov_text.text = RULES[rule]
                self.overlay_t = 0.0
                self.overlay_phase = "rule"
                g.player.frozen = True
        elif self.overlay_phase == "rule":
            if t > 5.5:
                destroy(self.overlay)
                self.overlay = None
                self.game.player.frozen = False
                self.game.ui.hud.show()
