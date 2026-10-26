"""Modèles 3D photoréalistes (Poly Haven, CC0) : voir fetch_models.py.

`place()` instancie un modèle mis à l'échelle dans l'emprise prévue pour le meuble (mêmes dimensions que la
version en boîtes, donc mêmes colliders). Convention commune aux meubles de room_builder : la façade du meuble
(côté assise, pied de lit...) regarde +z local, puis le tout est tourné de `rot` degrés autour de y.
Si le modèle est absent, `place()` renvoie None et l'appelant construit la version en boîtes.
"""
import os

from panda3d.core import ColorAttrib, Filename, Mat4, MaterialAttrib, TextureAttrib
from ursina import Entity

import config
from shaders import horror_shader

_DIR = config.resource_path("models")
_templates = {}
_placed = []          # (entité, nom) des modèles posés (audits de placement)

# Modèles convertis par gltf2bam en z-up main droite ; Ursina travaille en y-up main gauche :
# z -> y, y -> -z, et x inversé pour changer de main (sinon textes et cadrans apparaissent en miroir).
_TO_URSINA = Mat4(-1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1)
# Après conversion, la façade regarde +z (convention des meubles) sauf exceptions : quart de tour correctif (degrés).
_YAW_FIX = {"painted_wooden_chair_01": 90.0}


def available(name):
    return os.path.exists(os.path.join(_DIR, name, name + ".bam"))


def _template(name):
    if name not in _templates:
        from ursina import application
        np = application.base.loader.loadModel(Filename.fromOsSpecific(os.path.join(_DIR, name, name + ".bam")))
        # géométries sans texture : le shader du monde lit la couleur de sommet -> couleur de base du matériau
        for gnp in np.findAllMatches("**/+GeomNode"):
            node = gnp.node()
            for i in range(node.getNumGeoms()):
                state = node.getGeomState(i)
                if state.hasAttrib(TextureAttrib) and state.getAttrib(TextureAttrib).getNumOnStages():
                    continue
                if state.hasAttrib(MaterialAttrib):
                    mat = state.getAttrib(MaterialAttrib).getMaterial()
                    if mat is not None:
                        c = mat.getBaseColor() if mat.hasBaseColor() else mat.getDiffuse()
                        node.setGeomState(i, state.setAttrib(ColorAttrib.makeFlat(c)))
        np.clearModelNodes()
        np.flattenStrong()
        _templates[name] = np
    return _templates[name]


def place(name, parent, cx, cz, y0, rot=0.0, size=None, stretch=False, pitch=0.0, free_yaw=False):
    """Pose `name` au sol en (cx, y0, cz), tourné de `rot` degrés.

    size = (largeur x, hauteur y, profondeur z) de l'emprise locale : le modèle y est inscrit en gardant
    ses proportions (ou étiré sur chaque axe si `stretch`). Un axe à None n'est pas contraint.
    free_yaw : objet sans façade (table, carton) : tourné d'un quart de tour si son côté long ne suit pas l'emprise.
    """
    if not available(name):
        return None
    root = Entity(parent=parent, position=(cx, y0, cz), rotation_y=rot, shader=horror_shader)
    root.set_shader_input("emit", 0.0)
    scaler = Entity(parent=root)                                   # échelle dans le repère de l'emprise
    turner = Entity(parent=scaler, rotation=(pitch, _YAW_FIX.get(name, 0.0), 0))
    inner = _template(name).copyTo(turner)
    inner.setMat(_TO_URSINA)

    def dims():
        lo, hi = inner.getTightBounds(scaler)
        return lo, hi, (hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)

    lo, hi, d = dims()
    if free_yaw and size is not None and size[0] and size[2] and (d[0] - d[2]) * (size[0] - size[2]) < 0:
        turner.rotation_y += 90.0
        lo, hi, d = dims()
    if size is not None:
        ratios = [want / have for want, have in zip(size, d) if want is not None and have > 1e-6]
        if ratios:
            k = min(ratios)
            if stretch:
                scaler.scale = tuple((want / have) if (want is not None and have > 1e-6) else k for want, have in zip(size, d))
            else:
                scaler.scale = (k, k, k)
    lo, hi = inner.getTightBounds(root)
    # pose : centré en x/z, posé sur le sol (repère Ursina : y vers le haut)
    scaler.position = (-(lo.x + hi.x) / 2, -lo.y, -(lo.z + hi.z) / 2)
    _placed.append((root, name))
    return root
