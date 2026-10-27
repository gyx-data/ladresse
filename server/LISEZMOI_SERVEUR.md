# Serveur multijoueur L'ADRESSE — installation Pterodactyl (ou tout PC / VPS)

Aucune dépendance : Python 3.8 ou plus récent suffit.

## Comment ça marche

**Toutes les parties tournent sur ce serveur.**

* L'écran *Multijoueur* du jeu liste les parties disponibles. N'importe quel joueur peut **créer** la sienne
  (nom, nombre de joueurs maximum de 1 à 8, mot de passe facultatif) ; les autres la **rejoignent**.
* Chaque partie (IA du livreur, minuteries, messages d'assistance, morts, victoire) tourne **ici**, dans une
  seule boucle de jeu à 20 ticks/s pour tous les salons. Si le créateur quitte, la partie **continue** et un autre
  joueur devient créateur. Le salon disparaît quand le dernier joueur part.
* Les positions des joueurs passent en UDP, directement d'un joueur à tous les autres (un seul passage par le
  serveur), et basculent automatiquement en TCP si l'UDP d'un joueur est bloqué.

Quand faut-il mettre le serveur à jour ?
* **Oui** si les règles du multijoueur changent : `coop_rules.py`, `coop_state.py`, `coop_game.py`.
* **Non** pour tout le reste (graphismes, interface, maison, quartier, mode solo...).
Les joueurs d'une même partie doivent avoir la même version du jeu (le serveur refuse les autres avec un message clair).

## Fichiers à envoyer sur le serveur

Décompressez `LADRESSE-serveur.zip` dans le dossier racine du serveur Pterodactyl (`/home/container`) :

| Fichier | Rôle |
| --- | --- |
| `server.py` | le serveur (fichier à lancer) |
| `server_config.py` | réglages réseau par défaut |
| `coop_game.py` | déroulé d'une partie |
| `coop_state.py` | état d'une partie, IA du livreur |
| `coop_rules.py` | règles et durées du multijoueur |

Supprimez l'ancien `game_state.py` s'il est encore là : il ne sert plus.
Optionnel : `server_config.json` (copie de `server_config.example.json`) pour changer des valeurs **sans toucher au code**.

## Réglages Pterodactyl (egg « Python »)

* **App py file / PY_FILE** : `server.py`
* **Requirements file** : laisser vide (aucune dépendance)
* **Allocation** : 27326, ouverte en **TCP et UDP** (Pterodactyl le fait pour l'allocation).
* Le port est détecté automatiquement (`SERVER_PORT` fourni par Pterodactyl). Rien à modifier.
* Commande d'arrêt : `stop` (ou `^C`) — les joueurs sont prévenus.

Au démarrage, la console affiche « serveur démarré sur 0.0.0.0:27326 ».
Le jeu se connecte par défaut à `5.180.34.43:27326`. Un autre serveur peut être saisi en bas de l'écran
*Multijoueur* (champ « Serveur »).

## Console

`help`, `list` (salons, phase de chaque partie, joueurs, IP, UDP), `rooms`, `kick <id>`, `close <code du salon>`,
`say <texte>` (message à tous), `stats` (trafic, temps moyen d'un tick), `stop`.

## Changer une valeur sans modifier le code

Par ordre de priorité : variable d'environnement `LADRESSE_<NOM>` (ex. `LADRESSE_MAX_ROOMS=20`), puis
`server_config.json`, puis la valeur par défaut. Une valeur invalide est ignorée et signalée au démarrage.

| Clé (json) | Défaut | Description |
| --- | --- | --- |
| `port` | `SERVER_PORT` ou 27326 | port TCP + UDP |
| `host` | 0.0.0.0 | interface d'écoute |
| `motd` | « Bienvenue… » | message d'accueil affiché dans le jeu |
| `max_rooms` | 64 | parties simultanées sur le serveur |
| `max_room_players` | 8 | limite maximale qu'un créateur peut choisir |
| `max_rooms_per_ip` | 4 | parties créées depuis une même IP |
| `max_connections` | 256 | connexions TCP simultanées |
| `max_per_ip` | 8 | connexions par IP |
| `client_timeout` | 25 | secondes sans message avant déconnexion |
| `udp_fallback_hz` | 12 | paquets renvoyés en TCP par seconde si l'UDP d'un joueur est bloqué |
| `rate_per_sec` / `rate_burst` / `flood_kick` | 150 / 300 / 900 | anti-flood TCP |
| `udp_rate_per_sec` | 120 | paquets UDP par seconde et par joueur |
| `log` | `server.log` | fichier journal (rotation à 2 Mo) |

Les durées et règles de partie (temps de survie, rythme des évènements...) se règlent dans `coop_rules.py`.

## Héberger sans Pterodactyl

* Sur un PC : `python server.py`, ou le bouton **Serveur local (LAN)** de l'écran *Multijoueur*.
* Pour jouer par Internet sur son propre PC : ouvrir le port 27326 en TCP **et** UDP sur la box.

## Vérifier

`python tests/server_stress_test.py` (depuis le dossier du jeu) lance un serveur local, l'attaque avec des
clients simulés, joue une partie entre deux vrais clients du jeu et fait tourner 40 parties en parallèle :
doit afficher `SERVER STRESS OK`.
