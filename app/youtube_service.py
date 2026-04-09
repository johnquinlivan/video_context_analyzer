"""
YouTube Data API v3 client for video_context_analyzer.

Handles:
  - Video metadata (snippet + statistics)
  - Channel metadata
  - Playlist membership / series context
  - Recent channel uploads for baseline comparison
  - Larger channel-history samples for topic clustering
  - Top-level comment threads
  - Graceful error handling for disabled comments, quota errors, and bad responses
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import requests

from app import config
from app.models import CommentRecord
from app.utils import AnalysisError, debug_log, fatal


# ── Internal request helper ───────────────────────────────────────────────────


def _get(endpoint: str, params: dict) -> Dict[str, Any]:
    """
    Perform a GET request against the YouTube Data API.

    Raises AnalysisError on HTTP errors or quota exhaustion.
    Returns the parsed JSON body on success.
    """
    params["key"] = config.YOUTUBE_API_KEY
    url = f"{config.YOUTUBE_API_BASE}/{endpoint}"

    try:
        response = requests.get(url, params=params, timeout=15)
    except requests.exceptions.ConnectionError:
        fatal("Network error: could not reach the YouTube API. Check your internet connection.")
    except requests.exceptions.Timeout:
        fatal("Request timed out while contacting the YouTube API.")

    if response.status_code == 403:
        body = response.json()
        reason = _extract_error_reason(body)
        if reason in ("quotaExceeded", "dailyLimitExceeded"):
            fatal("YouTube API quota exceeded. Wait until midnight Pacific Time or use a different API key.")
        fatal(f"YouTube API returned 403 Forbidden. Reason: {reason}")

    if response.status_code == 400:
        body = response.json()
        reason = _extract_error_reason(body)
        fatal(f"YouTube API returned 400 Bad Request. Reason: {reason}")

    if not response.ok:
        fatal(f"YouTube API error: HTTP {response.status_code} — {response.text[:300]}")

    try:
        return response.json()
    except ValueError:
        fatal("YouTube API returned a malformed (non-JSON) response.")


def _extract_error_reason(body: dict) -> str:
    """Pull the machine-readable reason code out of a YouTube API error envelope."""
    try:
        return body["error"]["errors"][0]["reason"]
    except (KeyError, IndexError, TypeError):
        return "unknown"


# ── Public API ────────────────────────────────────────────────────────────────


def fetch_video_metadata(video_id: str) -> Dict[str, Any]:
    """
    Fetch snippet and statistics for a single video.

    Returns a dict with keys: title, channelName, channelId, publishedAt,
    description, thumbnail, views, commentCount, likeCount.

    Raises AnalysisError if the video is not found or the response is malformed.
    """
    if not config.YOUTUBE_API_KEY:
        fatal(
            "YOUTUBE_API_KEY is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Add your YouTube Data API v3 key\n"
            "  3. Re-run the script"
        )

    data = _get(
        "videos",
        {"part": "snippet,statistics", "id": video_id},
    )

    items = data.get("items", [])
    if not items:
        fatal(
            f"No video found for ID '{video_id}'.\n"
            "The video may be private, deleted, or the ID may be wrong."
        )

    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})

    thumbnail_url = (
        snippet.get("thumbnails", {})
        .get("high", snippet.get("thumbnails", {}).get("default", {}))
        .get("url", "")
    )

    return {
        "title": snippet.get("title", ""),
        "channelName": snippet.get("channelTitle", ""),
        "channelId": snippet.get("channelId", ""),
        "categoryId": snippet.get("categoryId", ""),
        "tags": snippet.get("tags", []),
        "publishedAt": snippet.get("publishedAt", ""),
        "description": snippet.get("description", ""),
        "thumbnail": thumbnail_url,
        "views": int(stats.get("viewCount", 0)),
        "commentCount": int(stats.get("commentCount", 0)),
        "likeCount": int(stats.get("likeCount", 0)),
    }


def fetch_channel_metadata(channel_id: str) -> Dict[str, Any]:
    """Fetch metadata and statistics for the video's channel."""
    data = _get(
        "channels",
        {"part": "snippet,statistics,brandingSettings,contentDetails", "id": channel_id},
    )

    items = data.get("items", [])
    if not items:
        return {}

    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    branding = item.get("brandingSettings", {}).get("channel", {})
    content_details = item.get("contentDetails", {})

    return {
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "publishedAt": snippet.get("publishedAt", ""),
        "country": snippet.get("country", ""),
        "customUrl": snippet.get("customUrl", ""),
        "keywords": branding.get("keywords", ""),
        "subscriberCount": _safe_int(stats.get("subscriberCount")),
        "videoCount": _safe_int(stats.get("videoCount")),
        "viewCount": _safe_int(stats.get("viewCount")),
        "subscriberCountHidden": bool(stats.get("hiddenSubscriberCount", False)),
        "uploadsPlaylistId": content_details.get("relatedPlaylists", {}).get("uploads", ""),
    }


