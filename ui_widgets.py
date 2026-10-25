"""Boîte à outils d'interface (Ursina UI) : textes, panneaux, boutons stylés animés, curseurs, interrupteurs.

Les boutons utilisent les textures arrondies de ``ui_theme`` (états normal / survol / appuyé) et jouent
des sons d'interface. Les classes personnalisées (`StyledButton`, `UISlider`, `UIToggle`) ne sont pas
« ignorées » par l'optimisation de `main.py`, donc elles reçoivent bien les entrées souris.
"""
import math

from ursina import Entity, Text, Button, Mesh, color, camera, Vec3, curve, mouse, destroy

import config
import ui_theme as theme

SOUND_ON = True


def text_scale():
    return config.TEXT_SCALE.get(config.settings["taille_texte"], 1.0)


def rgb(r, g, b, a=255):
    return color.rgba32(r, g, b, a)


# ---------------------------------------------------------------------------
# Textes
# ---------------------------------------------------------------------------
def text_box(t, ref=None):
    """Boîte englobante (x0, y0, x1, y1) d'un texte dans le repère de `ref` (parent par défaut), ou None."""
    try:
        if not t.text or not str(t.text).strip():
            return None
        b = t.getTightBounds(ref if ref is not None else t.parent)
        if not b:
            return None
        lo, hi = b
        return (lo[0], lo[1], hi[0], hi[1])
    except Exception:
        return None


def fit_text(t, max_w=None, max_h=None, ref=None, min_ratio=0.4):
    """Réduit l'échelle d'un texte jusqu'à ce qu'il tienne dans max_w x max_h (unités du repère `ref`)."""
    if t is None or (max_w is None and max_h is None):
        return t
    base = getattr(t, "_fit_base", None)
    if base is None:
        base = t._fit_base = Vec3(t.scale_x, t.scale_y, t.scale_z)
    t.scale = base
    for _ in range(3):
        bx = text_box(t, ref)
        if bx is None:
            return t
        w, h = bx[2] - bx[0], bx[3] - bx[1]
        k = 1.0
        if max_w is not None and w > max_w:
            k = min(k, max_w / max(w, 1e-6))
        if max_h is not None and h > max_h:
            k = min(k, max_h / max(h, 1e-6))
        if k >= 0.999:
            return t
        k = max(min_ratio * base[0] / max(t.scale_x, 1e-6), k * 0.98)
        t.scale = Vec3(t.scale_x * k, t.scale_y * k, t.scale_z)
        if t.scale_x <= base[0] * min_ratio + 1e-6:
            return t
    return t


def label(parent, text, x=0.0, y=0.0, size=1.0, col=color.white, origin=(0, 0), wrap=None, z=-0.01,
          scale_text=True, bold=False, align=None, shadow=False, max_w=None, max_h=None):
    """Texte d'interface. max_w / max_h (unités du parent) : le texte est réduit pour ne jamais déborder."""
    kw = {}
    if wrap:
        kw["wordwrap"] = wrap
    s = size * (text_scale() if scale_text else 1.0)
    if shadow:
        Text(parent=parent, text=text if text else " ", position=(x + 0.0016, y - 0.0022, z + 0.001), origin=origin,
             scale=s, color=color.rgba32(0, 0, 0, 170), **kw)
    t = Text(parent=parent, text=text if text else " ", position=(x, y, z), origin=origin, scale=s, color=col, **kw)
    if align == "center":
        t.origin = (0, 0)
    if max_w is not None or max_h is not None:
        t._fit = (max_w, max_h)
        fit_text(t, max_w, max_h)
    return t


def set_label(t, text):
    """Change le texte d'un label en conservant son ajustement automatique (max_w / max_h)."""
    t.text = text if text else " "
    fit = getattr(t, "_fit", None)
    if fit:
        fit_text(t, fit[0], fit[1])
    return t


# ---------------------------------------------------------------------------
# Formes
# ---------------------------------------------------------------------------
def rect(parent, x, y, w, h, col=color.black, z=0.0, texture=None, rotation=0.0, radius=None):
    """Rectangle plein. radius (0..0.5, relatif au plus petit côté) => coins arrondis."""
    if radius:
        return rounded_solid(parent, x, y, w, h, col, radius, z)
    e = Entity(parent=parent, model="quad", position=(x, y, z), scale=(w, h), color=col, rotation_z=rotation)
    if texture is not None:
        e.texture = texture
    e.ui_box = (w, h)
    return e


