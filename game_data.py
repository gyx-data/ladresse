"""Toutes les données narratives de L'ADRESSE (en français).

Aucune logique ici : uniquement des textes, des tables et des constantes
d'équilibrage utilisées par les autres modules.
"""

# ---------------------------------------------------------------------------
# Personnages
# ---------------------------------------------------------------------------
PLAYER_NAME = "Adrien Morel"
PLAYER_FIRST = "Adrien"
BOSS_NAME = "Mme Duval"
AGENCY = "Clairvue Immobilier"
HOUSE_ADDRESS = "17 rue des Lilas, 06300 Nice"
CITY = "Nice"

# ---------------------------------------------------------------------------
# SMS de la cinématique
# ---------------------------------------------------------------------------
INTRO_SMS = [
    ("21:03", "Mme Duval",
     "Adrien, j'ai un mandat urgent. État des lieux au 17 rue des Lilas, à Nice, côté Mont-Boron. "
     "Le propriétaire M. Garnier est décédé il y a 3 mois. Personne n'est entré depuis. "
     "Tarif doublé si les photos sont là demain 8h. Tu prends ?", False),
    ("21:04", "Adrien", "J'arrive.", True),
    ("21:05", "Mme Duval",
     "Merci. Les clés sont sous le pot de fleurs à gauche de l'entrée. Bonne soirée.", False),
    ("21:06", "Mme Duval", "Ah, et Adrien ? L'électricité est coupée. Prends ta lampe.", False),
]

CINEMATIC_CAPTIONS = {
    "bureau": ["Agence Clairvue Immobilier — Nice, Promenade des Anglais", "Vendredi 13 octobre — 20h58"],
    "voiture": ["Nice, colline du Mont-Boron — 21h34"],
    "titre": "L'ADRESSE",
}

# ---------------------------------------------------------------------------
# Applications / contacts
# ---------------------------------------------------------------------------
CONTACT_DUVAL = "Mme Duval"
CONTACT_MAMAN = "Maman"
CONTACT_SUPPORT = "QuickEats Support"

MAMAN_MESSAGES = [
    ("Maman", "Coucou mon chéri, tu rentres tard ce soir ?", "hier 18:12"),
    ("Adrien", "Oui, un petit boulot de dernière minute.", "hier 18:15"),
    ("Maman", "Tu manges bien ?", "hier 18:16"),
    ("Maman", "N'oublie pas d'appeler ta tante dimanche.", "hier 18:17"),
]

BANK_NAME = "BNR Banque"
BANK_BALANCE = 1247.83
BANK_CARD = "Visa •••• 4721"
BANK_TRANSACTIONS = [
    ("Esso — Bd Gambetta", -62.40, "12/10"),
    ("Monoprix — Jean Médecin", -48.17, "11/10"),
    ("Netflix", -13.49, "10/10"),
    ("Pharmacie Masséna", -11.80, "09/10"),
    ("Virement Clairvue Immobilier", 1180.00, "05/10"),
    ("Spotify", -10.99, "03/10"),
    ("Lignes d'Azur — Abonnement", -34.00, "01/10"),
]

BANK_CALL_ATTEMPTS = [
    # (type, texte) — type: 'wait' = musique d'attente, 'dead' = numéro non attribué, 'silence'
    ("wait", "Tous nos conseillers sont actuellement indisponibles. Veuillez réessayer ultérieurement."),
    ("dead", "Le numéro que vous avez composé n'est plus attribué."),
    ("silence", "..."),
]

# ---------------------------------------------------------------------------
# QuickEats
# ---------------------------------------------------------------------------
CATEGORIES = ["Pizza", "Burger", "Asiatique", "Kebab", "Desserts"]

# adresse -> description
ADDRESSES = {
    "bonne": {"label": "17 rue des Lilas", "difficulty": "normal",
              "aliases": ["17 rue des lilas", "17 rue des lilas 06300", "17 rue des lilas nice",
                          "17 rue des lilas, 06300 nice", "17 rue des lilas 06300 nice"]},
    "piege": {"label": "4 impasse du Calvaire", "difficulty": "cauchemar",
              "aliases": ["4 impasse du calvaire", "4 impasse du calvaire 06300",
                          "4 impasse du calvaire, 06300", "4 impasse du calvaire 06300 nice"]},
    "erreur": {"label": "23 boulevard du Mont-Boron", "difficulty": "none",
               "aliases": ["23 avenue du grand champ", "23 av du grand champ", "23 avenue du grand champ 06000"]},
}

