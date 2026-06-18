"""
Module: 2025 MCM Problem A — UAV Smoke Screen Strategy Optimization
Description: Complete solver for all 5 sub-problems using geometric occlusion
             detection, grid search, Nelder-Mead, and Differential Evolution.
Author: Coding Expert Agent
Date: 2026-06-01

本次已主动避免 ERR-003 (ambiguous_algorithm) — 所有算法步骤完全按 model_design 实现
本次已主动避免 ERR-004 (计算可行性) — 使用 numpy 向量化 + 早期终止控制计算量
本次已主动避免 ERR-005 (模型定义矛盾) — 目标函数严格使用几何模拟结果
"""

import numpy as np
from scipy.optimize import minimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
import pandas as pd
import time
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 全局常量 (硬编码，来源于赛题和 problem_data.json)
# ============================================================
np.random.seed(42)

# 物理常量
G = 9.8            # 重力加速度 m/s^2
V_SINK = 3.0       # 云团下沉速度 m/s
R_S = 10.0         # 云团有效遮蔽半径 m
T_C = 20.0         # 云团有效遮蔽持续时间 s
V_M = 300.0        # 导弹速度 m/s

# 目标圆柱参数
R_T = 7.0          # 圆柱底面半径 m
H_T = 10.0         # 圆柱高度 m
REAL_TARGET_CENTER = np.array([0.0, 200.0, 0.0])  # 真目标下底面圆心

# 假目标 (导弹飞行目标)
DECOY_TARGET = np.array([0.0, 0.0, 0.0])

# 无人机速度范围
V_U_MIN = 70.0
V_U_MAX = 140.0

# 最小投弹间隔
MIN_BOMB_INTERVAL = 1.0

# 导弹初始位置
M_POSITIONS = {
    1: np.array([20000.0, 0.0, 2000.0]),
    2: np.array([19000.0, 600.0, 2100.0]),
    3: np.array([18000.0, -600.0, 1900.0]),
}

# 无人机初始位置
U_POSITIONS = {
    1: np.array([17800.0, 0.0, 1800.0]),      # FY1
    2: np.array([12000.0, 1400.0, 1400.0]),    # FY2
    3: np.array([6000.0, -3000.0, 700.0]),     # FY3
    4: np.array([11000.0, 2000.0, 1800.0]),    # FY4
    5: np.array([13000.0, -2000.0, 1300.0]),   # FY5
}

# Q1 给定参数
Q1_THETA = np.pi       # 航向角 (朝向假目标，即-x方向)
Q1_V = 120.0           # 无人机速度 m/s
Q1_T_D = 1.5           # 投放时刻 s
Q1_T_B = 5.1           # 起爆时刻 s

# 圆周离散采样点数
N_PHI = 300

# 时间扫描参数
DT_COARSE = 0.05       # 粗扫描时间步长 s
EPS_BISECTION = 1e-3   # 二分查找精度 s


# ============================================================
# 预计算: 目标圆柱表面采样点 (600个点: 下底面300 + 上底面300)
# ============================================================
def generate_target_surface_points():
    """生成目标圆柱上下底面圆周的离散采样点"""
    phi = np.linspace(0, 2 * np.pi, N_PHI, endpoint=False)
    cos_phi = np.cos(phi)
    sin_phi = np.sin(phi)

    # 下底面圆周点: (r_t*cos(phi), 200 + r_t*sin(phi), 0)
    bottom = np.column_stack([
        R_T * cos_phi,
        200.0 + R_T * sin_phi,
        np.zeros(N_PHI)
    ])

    # 上底面圆周点: (r_t*cos(phi), 200 + r_t*sin(phi), H_t)
    top = np.column_stack([
        R_T * cos_phi,
        200.0 + R_T * sin_phi,
        np.full(N_PHI, H_T)
    ])

    # 合并为 (600, 3)
    all_points = np.vstack([bottom, top])
    return all_points, bottom, top


# 全局预计算
TARGET_POINTS_ALL, TARGET_POINTS_BOTTOM, TARGET_POINTS_TOP = generate_target_surface_points()
N_TARGET_POINTS = len(TARGET_POINTS_ALL)  # 600

# 导弹飞行方向单位向量 (指向假目标原点)
M_DIRECTIONS = {}
for i, pos in M_POSITIONS.items():
    norm = np.linalg.norm(pos)
    M_DIRECTIONS[i] = -pos / norm  # 指向原点

# 导弹飞行时间上界 (到达目标区)
M_FLIGHT_TIMES = {}
for i, pos in M_POSITIONS.items():
    M_FLIGHT_TIMES[i] = np.linalg.norm(pos) / V_M


# ============================================================
# 核心几何函数: 线段-球体相交判定 (向量化)
# ============================================================
def segment_sphere_intersection_vectorized(M, T_points, C, R):
    """
    向量化线段-球体相交判定。
    检查从导弹位置 M 到所有目标点 T_points 的线段是否都与球 C(R) 相交。

    参数:
        M: 导弹位置 (3,) 或 scalar 可广播
        T_points: 目标点矩阵 (N, 3)
        C: 球心位置 (3,)
        R: 球半径

    返回:
        bool: 所有线段是否都与球相交
    """
    d_vec = T_points - M  # (N, 3) — 线段方向向量
    v_vec = M - C         # (3,) — 导弹到球心的向量

    # 二次方程系数: a*s^2 + b*s + c = 0
    a = np.sum(d_vec * d_vec, axis=1)  # (N,)
    b = 2.0 * np.dot(d_vec, v_vec)    # (N,)
    c_scalar = np.dot(v_vec, v_vec) - R * R  # scalar

    # 处理退化情况 (M ≈ T，间距极小)
    degenerate_mask = a < 1e-12
    # 退化时：点M就在T附近，只需检查该点是否在球内
    if np.any(degenerate_mask):
        # 点M在球内当 c_scalar <= 0
        # 这里简化：若M≈T且c_scalar<=0则退化点被遮挡
        pass

    # 判别式
    delta = b * b - 4.0 * a * c_scalar  # (N,)

    # 有实根
    has_real_roots = delta >= 0

    # 若没有实根 → 不相交
    if not np.any(has_real_roots):
        return False

    # 计算根
    sqrt_delta = np.sqrt(np.maximum(delta, 0))
    s1 = (-b - sqrt_delta) / (2.0 * a)
    s2 = (-b + sqrt_delta) / (2.0 * a)

    # 遮挡条件：至少一个根在[0, 1]区间内
    # 或者 s1 < 0 且 s2 > 1 (线段完全在球内)
    intersects = has_real_roots & (
        ((s1 <= 1.0) & (s2 >= 0.0))
    )

    # 额外检查：c_scalar <= 0 表示导弹在球内 → 所有方向都被遮挡
    if c_scalar <= 0:
        return True

    # 额外检查：目标点在球内
    # 对于每个目标点 T，若 |T-C|^2 <= R^2，则该点被遮挡
    t_to_c = np.sum((T_points - C) ** 2, axis=1)
    points_in_sphere = t_to_c <= R * R

    # 合并判定
    intersects = intersects | points_in_sphere

    # 所有点都必须被遮挡
    # 早期终止：一旦发现任何点未被遮挡，立即返回 False
    return bool(np.all(intersects))


def _check_batch_occlusion(batch, M, C, R, c_scalar):
    """
    Check if ALL points in a batch are occluded by the sphere.
    Returns True only if every single point is occluded.
    Handles edge cases: missile in sphere, degenerate segments, points in sphere.
    """
    d_vec = batch - M
    v_vec = M - C
    a = np.sum(d_vec * d_vec, axis=1)
    b = 2.0 * np.dot(d_vec, v_vec)

    # Handle degenerate segments (a ≈ 0, i.e., M very close to T)
    deg = a < 1e-12
    a_safe = np.where(deg, 1.0, a)

    delta = b * b - 4.0 * a_safe * c_scalar
    has_roots = delta >= 0

    # For degenerate points: if M≈T and c_scalar<=0 (M in sphere), point is occluded
    # Otherwise if M≈T and c_scalar>0, M and T are the same point outside sphere → not occluded
    deg_occluded = deg & (c_scalar <= 0.0)

    if not np.all(has_roots | deg_occluded):
        return False

    sqrt_d = np.sqrt(np.maximum(delta, 0))
    s1 = np.where(deg, 0.0, (-b - sqrt_d) / (2.0 * a_safe))
    s2 = np.where(deg, 0.0, (-b + sqrt_d) / (2.0 * a_safe))

    intersects = (
        deg_occluded |
        (has_roots & ((s1 <= 1.0) & (s2 >= 0.0)))
    )

    # Also check if target point itself is inside the sphere
    t_to_c_sq = np.sum((batch - C) ** 2, axis=1)
    points_in_sphere = t_to_c_sq <= R * R
    intersects = intersects | points_in_sphere

    if not np.all(intersects):
        return False

    return True


def segment_sphere_intersection_early_terminate(M, T_points_all, C, R):
    """
    带早期终止的向量化遮挡检查。
    分批检查上下底面，一旦发现任何未遮挡点立即返回 False。
    这比一次性检查全部 600 个点更快（大多数情况下云团不遮挡）。
    """
    v_vec = M - C
    c_scalar = np.dot(v_vec, v_vec) - R * R

    # 快速检查：若导弹在球内，所有视线都被遮挡
    if c_scalar <= 0.0:
        return True

    # 分批检查下底面 (300点)
    for start in range(0, N_PHI, 100):
        end = min(start + 100, N_PHI)
        batch = TARGET_POINTS_BOTTOM[start:end]
        if not _check_batch_occlusion(batch, M, C, R, c_scalar):
            return False

    # 分批检查上底面 (300点)
    for start in range(0, N_PHI, 100):
        end = min(start + 100, N_PHI)
        batch = TARGET_POINTS_TOP[start:end]
        if not _check_batch_occlusion(batch, M, C, R, c_scalar):
            return False

    return True


