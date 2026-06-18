"""Verify geometric feasibility with the CORRECT parameters from problem_data.json."""
import json, sys, math
from pathlib import Path
import numpy as np

# Read the ACTUAL problem_data.json
with open("_workspace/run-20260617-133444/input/problem_data.json") as f:
    data = json.load(f)

missiles = data["initial_positions"]["missiles"]
drones = data["initial_positions"]["drones"]
params = data["parameters"]

print("=== Missiles ===")
for name, pos in missiles.items():
    print(f"  {name}: {pos}")

print("\n=== Drones ===")
for name, pos in drones.items():
    print(f"  {name}: {pos}")

# Check which drone can intercept which missile
R_s = params["smoke_effective_radius"]
print(f"\nCloud radius: {R_s}m")

for m_name, m_pos in missiles.items():
    m0 = np.array(m_pos, dtype=float)
    print(f"\n{m_name}: starts at {m_pos}")
    # Missile direction: toward origin (0,0,0)
    d_m = -m0 / np.linalg.norm(m0)
    v_m = params["missile_speed"]  # 300 m/s
    print(f"  direction: {d_m.round(3)}, speed={v_m}")

    for d_name, d_pos in drones.items():
        d0 = np.array(d_pos, dtype=float)
        # Check if drone can fly toward missile path
        # Find t when missile x crosses drone x
        if abs(d_m[0]) < 1e-9:
            continue
        t_cross = (d0[0] - m0[0]) / (-d_m[0] * v_m)
        if t_cross < 0:
            continue
        # Missiles position at t_cross
        m_at_cross = m0 + v_m * t_cross * d_m
        dist_xy = np.linalg.norm(m_at_cross[:2] - d0[:2])
        print(f"  {d_name} at x={d0[0]}: missile crosses at t={t_cross:.1f}s, "
              f"missile_z={m_at_cross[2]:.0f}m, drone_z={d0[2]:.0f}m, Δz={abs(m_at_cross[2]-d0[2]):.0f}m, "
              f"Δxy={dist_xy:.0f}m")
        if dist_xy < R_s + 20:  # within reach
            print(f"    → CAN OCCLUDE (Δz={abs(m_at_cross[2]-d0[2]):.0f}m)")
        else:
            print(f"    → too far")
