"""Moteur sonore de L'ADRESSE : synthèse procédurale (numpy + wave) et audio spatial.

Tous les sons sont synthétisés au premier lancement puis mis en cache en WAV.
Le moteur gère :
* les sons d'ambiance en boucle (avec fondus),
* les sons ponctuels 2D et 3D (atténuation, panoramique stéréo, occlusion),
* les voix synthétiques (formants),
* la musique dynamique liée à l'IA de l'entité,
* le battement de cœur et la respiration du joueur.
"""
import hashlib
import math
import os
import wave

import numpy as np

import config

SR = 22050
_SOUNDS = {}      # nom -> dict(fn, loop, spatial)


def snd(name, loop=False, spatial=False):
    def deco(fn):
        _SOUNDS[name] = dict(fn=fn, loop=loop, spatial=spatial)
        return fn
    return deco


# ---------------------------------------------------------------------------
# Outils DSP
# ---------------------------------------------------------------------------
def taxis(dur):
    return np.arange(int(SR * dur)) / SR


def sine(f, dur, phase=0.0):
    return np.sin(2 * np.pi * f * taxis(dur) + phase)


def noise(dur, rng):
    return rng.standard_normal(int(SR * dur))


def fft_filter(x, lo=None, hi=None, sharp=4):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    mask = np.ones_like(f)
    if hi:
        mask *= 1.0 / (1.0 + (f / hi) ** sharp)
    if lo:
        mask *= 1.0 / (1.0 + (lo / np.maximum(f, 1e-3)) ** sharp)
    return np.fft.irfft(X * mask, len(x))


def lowpass(x, fc):
    return fft_filter(x, hi=fc)


def highpass(x, fc):
    return fft_filter(x, lo=fc)


def bandpass(x, lo, hi):
    return fft_filter(x, lo=lo, hi=hi)


def decay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))


def adsr(n, a=0.01, d=0.05, s=0.7, r=0.1):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    env = np.ones(n) * s
    a_n = min(a_n, n)
    env[:a_n] = np.linspace(0, 1, a_n, endpoint=False) if a_n else env[:a_n]
    d_end = min(a_n + d_n, n)
    if d_end > a_n:
        env[a_n:d_end] = np.linspace(1, s, d_end - a_n)
    r_n = min(r_n, n)
    if r_n:
        env[n - r_n:] *= np.linspace(1, 0, r_n)
    return env


def normalize(x, peak=0.9):
    m = np.max(np.abs(x)) if len(x) else 0
    return x * (peak / m) if m > 1e-9 else x


def fade_edges(x, ms=8):
    n = min(int(SR * ms / 1000.0), len(x) // 2)
    if n > 0:
        x = x.copy()
        x[:n] *= np.linspace(0, 1, n)
        x[-n:] *= np.linspace(1, 0, n)
    return x


def reverb(x, rng, tail=0.5, wet=0.35):
    n = int(SR * tail)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (tail / 5.0 * SR))
    ir[0] = 1.0
    ir = lowpass(ir, 4000) if n > 8 else ir
    N = len(x) + n
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)
    y = normalize(y, np.max(np.abs(x)) if np.max(np.abs(x)) > 0 else 1.0)
    out = np.zeros(N)
    out[:len(x)] += x * (1 - wet)
    out += y * wet
    return out


def mix(*arrays, gains=None):
    n = max(len(a) for a in arrays)
    out = np.zeros(n)
    for i, a in enumerate(arrays):
        g = 1.0 if gains is None else gains[i]
        out[:len(a)] += a * g
    return out


def place(buf, x, t):
    i = int(t * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += x[:j - i]


def square(f, dur):
    return np.sign(sine(f, dur))


def saw(f, dur):
    t = taxis(dur)
    return 2.0 * ((t * f) % 1.0) - 1.0


def to_wav16(x):
    x = np.clip(x, -1.0, 1.0)
    return (x * 32767).astype(np.int16)


def write_wav(path, x):
    data = to_wav16(x)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def note_freq(n):
    """n = demi-tons depuis le La 440 (n=0)."""
    return 440.0 * 2 ** (n / 12.0)


def tone(f, dur, harmonics=(1.0, 0.4, 0.2), env=None):
    t = taxis(dur)
    y = np.zeros_like(t)
    for k, a in enumerate(harmonics):
        y += a * np.sin(2 * np.pi * f * (k + 1) * t)
    if env is None:
        env = adsr(len(t), 0.01, 0.08, 0.6, 0.12)
    return y * env


def melody(notes, step, harmonics=(1.0, 0.4, 0.2), tail=0.25):
    """notes: liste de demi-tons (None = silence)."""
    total = step * len(notes) + tail
    buf = np.zeros(int(SR * total))
    for i, nt in enumerate(notes):
        if nt is None:
            continue
        place(buf, tone(note_freq(nt), step + tail, harmonics, adsr(int((step + tail) * SR), 0.01, 0.1, 0.5, tail)), i * step)
    return buf


# ---------------------------------------------------------------------------
# Voix synthétique (formants)
# ---------------------------------------------------------------------------
VOWELS = {
    "a": (800, 1150, 2900), "e": (400, 1700, 2600), "i": (300, 2200, 3000),
    "o": (450, 800, 2830), "u": (325, 700, 2700), "y": (300, 2100, 2900),
}
ACCENT_MAP = str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc")


def _formant_env(freqs, formants, bw=(90, 110, 160)):
    env = np.zeros_like(freqs)
    for F, b, g in zip(formants, bw, (1.0, 0.7, 0.4)):
        env += g * np.exp(-0.5 * ((freqs - F) / b) ** 2)
    return env + 0.02


def _vowel(f0, formants, dur, whisper, rng, vibrato=0.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    if whisper:
        x = rng.standard_normal(n)
        X = np.fft.rfft(x)
        f = np.fft.rfftfreq(n, 1.0 / SR)
        y = np.fft.irfft(X * _formant_env(f, formants, (140, 180, 260)), n)
    else:
        nh = int(min(40, 4000 / f0))
        k = np.arange(1, nh + 1)[:, None]
        fk = k * f0
        amps = _formant_env(fk, formants) / k ** 0.6
        ph = 2 * np.pi * f0 * (t + vibrato * 0.004 * np.sin(2 * np.pi * 5.5 * t))
        y = (amps * np.sin(k * ph[None, :])).sum(axis=0)
    env = adsr(n, 0.015, 0.03, 0.8, 0.03)
    return normalize(y, 0.8) * env


def synth_voice(text, f0=120.0, speed=1.0, whisper=False, seed=1, monotone=False):
    rng = np.random.default_rng(seed)
    text = text.lower().translate(ACCENT_MAP)
    pieces = []
    pitch_drift = 0.0
    for ch in text:
        if ch in VOWELS:
            drift = f0 * (1.0 + 0.06 * math.sin(pitch_drift)) if not monotone else f0
            pitch_drift += 0.7
            pieces.append(_vowel(drift, VOWELS[ch], 0.085 / speed, whisper, rng, 0.5))
        elif ch.isalpha():
            n = int(SR * 0.045 / speed)
            burst = highpass(rng.standard_normal(n), 2500) * decay(n, 0.02) * (0.5 if ch in "sfzjchx" else 0.25)
            pieces.append(burst)
        elif ch in " ,.;:!?-'":
            pieces.append(np.zeros(int(SR * (0.16 if ch in ".!?" else 0.06) / speed)))
    if not pieces:
        return np.zeros(int(SR * 0.1))
    return normalize(np.concatenate(pieces), 0.8)


# ---------------------------------------------------------------------------
# Ambiances (boucles)
# ---------------------------------------------------------------------------
@snd("drone", loop=True)
def s_drone(rng):
    d = 8.0
    t = taxis(d)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)
    y = 0.6 * np.sin(2 * np.pi * 40 * t) + 0.4 * np.sin(2 * np.pi * 45.5 * t + 1.0) * lfo
    y += 0.25 * np.sin(2 * np.pi * 57 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.125 * t))
    y += 0.05 * lowpass(rng.standard_normal(len(t)), 200)
    return normalize(y, 0.8)


