"""Auto-test sans fenêtre : `LADRESSE.exe --selftest` (ou `python main.py --selftest`).

Vérifie, dans l'exécutable compilé lui-même, que tout ce qui est embarqué fonctionne : modules, textures,
sons, polices, illustrations, données du jeu, carte fidélité, sauvegarde, serveur embarqué et moteur vocal.
Rapport : %APPDATA%/LADRESSE/selftest.txt ; code de sortie 0 si tout est bon, 1 sinon.
"""
import importlib
import json
import os
import socket
import sys
import tempfile
import threading
import time
import traceback

MODULES = [
    "config", "game_data", "world_state", "timers", "texture_generator", "sound_engine", "shaders", "lighting_system",
    "room_builder", "house_generator", "house_props", "house_events", "player", "interaction_system", "inventory",
    "phone_system", "delivery_app", "bank_app", "assistance_system", "entity_ai", "entity_behaviors", "effects",
    "particle_system", "jumpscare_system", "quest_system", "cinematic_engine", "intro_cinematic", "ui_manager",
    "settings_menu", "save_system", "multiplayer_client", "multiplayer_manager", "game_manager", "typography",
    "ui_theme", "ui_widgets", "illustrations", "character_model", "neighborhood", "shop", "fidelite", "achievements",
    "crash_handler", "tts", "tutorial",
]


class Report:
    def __init__(self):
        self.lines = []
        self.failed = 0
        self.warned = 0

    def ok(self, name, detail=""):
        self.lines.append(f"OK    {name}" + (f" — {detail}" if detail else ""))

    def warn(self, name, detail):
        self.warned += 1
        self.lines.append(f"AVERT {name} — {detail}")

    def fail(self, name, detail):
        self.failed += 1
        self.lines.append(f"ÉCHEC {name}\n{detail}")

    def step(self, name, fn):
        t = time.time()
        try:
            detail = fn()
            self.ok(name, (detail or "") + f" ({time.time() - t:.1f} s)")
        except Exception:
            self.fail(name, traceback.format_exc())


def _modules():
    for m in MODULES:
        importlib.import_module(m)
    return f"{len(MODULES)} modules"


def _textures():
    import numpy as np
    import texture_generator as tg
    n = 0
    for name, (fn, size) in tg._REGISTRY.items():
        img = fn(np.random.default_rng(7))
        assert img is not None and img.size[0] > 0, name
        n += 1
    return f"{n} textures"


def _sounds():
    import numpy as np
    import sound_engine as se
    n = 0
    for name, spec in se._SOUNDS.items():
        x = spec["fn"](np.random.default_rng(3))
        assert len(x) > 10 and np.all(np.isfinite(x)), name
        n += 1
    v = se.synth_voice("Bonjour, ceci est un test.", 120.0, 1.0, False, seed=1)
    assert len(v) > 1000
    return f"{n} sons + voix procédurale"


def _fonts():
    import typography as T
    paths = {k: T.find_font(k) for k in ("sans", "serif", "title", "hand", "mono")}
    T.render_title("L'ADRESSE", 120)
    T.handwriting_page("Test d'écriture manuscrite.\nDeuxième ligne é à ç.", (380, 490), px=24)
    T.typed_page("TICKET\nTOTAL 6,64 EUR", (350, 450), 18)
    T.newspaper_page(["NICE-MATIN : test", "Deuxième titre"], (350, 450))
    return ", ".join(f"{k}={os.path.basename(v) if v else 'défaut'}" for k, v in paths.items())


def _illustrations():
    import illustrations as ill
    for f in (ill.icon_flashlight, ill.icon_phone, ill.icon_crown, ill.avatar):
        f()
    for it in ("pile", "sel", "cle_tiroir", "inconnu"):
        ill.item_icon(it, 64)
    return "icônes et avatars"


def _data():
    import game_data as gd
    import config
    from neighborhood import NPC_VOICES
    from shop import CATALOG, KIOSK_LINES, RESTO_MENU
    from inventory import ITEM_DEFS
    from tutorial import Tutorial, key_label
    missing = [n for n in gd.NPC_LINES if n not in NPC_VOICES]
    assert not missing, f"PNJ sans voix : {missing}"
    for a in CATALOG:
        assert a.item is None or a.item in ITEM_DEFS, a.id
        assert a.card_price is None or a.card_price < a.price, a.id
    for st in Tutorial.STEPS:
        st["text"].format(**{a: key_label(a) for a in config.DEFAULT_KEYS})
    assert KIOSK_LINES and RESTO_MENU
    return f"{len(CATALOG)} articles, {len(gd.NPC_LINES)} PNJ, {len(Tutorial.STEPS)} étapes de didacticiel"


