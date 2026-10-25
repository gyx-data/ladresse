"""Configuration du serveur multijoueur L'ADRESSE (Pterodactyl, Python 3.8+, aucune dépendance).

Toutes les parties tournent sur ce serveur (règles : coop_rules.py, état : coop_state.py, déroulé : coop_game.py).
Seuls ces fichiers concernent le jeu : une mise à jour graphique ou solo du jeu ne demande rien côté serveur.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get("LADRESSE_CONFIG", os.path.join(HERE, "server_config.json"))

# Valeurs modifiables SANS toucher au code, par ordre de priorité :
#   1. variable d'environnement LADRESSE_<NOM>   (ex. LADRESSE_MAX_ROOMS=20)
#   2. fichier server_config.json à côté de server.py   (ex. {"motd": "Salut"})
#   3. pour le port uniquement : SERVER_PORT (fourni automatiquement par Pterodactyl)
#   4. valeur par défaut ci-dessous
try:
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as _f:
        _FILE = json.load(_f)
    if not isinstance(_FILE, dict):
        _FILE = {}
except (OSError, ValueError):
    _FILE = {}

CONFIG_ERRORS = []


def _get(name, default, cast=None, lo=None, hi=None):
    cast = cast or type(default)
    raw = os.environ.get("LADRESSE_" + name)
    if raw is None:
        raw = _FILE.get(name.lower(), _FILE.get(name))
    if raw is None:
        return default
    try:
        if cast is bool:
            v = raw if isinstance(raw, bool) else str(raw).strip().lower() in ("1", "true", "oui", "yes", "on")
        else:
            v = cast(raw)
        if lo is not None and v < lo or hi is not None and v > hi:
            raise ValueError("hors limites")
        return v
    except (TypeError, ValueError) as e:
        CONFIG_ERRORS.append(f"{name} = {raw!r} ignoré ({e}) -> {default!r}")
        return default


def _default_port():
    try:
        return int(os.environ.get("SERVER_PORT", "27326"))
    except ValueError:
        return 27326


HOST = _get("HOST", "0.0.0.0", str)
PORT = _get("PORT", _default_port(), int, 1, 65535)        # IP publique : 5.180.34.43
PROTOCOL_VERSION = "4.0"     # protocole réseau (4 = parties tenues par le serveur)
MOTD = _get("MOTD", "Bienvenue au 17 rue des Lilas.", str)[:200]
LOG_FILE = _get("LOG", os.path.join(HERE, "server.log"), str)

# Salons
MAX_ROOMS = _get("MAX_ROOMS", 64, int, 1, 10000)                 # salons simultanés sur le serveur
MAX_ROOM_PLAYERS = _get("MAX_ROOM_PLAYERS", 8, int, 1, 32)        # limite haute choisie par l'hôte
MAX_ROOMS_PER_IP = _get("MAX_ROOMS_PER_IP", 4, int, 1, 1000)

# Robustesse réseau
MAX_CONNECTIONS = _get("MAX_CONNECTIONS", 256, int, 1, 10000)  # connexions TCP simultanées
MAX_PER_IP = _get("MAX_PER_IP", 8, int, 1, 256)               # par adresse IP (amis derrière la même box)
CLIENT_TIMEOUT = _get("CLIENT_TIMEOUT", 25.0, float, 5, 600)  # s sans message -> déconnexion (ping client : 4 s)
MAX_LINE = _get("MAX_LINE", 32 * 1024, int, 1024, 1 << 20)   # taille maximale d'un message JSON
SEND_QUEUE_MAX = _get("SEND_QUEUE_MAX", 4000, int, 50, 100000)
RATE_PER_SEC = _get("RATE_PER_SEC", 150.0, float, 5, 10000)   # messages TCP par seconde tolérés (seau à jetons)
RATE_BURST = _get("RATE_BURST", 300, int, 5, 100000)
FLOOD_KICK = _get("FLOOD_KICK", 900, int, 10, 10 ** 7)        # messages rejetés avant exclusion
UDP_RATE_PER_SEC = _get("UDP_RATE_PER_SEC", 120.0, float, 5, 10000)
UDP_FALLBACK_HZ = _get("UDP_FALLBACK_HZ", 12.0, float, 1, 60)  # paquets UDP renvoyés en TCP si l'UDP d'un joueur est bloqué