MEALS = {
    "kebab": {
        "name": "Menu Nuit Tranquille", "desc": "Kebab frites + Coca", "price": 15.90,
        "entity": "silencieux", "stars": 3, "category": "Kebab", "color": (0.85, 0.5, 0.15),
    },
    "pizza": {
        "name": "Menu Réconfort", "desc": "Pizza 4 fromages", "price": 18.50,
        "entity": "rampant", "stars": 4, "category": "Pizza", "color": (0.9, 0.7, 0.2),
    },
    "sushi": {
        "name": "Menu Gastro", "desc": "Sushi variés + Miso", "price": 24.90,
        "entity": "multiple", "stars": 5, "category": "Asiatique", "color": (0.9, 0.35, 0.35),
    },
    "burger": {
        "name": "Menu Classique", "desc": "Burger + Frites + Sundae", "price": 13.90,
        "entity": "imposteur", "stars": 2, "category": "Burger", "color": (0.8, 0.5, 0.2),
    },
}
MEAL_ORDER = ["kebab", "pizza", "sushi", "burger"]

ENTITY_NAMES = {
    "silencieux": "Le Silencieux",
    "rampant": "Le Rampant",
    "multiple": "Le Multiple",
    "imposteur": "L'Imposteur",
}

ENTITY_DESCRIPTIONS = {
    "silencieux": "Il ne fait aucun bruit. Il attend que vous détourniez le regard.",
    "rampant": "À quatre pattes, rapide, il se glisse sous les meubles.",
    "multiple": "Trois silhouettes. Une seule est réelle.",
    "imposteur": "Il a l'air d'un livreur normal. Presque.",
}

ORDER_ERRORS = [
    "Commande annulée — restaurant fermé",
    "Commande annulée — adresse introuvable",
    "Commande annulée — erreur technique",
    "Commande annulée — nous ne livrons plus à cette adresse. Pour votre sécurité.",
]
FIRST_CANCEL = "Commande annulée — Fonds insuffisants"
ORDER_NO_ADDRESS = "Veuillez entrer une adresse de livraison"
ORDER_UNKNOWN_ADDRESS = "Adresse non reconnue"
ORDER_UNSERVED_ADDRESS = "Adresse non desservie"
ORDER_CONFIRMED = "Commande confirmée ! Votre livreur prépare votre repas..."

# ---------------------------------------------------------------------------
# Assistance
# ---------------------------------------------------------------------------
ASSIST_INTRO = [
    # (délai en secondes après l'événement précédent, texte)
    (0.0, "Bonjour Adrien. Nous avons constaté un problème avec votre commande. Nous y travaillons. "
          "Veuillez ne pas quitter les lieux."),
    (30.0, "Bonne nouvelle ! Votre commande a été reprise par un livreur partenaire. "
           "Il sera chez vous dans 8 minutes."),
    (60.0, "Votre livreur est en chemin."),
]
ASSIST_DELAY_AFTER_FIRST_CANCEL = 120.0        # (ancien déclenchement fixe, gardé pour le multijoueur)
# Solo : l'assistance ne contacte le joueur qu'une fois l'annulation « comprise » (banque vérifiée,
# banque appelée, nouvelle tentative de commande), puis après ce délai.
ASSIST_DELAY_AFTER_INVESTIGATION = 20.0

# Pensées d'Adrien qui guident l'enquête sur l'annulation (sous-titres seulement, pas de voix enregistrée)
LINE_CHECK_BANK = "Fonds insuffisants ? Il y a de l'argent sur ce compte... Je vais vérifier l'appli de la banque."
LINE_CALL_BANK = "Le paiement est refusé alors que le solde est largement suffisant. J'appelle la banque."
LINE_RETRY_ORDER = "Personne pour m'expliquer. Bon... je réessaie de commander."

