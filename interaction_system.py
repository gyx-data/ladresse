"""Système d'interaction : portes, objets, interrupteurs, papiers...

Les objets interactifs sont de simples points 3D (pas de colliders Ursina) : la cible est
celle qui est la plus proche du centre de l'écran dans un cône étroit, à portée, et non
masquée par un mur. L'invite « [E] Ouvrir » est affichée au centre de l'écran.
"""
import math

from ursina import Vec3


class Interactable:
    def __init__(self, iid, pos, prompt, on_use, level=0, radius=0.7, enabled=True,
                 reach=2.3, can_use=None, once=False, door=None):
        self.id = iid
        self.pos = Vec3(*pos)
        self.prompt = prompt          # str ou callable() -> str | None
        self.on_use = on_use
        self.level = level
        self.radius = radius
        self.enabled = enabled
        self.reach = reach
        self.can_use = can_use
        self.once = once
        self.used = False
        self.door = door

    def current_prompt(self):
        if not self.enabled or (self.once and self.used):
            return None
        if self.can_use is not None and not self.can_use():
            return None
        p = self.prompt() if callable(self.prompt) else self.prompt
        return p


class InteractionSystem:
    def __init__(self, house=None):
        self.items = {}
        self.house = house
        self.target = None
        self.cooldown = 0.0

    def add(self, item):
        self.items[item.id] = item
        return item

    def remove(self, iid):
        self.items.pop(iid, None)

    def get(self, iid):
        return self.items.get(iid)

    def enable(self, iid, state=True):
        it = self.items.get(iid)
        if it:
            it.enabled = state

    def clear(self):
        self.items.clear()
        self.target = None

    def find_target(self, cam_pos, cam_dir):
        """Retourne l'Interactable visé, ou None."""
        best, best_score = None, 1e9
        for it in self.items.values():
            if it.current_prompt() is None:
                continue
            to = it.pos - cam_pos
            dist = to.length()
            if dist > it.reach + it.radius or dist < 0.05:
                continue
            if abs(it.pos[1] - cam_pos[1]) > 2.6:
                continue
            d = to / dist
            cosang = d.dot(cam_dir)
            # tolérance angulaire : plus l'objet est grand/proche, plus large
            tol = math.cos(math.atan2(it.radius + 0.12, max(dist, 0.3)))
            if cosang < tol or cosang < 0.78:
                continue
            if self.house is not None:
                eye = cam_pos
                target = it.pos
                if self.house.wall_count(eye, target) > 0 and dist > 0.9:
                    continue
            score = (1.0 - cosang) * 10.0 + dist * 0.1
            if score < best_score:
                best, best_score = it, score
        self.target = best
        return best

    def use(self, item=None):
        it = item or self.target
        if it is None or it.current_prompt() is None:
            return False
        it.used = True
        it.on_use(it)
        return True
