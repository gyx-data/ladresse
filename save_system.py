"""Sauvegarde / chargement : fichier JSON dans %APPDATA%/LADRESSE/save.json.

Sauvegarde automatique à chaque changement d'acte (fin de cinématique, première annulation,
arrivée du livreur, descente au sous-sol). Pas de sauvegarde manuelle ; aucune en multijoueur.
"""
import json
import os
import time

import config


class SaveSystem:
    def __init__(self):
        self.path = os.path.join(config.app_data_dir(), "save.json")

    def exists(self):
        return os.path.exists(self.path)

    def delete(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def save(self, game, tag=""):
        if game.is_multiplayer:
            return False
        try:
            data = dict(
                version=config.VERSION, tag=tag, saved_at=time.time(),
                state=game.state.to_dict(),
                quests=game.quests.to_dict(),
                assistance=game.assistance.to_dict(),
                entity=game.entity.serialize() if game.entity and game.entity.kind else None,
                doors={did: d.is_open for did, d in game.house.doors.items()},
                playtime=game.playtime,
            )
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, self.path)
            return True
        except Exception:
            return False

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None
