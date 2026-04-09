# video_context_analyzer

A Python module that takes a YouTube video URL and returns a structured JSON context report about that video.

It is designed to be embedded inside a larger application, not used as a standalone end-user product.

> **This module does not issue a truth verdict.** It estimates context from YouTube metadata, channel history, playlists, description links, and comments so downstream systems or reviewers can reason about the video with more background.

---

## What This Module Does

Input:
- A single YouTube video URL

Output:
- A JSON-serializable Python `dict`
- Or a JSON string if you call the string helper

Given a YouTube URL, the module builds context in several layers:

1. Calls the **YouTube Data API v3** to fetch video metadata (title, channel, publish date, view/like/comment counts, description, thumbnail).
2. Fetches **channel metadata** to infer what kind of source uploaded the video.
3. Fetches recent uploads and a larger upload-history sample from the same channel to estimate channel fit, recurring topics, and performance relative to baseline.
4. Scans visible channel playlists to detect whether the video appears to be part of a series or grouped narrative.
5. Parses links in the description to identify outbound domains and infer whether the description points to social posts, commerce, blogs, or more source-like destinations.
6. Fetches the top comments and profiles visible audience dynamics such as skepticism, correction attempts, hostility, source requests, and polarization.
7. Detects metadata-level cues such as urgent framing, possible freshness mismatch, possible reposting, and misleading-title complaints.
8. Returns a structured JSON report containing both raw fields and inferred context fields.

## What The JSON Contains

The report includes:

- Core video fields such as `videoId`, `videoUrl`, `title`, `channelName`, `publishedAt`, `views`, `commentCount`, and `likeCount`
- Context summaries such as `descriptionSummary`, `channelContextSummary`, `videoContextSummary`, `commentSummary`, `playlistContextSummary`, `channelHistorySummary`, and `freshnessSummary`
- Inference fields such as `contentIntent`, `claimRiskScore`, `contextRiskScore`, `channelFit`, `riskFlags`, `narrativeSignals`, and `topThemes`
- Structured supporting data such as `descriptionDomains`, `playlistContext`, `channelTopicClusters`, `freshnessSignals`, `engagementProfile`, `commentDynamics`, and sampled `comments`
- `dataAvailability` flags so the caller can see which sections were actually populated

This makes the module suitable for use as an enrichment step inside a larger pipeline.

## What It Does Not Do

- It does not watch or interpret the video frames
- It does not determine whether the video is true or false
- It does not use private YouTube data
- It does not require user authentication for public videos
- It does not guarantee that heuristic inferences are correct

---

## Architecture

```
video_context_analyzer/
├── app/
│   ├── __init__.py
│   ├── api.py               # Public embeddable API
│   ├── main.py              # Thin CLI wrapper: URL in, JSON out
│   ├── config.py            # All configuration and environment variable loading
│   ├── models.py            # Data models (VideoContextReport, CommentRecord)
│   ├── youtube_service.py   # YouTube Data API v3 client
│   ├── summarizer.py        # Dispatches to LLM or heuristic summarization
│   ├── heuristics.py        # Heuristic summarization engine (no LLM required)
│   └── utils.py             # YouTube URL parsing, exceptions, and helpers
├── .env.example             # Template for environment variables
├── .gitignore
├── requirements.txt
└── README.md
```

### Analysis modes

| Mode | When used | What it does |
|---|---|---|
| **LLM mode** | `OPENAI_API_KEY` is set | Uses an OpenAI-compatible model to produce richer context summaries and structured inferences |
| **Heuristic mode** | No `OPENAI_API_KEY` | Uses deterministic rules and keyword/pattern analysis only |

The module works fully in heuristic mode. LLM mode is additive.

---

## Setup

### Prerequisites

- Python 3.11 or newer
- A [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) key (free quota: 10,000 units/day)

### Steps

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env and add your YOUTUBE_API_KEY
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `YOUTUBE_API_KEY` | **Yes** | — | YouTube Data API v3 key |
| `OPENAI_API_KEY` | No | — | Enables LLM summarization (OpenAI or compatible) |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | Override for Ollama, Groq, Azure, etc. |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Override the model used for summarization |

---

## Configuration

Edit `app/config.py` to change analysis settings:

```python
DEFAULT_COMMENT_LIMIT = 50    # max comments to fetch
COMMENT_ORDER = "relevance"   # "relevance" or "time"
RECENT_UPLOAD_BASELINE_SIZE = 12
```

---

## Public API

Primary entry points:

- `analyze_video_context(url)` returns a JSON-serializable Python `dict`
- `analyze_video_context_json(url)` returns the same report as a JSON string
- `AnalysisError` is raised for analysis failures such as API errors or missing video data

Example:

```python
from app import AnalysisError, analyze_video_context

try:
    report = analyze_video_context("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
except ValueError:
    # invalid or unsupported URL
    ...
except AnalysisError:
    # API/data failure
    ...
```

## CLI Wrapper

The repository also includes a small CLI wrapper that prints the JSON report to stdout:

```bash
python -m app.main "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

---

## Sample JSON Output

```json
{
  "platform": "YouTube",
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "channelName": "Rick Astley",
  "descriptionSummary": "The official music video for 'Never Gonna Give You Up' by Rick Astley.",
  "videoContextSummary": "This appears to be an entertainment video ...",
  "commentSummary": "Analyzed 50 comments. The overall tone is mostly positive.",
  "contentIntent": "clip",
  "contextRiskScore": 12,
  "topThemes": ["never", "gonna", "give", "rick", "love"]
}
```

---

## Supported YouTube URL Formats

The module handles all common YouTube URL shapes:

```
https://www.youtube.com/watch?v=VIDEOID
https://youtu.be/VIDEOID
https://www.youtube.com/shorts/VIDEOID
https://www.youtube.com/embed/VIDEOID
```

Additional query parameters (e.g. `&t=30s`, `&list=...`) are safely ignored.

---

## Limitations

- **No streaming or live video support** — the tool analyzes published videos only.
- **Public-video scope only** — private or inaccessible videos cannot be analyzed.
- **No video-frame understanding** — all inference is based on YouTube API metadata and comments, not the audiovisual content itself.
- **Comment pagination** — fetches up to 100 comments per API call (YouTube API limit). A second call would be needed for more.
- **Heuristic accuracy** — the non-LLM inference layer is keyword- and pattern-based, so intent classification, channel-fit estimates, and risk scoring are useful but approximate.
- **YouTube API quota** — the free tier provides 10,000 units/day. Each run costs roughly 3–5 units. Quota resets at midnight Pacific Time.
- **No authentication** — only public videos can be analyzed.

---

## Potential Next Steps

- Add multi-video batch mode (analyze a list of URLs)
- Add pagination to retrieve more than 100 comments
- Add a proper claim-extraction pass over comments
- Integrate with a fact-checking API (e.g. ClaimBuster, Google Fact Check Tools)
- Add channel-level analysis (subscriber count, upload history)
- Export to a structured claim worksheet format

---

## Disclaimer

This module is a **context-enrichment component**. It is not a production-grade misinformation detection system. All summaries, risk scores, and signals are heuristic or LLM-generated estimates and should be treated as supporting context, not conclusions.
