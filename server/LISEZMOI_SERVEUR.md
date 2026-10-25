# Serveur L'ADRESSE — installation Pterodactyl (ou tout PC / VPS)

Aucune dépendance : Python 3.8 ou plus récent suffit (3.11 recommandé).

## Fichiers à envoyer sur le serveur

Dans le dossier racine du serveur Pterodactyl (`/home/container`), mettez **uniquement ces 3 fichiers** :

| Fichier | Rôle |
| --- | --- |
| `server.py` | le serveur (à lancer) |
| `game_state.py` | état de la partie et IA de l'entité |
| `server_config.py` | réglages par défaut |

Optionnel : `server_config.json` (copie de `server_config.example.json`) pour changer des valeurs **sans toucher au code**.

Le plus simple : téléchargez `LADRESSE-serveur.zip` (publié avec le jeu) et décompressez-le dans `/home/container`.

## Réglages Pterodactyl (egg « Python »)

* **App py file / PY_FILE** : `server.py`
* **Requirements file** : laisser vide (aucune dépendance)
* **Allocation** : le port attribué (ex. 27303) doit être ouvert en **TCP et UDP** (Pterodactyl le fait pour l'allocation).
* Le port est détecté automatiquement (`SERVER_PORT` fourni par Pterodactyl). Rien à modifier.
* Commande d'arrêt : `stop` (ou `^C`) — l'arrêt est propre, les joueurs sont prévenus.

Le jeu se connecte par défaut à `5.180.34.43:27303`. Si votre port est différent, les joueurs l'indiquent dans
l'écran *Coopératif en ligne* (`IP:port`), ou changez `SERVER_HOST` / `SERVER_PORT` dans `config.py` du jeu.

## Console

`help`, `list` (joueurs, IP, phase), `kick <id>`, `say <texte>` (message à tous), `reset` (vide la salle), `stop`.

## Changer une valeur sans modifier le code

Par ordre de priorité : variable d'environnement `LADRESSE_<NOM>` (ex. `LADRESSE_MAX_PLAYERS=3`), puis
`server_config.json`, puis la valeur par défaut. Une valeur invalide est ignorée et signalée au démarrage.

| Clé (json) | Défaut | Description |
| --- | --- | --- |
| `port` | `SERVER_PORT` ou 27303 | port TCP + UDP |
| `host` | 0.0.0.0 | interface d'écoute |
| `max_players` | 4 | 1 à 4 |
| `motd` | « Bienvenue… » | message d'accueil |
| `time_scale` | 0.5 | durée de la partie (1.0 = solo) |
| `survival_seconds` | 360 | survie à tenir après la libération de l'entité |
| `tick_rate` | 20 | ticks / s |
| `max_connections` | 16 | connexions TCP simultanées |
| `max_per_ip` | 6 | connexions par IP |
| `client_timeout` | 25 | secondes sans message avant déconnexion |
| `udp_fallback_hz` | 10 | positions envoyées en TCP si l'UDP d'un joueur est bloqué |
| `rate_per_sec` / `rate_burst` / `flood_kick` | 90 / 180 / 600 | anti-flood |
| `log` | `server.log` | fichier journal (rotation à 2 Mo) |

## Héberger sans Pterodactyl

* Sur un PC : `python server.py` (ou le bouton **Héberger une partie** dans le jeu).
* Ouvrez le port 27303 en TCP **et** UDP sur la box (redirection vers le PC). Si l'UDP est bloqué, le jeu
  bascule automatiquement les positions en TCP.

## Vérifier

`python tests/server_stress_test.py` (depuis le dossier du jeu) lance un serveur local et l'attaque avec des
clients simulés : doit afficher `SERVER STRESS OK`.
