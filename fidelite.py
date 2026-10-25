"""Programme de fidélité du supermarché (« Carte Fidélité »).

Les cartes sont persistantes entre les parties (fichier fidelite.json dans le dossier de données).
Numérotation séquentielle : 9531700001 est la carte par défaut du joueur, chaque nouvelle carte
créée en caisse reçoit le numéro suivant (9531700002, 9531700003, ...).

Règles :
  * 1 point par euro payé (arrondi à l'inférieur) ;
  * prix « carte » sur certains articles (remise immédiate) ;
  * dès 100 points, un bon de 5 € est automatiquement déduit (100 points consommés) ;
  * historique des 30 derniers passages en caisse.

Petite référence : la carte 9531700000 existe déjà... au nom de M. Raymond Garnier.
"""
import json
import os
import time

import config

PREFIX = "95317"
FIRST_NUMBER = 9531700001
GARNIER_CARD = "9531700000"
POINTS_PER_VOUCHER = 100
VOUCHER_VALUE = 5.0


def _default_data():
    return {
        "version": 1,
        "next_number": FIRST_NUMBER + 1,
        "active": str(FIRST_NUMBER),
        "cards": {
            str(FIRST_NUMBER): {"holder": "ADRIEN M.", "points": 0, "created": "21/10", "visits": 0, "spent": 0.0, "history": []},
            GARNIER_CARD: {"holder": "M. R. GARNIER", "points": 1407, "created": "03/02/2009", "visits": 211, "spent": 1407.6,
                           "history": [["14/07", "GROS SEL 1KG x14 / PILES AA x8 / BOUGIES x40", 63.4],
                                       ["13/07", "GROS SEL 1KG x6", 12.9], ["12/07", "CADENAS / CHAINE 2M", 27.8]],
                           "locked": True},
        },
    }


def valid_format(number):
    n = str(number).strip().replace(" ", "")
    return len(n) == 10 and n.isdigit() and n.startswith(PREFIX)


class Loyalty:
    def __init__(self, path=None):
        self.path = path or os.path.join(config.app_data_dir(), "fidelite.json")
        self.data = _default_data()
        self.load()

    # --- persistance ------------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("cards"), dict):
                base = _default_data()
                base.update({k: d[k] for k in ("next_number", "active") if k in d})
                for num, card in d["cards"].items():
                    if valid_format(num) and isinstance(card, dict):
                        c = dict(base["cards"].get(num, {"holder": "CLIENT", "points": 0, "created": "", "visits": 0,
                                                          "spent": 0.0, "history": []}))
                        c.update({k: card[k] for k in ("holder", "points", "created", "visits", "spent", "history", "locked")
                                  if k in card})
                        c["points"] = max(0, int(c.get("points", 0)))
                        base["cards"][num] = c
                nxt = max([int(n) for n in base["cards"]] + [FIRST_NUMBER]) + 1
                base["next_number"] = max(int(base.get("next_number", nxt)), nxt)
                if base["active"] not in base["cards"]:
                    base["active"] = str(FIRST_NUMBER)
                self.data = base
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # --- cartes -----------------------------------------------------------
    @property
    def active(self):
        return self.data["active"]

    def card(self, number):
        return self.data["cards"].get(str(number).strip().replace(" ", ""))

    def exists(self, number):
        return self.card(number) is not None

    def set_active(self, number):
        n = str(number).strip().replace(" ", "")
        if n in self.data["cards"] and not self.data["cards"][n].get("locked"):
            self.data["active"] = n
            self.save()
            return True
        return False

    def create(self, holder="NOUVEAU CLIENT"):
        n = str(self.data["next_number"])
        self.data["next_number"] += 1
        self.data["cards"][n] = {"holder": holder, "points": 0, "created": time.strftime("%d/%m"), "visits": 0,
                                 "spent": 0.0, "history": []}
        self.data["active"] = n
        self.save()
        return n

    @staticmethod
    def pretty(number):
        n = str(number)
        return f"{n[:4]} {n[4:7]} {n[7:]}" if len(n) == 10 else n

    # --- calculs ----------------------------------------------------------
    def quote(self, lines, number):
        """lines : [(article, qty)] -> dict(sous_total, remises carte, bon, total, points gagnés)."""
        card = self.card(number) if number else None
        sub = sum(a.price * q for a, q in lines)
        disc = 0.0
        if card is not None and not card.get("locked"):
            disc = sum((a.price - a.card_price) * q for a, q in lines if a.card_price is not None)
        voucher = 0.0
        if card is not None and not card.get("locked") and card["points"] >= POINTS_PER_VOUCHER and sub - disc >= VOUCHER_VALUE:
            voucher = VOUCHER_VALUE
        total = round(max(0.0, sub - disc - voucher), 2)
        pts = int(total) if card is not None and not card.get("locked") else 0
        return dict(subtotal=round(sub, 2), discount=round(disc, 2), voucher=voucher, total=total, points=pts)

    def commit(self, lines, number, quote, date="21/10"):
        card = self.card(number) if number else None
        if card is None or card.get("locked"):
            return None
        if quote["voucher"] > 0:
            card["points"] -= POINTS_PER_VOUCHER
        card["points"] += quote["points"]
        card["visits"] = card.get("visits", 0) + 1
        card["spent"] = round(card.get("spent", 0.0) + quote["total"], 2)
        desc = " / ".join(f"{a.short} x{q}" for a, q in lines)[:80]
        card.setdefault("history", []).insert(0, [date, desc, quote["total"]])
        del card["history"][30:]
        self.save()
        return card["points"]