def check_full_occlusion(missile_pos, cloud_center, cloud_radius):
    """
    检查云团是否完全遮蔽目标（对所有 600 个表面点）。

    参数:
        missile_pos: 导弹位置 (3,)
        cloud_center: 云团中心 (3,)
        cloud_radius: 云团半径 (scalar)

    返回:
        bool: 是否完全遮蔽
    """
    return segment_sphere_intersection_early_terminate(
        missile_pos, TARGET_POINTS_ALL, cloud_center, cloud_radius
    )


# ============================================================
# 运动学模型
# ============================================================
def missile_position(missile_id, t):
    """计算导弹在时刻 t 的位置"""
    M0 = M_POSITIONS[missile_id]
    d = M_DIRECTIONS[missile_id]
    return M0 + V_M * t * d


def uav_position(uav_id, theta, v, t):
    """计算无人机在时刻 t 的位置（匀速等高直线飞行）"""
    P0 = U_POSITIONS[uav_id]
    return np.array([
        P0[0] + v * t * np.cos(theta),
        P0[1] + v * t * np.sin(theta),
        P0[2]
    ])


def bomb_burst_position(uav_id, theta, v, t_d, t_b):
    """
    计算烟幕弹的起爆位置。
    弹在 t_d 时刻投放，在 t_b 时刻起爆。
    水平: 继承无人机速度匀速运动
    垂直: 从投放时刻起自由落体
    """
    P0 = U_POSITIONS[uav_id]
    dt_fall = t_b - t_d  # 自由落体时长
    return np.array([
        P0[0] + v * t_b * np.cos(theta),
        P0[1] + v * t_b * np.sin(theta),
        P0[2] - 0.5 * G * dt_fall * dt_fall
    ])


def cloud_center(burst_pos, t, t_b):
    """
    云团中心在时刻 t 的位置 (t >= t_b)。
    起爆后云团以 V_SINK 匀速下沉。
    """
    dt = t - t_b
    return np.array([
        burst_pos[0],
        burst_pos[1],
        burst_pos[2] - V_SINK * dt
    ])


# ============================================================
# 遮蔽区间查找
# ============================================================
def _quick_occlusion_feasibility(missile_id, burst_pos, t_b):
    """
    快速预筛选：检查云团是否有可能遮蔽目标。
    在云团生命期内多点采样，若所有采样点云团到导弹-目标视线的距离都 > 20*R_s，则跳过。
    """
    T_center = REAL_TARGET_CENTER
    t_start = t_b
    t_end = min(t_b + T_C, M_FLIGHT_TIMES[missile_id])

    # 在云团生命期内均匀采样 5 个时间点
    for t_sample in np.linspace(t_start, t_end, 5):
        M = missile_position(missile_id, t_sample)
        C = cloud_center(burst_pos, t_sample, t_b)

        d_line = T_center - M
        line_len_sq = np.dot(d_line, d_line)
        if line_len_sq < 1e-12:
            continue

        v_mc = M - C
        t_proj = -np.dot(v_mc, d_line) / line_len_sq
        t_proj = np.clip(t_proj, 0.0, 1.0)
        closest_point = M + t_proj * d_line
        min_dist = np.linalg.norm(closest_point - C)

        # 只要有一个采样点距离 < 20*R_s 就不跳过
        if min_dist < 20.0 * R_S:
            return True

    return False


def find_occlusion_interval_single_cloud(missile_id, burst_pos, t_b):
    """
    查找单朵云团对指定导弹的有效遮蔽区间。
    返回 (t_start, t_end) 或 (None, None) 若无遮蔽。

    使用粗扫描 + 二分查找精确定位区间端点。
    """
    t_min = t_b
    t_max = t_b + T_C
    # 导弹到达目标的时间上界
    t_flight = M_FLIGHT_TIMES[missile_id]
    t_max = min(t_max, t_flight)

    if t_min >= t_max:
        return None, None

    # 快速预筛选：若云团几何上不可能落在导弹-目标之间，直接返回 None
    if not _quick_occlusion_feasibility(missile_id, burst_pos, t_b):
        return None, None

    # 粗扫描
    n_steps = int(np.ceil((t_max - t_min) / DT_COARSE))
    if n_steps < 10:
        n_steps = 10

    times = np.linspace(t_min, t_max, n_steps + 1)
    occlusion_flags = np.zeros(len(times), dtype=bool)

    for idx, t in enumerate(times):
        M_t = missile_position(missile_id, t)
        C_t = cloud_center(burst_pos, t, t_b)
        occlusion_flags[idx] = check_full_occlusion(M_t, C_t, R_S)

    # 查找 0→1 切换 (遮蔽开始) 和 1→0 切换 (遮蔽结束)
    transitions = np.diff(occlusion_flags.astype(int))

    # 找到第一个 True 区间
    true_indices = np.where(occlusion_flags)[0]
    if len(true_indices) == 0:
        return None, None

    # 第一个遮蔽区间的边界
    first_true = true_indices[0]
    last_true = true_indices[-1]

    # 处理可能的多个区间：取第一个 (单朵云团仅产生一个连续区间)
    # 找到过渡点
    start_transitions = np.where(transitions == 1)[0]
    end_transitions = np.where(transitions == -1)[0]

    if len(start_transitions) == 0:
        # 从 t_min 就开始遮蔽
        t_start_coarse = t_min
    else:
        t_start_coarse = times[start_transitions[0] + 1]

    if len(end_transitions) == 0:
        # 持续到 t_max
        t_end_coarse = t_max
    else:
        t_end_coarse = times[end_transitions[0]]

    # 二分查找精确定位 t_start
    # 在 [t_start_coarse - DT_COARSE, t_start_coarse] 区间内二分
    t_left = max(t_min, t_start_coarse - DT_COARSE)
    t_right = t_start_coarse

    # 验证端点状态
    M_left = missile_position(missile_id, t_left)
    C_left = cloud_center(burst_pos, t_left, t_b)
    state_left = check_full_occlusion(M_left, C_left, R_S)

    M_right = missile_position(missile_id, t_right)
    C_right = cloud_center(burst_pos, t_right, t_b)
    state_right = check_full_occlusion(M_right, C_right, R_S)

    if not state_left and state_right:
        # 正常情况：在 [t_left, t_right] 内二分找切换点
        while (t_right - t_left) > EPS_BISECTION:
            t_mid = (t_left + t_right) / 2.0
            M_mid = missile_position(missile_id, t_mid)
            C_mid = cloud_center(burst_pos, t_mid, t_b)
            state_mid = check_full_occlusion(M_mid, C_mid, R_S)
            if state_mid:
                t_right = t_mid
            else:
                t_left = t_mid
        t_start = (t_left + t_right) / 2.0
    elif state_left:
        # 区间左端点已遮挡 → t_start = t_left
        t_start = t_left
    else:
        t_start = t_start_coarse

    # 二分查找精确定位 t_end
    t_left = t_end_coarse
    t_right = min(t_max, t_end_coarse + DT_COARSE)

    M_left_e = missile_position(missile_id, t_left)
    C_left_e = cloud_center(burst_pos, t_left, t_b)
    state_left_e = check_full_occlusion(M_left_e, C_left_e, R_S)

    M_right_e = missile_position(missile_id, t_right)
    C_right_e = cloud_center(burst_pos, t_right, t_b)
    state_right_e = check_full_occlusion(M_right_e, C_right_e, R_S)

    if state_left_e and not state_right_e:
        while (t_right - t_left) > EPS_BISECTION:
            t_mid = (t_left + t_right) / 2.0
            M_mid = missile_position(missile_id, t_mid)
            C_mid = cloud_center(burst_pos, t_mid, t_b)
            state_mid = check_full_occlusion(M_mid, C_mid, R_S)
            if state_mid:
                t_left = t_mid
            else:
                t_right = t_mid
        t_end = (t_left + t_right) / 2.0
    elif not state_left_e:
        t_end = t_left
    else:
        t_end = t_end_coarse

    return t_start, t_end


def merge_intervals(intervals):
    """合并重叠的时间区间，返回合并后的区间列表和总时长"""
    if not intervals:
        return [], 0.0

    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(sorted_intervals[0])]

    for start, end in sorted_intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    total = sum(end - start for start, end in merged)
    return merged, total


# ============================================================
# 通用目标函数评估 (底层核心)
# ============================================================
def evaluate_occlusion_time_single_uav(missile_id, theta, v, td_list, tb_list):
    """
    评估单架无人机的投弹方案对指定导弹的有效遮蔽时长。

    参数:
        missile_id: 导弹编号 (1/2/3)
        theta: 无人机航向角
        v: 无人机速度
        td_list: 投放时刻列表 [t_d1, t_d2, ...]
        tb_list: 起爆时刻列表 [t_b1, t_b2, ...]

    返回:
        T_eff: 总有效遮蔽时长 (s)
        intervals: 所有遮蔽区间 [(start, end), ...]
    """
    uav_id = 1  # 默认 FY1 (被调用时会重载)
    # NOTE: 这个函数需要 uav_id 参数，但为了兼容多无人机场景，
    # 这里保留为通用接口。实际调用时 uav_id 由具体问题确定。

    all_intervals = []

    for k, (t_d, t_b) in enumerate(zip(td_list, tb_list)):
        if t_b <= t_d:
            continue  # 不可行：起爆在投放之前
        if t_b > M_FLIGHT_TIMES[missile_id]:
            continue  # 不可行：导弹已到达目标

        burst_pos = bomb_burst_position(uav_id, theta, v, t_d, t_b)

        # 快速剪枝：若云团中心距导弹轨迹过远 (>500m)，跳过
        # (这是一个启发式优化)
        t_mid = t_b + T_C / 2.0
        M_mid = missile_position(missile_id, t_mid)
        C_mid = cloud_center(burst_pos, t_mid, t_b)
        if np.linalg.norm(M_mid - C_mid) > 5000:
            continue

        t_start, t_end = find_occlusion_interval_single_cloud(
            missile_id, burst_pos, t_b
        )

        if t_start is not None and t_end is not None:
            all_intervals.append((t_start, t_end))

    merged, total = merge_intervals(all_intervals)
    return total, merged


