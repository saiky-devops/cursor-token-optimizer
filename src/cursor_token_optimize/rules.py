from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from cursor_token_optimize.models import AnalysisReport

DEFAULT_RULES = """---
description: Cursor Token Optimize — keep context small and changes focused
globs:
alwaysApply: true
---

# Token Optimize Rules

- Include goal, constraints, and done-when in each message; trim filler, not requirements.
- Target specific files; no repo-wide scans or **/* globs unless the user asks.
- One task per message; start a fresh chat when the thread gets long.
- Prefer concise replies; put long code in edits, not chat walls.
- Read only required files; keep changes small; reuse existing project patterns.
- Do not include node_modules, dist/, build output, or large logs unless requested.
- Add tests when changing code.
"""

RULES_FILENAME = "token-optimize.mdc"


def rules_path(project_path: Path) -> Path:
    return project_path / ".cursor" / "rules" / RULES_FILENAME


def backup_rules_file(path: Path) -> Path | None:
    """Copy existing rules to a timestamped backup. Returns backup path if created."""
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.parent / f"{path.stem}.backup.{timestamp}{path.suffix}"
    shutil.copy2(path, backup)
    return backup


def build_rules_content(report: AnalysisReport | None = None) -> str:
    """Baseline rules plus tailored bullets from session analysis."""
    from cursor_token_optimize.report import rules_from_findings

    sections = [DEFAULT_RULES.rstrip()]
    if report and report.aggregate_findings:
        tailored = rules_from_findings(report.aggregate_findings, existing_rules=DEFAULT_RULES)
        if tailored:
            sections.append("")
            sections.append("# Tailored from recent Cursor sessions")
            for item in tailored:
                sections.append(f"- {item['rule']}")
    sections.append("")
    return "\n".join(sections)


def install_rules(project_path: Path, content: str) -> tuple[Path, Path | None]:
    """Write rules file, backing up any existing file first. Returns (path, backup_path)."""
    path = rules_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = backup_rules_file(path)
    path.write_text(content, encoding="utf-8")
    return path, backup


def create_rules(project_path: Path, *, force: bool = False) -> Path:
    """Write default rules. Backs up and replaces if the file already exists."""
    path, _ = install_rules(project_path, build_rules_content())
    return path


def read_rules(project_path: Path) -> str | None:
    path = rules_path(project_path)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def append_suggested_rules(project_path: Path, new_bullets: list[str]) -> Path:
    path = rules_path(project_path)
    additions = [b if b.startswith("- ") else f"- {b}" for b in new_bullets if b.strip()]
    if not additions:
        return path

    existing = read_rules(project_path) or DEFAULT_RULES.rstrip()
    if not existing.endswith("\n"):
        existing += "\n"
    content = existing + "\n# Added by cursor-token-optimize suggest\n" + "\n".join(additions) + "\n"
    installed, _ = install_rules(project_path, content)
    return installed