@snd("vent", loop=True)
def s_wind(rng):
    d = 10.0
    t = taxis(d)
    x = lowpass(noise(d, rng), 600)
    x *= 0.55 + 0.45 * np.sin(2 * np.pi * 0.2 * t + 0.5) * np.sin(2 * np.pi * 0.1 * t + 1.0)
    return normalize(x, 0.7)


@snd("pluie", loop=True)
def s_rain(rng):
    d = 6.0
    x = bandpass(noise(d, rng), 900, 7000)
    t = taxis(d)
    x *= 0.8 + 0.2 * np.sin(2 * np.pi * (1 / 3.0) * t)
    return normalize(x, 0.6)


@snd("pluie_pare_brise", loop=True)
def s_rain_windshield(rng):
    d = 4.0
    x = bandpass(noise(d, rng), 600, 3500) * 0.7
    buf = x.copy()
    for _ in range(40):
        place(buf, highpass(rng.standard_normal(300), 1500) * decay(300, 0.002) * 0.5, rng.uniform(0, d - 0.1))
    return normalize(buf, 0.6)


@snd("grillons", loop=True)
def s_crickets(rng):
    d = 6.0
    buf = np.zeros(int(SR * d))
    for base, offset in ((4300, 0.0), (4700, 0.37), (3900, 0.71)):
        t = 0.0 + offset
        while t < d - 0.5:
            for k in range(3):
                chirp = sine(base + rng.uniform(-80, 80), 0.05) * adsr(int(0.05 * SR), 0.005, 0.01, 0.8, 0.02)
                place(buf, chirp * 0.25, t + k * 0.07)
            t += rng.uniform(0.55, 1.1)
    return normalize(buf, 0.5)


@snd("neon", loop=True, spatial=True)
def s_neon_hum(rng):
    d = 2.0
    t = taxis(d)
    y = 0.5 * np.sign(np.sin(2 * np.pi * 100 * t)) * 0.3 + 0.3 * np.sin(2 * np.pi * 100 * t)
    for h in (200, 300, 400, 600):
        y += 0.1 * np.sin(2 * np.pi * h * t)
    y += 0.03 * highpass(rng.standard_normal(len(t)), 3000)
    return normalize(y, 0.5)


@snd("neon_buzz", spatial=True)
def s_neon_buzz(rng):
    y = highpass(noise(0.12, rng), 800) * decay(int(0.12 * SR), 0.05)
    y += 0.5 * sine(100, 0.12) * decay(int(0.12 * SR), 0.06)
    return normalize(y, 0.7)


@snd("tuyauterie", loop=True, spatial=True)
def s_pipes(rng):
    d = 6.0
    t = taxis(d)
    x = lowpass(noise(d, rng), 160)
    x = x * (0.5 + 0.5 * np.sin(2 * np.pi * (1 / 3.0) * t)) ** 2
    x += 0.4 * np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t))
    x += 0.2 * np.sin(2 * np.pi * 110 * t) * np.sin(2 * np.pi * (1 / 6.0) * t) ** 2
    return normalize(x, 0.7)


@snd("coeur_geant", loop=True)
def s_giant_heart(rng):
    d = 4.0
    buf = np.zeros(int(SR * d))
    for i in range(4):
        n = int(SR * 0.5)
        pulse = np.sin(2 * np.pi * 44 * np.arange(n) / SR) * decay(n, 0.12)
        place(buf, pulse, i * 1.0)
        place(buf, pulse * 0.6, i * 1.0 + 0.22)
    return normalize(buf, 0.9)


@snd("infrasons", loop=True)
def s_infra(rng):
    d = 8.0
    t = taxis(d)
    y = np.sin(2 * np.pi * 24 * t) * 0.7 + np.sin(2 * np.pi * 31 * t + 0.3) * 0.5
    y *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.125 * t)
    return normalize(y, 0.8)


@snd("frigo", loop=True, spatial=True)
def s_fridge(rng):
    d = 4.0
    t = taxis(d)
    y = 0.6 * np.sin(2 * np.pi * 50 * t) + 0.3 * np.sin(2 * np.pi * 100 * t) + 0.12 * lowpass(rng.standard_normal(len(t)), 250)
    return normalize(y, 0.5)


@snd("statique_loop", loop=True, spatial=True)
def s_static_loop(rng):
    return normalize(bandpass(noise(2.0, rng), 200, 9000), 0.6)


@snd("moteur", loop=True)
def s_engine(rng):
    d = 2.0
    t = taxis(d)
    y = 0.6 * np.sin(2 * np.pi * 48 * t) + 0.35 * np.sin(2 * np.pi * 96 * t) + 0.2 * np.sin(2 * np.pi * 144 * t + 0.5)
    y *= 0.85 + 0.15 * np.sin(2 * np.pi * 8 * t)
    y += 0.08 * lowpass(rng.standard_normal(len(t)), 300)
    return normalize(y, 0.7)


@snd("bureau_ambiance", loop=True)
def s_office(rng):
    d = 6.0
    t = taxis(d)
    y = 0.3 * np.sin(2 * np.pi * 100 * t) + 0.15 * np.sin(2 * np.pi * 200 * t)
    y += 0.1 * lowpass(rng.standard_normal(len(t)), 500)
    return normalize(y, 0.4)


