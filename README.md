# Cursor Token Optimize

A **local CLI** that reads Cursor agent transcripts, finds likely token waste, and installs `.cursor/rules/token-optimize.mdc` into any project you choose.

Data source: `~/.cursor/projects/*/agent-transcripts/*.jsonl`. The tool is independent of the target project — install the CLI once, then write rules wherever you work.

## Prerequisites

- Python 3.10+ (`python3 --version`)
- Cursor with **Agent** mode (transcripts are created when the agent runs tools)
- A terminal — no API keys or network access required

## Setup

```bash
git clone <your-repo-url> cursor-token-optimize
cd cursor-token-optimize

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1

pip install -e .
cursor-token-optimize --help       # run, analyze, create-rules, suggest
```

If `python3 -m venv .venv` fails with an `ensurepip` error, try:

```bash
python3.12 -m venv .venv           # or: /usr/local/bin/python3 -m venv .venv
# fallback:
python3 -m venv .venv --without-pip && source .venv/bin/activate
curl -sS https://bootstrap.pypa.io/get-pip.py | python
pip install -e .
```

## Quick start (recommended)

After [Setup](#setup), one command scans **all** Cursor sessions, shows a report, asks where to install rules, backs up any existing file, and writes a new one:

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

`analyze` and `run` render a **color-coded report**: summary panel, findings table (severity in red/yellow), detail panels, and per-session summaries.

```bash
cursor-token-optimize analyze --all --limit 2
```

```text
Cursor Token Optimize — Token Waste Report
========================================
Sessions scanned: 2
Estimated tokens (rough): ~122,406

Overall findings (all sessions)
----------------------------------------
1. [HIGH] High tool-call volume (score 514)
   285 tool calls in one session.
   → Split the task into phases. Cancel and restart with a narrower goal if the agent loops.
2. [HIGH] Very long chat history (score 396)
   218 turns in one session (47 user, 171 assistant).
   → Start a fresh chat for new topics. Summarize decisions in a RULES file instead of re-explaining.
3. [HIGH] Too many files added to context (score 362)
   144 file-discovery tool calls (51 unique reads). Top tools: Read=99, StrReplace=48, Shell=40, Write=32, Grep=30.
   → Point Cursor at specific files. Add rules to avoid repo-wide scans unless necessary.
…

Session Summary
- ID: 7585639b…  (7585639b-a1a4-48a0-aa3d-d01dbb233bb8.jsonl)
- Turns: 218  |  Est. tokens: ~66,650  |  Waste score: 752
- High token usage patterns found
- Main reason: high tool-call volume
  285 tool calls in one session.
- Second reason: very long chat history
  218 turns in one session (47 user, 171 assistant).

Suggestion:
Split the task into phases. Cancel and restart with a narrower goal if the agent loops.

Quick actions
----------------------------------------
  cursor-token-optimize run                # analyze, prompt for path, install rules
  cursor-token-optimize suggest --apply    # append tailored rules to an existing file
```

After `run` installs rules, you get a success panel:

```text
Rules updated
  Project: /path/to/my-app
  File:    /path/to/my-app/.cursor/rules/token-optimize.mdc
```

Numbers and findings depend on your local Cursor agent transcripts.

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
