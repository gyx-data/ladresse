"""Journal des erreurs : %APPDATA%/LADRESSE/crash.log (rotation à 512 Ko).

Les exceptions non rattrapées sont écrites avec la version du jeu, l'OS et la pile d'appels ; les
erreurs répétées dans la boucle de jeu sont dédoublonnées pour ne pas saturer le disque.
"""
import os
import platform
import sys
import time
import traceback

import config

MAX_SIZE = 512 * 1024
_seen = {}


def path():
    return os.path.join(config.app_data_dir(), "crash.log")


def _write(text):
    p = path()
    try:
        if os.path.exists(p) and os.path.getsize(p) > MAX_SIZE:
            os.replace(p, p + ".old")
        with open(p, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def _header(kind):
    return (f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')}  {kind}  v{config.VERSION}  "
            f"{platform.system()} {platform.release()}  Python {platform.python_version()} =====\n")


def log_exception(where=""):
    tb = traceback.format_exc()
    key = tb.strip().splitlines()[-1] + where.split(" ")[0]
    n = _seen.get(key, 0) + 1
    _seen[key] = n
    if n in (1, 10, 100) or n % 1000 == 0:
        _write(_header(f"erreur ({where}) x{n}") + tb)
        try:
            sys.__stderr__.write(tb)
        except Exception:
            pass


def _hook(exc_type, exc, tb):
    _write(_header("CRASH") + "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


def install():
    sys.excepthook = _hook