def evaluate_q1_q2(missile_id, uav_id, theta, v, td, tb):
    """
    Q1/Q2 的简化评估函数 (单机单弹)。
    """
    all_intervals = []
    burst_pos = bomb_burst_position(uav_id, theta, v, td, tb)
    t_start, t_end = find_occlusion_interval_single_cloud(
        missile_id, burst_pos, tb
    )
    if t_start is not None and t_end is not None:
        all_intervals.append((t_start, t_end))
    merged, total = merge_intervals(all_intervals)
    return total, merged, burst_pos


# ============================================================
# 问题一: 确定性计算 (Q1)
# ============================================================
def solve_q1():
    """
    Q1: 给定参数下计算单机单弹的有效遮蔽时长。

    参数:
        UAV FY1, 航向 pi (朝向假目标), v=120 m/s
        t_d=1.5s, t_b=5.1s
        导弹 M1
    """
    print("=" * 60)
    print("问题一 (Q1): 给定参数确定性计算")
    print("=" * 60)

    missile_id = 1
    uav_id = 1
    theta = Q1_THETA
    v = Q1_V
    t_d = Q1_T_D
    t_b = Q1_T_B

    print(f"  无人机 FY1: 初始位置 {U_POSITIONS[uav_id]}")
    print(f"  航向角: {theta:.4f} rad ({np.degrees(theta):.1f}°)")
    print(f"  速度: {v} m/s")
    print(f"  投放时刻 t_d: {t_d} s")
    print(f"  起爆时刻 t_b: {t_b} s (Δt = {t_b - t_d} s)")
    print(f"  导弹 M1: 初始位置 {M_POSITIONS[missile_id]}")
    print(f"  导弹方向: {M_DIRECTIONS[missile_id]}")

    # 计算起爆位置
    burst_pos = bomb_burst_position(uav_id, theta, v, t_d, t_b)
    print(f"\n  起爆位置 B: ({burst_pos[0]:.1f}, {burst_pos[1]:.1f}, {burst_pos[2]:.1f})")

    # 计算遮蔽区间
    T_eff, intervals, _ = evaluate_q1_q2(missile_id, uav_id, theta, v, t_d, t_b)

    print(f"\n  >>> 有效遮蔽时长 T_eff = {T_eff:.3f} s <<<")

    if intervals:
        for i, (start, end) in enumerate(intervals):
            print(f"  遮蔽区间 {i+1}: [{start:.3f}, {end:.3f}] s (持续 {end-start:.3f} s)")
    else:
        print("  无遮蔽区间!")

    # 生成时间序列数据 (用于绘图)
    t_series = np.linspace(0, min(M_FLIGHT_TIMES[missile_id], 30), 300)
    occl_series = np.zeros(len(t_series), dtype=bool)

    for idx, t in enumerate(t_series):
        if t >= t_b and t <= t_b + T_C:
            M_t = missile_position(missile_id, t)
            C_t = cloud_center(burst_pos, t, t_b)
            occl_series[idx] = check_full_occlusion(M_t, C_t, R_S)

    # 导弹和云团轨迹
    missile_traj = np.array([missile_position(missile_id, t) for t in t_series])
    cloud_traj = np.array([
        cloud_center(burst_pos, t, t_b) if t >= t_b else burst_pos
        for t in t_series
    ])

    result = {
        'T_eff': T_eff,
        'intervals': intervals,
        'burst_pos': burst_pos,
        't_series': t_series,
        'occl_series': occl_series,
        'missile_traj': missile_traj,
        'cloud_traj': cloud_traj,
        'params': {
            'theta': theta, 'v': v, 't_d': t_d, 't_b': t_b,
            'uav_id': uav_id, 'missile_id': missile_id
        }
    }

    return result


# ============================================================
# 问题二: 4D 优化 (Q2) — 网格搜索 + Nelder-Mead
# ============================================================
def solve_q2():
    """
    Q2: 单机单弹 4 维优化 (θ, v, t_d, t_b)。
    策略: 粗粒度网格搜索 + Top-N Nelder-Mead 局部爬山。
    """
    print("\n" + "=" * 60)
    print("问题二 (Q2): 4D 网格搜索 + Nelder-Mead 优化")
    print("=" * 60)

    missile_id = 1
    uav_id = 1

    # 第一阶段: 粗粒度网格搜索
    N_theta = 36   # 每 10°
    N_v = 8        # 每 10 m/s
    N_td = 16      # 每 1 s
    N_tb_per_td = 8

    t_flight = M_FLIGHT_TIMES[missile_id]
    print(f"  导弹 M1 飞行时间: {t_flight:.1f} s")

    grid_best = []  # [(T_eff, theta, v, td, tb), ...]
    total_grid = N_theta * N_v * N_td * N_tb_per_td
    print(f"  网格总点数: {total_grid}")
    print(f"  正在搜索...")

    count = 0
    t_start_grid = time.time()

    for i_theta in range(N_theta):
        theta = i_theta * 2.0 * np.pi / N_theta
        for i_v in range(N_v):
            v = V_U_MIN + i_v * 10.0
            for i_td in range(N_td):
                td = i_td * 1.0
                for i_tb in range(N_tb_per_td):
                    tb = td + 1.0 + i_tb * 3.0  # td+1, td+4, td+7, ..., td+22
                    if tb > t_flight:
                        continue

                    T_eff, _, _ = evaluate_q1_q2(missile_id, uav_id, theta, v, td, tb)
                    grid_best.append((T_eff, theta, v, td, tb))
                    count += 1

                    if count % 5000 == 0:
                        elapsed = time.time() - t_start_grid
                        print(f"    已评估 {count} 点, 当前最优 T_eff={max(g[0] for g in grid_best):.3f}s, 耗时 {elapsed:.1f}s")

    t_end_grid = time.time()
    print(f"  网格搜索完成: {count} 个有效点, 耗时 {t_end_grid - t_start_grid:.1f}s")

    # 按 T_eff 降序排序，取 Top-20
    grid_best.sort(key=lambda x: x[0], reverse=True)
    N_top = 20
    top_starts = grid_best[:N_top]

    print(f"\n  网格搜索 Top-5 结果:")
    for i, (Te, th, v, td, tb) in enumerate(grid_best[:5]):
        print(f"    #{i+1}: T_eff={Te:.3f}s, θ={np.degrees(th):.1f}°, v={v:.0f}m/s, td={td:.1f}s, tb={tb:.1f}s")

    # 第二阶段: Nelder-Mead 局部爬山
    print(f"\n  第二阶段: Nelder-Mead 局部爬山 (Top-{N_top} 起点)...")

    local_best = []
    nm_count = 0

    for rank, (T0, th0, v0, td0, tb0) in enumerate(top_starts):
        x0 = np.array([th0, v0, td0, tb0])

        # 使用 scipy Nelder-Mead (加硬边界罚项)
        def _nm_objective(x):
            th, v, td, tb = x
            # 边界罚项: 超出范围则大幅惩罚
            penalty = 0.0
            if v < V_U_MIN or v > V_U_MAX:
                penalty += 1e6 * min((v - V_U_MIN)**2, (v - V_U_MAX)**2)
            if td < 0 or td > 60:
                penalty += 1e6 * (max(0, -td)**2 + max(0, td-60)**2)
            if tb <= td:
                penalty += 1e6 * (td - tb + 0.1)**2
            if tb - td > 20:
                penalty += 1e6 * (tb - td - 20)**2
            T_eff, _, _ = evaluate_q1_q2(missile_id, uav_id, th, v, td, tb)
            return -(T_eff - penalty)

        res = minimize(
            _nm_objective,
            x0,
            method='Nelder-Mead',
            options={
                'maxiter': 200,
                'xatol': 1e-3,
                'fatol': 1e-3,
                'return_all': False
            }
        )

        T_opt = -res.fun
        local_best.append((T_opt, res.x, res.nfev if hasattr(res, 'nfev') else 0))
        nm_count += 1

    local_best.sort(key=lambda x: x[0], reverse=True)

    print(f"\n  Nelder-Mead 最佳结果:")
    T_best, x_best, _ = local_best[0]
    th_best, v_best, td_best, tb_best = x_best
    print(f"    T_eff = {T_best:.3f} s")
    print(f"    θ = {th_best:.4f} rad ({np.degrees(th_best):.1f}°)")
    print(f"    v = {v_best:.2f} m/s")
    print(f"    t_d = {td_best:.3f} s")
    print(f"    t_b = {tb_best:.3f} s")

    # 第三阶段: PSO 交叉验证 (简化版 — 若 NM 结果较差)
    if T_best < 2.0:
        print(f"\n  NM 结果 T_eff={T_best:.3f} < 2.0s, 运行简化 PSO 交叉验证...")
        T_pso, x_pso = _pso_search(missile_id, uav_id, n_particles=40, n_iter=80)
        if T_pso > T_best * 1.05:
            print(f"  PSO 更优! T_eff={T_pso:.3f}s, 采纳 PSO 结果")
            T_best, x_best = T_pso, x_pso
            th_best, v_best, td_best, tb_best = x_best

    # 生成结果数据
    T_eff_final, intervals, burst_pos = evaluate_q1_q2(
        missile_id, uav_id, th_best, v_best, td_best, tb_best
    )

    t_series = np.linspace(0, min(t_flight, 40), 400)
    occl_series = np.zeros(len(t_series), dtype=bool)
    for idx, t in enumerate(t_series):
        if t >= tb_best and t <= tb_best + T_C:
            M_t = missile_position(missile_id, t)
            C_t = cloud_center(burst_pos, t, tb_best)
            occl_series[idx] = check_full_occlusion(M_t, C_t, R_S)

    result = {
        'T_eff': T_eff_final,
        'intervals': intervals,
        'burst_pos': burst_pos,
        'params': {
            'theta': th_best, 'v': v_best, 't_d': td_best, 't_b': tb_best,
            'uav_id': uav_id, 'missile_id': missile_id
        },
        't_series': t_series,
        'occl_series': occl_series,
        'grid_top5': grid_best[:5],
        'nm_results': local_best[:5],
        'method': 'GridSearch + Nelder-Mead'
    }

    return result


