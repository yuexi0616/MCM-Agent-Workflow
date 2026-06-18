# Modeling and Coding Optimization Protocol

This note tightens Phase 1 and Phase 2 without changing the existing chain-intercept workflow. It turns the recurring audit findings into explicit gates that can be checked before a Devil's Advocate review.

## Phase 1: Modeling Gate

The modeling hand must add these items to `<model_design>`:

1. `parameter_source_map`: every hard numeric parameter used by the model must map to `problem_data.json`, the problem statement, or a named attachment. No competition-given value may be moved into assumptions.
2. `feasibility_precheck`: before proposing a high-dimensional optimizer, derive cheap reachability/geometry/capacity checks. If a task can be infeasible, state the diagnostic condition and the fallback output.
3. `baseline_and_invariants`: define simple baselines and monotonic sanity rules. Example: if Q2 optimizes over Q1's feasible point, Q2 must not score below Q1 unless the domains differ and the model says why.
4. `implementation_contract`: provide function signatures, input/output schemas, return types, failure semantics, random seed policy, and precision levels for coarse search vs. final validation.
5. `validation_plan`: specify unit checks, boundary cases, conservation/geometry checks, convergence checks, and result-regression checks that the coding hand must run.
6. `complexity_budget`: estimate objective evaluations and dominant operations. If the budget is too high for contest hardware, redesign before coding.

The model is not approved if it leaves the coding hand to infer an allocation rule, baseline, boundary policy, or return format.

## Phase 2: Coding Gate

The coding hand must implement these requirements:

1. Load or mirror `problem_data.json` through a typed config layer. If constants are hard-coded for performance, each block must cite the source path in `problem_data.json`.
2. Keep a traceable path from input constants to formula implementation to output rows. Every row in `results_summary.csv` must include `problem_id`, `metric_name`, `value`, `unit`, `method`, `figure_ref`, and `formula_ref`.
3. Add baseline regression checks after each optimization. If a more general optimization underperforms an included baseline, keep the baseline result or emit a blocking diagnostic.
4. Add feasibility diagnostics before returning zero or empty results. Empty intervals, infeasible assignments, and skipped figures must remove stale artifacts and write a fresh diagnostic table.
5. Use deterministic randomness with local RNG objects. Avoid global RNG resets except at program entry.
6. Do not import precomputed result artifacts. Attachments may be read as inputs, but final answers must be calculated by the model formulas.
7. Use parseable structured output. Lists in CSV cells should be JSON strings or normalized child tables, not Python `repr()` strings.
8. Validate final reported values at production precision, not only at coarse optimization precision.

## Local Quality Gate

Run the fixed gate runner after Phase 1 and Phase 2:

```powershell
python tools/run_mcm_gates.py --phase modeling
python tools/run_mcm_gates.py --phase coding --run _workspace/run-YYYYMMDD-HHMMSS
```

The runner defaults to strict mode and appends `_workspace/quality-gate-log.md`.
Use `--non-strict` during exploration when warnings should be recorded but not block promotion.

The lower-level checker remains available for one-off checks:

```powershell
python tools/mcm_quality_gate.py --model _workspace/phase-1-model.xml --problem-data _workspace/input/problem_data.json
python tools/mcm_quality_gate.py --run _workspace/run-YYYYMMDD-HHMMSS --problem-data _workspace/input/problem_data.json
```

Use `--strict` on the lower-level checker when preparing for formal audit:

```powershell
python tools/mcm_quality_gate.py --model _workspace/phase-1-model.xml --problem-data _workspace/input/problem_data.json --strict
python tools/mcm_quality_gate.py --run _workspace/run-YYYYMMDD-HHMMSS --problem-data _workspace/input/problem_data.json --strict
```

Warnings are not automatic rejections during exploration. In strict mode they block promotion to the next phase.