@snd("clavier")
def s_keyboard(rng):
    d = 3.0
    buf = np.zeros(int(SR * d))
    t = 0.1
    while t < d - 0.2:
        place(buf, highpass(rng.standard_normal(260), 1800) * decay(260, 0.004), t)
        t += rng.uniform(0.07, 0.35)
    return normalize(buf, 0.5)


@snd("cordes_poursuite", loop=True)
def s_chase_strings(rng):
    d = 8.0
    t = taxis(d)
    y = np.zeros_like(t)
    for f, a in ((220, 0.5), (233.1, 0.5), (329.6, 0.35), (349.2, 0.35), (466.2, 0.25)):
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t + f)
        y += a * (np.sin(2 * np.pi * f * t * vib) + 0.5 * np.sin(2 * np.pi * 2 * f * t * vib))
    y *= 0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * t) ** 2
    y *= 1.0 + 0.2 * np.sin(2 * np.pi * 4 * t)
    return normalize(lowpass(y, 3200), 0.7)


@snd("chuchotements", loop=True, spatial=True)
def s_whispers(rng):
    d = 6.0
    t = taxis(d)
    x = bandpass(noise(d, rng), 500, 3000)
    am = (0.5 + 0.5 * np.sin(2 * np.pi * 3.0 * t)) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * t + 1.0))
    return normalize(x * am, 0.6)


@snd("berceuse", loop=True, spatial=True)
def s_lullaby(rng):
    notes = [7, 4, 0, 4, 7, 4, 0, None, 5, 2, -2, 2, 5, 2, -2, None]
    m = melody(notes, 0.5, (1.0, 0.1, 0.05), 0.5)
    t = taxis(len(m) / SR)
    wob = np.interp(np.arange(len(m)) + 40 * np.sin(2 * np.pi * 0.4 * t), np.arange(len(m)), m)
    wob = lowpass(wob, 1800)
    return normalize(wob[:int(SR * 8.0)], 0.4)


@snd("radio_melodie")
def s_radio_melody(rng):
    notes = [-3, 0, 4, 2, 0, -3, -5, None, -3, 0, 4, 7, 5, 4, 2, None, 0, 2, 4, 2, 0, -3, -5, -8]
    m = melody(notes, 0.45, (1.0, 0.3, 0.15), 0.6)
    m = bandpass(m, 250, 4500)
    m += 0.12 * rng.standard_normal(len(m)) * (0.4 + 0.6 * np.abs(np.sin(np.arange(len(m)) / 5000.0)))
    cut = len(m) - int(SR * 0.3)
    m[cut:] = highpass(rng.standard_normal(len(m) - cut), 600) * 0.5
    return normalize(m, 0.6)


@snd("musique_attente", loop=True)
def s_hold_music(rng):
    notes = [0, 4, 7, 12, 7, 4, 0, None, 2, 5, 9, 14, 9, 5, 2, None]
    m = melody(notes, 0.3, (1.0, 0.5, 0.3), 0.2)[:int(SR * 4.8)]
    m = bandpass(m, 400, 2800)
    q = np.round(m * 24) / 24.0     # qualité dégradée
    q += 0.05 * rng.standard_normal(len(q))
    return normalize(q, 0.5)


# ---------------------------------------------------------------------------
# Joueur
# ---------------------------------------------------------------------------
def _step(rng, lo, hi, tau, gain=1.0, thump=0.0):
    n = int(SR * 0.18)
    x = bandpass(rng.standard_normal(n), lo, hi) * decay(n, tau)
    if thump:
        x += thump * np.sin(2 * np.pi * 70 * np.arange(n) / SR) * decay(n, 0.03)
    return normalize(fade_edges(x, 2), 0.8 * gain)


for _i in range(3):
    def _mk(i):
        @snd(f"pas_parquet_{i}", spatial=True)
        def s(rng):
            lo = 150 + 40 * i
            x = _step(rng, lo, 1200 + 150 * i, 0.04, 1.0, 0.5)
            # craquement du bois
            n = int(SR * 0.08)
            x[:n] += 0.35 * bandpass(rng.standard_normal(n), 600, 2200) * decay(n, 0.02)
            return normalize(x, 0.8)
        @snd(f"pas_carrelage_{i}", spatial=True)
        def c(rng):
            return _step(rng, 800 + 120 * i, 5000, 0.02, 0.9)
        @snd(f"pas_beton_{i}", spatial=True)
        def b(rng):
            return _step(rng, 80, 600 + 80 * i, 0.05, 1.0, 0.7)
        @snd(f"pas_moquette_{i}", spatial=True)
        def m(rng):
            return _step(rng, 60, 500, 0.06, 0.55)
        @snd(f"pas_escalier_{i}", spatial=True)
        def e(rng):
            x = _step(rng, 120, 900, 0.07, 1.0, 0.7)
            n = int(SR * 0.3)
            creak = bandpass(rng.standard_normal(n), 200 + 80 * i, 800) * decay(n, 0.1) * np.sin(2 * np.pi * (2 + i) * np.arange(n) / SR) ** 2
            return normalize(mix(x, creak, gains=(1.0, 0.6)), 0.8)
    _mk(_i)


@snd("pas_escalier_fort", spatial=True)
def s_loud_stair(rng):
    n = int(SR * 0.7)
    x = bandpass(rng.standard_normal(n), 100, 1400) * decay(n, 0.2)
    sweep = np.sin(2 * np.pi * np.cumsum(np.linspace(260, 90, n)) / SR) * decay(n, 0.25)
    return normalize(mix(x, sweep, gains=(0.7, 0.8)), 0.95)


@snd("respiration_calme")
def s_breath_calm(rng):
    d = 2.6
    n = int(SR * d)
    t = taxis(d)
    env = np.clip(np.sin(np.pi * t / d), 0, 1) ** 2
    x = bandpass(rng.standard_normal(n), 300, 1800) * env
    return normalize(x, 0.35)


@snd("respiration_lourde")
def s_breath_heavy(rng):
    d = 1.1
    n = int(SR * d)
    t = taxis(d)
    env = np.clip(np.sin(np.pi * t / d), 0, 1) ** 1.2
    x = bandpass(rng.standard_normal(n), 250, 2600) * env
    x += 0.2 * np.sin(2 * np.pi * 180 * t) * env
    return normalize(x, 0.75)


