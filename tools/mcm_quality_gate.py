#!/usr/bin/env python3
"""
Quality gate for the MCM chain-intercept workflow.

The checks are intentionally lightweight and dependency-free. They are meant to
catch recurring modeling/coding failures before the Devil's Advocate phase:

- model XML missing required sections or hard-data traceability
- solver code importing precomputed answers or lacking deterministic execution
- run directories with incomplete results/figures or stale references

Usage:
    python tools/mcm_quality_gate.py --model _workspace/phase-1-model.xml \
        --problem-data _workspace/input/problem_data.json

    python tools/mcm_quality_gate.py --run _workspace/run-20260601-103030 \
        --problem-data _workspace/input/problem_data.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REQUIRED_MODEL_TAGS = [
    "problem_analysis",
    "assumptions",
    "symbol_table",
    "mathematical_model",
    "algorithm_flow",
]

RECOMMENDED_MODEL_MARKERS = {
    "parameter_source_map": [
        "parameter_source_map",
        "parameter source",
        "参数来源",
        "来源映射",
        "problem_data.json",
    ],
    "feasibility_precheck": [
        "feasibility_precheck",
        "feasibility precheck",
        "可行性预检",
        "几何可行",
        "可达性",
    ],
    "baseline_and_invariants": [
        "baseline",
        "invariant",
        "regression",
        "基线",
        "单弹基线",
        "单机基线",
        "不低于",
    ],
    "implementation_contract": [
        "implementation_contract",
        "function signature",
        "return format",
        "函数签名",
        "返回值",
        "输入/输出",
    ],
    "validation_plan": [
        "validation_plan",
        "sanity",
        "robustness",
        "验证计划",
        "边界情况",
        "自检",
    ],
}

REQUIRED_SUMMARY_COLUMNS = {
    "problem_id",
    "metric_name",
    "value",
    "unit",
    "method",
    "figure_ref",
    "formula_ref",
}

SUSPICIOUS_CODE_PATTERNS = [
    (re.compile(r"\bnp\.load\s*\("), "np.load() can import precomputed arrays"),
    (re.compile(r"\bpickle\.load\s*\("), "pickle.load() can import precomputed objects"),
    (re.compile(r"\bjoblib\.load\s*\("), "joblib.load() can import precomputed models/results"),
    (re.compile(r"results?\.(npy|npz|pkl|pickle|joblib)", re.I), "result artifact imported by name"),
    (re.compile(r"synthetic|fake_data|mock_result", re.I), "synthetic/fake-result marker"),
]


@dataclass
class Issue:
    level: str
    area: str
    message: str


def read_text(path: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def load_json(path: Path | None) -> Any:
    if path is None:
        return None
    try:
        return json.loads(read_text(path))
    except Exception as exc:  # noqa: BLE001 - this is a CLI checker
        raise SystemExit(f"ERROR: cannot parse JSON {path}: {exc}") from exc


def flatten_json(obj: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_json(value, new_prefix)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            yield from flatten_json(value, f"{prefix}[{idx}]")
    else:
        yield prefix, obj


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def number_patterns(value: int | float) -> set[str]:
    v = float(value)
    patterns = {f"{v:g}", f"{v:.1f}", f"{v:.2f}"}
    if abs(v - round(v)) < 1e-9:
        iv = int(round(v))
        patterns.update({str(iv), f"{iv}.0"})
    return patterns


def is_critical_numeric(path: str, value: int | float) -> bool:
    if abs(float(value)) < 1e-12:
        return False
    lower = path.lower()
    markers = [
        "speed",
        "radius",
        "duration",
        "interval",
        "height",
        "position",
        "center",
        "missile",
        "uav",
        ".m",
        ".fy",
        "q1",
    ]
    return any(marker in lower for marker in markers)


def text_contains_number(text: str, value: int | float) -> bool:
    compact = text.replace(",", "")
    return any(re.search(rf"(?<![\d.]){re.escape(pat)}(?![\d.])", compact) for pat in number_patterns(value))


def check_model(model_path: Path, problem_data_path: Path | None) -> list[Issue]:
    issues: list[Issue] = []
    if not model_path.exists():
        return [Issue("ERROR", "model", f"missing model file: {model_path}")]

    text = read_text(model_path)
    lower = text.lower()

    for tag in REQUIRED_MODEL_TAGS:
        if not re.search(rf"<{tag}\b[^>]*>.*?</{tag}>", text, flags=re.S | re.I):
            issues.append(Issue("ERROR", "model", f"missing required XML tag <{tag}>"))

    for name, markers in RECOMMENDED_MODEL_MARKERS.items():
        if not any(marker.lower() in lower for marker in markers):
            issues.append(Issue("WARN", "model", f"recommended modeling section/marker not found: {name}"))

    if re.search(r"待定|自行假设|自设|猜测", text):
        issues.append(Issue("WARN", "model", "model text still contains placeholder or self-assumption wording"))

    data = load_json(problem_data_path) if problem_data_path else None
    if data is not None:
        critical = [
            (path, value)
            for path, value in flatten_json(data)
            if is_number(value) and is_critical_numeric(path, value)
        ]
        missing = [(path, value) for path, value in critical if not text_contains_number(text, value)]
        if missing:
            preview = ", ".join(f"{path}={value}" for path, value in missing[:12])
            issues.append(
                Issue(
                    "WARN",
                    "model",
                    f"{len(missing)}/{len(critical)} critical numeric values from problem_data are not explicit in model text; first: {preview}",
                )
            )

        smoke = data.get("smoke_bomb", {}) if isinstance(data, dict) else {}
        cloud_radius = smoke.get("cloud_radius_m")
        if cloud_radius == 10 and re.search(r"R[_\s-]*s\s*=?\s*50|cloud_radius[^0-9]{0,20}50", text, flags=re.I):
            issues.append(Issue("ERROR", "model", "possible stale/self-set smoke radius 50 found; problem_data says 10m"))

    if "algorithm_flow" in lower and not re.search(r"\b(function|algorithm|for|while|step)\b|函数|算法|循环|步骤", text, re.I):
        issues.append(Issue("WARN", "model", "algorithm_flow appears too vague for direct implementation"))

    return issues


def check_solver_code(solver_path: Path, problem_data_path: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    if not solver_path.exists():
        return [Issue("ERROR", "code", f"missing solver file: {solver_path}")]

    text = read_text(solver_path)

    if "if __name__" not in text:
        issues.append(Issue("ERROR", "code", "solver has no if __name__ == '__main__' entry point"))

    for pattern, message in SUSPICIOUS_CODE_PATTERNS:
        if pattern.search(text):
            issues.append(Issue("ERROR", "code", f"suspicious result-loading pattern: {message}"))

    if re.search(r"\bTODO\b|pass\s*(#|$)", text):
        issues.append(Issue("WARN", "code", "solver contains TODO/pass markers; confirm they are intentional"))

    uses_random = bool(re.search(r"\bnp\.random\b|\brandom\.", text))
    has_seed = bool(re.search(r"np\.random\.seed\s*\(|default_rng\s*\(|RandomState\s*\(", text))
    if uses_random and not has_seed:
        issues.append(Issue("ERROR", "code", "solver uses randomness without a fixed seed or local RNG"))

    if problem_data_path and problem_data_path.exists():
        data = load_json(problem_data_path)
        if "problem_data.json" not in text and data is not None:
            issues.append(
                Issue(
                    "WARN",
                    "code",
                    "solver does not load problem_data.json; hard-coded constants must be source-commented and audited",
                )
            )
        smoke = data.get("smoke_bomb", {}) if isinstance(data, dict) else {}
        cloud_radius = smoke.get("cloud_radius_m")
        if cloud_radius == 10 and re.search(r"R[_\s-]*S\s*=\s*50|cloud_radius[^0-9]{0,20}50", text, flags=re.I):
            issues.append(Issue("ERROR", "code", "possible stale/self-set smoke radius 50 found; problem_data says 10m"))

    if "to_csv" not in text and "to_excel" not in text:
        issues.append(Issue("WARN", "code", "solver does not appear to write structured CSV/XLSX results"))

    return issues


def read_summary_csv(path: Path) -> tuple[list[dict[str, str]], list[Issue]]:
    issues: list[Issue] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except UnicodeDecodeError:
        with path.open("r", encoding="gb18030", newline="") as fh:
            rows = list(csv.DictReader(fh))
    except Exception as exc:  # noqa: BLE001
        return [], [Issue("ERROR", "run", f"cannot read results summary {path}: {exc}")]

    if not rows:
        issues.append(Issue("ERROR", "run", f"empty results summary: {path}"))
        return rows, issues

    missing_cols = REQUIRED_SUMMARY_COLUMNS.difference(rows[0].keys())
    if missing_cols:
        issues.append(Issue("ERROR", "run", f"results summary missing columns: {sorted(missing_cols)}"))
    return rows, issues


def parse_float(value: str) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def split_refs(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,|]\s*|\s+", value.strip())
    return [p for p in parts if p and p.lower() not in {"none", "nan", "-"}]


def check_ordered_duration_sanity(rows: list[dict[str, str]]) -> list[Issue]:
    issues: list[Issue] = []
    durations: dict[str, float] = {}
    for row in rows:
        pid = row.get("problem_id", "").upper()
        if not re.fullmatch(r"Q\d+", pid):
            continue
        if row.get("unit", "").strip().lower() not in {"s", "sec", "second", "seconds"}:
            continue
        value = parse_float(row.get("value", ""))
        if value is None:
            continue
        durations.setdefault(pid, value)

    eps = 1e-6
    if "Q1" in durations and "Q2" in durations and durations["Q2"] + eps < durations["Q1"]:
        issues.append(Issue("WARN", "run", f"Q2 duration {durations['Q2']} is below Q1 baseline {durations['Q1']}"))
    if "Q2" in durations and "Q3" in durations and durations["Q3"] + eps < durations["Q2"]:
        issues.append(Issue("WARN", "run", f"Q3 duration {durations['Q3']} is below Q2 baseline {durations['Q2']}"))
    if "Q2" in durations and "Q4" in durations and durations["Q4"] + eps < durations["Q2"]:
        issues.append(Issue("WARN", "run", f"Q4 duration {durations['Q4']} is below Q2 baseline {durations['Q2']}"))
    if "Q5" in durations and abs(durations["Q5"]) < eps:
        issues.append(Issue("WARN", "run", "Q5 duration is zero; require explicit feasibility diagnostic and paper explanation"))
    return issues


def check_run(run_dir: Path, problem_data_path: Path | None) -> list[Issue]:
    issues: list[Issue] = []
    if not run_dir.exists():
        return [Issue("ERROR", "run", f"missing run directory: {run_dir}")]

    solver_path = run_dir / "code" / "solver.py"
    requirements_path = run_dir / "code" / "requirements.txt"
    figures_dir = run_dir / "figures"
    results_dir = run_dir / "results"
    summary_csv = results_dir / "results_summary.csv"
    summary_xlsx = results_dir / "results_summary.xlsx"

    issues.extend(check_solver_code(solver_path, problem_data_path))

    if not requirements_path.exists():
        issues.append(Issue("ERROR", "run", "missing code/requirements.txt"))
    if not figures_dir.exists() or not any(figures_dir.glob("*.png")):
        issues.append(Issue("ERROR", "run", "missing figures/*.png"))
    if not results_dir.exists():
        issues.append(Issue("ERROR", "run", "missing results directory"))
    if not summary_csv.exists() and not summary_xlsx.exists():
        issues.append(Issue("ERROR", "run", "missing results_summary.csv/xlsx"))

    rows: list[dict[str, str]] = []
    if summary_csv.exists():
        rows, summary_issues = read_summary_csv(summary_csv)
        issues.extend(summary_issues)

    if rows and figures_dir.exists():
        referenced_figures: set[str] = set()
        for row in rows:
            for ref in split_refs(row.get("figure_ref", "")):
                if ref.lower().endswith(".png"):
                    referenced_figures.add(Path(ref).name)
                    if not (figures_dir / Path(ref).name).exists():
                        issues.append(Issue("ERROR", "run", f"figure_ref not found: {ref}"))

        actual_figures = {p.name for p in figures_dir.glob("*.png")}
        unreferenced = sorted(actual_figures.difference(referenced_figures))
        if unreferenced:
            issues.append(Issue("WARN", "run", f"unreferenced figures in run directory: {unreferenced[:8]}"))

        bad_names = [name for name in actual_figures if not re.match(r"fig\d{2}_.+\.png$", name, re.I)]
        if bad_names:
            issues.append(Issue("WARN", "run", f"figure names do not match figNN_*.png: {bad_names[:8]}"))

    if rows and results_dir.exists():
        pids = sorted({row.get("problem_id", "").upper() for row in rows if row.get("problem_id")})
        for pid in pids:
            csv_files = list(results_dir.glob(f"{pid}_*.csv")) + list(results_dir.glob(f"{pid.lower()}_*.csv"))
            xlsx_files = list(results_dir.glob(f"{pid}_*.xlsx")) + list(results_dir.glob(f"{pid.lower()}_*.xlsx"))
            if not csv_files and not xlsx_files:
                issues.append(Issue("WARN", "run", f"no dedicated result table found for {pid}"))

        issues.extend(check_ordered_duration_sanity(rows))

    return issues


def print_issues(issues: list[Issue]) -> None:
    if not issues:
        print("PASS: no issues found")
        return
    for issue in issues:
        print(f"{issue.level}: [{issue.area}] {issue.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="MCM modeling/code quality gate")
    parser.add_argument("--model", type=Path, help="Path to phase-1 model XML")
    parser.add_argument("--run", type=Path, help="Path to run directory")
    parser.add_argument("--solver", type=Path, help="Path to a standalone solver.py")
    parser.add_argument("--problem-data", type=Path, help="Path to problem_data.json")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    issues: list[Issue] = []
    if args.model:
        issues.extend(check_model(args.model, args.problem_data))
    if args.solver:
        issues.extend(check_solver_code(args.solver, args.problem_data))
    if args.run:
        issues.extend(check_run(args.run, args.problem_data))
    if not (args.model or args.solver or args.run):
        parser.error("provide at least one of --model, --solver, or --run")

    print_issues(issues)

    has_error = any(issue.level == "ERROR" for issue in issues)
    has_warn = any(issue.level == "WARN" for issue in issues)
    return 1 if has_error or (args.strict and has_warn) else 0


if __name__ == "__main__":
    sys.exit(main())