# Objectifs d'attente affichés dans le HUD
OBJ_WAIT_ORDER = "Attendre votre commande QuickEats"
OBJ_WAIT_SUPPORT = "Attendre une réponse de QuickEats"
OBJ_READ_SUPPORT = "Lire les messages de QuickEats Support"
DELIVERY_TOTAL_SECONDS = 480.0

# Déroulé de l'attente (secondes depuis « Votre livreur est en chemin »)
PAIR_SCHEDULE = {
    1: dict(a=20.0, b=40.0, window_end=110.0),
    2: dict(a=125.0, b=145.0, window_end=220.0),
    3: dict(a=290.0, b=310.0, window_end=None),     # évalué au moment des coups à la porte
    4: dict(a=60.0, b=80.0, window_end=170.0),      # depuis la libération de l'entité
    5: dict(a=190.0, b=210.0, window_end=300.0),    # depuis la libération de l'entité
}

PAIRS = {
    1: {
        "topic": "lumiere",
        "A": "Conseil : laissez les lumières allumées. Le livreur doit pouvoir vous identifier.",
        "B": "CORRECTION : Éteignez toutes les lumières. Le livreur est photosensible.",
        "hint": "Les fenêtres sont condamnées. Garnier vivait dans le noir.",
    },
    2: {
        "topic": "etage",
        "A": "Restez au rez-de-chaussée. Le livreur ne monte pas les étages.",
        "B": "Montez à l'étage immédiatement. Le rez-de-chaussée n'est plus sûr.",
        "hint": "Les griffures sont sur la porte du sous-sol, au rez-de-chaussée.",
    },
    3: {
        "topic": "porte",
        "A": "Si le livreur frappe, ouvrez la porte. C'est la procédure.",
        "B": "N'OUVREZ PAS LA PORTE. Quoi que vous entendiez.",
        "hint": "Garnier n'a jamais ouvert. Et il a survécu des mois.",
    },
    4: {
        "topic": "bruit",
        "A": "Parlez-lui. Il a besoin d'entendre une voix humaine pour se calmer.",
        "B": "Ne faites AUCUN bruit. Il chasse au son.",
        "hint": "Cela dépend de ce qui vous poursuit.",
    },
    5: {
        "topic": "sel",
        "A": "Le sel est un répulsif efficace. Tracez un cercle autour de vous.",
        "B": "Ne touchez PAS au sel. C'est ce qui le maintient enfermé.",
        "hint": "Le cercle de sel de la chambre condamnée... et celui du sous-sol.",
    },
}

# Vérité de la paire 4 selon l'entité : 'A' ou 'B'
PAIR4_TRUTH = {"silencieux": "A", "rampant": "B", "multiple": "B", "imposteur": "B"}
# Vérité fixe des paires 1 à 3
PAIR_FIXED_TRUTH = {1: "B", 2: "B", 3: "B"}

ASSIST_PHASE4 = [
    # (secondes restantes, notification, texte app)
    (120, "Votre livreur arrive dans 2 minutes.", "Votre livreur est devant votre porte."),
    (60, "Votre livreur est devant chez vous.", "Votre livreur vous attend."),
    (30, "Votre livreur entre dans la zone de livraison.", "Livreur en zone de livraison."),
    (0, "Livraison effectuée. Bon appétit !", "Livraison effectuée."),
]
ASSIST_RATING = "Notez votre expérience. *****"

# Messages de paranoïa générés en multijoueur (par joueur, au hasard)
MULTI_PARANOIA = [
    "Ne faites pas confiance à {autre}.",
    "{autre} ne voit pas les choses correctement.",
    "{autre} est déjà passé de l'autre côté.",
    "Demandez à {autre} ce qu'il a vu dans le salon. Il ment.",
    "Restez près de {autre}. Il sait comment sortir.",
    "{autre} vous a menti sur la porte.",
    "Un seul d'entre vous est réellement ici.",
    "Votre équipier a été livré. Il ne vous le dira pas.",
]

