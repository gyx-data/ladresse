"""Chat d'assistance QuickEats : messages contradictoires, compte à rebours du livreur.

Chronologie (secondes) :
  première annulation + 120 s : messages 1-2-3 (« votre livreur est en chemin »)
  +20/+40 s  : paire 1 (lumières)      → évaluée à +110 s
  +125/+145  : paire 2 (étage)         → évaluée à +220 s
  +290/+310  : paire 3 (porte)         → évaluée au moment des coups à la porte
  +360 s : « arrive dans 2 minutes » (lumières qui clignotent, cœur géant)
  +420 s : « devant chez vous » (trois coups)
  +450 s : « entre dans la zone » (la porte s'ouvre en bas, pas sur le carrelage)
  +480 s : « Livraison effectuée » → l'entité est lâchée.
  Libération + 60/80 : paire 4 (bruit) ; +190/210 : paire 5 (sel).
"""
import game_data as gd
from sound_engine import engine as sound


class AssistanceSystem:
    def __init__(self, game):
        self.game = game
        self.reset()

    def reset(self):
        self.ts = 1.0             # échelle de temps (adresse piège : le livreur arrive plus vite)
        self.phase = 0            # 0 repos, 1 attente contact, 2 contact, 3 attente, 4 arrivée, 5 libéré
        self.t0 = None            # instant « livreur en chemin » (temps de jeu)
        self.release_t0 = None
        self.status_text = "En attente de votre commande."
        self.window = {}          # pair_id -> dict d'évaluation en cours
        self.knock_active = False
        self.door_opened_fatal = False
        self.salt_circle_until = 0.0
        self.salt_circle_pos = None
        self.light_samples = [0.0, 0.0]
        self.remote = False
        self.pairs_done = set()
        self._phase4_done = set()
        self.salt_truth_a = True
        self.messages_sent = 0

    # ------------------------------------------------------------------
    @property
    def timers(self):
        return self.game.timers

    def now(self):
        return self.game.timers.t

    def total(self):
        return gd.DELIVERY_TOTAL_SECONDS * self.ts

    def eta_seconds(self):
        if self.t0 is None:
            return None
        return max(0.0, self.total() - (self.now() - self.t0))

    def tracking_available(self):
        return self.t0 is not None and self.phase < 5

    # ------------------------------------------------------------------
    # Envoi d'un message de l'assistance
    # ------------------------------------------------------------------
    def send(self, text, notify=True):
        phone = self.game.phone
        phone.model.add_message("support", gd.CONTACT_SUPPORT, text)
        self.messages_sent += 1
        if notify:
            phone.notify("QuickEats Support", text, "icone_quickeats", target=("messages", "support"))
        if phone.is_open and phone.current == "messages":
            app = phone.apps["messages"]
            if app.page == "list" or app.conv == "support":
                app.render()
        self.game.quests.on_event("assistance_message")

    # ------------------------------------------------------------------
    # Phase 1 : première annulation
    # ------------------------------------------------------------------
    def on_first_cancel(self):
        if self.phase != 0:
            return
        self.phase = 1
        self.status_text = "Commande annulée."
        self.timers.after(gd.ASSIST_DELAY_AFTER_FIRST_CANCEL, self.start_contact)

    def start_contact(self):
        if self.phase != 1 or self.remote:
            return
        self.phase = 2
        d1, t1 = gd.ASSIST_INTRO[0]
        self.send(t1)
        d2, t2 = gd.ASSIST_INTRO[1]
        self.timers.after(d2, self._intro2, t2)
        self.timers.after(d2 + gd.ASSIST_INTRO[2][0], self._intro3, gd.ASSIST_INTRO[2][1])
        self.game.set_act(2)

    def _intro2(self, text):
        self.send(text)
        self.status_text = "Commande reprise par un livreur partenaire."

    def _intro3(self, text):
        self.send(text)
        self.start_delivery()

    # ------------------------------------------------------------------
    # Phase 3 : l'attente (8 minutes)
    # ------------------------------------------------------------------
    def start_delivery(self):
        self.phase = 3
        self.t0 = self.now()
        self.ts = 0.8 if self.game.state.address == "piege" else 1.0
        self.status_text = "Votre livreur est en chemin."
        self.game.set_act(3)
        self.game.save_checkpoint("livreur_en_chemin")
        if self.remote:
            return
        ts = self.ts
        for pid in (1, 2, 3):
            sch = gd.PAIR_SCHEDULE[pid]
            self.timers.after(sch["a"] * ts, self._send_option, pid, "A")
            self.timers.after(sch["b"] * ts, self._send_option, pid, "B")
            if sch["window_end"]:
                self.timers.after(sch["window_end"] * ts, self.evaluate, pid)
        for (remaining, notif, app_text) in gd.ASSIST_PHASE4:
            when = (gd.DELIVERY_TOTAL_SECONDS - remaining) * ts
            self.timers.after(when, self._phase4, remaining, notif, app_text)

    def _send_option(self, pid, opt):
        if self.remote:
            return
        self.send(gd.PAIRS[pid][opt])
        w = self.window.setdefault(pid, {"samples": 0, "light_on": 0, "start": self.now(), "talk_start": self.now()})
        if opt == "B":
            w["start"] = self.now()
            w["talk_start"] = self.now()
        self.game.quests.on_event("pair_shown", pair=pid, option=opt)

    def remote_option(self, pid, opt, text):
        """Message reçu du serveur (multijoueur)."""
        self.send(text)
        w = self.window.setdefault(pid, {"samples": 0, "light_on": 0, "start": self.now(), "talk_start": self.now()})
        if opt == "B":
            w["start"] = self.now()
            w["talk_start"] = self.now()
            sch = gd.PAIR_SCHEDULE[pid]
            if pid not in self.pairs_done and sch["window_end"]:
                self.timers.after((sch["window_end"] - sch["b"]) * 0.5, self.evaluate, pid)
            elif pid == 3:
                self.timers.after(35.0, self.evaluate, 3)

    # ------------------------------------------------------------------
    # Évaluation continue des fenêtres
    # ------------------------------------------------------------------
    def update(self, dt):
        game = self.game
        p = game.player
        # paire 1 : échantillonnage de la lampe
        w = self.window.get(1)
        if w is not None and 1 not in self.pairs_done and w.get("start") is not None:
            lit = p.flashlight.on or game.phone.model.torch_on
            w["samples"] += dt
            if lit:
                w["light_on"] += dt
        # cercle de sel
        if self.salt_circle_until > self.now() and self.salt_circle_pos is not None:
            game.entity.set_ward(self.salt_circle_pos, 2.2)
        elif self.salt_circle_pos is not None:
            game.entity.set_ward(None, 0)
            self.salt_circle_pos = None

    def level_sample(self):
        return self.game.player.level

    def truth(self, pid):
        if pid in gd.PAIR_FIXED_TRUTH:
            return gd.PAIR_FIXED_TRUTH[pid]
        if pid == 4:
            return gd.PAIR4_TRUTH.get(self.game.state.entity_type or "imposteur", "B")
        # paire 5 : dépend de l'état du sous-sol
        return "B" if self.game.state.flag("cave_open") else "A"

    def evaluate(self, pid):
        if pid in self.pairs_done:
            return
        game, state, p = self.game, self.game.state, self.game.player
        w = self.window.get(pid, {})
        choice = "B"
        if pid == 1:
            samples = max(w.get("samples", 0.0), 0.001)
            off_frac = 1.0 - w.get("light_on", 0.0) / samples
            choice = "B" if off_frac >= 0.55 else "A"
        elif pid == 2:
            choice = "B" if p.level >= 1 else "A"
        elif pid == 3:
            choice = "A" if self.door_opened_fatal else "B"
        elif pid == 4:
            choice = "A" if p.recent_talk(gd.PAIR_SCHEDULE[4]["window_end"] - gd.PAIR_SCHEDULE[4]["b"]) > 0 else "B"
        elif pid == 5:
            used = state.flag("sel_used") or state.flag("sel_touched")
            choice = "A" if used else "B"
        truth = self.truth(pid)
        self.pairs_done.add(pid)
        state.record_choice(pid, choice, truth)
        good = (choice == truth)
        game.quests.on_event("pair_done", pair=pid, good=good)
        game.on_choice_made(pid, choice, truth)
        self._apply_consequence(pid, choice, truth)
        if self.game.net:
            self.game.net.send_choice(pid, choice)

    def _apply_consequence(self, pid, choice, truth):
        ent = self.game.entity
        good = choice == truth
        if pid == 1:
            if not good:
                ent.detection_mult *= 1.5
                ent.light_attracted = True
            else:
                ent.detection_mult *= 0.9
        elif pid == 2:
            if not good:
                ent.speed_mult *= 1.1
                ent.release_near_player = True
        elif pid == 4:
            if not good:
                ent.detection_mult *= 1.3
                if choice == "A" and truth == "B":
                    ent.alert_to(self.game.player.pos)
            else:
                if truth == "A":
                    ent.stall(6.0)
        elif pid == 5:
            if choice == "A" and truth == "A":
                self.salt_circle_until = self.now() + 90.0
            if not good:
                ent.speed_mult *= 1.12
                ent.detection_mult *= 1.2

    # ------------------------------------------------------------------
    # Phase 4 : le livreur arrive
    # ------------------------------------------------------------------
    def _phase4(self, remaining, notif, app_text):
        if remaining in self._phase4_done:
            return
        self._phase4_done.add(remaining)
        game = self.game
        self.status_text = app_text
        if remaining == 120:
            self.phase = 4
            game.set_act(3)
            game.phone.notify("QuickEats", notif, "icone_quickeats", target=("quickeats",))
            game.quests.on_event("delivery_incoming")
            game.on_countdown_start()
        elif remaining == 60:
            game.phone.notify("QuickEats", notif, "icone_quickeats", target=("quickeats",))
            self.timers.after(0.5, self._knock, 0)
            self.timers.after(2.7, self._knock, 1)
            self.timers.after(4.9, self._knock, 2)
            self.timers.after(5.5, self._unlock_front)
            if self.game.state.entity_type == "imposteur":
                self.timers.after(7.5, self._impostor_door_line, 0)
                self.timers.after(13.0, self._impostor_door_line, 1)
            self.timers.after(30.0, self._end_knock_window)
        elif remaining == 30:
            game.phone.notify("QuickEats", notif, "icone_quickeats", target=("quickeats",))
            self.knock_active = False
            game.on_entity_enters()
        elif remaining == 0:
            self.release()

    def _knock(self, i):
        pos = self.game.front_door_pos()
        sound.play_at("coups_porte", pos, 1.0, ref=6.0)
        self.game.player.add_stress(6)
        self.game.player.shake(0.15, 0.3)
        if i == 2:
            self.knock_active = True

    def _unlock_front(self):
        door = self.game.house.doors["front"]
        door.locked = False
        sound.play_at("verrou", self.game.front_door_pos(), 0.9)
        self.game.state.set("front_unlocked_by_knock", True)

    def _end_knock_window(self):
        if 3 not in self.pairs_done:
            self.evaluate(3)

    def _impostor_door_line(self, idx):
        line = gd.IMPOSTOR_LINES[1 if idx else 0]
        pos = self.game.front_door_pos()
        sound.speak(line, f0=112, speed=0.95, pos=pos, volume=1.0, channel="sfx", speaker="Livreur")

    def front_door_opened(self):
        """Appelé quand le joueur ouvre la porte d'entrée : fatal pendant la fenêtre."""
        if self.knock_active and not self.door_opened_fatal:
            self.door_opened_fatal = True
            self.evaluate(3)
            self.game.kill_player("door_open")
            return True
        return False

    def release(self):
        """0 seconde : « Livraison effectuée ». L'entité est lâchée."""
        game = self.game
        self.phase = 5
        self.release_t0 = self.now()
        self.status_text = "Livraison effectuée."
        game.phone.notify("QuickEats", gd.ASSIST_PHASE4[-1][1], "icone_quickeats", sound_on=True)
        game.on_delivery_done()
        # paires de la phase de survie (en multijoueur, le serveur envoie les messages)
        for pid in (4, 5):
            sch = gd.PAIR_SCHEDULE[pid]
            if not self.remote:
                self.timers.after(sch["a"], self._send_option, pid, "A")
                self.timers.after(sch["b"], self._send_option, pid, "B")
            self.timers.after(sch["window_end"] * (0.5 if self.remote else 1.0), self.evaluate, pid)
        self.timers.after(12.0, self._rating_message)

    def _rating_message(self):
        self.send(gd.ASSIST_RATING.replace("*****", "(5 étoiles)"), notify=True)

    # ------------------------------------------------------------------
    # Sauvegarde
    # ------------------------------------------------------------------
    def to_dict(self):
        now = self.now()
        return dict(phase=self.phase, status=self.status_text, ts=self.ts,
                    elapsed=None if self.t0 is None else now - self.t0,
                    rel=None if self.release_t0 is None else now - self.release_t0,
                    pairs_done=sorted(self.pairs_done), salt_left=max(0.0, self.salt_circle_until - now))

    def restore(self, d):
        """Recrée la chronologie restante à partir du temps écoulé."""
        self.reset()
        self.phase = d.get("phase", 0)
        self.ts = d.get("ts", 1.0)
        self.status_text = d.get("status", "")
        self.pairs_done = set(d.get("pairs_done", []))
        now = self.now()
        el, rel = d.get("elapsed"), d.get("rel")
        if self.phase == 1:
            self.timers.after(10.0, self.start_contact)
        elif self.phase in (2, 3, 4) and el is not None:
            self.t0 = now - el
            for pid in (1, 2, 3):
                if pid in self.pairs_done:
                    continue
                sch = gd.PAIR_SCHEDULE[pid]
                for opt in ("a", "b"):
                    if sch[opt] * self.ts > el:
                        self.timers.after(sch[opt] * self.ts - el, self._send_option, pid, opt.upper())
                if sch["window_end"] and sch["window_end"] * self.ts > el:
                    self.timers.after(sch["window_end"] * self.ts - el, self.evaluate, pid)
            for (remaining, notif, app_text) in gd.ASSIST_PHASE4:
                when = (gd.DELIVERY_TOTAL_SECONDS - remaining) * self.ts
                if when > el:
                    self.timers.after(when - el, self._phase4, remaining, notif, app_text)
        elif self.phase == 5 and rel is not None:
            self.t0 = now - self.total() - rel
            self.release_t0 = now - rel
            for pid in (4, 5):
                if pid in self.pairs_done:
                    continue
                sch = gd.PAIR_SCHEDULE[pid]
                for opt in ("a", "b"):
                    if sch[opt] > rel:
                        self.timers.after(sch[opt] - rel, self._send_option, pid, opt.upper())
                if sch["window_end"] > rel:
                    self.timers.after(sch["window_end"] - rel, self.evaluate, pid)
        left = d.get("salt_left", 0.0)
        if left > 0:
            self.salt_circle_until = now + left

    # ------------------------------------------------------------------
    # Utilisation du sel (inventaire)
    # ------------------------------------------------------------------
    def use_salt(self):
        state = self.game.state
        if not state.has("sel"):
            return False
        state.remove_item("sel")
        state.set("sel_used", True)
        if self.truth_for_salt() == "A":
            self.salt_circle_pos = self.game.player.pos
            self.salt_circle_until = self.now() + 90.0
            self.game.draw_salt_circle(self.game.player.pos)
            self.game.say("Un cercle de sel. Quelque chose d'ancien me dit que ça tiendra.")
            self.game.player.relieve_stress(25)
        else:
            self.game.say("Le sel s'éparpille... c'était une erreur.")
            self.game.player.add_stress(20)
            self.game.entity.detection_mult *= 1.15
        return True

    def truth_for_salt(self):
        return "B" if self.game.state.flag("cave_open") else "A"