def rounded_solid(parent, x, y, w, h, col, radius=0.3, z=0.0):
    """Rectangle arrondi uni (couleur propre, anti-crénelé)."""
    from PIL import Image, ImageDraw
    c = tuple(int(v * 255) for v in col) if hasattr(col, "r") else tuple(col)
    key = ("solid", theme.px(w), theme.px(h), c, radius)
    if key not in theme._cache:
        W, H = theme.px(w), theme.px(h)
        S = 3
        img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([0, 0, W * S - 1, H * S - 1], radius=int(radius * min(W, H) * S),
                                              fill=c if len(c) == 4 else c + (255,))
        theme._cache[key] = theme._tex(img.resize((W, H), Image.LANCZOS))
    e = Entity(parent=parent, model="quad", texture=theme._cache[key], position=(x, y, z), scale=(w, h))
    e.ui_box = (w, h)
    return e


def panel(parent, x, y, w, h, style="panel", z=0.0, radius=None, shadow=True):
    e = theme.make_panel(parent, x, y, w, h, style, z, radius, shadow)
    e.ui_box = (w, h)
    return e


def image(parent, pil_image, x, y, w, h, z=0.0):
    """Affiche une image PIL dans un quad."""
    return Entity(parent=parent, model="quad", texture=theme._tex(pil_image), position=(x, y, z), scale=(w, h))


def star(parent, x, y, size, col=color.rgb32(255, 200, 40), z=-0.02):
    """Étoile à 5 branches (mesh)."""
    verts = [Vec3(0, 0, 0)]
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        r = 0.5 if i % 2 == 0 else 0.22
        verts.append(Vec3(math.cos(a) * r, math.sin(a) * r, 0))
    tris = []
    for i in range(10):
        tris.extend([0, 1 + i, 1 + (i + 1) % 10])
    m = Mesh(vertices=verts, triangles=tris, mode="triangle")
    return Entity(parent=parent, model=m, position=(x, y, z), scale=size, color=col)


def clear(entity):
    for c in list(entity.children):
        c.disable()
        c.parent = None
        try:
            destroy(c)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Boutons
# ---------------------------------------------------------------------------
def infer_style(col):
    """Choisit un style de thème d'après une couleur historique (r, g, b, a de 0..1)."""
    if col is None:
        return "dark"
    r, g, b = col[0] * 255, col[1] * 255, col[2] * 255
    if r > 190 and 70 < g < 190 and b < 90:
        return "primary"
    if g > r + 40 and g > b + 15:
        return "success"
    if r > g + 55 and r > b + 55:
        return "danger" if r > 120 else "dark"
    if b > r + 55 and b > g + 20:
        return "blue"
    if col[3] < 0.05:
        return "ghost"
    return "dark"


class StyledButton(Button):
    """Bouton à textures arrondies (normal / survol / appuyé), son de survol et de clic."""

    def __init__(self, parent, text, x, y, w, h, on_click=None, style="dark", text_col=None, size=0.8, z=-0.02,
                 radius=None, shadow=True, glow=None, sound=True):
        self._w, self._h = w, h
        self._style = style
        self._radius = radius
        self._shadow = shadow
        self._glow = glow
        self._sound = sound
        self._state = "normal"
        tex, pad = theme.get_texture(theme.px(w), theme.px(h), style, "normal", radius, shadow, glow)
        self._pad = pad
        ext_w, ext_h = w + 2 * pad / theme.PX, h + 2 * pad / theme.PX
        kw = {}
        st = theme.STYLES[style]
        if text:
            tc = text_col if text_col is not None else color.rgb32(*st["text"])
            kw = dict(text=text, text_color=tc, text_size=size * text_scale())
        super().__init__(parent=parent, model="quad", position=(x, y, z), scale=(ext_w, ext_h), color=color.white,
                         highlight_color=color.white, pressed_color=color.white, highlight_scale=1.0, pressed_scale=1.0, **kw)
        self.texture = tex
        if on_click:
            self.on_click = on_click
        self.inner = (w, h)
        # zone cliquable invisible (sans texte, style transparent) : ce n'est pas un cadre visuel
        self.ui_box = (w, h) if (text or style != "ghost") else None
        self._fit_label()

    def _fit_label(self):
        """Le texte du bouton tient toujours dans le bouton (marges comprises)."""
        t = getattr(self, "text_entity", None)
        if t is None or self.parent is None:
            return
        fit_text(t, self._w - min(0.03, self._w * 0.12), self._h * 0.78, ref=self.parent)

    def _set_state(self, state):
        if state == self._state:
            return
        self._state = state
        tex, _ = theme.get_texture(theme.px(self._w), theme.px(self._h), self._style, state, self._radius, self._shadow, self._glow)
        self.texture = tex

    def on_mouse_enter(self):
        self._set_state("hover")
        if self._sound and SOUND_ON:
            theme.play_ui_sound("ui_hover")

    def on_mouse_exit(self):
        self._set_state("normal")

    def input(self, key):
        if key == "left mouse down" and self.hovered:
            self._set_state("pressed")
            if self._sound and SOUND_ON:
                theme.play_ui_sound("ui_click")
        elif key == "left mouse up" and self._state == "pressed":
            self._set_state("hover" if self.hovered else "normal")
        super().input(key)

    def set_style(self, style):
        self._style = style
        self._state = ""
        self._set_state("normal")

    def set_text(self, text):
        if self.text_entity is not None:
            self.text_entity.text = text
            self.text_entity._fit_base = None
            self._fit_label()


