import os
import json
import time
import pickle
import random
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# ─── YouTube Auth ─────────────────────────────────────────────────────────────
def get_authenticated_service():
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    token_path = "token.pickle"
    client_secrets_path = "client_secrets.json"
    creds = None

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

youtube = get_authenticated_service()

# ─── Configuration ────────────────────────────────────────────────────────────
ROOT = Path("/Users/Dylan/Documents/GitHub/AutoTube")
FINAL_DIR = ROOT / "data" / "final"
SCRIPT_DIR = ROOT / "data" / "processed" / "scripts"
SCHEDULE_FILE = ROOT / "data" / "schedule.json"

UPLOAD_TIMES = ["10:00", "15:00", "19:00"]
TAGS = "#reddit #story #redditstory"
DESCRIPTION = "#reddit #story #redditstory #storytime #stories"
MAX_TITLE_LEN = 100

# ─── Load Schedule ────────────────────────────────────────────────────────────
if SCHEDULE_FILE.exists():
    with open(SCHEDULE_FILE) as f:
        schedule = json.load(f)
else:
    schedule = []

scheduled_videos = {entry["video"] for entry in schedule if "uploaded" in entry}

# ─── Load Metadata ────────────────────────────────────────────────────────────
story_lookup = {}
for file in SCRIPT_DIR.glob("*.json"):
    with open(file) as f:
        for entry in json.load(f):
            story_lookup[entry["id"]] = entry

# ─── Detect Unscheduled Videos ────────────────────────────────────────────────
unscheduled = []
for folder in FINAL_DIR.iterdir():
    if folder.is_dir():
        for file in folder.glob("*.mp4"):
            if file.name not in {e["video"] for e in schedule}:
                unscheduled.append(file)

# ─── Generate Time Slots ──────────────────────────────────────────────────────
today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
available_slots = []
used_slots = {e["scheduled_time"] for e in schedule}

for i in range(14):
    d = today + timedelta(days=i)
    for t in UPLOAD_TIMES:
        h, m = map(int, t.split(":"))
        dt = d.replace(hour=h, minute=m)
        iso = dt.isoformat()
        if iso not in used_slots and dt > datetime.now():
            available_slots.append(iso)

# ─── Assign Random Video to Random Slot Per Day (3/day) ───────────────────────
slots_by_day = defaultdict(list)
for iso in available_slots:
    date = iso.split("T")[0]
    slots_by_day[date].append(iso)

random.shuffle(unscheduled)
scheduled_set = {e["video"] for e in schedule}
unscheduled = [v for v in unscheduled if v.name not in scheduled_set]

for date, slots in sorted(slots_by_day.items()):
    if len(unscheduled) < 3:
        break

    day_slots = random.sample(slots, min(3, len(slots)))
    for slot in day_slots:
        video_path = unscheduled.pop()
        story_id = video_path.stem.split("_")[0]
        metadata = story_lookup.get(story_id)
        if not metadata:
            continue

        base_title = metadata["title"]
        safe_title = (base_title[:MAX_TITLE_LEN - len(TAGS) - 1] + "…") if len(base_title) + len(TAGS) > MAX_TITLE_LEN else base_title
        full_title = f"{safe_title} {TAGS}"

        schedule.append({
            "video": video_path.name,
            "scheduled_time": slot,
            "title": full_title,
            "description": DESCRIPTION,
            "tags": TAGS.strip("#").split() + ["storytime", "stories"],
            "platforms": ["youtube"]
        })

# ─── Upload Scheduled Videos ──────────────────────────────────────────────────
for entry in schedule:
    if entry.get("uploaded"):
        continue

    scheduled_time = datetime.fromisoformat(entry["scheduled_time"])
    if scheduled_time <= datetime.now():
        continue

    video_filename = entry["video"]
    video_path = None
    for folder in FINAL_DIR.iterdir():
        path = folder / video_filename
        if path.exists():
            video_path = path
            break

    if not video_path:
        print(f"[SKIP] File not found: {video_filename}")
        continue

    print(f"[UPLOAD] {video_filename} → {entry['title']}")
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": entry["title"],
                "description": entry["description"],
                "tags": entry["tags"],
                "categoryId": "22"
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": scheduled_time.astimezone().isoformat(),
                "selfDeclaredMadeForKids": False
            }
        },
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading {int(status.progress() * 100)}%...")

    print(f"✅ Uploaded: {entry['title']}")
    entry["uploaded"] = True

# ─── Save Schedule ────────────────────────────────────────────────────────────
with open(SCHEDULE_FILE, "w") as f:
    json.dump(schedule, f, indent=2)

print("✅ All scheduled uploads complete.")
