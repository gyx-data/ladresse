"""Succès (façon Steam) : persistants entre les parties, notification animée au déblocage, écran récapitulatif.

Stockage : %APPDATA%/LADRESSE/succes.json. Les succès sont vérifiés à partir de l'état du jeu
(drapeaux, statistiques) une fois par seconde, ou débloqués directement via `unlock(id)`.
"""
import json
import os
import time

from ursina import Entity, camera, color

import config
from sound_engine import engine as sound
from ui_widgets import label, rect, button, rgb, panel

ACHIEVEMENTS = [
    # id, titre, description, secret
    ("arrivee", "Bienvenue à Nice", "Arriver rue des Lilas.", False),
    ("courses", "Liste de courses", "Payer à une caisse automatique.", False),
    ("fidele", "Client fidèle", "Créer une nouvelle carte fidélité.", False),
    ("garnier_card", "Il venait tous les soirs", "Consulter la carte fidélité de M. Garnier.", True),
    ("socca", "Brûlant", "Manger chez Nino.", False),
    ("bavard", "Le quartier parle", "Discuter 8 fois avec les habitants.", False),
    ("voleur", "Pas vu, pas pris", "Se faire arrêter par le vigile.", True),
    ("entree", "Le poste est à vous", "Entrer au 17 rue des Lilas.", False),
    ("troisieme", "Hors de son corps", "Jouer en vue troisième personne.", False),
    ("photo", "Pièce par pièce", "Prendre 10 photos.", False),
    ("revelation", "Ce que l'œil ne voit pas", "Révéler 3 choses avec l'appareil photo.", True),
    ("mort", "Livraison effectuée", "Être livré pour la première fois.", False),
    ("fin_a", "Fin A", "Découvrir la fin A.", True),
    ("fin_b", "Fin B", "Découvrir la fin B.", True),
    ("fin_c", "Fin C", "Découvrir la fin C.", True),
    ("fin_d", "Fin D", "Découvrir la fin D.", True),
    ("coop", "On est plus forts à plusieurs", "Lancer une partie coopérative.", False),
    ("cauchemar", "Insomniaque", "Terminer une fin en difficulté Cauchemar.", False),
]
BY_ID = {a[0]: a for a in ACHIEVEMENTS}