# ---------------------------------------------------------------------------
# Monologues du joueur et murmures
# ---------------------------------------------------------------------------
MURMURS_STRESS = [
    "C'est quoi ça...",
    "Faut que je me casse...",
    "J'aurais pas dû venir...",
    "Y'a quelqu'un ?",
    "Respire... respire...",
    "C'est dans ma tête. C'est dans ma tête.",
    "Calme-toi, Adrien.",
]
LINE_HUNGRY = "J'ai la dalle... J'vais commander un truc."
LINE_DOOR_LOCKED = "La porte d'entrée... elle est verrouillée ? Je l'ai pas fermée."
LINE_START = "Bon... Photos, pièce par pièce, et je rentre."
LINE_FIRST_NIGHT = "Il fait glacial ici."
LINE_BEFORE_ORDER_EXPLORE = "Il me faut une adresse valide pour commander."
LINE_PHOTO_NOTHING = "Rien de spécial sur la photo."
LINE_PHOTO_SOMETHING = "Qu'est-ce que... c'était pas là tout à l'heure."

# ---------------------------------------------------------------------------
# Documents et objets de la maison
# ---------------------------------------------------------------------------
NOTEBOOK_PAGES = [
    "12 mars\n\nJ'ai encore entendu les coups cette nuit.\nTrois coups. Toujours trois.",
    "28 mars\n\nJ'ai commandé à manger ce soir. Le livreur a dit qu'il était devant la porte. "
    "J'ai regardé par le judas. Y'avait personne. Mais l'appli disait qu'il était LÀ.",
    "4 avril\n\nJ'ai barricadé la porte du sous-sol. Je sais ce qu'il y a en bas. Ça frappe la nuit.",
    "15 avril\n\nNe commande pas. Ne commande JAMAIS. Si tu commandes, il vient. Le livreur. "
    "Celui qui n'a pas de visage.",
    "2 mai\n\nIl écrit comme l'assistance. Mêmes mots, même politesse. Mais quand c'est lui, son téléphone "
    "s'allume. La lumière bleue passe sous la porte d'entrée. Toujours.",
    "(illisible)\n\nL'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE "
    "L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE L'ADRESSE ...\n"
    "[le mot est écrit 47 fois]",
]

BANK_STATEMENT_TEXT = (
    "BNR BANQUE — RELEVÉ DE COMPTE\n\nTitulaire : M. Raymond GARNIER\n"
    "17 rue des Lilas, 06300 Nice\n\n"
    "~~4 impasse du Calvaire, 06300~~\n(adresse barrée au stylo, plusieurs fois)\n\n"
    "Prélèvements : QuickEats x 23\nSolde : 0,00 €"
)

POLAROID_PAGES = [
    "Polaroïd 1 — le salon.\nLe fauteuil est tourné vers la fenêtre.\nUne silhouette sombre se tient derrière.",
    "Polaroïd 2 — la cuisine.\nLa porte du four est ouverte.\nQuelqu'un est accroupi dans l'angle.",
    "Polaroïd 3 — le couloir du premier.\nLes portraits au mur n'ont plus de visage.",
    "Polaroïd 4 — la chambre vide.\nLe crochet au plafond.\nLe cercle de sel est brisé.",
    "Polaroïd 5 — le couloir du rez-de-chaussée.\nLa porte du sous-sol est ouverte.\nElle ne l'est pas encore.",
]

PLAN_TEXT = (
    "PLAN ORIGINAL DE LA MAISON — architecte J. Perrin, 1961\n\n"
    "Rez-de-chaussée : entrée, salon, cuisine, salle d'eau, bureau.\n"
    "1er étage : trois chambres, salle de bain, placard.\n"
    "Combles.\n\nAucun sous-sol n'est dessiné.\n\n"
    "En marge, au stylo : « Il n'y a pas de sous-sol. »"
)

GARNIER_PHONE_TEXT = [
    "HISTORIQUE QUICKEATS — M. GARNIER",
    "23 commandes — toutes à 23h47 — toutes 'Livrée'.",
    "Dernière commande : 'En cours de livraison...'",
    "Date : le jour de sa mort.",
]

NEWSPAPER_HEADLINES = [
    "NICE-MONT-BORON : TROISIÈME DISPARITION EN DEUX ANS AUTOUR DE LA RUE DES LILAS",
    "Un livreur à scooter retrouvé sans vie Promenade des Anglais — enquête ouverte",
    "Les riverains inquiets : « On entend des coups la nuit »",
    "Petites annonces : maison à vendre, 23 boulevard du Mont-Boron. Visites sur rendez-vous.",
    "Météo : orages sur l'arrière-pays niçois, vigilance orange jusqu'à dimanche",
]

