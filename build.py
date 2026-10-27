"""Compilation de L'ADRESSE en application Windows native (LADRESSE.exe) avec PyInstaller.

Usage (sous Windows, Python 3.11+) :
    pip install -r requirements.txt
    python build.py

Le script :
  1. génère l'icône (maison sombre + point lumineux) et l'écran de démarrage
     (« L'ADRESSE » en blanc sur fond noir) avec Pillow ;
  2. lance PyInstaller en mode --onefile --windowed ;
  3. produit dist/LADRESSE.exe.

Seuls les polices, les textures photo (textures/) et les modèles 3D (models/), sous licence CC0, sont embarqués : les autres textures et
les sons sont générés au premier lancement (mis en cache dans le dossier temporaire).
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "build_assets")

# Modules du jeu (importés statiquement ou paresseusement)
GAME_MODULES = [
    "config", "game_data", "game_manager", "world_state", "timers", "player", "house_generator", "room_builder",
    "house_props", "house_events", "phone_system", "delivery_app", "bank_app", "assistance_system", "entity_ai",
    "entity_behaviors", "cinematic_engine", "intro_cinematic", "quest_system", "sound_engine", "texture_generator",
    "effects", "lighting_system", "shaders", "ui_manager", "ui_widgets", "settings_menu", "multiplayer_client",
    "multiplayer_manager", "interaction_system", "inventory", "jumpscare_system", "save_system", "particle_system",
    "typography", "ui_theme", "ui_cursor", "illustrations", "character_model", "neighborhood", "shop", "fidelite", "achievements",
    "crash_handler", "tts", "tutorial", "selftest", "autoplay", "models", "products", "car_builder", "fresh_aisle", "courier_story", "bianchi_house", "world_sync", "favoris_quest", "perf",
]


def make_assets():
    os.makedirs(ASSETS, exist_ok=True)
    sys.path.insert(0, HERE)
    from PIL import Image, ImageDraw, ImageFont
    from texture_generator import make_icon_ico
    icon = os.path.join(ASSETS, "icon.ico")
    make_icon_ico(icon)
    # écran de démarrage : noir avec le titre en blanc
    splash = os.path.join(ASSETS, "splash.png")
    img = Image.new("RGB", (640, 360), (0, 0, 0))
    d = ImageDraw.Draw(img)
    try:
        import ursina
        font = ImageFont.truetype(os.path.join(os.path.dirname(ursina.__file__), "fonts", "OpenSans-Regular.ttf"), 72)
    except Exception:
        font = ImageFont.load_default()
    d.text((320, 170), "L'ADRESSE", fill=(255, 255, 255), font=font, anchor="mm")
    d.text((320, 240), "chargement...", fill=(120, 120, 126), anchor="mm")
    img.save(splash)
    return icon, splash


def main():
    icon, splash = make_assets()
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "LADRESSE",
        "--icon", icon,
        "--distpath", os.path.join(HERE, "dist"),
        "--workpath", os.path.join(HERE, "build"),
        "--specpath", os.path.join(HERE, "build"),
        "--paths", HERE,
        "--collect-all", "ursina",
        "--collect-all", "panda3d",
        "--collect-all", "panda3d_gltf",
        "--collect-all", "panda3d_simplepbr",
        "--hidden-import", "numpy",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "screeninfo",
        "--exclude-module", "tkinter.test",
        "--exclude-module", "server",
        # serveur embarqué (bouton « Serveur local (LAN) » de l'écran Multijoueur)
        "--add-data", f"{os.path.join(HERE, 'server')}{os.pathsep}server",
        # polices libres embarquées (rendu identique sur tous les PC)
        "--add-data", f"{os.path.join(HERE, 'fonts')}{os.pathsep}fonts",
        # textures photo (Poly Haven, CC0) : voir fetch_textures.py
        "--add-data", f"{os.path.join(HERE, 'textures')}{os.pathsep}textures",
        # modèles 3D (Poly Haven, CC0) : voir fetch_models.py
        "--add-data", f"{os.path.join(HERE, 'models')}{os.pathsep}models",
        # voix enregistrées (voices/<id>.mp3 + voices.json)
        "--add-data", f"{os.path.join(HERE, 'voices')}{os.pathsep}voices",
    ]
    for m in GAME_MODULES:
        cmd += ["--hidden-import", m]
    # écran de démarrage (nécessite tkinter, inclus dans l'installeur Python officiel pour Windows)
    try:
        import tkinter  # noqa: F401
        cmd += ["--splash", splash]
    except ImportError:
        print("tkinter indisponible : pas d'écran de démarrage PyInstaller.")
    cmd.append(os.path.join(HERE, "main.py"))
    print(" ".join(cmd))
    code = subprocess.call(cmd, cwd=HERE)
    if code == 0:
        out = os.path.join(HERE, "dist", "LADRESSE.exe" if os.name == "nt" else "LADRESSE")
        print(f"\nTerminé : {out}")
    sys.exit(code)


if __name__ == "__main__":
    main()
