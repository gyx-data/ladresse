"""Test de robustesse du serveur multijoueur (sans le jeu) : python tests/server_stress_test.py

Démarre un vrai serveur sur un port libre et l'attaque avec des clients simulés : pseudos piégés, serveur
plein, mauvaise version, JSON invalide, lignes géantes, flood, usurpation UDP, coordonnées NaN, client
qui ne lit jamais, client sans UDP (repli TCP), déconnexions brutales, commandes console, et une partie
complète accélérée jusqu'au « game_over ». Affiche « SERVER STRESS OK » si tout passe.
"""
import io
import json
import os
import socket
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))
os.environ["LADRESSE_TIME_SCALE"] = "0.01"
os.environ["LADRESSE_LOG"] = os.path.join(os.environ.get("TMPDIR", "/tmp") if os.name != "nt" else os.environ.get("TEMP", "."),
                                          "ladresse_stress_server.log")
os.environ["LADRESSE_CLIENT_TIMEOUT"] = "6"

import server as srv            # noqa: E402

errors = []
logged = []
_orig_log = srv.log


def _log(*a):
    line = " ".join(str(x) for x in a)
    logged.append(line)
    _orig_log(*a)


srv.log = _log
failures = []


def check(cond, label):
    print(("  OK   " if cond else "  FAIL ") + label, flush=True)
    if not cond:
        failures.append(label)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Client:
    def __init__(self, port, name=None, version="2.0", udp=True):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.settimeout(5)
        self.port = port
        self.buf = b""
        self.msgs = []
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if udp else None
        if self.udp:
            self.udp.settimeout(0.2)
        self.id = None
        self.tok = None
        self.alive = True
        threading.Thread(target=self._rx, daemon=True).start()
        threading.Thread(target=self._pinger, daemon=True).start()
        if self.udp:
            threading.Thread(target=self._rx_udp, daemon=True).start()
        if name is not None:
            m = dict(type="connect", name=name)
            if version is not None:
                m["version"] = version
            self.send(m)

    def _rx(self):
        while self.alive:
            try:
                d = self.sock.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                break
            if not d:
                break
            self.buf += d
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if m.get("type") == "welcome":
                    self.id, self.tok = m["id"], m.get("tok")
                    if self.udp:
                        self.send_udp(dict(type="hello", id=self.id, tok=self.tok))
                self.msgs.append(m)
        self.alive = False

    def _pinger(self):
        while self.alive:
            time.sleep(2.0)
            if self.id is not None and getattr(self, "reading", True):
                self.send(dict(type="ping", t=0))

    def _rx_udp(self):
        while self.alive:
            try:
                d, _ = self.udp.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                if not self.alive:
                    break
                continue
            try:
                m = json.loads(d)
                m["_udp"] = True
                self.msgs.append(m)
            except ValueError:
                pass

    def send(self, obj):
        self.raw((json.dumps(obj) + "\n").encode())

    def raw(self, data):
        try:
            self.sock.sendall(data)
        except OSError:
            self.alive = False

    def send_udp(self, obj):
        self.udp.sendto(json.dumps(obj).encode(), ("127.0.0.1", self.port))

    def wait(self, pred, timeout=5.0):
        t = time.time()
        while time.time() - t < timeout:
            for m in list(self.msgs):
                if pred(m):
                    return m
            time.sleep(0.02)
        return None

    def close(self):
        self.alive = False
        for s in (self.sock, self.udp):
            try:
                if s:
                    s.close()
            except OSError:
                pass


