import os
import json
import random
import datetime
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import shutil

# ─── Constants ───────────────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = ROOT_DIR / "data" / "final"
SCRIPTS_DIR = ROOT_DIR / "data" / "processed" / "scripts"
CREDENTIALS_FILE = ROOT_DIR / "credentials.json"
TOKEN_FILE = ROOT_DIR / "token.pickle"
SCHEDULE_JSON = ROOT_DIR / "data" / "schedule.json"

# ─── Auth ─────────────────────────────────────────────────────────────────────
def get_authenticated_service():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)
    return build("youtube", "v3", credentials=creds)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_schedule():
    if SCHEDULE_JSON.exists():
        with open(SCHEDULE_JSON, "r") as f:
            return json.load(f)
    return {}

def save_schedule(schedule):
    with open(SCHEDULE_JSON, "w") as f:
        json.dump(schedule, f, indent=2)

def get_script_entry(video_id):
    for script_file in SCRIPTS_DIR.glob("*.json"):
        with open(script_file) as f:
            data = json.load(f)
            for entry in data:
                if entry["id"] in video_id:
                    return entry
    return None

def upload_video_to_youtube(file_path, title, description, scheduled_datetime):
    youtube = get_authenticated_service()
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["reddit", "story", "redditstory", "storytime", "stories"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": scheduled_datetime.isoformat() + "Z",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True, mimetype='video/*')
    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {file_path}: {int(status.progress() * 100)}%")

# ─── Main Logic ───────────────────────────────────────────────────────────────
def schedule_and_upload():
    scheduled = load_schedule()

    folders = ["1", "2", "3"]
    SUCCESS_DIR = FINAL_DIR / "success"
    SUCCESS_DIR.mkdir(parents=True, exist_ok=True)

    # Clear the success folder before each run
    for f in SUCCESS_DIR.glob("*.mp4"):
        f.unlink()

    all_videos = []
    for folder in folders:
        folder_path = FINAL_DIR / folder
        for f in os.listdir(folder_path):
            if f.endswith(".mp4") and not any(f in val for val in scheduled.values()):
                all_videos.append((folder_path / f, f))

    if not all_videos:
        print("[INFO] No unscheduled videos found.")
        return

    now = datetime.datetime.now()
    schedule_slots = []
    for i in range(7):
        day = now.date() + datetime.timedelta(days=i)
        for hour in [10, 15, 19]:
            dt = datetime.datetime.combine(day, datetime.time(hour, 0))
            if dt > now and dt.isoformat() not in scheduled:
                schedule_slots.append(dt)
            if len(schedule_slots) >= len(all_videos):
                break
        if len(schedule_slots) >= len(all_videos):
            break

    print(f"[INFO] Scheduling {min(len(schedule_slots), len(all_videos))} videos")
    random.shuffle(all_videos)

    uploaded_videos = []

    try:
        for dt, (video_path, filename) in zip(schedule_slots, all_videos):
            video_id = filename.split(".")[0]
            script = get_script_entry(video_id)
            if not script:
                print(f"[SKIP] Script not found for {video_id}")
                continue

            title_raw = script["title"]
            title = (title_raw[:92] + " #reddit #story #redditstory")[:100]
            description = "#reddit #story #redditstory #storytime #stories"

            print(f"[UPLOAD] {filename} → {title}")
            try:
                upload_video_to_youtube(str(video_path), title, description, dt)
                print(f"✅ Uploaded: {title}")

                uploaded_videos.append((dt.isoformat(), filename))

                # Move to success folder
                shutil.move(str(video_path), SUCCESS_DIR / filename)

            except Exception as e:
                print(f"[ERROR] Failed to upload {filename}: {e}")
                break
    finally:
        for dt_str, fname in uploaded_videos:
            scheduled[dt_str] = fname
        save_schedule(scheduled)

if __name__ == "__main__":
    schedule_and_upload()
