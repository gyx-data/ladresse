"""Shaders GLSL de L'ADRESSE.

* ``horror_shader``  : shader du monde 3D. Lampe torche (projecteur), jusqu'à 8
  lumières ponctuelles, lumière ambiante, brouillard exponentiel, distorsion
  autour de l'entité, émission par objet.
* ``post_shader``    : post-traitement plein écran (vignette, grain, aberration
  chromatique, distorsion, teinte, flash, fondu, daltonisme).

Les uniformes globaux sont poussés chaque frame par ``ShaderState``.
"""
from panda3d.core import PTA_LVecBase4f, LVecBase4f, LMatrix4f
from ursina import Shader, Vec2, Vec3, scene, camera

MAX_POINT_LIGHTS = 8

WORLD_VERTEX = '''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
out vec2 uvs;
out vec3 wpos;
out vec3 wnorm;
out vec4 vcol;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    vec4 w = p3d_ModelMatrix * p3d_Vertex;
    wpos = w.xyz;
    vec3 nn = mat3(p3d_ModelMatrix) * p3d_Normal;
    wnorm = length(nn) > 0.001 ? normalize(nn) : vec3(0.0, 1.0, 0.0);
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vcol = p3d_Color;
}
'''

WORLD_FRAGMENT = '''#version 140
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform float emit;

uniform vec3 cam_pos;
uniform vec3 fl_pos;
uniform vec3 fl_dir;
uniform vec3 fl_color;
uniform vec4 fl_params;      // cos externe, cos interne, intensité, portée
uniform vec3 ambient;
uniform vec3 fog_color;
uniform float fog_density;
uniform vec4 pl_pos[8];      // xyz position, w portée
uniform vec4 pl_col[8];      // rgb couleur, a intensité
uniform vec4 ent_data;       // xyz position de l'entité, w force de distorsion
uniform vec3 sun_dir;        // direction de la lumière lunaire (extérieur)
uniform vec3 sun_col;
uniform float u_time;

in vec2 uvs;
in vec3 wpos;
in vec3 wnorm;
in vec4 vcol;
out vec4 fragColor;

void main() {
    vec2 uv = uvs;
    float de = distance(wpos, ent_data.xyz);
    if (ent_data.w > 0.0 && de < 6.0) {
        float k = (1.0 - de / 6.0) * ent_data.w;
        uv += vec2(sin(wpos.y * 9.0 + u_time * 4.0), cos(wpos.x * 7.0 + u_time * 3.0)) * 0.03 * k;
    }
    vec4 base = texture(p3d_Texture0, uv) * p3d_ColorScale * vcol;
    if (base.a < 0.02) discard;
    vec3 N = normalize(wnorm);
    if (!gl_FrontFacing) N = -N;

    vec3 light = ambient + sun_col * (max(dot(N, -sun_dir), 0.0) * 0.9 + 0.1);

    // Lampe torche
    vec3 Lf = fl_pos - wpos;
    float df = length(Lf);
    Lf /= max(df, 0.001);
    float cosang = dot(-Lf, fl_dir);
    float spot = smoothstep(fl_params.x, fl_params.y, cosang);
    float attf = clamp(1.0 - df / fl_params.w, 0.0, 1.0);
    attf *= attf;
    float ndl = max(dot(N, Lf), 0.0) * 0.75 + 0.25;
    light += fl_color * fl_params.z * spot * attf * ndl;

    // Lumières ponctuelles
    for (int i = 0; i < 8; i++) {
        float range = pl_pos[i].w;
        if (range <= 0.0) continue;
        vec3 Lp = pl_pos[i].xyz - wpos;
        float dp = length(Lp);
        if (dp > range) continue;
        Lp /= max(dp, 0.001);
        float a = 1.0 - dp / range;
        a *= a;
        light += pl_col[i].rgb * pl_col[i].a * a * (max(dot(N, Lp), 0.0) * 0.8 + 0.2);
    }

    vec3 rgb = base.rgb * light + base.rgb * emit;

    // Brouillard exponentiel
    float dist = distance(wpos, cam_pos);
    float f = 1.0 - exp(-pow(dist * fog_density, 1.6));
    rgb = mix(rgb, fog_color, clamp(f, 0.0, 1.0));
    fragColor = vec4(rgb, base.a);
}
'''