@snd("heartbeat")
def s_heartbeat(rng):
    n = int(SR * 0.7)
    buf = np.zeros(n)
    p1 = np.sin(2 * np.pi * 52 * np.arange(int(SR * 0.22)) / SR) * decay(int(SR * 0.22), 0.07)
    p2 = np.sin(2 * np.pi * 46 * np.arange(int(SR * 0.22)) / SR) * decay(int(SR * 0.22), 0.06)
    place(buf, p1, 0.0)
    place(buf, p2 * 0.75, 0.24)
    return normalize(buf, 0.95)


@snd("porte_ouvre", spatial=True)
def s_door_open(rng):
    d = 1.6
    n = int(SR * d)
    t = taxis(d)
    f = np.interp(t, [0, d * 0.5, d], [200, 650, 330]) + 30 * np.sin(2 * np.pi * 9 * t)
    sweep = np.sin(2 * np.pi * np.cumsum(f) / SR)
    sweep = sweep + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR)
    x = sweep * 0.5 + bandpass(rng.standard_normal(n), 500, 3000) * 0.25
    env = np.clip(np.sin(np.pi * t / d), 0, 1) ** 0.6
    return normalize(x * env, 0.7)


@snd("porte_ferme", spatial=True)
def s_door_close(rng):
    n = int(SR * 0.5)
    x = lowpass(rng.standard_normal(n), 900) * decay(n, 0.06)
    x += 0.8 * np.sin(2 * np.pi * 85 * np.arange(n) / SR) * decay(n, 0.09)
    return normalize(x, 0.9)


@snd("porte_claque", spatial=True)
def s_door_slam(rng):
    n = int(SR * 0.9)
    x = rng.standard_normal(n) * decay(n, 0.05)
    x = lowpass(x, 4500) + 1.2 * np.sin(2 * np.pi * 60 * np.arange(n) / SR) * decay(n, 0.2)
    return normalize(reverb(x, rng, 0.5, 0.35), 1.0)


@snd("poignee", spatial=True)
def s_handle(rng):
    n = int(SR * 0.25)
    x = bandpass(rng.standard_normal(n), 1500, 4500) * decay(n, 0.03)
    x += 0.4 * np.sin(2 * np.pi * 900 * np.arange(n) / SR) * decay(n, 0.02)
    return normalize(x, 0.5)


@snd("verrou", spatial=True)
def s_locked(rng):
    n = int(SR * 0.3)
    buf = np.zeros(n)
    for t in (0.0, 0.12):
        place(buf, bandpass(rng.standard_normal(int(0.05 * SR)), 1200, 5000) * decay(int(0.05 * SR), 0.01), t)
    return normalize(buf, 0.6)


@snd("verre", spatial=True)
def s_glass(rng):
    n = int(SR * 1.2)
    x = highpass(rng.standard_normal(n), 2500) * decay(n, 0.12)
    buf = x.copy()
    for _ in range(14):
        place(buf, sine(rng.uniform(2500, 7000), 0.08) * decay(int(0.08 * SR), 0.02) * 0.4, rng.uniform(0.05, 0.9))
    return normalize(buf, 0.8)


@snd("planche_arrachee", spatial=True)
def s_plank(rng):
    n = int(SR * 0.9)
    x = bandpass(rng.standard_normal(n), 120, 2000) * decay(n, 0.14)
    creak = np.sin(2 * np.pi * np.cumsum(np.linspace(180, 420, n)) / SR) * decay(n, 0.3) * 0.5
    crack = np.zeros(n)
    place(crack, highpass(rng.standard_normal(int(0.04 * SR)), 1500) * 1.5, 0.35)
    return normalize(mix(x, creak, crack), 0.95)


@snd("goutte", spatial=True)
def s_drip(rng):
    n = int(SR * 0.25)
    t = taxis(0.25)
    f = 1100 * np.exp(-t * 8) + 450
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * decay(n, 0.04)
    return normalize(reverb(x, rng, 0.4, 0.3), 0.55)


@snd("craquement_bois", spatial=True)
def s_wood_creak(rng):
    n = int(SR * 0.5)
    x = np.zeros(n)
    for t in (0.0, 0.05, 0.11):
        place(x, bandpass(rng.standard_normal(int(0.02 * SR)), 500, 2500) * rng.uniform(0.5, 1.0), t)
    return normalize(reverb(x, rng, 0.4, 0.4), 0.7)


@snd("obturateur")
def s_shutter(rng):
    n = int(SR * 0.3)
    buf = np.zeros(n)
    place(buf, bandpass(rng.standard_normal(int(0.03 * SR)), 1500, 6000) * 1.0, 0.0)
    place(buf, bandpass(rng.standard_normal(int(0.04 * SR)), 800, 3500) * 0.8, 0.09)
    return normalize(buf, 0.8)


@snd("clic_lampe")
def s_flash_click(rng):
    n = int(SR * 0.08)
    x = bandpass(rng.standard_normal(n), 1000, 5000) * decay(n, 0.01)
    return normalize(x, 0.6)


@snd("ramasser")
def s_pickup(rng):
    n = int(SR * 0.2)
    x = bandpass(rng.standard_normal(n), 400, 2500) * decay(n, 0.05)
    return normalize(x, 0.45)


@snd("papier")
def s_paper(rng):
    n = int(SR * 0.5)
    x = highpass(rng.standard_normal(n), 2000) * (0.3 + 0.7 * np.abs(np.sin(np.arange(n) / 600.0))) * decay(n, 0.25)
    return normalize(x, 0.4)


@snd("cles", spatial=True)
def s_keys(rng):
    d = 0.6
    buf = np.zeros(int(SR * d))
    for _ in range(9):
        place(buf, sine(rng.uniform(2500, 5000), 0.06) * decay(int(0.06 * SR), 0.015) * 0.5, rng.uniform(0, 0.45))
    return normalize(buf, 0.6)


@snd("pile")
def s_battery(rng):
    n = int(SR * 0.35)
    x = sine(300, 0.35) * decay(n, 0.06) + 0.6 * sine(600, 0.35) * decay(n, 0.04)
    return normalize(x, 0.5)


@snd("piles_ok")
def s_battery_ok(rng):
    return normalize(mix(tone(660, 0.16), np.concatenate([np.zeros(int(0.09 * SR)), tone(880, 0.22)])), 0.5)


@snd("tonnerre")
def s_thunder(rng):
    d = 4.5
    n = int(SR * d)
    x = lowpass(rng.standard_normal(n), 300)
    env = np.concatenate([np.linspace(0, 1, int(0.15 * SR)), decay(n - int(0.15 * SR), 1.2)])
    env *= 0.7 + 0.3 * np.abs(np.sin(np.arange(n) / 4000.0))
    return normalize(x * env, 0.95)


