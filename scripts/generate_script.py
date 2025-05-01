# scripts/generate_scripts.py

import os
import json
import openai
import time

# ─── Configuration ─────────────────────────────────────────────────────────────
ROOT_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR    = os.path.join(ROOT_DIR, "data", 'posts')
SCRIPTS_DIR  = os.path.join(ROOT_DIR, "data", 'scripts')
MAX_POSTS    = 100  # Max stories to process per run

# openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_key = "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"

# ─── GPT Helper ────────────────────────────────────────────────────────────────
def gpt_rewrite_story(selftext: str) -> str:
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a critical editor for a YouTube Shorts script pipeline. You are given Reddit stories and "
                    "must decide if they would make strong, dramatic, or hilarious 90-second MAXIMUM YouTube Shorts."
                    "**Only pass stories that:**"
                    "– Grab attention within 5 seconds  "
                    "– Have escalating drama or tension  "
                    "– End in a twist, laugh, or emotionally satisfying moment"
                    "**Reject stories by responding only with “False” if they:**"
                    "– Take too long to set up  "
                    "– Rely on weak tension like food fails or awkward moments  "
                    "– Don’t have a twist, shocking moment, or emotional impact"
                    "– Feel like a vent, essay, or slice-of-life without payoff"
                    "**Imagine someone reading this aloud in a 90-second video. If it would feel boring or lose viewers, reject it.** Be ruthless."
                    "If the story is worth keeping, trim all filler but retain the author's voice. Remove TL;DRs, promises"
                    "for updates or pictures, and any unnecessary context. Do not add to or embellish the story."
                    " Return the final output as a single script, formatted like this:\n"
                    "Title: [Always first-person, reddit-style compelling/dramatic title]\n"
                    "Story: [The cleaned up version of the post]\n"
                )},
                {"role": "user", "content": selftext}
            ],
            temperature=0.6,
            max_tokens=400
        )
        result = response.choices[0].message.content.strip()
        return result
    except Exception as e:
        print(f"[ERROR] GPT call failed: {e}")
        return "False"

# ─── Main Script Generator ─────────────────────────────────────────────────────
def generate_scripts():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)

    scripts_written = 0

    for filename in sorted(os.listdir(POSTS_DIR)):
        if not (filename.startswith('posts_') and filename.endswith('.json')):
            continue

        with open(os.path.join(POSTS_DIR, filename), 'r') as f:
            posts = json.load(f)

        output_scripts = []
        for post in posts:
            if scripts_written >= MAX_POSTS:
                break

            story = post.get("selftext", "").strip()
            if len(story) < 20:
                continue  # Skip trivial stories

            print(f"\n[Evaluating] Post {post['id']} from r/{post['subreddit']}...")
            result = gpt_rewrite_story(story)

            if result == "False":
                print("False")
                print("[Skipped] Not suitable for Shorts.")
                continue

            print("[Accepted] Script added.")
            lines = result.splitlines()
            title_line = next((l for l in lines if l.lower().startswith("title:")), None)
            story = result.split("Story:", 1)[-1].strip() if "Story:" in result else None

            if title_line and story:
                title = title_line.replace("Title:", "").strip()
                output_scripts.append({
                    "id": post["id"],
                    "subreddit": post["subreddit"],
                    "title": title,
                    "script": story
                })
            else:
                print("[WARN] Invalid GPT format. Skipping.")
            scripts_written += 1
            time.sleep(1.5)  # small delay to avoid rate limits

        if output_scripts:
            out_path = os.path.join(SCRIPTS_DIR, filename.replace('posts_', 'scripts_'))
            with open(out_path, 'w') as f:
                json.dump(output_scripts, f, indent=4)
            print(f"[Saved] {len(output_scripts)} script(s) to {out_path}")

        if scripts_written >= MAX_POSTS:
            break

if __name__ == "__main__":
    generate_scripts()