POST_VERTEX = '''#version 140
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
'''

POST_FRAGMENT = '''#version 140
uniform sampler2D tex;
uniform float u_time;
uniform float vignette;      // 0..1
uniform float vig_pulse;     // 0..1 pulsation
uniform float grain;         // 0..1
uniform float chroma;        // 0..1
uniform float distort;       // 0..1
uniform vec3 tint;           // multiplicateur couleur
uniform float flash;         // 0..1 (blanc)
uniform float fade;          // 0..1 (noir)
uniform float enabled;       // 1 = post-traitement actif
uniform mat4 cb_matrix;      // correction daltonien
uniform vec2 res;
in vec2 uv;
out vec4 color;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void main() {
    vec2 p = uv;
    if (enabled < 0.5) {
        vec3 c0 = texture(tex, p).rgb * tint;
        c0 = mix(c0, vec3(1.0), flash);
        c0 = mix(c0, vec3(0.0), fade);
        color = vec4((cb_matrix * vec4(c0, 1.0)).rgb, 1.0);
        return;
    }
    if (distort > 0.001) {
        p += vec2(sin(p.y * 28.0 + u_time * 5.0), cos(p.x * 24.0 + u_time * 4.2)) * 0.006 * distort;
        p += vec2(sin(p.y * 90.0 + u_time * 30.0) * 0.012 * pow(distort, 3.0), 0.0);
    }
    vec2 c = p - 0.5;
    float r2 = dot(c, c);
    float ca = chroma * (0.003 + 0.02 * r2);
    vec3 col;
    col.r = texture(tex, p + c * ca * 2.0).r;
    col.g = texture(tex, p).g;
    col.b = texture(tex, p - c * ca * 2.0).b;

    float luma = dot(col, vec3(0.299, 0.587, 0.114));
    float g = hash(uv * res + fract(u_time) * 100.0) - 0.5;
    col += g * grain * (0.10 + 0.25 * (1.0 - clamp(luma * 3.0, 0.0, 1.0)));

    float v = smoothstep(0.80 - 0.55 * vignette, 0.12, sqrt(r2) * (1.0 + 0.3 * vig_pulse));
    col *= mix(1.0, v, clamp(0.35 + vignette, 0.0, 1.0));

    col *= tint;
    col = mix(col, vec3(1.0), flash);
    col = mix(col, vec3(0.0), fade);
    color = vec4((cb_matrix * vec4(col, 1.0)).rgb, 1.0);
}
'''

horror_shader = Shader(name='horror_world', language=Shader.GLSL,
                       vertex=WORLD_VERTEX, fragment=WORLD_FRAGMENT,
                       default_input={
                           'texture_scale': Vec2(1, 1),
                           'texture_offset': Vec2(0, 0),
                           'emit': 0.0,
                       })

post_shader = Shader(name='horror_post', language=Shader.GLSL,
                     vertex=POST_VERTEX, fragment=POST_FRAGMENT,
                     default_input={
                         'u_time': 0.0, 'vignette': 0.3, 'vig_pulse': 0.0,
                         'grain': 0.5, 'chroma': 0.2, 'distort': 0.0,
                         'tint': Vec3(1, 1, 1), 'flash': 0.0, 'fade': 0.0,
                         'enabled': 1.0, 'res': Vec2(1280, 720),
                     })

# Matrices de correction pour le daltonisme (daltonisation simple).
COLORBLIND_MATRICES = {
    'Normal': (1, 0, 0, 0, 1, 0, 0, 0, 1),
    'Protanopie': (1.0, 0.0, 0.0, 0.7, 1.0, 0.0, 0.7, 0.0, 1.0),
    'Deutéranopie': (1.0, 0.7, 0.0, 0.0, 1.0, 0.0, 0.0, 0.7, 1.0),
    'Tritanopie': (1.0, 0.0, 0.7, 0.0, 1.0, 0.7, 0.0, 0.0, 1.0),
}