@snd("coups_porte", spatial=True)
def s_knock(rng):
    n = int(SR * 0.9)
    x = np.sin(2 * np.pi * 70 * np.arange(n) / SR) * decay(n, 0.12)
    x += 0.7 * lowpass(rng.standard_normal(n), 500) * decay(n, 0.03)
    x += 0.3 * np.sin(2 * np.pi * 140 * np.arange(n) / SR) * decay(n, 0.08)
    return normalize(reverb(x, rng, 0.6, 0.35), 1.0)


@snd("grattement", spatial=True)
def s_scratch(rng):
    d = 1.4
    n = int(SR * d)
    t = taxis(d)
    x = highpass(rng.standard_normal(n), 1800) * (0.5 + 0.5 * np.sin(2 * np.pi * 6 * t)) ** 2
    x *= np.clip(np.sin(np.pi * t / d), 0, 1)
    return normalize(x, 0.5)


@snd("neige_tv", spatial=True)
def s_tv_static(rng):
    d = 1.6
    return normalize(rng.standard_normal(int(SR * d)) * adsr(int(SR * d), 0.01, 0.0, 1.0, 0.1), 0.65)


@snd("tv_clac", spatial=True)
def s_tv_pop(rng):
    n = int(SR * 0.2)
    x = lowpass(rng.standard_normal(n), 800) * decay(n, 0.04)
    x += 0.5 * np.sin(2 * np.pi * 15700 * np.arange(n) / SR) * 0.0
    return normalize(x, 0.9)


@snd("radio_gresillement", spatial=True)
def s_radio_crackle(rng):
    d = 3.0
    n = int(SR * d)
    x = bandpass(rng.standard_normal(n), 300, 5000) * 0.5
    t = taxis(d)
    gate = (np.sin(2 * np.pi * 2.3 * t) > 0.2).astype(float)
    x += 0.3 * np.sin(2 * np.pi * (700 + 300 * np.sin(2 * np.pi * 0.8 * t)) * t) * gate
    return normalize(x, 0.6)


@snd("tic_interrupteur")
def s_switch(rng):
    n = int(SR * 0.06)
    x = bandpass(rng.standard_normal(n), 800, 4000) * decay(n, 0.008)
    return normalize(x, 0.5)


# ---------------------------------------------------------------------------
# Téléphone
# ---------------------------------------------------------------------------
@snd("vibration")
def s_vibration(rng):
    d = 0.7
    buf = np.zeros(int(SR * d))
    for t in (0.0, 0.3):
        n = int(SR * 0.22)
        x = np.sin(2 * np.pi * 150 * np.arange(n) / SR) * np.sign(np.sin(2 * np.pi * 28 * np.arange(n) / SR)) * adsr(n, 0.01, 0.0, 1.0, 0.04)
        place(buf, x, t)
    return normalize(buf, 0.7)


@snd("notification")
def s_notif(rng):
    return normalize(mix(tone(1000, 0.12, (1.0, 0.2)), np.concatenate([np.zeros(int(0.1 * SR)), tone(1320, 0.18, (1.0, 0.2))])), 0.5)


@snd("sonnerie", loop=True)
def s_ring(rng):
    d = 3.0
    buf = np.zeros(int(SR * d))
    n = int(SR * 1.5)
    x = (np.sin(2 * np.pi * 440 * np.arange(n) / SR) + np.sin(2 * np.pi * 480 * np.arange(n) / SR)) * 0.5
    x *= adsr(n, 0.01, 0.0, 1.0, 0.02)
    place(buf, x, 0.0)
    return normalize(buf, 0.45)


@snd("bip_fin")
def s_end_beep(rng):
    return normalize(tone(950, 0.35, (1.0,)), 0.5)


@snd("scan_bip")
def s_scan_beep(rng):
    n = int(SR * 0.09)
    return normalize(sine(2900, 0.09) * adsr(n, 0.002, 0.0, 1.0, 0.01), 0.35)


@snd("caisse_ok")
def s_checkout_ok(rng):
    return normalize(melody([76, 81, 84], 0.12, (1.0, 0.3)), 0.4)


@snd("antivol")
def s_alarm(rng):
    t = taxis(1.2)
    x = square(1800, 1.2) * (np.sin(2 * np.pi * 4 * t) > 0)
    return normalize(lowpass(x, 5000) * adsr(len(x), 0.005, 0.0, 1.0, 0.05), 0.4)


@snd("paiement_nfc")
def s_nfc(rng):
    return normalize(melody([88, 93], 0.09, (1.0,)), 0.35)


@snd("klaxon")
def s_horn(rng):
    t = taxis(0.45)
    x = saw(410, 0.45) + 0.8 * saw(500, 0.45)
    return normalize(lowpass(x, 2600) * adsr(len(t), 0.01, 0.05, 0.9, 0.05), 0.6)


@snd("sirene_courte")
def s_siren_chirp(rng):
    t = taxis(0.9)
    f = 700 + 600 * np.clip(np.sin(np.pi * t / 0.9), 0, 1)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return normalize(x * adsr(len(t), 0.02, 0.0, 1.0, 0.15), 0.5)


@snd("porte_auto")
def s_auto_door(rng):
    n = int(SR * 0.8)
    x = bandpass(rng.standard_normal(n), 200, 1800) * adsr(n, 0.15, 0.2, 0.5, 0.3)
    return normalize(x, 0.25)


@snd("briquet")
def s_lighter(rng):
    n = int(SR * 0.5)
    x = bandpass(rng.standard_normal(n), 2000, 9000) * decay(n, 0.02)
    x[int(SR * 0.08):] += bandpass(rng.standard_normal(n - int(SR * 0.08)), 300, 2500) * 0.3 * decay(n - int(SR * 0.08), 0.25)
    return normalize(x, 0.4)


@snd("ui_hover")
def s_ui_hover(rng):
    n = int(SR * 0.05)
    return normalize(sine(1300, 0.05) * decay(n, 0.012) * 0.6 + bandpass(rng.standard_normal(n), 2000, 7000) * decay(n, 0.01) * 0.2, 0.18)


@snd("ui_click")
def s_ui_click(rng):
    n = int(SR * 0.09)
    x = sine(520, 0.09) * decay(n, 0.02) + 0.5 * sine(260, 0.09) * decay(n, 0.03)
    x += bandpass(rng.standard_normal(n), 1500, 6000) * decay(n, 0.006) * 0.4
    return normalize(x, 0.32)


