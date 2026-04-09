"""
Summarization layer for video_context_analyzer.

Dispatches to either:
  - LLM mode  (if OPENAI_API_KEY is set) via an OpenAI-compatible chat completion API
  - Heuristic mode (always available as fallback)

The public function `summarize()` is the only entry-point called by main.py.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

import requests

from app import config, heuristics
from app.models import CommentRecord
from app.utils import debug_log


# ── Public entry point ────────────────────────────────────────────────────────


def summarize(
    video: Dict[str, Any],
    channel: Dict[str, Any],
    recent_videos: List[Dict[str, Any]],
    comments: List[CommentRecord],
    comments_enabled: bool,
) -> Dict[str, Any]:
    """
    Produce summarization fields for the video context report.

    Returns a dict with keys:
        descriptionSummary, channelContextSummary, videoContextSummary,
        commentSummary, contentIntent, claimRiskScore, contextRiskScore,
        contextRiskSummary, channelFit, topThemes, riskFlags,
        narrativeSignals, engagementProfile, commentDynamics,
        descriptionLinkSummary, playlistContextSummary, channelHistorySummary,
        freshnessSummary, descriptionDomains, playlistContext,
        channelTopicClusters, freshnessSignals
    """
    if config.OPENAI_API_KEY:
        debug_log("[INFO] OPENAI_API_KEY detected — using LLM summarization mode.")
        try:
            return _llm_summarize(
                video=video,
                channel=channel,
                recent_videos=recent_videos,
                comments=comments,
                comments_enabled=comments_enabled,
            )
        except Exception as exc:
            debug_log(f"[WARN] LLM summarization failed ({exc}). Falling back to heuristics.")

    debug_log("[INFO] Using heuristic summarization mode.")
    return _heuristic_summarize(
        video=video,
        channel=channel,
        recent_videos=recent_videos,
        comments=comments,
        comments_enabled=comments_enabled,
    )


# ── Heuristic mode ────────────────────────────────────────────────────────────


def _heuristic_summarize(
    video: Dict[str, Any],
    channel: Dict[str, Any],
    recent_videos: List[Dict[str, Any]],
    comments: List[CommentRecord],
    comments_enabled: bool,
) -> Dict[str, Any]:
    title = video.get("title", "")
    channel_name = video.get("channelName", "")
    description = video.get("description", "")
    views = video.get("views")

    source_type = heuristics.infer_source_type(
        channel_name,
        title,
        f"{description} {channel.get('description', '')} {channel.get('keywords', '')}",
    )
    description_links = heuristics.analyze_description_links(description)
    playlist_context = video.get("playlistContext", {})
    history_videos = video.get("historyVideos", [])
    topic_clusters = heuristics.cluster_channel_topics(history_videos)
    freshness = heuristics.analyze_freshness_and_repost_signals(
        title=title,
        description=description,
        published_at=video.get("publishedAt", ""),
        comments=comments,
    )
    content_intent = heuristics.infer_content_intent(channel_name, title, description)
    engagement_profile = heuristics.build_engagement_profile(video, recent_videos)
    channel_fit = heuristics.analyze_channel_fit(video, recent_videos)
    comment_dynamics = heuristics.analyze_comment_dynamics(comments, comments_enabled)
    narrative_signals = heuristics.infer_narrative_signals(title, description, comments)
    risk_flags = heuristics.infer_risk_flags(title, description, channel_name, comments)
    claim_risk_score = heuristics.infer_claim_risk_score(
        title=title,
        description=description,
        content_intent=content_intent,
        risk_flags=risk_flags,
        narrative_signals=narrative_signals,
    )
    context_risk_score, context_risk_summary = heuristics.summarize_context_risk(
        claim_risk_score=claim_risk_score,
        risk_flags=risk_flags,
        narrative_signals=narrative_signals,
        comment_dynamics=comment_dynamics,
        channel_fit=channel_fit,
        freshness_signals=freshness["signals"],
    )

    return {
        "descriptionSummary": heuristics.summarize_description(description),
        "channelContextSummary": heuristics.summarize_channel_context(channel, source_type),
        "videoContextSummary": heuristics.build_video_context_summary(
            channel_name=channel_name,
            title=title,
            description=description,
            source_type=source_type,
            content_intent=content_intent,
            views=views,
            channel_fit=channel_fit,
            engagement_profile=engagement_profile,
        ),
        "commentSummary": heuristics.summarize_comments(comments, comments_enabled),
        "descriptionLinkSummary": description_links["summary"],
        "playlistContextSummary": heuristics.analyze_playlist_context(playlist_context),
        "channelHistorySummary": heuristics.summarize_channel_history(history_videos, topic_clusters),
        "freshnessSummary": freshness["summary"],
        "contentIntent": content_intent,
        "claimRiskScore": claim_risk_score,
        "contextRiskScore": context_risk_score,
        "contextRiskSummary": context_risk_summary,
        "channelFit": channel_fit,
        "topThemes": heuristics.extract_top_themes(comments, title, description),
        "riskFlags": risk_flags,
        "narrativeSignals": narrative_signals,
        "descriptionDomains": description_links["domains"],
        "playlistContext": playlist_context,
        "channelTopicClusters": topic_clusters,
        "freshnessSignals": freshness["signals"],
        "engagementProfile": engagement_profile,
        "commentDynamics": comment_dynamics,
    }


# ── LLM mode ──────────────────────────────────────────────────────────────────


def _llm_summarize(
    video: Dict[str, Any],
    channel: Dict[str, Any],
    recent_videos: List[Dict[str, Any]],
    comments: List[CommentRecord],
    comments_enabled: bool,
) -> Dict[str, Any]:
    """
    Use an OpenAI-compatible chat completion API to produce structured summaries.
    Returns the same dict shape as _heuristic_summarize.
    """
    title = video.get("title", "")
    channel_name = video.get("channelName", "")
    description = video.get("description", "")
    views = video.get("views")

    comment_block = _format_comments_for_prompt(comments, comments_enabled)
    recent_block = _format_recent_videos_for_prompt(recent_videos)
    history_block = _format_recent_videos_for_prompt(video.get("historyVideos", []))
    playlist_block = json.dumps(video.get("playlistContext", {}), ensure_ascii=False)
    description_link_block = json.dumps(
        heuristics.analyze_description_links(description),
        ensure_ascii=False,
    )

    system_prompt = (
        "You are a neutral media analyst assisting with fact-checking preparation. "
        "Your role is to establish the context of a video BEFORE any fact-checking occurs. "
        "You do NOT issue truth verdicts. You do NOT invent facts. "
        "You summarize only what is supported by the provided data."
    )

    user_prompt = f"""Analyze the following video data and return a JSON object with exactly these keys:
