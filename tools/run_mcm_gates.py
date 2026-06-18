#!/usr/bin/env python3
"""
Run the fixed MCM quality gates at Phase 1/Phase 2 handoff points.

This is a convenience wrapper around mcm_quality_gate.py. It auto-locates the
standard workspace files, prints gate findings, appends a durable log entry, and
returns a non-zero exit code when the gate blocks promotion.

Supports run_state.json for checkpoint/resume:
    --resume: auto-detect latest run with run_state.json and resume from current phase
    --resume-run PATH: resume a specific run from its run_state.json

Examples:
    python tools/run_mcm_gates.py --phase modeling
    python tools/run_mcm_gates.py --phase coding --run _workspace/run-20260601-103030
    python tools/run_mcm_gates.py --phase all --non-strict
    python tools/run_mcm_gates.py --resume
    python tools/run_mcm_gates.py --resume-run _workspace/run-20260601-103030
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcm_quality_gate import Issue, check_model, check_run, print_issues

RUN_STATE_FILE = "run_state.json"


def latest_run_dir(workspace: Path) -> Path | None:
    candidates = [p for p in workspace.glob("run-*") if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: (p.stat().st_mtime, p.name))


def find_runs_with_state(workspace: Path) -> list[Path]:
    """Find all run directories that have a run_state.json."""
    runs: list[Path] = []
    for d in sorted(workspace.glob("run-*"), reverse=True):
        if d.is_dir() and (d / RUN_STATE_FILE).exists():
            runs.append(d)
    return runs


def read_run_state(run_dir: Path) -> dict[str, Any] | None:
    """Read run_state.json from a run directory."""
    state_path = run_dir / RUN_STATE_FILE
    if not state_path.exists():
        return None
    try:
        with state_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def write_run_state(run_dir: Path, state: dict[str, Any]) -> None:
    """Write run_state.json."""
    state_path = run_dir / RUN_STATE_FILE
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def update_run_state_phase(
    run_dir: Path,
    phase: str,
    status: str,
    rejection_count: int | None = None,
) -> None:
    """Update phase status in run_state.json."""
    state = read_run_state(run_dir)
    if state is None:
        return
    state["phase_status"][phase] = status
    state["current_phase"] = phase
    if status == "approved":
        state["last_approved_phase"] = phase
    if rejection_count is not None:
        key = phase.replace("-", "")
        if key in state.get("rejection_counts", {}):
            state["rejection_counts"][key] = rejection_count
    write_run_state(run_dir, state)


def determine_resume_phase(state: dict[str, Any]) -> str | None:
    """Determine which phase to resume from based on run_state.json."""
    phase_status = state.get("phase_status", {})
    # Find the first phase that is not 'approved' or 'completed'
    phase_order = ["phase-0", "phase-1", "phase-2", "phase-3", "phase-4"]
    for phase in phase_order:
        status = phase_status.get(phase, "pending")
        if status not in ("approved", "completed"):
            return phase
    return None  # All phases complete


def status_for(issues: list[Issue], strict: bool) -> str:
    has_error = any(issue.level == "ERROR" for issue in issues)
    has_warn = any(issue.level == "WARN" for issue in issues)
    if has_error or (strict and has_warn):
        return "BLOCKED"
    return "PASS"


def append_log(
    log_path: Path,
    phase: str,
    strict: bool,
    model: Path | None,
    run: Path | None,
    problem_data: Path,
    issues: list[Issue],
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    status = status_for(issues, strict)
    lines = [
        f"## {datetime.now().isoformat(timespec='seconds')} | phase={phase} | status={status}",
        "",
        f"- strict: {strict}",
        f"- problem_data: {problem_data}",
    ]
    if model is not None:
        lines.append(f"- model: {model}")
    if run is not None:
        lines.append(f"- run: {run}")
    lines.append("")
    if not issues:
        lines.append("- PASS: no issues found")
    else:
        for issue in issues:
            lines.append(f"- {issue.level}: [{issue.area}] {issue.message}")
    lines.append("")
    with log_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def print_resume_status(state: dict[str, Any]) -> None:
    """Print a human-readable summary of the run state."""
    print(f"\n=== Run: {state.get('run_id', 'unknown')} ===")
    print(f"  Problem: {state.get('problem', 'unknown')}")
    print(f"  Competition: {state.get('competition', 'mcm').upper()}  Year: {state.get('year', '?')}")
    print(f"  Current phase: {state.get('current_phase', 'unknown')}")
    print(f"  Last approved: {state.get('last_approved_phase', 'none')}")
    print(f"\n  Phase status:")
    for phase, status in state.get("phase_status", {}).items():
        icon = {"approved": "✓", "completed": "✓", "in_progress": "→", "rejected": "✗", "pending": "○"}.get(status, "?")
        print(f"    [{icon}] {phase}: {status}")
    print(f"\n  Rejection counts: {json.dumps(state.get('rejection_counts', {}))}")
    if state.get("notes"):
        print(f"  Notes: {len(state['notes'])} note(s)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MCM Phase 1/2 quality gates")
    parser.add_argument("--phase", choices=["modeling", "coding", "all"], default="all")
    parser.add_argument("--workspace", type=Path, default=Path("_workspace"))
    parser.add_argument("--model", type=Path, help="Override model XML path")
    parser.add_argument("--run", type=Path, help="Run directory path (auto-detected if omitted)")
    parser.add_argument("--problem-data", type=Path, help="Override problem_data.json path")
    parser.add_argument("--non-strict", action="store_true", help="Warnings do not block")
    parser.add_argument("--no-log", action="store_true", help="Do not append _workspace/quality-gate-log.md")
    parser.add_argument("--resume", action="store_true",
                        help="Auto-detect latest run with run_state.json and resume from current phase")
    parser.add_argument("--resume-run", type=Path, dest="resume_run",
                        help="Resume a specific run from its run_state.json")
    parser.add_argument("--status", action="store_true",
                        help="Show run_state.json status for the specified run and exit")
    args = parser.parse_args()

    strict = not args.non_strict
    workspace = args.workspace

    run_path: Path | None = None

    # Handle --resume and --resume-run
    if args.resume or args.resume_run:
        if args.resume_run:
            run_path = args.resume_run
        else:
            runs = find_runs_with_state(workspace)
            if not runs:
                print("ERROR: No run directories with run_state.json found.")
                print("       Use 'python tools/scaffold.py' to create a new run first.")
                return 1
            run_path = runs[0]

        state = read_run_state(run_path)
        if state is None:
            print(f"ERROR: Cannot read run_state.json from {run_path}")
            return 1

        if args.status:
            print_resume_status(state)
            return 0

        print_resume_status(state)
        resume_phase = determine_resume_phase(state)
        if resume_phase is None:
            print("\nAll phases complete. Use --status to review.")
            return 0

        print(f"\nResuming from {resume_phase}...")

        # Map phase to gate check
        if resume_phase == "phase-1":
            args.phase = "modeling"
        elif resume_phase == "phase-2":
            args.phase = "coding"
        else:
            print(f"Note: {resume_phase} does not have an automated gate check.")
            print(f"      Run manual checks or proceed to the next phase.")
            return 0

    # Determine run path
    if args.run:
        run_path = args.run
    elif run_path is None:
        # Try auto-detection (prefer runs with state)
        runs_with_state = find_runs_with_state(workspace)
        if runs_with_state:
            run_path = runs_with_state[0]
        else:
            run_path = latest_run_dir(workspace)

    # Determine model path and problem_data
    if run_path:
        model_path = args.model or run_path / "phase-1-modeling" / "model-design.xml"
        # Also check workspace-level model file
        if not model_path.exists():
            model_path = args.model or workspace / "phase-1-model.xml"
        problem_data = args.problem_data or run_path / "input" / "problem_data.json"
        if not problem_data.exists():
            problem_data = args.problem_data or workspace / "input" / "problem_data.json"
    else:
        model_path = args.model or workspace / "phase-1-model.xml"
        problem_data = args.problem_data or workspace / "input" / "problem_data.json"

    issues: list[Issue] = []

    if args.phase in {"modeling", "all"}:
        issues.extend(check_model(model_path, problem_data))

    if args.phase in {"coding", "all"}:
        if run_path is None:
            issues.append(Issue("ERROR", "run", f"no run-* directory found under {workspace}"))
        else:
            issues.extend(check_run(run_path, problem_data))

    print_issues(issues)

    if not args.no_log:
        append_log(
            workspace / "quality-gate-log.md",
            args.phase,
            strict,
            model_path if args.phase in {"modeling", "all"} else None,
            run_path if args.phase in {"coding", "all"} else None,
            problem_data,
            issues,
        )

    gate_status = status_for(issues, strict)

    # Update run_state.json if available
    if run_path and run_path.exists():
        phase_key = f"phase-{1 if args.phase == 'modeling' else 2 if args.phase == 'coding' else '?'}"
        if gate_status == "PASS":
            update_run_state_phase(run_path, phase_key, "approved")
            print(f"\n  run_state.json: {phase_key} → approved")
        else:
            update_run_state_phase(run_path, phase_key, "rejected")
            print(f"\n  run_state.json: {phase_key} → rejected (fix issues and re-run)")

    return 1 if gate_status == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())