"""Join the past week's Shorts into one horizontal 1920x1080 long video and upload it to YouTube.

Usage: python scripts/compile_weekly.py           (expects the week's MP4s in out/<name>.mp4)
       python scripts/compile_weekly.py --list    (only print the story names to include)
Env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN; optional RESULTS_FILE.
"""
import datetime, json, os, re, subprocess, sys
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TZ = ZoneInfo("Asia/Colombo")
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
W, H, FPS = 1920, 1080, 30
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
       "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]


def week_stories():
    now = datetime.datetime.now(TZ); seen = {}
    for line in open("stories/PUBLISHED.md"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 3 or not c[2].startswith("https://youtube.com/") or not re.match(r"\d{4}-\d{2}-\d{2}-", c[1]): continue
        live = next((x[5:] for x in c[3:] if x.startswith("live ")), None)
        t = datetime.datetime.fromisoformat(live) if live else datetime.datetime.fromisoformat(c[1][:10] + "T12:00+05:30")
        if now - datetime.timedelta(days=7) <= t <= now and os.path.exists(f"stories/{c[1]}.json"):
            seen[c[1]] = t
    return [n for n, _ in sorted(seen.items(), key=lambda kv: kv[1])][:12]


def font(name, size, bold=True):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if "Lora" in name:
        try: f.set_variation_by_name("Bold")
        except Exception: pass
    return f


def card(path, top, big, small=None):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        u = y / H; d.line([(0, y), (W, y)], fill=(int(14 + 30 * u), int(16 + 18 * u), int(42 + 40 * u)))
    d.text((W / 2, H * .33), top, font=font("Poppins-Bold.ttf", 44), anchor="mm", fill=(255, 210, 122))
    words, lines, cur = big.split(), [], ""
    f = font("Lora-Variable.ttf", 84)
    for w in words:
        if f.getlength((cur + " " + w).strip()) > 1500: lines.append(cur); cur = w
        else: cur = (cur + " " + w).strip()
    lines.append(cur)
    for i, ln in enumerate(lines):
        d.text((W / 2, H * .5 + (i - (len(lines) - 1) / 2) * 104), ln, font=f, anchor="mm", fill=(255, 243, 214))
    if small: d.text((W / 2, H * .78), small, font=font("Poppins-Bold.ttf", 36), anchor="mm", fill=(200, 196, 220))
    im.save(path)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def still_clip(png, seconds, out):
    run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", png, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-t", str(seconds), "-vf", f"format=yuv420p,fade=t=in:st=0:d=0.4,fade=t=out:st={seconds - 0.4}:d=0.4", *ENC, "-shortest", out])


def wide_clip(src, out):
    # vertical Short centred on a soft blurred copy of itself
    fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,eq=brightness=-0.12[bg];"
          f"[0:v]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p[v]")
    run(["ffmpeg", "-y", "-i", src, "-filter_complex", fc, "-map", "[v]", "-map", "0:a", *ENC, out])


def duration(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).decode())