def _pso_search(missile_id, uav_id, n_particles=40, n_iter=80):
    """简化版 PSO 用于 Q2 交叉验证"""
    bounds = np.array([[0, 2*np.pi], [70, 140], [0, 30], [1, 67]])
    dim = 4

    # 初始化
    pos = np.random.uniform(
        [b[0] for b in bounds],
        [b[1] for b in bounds],
        (n_particles, dim)
    )
    vel = np.zeros((n_particles, dim))
    p_best_pos = pos.copy()
    p_best_val = np.array([
        evaluate_q1_q2(missile_id, uav_id, p[0], p[1], p[2], p[3])[0]
        for p in pos
    ])

    g_best_idx = np.argmax(p_best_val)
    g_best_pos = p_best_pos[g_best_idx].copy()
    g_best_val = p_best_val[g_best_idx]

    w = 0.7
    c1 = 1.5
    c2 = 1.5

    for iteration in range(n_iter):
        r1, r2 = np.random.random(2)
        vel = (w * vel +
               c1 * r1 * (p_best_pos - pos) +
               c2 * r2 * (g_best_pos - pos))

        pos = pos + vel
        # 边界修复
        for d in range(dim):
            pos[:, d] = np.clip(pos[:, d], bounds[d][0], bounds[d][1])
        # td < tb
        pos[:, 3] = np.maximum(pos[:, 3], pos[:, 2] + 0.01)

        for i in range(n_particles):
            val = evaluate_q1_q2(missile_id, uav_id,
                                pos[i, 0], pos[i, 1], pos[i, 2], pos[i, 3])[0]
            if val > p_best_val[i]:
                p_best_val[i] = val
                p_best_pos[i] = pos[i].copy()
                if val > g_best_val:
                    g_best_val = val
                    g_best_pos = pos[i].copy()

    return g_best_val, g_best_pos


# ============================================================
# 问题三: 差分进化 (Q3) — 单机三弹 8D 优化
# ============================================================
def solve_q3():
    """
    Q3: 单机三弹时序优化 (8维 DE)。
    决策变量: [θ, v, td1, td2, td3, tb1, tb2, tb3]
    """
    print("\n" + "=" * 60)
    print("问题三 (Q3): 差分进化 8D 优化 (单机三弹)")
    print("=" * 60)

    missile_id = 1
    uav_id = 1

    Np = 60       # 种群规模
    F = 0.8       # 缩放因子
    CR = 0.9      # 交叉概率
    G_max = 150   # 最大代数
    G_stagnant = 30
    n_restarts = 5

    dim = 8
    t_flight = M_FLIGHT_TIMES[missile_id]

    # 边界定义
    bounds = np.array([
        [0.0, 2*np.pi],   # theta
        [70.0, 140.0],    # v
        [0.0, 35.0],      # td1
        [0.0, 40.0],      # td2
        [0.0, 45.0],      # td3
        [0.01, 55.0],     # tb1
        [0.01, 60.0],     # tb2
        [0.01, 65.0],     # tb3
    ])

    global_best_x = None
    global_best_T = 0.0
    all_run_results = []

    for run in range(n_restarts):
        print(f"\n  DE 运行 {run+1}/{n_restarts}...")
        best_x, best_T, history = _de_single_run(
            missile_id, uav_id, Np, F, CR, G_max, G_stagnant,
            bounds, t_flight
        )
        all_run_results.append({'x': best_x, 'T': best_T, 'history': history})
        print(f"    运行 {run+1} 最优: T_eff = {best_T:.3f} s")

        if best_T > global_best_T:
            global_best_T = best_T
            global_best_x = best_x.copy()

    print(f"\n  全局最优: T_eff = {global_best_T:.3f} s")
    print(f"  参数: θ={np.degrees(global_best_x[0]):.1f}°, v={global_best_x[1]:.1f}m/s")
    for k in range(3):
        print(f"    弹{k+1}: td={global_best_x[2+k]:.3f}s, tb={global_best_x[5+k]:.3f}s")

    # 最终评估
    T_eff_final, intervals = _evaluate_multi_bomb(
        missile_id, uav_id, global_best_x
    )

    # 准备结果
    t_series = np.linspace(0, min(t_flight, 60), 600)
    burst_positions = []
    for k in range(3):
        bp = bomb_burst_position(uav_id, global_best_x[0], global_best_x[1],
                                 global_best_x[2+k], global_best_x[5+k])
        burst_positions.append(bp)

    result = {
        'T_eff': T_eff_final,
        'intervals': intervals,
        'params': {
            'theta': global_best_x[0], 'v': global_best_x[1],
            'td_list': global_best_x[2:5].tolist(),
            'tb_list': global_best_x[5:8].tolist(),
            'uav_id': uav_id, 'missile_id': missile_id
        },
        't_series': t_series,
        'burst_positions': burst_positions,
        'de_history': all_run_results,
        'method': 'DE/rand/1/bin'
    }

    return result


def _evaluate_multi_bomb(missile_id, uav_id, x):
    """Q3/Q4 的通用评估函数，返回 (T_eff, intervals)"""
    theta, v = x[0], x[1]
    n_bombs = (len(x) - 2) // 2
    td_list = x[2:2+n_bombs]
    tb_list = x[2+n_bombs:2+2*n_bombs]

    all_intervals = []
    for k in range(n_bombs):
        td, tb = td_list[k], tb_list[k]
        if tb <= td or tb > M_FLIGHT_TIMES[missile_id]:
            continue
        burst_pos = bomb_burst_position(uav_id, theta, v, td, tb)
        t_start, t_end = find_occlusion_interval_single_cloud(
            missile_id, burst_pos, tb
        )
        if t_start is not None and t_end is not None:
            all_intervals.append((t_start, t_end))

    merged, total = merge_intervals(all_intervals)
    return total, merged


def _repair_solution(x, bounds, t_flight):
    """DE 个体修复: 边界裁切 + 时序约束修复"""
    xr = x.copy()
    dim = len(xr)

    # 边界裁切
    for d in range(min(dim, len(bounds))):
        xr[d] = np.clip(xr[d], bounds[d][0], bounds[d][1])

    # theta 取模
    xr[0] = xr[0] % (2 * np.pi)

    # td 排序并强制间隔 >= 1
    if dim >= 5:
        td_start = 2
        n_bombs = (dim - 2) // 2
        td_vals = xr[td_start:td_start + n_bombs].copy()
        td_vals.sort()
        for k in range(1, n_bombs):
            if td_vals[k] < td_vals[k-1] + MIN_BOMB_INTERVAL:
                td_vals[k] = td_vals[k-1] + MIN_BOMB_INTERVAL
        xr[td_start:td_start + n_bombs] = td_vals

    # tb > td 约束
    if dim >= 6:
        n_bombs = (dim - 2) // 2
        for k in range(n_bombs):
            tb_idx = 2 + n_bombs + k
            td_val = xr[2 + k]
            if xr[tb_idx] <= td_val:
                xr[tb_idx] = td_val + 0.01

    # tb 非递减
    if dim >= 7:
        n_bombs = (dim - 2) // 2
        for k in range(1, n_bombs):
            tb_idx = 2 + n_bombs + k
            if xr[tb_idx] < xr[tb_idx - 1]:
                xr[tb_idx] = xr[tb_idx - 1]

    return xr


def _de_single_run(missile_id, uav_id, Np, F, CR, G_max, G_stagnant,
                   bounds, t_flight):
    """单次 DE 运行"""
    dim = len(bounds)
    n_bombs = (dim - 2) // 2

    # 种群初始化
    population = np.zeros((Np, dim))
    fitness = np.zeros(Np)

    for p in range(Np):
        x = np.zeros(dim)
        x[0] = np.random.uniform(0, 2*np.pi)
        x[1] = np.random.uniform(70, 140)

        # td 初始化（有序且间隔≥1）
        td_raw = np.sort(np.random.uniform(0, 30, n_bombs))
        for k in range(1, n_bombs):
            td_raw[k] = max(td_raw[k], td_raw[k-1] + MIN_BOMB_INTERVAL)
        x[2:2+n_bombs] = td_raw

        # tb 初始化
        for k in range(n_bombs):
            x[2+n_bombs+k] = np.random.uniform(
                x[2+k] + 0.01,
                min(x[2+k] + 25, t_flight)
            )
        # tb 非递减
        for k in range(1, n_bombs):
            x[2+n_bombs+k] = max(x[2+n_bombs+k], x[2+n_bombs+k-1])

        population[p] = x
        fitness[p] = _evaluate_multi_bomb(missile_id, uav_id, x)[0]

    best_idx = np.argmax(fitness)
    best_x = population[best_idx].copy()
    best_f = fitness[best_idx]
    stagnant_count = 0
    history = [best_f]

    # 主循环
    for g in range(G_max):
        new_population = np.zeros_like(population)
        new_fitness = np.zeros(Np)

        for p in range(Np):
            # 变异: DE/rand/1
            candidates = [i for i in range(Np) if i != p]
            a, b, c = np.random.choice(candidates, 3, replace=False)
            mutant = population[a] + F * (population[b] - population[c])

            # 交叉: 二项式
            trial = population[p].copy()
            j_rand = np.random.randint(0, dim)
            for d in range(dim):
                if np.random.random() < CR or d == j_rand:
                    trial[d] = mutant[d]

            # 修复
            trial = _repair_solution(trial, bounds, t_flight)

            # 评估
            trial_f, _ = _evaluate_multi_bomb(missile_id, uav_id, trial)

            # 选择
            if trial_f >= fitness[p]:
                new_population[p] = trial
                new_fitness[p] = trial_f
            else:
                new_population[p] = population[p]
                new_fitness[p] = fitness[p]

        population = new_population
        fitness = new_fitness

        current_best_idx = np.argmax(fitness)
        if fitness[current_best_idx] > best_f + 1e-6:
            best_f = fitness[current_best_idx]
            best_x = population[current_best_idx].copy()
            stagnant_count = 0
        else:
            stagnant_count += 1

        history.append(best_f)

        if stagnant_count >= G_stagnant:
            break

    return best_x, best_f, history


