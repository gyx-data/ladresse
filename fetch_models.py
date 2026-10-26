"""Télécharge les modèles 3D (Poly Haven, licence CC0) et les convertit au format Panda3D (.bam).

Usage : python fetch_models.py            (tous les modèles)
        python fetch_models.py lemon croissant   (seulement ceux-là)
Résultat : models/<id>/<id>.bam + ses textures de couleur (1K). Seules les textures de couleur sont gardées :
le shader du jeu (shaders.py) n'utilise ni normal map ni rugosité, ces références sont retirées des matériaux.
Le jeu fonctionne sans ce dossier : chaque meuble retombe alors sur sa version en boîtes.
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "models")

MODELS = [
    # maison
    "sofa_03", "GreenChair_01", "painted_wooden_chair_01", "dining_table", "WoodenTable_01",
    "painted_wooden_nightstand", "gothic_coffee_table", "GothicBed_01", "vintage_cabinet_01",
    "cardboard_box_01", "wooden_crate_01", "Television_01", "wall_clock", "potted_plant_02",
    # quartier
    "street_lamp_01", "metal_trash_can", "concrete_road_barrier",
    "outdoor_table_chair_set_01", "CashRegister_01", "WetFloorSign_01", "utility_box_01", "covered_car", "Barrel_01",
    # supérette : fruits et légumes, boulangerie, conserves, cagettes
    "food_apple_01", "lemon", "food_lime_01", "food_avocado_01", "food_kiwi_01", "food_pears_asian_01",
    "food_pomegranate_01", "yellow_onion", "sweet_potato", "food_ginger_01", "bananas", "croissant", "hamburger_buns",
    "russian_food_cans_01", "plastic_crate_01", "wine_bottles_01",
]


def _get(url, tries=4):
    req = urllib.request.Request(url, headers={"User-Agent": "LADRESSE-model-fetch"})
    for k in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except OSError:
            if k == tries - 1:
                raise


def fetch(ph_id):
    folder = os.path.join(OUT, ph_id)
    tmp = os.path.join(folder, "_gltf")
    os.makedirs(tmp, exist_ok=True)
    files = json.loads(_get(f"https://api.polyhaven.com/files/{ph_id}"))
    g = files["gltf"]["1k"]["gltf"]
    doc = json.loads(_get(g["url"]))
    inc = g.get("include", {})
    # chaque matériau ne garde que sa texture de couleur (le shader du jeu n'utilise pas les autres cartes)
    color_images = set()
    for mat in doc.get("materials", []):
        for key in ("normalTexture", "occlusionTexture", "emissiveTexture"):
            mat.pop(key, None)
        pbr = mat.get("pbrMetallicRoughness", {})
        pbr.pop("metallicRoughnessTexture", None)
        if "baseColorTexture" in pbr:
            color_images.add(doc["textures"][pbr["baseColorTexture"]["index"]]["source"])
    for path, info in inc.items():
        wanted = path.endswith(".bin") or any(doc["images"][i].get("uri") == path for i in color_images)
        if wanted:
            dst = os.path.join(tmp, path)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(_get(info["url"]))
    # images devenues inutilisées : pointées vers une texture téléchargée (le glTF reste valide)
    kept = [doc["images"][i]["uri"] for i in sorted(color_images)]
    for i, img in enumerate(doc.get("images", [])):
        if i not in color_images and kept:
            img["uri"] = kept[0]
    src = os.path.join(tmp, ph_id + ".gltf")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    bam = os.path.join(folder, ph_id + ".bam")
    gltf2bam = shutil.which("gltf2bam") or os.path.join(os.path.dirname(sys.executable), "Scripts", "gltf2bam.exe")
    if not os.path.exists(gltf2bam):
        gltf2bam = os.path.join(os.path.dirname(sys.executable), "gltf2bam")
    subprocess.check_call([gltf2bam, "--no-srgb", "--textures", "copy", src, bam])
    shutil.rmtree(tmp)
    return bam


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "models.json")
    try:
        with open(path, encoding="utf-8") as f:
            credits = json.load(f)
    except (OSError, ValueError):
        credits = {}
    for ph_id in (sys.argv[1:] or MODELS):
        bam = fetch(ph_id)
        credits[ph_id] = f"https://polyhaven.com/a/{ph_id}"
        print(f"{ph_id:28s} -> {os.path.relpath(bam, HERE)}")
    with open(os.path.join(OUT, "models.json"), "w", encoding="utf-8") as f:
        json.dump(credits, f, indent=2)


if __name__ == "__main__":
    main()
