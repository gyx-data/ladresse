"""Didacticiel guidé, doublé à la voix : une étape à la fois, avec les touches réelles (reconfigurables)
affichées en touches de clavier, un carillon d'apparition, une validation automatique quand le joueur
fait l'action, et un délai maximal pour ne jamais bloquer la partie.

Désactivable dans Paramètres → Jeu → « Didacticiel ».
"""
from ursina import Entity, camera, color

import config
from config import settings
import ui_theme as theme
from sound_engine import engine as sound
from ui_widgets import label, rect, panel, rgb, set_label, clear

KEY_NAMES = {"left shift": "MAJ", "right shift": "MAJ", "space": "ESPACE", "tab": "TAB", "escape": "ÉCHAP",
             "left mouse": "CLIC", "enter": "ENTRÉE", "backspace": "RETOUR", "left control": "CTRL", "scroll up": "MOLETTE"}


def key_label(action):
    """Nom affiché d'une touche ; en AZERTY on montre Z/Q (acceptées en plus de W/A)."""
    k = settings.key(action)
    alt = config.ALT_KEYS.get(action)
    if alt and k == config.DEFAULT_KEYS[action]:
        k = alt
    return KEY_NAMES.get(k, k.upper())


class Tutorial:
    W = 0.5

    STEPS = [
        dict(id="deplacement", phase="dehors", keys=["avancer", "gauche", "reculer", "droite"],
             text="Déplacez-vous avec {avancer} {gauche} {reculer} {droite}, et regardez autour de vous avec la souris.",
             voice="Pour vous déplacer, utilisez les touches de direction. La souris sert à regarder autour de vous.", timeout=30),
        dict(id="course", phase="dehors", keys=["sprint", "accroupir"],
             text="Maintenez {sprint} pour courir, {accroupir} pour vous accroupir. La course fatigue et fait du bruit.",
             voice="Vous pouvez courir, ou vous accroupir pour rester discret. Courir fait du bruit. Souvenez-vous-en.", timeout=25),
        dict(id="vue", phase="dehors", keys=["vue"],
             text="{vue} : basculer entre la vue à la première et à la troisième personne.",
             voice="Vous pouvez passer à la troisième personne à tout moment. Essayez maintenant.", timeout=20),
        dict(id="interagir", phase="dehors", keys=["interagir"],
             text="Approchez-vous d'un habitant ou d'un objet et appuyez sur {interagir} pour interagir.",
             voice="Approchez-vous d'un habitant, ou d'un objet, et appuyez sur la touche d'interaction.", timeout=40),
        dict(id="telephone", phase="dehors", keys=["telephone"],
             text="{telephone} : sortir le téléphone. Banque, messages, QuickEats... et l'appareil photo.",
             voice="Sortez votre téléphone. Tout passe par lui ce soir : vos messages, votre banque, et l'appareil photo.",
             timeout=35),
        dict(id="courses", phase="dehors", keys=["interagir"],
             text="Le Carrefour City est ouvert : prenez des articles avec {interagir}, puis payez aux caisses automatiques.",
             voice="La supérette est encore ouverte. Des piles, de l'eau, du sel... Ça pourrait servir.", timeout=25,
             trigger="near_shop"),
        dict(id="maison", phase="dehors", keys=[],
             text="Quand vous êtes prêt, entrez au 17 rue des Lilas. La nuit commencera vraiment.",
             voice="Quand vous serez prêt, entrez dans la maison. Après, il sera trop tard pour faire demi-tour.", timeout=14,
             trigger="near_house"),
        dict(id="lampe", phase="maison", keys=["lampe"],
             text="{lampe} : allumer / éteindre la lampe torche. Molette : faisceau large ou concentré.",
             voice="Allumez votre lampe torche. La molette règle le faisceau. Surveillez la batterie.", timeout=30),
        dict(id="inventaire", phase="maison", keys=["inventaire"],
             text="{inventaire} : ouvrir l'inventaire. Utilisez vos piles, vos objets, relisez les documents trouvés.",
             voice="Votre inventaire contient vos objets et les documents que vous trouverez. Utilisez-les.", timeout=30),
        dict(id="photo", phase="maison", keys=["telephone"],
             text="Dans le téléphone, l'appareil photo révèle parfois ce que l'œil ne voit pas.",
             voice="Une dernière chose. L'appareil photo voit parfois ce que vos yeux refusent de voir.", timeout=16),
    ]

    def __init__(self, game):
        self.game = game
        self.root = Entity(parent=camera.ui, z=-6, enabled=False)
        self.cur = None
        self.t = 0.0
        self.done = set()
        self.gap = 2.0
        self.success_t = 0.0
        self.base = {}
        self.forced = False
        self.voice = None

    # ------------------------------------------------------------------
    @property
    def enabled(self):
        return bool(settings.get("didacticiel", True)) and not self.game.is_multiplayer

    def reset(self):
        self.done = set()
        self.cur = None
        self.gap = 3.0
        self.hide()

    def hide(self):
        self.root.enabled = False
        self.cur = None
        self.forced = False
        self.stop_voice()

    def stop_voice(self):
        h, self.voice = self.voice, None
        try:
            if h is not None:
                h.stop()
        except Exception:
            pass

    def set_enabled(self, on):
        """Active / coupe le didacticiel tout de suite (paramètres, menu pause)."""
        settings["didacticiel"] = bool(on)
        settings.save()
        if not on:
            self.hide()

    def force(self, sid):
        """Affiche une étape précise (tests d'interface)."""
        step = next(s for s in self.STEPS if s["id"] == sid)
        self._show(step, voice=False)
        self.forced = True

    # ------------------------------------------------------------------
    def _phase(self):
        nb = self.game.neighborhood
        return "dehors" if nb is not None and nb.outside_phase else "maison"

    def _trigger_ok(self, step):
        tr = step.get("trigger")
        p = self.game.player.pos
        if tr == "near_shop":
            from neighborhood import SHOP_DOOR_X, SHOP
            return ((p[0] - SHOP_DOOR_X) ** 2 + (p[2] - SHOP[3]) ** 2) ** 0.5 < 14
        if tr == "near_house":
            return ((p[0] - 7.0) ** 2 + (p[2] + 3.0) ** 2) ** 0.5 < 9
        return True

    def _next_step(self):
        ph = self._phase()
        for s in self.STEPS:
            if s["id"] in self.done or s["phase"] != ph:
                continue
            if self._trigger_ok(s):
                return s
            if s.get("trigger"):
                continue            # étape contextuelle : on passe aux suivantes en attendant
            return None
        return None

    def _show(self, step, voice=True):
        self.cur = step
        self.t = 0.0
        self.success_t = 0.0
        g = self.game
        p = g.player
        self.base = dict(pos=Vec3c(p.pos), sprint=False, crouch=False, view=settings["vue"], phone=g.phone.is_open,
                         flash=p.flashlight.on, inv=g.inv_panel.visible, uses=getattr(g.interactions, "uses", 0),
                         basket=g.neighborhood.basket.count if g.neighborhood is not None else 0)
        clear(self.root)
        r = self.root
        h = 0.135
        x, y = -0.86 + self.W / 2, 0.24
        self.bg = panel(r, x, y, self.W, h, "panel", z=0.2, radius=0.12)
        rect(r, x - self.W / 2 + 0.008, y, 0.005, h - 0.03, rgb(170, 22, 20), z=0.1, radius=0.5)
        label(r, "DIDACTICIEL", x - self.W / 2 + 0.025, y + h / 2 - 0.02, 0.5, rgb(190, 40, 36), origin=(-0.5, 0), z=0)
        idx = [s["id"] for s in self.STEPS].index(step["id"]) + 1
        label(r, f"{idx}/{len(self.STEPS)}", x + self.W / 2 - 0.02, y + h / 2 - 0.02, 0.5, rgb(140, 138, 134), origin=(0.5, 0), z=0)
        # touches
        kx = x - self.W / 2 + 0.042
        ky = y + 0.012
        for a in step["keys"]:
            lab = key_label(a)
            w = 0.034 if len(lab) <= 2 else 0.016 * len(lab) + 0.02
            tex, _ = theme.keycap_texture(lab, 64) if len(lab) <= 2 else (None, 0)
            if tex is not None:
                Entity(parent=r, model="quad", texture=tex, position=(kx, ky, 0), scale=0.036)
            else:
                panel(r, kx + w / 2 - 0.018, ky, w, 0.03, "key", z=0.05, radius=0.25)
                label(r, lab, kx + w / 2 - 0.018, ky, 0.45, color.white, z=0, max_w=w - 0.008)
                kx += w - 0.036
            kx += 0.042
        txt = step["text"].format(**{a: key_label(a) for a in config.DEFAULT_KEYS})
        ty = y - (0.022 if step["keys"] else -0.005)
        self.text = label(r, txt, x - self.W / 2 + 0.025, ty, 0.62, rgb(236, 234, 228), origin=(-0.5, 0), z=0,
                          wrap=56, max_w=self.W - 0.045, max_h=0.072 if step["keys"] else 0.09)
        self.check = label(r, "", x + self.W / 2 - 0.03, y - h / 2 + 0.02, 0.7, rgb(120, 220, 140), z=0)
        label(r, "Couper : Échap > Didacticiel", x + self.W / 2 - 0.02, y - h / 2 - 0.016, 0.42, rgb(120, 116, 110),
              origin=(0.5, 0), z=0)
        self.root.enabled = True
        if voice:
            sound.play("tuto_carillon", 0.5, channel="voice")
            self.stop_voice()
            self.voice = sound.speak(step["voice"], f0=205, speed=1.0, volume=0.85, channel="voice", subtitle=False,
                                     speaker="Didacticiel")

    def _completed(self, step):
        g = self.game
        p = g.player
        b = self.base
        sid = step["id"]
        if sid == "deplacement":
            return (Vec3c(p.pos) - b["pos"]).length() > 3.0
        if sid == "course":
            return p.sprinting or p.crouching
        if sid == "vue":
            return settings["vue"] != b["view"]
        if sid in ("interagir", "courses"):
            nb = g.neighborhood
            return getattr(g.interactions, "uses", 0) > b["uses"] or (nb is not None and nb.basket.count > b["basket"])
        if sid in ("telephone", "photo"):
            return g.phone.is_open and not b["phone"] or g.camera_mode
        if sid == "lampe":
            return p.flashlight.on != b["flash"]
        if sid == "inventaire":
            return g.inv_panel.visible
        return False

    def update(self, dt):
        g = self.game
        if self.forced:
            return
        if not self.enabled or g.mode != "playing" or g.paused:
            if self.root.enabled and (not self.enabled or g.mode != "playing"):
                self.root.enabled = False
                self.cur = None
            if not self.enabled:
                self.stop_voice()
            return
        if self.cur is None:
            self.gap -= dt
            if self.gap > 0:
                return
            step = self._next_step()
            if step is not None:
                self._show(step)
            else:
                self.gap = 1.0
            return
        # une fenêtre est ouverte (inventaire, caisse...) : on masque le panneau, sans perdre l'étape
        modal = g.modal_open() and self.cur["id"] != "inventaire"
        self.root.enabled = not modal
        if modal:
            return
        self.t += dt
        if self.success_t > 0:
            self.success_t -= dt
            if self.success_t <= 0:
                self.done.add(self.cur["id"])
                self.root.enabled = False
                self.cur = None
                self.gap = 2.5
            return
        if self._completed(self.cur):
            set_label(self.check, "OK")
            sound.play("tuto_ok", 0.55, channel="voice")
            self.success_t = 1.3
        elif self.t > self.cur.get("timeout", 25):
            self.done.add(self.cur["id"])
            self.root.enabled = False
            self.cur = None
            self.gap = 2.0


def Vec3c(v):
    from ursina import Vec3
    return Vec3(v[0], v[1], v[2])