RECEIPTS_TEXT = (
    "Une pile de reçus QuickEats agrafés.\n\n"
    "Des dizaines. Toujours la même adresse. Toujours 'Livré'.\n"
    "Le champ 'Signature du client' est vide sur chacun d'eux.\n\n"
    "Dernier reçu : 23h47."
)

NOTE_FRIGO = "Ne pas commander après 23h."
NOTE_SDB = "IL SAIT OÙ TU ES"
NOTE_COAT = "Un bout de papier : un numéro de téléphone... barré, plusieurs fois."
NOTE_FRIGO_ADDRESS = "17 rue des Lilas, 06300 Nice\nCode du portail : 1704\n\n(au crayon, d'une autre main) NE LE DONNE À PERSONNE"
NOTE_DOOR_END_D = "Le gardien précédent est parti. Le poste est à vous."
WALL_MESSAGE_PHOTO = "Derrière le papier peint, écrit à la main : « IL EST DÉJÀ ARRIVÉ »"

INTERACT_TEXT = {
    "porte_cadenas": "La porte est barricadée. Il faudrait un outil pour retirer les planches.",
    "porte_condamnee": "La porte ne bouge pas. Elle semble bloquée de l'intérieur.",
    "volets_cloues": "Les volets sont cloués de l'extérieur.",
    "four": "Ça sent le brûlé.",
    "frigo_vide": "Ça empeste... Tout a pourri là-dedans, depuis des semaines. Et une note sur l'assiette.",
    "tiroirs_cles": "Un trousseau de clés. Elles n'ouvrent rien ici.",
    "miroir_drap": "Un drap recouvre le miroir.",
    "lit_forme": "Ce n'est qu'un amas d'oreillers. Mais la forme est dérangeante.",
    "rideau": "Rien derrière le rideau.",
    "congelateur_vide": "Vide. Les parois sont couvertes de griffures.",
    "porte_entree_verrouillee": "Verrouillée.",
    "tiroir_ferme": "Le tiroir est fermé à clé.",
    "uniforme": "Un uniforme de gardien de nuit. Au nom de R. Garnier.",
    "pharmacie": "Des anxiolytiques au nom de Garnier.",
    "radio_morte": "Le poste ne répond plus.",
    "jouet": "Un hochet. Il est tiède.",
}

REFLECTION_NOTE = "Le reflet bouge avec un léger retard."

# Textes de l'Imposteur
IMPOSTOR_LINES = [
    "Bonsoir ! J'ai votre commande !",
    "Vous pouvez m'ouvrir s'il vous plaît ?",
    "Monsieur Morel ? Votre kebab... euh, votre burger est prêt.",
    "Il y a quelqu'un ?",
    "C'est pour une livraison. Vous êtes bien Monsieur Morel ?",
    "Je ne vais pas vous faire de mal. C'est juste un repas.",
]

# ---------------------------------------------------------------------------
# Fins
# ---------------------------------------------------------------------------
ENDINGS = {
    "A": {
        "title": "Livraison refusée",
        "kind": "Bonne fin",
        "lines": [
            "Vous remontez du sous-sol. La porte d'entrée est déverrouillée.",
            "Vous sortez. Le soleil se lève.",
            "Vous vous retournez. La maison est normale. Comme si rien ne s'était passé.",
            "Votre téléphone vibre.",
            "QuickEats : « Votre commande a été annulée. Merci de votre compréhension. "
            "À bientôt sur QuickEats ! »",
        ],
        "post": "Mme Duval : « Adrien ? Les photos ? »",
    },
    "B": {
        "title": "5 étoiles",
        "kind": "Fin neutre",
        "lines": [
            "Les bougies sont allumées. L'entité se tient de l'autre côté du congélateur.",
            "Le téléphone affiche : « Notez votre livreur »",
            "Vous devez mettre 5 étoiles. Il n'y a pas d'autre choix.",
            "L'entité disparaît. Silence. Vous remontez. Vous sortez.",
            "Dans le rétroviseur, l'entité est assise à l'arrière.",
        ],
        "post": "Prochain arrêt : 4 impasse du Calvaire.",
    },
    "C": {
        "title": "Abonné",
        "kind": "Mauvaise fin",
        "lines": [
            "Le congélateur ne se ferme plus. Un bras noir en sort lentement.",
            "Le téléphone affiche : « Félicitations ! Vous êtes maintenant abonné QuickEats Premium. "
            "Livraisons illimitées. 24h/24. Partout. »",
            "L'entité se lève du congélateur. Elle est immense.",
            "Des pas lourds. Trois coups. BOUM. BOUM. BOUM.",
        ],
        "post": "Quelqu'un a commandé à votre adresse.",
    },
    "D": {
        "title": "Le nouveau gardien",
        "kind": "Fin secrète",
        "lines": [
            "Les bruits de la maison s'arrêtent, un à un.",
            "Le silence est total. La maison semble... calme.",
            "L'entité n'a pas été invitée.",
            "Sous la porte d'entrée, une note : « Le gardien précédent est parti. Le poste est à vous. »",
        ],
        "post": "Mme Duval envoie un nouveau mandat à un autre photographe. Pour la même adresse.",
    },
}