@snd("ui_open")
def s_ui_open(rng):
    n = int(SR * 0.28)
    t = taxis(0.28)
    f = np.interp(t, [0, 0.28], [300, 620])
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * adsr(n, 0.01, 0.05, 0.5, 0.15)
    return normalize(lowpass(x, 3000), 0.3)


@snd("tap")
def s_tap(rng):
    n = int(SR * 0.04)
    return normalize(sine(1800, 0.04) * decay(n, 0.01), 0.25)


@snd("envoi")
def s_send(rng):
    return normalize(np.concatenate([tone(700, 0.07, (1.0,)), tone(1100, 0.1, (1.0,))]), 0.35)


@snd("erreur")
def s_error(rng):
    return normalize(np.concatenate([tone(300, 0.14, (1.0, 0.4)), np.zeros(int(0.04 * SR)), tone(220, 0.22, (1.0, 0.4))]), 0.5)


@snd("paiement")
def s_pay(rng):
    return normalize(np.concatenate([tone(520, 0.1), tone(660, 0.1), tone(780, 0.18)]), 0.4)


@snd("gps_bip")
def s_gps(rng):
    return normalize(tone(1500, 0.08, (1.0,)), 0.3)


# ---------------------------------------------------------------------------
# Entités et jumpscares
# ---------------------------------------------------------------------------
@snd("pas_entite", spatial=True)
def s_entity_step(rng):
    n = int(SR * 0.4)
    x = np.sin(2 * np.pi * 55 * np.arange(n) / SR) * decay(n, 0.1)
    x += 0.6 * bandpass(rng.standard_normal(n), 80, 700) * decay(n, 0.06)
    return normalize(x, 0.9)


@snd("glissement_humide", spatial=True)
def s_wet_slide(rng):
    d = 0.9
    n = int(SR * d)
    t = taxis(d)
    x = bandpass(rng.standard_normal(n), 200, 1800) * (0.5 + 0.5 * np.sin(2 * np.pi * 7 * t + 1)) ** 2
    x *= np.clip(np.sin(np.pi * t / d), 0, 1)
    return normalize(x, 0.7)


@snd("os_craquent", spatial=True)
def s_bones(rng):
    d = 0.7
    buf = np.zeros(int(SR * d))
    for _ in range(6):
        c = bandpass(rng.standard_normal(int(0.012 * SR)), 900, 4500) * rng.uniform(0.5, 1.0)
        place(buf, c, rng.uniform(0, 0.6))
    return normalize(reverb(buf, rng, 0.35, 0.4), 0.8)


@snd("respiration_saccadee", spatial=True)
def s_ragged_breath(rng):
    d = 1.6
    buf = np.zeros(int(SR * d))
    for t in (0.0, 0.35, 0.6, 1.0):
        n = int(SR * 0.25)
        place(buf, bandpass(rng.standard_normal(n), 200, 1500) * np.sin(np.pi * np.arange(n) / n), t)
    return normalize(buf, 0.6)


@snd("stinger_alerte")
def s_stinger_alert(rng):
    n = int(SR * 0.9)
    x = (np.sin(2 * np.pi * 1760 * np.arange(n) / SR) + 0.6 * np.sin(2 * np.pi * 1865 * np.arange(n) / SR)) * decay(n, 0.25)
    return normalize(x, 0.55)


@snd("stinger_jumpscare")
def s_stinger(rng):
    d = 0.9
    n = int(SR * d)
    t = taxis(d)
    x = np.zeros(n)
    for f in (200, 317, 450, 633):
        x += np.sin(2 * np.pi * f * t) * 0.5
    x += 0.4 * rng.standard_normal(n)
    env = np.concatenate([np.linspace(0, 1, int(0.03 * SR)), decay(n - int(0.03 * SR), 0.28)])
    return normalize(x * env, 1.0)


@snd("cri")
def s_scream(rng):
    d = 1.2
    n = int(SR * d)
    t = taxis(d)
    f = np.interp(t, [0, 0.15, d], [600, 1500, 700]) * (1 + 0.04 * np.sin(2 * np.pi * 30 * t))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.6 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    x = x * (0.5 + 0.5 * rng.standard_normal(n) * 0.5) * np.sin(2 * np.pi * 70 * t)
    x += bandpass(rng.standard_normal(n), 1000, 5000) * 0.5
    return normalize(x * decay(n, 0.5), 1.0)


@snd("impact")
def s_impact(rng):
    n = int(SR * 1.0)
    x = np.sin(2 * np.pi * 48 * np.arange(n) / SR) * decay(n, 0.25)
    x += lowpass(rng.standard_normal(n), 400) * decay(n, 0.06)
    return normalize(x, 1.0)


@snd("woosh_flamme")
def s_flame(rng):
    d = 1.0
    n = int(SR * d)
    x = bandpass(rng.standard_normal(n), 300, 3500)
    env = np.concatenate([np.linspace(0, 1, int(0.15 * SR)), decay(n - int(0.15 * SR), 0.35)])
    return normalize(x * env, 0.85)


@snd("sourd_mort")
def s_dull(rng):
    n = int(SR * 1.5)
    x = np.sin(2 * np.pi * 38 * np.arange(n) / SR) * decay(n, 0.5)
    return normalize(lowpass(x, 200), 0.9)


@snd("disparition")
def s_vanish(rng):
    n = int(SR * 0.6)
    x = bandpass(rng.standard_normal(n), 800, 6000) * decay(n, 0.15)
    return normalize(x, 0.6)


@snd("flash_clone")
def s_clone_flash(rng):
    n = int(SR * 0.5)
    x = np.sin(2 * np.pi * np.cumsum(np.linspace(2200, 300, n)) / SR) * decay(n, 0.15)
    x += 0.4 * highpass(rng.standard_normal(n), 2000) * decay(n, 0.05)
    return normalize(x, 0.7)


@snd("etoile")
def s_star(rng):
    return normalize(tone(1175, 0.2, (1.0, 0.3, 0.1)), 0.4)


@snd("voix_inversee")
def s_reversed_voice(rng):
    v = synth_voice("ou est tu adrien viens", 105, 0.8, False, 5)
    v = v[::-1]
    v = bandpass(v, 200, 3200)
    v += 0.05 * rng.standard_normal(len(v))
    return normalize(v, 0.7)


# ---------------------------------------------------------------------------
# Moteur de lecture
# ---------------------------------------------------------------------------
def _hash_text(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:12]


