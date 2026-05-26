from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cursor_token_optimize.analyzer import analyze_project
from cursor_token_optimize.report import format_report, format_suggestions, rules_from_findings
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


def _prompt_project_path(default: Path | None = None) -> Path:
    default = default or Path.cwd()
    print("")
    print("Install Cursor rules")
    print(f"  → {{your-project}}/.cursor/rules/token-optimize.mdc")
    print("")

    while True:
        raw = input(f"Project path [{default}]: ").strip()
        path = Path(raw).expanduser().resolve() if raw else default
        if path.exists() and path.is_dir():
            return path
        print(f"  Not a directory: {path}")
        again = input("  Try again? [Y/n]: ").strip().lower()
        if again == "n":
            print("Aborted.", file=sys.stderr)
            sys.exit(1)


def cmd_run(args: argparse.Namespace) -> int:
    report = analyze_project(project_path=None, days=args.days, limit=args.limit)
    print(format_report(report))

    project = _resolve_project(args.project) if args.project else _prompt_project_path()
    target = rules_path(project)
    content = build_rules_content(report)
    path, backup = install_rules(project, content)

    print("")
    print("Rules installed")
    print(f"  Project: {project}")
    print(f"  File:    {path}")
    if backup:
        print(f"  Backup:  {backup}")
    else:
        print("  Backup:  (none — no previous file)")
    print("")
    print("Open this project in Cursor and commit .cursor/rules/token-optimize.mdc to share with your team.")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    project = None if getattr(args, "all_projects", False) else _resolve_project(args.project)
    report = analyze_project(project_path=project, days=args.days, limit=args.limit)
    print(format_report(report))
    return 0


def cmd_create_rules(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    content = build_rules_content() if not args.tailored else build_rules_content(
        analyze_project(project_path=None, days=30, limit=20)
    )
    path, backup = install_rules(project, content)
    print(f"Installed rules: {path}")
    if backup:
        print(f"Previous file backed up to: {backup}")
    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    scan_project = None if getattr(args, "all_projects", False) else project
    report = analyze_project(project_path=scan_project, days=args.days, limit=args.limit)
    existing = read_rules(project)
    text = format_suggestions(report, existing)
    print(text)

    if args.apply:
        items = rules_from_findings(report.aggregate_findings, existing)
        bullets = [i["rule"] for i in items]
        if bullets:
            path = append_suggested_rules(project, bullets)
            print("")
            print(f"Updated rules (with backup): {path}")
        else:
            print("")
            print("Nothing new to apply (rules may already cover these findings).")
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
    parser = argparse.ArgumentParser(
        prog="cursor-token-optimize",
        description="Analyze Cursor agent sessions and install token-saving rules.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser(
        "run",
        help="Analyze all sessions, prompt for project path, install rules (with backup)",
    )
    _add_common_args(run)

    analyze = sub.add_parser("analyze", help="Analyze Cursor sessions and print a report")
    _add_common_args(analyze)
    analyze.add_argument(
        "--all",
        dest="all_projects",
        action="store_true",
        help="Analyze transcripts from all Cursor projects (ignore --project)",
    )

    create = sub.add_parser("create-rules", help="Install .cursor/rules/token-optimize.mdc (with backup)")
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

    suggest = sub.add_parser("suggest", help="Suggest rule updates from recent sessions")
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

    commands = {
        "run": cmd_run,
        "analyze": cmd_analyze,
        "create-rules": cmd_create_rules,
        "suggest": cmd_suggest,
    }
    try:
        code = commands[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
