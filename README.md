# Cursor Token Optimize

A **Local CLI** that reads Cursor agent transcripts, finds likely token waste, and installs `.cursor/rules/token-optimize.mdc` into any project you choose.

Data source: `~/.cursor/projects/*/agent-transcripts/*.jsonl`. The tool is independent of the target project — install the CLI once, then write rules wherever you work.

## Prerequisites

- Python 3.10+ (`python3 --version`)
- Cursor with **Agent** mode (transcripts are created when the agent runs tools)
- A terminal — no API keys or network access required; everything stays on your machine (reads ~/.cursor/projects/ transcripts, writes .cursor/rules/ in the project you choose; nothing is uploaded)

## Setup

```bash
git clone <your-repo-url> cursor-token-optimize
cd cursor-token-optimize

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -e .
cursor-token-optimize --help       # run, analyze, create-rules, suggest
```
## Quick start (recommended)

After [Setup](#setup), one command scans **all** Cursor sessions, shows a report, asks where to install rules, and **updates** `.cursor/rules/token-optimize.mdc` in place (merging new tailored bullets):

```bash
cursor-token-optimize run
```

You will be prompted:

```text
Project path [/current/directory]:
```

Enter the app where you want rules, e.g. `/Users/you/projects/my-app`. The tool writes:

```text
my-app/.cursor/rules/token-optimize.mdc
```

If that file already exists, new tailored bullets are merged into it (your baseline and prior rules are kept).

Skip the prompt in scripts:

```bash
cursor-token-optimize run --project /path/to/my-app
```

## Commands

Other subcommands and flags:

| Command | Purpose |
|---------|---------|
| **`run`** | Full workflow — see [Quick start](#quick-start-recommended) |
| `analyze` | Print a waste report only |
| `create-rules` | Install or update baseline rules at `--project` |
| `suggest` | Show tailored rule suggestions |
| `suggest --apply` | Append new suggestions to the existing rules file |

### Common flags

| Flag | Default | Description |
|------|---------|-------------|
| `--project`, `-p` | interactive prompt on `run` | Target project directory |
| `--days` | 30 | Only transcripts modified in the last N days |
| `--limit` | 20 | Max sessions to analyze |
| `--all` | off (`run` scans all projects by default) | On `analyze` / `suggest`: scan every Cursor project |

## Sample output

```bash
cursor-token-optimize analyze --all --limit 1
```

Illustrative terminal layout (severity shown in color when your terminal supports it):

```text
╭──────────── Cursor Token Optimize — Token Waste Report ────────────╮
│ Sessions scanned     1                                             │
│ Est. tokens (rough)  ~91,305                                       │
╰────────────────────────────────────────────────────────────────────╯

Overall findings (all sessions)
┏━━━┳━━━━━━━━━━┳─────────────────────────────────────┳━━━━━━━┓
┃ # ┃ Severity ┃ Finding                             ┃ Score ┃
┡━━━╇━━━━━━━━━━╇────────────────────────────────────━╇━━━━━━━┩
│ 1 │ HIGH     │ High tool-call volume               │   409 │
│ 2 │ HIGH     │ Very long chat history              │   298 │
│ 3 │ HIGH     │ Too many files added to context     │   278 │
└───┴──────────┴─────────────────────────────────────┴───────┘

╭─ 1. High tool-call volume ─────────────────────────────────────────╮
│ 409 tool calls in one session.                                     │
│ → Split the task into phases. Cancel and restart with a narrower   │
│   goal if the agent loops.                                         │
╰────────────────────────────────────────────────────────────────────╯

╭─ Session Summary ──────────────────────────────────────────────────╮
│ ID 7585639b…  ·  298 turns  ·  ~91,305 tokens  ·  waste score 1414 │
│ Main: high tool-call volume · Second: very long chat history       │
╰────────────────────────────────────────────────────────────────────╯

╭─ Quick actions ────────────────────────────────────────────────────╮
│ cursor-token-optimize run              # analyze, install rules    │
│ cursor-token-optimize suggest --apply  # append tailored rules     │
╰────────────────────────────────────────────────────────────────────╯

╭─ Rules updated (after run) ────────────────────────────────────────╮
│ File  my-app/.cursor/rules/token-optimize.mdc                      │
╰────────────────────────────────────────────────────────────────────╯
```

Use `--no-color` for a plain, pipe-friendly version. Numbers depend on your local transcripts.

## How analysis works

This tool does **not** read Cursor's billing or real token meters. It uses transcript content plus fixed heuristics.

### Token estimate (informational)

- Message text: `characters ÷ 4`
- Tool call arguments: same formula (capped at 2000 chars per call)
- **Not included:** file contents returned by `Read`, terminal output, or hidden system prompt — so printed totals are a **rough lower bound**

### Waste patterns (what triggers a finding)

| Pattern | Threshold | What it means |
|---------|-----------|---------------|
| Long prompts | User message ≥ 1500 chars | Large pasted specs or long asks |
| Very long prompts | User message ≥ 4000 chars | Move spec to a doc; paste only the active section |
| Thin prompt + exploration | Short asks (<120 chars) with ≥ 10 file-tool calls | Add scope (files, done-when) to avoid wide search |
| Too many files | ≥ 12 Read/Glob/Grep calls **or** ≥ 8 unique reads | Agent pulled in lots of context |
| Repo-wide globs | ≥ 1 broad Glob pattern (e.g. `**/*`) | Full-repo scan instead of targeted search |
| Unnecessary reads | `node_modules`, logs, etc. **or** same file read twice | Avoidable context bloat |
| Long history | ≥ 25 turns in one session | Context accumulates across the thread |
| Repeated retries | Similar consecutive user messages (≥ 72%) **or** assistant:user ratio ≥ 4:1 | Back-and-forth corrections |
| Broad questions | "review entire codebase", etc. **or** vague ask + ≥ 8 file-tool calls | Triggers repo-wide exploration |
| Runaway tools | ≥ 20 tool calls in one session | Possible agent loop |

Each pattern gets a **score**. Sessions are ranked by total **waste score**. The `run` command merges baseline rules plus tailored bullets from your top findings.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `command not found` | Activate venv: `source .venv/bin/activate`, then `pip install -e .` |
| `No Cursor agent transcripts found` | Use Agent mode, complete a session, then retry with `--days 90` |
| `Sessions scanned: 0` on `analyze --project` | Use `run` (scans all projects) or `analyze --all` |
| Wrong project path at prompt | Re-run `run` or pass `--project /full/path` |

## Data privacy

Everything runs locally. Reads only `~/.cursor/projects/` and your target project's `.cursor/rules/`. Nothing is sent to the network.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
