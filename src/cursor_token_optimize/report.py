from __future__ import annotations

from cursor_token_optimize.models import AnalysisReport, SessionAnalysis, WasteFinding

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def format_report(report: AnalysisReport) -> str:
    lines: list[str] = []
    lines.append("Cursor Token Optimize — Token Waste Report")
    lines.append("=" * 40)

    if report.project_path:
        lines.append(f"Project: {report.project_path}")
    lines.append(f"Sessions scanned: {len(report.sessions)}")
    lines.append(f"Estimated tokens (rough): ~{report.total_estimated_tokens:,}")
    lines.append("")

    if not report.sessions:
        lines.append("No Cursor agent transcripts found.")
        lines.append("")
        lines.append("Tips:")
        lines.append("- Use Cursor Agent mode in this project, then re-run analyze.")
        lines.append(f"- Transcripts live under ~/.cursor/projects/*/agent-transcripts/")
        return "\n".join(lines)

    agg = report.aggregate_findings
    if agg:
        lines.append("Overall findings (all sessions)")
        lines.append("-" * 40)
        for i, f in enumerate(agg[:5], 1):
            lines.append(f"{i}. [{f.severity.upper()}] {f.title} (score {f.score})")
            lines.append(f"   {f.detail}")
            lines.append(f"   → {f.suggestion}")
        lines.append("")

    for sa in report.sessions[:5]:
        lines.extend(_format_session(sa))
        lines.append("")

    lines.append("Quick actions")
    lines.append("-" * 40)
    lines.append("  cursor-token-optimize run                # analyze, prompt for path, install rules")
    lines.append("  cursor-token-optimize suggest --apply    # append tailored rules to an existing file")
    return "\n".join(lines)


def _format_session(sa: SessionAnalysis) -> list[str]:
    s = sa.session
    lines = [
        "Session Summary",
        f"- ID: {s.session_id[:8]}…  ({s.transcript_path.name})",
        f"- Turns: {len(s.turns)}  |  Est. tokens: ~{sa.estimated_tokens:,}  |  Waste score: {sa.waste_score}",
    ]

    if not sa.findings:
        lines.append("- No major waste patterns detected in this session.")
        return lines

    primary = sa.primary_finding
    secondary = sa.findings[1] if len(sa.findings) > 1 else None

    lines.append("- High token usage patterns found" if sa.waste_score >= 10 else "- Some optimization opportunities found")
    if primary:
        lines.append(f"- Main reason: {primary.title.lower()}")
        lines.append(f"  {primary.detail}")
    if secondary:
        lines.append(f"- Second reason: {secondary.title.lower()}")
        lines.append(f"  {secondary.detail}")

    lines.append("")
    lines.append("Suggestion:")
    if primary:
        lines.append(primary.suggestion)
    else:
        lines.append("Ask smaller questions and add clear project rules.")
    return lines


def format_suggestions(report: AnalysisReport, existing_rules: str | None = None) -> str:
    lines: list[str] = []
    lines.append("Suggested rule updates for .cursor/rules/token-optimize.mdc")
    lines.append("=" * 50)
    lines.append("")

    agg = report.aggregate_findings
    if not agg:
        lines.append("No findings yet — run `cursor-token-optimize analyze` after using Cursor Agent.")
        return "\n".join(lines)

    suggestions = rules_from_findings(agg, existing_rules)
    for item in suggestions:
        lines.append(f"Add this rule:")
        lines.append(f'  "{item["rule"]}"')
        lines.append("")
        lines.append("Reason:")
        lines.append(f"  {item['reason']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def rules_from_findings(
    findings: list[WasteFinding],
    existing_rules: str | None,
) -> list[dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {
        "too_many_files": {
            "rule": "Read only files needed for the current task; do not scan the full repo unless the user explicitly asks.",
            "reason": "Recent sessions triggered many file-discovery tool calls, which inflates context.",
        },
        "unnecessary_reads": {
            "rule": "Do not include large log files, node_modules, dist/, or build artifacts unless explicitly requested.",
            "reason": "Noisy or repeated file reads increased token usage in recent sessions.",
        },
        "long_prompts": {
            "rule": "Prefer small, scoped tasks. If the user pastes a long spec, ask which section to tackle first.",
            "reason": "Long user prompts were a major contributor to estimated token usage.",
        },
        "long_history": {
            "rule": "For long threads, summarize prior decisions briefly instead of re-reading entire history.",
            "reason": "Sessions with many turns accumulate context and cost more over time.",
        },
        "repeated_retries": {
            "rule": "Confirm acceptance criteria before large edits to reduce back-and-forth corrections.",
            "reason": "Repeated or similar user messages suggest costly retry loops.",
        },
        "broad_questions": {
            "rule": "When the request is broad, propose a short plan and wait for approval before wide exploration.",
            "reason": "Broad or vague questions led to expensive repo-wide exploration.",
        },
        "runaway_tools": {
            "rule": "Stop and ask for direction after 10+ tool calls on the same sub-task.",
            "reason": "High tool-call volume in a single session indicates possible agent looping.",
        },
    }

    existing = (existing_rules or "").lower()
    out: list[dict[str, str]] = []
    for f in findings[:5]:
        item = catalog.get(f.code)
        if not item:
            continue
        if item["rule"][:40].lower() in existing:
            continue
        out.append({"rule": item["rule"], "reason": item["reason"]})
    return out