- descriptionSummary: A concise 1–3 sentence summary of the video description. If empty, say so.
- channelContextSummary: 1–3 sentences describing the channel type, scale, and any notable metadata context.
- videoContextSummary: 1–3 sentences identifying the probable source type and the nature of the content, including whether this upload looks typical or atypical versus recent uploads.
- commentSummary: 1–3 sentences summarizing the overall public reaction visible in the comments. Note sentiment, major themes, and any notable disagreements or corrections.
- descriptionLinkSummary: 1–2 sentences describing what kinds of domains are linked in the video description and what that implies about sourcing or promotion.
- playlistContextSummary: 1–2 sentences describing whether the video appears to belong to a playlist/series and what that suggests.
- channelHistorySummary: 1–2 sentences summarizing the channel's recurring topics from a larger upload-history sample.
- freshnessSummary: 1–2 sentences describing any freshness mismatch, repost, or misleading-title cues seen in metadata/comments.
- contentIntent: One short label from this set only: reporting, commentary, reaction, satire/comedy, tutorial, promotion, testimonial, clip, call_to_action, general
- claimRiskScore: Integer from 0 to 100 estimating how strongly the title/description imply sensitive factual claims.
- contextRiskScore: Integer from 0 to 100 combining text framing, topic sensitivity, comment pushback, and channel-fit signals.
- contextRiskSummary: 1–2 sentences explaining the main drivers of contextRiskScore.
- channelFit: One short phrase describing whether the upload appears typical or atypical for the channel.
- topThemes: A JSON array of 3–6 short keyword strings representing the main topics discussed.
- riskFlags: A JSON array of relevant risk-sensitive labels from this set only: politics, elections, war/conflict, public health, finance/investing, conspiracy, medical claims, breaking news, AI-generated, deepfake. Only include flags that are clearly supported by the data. Return an empty array if none apply.
- narrativeSignals: A JSON array of short labels describing metadata-level framing signals such as urgent_framing, emotionally_loaded, call_to_action, conspiracy_language, source_missing, viewer_pushback.
- descriptionDomains: A JSON array of linked domains found in the description.
- playlistContext: A JSON object summarizing playlist matches.
- channelTopicClusters: A JSON array of objects with labels and approximate recurring-video counts from channel history.
- freshnessSignals: A JSON array of short labels such as freshness_mismatch, stale_but_currently_framed, possible_repost, possible_misleading_title, viewer_dates_it_as_old.
- engagementProfile: A JSON object with concise fields summarizing relative performance against recent uploads. Include at least: performanceBand, baselineSampleSize, summary.
- commentDynamics: A JSON object with integer counts for supportive, skeptical, corrective, hostile, source_requesting, polarized.

