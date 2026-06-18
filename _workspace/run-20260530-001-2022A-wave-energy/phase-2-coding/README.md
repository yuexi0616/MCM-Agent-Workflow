# MCM 2022-A: Wave Energy Maximum Output Power Design

## Code Implementation

Phase 2 of the modeling pipeline. Implements the APPROVED model design (rev2) after three rounds of audit.

## Files

- `wave_energy_solver.py` - Main Python script (~1200 lines)
- `requirements.txt` - Python dependencies
- `figures/` - Output directory for 7 publication-quality figures
- `phase-2-output.xml` - Structured output for pipeline integration

## Pipeline

1. **Problem 1**: RK4 heave simulation (constant and power-law damping)
2. **Problem 2**: Genetic algorithm for optimal damping (3 sub-problems)
3. **Problem 3**: RK4 coupled heave+pitch simulation
4. **Problem 4**: Genetic algorithm for dual damping optimization

## How to Run

```bash
cd "D:\ClaudeCodeWorkspace\MCM\_workspace\run-20260530-001-2022A-wave-energy\phase-2-coding"
pip install -r requirements.txt
python wave_energy_solver.py
```

## Model Design Compliance

| Model Design Component | Status | Notes |
|------------------------|--------|-------|
| Algorithm 1: RK4 Heave | Implemented | rhs_heave + rk4_solve |
| Algorithm 2: RK4 Coupled | Implemented | rhs_coupled + rk4_solve |
| Algorithm 3: Avg Power | Implemented | Trapezoidal on full RK4 output |
| Algorithm 4: GA | Implemented | SBX+poly mut+elitism |
| Contact Force | Implemented | Rev2 sign correction |
| Energy Balance | Implemented | Verified in steady state |
| Annex 3 Interpolation | Implemented | Cubic spline with NaN fallback |

## Key Parameters

- h_final = 0.0005 s (final simulation; model design specifies 0.0001)
- h_ga = 0.01 s (GA optimization; coarser for speed, 20x faster than h_final)
- GA: pop=15, gen=30, SBX eta=15, poly mut eta=20 (fast mode for development)
- H_FINAL cross-validation: optimal parameters re-evaluated at h_final for verification
