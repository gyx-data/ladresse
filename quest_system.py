"""Système de quêtes / objectifs avec suivi par événements.

Quêtes principales : Explorer → Commander → Comprendre l'annulation → Survivre au Livreur →
Le sous-sol.

Enchaînement scénarisé : la commande confirmée est annulée 30 s plus tard (« fonds insuffisants ») ; le joueur
doit vérifier l'appli bancaire, appeler la banque puis réessayer de commander. Ce n'est qu'ensuite que
l'assistance QuickEats le contacte et qu'un « livreur partenaire » se met en route (assistance_system). Quête optionnelle : l'histoire de Garnier. Quêtes secondaires : piles, photos,
pièces, documents.
"""
import game_data as gd

RDC_ROOMS = ["couloir0", "salon", "cuisine", "bureau", "hall0", "sdb0", "buanderie"]
ALL_ROOMS = RDC_ROOMS + ["couloir1", "palier", "branche", "master", "amis", "placard", "condamnee", "sdb1", "grenier", "sous_sol"]
MAIN_ORDER = ["explorer", "commander", "comprendre", "survivre", "favoris", "sous_sol"]


class Quest:
    def __init__(self, qid):
        d = gd.QUESTS[qid]
        self.id = qid
        self.title = d["title"]
        self.objective = d["objective"]
        self.steps = list(d["steps"])
        self.done_steps = set()
        self.active = False
        self.complete = False

    def step_label(self):
        for key, label in self.steps:
            if key not in self.done_steps:
                return label
        return None

    def to_dict(self):
        return dict(active=self.active, complete=self.complete, steps=sorted(self.done_steps))

    def from_dict(self, d):
        self.active = d.get("active", False)
        self.complete = d.get("complete", False)
        self.done_steps = set(d.get("steps", []))


