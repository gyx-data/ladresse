"""Test de robustesse du serveur multijoueur et des parties qu'il fait tourner (sans Ursina).

    python tests/server_stress_test.py      -> « SERVER STRESS OK » ou la liste des échecs
"""
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="ladresse_stress_")
os.environ["LADRESSE_LOG"] = os.path.join(os.environ["APPDATA"], "server.log")
os.environ["LADRESSE_MAX_ROOMS_PER_IP"] = "50"
os.environ["LADRESSE_MAX_PER_IP"] = "128"

import server as srv            # noqa: E402
import config                   # noqa: E402

failures = []


def check(cond, name):
    print(("  OK   " if cond else "  FAIL ") + name, flush=True)
    if not cond:
        failures.append(name)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Raw:
    """Client brut (TCP + UDP) pour piloter le relais."""

    def __init__(self, port, name=None, proto="4.0"):
        self.port = port
        self.s = socket.create_connection(("127.0.0.1", port), timeout=3)
        self.s.settimeout(0.05)
        self.u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.u.bind(("127.0.0.1", 0))
        self.u.settimeout(0.05)
        self.buf = b""
        self.msgs = []
        self.udp_msgs = []
        self.id = self.tok = None
        if name is not None:
            self.send(type="hello", name=name, proto=proto)
            m = self.wait("hello_ok")
            if m:
                self.id, self.tok = m["id"], m["tok"]

    def send(self, **obj):
        self.s.sendall((json.dumps(obj) + "\n").encode())

    def raw(self, data):
        self.s.sendall(data)

    def pump(self, t=0.15):
        end = time.time() + t
        while time.time() < end:
            try:
                d = self.s.recv(65536)
                if not d:
                    break
                self.buf += d
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    self.msgs.append(json.loads(line))
            except socket.timeout:
                pass
            except OSError:
                break
            try:
                d, _ = self.u.recvfrom(4096)
                self.udp_msgs.append(json.loads(d))
            except (socket.timeout, OSError):
                pass

    def wait(self, typ, t=2.0, pred=None):
        end = time.time() + t
        while time.time() < end:
            for m in self.msgs:
                if m.get("type") == typ and (pred is None or pred(m)):
                    self.msgs.remove(m)
                    return m
            self.pump(0.05)
        return None

    def udp(self, **obj):
        self.u.sendto(json.dumps(obj).encode(), ("127.0.0.1", self.port))

    def close(self):
        for x in (self.s, self.u):
            try:
                x.close()
            except OSError:
                pass


