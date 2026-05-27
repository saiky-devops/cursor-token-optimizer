from io import StringIO
from pathlib import Path

from rich.console import Console

from cursor_token_optimize.analyzer import analyze_session
from cursor_token_optimize.models import AnalysisReport
from cursor_token_optimize.parser import parse_transcript
from cursor_token_optimize.report import format_report, print_report

FIXTURE = Path(__file__).parent / "fixtures" / "wasteful.jsonl"


def _sample_report() -> AnalysisReport:
    analysis = analyze_session(parse_transcript(FIXTURE))
    return AnalysisReport(
        project_path=Path("/tmp/my-app"),
        sessions=[analysis],
        scanned_transcripts=1,
    )


def test_format_report_plain():
    report = _sample_report()
    text = format_report(report)
    assert "Cursor Token Optimize" in text
    assert "Sessions scanned: 1" in text
    assert "Quick actions" in text
    assert any(f.title in text for f in report.sessions[0].findings)


def test_print_report_rich():
    report = _sample_report()
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120, no_color=False)
    print_report(console, report)
    output = buf.getvalue()
    assert "Sessions scanned" in output or "1" in output
    assert report.sessions[0].findings[0].title in output


def test_no_color_plain_fallback(capsys):
    report = _sample_report()
    expected = format_report(report)
    console = Console(file=StringIO(), no_color=True, force_terminal=False)
    print_report(console, report)
    assert capsys.readouterr().out.strip() == expected.strip()