def button(parent, text, x, y, w, h, on_click=None, col=None, text_col=None, size=0.8, z=-0.02,
           highlight=None, press=None, style=None, radius=None, shadow=True, glow=None):
    """Bouton stylé. `col` (ancienne API) sert à déduire le style ; `style` le force."""
    st = style or infer_style(col)
    return StyledButton(parent, text, x, y, w, h, on_click, st, text_col, size, z, radius, shadow, glow)


# ---------------------------------------------------------------------------
# Curseur, interrupteur, barre de progression
# ---------------------------------------------------------------------------
class UISlider(Entity):
    """Curseur horizontal déplaçable à la souris (valeur entre lo et hi)."""

    def __init__(self, parent, x, y, w, lo, hi, value, on_change=None, step=1, z=-0.02, height=0.016):
        super().__init__(parent=parent, position=(x, y, z))
        self.w, self.lo, self.hi, self.step, self.on_change = w, lo, hi, step, on_change
        self.value = value
        self.dragging = False
        self.track = theme.make_panel(self, 0, 0, w, height, "dark", 0.0, 0.5, False)
        self.fill = Entity(parent=self, model="quad", color=color.rgb32(236, 150, 60), position=(-w / 2, 0, -0.001),
                           scale=(0.001, height * 0.62))
        self.fill.origin = (-0.5, 0)
        kt, kp = theme.get_texture(theme.px(0.03), theme.px(0.03), "primary", "normal", 0.5, True)
        self.knob = Entity(parent=self, model="quad", texture=kt, scale=0.03 + 2 * kp / theme.PX, z=-0.003)
        self.hit = Button(parent=self, model="quad", scale=(w + 0.03, 0.05), color=color.rgba32(0, 0, 0, 1),
                          highlight_color=color.rgba32(0, 0, 0, 1), pressed_color=color.rgba32(0, 0, 0, 1), z=-0.004)
        self.hit.on_click = self._begin
        self._sync()

    def _begin(self):
        self.dragging = True
        theme.play_ui_sound("ui_click")
        self._from_mouse()

    def _from_mouse(self):
        p = self.get_position(relative_to=camera.ui)
        t = (mouse.x - (p[0] - self.w / 2)) / self.w
        t = max(0.0, min(1.0, t))
        v = self.lo + t * (self.hi - self.lo)
        v = round(v / self.step) * self.step
        v = int(v) if float(self.step).is_integer() and isinstance(self.lo, int) else round(v, 2)
        v = max(self.lo, min(self.hi, v))
        if v != self.value:
            self.value = v
            self._sync()
            if self.on_change:
                self.on_change(v)

    def _sync(self):
        t = (self.value - self.lo) / max(1e-6, (self.hi - self.lo))
        self.fill.scale_x = max(0.001, self.w * t)
        self.knob.x = -self.w / 2 + self.w * t

    def set_value(self, v):
        self.value = v
        self._sync()

    def input(self, key):
        if key == "left mouse up":
            self.dragging = False

    def update(self):
        if self.dragging:
            if mouse.left:
                self._from_mouse()
            else:
                self.dragging = False