def relay_tests(port, server):
    print("== relais ==")
    bad = Raw(port, "Vieux", proto="2.0")
    check(bad.wait("error", pred=lambda m: m.get("code") == "proto") is not None, "ancien client refusé (protocole)")
    bad.close()
    anon = Raw(port)
    anon.send(type="list")
    check(anon.wait("error", pred=lambda m: m.get("code") == "hello") is not None, "list sans hello refusé")
    anon.close()

    a = Raw(port, "Alice")
    check(a.id is not None and a.tok, "hello -> identifiant + jeton UDP")
    a.send(type="create", name="Maison\x00 hantée", max=99, game="1.0")
    r = a.wait("room")
    check(r is not None and r["host"] == a.id and r["room"]["max"] == server_cfg().MAX_ROOM_PLAYERS, "création + limite bornée")
    check(r is not None and "\x00" not in r["room"]["name"], "nom de salon nettoyé")
    code = r["room"]["id"] if r else None

    b = Raw(port, "Alice")
    b.send(type="list")
    lst = b.wait("rooms")
    check(lst is not None and any(x["id"] == code and x["players"] == 1 for x in lst["rooms"]), "la partie apparaît dans la liste")
    b.send(type="join", room=code, game="0.9")
    check(b.wait("error", pred=lambda m: m.get("code") == "version") is not None, "version du jeu différente refusée")
    b.send(type="join", room="ZZZZZ", game="1.0")
    check(b.wait("error", pred=lambda m: m.get("code") == "gone") is not None, "salon inexistant")
    b.send(type="join", room=code, game="1.0")
    rb = b.wait("room")
    check(rb is not None and len(rb["players"]) == 2, "rejoindre une partie")
    check(rb is not None and [p["name"] for p in rb["players"]] == ["Alice", "Alice#2"], "pseudo en double renommé")
    check(a.wait("room", pred=lambda m: len(m["players"]) == 2) is not None, "l'hôte voit le nouveau joueur")

    # relais TCP
    b.send(type="to", to="host", d={"type": "chat", "message": "allo"})
    m = a.wait("from", pred=lambda m: m["d"].get("type") == "chat")
    check(m is not None and m["from"] == 0 and m["d"]["name"] == "Alice#2", "action d'un joueur traitée par la partie du serveur")
    a.send(type="to", to="all", d={"type": "game_event", "event": "x"})
    m = b.wait("from", pred=lambda m: m["d"].get("event") == "x")
    check(m is not None and m["from"] == a.id, "relais joueur -> tous")
    b.send(type="to", to="all", d="pas un objet")
    b.pump(0.2)
    check(not [x for x in a.msgs if x.get("type") == "from"], "charge utile invalide ignorée")

    # UDP
    for c in (a, b):
        c.udp(i=c.id, k=c.tok, h=1)
    a.pump(0.3)
    b.pump(0.3)
    check(any(x.get("ack") for x in a.udp_msgs) and any(x.get("ack") for x in b.udp_msgs), "UDP : accusé de réception")
    b.udp(i=b.id, k=b.tok, to="all", d={"type": "move", "pos": [1, 0, 2], "s": 1})
    a.pump(0.3)
    check(any(x.get("f") == b.id and x["d"].get("type") == "move" for x in a.udp_msgs), "UDP : position relayée")
    a.udp_msgs.clear()
    b.udp(i=b.id, k="faux", to="all", d={"type": "move", "pos": [9, 9, 9]})
    b.udp(i=a.id, k=b.tok, to="all", d={"type": "move", "pos": [9, 9, 9]})
    a.pump(0.3)
    check(not any(x.get("d", {}).get("pos") == [9, 9, 9] for x in a.udp_msgs), "UDP : usurpation ignorée")

    # joueur sans UDP : repli TCP
    c = Raw(port, "Carl")
    c.send(type="join", room=code, game="1.0")
    c.wait("room")
    b.udp(i=b.id, k=b.tok, to="all", d={"type": "move", "pos": [3, 0, 3], "s": 2})
    m = c.wait("from", pred=lambda m: m["d"].get("type") == "move")
    check(m is not None and m["from"] == b.id, "UDP bloqué : repli TCP")

    # salon privé, complet
    h = Raw(port, "Hugo")
    h.send(type="create", name="Privée", max=2, password="sel", game="1.0")
    code2 = h.wait("room")["room"]["id"]
    d = Raw(port, "Dana")
    d.send(type="join", room=code2, password="poivre", game="1.0")
    check(d.wait("error", pred=lambda m: m.get("code") == "password") is not None, "mauvais mot de passe refusé")
    d.send(type="join", room=code2, password="sel", game="1.0")
    check(d.wait("room") is not None, "bon mot de passe accepté")
    e = Raw(port, "Eve")
    e.send(type="join", room=code2, password="sel", game="1.0")
    check(e.wait("error", pred=lambda m: m.get("code") == "full") is not None, "partie complète refusée")
    e.send(type="list")
    lst = e.wait("rooms")
    info = [x for x in lst["rooms"] if x["id"] == code2][0]
    check(info["locked"] and info["players"] == 2 and "password" not in info, "liste : privée, sans fuite du mot de passe")

    # exclusion par l'hôte
    h.send(type="kick", id=d.id)
    check(d.wait("room_closed") is not None, "exclusion par l'hôte")
    d.send(type="kick", id=h.id)
    h.pump(0.2)
    check(server.rooms.get(code2) is not None and h.id in server.rooms[code2].members, "un non-hôte ne peut pas exclure")

    # partie lancée : plus de nouveaux joueurs ; départ de l'hôte -> salon fermé
    b.send(type="to", to="host", d={"type": "start"})
    b.pump(0.3)
    check(server.rooms[code].sim.phase == "lobby", "seul le créateur peut lancer")
    a.send(type="to", to="host", d={"type": "start"})
    check(a.wait("room", pred=lambda m: m["room"]["phase"] == "playing") is not None, "lancement par le créateur")
    e.send(type="join", room=code, game="1.0")
    check(e.wait("error", pred=lambda m: m.get("code") == "started") is not None, "partie en cours : rejoindre refusé")
    a.close()
    m = b.wait("room", t=3, pred=lambda m: a.id not in [p["id"] for p in m["players"]])
    check(m is not None and m["host"] == b.id, "départ du créateur en jeu : un autre joueur prend la main")
    time.sleep(0.2)
    check(code in server.rooms and server.rooms[code].sim.phase != "lobby", "la partie continue sur le serveur")
    b.send(type="leave")
    c.send(type="leave")
    b.wait("left")
    c.wait("left")

    # départ de l'hôte dans le salon d'attente : un autre joueur devient hôte
    b.pump(0.2)
    c.pump(0.2)
    b.msgs.clear()
    c.msgs.clear()
    b.send(type="create", name="Relève", max=4, game="1.0")
    code3 = b.wait("room")["room"]["id"]
    c.send(type="join", room=code3, game="1.0")
    c.wait("room")
    b.close()
    m = c.wait("room", t=3, pred=lambda m: m["host"] == c.id)
    check(m is not None, "départ de l'hôte au salon : passation")

    # robustesse
    f = Raw(port, "Flood")
    f.raw(b"{pas du json}\n" + b"[1,2]\n" + b'{"type":"inconnu"}\n')
    f.send(type="ping", t=1)
    check(f.wait("pong") is not None, "messages malformés ignorés, connexion conservée")
    f.raw(b"x" * (server_cfg().MAX_LINE + 10))
    time.sleep(1.5)
    f.pump(0.2)
    try:
        f.s.sendall(b'{"type":"ping"}\n')
        f.pump(0.5)
        alive = bool(f.wait("pong", t=0.5))
    except OSError:
        alive = False
    check(not alive, "ligne géante : déconnexion")
    g = Raw(port, "Spam")
    try:
        for _ in range(3000):
            g.raw(b'{"type":"ping","t":1}\n')
    except OSError:
        pass
    time.sleep(1.0)
    check(len(server.conns) < 12, "flood limité")
    for x in (c, d, e, h, g):
        x.close()

    buf = io.StringIO("help\nlist\nrooms\nstats\nsay bonjour\nclose ZZZZZ\nkick 99999\nbizarre\n")
    console_out = []
    orig = srv.log
    srv.log = lambda *a: console_out.append(" ".join(str(x) for x in a))
    try:
        srv.console(server, buf)
    finally:
        srv.log = orig
    check(any("commandes" in x for x in console_out) and any("connexions=" in x for x in console_out), "console : help / list / stats")


