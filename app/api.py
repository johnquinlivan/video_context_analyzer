"""
Public API for embedding video_context_analyzer in a larger application.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from app import analyzer_router
from app.utils import AnalysisError, validate_youtube_url


def analyze_video_context(url: str) -> Dict[str, Any]:
    """
    Analyze a YouTube URL and return a JSON-serializable report dict.

    Raises:
        ValueError: if the URL is not a supported YouTube URL.
        AnalysisError: if analysis fails due to API or data issues.
    """
    validate_youtube_url(url)
    report = analyzer_router.analyze(url)
    return report.to_dict()


def analyze_video_context_json(url: str) -> str:
    """Analyze a YouTube URL and return the report as a JSON string."""
    return json.dumps(analyze_video_context(url), ensure_ascii=False)
