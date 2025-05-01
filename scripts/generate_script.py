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

# ─── Set your API key here ─────────────────────────────────────────────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
# OR directly for testing (make sure not to leak):

# ─── GPT Helper ────────────────────────────────────────────────────────────────
def gpt_rewrite_story(selftext: str) -> str:
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You're a critical editor. You are given Reddit stories and must decide if they would make strong, engaging YouTube Shorts. "
                    "We want controversial stories with drama, but no domestic violence, discussion of child pornography"
                    "or incest. If the story is too weak, too slow, or has no payoff, respond only with 'False'. "
                    "If it's usable, remove unnecessary side tangents and information, but keep important background information (just make it brief)."
                    "We want to retain most of the original author's voice, and shorten it to have a maximum spoken length of 2 minutes if necessary. Return only the short."
                )},
                {"role": "user", "content": selftext}
            ],
            temperature=0.7,
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
            output_scripts.append({
                "id": post["id"],
                "subreddit": post["subreddit"],
                "script": result
            })
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
