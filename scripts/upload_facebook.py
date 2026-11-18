"""Publish a rendered story video as a Reel on the Facebook Page (Reels Publishing API).

Env (GitHub Secrets): FB_PAGE_ID, FB_PAGE_TOKEN (a non-expiring Page access token)
Usage: python scripts/upload_facebook.py stories/<story>.json out/<video>.mp4
"""
import json, os, sys, time, urllib.request, urllib.parse

GRAPH = "https://graph.facebook.com/v25.0"


def req(method, url, data=None, headers=None, raw=None):
    body = raw if raw is not None else (urllib.parse.urlencode(data).encode() if data else None)
    r = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=600) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Facebook API error {e.code} on {url.split('?')[0]}: {e.read().decode()[:600]}")


def main():
    story = json.load(open(sys.argv[1])); video = sys.argv[2]
    page, token = os.environ["FB_PAGE_ID"], os.environ["FB_PAGE_TOKEN"]
    tags = " ".join(w for w in story.get("description", "").split() if w.startswith("#"))[:300]
    caption = f"{story['youtube_title'].split('#')[0].strip()}\n\n{story['scenes'][-1]['narration']}\n\nA new tiny tale every day 🌙 Follow Tiny Tales Daily.\n{tags}"

    start = req("POST", f"{GRAPH}/{page}/video_reels", {"upload_phase": "start", "access_token": token})
    vid = start["video_id"]; upload_url = start.get("upload_url") or f"https://rupload.facebook.com/video-upload/v25.0/{vid}"
    size = os.path.getsize(video)
    req("POST", upload_url, headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size),
                                     "Content-Type": "application/octet-stream"}, raw=open(video, "rb").read())
    print(f"Uploaded {size} bytes to Facebook (video {vid}); publishing…")
    req("POST", f"{GRAPH}/{page}/video_reels", {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                                "description": caption, "access_token": token})
    for _ in range(40):
        time.sleep(15)
        st = req("GET", f"{GRAPH}/{vid}?fields=status,permalink_url&access_token={token}")
        status = st.get("status", {})
        if status.get("video_status") == "ready" or status.get("publishing_phase", {}).get("status") == "complete":
            link = "https://www.facebook.com" + st["permalink_url"] if st.get("permalink_url", "").startswith("/") else st.get("permalink_url", f"https://www.facebook.com/reel/{vid}")
            print(f"Facebook Reel published: {link}")
            with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
                f.write(f"facebook_link={link}\n")
            return
        if status.get("video_status") == "error" or status.get("processing_phase", {}).get("status") == "error":
            raise SystemExit(f"Facebook processing failed: {status}")
    raise SystemExit("Facebook Reel still processing after 10 minutes (it may still appear later).")


if __name__ == "__main__":
    main()
