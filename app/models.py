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

    videoId: str
    videoUrl: str
    title: str
    channelName: str
    channelId: str
    publishedAt: str
    views: Optional[int]
    commentCount: Optional[int]
    likeCount: Optional[int]
    channelContextSummary: str
    videoContextSummary: str
    freshnessSummary: str
    contentIntent: str
    contextRiskScore: int
    channelFit: str
    riskFlags: List[str]
    narrativeSignals: List[str]
    dataAvailability: Dict[str, bool]
    descriptionDomains: List[str] = field(default_factory=list)
    playlistContext: Dict[str, Any] = field(default_factory=dict)
    channelTopicClusters: List[Dict[str, Any]] = field(default_factory=list)
    freshnessSignals: List[str] = field(default_factory=list)
    engagementProfile: Dict[str, Any] = field(default_factory=dict)
    commentDynamics: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the report to a plain dictionary suitable for JSON output."""
        return {
            "videoId": self.videoId,
            "videoUrl": self.videoUrl,
            "title": self.title,
            "channelName": self.channelName,
            "channelId": self.channelId,
            "publishedAt": self.publishedAt,
            "views": self.views,
            "commentCount": self.commentCount,
            "likeCount": self.likeCount,
            "channelContextSummary": self.channelContextSummary,
            "videoContextSummary": self.videoContextSummary,
            "freshnessSummary": self.freshnessSummary,
            "contentIntent": self.contentIntent,
            "contextRiskScore": self.contextRiskScore,
            "channelFit": self.channelFit,
            "riskFlags": self.riskFlags,
            "narrativeSignals": self.narrativeSignals,
            "dataAvailability": self.dataAvailability,
            "descriptionDomains": self.descriptionDomains,
            "playlistContext": self.playlistContext,
            "channelTopicClusters": self.channelTopicClusters,
            "freshnessSignals": self.freshnessSignals,
            "engagementProfile": self.engagementProfile,
            "commentDynamics": self.commentDynamics,
        }
