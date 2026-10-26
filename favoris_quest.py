"""Quête « Rayé des favoris » (solo) : le but de la nuit de livraison, et la seule fin où il repart.

« Votre adresse a été ajoutée à mes favoris. » Tant que le 17 est dans ses favoris, il revient. Pour l'en retirer :
  1. récupérer le vieux téléphone de Garnier (tiroir de la chambre d'amis) : l'écran est mort mais la carte SIM marche
     dans le téléphone d'Adrien, et le compte QuickEats de Garnier écrit par SMS (conversation « Compte de M. Garnier ») ;
  2. retrouver son code à 4 chiffres : l'année de la fête des voisins (photo chez Mme Bianchi, fond d'écran de Garnier) ;
  3. répondre SUPPRIMER pour retirer « 17 rue des Lilas » de ses adresses — il le sent, et il cherche une autre entrée ;
  4. tracer une ligne de sel (salière de la cuisine) devant les trois entrées du rez-de-chaussée.
Tout fait sans lui avoir donné le code du portail : « Adresse introuvable », il repart (fin E).
"""
from ursina import Entity, destroy

import game_data as gd
from room_builder import MeshBuilder
from sound_engine import engine as sound

CONV = "garnier"
NAME = "Compte de M. Garnier"
PIN = "1998"
# entrées du rez-de-chaussée à protéger : (id, centre de la ligne au sol, axe de la ligne, libellé)
ENTRANCES = (("porte", (7.0, 0.0, 0.45), "x", "la porte d'entrée"),
             ("salon", (1.5, 0.0, 0.45), "x", "la fenêtre du salon"),
             ("bureau", (15.55, 0.0, 2.2), "z", "la fenêtre du bureau"))


