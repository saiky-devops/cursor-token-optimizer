from pathlib import Path

from cursor_token_optimize.analyzer import analyze_session
from cursor_token_optimize.models import AnalysisReport
from cursor_token_optimize.parser import parse_transcript
from cursor_token_optimize.rules import (
    RULES_FILENAME,
    TAILORED_HEADER,
    build_rules_content,
    install_rules,
    read_rules,
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
    assert TAILORED_HEADER in content
    assert len(content) > len(baseline)


def test_build_rules_content_merges_into_existing(tmp_path: Path):
    project = tmp_path / "my-app"
    project.mkdir()
    custom = "---\nalwaysApply: true\n---\n\n# My custom baseline\n\n- Keep my custom bullet.\n"
    install_rules(project, custom)

    analysis = analyze_session(parse_transcript(FIXTURE))
    report = AnalysisReport(project_path=project, sessions=[analysis], scanned_transcripts=1)
    content = build_rules_content(report, project_path=project)

    assert "Keep my custom bullet." in content
    assert TAILORED_HEADER in content
    assert "My custom baseline" in content


def test_build_rules_content_appends_tailored_without_duplicates(tmp_path: Path):
    project = tmp_path / "my-app"
    project.mkdir()
    existing_rule = "Stop and ask for direction after 10+ tool calls on the same sub-task."
    install_rules(
        project,
        build_rules_content().rstrip()
        + f"\n\n{TAILORED_HEADER}\n- {existing_rule}\n",
    )

    analysis = analyze_session(parse_transcript(FIXTURE))
    report = AnalysisReport(project_path=project, sessions=[analysis], scanned_transcripts=1)
    content = build_rules_content(report, project_path=project)

    assert content.count(existing_rule) == 1


def test_install_rules_updates_in_place_no_backup(tmp_path: Path):
    project = tmp_path / "my-app"
    project.mkdir()
    path = rules_path(project)
    path.parent.mkdir(parents=True)
    path.write_text("old content", encoding="utf-8")

    installed = install_rules(project, "new content")
    assert installed.read_text(encoding="utf-8") == "new content"
    assert installed.name == RULES_FILENAME
    assert list(path.parent.glob("token-optimize.backup.*")) == []


def test_install_rules_creates_file_when_missing(tmp_path: Path):
    project = tmp_path / "fresh-app"
    project.mkdir()
    installed = install_rules(project, "first content")
    assert read_rules(project) == "first content"
    assert installed.name == RULES_FILENAME