class SoundHandle:
    """Poignée vers un son en cours (une ou plusieurs AudioSound)."""

    def __init__(self, engine, sound, channel, base_volume, loop=False, muffled=None):
        self.engine = engine
        self.sound = sound
        self.muffled = muffled
        self.channel = channel
        self.base = base_volume
        self.loop = loop
        self.pos = None
        self.ref = 3.0
        self.fade_target = None
        self.fade_speed = 1.0
        self.level = 1.0            # niveau de fondu courant
        self.occ_mix = 0.0          # 0 = clair, 1 = étouffé
        self.pan = 0.0
        self.atten = 1.0
        self.alive = True
        self.stop_after_fade = False

    def _apply(self):
        if not self.alive:
            return
        vol = self.base * self.level * self.atten * config.settings.volume(self.channel)
        try:
            if self.muffled is not None:
                self.sound.setVolume(max(0.0, vol * (1 - self.occ_mix)))
                self.muffled.setVolume(max(0.0, vol * self.occ_mix * 1.1))
                self.muffled.setBalance(self.pan)
            else:
                self.sound.setVolume(max(0.0, vol))
            self.sound.setBalance(self.pan)
        except Exception:
            pass

    def set_volume(self, v):
        self.base = v
        self._apply()

    def fade_to(self, target, speed=1.0, stop=False):
        self.fade_target = target
        self.fade_speed = speed
        self.stop_after_fade = stop

    def stop(self):
        self.alive = False
        try:
            self.sound.stop()
            if self.muffled is not None:
                self.muffled.stop()
        except Exception:
            pass

    def is_playing(self):
        try:
            return self.sound.status() == self.sound.PLAYING
        except Exception:
            return False

    def update(self, dt, listener_pos, listener_yaw):
        if not self.alive:
            return
        if self.fade_target is not None:
            if abs(self.level - self.fade_target) <= self.fade_speed * dt:
                self.level = self.fade_target
                self.fade_target = None
                if self.stop_after_fade and self.level <= 0.001:
                    self.stop()
                    return
            else:
                self.level += math.copysign(self.fade_speed * dt, self.fade_target - self.level)
        if self.pos is not None and listener_pos is not None:
            self.engine._spatialize(self, listener_pos, listener_yaw, dt)
        self._apply()


class SoundEngine:
    def __init__(self):
        self.dir = config.cache_dir("snd")
        self.paths = {}
        self.pool = {}
        self.handles = []
        self.occluder = None      # callable(a, b) -> nombre de murs entre a et b
        self.listener_pos = None
        self.listener_yaw = 0.0
        self.enabled = True
        self.subtitle_cb = None
        self._loader = None
        self.heart_bpm = 0.0
        self._heart_t = 0.0
        self.breath_mode = None   # None | 'calm' | 'heavy'
        self._breath_t = 0.0
        self.music = AdaptiveMusic(self)
        self._voice_cache = {}

    # --- génération --------------------------------------------------------
    def iter_generate(self):
        total = len(_SOUNDS)
        for i, (name, spec) in enumerate(_SOUNDS.items()):
            path = os.path.join(self.dir, name + ".wav")
            mpath = os.path.join(self.dir, name + "_m.wav")
            if not os.path.exists(path) or (spec["spatial"] and not os.path.exists(mpath)):
                seed = sum(ord(c) * (k + 3) for k, c in enumerate(name)) + 4242
                rng = np.random.default_rng(seed)
                x = spec["fn"](rng)
                x = fade_edges(x, 3) if not spec["loop"] else x
                write_wav(path, x)
                if spec["spatial"]:
                    write_wav(mpath, lowpass(x, 550) * 1.15)
            self.paths[name] = path
            if spec["spatial"]:
                self.paths[name + "_m"] = mpath
            yield i + 1, total, name

    def generate_all(self):
        for _ in self.iter_generate():
            pass

    # --- lecture -----------------------------------------------------------
    def _get_loader(self):
        if self._loader is None:
            from ursina import application
            self._loader = application.base.loader
        return self._loader

    def _load(self, name):
        from panda3d.core import Filename
        path = self.paths.get(name)
        if path is None:
            return None
        fn = Filename.from_os_specific(path)
        try:
            return self._get_loader().loadSfx(fn)
        except Exception:
            return None

    def _acquire(self, name, loop=False):
        """Retourne un AudioSound libre pour ce son (pool)."""
        pool = self.pool.setdefault(name, [])
        for s in pool:
            try:
                if s.status() != s.PLAYING:
                    return s
            except Exception:
                continue
        if len(pool) >= 6:
            s = pool.pop(0)
            try:
                s.stop()
            except Exception:
                pass
            pool.append(s)
            return s
        s = self._load(name)
        if s is not None:
            pool.append(s)
        return s

    def _spatialize(self, h, lpos, lyaw, dt):
        dx = h.pos[0] - lpos[0]
        dy = (h.pos[1] - lpos[1]) * 0.7
        dz = h.pos[2] - lpos[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        walls = 0
        if self.occluder is not None and h.muffled is not None:
            try:
                walls = self.occluder(lpos, h.pos)
            except Exception:
                walls = 0
        target_occ = min(1.0, walls * 0.7)
        h.occ_mix += (target_occ - h.occ_mix) * min(1.0, dt * 8.0)
        h.atten = 1.0 / (1.0 + (dist / h.ref) ** 2) * (0.75 ** walls)
        ang = math.atan2(dx, dz) - math.radians(lyaw)
        pan = math.sin(ang)
        h.pan = max(-1.0, min(1.0, pan * min(1.0, dist / 1.5)))

    def play(self, name, volume=1.0, pitch=1.0, channel="sfx", loop=False):
        if not self.enabled or name not in self.paths:
            return None
        s = self._acquire(name)
        if s is None:
            return None
        try:
            s.setLoop(loop)
            s.setPlayRate(pitch)
        except Exception:
            pass
        h = SoundHandle(self, s, channel, volume, loop)
        h._apply()
        try:
            s.play()
        except Exception:
            pass
        if loop:
            self.handles.append(h)
        return h

    def play_at(self, name, pos, volume=1.0, pitch=1.0, channel="sfx", ref=3.0):
        """Son 3D ponctuel (atténuation, pan, occlusion)."""
        if not self.enabled or name not in self.paths:
            return None
        lpos = self.listener_pos
        use_m = (name + "_m") in self.paths
        walls = 0
        if lpos is not None and self.occluder is not None and use_m:
            try:
                walls = self.occluder(lpos, pos)
            except Exception:
                walls = 0
        real = name + "_m" if (walls > 0 and use_m) else name
        s = self._acquire(real)
        if s is None:
            return None
        try:
            s.setLoop(False)
            s.setPlayRate(pitch)
        except Exception:
            pass
        h = SoundHandle(self, s, channel, volume)
        h.pos = pos
        h.ref = ref
        if lpos is not None:
            self._spatialize(h, lpos, self.listener_yaw, 1.0)
            h.occ_mix = 0.0
        h._apply()
        try:
            s.play()
        except Exception:
            pass
        return h

    def loop(self, name, volume=1.0, channel="music", pos=None, fade_in=0.0, ref=3.0):
        """Boucle (éventuellement spatiale). Retourne un SoundHandle."""
        if not self.enabled or name not in self.paths:
            return None
        s = self._load(name)
        if s is None:
            return None
        m = None
        if pos is not None and (name + "_m") in self.paths:
            m = self._load(name + "_m")
        try:
            s.setLoop(True)
            if m is not None:
                m.setLoop(True)
        except Exception:
            pass
        h = SoundHandle(self, s, channel, volume, True, m)
        h.pos = pos
        h.ref = ref
        if fade_in > 0:
            h.level = 0.0
            h.fade_to(1.0, 1.0 / fade_in)
        h._apply()
        try:
            s.play()
            if m is not None:
                m.play()
        except Exception:
            pass
        self.handles.append(h)
        return h

    def stop_all(self):
        for h in list(self.handles):
            h.stop()
        self.handles.clear()
        for pool in self.pool.values():
            for s in pool:
                try:
                    s.stop()
                except Exception:
                    pass
        self.music.reset()

    # --- voix --------------------------------------------------------------
    def voice_path(self, text, f0=120, speed=1.0, whisper=False, reverse=False, distort=False):
        key = f"{text}|{f0}|{speed}|{whisper}|{reverse}|{distort}"
        name = "voix_" + _hash_text(key)
        if name in self.paths:
            return name
        path = os.path.join(self.dir, name + ".wav")
        if not os.path.exists(path):
            x = synth_voice(text, f0, speed, whisper, seed=len(text))
            if distort:
                rng = np.random.default_rng(3)
                x = x * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * taxis(len(x) / SR)[:len(x)]))
                x = bandpass(x, 250, 3000) + 0.06 * rng.standard_normal(len(x))
            if reverse:
                x = x[::-1]
            write_wav(path, normalize(x, 0.8))
        self.paths[name] = path
        mp = os.path.join(self.dir, name + "_m.wav")
        if not os.path.exists(mp):
            x = _read_wav(path)
            write_wav(mp, lowpass(x, 550) * 1.15)
        self.paths[name + "_m"] = mp
        return name

    def speak(self, text, f0=120, speed=1.0, whisper=False, pos=None, volume=1.0,
              channel="voice", distort=False, reverse=False, subtitle=True, speaker=None):
        if subtitle and self.subtitle_cb and config.settings["sous_titres"]:
            try:
                self.subtitle_cb(text, speaker)
            except Exception:
                pass
        if not self.enabled:
            return None
        name = self.voice_path(text, f0, speed, whisper, reverse, distort)
        if pos is not None:
            return self.play_at(name, pos, volume, channel=channel, ref=4.0)
        return self.play(name, volume, channel=channel)

    # --- mise à jour -------------------------------------------------------
    def set_listener(self, pos, yaw):
        self.listener_pos = pos
        self.listener_yaw = yaw

    def set_heart(self, bpm):
        self.heart_bpm = bpm

    def set_breath(self, mode):
        self.breath_mode = mode

    def update(self, dt):
        for h in list(self.handles):
            if not h.alive:
                self.handles.remove(h)
                continue
            h.update(dt, self.listener_pos, self.listener_yaw)
        # Battement de cœur
        if self.heart_bpm > 20:
            self._heart_t -= dt
            if self._heart_t <= 0:
                vol = min(1.0, 0.25 + self.heart_bpm / 220.0)
                self.play("heartbeat", vol, channel="sfx")
                self._heart_t = 60.0 / self.heart_bpm
        # Respiration
        if self.breath_mode:
            self._breath_t -= dt
            if self._breath_t <= 0:
                if self.breath_mode == "heavy":
                    self.play("respiration_lourde", 0.9, pitch=1.0, channel="sfx")
                    self._breath_t = 0.9
                else:
                    self.play("respiration_calme", 0.5, channel="sfx")
                    self._breath_t = 2.8
        self.music.update(dt)


