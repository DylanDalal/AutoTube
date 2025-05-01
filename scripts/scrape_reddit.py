# scrape_reddit.py

import praw
import json
import os
from datetime import datetime
import random
import config

# Settings
SUBREDDITS = ['aitah']
MIN_UPVOTES = 200
TARGET_TOTAL_NEW_POSTS = 20
INTERNAL_FETCH_LIMIT = 500  # Scan up to 100 per subreddit per attempt

# Paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data", 'posts')

def load_existing_post_ids():
    existing_ids = set()

    paths_to_check = [
        os.path.join(ROOT_DIR, "data", 'posts'),
        os.path.join(ROOT_DIR, "data", 'processed', 'scripts')
    ]

    for path in paths_to_check:
        print(path)
        if not os.path.exists(path):
            continue

        for filename in os.listdir(path):
            if filename.endswith('.json'):
                filepath = os.path.join(path, filename)
                with open(filepath, 'r') as f:
                    try:
                        posts = json.load(f)
                        for post in posts:
                            existing_ids.add(post['id'])
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode {filename}, skipping.")

    return existing_ids


def scrape_posts():
    reddit = praw.Reddit(
        client_id=config.REDDIT_CLIENT_ID,
        client_secret=config.REDDIT_CLIENT_SECRET,
        user_agent=config.REDDIT_USER_AGENT
    )

    existing_ids = load_existing_post_ids()
    print(f"Loaded {len(existing_ids)} existing post IDs.")

    new_posts = []
    total_new = 0

    while total_new < TARGET_TOTAL_NEW_POSTS:
        # Randomize subreddit selection a little
        subreddit_name = random.choice(SUBREDDITS)
        subreddit = reddit.subreddit(subreddit_name)
        print(f"Scanning r/{subreddit_name}...")

        found_in_this_round = False

        for post in subreddit.top(time_filter='all', limit=INTERNAL_FETCH_LIMIT):
            if post.score < MIN_UPVOTES:
                print(post.score)
                print("not enough upvotes")
                continue
            if post.stickied:
                print("stickied")
                continue
            if post.over_18:
                print("nsfw")
                continue
            if post.id in existing_ids:
                print("already found post")
                continue

            if not post.selftext or len(post.selftext.strip()) < 10:
                continue

            post_data = {
                "subreddit": subreddit_name,
                "title": post.title.strip(),
                "selftext": post.selftext.strip(),
                "score": post.score,
                "id": post.id,
                "url": post.url,
                "created_utc": post.created_utc
            }
            new_posts.append(post_data)
            existing_ids.add(post.id)
            total_new = total_new + 1
            found_in_this_round = True
            print(f"Added post {post.id} from r/{subreddit_name} (total: {total_new}/{TARGET_TOTAL_NEW_POSTS})")
            break

        if not found_in_this_round:
            print(f"No good posts found in r/{subreddit_name}, trying another...")

    # Save collected posts
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, f'posts_{timestamp}.json')

    with open(output_path, 'w') as f:
        json.dump(new_posts, f, indent=4)

    print(f"Saved {len(new_posts)} posts to {output_path}")

if __name__ == "__main__":
    scrape_posts()
