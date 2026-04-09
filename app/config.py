"""
Central configuration for video_context_analyzer.

All sensitive credentials are loaded from the .env file via python-dotenv.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Locate project root and load .env ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Analysis settings ─────────────────────────────────────────────────────────
DEFAULT_COMMENT_LIMIT: int = 50          # Max top-level comments to fetch
COMMENT_ORDER: str = "relevance"         # "relevance" or "time"
RECENT_UPLOAD_BASELINE_SIZE: int = 12    # Number of recent channel uploads to compare against
CHANNEL_HISTORY_SAMPLE_SIZE: int = 40    # Larger upload history sample for topic clustering
PLAYLIST_SCAN_LIMIT: int = 8             # Max channel playlists to inspect for series context

# ── YouTube API ───────────────────────────────────────────────────────────────
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")
YOUTUBE_API_BASE: str = "https://www.googleapis.com/youtube/v3"

# ── OpenAI-compatible LLM (optional) ─────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
