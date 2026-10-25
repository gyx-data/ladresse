"""Synthèse vocale réelle (voix françaises du système) avec repli automatique sur la voix procédurale.

Moteurs, par ordre de préférence :
  * Windows : System.Speech (SAPI 5) piloté par PowerShell — utilise une voix française installée
    (ex. « Microsoft Hortense », « Paul », « Julie »). Aucune dépendance Python, fonctionne dans le .exe.
  * Linux : espeak-ng / espeak (si installé) ;  macOS : `say` (voix Thomas / Amélie).
  * Sinon : None -> le moteur sonore garde sa voix procédurale (formants).

Les fichiers sont générés en arrière-plan (un seul processus PowerShell pour tout un lot de répliques),
mis en cache sur disque (dossier cache/tts) et réutilisés d'une partie à l'autre. Tant qu'une réplique
n'est pas prête, l'appelant utilise la voix procédurale : le jeu ne bloque jamais.
"""
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave

import numpy as np

import config

ENGINE_VERSION = "1"
CREATE_NO_WINDOW = 0x08000000

# Script 100 % ASCII envoyé sur l'entrée standard (pas de fichier .ps1, pas de contournement de stratégie
# d'exécution) ; les chemins et les textes passent par une variable d'environnement et un JSON UTF-8.
_PS_SCRIPT = r"""
$JobsFile = $env:LADRESSE_TTS_JOBS
$Mode = $env:LADRESSE_TTS_MODE
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { Add-Type -AssemblyName System.Speech } catch { Write-Output 'NOSPEECH'; exit 2 }
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voices = @($s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'fr*' })
if ($Mode -eq 'probe') {
    foreach ($v in $voices) { Write-Output ('VOICE|' + $v.VoiceInfo.Name + '|' + $v.VoiceInfo.Gender) }
    if ($voices.Count -eq 0) { Write-Output 'NOVOICE' }
    $s.Dispose(); exit 0
}
if ($voices.Count -eq 0) { Write-Output 'NOVOICE'; $s.Dispose(); exit 3 }
$jobs = Get-Content -Raw -Encoding UTF8 -LiteralPath $JobsFile | ConvertFrom-Json
foreach ($j in $jobs) {
    try {
        $pick = $voices | Where-Object { $_.VoiceInfo.Gender.ToString() -eq $j.gender } | Select-Object -First 1
        if (-not $pick) { $pick = $voices[0] }
        $s.SelectVoice($pick.VoiceInfo.Name)
        $s.Rate = [int]$j.rate
        $s.Volume = 100
        $tmp = $j.path + '.part'
        $s.SetOutputToWaveFile($tmp)
        $s.Speak([string]$j.text)
        $s.SetOutputToNull()
        Move-Item -LiteralPath $tmp -Destination $j.path -Force
        Write-Output ('OK|' + $j.id)
    } catch {
        try { $s.SetOutputToNull() } catch {}
        Write-Output ('ERR|' + $j.id + '|' + $_.Exception.Message)
    }
}
$s.Dispose()
"""


_EL_URL = "https://api.elevenlabs.io/v1"


def _key(text, gender, rate):
    raw = f"{ENGINE_VERSION}|{text}|{gender}|{rate}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def read_wav_any(path, sr):
    """Lit un WAV PCM 8/16/24/32 bits, mono ou stéréo, et le rééchantillonne à `sr` (float -1..1)."""
    with wave.open(path, "rb") as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128.0) / 128.0
    elif sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16))
        v = np.where(v & 0x800000, v - 0x1000000, v)
        x = v.astype(np.float64) / 8388608.0
    else:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / 2147483648.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != sr and len(x) > 1:
        t_new = np.arange(int(len(x) * sr / rate)) * (rate / sr)
        x = np.interp(t_new, np.arange(len(x)), x)
    # retire les silences de début / fin (les voix SAPI en ajoutent)
    if len(x):
        thr = 0.01 * max(1e-6, np.max(np.abs(x)))
        nz = np.nonzero(np.abs(x) > thr)[0]
        if len(nz):
            a = max(0, nz[0] - int(0.02 * sr))
            b = min(len(x), nz[-1] + int(0.08 * sr))
            x = x[a:b]
    return x