# ============================================================
# 问题四: 三机单弹空间协同 (Q4) — 12D DE
# ============================================================
def solve_q4():
    """
    Q4: 三架无人机各投 1 枚弹的 12 维 DE 优化。
    决策变量: [θ1,v1,td1,tb1, θ2,v2,td2,tb2, θ3,v3,td3,tb3]
    """
    print("\n" + "=" * 60)
    print("问题四 (Q4): 差分进化 12D 优化 (三机单弹)")
    print("=" * 60)

    missile_id = 1  # 目标导弹
    uav_ids = [1, 2, 3]  # FY1, FY2, FY3

    Np = 100
    F = 0.8
    CR = 0.9
    G_max = 200
    G_stagnant = 40
    n_restarts = 3

    n_uavs = len(uav_ids)
    dim = 4 * n_uavs  # 12
    t_flight = M_FLIGHT_TIMES[missile_id]

    bounds_list = []
    for j in range(n_uavs):
        bounds_list.extend([
            [0.0, 2*np.pi],   # theta_j
            [70.0, 140.0],    # v_j
            [0.0, 30.0],      # td_j
            [0.01, 60.0],     # tb_j
        ])
    bounds = np.array(bounds_list)

    global_best_x = None
    global_best_T = 0.0

    for run in range(n_restarts):
        print(f"\n  DE 运行 {run+1}/{n_restarts}...")
        best_x, best_T, _ = _de_multi_uav_run(
            missile_id, uav_ids, Np, F, CR, G_max, G_stagnant,
            bounds, t_flight
        )
        print(f"    运行 {run+1} 最优: T_eff = {best_T:.3f} s")
        if best_T > global_best_T:
            global_best_T = best_T
            global_best_x = best_x.copy()

    print(f"\n  全局最优: T_eff = {global_best_T:.3f} s")
    for j, uid in enumerate(uav_ids):
        idx = j * 4
        th = global_best_x[idx]
        v = global_best_x[idx+1]
        td = global_best_x[idx+2]
        tb = global_best_x[idx+3]
        print(f"    FY{uid}: θ={np.degrees(th):.1f}°, v={v:.1f}m/s, td={td:.3f}s, tb={tb:.3f}s")

    # 最终评估
    T_eff_final, intervals = _evaluate_multi_uav(missile_id, uav_ids, global_best_x)

    burst_positions = []
    for j, uid in enumerate(uav_ids):
        idx = j * 4
        bp = bomb_burst_position(uid, global_best_x[idx], global_best_x[idx+1],
                                 global_best_x[idx+2], global_best_x[idx+3])
        burst_positions.append(bp)

    t_series = np.linspace(0, min(t_flight, 60), 600)

    result = {
        'T_eff': T_eff_final,
        'intervals': intervals,
        'params': {f'FY{uid}': {
            'theta': global_best_x[j*4],
            'v': global_best_x[j*4+1],
            't_d': global_best_x[j*4+2],
            't_b': global_best_x[j*4+3]
        } for j, uid in enumerate(uav_ids)},
        't_series': t_series,
        'burst_positions': burst_positions,
        'method': 'DE/rand/1/bin (Multi-UAV)'
    }

    return result


def _evaluate_multi_uav(missile_id, uav_ids, x):
    """多无人机评估函数"""
    n_uavs = len(uav_ids)
    all_intervals = []

    for j, uid in enumerate(uav_ids):
        idx = j * 4
        theta, v, td, tb = x[idx], x[idx+1], x[idx+2], x[idx+3]

        if tb <= td or tb > M_FLIGHT_TIMES[missile_id]:
            continue

        burst_pos = bomb_burst_position(uid, theta, v, td, tb)
        t_start, t_end = find_occlusion_interval_single_cloud(
            missile_id, burst_pos, tb
        )
        if t_start is not None and t_end is not None:
            all_intervals.append((t_start, t_end))

    merged, total = merge_intervals(all_intervals)
    return total, merged


def _de_multi_uav_run(missile_id, uav_ids, Np, F, CR, G_max, G_stagnant,
                      bounds, t_flight):
    """多无人机 DE 单次运行"""
    dim = len(bounds)
    n_uavs = len(uav_ids)

    population = np.zeros((Np, dim))
    fitness = np.zeros(Np)

    for p in range(Np):
        x = np.zeros(dim)
        for j in range(n_uavs):
            idx = j * 4
            x[idx] = np.random.uniform(0, 2*np.pi)
            x[idx+1] = np.random.uniform(70, 140)
            x[idx+2] = np.random.uniform(0, 25)
            x[idx+3] = np.random.uniform(x[idx+2] + 0.5, min(x[idx+2] + 20, t_flight))
        population[p] = x
        fitness[p] = _evaluate_multi_uav(missile_id, uav_ids, x)[0]

    best_idx = np.argmax(fitness)
    best_x = population[best_idx].copy()
    best_f = fitness[best_idx]
    stagnant_count = 0
    history = [best_f]

    for g in range(G_max):
        new_population = np.zeros_like(population)
        new_fitness = np.zeros(Np)

        for p in range(Np):
            candidates = [i for i in range(Np) if i != p]
            a, b, c = np.random.choice(candidates, 3, replace=False)
            mutant = population[a] + F * (population[b] - population[c])

            trial = population[p].copy()
            j_rand = np.random.randint(0, dim)
            for d in range(dim):
                if np.random.random() < CR or d == j_rand:
                    trial[d] = mutant[d]

            trial = _repair_multi_uav(trial, bounds, n_uavs, t_flight)
            trial_f, _ = _evaluate_multi_uav(missile_id, uav_ids, trial)

            if trial_f >= fitness[p]:
                new_population[p] = trial
                new_fitness[p] = trial_f
            else:
                new_population[p] = population[p]
                new_fitness[p] = fitness[p]

        population = new_population
        fitness = new_fitness

        curr_best = np.argmax(fitness)
        if fitness[curr_best] > best_f + 1e-6:
            best_f = fitness[curr_best]
            best_x = population[curr_best].copy()
            stagnant_count = 0
        else:
            stagnant_count += 1

        history.append(best_f)
        if stagnant_count >= G_stagnant:
            break

    return best_x, best_f, history


def _repair_multi_uav(x, bounds, n_uavs, t_flight):
    """多无人机个体修复"""
    xr = x.copy()
    for d in range(len(bounds)):
        xr[d] = np.clip(xr[d], bounds[d][0], bounds[d][1])

    for j in range(n_uavs):
        idx = j * 4
        xr[idx] = xr[idx] % (2*np.pi)  # theta 取模
        if xr[idx+3] <= xr[idx+2]:
            xr[idx+3] = xr[idx+2] + 0.01

    return xr


# ============================================================
# 问题五: 多机多弹多目标分层优化 (Q5)
# ============================================================
def solve_q5():
    """
    Q5: 5 架无人机 vs 3 枚导弹 — 分层优化框架。
    Layer 1: 任务分配 (UAV → Missile)
    Layer 2: 逐导弹子问题 DE 求解
    Layer 3: 全局合并 (木桶效应取 min)
    """
    print("\n" + "=" * 60)
    print("问题五 (Q5): 分层优化 (5 UAV × 3 Missile)")
    print("=" * 60)

    # 候选分配方案
    allocations = [
        {
            'name': '方案A (自然聚类)',
            'mapping': {1: [1], 2: [2, 4], 3: [3, 5]},
            # FY1→M1, FY2→M2, FY3→M3, FY4→M2, FY5→M3
        },
        {
            'name': '方案B (FY2→M1)',
            'mapping': {1: [1, 2], 2: [4], 3: [3, 5]},
            # FY1→M1, FY2→M1, FY3→M3, FY4→M2, FY5→M3
        },
        {
            'name': '方案C (FY2→M3)',
            'mapping': {1: [1], 2: [4], 3: [2, 3, 5]},
            # FY1→M1, FY2→M3, FY3→M3, FY4→M2, FY5→M3
        },
    ]

    best_global = {
        'T_global': 0.0,
        'alloc_name': None,
        'per_missile': {}
    }

    for alloc in allocations:
        print(f"\n  评估 {alloc['name']}...")
        T_per_missile = {}
        solutions_per_missile = {}

        for missile_id, uav_list in alloc['mapping'].items():
            n_uavs = len(uav_list)
            # 每架 UAV 最多 2 枚弹 (为计算效率)
            max_bombs_per_uav = 2

            # 使用简化的 DE 求解子问题
            T_opt, sol = _solve_subproblem(
                missile_id, uav_list, max_bombs_per_uav
            )
            T_per_missile[missile_id] = T_opt
            solutions_per_missile[missile_id] = sol

            print(f"    M{missile_id} (UAVs {uav_list}): T_eff = {T_opt:.3f} s")

        T_global = min(T_per_missile.values())  # 木桶效应
        print(f"    全局指标: T_global = {T_global:.3f} s")

        if T_global > best_global['T_global']:
            best_global = {
                'T_global': T_global,
                'alloc_name': alloc['name'],
                'per_missile': T_per_missile.copy(),
                'solutions': solutions_per_missile,
                'mapping': alloc['mapping']
            }

    if best_global['alloc_name'] is None:
        print(f"\n  [注意] 所有分配方案全局遮蔽时长均为0")
        return {'T_eff_global': 0.0, 'alloc_name': '无有效方案', 'per_missile': {1:0,2:0,3:0}, 'method': 'Hierarchical DE (all failed)'}
    print(f"\n  最优分配方案: {best_global['alloc_name']}")
    print(f"  全局遮蔽时长: {best_global['T_global']:.3f} s")
    for mid in [1, 2, 3]:
        print(f"    M{mid}: T_eff = {best_global['per_missile'].get(mid, 0):.3f} s")

    result = {
        'T_eff_global': best_global['T_global'],
        'alloc_name': best_global['alloc_name'],
        'per_missile': best_global['per_missile'],
        'method': 'Hierarchical DE'
    }

    return result


