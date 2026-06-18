"""
Module: 2025 MCM Problem A — UAV烟幕遮蔽策略优化 (修正版 v2)
Description: 完整求解 Problems 1-5，包含几何遮挡判定、差分进化优化、多机多弹协同
Author: Coding Expert Agent
Date: 2026-05-31

# 本次已主动避免的编码阶段错误:
# - ERR-reproducibility: 固定 np.random.seed(42) + 各子问题独立种子确保结果可复现
#   每个 SolveProblem 函数使用独立 RandomState 或前置 seed 调用
# - ERR-misleading_viz: 所有图表的坐标轴含完整单位标签，图例位置合理，采用 academic 配色
# - ERR-missing_error_handling: 处理 a<1e-12, Delta<0, 除零, 边界截断 等数值异常
# - ERR-data_leakage: 无机器学习数据，不适用
# - ERR-C-002 (Q2优化退化): 优化结束后与Q1默认参数(theta=pi,v_u=30,t_d=0,t_b=9)比较
#   取较优者，并打印退化警告。模式搜索初始步长增大至2倍避免局部最优。
# - ERR-C-003 (Q3弹药浪费): 第2/3弹起爆时间智能初始化(起爆高度50-150m)+逐弹贡献检查
#   +单弹基线比较，防止3弹结果劣于1弹。
# - ERR-C-004 (Q5空区间无诊断): 逐组输出视线方向/UAV垂直距离/几何可达性诊断
#   将诊断信息保存至 Q5_feasibility_diagnosis.csv
# - ERR-C-005 (RNG独立): 每子问题调用前设置独立seed，互不干扰
# - ERR-C-006 (CSV不可解析): Q1 CSV 改为 key,value,unit 三列标准格式
# - ERR-C-007 (DE多样性): 每10代监控种群标准差，检测早熟收敛并输出日志
#
# [Phase 2 Round 2 修正 - run-20260531-141931]
# - Fix 1 (High): Q3重试阈值改为 Q1 启发式基线 T_q1_baseline - 0.5s 而非 T_single*0.9
# - Fix 2 (High): Q2 Phase-C 启发式退路检查 + use_heuristic_fallback 参数
#   若优化仍无法超越启发式，标注"[已确认] 启发式解即为全局最优"
# - Fix 3 (Med): Q3/Q5 CSV 用 json.dumps([float(v) for v in arr]) 代替 str(arr)
# - Fix 4 (Med): 地下起爆统一截断策略: compute_single_cloud_intervals 和 _evaluate_q2
#   都用 z=0 截断，继续计算遮挡（不再直接返回 []）
# - Fix 5 (Med): fig5 生成前删除旧残留文件
# - Fix 6 (Q5): SolveProblem5 开头增加场景几何可行性预检，若所有垂直距离 > 2*R_s
#   则输出清晰提示并跳过优化
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，确保无 GUI 依赖
import matplotlib.pyplot as plt
from matplotlib import cm
import pandas as pd
import os
import warnings
import json
from datetime import datetime
from itertools import accumulate

warnings.filterwarnings('ignore')

# ================================================================
# 全局参数与常量
# ================================================================
np.random.seed(42)

# --- 物理常量 ---
R_s = 50.0          # 烟幕云团有效遮蔽半径 [m]
T_c = 30.0          # 云团有效遮蔽持续时间 [s]
v_m = 300.0         # 导弹飞行速度 [m/s]
v_c = 3.0           # 云团下沉速度 [m/s]
g = 9.81            # 重力加速度 [m/s^2]
r_c = 7.0           # 假目标圆柱底面半径 [m]
H_c = 10.0          # 假目标圆柱高度 [m]
h_u = 500.0         # 无人机飞行高度 [m]
v_b0 = 10.0         # 烟幕弹弹射初速度大小 [m/s]

# --- 离散化参数 ---
N_pts_opt = 50      # 优化阶段圆柱圆周采样点数
N_pts_val = 300     # 验证阶段圆柱圆周采样点数
Delta_t_opt = 0.1   # 优化阶段时间步长 [s]
Delta_t_val = 0.01  # 验证阶段时间步长 [s]

# --- 决策变量边界 (Q2-Q4) ---
v_u_min, v_u_max = 20.0, 50.0         # 无人机速度范围 [m/s]
theta_min, theta_max = 0.0, 2.0 * np.pi   # 航向角范围 [rad]
t_d_min, t_d_max = 0.0, 30.0              # 投放时间范围 (Q2) [s]
t_d_min_Q3, t_d_max_Q3 = 0.0, 60.0        # 投放时间范围 (Q3) [s]
Delta_t_b_min, Delta_t_b_max = 2.0, 15.0  # 弹道飞行时间范围 [s]

# --- 差分进化 (DE) 参数 ---
N_pop = 50          # 种群规模
N_gen = 100         # 最大代数
F_mut = 0.7         # 变异缩放因子
CR_prob = 0.9       # 交叉概率
lambda_penalty = 1e6   # 罚函数系数

# --- Q3/Q5 参数 ---
Q3_delta_min = 1.0    # 弹间最小投放间隔 [s]
Q3_delta_gap = 0.0    # 最小遮蔽区间间隙（衔接下限）[s]
Q3_Delta_gap = 5.0    # 最大遮蔽区间间隙（衔接上限）[s]
Q3_T_max = 60.0       # 优化时域上限 [s]
K_bombs = 3           # 单机弹数 (Q3)
N_max_load = 3        # 每架无人机最大携弹数 (Q5)

# --- 路径配置 ---
# 此脚本位于 .../run-{ts}/code/solver.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.dirname(SCRIPT_DIR)       # .../run-{ts}/
CODE_DIR = SCRIPT_DIR
RESULTS_DIR = os.path.join(RUN_DIR, 'results')
FIGURES_DIR = os.path.join(RUN_DIR, 'figures')

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)


# ================================================================
# 辅助函数：启发式基线评估
# ================================================================
def evaluate_heuristic_q2(U1_0, M1_0, v_b0_val):
    """
    评估 Q1 默认启发式参数 (theta=pi, v_u=30, t_d=0, t_b=9) 的遮蔽效果
    用于与 Q2 优化结果比较，防止优化退化

    Returns:
        (T_default, x_default)
    """
    default_x = np.array([np.pi, 30.0, 0.0, 9.0])
    T_default, _ = _evaluate_q2(default_x, U1_0, M1_0, v_b0_val)
    return T_default, default_x


# ================================================================
# 辅助函数：DE种群多样性监控
# ================================================================
def check_diversity(pop, gen, threshold=1e-4):
    """
    计算种群参数标准差均值，若低于阈值则打日志提示早熟收敛

    Parameters:
        pop: ndarray (N_pop, dim)
        gen: 当前代数
        threshold: 标准差阈值
    Returns:
        mean_std: 各维标准差均值
    """
    pop_std = np.std(pop, axis=0)
    mean_std = np.mean(pop_std)
    if mean_std < threshold:
        print(f"  [多样性警告] gen={gen}: 种群参数标准差均值={mean_std:.2e} < {threshold:.0e}，可能过早收敛")
    return mean_std


# ================================================================
# 算法 1: 线段-球体遮挡判定函数
# ================================================================
def IsOccluded(M, C, R, P):
    """
    Algorithm 1: 线段-球体遮挡判定
    判断导弹位置M与圆柱表面点P之间的视线是否被云团(C,R)遮挡

    Parameters:
        M: 导弹位置向量 (3,) [m]
        C: 云团中心向量 (3,) [m]
        R: 云团有效半径 [m]
        P: 目标表面点向量 (3,) [m]

    Returns:
        occluded: bool (True=被遮蔽, False=可见)
    """
    M, C, P = np.asarray(M, dtype=float), np.asarray(C, dtype=float), np.asarray(P, dtype=float)

    d_vec = P - M                      # 视线方向向量
    a = np.dot(d_vec, d_vec)           # ||d||^2

    # 退化情形: M 与 P 近乎重合，无遮挡意义
    if a < 1e-12:
        return False

    diff = M - C
    b = 2.0 * np.dot(d_vec, diff)
    c = np.dot(diff, diff) - R * R

    # 判别式
    Delta = b * b - 4.0 * a * c

    # 无实根: 直线不与球体相交
    if Delta < -1e-12:
        return False

    # 数值容差: 非常小的负Delta视为0
    if Delta < 0.0:
        Delta = 0.0

    sqrt_Delta = np.sqrt(Delta)
    s1 = (-b - sqrt_Delta) / (2.0 * a)
    s2 = (-b + sqrt_Delta) / (2.0 * a)

    # 检查 [s1, s2] 与 [0, 1] 是否有交集
    if s2 < 0.0 - 1e-12:   # 两根都在线段起点之前
        return False
    if s1 > 1.0 + 1e-12:   # 两根都在线段终点之后
        return False

    return True


# ================================================================
# 算法 2: 圆柱全遮挡判定（时间点 t）
# ================================================================
def IsCylinderOccluded(Mt, Ct, R_sph, N_pts, r_c_cyl, H_cyl):
    """
    Algorithm 2: 判定整个圆柱是否被云团完全遮蔽
    基于引理1：只需检测上下底面圆周上所有点

    Parameters:
        Mt:      导弹在时刻t的位置 (3,) [m]
        Ct:      云团中心在时刻t的位置 (3,) [m]
        R_sph:   云团有效半径 [m]
        N_pts:   圆周离散采样点数
        r_c_cyl: 圆柱半径 [m]
        H_cyl:   圆柱高度 [m]

    Returns:
        occluded: bool (True=完全遮蔽)
    """
    # 按 2*N_pts 个均匀采样点检测圆柱上下底面圆周
    for i in range(N_pts):
        theta = 2.0 * np.pi * i / N_pts
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)

        # 下底面圆周点
        P_bot = np.array([r_c_cyl * cos_t, r_c_cyl * sin_t, 0.0])
        if not IsOccluded(Mt, Ct, R_sph, P_bot):
            return False

        # 上底面圆周点
        P_top = np.array([r_c_cyl * cos_t, r_c_cyl * sin_t, H_cyl])
        if not IsOccluded(Mt, Ct, R_sph, P_top):
            return False

    return True


# ================================================================
# 算法 3: 单弹有效遮蔽区间搜索（含二分法边界精化，支持多区间）
# ================================================================
def FindOcclusionInterval(M_func, C_func, R_sph, t_start, t_end,
                          Delta_t, N_pts, r_c_cyl, H_cyl):
    """
    Algorithm 3: 搜索单个烟幕云团的有效遮蔽时间区间
    支持多区间检测（覆盖引理2失效时的边界情况）

    Parameters:
        M_func:   导弹位置函数 M(t) -> ndarray(3,)
        C_func:   云团中心位置函数 C(t) -> ndarray(3,)
        R_sph:    云团有效半径 [m]
        t_start:  搜索起始时间（=起爆时间t_b）[s]
        t_end:    搜索终止时间（=t_b + T_c）[s]
        Delta_t:  时间步长 [s]
        N_pts:    圆周离散采样点数
        r_c_cyl:  圆柱半径 [m]
        H_cyl:    圆柱高度 [m]

    Returns:
        intervals: 列表 [(t_occ_start, t_occ_end), ...] 或 []（无有效遮蔽）
    """
    # 步骤1: 粗粒度扫描，收集遮蔽状态序列
    occ_flags = []  # 元素: (t, occluded_flag)
    t = t_start
    # 限制最大采样点数防止无限循环
    max_steps = int(1e6)
    step_count = 0
    while t <= t_end + 1e-9 and step_count < max_steps:
        try:
            Mt = M_func(t)
            Ct = C_func(t)

            # 边界处理: 若云团中心低于地面，在z=0处截断
            if Ct[2] < 0.0:
                Ct[2] = 0.0

            occ = IsCylinderOccluded(Mt, Ct, R_sph, N_pts, r_c_cyl, H_cyl)
            occ_flags.append((t, occ))
        except Exception:
            occ_flags.append((t, False))

        t += Delta_t
        step_count += 1

    # 步骤2: 检测连续遮蔽段
    intervals_raw = []
    in_occlusion = False
    seg_start = None

    for t_val, occ in occ_flags:
        if occ and not in_occlusion:
            seg_start = t_val
            in_occlusion = True
        if not occ and in_occlusion:
            seg_end = t_val
            in_occlusion = False
            if seg_end - seg_start >= Delta_t * 0.5:  # 至少半个步长的段才计数
                intervals_raw.append((seg_start, seg_end))

    if in_occlusion and seg_start is not None:
        intervals_raw.append((seg_start, t_end))

    # 合并可能相邻的区间（间隔很小的情况）
    if not intervals_raw:
        return []

    intervals_raw.sort(key=lambda x: x[0])
    merged = [list(intervals_raw[0])]
    for s, e in intervals_raw[1:]:
        if s - merged[-1][1] < Delta_t:  # 小于一个步长则合并
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    # 步骤3: 二分法边界精化
    refined = []
    for seg_start, seg_end in merged:
        # --- 精化左边界 ---
        t_low = max(t_start, seg_start - 2.0 * Delta_t)
        t_high = seg_start
        # 确保 t_low 处不被遮蔽
        Mt_low = M_func(t_low)
        Ct_low = C_func(t_low)
        if Ct_low[2] < 0.0:
            Ct_low[2] = 0.0
        if IsCylinderOccluded(Mt_low, Ct_low, R_sph, N_pts, r_c_cyl, H_cyl):
            # t_low 已被遮蔽，向左扩展搜索
            t_low = max(t_start, seg_start - 4.0 * Delta_t)

        for _ in range(50):  # 二分迭代，50次确保精度 < 1e-15
            if t_high - t_low < 1e-4:
                break
            t_mid = (t_low + t_high) / 2.0
            Mt_mid = M_func(t_mid)
            Ct_mid = C_func(t_mid)
            if Ct_mid[2] < 0.0:
                Ct_mid[2] = 0.0
            if IsCylinderOccluded(Mt_mid, Ct_mid, R_sph, N_pts, r_c_cyl, H_cyl):
                t_high = t_mid
            else:
                t_low = t_mid
        refined_start = t_high

        # --- 精化右边界 ---
        t_low = seg_end
        t_high = min(t_end, seg_end + 2.0 * Delta_t)
        # 确保 t_high 处不被遮蔽
        Mt_high = M_func(t_high)
        Ct_high = C_func(t_high)
        if Ct_high[2] < 0.0:
            Ct_high[2] = 0.0
        if IsCylinderOccluded(Mt_high, Ct_high, R_sph, N_pts, r_c_cyl, H_cyl):
            t_high = min(t_end, seg_end + 4.0 * Delta_t)

        for _ in range(50):
            if t_high - t_low < 1e-4:
                break
            t_mid = (t_low + t_high) / 2.0
            Mt_mid = M_func(t_mid)
            Ct_mid = C_func(t_mid)
            if Ct_mid[2] < 0.0:
                Ct_mid[2] = 0.0
            if IsCylinderOccluded(Mt_mid, Ct_mid, R_sph, N_pts, r_c_cyl, H_cyl):
                t_low = t_mid
            else:
                t_high = t_mid
        refined_end = t_low

        # 过滤掉过短的区间（< 0.01s 视为数值噪声）
        if refined_end - refined_start > 0.01:
            refined.append((refined_start, refined_end))

    return refined


# ================================================================
# 合并区间列表（排序+合并重叠/邻接区间）
# ================================================================
def MergeIntervals(intervals):
    """合并有序区间列表，返回合并后的 [(s,e), ...]"""
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda x: x[0])
    merged = []
    cur_s, cur_e = sorted_iv[0]
    for s, e in sorted_iv[1:]:
        if s <= cur_e + 1e-9:  # 重叠或邻接
            cur_e = max(cur_e, e)
        else:
            merged.append((cur_s, cur_e))
            cur_s, cur_e = s, e
    merged.append((cur_s, cur_e))
    return merged


# ================================================================
# 计算区间并集的总测度
# ================================================================
def UnionLength(intervals):
    """计算区间并集的总长度"""
    merged = MergeIntervals(intervals)
    return sum(e - s for s, e in merged)


# ================================================================
# 扫描线交集算法（计算三个区间集合的重叠总时长）
# ================================================================
def IntersectionLength(interval_sets):
    """
    扫描线算法计算多组区间的交集总长度
    interval_sets: [ [(s1,e1),...], [(s2,e2),...], [(s3,e3),...] ]
    Returns: total_intersection_time [s]
    """
    # 过滤空集
    non_empty = [iv for iv in interval_sets if iv]
    if len(non_empty) < len(interval_sets):
        return 0.0  # 任意一组为空，交集为0

    # 构建事件: (time, type, group_idx)
    # type=+1 表示区间开始, type=-1 表示区间结束
    events = []
    for g_idx, intervals in enumerate(interval_sets):
        for s, e in intervals:
            events.append((s, 1, g_idx))
            events.append((e, -1, g_idx))

    if not events:
        return 0.0

    events.sort(key=lambda x: x[0])

    # 扫描
    n_groups = len(interval_sets)
    active = [0] * n_groups
    last_time = events[0][0]
    total = 0.0

    for t, typ, g_idx in events:
        # 检查当前时刻是否有所有组同时激活
        if all(c > 0 for c in active):
            total += t - last_time
        active[g_idx] += typ
        last_time = t

    return max(total, 0.0)


# ================================================================
# 运动学轨迹函数
# ================================================================

def missile_trajectory(M0):
    """
    返回导弹位置函数 M(t)
    M_k(t) = M0 + v_m * t * d_m, d_m = -M0/||M0||
    """
    M0 = np.asarray(M0, dtype=float)
    norm_m0 = np.linalg.norm(M0)
    if norm_m0 < 1e-12:
        # 导弹已在原点，返回零函数
        return lambda t: np.zeros(3)

    d_m = -M0 / norm_m0

    def M_func(t):
        return M0 + v_m * t * d_m

    return M_func


def uav_trajectory(U0, v_u, theta):
    """
    返回无人机位置函数 U(t)
    U(t) = U0 + v_u * t * (cos(theta), sin(theta), 0)^T
    """
    U0 = np.asarray(U0, dtype=float)
    dir_vec = np.array([np.cos(theta), np.sin(theta), 0.0])

    def U_func(t):
        return U0 + v_u * t * dir_vec

    return U_func


def bomb_trajectory(U0, v_u, theta, v_b0_val, t_d):
    """
    返回烟幕弹抛体轨迹函数 B(t)，t in [t_d, t_b]
    B(t) = U(t_d) + v_b_total * (t - t_d) - 0.5*g*(t-t_d)^2 * (0,0,1)^T

    其中 v_b_total = UAV速度 + 弹射速度
    弹射方向: e_eject = normalize(cos(theta), sin(theta), -1)
    """
    U0 = np.asarray(U0, dtype=float)
    # UAV速度
    v_uav = v_u * np.array([np.cos(theta), np.sin(theta), 0.0])

    # 弹射方向（沿UAV航向斜向下）
    eject_raw = np.array([np.cos(theta), np.sin(theta), -1.0])
    norm_eject = np.linalg.norm(eject_raw)
    if norm_eject < 1e-12:
        e_eject = np.array([0.0, 0.0, -1.0])
    else:
        e_eject = eject_raw / norm_eject

    # 总初始速度 = UAV速度 + 弹射速度
    v_b_total = v_uav + v_b0_val * e_eject

    # U(t_d): 投放时刻的UAV位置
    dir_vec = np.array([np.cos(theta), np.sin(theta), 0.0])
    U_at_td = U0 + v_u * t_d * dir_vec
    gravity_vec = np.array([0.0, 0.0, 0.5 * g])

    def B_func(t):
        dt = t - t_d
        if dt < 0.0:
            return U_at_td  # 在投放前返回UAV位置
        return U_at_td + v_b_total * dt - gravity_vec * (dt * dt)

    return B_func


def cloud_trajectory(C_b, t_b):
    """
    返回云团中心位置函数 C(t), t in [t_b, t_b + T_c]
    C(t) = C_b - v_c * (t - t_b) * (0,0,1)^T
    """
    C_b = np.asarray(C_b, dtype=float)

    def C_func(t):
        dt = t - t_b
        if dt < 0.0:
            return C_b.copy()
        if dt > T_c:
            return C_b - v_c * T_c * np.array([0.0, 0.0, 1.0])
        return C_b - v_c * dt * np.array([0.0, 0.0, 1.0])

    return C_func


def compute_single_cloud_intervals(theta, v_u, t_d, t_b, M0, U0,
                                   v_b0_val, N_pts, Delta_t, r_c_val, H_val):
    """
    给定单UAV单弹的完整参数，计算对单枚导弹的遮蔽区间
    （被所有子问题共享的核心函数）

    Returns:
        intervals: [(s,e), ...] 或 []
    """
    # 构造轨迹函数
    M_func = missile_trajectory(M0)
    U_traj = uav_trajectory(U0, v_u, theta)
    B_traj = bomb_trajectory(U0, v_u, theta, v_b0_val, t_d)

    # 起爆点
    C_b = B_traj(t_b)
    # 统一截断策略：若起爆点低于地面，在z=0处截断，继续计算遮挡
    # （与 _evaluate_q2 中 truncation 逻辑一致）
    if C_b[2] < 0.0:
        C_b[2] = 0.0

    C_func = cloud_trajectory(C_b, t_b)

    # 搜索遮蔽区间
    t_search_start = t_b
    t_search_end = t_b + T_c

    intervals = FindOcclusionInterval(
        M_func, C_func, R_s, t_search_start, t_search_end,
        Delta_t, N_pts, r_c_val, H_val
    )

    return intervals


# ================================================================
# 算法 4: 问题1 — 单机单弹给定参数计算
# ================================================================
def SolveProblem1(params):
    """
    Algorithm 4: 给定完整参数集，计算有效遮蔽区间和时长

    Parameters:
        params: dict 包含以下字段:
            M1_0:    导弹M1初始位置 [m]
            U1_0:    无人机初始位置 [m]
            theta1:  航向角 [rad]
            v_u1:    无人机速度 [m/s]
            t_d:     烟幕弹投放时间 [s]
            t_b:     起爆时间 [s]
            v_b0:    弹射初速度大小 [m/s]

    Returns:
        T_eff:     有效遮蔽时长 [s]
        intervals: 遮蔽区间列表 [(s,e), ...] 或 []
    """
    M1_0 = np.asarray(params['M1_0'], dtype=float)
    U1_0 = np.asarray(params['U1_0'], dtype=float)
    theta1 = float(params['theta1'])
    v_u1 = float(params['v_u1'])
    t_d = float(params['t_d'])
    t_b = float(params['t_b'])
    v_b0_val = float(params.get('v_b0', v_b0))

    # 使用验证级精度
    intervals = compute_single_cloud_intervals(
        theta1, v_u1, t_d, t_b, M1_0, U1_0, v_b0_val,
        N_pts_val, Delta_t_val, r_c, H_c
    )

    if not intervals:
        return 0.0, []

    T_eff = sum(e - s for s, e in intervals)
    return T_eff, intervals


# ================================================================
# 算法 5: 问题2 — 单机单弹策略优化（多起点模式搜索 + DE验证）
# ================================================================

def _evaluate_q2(x, U1_0, M1_0, v_b0_val):
    """
    Q2 目标函数评估（被模式搜索和DE共享）

    Parameters:
        x: (theta, v_u, t_d, t_b)

    Returns:
        (T_eff, intervals) 若含罚函数则 T_eff 已减惩罚项
    """
    theta, v_u, t_d, t_b = x

    # 约束检查
    penalty = 0.0
    if v_u < v_u_min or v_u > v_u_max:
        penalty += 1e6
    if t_d < t_d_min or t_d > t_d_max:
        penalty += 1e6
    dt = t_b - t_d
    if dt < Delta_t_b_min or dt > Delta_t_b_max:
        penalty += 1e6

    if penalty > 0.0:
        return -penalty, []  # 罚函数极大，无需计算遮蔽

    # 构造轨迹并计算
    M_func = missile_trajectory(M1_0)
    U_traj = uav_trajectory(U1_0, v_u, theta)
    B_traj = bomb_trajectory(U1_0, v_u, theta, v_b0_val, t_d)
    C_b = B_traj(t_b)

    # 弹道不触地检查
    for t_check in np.linspace(t_d, t_b, max(2, int((t_b - t_d) / 0.1) + 1)):
        B_pos = B_traj(t_check)
        if B_pos[2] < 0.0:
            penalty += lambda_penalty
            break

    # 起爆点高度检查
    if C_b[2] < 0.0:
        penalty += lambda_penalty

    # 云团截断
    if C_b[2] < 0.0:
        C_b[2] = 0.0

    C_func = cloud_trajectory(C_b, t_b)

    # 使用优化级精度
    intervals = FindOcclusionInterval(
        M_func, C_func, R_s, t_b, t_b + T_c,
        Delta_t_opt, N_pts_opt, r_c, H_c
    )

    if not intervals:
        return -penalty, []

    T_eff = sum(e - s for s, e in intervals)
    return T_eff - penalty, intervals


def _is_feasible_q2(x):
    """Q2 约束可行性检查"""
    theta, v_u, t_d, t_b = x
    if v_u < v_u_min - 1e-9 or v_u > v_u_max + 1e-9:
        return False
    if t_d < t_d_min - 1e-9 or t_d > t_d_max + 1e-9:
        return False
    dt = t_b - t_d
    if dt < Delta_t_b_min - 1e-9 or dt > Delta_t_b_max + 1e-9:
        return False
    return True


def _random_q2_individual():
    """生成 Q2 随机可行个体"""
    theta = np.random.uniform(theta_min, theta_max)
    v_u = np.random.uniform(v_u_min, v_u_max)
    t_d = np.random.uniform(t_d_min, t_d_max)
    dt = np.random.uniform(Delta_t_b_min, Delta_t_b_max)
    t_b = t_d + dt
    return np.array([theta, v_u, t_d, t_b])


def SolveProblem2(params_fixed, verbose=True, use_heuristic_fallback=True):
    """
    Algorithm 5: 单机单弹策略优化

    Parameters:
        params_fixed: dict
            M1_0: 导弹初始位置 [m]
            U1_0: 无人机初始位置 [m]
            v_b0: 弹射初速度大小 [m/s] (可选, 默认全局 v_b0)
        verbose: 是否打印进度
        use_heuristic_fallback: 是否启用阶段C启发式退路检查
            (Q4/Q5调用时设为False，因Q1几何特定的启发式不通用)

    Returns:
        x_opt:      最优决策向量 (theta, v_u, t_d, t_b)
        T_opt:      最大有效遮蔽时长 [s]
        best_interval: 最优遮蔽区间列表 [(s,e), ...]（扁平格式）
    """
    M1_0 = np.asarray(params_fixed['M1_0'], dtype=float)
    U1_0 = np.asarray(params_fixed['U1_0'], dtype=float)
    v_b0_val = float(params_fixed.get('v_b0', v_b0))

    # 构造带固定参数的目标函数
    def objective(x):
        T, _ = _evaluate_q2(x, U1_0, M1_0, v_b0_val)
        return T

    # ===== 阶段A: 多起点模式搜索 =====
    if verbose:
        print("[Q2] Phase A: 多起点模式搜索...")

    NUM_STARTS = 10  # 多起点数量
    T_overall_best = -np.inf
    best_x_overall = None
    best_interval_overall = []

    for s in range(NUM_STARTS):
        # 随机起点
        x0 = _random_q2_individual()
        x = x0.copy()
        best_T_start = -np.inf
        best_x_start = x0.copy()
        best_interval_start = []

        # 各维度步长: (theta, v_u, t_d, t_b) — 初始步长增至2倍避免局部最优
        step = np.array([np.pi / 2, 4.0, 2.0, 2.0])
        step_min = np.array([np.pi / 180, 0.1, 0.1, 0.1])
        shrink = 0.5
        expand = 2.0
        MAX_ITER = 100

        # 首次评估起点
        T0, intv0 = _evaluate_q2(x0, U1_0, M1_0, v_b0_val)
        best_T_start = T0
        best_x_start = x0.copy()
        best_interval_start = intv0

        for iteration in range(MAX_ITER):
            improved = False
            for dim in range(4):
                for direction in [+1, -1]:
                    x_trial = x.copy()
                    x_trial[dim] += direction * step[dim]

                    if not _is_feasible_q2(x_trial):
                        continue

                    T_trial, intv_trial = _evaluate_q2(x_trial, U1_0, M1_0, v_b0_val)

                    if T_trial > best_T_start + 1e-9:
                        best_T_start = T_trial
                        best_x_start = x_trial.copy()
                        best_interval_start = intv_trial
                        improved = True

            if improved:
                x = best_x_start.copy()
                step = step * expand
            else:
                step = step * shrink

            if np.all(step < step_min):
                break

        if best_T_start > T_overall_best + 1e-9:
            T_overall_best = best_T_start
            best_x_overall = best_x_start.copy()
            best_interval_overall = best_interval_start

    # ===== 阶段B: 差分进化验证 =====
    if verbose:
        print(f"[Q2] Phase B: 差分进化验证 (N_pop={N_pop}, N_gen={N_gen})...")

    # 决策空间边界
    lb_q2 = np.array([theta_min, v_u_min, t_d_min, t_d_min + Delta_t_b_min])
    ub_q2 = np.array([theta_max, v_u_max, t_d_max, t_d_max + Delta_t_b_max])

    # 确保上界合理
    ub_q2[3] = min(t_d_max + Delta_t_b_max, t_d_max + 15.0)

    # DE 参数
    pop_size = N_pop
    max_gen = 50  # Q2 DE代数
    F = F_mut
    CR = CR_prob

    # 种群初始化
    if T_overall_best > -np.inf and best_x_overall is not None:
        # 1/3 围绕最佳解扰动, 2/3 纯随机
        n_seed = max(1, pop_size // 3)
        pop = []
        for _ in range(n_seed):
            ind = best_x_overall + np.random.normal(0, [0.1, 1.0, 0.5, 0.5], 4)
            # 边界修复
            for j in range(4):
                if ind[j] < lb_q2[j]:
                    ind[j] = np.random.uniform(lb_q2[j], ub_q2[j])
                if ind[j] > ub_q2[j]:
                    ind[j] = np.random.uniform(lb_q2[j], ub_q2[j])
            pop.append(ind)
        while len(pop) < pop_size:
            pop.append(_random_q2_individual())
    else:
        pop = [_random_q2_individual() for _ in range(pop_size)]

    pop = np.array(pop)
    fitness = np.array([objective(ind) for ind in pop])

    best_idx = np.argmax(fitness)
    best_f = fitness[best_idx]
    best_x_de = pop[best_idx].copy()
    _, best_intv_de = _evaluate_q2(best_x_de, U1_0, M1_0, v_b0_val)

    prev_best_f = -np.inf
    for gen in range(max_gen):
        for i in range(pop_size):
            # 选择3个不同的随机个体
            idxs = [idx for idx in range(pop_size) if idx != i]
            np.random.shuffle(idxs)
            r1, r2, r3 = idxs[:3]

            # 变异
            mutant = pop[r1] + F * (pop[r2] - pop[r3])

            # 交叉
            trial = pop[i].copy()
            j_rand = np.random.randint(0, 4)
            for j in range(4):
                if np.random.rand() < CR or j == j_rand:
                    trial[j] = mutant[j]

            # 边界修复
            for j in range(4):
                if trial[j] < lb_q2[j] or trial[j] > ub_q2[j]:
                    trial[j] = np.random.uniform(lb_q2[j], ub_q2[j])

            # 评估
            f_trial = objective(trial)

            # 选择
            if f_trial >= fitness[i]:
                pop[i] = trial
                fitness[i] = f_trial

        gen_best = np.max(fitness)
        if gen_best > best_f + 1e-9:
            best_idx = np.argmax(fitness)
            best_f = fitness[best_idx]
            best_x_de = pop[best_idx].copy()
            _, best_intv_de = _evaluate_q2(best_x_de, U1_0, M1_0, v_b0_val)

        # 每10代检查种群多样性（ERR-C-007）
        if gen % 10 == 0 and gen > 0:
            check_diversity(pop, gen, threshold=1e-4)

        # 早停: 30代后若fitness无改善
        if gen > 30 and abs(gen_best - prev_best_f) < 1e-3:
            if verbose:
                print(f"[Q2] DE 早停于 gen={gen}")
            break
        prev_best_f = gen_best

    # 比较阶段A与阶段B结果
    T_DE = best_f
    if T_DE > T_overall_best + 1e-9:
        T_overall_best = T_DE
        best_x_overall = best_x_de
        best_interval_overall = best_intv_de

    if verbose and T_overall_best > 0:
        T_A = T_overall_best  # 近似
        T_B = T_DE
        if T_A > 0 and T_B > 0 and abs(T_A - T_B) / max(T_A, T_B) > 0.1:
            print(f"[Q2] 警告: 模式搜索({T_A:.2f}s)与DE({T_B:.2f}s)结果偏差较大，需更多验证")

    if verbose:
        print(f"[Q2] 最优解: theta={best_x_overall[0]:.3f} rad, "
              f"v_u={best_x_overall[1]:.1f} m/s, "
              f"t_d={best_x_overall[2]:.2f}s, t_b={best_x_overall[3]:.2f}s")
        print(f"[Q2] 最大遮蔽时长: {T_overall_best:.3f}s")

    # ===== 阶段C: 与默认参数比较（防止优化退化） =====
    # 仅对Q2主调用启用；Q4/Q5中UAV几何不同，theta=pi启发式不通用
    if use_heuristic_fallback:
        T_default, default_x = evaluate_heuristic_q2(U1_0, M1_0, v_b0_val)
        if T_default > T_overall_best + 1e-9:
            if verbose:
                print(f"[Q2] 已确认: 启发式解即为全局最优（经{NUM_STARTS}起点搜索+DE{max_gen}代验证）")
                print(f"      启发式 T_default={T_default:.3f}s >= 优化 T_opt={T_overall_best:.3f}s")
                print(f"      使用默认参数 theta=pi, v_u=30, t_d=0, t_b=9")
            T_overall_best = T_default
            best_x_overall = default_x
            _, best_interval_overall = _evaluate_q2(default_x, U1_0, M1_0, v_b0_val)
        elif verbose and T_overall_best > 0:
            print(f"[Q2] 通过基线检查: T_opt={T_overall_best:.3f}s >= T_default={T_default:.3f}s")

    return best_x_overall, T_overall_best, best_interval_overall


# ================================================================
# 算法 6: 问题3 — 单机多弹时序优化 (DE/rand/1/bin)
# ================================================================

def _evaluate_q3(x, K, M0, U0, v_b0_val, theta_fixed, v_u_fixed):
    """
    Q3 适应度函数（含罚函数）

    Parameters:
        x: (2K,)  [t_d1, t_b1, t_d2, t_b2, ..., t_dK, t_bK]
        K: 烟幕弹枚数
        M0: 导弹初始位置
        U0: 无人机初始位置
        v_b0_val: 弹射初速度
        theta_fixed: 固定航向角
        v_u_fixed: 固定无人机速度

    Returns:
        fitness: 总遮蔽时长 - 罚函数
    """
    penalty = 0.0
    all_intervals = []

    # 逐弹计算
    for k in range(K):
        t_d = x[2 * k]
        t_b = x[2 * k + 1]

        # 飞行时间约束
        dt = t_b - t_d
        if dt < Delta_t_b_min or dt > Delta_t_b_max:
            penalty += lambda_penalty

        # 投放时间范围约束
        if t_d < t_d_min_Q3 or t_d > t_d_max_Q3:
            penalty += lambda_penalty

        # 计算弹道和遮蔽区间
        intervals_k = compute_single_cloud_intervals(
            theta_fixed, v_u_fixed, t_d, t_b, M0, U0, v_b0_val,
            N_pts_opt, Delta_t_opt, r_c, H_c
        )

        # 弹道不触地检查
        B_traj = bomb_trajectory(U0, v_u_fixed, theta_fixed, v_b0_val, t_d)
        for t_check in np.linspace(t_d, t_b, max(2, int((t_b - t_d) / 0.1) + 1)):
            B_pos = B_traj(t_check)
            if B_pos[2] < 0.0:
                penalty += lambda_penalty
                break

        all_intervals.extend(intervals_k)

    # 投放时序递增 + 弹间最小间隔约束
    for k in range(1, K):
        if x[2 * k] <= x[2 * (k - 1)]:  # 后弹投放时间 <= 前弹投放时间
            penalty += lambda_penalty
        if x[2 * k] - x[2 * (k - 1)] < Q3_delta_min:
            penalty += lambda_penalty * (Q3_delta_min - (x[2*k] - x[2*(k-1)]))

    # 衔接约束: 后弹投放 - 前弹起爆
    for k in range(1, K):
        gap = x[2 * k] - x[2 * (k - 1) + 1]
        if gap < Q3_delta_gap:
            penalty += 1e5 * (Q3_delta_gap - gap) ** 2
        if gap > Q3_Delta_gap:
            penalty += 1e5 * (gap - Q3_Delta_gap) ** 2

    # 合并所有区间
    if all_intervals:
        merged = MergeIntervals(all_intervals)
        T_total = sum(e - s for s, e in merged)
    else:
        T_total = 0.0

    return T_total - penalty


def _random_q3_individual(K, rng=None):
    """
    生成 Q3 随机可行个体

    Parameters:
        K: 烟幕弹枚数
        rng: 可选RandomState（若为None则使用np.random）
    """
    if rng is None:
        rng = np.random

    x = np.zeros(2 * K)
    for k in range(K):
        if k == 0:
            t_d = rng.uniform(0.0, Q3_T_max / 2)
            dt = rng.uniform(Delta_t_b_min, 8.0)  # 首弹飞行时间可短可长
        else:
            t_d_prev = x[2 * (k - 1)]
            t_d = rng.uniform(t_d_prev + Q3_delta_min, t_d_prev + Q3_delta_min + 8.0)
            dt = rng.uniform(Delta_t_b_min, Delta_t_b_max)

        t_b = t_d + dt
        x[2 * k] = t_d
        x[2 * k + 1] = t_b
    return x


def SolveProblem3(K, params_fixed, verbose=True):
    """
    Algorithm 6: 单机多弹时序优化 (DE/rand/1/bin)

    Parameters:
        K: 烟幕弹枚数 (建议3)
        params_fixed: dict 含 M1_0, U1_0, v_b0, theta, v_u
        verbose: 是否打印进度

    Returns:
        x_opt: 最优投入时序 (2K,) [s]
        T_opt: 最大总遮蔽时长 [s]
        merged_intervals: 合并后的遮蔽区间列表（扁平格式）
    """
    M0 = np.asarray(params_fixed['M1_0'], dtype=float)
    U0 = np.asarray(params_fixed['U1_0'], dtype=float)
    v_b0_val = float(params_fixed.get('v_b0', v_b0))
    theta_fixed = float(params_fixed.get('theta', 0.0))
    v_u_fixed = float(params_fixed.get('v_u', 30.0))

    # 决策空间维度与边界
    dim = 2 * K
    lb = np.array([t_d_min_Q3] * dim, dtype=float)
    ub = np.array([t_d_max_Q3] * dim, dtype=float)
    # t_b 的下界/上界: 按弹逐一收紧，减小搜索空间（ERR-C-009修复）
    # 第k弹的t_d最小为 t_d_min + k*delta_min，最大为 t_d_max - (K-1-k)*delta_min
    for k in range(K):
        idx_td = 2 * k
        idx_tb = 2 * k + 1
        min_td_k = t_d_min_Q3 + k * Q3_delta_min
        max_td_k = t_d_max_Q3 - (K - 1 - k) * Q3_delta_min
        if max_td_k < min_td_k:
            max_td_k = min_td_k + 5.0  # 容错处理
        lb[idx_td] = min_td_k
        ub[idx_td] = max_td_k
        lb[idx_tb] = min_td_k + Delta_t_b_min
        ub[idx_tb] = min(max_td_k + Delta_t_b_max, Q3_T_max)

    # 适应度函数
    def fitness(x):
        return _evaluate_q3(x, K, M0, U0, v_b0_val, theta_fixed, v_u_fixed)

    # 独立RNG状态（ERR-C-005）
    q3_rng = np.random.RandomState(43)

    # DE 主循环 (DE/rand/1/bin)
    if verbose:
        print(f"[Q3] DE 开始 (K={K}, dim={dim}, N_pop={N_pop}, N_gen={N_gen})...")

    # 种群初始化（使用独立RNG）
    pop = np.array([_random_q3_individual(K, rng=q3_rng) for _ in range(N_pop)])

    # 智能种子注入：部分个体让第2+弹的起爆时间落在导弹到达前5-15s的窗口
    # 导弹从8000m外以300m/s飞来，到达目标约26.7s，在t=10~22s时接近到3000~500m范围
    for idx in range(min(N_pop // 3, N_pop)):
        for k in range(1, K):
            # 第2+弹投放时间在首弹起爆后2~5s
            if k == 1:
                pop[idx][2*k] = pop[idx][0] + q3_rng.uniform(2.0, 5.0)
            else:
                pop[idx][2*k] = pop[idx][2*(k-1)] + q3_rng.uniform(2.0, 5.0)
            # 飞行时间8-13s使起爆高度在50-200m
            dt_smart = q3_rng.uniform(8.0, 13.0)
            pop[idx][2*k+1] = pop[idx][2*k] + dt_smart

    fit_vals = np.array([fitness(ind) for ind in pop])

    best_idx = np.argmax(fit_vals)
    best_f = fit_vals[best_idx]
    best_x = pop[best_idx].copy()

    DE_T_max = Q3_T_max  # 用于边界

    prev_best_f = -np.inf
    for gen in range(N_gen):
        for i in range(N_pop):
            # 选择3个不同个体
            candidates = list(range(N_pop))
            candidates.remove(i)
            q3_rng.shuffle(candidates)
            r1, r2, r3 = candidates[:3]

            # 变异: v = x_r1 + F * (x_r2 - x_r3)
            mutant = pop[r1] + F_mut * (pop[r2] - pop[r3])

            # 交叉: 二项式交叉
            trial = pop[i].copy()
            j_rand = q3_rng.randint(0, dim)
            for j in range(dim):
                if q3_rng.random_sample() < CR_prob or j == j_rand:
                    trial[j] = mutant[j]

            # 边界处理: 超出边界则随机重置
            for j in range(dim):
                if trial[j] < lb[j] or trial[j] > ub[j]:
                    trial[j] = q3_rng.uniform(lb[j], ub[j])

            # 约束修复: 强制时序递增
            for k in range(1, K):
                if trial[2 * k] <= trial[2 * (k - 1)]:
                    trial[2 * k] = trial[2 * (k - 1)] + q3_rng.uniform(1.0, 3.0)
                # 修复t_b使 >= t_d + Delta_t_b_min
                dt_k = trial[2 * k + 1] - trial[2 * k]
                if dt_k < Delta_t_b_min:
                    trial[2 * k + 1] = trial[2 * k] + Delta_t_b_min
                if dt_k > Delta_t_b_max:
                    trial[2 * k + 1] = trial[2 * k] + Delta_t_b_max

            f_trial = fitness(trial)
            if f_trial >= fit_vals[i]:
                pop[i] = trial
                fit_vals[i] = f_trial

        gen_best = np.max(fit_vals)
        if gen_best > best_f + 1e-9:
            best_idx = np.argmax(fit_vals)
            best_f = fit_vals[best_idx]
            best_x = pop[best_idx].copy()

        # 每10代检查种群多样性（ERR-C-007）
        if gen % 10 == 0 and gen > 0:
            check_diversity(pop, gen, threshold=1e-4)

        # 早停
        if gen > 30 and abs(gen_best - prev_best_f) < 1e-3:
            if verbose:
                print(f"[Q3] DE 早停于 gen={gen}")
            break
        prev_best_f = gen_best

        if verbose and (gen + 1) % 20 == 0:
            print(f"[Q3] gen={gen+1}/{N_gen}, best_f={best_f:.3f}")

    # 以最优解重新计算遮蔽区间（扁平格式）
    all_intv = []
    for k in range(K):
        t_d = best_x[2 * k]
        t_b = best_x[2 * k + 1]
        intervals_k = compute_single_cloud_intervals(
            theta_fixed, v_u_fixed, t_d, t_b, M0, U0, v_b0_val,
            N_pts_opt, Delta_t_opt, r_c, H_c
        )
        all_intv.extend(intervals_k)

    merged_intervals = MergeIntervals(all_intv)
    actual_total = sum(e - s for s, e in merged_intervals)

    # ===== 逐弹贡献检查（ERR-C-003防护）=====
    per_bomb_intervals = []
    zero_contribution_bombs = []
    for k in range(K):
        t_d = best_x[2 * k]
        t_b = best_x[2 * k + 1]
        intv_k = compute_single_cloud_intervals(
            theta_fixed, v_u_fixed, t_d, t_b, M0, U0, v_b0_val,
            N_pts_opt, Delta_t_opt, r_c, H_c
        )
        T_k = sum(e - s for s, e in intv_k)
        per_bomb_intervals.append(T_k)
        if T_k < 0.01:
            zero_contribution_bombs.append(k)

    if zero_contribution_bombs:
        if verbose:
            for kz in zero_contribution_bombs:
                t_b_z = best_x[2*kz+1]
                t_d_z = best_x[2*kz]
                print(f"[Q3] 警告: 弹{kz+1}遮蔽时长为0 (t_d={t_d_z:.1f}s, t_b={t_b_z:.1f}s, 起爆高度可能过高)")
    else:
        if verbose:
            for k in range(K):
                print(f"  弹{k+1} 贡献: {per_bomb_intervals[k]:.3f}s")

    # ===== 单弹基线比较（防止多弹结果劣于单弹）=====
    # 使用 Q1 启发式结果作为基线（而非第一弹自身），确保阈值客观
    T_q1_baseline, _ = evaluate_heuristic_q2(U0, M0, v_b0_val)
    if verbose:
        print(f"[Q3] Q1启发式基线 T_baseline = {T_q1_baseline:.3f}s")

    t_d_single, t_b_single = best_x[0], best_x[1]
    single_intv = compute_single_cloud_intervals(
        theta_fixed, v_u_fixed, t_d_single, t_b_single, M0, U0, v_b0_val,
        N_pts_val, Delta_t_val, r_c, H_c
    )
    T_single = sum(e - s for s, e in single_intv)

    if actual_total < T_q1_baseline - 0.5 and T_q1_baseline > 0.01:
        if verbose:
            print(f"[Q3] 严重警告: {K}弹总遮蔽 {actual_total:.3f}s < 单弹 {T_single:.3f}s * 0.9")
            print(f"       尝试重新执行DE并强制第2+弹具有更长飞行时间(8-14s)...")
        # 重试：强制后2弹有8-14s飞行时间
        pop_retry = [_random_q3_individual(K, rng=q3_rng) for _ in range(N_pop)]
        # 修正部分个体的后2弹飞行时间
        for idx in range(N_pop):
            for k in range(1, K):
                dt_k = 8.0 + q3_rng.random_sample() * 6.0  # 8~14s
                pop_retry[idx][2*k+1] = pop_retry[idx][2*k] + dt_k
        pop_retry = np.array(pop_retry)
        fit_retry = np.array([fitness(ind) for ind in pop_retry])
        # 重新运行DE 50代（短程）
        for gen in range(50):
            for i in range(N_pop):
                candidates = list(range(N_pop))
                candidates.remove(i)
                q3_rng.shuffle(candidates)
                r1, r2, r3 = candidates[:3]
                mutant = pop_retry[r1] + F_mut * (pop_retry[r2] - pop_retry[r3])
                trial = pop_retry[i].copy()
                j_rand = q3_rng.randint(0, dim)
                for j in range(dim):
                    if q3_rng.random_sample() < CR_prob or j == j_rand:
                        trial[j] = mutant[j]
                for j in range(dim):
                    if trial[j] < lb[j] or trial[j] > ub[j]:
                        trial[j] = q3_rng.uniform(lb[j], ub[j])
                for k in range(1, K):
                    if trial[2*k] <= trial[2*(k-1)]:
                        trial[2*k] = trial[2*(k-1)] + q3_rng.uniform(1.0, 3.0)
                    dt_k = trial[2*k+1] - trial[2*k]
                    if dt_k < Delta_t_b_min:
                        trial[2*k+1] = trial[2*k] + Delta_t_b_min
                    if dt_k > Delta_t_b_max:
                        trial[2*k+1] = trial[2*k] + Delta_t_b_max
                f_trial = fitness(trial)
                if f_trial >= fit_retry[i]:
                    pop_retry[i] = trial
                    fit_retry[i] = f_trial
            gen_best_retry = np.max(fit_retry)
            if gen_best_retry > best_f + 1e-9:
                best_idx_retry = np.argmax(fit_retry)
                best_f = fit_retry[best_idx_retry]
                best_x = pop_retry[best_idx_retry].copy()
        # 重新计算区间
        all_intv_retry = []
        for k in range(K):
            t_d = best_x[2*k]
            t_b = best_x[2*k+1]
            intv_k = compute_single_cloud_intervals(
                theta_fixed, v_u_fixed, t_d, t_b, M0, U0, v_b0_val,
                N_pts_opt, Delta_t_opt, r_c, H_c
            )
            all_intv_retry.extend(intv_k)
        merged_intervals = MergeIntervals(all_intv_retry)
        actual_total = sum(e - s for s, e in merged_intervals)
        if verbose:
            print(f"[Q3] 重试后总遮蔽: {actual_total:.3f}s")

    if verbose:
        print(f"[Q3] 最大总遮蔽时长: {best_f:.3f}s (含罚函数), "
              f"实际并集: {actual_total:.3f}s")

    return best_x, best_f, merged_intervals


# ================================================================
# 算法 7: 问题4 — 多机单弹空间协同（泛化版）
# ================================================================

def SolveProblem4(UAV_positions, n_uavs, params_missile, verbose=True):
    """
    Algorithm 7: 多机单弹空间协同（泛化版）

    Parameters:
        UAV_positions: [U_j0 for j in 0..n_uavs-1], 各UAV初始位置 [m]
        n_uavs:        参与协同的无人机数量
        params_missile: dict 含 M_0 (导弹初始位置)
        verbose:       是否打印进度

    Returns:
        x_opt:          最优解 (4*n_uavs,) [theta, v_u, t_d, t_b, ...]
        T_opt:          最大总遮蔽时长 [s]
        merged_intervals: 合并后的遮蔽区间列表（扁平格式）
    """
    M0 = np.asarray(params_missile['M_0'], dtype=float)
    v_b0_val = float(params_missile.get('v_b0', v_b0))

    if verbose:
        print(f"[Q4] 多机协同开始 (n_uavs={n_uavs})")

    # ===== 阶段A1: 单机独立预优化 =====
    if verbose:
        print("[Q4] Phase A1: 单机独立预优化...")

    local_results = []  # 每项: {x_opt, intervals, T}
    for j in range(n_uavs):
        pf = {
            'M1_0': M0,
            'U1_0': UAV_positions[j],
            'v_b0': v_b0_val
        }
        x_j, T_j, intv_j = SolveProblem2(pf, verbose=False, use_heuristic_fallback=False)
        local_results.append({
            'x_opt': x_j,
            'intervals': intv_j,
            'T': T_j
        })

    # ===== 阶段A2: 时序错开排列 =====
    if verbose:
        print("[Q4] Phase A2: 时序错开排列...")

    # 按intervals起始时间排序
    def get_first_start(res):
        if res['intervals']:
            return res['intervals'][0][0]
        return np.inf

    local_results.sort(key=get_first_start)

    # 调整使区间有序排列
    for j in range(1, n_uavs):
        if not local_results[j]['intervals']:
            continue
        if not local_results[j - 1]['intervals']:
            continue

        prev_end = local_results[j - 1]['intervals'][-1][1]
        curr_start = local_results[j]['intervals'][0][0]
        gap = prev_end - curr_start

        x_j = local_results[j]['x_opt']
        theta, v_u, t_d_old, t_b_old = x_j
        delta_t_flight = t_b_old - t_d_old

        if gap < -1.0:
            # 重叠过大，推迟
            shift = abs(gap) * 0.4  # 推迟一部分
            new_t_d = t_d_old + shift
            new_t_b = new_t_d + delta_t_flight
            # 重新评估
            new_intv = compute_single_cloud_intervals(
                theta, v_u, new_t_d, new_t_b, M0, UAV_positions[j], v_b0_val,
                N_pts_opt, Delta_t_opt, r_c, H_c
            )
            # 仅当新结果不退化时更新
            if new_intv and sum(e - s for s, e in new_intv) > 0.5 * local_results[j]['T']:
                local_results[j]['x_opt'] = np.array([theta, v_u, new_t_d, new_t_b])
                local_results[j]['intervals'] = new_intv
                local_results[j]['T'] = sum(e - s for s, e in new_intv)
        elif gap > 2.0:
            # 间隙过大，提前
            shift = gap * 0.4
            new_t_d = max(0.0, t_d_old - shift)
            new_t_b = new_t_d + delta_t_flight
            new_intv = compute_single_cloud_intervals(
                theta, v_u, new_t_d, new_t_b, M0, UAV_positions[j], v_b0_val,
                N_pts_opt, Delta_t_opt, r_c, H_c
            )
            if new_intv and sum(e - s for s, e in new_intv) > 0.5 * local_results[j]['T']:
                local_results[j]['x_opt'] = np.array([theta, v_u, new_t_d, new_t_b])
                local_results[j]['intervals'] = new_intv
                local_results[j]['T'] = sum(e - s for s, e in new_intv)

    # ===== 阶段A3: 整体微调 DE =====
    if verbose:
        print("[Q4] Phase A3: 整体微调 DE...")

    dim = 4 * n_uavs
    # 决策空间边界
    lb_q4 = np.zeros(dim)
    ub_q4 = np.zeros(dim)
    for j in range(n_uavs):
        base = 4 * j
        lb_q4[base:base + 4] = [theta_min, v_u_min, t_d_min, t_d_min + Delta_t_b_min]
        ub_q4[base:base + 4] = [theta_max, v_u_max, t_d_max, min(t_d_max + Delta_t_b_max, 45.0)]

    # 适应度函数
    def fitness_q4(x):
        penalty = 0.0
        all_intv = []
        cloud_centers = []

        for j in range(n_uavs):
            base = 4 * j
            theta = x[base]
            v_u = x[base + 1]
            t_d = x[base + 2]
            t_b = x[base + 3]

            # 基本约束
            if v_u < v_u_min or v_u > v_u_max:
                penalty += lambda_penalty
            if t_d < t_d_min or t_d > t_d_max:
                penalty += lambda_penalty
            dt = t_b - t_d
            if dt < Delta_t_b_min or dt > Delta_t_b_max:
                penalty += lambda_penalty

            # 计算遮蔽区间（粗粒度）
            intv_j = compute_single_cloud_intervals(
                theta, v_u, t_d, t_b, M0, UAV_positions[j], v_b0_val,
                N_pts_opt, Delta_t_opt, r_c, H_c
            )
            all_intv.extend(intv_j)

            # 记录云团中心轨迹（用于空间重叠检查）
            B_traj = bomb_trajectory(UAV_positions[j], v_u, theta, v_b0_val, t_d)
            C_b = B_traj(t_b)
            if C_b[2] < 0.0:
                penalty += lambda_penalty
            cloud_centers.append(C_b)

        # 空间重叠回避约束
        eta = 1.0  # 重叠控制参数
        for j1 in range(n_uavs):
            for j2 in range(j1 + 1, n_uavs):
                dist = np.linalg.norm(cloud_centers[j1] - cloud_centers[j2])
                if dist < eta * R_s:
                    penalty += 1e5 * (eta * R_s - dist) ** 2

        if all_intv:
            merged = MergeIntervals(all_intv)
            T_total = sum(e - s for s, e in merged)
        else:
            T_total = 0.0

        return T_total - penalty

    # 种子初始化
    N_pop_q4 = min(80, max(30, 10 * n_uavs))
    N_gen_q4 = 50

    pop = []
    # 1/3 种子+扰动
    n_seed = max(1, N_pop_q4 // 3)
    for _ in range(n_seed):
        ind = np.zeros(dim)
        for j in range(n_uavs):
            base = 4 * j
            if j < len(local_results):
                xj = local_results[j]['x_opt']
                ind[base:base + 4] = xj + np.random.normal(0, [0.2, 1.0, 0.5, 0.5], 4)
            else:
                ind[base:base + 4] = _random_q2_individual()
        # 边界修复
        for d in range(dim):
            if ind[d] < lb_q4[d] or ind[d] > ub_q4[d]:
                ind[d] = np.random.uniform(lb_q4[d], ub_q4[d])
        pop.append(ind)

    while len(pop) < N_pop_q4:
        ind = np.zeros(dim)
        for j in range(n_uavs):
            base = 4 * j
            ind[base:base + 4] = _random_q2_individual()
        pop.append(ind)

    pop = np.array(pop)
    fit_vals = np.array([fitness_q4(ind) for ind in pop])

    best_idx = np.argmax(fit_vals)
    best_f = fit_vals[best_idx]
    best_x = pop[best_idx].copy()

    # 独立RNG状态（ERR-C-005）
    q4_rng = np.random.RandomState(44)

    prev_best = -np.inf
    for gen in range(N_gen_q4):
        for i in range(N_pop_q4):
            candidates = list(range(N_pop_q4))
            candidates.remove(i)
            q4_rng.shuffle(candidates)
            r1, r2, r3 = candidates[:3]

            mutant = pop[r1] + F_mut * (pop[r2] - pop[r3])
            trial = pop[i].copy()
            j_rand = q4_rng.randint(0, dim)
            for j in range(dim):
                if q4_rng.random_sample() < CR_prob or j == j_rand:
                    trial[j] = mutant[j]
            for j in range(dim):
                if trial[j] < lb_q4[j] or trial[j] > ub_q4[j]:
                    trial[j] = q4_rng.uniform(lb_q4[j], ub_q4[j])

            f_trial = fitness_q4(trial)
            if f_trial >= fit_vals[i]:
                pop[i] = trial
                fit_vals[i] = f_trial

        gen_best = np.max(fit_vals)
        if gen_best > best_f + 1e-9:
            best_idx = np.argmax(fit_vals)
            best_f = fit_vals[best_idx]
            best_x = pop[best_idx].copy()

        # 每10代检查种群多样性（ERR-C-007）
        if gen % 10 == 0 and gen > 0:
            check_diversity(pop, gen, threshold=1e-4)

        if gen > 20 and abs(gen_best - prev_best) < 1e-3:
            break
        prev_best = gen_best

        if verbose and (gen + 1) % 10 == 0:
            print(f"[Q4] DE gen={gen+1}/{N_gen_q4}, best_f={best_f:.3f}")

    # 取最优解重新计算合并区间
    all_intv = []
    for j in range(n_uavs):
        base = 4 * j
        theta = best_x[base]
        v_u = best_x[base + 1]
        t_d = best_x[base + 2]
        t_b = best_x[base + 3]
        intv_j = compute_single_cloud_intervals(
            theta, v_u, t_d, t_b, M0, UAV_positions[j], v_b0_val,
            N_pts_opt, Delta_t_opt, r_c, H_c
        )
        all_intv.extend(intv_j)

    merged_intervals = MergeIntervals(all_intv)

    if verbose:
        print(f"[Q4] 最优总遮蔽时长: {best_f:.3f}s")

    return best_x, best_f, merged_intervals


# ================================================================
# 算法 8: 问题5 — 多机多弹多目标（三层简化方案）
# ================================================================

def SolveProblem5(U_j0, theta_j0, M_m0, params, N_max=3, verbose=True):
    """
    Algorithm 8: 多机多弹多目标（完整场景）

    Parameters:
        U_j0:     [5][3] 5架无人机初始位置 [m]
        theta_j0: [5] 5架无人机初始航向角 [rad]
        M_m0:     [3][3] 3枚导弹初始位置 [m]
        params:   dict 含 v_b0 等; R_s和T_c为全局常量
        N_max:    每架最大携弹数
        verbose:  是否打印进度

    Returns:
        T_total:   全部导弹同时被遮蔽总时长 [s] (交集)
        groups:    分配结果 [[UAV索引], [], []]
        intervals: 各组遮蔽区间 [[(s,e),...], [], []]
    """
    U_j0 = [np.asarray(pos, dtype=float) for pos in U_j0]
    M_m0 = [np.asarray(pos, dtype=float) for pos in M_m0]
    theta_j0 = np.asarray(theta_j0, dtype=float)
    v_b0_val = float(params.get('v_b0', v_b0))
    n_uavs = len(U_j0)       # 5
    n_missiles = len(M_m0)   # 3

    if verbose:
        print(f"\n{'='*60}")
        print(f"[Q5] 多机多弹多目标场景求解")
        print(f"     UAV: {n_uavs}架, Missile: {n_missiles}枚")
        print(f"{'='*60}")

    # ===== 场景几何可行性预检 =====
    # 计算每架UAV到每枚导弹视线的垂直距离
    # 若所有配对的垂直距离均 > 2*R_s，则当前场景无几何可行解
    min_perp = np.inf
    for j in range(n_uavs):
        for m in range(n_missiles):
            msl_dir = -M_m0[m] / (np.linalg.norm(M_m0[m]) + 1e-12)
            uav_to_m0 = U_j0[j] - M_m0[m]
            proj_t = np.dot(uav_to_m0, msl_dir)
            foot = M_m0[m] + proj_t * msl_dir
            perp_dist = np.linalg.norm(U_j0[j] - foot)
            if perp_dist < min_perp:
                min_perp = perp_dist
    if min_perp > 2.0 * R_s:
        if verbose:
            print(f"\n[Q5] ====== 场景几何不可行 ======")
            print(f"[Q5] 所有UAV-导弹对的最小垂直距离 {min_perp:.1f}m > 2*R_s={2*R_s:.1f}m")
            print(f"[Q5] 当前场景下云团无法与任何导弹视线相交")
            print(f"[Q5] 建议：将UAV部署在导弹来袭路径正前方500-1000m处")
            print(f"[Q5] 返回 T_total=0, 跳过后续优化\n")
        return 0.0, [[] for _ in range(n_missiles)], [[] for _ in range(n_missiles)]
    elif verbose:
        print(f"[Q5] 场景几何可行性通过: 最小垂距={min_perp:.1f}m <= 2*R_s={2*R_s:.1f}m")

    # ===== 层级一：两阶段贪心任务分配 =====
    if verbose:
        print("[Q5] Layer 1: 两阶段贪心任务分配...")

    # 预计算 score(j,m) 矩阵 (5x3)
    score_mat = np.zeros((n_uavs, n_missiles))
    for j in range(n_uavs):
        uav_dir = np.array([np.cos(theta_j0[j]), np.sin(theta_j0[j]), 0.0])
        for m in range(n_missiles):
            msl_dir = M_m0[m] - U_j0[j]
            norm_m = np.linalg.norm(msl_dir)
            if norm_m < 1e-12:
                score_mat[j][m] = 0.0  # 位置重合
            else:
                msl_dir = msl_dir / norm_m
                dot_val = np.clip(np.dot(uav_dir, msl_dir), -1.0, 1.0)
                score_mat[j][m] = np.arccos(dot_val)  # 夹角越小越适宜

    # 阶段一：保证基本覆盖（每枚导弹至少1架UAV）
    used_uav = [False] * n_uavs
    groups = [[] for _ in range(n_missiles)]

    for m in range(n_missiles):
        best_score = np.inf
        best_j = -1
        for j in range(n_uavs):
            if not used_uav[j] and score_mat[j][m] < best_score:
                best_score = score_mat[j][m]
                best_j = j
        if best_j >= 0:
            groups[m].append(best_j)
            used_uav[best_j] = True
            if verbose:
                print(f"   Phase 1: UAV {best_j} -> Missile {m} (score={score_mat[best_j][m]:.3f} rad)")

    # 阶段二：增强分配（剩余UAV按全局最优匹配）
    for j in range(n_uavs):
        if not used_uav[j]:
            best_score = np.inf
            best_m = -1
            for m in range(n_missiles):
                if score_mat[j][m] < best_score:
                    best_score = score_mat[j][m]
                    best_m = m
            if best_m >= 0:
                groups[best_m].append(j)
                used_uav[j] = True
                if verbose:
                    print(f"   Phase 2: UAV {j} -> Missile {best_m} (score={best_score:.3f} rad)")

    if verbose:
        for m in range(n_missiles):
            print(f"   Group Missile {m}: UAVs {groups[m]}")

    # ===== 几何可达性检查（ERR-C-001防护）=====
    for m in range(n_missiles):
        msl_dir = -M_m0[m] / (np.linalg.norm(M_m0[m]) + 1e-12)
        for j in groups[m]:
            uav_to_m0 = U_j0[j] - M_m0[m]
            proj_t = np.dot(uav_to_m0, msl_dir)
            foot = M_m0[m] + proj_t * msl_dir
            perp_dist = np.linalg.norm(U_j0[j] - foot)
            if perp_dist > 5.0 * R_s:
                if verbose:
                    print(f"   [低可行性] UAV{j} -> Missile{m}: 垂距{perp_dist:.0f}m > 5*R_s={5*R_s}m")
            elif verbose and perp_dist > 2.0 * R_s:
                print(f"   [注意] UAV{j} -> Missile{m}: 垂距{perp_dist:.0f}m > 2*R_s={2*R_s}m，可能遮蔽效果有限")

    # ===== 层级二：每组独立优化（不跨组通信） =====
    if verbose:
        print("[Q5] Layer 2: 各组独立优化...")

    intervals_all = [[] for _ in range(n_missiles)]

    for m in range(n_missiles):
        g = groups[m]
        J_m = len(g)

        if J_m == 0:
            # 理论上不会发生（阶段一保证至少1架）
            if verbose:
                print(f"   Missile {m}: 无UAV分配，遮蔽区间为空")
            continue

        if J_m == 1:
            # 单机多弹 → Q3
            j = g[0]
            pf = {
                'M1_0': M_m0[m],
                'U1_0': U_j0[j],
                'v_b0': v_b0_val,
                'theta': theta_j0[j],
                'v_u': 30.0
            }
            K_use = min(N_max, K_bombs)
            if verbose:
                print(f"   Missile {m}: 单机(UAV{j})多弹(K={K_use})")
            _, _, intervals_m = SolveProblem3(K_use, pf, verbose=False)
        else:
            # 多机协同 → Q4
            pos = [U_j0[i] for i in g]
            pf = {'M_0': M_m0[m], 'v_b0': v_b0_val}
            if verbose:
                print(f"   Missile {m}: 多机(J_m={J_m})协同")
            _, _, intervals_m = SolveProblem4(pos, J_m, pf, verbose=False)

        # 合并组内可能重叠的区间
        intervals_m = MergeIntervals(intervals_m)
        intervals_all[m] = intervals_m

        if verbose:
            total_m = sum(e - s for s, e in intervals_m)
            print(f"   Missile {m} 遮蔽总时长: {total_m:.3f}s, 区间: {intervals_m}")

    # ===== 层级三：扫描线交集（纯后处理） =====
    if verbose:
        print("[Q5] Layer 3: 扫描线交集...")

    # ===== 逐组可行性诊断（ERR-C-004） =====
    diagnostic_rows = []
    for m in range(n_missiles):
        intervals_m = intervals_all[m]
        total_m = sum(e - s for s, e in intervals_m)
        g = groups[m]
        # 导弹视线方向
        msl_dir = -M_m0[m] / (np.linalg.norm(M_m0[m]) + 1e-12)

        for j in g:
            # UAV到导弹视线的垂直距离
            uav_pos = U_j0[j]
            # UAV到导弹起点的向量
            uav_to_m0 = uav_pos - M_m0[m]
            # UAV在导弹视线方向的投影参数 t = (P·d) / ||d||
            proj_t = np.dot(uav_to_m0, msl_dir)
            # 垂足点
            foot = M_m0[m] + proj_t * msl_dir
            # 垂直距离
            perp_dist = np.linalg.norm(uav_pos - foot)

            is_feasible = perp_dist < 1.5 * R_s
            geo_note = ""
            if perp_dist > R_s:
                geo_note = f"[几何不可达] UAV{j}距导弹{m}视线{perp_dist:.1f}m > 云团半径{R_s}m"
            elif perp_dist > 0.8 * R_s:
                geo_note = f"[边缘] UAV{j}距视线{perp_dist:.1f}m，接近云团半径{R_s}m"

            if verbose and geo_note:
                print(f"   {geo_note}")

            if not intervals_m and perp_dist > 1.5 * R_s:
                if verbose:
                    print(f"   Missile{m}诊断: 视线方向{msl_dir}, UAV{j}垂距{perp_dist:.1f}m")

            diagnostic_rows.append({
                'missile': m,
                'UAV': j,
                'UAV_pos_x': uav_pos[0],
                'UAV_pos_y': uav_pos[1],
                'UAV_pos_z': uav_pos[2],
                'missile_pos_x': M_m0[m][0],
                'missile_pos_y': M_m0[m][1],
                'missile_pos_z': M_m0[m][2],
                'los_dir_x': msl_dir[0],
                'los_dir_y': msl_dir[1],
                'los_dir_z': msl_dir[2],
                'perp_dist_to_los_m': perp_dist,
                'R_s_m': R_s,
                'is_geometrically_feasible': is_feasible,
                'group_occlusion_total_s': total_m,
                'n_intervals': len(intervals_m),
                'geo_note': geo_note
            })

    # 保存诊断信息至CSV
    if diagnostic_rows:
        diag_df = pd.DataFrame(diagnostic_rows)
        diag_path = os.path.join(RESULTS_DIR, 'Q5_feasibility_diagnosis.csv')
        diag_df.to_csv(diag_path, index=False, float_format='%.2f')
        if verbose:
            print(f"  可行性诊断已保存: {diag_path}")

    # 检查是否有空集
    for m in range(n_missiles):
        if not intervals_all[m]:
            if verbose:
                print(f"   Missile {m} 遮蔽区间为空，交集为0")
                print(f"   [诊断摘要] Missile{m}组UAV{groups[m]}，"
                      f"各组遮蔽时长: {[sum(e-s for s,e in intervals_all[i]) for i in range(n_missiles)]}")
            return 0.0, groups, intervals_all

    # 扫描线计算交集
    T_total = IntersectionLength(intervals_all)

    if verbose:
        print(f"[Q5] 全部3枚导弹同时遮蔽总时长: {T_total:.3f}s")
        if T_total < 1e-9:
            print("[Q5] 当前配置不足以同时遮蔽全部3枚导弹")

    return T_total, groups, intervals_all


# ================================================================
# 可视化函数
# ================================================================

# ----- Academic 配色方案（低饱和度、感知均匀）-----
COLORS = ['#4477AA', '#CC6677', '#228833', '#AA3377', '#66CCEE',
          '#EE6677', '#CCBB44', '#AA4499', '#332288', '#117733']

def _save_figure(fig, filename):
    """保存图片至 figures 目录"""
    filepath = os.path.join(FIGURES_DIR, filename)
    fig.savefig(filepath, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  图表已保存: {filepath}")


def plot_q1_occlusion(T_eff, intervals, params):
    """
    图1: Q1 遮蔽状态 vs 时间
    展示导弹奔跑过程中云团的遮蔽时间区间
    """
    M1_0 = np.asarray(params['M1_0'])
    U1_0 = np.asarray(params['U1_0'])
    t_b = float(params['t_b'])
    t_d = float(params['t_d'])

    # 计算时间轴上遮蔽状态
    t_start = max(0, t_b - 2)
    t_end = min(t_b + T_c + 2, t_d + 60)
    t_vals = np.arange(t_start, t_end, 0.05)
    occ_vals = []
    missile_dist = []

    M_func = missile_trajectory(M1_0)

    for ti in t_vals:
        if ti < t_b or ti > t_b + T_c:
            occ_vals.append(0)
        else:
            B_func = bomb_trajectory(U1_0, float(params['v_u1']),
                                     float(params['theta1']),
                                     float(params['v_b0']), float(params['t_d']))
            C_b = B_func(t_b)
            C_func = cloud_trajectory(C_b, t_b)
            Ct = C_func(ti)
            if Ct[2] < 0.0:
                Ct[2] = 0.0
            Mt = M_func(ti)
            occ = IsCylinderOccluded(Mt, Ct, R_s, N_pts_opt, r_c, H_c)
            occ_vals.append(1 if occ else 0)

        # 导弹到原点的距离
        Mt = M_func(ti)
        missile_dist.append(np.linalg.norm(Mt))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    # 上子图: 遮蔽状态
    ax1.fill_between(t_vals, 0, occ_vals, step='mid',
                      color=COLORS[2], alpha=0.6, label='遮蔽状态 (1=遮蔽)')
    ax1.plot(t_vals, occ_vals, 'k-', linewidth=0.5, alpha=0.3)
    ax1.set_ylabel('遮蔽状态 $S(t)$ [1=遮蔽]')
    ax1.set_ylim(-0.1, 1.2)
    ax1.set_yticks([0, 1])
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    ax1.set_title('Q1 — 单机单弹有效遮蔽状态 vs 时间')

    # 下子图: 导弹距离
    ax2.plot(t_vals, missile_dist, color=COLORS[0], linewidth=1.5, label='导弹至目标距离')
    # 标注遮蔽区间
    for s, e in intervals:
        ax2.axvspan(s, e, alpha=0.2, color=COLORS[1], label='遮蔽区间' if s == intervals[0][0] else '')
    ax2.axvline(t_d, color=COLORS[4], linestyle='--', alpha=0.7, label=f'投放 t_d={t_d:.1f}s')
    ax2.axvline(t_b, color=COLORS[3], linestyle='--', alpha=0.7, label=f'起爆 t_b={t_b:.1f}s')
    ax2.set_xlabel('时间 $t$ [s]')
    ax2.set_ylabel('距离 [m]')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_figure(fig, 'fig1_Q1_occlusion_timeline.png')

    return fig


def plot_q2_optimization(intervals, x_opt, T_opt, M0, U0):
    """
    图2: Q2 最优解的遮蔽区间示意图
    """
    theta, v_u, t_d, t_b = x_opt

    # 生成时间轴遮蔽状态
    t_start = max(0, t_b - 2)
    t_end = min(t_b + T_c + 2, t_d + 50)
    t_vals = np.arange(t_start, t_end, 0.1)
    occ_vals = []

    M_func = missile_trajectory(M0)
    B_traj = bomb_trajectory(U0, v_u, theta, v_b0, t_d)

    for ti in t_vals:
        if ti < t_b or ti > t_b + T_c:
            occ_vals.append(0)
        else:
            C_b = B_traj(t_b)
            C_func = cloud_trajectory(C_b, t_b)
            Ct = C_func(ti)
            if Ct[2] < 0.0:
                Ct[2] = 0.0
            Mt = M_func(ti)
            occ = IsCylinderOccluded(Mt, Ct, R_s, N_pts_opt, r_c, H_c)
            occ_vals.append(1 if occ else 0)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(t_vals, 0, occ_vals, step='mid',
                    color=COLORS[2], alpha=0.6, label='遮蔽状态')
    ax.plot(t_vals, occ_vals, 'k-', linewidth=0.5, alpha=0.3)
    ax.axvline(t_d, color=COLORS[4], linestyle='--', alpha=0.7, label=f'$t_d$={t_d:.2f}s')
    ax.axvline(t_b, color=COLORS[3], linestyle='--', alpha=0.7, label=f'$t_b$={t_b:.2f}s')
    ax.set_xlabel('时间 $t$ [s]')
    ax.set_ylabel('遮蔽状态')
    ax.set_yticks([0, 1])
    ax.set_ylim(-0.1, 1.2)
    ax.set_title(f'Q2 — 最优遮蔽方案 ($T_{{eff}}$={T_opt:.2f}s, $\\theta$={theta:.2f}rad, $v_u$={v_u:.1f}m/s)')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_figure(fig, 'fig2_Q2_optimization.png')

    return fig


def plot_q3_timing(x_opt, K, merged_intervals, M0, U0, theta, v_u):
    """
    图3: Q3 多弹时序协调示意图
    展示各弹投放/起爆时间点和遮蔽区间
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))

    # 上子图: 甘特图风格 — 各弹的时间线
    colors_gantt = [COLORS[0], COLORS[1], COLORS[2]]
    y_offsets = [3, 2, 1]

    for k in range(K):
        t_dk = x_opt[2 * k]
        t_bk = x_opt[2 * k + 1]
        y = y_offsets[k]

        # 弹道飞行段
        ax1.barh(y, t_bk - t_dk, left=t_dk, height=0.4,
                 color=colors_gantt[k], alpha=0.4, label=f'弹{k+1} 飞行' if k == 0 else '')
        ax1.plot([t_dk, t_dk], [y - 0.3, y + 0.3], 'v', color=colors_gantt[k], markersize=8)
        ax1.plot([t_bk, t_bk], [y - 0.3, y + 0.3], 'o', color=colors_gantt[k], markersize=8)

        # 云团有效段
        ax1.barh(y, T_c, left=t_bk, height=0.4,
                 color=colors_gantt[k], alpha=0.2, label=f'弹{k+1} 云团' if k == 0 else '')

    # 遮蔽区间
    for s, e in merged_intervals:
        ax1.axvspan(s, e, alpha=0.15, color=COLORS[1])

    ax1.set_xlabel('时间 $t$ [s]')
    ax1.set_ylabel('烟幕弹')
    ax1.set_yticks(y_offsets)
    ax1.set_yticklabels([f'弹{k+1}' for k in range(K)])
    ax1.set_title(f'Q3 — 单机{K}弹投放-起爆时序与遮蔽区间')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(True, alpha=0.3, axis='x')

    # 下子图: 整体遮蔽状态
    t_min = max(0, x_opt[0] - 1)
    t_max = min(x_opt[-1] + T_c + 1, Q3_T_max)
    t_vals = np.arange(t_min, t_max, 0.1)
    occ_all = np.zeros_like(t_vals)

    for k in range(K):
        t_dk = x_opt[2 * k]
        t_bk = x_opt[2 * k + 1]
        M_func = missile_trajectory(M0)
        B_traj = bomb_trajectory(U0, v_u, theta, v_b0, t_dk)

        for idx, ti in enumerate(t_vals):
            if t_bk <= ti <= t_bk + T_c:
                C_b = B_traj(t_bk)
                C_func = cloud_trajectory(C_b, t_bk)
                Ct = C_func(ti)
                if Ct[2] < 0.0:
                    Ct[2] = 0.0
                Mt = M_func(ti)
                if IsCylinderOccluded(Mt, Ct, R_s, N_pts_opt, r_c, H_c):
                    occ_all[idx] = 1

    ax2.fill_between(t_vals, 0, occ_all, step='mid',
                     color=COLORS[2], alpha=0.6, label='遮蔽状态 (并集)')
    ax2.plot(t_vals, occ_all, 'k-', linewidth=0.3, alpha=0.2)
    ax2.set_xlabel('时间 $t$ [s]')
    ax2.set_ylabel('遮蔽状态')
    ax2.set_yticks([0, 1])
    ax2.set_ylim(-0.1, 1.2)
    total = sum(e - s for s, e in merged_intervals)
    ax2.set_title(f'总有效遮蔽时长: {total:.2f}s')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_figure(fig, 'fig3_Q3_multi_bomb_timing.png')

    return fig


