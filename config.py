import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.absolute()
ASSETS_DIR = PROJECT_ROOT / "assets"
BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
MUSIC_DIR = ASSETS_DIR / "bgmusics"
OUTPUT_DIR = PROJECT_ROOT / "output"
BACKUP_DIR = PROJECT_ROOT / "backup"

OUTPUT_DIR.mkdir(exist_ok=True)
BACKGROUNDS_DIR.mkdir(exist_ok=True)
MUSIC_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30
VIDEO_BITRATE = "5000k"
TEXT_DISPLAY_SECONDS = 16
FADE_DURATION = 0.5
QUOTES_PER_BATCH = 25

DEFAULT_QUOTE_CATEGORIES = ["inspirational", "wisdom", "success", "life", "motivation"]
BG_MUSIC_VOLUME = 0.50  # Background music volume multiplier (0.0-1.0)
USE_GRADIENT_BACKGROUND = False  # Disable gradient to use blurred background
GRADIENT_COLOR_START = (255, 0, 0)  # Red
GRADIENT_COLOR_END = (0, 0, 255)  # Blue
BACKGROUND_DIM_ALPHA = 30  # Alpha for dim overlay (0-255) – lighter overlay for clearer text
YOUTUBE_CLIENT_SECRET_GLOB = "client_secret*.json"
YOUTUBE_CLIENT_SECRET_FALLBACK = "client_secret.json"
YOUTUBE_TOKEN_FILE = "token.pickle"
YOUTUBE_PRIVACY_STATUS = "private"
YOUTUBE_CATEGORY_ID = "22"
YOUTUBE_MADE_FOR_KIDS = False

# Image Fetcher & Gradient Blending Settings
USE_DYNAMIC_IMAGES = True
IMAGE_KEYWORDS_DEFAULT = ["aesthetic", "nature", "nebula", "stars", "abstract"]
SLIDE_TRANSITION_TYPE = "crossfade"  # crossfade, slide_left, slide_right, fade
SLIDE_TRANSITION_DURATION = 0.8
# New settings for YouTube Shorts and scheduling
DEFAULT_YT_TAGS = ["inspirational", "quote", "shorts", "motivation"]  # base tags for all uploads
SCHEDULE_START = "06:00"  # start time for scheduling
SCHEDULE_INTERVAL_HOURS = 3  # interval in hours between uploads
CTA_ASSETS_DIR = ASSETS_DIR / "cta"  # optional folder for CTA images
DEFAULT_LANGUAGE = "en"

SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "hi"]  # added Hindi support

# Scheduling iterator moved to main logic
