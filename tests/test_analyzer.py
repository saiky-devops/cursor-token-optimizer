from pathlib import Path

from cursor_token_optimize.analyzer import analyze_session
from cursor_token_optimize.parser import parse_transcript, strip_user_metadata


FIXTURE = Path(__file__).parent / "fixtures" / "wasteful.jsonl"


def test_strip_user_metadata():
    raw = "<timestamp>Mon</timestamp>\n<user_query>\nHello world\n</user_query>"
    assert strip_user_metadata(raw) == "Hello world"


def test_parse_fixture():
    session = parse_transcript(FIXTURE)
    assert len(session.user_turns) == 2
    assert any(tc.name == "Read" for t in session.turns for tc in t.tool_calls)


def test_analyze_detects_waste():
    session = parse_transcript(FIXTURE)
    analysis = analyze_session(session)
    codes = {f.code for f in analysis.findings}
    assert "too_many_files" in codes or "broad_questions" in codes
    assert "repeated_retries" in codes
    assert analysis.waste_score > 0
