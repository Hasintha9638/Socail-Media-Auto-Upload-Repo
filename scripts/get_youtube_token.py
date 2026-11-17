"""One-time: run on YOUR computer to get the YouTube refresh token for GitHub Secrets.

1. pip install google-auth-oauthlib
2. Put the OAuth client file you downloaded from Google Cloud (Desktop app type) next to this script as client_secret.json
3. python get_youtube_token.py  -> a browser opens, sign in with the channel's Google account, allow access
4. Copy the three printed values into GitHub -> repo Settings -> Secrets and variables -> Actions
"""
from google_auth_oauthlib.flow import InstalledAppFlow
import json

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes=["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
c = json.load(open("client_secret.json"))["installed"]
print("\nYT_CLIENT_ID     =", c["client_id"])
print("YT_CLIENT_SECRET =", c["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
