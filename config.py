"""Configuration globale de L'ADRESSE : constantes, chemins, paramètres utilisateur."""
import json
import os
import sys
import tempfile

GAME_TITLE = "L'ADRESSE"
GAME_SUBTITLE = "17 rue des Lilas"
VERSION = "1.0.0"
CACHE_VERSION = "v1"

# --- Réseau ---------------------------------------------------------------
SERVER_HOST = "5.180.34.43"
SERVER_PORT = 27303
TICK_RATE = 20
MAX_PLAYERS = 4

# --- Maison ---------------------------------------------------------------
HOUSE_W = 16.0
HOUSE_D = 12.0
FLOOR_H = 3.0
WALL_T = 0.2
DOOR_W = 0.9
DOOR_H = 2.1
BASEMENT_Y = -3.0
BASEMENT_CEIL_H = 2.2

# Altitudes (sol) de chaque niveau
LEVEL_Y = {-1: BASEMENT_Y, 0: 0.0, 1: FLOOR_H, 2: 2 * FLOOR_H}
LEVEL_NAMES = {-1: "Sous-sol", 0: "Rez-de-chaussée", 1: "Premier étage", 2: "Grenier"}

# --- Joueur ---------------------------------------------------------------
PLAYER_HEIGHT = 1.7
PLAYER_CROUCH_HEIGHT = 1.0
PLAYER_RADIUS = 0.32
WALK_SPEED = 2.6
SPRINT_SPEED = 4.6
CROUCH_SPEED = 1.3
JUMP_SPEED = 3.6
GRAVITY = 11.0
STAMINA_DRAIN = 22.0
STAMINA_REGEN = 14.0
FLASHLIGHT_DRAIN = 0.35        # % par seconde
PHONE_DRAIN = 0.12             # % par seconde
PHONE_DRAIN_QUICKEATS = 0.35
PHONE_DRAIN_CALL = 0.5
GAME_MINUTES_PER_REAL_MINUTE = 5

# --- Chemins --------------------------------------------------------------


def app_data_dir():
    base = os.environ.get("APPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    path = os.path.join(base, "LADRESSE")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        path = os.path.join(tempfile.gettempdir(), "LADRESSE_data")
        os.makedirs(path, exist_ok=True)
    return path


def cache_dir(sub=""):
    path = os.path.join(tempfile.gettempdir(), "LADRESSE_cache", CACHE_VERSION, sub)
    os.makedirs(path, exist_ok=True)
    return path


def resource_path(rel):
    """Chemin d'une ressource, compatible PyInstaller (sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# --- Paramètres utilisateur ----------------------------------------------
DEFAULT_KEYS = {
    "avancer": "w",
    "reculer": "s",
    "gauche": "a",
    "droite": "d",
    "sprint": "left shift",
    "sauter": "space",
    "interagir": "e",
    "lampe": "f",
    "telephone": "t",
    "inventaire": "tab",
    "accroupir": "c",
    "parler": "v",
}

# Touches alternatives acceptées tant que la touche par défaut est conservée (ZQSD / WASD)
ALT_KEYS = {"avancer": "z", "gauche": "q"}

KEY_LABELS = {
    "avancer": "Avancer",
    "reculer": "Reculer",
    "gauche": "Gauche",
    "droite": "Droite",
    "sprint": "Sprint",
    "sauter": "Sauter",
    "interagir": "Interagir",
    "lampe": "Lampe torche",
    "telephone": "Téléphone",
    "inventaire": "Inventaire",
    "accroupir": "S'accroupir",
    "parler": "Parler à voix haute",
}

DEFAULT_SETTINGS = {
    # Graphismes
    "ombres": "Moyenne",
    "fog": "Moyen",
    "particules": True,
    "postprocess": True,
    "resolution": "Natif",
    "plein_ecran": True,
    "vsync": True,
    "fps_max": "60",
    "msaa": 4,
    # Audio
    "vol_main": 80,
    "vol_music": 70,
    "vol_sfx": 80,
    "vol_voice": 80,
    "sous_titres": True,
    # Contrôles
    "sensibilite": 10,
    "inverser_y": False,
    "fov": 75,
    "keys": dict(DEFAULT_KEYS),
    # Accessibilité
    "reduire_jumpscares": False,
    "daltonien": "Normal",
    "taille_texte": "Moyen",
    # Multijoueur
    "mp_adresse": f"{SERVER_HOST}:{SERVER_PORT}",
    "mp_pseudo": "Joueur",
}

FOG_DENSITY = {"Près": 0.16, "Moyen": 0.11, "Loin": 0.075}
SHADOW_LEVELS = {"Basse": 512, "Moyenne": 1024, "Haute": 2048}
RESOLUTIONS = {"720p": (1280, 720), "1080p": (1920, 1080), "1440p": (2560, 1440)}
TEXT_SCALE = {"Petit": 0.85, "Moyen": 1.0, "Grand": 1.25}


class Settings:
    """Paramètres persistants (JSON dans %APPDATA%/LADRESSE/settings.json)."""

    def __init__(self):
        self.path = os.path.join(app_data_dir(), "settings.json")
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k == "keys" and isinstance(v, dict):
                    self.data["keys"].update(v)
                elif k in self.data:
                    self.data[k] = v
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def get(self, key, default=None):
        return self.data.get(key, default)

    def key(self, action):
        return self.data["keys"].get(action, DEFAULT_KEYS[action])

    def reset(self):
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))

    def volume(self, channel):
        """Volume effectif 0..1 d'un canal ('music', 'sfx', 'voice')."""
        return (self.data["vol_main"] / 100.0) * (self.data["vol_" + channel] / 100.0)


settings = Settings()

# --- Couleurs (r, g, b) 0..1 -------------------------------------------------
COL_WHITE = (1.0, 1.0, 1.0)
COL_BLOOD = (0.55, 0.02, 0.02)
COL_PHONE_BLUE = (0.35, 0.55, 1.0)
COL_QUICKEATS = (1.0, 0.45, 0.05)
COL_BANK = (0.1, 0.3, 0.75)
COL_MSG_GREEN = (0.2, 0.75, 0.3)
