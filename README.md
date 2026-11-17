# Daily Moral Stories

An animated moral story Short every day, for YouTube Shorts, TikTok and Instagram Reels.

- `storykit/`: the renderer. It turns a story JSON into a 1080×1920 video with paper-cut animation, a neural voiceover (Kokoro), captions, music and sound effects.
- `stories/`: one JSON per day. A scheduled Claude task writes these (see `STORY_GUIDE.md`).
- `.github/workflows/publish.yml`: when a new story is pushed, Actions renders it, uploads it to YouTube, sets it to go live at 6:30 PM Sri Lanka time, and logs it in `stories/PUBLISHED.md`.

## One-time YouTube setup
1. Go to console.cloud.google.com and create a project, then enable **YouTube Data API v3**.
2. Set up the OAuth consent screen: External type, add yourself as a test user, then **publish the app** (otherwise the token expires after 7 days).
3. Create Credentials → OAuth client ID → **Desktop app**, and download the JSON as `client_secret.json`.
4. On your PC, run `pip install google-auth-oauthlib` and then `python scripts/get_youtube_token.py`.
5. In the repo, go to Settings → Secrets and variables → Actions, and add `YT_CLIENT_ID`, `YT_CLIENT_SECRET` and `YT_REFRESH_TOKEN`.
6. **Request the API audit** (search "YouTube API Services audit and quota extension form"). Until Google approves it, API uploads stay private.

## Run locally
```
pip install -r requirements.txt   # plus ffmpeg
mkdir models && curl -L -o models/kokoro.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o models/voices.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
python storykit/storykit.py stories/2026-11-17-farmer-who-planted-stones.json out/test.mp4
```
