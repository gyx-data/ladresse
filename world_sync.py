"""Multijoueur : synchronisation de l'état du monde entre joueurs (maison partagée).

Après chaque interaction locale, on compare l'état du monde avant / après et on envoie seulement ce qui a changé
aux autres joueurs (relais « à tous », sans passer par la partie du serveur) :
  * objets fouillés / ramassés (state.opened), documents lus (state.docs), drapeaux du monde (miroir dévoilé,
    planches arrachées...) ;
  * portes ouvertes / fermées, pièces animées (tiroirs, porte du frigo, rideau...) et pièces masquées ;
  * interactables désactivés (pile ramassée) ou déjà utilisés.
L'inventaire n'est pas partagé : celui qui ramasse garde l'objet, les autres le voient simplement disparaître.
"""

# drapeaux propres à un joueur (jamais recopiés chez les autres)
PRIVATE_FLAGS = ("phone_used", "rewinds", "order_", "courier_", "tuto", "first_", "bank_", "play_started")


def _private(k):
    return any(k.startswith(p) for p in PRIVATE_FLAGS)


def snapshot(game):
    st, h = game.state, game.house
    parts = {}
    for name, part in getattr(h, "parts", {}).items():
        parts[name] = (getattr(part, "is_open", None), getattr(part, "enabled", None))
    return dict(
        opened=set(st.opened), docs=set(st.docs),
        flags={k: v for k, v in st.flags.items() if not _private(k) and isinstance(v, (bool, int, float, str))},
        parts=parts,
        doors={did: d.is_open for did, d in h.doors.items()},
        ia={iid: (it.enabled, getattr(it, "used", False)) for iid, it in game.interactions.items.items()},
    )


def diff(a, b):
    """Changements de a vers b, sous forme sérialisable (None si rien n'a changé)."""
    d = {}
    if b["opened"] - a["opened"]:
        d["opened"] = sorted(b["opened"] - a["opened"])
    if b["docs"] - a["docs"]:
        d["docs"] = sorted(b["docs"] - a["docs"])
    fl = {k: v for k, v in b["flags"].items() if a["flags"].get(k) != v}
    if fl:
        d["flags"] = fl
    pa = {k: list(v) for k, v in b["parts"].items() if a["parts"].get(k) != v}
    if pa:
        d["parts"] = pa
    do = {k: v for k, v in b["doors"].items() if a["doors"].get(k) != v}
    if do:
        d["doors"] = do
    ia = {k: list(v) for k, v in b["ia"].items() if a["ia"].get(k) != v}
    if ia:
        d["ia"] = ia
    return d or None


def apply(game, d):
    """Applique les changements reçus d'un autre joueur (sans effets personnels : pas de texte, pas d'objet)."""
    st, h = game.state, game.house
    for k in d.get("opened", ()):
        st.opened.add(k)
    for k in d.get("docs", ()):
        st.docs.add(k)
    for k, v in (d.get("flags") or {}).items():
        if not _private(k):
            st.flags[k] = v
    for name, (is_open, enabled) in (d.get("parts") or {}).items():
        part = h.parts.get(name)
        if part is None:
            continue
        if enabled is not None and hasattr(part, "enabled"):
            part.enabled = bool(enabled)
        if is_open is not None and hasattr(part, "set_open") and getattr(part, "is_open", None) != is_open:
            try:
                part.set_open(bool(is_open))
            except TypeError:
                pass
    for did, is_open in (d.get("doors") or {}).items():
        door = h.doors.get(did)
        if door is not None and door.is_open != is_open:
            (door.open if is_open else door.close)(silent=False)
    for iid, (enabled, used) in (d.get("ia") or {}).items():
        it = game.interactions.items.get(iid)
        if it is not None:
            it.enabled = bool(enabled)
            it.used = bool(used)


class WorldSync:
    """Envoie l'état modifié par les interactions du joueur local."""

    def __init__(self, game):
        self.game = game

    def around(self, fn):
        """Exécute fn (une interaction) et diffuse ce qu'elle a changé, tout de suite puis 1 s plus tard
        (animations et effets différés)."""
        g = self.game
        if not g.is_multiplayer or g.net is None:
            return fn()
        before = snapshot(g)
        res = fn()
        self._send(before)
        g.timers.after(1.2, self._send, before)
        return res

    def _send(self, before):
        g = self.game
        if g.net is None:
            return
        try:
            d = diff(before, snapshot(g))
        except Exception:
            return
        if d:
            g.net.relay("all", dict(type="world_sync", **d))
