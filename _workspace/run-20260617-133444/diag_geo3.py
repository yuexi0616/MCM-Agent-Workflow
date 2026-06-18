"""Check which drone can intercept which missile."""
import json
import numpy as np
import sys

sys.stdout.reconfigure(line_buffering=True)

with open("_workspace/run-20260617-133444/input/problem_data.json") as f:
    data = json.load(f)

missiles = data["initial_positions"]["missiles"]
drones = data["initial_positions"]["drones"]
R_s = data["parameters"]["smoke_effective_radius"]
v_m = data["parameters"]["missile_speed"]

lines = []
lines.append(f"R_s={R_s}m, v_m={v_m}m/s\n")

for m_name, m_pos in missiles.items():
    m0 = np.array(m_pos, float)
    d_m = -m0 / np.linalg.norm(m0)
    lines.append(f"{m_name}: {m_pos} dir=[{d_m[0]:.3f},{d_m[1]:.3f},{d_m[2]:.3f}]")

    for d_name, d_pos in drones.items():
        d0 = np.array(d_pos, float)
        if abs(d_m[0]) < 1e-9:
            continue
        t_x = (d0[0] - m0[0]) / (-d_m[0] * v_m)
        if t_x <= 0:
            lines.append(f"  {d_name}: BEHIND missile (missile already past)")
            continue
        m_at = m0 + v_m * t_x * d_m
        dz = abs(m_at[2] - d0[2])
        dxy = np.linalg.norm(m_at[:2] - d0[:2])
        reachable = "CAN_OCCLUDE" if dxy <= R_s + 20 else "TOO_FAR"
        lines.append(f"  {d_name}: t={t_x:.1f}s missile_z={m_at[2]:.0f}m drone_z={d0[2]:.0f}m dxy={dxy:.0f}m {reachable}")
    lines.append("")

with open("_workspace/run-20260617-133444/geometry_result.txt", "w") as f:
    f.write("\n".join(lines))
print("Written to geometry_result.txt")