class UIToggle(Button):
    """Interrupteur on/off (pilule colorée avec bouton rond)."""

    def __init__(self, parent, x, y, value, on_change=None, z=-0.02):
        self.value = bool(value)
        self.on_change_cb = on_change
        self.pw, self.ph = 0.085, 0.036
        tex, pad = theme.get_texture(theme.px(self.pw), theme.px(self.ph), "success" if self.value else "dark", "normal", 0.5, False)
        super().__init__(parent=parent, model="quad", position=(x, y, z), scale=(self.pw + 2 * pad / theme.PX, self.ph + 2 * pad / theme.PX),
                         color=color.white, highlight_color=color.white, pressed_color=color.white, highlight_scale=1.0, pressed_scale=1.0)
        self.texture = tex
        kt, kp = theme.get_texture(theme.px(0.03), theme.px(0.03), "key", "normal", 0.5, True)
        self.knob = Entity(parent=self, model="quad", texture=kt, scale=(0.03 / self.scale_x, 0.03 / self.scale_y), z=-0.01)
        self._place()
        self.on_click = self.toggle

    def _place(self):
        tex, _ = theme.get_texture(theme.px(self.pw), theme.px(self.ph), "success" if self.value else "dark", "normal", 0.5, False)
        self.texture = tex
        off = (self.pw / 2 - 0.02) / self.scale_x
        self.knob.x = off if self.value else -off

    def toggle(self):
        self.value = not self.value
        self._place()
        theme.play_ui_sound("ui_click")
        if self.on_change_cb:
            self.on_change_cb(self.value)


class ProgressBar(Entity):
    def __init__(self, parent, x, y, w, h, fill_col=(236, 150, 60), z=-0.01):
        super().__init__(parent=parent, position=(x, y, z))
        self.w = w
        theme.make_panel(self, 0, 0, w, h, "dark", 0.0, 0.5, False)
        self.fill = Entity(parent=self, model="quad", color=color.rgb32(*fill_col), position=(-w / 2 + 0.002, 0, -0.001),
                           scale=(0.001, h * 0.6))
        self.fill.origin = (-0.5, 0)

    def set(self, frac):
        self.fill.scale_x = max(0.001, (self.w - 0.004) * max(0.0, min(1.0, frac)))


# ---------------------------------------------------------------------------
# Divers
# ---------------------------------------------------------------------------
class Toast:
    """Message court affiché en bas de l'écran (ou d'un parent)."""

    def __init__(self, parent=None, y=-0.42):
        self.root = Entity(parent=parent or camera.ui, z=-5)
        self.bg = panel(self.root, 0, y, 0.72, 0.07, "panel", 0.0, 0.3, True)
        self.text = label(self.root, "", 0, y, 0.9, color.white, max_w=0.68, max_h=0.06)
        self.root.enabled = False
        self.timer = 0.0

    def show(self, message, duration=2.5, col=color.white):
        set_label(self.text, message)
        self.text.color = col
        self.root.enabled = True
        self.timer = duration

    def update(self, dt):
        if self.timer > 0:
            self.timer -= dt
            if self.timer <= 0:
                self.root.enabled = False


def fade_in(entity, duration=0.4):
    entity.alpha = 0
    entity.animate("alpha", 1, duration=duration, curve=curve.linear)


# ---------------------------------------------------------------------------
# Audit : textes qui sortent de leur cadre ou de l'écran
# ---------------------------------------------------------------------------
def _visible(e, root):
    n = e
    while n is not None:
        if not getattr(n, "enabled", True) or getattr(n, "audit_skip", False):
            return False
        if n is root:
            return True
        n = getattr(n, "parent", None)
    return False


def audit_overflow(root=None, tol=0.004):
    """Retourne la liste des textes visibles qui débordent de leur boîte (panneau, bouton, rectangle)
    ou de l'écran. Utilisé par tests/ui_audit.py sur tous les écrans du jeu."""
    from ursina import scene, window
    root = root or camera.ui
    half_w = window.aspect_ratio / 2.0
    boxes, texts = [], []
    for e in list(scene.entities):
        try:
            if not _visible(e, root):
                continue
            if isinstance(e, Text):
                if e.text and str(e.text).strip() and (e.color is None or e.color[3] > 0.05):
                    texts.append(e)
            elif getattr(e, "ui_box", None) is not None:
                b = e.getTightBounds(root)
                if b:
                    lo, hi = b
                    w, h = hi[0] - lo[0], hi[1] - lo[1]
                    if 0.03 <= min(w, h) and not (w > 1.9 and h > 1.0):
                        boxes.append((lo[0], lo[1], hi[0], hi[1], w * h, e))
                        e._audit_desc = f"{type(e).__name__}({getattr(e, 'text', '') or ''}) ui_box={e.ui_box}"
        except Exception:
            continue
    def top(e):
        n = e
        while n is not None and getattr(n, "parent", None) is not root:
            n = getattr(n, "parent", None)
        return n

    issues = []
    for t in texts:
        bx = text_box(t, root)
        if bx is None:
            continue
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        fully_out = bx[2] < -half_w or bx[0] > half_w or bx[3] < -0.5 or bx[1] > 0.5
        if fully_out:
            continue            # texte hors champ (générique qui défile...) : invisible
        if bx[0] < -half_w - tol or bx[2] > half_w + tol or bx[1] < -0.5 - tol or bx[3] > 0.5 + tol:
            issues.append(("écran", str(t.text)[:60], tuple(round(v, 3) for v in bx)))
            continue
        tt = top(t)
        best = None
        for (x0, y0, x1, y1, area, e) in boxes:
            if top(e) is not tt:
                continue
            if x0 <= cx <= x1 and y0 <= cy <= y1 and (best is None or area < best[4]):
                best = (x0, y0, x1, y1, area, e)
        if best is None:
            continue
        x0, y0, x1, y1 = best[:4]
        if bx[0] < x0 - tol or bx[2] > x1 + tol or bx[1] < y0 - tol or bx[3] > y1 + tol:
            issues.append(("boîte", str(t.text)[:60], (round(bx[0], 3), round(bx[2], 3), round(x0, 3), round(x1, 3),
                                                       getattr(best[5], "_audit_desc", ""))))
    return issues


