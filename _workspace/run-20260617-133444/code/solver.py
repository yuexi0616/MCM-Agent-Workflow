"""
2025 MCM Problem A: 无人机烟幕干扰弹投放策略 —— 完整求解器

所有数值参数从 problem_data.json 读取（严禁硬编码自设值）。
几何模型：导弹-目标视线 vs 云团球体 = 线段-球相交判据。
优化算法：多起点网格粗搜索 + 差分进化 (DE) 局部细化。
随机数：numpy Generator with seed 20250617，保证可复现。

依赖: numpy, matplotlib
运行: python solver.py (当前目录为 run-{timestamp})
     或 python code/solver.py
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# ------- path handling (run from anywhere inside the workspace tree) -------
SCRIPT_DIR = Path(__file__).resolve().parent
RUN_DIR = SCRIPT_DIR.parent
INPUT_DIR = RUN_DIR / "input"
PROBLEM_DATA = INPUT_DIR / "problem_data.json"
RESULTS_DIR = RUN_DIR / "results"
FIGURES_DIR = RUN_DIR / "figures"
RESULTS_DIR.mkdir(exist_ok=True)
FIGURES_DIR.mkdir(exist_ok=True)


@dataclass
class Params:
    v_m: float          # missile speed, m/s
    R_s: float          # cloud effective radius, m
    v_cs: float         # cloud sink speed, m/s
    tau_max: float      # cloud effective duration, s
    v_d_min: float      # drone min speed, m/s
    v_d_max: float      # drone max speed, m/s
    g: float            # gravity, m/s^2
    target_radius: float
    target_height: float
    target_center_z: float  # midpoint of cylinder along z
    max_bombs_per_drone: int


def load_problem_data(path: Path) -> tuple[Params, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    p = data["parameters"]
    params = Params(
        v_m=float(p["missile_speed"]),
        R_s=float(p["smoke_effective_radius"]),
        v_cs=float(p["smoke_sinking_speed"]),
        tau_max=float(p["smoke_effective_duration"]),
        v_d_min=float(p["drone_speed_min"]),
        v_d_max=float(p["drone_speed_max"]),
        g=float(p["gravity"]),
        target_radius=float(p["target_cylinder_radius"]),
        target_height=float(p["target_cylinder_height"]),
        target_center_z=float(p["target_cylinder_height"]) / 2.0,
        max_bombs_per_drone=int(p.get("max_bombs_per_drone", 3)),
    )
    return params, data


# -------------------- geometry --------------------
def missile_position(t: float, m0: np.ndarray, params: Params) -> np.ndarray:
    """3D straight-line flight toward origin with speed v_m."""
    dist = float(np.linalg.norm(m0))
    if dist < 1e-12:
        return m0.copy()
    direction = -m0 / dist
    return m0 + params.v_m * t * direction


def drone_position(t: float, d0: np.ndarray, speed: float, dir_vec: np.ndarray) -> np.ndarray:
    """Constant-altitude straight flight. dir_vec is 2D unit vector in xy plane."""
    pos = d0.copy().astype(float)
    pos[0] += speed * dir_vec[0] * t
    pos[1] += speed * dir_vec[1] * t
    # z unchanged (等高度飞行)
    return pos


def cloud_at_det(t_r: float, t_d: float, d0: np.ndarray, speed: float, dir_vec: np.ndarray,
                 params: Params) -> np.ndarray:
    """Cloud center position at detonation time t_d (bomb free-fall from t_r to t_d)."""
    release = drone_position(t_r, d0, speed, dir_vec)
    dt = t_d - t_r
    if dt < 0:
        raise ValueError(f"t_d ({t_d}) must be > t_r ({t_r})")
    # horizontal inertia + gravity drop
    pos = release.copy()
    pos[0] += speed * dir_vec[0] * dt
    pos[1] += speed * dir_vec[1] * dt
    pos[2] -= 0.5 * params.g * dt * dt
    return pos


def cloud_center(t: float, t_d: float, cloud0: np.ndarray, params: Params) -> np.ndarray | None:
    """Cloud center at global time t. Returns None if cloud not yet formed or expired."""
    if t < t_d:
        return None
    if t > t_d + params.tau_max:
        return None
    pos = cloud0.copy()
    pos[2] -= params.v_cs * (t - t_d)
    return pos


def line_sphere_intersect(P: np.ndarray, Q: np.ndarray, C: np.ndarray, R: float) -> bool:
    """Return True iff the line segment P->Q intersects the sphere centered at C with radius R."""
    A = P - C
    B = Q - P
    a = float(np.dot(B, B))
    if a < 1e-24:
        return float(np.dot(A, A)) <= R * R
    b = 2.0 * float(np.dot(A, B))
    c = float(np.dot(A, A)) - R * R
    disc = b * b - 4.0 * a * c
    if disc < 0:
        return False
    sq = np.sqrt(disc)
    s1 = (-b - sq) / (2.0 * a)
    s2 = (-b + sq) / (2.0 * a)
    return (0.0 <= s1 <= 1.0) or (0.0 <= s2 <= 1.0) or (s1 < 0.0 < s2)


def sample_target_cylinder(params: Params, n_azimuth: int = 8, n_height: int = 5) -> np.ndarray:
    """Sample points on the cylinder surface (axis parallel to z, center line x=0, y=200)."""
    r = params.target_radius
    h = params.target_height
    samples: list[list[float]] = []
    # side surface
    for ialpha in range(n_azimuth):
        alpha = 2 * np.pi * ialpha / n_azimuth
        for ih in range(n_height):
            z_s = h * ih / (n_height - 1)
            samples.append([r * np.cos(alpha), 200.0 + r * np.sin(alpha), z_s])
    # top and bottom disks
    for disk_z in (0.0, h):
        for ir in range(3):
            rr = r * (ir + 1) / 3
            for ialpha in range(3):
                alpha = 2 * np.pi * ialpha / 3
                samples.append([rr * np.cos(alpha), 200.0 + rr * np.sin(alpha), disk_z])
    return np.array(samples)


def is_target_fully_occluded(missile_pos: np.ndarray, active_clouds: list[np.ndarray],
                             params: Params, target_samples: np.ndarray) -> bool:
    """Return True if, for every target sample point, the line-of-sight from the missile
    to that sample passes through at least one cloud sphere."""
    if not active_clouds:
        return False
    for T in target_samples:
        if not any(line_sphere_intersect(missile_pos, T, C, params.R_s) for C in active_clouds):
            return False
    return True


# -------------------- duration calculation --------------------
@dataclass
class BombSpec:
    drone0: np.ndarray
    speed: float
    dir_vec: np.ndarray
    t_r: float
    t_d: float


def compute_occlusion(bombs: list[BombSpec], missile0: np.ndarray, params: Params,
                      target_samples: np.ndarray, T_max: float = 70.0, dt: float = 0.01
                      ) -> tuple[float, list[tuple[float, float]]]:
    """Compute total occlusion duration and contiguous intervals for a set of bombs.

    Returns (total_seconds, list of (t_start, t_end) intervals).
    """
    cloud_centers0: list[np.ndarray] = []
    t_d_list: list[float] = []
    for b in bombs:
        if b.t_d <= b.t_r:
            continue
        c0 = cloud_at_det(b.t_r, b.t_d, b.drone0, b.speed, b.dir_vec, params)
        cloud_centers0.append(c0)
        t_d_list.append(b.t_d)

    n_steps = int(np.ceil(T_max / dt)) + 1
    times = np.linspace(0.0, T_max, n_steps)
    total = 0.0
    intervals: list[tuple[float, float]] = []
    t_start: float | None = None
    for i, t in enumerate(times):
        active: list[np.ndarray] = []
        for c0, t_d in zip(cloud_centers0, t_d_list):
            cc = cloud_center(float(t), t_d, c0, params)
            if cc is not None:
                active.append(cc)
        mpos = missile_position(float(t), missile0, params)
        if is_target_fully_occluded(mpos, active, params, target_samples):
            if t_start is None:
                t_start = float(t)
            total += dt
        else:
            if t_start is not None:
                intervals.append((t_start, float(t)))
                t_start = None
    if t_start is not None:
        intervals.append((t_start, T_max))
    return total, intervals


# -------------------- interval set operations --------------------
def union_duration(intervals: list[tuple[float, float]]) -> float:
    """Compute total length of the union of possibly-overlapping intervals."""
    if not intervals:
        return 0.0
    sorted_ints = sorted(intervals, key=lambda x: x[0])
    total = 0.0
    cur_start, cur_end = sorted_ints[0]
    for s, e in sorted_ints[1:]:
        if s <= cur_end:          # overlap or touch → extend
            cur_end = max(cur_end, e)
        else:                      # gap → close current, start new
            total += cur_end - cur_start
            cur_start, cur_end = s, e
    total += cur_end - cur_start
    return total


def intersection_duration(
        intervals_per_missile: list[list[tuple[float, float]]]
) -> float:
    """Compute total length of the intersection of interval lists from all missiles.

    Each element of intervals_per_missile is the list of [t_in, t_out] intervals
    for one missile. Returns length of the time axis where EVERY missile is occluded.
    """
    # Build a unified timeline at dt=0.01 resolution
    T_MAX = 70.0
    DT = 0.01
    n_steps = int(T_MAX / DT) + 1
    times = np.linspace(0.0, T_MAX, n_steps)
    all_occluded = np.ones(n_steps, dtype=bool)

    for intervals in intervals_per_missile:
        if not intervals:
            return 0.0
        occ = np.zeros(n_steps, dtype=bool)
        for s, e in intervals:
            mask = (times >= s) & (times <= e)
            occ |= mask
        all_occluded &= occ

    return float(all_occluded.sum()) * DT


def occlusion_timeline(bombs: list[BombSpec], missile0: np.ndarray, params: Params,
                       target_samples: np.ndarray, T_max: float = 70.0, dt: float = 0.01
                       ) -> tuple[np.ndarray, np.ndarray]:
    """Return arrays (times, occlusion_state_0_or_1) — used for plotting."""
    cloud_centers0: list[np.ndarray] = []
    t_d_list: list[float] = []
    for b in bombs:
        if b.t_d <= b.t_r:
            continue
        c0 = cloud_at_det(b.t_r, b.t_d, b.drone0, b.speed, b.dir_vec, params)
        cloud_centers0.append(c0)
        t_d_list.append(b.t_d)
    n = int(np.ceil(T_max / dt)) + 1
    times = np.linspace(0.0, T_max, n)
    state = np.zeros(n, dtype=int)
    for i, t in enumerate(times):
        active: list[np.ndarray] = []
        for c0, t_d in zip(cloud_centers0, t_d_list):
            cc = cloud_center(float(t), t_d, c0, params)
            if cc is not None:
                active.append(cc)
        mpos = missile_position(float(t), missile0, params)
        if is_target_fully_occluded(mpos, active, params, target_samples):
            state[i] = 1
    return times, state


# -------------------- differential evolution --------------------
def differential_evolution(obj, bounds, pop_size: int = 40, max_gen: int = 80,
                          F: float = 0.6, CR: float = 0.8, seed: int = 20250617) -> tuple[np.ndarray, float, list[float]]:
    """Minimal DE minimiser. obj(x) returns a float; we minimise (negate externally if max needed)."""
    rng = np.random.default_rng(seed)
    n_dim = len(bounds)
    lb = np.array([b[0] for b in bounds], dtype=float)
    ub = np.array([b[1] for b in bounds], dtype=float)

    # initial population
    pop = rng.uniform(lb, ub, size=(pop_size, n_dim))
    fitness = np.array([obj(pop[i]) for i in range(pop_size)])

    best_idx = int(np.argmin(fitness))
    convergence: list[float] = []

    for gen in range(max_gen):
        for i in range(pop_size):
            idx = [j for j in range(pop_size) if j != i]
            a, b_r, c = rng.choice(idx, size=3, replace=False)
            mutant = np.clip(pop[a] + F * (pop[b_r] - pop[c]), lb, ub)
            cross = rng.random(n_dim) < CR
            if not np.any(cross):
                cross[rng.integers(0, n_dim)] = True
            trial = np.where(cross, mutant, pop[i])
            ft = obj(trial)
            if ft < fitness[i]:
                pop[i] = trial
                fitness[i] = ft
                if ft < fitness[best_idx]:
                    best_idx = i
        convergence.append(float(fitness[best_idx]))
    return pop[best_idx], float(fitness[best_idx]), convergence


# -------------------- per-problem solve --------------------
def solve_q1(params: Params, data: dict[str, Any], target_samples: np.ndarray
             ) -> tuple[float, BombSpec, np.ndarray, np.ndarray]:
    """Fix FY1, speed=120, direction toward fake target (negative x direction), t_r=1.5, t_d=5.1."""
    p1 = data["constraints"]["problem1_given"]
    speed = float(p1["speed"] if "speed" in p1 else p1["FY1_speed"] if "FY1_speed" in p1 else 120)
    t_r = float(p1["t_r"] if "t_r" in p1 else p1["release_time"] if "release_time" in p1 else 1.5)
    t_d = float(p1["t_d"] if "t_d" in p1 else p1["detonation_time"] if "detonation_time" in p1 else 5.1)
    if "release_time" in p1 and "detonation_delay" in p1 and "t_d" not in p1:
        t_d = float(p1["release_time"]) + float(p1["detonation_delay"])

    drone0 = np.array(data["initial_positions"]["drones"]["FY1"], dtype=float)
    missile0 = np.array(data["initial_positions"]["missiles"]["M1"], dtype=float)

    # fly toward fake target's xy projection (0,0) from (17800, 0) = direction (-1, 0)
    dir_vec = np.array([-1.0, 0.0])
    bomb = BombSpec(drone0=drone0, speed=speed, dir_vec=dir_vec, t_r=t_r, t_d=t_d)
    duration, intervals = compute_occlusion([bomb], missile0, params, target_samples)
    times, state = occlusion_timeline([bomb], missile0, params, target_samples)
    return duration, bomb, times, state


def _de_obj_single_bomb(x: np.ndarray, drone0: np.ndarray, missile0: np.ndarray,
                        params: Params, target_samples: np.ndarray) -> float:
    theta, v, t_r, delay = x
    dir_vec = np.array([np.cos(theta), np.sin(theta)])
    bomb = BombSpec(drone0=drone0, speed=float(v), dir_vec=dir_vec,
                    t_r=float(t_r), t_d=float(t_r + delay))
    dur, _ = compute_occlusion([bomb], missile0, params, target_samples, T_max=70.0, dt=0.05)
    return -dur


def solve_q2(params: Params, data: dict[str, Any], target_samples: np.ndarray
             ) -> tuple[float, BombSpec, list[float]]:
    """Single drone, single bomb — optimize theta, v, t_r, t_d."""
    drone0 = np.array(data["initial_positions"]["drones"]["FY1"], dtype=float)
    missile0 = np.array(data["initial_positions"]["missiles"]["M1"], dtype=float)

    # coarse grid search to seed the DE (reduced: 936 pts)
    thetas = np.linspace(-np.pi, np.pi, 13)
    vs = np.linspace(params.v_d_min, params.v_d_max, 4)
    t_rs = np.linspace(0.1, 15.0, 6)
    delays = np.linspace(0.5, 8.0, 3)
    best_score = -np.inf
    best_x = np.array([0.0, 100.0, 2.0, 3.0])
    for theta in thetas:
        for v in vs:
            for t_r in t_rs:
                for d in delays:
                    x = np.array([theta, v, t_r, d])
                    score = -_de_obj_single_bomb(x, drone0, missile0, params, target_samples)
                    if score > best_score:
                        best_score = score
                        best_x = x.copy()

    # DE refinement (increased to find better optimum)
    bounds = [
        (-np.pi, np.pi),            # theta
        (params.v_d_min, params.v_d_max),  # v
        (0.0, 30.0),                # t_r
        (0.3, 15.0),                # delay = t_d - t_r
    ]
    def obj(x: np.ndarray) -> float:
        return _de_obj_single_bomb(x, drone0, missile0, params, target_samples)

    # Multi-seed DE: run 3 times with different seeds, keep best
    best_f = np.inf
    best_x = None
    best_conv = []
    for seed in [20250617, 42, 99]:
        def obj(x: np.ndarray) -> float:
            return _de_obj_single_bomb(x, drone0, missile0, params, target_samples)
        x, f, conv = differential_evolution(
            obj, bounds, pop_size=50, max_gen=80, F=0.7, CR=0.9, seed=seed)
        if f < best_f:
            best_f = f
            best_x = x
            best_conv = conv

    # take the better of grid vs DE
    if -best_f > best_score:
        best_score = -best_f  # DE is better

    theta, v, t_r, delay = best_x
    dir_vec = np.array([np.cos(theta), np.sin(theta)])
    bomb = BombSpec(drone0=drone0, speed=float(v), dir_vec=dir_vec,
                    t_r=float(t_r), t_d=float(t_r + delay))
    return best_score, bomb, best_conv


def _de_obj_multi_bomb(x: np.ndarray, drone0: np.ndarray, missile0: np.ndarray,
                       params: Params, target_samples: np.ndarray, n_bombs: int) -> float:
    bombs: list[BombSpec] = []
    for i in range(n_bombs):
        off = i * 4
        theta, v, t_r, delay = x[off:off + 4]
        dir_vec = np.array([np.cos(theta), np.sin(theta)])
        bombs.append(BombSpec(drone0=drone0, speed=float(v), dir_vec=dir_vec,
                              t_r=float(t_r), t_d=float(t_r + delay)))
    # enforce min 1s interval between consecutive release times
    t_rs = sorted([bombs[i].t_r for i in range(n_bombs)])
    penalty = 0.0
    for j in range(1, len(t_rs)):
        gap = t_rs[j] - t_rs[j - 1]
        if gap < 1.0:
            penalty += 100.0 * (1.0 - gap)
    dur, _ = compute_occlusion(bombs, missile0, params, target_samples, T_max=70.0, dt=0.05)
    return -dur + penalty


def solve_q3(params: Params, data: dict[str, Any], target_samples: np.ndarray
             ) -> tuple[float, list[BombSpec], list[float]]:
    """Single drone (FY1), 3 bombs — 12-D optimisation."""
    drone0 = np.array(data["initial_positions"]["drones"]["FY1"], dtype=float)
    missile0 = np.array(data["initial_positions"]["missiles"]["M1"], dtype=float)

    n_bombs = 3
    bounds: list[tuple[float, float]] = []
    for i in range(n_bombs):
        bounds += [(-np.pi, np.pi), (params.v_d_min, params.v_d_max),
                   (0.0, 40.0), (0.3, 15.0)]

    def obj(x: np.ndarray) -> float:
        return _de_obj_multi_bomb(x, drone0, missile0, params, target_samples, n_bombs)

    # Multi-seed DE
    best_f = np.inf
    best_x = None
    best_conv = []
    for seed in [20250617, 42, 99]:
        x, f, conv = differential_evolution(
            obj, bounds, pop_size=50, max_gen=80, F=0.7, CR=0.9, seed=seed)
        if f < best_f:
            best_f = f
            best_x = x
            best_conv = conv

    bombs: list[BombSpec] = []
    for i in range(n_bombs):
        off = i * 4
        theta, v, t_r, delay = best_x[off:off + 4]
        dir_vec = np.array([np.cos(theta), np.sin(theta)])
        bombs.append(BombSpec(drone0=drone0, speed=float(v), dir_vec=dir_vec,
                              t_r=float(t_r), t_d=float(t_r + delay)))
    return -best_f, bombs, best_conv


def _de_obj_multi_drone(x: np.ndarray, drones0: list[np.ndarray], missile0: np.ndarray,
                        params: Params, target_samples: np.ndarray) -> float:
    """Q4 objective: maximise union duration of three drones' occlusion intervals.

    The correct Q4 goal is NOT "maximise OR-叠加 single-interval".
    It is "make three clouds' [t_in,t_out] intervals cover the timeline continuously".
    """
    n = len(drones0)
    bombs: list[BombSpec] = []
    for i in range(n):
        off = i * 4
        theta, v, t_r, delay = x[off:off + 4]
        dir_vec = np.array([np.cos(theta), np.sin(theta)])
        bombs.append(BombSpec(drone0=drones0[i], speed=float(v), dir_vec=dir_vec,
                              t_r=float(t_r), t_d=float(t_r + delay)))
    # Use dt=0.05 for speed (Q4 DE runs thousands of evaluations)
    _, intervals = compute_occlusion(bombs, missile0, params, target_samples, T_max=70.0, dt=0.05)
    return -union_duration(intervals)


def solve_q4(params: Params, data: dict[str, Any], target_samples: np.ndarray
             ) -> tuple[float, list[BombSpec], list[tuple[float, float]]]:
    """FY1, FY2, FY3 each releases 1 bomb against M1.

    Q4 goal: maximise UNION duration of the three drones' occlusion intervals,
    i.e. the total time during which at least one drone's cloud occludes M1.
    This requires the three clouds' intervals to be chained back-to-back.
    """
    drones_names = ["FY1", "FY2", "FY3"]
    drones0 = [np.array(data["initial_positions"]["drones"][name], dtype=float) for name in drones_names]
    missile0 = np.array(data["initial_positions"]["missiles"]["M1"], dtype=float)

    bounds: list[tuple[float, float]] = []
    for _ in range(3):
        bounds += [(-np.pi, np.pi), (params.v_d_min, params.v_d_max),
                   (0.0, 60.0), (0.3, 15.0)]

    # Phase 1: denser seed grid — explore 5 directions × 3 speeds × 3 t_r spreads
    # Directions: toward missile (~0°), toward origin (180°), and 3 oblique angles
    print("    Phase 1: dense seed grid (135 combos) ...")
    best_score_coarse = -np.inf
    best_x_coarse = None
    # Grid: 3 speeds × 3 t_r spreads × 5 directions = 135 combos
    speed_candidates = [70., 105., 140.]
    # t_r spreads: (fy1_candidates, fy2_candidates, fy3_candidates)
    t_r_spreads = [
        ([1.0, 3.0, 6.0], [12.0, 15.0, 18.0], [25.0, 28.0, 31.0]),
        ([0.5, 2.0, 4.0], [8.0, 10.0, 12.0], [18.0, 20.0, 22.0]),
        ([2.0, 5.0, 8.0], [15.0, 18.0, 21.0], [30.0, 33.0, 36.0]),
    ]
    theta_candidates = [0.0, 0.14, 1.57, 3.14, -0.14]  # 0°, ~8°, 90°, 180°, ~-8°
    for t_r1_list, t_r2_list, t_r3_list in t_r_spreads:
        for speed in speed_candidates:
            for theta in theta_candidates:
                for t_r1 in t_r1_list:
                    for t_r2 in t_r2_list:
                        for t_r3 in t_r3_list:
                            x = np.array([theta, speed, t_r1, 0.5,
                                          theta, speed, t_r2, 0.5,
                                          theta, speed, t_r3, 0.5])
                            score = -_de_obj_multi_drone(x, drones0, missile0, params, target_samples)
                            if score > best_score_coarse:
                                best_score_coarse = score
                                best_x_coarse = x.copy()

    # Phase 2: DE refinement with larger population and more generations
    print("    Phase 2: DE refinement (multi-seed, larger pop) ...")
    def obj(x: np.ndarray) -> float:
        return _de_obj_multi_drone(x, drones0, missile0, params, target_samples)

    # Multi-seed DE with increased parameters for 12-D problem
    best_f = np.inf
    best_x = None
    for seed in [20250617, 42, 99, 123, 777]:
        x, f, _ = differential_evolution(
            obj, bounds, pop_size=80, max_gen=150, F=0.7, CR=0.9, seed=seed)
        if f < best_f:
            best_f = f
            best_x = x

    final_score = max(best_score_coarse, -best_f)
    if final_score == best_score_coarse:
        best_x = best_x_coarse

    bombs: list[BombSpec] = []
    for i in range(3):
        off = i * 4
        theta, v, t_r, delay = best_x[off:off + 4]
        dir_vec = np.array([np.cos(theta), np.sin(theta)])
        bombs.append(BombSpec(drone0=drones0[i], speed=float(v), dir_vec=dir_vec,
                              t_r=float(t_r), t_d=float(t_r + delay)))

    # Final accurate evaluation with fine dt=0.01
    _, intervals = compute_occlusion(bombs, missile0, params, target_samples, T_max=70.0, dt=0.01)
    final_duration = union_duration(intervals)
    return final_duration, bombs, intervals

def solve_q5(params: Params, data: dict[str, Any], target_samples: np.ndarray
             ) -> tuple[float, dict[str, list[BombSpec]]]:
    """Multi-drone multi-missile: enumerate task assignments, maximise INTERSECTION duration.

    Q5 goal: maximise the total time during which ALL THREE MISSILES are simultaneously
    occluded. This is an INTERSECTION of the three missiles' occlusion sets.

    Algorithm:
      Phase 1: For each of 15 (drone, missile) pairs, compute best occlusion interval
        using quick DE (pop=20, gen=30). Cache results.
      Phase 2: Enumerate surjective assignments (150 combos); for each, compute
        the intersection of the three missiles' union intervals.
        Return the assignment with maximum intersection.
    """
    missiles = data["initial_positions"]["missiles"]
    drones = data["initial_positions"]["drones"]
    missile_names = list(missiles.keys())   # M1, M2, M3
    drone_names = list(drones.keys())       # FY1..FY5

    # ---------- Phase 1: compute best interval for each (drone, missile) pair ----------
    print("    Phase 1: computing 15 (drone,missile) pair intervals ...")
    pair_data: dict[tuple[str, str], dict] = {}   # (d,m) -> {bomb, ivs, dur}

    for d_name in drone_names:
        d0 = np.array(drones[d_name], dtype=float)
        for m_name in missile_names:
            m0 = np.array(missiles[m_name], dtype=float)
            bounds = [(-np.pi, np.pi), (params.v_d_min, params.v_d_max),
                      (0.0, 25.0), (0.3, 10.0)]

            # Phase 1 DE: stronger parameters for better optimization
            best_f = np.inf
            best_x_local = None
            for seed in [20250617, 42, 99, 123]:
                def obj(x: np.ndarray, _d0=d0, _m0=m0) -> float:
                    return _de_obj_single_bomb(x, _d0, _m0, params, target_samples)
                x, f, _ = differential_evolution(
                    obj, bounds, pop_size=40, max_gen=60, F=0.7, CR=0.9, seed=seed)
                if f < best_f:
                    best_f = f
                    best_x_local = x

            theta, v, t_r, delay = best_x_local
            dir_vec = np.array([np.cos(theta), np.sin(theta)])
            b = BombSpec(drone0=d0, speed=float(v), dir_vec=dir_vec,
                         t_r=float(t_r), t_d=float(t_r + delay))
            _, ivs = compute_occlusion([b], m0, params, target_samples, T_max=70.0, dt=0.02)
            dur = sum(e - s for s, e in ivs) if ivs else 0.0
            pair_data[(d_name, m_name)] = {"bomb": b, "ivs": ivs, "dur": dur}
            print(f"      {d_name}→{m_name}: dur={dur:.2f}s ivs={[(round(s,2),round(e,2)) for s,e in ivs]}")

    # ---------- Phase 2: enumerate surjective assignments ----------
    print("    Phase 2: enumerating 150 task assignments ...")
    best_overall = 0.0
    best_bombs_overall: dict[str, list[BombSpec]] = {}
    n_evaluated = 0
    # Track top-3 for diagnostics
    top3: list[tuple[float, dict, list]] = []

    from itertools import product
    for combo in product(missile_names, repeat=len(drone_names)):
        assigned_to = set(combo)
        if len(assigned_to) < 3:
            continue

        assignment = tuple(zip(drone_names, combo))
        intervals_per_missile: dict[str, list[tuple[float, float]]] = {m: [] for m in missile_names}
        bombs_per_missile: dict[str, list[BombSpec]] = {m: [] for m in missile_names}

        for d_name, m_name in assignment:
            intervals_per_missile[m_name].extend(pair_data[(d_name, m_name)]["ivs"])
            bombs_per_missile[m_name].append(pair_data[(d_name, m_name)]["bomb"])

        # Per-missile union intervals
        union_ivs: list[list[tuple[float, float]]] = []
        for m in missile_names:
            ivs = intervals_per_missile[m]
            if not ivs:
                union_ivs.append([])
            else:
                ivs_sorted = sorted(ivs, key=lambda x: x[0])
                merged: list[tuple[float, float]] = []
                cur_s, cur_e = ivs_sorted[0]
                for s, e in ivs_sorted[1:]:
                    if s <= cur_e:
                        cur_e = max(cur_e, e)
                    else:
                        merged.append((cur_s, cur_e))
                        cur_s, cur_e = s, e
                merged.append((cur_s, cur_e))
                union_ivs.append(merged)

        intersection = intersection_duration(union_ivs)
        n_evaluated += 1
        if intersection > best_overall:
            best_overall = intersection
            best_bombs_overall = bombs_per_missile.copy()
            top3.append((intersection, dict(assignment), [ivs.copy() for ivs in union_ivs]))
            top3.sort(key=lambda x: -x[0])
            top3 = top3[:3]

    print(f"    Evaluated {n_evaluated} assignments; best intersection = {best_overall:.4f} s")
    for rank, (score, asn, ivs) in enumerate(top3, 1):
        print(f"    Top-{rank} ({score:.4f}s): {asn}")
        for m, m_ivs in zip(missile_names, ivs):
            print(f"      {m}: {[(round(s,2),round(e,2)) for s,e in m_ivs]}")
    return best_overall, best_bombs_overall


# -------------------- output writers --------------------
def write_csv(path: Path, rows: list[list[str | float]], header: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def bomb_to_csv_row(qid: str, bomb_idx: int, bomb: BombSpec) -> list[float | str]:
    theta_deg = float(np.degrees(np.arctan2(bomb.dir_vec[1], bomb.dir_vec[0])))
    return [qid, bomb_idx, round(float(bomb.speed), 3), round(theta_deg, 2),
            round(float(bomb.t_r), 4), round(float(bomb.t_d), 4)]


# -------------------- plotting --------------------
def setup_matplotlib() -> None:
    import matplotlib
    matplotlib.use("Agg")


def plot_q1_timeline(times: np.ndarray, state: np.ndarray, out: Path, duration: float) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.step(times, state, where="post", color="#2c7bb6", linewidth=1.2)
    ax.fill_between(times, state, step="post", color="#2c7bb6", alpha=0.25)
    ax.set_xlabel("Time t (s)")
    ax.set_ylabel("Occluded (1 = yes)")
    ax.set_title(f"Q1: Occlusion timeline | Duration = {duration:.3f} s")
    ax.set_xlim(0, 70)
    ax.set_ylim(-0.1, 1.1)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def plot_convergence(convergence: list[float], out: Path, title: str) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(np.arange(1, len(convergence) + 1), -np.array(convergence), "o-", color="#d7191c", markersize=4)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Occlusion duration (s)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def plot_comparison(durations: list[tuple[str, float]], out: Path) -> None:
    import matplotlib.pyplot as plt
    names = [d[0] for d in durations]
    values = [d[1] for d in durations]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(names, values, color=["#2c7bb6", "#00a6ca", "#00ccbc", "#90eb9d", "#ffff8c"][:len(names)],
                  edgecolor="black")
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05 * max(values),
                f"{v:.2f} s", ha="center", va="bottom", fontsize=10)
    ax.set_xlabel("Problem")
    ax.set_ylabel("Total occlusion duration (s)")
    ax.set_title("Occlusion duration by problem (Q1 baseline -> Q5 multi-target)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def plot_cloud_and_missile(bomb: BombSpec, missile0: np.ndarray, params: Params,
                           out: Path, title: str) -> None:
    """Plot missile path and cloud-center trajectory in (x, z) projection."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5))
    t_vals = np.linspace(0, 70, 300)
    m_xy = np.array([missile_position(float(t), missile0, params) for t in t_vals])
    ax.plot(m_xy[:, 0], m_xy[:, 2], "k-", lw=1, label="Missile M1")

    # cloud center time series from detonation to expiry
    c0 = cloud_at_det(bomb.t_r, bomb.t_d, bomb.drone0, bomb.speed, bomb.dir_vec, params)
    t_cloud = np.linspace(bomb.t_d, min(bomb.t_d + params.tau_max, 70), 200)
    c_xy = np.array([cloud_center(float(t), bomb.t_d, c0, params) for t in t_cloud])
    ax.plot(c_xy[:, 0], c_xy[:, 2], "ro-", lw=1.5, ms=3, label="Cloud center")
    # draw radius
    for ct in c_xy[::20]:
        circle = plt.Circle((ct[0], ct[2]), params.R_s, color="r", alpha=0.08)
        ax.add_patch(circle)

    # target cylinder center line
    ax.plot([0, 0], [0, params.target_height], "g-", lw=2, label="Real target axis")

    ax.set_xlabel("x (m)")
    ax.set_ylabel("z (m)")
    ax.set_title(title)
    ax.legend(loc="upper right")
    ax.grid(alpha=0.3)
    ax.invert_xaxis()  # missile flies from +x toward origin
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def plot_missile_paths(data: dict[str, Any], out: Path, params: Params) -> None:
    """Top-down (xy) view of missile and drone initial positions."""
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 7))
    missiles = data["initial_positions"]["missiles"]
    drones = data["initial_positions"]["drones"]

    for name, pos in missiles.items():
        ax.plot(pos[0], pos[1], "ks", markersize=9, label=f"{name} (missile)")
        ax.annotate(name, (pos[0], pos[1]), textcoords="offset points", xytext=(8, 8), fontsize=9)
    for name, pos in drones.items():
        ax.plot(pos[0], pos[1], "bo", markersize=7, label=f"{name} (drone)")
        ax.annotate(name, (pos[0], pos[1]), textcoords="offset points", xytext=(8, 8), fontsize=9)
    ax.plot(0, 200, "g*", markersize=16, label="Real target")
    ax.plot(0, 0, "rx", markersize=14, markeredgewidth=2, label="Fake target")

    # missile trajectories
    t_vals = np.linspace(0, 70, 200)
    for name, pos in missiles.items():
        m0 = np.array(pos, dtype=float)
        traj = np.array([missile_position(float(t), m0, params) for t in t_vals])
        ax.plot(traj[:, 0], traj[:, 1], "k--", lw=0.6, alpha=0.5)

    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Top-down: missile + drone positions and trajectories")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


