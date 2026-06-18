#!/usr/bin/env python3
"""
MCM 赛题启动脚手架 —— 标准化新赛题运行的目录结构、数据提取和状态初始化。

Usage:
    python tools/scaffold.py --problem "2025 MCM Problem A" --year 2025 --letter A
    python tools/scaffold.py --problem "2024 CUMCM Problem C" --year 2024 --letter C --competition cumcm
    python tools/scaffold.py --list  # 列出知识库中可用的赛题
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT / "_workspace"
KB_RAW = PROJECT_ROOT / "MCMKnowledgeBase" / "raw"
KB_WIKI_ENTITIES = PROJECT_ROOT / "MCMKnowledgeBase" / "wiki" / "entities"

RUN_STATE_TEMPLATE: dict[str, Any] = {
    "run_id": "",
    "problem": "",
    "year": 0,
    "letter": "",
    "competition": "mcm",
    "created_at": "",
    "current_phase": "phase-0",
    "phase_status": {
        "phase-0": "pending",
        "phase-1": "pending",
        "phase-2": "pending",
        "phase-3": "pending",
        "phase-4": "pending",
    },
    "rejection_counts": {
        "phase-1": 0,
        "phase-2": 0,
        "phase-3": 0,
    },
    "phase1_total_rejections": 0,
    "phase1_consecutive_rejections": 0,
    "phase2_code_rejections": 0,
    "phase2_model_feedback_count": 0,
    "phase3_rejections": 0,
    "last_approved_phase": None,
    "notes": [],
}

PROBLEM_DATA_TEMPLATE: dict[str, Any] = {
    "problem": "",
    "source": "",
    "parameters": {},
    "initial_positions": {},
    "constraints": {},
    "attachments": [],
}


def find_kb_problem(year: int, letter: str) -> dict[str, Path | None]:
    """Locate problem files in the knowledge base."""
    letter_upper = letter.upper()
    result: dict[str, Path | None] = {
        "entity_page": None,
        "problem_pdf": None,
        "problem_md": None,
        "attachments_dir": None,
        "overview_page": None,
    }

    # Entity wiki page
    entity = KB_WIKI_ENTITIES / f"{year}-{letter_upper.lower()}-*.md"
    matches = list(KB_WIKI_ENTITIES.glob(f"{year}-{letter_upper.lower()}-*.md"))
    if matches:
        result["entity_page"] = matches[0]

    # Overview page
    overview = PROJECT_ROOT / "MCMKnowledgeBase" / "wiki" / "overviews" / f"{year}-mcm-competition.md"
    if overview.exists():
        result["overview_page"] = overview

    # Raw problem files
    raw_year = KB_RAW / str(year)
    if not raw_year.exists():
        return result

    # Try 赛题 directory first
    raw_problem_dir = KB_RAW / f"{year}赛题" / f"{letter_upper}题"
    if raw_problem_dir.exists():
        pdf = raw_problem_dir / f"{letter_upper}题.pdf"
        md = raw_problem_dir / f"{letter_upper}题.md"
        if pdf.exists():
            result["problem_pdf"] = pdf
        if md.exists():
            result["problem_md"] = md
        attachments = raw_problem_dir / "附件"
        if attachments.exists():
            result["attachments_dir"] = attachments
        else:
            result["attachments_dir"] = raw_problem_dir
        return result

    # Try raw/year/letter/ directory
    raw_letter = raw_year / letter_upper
    if raw_letter.exists():
        pdf = raw_letter / f"{letter_upper}题.pdf"
        md = raw_letter / f"{letter_upper}题.md"
        if pdf.exists():
            result["problem_pdf"] = pdf
        if md.exists():
            result["problem_md"] = md
        attachments = raw_letter / "附件"
        if attachments.exists():
            result["attachments_dir"] = attachments
        return result

    return result


def list_available_problems() -> list[dict[str, Any]]:
    """List all problems available in the knowledge base."""
    problems: list[dict[str, Any]] = []
    # Scan wiki entities
    if KB_WIKI_ENTITIES.exists():
        for entity_file in sorted(KB_WIKI_ENTITIES.glob("20*-*-*.md")):
            name = entity_file.stem
            parts = name.split("-", 2)
            if len(parts) >= 2:
                problems.append({
                    "year": parts[0],
                    "letter": parts[1].upper(),
                    "slug": parts[2] if len(parts) > 2 else "",
                    "entity_page": str(entity_file.relative_to(PROJECT_ROOT)),
                })
    return problems


def create_run_directory(timestamp: str) -> Path:
    """Create the standardized run directory structure."""
    run_dir = WORKSPACE / f"run-{timestamp}"
    dirs = [
        run_dir,
        run_dir / "phase-1-modeling",
        run_dir / "phase-2-coding",
        run_dir / "phase-3-paper",
        run_dir / "code",
        run_dir / "figures",
        run_dir / "results",
        run_dir / "paper",
        run_dir / "input",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return run_dir


def init_run_state(run_dir: Path, problem: str, year: int, letter: str, competition: str) -> Path:
    """Initialize run_state.json for the new run."""
    timestamp = run_dir.name.replace("run-", "")
    state = dict(RUN_STATE_TEMPLATE)
    state["run_id"] = run_dir.name
    state["problem"] = problem
    state["year"] = year
    state["letter"] = letter.upper()
    state["competition"] = competition
    state["created_at"] = datetime.now().isoformat(timespec="seconds")
    state["phase_status"]["phase-0"] = "in_progress"

    state_path = run_dir / "run_state.json"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state_path


def init_problem_data_template(run_dir: Path, problem: str, source: str) -> Path:
    """Initialize problem_data.json template."""
    data = dict(PROBLEM_DATA_TEMPLATE)
    data["problem"] = problem
    data["source"] = source

    data_path = run_dir / "input" / "problem_data.json"
    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data_path


def copy_problem_files(run_dir: Path, kb_info: dict[str, Path | None]) -> list[str]:
    """Copy problem files from knowledge base to run input directory."""
    copied: list[str] = []
    input_dir = run_dir / "input"

    if kb_info.get("problem_md") and kb_info["problem_md"].exists():
        dest = input_dir / "problem.md"
        dest.write_text(kb_info["problem_md"].read_text(encoding="utf-8"), encoding="utf-8")
        copied.append(f"problem.md (from {kb_info['problem_md'].relative_to(PROJECT_ROOT)})")

    if kb_info.get("problem_pdf") and kb_info["problem_pdf"].exists():
        import shutil
        dest = input_dir / "problem.pdf"
        shutil.copy2(kb_info["problem_pdf"], dest)
        copied.append(f"problem.pdf (from {kb_info['problem_pdf'].relative_to(PROJECT_ROOT)})")

    if kb_info.get("attachments_dir") and kb_info["attachments_dir"].exists():
        import shutil
        attachments_dest = input_dir / "attachments"
        if attachments_dest.exists():
            shutil.rmtree(attachments_dest)
        shutil.copytree(kb_info["attachments_dir"], attachments_dest)
        copied.append(f"attachments/ (from {kb_info['attachments_dir'].relative_to(PROJECT_ROOT)})")

    return copied


def append_audit_log(run_dir: Path, problem: str) -> None:
    """Append a new run marker to the audit log."""
    log_path = WORKSPACE / "audit-log.md"
    timestamp = datetime.now().isoformat(timespec="seconds")
    entry = (
        f"\n## {timestamp} | NEW RUN | {run_dir.name}\n"
        f"- Problem: {problem}\n"
        f"- Status: Phase 0 — data extraction\n"
        f"\n"
    )
    with log_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description="MCM 赛题启动脚手架")
    parser.add_argument("--problem", type=str, help="赛题描述，如 '2025 MCM Problem A'")
    parser.add_argument("--year", type=int, help="赛题年份")
    parser.add_argument("--letter", type=str, help="赛题字母 (A/B/C/D/E)")
    parser.add_argument("--competition", type=str, default="mcm", choices=["mcm", "cumcm"],
                        help="竞赛类型 (mcm 或 cumcm)")
    parser.add_argument("--list", action="store_true", help="列出知识库中可用的赛题")
    parser.add_argument("--workspace", type=Path, default=WORKSPACE,
                        help="工作区路径 (默认 _workspace)")
    args = parser.parse_args()

    if args.list:
        problems = list_available_problems()
        if not problems:
            print("知识库中未找到赛题实体页。")
            return 0
        print(f"知识库中共有 {len(problems)} 个赛题实体页：\n")
        for p in problems:
            print(f"  {p['year']} Problem {p['letter']} — {p['slug']}  ({p['entity_page']})")
        return 0

    if not args.problem or not args.year or not args.letter:
        parser.error("必须提供 --problem, --year, --letter 参数（或使用 --list 查看可用赛题）")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    print(f"=== MCM 赛题脚手架 ===\n")
    print(f"赛题: {args.problem}")
    print(f"年份: {args.year}  字母: {args.letter.upper()}  竞赛: {args.competition.upper()}")
    print(f"Run ID: run-{timestamp}\n")

    # 1. Locate KB resources
    print("[1/7] 检索知识库...")
    kb_info = find_kb_problem(args.year, args.letter)
    if kb_info["entity_page"]:
        print(f"  ✓ 实体页: {kb_info['entity_page'].relative_to(PROJECT_ROOT)}")
    else:
        print(f"  ⚠ 未找到实体页 (wiki/entities/{args.year}-{args.letter.lower()}-*.md)")
    if kb_info["overview_page"]:
        print(f"  ✓ 年度概览: {kb_info['overview_page'].relative_to(PROJECT_ROOT)}")
    if kb_info["problem_md"]:
        print(f"  ✓ 赛题 MD: {kb_info['problem_md'].relative_to(PROJECT_ROOT)}")
    if kb_info["problem_pdf"]:
        print(f"  ✓ 赛题 PDF: {kb_info['problem_pdf'].relative_to(PROJECT_ROOT)}")
    if kb_info["attachments_dir"]:
        print(f"  ✓ 附件目录: {kb_info['attachments_dir'].relative_to(PROJECT_ROOT)}")
    if not any([kb_info["entity_page"], kb_info["problem_md"], kb_info["problem_pdf"]]):
        print(f"  ⚠ 知识库中未找到 {args.year} Problem {args.letter.upper()} 的任何资料")
        print(f"  → 将创建空模板，需手动填充 input/ 目录")

    # 2. Create run directory
    print("\n[2/7] 创建目录结构...")
    run_dir = create_run_directory(timestamp)
    print(f"  ✓ {run_dir.relative_to(PROJECT_ROOT)}/")

    # 3. Initialize run_state.json
    print("\n[3/7] 初始化运行状态...")
    state_path = init_run_state(run_dir, args.problem, args.year, args.letter, args.competition)
    print(f"  ✓ run_state.json (phase=phase-0)")

    # 4. Initialize problem_data.json template
    print("\n[4/7] 创建 problem_data.json 模板...")
    source = f"MCMKnowledgeBase/raw/{args.year}/{args.letter.upper()}/"
    if kb_info["problem_md"]:
        source = str(kb_info["problem_md"].relative_to(PROJECT_ROOT))
    data_path = init_problem_data_template(run_dir, args.problem, source)
    print(f"  ✓ input/problem_data.json (模板，需手动填充参数)")

    # 5. Copy problem files
    print("\n[5/7] 复制赛题文件...")
    copied = copy_problem_files(run_dir, kb_info)
    if copied:
        for c in copied:
            print(f"  ✓ {c}")
    else:
        print(f"  ⚠ 无可复制文件，请手动将赛题放入 input/")

    # 6. Append audit log
    print("\n[6/7] 追加审计日志...")
    append_audit_log(run_dir, args.problem)
    print(f"  ✓ _workspace/audit-log.md")

    # 7. Summary
    print("\n[7/7] 脚手架完成！\n")
    print("=" * 60)
    print(f"  Run 目录:  {run_dir.relative_to(PROJECT_ROOT)}/")
    print(f"  当前阶段:  Phase 0 — 数据提取")
    print(f"  下一步:    从赛题 PDF/附件中提取所有硬数据，填充")
    print(f"             {run_dir.name}/input/problem_data.json")
    print(f"  续跑命令:  python tools/run_mcm_gates.py --phase modeling --run {run_dir.relative_to(PROJECT_ROOT)}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())