CREDITS = [
    ("L'ADRESSE", 2.0),
    ("", 0.5),
    ("Un jeu d'horreur en première personne", 1.0),
    ("", 0.5),
    ("Scénario, programmation, direction artistique", 1.0),
    ("Assets 100 % procéduraux", 1.0),
    ("Moteur : Ursina / Panda3D", 1.0),
    ("", 0.5),
    ("Merci d'avoir joué.", 1.0),
    ("N'ouvrez jamais la porte.", 1.5),
]

GAMEOVER_TITLE = "Livraison effectuée."
GAMEOVER_RATING = "Notez votre expérience :"
GAMEOVER_TIP = "Conseil : Lisez attentivement les messages de l'assistance. Tous ne disent pas la vérité."

# ---------------------------------------------------------------------------
# Quêtes
# ---------------------------------------------------------------------------
QUESTS = {
    "explorer": {
        "title": "Explorer la maison",
        "objective": "Explorer le rez-de-chaussée",
        "steps": [],
    },
    "commander": {
        "title": "Commander à manger",
        "objective": "Commander à manger avec QuickEats",
        "steps": [
            ("phone", "Ouvrir le téléphone"),
            ("app", "Ouvrir QuickEats"),
            ("addr_found", "Trouver une adresse valide"),
            ("addr_entered", "Entrer l'adresse"),
            ("meal", "Choisir un repas"),
            ("confirm", "Confirmer la commande"),
        ],
    },
    "comprendre": {
        "title": "Comprendre l'annulation",
        "objective": "Comprendre pourquoi la commande est annulée",
        "steps": [
            ("bank", "Vérifier l'application bancaire"),
            ("call", "Rappeler la banque"),
            ("retry", "Réessayer de commander"),
        ],
    },
    "survivre": {
        "title": "Survivre au Livreur",
        "objective": "Survivre aux instructions de l'assistance",
        "steps": [
            ("p1", "Message d'assistance n°1"),
            ("p2", "Message d'assistance n°2"),
            ("p3", "Message d'assistance n°3"),
            ("p4", "Message d'assistance n°4"),
            ("p5", "Message d'assistance n°5"),
        ],
    },
    "sous_sol": {
        "title": "Le sous-sol",
        "objective": "Descendre au sous-sol pour mettre fin au cycle",
        "steps": [
            ("planches", "Arracher les planches de la porte"),
            ("descendre", "Descendre"),
            ("congelateur", "Ouvrir le congélateur"),
            ("message", "Lire le message sur le téléphone"),
            ("final", "Événement final"),
        ],
    },
    "garnier": {
        "title": "L'histoire de Garnier",
        "objective": "Trouver les documents sur M. Garnier",
        "steps": [],
    },
}

REQUIRED_DOCS = ["carnet", "releve", "polaroids", "plan", "mur", "tel_garnier"]
DOC_TITLES = {
    "carnet": "Carnet de Garnier",
    "releve": "Relevé bancaire",
    "polaroids": "Polaroïds",
    "plan": "Plan de la maison",
    "mur": "Message sous le papier peint",
    "tel_garnier": "Téléphone de Garnier",
    "recus": "Reçus QuickEats",
    "journaux": "Journaux du salon",
    "note_frigo": "Note du réfrigérateur",
    "note_sdb": "Mot derrière le miroir",
    "regles": "Règles (à ne pas oublier)",
    "carnet_bianchi": "Carnet de Mme Bianchi",
    "telephone_bianchi": "Téléphone de Mme Bianchi",
}