class QuestSystem:
    def __init__(self, game):
        self.game = game
        self.quests = {qid: Quest(qid) for qid in gd.QUESTS}
        self.hungry_triggered = False
        self.secondary = {sid: 0 for sid, _, _ in gd.SECONDARY_QUESTS}
        self.secondary_done = set()

    # ------------------------------------------------------------------
    def reset(self):
        self.__init__(self.game)

    def start(self, qid, silent=False):
        q = self.quests[qid]
        if q.active or q.complete:
            return
        q.active = True
        if not silent:
            self.game.ui.notify_quest("Nouvel objectif : " + q.objective)
        # le bandeau d'objectif du HUD n'est recalculé que sur demande : sans cela il gardait l'objectif précédent
        # (« Attendre votre commande » après l'annulation, documents de Garnier au lieu de « Commander »...)
        self.game.ui.refresh_objective()

    def complete(self, qid):
        q = self.quests[qid]
        if q.complete:
            return
        q.complete = True
        q.active = False
        self.game.ui.refresh_objective()

    # quêtes dont les étapes peuvent être accomplies avant que la quête n'apparaisse (planches arrachées tôt,
    # paires d'assistance évaluées...) : l'étape est retenue et l'objectif affiché saute directement à la suivante
    PRE_RECORD = ("survivre", "sous_sol", "favoris")

    def step(self, qid, key):
        q = self.quests[qid]
        if qid == "commander" and not q.active and not q.complete:
            self.start(qid, silent=True)
        if q.complete or key in q.done_steps or key not in [k for k, _ in q.steps]:
            return
        if not q.active and qid not in self.PRE_RECORD:
            return
        q.done_steps.add(key)
        if not q.active:
            return
        nxt = q.step_label()
        if nxt:
            self.game.ui.notify_quest(f"{q.title} — {nxt}")
        self.game.ui.refresh_objective()
        if qid == "comprendre":
            self._after_investigation_step(key)

    def investigation_done(self):
        q = self.quests["comprendre"]
        return q.complete or all(k in q.done_steps for k, _ in q.steps)

    def is_active(self, qid):
        return self.quests[qid].active

    # ------------------------------------------------------------------
    def current_objective(self):
        """Texte de l'objectif affiché dans le HUD (toujours calé sur l'état réel de la partie)."""
        st = self.game.state
        a = getattr(self.game, "assistance", None)
        for qid in reversed(MAIN_ORDER):
            q = self.quests[qid]
            if not q.active or q.complete:
                continue
            if qid == "explorer":
                if st.flag("order_placed") and not st.flag("order_cancelled"):
                    return gd.OBJ_WAIT_ORDER
                left = [r for r in RDC_ROOMS if r not in st.rooms_visited]
                return f"{q.objective} ({len(RDC_ROOMS) - len(left)}/{len(RDC_ROOMS)})"
            lbl = q.step_label()
            if qid == "favoris" and lbl is not None and "favoris" in q.done_steps:
                lbl += f" ({len(self.game.favoris.salt_lines())}/3)"
            if qid == "sous_sol" and q.step_label() is not None and "planches" not in q.done_steps \
                    and not st.has("pied_de_biche"):
                lbl = gd.OBJ_FIND_CROWBAR
            if qid == "comprendre" and lbl is None:
                lbl = gd.OBJ_READ_SUPPORT if (a is not None and a.phase >= 2) else gd.OBJ_WAIT_SUPPORT
            return f"{q.objective}" + (f"\n  > {lbl}" if lbl else "")
        if st.flag("order_placed") and not st.flag("order_cancelled"):
            return gd.OBJ_WAIT_ORDER
        g = self.quests["garnier"]
        if g.active and not g.complete:
            return f"{g.objective} ({st.docs_required_found}/{len(gd.REQUIRED_DOCS)})"
        return ""

    # ------------------------------------------------------------------
    # Événements du jeu
    # ------------------------------------------------------------------
    def on_event(self, name, **kw):
        g = self.game
        st = g.state
        if name == "game_started":
            self.start("explorer", silent=True)
            self.start("garnier", silent=True)
        elif name == "room_entered":
            self._check_explore()
            self._check_secondary()
        elif name == "phone_opened":
            self.step("commander", "phone")
        elif name == "app_opened":
            if kw.get("app") == "quickeats":
                self.step("commander", "app")
        elif name == "bank_checked":
            # le relevé affiche le paiement refusé (alors que le solde est suffisant)
            self.step("comprendre", "bank")
        elif name == "address_found":
            if kw.get("key") in ("bonne", "piege"):
                self.step("commander", "addr_found")
        elif name == "address_entered":
            self.step("commander", "addr_found")
            self.step("commander", "addr_entered")
        elif name == "meal_chosen":
            self.step("commander", "meal")
        elif name == "order_confirmed":
            self.step("commander", "confirm")
            self.complete("commander")
        elif name == "first_cancel":
            self.start("comprendre")
            self._hint_later(8.0, "bank")
        elif name == "call_started":
            if kw.get("kind") == "bank":
                self.step("comprendre", "call")
        elif name == "call_ended":
            if kw.get("kind") == "bank":
                self._hint_later(3.0, "retry")
        elif name == "order_failed":
            self.step("comprendre", "retry")
        elif name == "assistance_message":
            # premier message de l'assistance : « Attendre une réponse » devient « Lire les messages »
            g.ui.refresh_objective()
        elif name == "delivery_started":
            # « Votre livreur est en chemin » : l'enquête est close, place à la survie
            self.complete("comprendre")
            self.start("survivre")
            if not g.is_multiplayer:
                g.timers.after(12.0, self.start, "favoris")
        elif name == "favoris_phone":
            self.step("favoris", "telephone")
        elif name == "favoris_code":
            self.step("favoris", "telephone")
            self.step("favoris", "code")
        elif name == "favoris_deleted":
            self.step("favoris", "favoris")
        elif name == "favoris_salt":
            g.ui.refresh_objective()
        elif name == "favoris_done":
            self.step("favoris", "sel")
            self.complete("favoris")
        elif name == "pair_done":
            pid = kw.get("pair")
            q = self.quests["survivre"]
            if not q.active and not q.complete:
                self.start("survivre", silent=True)
                self.complete("comprendre")
            self.step("survivre", f"p{pid}")
            if len(q.done_steps) >= len(q.steps):
                self.complete("survivre")
                self.complete("comprendre")
                self.start("sous_sol")
        elif name == "delivery_incoming":
            self.start("survivre")
            self.complete("comprendre")
        elif name == "delivery_done":
            # l'entité est lâchée : le seul moyen d'en finir est en bas
            self.start("sous_sol")
            self.game.ui.refresh_objective()
        elif name == "doc_found":
            self._check_secondary()
            g.ui.refresh_objective()
        elif name == "planks_removed":
            self.step("sous_sol", "planches")
        elif name == "descended":
            self.step("sous_sol", "descendre")
        elif name == "freezer_opened":
            self.step("sous_sol", "congelateur")
        elif name == "message_read":
            self.step("sous_sol", "message")
        elif name == "final":
            self.step("sous_sol", "final")
            self.complete("sous_sol")
        elif name in ("item_picked", "photo_taken"):
            self._check_secondary()

    # ------------------------------------------------------------------
    # Enquête sur l'annulation (banque → appel → nouvelle tentative)
    # ------------------------------------------------------------------
    HINTS = {"bank": "LINE_CHECK_BANK", "call": "LINE_CALL_BANK", "retry": "LINE_RETRY_ORDER"}

    def _after_investigation_step(self, key):
        if self.investigation_done():
            # tout est vérifié : l'assistance QuickEats peut (enfin) se manifester
            self.game.assistance.on_investigation_done()
            self.game.ui.refresh_objective()
            return
        q = self.quests["comprendre"]
        nxt = next(k for k, _ in q.steps if k not in q.done_steps)
        if key == "bank" and nxt == "call":
            self._hint_later(2.5, "call")
        elif key == "retry" and nxt == "call":
            self._hint_later(3.0, "call")

    def _hint_later(self, delay, step):
        self.game.timers.after(delay, self._hint, step)

    def _hint(self, step):
        """Pensée d'Adrien (sous-titre) si l'étape attendue n'est toujours pas faite."""
        q = self.quests["comprendre"]
        if not q.active or q.complete or step in q.done_steps:
            return
        need = {"bank": (), "call": ("bank",), "retry": ("bank", "call")}[step]
        if any(k not in q.done_steps for k in need):
            return
        self.game.say(getattr(gd, self.HINTS[step]))

    def _check_explore(self):
        st = self.game.state
        q = self.quests["explorer"]
        if q.active and all(r in st.rooms_visited for r in RDC_ROOMS):
            self.complete("explorer")
            self.game.on_exploration_done()
        else:
            self.game.ui.refresh_objective()

    def _check_secondary(self):
        st = self.game.state
        self.secondary["piles"] = st.flags.get("piles_found", 0)
        self.secondary["photos"] = st.stats.get("photos_reveal", 0)
        self.secondary["pieces"] = len([r for r in ALL_ROOMS if r in st.rooms_visited])
        self.secondary["docs"] = st.docs_required_found
        goals = {"piles": 5, "photos": 10, "pieces": len(ALL_ROOMS), "docs": len(gd.REQUIRED_DOCS)}
        for sid, goal in goals.items():
            if self.secondary[sid] >= goal and sid not in self.secondary_done:
                self.secondary_done.add(sid)
                title = [t for s, t, _ in gd.SECONDARY_QUESTS if s == sid][0]
                self.game.ui.notify_quest(f"Quête secondaire terminée : {title}")
        if st.docs_required_found >= len(gd.REQUIRED_DOCS):
            self.complete("garnier")

    # ------------------------------------------------------------------
    def to_dict(self):
        return dict(q={qid: q.to_dict() for qid, q in self.quests.items()}, sec=self.secondary, done=sorted(self.secondary_done),
                    hungry=self.hungry_triggered)

    def from_dict(self, d):
        for qid, qd in d.get("q", {}).items():
            if qid in self.quests:
                self.quests[qid].from_dict(qd)
        self.secondary.update(d.get("sec", {}))
        self.secondary_done = set(d.get("done", []))
        self.hungry_triggered = d.get("hungry", False)
