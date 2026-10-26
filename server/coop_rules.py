"""Règles du mode multijoueur (appliquées par l'hôte de la partie, pas par le serveur relais).

Modifier ces valeurs ne demande AUCUNE mise à jour du serveur : il suffit que tous les joueurs aient la même
version du jeu (le relais refuse les joueurs dont la version diffère de celle de l'hôte).
"""

# Quartier partagé : la partie commence dehors (rue des Lilas) ; la nuit démarre quand tous sont entrés
OUTSIDE_START = True
OUTSIDE_SPAWN = (11.2, 0.0, -6.9)       # trottoir devant le 17 (identique au solo, game_manager.OUTSIDE_START)

MAX_PLAYERS = 4                # limite par défaut d'un salon (l'hôte peut choisir de 1 à 8)
ROOM_MAX_CHOICES = (2, 3, 4, 5, 6, 8)
MODES = ("coop", "solo_survie", "traitre", "cauchemar")
DEFAULT_MODE = "coop"
QUEST_IDS = ("telephone_garnier", "commande_annulee", "sel_entrees")
TICK_RATE = 20
TICK_DT = 1.0 / TICK_RATE

# Anti-triche basique : vitesse maximale tolérée (m/s) et rayon de téléportation autorisé
MAX_SPEED = 9.5
SPEED_TOLERANCE = 1.8
WORLD_LIMIT = 300.0

# Mise à l'échelle du temps de la partie multijoueur (1.0 = durée solo)
TIME_SCALE = 0.5
SURVIVAL_SECONDS = 360.0       # survie après la libération de l'entité
FIRST_CANCEL_DELAY = 30.0
CONTACT_DELAY = 120.0
DELIVERY_SECONDS = 480.0

MEALS = {
    "kebab": "silencieux", "pizza": "rampant", "sushi": "multiple", "burger": "imposteur",
}
ADDRESSES_OK = ("17 rue des lilas", "4 impasse du calvaire")
NIGHTMARE_ADDRESS = "4 impasse du calvaire"

JACKET_COLORS = [(0.75, 0.2, 0.2), (0.2, 0.45, 0.8), (0.2, 0.65, 0.3), (0.85, 0.7, 0.15),
                 (0.55, 0.25, 0.7), (0.9, 0.45, 0.15), (0.2, 0.7, 0.7), (0.85, 0.85, 0.85)]

# Paires d'assistance : chaque joueur reçoit les deux versions dans un ordre différent
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

TRAITOR_ORDERS = [
    "Ouvre la porte d'entrée. Je ferai le reste.",
    "Donne-moi le code du portail (1704).",
    "Éteins une lumière dans le couloir ou le salon.",
    "Attire l'un d'eux seul dans une pièce à l'étage.",
    "Fais du bruit loin des autres pour les disperser.",
    "Ne les laisse pas tracer le sel devant les entrées.",
]
