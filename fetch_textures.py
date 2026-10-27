"""Télécharge les textures photo (Poly Haven, licence CC0) utilisées à la place des textures procédurales.

Usage : python fetch_textures.py
Les images (diffuse 1K) sont enregistrées dans textures/<nom_jeu>.jpg et leurs dimensions réelles
dans textures/textures.json (lu par texture_generator pour l'échelle de répétition).
Le jeu fonctionne sans ce dossier : il retombe alors sur les textures procédurales.
"""
import io
import json
import os
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures")

# nom de texture du jeu -> identifiant Poly Haven
SOURCES = {
    "parquet": "wood_floor_worn",
    "carrelage": "floor_tiles_06",
    "moquette": "dirty_carpet",
    "beton": "concrete_floor_damaged_01",
    "asphalte": "asphalt_02",
    "herbe": "leafy_grass",
    "planches": "old_planks_02",
    "bois_meuble": "wood_cabinet_worn_long",
    "platre": "grey_plaster",
    "plafond": "ceiling_interior",
    "crepi": "clay_plaster",
    "crepi_rose": "red_plaster_weathered",
    "tuiles": "clay_roof_tiles_02",
    "marbre": "marble_01",
    "tissu": "fabric_pattern_05",
    "papier_peint": "decrepit_wallpaper",
    "papier_chambre": "decrepit_wallpaper",
    "papier_couloir": "decrepit_wallpaper",
    "palmier_tronc": "palm_tree_bark",
    "volet": "worn_shutter",
    "etoffe": "cotton_jersey",
    "drap": "rough_linen",
    "rideau": "velour_velvet",
    "metal": "metal_plate_02",
    # mode « detail » : le dessin procédural est conservé (panneaux de porte, griffures...) et reçoit le grain de la photo
    "porte": "rough_pine_door",
    "porte_griffes": "rough_pine_door",          # + griffures ajoutées au chargement (texture_generator)
    "email": ("white_plaster_02", "detail"),
    "papier": ("white_plaster_02", "detail"),
}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "LADRESSE-texture-fetch"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = {}
    for name, src in SOURCES.items():
        ph_id, mode = src if isinstance(src, tuple) else (src, "replace")
        info = json.loads(_get(f"https://api.polyhaven.com/info/{ph_id}"))
        files = json.loads(_get(f"https://api.polyhaven.com/files/{ph_id}"))
        key = "Diffuse" if "Diffuse" in files else sorted(k for k in files if k.startswith("col_"))[0]   # variantes de couleur (tissus)
        url = files[key]["1k"]["jpg"]["url"]
        img = Image.open(io.BytesIO(_get(url))).convert("RGB")
        dims = list(info.get("dimensions") or [2000, 2000])    # millimètres
        # texture non carrée (ex. 1 x 0,5 m) : on la répète sur l'axe court (elle est raccordable) pour obtenir un carré
        w, h = img.size
        if w != h:
            reps = max(1, round(max(w, h) / min(w, h)))
            sq = Image.new("RGB", (w * reps, h) if w < h else (w, h * reps))
            for k in range(reps):
                sq.paste(img, (k * w, 0) if w < h else (0, k * h))
            img = sq
            dims = [dims[0] * reps, dims[1]] if w < h else [dims[0], dims[1] * reps]
        if img.size != (1024, 1024):
            img = img.resize((1024, 1024), Image.LANCZOS)
        img.save(os.path.join(OUT, name + ".jpg"), quality=90)
        meta[name] = dict(source=ph_id, url=f"https://polyhaven.com/a/{ph_id}", mode=mode,
                          size_m=[dims[0] / 1000.0, dims[1] / 1000.0])
        print(f"{name:16s} <- {ph_id}  ({dims[0] / 1000:.2f} x {dims[1] / 1000:.2f} m)")
    with open(os.path.join(OUT, "textures.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