def server_cfg():
    return srv.cfg


def game_tests(port, server):
    """Deux vrais clients du jeu : la partie tourne sur le serveur."""
    print("== partie sur le serveur ==")
    from multiplayer_client import NetClient
    import coop_rules
    coop_rules.FIRST_CANCEL_DELAY = 0.2
    coop_rules.TIME_SCALE = 1.0
    owner, peer = NetClient(), NetClient()
    owner.connect("127.0.0.1", port, "Créateur")
    peer.connect("127.0.0.1", port, "Invité")
    got = {"o": [], "p": []}

    def drain(t=0.4):
        end = time.time() + t
        while time.time() < end:
            got["o"] += owner.poll()
            got["p"] += peer.poll()
            time.sleep(0.02)

    def find(who, typ, pred=None, t=2.0):
        end = time.time() + t
        while time.time() < end:
            for m in got[who]:
                if m.get("type") == typ and (pred is None or pred(m)):
                    got[who].remove(m)
                    return m
            drain(0.05)
        return None

    drain(0.3)
    owner.create_room("Test serveur", 4)
    room = find("o", "room")
    check(room is not None and owner.is_host, "créer une partie -> on en est le créateur")
    code = room["room"]["id"]
    sim = server.rooms[code].sim
    peer.join_room(code)
    check(find("p", "room") is not None and not peer.is_host, "second joueur dans le salon")
    drain(0.3)
    check(len(sim.state.players) == 2, "la partie du serveur connaît les deux joueurs")
    owner.send_start()
    so, sp = find("o", "start"), find("p", "start")
    check(so is not None and sp is not None and len(sp["players"]) == 2 and sp["_from"] == 0, "lancement envoyé par le serveur aux deux joueurs")
    for _ in range(5):
        peer.send_move((7.2, 0.0, 1.5), (0, 45))
        time.sleep(0.06)
    mv = find("o", "move", pred=lambda m: m.get("_from") == peer.id)
    check(mv is not None and mv["pos"][2] == 1.5, "position reçue directement par l'autre joueur")
    check(abs(sim.state.players[peer.id].pos[2] - 1.5) < 1e-6, "le serveur suit la position pour l'IA")
    peer.send_order("pizza", "17 rue des Lilas")
    oo, op = find("o", "order_result"), find("p", "order_result")
    check(oo is not None and op is not None and op["entity"] == "rampant", "commande traitée par le serveur, résultat diffusé")
    check(find("p", "game_event", pred=lambda m: m.get("event") == "order_cancelled", t=3) is not None, "évènement programmé diffusé")
    peer.send_chat("on est où ?")
    ch = find("o", "chat")
    check(ch is not None and ch["name"] == "Invité", "chat diffusé par le serveur")
    peer.relay("all", {"type": "game_over", "result": "win"})
    drain(0.4)
    check(not [m for m in got["o"] if m.get("type") == "game_over"], "faux messages de partie d'un joueur ignorés")
    owner.close()
    m = find("p", "room", pred=lambda m: m["host"] == peer.id, t=3)
    check(m is not None and not [x for x in got["p"] if x.get("type") == "room_closed"], "le créateur part : la partie continue")
    peer.send_chat("toujours là")
    check(find("p", "chat", pred=lambda m: m.get("message") == "toujours là") is not None, "la partie répond toujours")
    peer.send_death("test")
    d = find("p", "player_death")
    check(d is not None and d["id"] == peer.id, "mort d'un joueur diffusée")
    check(not sim.errors, f"aucune erreur dans la partie {sim.errors[:2]}")
    peer.close()
    time.sleep(0.4)
    check(code not in server.rooms, "dernier joueur parti : salon supprimé")