def _walk(e):
    for c in list(getattr(e, "children", ())):
        if not getattr(c, "enabled", True):
            continue
        yield c
        yield from _walk(c)


def autofit(root, margin=0.006, min_ratio=0.45):
    """Réduit chaque texte visible de `root` qui dépasse de son cadre (panneau, bouton, rectangle) ou de l'écran.

    Appelé périodiquement sur tous les écrans ouverts : garantit qu'aucun texte ne sort de sa boîte,
    quelle que soit la taille de texte choisie, la langue de la chaîne ou la résolution."""
    from ursina import window
    ui = camera.ui
    half_w = window.aspect_ratio / 2.0
    boxes, texts = [], []
    for e in _walk(root):
        if getattr(e, "audit_skip", False):
            continue
        if isinstance(e, Text):
            if e.text and str(e.text).strip():
                texts.append(e)
        elif getattr(e, "ui_box", None) is not None:
            try:
                b = e.getTightBounds(ui)
            except Exception:
                b = None
            if b:
                lo, hi = b
                w, h = hi[0] - lo[0], hi[1] - lo[1]
                if 0.03 <= min(w, h) and not (w > 1.9 and h > 1.0):
                    boxes.append((lo[0], lo[1], hi[0], hi[1], w * h))
    changed = 0
    for t in texts:
        for _ in range(2):
            bx = text_box(t, ui)
            if bx is None:
                break
            cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            if bx[2] < -half_w or bx[0] > half_w or bx[3] < -0.5 or bx[1] > 0.5:
                break
            lim = (-half_w + 0.01, -0.495, half_w - 0.01, 0.495)
            best = None
            for (x0, y0, x1, y1, area) in boxes:
                if x0 <= cx <= x1 and y0 <= cy <= y1 and (best is None or area < best[4]):
                    best = (x0, y0, x1, y1, area)
            if best is not None:
                lim = (max(lim[0], best[0] + margin), max(lim[1], best[1] + margin * 0.5),
                       min(lim[2], best[2] - margin), min(lim[3], best[3] - margin * 0.5))
            try:
                a = t.get_position(relative_to=ui)
            except Exception:
                break
            k = 1.0
            if bx[0] < lim[0] and a[0] - bx[0] > 1e-6:
                k = min(k, (a[0] - lim[0]) / (a[0] - bx[0]))
            if bx[2] > lim[2] and bx[2] - a[0] > 1e-6:
                k = min(k, (lim[2] - a[0]) / (bx[2] - a[0]))
            if bx[1] < lim[1] and a[1] - bx[1] > 1e-6:
                k = min(k, (a[1] - lim[1]) / (a[1] - bx[1]))
            if bx[3] > lim[3] and bx[3] - a[1] > 1e-6:
                k = min(k, (lim[3] - a[1]) / (bx[3] - a[1]))
            if k >= 0.999 or k <= 0:
                break
            base = getattr(t, "_fit_base", None)
            if base is None:
                base = t._fit_base = Vec3(t.scale_x, t.scale_y, t.scale_z)
            k = max(k * 0.985, min_ratio * base[0] / max(t.scale_x, 1e-6))
            if k >= 0.999:
                break
            t.scale = Vec3(t.scale_x * k, t.scale_y * k, t.scale_z)
            changed += 1
    return changed


def autofit_all(skip=()):
    """Passe d'ajustement sur tous les écrans d'interface ouverts."""
    n = 0
    for c in list(camera.ui.children):
        if getattr(c, "enabled", False) and c not in skip and not getattr(c, "audit_skip", False):
            try:
                n += autofit(c)
            except Exception:
                pass
    return n
