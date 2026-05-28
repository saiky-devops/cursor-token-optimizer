from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from cursor_token_optimize.analyzer import analyze_project
from cursor_token_optimize.report import (
    print_nothing_to_apply,
    print_report,
    print_rules_create,
    print_rules_installed,
    print_rules_updated,
    print_suggestions,
    rules_from_findings,
)
from cursor_token_optimize.rules import (
    append_suggested_rules,
    build_rules_content,
    install_rules,
    read_rules,
    rules_path,
)


def _resolve_project(path: str | None) -> Path:
    if path:
        return Path(path).expanduser().resolve()
    return Path.cwd().resolve()


def make_console(no_color: bool = False) -> Console:
    env_no_color = os.environ.get("NO_COLOR", "") != ""
    if no_color or env_no_color:
        return Console(no_color=True)
    return Console()


def _prompt_project_path(console: Console, default: Path | None = None) -> Path:
    default = default or Path.cwd()
    console.print()
    console.print(
        Panel(
            "Rules will be written to:\n  {your-project}/.cursor/rules/token-optimize.mdc",
            title="Install Cursor rules",
            border_style="cyan",
        )
    )
    console.print()

    while True:
        raw = Prompt.ask("Project path", default=str(default), console=console).strip()
        path = Path(raw).expanduser().resolve() if raw else default
        if path.exists() and path.is_dir():
            return path
        console.print(f"[red]Not a directory:[/] {path}")
        if not Confirm.ask("Try again?", default=True, console=console):
            console.print("[red]Aborted.[/]", file=sys.stderr)
            sys.exit(1)


def cmd_run(args: argparse.Namespace, console: Console) -> int:
    report = analyze_project(project_path=None, days=args.days, limit=args.limit)
    print_report(console, report)

    project = _resolve_project(args.project) if args.project else _prompt_project_path(console)
    content = build_rules_content(report, project_path=project)
    path = install_rules(project, content)
    print_rules_installed(console, project, path)
    return 0


def cmd_analyze(args: argparse.Namespace, console: Console) -> int:
    project = None if getattr(args, "all_projects", False) else _resolve_project(args.project)
    report = analyze_project(project_path=project, days=args.days, limit=args.limit)
    print_report(console, report)
    return 0


def cmd_create_rules(args: argparse.Namespace, console: Console) -> int:
    project = _resolve_project(args.project)
    report = (
        analyze_project(project_path=None, days=30, limit=20) if args.tailored else None
    )
    content = build_rules_content(report, project_path=project)
    path = install_rules(project, content)
    print_rules_create(console, path)
    return 0


def cmd_suggest(args: argparse.Namespace, console: Console) -> int:
    project = _resolve_project(args.project)
    scan_project = None if getattr(args, "all_projects", False) else project
    report = analyze_project(project_path=scan_project, days=args.days, limit=args.limit)
    existing = read_rules(project)
    print_suggestions(console, report, existing)

    if args.apply:
        items = rules_from_findings(report.aggregate_findings, existing)
        bullets = [i["rule"] for i in items]
        if bullets:
            path = append_suggested_rules(project, bullets)
            print_rules_updated(console, path)
        else:
            print_nothing_to_apply(console)
    return 0


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        "-p",
        help="Project directory (skips interactive prompt where supported)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Only analyze transcripts modified in the last N days (default: 30)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max sessions to analyze (default: 20)",
    )


def build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored terminal output (also respects NO_COLOR=1)",
    )

    parser = argparse.ArgumentParser(
        prog="cursor-token-optimize",
        description="Analyze Cursor agent sessions and install token-saving rules.",
        parents=[shared],
    )

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run",
        help="Analyze all sessions, prompt for project path, update rules in place",
        parents=[shared],
    )
    _add_common_args(run)

    analyze = sub.add_parser(
        "analyze",
        help="Analyze Cursor sessions and print a report",
        parents=[shared],
    )
    _add_common_args(analyze)
    analyze.add_argument(
        "--all",
        dest="all_projects",
        action="store_true",
        help="Analyze transcripts from all Cursor projects (ignore --project)",
    )

    create = sub.add_parser(
        "create-rules",
        help="Install or update .cursor/rules/token-optimize.mdc in place",
        parents=[shared],
    )
    create.add_argument(
        "--project",
        "-p",
        help="Project directory (default: current directory)",
    )
    create.add_argument(
        "--tailored",
        action="store_true",
        help="Include tailored rules from recent sessions (default: baseline only)",
    )

    suggest = sub.add_parser(
        "suggest",
        help="Suggest rule updates from recent sessions",
        parents=[shared],
    )
    _add_common_args(suggest)
    suggest.add_argument(
        "--all",
        dest="all_projects",
        action="store_true",
        help="Base suggestions on transcripts from all Cursor projects",
    )
    suggest.add_argument(
        "--apply",
        action="store_true",
        help="Append suggested rules (backs up existing file first)",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    console = make_console(getattr(args, "no_color", False))

    commands = {
        "run": cmd_run,
        "analyze": cmd_analyze,
        "create-rules": cmd_create_rules,
        "suggest": cmd_suggest,
    }
    try:
        code = commands[args.command](args, console)
    except KeyboardInterrupt:
        console.print("\nInterrupted.", style="red", file=sys.stderr)
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