class FavorisQuest:
    def __init__(self, game):
        self.game = game
        self.decals = []

    @property
    def st(self):
        return self.game.state

    # étape locale -> quête d'équipe côté serveur (server/coop_rules.QUEST_IDS)
    MP_QUESTS = {"favoris_unlocked": "telephone_garnier", "favoris_deleted": "commande_annulee", "favoris_done": "sel_entrees"}

    def active(self):
        g = self.game
        if g.is_multiplayer:
            return getattr(g, "mp_mode", "coop") != "solo_survie"
        return g.net is None

    def _mp_send(self, flag):
        g = self.game
        if g.is_multiplayer and g.net is not None:
            g.net.send_quest_done(self.MP_QUESTS[flag])

    def update(self, dt):
        """Multijoueur : lance la quête une fois dans la maison et reprend les étapes faites par les coéquipiers
        (multiplayer_manager pose state.flags["mp_quest_<id>"])."""
        g = self.game
        if not g.is_multiplayer or not self.active() or g.mode != "playing":
            return
        st = self.st
        q = g.quests.quests["favoris"]
        if not q.active and not q.complete and g.player.zone in ("rdc", "etage", "grenier"):
            g.quests.start("favoris")
        # étapes faites par un coéquipier : annonce du serveur (mp_quest_*) ou drapeaux recopiés par world_sync
        for flag, qid, msg in (("favoris_unlocked", "telephone_garnier", "Un coéquipier a déverrouillé le compte de Garnier."),
                               ("favoris_deleted", "commande_annulee", "Un coéquipier a supprimé l'adresse. Il reste le sel."),
                               ("favoris_done", "sel_entrees", None)):
            if st.flag("mp_quest_" + qid) and not st.flag(flag):
                st.set(flag, True)
                if msg:
                    g.ui.notify_quest(msg)
        if st.flag("favoris_done"):
            for (eid, _, _, _) in ENTRANCES:
                st.set("favoris_sel_" + eid, True)
        steps = q.done_steps
        if st.flag("favoris_unlocked") and "code" not in steps:
            g.quests.on_event("favoris_code")
        if st.flag("favoris_deleted") and "favoris" not in steps:
            g.quests.on_event("favoris_deleted")
            self.enable_spots()
        if st.flag("favoris_done") and not q.complete:
            g.quests.on_event("favoris_done")
        # lignes de sel tracées par un coéquipier (drapeaux recopiés par world_sync) : on les dessine aussi
        if len(self.decals) != len(self.salt_lines()):
            self.redraw()

    def reset(self):
        for e in self.decals:
            destroy(e)
        self.decals = []

    # ------------------------------------------------------------------
    # Étape 1 : le téléphone de Garnier (appelé par house_events.h_tel_garnier)
    # ------------------------------------------------------------------
    def on_phone_taken(self):
        g = self.game
        if not self.active() or self.st.flag("favoris_sim"):
            return
        self.st.set("favoris_sim", True)
        self.st.add_item("tel_garnier")
        g.quests.on_event("favoris_phone")
        g.timers.after(2.5, g.say, "Son écran est mort... mais la carte SIM a l'air intacte. Je la mets dans mon téléphone.", 4.5)
        g.timers.after(7.5, self._sms, "QuickEats : connexion au compte de M. Garnier depuis un nouvel appareil. "
                                       "Répondez avec son code à 4 chiffres.")

    def _sms(self, text):
        ph = self.game.phone
        conv = ph.model.conversations.get(CONV)
        if conv is None:
            return
        conv["hidden"] = False
        ph.model.add_message(CONV, "QuickEats", text)
        ph.notify(NAME, text, "icone_quickeats", target=("messages", CONV))
        sound.play("vibration", 0.7, channel="voice")
        app = ph.apps.get("messages")
        if ph.is_open and ph.current == "messages" and app is not None and (app.page == "list" or app.conv == CONV):
            app.render()

    # ------------------------------------------------------------------
    # Étapes 2 et 3 : réponses tapées dans la conversation du compte
    # ------------------------------------------------------------------
    def on_reply(self, text):
        g = self.game
        st = self.st
        digits = "".join(c for c in text if c.isdigit())
        word = "".join(c for c in text.lower() if c.isalpha())
        if not st.flag("favoris_unlocked"):
            if digits == PIN:
                st.set("favoris_unlocked", True)
                g.quests.on_event("favoris_code")
                self._mp_send("favoris_unlocked")
                g.timers.after(1.5, self._sms, "Code accepté. Adresses favorites de votre livreur : « 17 rue des Lilas ». "
                                               "Répondez SUPPRIMER pour retirer cette adresse.")
                return
            fails = int(st.flags.get("favoris_fails", 0) or 0) + 1
            st.flags["favoris_fails"] = fails
            hint = ("Code incorrect." if fails < 2 else
                    "Code incorrect. Indice du compte : « la fête des voisins ».")
            g.timers.after(1.5, self._sms, hint)
            if fails == 3:
                g.timers.after(4.0, g.say, "La fête des voisins... Mme Bianchi avait une photo de ce jour-là, avec l'année.", 4.5)
            elif fails >= 6 and not st.flag("favoris_pin_hint"):
                st.set("favoris_pin_hint", True)
                g.timers.after(4.0, g.say, "Le panneau au bout de la rue... « Fête des voisins de la rue des Lilas, depuis 1998 ».", 5.0)
            return
        if st.flag("favoris_deleted"):
            g.timers.after(1.5, self._sms, "Aucune adresse favorite.")
            return
        if word.startswith("supprim") and g.assistance.t0 is None and not g.is_multiplayer:
            g.timers.after(1.5, self._sms, "Aucune livraison en cours sur ce compte.")
            return
        if word.startswith("supprim"):
            st.set("favoris_deleted", True)
            g.quests.on_event("favoris_deleted")
            self._mp_send("favoris_deleted")
            g.timers.after(1.5, self._sms, "« 17 rue des Lilas » a été retiré des adresses favorites.")
            g.timers.after(5.0, self._courier_reacts)
            self.enable_spots()
        else:
            g.timers.after(1.5, self._sms, "Répondez SUPPRIMER pour retirer « 17 rue des Lilas ».")

    def _courier_reacts(self):
        g = self.game
        cs = g.courier
        if cs.flag("code_given"):
            cs.say("Tu m'as déjà donné le code, Adrien. Je n'ai plus besoin de l'adresse.")
            return
        cs.say("Qu'est-ce que tu as fait ?")
        g.timers.after(4.0, cs.say, "Je trouverai une autre entrée.")
        g.timers.after(6.0, g.say, "Il va chercher un autre moyen d'entrer... Du sel. Devant chaque entrée.", 4.5)
        g.player.add_stress(12)

    # ------------------------------------------------------------------
    # Étape 4 : lignes de sel (interactables posés par house_events)
    # ------------------------------------------------------------------
    def salt_lines(self):
        return [e for e in ENTRANCES if self.st.flag("favoris_sel_" + e[0])]

    def can_salt(self, eid):
        return self.st.flag("favoris_deleted") and not self.st.flag("favoris_sel_" + eid)

    def pour_salt(self, eid):
        g = self.game
        st = self.st
        if not st.flag("favoris_deleted"):
            g.say("Une ligne de sel... comme chez Mme Bianchi. Pas encore.", 3.5)
            return
        if st.flag("favoris_sel_" + eid):
            return
        if not st.has("sel"):
            g.say("Il me faut du sel. Il y en avait dans la cuisine.", 3.5)
            return
        st.set("favoris_sel_" + eid, True)
        g.interactions.enable("sel_" + eid, False)
        ent = next(e for e in ENTRANCES if e[0] == eid)
        self._draw_line(ent)
        sound.play("ramasser", 0.6)
        n = len(self.salt_lines())
        g.quests.on_event("favoris_salt", n=n)
        if n < len(ENTRANCES):
            g.say(f"Une ligne devant {ent[3]}. Encore {len(ENTRANCES) - n}.", 3.0)
        else:
            st.remove_item("sel")
            self._complete()

    def _draw_line(self, ent):
        _, (x, y, z), axis, _ = ent
        b = MeshBuilder("sel_entree")
        w, d = (1.3, 0.12) if axis == "x" else (0.12, 1.3)
        b.quad("sel", (-w / 2, 0, -d / 2), (w / 2, 0, -d / 2), (w / 2, 0, d / 2), (-w / 2, 0, d / 2), (0, 1, 0), (1, 1, 1),
               tile=max(w, d))
        e = Entity(position=(x, y + 0.016, z))
        b.build(parent=e, emit=0.15)
        self.decals.append(e)

    def redraw(self):
        """Après un rechargement : les lignes déjà tracées réapparaissent."""
        self.reset()
        for ent in self.salt_lines():
            self._draw_line(ent)
        self.enable_spots()

    def enable_spots(self):
        """Les points « Tracer une ligne de sel » n'apparaissent qu'une fois l'adresse supprimée."""
        ia = self.game.interactions
        for (eid, _, _, _) in ENTRANCES:
            ia.enable("sel_" + eid, self.can_salt(eid))

    # ------------------------------------------------------------------
    # Fin : « Adresse introuvable »
    # ------------------------------------------------------------------
    def _complete(self):
        g = self.game
        st = self.st
        st.set("favoris_done", True)
        g.quests.on_event("favoris_done")
        if g.is_multiplayer:
            self._mp_send("favoris_done")              # le serveur annonce la victoire (« win ») à l'équipe
            return
        cs = g.courier
        if cs.flag("code_given"):
            g.timers.after(3.0, cs.say, "Le portail est ouvert. Tu m'as invité, Adrien.")
            g.timers.after(6.0, g.say, "Le sel ne suffira pas... je lui ai donné le code.", 4.0)
            return
        g.say("Trois lignes. Plus d'adresse. Plus d'entrée.", 3.5)
        g.player.relieve_stress(20)
        g.timers.after(5.0, cs.say, "Adresse introuvable.", False)
        g.timers.after(9.0, g.phone.notify, "QuickEats", "Votre livreur n'a pas trouvé l'adresse. Commande annulée.", "icone_quickeats")
        g.timers.after(10.0, sound.play, "porte_ferme", 0.5)
        g.timers.after(14.0, self._ending)

    def _ending(self):
        g = self.game
        if g.player.dead or g.ending_active or g.mode != "playing":
            return
        g.trigger_ending("E")
