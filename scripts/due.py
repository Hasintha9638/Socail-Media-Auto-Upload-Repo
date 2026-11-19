"""List stories that are uploaded to YouTube but not yet posted to a platform, oldest first.

Usage: python scripts/due.py facebook|tiktok [--window-min 40]
  facebook: only stories whose YouTube go-live time is within the window (so the Reel goes out with it)
  tiktok:   any not-yet-sent story from the last 3 days (TikTok keeps inbox drafts until you post)
Prints one story name per line (max 2).
"""
import datetime, re, sys
from zoneinfo import ZoneInfo

platform = sys.argv[1]
window = int(sys.argv[sys.argv.index("--window-min") + 1]) if "--window-min" in sys.argv else 40
tz = ZoneInfo("Asia/Colombo"); now = datetime.datetime.now(tz)
uploaded, done = {}, set()
for line in open("stories/PUBLISHED.md"):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) < 3 or not re.match(r"\d{4}-\d{2}-\d{2}-", cells[1]): continue
    name, what = cells[1], cells[2]
    if what.startswith("https://youtube.com/"):
        live = next((c[5:] for c in cells[3:] if c.startswith("live ")), None)
        uploaded[name] = datetime.datetime.fromisoformat(live) if live else datetime.datetime.fromisoformat(name[:10] + "T00:00+05:30")
    elif what.lower().startswith(platform):
        done.add(name)

due = []
for name, live in sorted(uploaded.items(), key=lambda kv: kv[1]):
    if name in done: continue
    if platform == "facebook" and not (now - datetime.timedelta(hours=20) <= live <= now + datetime.timedelta(minutes=window)): continue
    if platform == "tiktok" and live < now - datetime.timedelta(days=3): continue
    due.append(name)
print("\n".join(due[:2]))