SECONDARY_QUESTS = [
    ("piles", "Trouver toutes les piles", 5),
    ("photos", "Prendre 10 photos révélatrices", 10),
    ("pieces", "Explorer toutes les pièces", 0),
    ("docs", "Lire tous les documents de Garnier", len(REQUIRED_DOCS)),
]

# ---------------------------------------------------------------------------
# Conseils d'écran de chargement
# ---------------------------------------------------------------------------
LOADING_TIPS = [
    "La lumière attire ce qui rôde.",
    "Les murs gardent des secrets.",
    "Lisez tout. Doutez de tout.",
    "Le téléphone est votre seule fenêtre sur le monde.",
    "N'ouvrez jamais la porte.",
]

TUTORIAL_HINTS = [
    "ZQSD : se déplacer — Maj : courir — C : s'accroupir — E : interagir",
    "F : lampe torche — T : téléphone — Tab : inventaire",
]


# ---------------------------------------------------------------------------
# Quartier du Mont-Boron (avant d'entrer dans la maison)
# ---------------------------------------------------------------------------
LINE_OUTSIDE_START = "17 rue des Lilas... C'est là. Je devrais peut-être prendre deux-trois trucs au Carrefour avant."
OUTSIDE_HINT = "Le quartier est libre d'accès : supérette, restaurant, voisins. Entrez dans la maison quand vous êtes prêt."

NPC_LINES = {
    "Mme Bianchi": [
        "Vous allez au 17 ? Chez Garnier ? Faites bien attention à vous, mon petit.",
        "Depuis qu'il est mort, il y a de la lumière au grenier certaines nuits. Personne n'y habite pourtant.",
        "Moi je ne commande plus rien après 23 heures. Plus jamais.",
    ],
    "Karim": [
        "Salut ! Pas le temps, je finis mon tour du Mont-Boron.",
        "Le livreur de l'autre nuit ? Il est entré au 17... Je l'ai jamais vu ressortir.",
    ],
    "Jean-Mi": [
        "Belle soirée, hein ? Enfin, pour ici.",
        "Les volets du 17 sont cloués de l'intérieur. De l'intérieur, vous comprenez ?",
        "Si on vous appelle d'un numéro masqué cette nuit, ne décrochez pas.",
    ],
    "Lucie": [
        "On fête l'anniversaire de Théo. La socca de Nino, c'est la meilleure de Nice.",
        "Le quartier est mort après 22 heures. Sauf ici.",
    ],
    "Théo": [
        "Trente ans aujourd'hui. Et vous, vous faites quoi dans le coin à cette heure-ci ?",
        "Gardien de nuit au 17 ? Sérieux ? Bon courage, mec.",
    ],
    "Nino": ["Bonsoir ! Une socca bien chaude ?"],
    "Sandrine": [
        "La caisse 1 est fermée, utilisez les caisses automatiques.",
        "Vous avez la carte fidélité ? Ça fait des points, hein. Les piles sont en promo avec la carte.",
        "M. Garnier venait tous les soirs. Toujours du gros sel. Des kilos de gros sel...",
    ],
    "Moussa": [
        "Bonsoir.",
        "Les articles restent dans le magasin tant qu'ils ne sont pas payés.",
    ],
    "Brigadier Rossi": [
        "Bonsoir. Contrôle de routine, rien de grave.",
        "Vous êtes le gardien pour le 17 ? On a eu trois signalements de disparition dans cette rue.",
        "Si vous entendez frapper à la porte cette nuit... appelez-nous. Enfin, essayez.",
    ],
    "Gardien Martin": [
        "Circulez, s'il vous plaît.",
        "Le scooter retrouvé sur la Promenade... On n'a jamais retrouvé le livreur.",
    ],
    "Inès": [
        "Le 33 est encore en retard...",
        "Le 17 rue des Lilas ? La maison avec les volets cloués ? Bon courage.",
    ],
}
