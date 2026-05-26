from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ToolCall:
    name: str
    input: dict


@dataclass
class Turn:
    role: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    estimated_tokens: int = 0


@dataclass
class Session:
    session_id: str
    transcript_path: Path
    project_slug: str
    turns: list[Turn] = field(default_factory=list)
    modified_at: datetime | None = None

    @property
    def user_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "user"]

    @property
    def assistant_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "assistant"]

    @property
    def estimated_tokens(self) -> int:
        return sum(t.estimated_tokens for t in self.turns)


@dataclass
class WasteFinding:
    code: str
    title: str
    severity: str  # low | medium | high
    detail: str
    suggestion: str
    score: int = 0


@dataclass
class SessionAnalysis:
    session: Session
    findings: list[WasteFinding] = field(default_factory=list)
    estimated_tokens: int = 0
    waste_score: int = 0

    @property
    def primary_finding(self) -> WasteFinding | None:
        if not self.findings:
            return None
        return max(self.findings, key=lambda f: f.score)


@dataclass
class AnalysisReport:
    project_path: Path | None
    sessions: list[SessionAnalysis] = field(default_factory=list)
    scanned_transcripts: int = 0

    @property
    def total_estimated_tokens(self) -> int:
        return sum(s.estimated_tokens for s in self.sessions)

    @property
    def aggregate_findings(self) -> list[WasteFinding]:
        counts: dict[str, WasteFinding] = {}
        for sa in self.sessions:
            for f in sa.findings:
                if f.code not in counts:
                    counts[f.code] = WasteFinding(
                        code=f.code,
                        title=f.title,
                        severity=f.severity,
                        detail=f.detail,
                        suggestion=f.suggestion,
                        score=0,
                    )
                counts[f.code].score += f.score
        return sorted(counts.values(), key=lambda x: x.score, reverse=True)
