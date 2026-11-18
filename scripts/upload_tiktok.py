"""Post a rendered story video to TikTok with the Content Posting API (Direct Post, FILE_UPLOAD).

Env (GitHub Secrets): TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN
Optional: GH_PAT (lets the script save a rotated refresh token back to the repo secrets),
          GITHUB_REPOSITORY, TIKTOK_PRIVACY (force a privacy level, e.g. SELF_ONLY)
Usage: python scripts/upload_tiktok.py stories/<story>.json out/<video>.mp4
"""
import json, os, subprocess, sys, time, urllib.request, urllib.parse

API = "https://open.tiktokapis.com"


def call(method, url, data=None, headers=None, form=False, raw=None):
    headers = dict(headers or {})
    body = raw
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode(); headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode(); headers["Content-Type"] = "application/json; charset=UTF-8"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            txt = r.read().decode() or "{}"
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        raise SystemExit(f"TikTok API error {e.code} on {url.split('?')[0]}: {txt[:500]}")
    return json.loads(txt) if txt.strip().startswith("{") else {}


def refresh_access_token():
    r = call("POST", f"{API}/v2/oauth/token/", {
        "client_key": os.environ["TIKTOK_CLIENT_KEY"], "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
        "grant_type": "refresh_token", "refresh_token": os.environ["TIKTOK_REFRESH_TOKEN"]}, form=True)
    if "access_token" not in r:
        raise SystemExit(f"Could not refresh TikTok token: {r.get('error')} {r.get('error_description')}")
    new_rt = r.get("refresh_token")
    if new_rt and new_rt != os.environ["TIKTOK_REFRESH_TOKEN"] and os.environ.get("GH_PAT"):
        subprocess.run(["gh", "secret", "set", "TIKTOK_REFRESH_TOKEN", "-R", os.environ["GITHUB_REPOSITORY"], "--body", new_rt],
                       check=True, env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]}, capture_output=True)
        print("Saved rotated TikTok refresh token to repo secrets.")
    return r["access_token"]


def main():
    story = json.load(open(sys.argv[1])); video = sys.argv[2]
    token = refresh_access_token()
    auth = {"Authorization": f"Bearer {token}"}

    info = call("POST", f"{API}/v2/post/publish/creator_info/query/", {}, auth)["data"]
    options = info.get("privacy_level_options", [])
    privacy = os.environ.get("TIKTOK_PRIVACY") or ("PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in options else (options or ["SELF_ONLY"])[0])
    print(f"Posting as @{info.get('creator_username')} with privacy {privacy} (allowed: {options})")

    tags = " ".join("#" + t.replace(" ", "") for t in ["TinyTalesDaily", "moralstory", "storytime", "animation", "fyp"])
    caption = f"{story['title']} — {story['scenes'][-1]['narration']} {tags}"[:2200]
    size = os.path.getsize(video)
    init = call("POST", f"{API}/v2/post/publish/video/init/", {
        "post_info": {"title": caption, "privacy_level": privacy, "disable_comment": False, "disable_duet": False,
                      "disable_stitch": False, "video_cover_timestamp_ms": 1500, "is_aigc": True},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}}, auth)
    if init.get("error", {}).get("code") not in (None, "ok"):
        raise SystemExit(f"TikTok init failed: {init['error']}")
    publish_id, upload_url = init["data"]["publish_id"], init["data"]["upload_url"]

    call("PUT", upload_url, headers={"Content-Type": "video/mp4", "Content-Length": str(size),
                                     "Content-Range": f"bytes 0-{size - 1}/{size}"}, raw=open(video, "rb").read())
    print("Uploaded video bytes; waiting for TikTok to process…")

    for _ in range(60):
        time.sleep(10)
        st = call("POST", f"{API}/v2/post/publish/status/fetch/", {"publish_id": publish_id}, auth).get("data", {})
        status = st.get("status")
        if status == "PUBLISH_COMPLETE":
            ids = st.get("publicaly_available_post_id") or st.get("publicly_available_post_id") or []
            print(f"TikTok post complete. publish_id={publish_id} post_ids={ids}")
            with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
                f.write(f"tiktok_status=posted ({privacy})\n")
            return
        if status == "FAILED":
            raise SystemExit(f"TikTok publish failed: {st.get('fail_reason')}")
    raise SystemExit("TikTok publish still processing after 10 minutes")


if __name__ == "__main__":
    main()
