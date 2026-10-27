# L'ADRESSE

Jeu d'horreur 3D (vue 1re ou 3e personne), en **Python + Ursina Engine** (Panda3D). Entièrement en français.
Tous les assets (textures, sons, modèles, icônes) sont **générés de manière procédurale** : aucun fichier externe.

> Vous êtes Adrien Morel, photographe immobilier. Une maison sur les hauteurs de Nice (Mont-Boron), un propriétaire mort depuis trois mois,
> une appli de livraison qui n'aurait jamais dû vous envoyer ce message : *« Votre livreur arrive dans 2 minutes. »*
> **L'ADRESSE n'est pas un jeu de monstre. C'est un jeu de confiance.**

## Lancer le jeu

```bash
pip install -r requirements.txt
python main.py
```

Python 3.11+ recommandé. Au premier lancement, les textures et les sons sont générés (quelques secondes, barre de
progression) puis mis en cache dans le dossier temporaire.

### Contrôles

| Action | Touche |
| --- | --- |
| Déplacement | ZQSD / WASD |
| Sprint / Accroupi / Saut | Maj / C / Espace |
| Interagir | E |
| Lampe torche (+ molette : faisceau large ↔ concentré) | F |
| Téléphone | T |
| Inventaire | Tab |
| Parler à voix haute (certaines consignes de l'assistance) | V |
| Changer de vue (1re ↔ 3e personne, caméra d'épaule) | F5 |
| Pause / paramètres | Échap |

Toutes les touches sont reconfigurables dans *Paramètres → Contrôles*. FOV, vue, distance et épaule de la caméra se
règlent dans *Paramètres → Caméra* ; difficulté (Facile / Normal / Cauchemar), pause automatique et compteur FPS dans
*Paramètres → Jeu*.

## Le quartier (avant d'entrer dans la maison)

Une nouvelle partie commence rue des Lilas, à côté de la voiture : le quartier du Mont-Boron est libre d'accès
(désactivable dans *Paramètres → Jeu*).

* **Carrefour City** : rayons, produits à prendre (E), portique antivol et vigile, **caisses automatiques** :
  scanner les articles, retirer un article, prix « carte », paiement sans contact (débite le compte BNR visible dans
  l'appli banque du téléphone), ticket de caisse.
* **Carte fidélité** : carte par défaut **9531700001** ; chaque carte créée en caisse reçoit le numéro suivant
  (9531700002, 9531700003…). 1 point par euro, bon de 5 € automatique à 100 points, historique, cartes
  persistantes entre les parties (`%APPDATA%/LADRESSE/fidelite.json`). Essayez la carte 9531700000…
* **Chez Nino** : socca, pan bagnat, pissaladière… (santé et stress).
* Villas niçoises, voitures des voisins, circulation qui s'arrête au feu et devant vous, voiture de police avec
  gyrophares et agents, piétons, abribus Lignes d'Azur. Parlez aux habitants (E) : ils en savent long sur le 17.
* Achats utiles : piles, batterie externe, bougies, pansements, eau, boisson énergisante, gros sel, journal.

La nuit commence vraiment quand vous franchissez la porte d'entrée.

> Note : les noms d'enseignes réelles (« Carrefour City ») sont regroupés dans `shop.py` (`SHOP_NAME`, `SHOP_FULL`)
> pour pouvoir être remplacés facilement avant une diffusion commerciale.

## Compiler LADRESSE.exe (Windows)

```bash
pip install -r requirements.txt
python build.py
```

`build.py` génère l'icône (maison sombre + point lumineux) et un écran de démarrage (« L'ADRESSE » en blanc sur fond
noir), puis appelle PyInstaller (`--onefile --windowed --name LADRESSE`). Résultat : `dist/LADRESSE.exe`.

## Multijoueur (parties publiques, 1 à 8 joueurs)

Toutes les parties tournent sur le serveur `5.180.34.43:27326` (Python pur, aucune dépendance, Pterodactyl) :

```bash
cd server
python server.py          # écoute en TCP + UDP sur 0.0.0.0:27326
```

* L'écran *Multijoueur* liste les parties disponibles ; n'importe qui peut **créer** la sienne (nom, joueurs
  maximum, mot de passe facultatif) ou en **rejoindre** une.
* Le serveur fait tourner chaque partie (`server/coop_game.py` : IA de l'entité, minuteries, messages
  d'assistance différents pour chaque joueur, morts, victoire) dans une seule boucle à 20 ticks/s ; une partie
  continue si son créateur s'en va. Seuls `server/coop_*.py` demandent une mise à jour du serveur.
* Positions en UDP de joueur à joueur (repli TCP automatique), interpolation côté client pour des mouvements fluides.
* Robustesse : limiteurs de débit TCP/UDP, taille maximale, délais d'inactivité, limites par IP,
  jeton de session UDP anti-usurpation, arrêt propre, console (`list`, `kick`, `close`, `say`, `stats`, `stop`).
  Détails : `server/LISEZMOI_SERVEUR.md`.

Le bouton **Serveur local (LAN)** lance le serveur dans le jeu (port 27326, TCP + UDP à ouvrir sur la box pour
jouer par Internet sans le serveur officiel).

## Fiabilité

* Journal d'erreurs `%APPDATA%/LADRESSE/crash.log` (les erreurs ponctuelles n'arrêtent pas le jeu).
* Sauvegardes atomiques avec copie de secours `.bak` et validation au chargement ; paramètres vérifiés et bornés.
* Pause automatique quand la fenêtre perd le focus ; succès persistants (`succes.json`).

## Architecture

```
main.py                 point d'entrée (fenêtre, MSAA, boucle)        config.py / game_data.py   constantes, textes
game_manager.py         machine à états (chargement, menu, cinématique, jeu, mort, fins)
player.py               contrôleur 1re personne, stamina, stress, bruit      inventory.py, interaction_system.py
house_generator.py      maison procédurale (RDC, 1er, grenier, sous-sol), collisions, navigation A*
room_builder.py         constructeur de maillages + meubles                    house_props.py / house_events.py
phone_system.py         téléphone (Messages, Appareil photo, Lampe, Appels)    delivery_app.py (QuickEats), bank_app.py
assistance_system.py    chat d'assistance, paires contradictoires, compte à rebours
entity_ai.py            IA du Livreur (5 états, détection vue/ouïe/proximité)  entity_behaviors.py (4 types)
cinematic_engine.py     moteur de cinématiques                                  intro_cinematic.py (acte 0)
quest_system.py         quêtes                      sound_engine.py (synthèse numpy + audio spatial + musique dynamique)
texture_generator.py    textures (Pillow/numpy)     shaders.py / lighting_system.py / effects.py / particle_system.py
jumpscare_system.py     jumpscares                  ui_manager.py / settings_menu.py / ui_widgets.py
save_system.py          sauvegarde JSON             multiplayer_client.py / multiplayer_manager.py
server/                 server.py, server_config.py (salons, transfert des positions) + coop_game.py, coop_state.py, coop_rules.py (parties)
tests/smoke_test.py     test de fumée (xvfb-run -a python tests/smoke_test.py)
```

### Rendu

* Shader GLSL maison : lampe torche en projecteur (faisceau réglable, jaunissant quand la pile faiblit),
  jusqu'à 8 lumières ponctuelles (néon, bougies, TV, téléphone), lumière lunaire à l'extérieur, brouillard exponentiel
  par zone, distorsion de l'image autour de l'entité.
* Post-traitement plein écran : vignette (liée au stress, pulsante en poursuite), grain, aberration chromatique,
  distorsion, teinte (sous-sol bleuté), flash, fondu, correction daltonien.
* Les ombres portées par shadow-map ne sont **pas** implémentées : la lampe est collée à la caméra (une carte d'ombre
  centrée sur l'œil ne montrerait rien). Le réglage « Qualité des ombres » pilote le nombre de lumières ponctuelles
  évaluées par pixel (3 / 6 / 8).

### Fins

A « Livraison refusée » (tous les bons choix + tous les documents, sans ouvrir le congélateur) • B « 5 étoiles » •
C « Abonné » (congélateur ouvert + adresse piège) • D « Le nouveau gardien » (ne jamais sortir le téléphone).

## Tests

```bash
xvfb-run -a python tests/smoke_test.py     # Linux sans écran ; affiche « SMOKE TEST OK »
```
