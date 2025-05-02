# scripts/assemble_video.py
import os
import json
import numpy as np
from pathlib import Path
import pyphen
from PIL import Image, ImageDraw, ImageFont
import random

from matplotlib.pyplot import title
from moviepy import AudioFileClip, CompositeVideoClip, ImageClip, VideoFileClip, vfx, TextClip, ColorClip, clips_array
from moviepy.video.fx import Crop, MultiplySpeed

# ─── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_DIR = os.path.join(ROOT_DIR, "data", "audio")
SCRIPT_DIR = os.path.join(ROOT_DIR, "data", "processed", "scripts")
VIDEO_DIR = os.path.join(ROOT_DIR, "data", "videos")
FINAL_DIR = os.path.join(ROOT_DIR, "data", "final")
SYSTEM_ARIAL = Path("/Users/Dylan/Library/Fonts/LuckiestGuy-Regular.ttf")

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

        # Always break group at the end of a sentence
        is_sentence_end = word.endswith(".")

        if current_syllables + syllables > target_syllables or is_sentence_end:
            if current_group:
                groups.append(current_group)
                current_group = []
                current_syllables = 0

        current_group.append(word_data)
        current_syllables += syllables

        if is_sentence_end:
            groups.append(current_group)
            current_group = []
            current_syllables = 0

    if current_group:
        groups.append(current_group)

    return groups