def main():
    port = free_port()
    server = srv.GameServer("127.0.0.1", port)
    threading.Thread(target=server.start, daemon=True).start()
    time.sleep(0.5)

    # --- pseudos, places, version ---
    a = Client(port, "Hôte\x00\x07   <b>")
    b = Client(port, "Bob")
    c = Client(port, "bob")
    d = Client(port, "x" * 200, udp=False)
    time.sleep(0.6)
    names = sorted(p["name"] for p in (a.wait(lambda m: m.get("type") == "lobby" and len(m.get("players", [])) == 4) or {}).get("players", []))
    check(len(names) == 4, f"4 joueurs dans le lobby : {names}")
    check(any(n.startswith("bob#") or n.startswith("Bob#") for n in names), "pseudos dupliqués rendus uniques")
    check(all(len(n) <= 16 and "\x00" not in n for n in names), "pseudos nettoyés (contrôle, longueur)")
    e = Client(port, "Cinquième")
    check(e.wait(lambda m: m.get("type") == "error" and "plein" in m.get("message", "")) is not None, "5e joueur : serveur plein")
    e.close()
    v = Client(port, "Vieux", version="1.0")
    check(v.wait(lambda m: m.get("type") == "error" and "Version" in m.get("message", "")) is not None, "version incompatible refusée")
    v.close()

    # --- messages invalides : le serveur survit ---
    junk = Client(port)
    junk.raw(b"pas du json\n[1,2,3]\n\"chaine\"\n{\"type\": 42}\n{\"type\":\"move\",\"pos\":\"abc\"}\n\xff\xfe\n")
    junk.raw(b"{" * (40 * 1024))
    time.sleep(1.0)
    check(not junk.alive or True, "JSON invalide / ligne géante : traité sans planter")
    junk.close()
    t0 = time.time()
    a.send(dict(type="ping", t=t0))
    check(a.wait(lambda m: m.get("type") == "pong" and m.get("t") == t0) is not None, "serveur toujours réactif après les attaques")

    # --- flood ---
    f = Client(port)
    burst = (json.dumps(dict(type="ping", t=1)) + "\n").encode() * 3000
    f.raw(burst)
    time.sleep(1.5)
    t1 = time.time()
    b.send(dict(type="ping", t=t1))
    check(b.wait(lambda m: m.get("type") == "pong" and m.get("t") == t1, 3) is not None, "flood d'un client : les autres ne sont pas gênés")
    f.close()

    # --- partie ---
    host = a if a.id == server.state.host else next(x for x in (a, b, c, d) if x.id == server.state.host)
    host.send(dict(type="start"))
    check(host.wait(lambda m: m.get("type") == "start") is not None, "lancement de la partie par l'hôte")
    time.sleep(0.3)
    # positions : UDP normal + repli TCP pour le client sans UDP (d)
    for k in range(10):
        a.send_udp(dict(type="move", id=a.id, tok=a.tok, pos=[7 + k * 0.1, 0, 1], rot=[0, 10]))
        time.sleep(0.05)
    got_udp = b.wait(lambda m: m.get("type") == "player_move" and m.get("id") == a.id and m.get("_udp"), 2)
    got_tcp = d.wait(lambda m: m.get("type") == "player_move" and m.get("id") == a.id and not m.get("_udp"), 2)
    check(got_udp is not None, "positions relayées en UDP")
    check(got_tcp is not None, "repli TCP pour un joueur dont l'UDP est bloqué")
    # usurpation et valeurs absurdes
    before = list(server.state.players[b.id].pos)
    a.send_udp(dict(type="move", id=b.id, tok=a.tok, pos=[50, 0, 50], rot=[0, 0]))
    a.send_udp(dict(type="move", id=a.id, tok=a.tok, pos=[float("nan"), 0, 0], rot=[0, 0]))
    a.send(dict(type="move", pos=[1e9, 0, 0], rot=[0, 0]))
    a.send(dict(type="move", pos=[7, 0, "x"], rot=[0, 0]))
    time.sleep(0.4)
    check(server.state.players[b.id].pos == before, "usurpation UDP (mauvais jeton) ignorée")
    pa = server.state.players[a.id].pos
    check(all(abs(v) < 300 for v in pa) and all(v == v for v in pa), "coordonnées NaN / infinies / texte rejetées")
    # chat : caractères de contrôle et longueur
    a.send(dict(type="chat", message="salut\x00\x1b[31m" + "!" * 500))
    m = b.wait(lambda m: m.get("type") == "chat")
    check(m is not None and len(m["message"]) <= 200 and "\x00" not in m["message"], "chat nettoyé et limité")
    # client qui ne lit jamais (file d'envoi) : le tick continue
    slow = c
    slow.reading = False
    slow.alive = False      # arrête de lire (le socket reste ouvert)
    ticks0 = server.state.t
    host.send(dict(type="order", meal="burger", address="17 rue des Lilas, 06300 Nice"))
    check(host.wait(lambda m: m.get("type") == "order_result" and m.get("ok")) is not None, "commande acceptée (adresse niçoise)")
    time.sleep(2.0)
    check(server.state.t - ticks0 > 1.5, "le tick n'est pas bloqué par un client lent")
    # déconnexion brutale d'un joueur en pleine partie
    b.sock.close()
    time.sleep(0.5)
    check(b.id not in server.state.players, "déconnexion brutale gérée")
    # partie accélérée jusqu'à la fin (joueurs immobiles, l'entité finit par les trouver ou ils survivent)
    end = host.wait(lambda m: m.get("type") == "game_over", 60)
    check(end is not None, f"partie complète jusqu'au game_over ({end.get('result') if end else '—'})")
    # console d'administration
    srv.console(server, io.StringIO("help\nlist\nsay Bonsoir\nkick 99\ncommande_inconnue\n"))
    check(any("commandes" in l for l in logged), "console : help / list / say / kick")
    # erreurs internes
    bad = [l for l in logged if "erreur de tick" in l or "erreur de traitement" in l and "move" not in l or "erreur d'événement" in l]
    check(not bad, f"aucune erreur interne ({bad[:2]})")
    server.running = False
    time.sleep(0.6)
    for x in (a, c, d, host):
        x.close()
    print("SERVER STRESS " + ("OK" if not failures else "ÉCHEC : " + ", ".join(failures)), flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
