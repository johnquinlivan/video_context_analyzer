"""
Utility helpers for video_context_analyzer.
Includes YouTube URL parsing, validation, and output file writing.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse


_YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "youtu.be", "m.youtube.com"}


class AnalysisError(RuntimeError):
    """Raised when video context analysis cannot be completed."""


def validate_youtube_url(url: str) -> None:
    """Raise ``ValueError`` if *url* is not a supported YouTube URL."""
    raw_host = urlparse(url.strip()).netloc.lower()
    host = raw_host.lstrip("www.")
    if raw_host in _YOUTUBE_HOSTS or host in {h.lstrip("www.") for h in _YOUTUBE_HOSTS}:
        return
    raise ValueError(
        f"Unsupported URL: {url!r}\n"
        "This app only supports YouTube URLs (youtube.com, youtu.be)."
    )


# ── YouTube URL parsing ───────────────────────────────────────────────────────

# Matches the 11-character YouTube video ID
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def extract_video_id(url: str) -> str:
    """
    Extract the YouTube video ID from a variety of URL formats.

    Supported formats:
        https://www.youtube.com/watch?v=VIDEOID
        https://youtu.be/VIDEOID
        https://www.youtube.com/shorts/VIDEOID
        https://www.youtube.com/embed/VIDEOID
        Additional query parameters are tolerated.

    Returns the 11-character video ID string.
    Raises ValueError if the ID cannot be found or is malformed.
    """
    url = url.strip()
    parsed = urlparse(url)

    # youtu.be short links: path is /VIDEOID
    if parsed.netloc in ("youtu.be",):
        video_id = parsed.path.lstrip("/").split("/")[0]
        return _validate_video_id(video_id, url)

    # Standard watch URL: ?v=VIDEOID
    if parsed.path in ("/watch", "/watch/"):
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return _validate_video_id(qs["v"][0], url)

    # Shorts and embed: /shorts/VIDEOID or /embed/VIDEOID
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in ("shorts", "embed", "v", "e"):
        return _validate_video_id(path_parts[1], url)

    # Last-resort: look for v= in the raw query string
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return _validate_video_id(qs["v"][0], url)

    raise ValueError(
        f"Could not extract a YouTube video ID from the URL: {url!r}\n"
        "Expected formats:\n"
        "  https://www.youtube.com/watch?v=VIDEOID\n"
        "  https://youtu.be/VIDEOID\n"
        "  https://www.youtube.com/shorts/VIDEOID\n"
        "  https://www.youtube.com/embed/VIDEOID"
    )


def _validate_video_id(video_id: str, original_url: str) -> str:
    """Confirm the extracted string looks like a valid YouTube video ID."""
    if not video_id or not _VIDEO_ID_RE.match(video_id):
        raise ValueError(
            f"Extracted an invalid YouTube video ID {video_id!r} from URL: {original_url!r}"
        )
    return video_id

# ── Output helpers ────────────────────────────────────────────────────────────


def save_json(data: dict, path: Path) -> None:
    """Serialize *data* to pretty-printed JSON and write to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    print(f"  JSON report saved → {path}")


def save_txt(content: str, path: Path) -> None:
    """Write a plain-text string to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  TXT  report saved → {path}")


# ── Console formatting ────────────────────────────────────────────────────────


def hr(char: str = "─", width: int = 60) -> str:
    """Return a horizontal rule string."""
    return char * width


def debug_log(message: str) -> None:
    """Emit diagnostics only when explicitly enabled."""
    if os.getenv("VIDEO_CONTEXT_ANALYZER_DEBUG", "").lower() in {"1", "true", "yes"}:
        print(message, file=sys.stderr)


def fatal(message: str, exit_code: int = 1) -> None:
    """Raise a structured analysis error for the caller to handle."""
    raise AnalysisError(message)