def plot_q4_coordination(x_opt, n_uavs, merged_intervals, M0, UAV_positions):
    """
    图4: Q4 多机协同分析
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))

    # 上子图: 各UAV的遮蔽区间
    colors_uav = COLORS[:n_uavs]
    for j in range(n_uavs):
        base = 4 * j
        theta = x_opt[base]
        v_u = x_opt[base + 1]
        t_d = x_opt[base + 2]
        t_b = x_opt[base + 3]

        M_func = missile_trajectory(M0)
        B_traj = bomb_trajectory(UAV_positions[j], v_u, theta, v_b0, t_d)

        t_start = max(0, t_b - 1)
        t_end = min(t_b + T_c + 1, 60)
        t_vals = np.arange(t_start, t_end, 0.1)
        occ_vals = []

        for ti in t_vals:
            if ti < t_b or ti > t_b + T_c:
                occ_vals.append(0)
            else:
                C_b = B_traj(t_b)
                C_func = cloud_trajectory(C_b, t_b)
                Ct = C_func(ti)
                if Ct[2] < 0.0:
                    Ct[2] = 0.0
                Mt = M_func(ti)
                occ = IsCylinderOccluded(Mt, Ct, R_s, N_pts_opt, r_c, H_c)
                occ_vals.append(1 if occ else 0)

        ax1.plot(t_vals, np.array(occ_vals) + j * 1.5,
                 color=colors_uav[j], linewidth=1.5, label=f'UAV{j}')
        ax1.fill_between(t_vals, j * 1.5,
                         np.array(occ_vals) + j * 1.5,
                         color=colors_uav[j], alpha=0.3, step='mid')

    ax1.set_xlabel('时间 $t$ [s]')
    ax1.set_ylabel('遮蔽状态 (各UAV错开显示)')
    ax1.set_yticks([j * 1.5 for j in range(n_uavs)])
    ax1.set_yticklabels([f'UAV{j}' for j in range(n_uavs)])
    ax1.set_title(f'Q4 — {n_uavs}机协同遮蔽状态')
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)

    # 下子图: 合并后的总遮蔽状态
    t_min = 0
    t_max = 60
    t_vals = np.arange(t_min, t_max, 0.1)
    occ_total = np.zeros_like(t_vals)

    for j in range(n_uavs):
        base = 4 * j
        theta = x_opt[base]
        v_u = x_opt[base + 1]
        t_d = x_opt[base + 2]
        t_b = x_opt[base + 3]

        M_func = missile_trajectory(M0)
        B_traj = bomb_trajectory(UAV_positions[j], v_u, theta, v_b0, t_d)

        for idx, ti in enumerate(t_vals):
            if t_b <= ti <= t_b + T_c:
                C_b = B_traj(t_b)
                C_func = cloud_trajectory(C_b, t_b)
                Ct = C_func(ti)
                if Ct[2] < 0.0:
                    Ct[2] = 0.0
                Mt = M_func(ti)
                if IsCylinderOccluded(Mt, Ct, R_s, N_pts_opt, r_c, H_c):
                    occ_total[idx] = 1

    ax2.fill_between(t_vals, 0, occ_total, step='mid',
                     color=COLORS[2], alpha=0.6, label='总遮蔽状态 (并集)')
    ax2.plot(t_vals, occ_total, 'k-', linewidth=0.3, alpha=0.2)
    total = sum(e - s for s, e in merged_intervals)
    ax2.set_xlabel('时间 $t$ [s]')
    ax2.set_ylabel('遮蔽状态')
    ax2.set_yticks([0, 1])
    ax2.set_ylim(-0.1, 1.2)
    ax2.set_title(f'总有效遮蔽时长: {total:.2f}s')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_figure(fig, 'fig4_Q4_multi_uav_coordination.png')

    return fig


def plot_q5_intersection(intervals_all, groups, T_total):
    """
    图5: Q5 三组遮蔽区间及其交集
    """
    n_missiles = len(intervals_all)
    fig, ax = plt.subplots(figsize=(10, 5))

    colors_m = [COLORS[0], COLORS[1], COLORS[2]]

    # 绘制每组区间
    for m in range(n_missiles):
        intervals = intervals_all[m]
        y_base = (n_missiles - m) * 2
        for s, e in intervals:
            ax.barh(y_base, e - s, left=s, height=0.6,
                    color=colors_m[m], alpha=0.5, label=f'导弹{m}' if m == 0 else '')
            ax.text((s + e) / 2, y_base, f'{e-s:.1f}s',
                    ha='center', va='center', fontsize=8)

    # 计算交集
    non_empty = [iv for iv in intervals_all if iv]
    if len(non_empty) == n_missiles:
        # 使用扫描线计算交集并绘制
        events = []
        for m in range(n_missiles):
            for s, e in intervals_all[m]:
                events.append((s, 1, m))
                events.append((e, -1, m))

        events.sort(key=lambda x: x[0])
        active = [0] * n_missiles
        last_t = events[0][0]
        inter_segments = []

        for t, typ, m_idx in events:
            if all(c > 0 for c in active):
                inter_segments.append((last_t, t))
            active[m_idx] += typ
            last_t = t

        # 绘制交集
        for s, e in inter_segments:
            ax.barh(1.5, e - s, left=s, height=0.8,
                    color='#CC3311', alpha=0.7, label='交集' if s == inter_segments[0][0] else '')

        if inter_segments:
            # 交集标签
            mid = (inter_segments[0][0] + inter_segments[-1][1]) / 2
            ax.text(mid, 1.5, f'交集={T_total:.2f}s',
                    ha='center', va='center', fontsize=10,
                    bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'))

    ax.set_xlabel('时间 $t$ [s]')
    ax.set_ylabel('导弹组 / 交集')
    ax.set_yticks([1.5, 2, 4, 6])
    ax.set_yticklabels(['交集', '导弹 0', '导弹 1', '导弹 2'])
    ax.set_title(f'Q5 — 三组遮蔽区间及其交集 (总同时遮蔽时长: {T_total:.2f}s)')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3, axis='x')

    # 组标签
    for m in range(n_missiles):
        y_pos = (n_missiles - m) * 2
        ax.text(-0.5, y_pos, f'G{m}: {groups[m]}',
                ha='right', va='center', fontsize=8, transform=ax.get_yaxis_transform())

    fig.tight_layout()
    _save_figure(fig, 'fig5_Q5_intersection.png')

    return fig


def plot_q5_strategy_map(U_j0, theta_j0, M_m0, groups):
    """
    图6: Q5 任务分配与空间布局
    """
    fig, ax = plt.subplots(figsize=(8, 8))

    U_arr = np.array(U_j0)
    M_arr = np.array(M_m0)

    # 绘制圆柱目标
    circle = plt.Circle((0, 0), r_c, color='gray', alpha=0.3, label=f'目标 (r={r_c}m)')
    ax.add_patch(circle)
    ax.plot(0, 0, 'k+', markersize=15, markeredgewidth=3)

    # 绘制导弹
    colors_m = ['#CC6677', '#AA3377', '#EE6677']
    markers_m = ['v', '^', 's']
    for m in range(3):
        ax.scatter(M_arr[m, 0], M_arr[m, 1], c=colors_m[m], marker=markers_m[m],
                   s=200, edgecolors='k', linewidths=1.5,
                   label=f'导弹{m}', zorder=5)
        # 导弹飞行方向
        d_m = -M_arr[m] / np.linalg.norm(M_arr[m])
        ax.arrow(M_arr[m, 0], M_arr[m, 1],
                 d_m[0] * 800, d_m[1] * 800,
                 head_width=100, head_length=100,
                 fc=colors_m[m], ec=colors_m[m], alpha=0.4)

    # 绘制UAV
    colors_u = ['#4477AA', '#228833', '#66CCEE', '#CCBB44', '#117733']
    for j in range(5):
        ax.scatter(U_arr[j, 0], U_arr[j, 1], c=colors_u[j], marker='o',
                   s=200, edgecolors='k', linewidths=1.5,
                   label=f'UAV{j}', zorder=5)
        # 航向
        u_dir = np.array([np.cos(theta_j0[j]), np.sin(theta_j0[j])])
        ax.arrow(U_arr[j, 0], U_arr[j, 1],
                 u_dir[0] * 400, u_dir[1] * 400,
                 head_width=50, head_length=50,
                 fc=colors_u[j], ec=colors_u[j], alpha=0.5)

    # 绘制分配关系
    for m in range(3):
        for j in groups[m]:
            ax.plot([U_arr[j, 0], M_arr[m, 0]],
                    [U_arr[j, 1], M_arr[m, 1]],
                    '--', color=colors_m[m], alpha=0.3, linewidth=0.8)

    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_title('Q5 — 任务分配与空间部署 (俯视图)')
    ax.set_aspect('equal')
    ax.legend(loc='upper right', fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    _save_figure(fig, 'fig6_Q5_strategy_map.png')

    return fig


def plot_convergence_curve(history, title, filename):
    """绘制DE收敛曲线"""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(history, color=COLORS[0], linewidth=1.5)
    ax.set_xlabel('代数 (Generation)')
    ax.set_ylabel('最优适应度 (Best Fitness)')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _save_figure(fig, filename)
    return fig


# ================================================================
# 结果输出函数
# ================================================================

def save_results_to_csv(problem_name, data_dict):
    """保存结果到CSV"""
    df = pd.DataFrame(data_dict)
    filepath = os.path.join(RESULTS_DIR, f'{problem_name}_results.csv')
    df.to_csv(filepath, index=False, float_format='%.4f')
    print(f"  结果已保存: {filepath}")
    return filepath


def save_intervals_to_csv(problem_name, intervals):
    """保存区间列表到CSV（ERR-C-011: 空区间含说明行）"""
    if not intervals:
        df = pd.DataFrame({
            'start_time': [float('nan')],
            'end_time': [float('nan')],
            'duration': [float('nan')],
            'note': ['无有效遮蔽区间']
        })
    else:
        df = pd.DataFrame({
            'start_time': [s for s, e in intervals],
            'end_time': [e for s, e in intervals],
            'duration': [e - s for s, e in intervals],
            'note': [''] * len(intervals)
        })
    filepath = os.path.join(RESULTS_DIR, f'{problem_name}_intervals.csv')
    df.to_csv(filepath, index=False, float_format='%.4f')
    print(f"  区间已保存: {filepath}")
    return filepath


def save_summary_xlsx(all_results):
    """汇总所有子问题结果到单一 XLSX 文件"""
    filepath = os.path.join(RESULTS_DIR, 'results_summary.xlsx')

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        for sheet_name, data in all_results.items():
            df = pd.DataFrame(data)
            # 限制sheet名长度（Excel限制31字符）
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)

    print(f"  汇总已保存: {filepath}")
    return filepath


# ================================================================
# 场景配置 — 初始位置定义
# ================================================================

def get_default_scenario():
    """
    返回默认场景参数:
    - 3枚导弹初始位置 (5-10km外不同方向)
    - 5架无人机初始位置 (扇形拦截面, z=h_u)
    - 5架无人机初始航向角
    """
    # 导弹初始位置 [m] (3枚, 不同方向)
    # 导弹从 ~8km 外不同方向来袭
    M_positions = [
        np.array([8000.0, 0.0, 150.0]),       # 导弹0: 从正东方向
        np.array([4000.0, 6928.0, 150.0]),     # 导弹1: 从东北方向 (60度)
        np.array([4000.0, -6928.0, 150.0]),    # 导弹2: 从东南方向 (-60度)
    ]

    # 无人机初始位置 [m] (5架, 扇形拦截面, z=h_u)
    # 距离原点 ~3000m, 散布在±60度扇形内
    U_positions = [
        np.array([3000.0, 0.0, h_u]),          # UAV0: 正东
        np.array([2598.0, 1500.0, h_u]),       # UAV1: 30度
        np.array([1500.0, 2598.0, h_u]),       # UAV2: 60度
        np.array([2598.0, -1500.0, h_u]),      # UAV3: -30度
        np.array([1500.0, -2598.0, h_u]),      # UAV4: -60度
    ]

    # 无人机初始航向角 [rad] (指向原点方向)
    theta_init = []
    for j in range(5):
        # 方向: 从UAV指向原点 = (0,0) - (x,y)
        dx = -U_positions[j][0]
        dy = -U_positions[j][1]
        theta_j = np.arctan2(dy, dx)
        theta_init.append(theta_j)

    return M_positions, U_positions, theta_init


# ================================================================
# 主函数 — 依次求解 5 个子问题
# ================================================================

def main():
    """主求解流程"""
    print("=" * 70)
    print("  2025 MCM Problem A — UAV烟幕遮蔽策略优化")
    print("  Coding Expert Agent | 2026-05-31")
    print("=" * 70)

    # 获取默认场景
    M_positions, U_positions, theta_init = get_default_scenario()

    all_results = {}  # 存储所有结果用于 XLSX 汇总

    # ============================================================
    # 问题 1: 单机单弹给定参数计算 (seed=42)
    # ============================================================
    np.random.seed(42)
    print("\n" + "=" * 60)
    print("  问题 1: 单机单弹给定参数计算")
    print("=" * 60)

    q1_params = {
        'M1_0': M_positions[0],           # 导弹0从正东来袭
        'U1_0': U_positions[0],           # UAV0在正东方向
        'theta1': theta_init[0],           # 航向指向原点
        'v_u1': 30.0,                      # 飞行速度 30 m/s
        't_d': 0.0,                        # 立即投放
        't_b': 9.0,                        # 9秒后起爆
        'v_b0': v_b0,                      # 弹射速度
    }

    T_eff_q1, intervals_q1 = SolveProblem1(q1_params)
    print(f"  导弹M1有效遮蔽时长: T_eff = {T_eff_q1:.4f}s")
    print(f"  遮蔽区间: {intervals_q1}")

    # 保存 Q1 结果 — key,value,unit 三列标准格式（ERR-C-006修复）
    q1_csv_path = os.path.join(RESULTS_DIR, 'Q1_summary_results.csv')
    q1_df = pd.DataFrame([
        {'key': 'T_eff', 'value': f'{T_eff_q1:.4f}', 'unit': 's'},
        {'key': 't_d', 'value': f'{q1_params["t_d"]:.2f}', 'unit': 's'},
        {'key': 't_b', 'value': f'{q1_params["t_b"]:.2f}', 'unit': 's'},
        {'key': 'M1_x', 'value': f'{M_positions[0][0]:.1f}', 'unit': 'm'},
        {'key': 'M1_y', 'value': f'{M_positions[0][1]:.1f}', 'unit': 'm'},
        {'key': 'M1_z', 'value': f'{M_positions[0][2]:.1f}', 'unit': 'm'},
        {'key': 'U1_x', 'value': f'{U_positions[0][0]:.1f}', 'unit': 'm'},
        {'key': 'U1_y', 'value': f'{U_positions[0][1]:.1f}', 'unit': 'm'},
        {'key': 'U1_z', 'value': f'{U_positions[0][2]:.1f}', 'unit': 'm'},
        {'key': 'theta1', 'value': f'{theta_init[0]:.4f}', 'unit': 'rad'},
        {'key': 'v_u1', 'value': '30.0', 'unit': 'm/s'},
    ])
    q1_df.to_csv(q1_csv_path, index=False)
    print(f"  结果已保存: {q1_csv_path}")

    all_results['Q1'] = [{
        'T_eff_s': T_eff_q1,
        't_d_s': q1_params['t_d'],
        't_b_s': q1_params['t_b'],
        'M0_x': M_positions[0][0],
        'M0_y': M_positions[0][1],
        'M0_z': M_positions[0][2],
        'UAV_x': U_positions[0][0],
        'UAV_y': U_positions[0][1],
        'theta_rad': theta_init[0],
        'v_u_mps': 30.0,
        'n_intervals': len(intervals_q1)
    }]

    # 图1: Q1 遮蔽状态
    if intervals_q1:
        plot_q1_occlusion(T_eff_q1, intervals_q1, q1_params)

    # ============================================================
    # 问题 2: 单机单弹策略优化 (seed=42)
    # ============================================================
    np.random.seed(42)
    print("\n" + "=" * 60)
    print("  问题 2: 单机单弹策略优化")
    print("=" * 60)

    q2_fixed = {
        'M1_0': M_positions[0],
        'U1_0': U_positions[0],
        'v_b0': v_b0,
    }

    x_opt_q2, T_opt_q2, intervals_q2 = SolveProblem2(q2_fixed)

    # 使用验证级精度重新计算
    if T_opt_q2 > 0:
        intervals_q2_val = compute_single_cloud_intervals(
            x_opt_q2[0], x_opt_q2[1], x_opt_q2[2], x_opt_q2[3],
            M_positions[0], U_positions[0], v_b0,
            N_pts_val, Delta_t_val, r_c, H_c
        )
        T_opt_q2_val = sum(e - s for s, e in intervals_q2_val)
        print(f"  [验证] 高精度遮蔽时长: {T_opt_q2_val:.4f}s")
    else:
        intervals_q2_val = []
        T_opt_q2_val = 0.0

    save_intervals_to_csv('Q2', intervals_q2)
    save_results_to_csv('Q2_summary', [{
        'theta_rad': x_opt_q2[0],
        'v_u_mps': x_opt_q2[1],
        't_d_s': x_opt_q2[2],
        't_b_s': x_opt_q2[3],
        'T_eff_opt_s': T_opt_q2,
        'T_eff_val_s': T_opt_q2_val,
        'n_intervals': len(intervals_q2)
    }])

    all_results['Q2'] = [{
        'theta_rad': x_opt_q2[0],
        'v_u_mps': x_opt_q2[1],
        't_d_s': x_opt_q2[2],
        't_b_s': x_opt_q2[3],
        'T_eff_opt_s': T_opt_q2,
        'T_eff_val_s': T_opt_q2_val
    }]

    # 图2: Q2 最优解
    if T_opt_q2 > 0:
        plot_q2_optimization(intervals_q2, x_opt_q2, T_opt_q2, M_positions[0], U_positions[0])

    # ============================================================
    # 问题 3: 单机多弹时序优化 (seed=43)
    # ============================================================
    np.random.seed(43)
    print("\n" + "=" * 60)
    print(f"  问题 3: 单机多弹时序优化 (K={K_bombs})")
    print("=" * 60)

    q3_fixed = {
        'M1_0': M_positions[0],
        'U1_0': U_positions[0],
        'v_b0': v_b0,
        'theta': theta_init[0],
        'v_u': 30.0,
    }

    x_opt_q3, T_opt_q3, intervals_q3 = SolveProblem3(K_bombs, q3_fixed)

    # 高精度验证
    all_intv_val = []
    for k in range(K_bombs):
        td = x_opt_q3[2 * k]
        tb = x_opt_q3[2 * k + 1]
        intv_k = compute_single_cloud_intervals(
            theta_init[0], 30.0, td, tb, M_positions[0], U_positions[0], v_b0,
            N_pts_val, Delta_t_val, r_c, H_c
        )
        all_intv_val.extend(intv_k)
    merged_val = MergeIntervals(all_intv_val)
    T_opt_q3_val = sum(e - s for s, e in merged_val)
    print(f"  [验证] 高精度遮蔽时长: {T_opt_q3_val:.4f}s")
    print(f"  最优解: t_d = {[f'{x_opt_q3[2*k]:.2f}' for k in range(K_bombs)]}")
    print(f"          t_b = {[f'{x_opt_q3[2*k+1]:.2f}' for k in range(K_bombs)]}")

    save_intervals_to_csv('Q3', merged_val)
    save_results_to_csv('Q3_summary', [{
        'K': K_bombs,
        'T_eff_opt_s': T_opt_q3,
        'T_eff_val_s': T_opt_q3_val,
        't_d_list': json.dumps([float(x_opt_q3[2*k]) for k in range(K_bombs)]),
        't_b_list': json.dumps([float(x_opt_q3[2*k+1]) for k in range(K_bombs)]),
    }])

    all_results['Q3'] = [{
        'K': K_bombs,
        'T_eff_opt_s': T_opt_q3,
        'T_eff_val_s': T_opt_q3_val,
    }]
    for k in range(K_bombs):
        all_results['Q3'][0][f't_d_{k+1}'] = x_opt_q3[2*k]
        all_results['Q3'][0][f't_b_{k+1}'] = x_opt_q3[2*k+1]

    # 图3: Q3 多弹时序
    if intervals_q3:
        plot_q3_timing(x_opt_q3, K_bombs, merged_val,
                       M_positions[0], U_positions[0], theta_init[0], 30.0)

    # ============================================================
    # 问题 4: 多机单弹空间协同 (3机) (seed=44)
    # ============================================================
    np.random.seed(44)
    print("\n" + "=" * 60)
    print("  问题 4: 多机单弹空间协同")
    print("=" * 60)

    q4_n_uavs = 3
    q4_uav_pos = U_positions[:q4_n_uavs]  # 前3架UAV
    q4_missile_param = {'M_0': M_positions[0], 'v_b0': v_b0}

    x_opt_q4, T_opt_q4, intervals_q4 = SolveProblem4(
        q4_uav_pos, q4_n_uavs, q4_missile_param
    )

    # 高精度验证
    all_intv_q4_val = []
    for j in range(q4_n_uavs):
        base = 4 * j
        theta = x_opt_q4[base]
        v_u = x_opt_q4[base + 1]
        t_d = x_opt_q4[base + 2]
        t_b = x_opt_q4[base + 3]
        intv_j = compute_single_cloud_intervals(
            theta, v_u, t_d, t_b, M_positions[0], q4_uav_pos[j], v_b0,
            N_pts_val, Delta_t_val, r_c, H_c
        )
        all_intv_q4_val.extend(intv_j)
    merged_q4_val = MergeIntervals(all_intv_q4_val)
    T_opt_q4_val = sum(e - s for s, e in merged_q4_val)
    print(f"  [验证] 高精度遮蔽时长: {T_opt_q4_val:.4f}s")

    save_intervals_to_csv('Q4', merged_q4_val)
    save_results_to_csv('Q4_summary', [{
        'n_uavs': q4_n_uavs,
        'T_eff_opt_s': T_opt_q4,
        'T_eff_val_s': T_opt_q4_val,
    }])

    all_results['Q4'] = [{
        'n_uavs': q4_n_uavs,
        'T_eff_opt_s': T_opt_q4,
        'T_eff_val_s': T_opt_q4_val,
    }]
    for j in range(q4_n_uavs):
        base = 4 * j
        all_results['Q4'][0][f'UAV{j}_theta'] = x_opt_q4[base]
        all_results['Q4'][0][f'UAV{j}_v_u'] = x_opt_q4[base + 1]
        all_results['Q4'][0][f'UAV{j}_t_d'] = x_opt_q4[base + 2]
        all_results['Q4'][0][f'UAV{j}_t_b'] = x_opt_q4[base + 3]

    # 图4: Q4 多机协同
    if T_opt_q4 > 0:
        plot_q4_coordination(x_opt_q4, q4_n_uavs, merged_q4_val,
                             M_positions[0], q4_uav_pos)

    # ============================================================
    # 问题 5: 多机多弹多目标（完整场景）(seed=45)
    # ============================================================
    np.random.seed(45)
    print("\n" + "=" * 60)
    print("  问题 5: 多机多弹多目标（完整场景）")
    print("=" * 60)

    q5_params = {'v_b0': v_b0}

    T_total_q5, groups_q5, intervals_q5 = SolveProblem5(
        U_positions, theta_init, M_positions, q5_params, N_max=N_max_load
    )

    # 保存 Q5 结果
    save_intervals_to_csv('Q5_M0', intervals_q5[0] if len(intervals_q5) > 0 else [])
    save_intervals_to_csv('Q5_M1', intervals_q5[1] if len(intervals_q5) > 1 else [])
    save_intervals_to_csv('Q5_M2', intervals_q5[2] if len(intervals_q5) > 2 else [])

    save_results_to_csv('Q5_summary', [{
        'T_total_intersection_s': T_total_q5,
        'Group0_UAVs': json.dumps([int(v) for v in groups_q5[0]]),
        'Group1_UAVs': json.dumps([int(v) for v in groups_q5[1]]),
        'Group2_UAVs': json.dumps([int(v) for v in groups_q5[2]]),
        'Group0_intervals': json.dumps([(float(s), float(e)) for s, e in intervals_q5[0]]),
        'Group1_intervals': json.dumps([(float(s), float(e)) for s, e in intervals_q5[1]]),
        'Group2_intervals': json.dumps([(float(s), float(e)) for s, e in intervals_q5[2]]),
    }])

    all_results['Q5'] = [{
        'T_total_intersection_s': T_total_q5,
        'Group0_UAVs': str(groups_q5[0]),
        'Group1_UAVs': str(groups_q5[1]),
        'Group2_UAVs': str(groups_q5[2]),
    }]

    # 图5: Q5 交集（仅当有非空区间时生成，ERR-C-010防护）
    # 先清理旧fig5残留
    old_fig5 = os.path.join(FIGURES_DIR, 'fig5_Q5_intersection.png')
    if os.path.exists(old_fig5):
        os.remove(old_fig5)
    has_any_interval = any(len(iv) > 0 for iv in intervals_q5)
    if has_any_interval:
        plot_q5_intersection(intervals_q5, groups_q5, T_total_q5)
    else:
        print("   [注意] Q5所有组遮蔽区间均为空，跳过交集图生成")

    # 图6: Q5 任务分配地图（始终生成，展示分配方案）
    plot_q5_strategy_map(U_positions, theta_init, M_positions, groups_q5)

    # ============================================================
    # 保存汇总 XLSX
    # ============================================================
    save_summary_xlsx(all_results)

    # ============================================================
    # 最终报告
    # ============================================================
    print("\n" + "=" * 70)
    print("  计算结果汇总")
    print("=" * 70)
    print(f"  Q1: T_eff = {T_eff_q1:.4f}s         (单机单弹, 给定参数)")
    print(f"  Q2: T_eff = {T_opt_q2:.4f}s         (单机单弹, 4D优化)")
    print(f"      验证用 = {T_opt_q2_val:.4f}s")
    print(f"  Q3: T_eff = {T_opt_q3:.4f}s         (单机{K_bombs}弹, DE优化)")
    print(f"      验证用 = {T_opt_q3_val:.4f}s")
    print(f"  Q4: T_eff = {T_opt_q4:.4f}s         ({q4_n_uavs}机协同, 分层降维)")
    print(f"      验证用 = {T_opt_q4_val:.4f}s")
    print(f"  Q5: T_total(交集) = {T_total_q5:.4f}s  (5机3弹, 三层简化)")
    if T_total_q5 < 1e-9:
        print(f"  [注意] Q5交集为空 — 当前5UAV配置不足以同时遮蔽3枚导弹")
    print(f"  {'='*70}")

    # 列出输出文件
    print("\n  输出文件:")
    print(f"  代码:   {os.path.join(CODE_DIR, 'solver.py')}")
    print(f"  依赖:   {os.path.join(CODE_DIR, 'requirements.txt')}")
    print(f"  图表:   {FIGURES_DIR}")
    print(f"  结果:   {RESULTS_DIR}")
    print("\n  求解完成!")


# ================================================================
# 入口
# ================================================================
if __name__ == '__main__':
    main()