VIDEO DATA:
Title: {title}
Channel: {channel_name}
Views: {f"{views:,}" if views is not None else "unavailable"}
Description:
{description[:1500]}

CHANNEL METADATA:
{json.dumps(channel, ensure_ascii=False)}

RECENT CHANNEL UPLOADS:
{recent_block}

PLAYLIST CONTEXT:
{playlist_block}

LARGER CHANNEL HISTORY SAMPLE:
{history_block}

DESCRIPTION LINK ANALYSIS:
{description_link_block}

{comment_block}

Return ONLY a valid JSON object. No explanation. No markdown fences."""

    response = _call_openai(system_prompt, user_prompt)
    return _parse_llm_json(response)


def _format_comments_for_prompt(
    comments: List[CommentRecord],
    comments_enabled: bool,
) -> str:
    if not comments_enabled:
        return "Comments: DISABLED — comments are turned off for this video."
    if not comments:
        return "Comments: NONE — no comments were retrieved."

    lines = [f"Top {len(comments)} comments:"]
    for i, c in enumerate(comments[:30], 1):  # send at most 30 to limit tokens
        lines.append(f"  {i}. [{c.likeCount} likes] {c.author}: {c.text[:200]}")
    return "\n".join(lines)


def _format_recent_videos_for_prompt(recent_videos: List[Dict[str, Any]]) -> str:
    if not recent_videos:
        return "No recent uploads were available."
    lines = []
    for i, video in enumerate(recent_videos[:12], 1):
        lines.append(
            f"{i}. {video.get('title', '')[:120]} | {video.get('views', 0)} views | "
            f"{video.get('likeCount', 0)} likes | {video.get('commentCount', 0)} comments"
        )
    return "\n".join(lines)


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    """
    POST to the OpenAI-compatible chat completions endpoint.
    Returns the assistant message content as a string.
    """
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Could not reach the OpenAI API endpoint.")
    except requests.exceptions.Timeout:
        raise RuntimeError("OpenAI API request timed out.")

    if not resp.ok:
        raise RuntimeError(f"OpenAI API returned HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected OpenAI response shape: {data}") from exc


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    """
    Parse and validate the JSON returned by the LLM.
    Falls back gracefully if the LLM returns malformed output.
    """
    # Strip optional markdown fences the model may have added despite instructions
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:])
    if cleaned.endswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[:-1])
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM returned invalid JSON: {exc}\nRaw output:\n{raw[:500]}")

    required_keys = {
        "descriptionSummary", "channelContextSummary", "videoContextSummary",
        "commentSummary", "contentIntent", "claimRiskScore", "contextRiskScore",
        "contextRiskSummary", "channelFit", "topThemes", "riskFlags",
        "narrativeSignals", "engagementProfile", "commentDynamics",
        "descriptionLinkSummary", "playlistContextSummary", "channelHistorySummary",
        "freshnessSummary", "descriptionDomains", "playlistContext",
        "channelTopicClusters", "freshnessSignals",
    }
    missing = required_keys - set(result.keys())
    if missing:
        raise RuntimeError(f"LLM JSON missing required keys: {missing}")

    # Ensure list fields are actually lists
    for list_field in ("topThemes", "riskFlags", "narrativeSignals", "descriptionDomains", "freshnessSignals"):
        if not isinstance(result[list_field], list):
            result[list_field] = [str(result[list_field])]

    for int_field in ("claimRiskScore", "contextRiskScore"):
        try:
            result[int_field] = int(result[int_field])
        except (TypeError, ValueError):
            result[int_field] = 0

    if not isinstance(result["engagementProfile"], dict):
        result["engagementProfile"] = {"summary": str(result["engagementProfile"])}
    if not isinstance(result["commentDynamics"], dict):
        result["commentDynamics"] = {}
    if not isinstance(result["playlistContext"], dict):
        result["playlistContext"] = {}
    if not isinstance(result["channelTopicClusters"], list):
        result["channelTopicClusters"] = []

    return result
