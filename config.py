"""Configuration globale de L'ADRESSE : constantes, chemins, paramètres utilisateur."""
import json
import os
import sys
import tempfile

GAME_TITLE = "L'ADRESSE"
GAME_SUBTITLE = "17 rue des Lilas"
VERSION = "1.1.0"
CACHE_VERSION = "v5"

# --- Réseau ---------------------------------------------------------------
SERVER_HOST = "5.180.34.43"
SERVER_PORT = 27326          # serveur multijoueur : salons + parties
# Nom affiché aux joueurs à la place de l'adresse IP (qui reste connue du jeu seulement)
SERVER_NAME = "France 1"
SERVER_ALIASES = {SERVER_NAME.lower(): f"{SERVER_HOST}:{SERVER_PORT}"}
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
STAMINA_DRAIN = 10.0           # ~10 s de course
STAMINA_REGEN = 16.0
FLASHLIGHT_DRAIN = 0.35        # % par seconde
PHONE_DRAIN = 0.12             # % par seconde (écran allumé)
PHONE_DRAIN_IDLE = 0.015       # % par seconde, rangé (veille : ~1 % par minute)
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


def code_fingerprint(*funcs, extra=""):
    """Empreinte courte (10 hex) du bytecode de fonctions et des fonctions de leur module qu'elles appellent.

    Sert à nommer les fichiers du cache (textures, sons) : un générateur modifié par une mise à jour produit un
    nouveau fichier au lieu de réutiliser l'ancien. Marche aussi dans l'exécutable (pas besoin des sources)."""
    import hashlib
    import types
    h = hashlib.md5(extra.encode())
    seen = set()

    def code(co, glb, mod):
        if id(co) in seen:
            return
        seen.add(id(co))
        h.update(co.co_code)
        h.update(repr(co.co_names).encode())
        for c in co.co_consts:
            if isinstance(c, types.CodeType):
                code(c, glb, mod)
            elif isinstance(c, frozenset):                    # ordre d'itération variable d'un lancement à l'autre
                h.update(repr(sorted(map(repr, c))).encode())
            else:
                h.update(repr(c).encode())
        for n in co.co_names:
            f = glb.get(n)
            if isinstance(f, types.FunctionType) and f.__module__ == mod:
                code(f.__code__, glb, mod)
    for fn in funcs:
        code(fn.__code__, fn.__globals__, fn.__module__)
    return h.hexdigest()[:10]


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
    "vue": "f5",
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
    "vue": "Changer de vue (1re / 3e personne)",
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
    "rendu_multicoeur": True,         # Panda3D : cull et draw sur leurs propres threads (redémarrage requis)
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
    "vue": "Première personne",       # ou "Troisième personne"
    "cam_distance": 2.4,              # recul de la caméra en vue 3e personne (m)
    "cam_epaule": "Droite",           # Droite / Centre / Gauche
    "cam_lissage": True,              # caméra 3e personne amortie
    "bob_camera": True,               # balancement de la tête en marchant
    "difficulte": "Normal",           # Facile / Normal / Difficile / Cauchemar (choisie à chaque nouvelle partie)
    "quartier": True,                 # phase d'exploration du quartier avant la maison
    "didacticiel": True,              # didacticiel guidé et doublé
    "voix_reelles": True,             # voix françaises du système (Windows / espeak) si disponibles
    "elevenlabs_key": "",              # clé API ElevenLabs (prioritaire sur les voix système)
    "elevenlabs_voice_m": "",          # ID de la voix masculine ElevenLabs (auto si vide)
    "elevenlabs_voice_f": "",          # ID de la voix féminine ElevenLabs (auto si vide)
    "pause_auto": True,               # pause quand la fenêtre perd le focus
    "afficher_fps": False,
    "keys": dict(DEFAULT_KEYS),
    # Accessibilité
    "reduire_jumpscares": False,
    "daltonien": "Normal",
    "taille_texte": "Moyen",
    # Multijoueur
    "mp_adresse": SERVER_NAME,
    "mp_pseudo": "Joueur",
    "mp_max": 4,                      # limite de joueurs proposée à la création d'une partie
}

FOG_DENSITY = {"Près": 0.16, "Moyen": 0.11, "Loin": 0.075}
SHADOW_LEVELS = {"Basse": 512, "Moyenne": 1024, "Haute": 2048}
RESOLUTIONS = {"720p": (1280, 720), "1080p": (1920, 1080), "1440p": (2560, 1440)}
TEXT_SCALE = {"Petit": 0.85, "Moyen": 1.0, "Grand": 1.25}


