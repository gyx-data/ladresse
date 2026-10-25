"""Configuration du serveur multijoueur L'ADRESSE (tourne seul sur Pterodactyl, Python 3.11+)."""
import os

HOST = os.environ.get("LADRESSE_HOST", "0.0.0.0")
PORT = int(os.environ.get("LADRESSE_PORT", "27303"))        # IP publique : 5.180.34.43
MAX_PLAYERS = 4
TICK_RATE = 20                                              # ticks par seconde
TICK_DT = 1.0 / TICK_RATE

# Anti-triche basique : vitesse maximale tolérée (m/s) et rayon de téléportation autorisé
MAX_SPEED = 9.5
SPEED_TOLERANCE = 1.8

# Mise à l'échelle du temps de la partie multijoueur (1.0 = durée solo)
TIME_SCALE = float(os.environ.get("LADRESSE_TIME_SCALE", "0.5"))
SURVIVAL_SECONDS = 360.0       # durée de survie après la libération de l'entité
FIRST_CANCEL_DELAY = 30.0
CONTACT_DELAY = 120.0
DELIVERY_SECONDS = 480.0

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
