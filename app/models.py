"""
Data models for video_context_analyzer.
Uses dataclasses for lightweight, dependency-free modeling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class CommentRecord:
    """Represents a single top-level YouTube comment."""

    author: str
    text: str
    likeCount: int
    publishedAt: str
    replyCount: int


@dataclass
class VideoContextReport:
    """
    Full structured analysis report for a single video.

    This is the canonical output shape for both JSON and console output.
    """

    platform: str
    capabilityLevel: str
    videoId: str
    videoUrl: str
    title: str
    thumbnail: str
    channelName: str
    channelId: str
    publishedAt: str
    views: Optional[int]
    commentCount: Optional[int]
    likeCount: Optional[int]
    descriptionSummary: str
    channelContextSummary: str
    videoContextSummary: str
    commentSummary: str
    descriptionLinkSummary: str
    playlistContextSummary: str
    channelHistorySummary: str
    freshnessSummary: str
    contentIntent: str
    claimRiskScore: int
    contextRiskScore: int
    contextRiskSummary: str
    channelFit: str
    topThemes: List[str]
    riskFlags: List[str]
    narrativeSignals: List[str]
    commentsAnalyzed: int
    dataAvailability: Dict[str, bool]
    descriptionDomains: List[str] = field(default_factory=list)
    playlistContext: Dict[str, Any] = field(default_factory=dict)
    channelTopicClusters: List[Dict[str, Any]] = field(default_factory=list)
    freshnessSignals: List[str] = field(default_factory=list)
    engagementProfile: Dict[str, Any] = field(default_factory=dict)
    commentDynamics: Dict[str, int] = field(default_factory=dict)
    comments: List[CommentRecord] = field(default_factory=list)
    sourceMethods: List[str] = field(default_factory=list)
    extractionNotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the report to a plain dictionary suitable for JSON output."""
        return {
            "platform": self.platform,
            "capabilityLevel": self.capabilityLevel,
            "videoId": self.videoId,
            "videoUrl": self.videoUrl,
            "title": self.title,
            "thumbnail": self.thumbnail,
            "channelName": self.channelName,
            "channelId": self.channelId,
            "publishedAt": self.publishedAt,
            "views": self.views,
            "commentCount": self.commentCount,
            "likeCount": self.likeCount,
            "descriptionSummary": self.descriptionSummary,
            "channelContextSummary": self.channelContextSummary,
            "videoContextSummary": self.videoContextSummary,
            "commentSummary": self.commentSummary,
            "descriptionLinkSummary": self.descriptionLinkSummary,
            "playlistContextSummary": self.playlistContextSummary,
            "channelHistorySummary": self.channelHistorySummary,
            "freshnessSummary": self.freshnessSummary,
            "contentIntent": self.contentIntent,
            "claimRiskScore": self.claimRiskScore,
            "contextRiskScore": self.contextRiskScore,
            "contextRiskSummary": self.contextRiskSummary,
            "channelFit": self.channelFit,
            "topThemes": self.topThemes,
            "riskFlags": self.riskFlags,
            "narrativeSignals": self.narrativeSignals,
            "commentsAnalyzed": self.commentsAnalyzed,
            "dataAvailability": self.dataAvailability,
            "descriptionDomains": self.descriptionDomains,
            "playlistContext": self.playlistContext,
            "channelTopicClusters": self.channelTopicClusters,
            "freshnessSignals": self.freshnessSignals,
            "engagementProfile": self.engagementProfile,
            "commentDynamics": self.commentDynamics,
            "sourceMethods": self.sourceMethods,
            "extractionNotes": self.extractionNotes,
            "comments": [
                {
                    "author": c.author,
                    "text": c.text,
                    "likeCount": c.likeCount,
                    "publishedAt": c.publishedAt,
                    "replyCount": c.replyCount,
                }
                for c in self.comments
            ],
        }
