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

If that file already exists, a backup is created first:

```text
my-app/.cursor/rules/token-optimize.backup.20260525-153045.mdc
```

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
| `create-rules` | Install baseline rules to `--project` (with backup) |
| `suggest` | Show tailored rule suggestions |
| `suggest --apply` | Append suggestions (backs up existing file first) |

### Common flags

| Flag | Default | Description |
|------|---------|-------------|
| `--project`, `-p` | interactive prompt on `run` | Target project directory |
| `--days` | 30 | Only transcripts modified in the last N days |
| `--limit` | 20 | Max sessions to analyze |
| `--all` | off (`run` scans all projects by default) | On `analyze` / `suggest`: scan every Cursor project |

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
| Too many files | ≥ 12 Read/Glob/Grep calls **or** ≥ 8 unique reads | Agent pulled in lots of context |
| Unnecessary reads | Paths under `node_modules`, `dist`, logs, etc. **or** same file read twice | Avoidable context bloat |
| Long history | ≥ 25 turns in one session | Context accumulates across the thread |
| Repeated retries | Similar consecutive user messages (≥ 72%) **or** assistant:user ratio ≥ 4:1 | Back-and-forth corrections |
| Broad questions | Phrases like "review the entire codebase", "scan the whole repo" | Triggers repo-wide exploration |
| Vague + exploratory | Short vague ask **and** ≥ 8 file-tool calls | Unclear goal → wide search |
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
