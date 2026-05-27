from __future__ import annotations

from pathlib import Path

from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cursor_token_optimize.models import AnalysisReport, SessionAnalysis, WasteFinding

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _severity_style(severity: str) -> str:
    styles = {
        "high": "bold red",
        "medium": "yellow",
        "low": "dim",
    }
    return styles.get(severity.lower(), "white")


def _use_plain(console: Console) -> bool:
    return console.no_color or not console.is_terminal


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
        lines.append("- Transcripts live under ~/.cursor/projects/*/agent-transcripts/")
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

    lines.append(
        "- High token usage patterns found"
        if sa.waste_score >= 10
        else "- Some optimization opportunities found"
    )
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


def _summary_table(report: AnalysisReport) -> Table:
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Key", style="dim")
    table.add_column("Value")
    if report.project_path:
        table.add_row("Project", str(report.project_path))
    table.add_row("Sessions scanned", str(len(report.sessions)))
    table.add_row("Est. tokens (rough)", f"~{report.total_estimated_tokens:,}")
    return table


def _findings_table(findings: list[WasteFinding]) -> Table:
    table = Table(title="Overall findings (all sessions)", expand=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Severity", width=8)
    table.add_column("Finding")
    table.add_column("Score", justify="right", width=6)

    for i, f in enumerate(findings[:5], 1):
        severity = Text(f.severity.upper(), style=_severity_style(f.severity))
        table.add_row(str(i), severity, f.title, str(f.score))

    return table


def _finding_detail_panels(findings: list[WasteFinding]) -> list[RenderableType]:
    panels: list[RenderableType] = []
    for i, f in enumerate(findings[:5], 1):
        body = Text.assemble(
            (f.detail + "\n\n", ""),
            ("→ ", "dim"),
            (f.suggestion, "cyan"),
        )
        panels.append(
            Panel(
                body,
                title=f"[{_severity_style(f.severity)}]{i}. {f.title}[/]",
                border_style=_severity_style(f.severity),
            )
        )
    return panels


def _session_panel(sa: SessionAnalysis) -> Panel:
    s = sa.session
    lines: list[str | Text] = [
        f"[dim]ID[/] {s.session_id[:8]}…  ({s.transcript_path.name})",
        (
            f"[dim]Turns[/] {len(s.turns)}  "
            f"[dim]Est. tokens[/] ~{sa.estimated_tokens:,}  "
            f"[dim]Waste score[/] {sa.waste_score}"
        ),
    ]

    if not sa.findings:
        lines.append("")
        lines.append("[dim]No major waste patterns detected in this session.[/]")
    else:
        primary = sa.primary_finding
        secondary = sa.findings[1] if len(sa.findings) > 1 else None
        status = (
            "High token usage patterns found"
            if sa.waste_score >= 10
            else "Some optimization opportunities found"
        )
        lines.append("")
        lines.append(status)
        if primary:
            lines.append(f"[bold]Main reason:[/] {primary.title.lower()}")
            lines.append(f"  {primary.detail}")
        if secondary:
            lines.append(f"[bold]Second reason:[/] {secondary.title.lower()}")
            lines.append(f"  {secondary.detail}")
        lines.append("")
        lines.append("[bold]Suggestion:[/]")
        if primary:
            lines.append(primary.suggestion)
        else:
            lines.append("Ask smaller questions and add clear project rules.")

    return Panel("\n".join(str(line) for line in lines), title="Session Summary", border_style="blue")


def print_report(console: Console, report: AnalysisReport) -> None:
    if _use_plain(console):
        print(format_report(report))
        return

    console.print(
        Panel(
            _summary_table(report),
            title="[bold]Cursor Token Optimize[/] — Token Waste Report",
            border_style="green",
        )
    )
    console.print()

    if not report.sessions:
        tips = (
            "No Cursor agent transcripts found.\n\n"
            "• Use Cursor Agent mode in this project, then re-run analyze.\n"
            "• Transcripts live under ~/.cursor/projects/*/agent-transcripts/"
        )
        console.print(Panel(tips, title="Tips", border_style="yellow"))
        return

    agg = report.aggregate_findings
    if agg:
        console.print(_findings_table(agg))
        console.print()
        for panel in _finding_detail_panels(agg):
            console.print(panel)
            console.print()

    for sa in report.sessions[:5]:
        console.print(_session_panel(sa))
        console.print()

    actions = (
        "cursor-token-optimize run                "
        "[dim]# analyze, prompt for path, install rules[/]\n"
        "cursor-token-optimize suggest --apply    "
        "[dim]# append tailored rules to an existing file[/]"
    )
    console.print(Panel(actions, title="Quick actions", border_style="dim"))


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
        lines.append("Add this rule:")
        lines.append(f'  "{item["rule"]}"')
        lines.append("")
        lines.append("Reason:")
        lines.append(f"  {item['reason']}")
        lines.append("")

    return "\n".join(lines).rstrip()


def print_suggestions(
    console: Console,
    report: AnalysisReport,
    existing_rules: str | None = None,
) -> None:
    if _use_plain(console):
        print(format_suggestions(report, existing_rules))
        return

    agg = report.aggregate_findings
    if not agg:
        console.print(
            Panel(
                "No findings yet — run `cursor-token-optimize analyze` after using Cursor Agent.",
                title="Suggested rule updates",
                border_style="yellow",
            )
        )
        return

    suggestions = rules_from_findings(agg, existing_rules)
    console.print(
        Panel(
            "Tailored bullets for .cursor/rules/token-optimize.mdc",
            title="[bold]Suggested rule updates[/]",
            border_style="green",
        )
    )
    console.print()

    if not suggestions:
        console.print("[dim]No new rules to suggest (existing file may already cover these findings).[/]")
        return

    for i, item in enumerate(suggestions, 1):
        body = Text.assemble(
            ("Rule\n", "bold"),
            (f'"{item["rule"]}"\n\n', "cyan"),
            ("Reason\n", "bold"),
            (item["reason"], ""),
        )
        console.print(Panel(body, title=f"Suggestion {i}", border_style="blue"))
        console.print()


def print_rules_installed(
    console: Console,
    project: Path,
    path: Path,
    backup: Path | None,
) -> None:
    if _use_plain(console):
        print("")
        print("Rules installed")
        print(f"  Project: {project}")
        print(f"  File:    {path}")
        if backup:
            print(f"  Backup:  {backup}")
        else:
            print("  Backup:  (none — no previous file)")
        print("")
        print(
            "Open this project in Cursor and commit .cursor/rules/token-optimize.mdc to share with your team."
        )
        return

    lines = [
        f"[dim]Project[/] {project}",
        f"[dim]File[/]    {path}",
        f"[dim]Backup[/]  {backup if backup else '(none — no previous file)'}",
        "",
        "Open this project in Cursor and commit .cursor/rules/token-optimize.mdc to share with your team.",
    ]
    console.print()
    console.print(Panel("\n".join(lines), title="[bold green]Rules installed[/]", border_style="green"))


def print_rules_updated(console: Console, path: Path) -> None:
    if _use_plain(console):
        print("")
        print(f"Updated rules (with backup): {path}")
        return

    console.print()
    console.print(
        Panel(
            str(path),
            title="[bold green]Updated rules[/]",
            subtitle="Previous file backed up",
            border_style="green",
        )
    )


def print_rules_create(console: Console, path: Path, backup: Path | None) -> None:
    if _use_plain(console):
        print(f"Installed rules: {path}")
        if backup:
            print(f"Previous file backed up to: {backup}")
        return

    lines = [f"[dim]File[/] {path}"]
    if backup:
        lines.append(f"[dim]Backup[/] {backup}")
    console.print(Panel("\n".join(lines), title="[bold green]Installed rules[/]", border_style="green"))


def print_nothing_to_apply(console: Console) -> None:
    msg = "Nothing new to apply (rules may already cover these findings)."
    if _use_plain(console):
        print("")
        print(msg)
        return

    console.print()
    console.print(Panel(msg, border_style="yellow"))


def rules_from_findings(
    findings: list[WasteFinding],
    existing_rules: str | None,
) -> list[dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {
        "too_many_files": {
            "rule": "Read only files needed for the current task; do not scan the full repo unless the user explicitly asks.",
            "reason": "Recent sessions triggered many file-discovery tool calls, which inflates context.",
        },
        "broad_glob": {
            "rule": "Do not use repo-wide globs like **/*; search targeted paths or grep patterns instead.",
            "reason": "Broad Glob scans pulled in more context than the task required.",
        },
        "unnecessary_reads": {
            "rule": "Do not include large log files, node_modules, dist/, or build artifacts unless explicitly requested.",
            "reason": "Noisy or repeated file reads increased token usage in recent sessions.",
        },
        "long_prompts": {
            "rule": "Prefer small, scoped tasks. If the user pastes a long spec, ask which section to tackle first.",
            "reason": "Long user prompts were a major contributor to estimated token usage.",
        },
        "very_long_prompts": {
            "rule": "Move large specs to a doc or RULES file; paste only the active section into chat.",
            "reason": "Very long pasted specs dominated context without needing to live in every message.",
        },
        "thin_prompt_heavy_explore": {
            "rule": "Short prompts must still include target files, expected output, constraints, and done-when.",
            "reason": "Brief messages led to wide file exploration and extra context.",
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
