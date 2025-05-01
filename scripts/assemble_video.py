# scripts/assemble_video.py
import os
import json
import numpy as np
from pathlib import Path
import pyphen
from PIL import Image, ImageDraw, ImageFont

from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, VideoFileClip
from moviepy.video.fx import Crop

# ─── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT_DIR, "data", "audio")
SCRIPT_DIR = os.path.join(ROOT_DIR, "data", "processed", "scripts")
VIDEO_DIR = os.path.join(ROOT_DIR, "data", "videos")
FINAL_DIR = os.path.join(ROOT_DIR, "data", "final")
SYSTEM_ARIAL = Path("/Users/Dylan/Library/Fonts/Cachet-Bold.ttf")

os.makedirs(FINAL_DIR, exist_ok=True)
dic = pyphen.Pyphen(lang='en')

# ─── Utilities ─────────────────────────────────────────────────────────────────
def count_syllables(word):
    return dic.inserted(word).count('-') + 1

def group_words_by_syllables(words_data, target_syllables=4):
    groups = []
    current_group = []
    current_syllables = 0
    for word_data in words_data:
        word = word_data["word"]
        syllables = count_syllables(word)

        if current_syllables + syllables > target_syllables and current_group:
            groups.append(current_group)
            current_group = []
            current_syllables = 0

        current_group.append(word_data)
        current_syllables += syllables

    if current_group:
        groups.append(current_group)

    return groups

def make_highlight_clips(group, font_path, video_size):
    clips = []
    words = [w["word"] for w in group]
    font_size = 80
    font = ImageFont.truetype(font_path, font_size)
    w_img, _ = video_size

    total_text_width = sum(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(word + " ", font=font) for word in words)
    base_x = (w_img - total_text_width) // 2

    for i, word_data in enumerate(group):
        img = Image.new("RGBA", (w_img, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        x = base_x
        for j, word in enumerate(words):
            color = "yellow" if i == j else "white"
            for ox, oy in [(2, 2), (1, 1)]:
                draw.text((x + ox, 20 + oy), word, font=font, fill="black")
            draw.text((x, 20), word, font=font, fill=color)
            x += draw.textlength(word + " ", font=font)

        img_array = np.array(img)
        clip = ImageClip(img_array).with_position(("center", "center")) \
            .with_start(word_data["start"]) \
            .with_duration(word_data["end"] - word_data["start"]) \
            .resized(lambda t: 1.2 - 0.2 * min(t / 0.15, 1))

        clips.append(clip)
    return clips

def make_group_caption_clip_with_highlight(group, font_path, video_size, fontsize=80, start=0, end=1):
    """
    Create a single pop-in phrase clip with synced yellow highlights, supporting line wrapping.
    """
    font = ImageFont.truetype(font_path, fontsize)
    w_img, h_img = video_size
    max_width = int(w_img * 0.7)

    words = [w["word"] for w in group]
    word_widths = [ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(word + " ", font=font) for word in words]

    # Wrap text into lines
    lines = []
    current_line = []
    current_width = 0
    for word, width in zip(words, word_widths):
        if current_width + width > max_width and current_line:
            lines.append(current_line)
            current_line = []
            current_width = 0
        current_line.append(word)
        current_width += width
    if current_line:
        lines.append(current_line)

    img = Image.new("RGBA", (w_img, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    line_positions = {}
    y_start = 20
    spacing = 10

    for line_num, line_words in enumerate(lines):
        line_text = " ".join(line_words)
        total_line_width = sum(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(word + " ", font=font) for word in line_words)
        x = (w_img - total_line_width) // 2
        y = y_start + line_num * (fontsize + 20)

        for word in line_words:
            for ox, oy in [(2, 2), (1, 1)]:
                draw.text((x + ox, y + oy), word, font=font, fill="black")
            draw.text((x, y), word, font=font, fill="white")
            line_positions[word] = (x, y)
            x += draw.textlength(word + " ", font=font)

    base_clip = ImageClip(np.array(img)).with_position(("center", "center")).with_start(start).with_duration(end - start)
    # animated = base_clip.resized(lambda t: 1.2 - 0.2 * min(t / 0.15, 1))

    # Highlight overlays
    highlights = []
    for word_info in group:
        word = word_info["word"]
        if word not in line_positions:
            continue
        x, y = line_positions[word]
        w_overlay = Image.new("RGBA", (w_img, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(w_overlay)
        d.text((x, y), word, font=font, fill="yellow")
        highlight = ImageClip(np.array(w_overlay)).with_position(("center", "center")) \
            .with_start(word_info["start"]).with_duration(word_info["end"] - word_info["start"])
        highlights.append(highlight)

    return [base_clip] + highlights


def center_crop_to_shorts(clip, target_width=886, target_height=1920):
    w, h = clip.size
    if w / h > target_width / target_height:
        new_w = int(h * target_width / target_height)
        x1 = (w - new_w) // 2
        crop_fx = Crop(x1=x1, x2=x1 + new_w, y1=0, y2=h)
    else:
        new_h = int(w * target_height / target_width)
        y1 = (h - new_h) // 2
        crop_fx = Crop(x1=0, x2=w, y1=y1, y2=y1 + new_h)
    return crop_fx.apply(clip).resized((target_width, target_height))

# ─── Main Logic ────────────────────────────────────────────────────────────────
def assemble_video(audio_fn, script_txt, bg_path):
    audio_path = os.path.join(AUDIO_DIR, audio_fn)
    ts_path = audio_path.replace(".mp3", ".json")
    audio = AudioFileClip(audio_path)
    raw_video = VideoFileClip(bg_path)

    bg_video = center_crop_to_shorts(raw_video).subclipped(0, audio.duration).with_audio(audio)

    with open(ts_path) as jf:
        words_data = json.load(jf)

    text_clips = []
    for group in group_words_by_syllables(words_data):
        group_start = group[0]["start"]
        group_end = group[-1]["end"]

        clips = make_group_caption_clip_with_highlight(
            group,
            font_path=str(SYSTEM_ARIAL),
            video_size=bg_video.size,
            start=group_start,
            end=group_end
        )
        text_clips.extend(clips)

    if not text_clips:
        print("[WARN] No text clips were created. Final video will have no captions.")

    final = CompositeVideoClip([bg_video, *text_clips]).with_duration(audio.duration)
    out = os.path.join(FINAL_DIR, os.path.splitext(audio_fn)[0] + ".mp4")
    final.write_videofile(out, codec="libx264", audio_codec="aac", fps=30)

def generate_final_videos():
    scripts_files = sorted(f for f in os.listdir(SCRIPT_DIR) if f.endswith(".json"))
    videos = sorted(f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4"))

    if not scripts_files or not videos:
        print("[ERROR] Missing scripts or background videos.")
        return

    bg_path = os.path.join(VIDEO_DIR, videos[0])
    scripts_fp = os.path.join(SCRIPT_DIR, scripts_files[0])

    with open(scripts_fp) as f:
        scripts = json.load(f)

    for entry in scripts:
        pid = entry["id"]
        text = entry["script"]
        mp3 = f"{pid}.mp3"
        if os.path.exists(os.path.join(AUDIO_DIR, mp3)):
            print(f"[PROCESS] {pid}")
            assemble_video(mp3, text, bg_path)
        else:
            print(f"[SKIP] No audio for {pid}")

if __name__ == "__main__":
    generate_final_videos()
