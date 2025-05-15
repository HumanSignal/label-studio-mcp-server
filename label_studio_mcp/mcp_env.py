import os
from label_studio_sdk.client import LabelStudio

LABEL_STUDIO_URL = os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
LABEL_STUDIO_API_KEY = os.getenv("LABEL_STUDIO_API_KEY")

ls = None
if LABEL_STUDIO_API_KEY:
    try:
        ls = LabelStudio(base_url=LABEL_STUDIO_URL, api_key=LABEL_STUDIO_API_KEY)
        print(f"Connected to Label Studio at {LABEL_STUDIO_URL}")
    except Exception as e:
        print(f"Error initializing Label Studio client: {e}")
else:
    print("LABEL_STUDIO_API_KEY not set; Label Studio client unavailable.")
