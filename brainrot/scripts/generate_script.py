# scripts/generate_scripts.py

import os
import json
import openai
import time

# ─── Configuration ─────────────────────────────────────────────────────────────
ROOT_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS_DIR    = os.path.join(ROOT_DIR, "data", 'posts')
SCRIPTS_DIR  = os.path.join(ROOT_DIR, "data", 'scripts')
MAX_POSTS    = 50  # Max stories to process per run

# openai.api_key = os.getenv("OPENAI_API_KEY")

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
                    "for updates or pictures, and any unnecessary context. Do not add to or embellish the story, but you"
                    "can use the 'but / therefore' technique in your scripts where possible (However: Do not write therefore, write 'so'). I also"
                    "want you to give me 1-2 word tags, so that I can automatically tell which subjects do better than"
                    "others. Select from the examples I've provided and also add 3 about the specific content of the "
                    "story. Return the final output as a single script, formatted like this:\n"
                    "Title: [Original, unedited title]\n"
                    "Story: [The cleaned up version of the post]\n"
                    "Tags: [(partner drama), (family drama), (work drama), (medical drama), (law), (revenge), "
                    "(friendship fallout), (roommate drama), (money problems), (wedding drama), (child drama), "
                    "(breakup), (relationship advice), (cheating), (inheritance), (heartwarming), (wholesome), "
                    "(infuriating), (awkward), (unbelievable), (twist), (plot twist), (justice served)]"
                )},
                {"role": "user", "content": selftext}
            ],
            temperature=0.6,
            max_tokens=450
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

    post_files = sorted(
        [f for f in os.listdir(POSTS_DIR) if f.startswith('posts_') and f.endswith('.json')],
        reverse=True
    )

    # Process only the most recent file
    if post_files:
        post_files = [post_files[0]]
    else:
        print("[ERROR] No post files found.")
        exit()

    for filename in post_files:
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
                continue  # Skip short stories

            print(f"\n[Evaluating] Post {post['id']} from r/{post['subreddit']}...")
            result = gpt_rewrite_story(story)

            if result == "False":
                print("False")
                print("[Skipped] Not suitable for Shorts.")
                continue

            print("[Accepted] Script added.")
            lines = result.splitlines()
            title_line = next((l for l in lines if l.lower().startswith("title:")), None)
            tags_line = next((l for l in lines if l.lower().startswith("tags:")), None)
            # Extract only the story content, excluding the tags
            if "Story:" in result and "Tags:" in result:
                story_raw = result.split("Story:", 1)[-1]
                story = story_raw.split("Tags:", 1)[0].strip()
            else:
                story = None

            if title_line and story and tags_line:
                title = title_line.replace("Title:", "").strip()
                tags_raw = tags_line.replace("Tags:", "").strip()
                tags = [t.strip() for t in tags_raw.strip("()").split("), (")]

                output_scripts.append({
                    "id": post["id"],
                    "subreddit": post["subreddit"],
                    "title": title,
                    "script": story,
                    "tags": tags
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
