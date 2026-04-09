"""
CLI entry point for video_context_analyzer.

Run with:
    python -m app.main <youtube_url>

Prints the analysis report as JSON to stdout.
"""

from __future__ import annotations

import json
import sys

from app.api import analyze_video_context
from app.utils import AnalysisError


def main() -> None:
    try:
        url = sys.argv[1]
    except IndexError:
        print("Usage: python -m app.main <youtube_url>", file=sys.stderr)
        raise SystemExit(2)

    try:
        report = analyze_video_context(url)
    except (AnalysisError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

    print(json.dumps(report, ensure_ascii=False, indent=2))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
