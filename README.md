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

- Core video fields such as `videoId`, `videoUrl`, `title`, `channelName`, `channelId`, `publishedAt`, `views`, `commentCount`, and `likeCount`
- Compact context summaries such as `channelContextSummary`, `videoContextSummary`, and `freshnessSummary`
- Inference fields such as `contentIntent`, `contextRiskScore`, `channelFit`, `riskFlags`, and `narrativeSignals`
- Structured supporting data such as `descriptionDomains`, `playlistContext`, `channelTopicClusters`, `freshnessSignals`, `engagementProfile`, `commentDynamics`, and `dataAvailability`
- `dataAvailability` flags so the caller can see which sections were actually populated

This makes the module suitable for use as an enrichment step inside a larger pipeline.

## How Key Outputs Are Calculated

The module combines direct YouTube API fields with heuristic inference. The most important outputs should be interpreted as context signals, not facts.

### `freshnessSummary`

`freshnessSummary` is a short human-readable explanation derived from:

- the video's `publishedAt` timestamp
- urgency/currentness terms in the title or description, such as `today`, `breaking`, `live`, `just happened`, or `happening now`
- viewer reactions in comments, such as `this is old`, `repost`, `out of context`, or `misleading title`

Meaning:

- If it says no strong freshness mismatch was detected, the module did not see obvious metadata/comment cues that the video is being recirculated misleadingly.
- If it mentions freshness mismatch, the title/description makes the video sound current but the publish date is significantly older.
- If it mentions repost or misleading-title cues, viewers are explicitly reacting as if the framing is recycled, wrong, or contextually misleading.

This field is especially useful for identifying:

- real but old footage framed as current
- recycled uploads
- authentic media used misleadingly through timing or framing

### `freshnessSignals`

`freshnessSignals` is the structured version of `freshnessSummary`.

Possible values:

- `freshness_mismatch`
  Meaning: the title/description suggests current urgency, but the upload date is materially older.
- `stale_but_currently_framed`
  Meaning: a stronger version of freshness mismatch where the video is substantially old yet framed like current news.
- `possible_repost`
  Meaning: comments suggest the upload may be recycled or previously seen.
- `possible_misleading_title`
  Meaning: comments suggest the title or framing is inaccurate or clickbait-like.
- `viewer_dates_it_as_old`
  Meaning: viewers are explicitly saying the footage or upload is not recent.

### `contentIntent`

`contentIntent` is inferred from title, description, and channel text using keyword-pattern heuristics.

Possible values:

- `reporting`
- `commentary`
- `reaction`
- `satire/comedy`
- `tutorial`
- `promotion`
- `testimonial`
- `clip`
- `call_to_action`
- `general`

Meaning:

- This is the module's estimate of how the uploader is framing the content, not what the video objectively is.
- It is most useful for downstream interpretation. For example, a factual claim inside `satire/comedy` should be treated differently from the same claim inside `reporting`.

### `channelFit`

`channelFit` is calculated by comparing the video title against recent uploads from the same channel.

Possible values:

- `typical of the channel's recent uploads`
- `somewhat atypical`
- `atypical for this channel`
- `baseline unavailable`

Meaning:

- `typical` suggests the upload matches the channel's recent topics and style.
- `somewhat atypical` suggests partial mismatch.
- `atypical` suggests the video stands out relative to recent uploads and may reflect opportunistic posting, a narrative pivot, or an unusual topic.
- `baseline unavailable` means the module could not gather enough recent uploads to compare.

### `contextRiskScore`

`contextRiskScore` is a 0-100 heuristic score that combines:

- topic-sensitive `riskFlags`
- metadata-level `narrativeSignals`
- freshness/repost cues from `freshnessSignals`
- comment pushback from `commentDynamics`
- whether the upload looks unusual via `channelFit`

Meaning:

- Lower scores suggest fewer contextual red flags.
- Mid-range scores suggest mixed or moderate contextual concern.
- Higher scores suggest stronger signs of contextual risk, such as sensitive topics combined with misleading framing, viewer correction attempts, or freshness mismatch.

This is **not** a truth score and **not** an authenticity score.

### `riskFlags`

`riskFlags` are topic labels inferred from keywords across the title, description, channel text, and comments.

Possible values currently include:

- `politics`
- `elections`
- `war/conflict`
- `public health`
- `finance/investing`
- `conspiracy`
- `medical claims`
- `breaking news`
- `AI-generated`
- `deepfake`

Meaning:

- These flags indicate topic sensitivity, not proof that the video is false or dangerous.
- They are best used to route the video into stricter downstream review.

### `narrativeSignals`

`narrativeSignals` are framing cues inferred from metadata and some comment text.