def fetch_recent_channel_videos(
    channel_id: str,
    exclude_video_id: str,
    max_results: int = 12,
    uploads_playlist_id: str = "",
) -> List[Dict[str, Any]]:
    """Fetch recent uploads from the same channel for baseline comparison."""
    if uploads_playlist_id:
        return fetch_channel_upload_history(
            uploads_playlist_id=uploads_playlist_id,
            exclude_video_id=exclude_video_id,
            max_results=max_results,
        )

    search_data = _get(
        "search",
        {
            "part": "snippet",
            "channelId": channel_id,
            "order": "date",
            "type": "video",
            "maxResults": min(max_results + 3, 25),
        },
    )

    video_ids: List[str] = []
    for item in search_data.get("items", []):
        candidate = item.get("id", {}).get("videoId", "")
        if candidate and candidate != exclude_video_id:
            video_ids.append(candidate)
    video_ids = video_ids[:max_results]

    if not video_ids:
        return []

    video_data = _get(
        "videos",
        {"part": "snippet,statistics", "id": ",".join(video_ids)},
    )

    recent: List[Dict[str, Any]] = []
    for item in video_data.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        recent.append(
            {
                "videoId": item.get("id", ""),
                "title": snippet.get("title", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "description": snippet.get("description", ""),
                "views": _safe_int(stats.get("viewCount")) or 0,
                "likeCount": _safe_int(stats.get("likeCount")) or 0,
                "commentCount": _safe_int(stats.get("commentCount")) or 0,
            }
        )

    return recent


def fetch_channel_upload_history(
    uploads_playlist_id: str,
    exclude_video_id: str = "",
    max_results: int = 40,
) -> List[Dict[str, Any]]:
    """Fetch a channel upload-history sample from its uploads playlist."""
    if not uploads_playlist_id:
        return []

    playlist_data = _get(
        "playlistItems",
        {
            "part": "contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": min(max_results + 5, 50),
        },
    )

    video_ids: List[str] = []
    for item in playlist_data.get("items", []):
        candidate = item.get("contentDetails", {}).get("videoId", "")
        if candidate and candidate != exclude_video_id:
            video_ids.append(candidate)
    video_ids = video_ids[:max_results]

    if not video_ids:
        return []

    return _fetch_videos_by_ids(video_ids)


def fetch_video_playlist_context(
    channel_id: str,
    video_id: str,
    max_playlists: int = 8,
) -> Dict[str, Any]:
    """Find whether the video appears inside one of the channel's visible playlists."""
    playlist_data = _get(
        "playlists",
        {
            "part": "snippet,contentDetails",
            "channelId": channel_id,
            "maxResults": min(max_playlists, 25),
        },
    )

    matches: List[Dict[str, Any]] = []
    for playlist in playlist_data.get("items", [])[:max_playlists]:
        playlist_id = playlist.get("id", "")
        if not playlist_id:
            continue

        item_data = _get(
            "playlistItems",
            {
                "part": "contentDetails,snippet",
                "playlistId": playlist_id,
                "maxResults": 50,
            },
        )
        item_titles = []
        for item in item_data.get("items", []):
            item_titles.append(item.get("snippet", {}).get("title", ""))
            candidate = item.get("contentDetails", {}).get("videoId", "")
            if candidate == video_id:
                matches.append(
                    {
                        "playlistId": playlist_id,
                        "title": playlist.get("snippet", {}).get("title", ""),
                        "description": playlist.get("snippet", {}).get("description", ""),
                        "itemCount": int(playlist.get("contentDetails", {}).get("itemCount", 0)),
                        "sampleTitles": item_titles[:5],
                    }
                )
                break

    return {
        "playlistMatches": matches,
        "matched": bool(matches),
    }


def _fetch_videos_by_ids(video_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch a normalized list of videos for the given IDs."""
    video_data = _get(
        "videos",
        {"part": "snippet,statistics", "id": ",".join(video_ids)},
    )

    videos: List[Dict[str, Any]] = []
    for item in video_data.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        videos.append(
            {
                "videoId": item.get("id", ""),
                "title": snippet.get("title", ""),
                "publishedAt": snippet.get("publishedAt", ""),
                "description": snippet.get("description", ""),
                "views": _safe_int(stats.get("viewCount")) or 0,
                "likeCount": _safe_int(stats.get("likeCount")) or 0,
                "commentCount": _safe_int(stats.get("commentCount")) or 0,
            }
        )

    return videos


def fetch_comments(
    video_id: str,
    max_results: int = 50,
    order: str = "relevance",
) -> Tuple[List[CommentRecord], bool]:
    """
    Fetch top-level comment threads for a video.

    Returns a tuple of (list_of_CommentRecord, comments_enabled).
    If comments are disabled or unavailable, returns ([], False) rather than raising.

    Args:
        video_id:    The YouTube video ID.
        max_results: Maximum number of comments to retrieve (capped at 100 per API call).
        order:       "relevance" or "time".
    """
    if not config.YOUTUBE_API_KEY:
        return [], False

    params: Dict[str, Any] = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_results, 100),
        "order": order,
        "textFormat": "plainText",
    }

    try:
        data = _get("commentThreads", params)
    except AnalysisError:
        # Comments are sometimes disabled (403 commentsDisabled).
        # We re-check by inspecting the raw response instead of crashing.
        return [], False

    items = data.get("items", [])
    comments: List[CommentRecord] = []

    for item in items:
        top = item.get("snippet", {}).get("topLevelComment", {})
        cs = top.get("snippet", {})

        text = cs.get("textOriginal") or cs.get("textDisplay", "")
        author = cs.get("authorDisplayName", "Unknown")
        likes = int(cs.get("likeCount", 0))
        published = cs.get("publishedAt", "")
        reply_count = int(item.get("snippet", {}).get("totalReplyCount", 0))

        comments.append(
            CommentRecord(
                author=author,
                text=text,
                likeCount=likes,
                publishedAt=published,
                replyCount=reply_count,
            )
        )

    return comments, True


def _safe_int(value: Any) -> Optional[int]:
    """Parse an API integer field conservatively."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_comments_safe(
    video_id: str,
    max_results: int = 50,
    order: str = "relevance",
) -> Tuple[List[CommentRecord], bool]:
    """
    Wrapper around fetch_comments that captures HTTP-level 403 commentsDisabled errors
    without crashing the whole program.

    Returns (comments, enabled_flag).
    """
    params: Dict[str, Any] = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_results, 100),
        "order": order,
        "textFormat": "plainText",
        "key": config.YOUTUBE_API_KEY,
    }
    url = f"{config.YOUTUBE_API_BASE}/commentThreads"

    try:
        response = requests.get(url, params=params, timeout=15)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        debug_log("[WARN] Could not fetch comments (network issue). Continuing without them.")
        return [], False

    if response.status_code == 403:
        body = {}
        try:
            body = response.json()
        except ValueError:
            pass
        reason = _extract_error_reason(body)
        if reason in ("commentsDisabled", "forbidden"):
            debug_log(f"[INFO] Comments are disabled for this video (reason: {reason}).")
            return [], False
        # Quota / auth error — let the normal handler deal with it
        if reason in ("quotaExceeded", "dailyLimitExceeded"):
            fatal("YouTube API quota exceeded.")
        fatal(f"YouTube API 403 on comments endpoint. Reason: {reason}")

    if not response.ok:
        debug_log(f"[WARN] Failed to fetch comments (HTTP {response.status_code}). Continuing without them.")
        return [], False

    try:
        data = response.json()
    except ValueError:
        debug_log("[WARN] Malformed response from comments endpoint. Continuing without them.")
        return [], False

    items = data.get("items", [])
    comments: List[CommentRecord] = []

    for item in items:
        top = item.get("snippet", {}).get("topLevelComment", {})
        cs = top.get("snippet", {})

        text = cs.get("textOriginal") or cs.get("textDisplay", "")
        author = cs.get("authorDisplayName", "Unknown")
        likes = int(cs.get("likeCount", 0))
        published = cs.get("publishedAt", "")
        reply_count = int(item.get("snippet", {}).get("totalReplyCount", 0))

        comments.append(
            CommentRecord(
                author=author,
                text=text,
                likeCount=likes,
                publishedAt=published,
                replyCount=reply_count,
            )
        )

    return comments, True