class Achievements:
    def __init__(self, game):
        self.game = game
        self.path = os.path.join(config.app_data_dir(), "succes.json")
        self.unlocked = {}
        self.queue = []
        self.toast = None
        self.toast_t = 0.0
        self.check_t = 0.0
        self.screen = None
        self.load()

    # --- persistance --------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.unlocked = {k: v for k, v in d.get("unlocked", {}).items() if k in BY_ID}
        except (OSError, ValueError):
            self.unlocked = {}

    def save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"unlocked": self.unlocked}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # --- déblocage ------------------------------------------------------------
    def unlock(self, aid):
        if aid not in BY_ID or aid in self.unlocked:
            return False
        self.unlocked[aid] = time.strftime("%d/%m/%Y %H:%M")
        self.save()
        self.queue.append(aid)
        return True

    def check(self):
        g = self.game
        st = g.state
        f = st.flags
        stats = st.stats
        if f.get("courses_faites"):
            self.unlock("courses")
        if stats.get("repas", 0) > 0:
            self.unlock("socca")
        if stats.get("discussions", 0) >= 8:
            self.unlock("bavard")
        if f.get("play_started"):
            self.unlock("entree")
        if stats.get("photos", 0) >= 10:
            self.unlock("photo")
        if stats.get("photos_reveal", 0) >= 3:
            self.unlock("revelation")
        if stats.get("deaths", 0) > 0:
            self.unlock("mort")
        if config.settings["vue"] == "Troisième personne" and g.mode == "playing":
            self.unlock("troisieme")
        if st.ending:
            self.unlock("fin_" + str(st.ending).lower())
            if config.settings.get("difficulte") == "Cauchemar":
                self.unlock("cauchemar")
        if g.is_multiplayer:
            self.unlock("coop")
        nb = getattr(g, "neighborhood", None)
        if nb is not None:
            if nb.active:
                self.unlock("arrivee")
            if nb.theft_warnings > 0:
                self.unlock("voleur")
            if nb.loyalty.data["next_number"] > 9531700002:
                self.unlock("fidele")
            if nb.checkout.page == "garnier":
                self.unlock("garnier_card")

    # --- notification -----------------------------------------------------------
    def update(self, dt):
        self.check_t -= dt
        if self.check_t <= 0:
            self.check_t = 1.0
            try:
                self.check()
            except Exception:
                pass
        if self.toast is not None:
            self.toast_t -= dt
            k = min(1.0, (4.5 - self.toast_t) / 0.35, self.toast_t / 0.35)
            self.toast.x = 0.62 + (1 - max(0.0, k)) * 0.5
            self.toast.audit_skip = k < 0.999
            if self.toast_t <= 0:
                self.toast.enabled = False
                from ursina import destroy
                destroy(self.toast)
                self.toast = None
        elif self.queue:
            self._show(self.queue.pop(0))

    def _show(self, aid):
        _, title, desc, _ = BY_ID[aid]
        r = Entity(parent=camera.ui, z=-30, position=(1.1, 0.36))
        panel(r, 0, 0, 0.42, 0.1, "card", z=0.1, radius=0.25)
        rect(r, -0.17, 0, 0.06, 0.06, rgb(226, 140, 50), z=0.05, radius=0.3)
        label(r, "★", -0.17, 0, 1.4, color.white, z=0)
        label(r, "SUCCÈS DÉBLOQUÉ", -0.13, 0.024, 0.5, rgb(240, 170, 90), origin=(-0.5, 0), z=0, max_w=0.32)
        label(r, title, -0.13, 0.0, 0.8, color.white, origin=(-0.5, 0), z=0, max_w=0.33)
        label(r, desc, -0.13, -0.026, 0.5, rgb(180, 180, 190), origin=(-0.5, 0), z=0, max_w=0.33)
        r.audit_skip = True          # pendant l'animation d'entrée / sortie
        self.toast = r
        self.toast_t = 4.5
        sound.play("caisse_ok", 0.45, pitch=1.2, channel="voice")

    # --- écran récapitulatif ------------------------------------------------------
    def open_screen(self, on_close=None):
        from ursina import destroy
        if self.screen is not None:
            destroy(self.screen)
        r = Entity(parent=camera.ui, z=-25)
        self.screen = r
        rect(r, 0, 0, 2.6, 1.4, rgb(0, 0, 0, 210), z=2)
        panel(r, 0, 0, 1.4, 0.88, "panel", z=1.5)
        n = len(self.unlocked)
        label(r, "SUCCÈS", -0.65, 0.39, 1.7, color.white, origin=(-0.5, 0), z=1)
        label(r, f"{n} / {len(ACHIEVEMENTS)} débloqués", 0.65, 0.39, 0.8, rgb(240, 170, 90), origin=(0.5, 0), z=1)
        for i, (aid, title, desc, secret) in enumerate(ACHIEVEMENTS):
            col, row = i % 2, i // 2
            x = -0.34 + col * 0.68
            y = 0.3 - row * 0.072
            got = aid in self.unlocked
            rect(r, x, y, 0.66, 0.064, rgb(255, 255, 255, 14 if got else 6), z=1, radius=0.2)
            rect(r, x - 0.3, y, 0.042, 0.042, rgb(226, 140, 50) if got else rgb(60, 60, 66), z=0.9, radius=0.3)
            label(r, "★" if got else "?", x - 0.3, y, 0.9, color.white if got else rgb(140, 140, 146), z=0.8)
            t = title if (got or not secret) else "Succès secret"
            d = desc if (got or not secret) else "Continuez à jouer pour le découvrir."
            label(r, t, x - 0.27, y + 0.012, 0.66, color.white if got else rgb(170, 170, 176), origin=(-0.5, 0), z=0.8, max_w=0.58)
            label(r, d + (f"  ·  {self.unlocked[aid]}" if got else ""), x - 0.27, y - 0.016, 0.46, rgb(150, 150, 158),
                  origin=(-0.5, 0), z=0.8, max_w=0.58)

        def close():
            destroy(r)
            self.screen = None
            if on_close:
                on_close()
        button(r, "Retour", 0, -0.4, 0.22, 0.055, close, style="primary", size=0.8, z=0.5)
        return r
