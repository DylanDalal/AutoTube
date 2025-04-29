# scripts/assemble_video.py  ── MoviePy 2.x compliant
import os, json
import moviepy as mpy               # new canonical import
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path


# ─── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR  = os.path.join(ROOT_DIR, "data", "audio")
SCRIPT_DIR = os.path.join(ROOT_DIR, "data", "processed", "scripts")
VIDEO_DIR  = os.path.join(ROOT_DIR, "data", "videos")
FINAL_DIR  = os.path.join(ROOT_DIR, "data", "final")
SYSTEM_ARIAL = Path("/System/Library/Fonts/Supplemental/Arial.ttf")

os.makedirs(FINAL_DIR, exist_ok=True)

# ─── Helper: safe TextClip using Pillow so no ImageMagick needed ───────────────
def make_word_clip(word, start, dur):
    return (
        mpy.TextClip(
            text       = word,
            font       = str(SYSTEM_ARIAL) if SYSTEM_ARIAL.exists() else "DejaVu-Sans",
            font_size  = 60,
            color      = "white",
            bg_color   = None,
            stroke_color="black",
            stroke_width= 10,
            method="label"
        )
        .with_position(("center", "bottom")) # new API
        .with_start(start)
        .with_duration(dur)
    )

# ─── Assemble a single video ───────────────────────────────────────────────────
def assemble_video(audio_fn, script_txt, bg_path):
    audio_path  = os.path.join(AUDIO_DIR, audio_fn)
    ts_path     = audio_path.replace(".mp3", ".json")
    audio       = mpy.AudioFileClip(audio_path)
    bg_video    = mpy.VideoFileClip(bg_path).subclipped(0, audio.duration).with_audio(audio)

    # --- load ElevenLabs word timestamps ---
    with open(ts_path) as jf:
        words_data = json.load(jf)

    word_clips = []
    for w in words_data:
        clip = mpy.TextClip(
            txt=w["word"],
            fontsize=60,
            font=str(SYSTEM_ARIAL) if SYSTEM_ARIAL.exists() else "DejaVu-Sans",
            color="white",
            bg_color="black",
            method="label"
        ).with_position(("center", "bottom")) \
         .with_start(w["start"]) \
         .with_duration(w["end"] - w["start"])
        word_clips.append(clip)

    final = mpy.CompositeVideoClip([bg_video, *word_clips])
    out   = os.path.join(FINAL_DIR, os.path.splitext(audio_fn)[0] + ".mp4")
    final.write_videofile(out, codec="libx264", audio_codec="aac", fps=30)


# ─── Batch runner ──────────────────────────────────────────────────────────────
def generate_final_videos():
    scripts_files = sorted(f for f in os.listdir(SCRIPT_DIR) if f.endswith(".json"))
    videos        = sorted(f for f in os.listdir(VIDEO_DIR)  if f.endswith(".mp4"))

    if not scripts_files or not videos:
        print("[ERROR] Missing scripts or background videos.")
        return

    bg_path = os.path.join(VIDEO_DIR, videos[0])           # always first gameplay clip
    scripts_fp = os.path.join(SCRIPT_DIR, scripts_files[0])

    with open(scripts_fp) as f:
        scripts = json.load(f)

    for entry in scripts:
        pid   = entry["id"]
        text  = entry["script"]
        mp3   = f"{pid}.mp3"
        if os.path.exists(os.path.join(AUDIO_DIR, mp3)):
            print(f"[PROCESS] {pid}")
            assemble_video(mp3, text, bg_path)
        else:
            print(f"[SKIP] No audio for {pid}")

if __name__ == "__main__":
    generate_final_videos()