def _loyalty():
    from fidelite import Loyalty
    from shop import CATALOG_BY_ID
    d = tempfile.mkdtemp(prefix="ladresse_st_")
    lo = Loyalty(os.path.join(d, "f.json"))
    assert lo.active == "9531700001"
    n = lo.create("TEST")
    assert n == "9531700002", n
    lines = [(CATALOG_BY_ID["piles"], 2), (CATALOG_BY_ID["eau"], 1)]
    q = lo.quote(lines, n)
    lo.commit(lines, n, q)
    lo2 = Loyalty(os.path.join(d, "f.json"))
    assert lo2.card(n)["points"] == q["points"] and lo2.data["next_number"] == 9531700003
    return f"total {q['total']} €, {q['points']} points"


def _save():
    from world_state import WorldState
    st = WorldState()
    st.add_item("pile", 2)
    st.flags["purchases"] = [["Test", -1.5, "21/10 21:40"]]
    d = st.to_dict()
    s = json.dumps(d, ensure_ascii=False)
    st2 = WorldState()
    st2.from_dict(json.loads(s))
    assert st2.has("pile", 2)
    return f"{len(s)} octets"


def _server():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    sdir = os.path.join(base, "server")
    assert os.path.exists(os.path.join(sdir, "server.py")), "serveur non embarqué"
    if sdir not in sys.path:
        sys.path.append(sdir)
    os.environ.setdefault("LADRESSE_LOG", os.path.join(tempfile.gettempdir(), "ladresse_selftest_server.log"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("ladresse_server_st", os.path.join(sdir, "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = mod.RelayServer("127.0.0.1", port)
    srv.start(block=False)
    time.sleep(0.3)
    c = socket.create_connection(("127.0.0.1", port), timeout=5)
    c.sendall((json.dumps(dict(type="hello", name="Selftest", proto=mod.cfg.PROTOCOL_VERSION)) + "\n").encode())
    c.sendall((json.dumps(dict(type="create", name="Auto-test", max=4, game="selftest")) + "\n").encode())
    buf = b""
    t = time.time()
    while b'"type":"room"' not in buf and time.time() - t < 5:
        buf += c.recv(4096)
    c.close()
    srv.running = False
    assert b'"type":"room"' in buf, buf[:200]
    # les parties tournent sur le serveur : son module de partie doit être embarqué
    import coop_game  # noqa: F401
    return f"serveur local OK (port {port}), salon créé"


def _tts(rep):
    import tts as T
    eng = T.TTS()
    eng._probe()
    if not eng.available:
        rep.warn("voix réelles", eng.status + " — la voix procédurale sera utilisée")
        return
    eng._probe_done.set()
    path = os.path.join(eng.dir, "selftest_voice.wav")
    job = dict(id="selftest", text="Bonjour et bienvenue rue des Lilas.", gender="Female", rate=0, path=path)
    eng._generate([job])
    assert os.path.exists(path) and os.path.getsize(path) > 1000, "aucun fichier généré"
    x = T.read_wav_any(path, 22050)
    assert len(x) > 2000
    rep.ok("voix réelles", eng.status + f" — {len(x) / 22050:.1f} s générées")


def run():
    import config
    rep = Report()
    rep.lines.append(f"L'ADRESSE v{config.VERSION} — auto-test — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    rep.lines.append(f"Python {sys.version.split()[0]} — {sys.platform} — {'exe' if getattr(sys, 'frozen', False) else 'source'}")
    rep.step("modules", _modules)
    rep.step("textures", _textures)
    rep.step("sons", _sounds)
    rep.step("polices et pages", _fonts)
    rep.step("illustrations", _illustrations)
    rep.step("données du jeu", _data)
    rep.step("carte fidélité", _loyalty)
    rep.step("sauvegarde", _save)
    rep.step("serveur embarqué", _server)
    try:
        _tts(rep)
    except Exception:
        rep.fail("voix réelles", traceback.format_exc())
    rep.lines.append(f"\nRÉSULTAT : {'OK' if not rep.failed else 'ÉCHEC'} ({rep.failed} échec(s), {rep.warned} avertissement(s))")
    text = "\n".join(rep.lines)
    out = os.path.join(config.app_data_dir(), "selftest.txt")
    try:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    try:
        print(text)
    except Exception:
        pass
    return 0 if not rep.failed else 1
