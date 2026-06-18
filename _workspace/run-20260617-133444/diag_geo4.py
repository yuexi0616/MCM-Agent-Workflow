"""Check intercept feasibility with the CORRECT parameters."""
import json, numpy as np

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
    v_mx, v_my, v_mz = v_m * d_m[0], v_m * d_m[1], v_m * d_m[2]
    lines.append(f"{m_name}: start={m_pos} vel=[{v_mx:.1f},{v_my:.1f},{v_mz:.1f}]")

    for d_name, d_pos in drones.items():
        d0 = np.array(d_pos, float)
        # t when missile's x = drone's x
        if abs(d_m[0]) < 1e-9:
            continue
        t_x = (d0[0] - m0[0]) / (-d_m[0] * v_m)
        if t_x <= 0:
            lines.append(f"  {d_name}: BEHIND")
            continue
        m_at = m0 + v_m * t_x * d_m
        dz = abs(m_at[2] - d0[2])
        dxy = np.linalg.norm(m_at[:2] - d0[:2])
        # Check if occlusion is geometrically possible
        # Cloud at (d0[:2], d0[2]) sphere radius R_s
        # Missiles x-y at t_x is m_at[:2], z at t_x is m_at[2]
        # For occlusion: m_at must be within R_s of drone position
        # For occlusion: distance from missile to cloud center <= R_s
        # dxy = horizontal distance, dz = vertical distance
        # Need dxy^2 + dz^2 <= R_s^2 = 100
        dist2 = dxy**2 + dz**2
        possible = dist2 <= R_s**2 + 1  # small epsilon for numerical
        lines.append(f"  {d_name}: t={t_x:.1f}s m_z={m_at[2]:.0f}m d_z={d0[2]:.0f}m "
                     f"dz={dz:.0f}m dxy={dxy:.0f}m dist2={dist2:.0f} {'CAN' if possible else 'NO'}")
    lines.append("")

with open("_workspace/run-20260617-133444/geometry_result.txt", "w") as f:
    f.write("\n".join(lines))
print("OK")