def _compatible(default, value):
    """Le type d'une valeur chargée doit correspondre à celui de la valeur par défaut."""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, type(default))


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
            if not isinstance(saved, dict):
                raise ValueError("format")
            for k, v in saved.items():
                if k == "keys" and isinstance(v, dict):
                    for a, key in v.items():
                        if a in DEFAULT_KEYS and isinstance(key, str) and 0 < len(key) < 24:
                            self.data["keys"][a] = key
                elif k in self.data and _compatible(self.data[k], v):
                    self.data[k] = v
            # ancien serveur dédié (avant le relais) : on bascule sur le nouveau port
            # (et l'adresse IP enregistrée auparavant est remplacée par le nom affiché)
            if self.data.get("mp_adresse") in ("5.180.34.43:27303", "5.180.34.43", f"{SERVER_HOST}:{SERVER_PORT}"):
                self.data["mp_adresse"] = DEFAULT_SETTINGS["mp_adresse"]
        except (OSError, ValueError, TypeError):
            pass
        self._clamp()

    def _clamp(self):
        """Ramène les valeurs numériques dans des bornes sûres (fichier édité à la main, ancienne version...)."""
        bounds = {"fov": (60, 110), "sensibilite": (1, 30), "cam_distance": (1.2, 4.5), "vol_main": (0, 100),
                  "vol_music": (0, 100), "vol_sfx": (0, 100), "vol_voice": (0, 100), "msaa": (0, 8), "mp_max": (1, 8)}
        for k, (lo, hi) in bounds.items():
            try:
                self.data[k] = type(DEFAULT_SETTINGS[k])(max(lo, min(hi, self.data[k])))
            except (TypeError, ValueError):
                self.data[k] = DEFAULT_SETTINGS[k]

    def save(self):
        """Écriture atomique (fichier temporaire puis remplacement) : pas de fichier tronqué en cas de crash."""
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
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

DIFFICULTIES = ["Facile", "Normal", "Difficile", "Cauchemar"]
DIFFICULTY = {
    # entity : vitesse du livreur · detect : vue / flair de près · hear : ouïe · fov : champ de vision ·
    # search : durée de la traque quand il vous perd · ambush : délai entre deux embuscades (multiplicateurs)
    # battery / phone : consommation lampe / téléphone · stress : gain de stress · stamina / recovery : sprint
    # hits : contacts encaissés avant la mort (1 = mort au premier) · regen : vie récupérée par seconde
    # permadeath : la mort efface la sauvegarde (on recommence depuis le début)
    "Facile": dict(entity=0.8, detect=0.7, hear=0.65, fov=0.8, search=0.55, ambush=1.5, battery=0.6, phone=0.7,
                   stress=0.6, stamina=0.75, recovery=1.3, hits=3, regen=0.5, permadeath=False),
    "Normal": dict(entity=1.0, detect=1.0, hear=1.0, fov=1.0, search=1.0, ambush=1.0, battery=1.0, phone=1.0,
                   stress=1.0, stamina=1.0, recovery=1.0, hits=2, regen=0.0, permadeath=False),
    "Difficile": dict(entity=1.12, detect=1.25, hear=1.3, fov=1.2, search=1.4, ambush=0.75, battery=1.3, phone=1.2,
                      stress=1.25, stamina=1.2, recovery=0.85, hits=1, regen=0.0, permadeath=False),
    "Cauchemar": dict(entity=1.25, detect=1.5, hear=1.6, fov=1.45, search=2.0, ambush=0.55, battery=1.6, phone=1.4,
                      stress=1.45, stamina=1.35, recovery=0.75, hits=1, regen=0.0, permadeath=True),
}
DIFFICULTY_TEXT = {
    "Facile": ("Pour découvrir l'histoire.",
               "Le livreur est lent, voit et entend mal, et abandonne vite. Il faut trois contacts pour mourir, "
               "la vie remonte doucement. Batteries et souffle durent plus longtemps."),
    "Normal": ("L'expérience prévue.",
               "Le livreur vous traque normalement. Un contact vous blesse, le deuxième est fatal."),
    "Difficile": ("Il ne pardonne pas.",
                  "Plus rapide, plus attentif, il entend le moindre pas et cherche plus longtemps. "
                  "Un seul contact suffit. Batteries et souffle s'épuisent plus vite."),
    "Cauchemar": ("Une seule nuit. Une seule vie.",
                  "Le livreur voit presque tout, court vite et ne lâche jamais. Un contact est fatal "
                  "et la mort efface la sauvegarde : on recommence depuis le début."),
}


def diff(key):
    return DIFFICULTY.get(settings.get("difficulte", "Normal"), DIFFICULTY["Normal"])[key]

# --- Couleurs (r, g, b) 0..1 -------------------------------------------------
COL_WHITE = (1.0, 1.0, 1.0)
COL_BLOOD = (0.55, 0.02, 0.02)
COL_PHONE_BLUE = (0.35, 0.55, 1.0)
COL_QUICKEATS = (1.0, 0.45, 0.05)
COL_BANK = (0.1, 0.3, 0.75)
COL_MSG_GREEN = (0.2, 0.75, 0.3)