def _solve_subproblem(missile_id, uav_ids, max_bombs_per_uav=2):
    """求解单个导弹的遮蔽子问题 (简化版 DE)"""
    n_uavs = len(uav_ids)
    # 每架 UAV 决策: theta, v, td1, tb1, (td2, tb2 if k=2)
    # 固定每架各投 2 枚弹: dim = n_uavs * 6
    k_per_uav = max_bombs_per_uav
    dim = n_uavs * (2 + 2 * k_per_uav)  # 6 per UAV

    t_flight = M_FLIGHT_TIMES[missile_id]

    # 简化: 使用较小的种群和代数
    Np = max(40, dim * 5)
    F = 0.8
    CR = 0.9
    G_max = 80

    # 构建边界
    bounds_list = []
    for _ in range(n_uavs):
        bounds_list.extend([[0, 2*np.pi], [70, 140]])  # theta, v
        for _ in range(k_per_uav):
            bounds_list.extend([[0, 30], [0.01, t_flight]])  # td, tb

    bounds = np.array(bounds_list)

    # 初始化
    population = np.zeros((Np, dim))
    fitness = np.zeros(Np)

    for p in range(Np):
        x = np.zeros(dim)
        for j in range(n_uavs):
            base = j * (2 + 2*k_per_uav)
            x[base] = np.random.uniform(0, 2*np.pi)
            x[base+1] = np.random.uniform(70, 140)
            for k in range(k_per_uav):
                tb_idx = base + 2 + k_per_uav + k
                td_idx = base + 2 + k
                x[td_idx] = np.random.uniform(k * 5, k * 5 + 20)
                x[tb_idx] = np.random.uniform(x[td_idx] + 0.5,
                                              min(x[td_idx] + 20, t_flight))
        population[p] = x
        fitness[p] = _evaluate_subproblem(missile_id, uav_ids, x, k_per_uav)

    best_idx = np.argmax(fitness)
    best_x = population[best_idx].copy()
    best_f = fitness[best_idx]
    stagnant_count = 0

    for g in range(G_max):
        for p in range(Np):
            candidates = [i for i in range(Np) if i != p]
            a, b, c = np.random.choice(candidates, 3, replace=False)
            mutant = population[a] + F * (population[b] - population[c])

            trial = population[p].copy()
            jr = np.random.randint(0, dim)
            for d in range(dim):
                if np.random.random() < CR or d == jr:
                    trial[d] = mutant[d]

            # 修复
            for d in range(dim):
                trial[d] = np.clip(trial[d], bounds[d][0], bounds[d][1])
            for j in range(n_uavs):
                base = j * (2 + 2*k_per_uav)
                trial[base] = trial[base] % (2*np.pi)

                # 排序 td 并确保间隔 >= 1
                td_vals = [trial[base + 2 + k] for k in range(k_per_uav)]
                td_vals.sort()
                for k in range(k_per_uav):
                    trial[base + 2 + k] = td_vals[k]
                for k in range(1, k_per_uav):
                    if trial[base + 2 + k] < trial[base + 2 + k - 1] + MIN_BOMB_INTERVAL:
                        trial[base + 2 + k] = trial[base + 2 + k - 1] + MIN_BOMB_INTERVAL

                # tb > td 约束
                for k in range(k_per_uav):
                    if trial[base + 2 + k_per_uav + k] <= trial[base + 2 + k]:
                        trial[base + 2 + k_per_uav + k] = trial[base + 2 + k] + 0.01
                # tb 非递减
                for k in range(1, k_per_uav):
                    if trial[base + 2 + k_per_uav + k] < trial[base + 2 + k_per_uav + k - 1]:
                        trial[base + 2 + k_per_uav + k] = trial[base + 2 + k_per_uav + k - 1]

            tf = _evaluate_subproblem(missile_id, uav_ids, trial, k_per_uav)
            if tf >= fitness[p]:
                population[p] = trial
                fitness[p] = tf

        curr_best = np.max(fitness)
        if curr_best > best_f + 1e-6:
            best_f = curr_best
            best_idx = np.argmax(fitness)
            best_x = population[best_idx].copy()
            stagnant_count = 0
        else:
            stagnant_count += 1

        if stagnant_count >= 20:
            break

    return best_f, best_x


def _evaluate_subproblem(missile_id, uav_ids, x, k_per_uav):
    """子问题评估函数"""
    n_uavs = len(uav_ids)
    all_intervals = []

    for j, uid in enumerate(uav_ids):
        base = j * (2 + 2*k_per_uav)
        theta = x[base]
        v = x[base + 1]

        for k in range(k_per_uav):
            td = x[base + 2 + k]
            tb = x[base + 2 + k_per_uav + k]
            if tb <= td or tb > M_FLIGHT_TIMES[missile_id]:
                continue

            burst_pos = bomb_burst_position(uid, theta, v, td, tb)
            t_start, t_end = find_occlusion_interval_single_cloud(
                missile_id, burst_pos, tb
            )
            if t_start is not None and t_end is not None:
                all_intervals.append((t_start, t_end))

    _, total = merge_intervals(all_intervals)
    return total


# ============================================================
# 可视化函数
# ============================================================
def set_academic_style():
    """设置学术风格"""
    plt.rcParams.update({
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 9,
        'figure.dpi': 150,
        'savefig.dpi': 300,
        'savefig.bbox': 'tight',
        'font.family': 'serif',
        'font.serif': ['Times New Roman', 'DejaVu Serif'],
        'mathtext.fontset': 'stix',
        'axes.grid': True,
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
    })


def plot_q1_result(result, save_path):
    """图1: Q1 遮蔽状态时间序列"""
    set_academic_style()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

    t = result['t_series']
    occl = result['occl_series'].astype(float)
    params = result['params']

    # 上图: 遮蔽状态
    ax1.fill_between(t, 0, occl, where=(occl > 0.5),
                     color='#2196F3', alpha=0.3, label='Occluded')
    ax1.step(t, occl, where='mid', color='#1565C0', linewidth=1.5)
    ax1.axvline(x=params['t_b'], color='#E65100', linestyle='--',
                linewidth=1.2, label=f"t_b = {params['t_b']:.1f}s")
    ax1.axvline(x=params['t_b'] + T_C, color='#E65100', linestyle=':',
                linewidth=1.2, label=f"t_b + T_c = {params['t_b'] + T_C:.1f}s")

    if result['intervals']:
        for start, end in result['intervals']:
            ax1.axvspan(start, end, alpha=0.15, color='#4CAF50')
            ax1.annotate(f'{end-start:.2f}s',
                        xy=((start+end)/2, 0.5),
                        ha='center', fontsize=9,
                        bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.8))

    ax1.set_ylabel('Occlusion State')
    ax1.set_title(f'Q1: Single UAV Single Bomb — Occlusion Timeline\n'
                  f'(θ={np.degrees(params["theta"]):.0f}°, v={params["v"]:.0f}m/s, '
                  f'T_eff={result["T_eff"]:.3f}s)')
    ax1.legend(loc='upper right')
    ax1.set_ylim(-0.1, 1.2)
    ax1.set_xlabel('Time [s]')

    # 下图: 导弹-云团-目标空间几何
    missile_xy = result['missile_traj'][:, :2]
    cloud_xy = result['cloud_traj'][:, :2]

    ax2.plot(missile_xy[:, 0], missile_xy[:, 1], color='#D32F2F',
             linewidth=1.5, label='Missile M1 Trajectory')
    ax2.plot(cloud_xy[:, 0], cloud_xy[:, 1], color='#1976D2',
             linewidth=1.5, label='Cloud Center Trajectory')
    ax2.scatter(*REAL_TARGET_CENTER[:2], marker='s', s=80, color='#2E7D32',
                zorder=5, label='Real Target')
    ax2.scatter(0, 0, marker='x', s=80, color='#6A1B9A',
                zorder=5, label='Decoy Target')
    bp = result['burst_pos']
    ax2.scatter(bp[0], bp[1], marker='*', s=120, color='#E65100',
                zorder=5, label=f'Burst Point (t={params["t_b"]:.1f}s)')

    # 在起爆时刻绘制云团圆
    from matplotlib.patches import Circle
    circle = Circle((bp[0], bp[1]), R_S, fill=False, edgecolor='#FF9800',
                    linestyle='--', linewidth=1, alpha=0.7)
    ax2.add_patch(circle)

    ax2.set_xlabel('X [m]')
    ax2.set_ylabel('Y [m]')
    ax2.set_title('Top-Down View: Missile, Cloud, and Targets')
    ax2.legend(loc='upper left', fontsize=8)
    ax2.set_aspect('equal')

    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  [图] 已保存: {save_path}")