class TTS:
    def __init__(self):
        self.dir = config.cache_dir("tts")
        self.backend = None          # 'sapi' | 'espeak' | 'say' | None
        self.voices = []             # [(nom, genre)]
        self.ready = {}              # clé -> chemin
        self.pending = set()
        self.failed = set()
        self.q = queue.Queue()
        self.lock = threading.Lock()
        self.status = "inactif"
        self._worker = None
        self._probe_done = threading.Event()

    # ------------------------------------------------------------------
    def start(self):
        """Détecte le moteur (en arrière-plan) puis traite la file de génération."""
        if self._worker is not None:
            return
        if not config.settings.get("voix_reelles", True):
            self.status = "désactivé"
            self._probe_done.set()
            return
        self._worker = threading.Thread(target=self._run, daemon=True, name="tts")
        self._worker.start()

    @property
    def available(self):
        return self.backend is not None

    def has_gender(self, gender):
        if self.backend in ("espeak", "espeak-ng", "say"):
            return True
        return any(g == gender for _, g in self.voices)

    def _probe_elevenlabs(self):
        """Try ElevenLabs API — returns True if usable."""
        import urllib.request, urllib.error
        key = config.settings.get("elevenlabs_key", "").strip()
        if not key:
            return False
        try:
            req = urllib.request.Request(f"{_EL_URL}/voices",
                                        headers={"xi-api-key": key, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            voices = data.get("voices", [])
            self._el_key = key
            self._el_voices = {"Male": None, "Female": None}
            vm = config.settings.get("elevenlabs_voice_m", "").strip()
            vf = config.settings.get("elevenlabs_voice_f", "").strip()
            if vm:
                self._el_voices["Male"] = vm
            if vf:
                self._el_voices["Female"] = vf
            for v in voices:
                labels = v.get("labels", {})
                lang = labels.get("language", "") or v.get("fine_tuning", {}).get("language", "")
                if "fr" in lang.lower() or "french" in lang.lower() or "multilingual" in v.get("model_id", "").lower():
                    gender = labels.get("gender", "").capitalize()
                    if gender == "Male" and not self._el_voices["Male"]:
                        self._el_voices["Male"] = v["voice_id"]
                    elif gender == "Female" and not self._el_voices["Female"]:
                        self._el_voices["Female"] = v["voice_id"]
            if not self._el_voices["Male"] and not self._el_voices["Female"]:
                for v in voices[:3]:
                    vid = v["voice_id"]
                    g = v.get("labels", {}).get("gender", "").capitalize()
                    if g == "Male" and not self._el_voices["Male"]:
                        self._el_voices["Male"] = vid
                    elif not self._el_voices["Female"]:
                        self._el_voices["Female"] = vid
            if not self._el_voices["Male"]:
                self._el_voices["Male"] = self._el_voices["Female"]
            if not self._el_voices["Female"]:
                self._el_voices["Female"] = self._el_voices["Male"]
            if self._el_voices["Male"] or self._el_voices["Female"]:
                self.backend = "elevenlabs"
                self.status = "ElevenLabs"
                return True
        except Exception:
            pass
        return False

    def _probe(self):
        if self._probe_elevenlabs():
            return
        if sys.platform.startswith("win"):
            out = self._powershell(None, "probe", timeout=25)
            if out is not None:
                vs = [ln.split("|")[1:] for ln in out.splitlines() if ln.startswith("VOICE|")]
                if vs:
                    self.voices = [(v[0], v[1] if len(v) > 1 else "") for v in vs]
                    self.backend = "sapi"
                    self.status = "voix Windows : " + ", ".join(v[0] for v in self.voices)
                    return
            self.status = "aucune voix française Windows installée (voix procédurale)"
            return
        if sys.platform == "darwin" and shutil.which("say"):
            self.backend = "say"
            self.status = "voix macOS"
            return
        for exe in ("espeak-ng", "espeak"):
            if shutil.which(exe):
                self.backend = exe
                self.status = exe
                return
        self.status = "aucun moteur vocal (voix procédurale)"

    def _run(self):
        try:
            self._probe()
        except Exception as e:                 # ne doit jamais casser le jeu
            self.status = f"erreur moteur vocal : {e}"
            self.backend = None
        self._probe_done.set()
        while True:
            job = self.q.get()
            batch = [job]
            t0 = time.time()
            while len(batch) < 60 and time.time() - t0 < 0.3:
                try:
                    batch.append(self.q.get(timeout=0.05))
                except queue.Empty:
                    pass
            if self.backend is None:
                with self.lock:
                    for j in batch:
                        self.pending.discard(j["id"])
                        self.failed.add(j["id"])
                continue
            try:
                self._generate(batch)
            except Exception:
                pass
            with self.lock:
                for j in batch:
                    self.pending.discard(j["id"])
                    if os.path.exists(j["path"]) and os.path.getsize(j["path"]) > 1000:
                        self.ready[j["id"]] = j["path"]
                    else:
                        self.failed.add(j["id"])

    # ------------------------------------------------------------------
    def _powershell(self, jobs_file, mode, timeout=120):
        env = dict(os.environ)
        env["LADRESSE_TTS_JOBS"] = jobs_file or ""
        env["LADRESSE_TTS_MODE"] = mode
        cmd = ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", "-"]
        kw = {}
        if sys.platform.startswith("win"):
            kw["creationflags"] = CREATE_NO_WINDOW
        try:
            r = subprocess.run(cmd, input=_PS_SCRIPT.encode("ascii"), capture_output=True, timeout=timeout, env=env, **kw)
            return r.stdout.decode("utf-8", "replace")
        except (OSError, subprocess.SubprocessError, UnicodeError):
            return None

    def _generate_elevenlabs(self, job):
        """Generate one voice line via ElevenLabs API, save as WAV."""
        import urllib.request, urllib.error, struct
        gender = job["gender"]
        vid = self._el_voices.get(gender) or self._el_voices.get("Female") or self._el_voices.get("Male")
        if not vid:
            return
        body = json.dumps({
            "text": job["text"],
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }).encode("utf-8")
        url = f"{_EL_URL}/text-to-speech/{vid}?output_format=pcm_22050"
        req = urllib.request.Request(url, data=body, headers={
            "xi-api-key": self._el_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                pcm = resp.read()
        except (urllib.error.URLError, OSError):
            return
        if len(pcm) < 200:
            return
        tmp = job["path"] + ".part"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(pcm)
        shutil.move(tmp, job["path"])

    def _generate(self, batch):
        if self.backend == "elevenlabs":
            for j in batch:
                try:
                    self._generate_elevenlabs(j)
                except Exception:
                    pass
            return
        if self.backend == "sapi":
            fd, jf = tempfile.mkstemp(suffix=".json", prefix="ladresse_jobs_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump([dict(id=j["id"], text=j["text"], path=j["path"], gender=j["gender"], rate=j["rate"]) for j in batch],
                          f, ensure_ascii=False)
            try:
                self._powershell(jf, "speak", timeout=30 + 6 * len(batch))
            finally:
                try:
                    os.remove(jf)
                except OSError:
                    pass
            return
        for j in batch:
            kw = {}
            if sys.platform.startswith("win"):
                kw["creationflags"] = CREATE_NO_WINDOW
            try:
                if self.backend == "say":
                    voice = "Thomas" if j["gender"] == "Male" else "Amelie"
                    tmp = j["path"] + ".aiff"
                    subprocess.run(["say", "-v", voice, "-o", tmp, j["text"]], capture_output=True, timeout=30)
                    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050", tmp, j["path"]], capture_output=True, timeout=30)
                    if os.path.exists(tmp):
                        os.remove(tmp)
                else:
                    voice = "fr+m3" if j["gender"] == "Male" else "fr+f3"
                    speed = str(int(165 + 12 * j["rate"]))
                    subprocess.run([self.backend, "-v", voice, "-s", speed, "-w", j["path"], j["text"]], capture_output=True,
                                   timeout=30, **kw)
            except (OSError, subprocess.SubprocessError):
                continue

    # ------------------------------------------------------------------
    def request(self, text, gender="Female", rate=0):
        """Retourne le chemin du WAV s'il est prêt, sinon met la réplique en file et retourne None."""
        text = (text or "").strip()
        if not text or self.status == "désactivé":
            return None
        k = _key(text, gender, rate)
        with self.lock:
            p = self.ready.get(k)
            if p is not None:
                return p
            if k in self.failed or k in self.pending:
                return None
            path = os.path.join(self.dir, k + ".wav")
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                self.ready[k] = path
                return path
            if self._probe_done.is_set() and self.backend is None:
                return None
            self.pending.add(k)
        self.q.put(dict(id=k, text=text, gender=gender, rate=int(rate), path=os.path.join(self.dir, k + ".wav")))
        return None

    def prewarm(self, items):
        """items : [(texte, genre, débit)] — prépare les répliques connues dès le démarrage."""
        for text, gender, rate in items:
            self.request(text, gender, rate)


tts = TTS()
