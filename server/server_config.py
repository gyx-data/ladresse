"""Configuration du serveur multijoueur L'ADRESSE (tourne seul sur Pterodactyl, Python 3.11+)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get("LADRESSE_CONFIG", os.path.join(HERE, "server_config.json"))

# Valeurs modifiables SANS toucher au code, par ordre de priorité :
#   1. variable d'environnement LADRESSE_<NOM>   (ex. LADRESSE_PORT=27303, LADRESSE_MAX_PLAYERS=4)
#   2. fichier server_config.json à côté de server.py   (ex. {"port": 27303, "motd": "Salut"})
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
        return int(os.environ.get("SERVER_PORT", "27303"))
    except ValueError:
        return 27303


HOST = _get("HOST", "0.0.0.0", str)
PORT = _get("PORT", _default_port(), int, 1, 65535)        # IP publique : 5.180.34.43
MAX_PLAYERS = _get("MAX_PLAYERS", 4, int, 1, 4)
PROTOCOL_VERSION = "2.0"
MOTD = _get("MOTD", "Bienvenue au 17 rue des Lilas.", str)[:200]
LOG_FILE = _get("LOG", os.path.join(HERE, "server.log"), str)

# Robustesse réseau
MAX_CONNECTIONS = _get("MAX_CONNECTIONS", 16, int, 1, 512)   # connexions TCP simultanées (lobby + curieux)
MAX_PER_IP = _get("MAX_PER_IP", 6, int, 1, 64)               # par adresse IP (amis derrière la même box)
CLIENT_TIMEOUT = _get("CLIENT_TIMEOUT", 25.0, float, 5, 600)  # s sans message -> déconnexion (ping client : 4 s)
MAX_LINE = _get("MAX_LINE", 16 * 1024, int, 1024, 1 << 20)   # taille maximale d'un message JSON
SEND_QUEUE_MAX = _get("SEND_QUEUE_MAX", 2000, int, 50, 100000)
RATE_PER_SEC = _get("RATE_PER_SEC", 90.0, float, 5, 10000)    # messages TCP par seconde tolérés (seau à jetons)
RATE_BURST = _get("RATE_BURST", 180, int, 5, 100000)
FLOOD_KICK = _get("FLOOD_KICK", 600, int, 10, 10 ** 7)        # messages rejetés avant exclusion
TICK_RATE = _get("TICK_RATE", 20, int, 5, 60)                 # ticks par seconde
TICK_DT = 1.0 / TICK_RATE
UDP_FALLBACK_HZ = _get("UDP_FALLBACK_HZ", 10.0, float, 1, 60)  # positions par TCP si l'UDP est bloqué

# Anti-triche basique : vitesse maximale tolérée (m/s) et rayon de téléportation autorisé
MAX_SPEED = _get("MAX_SPEED", 9.5, float, 1, 100)
SPEED_TOLERANCE = _get("SPEED_TOLERANCE", 1.8, float, 0, 50)
WORLD_LIMIT = 300.0            # coordonnées absurdes rejetées (|x|, |y|, |z| > 300 m)

# Mise à l'échelle du temps de la partie multijoueur (1.0 = durée solo)
TIME_SCALE = _get("TIME_SCALE", 0.5, float, 0.01, 10)
SURVIVAL_SECONDS = _get("SURVIVAL_SECONDS", 360.0, float, 10, 7200)   # survie après la libération de l'entité
FIRST_CANCEL_DELAY = _get("FIRST_CANCEL_DELAY", 30.0, float, 1, 3600)
CONTACT_DELAY = _get("CONTACT_DELAY", 120.0, float, 1, 3600)
DELIVERY_SECONDS = _get("DELIVERY_SECONDS", 480.0, float, 10, 7200)

MEALS = {
    "kebab": "silencieux", "pizza": "rampant", "sushi": "multiple", "burger": "imposteur",
}
ADDRESSES_OK = ("17 rue des lilas", "4 impasse du calvaire")
NIGHTMARE_ADDRESS = "4 impasse du calvaire"

JACKET_COLORS = [(0.75, 0.2, 0.2), (0.2, 0.45, 0.8), (0.2, 0.65, 0.3), (0.85, 0.7, 0.15)]

# Paires d'assistance (textes dupliqués ici : le serveur est autonome)
PAIRS = {
    1: ("Conseil : laissez les lumières allumées. Le livreur doit pouvoir vous identifier.",
        "CORRECTION : Éteignez toutes les lumières. Le livreur est photosensible."),
    2: ("Restez au rez-de-chaussée. Le livreur ne monte pas les étages.",
        "Montez à l'étage immédiatement. Le rez-de-chaussée n'est plus sûr."),
    3: ("Si le livreur frappe, ouvrez la porte. C'est la procédure.",
        "N'OUVREZ PAS LA PORTE. Quoi que vous entendiez."),
    4: ("Parlez-lui. Il a besoin d'entendre une voix humaine pour se calmer.",
        "Ne faites AUCUN bruit. Il chasse au son."),
    5: ("Le sel est un répulsif efficace. Tracez un cercle autour de vous.",
        "Ne touchez PAS au sel. C'est ce qui le maintient enfermé."),
}
PAIR_SCHEDULE = {1: (20, 40), 2: (125, 145), 3: (290, 310)}
PAIR_SCHEDULE_AFTER_RELEASE = {4: (60, 80), 5: (190, 210)}

PARANOIA = [
    "Ne faites pas confiance à {autre}.",
    "{autre} ne voit pas les choses correctement.",
    "{autre} est déjà passé de l'autre côté.",
    "{autre} vous a menti sur la porte.",
    "Un seul d'entre vous est réellement ici.",
    "Restez près de {autre}. Il sait comment sortir.",
]
