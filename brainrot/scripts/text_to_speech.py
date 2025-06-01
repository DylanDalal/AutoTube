# scripts/text_to_speech.py

import os
import json
import time
import requests
from gtts import gTTS
import shutil
import subprocess
import librosa


os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ["PATH"]

# ─── Configuration ─────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(ROOT_DIR, 'data', 'scripts')
AUDIO_DIR = os.path.join(ROOT_DIR, 'data', 'audio')
MAX_VOICES = 50  # Number of scripts to process per run
USE_ELEVENLABS = True  # Toggle between ElevenLabs and gTTS

# ElevenLabs settings
ELEVENLABS_VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # 'Adam' voice (default ID for Adam)

# ─── Setup folders ─────────────────────────────────────────────────────────────
os.makedirs(AUDIO_DIR, exist_ok=True)

# ─── ElevenLabs Voiceover ───────────────────────────────────────────────────────
def generate_voice_elevenlabs(text, filename):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        out_path = os.path.join(AUDIO_DIR, filename)
        with open(out_path, "wb") as f:
            f.write(response.content)
        print(f"[Saved] {filename}")
    else:
        print(f"[ERROR] Failed to generate voice with ElevenLabs: {response.status_code}, {response.text}")

# ─── gTTS Voiceover (Free) ───────────────────────────────────────────────────────
def generate_voice_gtts(text, filename):
    try:
        tts = gTTS(text, lang='en')
        out_path = os.path.join(AUDIO_DIR, filename)
        tts.save(out_path)
        print(f"[Saved] {filename}")
    except Exception as e:
        print(f"[ERROR] gTTS failed: {e}")

def speed_up_audio(filepath, speed_factor=1.28):
    temp_path = filepath.replace(".mp3", "_temp.mp3")
    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"  # OR whatever `which ffmpeg` gives you

    command = [
        ffmpeg_path,
        "-i", filepath,
        "-filter:a", f"atempo={speed_factor}",
        "-y",
        temp_path
    ]

    try:
        subprocess.run(command, check=True)
        os.replace(temp_path, filepath)
        print(f"[Adjusted Speed] {filepath}")
    except subprocess.CalledProcessError:
        print(f"[ERROR] Failed to adjust speed for {filepath}")

def convert_to_wav(mp3_path: str) -> str:
    """
    Converts MP3 to clean 16kHz mono WAV file for WhisperX.
    Returns the new WAV file path.
    """
    wav_path = mp3_path.replace(".mp3", ".wav")
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i", mp3_path,
        "-ar", "16000",
        "-ac", "1",
        wav_path
    ]
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return wav_path
    except subprocess.CalledProcessError:
        print(f"[ERROR] Failed to convert {mp3_path} to WAV.")
        return None


def make_subtitle_json(audio_path, original_text):
    """
    Aligns spoken audio to text using WhisperX and saves word-level timing JSON
    next to the MP3 file (e.g., 1ehlrdd.json for 1ehlrdd.mp3)
    """
    import whisperx
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        # Convert MP3 to clean WAV first
        wav_path = convert_to_wav(audio_path)
        if not wav_path:
            return False

        print(f"[INFO] WhisperX aligning using WAV: {wav_path}")
        # Load ASR and alignment models
        asr_model = whisperx.load_model("large-v3", device=device, compute_type="float32")
        align_model, metadata = whisperx.load_align_model(language_code="en", device=device)

        # Dummy segmentation to force alignment of full text
        duration = librosa.get_duration(path=wav_path)
        segments = [{"text": original_text, "start": 0, "end": duration}]
        alignment = whisperx.align(segments, align_model, metadata, wav_path, device)

        # Save word-level timestamp JSON
        word_data = alignment.get("word_segments", [])
        json_path = audio_path.replace(".mp3", ".json")
        with open(json_path, "w") as f:
            json.dump(word_data, f, indent=2)

        print(f"[Saved] Subtitle JSON → {json_path}")
        return True

    except Exception as e:
        print(f"[ERROR] WhisperX alignment failed: {e}")
        return False

# ─── Main voiceover generator ────────────────────────────────────────────────────
def generate_voiceovers():
    scripts_files = sorted(
        [f for f in os.listdir(SCRIPTS_DIR) if f.startswith('scripts_') and f.endswith('.json')],
        reverse=True
    )

    if not scripts_files:
        print("[ERROR] No scripts found to process.")
        return

    # Only process the first available scripts_*.json
    for filename in scripts_files:
        if filename.startswith('scripts_') and filename.endswith('.json'):
            input_path = os.path.join(SCRIPTS_DIR, filename)
            with open(input_path, 'r') as f:
                scripts = json.load(f)

            print(f"\n[Processing] {filename} with {len(scripts)} script(s)...")

            count = 0
            for item in scripts:
                if count >= MAX_VOICES:
                    break

                story = item.get("script", "").strip()
                title = item.get("title", "").strip()
                post_id = item.get("id", "unknown")
                audio_filename = f"{post_id}.mp3"

                if not story or not title:
                    print(f"[Skipping] Missing title or script for post {post_id}")
                    continue

                # Combine title + story
                full_text = f"{title.strip().rstrip('.')}. {story.strip()}"

                if USE_ELEVENLABS:
                    generate_voice_elevenlabs(full_text, audio_filename)
                else:
                    generate_voice_gtts(full_text, audio_filename)

                count += 1
                speed_up_audio(os.path.join(AUDIO_DIR, audio_filename))

                try:
                    make_subtitle_json(os.path.join(AUDIO_DIR, audio_filename), full_text)
                except Exception as e:
                    print(f"Booboo {e}")

                time.sleep(1.5)

            print(f"\n[Completed] {count} voiceovers generated.\n")

            # Move processed JSON into /processed/scripts/
            processed_dir = os.path.join(ROOT_DIR, 'data', 'processed', 'scripts')
            os.makedirs(processed_dir, exist_ok=True)

            dest_path = os.path.join(processed_dir, filename)
            shutil.move(input_path, dest_path)

            print(f"[Moved] {filename} to {processed_dir}")

            break  # Process only one JSON per run

if __name__ == "__main__":
    generate_voiceovers()
