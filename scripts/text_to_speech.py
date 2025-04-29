# scripts/text_to_speech.py
"""
Generate MP3 voice-overs (and word-level timestamp JSON) from rewritten
Reddit scripts.

• Supports **ElevenLabs** (high-quality, Adam voice, timestamp JSON)
• Supports **gTTS** (offline / free fallback, no timestamps)
• Speeds audio up with ffmpeg (pitch-correct)
• After success moves the processed scripts_*.json → data/processed/scripts/

Folder layout it expects:

data/
 ├─ scripts/               ← ready-to-voice scripts_*.json
 ├─ processed/scripts/     ← auto-moved after voicing
 ├─ audio/                 ← .mp3 (and .json timestamps)
 └─ video/ …
"""
import os, json, time, shutil, subprocess, requests
from pathlib import Path
from gtts import gTTS
import base64
import requests, json
from pathlib import Path

# ─── Config ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[1]
SCRIPT_DIR  = ROOT / "data" / "scripts"
PROC_DIR    = ROOT / "data" / "processed" / "scripts"
AUDIO_DIR   = ROOT / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


USE_ELEVEN  = True                      # False → gTTS
SPEED_UP    = 1.10                      # 10 % faster (1.0 = off)

# ElevenLabs
EL_KEY      = "sk_a6d7314836f60c4c0e217a9e466cd3ec6aed63da2d181335"
VOICE_ID    = "pNInz6obpgDQGcFmaJgB"    # “Adam” voice
HEADERS     = {"xi-api-key": EL_KEY, "Content-Type": "application/json"}

HEADERS  = {"xi-api-key": EL_KEY, "Content-Type": "application/json"}
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"


# ─── Helpers ───────────────────────────────────────────────────────────────────
def save_elevenlabs(text: str, out_mp3: Path):
    """Fetch MP3 + word-timestamps JSON from ElevenLabs in one call."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"

    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
        "output_format": "json",     # <-- ask for JSON wrapper
        "timestamps": "word"         # <-- include word-level timings
    }

    resp = requests.post(url, headers=HEADERS, json=payload)
    resp.raise_for_status()
    blob = resp.json()              # { "audio": "<base64…>", "words":[…] }

    # ---- save MP3 ----
    audio_bytes = base64.b64decode(blob["audio"])
    with out_mp3.open("wb") as f:
        f.write(audio_bytes)

    # ---- save timestamps JSON (if present) ----
    words = blob.get("words") or blob.get("alignment", {}).get("words")
    if words:
        out_json = out_mp3.with_suffix(".json")
        out_json.write_text(json.dumps(words, indent=2))
    else:
        print(f"[WARN] ElevenLabs returned no word timestamps for {out_mp3.stem}")

def save_gtts(text: str, out_mp3: Path):
    tts = gTTS(text, lang="en")
    tts.save(str(out_mp3))

def speed_up_audio(mp3_path: Path, factor: float = 1.10):
    if factor == 1.0:
        return
    temp = mp3_path.with_suffix(".tmp.mp3")
    cmd  = ["ffmpeg", "-y", "-i", str(mp3_path),
            "-filter:a", f"atempo={factor:.3f}", str(temp)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    temp.replace(mp3_path)

# ─── Main routine ──────────────────────────────────────────────────────────────
def voice_batch(max_scripts: int = 10):
    if not any(SCRIPT_DIR.glob("scripts_*.json")):
        print("[!]  no script files to voice")
        return

    for script_file in sorted(SCRIPT_DIR.glob("scripts_*.json")):
        data = json.loads(script_file.read_text())
        processed = 0

        for item in data:
            if processed >= max_scripts:
                break
            post_id = item["id"]
            text    = item["script"].strip()
            if len(text) < 10:
                continue

            mp3_path = AUDIO_DIR / f"{post_id}.mp3"
            if mp3_path.exists():
                print(f"[-]  {post_id} already voiced")
                continue

            print(f"[+]  voicing {post_id} …")
            try:
                if USE_ELEVEN:
                    save_elevenlabs(text, mp3_path)
                else:
                    save_gtts(text, mp3_path)

                speed_up_audio(mp3_path, SPEED_UP)
                processed += 1
                time.sleep(1)      # gentle on API
            except Exception as e:
                print(f"[ERR] {post_id}: {e}")

        # move script file whether fully or partially processed
        PROC_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(script_file, PROC_DIR / script_file.name)
        print(f"[⮕]  moved {script_file.name} to processed/")
        break                 # only 1 JSON per run to save quota

if __name__ == "__main__":
    voice_batch()