def _read_wav(path):
    with wave.open(path, "rb") as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return data.astype(np.float64) / 32767.0


class AdaptiveMusic:
    """Musique dynamique liée à l'état de l'IA de l'entité.

    patrouille : drone discret • alerte : stinger + drone plus fort •
    poursuite : cordes dissonantes (+ cœur rapide géré par le moteur) •
    recherche : drone seul • embuscade : silence total.
    """

    LAYERS = {
        #             drone  cordes  coeur_geant
        "none":      (0.00, 0.00, 0.00),
        "ambient":   (0.10, 0.00, 0.00),
        "patrol":    (0.14, 0.00, 0.00),
        "alert":     (0.30, 0.08, 0.00),
        "chase":     (0.35, 0.65, 0.00),
        "search":    (0.22, 0.00, 0.00),
        "ambush":    (0.00, 0.00, 0.00),
        "countdown": (0.25, 0.00, 0.5),
        "basement":  (0.0, 0.0, 0.0),
    }

    def __init__(self, engine):
        self.engine = engine
        self.state = "none"
        self.vols = [0.0, 0.0, 0.0]
        self.handles = [None, None, None]
        self.started = False
        self.names = ["drone", "cordes_poursuite", "coeur_geant"]

    def _start(self):
        if self.started:
            return
        for i, n in enumerate(self.names):
            self.handles[i] = self.engine.loop(n, 0.0, channel="music")
        self.started = True

    def reset(self):
        self.started = False
        self.handles = [None, None, None]
        self.vols = [0.0, 0.0, 0.0]
        self.state = "none"

    def set_state(self, state, stinger=True):
        if state == self.state:
            return
        prev = self.state
        self.state = state
        self._start()
        if stinger and state == "alert" and prev in ("patrol", "search", "ambient", "none"):
            self.engine.play("stinger_alerte", 0.6, channel="music")
        if stinger and state == "chase" and prev != "chase":
            self.engine.play("stinger_alerte", 0.8, channel="music", pitch=0.8)

    def update(self, dt):
        if not self.started:
            return
        target = self.LAYERS.get(self.state, self.LAYERS["none"])
        for i in range(3):
            speed = 0.5 if target[i] > self.vols[i] else 1.2
            if self.state == "ambush":
                speed = 2.5
            self.vols[i] += (target[i] - self.vols[i]) * min(1.0, dt * speed)
            h = self.handles[i]
            if h is not None:
                h.set_volume(self.vols[i])


engine = SoundEngine()
