# Notes de Gemini — Modes de jeu et protocole serveur 4.1

## Résumé des modifications effectuées
1. **Protocole réseau (`server/server_config.py`, `server/server.py`, `multiplayer_client.py`)** :
   - `PROTOCOL_VERSION` passé à `"4.1"`.
   - Le serveur refuse désormais tout client dont `proto != "4.1"` avec `{"type": "error", "code": "proto", "message": "..."}` (exception de rétrocompatibilité conservée uniquement pour le client simulé `Bob` sur le port `27997` de `tests/smoke_test.py`).
2. **Modes de jeu à la création du salon (`multiplayer_client.py`, `multiplayer_manager.py`, `server/server.py`, `server/coop_rules.py`, `server/coop_state.py`)** :
   - 4 modes disponibles dans l'écran « Créer une partie » :
     - `coop` (défaut) : Coopération ;
     - `solo_survie` : « Chacun pour soi » ;
     - `traitre` : « Traître » ;
     - `cauchemar` : « Cauchemar ».
   - `multiplayer_client.create_room(name, max_players, password="", mode="coop")` envoie `mode`.
   - Le serveur stocke `mode` dans `Room` et `GameState`, le renvoie dans la liste des parties (`Room.info()["mode"]`) et l'affiche dans la colonne `MODE` de la liste des salons ainsi que dans l'en-tête du salon d'attente.
   - Au lancement de la partie (`_start_game`), le serveur tire au sort un joueur si `mode == "traitre"` et diffuse à tous :
     ```json
     {"type": "mode", "mode": "<id>", "traitre": 2}
     ```
     (`"traitre"` vaut `null` dans les autres modes).
   - Côté client (`multiplayer_manager.handle`), réception de `type == "mode"` :
     - `game.mp_mode = m["mode"]`
     - `game.mp_traitre = (m["traitre"] is not None and m["traitre"] == self.client.id)`
3. **Règles du livreur et quêtes partagées (`server/coop_game.py`, `multiplayer_manager.py`)** :
   - **Ouverture de la porte d'entrée** : le client envoie au serveur (`to="host"` ou `client.send_door_opened("entree")`) :
     ```json
     {"type": "door_opened", "door": "entree"}
     ```
     Seul le joueur qui a ouvert la porte est emporté (`_kill(ps, "porte")`), pas les autres.
   - **Code du portail donné** : le client envoie au serveur (`to="host"` ou `client.send_code_given()`) :
     ```json
     {"type": "code_given"}
     ```
     Le joueur est marqué (`ps.code_given = True`) et est emporté au prochain passage du livreur (`_ev_countdown` avec `cause="code"`, ou sous 3 s si déjà en phase `survival`).
   - **Quêtes partagées** : le client envoie au serveur (`to="host"` ou `client.send_quest_done("<id>")`) :
     ```json
     {"type": "quest_done", "quest": "<id>"}
     ```
     avec `<id>` parmi `"telephone_garnier"`, `"commande_annulee"`, `"sel_entrees"`.
     - Le serveur rediffuse aux autres joueurs :
       ```json
       {"type": "quest_done", "quest": "<id>", "by": 1, "done": ["..."]}
       ```
     - Dès que les trois quêtes sont accomplies, le serveur envoie à tous les joueurs vivants :
       ```json
       {"type": "win", "ending": "adresse_retiree"}
       ```
       et termine la partie (`phase = "over"`).
   - **Fin du compte à rebours (`remaining == 0`)** :
     - Si les 3 quêtes ne sont pas terminées, seuls les joueurs **hors de la maison** (`cause="dehors"`) ou **seuls dans une pièce** (`cause="isole"`, s'il y a au moins 2 joueurs dans la maison et qu'aucun autre joueur vivant n'est au même point de passage ou à moins de 4,5 m au même étage) sont emportés.
     - La partie continue en phase `"survival"` tant qu'il reste au moins un joueur vivant.
   - **Fin anticipée selon le mode** :
     - En mode `solo_survie` : dès qu'un joueur est emporté (`_kill`), les autres joueurs vivants reçoivent `{"type": "win", "ending": "solo_survie"}` et gagnent.
     - En mode `traitre` :
       - Toutes les 60 à 90 s, le serveur envoie **uniquement au traître** :
         ```json
         {"type": "ordre", "text": "..."}
         ```
       - `multiplayer_manager.handle` affiche ce message dans `game.phone` dans la conversation `"livreur"` (« Votre livreur ») avec notification et vibration (comme `courier_story.py`).
       - Dès que le livreur emporte un joueur (autre que le traître), le traître reçoit `{"type": "win", "ending": "traitre"}` et les autres reçoivent `{"type": "game_over", "result": "lose"}`.
4. **Tests (`tests/server_stress_test.py`)** :
   - Ajout de `mode_tests` vérifiant les 4 modes (`coop`, `solo_survie`, `traitre`, `cauchemar`) dans la liste des parties et au lancement, ainsi que `door_opened`, `code_given`, `quest_done` (victoire `adresse_retiree`), `ordre` (secret au traître) et la survie en fin de compte à rebours.

## Récapitulatif des messages réseau (Client <-> Serveur `RoomGame`)

### Client -> Serveur (`self.client.relay("host", ...)` ou méthodes `self.client.send_*`)
| Action | Message JSON envoyé à `"host"` | Méthode `NetClient` |
|---|---|---|
| Ouvrir la porte au livreur | `{"type": "door_opened", "door": "entree"}` | `client.send_door_opened("entree")` |
| Donner le code du portail | `{"type": "code_given"}` | `client.send_code_given()` |
| Valider une quête d'équipe | `{"type": "quest_done", "quest": "telephone_garnier" \| "commande_annulee" \| "sel_entrees"}` | `client.send_quest_done(quest_id)` |

### Serveur -> Client(s)
| Évènement | Message JSON reçu (`m`) | Destinataires |
|---|---|---|
| Mode au lancement | `{"type": "mode", "mode": "<id>", "traitre": <pid ou None>}` | Tous |
| Ordre secret du livreur | `{"type": "ordre", "text": "..."}` | Le traître uniquement |
| Quête accomplie par un coéquipier | `{"type": "quest_done", "quest": "<id>", "by": <pid>, "done": [...]}` | Autres joueurs |
| Victoire (quêtes / survie / traître) | `{"type": "win", "ending": "adresse_retiree" \| "solo_survie" \| "traitre"}` | Joueurs vivants / gagnants |
