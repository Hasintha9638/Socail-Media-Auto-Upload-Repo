"""Upload a rendered story to YouTube Shorts, scheduled to go public at a set local time.

Env (GitHub Secrets): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Optional env: PUBLISH_AT_LOCAL ("05:45"), PUBLISH_TZ ("Asia/Colombo"), YT_PRIVACY ("public"|"private"|"unlisted")
Usage: python scripts/upload_youtube.py stories/<story>.json out/<video>.mp4
"""
import json, os, sys, datetime
from zoneinfo import ZoneInfo
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

story = json.load(open(sys.argv[1])); video = sys.argv[2]
creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                    client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                    scopes=["https://www.googleapis.com/auth/youtube.upload"])
yt = build("youtube", "v3", credentials=creds)

status = {"selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}
tz = ZoneInfo(os.environ.get("PUBLISH_TZ", "Asia/Colombo"))
# The story may name its own slot: "publish_at": "05:45" or "18:45" (Sri Lanka), optional "publish_date": "YYYY-MM-DD".
hh, mm = map(int, (story.get("publish_at") or os.environ.get("PUBLISH_AT_LOCAL", "05:45")).split(":"))
now = datetime.datetime.now(tz)
if story.get("publish_date"):
    y, mo, d = map(int, story["publish_date"].split("-"))
    at = datetime.datetime(y, mo, d, hh, mm, tzinfo=tz)
else:
    at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
while at <= now + datetime.timedelta(minutes=10):
    at += datetime.timedelta(days=1)          # next peak slot
status.update(privacyStatus="private", publishAt=at.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"))

body = {"snippet": {"title": story["youtube_title"][:100], "description": story["description"],
                    "tags": story.get("tags", []), "categoryId": "24", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": status}
req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video, mimetype="video/mp4", resumable=True))
resp = None
while resp is None:
    st, resp = req.next_chunk()
    if st: print(f"uploaded {int(st.progress() * 100)}%")
vid = resp["id"]; print(f"YouTube video id: {vid}  https://youtube.com/shorts/{vid}  status={resp['status']}")
with open(os.environ.get("RESULTS_FILE", os.devnull), "a") as f:
    f.write(json.dumps({"id": vid, "at": at.isoformat(timespec="minutes"), "at_human": at.strftime("%a %d %b, %I:%M %p"), "title": story["youtube_title"]}) + "\n")