class ShaderState:
    """Contient l'état des uniformes globaux et les pousse vers les shaders."""

    def __init__(self):
        self.time = 0.0
        # Monde
        self.cam_pos = Vec3(0, 0, 0)
        self.fl_pos = Vec3(0, 0, 0)
        self.fl_dir = Vec3(0, 0, 1)
        self.fl_color = Vec3(1.0, 0.97, 0.88)
        self.fl_params = [0.80, 0.93, 0.0, 14.0]
        self.ambient = Vec3(0.035, 0.04, 0.06)
        self.fog_color = Vec3(0.0, 0.0, 0.0)
        self.fog_density = 0.11
        self.sun_dir = Vec3(-0.35, -0.8, 0.5).normalized()
        self.sun_col = Vec3(0, 0, 0)
        self.ent_pos = Vec3(0, -500, 0)
        self.ent_distort = 0.0
        self._pl_pos = PTA_LVecBase4f.empty_array(MAX_POINT_LIGHTS)
        self._pl_col = PTA_LVecBase4f.empty_array(MAX_POINT_LIGHTS)
        for i in range(MAX_POINT_LIGHTS):
            self._pl_pos.set_element(i, LVecBase4f(0, 0, 0, 0))
            self._pl_col.set_element(i, LVecBase4f(0, 0, 0, 0))
        # Post
        self.post = dict(vignette=0.3, vig_pulse=0.0, grain=0.5, chroma=0.2,
                         distort=0.0, tint=Vec3(1, 1, 1), flash=0.0, fade=0.0,
                         enabled=1.0)
        self.cb_mode = 'Normal'
        self._post_ready = False

    @staticmethod
    def _cb4(mode):
        m = COLORBLIND_MATRICES.get(mode, COLORBLIND_MATRICES['Normal'])
        # Panda3D: vecteur ligne * matrice -> on transpose pour M * v côté GLSL.
        return LMatrix4f(m[0], m[3], m[6], 0, m[1], m[4], m[7], 0,
                         m[2], m[5], m[8], 0, 0, 0, 0, 1)

    # --- lumières ponctuelles -------------------------------------------
    def set_point_lights(self, lights):
        """lights: liste de (position Vec3, couleur (r,g,b), intensité, portée)."""
        for i in range(MAX_POINT_LIGHTS):
            if i < len(lights):
                p, c, inten, rng = lights[i]
                self._pl_pos.set_element(i, LVecBase4f(p[0], p[1], p[2], rng))
                self._pl_col.set_element(i, LVecBase4f(c[0], c[1], c[2], inten))
            else:
                self._pl_pos.set_element(i, LVecBase4f(0, 0, 0, 0))
                self._pl_col.set_element(i, LVecBase4f(0, 0, 0, 0))

    # --- activation du post-traitement ----------------------------------
    def enable_post(self, resolution=(1280, 720)):
        camera.shader = post_shader
        self._post_ready = True
        camera.set_shader_input('res', Vec2(*resolution))
        camera.set_shader_input('cb_matrix', self._cb4('Normal'))

    def push(self):
        """À appeler une fois par frame."""
        s = scene
        s.set_shader_input('cam_pos', self.cam_pos)
        s.set_shader_input('fl_pos', self.fl_pos)
        s.set_shader_input('fl_dir', self.fl_dir)
        s.set_shader_input('fl_color', self.fl_color)
        s.set_shader_input('fl_params', LVecBase4f(*self.fl_params))
        s.set_shader_input('ambient', self.ambient)
        s.set_shader_input('sun_dir', self.sun_dir)
        s.set_shader_input('sun_col', self.sun_col)
        s.set_shader_input('fog_color', self.fog_color)
        s.set_shader_input('fog_density', float(self.fog_density))
        s.set_shader_input('pl_pos', self._pl_pos)
        s.set_shader_input('pl_col', self._pl_col)
        s.set_shader_input('ent_data', LVecBase4f(self.ent_pos[0], self.ent_pos[1], self.ent_pos[2], self.ent_distort))
        s.set_shader_input('u_time', float(self.time))
        if self._post_ready:
            camera.set_shader_input('u_time', float(self.time))
            for k, v in self.post.items():
                camera.set_shader_input(k, v)
            camera.set_shader_input('cb_matrix', self._cb4(self.cb_mode))


shader_state = ShaderState()