def plot_q2_result(result, save_path):
    """图2: Q2 优化结果"""
    set_academic_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 左上: 优化后遮蔽状态
    ax = axes[0, 0]
    t = result['t_series']
    occl = result['occl_series'].astype(float)
    ax.fill_between(t, 0, occl, where=(occl > 0.5),
                    color='#43A047', alpha=0.3)
    ax.step(t, occl, where='mid', color='#2E7D32', linewidth=1.5)
    ax.set_ylabel('Occlusion State')
    ax.set_xlabel('Time [s]')
    ax.set_title(f'Q2 Optimized Occlusion (T_eff={result["T_eff"]:.3f}s)')
    ax.set_ylim(-0.1, 1.2)

    # 右上: 网格搜索结果分布
    ax = axes[0, 1]
    grid_vals = [g[0] for g in result['grid_top5'][:30]]
    ax.bar(range(len(grid_vals)), grid_vals, color='#5C6BC0', alpha=0.8)
    ax.set_xlabel('Grid Point Rank')
    ax.set_ylabel('T_eff [s]')
    ax.set_title('Grid Search Top Results')

    # 左下: Nelder-Mead 收敛曲线
    ax = axes[1, 0]
    nm_vals = [r[0] for r in result['nm_results']]
    ax.plot(range(1, len(nm_vals)+1), nm_vals, 'o-', color='#E65100',
            markersize=6, linewidth=1.5)
    ax.set_xlabel('NM Start Point Rank')
    ax.set_ylabel('T_eff after NM [s]')
    ax.set_title('Nelder-Mead Refinement Results')

    # 右下: 参数文本
    ax = axes[1, 1]
    ax.axis('off')
    p = result['params']
    text = (f"Optimized Parameters:\n\n"
            f"θ = {np.degrees(p['theta']):.2f}°\n"
            f"v = {p['v']:.2f} m/s\n"
            f"t_d = {p['t_d']:.3f} s\n"
            f"t_b = {p['t_b']:.3f} s\n"
            f"Δ(t_b-t_d) = {p['t_b']-p['t_d']:.3f} s\n\n"
            f"Result: T_eff = {result['T_eff']:.3f} s\n"
            f"Method: {result['method']}")
    ax.text(0.1, 0.9, text, transform=ax.transAxes, fontsize=11,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', fc='#F5F5F5', ec='#BDBDBD'))

    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  [图] 已保存: {save_path}")


def plot_q3_result(result, save_path):
    """图3: Q3 DE 优化结果"""
    set_academic_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 左上: DE 收敛曲线
    ax = axes[0, 0]
    colors = ['#1565C0', '#2E7D32', '#E65100', '#6A1B9A', '#C62828']
    for i, run in enumerate(result['de_history']):
        hist = run['history']
        ax.plot(hist, color=colors[i % len(colors)], linewidth=1.2,
                alpha=0.8, label=f'Run {i+1} (best={run["T"]:.2f}s)')
    ax.set_xlabel('Generation')
    ax.set_ylabel('Best T_eff [s]')
    ax.set_title('Q3: DE Convergence (5 Independent Runs)')
    ax.legend(fontsize=8)

    # 右上: 遮蔽时间线
    ax = axes[0, 1]
    intervals = result['intervals']
    p = result['params']
    y_pos = 0
    for k in range(3):
        td_k = p['td_list'][k]
        tb_k = p['tb_list'][k]

        # 云团有效期
        ax.barh(y_pos, T_C, left=tb_k, height=0.6,
                color=colors[k], alpha=0.5, label=f'Bomb {k+1} (cloud)')

        # 遮蔽区间
        for start, end in intervals:
            if abs(start - tb_k) < 3 or (start <= tb_k <= end):
                pass  # approximate association
        y_pos += 1

    # 简化: 绘制遮蔽区间合并结果
    for i, (start, end) in enumerate(intervals):
        ax.axvspan(start, end, alpha=0.2, color='#4CAF50')
        mid = (start + end) / 2
        ax.annotate(f'{end-start:.2f}s', xy=(mid, 1.5),
                   ha='center', fontsize=9)

    ax.set_xlabel('Time [s]')
    ax.set_ylabel('Cloud')
    ax.set_title(f'Q3: Multi-Bomb Occlusion Timeline (T_eff={result["T_eff"]:.3f}s)')
    ax.legend(fontsize=7)

    # 左下: 参数可视化
    ax = axes[1, 0]
    ax.axis('off')
    text_lines = [f"Q3 DE/rand/1/bin Results:", ""]
    text_lines.append(f"θ = {np.degrees(p['theta']):.2f}°")
    text_lines.append(f"v = {p['v']:.2f} m/s")
    text_lines.append(f"")
    for k in range(3):
        text_lines.append(f"Bomb {k+1}: td={p['td_list'][k]:.3f}s, "
                         f"tb={p['tb_list'][k]:.3f}s, "
                         f"Δt={p['tb_list'][k]-p['td_list'][k]:.3f}s")
    text_lines.append(f"")
    text_lines.append(f"T_eff = {result['T_eff']:.3f} s")

    ax.text(0.05, 0.95, '\n'.join(text_lines), transform=ax.transAxes,
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', fc='#FAFAFA', ec='#BDBDBD'))

    # 右下: 起爆点空间分布
    ax = axes[1, 1]
    for k, bp in enumerate(result['burst_positions']):
        ax.scatter(bp[0], bp[1], marker='*', s=120,
                  color=colors[k], zorder=5, label=f'Bomb {k+1}')
        from matplotlib.patches import Circle
        circle = Circle((bp[0], bp[1]), R_S, fill=False,
                       edgecolor=colors[k], linestyle='--', linewidth=1, alpha=0.6)
        ax.add_patch(circle)

    ax.scatter(*REAL_TARGET_CENTER[:2], marker='s', s=80,
              color='#2E7D32', zorder=4, label='Real Target')
    ax.scatter(0, 0, marker='x', s=80, color='#6A1B9A', zorder=4, label='Decoy')

    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title('Q3: Burst Points Layout')
    ax.legend(fontsize=7)
    ax.set_aspect('equal')

    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  [图] 已保存: {save_path}")


def plot_q4_result(result, save_path):
    """图4: Q4 多机协同结果"""
    set_academic_style()
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 左上: 遮蔽区间甘特图
    ax = axes[0, 0]
    intervals = result['intervals']
    for i, (start, end) in enumerate(intervals):
        ax.barh(0, end - start, left=start, height=0.8,
                color='#43A047', alpha=0.7, edgecolor='#2E7D32')
        ax.text((start+end)/2, 0, f'{end-start:.2f}s',
                ha='center', va='center', fontsize=9)

    ax.set_xlabel('Time [s]')
    ax.set_yticks([])
    ax.set_title(f'Q4: Combined Occlusion (T_eff={result["T_eff"]:.3f}s)')

    # 右上: 参数表
    ax = axes[0, 1]
    ax.axis('off')
    text_lines = [f"Q4 Multi-UAV Results:", f"T_eff = {result['T_eff']:.3f} s", ""]
    for key, val in result['params'].items():
        text_lines.append(
            f"{key}: θ={np.degrees(val['theta']):.1f}°, v={val['v']:.1f}m/s, "
            f"td={val['t_d']:.3f}s, tb={val['t_b']:.3f}s"
        )
    ax.text(0.05, 0.95, '\n'.join(text_lines), transform=ax.transAxes,
            fontsize=9, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', fc='#FAFAFA', ec='#BDBDBD'))

    # 左下: 起爆点空间布局
    ax = axes[1, 0]
    colors_uav = ['#1565C0', '#2E7D32', '#E65100']
    for j, bp in enumerate(result['burst_positions']):
        ax.scatter(bp[0], bp[1], marker='*', s=120,
                  color=colors_uav[j], zorder=5, label=f'FY{j+1}')
        from matplotlib.patches import Circle
        circle = Circle((bp[0], bp[1]), R_S, fill=False,
                       edgecolor=colors_uav[j], linestyle='--', linewidth=1, alpha=0.6)
        ax.add_patch(circle)
        # UAV 初始位置
        uav_init = U_POSITIONS[j+1]
        ax.scatter(uav_init[0], uav_init[1], marker='^', s=60,
                  color=colors_uav[j], alpha=0.5)

    ax.scatter(*REAL_TARGET_CENTER[:2], marker='s', s=80,
              color='#2E7D32', zorder=4, label='Real Target')
    ax.scatter(0, 0, marker='x', s=80, color='#6A1B9A', zorder=4, label='Decoy')
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title('Q4: UAVs & Burst Points')
    ax.legend(fontsize=7)
    ax.set_aspect('equal')

    # 右下: 时间扫描 (每朵云团的遮蔽状态)
    ax = axes[1, 1]
    t = result['t_series']
    # 为每朵云团计算遮蔽状态
    for j, (key, val) in enumerate(result['params'].items()):
        uid = int(key[2])
        occl_j = np.zeros(len(t))
        for idx, ti in enumerate(t):
            if ti >= val['t_b'] and ti <= val['t_b'] + T_C:
                bp = result['burst_positions'][j]
                C_t = cloud_center(bp, ti, val['t_b'])
                M_t = missile_position(1, ti)
                occl_j[idx] = 1.0 if check_full_occlusion(M_t, C_t, R_S) else 0.0
        ax.fill_between(t, j*1.2, j*1.2 + occl_j, color=colors_uav[j], alpha=0.5,
                       label=key)

    ax.set_xlabel('Time [s]')
    ax.set_ylabel('UAV')
    ax.set_yticks([0.6, 1.8, 3.0])
    ax.set_yticklabels(['FY1', 'FY2', 'FY3'])
    ax.set_title('Q4: Per-UAV Occlusion States')
    ax.legend(fontsize=7)

    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  [图] 已保存: {save_path}")


def plot_q5_result(result, save_path):
    """图5: Q5 分层优化结果"""
    set_academic_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 左: 各导弹遮蔽时长对比
    ax = axes[0]
    missiles = [1, 2, 3]
    values = [result['per_missile'][m] for m in missiles]
    colors_bar = ['#1565C0', '#2E7D32', '#E65100']
    bars = ax.bar(missiles, values, color=colors_bar, alpha=0.85, edgecolor='#333')
    ax.axhline(y=result['T_eff_global'], color='#C62828', linestyle='--',
              linewidth=1.5, label=f'Min Threshold = {result["T_eff_global"]:.2f}s')

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.03,
                f'{val:.3f}s', ha='center', fontsize=10)

    ax.set_xlabel('Missile')
    ax.set_ylabel('T_eff [s]')
    ax.set_title(f'Q5: Per-Missile Occlusion Duration\n({result["alloc_name"]})')
    ax.set_xticks(missiles)
    ax.legend()

    # 右: 分配方案可视化
    ax = axes[1]
    ax.axis('off')
    text_lines = [
        f"Q5 Hierarchical Optimization",
        f"",
        f"Allocation: {result['alloc_name']}",
        f"Global T_eff = {result['T_eff_global']:.3f} s",
        f"",
        f"Per-Missile Results:",
        f"  M1: {result['per_missile'][1]:.3f} s",
        f"  M2: {result['per_missile'][2]:.3f} s",
        f"  M3: {result['per_missile'][3]:.3f} s",
        f"",
        f"Method: {result['method']}",
        f"(木桶效应: 取 min 作为全局指标)"
    ]
    ax.text(0.05, 0.95, '\n'.join(text_lines), transform=ax.transAxes,
            fontsize=11, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', fc='#F5F5F5', ec='#BDBDBD'))

    plt.tight_layout()
    fig.savefig(save_path)
    plt.close(fig)
    print(f"  [图] 已保存: {save_path}")


# ============================================================
# 结果保存函数
# ============================================================
def save_results_to_files(all_results, figures_dir, results_dir):
    """保存所有结果为 CSV/XLSX 文件"""
    rows = []

    # Q1
    q1 = all_results['q1']
    rows.append({
        'problem_id': 'Q1', 'metric_name': '有效遮蔽时长', 'value': q1['T_eff'],
        'unit': 's', 'method': '确定性计算 (几何模拟)',
        'figure_ref': 'fig01_q1_occlusion_timeline.png',
        'formula_ref': 'Eq.(1)-(7)'
    })
    rows.append({
        'problem_id': 'Q1', 'metric_name': '起爆位置X', 'value': q1['burst_pos'][0],
        'unit': 'm', 'method': '抛体运动公式',
        'figure_ref': 'fig01_q1_occlusion_timeline.png',
        'formula_ref': 'Eq.(3)'
    })
    rows.append({
        'problem_id': 'Q1', 'metric_name': '起爆位置Y', 'value': q1['burst_pos'][1],
        'unit': 'm', 'method': '抛体运动公式',
        'figure_ref': 'fig01_q1_occlusion_timeline.png',
        'formula_ref': 'Eq.(3)'
    })
    rows.append({
        'problem_id': 'Q1', 'metric_name': '起爆位置Z', 'value': q1['burst_pos'][2],
        'unit': 'm', 'method': '抛体运动公式',
        'figure_ref': 'fig01_q1_occlusion_timeline.png',
        'formula_ref': 'Eq.(3)'
    })

    # Q2
    q2 = all_results['q2']
    rows.append({
        'problem_id': 'Q2', 'metric_name': '最大有效遮蔽时长', 'value': q2['T_eff'],
        'unit': 's', 'method': q2['method'],
        'figure_ref': 'fig02_q2_optimization.png',
        'formula_ref': 'Eq.(1)-(7) + NM优化'
    })
    rows.append({
        'problem_id': 'Q2', 'metric_name': '最优航向角', 'value': np.degrees(q2['params']['theta']),
        'unit': '°', 'method': q2['method'],
        'figure_ref': 'fig02_q2_optimization.png',
        'formula_ref': 'Eq.(8)'
    })
    rows.append({
        'problem_id': 'Q2', 'metric_name': '最优速度', 'value': q2['params']['v'],
        'unit': 'm/s', 'method': q2['method'],
        'figure_ref': 'fig02_q2_optimization.png',
        'formula_ref': 'Eq.(8)'
    })
    rows.append({
        'problem_id': 'Q2', 'metric_name': '最优投放时刻', 'value': q2['params']['t_d'],
        'unit': 's', 'method': q2['method'],
        'figure_ref': 'fig02_q2_optimization.png',
        'formula_ref': 'Eq.(8)'
    })
    rows.append({
        'problem_id': 'Q2', 'metric_name': '最优起爆时刻', 'value': q2['params']['t_b'],
        'unit': 's', 'method': q2['method'],
        'figure_ref': 'fig02_q2_optimization.png',
        'formula_ref': 'Eq.(8)'
    })

    # Q3
    q3 = all_results['q3']
    rows.append({
        'problem_id': 'Q3', 'metric_name': '最大有效遮蔽时长', 'value': q3['T_eff'],
        'unit': 's', 'method': q3['method'],
        'figure_ref': 'fig03_q3_de_optimization.png',
        'formula_ref': 'Eq.(9)'
    })
    for k in range(3):
        rows.append({
            'problem_id': 'Q3', 'metric_name': f'弹{k+1}投放时刻', 'value': q3['params']['td_list'][k],
            'unit': 's', 'method': q3['method'],
            'figure_ref': 'fig03_q3_de_optimization.png',
            'formula_ref': f'DE x[{2+k}]'
        })
        rows.append({
            'problem_id': 'Q3', 'metric_name': f'弹{k+1}起爆时刻', 'value': q3['params']['tb_list'][k],
            'unit': 's', 'method': q3['method'],
            'figure_ref': 'fig03_q3_de_optimization.png',
            'formula_ref': f'DE x[{5+k}]'
        })

    # Q4
    q4 = all_results['q4']
    rows.append({
        'problem_id': 'Q4', 'metric_name': '最大有效遮蔽时长', 'value': q4['T_eff'],
        'unit': 's', 'method': q4['method'],
        'figure_ref': 'fig04_q4_multi_uav.png',
        'formula_ref': 'Eq.(10)'
    })
    for key, val in q4['params'].items():
        rows.append({
            'problem_id': 'Q4', 'metric_name': f'{key}航向角', 'value': np.degrees(val['theta']),
            'unit': '°', 'method': q4['method'],
            'figure_ref': 'fig04_q4_multi_uav.png',
            'formula_ref': 'DE 12D'
        })
        rows.append({
            'problem_id': 'Q4', 'metric_name': f'{key}速度', 'value': val['v'],
            'unit': 'm/s', 'method': q4['method'],
            'figure_ref': 'fig04_q4_multi_uav.png',
            'formula_ref': 'DE 12D'
        })

    # Q5
    q5 = all_results['q5']
    rows.append({
        'problem_id': 'Q5', 'metric_name': '全局最短遮蔽时长', 'value': q5['T_eff_global'],
        'unit': 's', 'method': q5['method'],
        'figure_ref': 'fig05_q5_hierarchical.png',
        'formula_ref': 'Eq.(11)-(12)'
    })
    for mid in [1, 2, 3]:
        rows.append({
            'problem_id': 'Q5', 'metric_name': f'M{mid}遮蔽时长',
            'value': q5['per_missile'][mid],
            'unit': 's', 'method': q5['method'],
            'figure_ref': 'fig05_q5_hierarchical.png',
            'formula_ref': f'Layer 2 subproblem M{mid}'
        })

    # 保存为 CSV
    df = pd.DataFrame(rows)
    csv_path = f'{results_dir}/results_summary.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8')
    print(f"\n  结果汇总已保存: {csv_path}")

    # 保存为 XLSX (每个问题一个 Sheet)
    try:
        xlsx_path = f'{results_dir}/results_summary.xlsx'
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            for pid in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
                subset = df[df['problem_id'] == pid]
                subset.to_excel(writer, sheet_name=pid, index=False)
            # 汇总 Sheet
            df.to_excel(writer, sheet_name='Summary', index=False)
        print(f"  结果汇总已保存: {xlsx_path}")
    except Exception as e:
        print(f"  XLSX 保存失败 ({e})，已使用 CSV 格式")

    # 每个子问题独立 CSV
    for pid in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
        subset = df[df['problem_id'] == pid]
        subset.to_csv(f'{results_dir}/{pid}_results.csv', index=False, encoding='utf-8')

    print(f"  各子问题结果已保存至 {results_dir}/")

    return df


# ============================================================
# 主函数
# ============================================================
def main():
    """主入口：依次求解 Q1-Q5 并生成图表和结果文件"""
    import os

    # 输出目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_dir = os.path.dirname(base_dir)  # run-{timestamp}/
    figures_dir = os.path.join(run_dir, 'figures')
    results_dir = os.path.join(run_dir, 'results')

    os.makedirs(figures_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    print("=" * 70)
    print(" 2025 MCM Problem A — 烟幕遮蔽策略优化求解器")
    print("=" * 70)
    print(f" 输出目录: {run_dir}")
    print(f" 图目录: {figures_dir}")
    print(f" 结果目录: {results_dir}")
    print()

    all_results = {}
    t_start_total = time.time()

    # ---- 问题一 ----
    q1_result = solve_q1()
    all_results['q1'] = q1_result
    plot_q1_result(q1_result, os.path.join(figures_dir, 'fig01_q1_occlusion_timeline.png'))

    # ---- 问题二 ----
    q2_result = solve_q2()
    all_results['q2'] = q2_result
    plot_q2_result(q2_result, os.path.join(figures_dir, 'fig02_q2_optimization.png'))

    # ---- 问题三 ----
    q3_result = solve_q3()
    all_results['q3'] = q3_result
    plot_q3_result(q3_result, os.path.join(figures_dir, 'fig03_q3_de_optimization.png'))

    # ---- 问题四 ----
    q4_result = solve_q4()
    all_results['q4'] = q4_result
    plot_q4_result(q4_result, os.path.join(figures_dir, 'fig04_q4_multi_uav.png'))

    # ---- 问题五 ----
    q5_result = solve_q5()
    all_results['q5'] = q5_result
    plot_q5_result(q5_result, os.path.join(figures_dir, 'fig05_q5_hierarchical.png'))

    # ---- 保存结果 ----
    df = save_results_to_files(all_results, figures_dir, results_dir)

    t_end_total = time.time()

    # ---- 结果汇总 ----
    print("\n" + "=" * 70)
    print(" 全部求解完成 — 结果汇总")
    print("=" * 70)
    print(f" {'问题':<6} {'T_eff [s]':<12} {'方法':<30}")
    print(f" {'-'*48}")
    print(f" {'Q1':<6} {q1_result['T_eff']:<12.3f} {'确定性几何模拟':<30}")
    print(f" {'Q2':<6} {q2_result['T_eff']:<12.3f} {q2_result['method']:<30}")
    print(f" {'Q3':<6} {q3_result['T_eff']:<12.3f} {q3_result['method']:<30}")
    print(f" {'Q4':<6} {q4_result['T_eff']:<12.3f} {q4_result['method']:<30}")
    print(f" {'Q5':<6} {q5_result['T_eff_global']:<12.3f} {q5_result['method']:<30}")
    print(f" {'-'*48}")
    print(f" 总耗时: {t_end_total - t_start_total:.1f} s")
    print(f"\n 所有文件已保存至: {run_dir}/")

    return all_results


if __name__ == '__main__':
    main()
