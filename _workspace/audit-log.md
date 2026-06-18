# Audit Log

## run-20260531-141931 | Phase 2 | Rev 3 (Final Coding Round) | Audit at 2026-06-01T00:48:00

### 裁决
**APPROVED**

### 审计摘要
Phase 2 final coding round passes with all High-risk vulnerabilities from previous rounds addressed. Key fixes verified:

- ERR-C-012 (High): Q3 retry threshold corrected to T_q1_baseline - 0.5
- ERR-C-013 (High): Q5 geometric pre-check + diagnostic CSV added
- ERR-C-014 (High): Q2 heuristic fallback with use_heuristic_fallback parameter
- ERR-C-016 (Med): CSV format standardized with json.dumps across all outputs
- ERR-C-017 (Med): Below-ground truncation unified between _evaluate_q2 and compute_single_cloud_intervals
- ERR-C-019 (Med): Stale fig5 cleanup before skip logic

### Remaining issues (do not block):
1. ERR-C-015 (High, reclassified): Q4 3-UAV result (7.43s) < Q1 single-UAV (8.90s). Root cause: scenario geometry -- only UAV0 is within R_s of M0's LOS. Paper must explain.
2. ERR-C-018 (Med): Q1/Q2 share random seed 42 -- fragile but functional.
3. ERR-C-020 (Low): cloud_trajectory z=0 truncation applied by callers not by function itself.
4. ERR-C-R3-001 (Low): Figure numbering skips from fig4 to fig6.
5. ERR-C-R3-002 (Low): Q3 retry print message stale (uses old threshold description).
6. ERR-C-R3-003 (Med): Q4 no baseline regression check against single-UAV max.

### 新发现的漏洞 (rev3)
| ID | Risk | Category | Description |
|----|------|----------|-------------|
| ERR-C-R3-001 | Low | misleading_viz | Figure numbering gap (fig4 to fig6) after fig5 suppression. |
| ERR-C-R3-002 | Low | missing_error_handling | Q3 retry print message describes old threshold, not current. |
| ERR-C-R3-003 | Med | missing_error_handling | Q4 result (7.43s) lower than Q1 baseline (8.90s); no regression flag. |

### Pipeline Decision
APPROVED for Phase 3 paper writing.

## run-20260531-141931 | Phase 1 | Rev 6 (Q5 Simplification) | Audit at 2026-05-31T23:45:00

### 裁决
**REJECTED**

### 审计摘要
The Q5 simplification correctly removes all joint DE refinement mechanisms (JointFitness, offset table, cross-group penalty, iterative reassignment) and adopts a clean three-level architecture. However, two issues block approval:

1. **HIGH**: Algorithm 8 references undefined variable `theta_j0` (line 3). The Hungarian cost matrix cannot be computed without UAV initial headings.
2. **MED**: Spare UAV fallback (lines 15-21) never fires because Hungarian 5x5 guarantees 1 UAV per missile column, wasting 2 UAVs. The |J_m| >= 2 code path is structurally unreachable.

Q1-Q4 models (Sections 0.1-0.6, Algorithms 1-7) are intact and audited as structurally correct.

### 新发现的漏洞
| ID | Risk | Category | Description |
|----|------|----------|-------------|
| A-031 | High | ambiguous_algorithm | Algorithm 8 line 3 references undefined `theta_j0` (UAV initial heading). Cost matrix computation blocked. |
| A-032 | Med | ambiguous_algorithm | Spare UAV fallback (lines 15-21) never fires: Hungarian 5x5 guarantees one assignment per missile column. |J_m| >= 2 code path unreachable. |
| A-033 | Med | ambiguous_algorithm | SolveProblem2 returns 2 values (x_opt, T_opt) but Algorithm 7 line 4 unpacks 3. Affects Q5 indirect code path. |
| A-034 | Low | ambiguous_algorithm | SolveProblem4 return format (flat vs list-of-lists) unspecified; Algorithm 8 lines 33-38 flattening may corrupt data. Latent bug. |
| A-035 | Low | missing_assumption | "跨组空间重叠不再强制约束" acknowledged in problem_analysis but not documented in mathematical_model or algorithm_flow sections. |

## run-20260531-141931 | Phase 1 | Rev 7 (Q5 2nd Round Audit) | Audit at 2026-05-31T23:55:00

### 裁决
**APPROVED**