def main():
    names = week_stories()
    if "--list" in sys.argv:
        print("\n".join(names)); return
    names = [n for n in names if os.path.exists(f"out/{n}.mp4")]
    if len(names) < 5:
        print(f"Only {len(names)} videos this week; skipping compilation."); return
    stories = [json.load(open(f"stories/{n}.json")) for n in names]
    formats = [s.get("format", "Story") for s in stories]
    top = max(set(formats), key=formats.count)
    themed = {"Zen story": "Zen Stories to Calm Your Mind", "Stoic wisdom": "Stoic Lessons for a Stronger Mind",
              "Rich vs Poor mindset": "Rich vs Poor Mindset Lessons", "Success tips": "Success Habits That Change Your Life"}
    if formats.count(top) >= len(names) * .6 and top in themed:
        title = f"{len(names)} {themed[top]} | Mindset Minute"
    else:
        title = f"{len(names)} Short Stories With Big Life Lessons | Mindset Minute"
    os.makedirs("comp", exist_ok=True); parts, chapters, t = [], [], 0.0
    card("comp/intro.png", "MINDSET MINUTE", title.split(" | ")[0], "One-minute lessons • New every day")
    still_clip("comp/intro.png", 4, "comp/000_intro.mp4"); parts.append("comp/000_intro.mp4"); chapters.append((0, "Intro")); t += duration(parts[-1])
    for i, (n, s) in enumerate(zip(names, stories), 1):
        name = s.get("title") or s["youtube_title"].split("#")[0].split("|")[0].strip()
        card(f"comp/c{i:02d}.png", f"STORY {i} OF {len(names)}", name, s.get("format", ""))
        still_clip(f"comp/c{i:02d}.png", 2.5, f"comp/{i:02d}a.mp4"); wide_clip(f"out/{n}.mp4", f"comp/{i:02d}b.mp4")
        chapters.append((t, f"{i}. {name}")); parts += [f"comp/{i:02d}a.mp4", f"comp/{i:02d}b.mp4"]
        t += duration(f"comp/{i:02d}a.mp4") + duration(f"comp/{i:02d}b.mp4")
        print(f"added {n}")
    card("comp/outro.png", "THANK YOU FOR WATCHING", "Subscribe for a new lesson every day", "Mindset Minute")
    still_clip("comp/outro.png", 5, "comp/999_outro.mp4"); parts.append("comp/999_outro.mp4")
    open("comp/list.txt", "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "comp/list.txt", "-c", "copy", "-movflags", "+faststart", "comp/weekly.mp4"])
    total = duration("comp/weekly.mp4"); print(f"compilation: {total / 60:.1f} min, {len(names)} stories")

    # thumbnail: a frame from the first story on the wide background, with the title
    run(["ffmpeg", "-y", "-ss", str(min(6, duration("comp/01b.mp4") / 2)), "-i", "comp/01b.mp4", "-frames:v", "1", "comp/thumb_bg.jpg"])
    th = Image.open("comp/thumb_bg.jpg").convert("RGB").resize((1280, 720)); d = ImageDraw.Draw(th)
    d.rectangle([0, 470, 1280, 720], fill=(10, 12, 30))
    d.text((640, 545), title.split(" | ")[0], font=font("Poppins-Bold.ttf", 54), anchor="mm", fill=(255, 210, 122))
    d.text((640, 640), "MINDSET MINUTE", font=font("Poppins-Bold.ttf", 34), anchor="mm", fill=(255, 243, 214))
    th.save("comp/thumb.jpg", quality=90)

    def ts(x): x = int(x); return f"{x // 60}:{x % 60:02d}" if x < 3600 else f"{x // 3600}:{x % 3600 // 60:02d}:{x % 60:02d}"
    tags = sorted({tg for s in stories for tg in s.get("tags", [])})[:25]
    desc = (f"{len(names)} animated stories with a lesson, from this week on Mindset Minute. Watch them all, or jump to one:\n\n"
            + "\n".join(f"{ts(a)} {b}" for a, b in chapters)
            + "\n\nA new one-minute lesson every day. Subscribe so you don't miss tomorrow's story.\n\n#MindsetMinute #shortstories #lifelessons #motivation #zen #mindset")
    publish(title, desc, tags)


def publish(title, desc, tags):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube", "v3", credentials=creds)
    now = datetime.datetime.now(TZ); at = now.replace(hour=6, minute=15, second=0, microsecond=0)   # = ~7:45 PM New York
    while at <= now + datetime.timedelta(minutes=10): at += datetime.timedelta(days=1)
    body = {"snippet": {"title": title[:100], "description": desc[:4900], "tags": tags, "categoryId": "24",
                        "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": "private", "publishAt": at.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                       "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload("comp/weekly.mp4", mimetype="video/mp4", resumable=True))
    resp = None
    while resp is None:
        st, resp = req.next_chunk()
        if st: print(f"uploaded {int(st.progress() * 100)}%")
    vid = resp["id"]; print(f"Weekly compilation: https://youtu.be/{vid}  goes live {at:%a %d %b %I:%M %p} Sri Lanka")
    try:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload("comp/thumb.jpg", mimetype="image/jpeg")).execute()
        print("custom thumbnail set")
    except Exception as e:  # needs a phone-verified channel; the video is fine without it
        print(f"thumbnail not set ({str(e)[:120]})")
    with open(os.environ.get("RESULTS_FILE", os.devnull), "a") as f:
        f.write(json.dumps({"id": vid, "at": at.isoformat(timespec="minutes"), "at_human": at.strftime("%a %d %b, %I:%M %p"), "title": title}) + "\n")


if __name__ == "__main__":
    main()
