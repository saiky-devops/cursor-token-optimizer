from __future__ import annotations

import difflib
import re
from collections import Counter
from pathlib import Path

from cursor_token_optimize.models import AnalysisReport, Session, SessionAnalysis, WasteFinding
from cursor_token_optimize.parser import extract_read_paths, is_noise_path, load_sessions

BROAD_QUESTION_RE = re.compile(
    r"\b(review everything|review the entire|scan the (whole|entire|full) repo|go through (the )?repo|"
    r"analyze (the )?(whole )?codebase|audit everything|check all files|refactor (the )?project)\b",
    re.IGNORECASE,
)
VAGUE_QUESTION_RE = re.compile(
    r"^(fix|help|improve|optimize|check|review|look at)( this| it| my code)?\.?$",
    re.IGNORECASE,
)
LOG_FILE_RE = re.compile(r"\.(log|jsonl)$|/(logs?)/", re.IGNORECASE)

THRESHOLDS = {
    "long_prompt_chars": 1500,
    "long_history_turns": 25,
    "many_file_reads": 12,
    "many_tool_calls": 20,
    "assistant_per_user_ratio": 4.0,
    "retry_similarity": 0.72,
}


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def analyze_session(session: Session) -> SessionAnalysis:
    findings: list[WasteFinding] = []
    user_turns = session.user_turns
    assistant_turns = session.assistant_turns
    read_paths = extract_read_paths(session)

    all_tools = [tc.name for t in session.turns for tc in t.tool_calls]
    tool_counts = Counter(all_tools)
    unique_reads = set(read_paths)
    noise_reads = [p for p in read_paths if is_noise_path(p) or LOG_FILE_RE.search(p)]
    duplicate_reads = [p for p, c in Counter(read_paths).items() if c > 1]

    # Long prompts
    long_prompts = [t for t in user_turns if len(t.text) >= THRESHOLDS["long_prompt_chars"]]
    if long_prompts:
        findings.append(
            WasteFinding(
                code="long_prompts",
                title="Long prompts",
                severity="high" if len(long_prompts) >= 2 else "medium",
                detail=f"{len(long_prompts)} user message(s) exceeded {THRESHOLDS['long_prompt_chars']} characters.",
                suggestion="Break requests into smaller steps. Paste only the relevant snippet, not whole specs.",
                score=len(long_prompts) * 3,
            )
        )

    # Too many files in context (via Read/Glob/Grep)
    file_tool_calls = tool_counts.get("Read", 0) + tool_counts.get("Glob", 0) + tool_counts.get("Grep", 0)
    if file_tool_calls >= THRESHOLDS["many_file_reads"] or len(unique_reads) >= 8:
        findings.append(
            WasteFinding(
                code="too_many_files",
                title="Too many files added to context",
                severity="high",
                detail=(
                    f"{file_tool_calls} file-discovery tool calls ({len(unique_reads)} unique reads). "
                    f"Top tools: {', '.join(f'{k}={v}' for k, v in tool_counts.most_common(5))}."
                ),
                suggestion="Point Cursor at specific files. Add rules to avoid repo-wide scans unless necessary.",
                score=file_tool_calls + len(unique_reads),
            )
        )

    # Unnecessary / noisy file reads
    if noise_reads or duplicate_reads:
        findings.append(
            WasteFinding(
                code="unnecessary_reads",
                title="Cursor read unnecessary or repeated files",
                severity="medium" if not noise_reads else "high",
                detail=(
                    f"{len(noise_reads)} noisy-path reads (node_modules/dist/logs), "
                    f"{len(duplicate_reads)} files read more than once."
                ),
                suggestion="Exclude build output and logs in rules. Re-read only when files change.",
                score=len(noise_reads) * 2 + len(duplicate_reads),
            )
        )

    # Long chat history
    if len(session.turns) >= THRESHOLDS["long_history_turns"]:
        findings.append(
            WasteFinding(
                code="long_history",
                title="Very long chat history",
                severity="medium" if len(session.turns) < 40 else "high",
                detail=f"{len(session.turns)} turns in one session ({len(user_turns)} user, {len(assistant_turns)} assistant).",
                suggestion="Start a fresh chat for new topics. Summarize decisions in a RULES file instead of re-explaining.",
                score=len(session.turns),
            )
        )

    # Repeated retries / corrections
    retries = 0
    for i in range(1, len(user_turns)):
        if _similar(user_turns[i - 1].text, user_turns[i].text) >= THRESHOLDS["retry_similarity"]:
            retries += 1
    if user_turns and len(assistant_turns) / max(1, len(user_turns)) >= THRESHOLDS["assistant_per_user_ratio"]:
        retries += 1
    if retries:
        findings.append(
            WasteFinding(
                code="repeated_retries",
                title="Repeated corrections or retries",
                severity="medium" if retries == 1 else "high",
                detail=f"{retries} likely retry pattern(s); high assistant-to-user turn ratio.",
                suggestion="Give one clear acceptance criterion up front. Use a checklist in the first message.",
                score=retries * 4,
            )
        )

    # Broad / vague questions
    broad = [t for t in user_turns if BROAD_QUESTION_RE.search(t.text)]
    vague = [t for t in user_turns if len(t.text) < 40 and VAGUE_QUESTION_RE.match(t.text.strip())]
    if broad or (vague and file_tool_calls >= 8):
        findings.append(
            WasteFinding(
                code="broad_questions",
                title="Broad or vague questions",
                severity="medium",
                detail=f"{len(broad)} broad repo-wide ask(s), {len(vague)} very short vague ask(s).",
                suggestion="Ask scoped questions with file paths, expected output, and constraints.",
                score=len(broad) * 3 + len(vague) * 2,
            )
        )

    # Runaway tool usage
    if len(all_tools) >= THRESHOLDS["many_tool_calls"]:
        findings.append(
            WasteFinding(
                code="runaway_tools",
                title="High tool-call volume",
                severity="high",
                detail=f"{len(all_tools)} tool calls in one session.",
                suggestion="Split the task into phases. Cancel and restart with a narrower goal if the agent loops.",
                score=len(all_tools),
            )
        )

    waste_score = sum(f.score for f in findings)
    return SessionAnalysis(
        session=session,
        findings=sorted(findings, key=lambda f: f.score, reverse=True),
        estimated_tokens=session.estimated_tokens,
        waste_score=waste_score,
    )


def analyze_project(
    *,
    project_path: Path | None = None,
    days: int | None = 30,
    limit: int = 20,
) -> AnalysisReport:
    sessions = load_sessions(project_path=project_path, days=days, limit=limit)
    analyses = [analyze_session(s) for s in sessions if s.turns]
    return AnalysisReport(
        project_path=project_path,
        sessions=sorted(analyses, key=lambda a: a.waste_score, reverse=True),
        scanned_transcripts=len(sessions),
    )