### 审计摘要
All 6 corrections verified as correctly implemented:

1. **ERR-A-031 (High -> RESOLVED)**: theta_j0[5] added to SolveProblem5 signature, theta_{j0} added to symbol table. All references consistent.
2. **ERR-A-032 (Med -> RESOLVED)**: Hungarian replaced by two-phase greedy. Phase 1 ensures 1 UAV/missile, Phase 2 assigns remaining 2 UAVs. |J_m| >= 2 path reachable via Q4 (SolveProblem4) call. Sequential greedy order acknowledged as suboptimal.
3. **ERR-A-033 (Med -> RESOLVED)**: SolveProblem2 now returns (x_opt, T_opt, best_interval) triple. Algorithm 7 Stage A1 unpacks consistently. Algorithm 8 Level 2 calls Q3/Q4 which also return triples.
4. **ERR-A-034 (Low -> RESOLVED)**: SolveProblem3/4 both return flat interval lists. Algorithm 8 merge + scanline operations process consistent flat format. Scanline intersection (3-group overlap) verified with multiple trace scenarios.
5. **ERR-A-035 (Low -> RESOLVED)**: Cross-group spatial overlap limitation documented in mathematical_model (Q5) with tactical justification and mitigation approach.
6. **R_s/T_c cleanup (Low -> RESOLVED)**: Both treated as global constants, excluded from all params dicts.

### 待解决项
None. Ready for Phase 2 coding.

### 注意事项
- Algorithm 7 Stage A2 assumes non-empty intervals from SolveProblem2; coding phase should add defensive check.
- Q5 single-UAV path calls SolveProblem3, which needs default theta/v_u values (not specified in Q3 model).

## run-20260531-141931 | Phase 3 (Paper Final Audit) | Audit at 2026-05-31T20:45:00

### 裁决
**APPROVED** (0 High-risk, 3 Med-risk, 3 Low-risk)

### 审计摘要
Paper is structurally complete with all 9 required MCM sections (Summary, Introduction, Assumptions, Notation, Model, Results, Sensitivity, Evaluation, References). All numerical values in the paper trace to CSV results files within rounding tolerances. Assumptions and model equations are consistent with the Phase 1 model design. AIGC patterns (filler phrases, over-paragraphing) are absent. The Summary Sheet includes quantitative results for all 5 sub-problems.

### 发现的漏洞
| ID | Risk | Category | Description |
|----|------|----------|-------------|
| ERR-P-R3-001 | Med | data_mismatch | Q5_feasibility_diagnosis.csv is stale (timestamp 15:41 vs 20:33 for other files); contains 5 of 15 pairs with perp 2640-3041 m but omits the minimum pair (UAV 0-M0, ~444 m) cited in paper. |
| ERR-P-R3-002 | Med | overfitting_conclusion | Q4 degradation explanation (7.43 < 8.90) uses unsupported causal claim about DE "attempting to generate synergy" without showing actual variable changes. |
| ERR-P-R3-003 | Med | missing_quantitative_claim | Section 6.1 R_s sensitivity is qualitative only; no numerical data on T_eff vs R_s relationship. |
| ERR-P-R3-004 | Low | data_mismatch | Q3 and Q4 have opt/val gaps (9.40 vs 9.32, 7.50 vs 7.43) not acknowledged in paper. |
| ERR-P-R3-005 | Low | missing_error_handling | Developer HTML comments (lines 279-295) remain in paper body. |
| ERR-P-R3-006 | Low | misleading_viz | Figure numbering gap: 4 to 6 with no Figure 5. |

### 修正指令 (见完整报告)
1. Clean/regenerate or remove stale Q5_feasibility_diagnosis.csv.
2. Replace speculative Q4 explanation with factual comparison of Q4 vs Q1/Q2 decision variables.
3. Add quantitative data to Section 6.1 (T_eff vs R_s table or plot) or acknowledge qualitative limitation.
4. Acknowledge optimization-validation discretization gap in Section 7.
5. Strip HTML comment blocks (lines 279-295).
6. Renumber Figure 6 to Figure 5 or explain the gap.

### Pipeline Decision
APPROVED. Final paper ready after correction directives are applied.

## 2026-06-17T13:34:44 | NEW RUN | run-20260617-133444
- Problem: 2025 MCM Problem A
- Status: Phase 0 — data extraction

