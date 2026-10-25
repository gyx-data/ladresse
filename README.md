# L'ADRESSE

Jeu d'horreur 3D en première personne, en **Python + Ursina Engine** (Panda3D). Entièrement en français.
Tous les assets (textures, sons, modèles, icônes) sont **générés de manière procédurale** : aucun fichier externe.

> Vous êtes Adrien Morel, photographe immobilier. Une maison à Vaulx-en-Velin, un propriétaire mort depuis trois mois,
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
| Pause / paramètres | Échap |

Toutes les touches sont reconfigurables dans *Paramètres → Contrôles*.

## Compiler LADRESSE.exe (Windows)

```bash
pip install -r requirements.txt
python build.py
```

`build.py` génère l'icône (maison sombre + point lumineux) et un écran de démarrage (« L'ADRESSE » en blanc sur fond
noir), puis appelle PyInstaller (`--onefile --windowed --name LADRESSE`). Résultat : `dist/LADRESSE.exe`.

## Serveur multijoueur (mode coopératif 2-4 joueurs)

Le serveur est autonome (Python pur, aucune dépendance), prévu pour un hébergement Pterodactyl avec Python 3.11 :

```bash
cd server
python server.py          # écoute en TCP + UDP sur 0.0.0.0:27303
```

Le client est pré-rempli avec `5.180.34.43:27303` ; l'adresse se change dans l'écran *Multijoueur*.
Le serveur gère : lobby (le premier connecté est l'hôte), IA de l'entité, messages d'assistance **différents pour
chaque joueur**, mort / spectateur, état des portes, chat, validation des positions (anti-triche basique), 20 ticks/s.
Variables d'environnement : `LADRESSE_HOST`, `LADRESSE_PORT`, `LADRESSE_TIME_SCALE`.

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
server/                 server.py, server_config.py, game_state.py
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
