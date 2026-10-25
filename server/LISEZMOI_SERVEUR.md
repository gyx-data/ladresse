# Serveur relais L'ADRESSE — installation Pterodactyl (ou tout PC / VPS)

Aucune dépendance : Python 3.8 ou plus récent suffit.

## Comment ça marche

Le serveur est un **relais** : il ne fait tourner aucune partie.

* Il **liste les parties** disponibles. N'importe quel joueur peut **créer** la sienne (nom, nombre de joueurs
  maximum de 1 à 8, mot de passe facultatif) et les autres la **rejoignent** depuis l'écran *Multijoueur*.
* La partie tourne **chez le joueur qui l'a créée** (l'hôte) : IA du livreur, minuteries, messages d'assistance.
* Le serveur se contente de **faire suivre les paquets** entre les joueurs d'une même partie.
  Les positions passent en UDP, directement d'un joueur à tous les autres (un seul passage par le relais),
  et basculent automatiquement en TCP si l'UDP d'un joueur est bloqué.

Conséquence : **une mise à jour du jeu ne demande pas de mettre le serveur à jour.** Seuls les joueurs doivent
avoir la même version du jeu que l'hôte (le relais refuse les autres avec un message clair).
Il ne faut redéployer le serveur que si le protocole du relais change (version 3.x aujourd'hui), ce qui est rare.

Si l'hôte quitte pendant la partie, elle s'arrête pour tout le monde. S'il quitte dans le salon d'attente,
un autre joueur devient l'hôte.

## Fichiers à envoyer sur le serveur

Dans le dossier racine du serveur Pterodactyl (`/home/container`), mettez **uniquement ces 2 fichiers** :

| Fichier | Rôle |
| --- | --- |
| `server.py` | le relais (à lancer) |
| `server_config.py` | réglages par défaut |

Supprimez l'ancien `game_state.py` s'il est encore là : il ne sert plus.
Optionnel : `server_config.json` (copie de `server_config.example.json`) pour changer des valeurs **sans toucher au code**.

## Réglages Pterodactyl (egg « Python »)

* **App py file / PY_FILE** : `server.py`
* **Requirements file** : laisser vide (aucune dépendance)
* **Allocation** : 27326, ouverte en **TCP et UDP** (Pterodactyl le fait pour l'allocation).
* Le port est détecté automatiquement (`SERVER_PORT` fourni par Pterodactyl). Rien à modifier.
* Commande d'arrêt : `stop` (ou `^C`) — les joueurs sont prévenus.

Le jeu se connecte par défaut à `5.180.34.43:27326`. Un autre serveur peut être saisi en bas de l'écran
*Multijoueur* (champ « Serveur »).

## Console

`help`, `list` (salons, joueurs, IP, UDP), `rooms`, `kick <id>`, `close <code du salon>`, `say <texte>` (message
à tous), `stats`, `stop`.

## Changer une valeur sans modifier le code

Par ordre de priorité : variable d'environnement `LADRESSE_<NOM>` (ex. `LADRESSE_MAX_ROOMS=20`), puis
`server_config.json`, puis la valeur par défaut. Une valeur invalide est ignorée et signalée au démarrage.

| Clé (json) | Défaut | Description |
| --- | --- | --- |
| `port` | `SERVER_PORT` ou 27326 | port TCP + UDP |
| `host` | 0.0.0.0 | interface d'écoute |
| `motd` | « Bienvenue… » | message d'accueil affiché dans le jeu |
| `max_rooms` | 64 | parties simultanées sur le serveur |
| `max_room_players` | 8 | limite maximale qu'un hôte peut choisir |
| `max_rooms_per_ip` | 4 | parties créées depuis une même IP |
| `max_connections` | 256 | connexions TCP simultanées |
| `max_per_ip` | 8 | connexions par IP |
| `client_timeout` | 25 | secondes sans message avant déconnexion |
| `udp_fallback_hz` | 12 | paquets renvoyés en TCP par seconde si l'UDP d'un joueur est bloqué |
| `rate_per_sec` / `rate_burst` / `flood_kick` | 150 / 300 / 900 | anti-flood TCP |
| `udp_rate_per_sec` | 120 | paquets UDP par seconde et par joueur |
| `log` | `server.log` | fichier journal (rotation à 2 Mo) |

## Héberger sans Pterodactyl

* Sur un PC : `python server.py`, ou le bouton **Serveur local (LAN)** de l'écran *Multijoueur*.
* Pour jouer par Internet sur son propre PC : ouvrir le port 27326 en TCP **et** UDP sur la box.

## Vérifier

`python tests/server_stress_test.py` (depuis le dossier du jeu) lance un relais local, l'attaque avec des
clients simulés, puis joue une partie entre deux vrais clients du jeu : doit afficher `SERVER STRESS OK`.
