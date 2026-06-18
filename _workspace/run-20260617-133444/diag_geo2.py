"""Check which drone can intercept which missile."""
import json
import numpy as np

with open("_workspace/run-20260617-133444/input/problem_data.json") as f:
    data = json.load(f)

missiles = data["initial_positions"]["missiles"]
drones = data["initial_positions"]["drones"]
R_s = data["parameters"]["smoke_effective_radius"]
v_m = data["parameters"]["missile_speed"]

print(f"R_s={R_s}m, v_m={v_m}m/s")
print()

for m_name, m_pos in missiles.items():
    m0 = np.array(m_pos, float)
    d_m = -m0 / np.linalg.norm(m0)
    print(f"{m_name}: {m_pos} dir=[{d_m[0]:.3f},{d_m[1]:.3f},{d_m[2]:.3f}]")

    for d_name, d_pos in drones.items():
        d0 = np.array(d_pos, float)
        # Missile crosses drone's x at:
        if abs(d_m[0]) < 1e-9:
            continue
        t_x = (d0[0] - m0[0]) / (-d_m[0] * v_m)
        if t_x <= 0:
            continue
        m_at = m0 + v_m * t_x * d_m
        dz = abs(m_at[2] - d0[2])
        dxy = np.linalg.norm(m_at[:2] - d0[:2])
        reachable = "YES" if dxy <= R_s + 20 else "NO"
        print(f"  {d_name}: t={t_x:.1f}s z={m_at[2]:.0f}m Δz={dz:.0f}m Δxy={dxy:.0f}m {reachable}")
    print()
