"""Branche le comportement de la maison : interactions, objets, événements scriptés.

`house_props.py` déclare les points d'interaction ; ce module crée les `Interactable` et
implémente tous les événements (miroir, rideau, télé, lucarne, chambre condamnée, sous-sol...).
"""
import math
import random
from collections import deque

from ursina import Entity, Vec3, invoke, curve

import game_data as gd
from interaction_system import Interactable
from room_builder import MeshBuilder
from shaders import horror_shader
from sound_engine import engine as sound
from texture_generator import textures


class HouseEvents:
    def __init__(self, game):
        self.game = game
        self.house = game.house
        self.state = game.state
        self.t = 0.0
        self.handles = {}
        self.history = deque(maxlen=400)       # (temps, x, z, accroupi) pour le reflet
        self.mirror_active = False
        self.mirror_t = 0.0
        self.mirror_avatar = None
        self.drip_t = 1.0
        self.tv_state = None
        self.tv_t = 0.0
        self.tv_planned = random.uniform(150, 420)
        self.curtain_state = None
        self.curtain_t = 0.0
        self.lucarne_state = None
        self.mannequin_done = False
        self.cave_stay = 0.0
        self.cave_scratch_done = False
        self.condamnee_state = None
        self.cond_t = 0.0
        self.portraits = []
        self.deformed = False
        self.radio_state = 0
        self.zone = None
        self.basement_started = False
        self.front_locked = False
        self.salt_decals = []
        self.note_door_spawned = False
        self.silhouette_car = None
        self.interactables_ready = False

    # ------------------------------------------------------------------
    # Mise en place
    # ------------------------------------------------------------------
    def setup(self):
        g = self.game
        h = self.house
        ia = g.interactions
        ia.clear()
        # points déclarés dans house_props
        for d in h.points:
            handler = getattr(self, "h_" + d["id"], None)
            if handler is None:
                continue
            ia.add(Interactable(d["id"], d["pos"], d["prompt"], handler, level=d["level"], radius=d["radius"],
                                enabled=d.get("enabled", True)))
        # portes
        for did, door in h.doors.items():
            ia.add(Interactable("door_" + did, door.pos, (lambda door=door: self._door_prompt(door)),
                                (lambda it, door=door: self.use_door(door)), level=door.level, radius=0.75, door=door))
        # pastilles lumineuses : néon du 1er étage (son synchronisé)
        neon = h.anchors["neon_light"]
        neon.on_buzz = lambda l: self._neon_buzz(l)
        # cadres photo du couloir (superposés pour pouvoir être déformés)
        for (x, y, z) in h.photo_frames:
            e = Entity(parent=h.level_roots[1], model="quad", texture=textures.get("portrait"), shader=horror_shader,
                       position=(x - 0.04, y, z), scale=(0.42, 0.55), rotation_y=90)
            e.set_shader_input("emit", 0.0)
            self.portraits.append(e)
        # le reflet : avatar dans le miroir (désactivé)
        self._build_mirror_avatar()
        # silhouette près de la voiture (lucarne)
        sb = MeshBuilder("sil")
        sb.quad("silhouette", (-0.4, 0, 0), (0.4, 0, 0), (0.4, 1.8, 0), (-0.4, 1.8, 0), (0, 0, -1), (1, 1, 1), tile=1.8)
        sb.quad("silhouette", (0.4, 0, 0), (-0.4, 0, 0), (-0.4, 1.8, 0), (0.4, 1.8, 0), (0, 0, 1), (1, 1, 1), tile=1.8)
        self.silhouette_car = Entity(position=h.anchors["car_pos"] + Vec3(2.8, 0, 0.4), enabled=False)
        for e in sb.build(parent=self.silhouette_car, emit=0.1):
            pass
        # état persistant : objets déjà ramassés
        self.apply_saved_state()
        self.interactables_ready = True

    def apply_saved_state(self):
        st = self.state
        h = self.house
        for opened in st.opened:
            if opened == "frigo":
                h.parts["frigo_porte"].set_open(True, instant=True)
                self._sync_fridge_note()
                self.house.anchors["frigo_light"].enabled = True
            elif opened == "tiroir_amis":
                h.parts["tiroir_bureau"].set_open(True)
                h.parts["tel_garnier"].enabled = True
        if st.flag("planks_removed"):
            for i in range(3):
                h.parts[f"planche_{i}"].enabled = False
            h.parts["cadenas"].enabled = False
            h.doors["cave"].locked = False
        if st.flag("miroir_vu"):
            h.parts["drap_miroir"].enabled = False
        if st.flag("act_cond_open"):
            h.doors["condamnee"].locked = False
        if st.act >= 3:
            self.deform_portraits()
        if st.flag("front_locked"):
            self.front_locked = True
            h.doors["front"].locked = True

    # ------------------------------------------------------------------
    # Documents / objets
    # ------------------------------------------------------------------
    def read_doc(self, doc_id, title, pages, then=None):
        g = self.game
        new = self.state.add_doc(doc_id)
        g.quests.on_event("doc_found")

        def after():
            g.quests.on_event("doc_found")
            if then:
                then()
        g.ui.docs.open(title, pages, after)
        return new

    def pickup(self, item, text=None, sound_name="ramasser", flag=None):
        st = self.state
        st.add_item(item)
        sound.play(sound_name, 0.8)
        if flag:
            st.opened.add(flag)
        if text:
            self.game.say(text)
        self.game.quests.on_event("item_picked")

    def _pile(self, key):
        if key in self.state.opened:
            return False
        self.state.opened.add(key)
        self.state.add_item("pile")
        self.state.flags["piles_found"] = self.state.flags.get("piles_found", 0) + 1
        sound.play("pile", 0.8)
        n = self.state.flags["piles_found"]
        self.game.say(f"Une pile. ({n}/5)")
        self.game.quests.on_event("item_picked")
        return True

    # ------------------------------------------------------------------
    # Portes
    # ------------------------------------------------------------------
    def _door_prompt(self, door):
        if door.id == "cave" and not self.state.flag("planks_removed"):
            return "Examiner la porte"
        return "Fermer" if door.is_open else "Ouvrir"

    def use_door(self, door):
        g = self.game
        st = self.state
        did = door.id
        if did == "cave" and not st.flag("planks_removed"):
            self.h_planches(None)
            return
        if door.locked:
            if did == "condamnee":
                g.say(gd.INTERACT_TEXT["porte_condamnee"])
                sound.play_at("verrou", door.pos, 0.8)
                g.player.add_stress(4)
                return
            sound.play_at("verrou", door.pos, 0.9)
            return
        if did == "front":
            if self.front_locked and not door.is_open:
                sound.play_at("verrou", door.pos, 0.9)
                g.say(gd.LINE_DOOR_LOCKED if not st.flag("front_msg") else "Verrouillée.")
                st.set("front_msg")
                g.player.add_stress(5)
                return
            if not door.is_open:
                if g.is_multiplayer and g.net is not None and g.assistance.t0 is not None:
                    g.net.send_door_opened("entree")          # le serveur décide (fatal seulement s'il est à la porte)
                if g.assistance.front_door_opened():
                    return
        if door.is_open:
            # on ne referme pas la porte sur soi-même (le battant passerait à travers le joueur)
            x0, _, z0, x1, _, z1 = door.aabb
            px, pz = g.player.pos[0], g.player.pos[2]
            if (max(x0, min(px, x1)) - px) ** 2 + (max(z0, min(pz, z1)) - pz) ** 2 < 0.34 ** 2 and abs(g.player.pos[1] - door.y0) < 1.0:
                return
        door.toggle()
        g.player.emit_noise(5.0, door.pos, "porte")

    def lock_front_door(self):
        g = self.game
        p = g.player
        # le joueur est ressorti dans le quartier : on attend qu'il soit à l'intérieur
        if p.zone not in ("rdc", "etage", "grenier", "sous_sol", "escalier_cave"):
            g.timers.after(15.0, self.lock_front_door)
            return
        if g.neighborhood is not None:
            g.house.outside_view = False
            g.neighborhood.deactivate()
            g.house.set_level_visibility(p.level)
        door = self.house.doors["front"]
        self.front_locked = True
        self.state.set("front_locked")
        door.locked = True
        if door.is_open:
            door.close()

    # ------------------------------------------------------------------
    # Handlers (id des points d'interaction)
    # ------------------------------------------------------------------
    def h_manteau(self, it):
        if "manteau" in self.state.opened:
            self.game.say("Rien d'autre dans les poches.")
            return
        self.state.opened.add("manteau")
        self.state.add_item("numero_barre")
        sound.play("papier", 0.8)
        self.game.ui.docs.open("Papier froissé", [gd.NOTE_COAT])

    def h_miroir(self, it):
        g = self.game
        if self.state.flag("miroir_vu"):
            return
        self.state.set("miroir_vu")
        self.house.parts["drap_miroir"].enabled = False
        sound.play("papier", 0.9)
        g.player.add_stress(10)
        self.mirror_active = True
        self.mirror_t = 0.0
        if self.mirror_avatar is not None:
            self.mirror_avatar.enabled = True
        it.enabled = False
        g.say("Le drap tombe. Mon reflet...")

    def h_planches(self, it):
        g = self.game
        st = self.state
        if st.flag("planks_removed"):
            return
        if not st.has("pied_de_biche"):
            g.say(gd.INTERACT_TEXT["porte_cadenas"])
            sound.play_at("verrou", self.house.doors["cave"].pos, 0.9)
            return
        n = st.flags.get("planks", 0)
        part = self.house.parts[f"planche_{n}"]
        sound.play("planche_arrachee", 1.0)
        g.player.emit_noise(10.0, self.house.doors["cave"].pos, "planches")
        part.animate_position(part.position + Vec3(0.2, -0.7, -0.5), duration=0.5)
        part.animate("rotation_z", 70, duration=0.5)
        invoke(lambda p=part: setattr(p, "enabled", False), delay=0.6)
        st.flags["planks"] = n + 1
        g.player.shake(0.25, 0.3)
        if n + 1 >= 3:
            cad = self.house.parts["cadenas"]
            cad.animate_y(0.0, duration=0.45, curve=curve.in_quad)
            invoke(lambda: sound.play("cles", 0.7), delay=0.4)
            invoke(lambda: setattr(cad, "enabled", False), delay=1.4)
            st.set("planks_removed")
            st.set("cave_open")
            self.house.doors["cave"].locked = False
            g.quests.on_event("planks_removed")
            g.say("Le cadenas tombe tout seul. Il n'était même pas fermé.")

    def h_journaux(self, it):
        st = self.state
        st.opened.add("journaux")
        st.add_item("adresse_erreur")
        self.game.quests.on_event("address_found", key="erreur")
        pages = ["\n\n".join(gd.NEWSPAPER_HEADLINES[:3]), "\n\n".join(gd.NEWSPAPER_HEADLINES[3:])]
        self.read_doc("journaux", "Journaux du salon", pages)

    def h_tisonnier(self, it):
        self.pickup("tisonnier", "Un tisonnier. Inutile comme arme.", flag="tisonnier")
        it.enabled = False

    def h_frigo(self, it):
        g = self.game
        part = self.house.parts["frigo_porte"]
        light = self.house.anchors["frigo_light"]
        if part.is_open:
            part.set_open(False)
            light.enabled = False
            sound.play_at("porte_ferme", self.house.anchors["frigo"], 0.5)
            self._fridge_buzz(False)
            invoke(self._sync_fridge_note, delay=0.75)
            return
        part.set_open(True)
        light.enabled = True
        sound.play_at("porte_ouvre", self.house.anchors["frigo"], 0.5, pitch=1.4)
        self._fridge_buzz(True)
        invoke(self._sync_fridge_note, delay=0.75)
        self.state.opened.add("frigo")
        if not self.state.flag("frigo_note"):
            self.state.set("frigo_note")
            invoke(lambda: self.read_doc("note_frigo", "Note du réfrigérateur", [gd.NOTE_FRIGO]), delay=0.9)
            g.say(gd.INTERACT_TEXT["frigo_vide"])

    def _fridge_buzz(self, on):
        """Les mouches bourdonnent tant que le frigo est ouvert."""
        h = self.handles.get("mouches")
        if on and (h is None or not getattr(h, "alive", True)):
            self.handles["mouches"] = sound.loop("mouches", 0.5, channel="sfx", pos=self.house.anchors["frigo_mouches"],
                                                 fade_in=0.8, ref=2.0)
        elif not on and h is not None:
            h.fade_to(0.0, 1.5, stop=True)
            self.handles.pop("mouches", None)

    def _sync_fridge_note(self):
        """Le papier de l'adresse est aimanté sur la porte : le point d'interaction suit la porte."""
        it = self.game.interactions.get("adresse_frigo")
        note = self.house.parts.get("papier_adresse")
        if it is not None and note is not None:
            p = note.world_position
            d = self.house.parts["frigo_porte"]
            # un peu devant la face avant (côté pièce quand fermée, côté -x quand la porte est ouverte)
            it.pos = Vec3(p[0] - 0.12, p[1], p[2]) if d.is_open else Vec3(p[0], p[1], p[2] - 0.12)

    def h_adresse_frigo(self, it):
        st = self.state
        st.add_item("adresse_bonne")
        st.opened.add("adresse_frigo")
        self.game.quests.on_event("address_found", key="bonne")
        self.house.parts["papier_adresse"].enabled = False
        sound.play("papier", 0.8)
        self.game.ui.docs.open("Papier de la cuisine", [gd.NOTE_FRIGO_ADDRESS])
        it.enabled = False

    def h_four(self, it):
        part = self.house.parts["four_porte"]
        if part.is_open:
            part.set_open(False)
            return
        part.set_open(True)
        self.game.say(gd.INTERACT_TEXT["four"])
        self.game.player.add_stress(2)

    def h_sel(self, it):
        self.pickup("sel", "Du gros sel.", flag="sel")
        it.enabled = False

    def h_tiroirs(self, it):
        part = self.house.parts["tiroir_cuisine"]
        if part.is_open:
            part.set_open(False)
            return
        part.set_open(True)
        sound.play("cles", 0.5)
        if "tiroir_cuisine" not in self.state.opened:
            self.state.opened.add("tiroir_cuisine")
            self.state.add_item("trousseau")
            self.game.say(gd.INTERACT_TEXT["tiroirs_cles"])
            self._pile("pile_cuisine")

    def h_rideau(self, it):
        g = self.game
        if self.state.flag("rideau_done") or self.curtain_state:
            return
        part = self.house.parts["rideau"]
        part.animate_x(part.x + 1.25, duration=0.6)
        sound.play_at("papier", self.house.anchors["rideau"], 0.7, pitch=0.7)
        self.curtain_state = "open"
        self.curtain_t = 0.0
        g.say(gd.INTERACT_TEXT["rideau"])
        it.enabled = False

    def h_miroir_brise(self, it):
        self.read_doc("note_sdb", "Derrière le miroir", [gd.NOTE_SDB])
        self.game.player.add_stress(14)
        sound.play("verre", 0.4, pitch=1.4)

    def h_recus(self, it):
        self.read_doc("recus", "Reçus QuickEats", [gd.RECEIPTS_TEXT])
        self.game.player.add_stress(6)

    def h_pile_bureau(self, it):
        if self._pile("pile_bureau"):
            it.enabled = False

    def h_pile_placard(self, it):
        if self._pile("pile_placard"):
            it.enabled = False

    def h_pile_grenier(self, it):
        if self._pile("pile_grenier"):
            it.enabled = False

    def h_sac_propre(self, it):
        self.game.say("Un sac QuickEats. Propre. Neuf. Vide.")
        self.game.player.add_stress(8)

    def h_lit(self, it):
        part = self.house.parts["oreillers"]
        if not part.enabled:
            return
        part.enabled = False
        sound.play("papier", 0.7, pitch=0.8)
        self.game.say(gd.INTERACT_TEXT["lit_forme"])
        self.game.player.add_stress(8)

    def h_dessous_lit(self, it):
        st = self.state
        st.add_item("adresse_piege")
        self.game.quests.on_event("address_found", key="piege")
        self.read_doc("releve", "Relevé bancaire", [gd.BANK_STATEMENT_TEXT])
        it.enabled = False

    def h_carnet(self, it):
        self.read_doc("carnet", "Carnet de Garnier", list(gd.NOTEBOOK_PAGES))
        self.game.player.add_stress(5)

    def h_armoire(self, it):
        g = self.house.parts
        a, b = g["armoire_g"], g["armoire_d"]
        if a.is_open:
            a.set_open(False)
            b.set_open(False)
            return
        a.set_open(True)
        b.set_open(True)
        sound.play_at("porte_ouvre", Vec3(4.4, 4.0, 0.8), 0.5, pitch=1.2)
        self.game.say(gd.INTERACT_TEXT["uniforme"])

    def h_volets_master(self, it):
        self.game.say(gd.INTERACT_TEXT["volets_cloues"])
        sound.play("craquement_bois", 0.4)

    def h_tiroir_amis(self, it):
        g = self.game
        part = self.house.parts["tiroir_bureau"]
        if part.is_open:
            part.set_open(False)
            return
        if not self.state.has("cle_tiroir") and "tiroir_amis" not in self.state.opened:
            g.say(gd.INTERACT_TEXT["tiroir_ferme"])
            sound.play_at("verrou", Vec3(3.4, 3.7, 9.3), 0.8)
            return
        part.set_open(True)
        self.state.opened.add("tiroir_amis")
        self.house.parts["tel_garnier"].enabled = True
        g.interactions.enable("tel_garnier", True)
        sound.play("cles", 0.6)

    def h_tel_garnier(self, it):
        self.read_doc("tel_garnier", "Téléphone de Garnier", ["\n\n".join(gd.GARNIER_PHONE_TEXT[:2]), "\n\n".join(gd.GARNIER_PHONE_TEXT[2:])])
        self.game.player.add_stress(12)
        it.enabled = False
        self.house.parts["tel_garnier"].enabled = False
        self.game.favoris.on_phone_taken()

    # lignes de sel de la quête « Rayé des favoris »
    def h_sel_porte(self, it):
        self.game.favoris.pour_salt("porte")

    def h_sel_salon(self, it):
        self.game.favoris.pour_salt("salon")

    def h_sel_bureau(self, it):
        self.game.favoris.pour_salt("bureau")

    def h_jouet(self, it):
        self.game.say(gd.INTERACT_TEXT["jouet"])
        self.game.player.add_stress(4)

    def h_sel_condamnee(self, it):
        self.state.set("sel_touched")
        self.game.say("Le sel crisse sous mes doigts. C'est froid.")
        self.game.player.add_stress(10)
        it.enabled = False

    def h_pharmacie(self, it):
        g = self.game
        part = self.house.parts["pharmacie"]
        if part.is_open:
            part.set_open(False)
            return
        part.set_open(True)
        sound.play_at("porte_ouvre", Vec3(15.5, 4.6, 10.4), 0.4, pitch=1.5)
        if "pharmacie" not in self.state.opened:
            self.state.opened.add("pharmacie")
            self.state.add_item("cle_tiroir")
            sound.play("cles", 0.7)
            self._pile("pile_pharmacie")
            g.say(gd.INTERACT_TEXT["pharmacie"] + " Une petite clé... et une pile.")

    def h_pied_de_biche(self, it):
        self.pickup("pied_de_biche", "Un pied de biche. Il pèse son poids.", flag="pied_de_biche")
        it.enabled = False

    def h_radio(self, it):
        g = self.game
        if self.radio_state != 0:
            if self.radio_state == 2:
                g.say(gd.INTERACT_TEXT["radio_morte"])
            return
        self.radio_state = 1
        pos = self.house.anchors["radio"]
        sound.play_at("radio_gresillement", pos, 0.9, ref=6.0)
        text = "Dix-sept... rue... des... Lilas..."
        for i in range(3):
            invoke(lambda i=i: sound.speak(text, f0=95, speed=0.55, pos=pos, volume=1.0, channel="sfx", distort=True,
                                           subtitle=(i == 0), speaker="Radio"), delay=2.0 + i * 5.2)
        invoke(self._radio_off, delay=18.0)
        g.player.add_stress(8)
        it.enabled = False

    def _radio_off(self):
        self.radio_state = 2
        sound.play_at("tv_clac", self.house.anchors["radio"], 0.9)

    def h_plan(self, it):
        self.read_doc("plan", "Plan de la maison", [gd.PLAN_TEXT])

    def h_polaroids(self, it):
        self.read_doc("polaroids", "Polaroïds", list(gd.POLAROID_PAGES))
        self.game.player.add_stress(10)
        it.enabled = False

    def h_lucarne(self, it):
        if self.lucarne_state is not None:
            return
        g = self.game
        courier = getattr(g, "courier", None)
        if courier is not None and courier.where() == "lampadaire":
            courier.look_out()
            g.say("Il est là, sous le lampadaire. Il ne bouge pas. Il est... beaucoup trop grand.", 4.5, voice=False)
            g.player.add_stress(10)
            return
        self.lucarne_state = "look"
        self.lucarne_t = 0.0
        lamp = self.house.anchors["lamp_light"]
        lamp.enabled = False
        self.silhouette_car.enabled = True
        g.say("La rue est vide, la voiture est toujours là... mais le lampadaire est éteint. Quelqu'un est debout près de la voiture.")
        g.player.add_stress(14)

    def h_congelateur(self, it):
        g = self.game
        st = self.state
        if st.freezer_opened:
            return
        g.ui.choice.ask("Le couvercle est froid. Quelque chose gratte à l'intérieur... ou c'est dans votre tête.\nOuvrir le congélateur ?",
                        self._open_freezer, self._decline_freezer, "Ouvrir", "Reculer")

    def _decline_freezer(self):
        self.state.set("freezer_declined")
        self.game.say("Quelque chose me dit de ne pas toucher à ça.")

    def _open_freezer(self):
        g = self.game
        st = self.state
        st.freezer_opened = True
        g.quests.on_event("freezer_opened")
        lid = self.house.parts["congelateur_lid"]
        lid.animate("rotation_x", -105, duration=1.2, curve=curve.out_cubic)
        sound.play_at("porte_ouvre", self.house.anchors["congelateur"], 0.9, pitch=0.7)
        self.house.parts["tel_fond"].enabled = True
        g.say(gd.INTERACT_TEXT["congelateur_vide"])
        invoke(self._freezer_message, delay=2.4)
        g.interactions.enable("congelateur", False)

    def _freezer_message(self):
        g = self.game
        g.ui.docs.open("Téléphone — message non lu", ["« Votre livreur est arrivé. »"], self._candles_light)

    def _candles_light(self):
        g = self.game
        g.quests.on_event("message_read")
        for l in self.house.candles:
            l.enabled = True
        sound.play("woosh_flamme", 1.0)
        g.effects.flash(0.5, 0.6)
        g.player.shake(0.6, 0.8)
        # la porte du sous-sol claque
        door = self.house.doors["cave"]
        invoke(lambda: (door.close(0.2, silent=True), sound.play("porte_claque", 1.0)), delay=0.7)
        g.player.add_stress(35)
        invoke(g.final_event, delay=2.2)

    # ------------------------------------------------------------------
    # Reflet du miroir
    # ------------------------------------------------------------------
    def _build_mirror_avatar(self):
        b = MeshBuilder("reflet")
        b.quad("silhouette", (0, 0, -0.4), (0, 0, 0.4), (0, 1.75, 0.4), (0, 1.75, -0.4), (-1, 0, 0), (0.55, 0.62, 0.8), tile=1.75)
        self.mirror_avatar = Entity(position=(7.885, 0, 3.8), enabled=False)
        for e in b.build(parent=self.mirror_avatar, emit=0.15):
            pass

    def _update_mirror(self, dt):
        p = self.game.player
        self.mirror_t += dt
        # le reflet suit le joueur avec 0,5 s de retard
        target_t = self.t - 0.5
        z = p.pos[2]
        for (tt, x, zz, cr) in reversed(self.history):
            if tt <= target_t:
                z = zz
                break
        self.mirror_avatar.z = max(3.4, min(4.2, z))
        self.mirror_avatar.scale_y = 0.6 if p.crouching else 1.0
        if self.mirror_t > 7.0:
            self.mirror_active = False
            self.mirror_avatar.enabled = False
            self.game.say("... Ça redevient normal. Le drap ne peut plus être remis.")

    # ------------------------------------------------------------------
    # Événements ambiants
    # ------------------------------------------------------------------
    def start_ambience(self):
        h = self.house
        A = h.anchors
        self.stop_ambience()
        self.handles["frigo"] = sound.loop("frigo", 0.45, channel="sfx", pos=A["frigo_hum"], ref=2.5)
        self.handles["tuyaux"] = sound.loop("tuyauterie", 0.5, channel="sfx", pos=A["tuyauterie"], ref=3.0)
        self.handles["neon"] = sound.loop("neon", 0.5, channel="sfx", pos=A["neon_pos"], ref=3.0)
        self.handles["berceuse"] = sound.loop("berceuse", 0.35, channel="sfx", pos=A["berceuse"], ref=3.5)
        self.handles["vent"] = sound.loop("vent", 0.28, channel="music", fade_in=3.0)
        self.handles["eau"] = sound.loop("tuyauterie", 0.3, channel="sfx", pos=A["eau_baignoire"], ref=2.0)
        sound.music.set_state("ambient", stinger=False)

    def stop_ambience(self):
        for k, hd in list(self.handles.items()):
            if hd:
                hd.stop()
        self.handles = {}

    def _neon_buzz(self, light):
        p = self.game.player
        if p.level == 1:
            sound.play_at("neon_buzz", light.pos, 0.6, ref=4.0)

    def on_zone_change(self, zone):
        g = self.game
        g.lighting.set_zone(zone)
        basement = zone in ("sous_sol", "escalier_cave")
        # sous-sol : les bruits de la maison disparaissent, bourdonnement grave
        for k in ("frigo", "tuyaux", "neon", "berceuse", "eau"):
            hd = self.handles.get(k)
            if hd:
                hd.fade_to(0.0 if basement else 1.0, 1.0)
        v = self.handles.get("vent")
        if v:
            v.fade_to(0.0 if basement else (0.6 if zone == "grenier" else 1.0), 1.0)
        if basement:
            if "infra" not in self.handles or not self.handles["infra"]:
                self.handles["infra"] = sound.loop("infrasons", 0.6, channel="music", fade_in=3.0)
            g.player.flash_shake = 1.0 if zone == "escalier_cave" else 0.35
            if not self.state.flag("descended") and zone == "sous_sol":
                self.state.set("descended")
                g.quests.on_event("descended")
                g.on_descend()
            sound.music.set_state("basement", stinger=False)
        else:
            if self.handles.get("infra"):
                self.handles["infra"].fade_to(0.0, 1.5, stop=True)
                self.handles["infra"] = None
            g.player.flash_shake = 0.0
            if sound.music.state == "basement":
                sound.music.set_state("ambient", stinger=False)
        g.house.set_level_visibility(g.player.level)

    def tv_event(self):
        h = self.house
        tv = h.parts["tv_screen"]
        light = h.anchors["tv_light"]
        self.tv_state = "on"
        self.tv_t = 0.0
        light.enabled = True
        tv.set_shader_input("emit", 1.0)
        sound.play_at("neige_tv", h.anchors["tv_screen_pos"], 1.0, ref=5.0)
        d = (h.anchors["tv_screen_pos"] - self.game.player.pos).length()
        if d < 12:
            self.game.player.add_stress(7)
            self.game.player.shake(0.2, 0.3)

    def deform_portraits(self):
        self.deformed = True
        for e in self.portraits:
            e.texture = textures.get("portrait_deforme")

    def open_condemned_door(self):
        """Pendant l'acte 4 : la porte de la chambre condamnée s'ouvre d'elle-même."""
        door = self.house.doors["condamnee"]
        door.locked = False
        self.state.set("act_cond_open")
        door.open(2.5, silent=True)
        sound.play_at("porte_ouvre", door.pos, 1.0, pitch=0.85, ref=6.0)
        self.game.player.add_stress(8)
        self.condamnee_state = "open"

    def spawn_door_note(self):
        """Fin D : une note glissée sous la porte d'entrée."""
        if self.note_door_spawned:
            return
        self.note_door_spawned = True
        b = MeshBuilder("note")
        b.quad("papier", (-0.1, 0, -0.08), (0.1, 0, -0.08), (0.1, 0, 0.08), (-0.1, 0, 0.08), (0, 1, 0), (1, 1, 1), tile=0.3)
        e = Entity(position=(7.0, 0.012, 0.35))
        for ent in b.build(parent=e, emit=0.1):
            pass
        self.game.interactions.add(Interactable("note_porte", (7.0, 0.1, 0.4), "Ramasser la note", lambda it: self.game.ending_d_note(),
                                                level=0, radius=0.8))

    def draw_salt_circle(self, pos):
        b = MeshBuilder("sel")
        b.quad("sel", (-1.2, 0, -1.2), (1.2, 0, -1.2), (1.2, 0, 1.2), (-1.2, 0, 1.2), (0, 1, 0), (1, 1, 1), tile=2.4)
        e = Entity(position=(pos[0], pos[1] + 0.015, pos[2]))
        for ent in b.build(parent=e, emit=0.15):
            pass
        self.salt_decals.append(e)

    # ------------------------------------------------------------------
    # Boucle
    # ------------------------------------------------------------------
    def update(self, dt):
        g = self.game
        p = g.player
        h = self.house
        self.t += dt
        self.history.append((self.t, p.pos[0], p.pos[2], p.crouching))
        if self.mirror_active:
            self._update_mirror(dt)
        # gouttes du robinet (toutes les 2 s)
        self.drip_t -= dt
        if self.drip_t <= 0:
            self.drip_t = 2.0
            if p.level == 0 and not (p.zone in ("sous_sol", "escalier_cave")):
                sound.play_at("goutte", h.anchors["robinet"], 0.6, ref=2.5)
        # berceuse : se tait quand le joueur entre dans la chambre
        room = p.room
        bh = self.handles.get("berceuse")
        if bh is not None:
            if room is not None and room.id == "amis":
                bh.fade_to(0.0, 2.5)
            elif p.zone != "sous_sol":
                bh.fade_to(1.0, 2.5)
        # événement télé
        if self.tv_state is None and not self.state.flag("tv_done") and g.playtime > self.tv_planned and g.state.act >= 1:
            self.state.set("tv_done")
            self.tv_event()
        if self.tv_state == "on":
            self.tv_t += dt
            tv = h.parts["tv_screen"]
            tv.texture = textures.get(f"tv_statique_{int(self.tv_t * 14) % 3}")
            if self.tv_t > 4.5:
                self.tv_state = "done"
                tv.texture = textures.get("ecran_noir")
                tv.set_shader_input("emit", 0.0)
                h.anchors["tv_light"].enabled = False
                sound.play_at("tv_clac", h.anchors["tv_screen_pos"], 1.0)
        # rideau de douche : se remet en place quand le joueur se retourne
        if self.curtain_state == "open":
            self.curtain_t += dt
            to = h.anchors["rideau"] - p.eye_pos
            looking = to.normalized().dot(p.forward) > 0.2 if to.length() > 0.1 else True
            if self.curtain_t > 1.5 and not looking:
                part = h.parts["rideau"]
                part.x -= 1.25
                self.curtain_state = "done"
                self.state.set("rideau_done")
                sound.play_at("papier", h.anchors["rideau"], 0.9, pitch=0.7)
                p.add_stress(12)
                g.say("Le rideau... il s'est remis tout seul.")
        # lucarne : la silhouette disparaît quand on regarde ailleurs
        if self.lucarne_state == "look":
            to = h.anchors["lucarne"] - p.eye_pos
            looking = p.forward.dot(Vec3(0, 0, -1)) > 0.3 and to.length() < 4
            self.lucarne_t += dt
            if self.lucarne_t > 2.0 and not looking:
                self.silhouette_car.enabled = False
                self.lucarne_state = "done"
        # mannequin : sursaut
        if not self.mannequin_done and p.level == 2:
            to = h.anchors["mannequin"] - p.eye_pos
            if to.length() < 6.0 and to.normalized().dot(p.forward) > 0.88:
                self.mannequin_done = True
                sound.play("impact", 0.4, pitch=1.6)
                sound.play("stinger_alerte", 0.6)
                p.add_stress(15)
                p.shake(0.3, 0.3)
        # grattements derrière la porte du sous-sol
        if not self.cave_scratch_done and not self.state.flag("planks_removed"):
            d = math.hypot(p.pos[0] - 7.0, p.pos[2] - 11.6)
            if d < 1.8 and p.level == 0:
                self.cave_stay += dt
                if self.cave_stay > 5.0:
                    self.cave_scratch_done = True
                    sound.play_at("grattement", Vec3(7.0, 1.0, 12.3), 0.8, ref=2.5)
                    p.add_stress(8)
            else:
                self.cave_stay = max(0.0, self.cave_stay - dt)
        # chambre condamnée : la porte se referme derrière le joueur, puis se rouvre
        if self.condamnee_state == "open":
            r = h.rooms["condamnee"]
            if p.level == 1 and r.contains(p.pos[0], p.pos[2]) and p.pos[2] < 3.8:
                door = h.doors["condamnee"]
                door.close(0.8, silent=False)
                self.condamnee_state = "closed"
                self.cond_t = 0.0
                p.add_stress(30)
                p.shake(0.3, 0.5)
        elif self.condamnee_state == "closed":
            self.cond_t += dt
            if self.cond_t > 10.0:
                door = h.doors["condamnee"]
                door.open(2.0, silent=False)
                self.condamnee_state = "done"
                sound.play_at("porte_ouvre", door.pos, 0.8, pitch=0.9)