def make_highlight_clips(group, font_path, video_size):
    clips = []
    words = [w["word"] for w in group]
    font_size = 65
    font = ImageFont.truetype(font_path, font_size)
    w_img, _ = video_size

    total_text_width = sum(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(word + " ", font=font) for word in words) #word.upper() + " "
    base_x = (w_img - total_text_width) // 2.2

    for i, word_data in enumerate(group):
        img = Image.new("RGBA", (w_img, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        x = base_x
        for j, word in enumerate(words):
            word_upper = word #.upper()
            color = "yellow" if i == j else "white"

            # Shadow
            draw.text((x + 2, 22), word_upper, font=font, fill="black")

            # Main text with stroke
            draw.text((x, 20), word_upper, font=font, fill=color, stroke_width=50, stroke_fill="black")

            x += draw.textlength(word_upper + " ", font=font)

        img_array = np.array(img)
        clip = ImageClip(img_array).with_position(("center", "center")) \
            .with_start(word_data["start"]) \
            .with_duration(word_data["end"] - word_data["start"]) \
            .resized(lambda t: 1.2 - 0.2 * min(t / 0.15, 1))

        clips.append(clip)
    return clips

def create_imessage_style_title_clip(subreddit, title_text, words_data, video_size,
                                     font_path="/System/Library/Fonts/HelveticaNeue.ttc",
                                     bg_image_path="iMessageBubble.png"):
    # Load and resize background image to 80% width
    base_img = Image.open(bg_image_path).convert("RGBA")
    target_width = int(video_size[0] * 0.8)
    aspect_ratio = base_img.height / base_img.width
    resized_height = int(target_width * aspect_ratio)
    base_img = base_img.resize((target_width, resized_height))

    draw = ImageDraw.Draw(base_img)
    title_font = ImageFont.truetype("/System/Library/Fonts/SF-Pro-Text-Bold.otf", 48)
    meta_font = ImageFont.truetype("/System/Library/Fonts/SF-Pro-Text-Regular.otf", 32)

    # Wrap the title text within 90% of container width
    max_text_width = int(target_width * 0.9)
    lines = []
    current_line = ""
    for word in title_text.split():
        test_line = f"{current_line} {word}".strip()
        if draw.textlength(test_line, font=title_font) > max_text_width:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)

    # Title lines: left-align, slightly below the top bar
    left_padding = 50
    top_padding = 135
    line_spacing = 50
    for line in lines:
        draw.text((left_padding, top_padding), line, font=title_font, fill="black")
        top_padding += line_spacing

    # Top left subreddit label
    draw.text((left_padding, 60), f"{subreddit}", font=meta_font, fill="black")

    # Footer bar
    footer = f"From the {subreddit} community on Reddit"
    draw.text((left_padding, resized_height - 80), footer, font=meta_font, fill="gray")

    # Estimate title display time
    last_title_word = title_text.strip().split()[-1].lower().rstrip(".!?")
    title_duration = 0
    for word_data in words_data:
        if word_data["word"].lower().rstrip(".!?") == last_title_word:
            title_duration = word_data["end"]
            break
        title_duration = word_data["end"]

    # Create image clip
    clip = ImageClip(np.array(base_img)) \
        .with_position(("center", "center")) \
        .with_start(0) \
        .with_duration(title_duration)

    # Add fade-out over last 0.5 seconds
    fade_duration = 0.5
    # clip = clip.with_opacity(
    #     lambda t: 1 if t < (title_duration - fade_duration)
    #     else max(0, 1 - (t - (title_duration - fade_duration)) / fade_duration)
    # )

    return clip, title_duration

def make_group_caption_clip_with_highlight(group, font_path, video_size, fontsize=120, start=0, end=1):
    font = ImageFont.truetype(font_path, fontsize)
    w_img, h_img = video_size
    max_width = int(w_img * 0.7)

    # Split group into subgroups with max 2 lines
    def split_group_into_max_two_lines(subgroup):
        word_widths = [ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(w["word"] + " ", font=font) for w in subgroup]
        lines = []
        current_line = []
        current_width = 0
        split_indices = []

        for idx, (w, width) in enumerate(zip(subgroup, word_widths)):
            if current_width + width > max_width and current_line:
                lines.append(current_line)
                current_line = []
                current_width = 0
                if len(lines) == 2:
                    split_indices.append(idx)
                    lines = []
            current_line.append(w)
            current_width += width

        if current_line:
            lines.append(current_line)

        if len(lines) > 2:
            split_indices.append(len(subgroup))  # Final overflow

        if not split_indices:
            return [subgroup]

        # Recursively split and merge chunks
        chunks = []
        start = 0
        for split in split_indices:
            chunks.append(subgroup[start:split])
            start = split
        if start < len(subgroup):
            chunks.append(subgroup[start:])

        return chunks

    subgroups = split_group_into_max_two_lines(group)
    clips = []

    for sub in subgroups:
        if not sub:
            continue

        words = [w["word"] for w in sub]
        word_widths = [ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(word + " ", font=font) for word in words]

        # Wrap to lines
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

        img = Image.new("RGBA", (w_img, 400), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        line_positions = {}
        y_start = 50

        for line_num, line_words in enumerate(lines):
            total_line_width = sum(ImageDraw.Draw(Image.new("RGBA", (1, 1))).textlength(word + " ", font=font) for word in line_words)
            x = (w_img - total_line_width) // 2.2
            y = y_start + line_num * (fontsize + 20)

            for word_base in line_words:
                word = word_base
                for ox, oy in [(2, 2), (1, 1)]:
                    draw.text((x + ox, y + oy), word, font=font, fill="black")
                draw.text((x, y), word, font=font, fill="white")
                line_positions[word] = (x, y)
                x += draw.textlength(word + " ", font=font)

        base_clip = ImageClip(np.array(img)).with_position(("center", "center")).with_start(sub[0]["start"]).with_duration(sub[-1]["end"] - sub[0]["start"])
        highlights = []
        for word_info in sub:
            word = word_info["word"]
            if word not in line_positions:
                continue
            x, y = line_positions[word]
            w_overlay = Image.new("RGBA", (w_img, 400), (0, 0, 0, 0))
            d = ImageDraw.Draw(w_overlay)
            d.text((x, y), word, font=font, fill="yellow")
            highlight = ImageClip(np.array(w_overlay)).with_position(("center", "center")).with_start(word_info["start"]).with_duration(word_info["end"] - word_info["start"])
            highlights.append(highlight)

        clips.extend([base_clip] + highlights)

    return clips

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
def assemble_video(audio_fn, title, subreddit, script_txt, _, use_split_videos=False):
    audio_path = os.path.join(AUDIO_DIR, audio_fn)
    ts_path = audio_path.replace(".mp3", ".json")
    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration

    # Select a random video and starting point
    if use_split_videos:
        top_dir = os.path.join(VIDEO_DIR, "top")
        bottom_dir = os.path.join(VIDEO_DIR, "bottom")

        top_videos = sorted(f for f in os.listdir(top_dir) if f.endswith(".mp4"))
        bottom_videos = sorted(f for f in os.listdir(bottom_dir) if f.endswith(".mp4"))

        top_path = os.path.join(top_dir, random.choice(top_videos))
        print(f"Randomly chose video at {top_path}")
        bottom_path = os.path.join(bottom_dir, random.choice(bottom_videos))
        print(f"Randomly chose video at {bottom_path}")

        top_raw = VideoFileClip(top_path).resized(width=1080)
        bottom_raw = VideoFileClip(bottom_path).resized(width=1080)

        speed = 1.18
        required_duration = audio_duration * speed

        max_start_top = max(0, top_raw.duration - required_duration - 1)
        max_start_bottom = max(0, bottom_raw.duration - required_duration - 1)

        start_top = random.uniform(0, max_start_top) if max_start_top > 0 else 0
        start_bottom = random.uniform(0, max_start_bottom) if max_start_bottom > 0 else 0

        top_clip = MultiplySpeed(speed).apply(
            top_raw.subclipped(start_top, start_top + required_duration)
        )
        bottom_clip = MultiplySpeed(speed).apply(
            bottom_raw.subclipped(start_bottom, start_bottom + required_duration)
        )

        stacked_video = clips_array([[top_clip], [bottom_clip]])
        stacked_video = center_crop_to_shorts(stacked_video, target_width=1080, target_height=1920)
        bg_video = stacked_video.with_audio(audio)

    else:
        video_files = sorted(f for f in os.listdir(VIDEO_DIR) if f.endswith(".mp4"))
        bg_path = os.path.join(VIDEO_DIR, random.choice(video_files))
        raw_video = VideoFileClip(bg_path)

        try:
            max_start = max(0, raw_video.duration - audio.duration - 10)
            start_time = random.uniform(0, max_start) if max_start > 0 else 0
        except Exception:
            start_time = 0

        bg_video = center_crop_to_shorts(raw_video.subclipped(start_time, start_time + audio.duration))
        bg_video = bg_video.with_audio(audio)

    # Load word timing data
    with open(ts_path) as jf:
        words_data = json.load(jf)


    text_clips = []

    # Create and add the title clip
    title_clip, title_duration = create_imessage_style_title_clip(
        subreddit=subreddit,
        title_text=title,
        words_data=words_data,
        video_size=bg_video.size,
        bg_image_path=os.path.join(ROOT_DIR, "data", "overlay", "imessage_popup.png")
    )
    text_clips.append(title_clip)

    for group in group_words_by_syllables(words_data):
        group_start = group[0]["start"]
        group_end = group[-1]["end"]
        if group_start > title_duration:
            clips = make_group_caption_clip_with_highlight(
                group,
                font_path=str(SYSTEM_ARIAL),
                video_size=bg_video.size,
                start=group_start,
                end=group_end
            )
            text_clips.extend(clips)

    final = CompositeVideoClip([bg_video, *text_clips]).with_duration(audio_duration)
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
        pid         = entry["id"]
        title       = entry["title"]
        text        = entry["script"]
        subreddit   = entry["subreddit"]
        mp3 = f"{pid}.mp3"
        if os.path.exists(os.path.join(AUDIO_DIR, mp3)):
            print(f"[PROCESS] {pid}")
            assemble_video(mp3, title, subreddit, text, bg_path, use_split_videos=False)  # set to False for single video
        else:
            print(f"[SKIP] No audio for {pid}")

if __name__ == "__main__":
    generate_final_videos()
