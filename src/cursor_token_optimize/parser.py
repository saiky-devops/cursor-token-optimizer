from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from cursor_token_optimize.models import Session, ToolCall, Turn

CURSOR_PROJECTS = Path.home() / ".cursor" / "projects"
USER_QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL)
TIMESTAMP_RE = re.compile(r"<timestamp>.*?</timestamp>\s*", re.DOTALL)
NOISE_PATH_PARTS = (
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "package-lock.json",
)


def estimate_tokens(text: str) -> int:
    """Rough token estimate when Cursor logs do not include usage metadata."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def strip_user_metadata(text: str) -> str:
    text = TIMESTAMP_RE.sub("", text)
    match = USER_QUERY_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def slug_to_path(slug: str) -> str | None:
    """Best-effort decode of Cursor project slug to filesystem path."""
    if slug.startswith("Users-"):
        parts = slug.split("-")
        # Users-saiyada-Desktop-foo -> /Users/saiyada/Desktop/foo
        if len(parts) >= 3 and parts[0] == "Users":
            return "/" + "/".join(parts).replace("Users/", "Users/", 1)
    return None


def path_to_slug(project_path: Path) -> str:
    return str(project_path.resolve()).lstrip("/").replace("/", "-")


def project_slug_matches(project_path: Path, slug: str) -> bool:
    expected = path_to_slug(project_path).lower()
    slug_lower = slug.lower()
    return slug_lower == expected or slug_lower.endswith(expected.split("-")[-1])


def discover_transcripts(
    *,
    project_path: Path | None = None,
    days: int | None = 30,
    limit: int = 20,
) -> list[Path]:
    if not CURSOR_PROJECTS.exists():
        return []

    cutoff: datetime | None = None
    if days is not None:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400

    paths: list[tuple[float, Path]] = []
    for transcript in CURSOR_PROJECTS.glob("**/agent-transcripts/**/*.jsonl"):
        try:
            mtime = transcript.stat().st_mtime
        except OSError:
            continue
        if cutoff is not None and mtime < cutoff:
            continue

        slug = transcript.parts[transcript.parts.index("projects") + 1] if "projects" in transcript.parts else ""
        if project_path is not None and not project_slug_matches(project_path, slug):
            continue

        paths.append((mtime, transcript))

    paths.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in paths[:limit]]


def _extract_content(record: dict) -> tuple[str, list[ToolCall]]:
    message = record.get("message") or {}
    content = message.get("content")
    text_parts: list[str] = []
    tools: list[ToolCall] = []

    if isinstance(content, str):
        return content, tools
    if not isinstance(content, list):
        return "", tools

    for block in content:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            text_parts.append(block.get("text") or "")
        elif kind == "tool_use":
            tools.append(
                ToolCall(
                    name=str(block.get("name") or "unknown"),
                    input=block.get("input") if isinstance(block.get("input"), dict) else {},
                )
            )
    return "".join(text_parts), tools


def parse_transcript(path: Path) -> Session:
    session_id = path.stem
    slug = ""
    parts = path.parts
    if "projects" in parts:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            slug = parts[idx + 1]

    turns: list[Turn] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        role = str(record.get("role") or "unknown")
        text, tool_calls = _extract_content(record)
        if role == "user":
            text = strip_user_metadata(text)

        turn = Turn(
            role=role,
            text=text,
            tool_calls=tool_calls,
            estimated_tokens=estimate_tokens(text),
        )
        # Tool inputs add context too (especially Read outputs aren't here, but paths do)
        for tc in tool_calls:
            turn.estimated_tokens += estimate_tokens(json.dumps(tc.input, default=str)[:2000])
        turns.append(turn)

    try:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        modified_at = None

    return Session(
        session_id=session_id,
        transcript_path=path,
        project_slug=slug,
        turns=turns,
        modified_at=modified_at,
    )


def load_sessions(
    *,
    project_path: Path | None = None,
    days: int | None = 30,
    limit: int = 20,
) -> list[Session]:
    transcripts = discover_transcripts(project_path=project_path, days=days, limit=limit)
    return [parse_transcript(p) for p in transcripts]


def is_noise_path(path: str) -> bool:
    lower = path.lower()
    return any(part in lower for part in NOISE_PATH_PARTS)


def extract_read_paths(session: Session) -> list[str]:
    paths: list[str] = []
    for turn in session.turns:
        for tc in turn.tool_calls:
            if tc.name != "Read":
                continue
            p = tc.input.get("path") or tc.input.get("target_file")
            if isinstance(p, str) and p:
                paths.append(p)
    return paths
