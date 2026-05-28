from pathlib import Path

import pytest

from cursor_token_optimize.parser import (
    MAX_TRANSCRIPT_BYTES,
    discover_transcripts,
    load_sessions,
    parse_transcript,
    transcript_too_large,
)

FIXTURE = Path(__file__).parent / "fixtures" / "wasteful.jsonl"


def test_parse_transcript_streams_fixture():
    session = parse_transcript(FIXTURE)
    assert session.turns
    assert session.session_id == FIXTURE.stem


def test_transcript_too_large(tmp_path: Path):
    big = tmp_path / "huge.jsonl"
    big.write_bytes(b"x" * (MAX_TRANSCRIPT_BYTES + 1))
    assert transcript_too_large(big)


def test_discover_skips_oversized_transcripts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    projects = tmp_path / "projects" / "Users-test-app" / "agent-transcripts"
    projects.mkdir(parents=True)
    ok = projects / "ok.jsonl"
    ok.write_text('{"role":"user","message":{"content":"hi"}}\n', encoding="utf-8")
    huge = projects / "huge.jsonl"
    huge.write_bytes(b"x" * (MAX_TRANSCRIPT_BYTES + 1))

    monkeypatch.setattr(
        "cursor_token_optimize.parser.CURSOR_PROJECTS",
        tmp_path / "projects",
    )
    found = discover_transcripts(limit=10)
    assert ok in found
    assert huge not in found


def test_load_sessions_skips_oversized_on_parse_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    projects = tmp_path / "projects" / "Users-test-app" / "agent-transcripts"
    projects.mkdir(parents=True)
    huge = projects / "edge.jsonl"
    # Under discover limit but force parse path: discover filters by size; same file skipped
    huge.write_bytes(b"x" * (MAX_TRANSCRIPT_BYTES + 1))
    monkeypatch.setattr(
        "cursor_token_optimize.parser.CURSOR_PROJECTS",
        tmp_path / "projects",
    )
    assert load_sessions(limit=10) == []
