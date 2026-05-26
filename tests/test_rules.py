from pathlib import Path

from cursor_token_optimize.analyzer import analyze_session
from cursor_token_optimize.models import AnalysisReport
from cursor_token_optimize.parser import parse_transcript
from cursor_token_optimize.rules import (
    RULES_FILENAME,
    build_rules_content,
    install_rules,
    rules_path,
)

FIXTURE = Path(__file__).parent / "fixtures" / "wasteful.jsonl"


def test_build_rules_content_includes_baseline():
    content = build_rules_content()
    assert "# Token Optimize Rules" in content
    assert "Read only required files" in content


def test_build_rules_content_adds_tailored_section():
    analysis = analyze_session(parse_transcript(FIXTURE))
    report = AnalysisReport(project_path=None, sessions=[analysis], scanned_transcripts=1)
    baseline = build_rules_content()
    content = build_rules_content(report)
    assert "Tailored from recent Cursor sessions" in content
    assert len(content) > len(baseline)


def test_install_rules_creates_backup(tmp_path: Path):
    project = tmp_path / "my-app"
    project.mkdir()
    path = rules_path(project)
    path.parent.mkdir(parents=True)
    path.write_text("old content", encoding="utf-8")

    installed, backup = install_rules(project, "new content")
    assert installed.read_text(encoding="utf-8") == "new content"
    assert backup is not None
    assert backup.read_text(encoding="utf-8") == "old content"
    assert backup.name.startswith("token-optimize.backup.")


def test_install_rules_no_backup_when_missing(tmp_path: Path):
    project = tmp_path / "fresh-app"
    project.mkdir()
    installed, backup = install_rules(project, "first content")
    assert backup is None
    assert installed.read_text(encoding="utf-8") == "first content"
    assert installed.name == RULES_FILENAME
