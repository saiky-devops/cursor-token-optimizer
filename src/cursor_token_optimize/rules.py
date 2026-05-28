from __future__ import annotations

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
TAILORED_HEADER = "# Tailored from recent Cursor sessions"
SUGGEST_HEADER = "# Added by cursor-token-optimize suggest"


def rules_path(project_path: Path) -> Path:
    return project_path / ".cursor" / "rules" / RULES_FILENAME


def read_rules(project_path: Path) -> str | None:
    path = rules_path(project_path)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _section_index(content: str, header: str) -> int:
    return content.find(header)


def _base_before_sections(content: str) -> str:
    """Keep frontmatter and baseline; drop optional sections we manage."""
    cut = len(content)
    for header in (TAILORED_HEADER, SUGGEST_HEADER):
        idx = _section_index(content, header)
        if idx != -1:
            cut = min(cut, idx)
    return content[:cut].rstrip()


def _tailored_bullets(content: str) -> list[str]:
    idx = _section_index(content, TAILORED_HEADER)
    if idx == -1:
        return []
    rest = content[idx + len(TAILORED_HEADER) :]
    for header in (SUGGEST_HEADER,):
        end = _section_index(rest, header)
        if end != -1:
            rest = rest[:end]
    bullets: list[str] = []
    for line in rest.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:])
    return bullets


def _suffix_after_tailored(content: str) -> str:
    """Preserve suggest-append section and anything after tailored block."""
    idx = _section_index(content, TAILORED_HEADER)
    if idx == -1:
        suggest_idx = _section_index(content, SUGGEST_HEADER)
        return content[suggest_idx:].rstrip() if suggest_idx != -1 else ""

    after = content[idx + len(TAILORED_HEADER) :]
    suggest_idx = _section_index(after, SUGGEST_HEADER)
    if suggest_idx == -1:
        return ""
    return after[suggest_idx:].rstrip()


def build_rules_content(
    report: AnalysisReport | None = None,
    *,
    project_path: Path | None = None,
) -> str:
    """Write or merge rules: keep existing file, append new tailored bullets only."""
    from cursor_token_optimize.report import rules_from_findings

    existing = read_rules(project_path) if project_path else None
    if existing:
        base = _base_before_sections(existing)
        tailored_bullets = _tailored_bullets(existing)
        suffix = _suffix_after_tailored(existing)
        existing_for_dedup = existing
    else:
        base = DEFAULT_RULES.rstrip()
        tailored_bullets = []
        suffix = ""
        existing_for_dedup = DEFAULT_RULES

    if report and report.aggregate_findings:
        for item in rules_from_findings(report.aggregate_findings, existing_for_dedup):
            rule = item["rule"]
            if rule not in tailored_bullets:
                tailored_bullets.append(rule)

    sections = [base]
    if tailored_bullets:
        sections.append("")
        sections.append(TAILORED_HEADER)
        for rule in tailored_bullets:
            sections.append(f"- {rule}")
    if suffix:
        sections.append("")
        sections.append(suffix)
    sections.append("")
    return "\n".join(sections)


def install_rules(project_path: Path, content: str) -> Path:
    """Update rules file in place (no backup)."""
    path = rules_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def create_rules(project_path: Path, *, force: bool = False) -> Path:
    """Create or update rules in the project rules file."""
    return install_rules(project_path, build_rules_content(project_path=project_path))


def append_suggested_rules(project_path: Path, new_bullets: list[str]) -> Path:
    path = rules_path(project_path)
    additions = [b if b.startswith("- ") else f"- {b}" for b in new_bullets if b.strip()]
    if not additions:
        return path

    existing = read_rules(project_path) or DEFAULT_RULES.rstrip()
    if not existing.endswith("\n"):
        existing += "\n"
    if SUGGEST_HEADER in existing:
        content = existing.rstrip() + "\n" + "\n".join(additions) + "\n"
    else:
        content = (
            existing
            + "\n"
            + SUGGEST_HEADER
            + "\n"
            + "\n".join(additions)
            + "\n"
        )
    return install_rules(project_path, content)