Possible values currently include:

- `urgent_framing`
- `emotionally_loaded`
- `call_to_action`
- `conspiracy_language`
- `source_missing`
- `viewer_pushback`

Meaning:

- `urgent_framing`: title/description presents the video as immediate or breaking
- `emotionally_loaded`: strong sensational or emotional framing
- `call_to_action`: the uploader is urging the viewer to act, donate, share, join, or support
- `conspiracy_language`: metadata contains language associated with conspiratorial framing
- `source_missing`: the description references evidence or reporting but does not visibly link sources
- `viewer_pushback`: comments contain skepticism, correction attempts, or out-of-context accusations

### `descriptionDomains`

`descriptionDomains` is extracted from all URLs found in the description.

Meaning:

- Empty list: no outbound links were found.
- Social-heavy domains may suggest self-promotion or recirculation.
- Institutional or source-like domains may indicate stronger sourcing.
- Commerce-heavy domains may suggest monetization or promotional intent.

### `playlistContext`

`playlistContext` is built by scanning visible playlists on the channel and checking whether the video appears in them.

Meaning:

- If matches exist, the video may be part of a series, campaign, recurring topic, or editorial grouping.
- If empty, no visible playlist membership was detected in the scanned playlists.

### `channelTopicClusters`

`channelTopicClusters` is generated from a larger sample of the channel's upload history.

Meaning:

- Each cluster contains a recurring term and an approximate count of how many sampled uploads share it.
- Strong clusters suggest sustained narratives or repeated topical focus.
- Weak or empty clusters suggest no dominant recurring theme was obvious from the sample.

### `engagementProfile`

`engagementProfile` compares the video's views, likes, and comments against recent uploads from the same channel.

Key fields:

- `performanceBand`
- `baselineSampleSize`
- `viewRatioVsRecentAverage`
- `likeRatioVsRecentAverage`
- `commentRatioVsRecentAverage`

Meaning:

- `well above channel baseline`: the upload is outperforming recent norms and may be unusually amplified
- `within normal channel range`: the upload looks broadly normal for the channel
- `below channel baseline`: the upload is underperforming relative to recent uploads
- `unclear`: not enough baseline data

### `commentDynamics`

`commentDynamics` counts coarse patterns in the comment sample.

Current keys:

- `supportive`
- `skeptical`
- `corrective`
- `hostile`
- `source_requesting`
- `polarized`

Meaning:

- `supportive`: comments contain broadly positive/supportive language
- `skeptical`: comments contain doubt, accusations of falsity, or authenticity skepticism
- `corrective`: comments attempt to add correction or missing context
- `hostile`: comments contain aggressive or abusive language
- `source_requesting`: viewers explicitly ask for proof, links, or evidence
- `polarized`: both supportive and skeptical reactions are visibly present

### `dataAvailability`

`dataAvailability` tells the caller which sections were actually populated.

Meaning:

- `true` means the module successfully gathered enough data for that section
- `false` means the data was unavailable, inaccessible, or not detected

This is important for downstream systems so they do not over-interpret missing sections.

## Why This Module Adds Value

This module is most useful when paired with other parts of a larger video-analysis system.

It does **not** determine whether a video is authentic, AI-generated, or a deepfake. It does **not** extract or fact-check the actual claims made in the audiovisual content. Instead, it adds the surrounding context that those systems usually lack.

The key value is that it helps answer questions like:

- Who is posting this video, and what kind of source do they appear to be?
- Is this upload typical for the channel, or is it unusual relative to recent history?
- Does the video appear to be part of a recurring series, playlist, or narrative arc?
- Is the uploader framing the video in an urgent, sensational, weakly sourced, or commercially motivated way?
- Are viewers reacting as if the video is misleading, old, out of context, or recycled?

In practice, the strongest insight this module can provide is often:

- **“This video may be real, but the way it is framed or recirculated is misleading.”**

That makes it especially valuable as a **contextual risk** layer. A separate authenticity model might conclude that the footage is real, and a claim-checking module might verify what is being said, but this module can still add important signals such as:

- likely source type
- channel-level narrative patterns
- freshness mismatch
- repost / misleading-title cues
- weak or absent sourcing in the description
- audience pushback and correction attempts

This is why the output is intentionally oriented around source context, distribution context, framing context, and audience-reaction context.

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
  "videoId": "dQw4w9WgXcQ",
  "videoUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "channelName": "Rick Astley",
  "videoContextSummary": "This appears to be an entertainment video ...",
  "contentIntent": "clip",
  "contextRiskScore": 12,
  "riskFlags": [],
  "descriptionDomains": [],
  "freshnessSignals": []
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