def load_test(port, server, rooms=40):
    """Beaucoup de salons en même temps sur la même boucle de jeu."""
    print("== charge ==")
    clients = []
    for i in range(rooms):
        c = Raw(port, f"P{i}")
        c.send(type="create", name=f"Charge {i}", max=2, game="1.0")
        clients.append(c)
    time.sleep(0.5)
    for c in clients:
        c.send(type="to", to="host", d={"type": "start"})
    time.sleep(2.0)
    playing = sum(1 for r in server.rooms.values() if r.sim.phase != "lobby")
    check(playing >= rooms, f"{playing} parties lancées en parallèle")
    from coop_state import EntityState
    with server.lock:
        for r in server.rooms.values():          # livreur actif partout : cas le plus lourd
            r.sim.state.entity = EntityState("rampant")
            r.sim.state.entity.active = True
            r.sim.state.phase = "survival"
            r.sim.state.t_release = r.sim.state.t
    server.stats["tick_ms"] = 0.0
    time.sleep(2.0)
    check(server.stats["tick_ms"] < 5.0, f"boucle de jeu rapide, livreur actif partout : {server.stats['tick_ms']:.2f} ms par tick pour {len(server.rooms)} salons")
    for c in clients:
        c.close()


def main():
    port = free_port()
    server = srv.RelayServer("127.0.0.1", port)
    server.start(block=False)
    time.sleep(0.3)
    try:
        relay_tests(port, server)
        game_tests(port, server)
        load_test(port, server)
    except Exception:
        import traceback
        traceback.print_exc()
        failures.append("exception")
    server.running = False
    print("SERVER STRESS OK" if not failures else f"SERVER STRESS : {len(failures)} échec(s) : {failures}", flush=True)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
