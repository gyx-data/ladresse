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

    def delete(self):
        for p in (self.path, self.path + ".bak"):
            try:
                os.remove(p)
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
                f.flush()
                os.fsync(f.fileno())
            # garde la sauvegarde précédente en secours (fichier corrompu, coupure de courant...)
            if os.path.exists(self.path):
                try:
                    os.replace(self.path, self.path + ".bak")
                except OSError:
                    pass
            os.replace(tmp, self.path)
            return True
        except Exception:
            return False

    @staticmethod
    def _valid(d):
        return (isinstance(d, dict) and isinstance(d.get("state"), dict) and isinstance(d["state"].get("act", 1), int)
                and isinstance(d.get("quests", {}), dict) and isinstance(d.get("assistance", {}), dict))

    def load(self):
        """Charge la sauvegarde ; si elle est illisible, bascule sur la copie de secours (.bak)."""
        for path in (self.path, self.path + ".bak"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if self._valid(d):
                    return d
            except (OSError, ValueError, UnicodeDecodeError):
                continue
        return None

    def exists(self):
        return self.load() is not None if (os.path.exists(self.path) or os.path.exists(self.path + ".bak")) else False
