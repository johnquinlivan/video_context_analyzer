"""
YouTube analysis router for video_context_analyzer.

Accepts a YouTube video URL, runs the analysis pipeline, and returns a
normalized ``VideoContextReport``.
"""

from __future__ import annotations

from app import config, summarizer, youtube_service
from app.models import VideoContextReport
from app.utils import debug_log, extract_video_id, fatal


# ── Public router ─────────────────────────────────────────────────────────────


def analyze(url: str) -> VideoContextReport:
    """Analyze a YouTube URL and return a ``VideoContextReport``."""
    debug_log("      Platform    : YouTube")
    return _analyze_youtube(url)


# ── YouTube pipeline ──────────────────────────────────────────────────────────


def _analyze_youtube(url: str) -> VideoContextReport:
    """Full YouTube analysis via YouTube Data API v3."""
    if not config.YOUTUBE_API_KEY:
        fatal(
            "YOUTUBE_API_KEY is missing.\n"
            "  Steps to fix:\n"
            "    1. Copy .env.example to .env\n"
            "    2. Set YOUTUBE_API_KEY=<your key>\n"
            "    3. Re-run: python -m app.main"
        )

    try:
        video_id = extract_video_id(url)
    except ValueError as exc:
        fatal(str(exc))

    debug_log(f"      Video ID    : {video_id}")

    debug_log("\n[2/5] Fetching video and channel metadata from YouTube Data API v3…")
    meta = youtube_service.fetch_video_metadata(video_id)
    channel = youtube_service.fetch_channel_metadata(meta["channelId"])
    debug_log(f"      Title       : {meta['title']}")
    debug_log(f"      Channel     : {meta['channelName']}")
    debug_log(f"      Published   : {meta['publishedAt']}")
    debug_log(f"      Views       : {meta['views']:,}")
    debug_log(f"      Comments    : {meta['commentCount']:,}")
    debug_log(f"      Likes       : {meta['likeCount']:,}")

    debug_log(
        f"\n[3/5] Fetching recent channel uploads and up to {config.DEFAULT_COMMENT_LIMIT} comments…"
    )
    recent_videos = youtube_service.fetch_recent_channel_videos(
        channel_id=meta["channelId"],
        exclude_video_id=video_id,
        max_results=config.RECENT_UPLOAD_BASELINE_SIZE,
        uploads_playlist_id=channel.get("uploadsPlaylistId", ""),
    )
    history_videos = youtube_service.fetch_channel_upload_history(
        uploads_playlist_id=channel.get("uploadsPlaylistId", ""),
        exclude_video_id=video_id,
        max_results=config.CHANNEL_HISTORY_SAMPLE_SIZE,
    )
    playlist_context = youtube_service.fetch_video_playlist_context(
        channel_id=meta["channelId"],
        video_id=video_id,
        max_playlists=config.PLAYLIST_SCAN_LIMIT,
    )
    comments, comments_enabled = youtube_service.fetch_comments_safe(
        video_id=video_id,
        max_results=config.DEFAULT_COMMENT_LIMIT,
        order=config.COMMENT_ORDER,
    )
    debug_log(f"      Baseline    : {len(recent_videos)} recent uploads")
    debug_log(f"      History     : {len(history_videos)} upload sample")
    debug_log(f"      Playlists   : {len(playlist_context.get('playlistMatches', []))} matches")
    debug_log(f"      Retrieved   : {len(comments)} comments  (enabled={comments_enabled})")

    debug_log("\n[4/5] Running summarization…")
    meta["playlistContext"] = playlist_context
    meta["historyVideos"] = history_videos
    summary = summarizer.summarize(
        video=meta,
        channel=channel,
        recent_videos=recent_videos,
        comments=comments,
        comments_enabled=comments_enabled,
    )

    return VideoContextReport(
        videoId=video_id,
        videoUrl=f"https://www.youtube.com/watch?v={video_id}",
        title=meta["title"],
        channelName=meta["channelName"],
        channelId=meta["channelId"],
        publishedAt=meta["publishedAt"],
        views=meta["views"],
        commentCount=meta["commentCount"],
        likeCount=meta["likeCount"],
        channelContextSummary=summary["channelContextSummary"],
        videoContextSummary=summary["videoContextSummary"],
        freshnessSummary=summary["freshnessSummary"],
        contentIntent=summary["contentIntent"],
        contextRiskScore=summary["contextRiskScore"],
        channelFit=summary["channelFit"],
        riskFlags=summary["riskFlags"],
        narrativeSignals=summary["narrativeSignals"],
        dataAvailability={
            "channelName": True,
            "channelId": True,
            "publishedAt": True,
            "views": True,
            "commentCount": True,
            "likeCount": True,
            "description": True,
            "comments": comments_enabled,
            "channelContext": bool(channel),
            "recentUploadsBaseline": bool(recent_videos),
            "descriptionLinks": bool(summary["descriptionDomains"]),
            "playlistContext": bool(playlist_context.get("playlistMatches")),
            "channelHistory": bool(history_videos),
            "freshnessSignals": bool(summary["freshnessSignals"]),
        },
        descriptionDomains=summary["descriptionDomains"],
        playlistContext=summary["playlistContext"],
        channelTopicClusters=summary["channelTopicClusters"],
        freshnessSignals=summary["freshnessSignals"],
        engagementProfile=summary["engagementProfile"],
        commentDynamics=summary["commentDynamics"],
    )
