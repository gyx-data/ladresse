"""Système de quêtes / objectifs avec suivi par événements.

Quêtes principales : Explorer → Commander → Comprendre l'annulation → Survivre au Livreur →
Le sous-sol. Quête optionnelle : l'histoire de Garnier. Quêtes secondaires : piles, photos,
pièces, documents.
"""
import game_data as gd

RDC_ROOMS = ["couloir0", "salon", "cuisine", "bureau", "hall0", "sdb0", "buanderie"]
ALL_ROOMS = RDC_ROOMS + ["couloir1", "palier", "branche", "master", "amis", "placard", "condamnee", "sdb1", "grenier", "sous_sol"]
MAIN_ORDER = ["explorer", "commander", "comprendre", "survivre", "sous_sol"]


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

    def complete(self, qid):
        q = self.quests[qid]
        if q.complete:
            return
        q.complete = True
        q.active = False
        self.game.ui.refresh_objective()

    def step(self, qid, key):
        q = self.quests[qid]
        if not q.active or key in q.done_steps:
            return
        if key not in [k for k, _ in q.steps]:
            return
        q.done_steps.add(key)
        nxt = q.step_label()
        if nxt:
            self.game.ui.notify_quest(f"{q.title} — {nxt}")
        self.game.ui.refresh_objective()

    def is_active(self, qid):
        return self.quests[qid].active

    # ------------------------------------------------------------------
    def current_objective(self):
        """Texte de l'objectif affiché dans le HUD."""
        for qid in MAIN_ORDER:
            q = self.quests[qid]
            if q.active and not q.complete:
                lbl = q.step_label()
                if qid == "explorer":
                    left = [r for r in RDC_ROOMS if r not in self.game.state.rooms_visited]
                    return f"{q.objective} ({len(RDC_ROOMS) - len(left)}/{len(RDC_ROOMS)})"
                return f"{q.objective}" + (f"\n  > {lbl}" if lbl else "")
        g = self.quests["garnier"]
        if g.active and not g.complete:
            return f"{g.objective} ({self.game.state.docs_required_found}/{len(gd.REQUIRED_DOCS)})"
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
            app = kw.get("app")
            if app == "quickeats":
                self.step("commander", "app")
            elif app == "banque":
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
        elif name == "call_started":
            if kw.get("kind") == "bank":
                self.step("comprendre", "call")
        elif name == "order_failed":
            if st.order_failed >= 2:
                self.step("comprendre", "retry")
        elif name == "pair_done":
            pid = kw.get("pair")
            self.step("survivre", f"p{pid}")
            q = self.quests["survivre"]
            if len(q.done_steps) >= 5:
                self.complete("survivre")
                self.complete("comprendre")
                self.start("sous_sol")
        elif name == "delivery_incoming":
            self.start("survivre")
            self.complete("comprendre")
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