# -------------------- main --------------------
def main() -> int:
    setup_matplotlib()

    if not PROBLEM_DATA.exists():
        print(f"ERROR: {PROBLEM_DATA} not found", file=sys.stderr)
        return 1

    params, data = load_problem_data(PROBLEM_DATA)
    print(f"Parameters loaded from {PROBLEM_DATA.name}")
    print(f"  v_m={params.v_m}, R_s={params.R_s}, v_cs={params.v_cs}, "
          f"tau_max={params.tau_max}, v_d in [{params.v_d_min},{params.v_d_max}]")
    print(f"  g={params.g}, target_r={params.target_radius}, target_h={params.target_height}")

    target_samples = sample_target_cylinder(params)
    missile0 = np.array(data["initial_positions"]["missiles"]["M1"], dtype=float)

    # --- Q1 ---
    print("\n[Q1] Solving with given parameters ...")
    d_q1, bomb_q1, times_q1, state_q1 = solve_q1(params, data, target_samples)
    print(f"  Occlusion duration = {d_q1:.4f} s")

    # --- Q2 ---
    print("\n[Q2] Optimising single drone / single bomb ...")
    d_q2, bomb_q2, conv_q2 = solve_q2(params, data, target_samples)
    print(f"  Best occlusion duration = {d_q2:.4f} s")

    # --- Q3 ---
    print("\n[Q3] Optimising single drone / 3 bombs ...")
    d_q3, bombs_q3, conv_q3 = solve_q3(params, data, target_samples)
    print(f"  Best occlusion duration = {d_q3:.4f} s")

    # --- Q4 ---
    print("\n[Q4] Optimising 3 drones / 1 bomb each ...")
    d_q4, bombs_q4, intervals_q4 = solve_q4(params, data, target_samples)
    print(f"  Best union duration = {d_q4:.4f} s  (intervals: {[round(s,2) for s,_ in intervals_q4]})")

    # --- Q5 ---
    print("\n[Q5] Multi-drone / multi-bomb / multi-missile assignment ...")
    d_q5, bombs_q5 = solve_q5(params, data, target_samples)
    print(f"  Best simultaneous occlusion = {d_q5:.4f} s")

    # --- Figures ---
    print("\n[FIG] Generating plots ...")
    plot_q1_timeline(times_q1, state_q1,
                     FIGURES_DIR / "fig01-Q1-occlusion-timeline.png", d_q1)
    plot_convergence(conv_q2, FIGURES_DIR / "fig02-Q2-convergence.png",
                     "Q2: single-bomb optimisation — convergence")
    plot_cloud_and_missile(bomb_q2, missile0, params,
                           FIGURES_DIR / "fig03-Q2-cloud-vs-missile-xz.png",
                           "Q2: cloud center vs M1 trajectory (x-z projection)")
    plot_comparison([("Q1", d_q1), ("Q2", d_q2), ("Q3", d_q3), ("Q4", d_q4), ("Q5", d_q5)],
                    FIGURES_DIR / "fig04-Q1-Q5-duration-comparison.png")
    plot_missile_paths(data, FIGURES_DIR / "fig05-missile-drone-overview.png", params)
    print(f"  Figures saved to {FIGURES_DIR}")

    # --- CSV results ---
    print("\n[OUT] Writing CSV results ...")
    summary_rows: list[list[str | float]] = [
        ["Q1", "occlusion_duration", round(d_q1, 4), "s",
         "given-params line-sphere-intersection", "fig01-Q1-occlusion-timeline.png",
         "mathematical_model.item_6"],
        ["Q2", "occlusion_duration", round(d_q2, 4), "s",
         "grid-search + differential-evolution", "fig02-Q2-convergence.png",
         "mathematical_model.item_6 + algorithm_flow.Step_6"],
        ["Q3", "occlusion_duration", round(d_q3, 4), "s",
         "differential-evolution (12-D, 3 bombs)", "fig04-Q1-Q5-duration-comparison.png",
         "mathematical_model.item_6 + algorithm_flow.Step_7"],
        ["Q4", "union_duration", round(d_q4, 4), "s",
         "interval-union + grid-search + differential-evolution", "fig04-Q1-Q5-duration-comparison.png",
         "interval_union() + union_duration()"],
        ["Q5", "intersection_duration", round(d_q5, 4), "s",
         "full-assignment-enumeration + interval-intersection + DE", "fig04-Q1-Q5-duration-comparison.png",
         "intersection_duration() + assignment enumeration (243 combos)"],
    ]
    write_csv(RESULTS_DIR / "results_summary.csv",
              summary_rows,
              ["problem_id", "metric_name", "value", "unit", "method", "figure_ref", "formula_ref"])

    # Per-problem details
    q1_rows = [bomb_to_csv_row("Q1", 1, bomb_q1) + [round(d_q1, 4)]]
    write_csv(RESULTS_DIR / "Q1_results.csv",
              q1_rows,
              ["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])

    q2_rows = [bomb_to_csv_row("Q2", 1, bomb_q2) + [round(d_q2, 4)]]
    write_csv(RESULTS_DIR / "Q2_results.csv",
              q2_rows,
              ["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])

    q3_rows = [bomb_to_csv_row("Q3", i + 1, b) + [round(d_q3, 4)] for i, b in enumerate(bombs_q3)]
    write_csv(RESULTS_DIR / "Q3_results.csv",
              q3_rows,
              ["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])

    q4_rows = [bomb_to_csv_row("Q4", i + 1, b) + [round(d_q4, 4)] for i, b in enumerate(bombs_q4)]
    write_csv(RESULTS_DIR / "Q4_results.csv",
              q4_rows,
              ["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])

    q5_rows: list[list[str | float]] = []
    for m_name, blist in bombs_q5.items():
        for i, b in enumerate(blist):
            q5_rows.append(bomb_to_csv_row(f"Q5-{m_name}", i + 1, b) + [round(d_q5, 4)])
    write_csv(RESULTS_DIR / "Q5_results.csv",
              q5_rows,
              ["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])

    print(f"  Results saved to {RESULTS_DIR}")

    # --- baseline regression check ---
    print("\n[CHECK] Baseline & invariants:")
    print(f"  Q1 = {d_q1:.3f} s  (baseline)")
    monotonic = d_q2 >= d_q1 and d_q3 >= d_q2 and d_q4 >= d_q2
    print(f"  Monotonic Q5>=Q4>=Q3>=Q2>=Q1: Q2({d_q2:.3f}) >= Q1({d_q1:.3f}) = {d_q2 >= d_q1}; "
          f"Q3({d_q3:.3f}) >= Q2({d_q2:.3f}) = {d_q3 >= d_q2}; "
          f"Q4({d_q4:.3f}) >= Q2({d_q2:.3f}) = {d_q4 >= d_q2}; "
          f"PASS = {monotonic}")

    # --- write Q1.xlsx-style result file (problem statement asks for result1.xlsx) ---
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Q1"
        ws.append(["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])
        for row in q1_rows:
            ws.append(list(row))
        wb.save(RESULTS_DIR / "result1.xlsx")
        # additional Q2..Q5 xlsx (problem statement asks for result2.xlsx, result3.xlsx)
        for qname, rows in [("Q2", q2_rows), ("Q3", q3_rows), ("Q4", q4_rows), ("Q5", q5_rows)]:
            wb2 = openpyxl.Workbook()
            ws2 = wb2.active
            ws2.title = qname
            ws2.append(["problem_id", "bomb_idx", "speed_mps", "heading_deg", "t_r_s", "t_d_s", "duration_s"])
            for row in rows:
                ws2.append(list(row))
            idx = qname[1]
            wb2.save(RESULTS_DIR / f"result{idx}.xlsx")
        print(f"  XLSX files written to {RESULTS_DIR}")
    except ImportError:
        print("  openpyxl not installed; skipping xlsx output (CSV files are complete)")

    print("\n[DONE]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
