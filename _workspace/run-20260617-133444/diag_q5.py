"""Quick Q5 diagnostic: just run Phase 1 pre-compute to see all 15 (drone,missile) intervals."""
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "code"))
from solver import (
    Params, load_problem_data, sample_target_cylinder,
    differential_evolution, _de_obj_single_bomb,
    BombSpec, compute_occlusion
)

RUN_DIR = Path(__file__).parent
PROBLEM_DATA = RUN_DIR / "input" / "problem_data.json"
params, data = load_problem_data(PROBLEM_DATA)
target_samples = sample_target_cylinder(params)

missiles = data["initial_positions"]["missiles"]
drones = data["initial_positions"]["drones"]
missile_names = list(missiles.keys())
drone_names = list(drones.keys())

print(f"Missiles: {missile_names}")
print(f"Drones: {drone_names}")
print()

for d_name in drone_names:
    d0 = np.array(drones[d_name], dtype=float)
    for m_name in missile_names:
        m0 = np.array(missiles[m_name], dtype=float)
        bounds = [(-np.pi, np.pi), (params.v_d_min, params.v_d_max),
                  (0.0, 30.0), (0.3, 15.0)]
        def obj(x, _d0=d0, _m0=m0):
            return _de_obj_single_bomb(x, _d0, _m0, params, target_samples)
        best_x, _, _ = differential_evolution(
            obj, bounds, pop_size=25, max_gen=40, F=0.6, CR=0.8, seed=20250617)
        theta, v, t_r, delay = best_x
        dir_vec = np.array([np.cos(theta), np.sin(theta)])
        b = BombSpec(drone0=d0, speed=float(v), dir_vec=dir_vec,
                     t_r=float(t_r), t_d=float(t_r + delay))
        _, ivs = compute_occlusion([b], m0, params, target_samples, T_max=70.0, dt=0.02)
        dur = sum(e - s for s, e in ivs) if ivs else 0.0
        print(f"{d_name}→{m_name}: v={v:.0f}m/s θ={np.degrees(theta):.1f}° "
              f"t_r={t_r:.2f}s t_d={t_r+delay:.2f}s → dur={dur:.2f}s "
              f"ivs={[(round(s,2),round(e,2)) for s,e in ivs]}")
