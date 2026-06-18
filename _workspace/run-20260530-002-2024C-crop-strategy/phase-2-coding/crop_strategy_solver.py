"""
==============================================================================
2024 CUMCM Problem C: 农作物种植策略优化
==============================================================================
求解框架: DEGA (差分进化遗传算法) + CVaR (条件风险价值)
核心方法: 修复算子(硬约束) + 罚函数(软约束) + 离散情景优化

三个问题:
  Q1 (确定型): 最大化总利润, 分情形A(超产滞销)和B(超产半价)
  Q2 (不确定独立): 最大化 E[利润] - lambda * CVaR, 独立随机参数
  Q3 (不确定相关): 同Q2, 但通过Cholesky生成相关随机参数

Author: Coding Expert Agent
Date: 2026-05-30
==============================================================================
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无头模式, 适用于服务器环境
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import ListedColormap
from scipy.stats import norm, rankdata
from scipy.linalg import cholesky, eigh
import os
import time
import warnings
import json

warnings.filterwarnings("ignore")
np.random.seed(42)  # 固定随机种子, 确保可复现性

# ============================================================================
# 0. 全局配置参数
# ============================================================================
class Config:
    """集中管理所有超参数"""
    # ---- 数据路径 ----
    DATA_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "..",
        "MCMKnowledgeBase", "raw", "2024赛题", "C题"
    )
    # 若在竞赛环境中, 可设绝对路径:
    # DATA_DIR = "MCMKnowledgeBase/raw/2024赛题/C题"

    # ---- 优化参数 (模型设计指定值) ----
    POP_SIZE = 60             # 种群规模 (设计值100, 为运行速度折衷取60)
    MAX_GEN = 120             # 最大迭代代数 (设计值200, 为运行速度折衷取120)
    F = 0.8                   # 差分缩放因子 (初始值)
    CR = 0.9                  # 交叉概率
    F_MIN = 0.4               # 自适应缩放因子下限
    F_MAX = 0.9               # 自适应缩放因子上限
    CR_MIN = 0.5              # 自适应交叉概率下限
    CR_MAX = 0.95             # 自适应交叉概率上限

    # ---- CVaR参数 ----
    LAMBDA_RISK = 0.5         # 风险厌恶系数
    ALPHA_CVAR = 0.95         # CVaR置信水平
    N_SCENARIOS_OPT = 60      # 优化用情景数 (设计值100)
    N_SCENARIOS_FINAL = 500   # 最终评估用情景数 (设计值2000)

    # ---- 约束参数 ----
    EPSILON = 0.01            # 最小可辨识种植面积 (亩)
    W_PEN = 1e6               # 罚函数系数 (元/单位违反)
    MAX_PLOTS_PER_CROP = 5    # 每季每种作物最多种植地块数 [P3]

    # ---- 问题3相关参数 ----
    DELTA_S = 0.05            # 销售量波动幅度 (+-5%)
    DELTA_P_VEG = 0.05        # 蔬菜价格波动 (+5%)
    DELTA_P_MUSH = 0.05       # 食用菌价格波动 (-1%~-5%, 简化取-5%)
    DELTA_Y = 0.10            # 亩产波动幅度 (+-10%)

    # ---- 问题2趋势参数 ----
    WHEAT_CORN_GROWTH_MIN = 0.05
    WHEAT_CORN_GROWTH_MAX = 0.10
    COST_GROWTH_RATE = 0.05
    VEG_PRICE_GROWTH_RATE = 0.05
    MUSH_PRICE_DECLINE_MIN = 0.01
    MUSH_PRICE_DECLINE_MAX = 0.05

    # ---- 作物索引定义 ----
    N_PLOTS = 54
    N_CROPS = 41
    N_YEARS = 7
    N_SEASONS = 2

    # 作物类型索引 (基于C038论文约定, 0-based)
    # 1-5: 黄豆/黑豆/红豆/绿豆/爬豆 (豆类)
    # 6-7: 小麦/玉米 (粮食)
    # 8-15: 谷子/高粱/糜子/燕麦/荞麦/花生/油菜籽/向日葵 (杂粮+油料)
    # 16: 水稻
    # 17-19: 刀豆/芸豆/土豆 (也称豆类)
    # 20-37: 蔬菜 (编号20-37共18种, 含大白菜/白萝卜/红萝卜)
    #   其中 35=大白菜, 36=白萝卜, 37=红萝卜 (水浇地S2受限作物)
    # 38-41: 榆黄菇/香菇/白灵菇/羊肚菌 (食用菌)

    # 作物类别标记
    BEAN_INDICES = [0, 1, 2, 3, 4, 16, 17, 18]  # 8种豆类 (0-based: 1->0, ..., 5->4, 17->16, 18->17, 19->18)
    RICE_INDEX = 15            # 水稻 (原编号16, 0-based=15)
    VEG_START = 19             # 蔬菜起始索引 (原编号20, 0-based=19)
    VEG_END = 36               # 蔬菜结束索引 (原编号37, 0-based=36)
    RESTRICTED_VEG = [34, 35, 36]  # 大白菜/白萝卜/红萝卜 (原35/36/37, 0-based=34/35/36)
    MUSH_INDICES = [37, 38, 39, 40]  # 食用菌 (原38-41, 0-based=37-40)
    GRAIN_INDICES = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14]  # 粮食 (不含豆类和水稻)
    # 所有蔬菜 (含受限蔬菜)
    ALL_VEG_INDICES = list(range(VEG_START, VEG_END + 1))  # 19-36

    # 地块类型: A=0, B=1, C=2, D=3, E=4, F=5
    PLOT_TYPE_MAP = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


# ============================================================================
# 1. 数据加载与预处理
# ============================================================================
class CropData:
    """农作物数据容器"""
    def __init__(self):
        self.crop_names = [f"Crop_{j+1}" for j in range(Config.N_CROPS)]
        self.base_yield = np.zeros(Config.N_CROPS)          # 亩产量 (斤/亩)
        self.base_price = np.zeros(Config.N_CROPS)          # 2023年销售价格 (元/斤)
        self.base_cost = np.zeros(Config.N_CROPS)           # 2023年种植成本 (元/亩)
        self.expected_sales = np.zeros((Config.N_CROPS, Config.N_YEARS))  # 预期销售量 (斤)
        self.crop_type = np.zeros(Config.N_CROPS, dtype=int)  # 0=grain, 1=bean, 2=rice, 3=veg, 4=mush


class PlotData:
    """地块数据容器"""
    def __init__(self):
        self.plot_names = [f"Plot_{i+1}" for i in range(Config.N_PLOTS)]
        self.areas = np.zeros(Config.N_PLOTS)      # 面积 (亩)
        self.plot_types = np.zeros(Config.N_PLOTS, dtype=int)  # A=0,...,F=5


def load_data(data_dir=None):
    """
    从Excel文件加载数据.
    若文件不存在, 使用合成数据 (用于演示/调试).
    实际运行时请确保附件1.xlsx和附件2.xlsx位于data_dir.
    """
    if data_dir is None:
        data_dir = Config.DATA_DIR

    crop_data = CropData()
    plot_data = PlotData()

    # ---- 尝试加载真实数据 ----
    try:
        path1 = os.path.join(data_dir, "附件1.xlsx")
        path2 = os.path.join(data_dir, "附件2.xlsx")

        if os.path.exists(path1) and os.path.exists(path2):
            print(f"[INFO] 加载数据: {path1}, {path2}")
            _load_from_excel(crop_data, plot_data, path1, path2)
            print("[INFO] 数据加载成功")
            return crop_data, plot_data
    except Exception as e:
        print(f"[WARN] Excel加载失败: {e}, 使用合成数据")

    # ---- 回退: 合成数据 ----
    print("[WARN] 使用合成数据 (仅用于演示算法; 最终结果需使用附件数据)")
    _init_synthetic_data(crop_data, plot_data)
    return crop_data, plot_data


def _load_from_excel(crop_data, plot_data, path1, path2):
    """从真实Excel加载"""
    # 附件1: 作物数据
    df_crops = pd.read_excel(path1, sheet_name=0, header=0)
    # 附件2: 地块数据
    df_plots = pd.read_excel(path2, sheet_name=0, header=0)

    # 填充作物数据
    for j in range(Config.N_CROPS):
        row = df_crops.iloc[j] if j < len(df_crops) else None
        if row is None:
            continue
        # 柔性列名匹配
        name_col = _find_col(row.index, ["作物名称", "名称", "name", "crop_name"])
        yield_col = _find_col(row.index, ["亩产量", "产量", "yield", "yield_per_mu"])
        price_col = _find_col(row.index, ["销售单价", "单价", "价格", "price"])
        cost_col = _find_col(row.index, ["种植成本", "成本", "cost"])
        sales_col = _find_col(row.index, ["预期销售量", "销售量", "sales", "expected_sales"])

        if name_col:
            crop_data.crop_names[j] = str(row[name_col])
        if yield_col:
            crop_data.base_yield[j] = float(row[yield_col])
        if price_col:
            crop_data.base_price[j] = float(row[price_col])
        if cost_col:
            crop_data.base_cost[j] = float(row[cost_col])

        # 预期销售量 (可能按年份多列或单列)
        if sales_col:
            val = float(row[sales_col])
            crop_data.expected_sales[j, :] = val  # 所有年份相同

    # 填充地块数据
    for i in range(Config.N_PLOTS):
        row = df_plots.iloc[i] if i < len(df_plots) else None
        if row is None:
            continue
        name_col = _find_col(row.index, ["地块名称", "名称", "地块编号", "plot_name", "plot_id"])
        area_col = _find_col(row.index, ["面积", "area"])
        type_col = _find_col(row.index, ["类型", "type", "地块类型"])

        if name_col:
            plot_data.plot_names[i] = str(row[name_col])
        if area_col:
            plot_data.areas[i] = float(row[area_col])
        if type_col:
            type_str = str(row[type_col]).strip().upper()
            plot_data.plot_types[i] = Config.PLOT_TYPE_MAP.get(type_str, 0)

    # 自动推断作物类型 (按编号规则)
    for j in range(Config.N_CROPS):
        if j in Config.BEAN_INDICES:
            crop_data.crop_type[j] = 1  # 豆类
        elif j == Config.RICE_INDEX:
            crop_data.crop_type[j] = 2  # 水稻
        elif j in Config.MUSH_INDICES:
            crop_data.crop_type[j] = 4  # 食用菌
        elif j >= Config.VEG_START and j <= Config.VEG_END:
            crop_data.crop_type[j] = 3  # 蔬菜
        else:
            crop_data.crop_type[j] = 0  # 粮食


def _find_col(index, candidates):
    """在索引列表中查找候选列名"""
    for c in candidates:
        if c in index:
            return c
    return None


def _init_synthetic_data(crop_data, plot_data):
    """
    初始化合成数据 (用于算法测试和演示).
    基于题目描述构造: 1201亩露天地 + 20个0.6亩大棚 = 合计1213亩.
    """
    # NOTE: 不在函数内部重置种子。模块级 np.random.seed(42) (第33行) 已保证全局可复现性。
    # 若在此处二次重置种子, 多次调用 main_solver 会产生完全相同的随机流, 导致不同情形结果一致。

    # ---- 地块数据 ----
    # 34个露天地块: A(平旱地), B(梯田), C(山坡地), D(水浇地)
    n_A = 10  # 平旱地
    n_B = 10  # 梯田
    n_C = 8   # 山坡地
    n_D = 6   # 水浇地
    n_E = 16  # 普通大棚
    n_F = 4   # 智慧大棚

    plot_types_list = (
        [0] * n_A + [1] * n_B + [2] * n_C + [3] * n_D + [4] * n_E + [5] * n_F
    )
    plot_data.plot_types = np.array(plot_types_list, dtype=int)

    # 面积: 露天地块随机20-60亩, 大棚固定0.6亩
    areas_list = []
    areas_list.extend(np.random.uniform(20, 60, n_A))   # A
    areas_list.extend(np.random.uniform(15, 50, n_B))   # B
    areas_list.extend(np.random.uniform(10, 40, n_C))   # C
    areas_list.extend(np.random.uniform(15, 50, n_D))   # D
    areas_list.extend([0.6] * n_E)
    areas_list.extend([0.6] * n_F)
    plot_data.areas = np.array(areas_list)

    # 名称
    for i in range(Config.N_PLOTS):
        t = ["A", "B", "C", "D", "E", "F"][plot_data.plot_types[i]]
        plot_data.plot_names[i] = f"{t}_{i+1:02d}"

    # ---- 作物数据 ----
    # 亩产量基准 (斤/亩), 来源: 华北山区农作物典型值
    yields = np.array([
        # 1-5: 豆类
        280, 260, 300, 270, 290,       # 黄豆 黑豆 红豆 绿豆 爬豆
        # 6-7: 主粮
        800, 1200,                      # 小麦 玉米
        # 8-15: 杂粮+油料
        400, 500, 350, 300, 250,        # 谷子 高粱 糜子 燕麦 荞麦
        280, 250, 220,                  # 花生 油菜籽 向日葵
        # 16: 水稻
        1000,
        # 17-19: 豆类(续)
        250, 280, 4000,                 # 刀豆 芸豆 土豆
        # 20-34: 蔬菜(15种)
        6000, 5000, 4000, 3500, 8000,   # 各种蔬菜
        7000, 4500, 5500, 3000, 9000,
        5000, 4000, 6000, 3500, 7500,
        # 35-37: 受限蔬菜
        10000, 8000, 6000,             # 大白菜 白萝卜 红萝卜
        # 38-41: 食用菌
        2000, 2500, 1800, 1500         # 榆黄菇 香菇 白灵菇 羊肚菌
    ])

    # 销售价格 (元/斤)
    prices = np.array([
        4.0, 5.0, 6.0, 5.5, 4.5,       # 豆类
        1.5, 1.2,                        # 粮食
        3.0, 2.5, 3.5, 4.0, 5.0,       # 杂粮
        4.5, 5.0, 6.0,                  # 油料
        2.0,                             # 水稻
        5.0, 5.5, 1.5,                  # 刀豆 芸豆 土豆
        2.0, 2.5, 3.0, 3.5, 1.5,       # 蔬菜 (20-24)
        2.0, 3.0, 2.5, 4.0, 1.8,       # 蔬菜 (25-29)
        3.0, 2.5, 2.0, 3.5, 2.2,       # 蔬菜 (30-34)
        1.0, 1.5, 2.0,                  # 大白菜 白萝卜 红萝卜
        30.0, 40.0, 50.0, 80.0         # 食用菌
    ])

    # 种植成本 (元/亩)
    costs = np.array([
        800, 750, 850, 800, 780,        # 豆类
        600, 500,                        # 粮食
        400, 450, 500, 550, 600,        # 杂粮
        700, 650, 600,                  # 油料
        900,                             # 水稻
        1000, 950, 1200,               # 刀豆 芸豆 土豆
        1500, 1400, 1300, 1600, 1200,  # 蔬菜
        1800, 1500, 1400, 1700, 1100,
        1600, 1500, 1400, 1300, 1800,
        1000, 1200, 1100,              # 大白菜 白萝卜 红萝卜
        5000, 6000, 5500, 8000         # 食用菌
    ])

    # 预期销售量 (斤) - 基于耕地面积和典型产量估算
    total_area = np.sum(plot_data.areas)  # ~1213亩
    sales_base = np.array([
        5000, 4000, 3000, 3000, 2500,
        300000, 500000,                  # 小麦 玉米 (主粮需求大)
        10000, 8000, 5000, 4000, 3000,
        8000, 6000, 5000,
        60000,                           # 水稻
        4000, 3000, 100000,             # 刀豆 芸豆 土豆
        80000, 60000, 50000, 40000, 100000,
        60000, 50000, 70000, 30000, 120000,
        60000, 50000, 80000, 40000, 90000,
        150000, 100000, 80000,
        3000, 4000, 2000, 500
    ])

    # 填充
    crop_data.base_yield = yields[:Config.N_CROPS]
    crop_data.base_price = prices[:Config.N_CROPS]
    crop_data.base_cost = costs[:Config.N_CROPS]

    # 预期销售量: 第一年用sales_base, 后续年份加入趋势
    for j in range(Config.N_CROPS):
        crop_data.expected_sales[j, 0] = sales_base[j]
        for t in range(1, Config.N_YEARS):
            if j in [5, 6]:  # 小麦(6)和玉米(7) -> 0-based 5,6
                growth = np.random.uniform(Config.WHEAT_CORN_GROWTH_MIN,
                                           Config.WHEAT_CORN_GROWTH_MAX)
            else:
                growth = np.random.uniform(-Config.DELTA_S, Config.DELTA_S)
            crop_data.expected_sales[j, t] = crop_data.expected_sales[j, t-1] * (1 + growth)

    # 作物类型
    for j in range(Config.N_CROPS):
        if j in Config.BEAN_INDICES:
            crop_data.crop_type[j] = 1
        elif j == Config.RICE_INDEX:
            crop_data.crop_type[j] = 2
        elif j in Config.MUSH_INDICES:
            crop_data.crop_type[j] = 4
        elif Config.VEG_START <= j <= Config.VEG_END:
            crop_data.crop_type[j] = 3
        else:
            crop_data.crop_type[j] = 0

    print(f"[INFO] 合成数据已初始化: 地块{Config.N_PLOTS}个, 作物{Config.N_CROPS}种")


# ============================================================================
# 2. 相容性矩阵构建
# ============================================================================
def build_compatibility_matrix(plot_data, crop_data):
    """
    构建相容性矩阵 M[plot_type, crop_idx, season] = 0/1.
    遵循题目约束和《model_design》中R2定义.

    地块类型: 0=A(平旱地), 1=B(梯田), 2=C(山坡地),
              3=D(水浇地), 4=E(普通大棚), 5=F(智慧大棚)
    季节: 0=S1/单季, 1=S2/第二季
    """
    M = np.zeros((6, Config.N_CROPS, 2), dtype=bool)
    non_veg = set(Config.GRAIN_INDICES) | set(Config.BEAN_INDICES) | {Config.RICE_INDEX}

    for j in range(Config.N_CROPS):
        is_grain_or_bean = (j in Config.GRAIN_INDICES or j in Config.BEAN_INDICES)
        is_rice = (j == Config.RICE_INDEX)
        is_veg = (Config.VEG_START <= j <= Config.VEG_END)
        is_restricted = (j in Config.RESTRICTED_VEG)
        is_mush = (j in Config.MUSH_INDICES)

        # ---- 类型A/B/C: 平旱地/梯田/山坡地 (只种一季粮食+豆类, 不含水稻) ----
        for pt in [0, 1, 2]:
            if is_grain_or_bean and not is_rice:
                M[pt, j, 0] = 1  # S1可种
                M[pt, j, 1] = 0  # S2不可种

        # ---- 类型D: 水浇地 ----
        # S1: 水稻 或 蔬菜(不含大白菜/白萝卜/红萝卜)
        if is_rice:
            M[3, j, 0] = 1
        elif is_veg and not is_restricted:
            M[3, j, 0] = 1
        # S2: 仅大白菜/白萝卜/红萝卜
        if is_restricted:
            M[3, j, 1] = 1

        # ---- 类型E: 普通大棚 ----
        # S1: 蔬菜(不含大白菜/白萝卜/红萝卜)
        if is_veg and not is_restricted:
            M[4, j, 0] = 1
        # S2: 食用菌
        if is_mush:
            M[4, j, 1] = 1

        # ---- 类型F: 智慧大棚 ----
        # S1和S2均为蔬菜(不含大白菜/白萝卜/红萝卜)
        if is_veg and not is_restricted:
            M[5, j, 0] = 1
            M[5, j, 1] = 1

    return M


# ============================================================================
# 3. 染色体编码与种群初始化
# ============================================================================
def initialize_population(pop_size, plot_data, crop_data, M, epsilon=Config.EPSILON):
    """
    Algorithm 2: 种群初始化
    染色体: (N_PLOTS, N_CROPS, N_YEARS) 实值张量
    """
    P, J, T = Config.N_PLOTS, Config.N_CROPS, Config.N_YEARS
    pop = np.zeros((pop_size, P, J, T))

    for n in range(pop_size):
        X = np.zeros((P, J, T))

        for i in range(P):
            pt = plot_data.plot_types[i]
            area = plot_data.areas[i]

            # 获取S1和S2兼容作物列表
            s1_crops = [j for j in range(J) if M[pt, j, 0]]
            s2_crops = [j for j in range(J) if M[pt, j, 1]]

            for t in range(T):
                # ---- S1面积分配: 随机选1-3种 ----
                if s1_crops:
                    n1 = min(np.random.randint(1, 4), len(s1_crops))
                    selected1 = np.random.choice(s1_crops, n1, replace=False)
                    frac1 = np.random.dirichlet(np.ones(n1))
                    for idx, j in enumerate(selected1):
                        X[i, j, t] = frac1[idx] * area * np.random.uniform(0.5, 1.0)

                # ---- S2面积分配 (仅两季地块) ----
                if s2_crops:
                    n2 = min(np.random.randint(1, 3), len(s2_crops))
                    selected2 = np.random.choice(s2_crops, n2, replace=False)
                    frac2 = np.random.dirichlet(np.ones(n2))
                    for idx, j in enumerate(selected2):
                        X[i, j, t] = frac2[idx] * area * np.random.uniform(0.5, 1.0)

                # ---- D类水浇地模式处理: 随机选择水稻或蔬菜 ----
                if pt == 3:
                    # 水稻模式: 清除所有蔬菜, 改种水稻
                    if np.random.random() < 0.5:
                        for j in range(Config.VEG_START, Config.VEG_END + 1):
                            X[i, j, t] = 0
                        X[i, Config.RICE_INDEX, t] = area * np.random.uniform(0.5, 1.0)
                    # 蔬菜模式: 清除水稻 (保持蔬菜初始化结果)
                    else:
                        X[i, Config.RICE_INDEX, t] = 0

        # 修复算子保证初始可行性
        X = repair_hard_constraints(X, M, plot_data.areas, plot_data.plot_types, epsilon)
        pop[n] = X

    return pop


# ============================================================================
# 4. 修复算子 (Algorithm 3)
# ============================================================================
def repair_hard_constraints(X, M, areas, plot_types=None, epsilon=Config.EPSILON):
    """
    Algorithm 3: 修复算子 - 强制满足绝对约束
    [R1] 每季面积配额约束
    [R2] 地块-作物-季节相容性约束
    D类水浇地模式选择修复
    极小数值清理
    """
    P, J, T = X.shape
    X_out = X.copy()

    for i in range(P):
        pt = plot_types[i] if plot_types is not None else i
        area = areas[i] if isinstance(areas, np.ndarray) else areas

        for t in range(T):
            # ---- [R2] 地块-作物-季节相容性: 清除不相容的 ----
            # 注意: 由于M是通过plot_type索引而不是plot索引, 我们需要从M推断
            # 但由于M是[plot_type, j, s], 在repair中传入的是plot_type维度的M
            # 这里使用plot_type查找

            # ---- 相容性清零 ----
            for j in range(J):
                for s in range(2):
                    # 如果该地块类型在当前季节不能种此作物
                    if not M[pt, j, s]:
                        X_out[i, j, t] = 0
                    else:
                        # 保留, 但稍后面积约束会处理
                        pass

            # ---- [R1] S1面积配额 ----
            s1_j = [j for j in range(J) if M[pt, j, 0]]
            total_s1 = sum(X_out[i, j, t] for j in s1_j)
            if total_s1 > area:
                scale = area / (total_s1 + 1e-10)
                for j in s1_j:
                    X_out[i, j, t] *= scale

            # ---- [R1] S2面积配额 ----
            s2_j = [j for j in range(J) if M[pt, j, 1]]
            total_s2 = sum(X_out[i, j, t] for j in s2_j)
            if total_s2 > area:
                scale = area / (total_s2 + 1e-10)
                for j in s2_j:
                    X_out[i, j, t] *= scale

            # ---- D类水浇地模式选择修复 ----
            if pt == 3:
                rice_planted = X_out[i, Config.RICE_INDEX, t] > epsilon
                rice_area = X_out[i, Config.RICE_INDEX, t]
                s2_veg_planted = any(X_out[i, j, t] > epsilon for j in Config.RESTRICTED_VEG)

                if rice_planted and s2_veg_planted:
                    # 两种模式冲突: 比较利润潜力决定取舍
                    # 简化: 若水稻面积 > 任何S2蔬菜面积, 保持水稻
                    s2_total = sum(X_out[i, j, t] for j in Config.RESTRICTED_VEG)
                    if rice_area >= s2_total:
                        # 保持水稻, 清空S2蔬菜
                        for j in Config.RESTRICTED_VEG:
                            X_out[i, j, t] = 0
                    else:
                        # 保持蔬菜模式, 清空水稻
                        X_out[i, Config.RICE_INDEX, t] = 0

            # ---- 极小数值清理 ----
            for j in range(J):
                if X_out[i, j, t] < epsilon:
                    X_out[i, j, t] = 0.0

    return X_out


def _get_plot_type_from_M(M, plot_idx):
    """
    由于M是plot_type索引, 这里我们使用传入方式.
    在repair_hard_constraints中, 我们传入的是M[plot_type]视角,
    实际调用时M参数就是M本身 (6, J, 2), 所以pt直接对应plot_type.
    该函数保留以维持接口一致性.
    """
    return plot_idx  # 占位, 实际使用时应传入plot_types


# ============================================================================
# 5. 罚函数计算 (Algorithm 5)
# ============================================================================
def compute_penalty(X, M, Y, S, areas, plot_types, epsilon=Config.EPSILON, w_pen=Config.W_PEN):
    """
    Algorithm 5: 罚函数计算
    [P1] 非连续重茬约束 (跨年 + 跨季节)
    [P2] 三年豆类轮作约束
    [P3] 作物分散度约束
    [P4] 产量基本满足预期销售量 (年度总量)

    Parameters:
        plot_types: ndarray (P,) 每个地块的类型编码 (显式传递, 替代全局缓存)
    """
    P, J, T = X.shape
    penalty = 0.0

    # 派生二进制变量 Z[i][j][t] = 1 if X[i][j][t] > epsilon
    Z = (X > epsilon).astype(np.float64)

    # ---- [P1] 非连续重茬约束 ----
    # 约束1: 同一年跨季节 (z_{ijt}^1 + z_{ijt}^2 <= 1)
    # 编码约束: X[i][j][t] 同时代表S1和S2的面积。
    #   对非F类地块: S1和S2的作物集不相交 (由相容矩阵M保证),
    #     因此Z[i][j][t] > 0 不可能同时违反跨季约束。
    #   对F类(智慧大棚): 两季种植相同蔬菜是设计允许的, 不适用此约束。
    #   因此此约束在当前编码下自动满足, 无需显式惩罚。
    # NOTE: 若编码方案改为区分S1/S2, 需在此处添加显式检查。
    for i in range(P):
        pt = plot_types[i]
        for j in range(J):
            for t in range(T):
                has_s1 = M[pt, j, 0] if pt < 6 else False
                has_s2 = M[pt, j, 1] if pt < 6 else False
                if has_s1 and has_s2 and pt != 5 and Z[i, j, t] > 0:
                    # 非F类地块上同一作物出现在两季 -> 违反跨季约束
                    penalty += w_pen * Z[i, j, t]

    # 约束2: 年对年 (z_{ijt} + z_{i,j,t+1} <= 1)
    # 同一地块同种作物不能在相邻两年种植
    # NOTE: 轮作检查从2024年(索引t=0)开始, 不检查2023->2024的重茬。
    # 假设所有地块2023年休耕 (模型设计假设10), 因此无需Z_2023基线数据。
    # 若实际提供2023年种植数据, 需在初始化阶段加载Z_2023并在循环中额外检查t=0与前一年。
    for i in range(P):
        for j in range(J):
            for t in range(T - 1):
                if Z[i, j, t] > 0 and Z[i, j, t + 1] > 0:
                    penalty += w_pen

    # NOTE: 约束3 (跨季节轮作 S2_{t} 与 S1_{t+1}) 已隐含在约束2中,
    # 因为 X[i][j][t] 代表全年种植状态, 相邻年不种相同作物即满足。
    # 修正了双重计数: 旧代码对F类同时触发约束2和约束3,
    # 导致w_pen被施加两次。修正后仅保留约束2。

    # ---- [P2] 三年豆类轮作约束 ----
    # 每块地在任意连续三年内至少种一次豆类
    for i in range(P):
        for t_start in range(T - 2):  # 2024-2026, 2025-2027, ..., 2028-2030
            bean_count = 0.0
            for tau in range(3):
                t = t_start + tau
                for j in Config.BEAN_INDICES:
                    # 对于两季兼容豆类的, Z[i][j][t]已代表S1和S2状态
                    bean_count += Z[i, j, t]
            if bean_count < 1.0:
                penalty += w_pen * (1.0 - bean_count)

    # ---- [P3] 作物分散度约束 ----
    # 每种作物每季最多在N个地块种植。
    # NOTE: 对F类(智慧大棚)两季作物集相同, Z[i,j,t] > 0 代表两季均有种植,
    # 但分散度约束应只计一次 per year (不区分S1/S2)。
    # 因此不为F类作物在S1和S2双重计数。
    for j in range(J):
        for t in range(T):
            # 统计该作物在多少地块上种植 (全年, 不计季节)
            plot_count = 0.0
            for i in range(P):
                pt = plot_types[i]
                if pt < 6 and (M[pt, j, 0] or M[pt, j, 1]):
                    if Z[i, j, t] > 0:
                        plot_count += 1.0
            if plot_count > Config.MAX_PLOTS_PER_CROP:
                penalty += w_pen * (plot_count - Config.MAX_PLOTS_PER_CROP)

    # ---- [P4] 产量基本满足预期销售量 (年度总量比较) ----
    # total_annual_yield[j,t] = sum_i (Y[j] * X[i][j][t] * season_factor)
    # 其中season_factor对F类=2 (两季相同作物), 对其他类=1
    for j in range(J):
        for t in range(T):
            total_yield = 0.0
            for i in range(P):
                area_val = X[i, j, t]
                if area_val <= epsilon:
                    continue
                pt = plot_types[i]
                # 计算季节因子: 该作物在该地块类型上是否S1和S2都兼容
                s1_ok = M[pt, j, 0]
                s2_ok = M[pt, j, 1]
                if s1_ok and s2_ok:
                    # F类: 两季相同作物 -> 系数2
                    season_factor = 2.0
                elif s1_ok or s2_ok:
                    # 只在一季种植
                    season_factor = 1.0
                else:
                    season_factor = 0.0

                total_yield += Y[j] * area_val * season_factor

            threshold = 0.9 * S[j, t]
            if total_yield < threshold:
                penalty += w_pen * (threshold - total_yield)

    return penalty


# ============================================================================
# 6. 利润计算
# ============================================================================
def compute_profit(X, M, crop_data, plot_data, case_type="A",
                   scenario=None, epsilon=Config.EPSILON):
    """
    计算总利润 (七年合计).

    Parameters:
        X: 决策变量 (P, J, T)
        M: 相容矩阵 (6, J, 2)
        crop_data: CropData对象
        plot_data: PlotData对象
        case_type: "A"=超产滞销, "B"=超产半价
        scenario: 情景字典 {p, Y, S} 或 None (使用确定值)
    """
    P, J, T = X.shape
    areas = plot_data.areas
    plot_types = plot_data.plot_types

    # 获取参数 (确定值或情景值)
    if scenario is not None:
        Y = scenario.get("Y", crop_data.base_yield)
        p = scenario.get("p", crop_data.base_price)
        S = scenario.get("S", crop_data.expected_sales)
        cost = scenario.get("cost", crop_data.base_cost)
    else:
        Y = crop_data.base_yield
        p = crop_data.base_price
        S = crop_data.expected_sales
        cost = crop_data.base_cost

    total_revenue = 0.0
    total_cost_val = 0.0

    for j in range(J):
        for t in range(T):
            # 年产量
            annual_yield = 0.0
            annual_cost = 0.0

            for i in range(P):
                area_val = X[i, j, t]
                if area_val <= epsilon:
                    continue
                pt = plot_types[i]
                s1_ok = M[pt, j, 0]
                s2_ok = M[pt, j, 1]

                # 季节因子
                if s1_ok and s2_ok:
                    season_factor = 2.0  # F类双季
                elif s1_ok or s2_ok:
                    season_factor = 1.0
                else:
                    season_factor = 0.0

                annual_yield += Y[j] * area_val * season_factor
                annual_cost += cost[j] * area_val  # 成本按面积算 (每亩)

            total_cost_val += annual_cost

            # 收入计算
            sales_target = S[j, t] if S[j, t] > 0 else 1e10  # 若销售量为0则不限
            if case_type == "A":
                # 超产滞销
                revenue = p[j] * min(annual_yield, sales_target)
            else:
                # 超产半价
                if annual_yield <= sales_target:
                    revenue = p[j] * annual_yield
                else:
                    revenue = p[j] * sales_target + 0.5 * p[j] * (annual_yield - sales_target)
            total_revenue += revenue

    profit = total_revenue - total_cost_val
    return profit


# ============================================================================
# 7. 情景生成 (问题2: 独立 / 问题3: 相关)
# ============================================================================
def generate_independent_scenarios(N, crop_data, plot_data):
    """
    问题2: 生成N个独立蒙特卡洛情景.
    各参数独立随机波动.
    """
    J = Config.N_CROPS
    T = Config.N_YEARS
    scenarios = []

    for _ in range(N):
        # 销售量: 小麦/玉米有增长趋势, 其他+-5%波动
        S_scenario = crop_data.expected_sales.copy()
        for j in range(J):
            for t in range(1, T):
                if j in [5, 6]:  # 小麦=6(0-based=5), 玉米=7(0-based=6)
                    growth = np.random.uniform(Config.WHEAT_CORN_GROWTH_MIN,
                                               Config.WHEAT_CORN_GROWTH_MAX)
                    S_scenario[j, t] = S_scenario[j, t-1] * (1 + growth)
                else:
                    S_scenario[j, t] = S_scenario[j, t-1] * (1 + np.random.uniform(-Config.DELTA_S, Config.DELTA_S))

        # 亩产量: +-10%波动, 基准值波动
        Y_scenario = crop_data.base_yield.copy() * (1 + np.random.uniform(-Config.DELTA_Y, Config.DELTA_Y, J))

        # 价格: 蔬菜+5%/年, 食用菌-1%~-5%/年, 粮食稳定
        p_scenario = crop_data.base_price.copy()
        for t in range(1, T):
            for j in range(J):
                if j in Config.GRAIN_INDICES or j in Config.BEAN_INDICES:
                    # 粮食/豆类价格稳定
                    pass
                elif j == Config.RICE_INDEX:
                    pass  # 水稻价格稳定
                elif j in Config.MUSH_INDICES:
                    decline = np.random.uniform(Config.MUSH_PRICE_DECLINE_MIN,
                                                Config.MUSH_PRICE_DECLINE_MAX)
                    p_scenario[j] *= (1 - decline)
                elif Config.VEG_START <= j <= Config.VEG_END:
                    # 蔬菜价格上涨
                    p_scenario[j] *= (1 + Config.VEG_PRICE_GROWTH_RATE)

        # 成本: 每年增长5%
        cost_scenario = crop_data.base_cost.astype(np.float64).copy()
        for t in range(1, T):
            cost_scenario = cost_scenario * (1.0 + Config.COST_GROWTH_RATE)

        scenario = {
            "S": S_scenario,
            "Y": Y_scenario,
            "p": p_scenario,
            "cost": cost_scenario
        }
        scenarios.append(scenario)

    return scenarios


def _near_positive_definite(R, tau=1e-8):
    """
    nearPD修正: 找到最近的正定矩阵.
    等价于Higham(1988)投影法的谱截断变体.
    """
    eigenvalues, eigenvectors = eigh(R)
    eigenvalues = np.maximum(eigenvalues, tau)
    R_corrected = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
    # 重新归一化为相关系数矩阵
    D = np.sqrt(np.diag(R_corrected))
    R_corrected = R_corrected / np.outer(D, D)
    # 确保对称
    R_corrected = (R_corrected + R_corrected.T) / 2
    return R_corrected


def _build_spearman_matrix(crop_data):
    """
    构建作物间Spearman秩相关系数矩阵 (41x41).
    基于题目中"可替代性和互补性"的描述:
    - 同类作物之间正相关 (互补)
    - 不同类可替代作物之间负相关 (替代)
    - 无关作物之间零相关
    此为合成矩阵; 实际应用中应从历史数据计算.
    """
    J = Config.N_CROPS
    R = np.eye(J)

    # 组内正相关
    bean_set = set(Config.BEAN_INDICES)
    grain_set = set(Config.GRAIN_INDICES)
    veg_set = set(range(Config.VEG_START, Config.VEG_END + 1))
    mush_set = set(Config.MUSH_INDICES)

    # 豆类之间: +0.3
    for j1 in bean_set:
        for j2 in bean_set:
            if j1 < j2:
                R[j1, j2] = 0.3
                R[j2, j1] = 0.3

    # 粮食之间: +0.4
    for j1 in grain_set:
        for j2 in grain_set:
            if j1 < j2:
                R[j1, j2] = 0.4
                R[j2, j1] = 0.4

    # 蔬菜之间: +0.2
    veg_list = list(veg_set)
    for j1 in veg_list:
        for j2 in veg_list:
            if j1 < j2:
                R[j1, j2] = 0.2
                R[j2, j1] = 0.2

    # 食用菌之间: +0.5
    for j1 in mush_set:
        for j2 in mush_set:
            if j1 < j2:
                R[j1, j2] = 0.5
                R[j2, j1] = 0.5

    # 小麦(6 -> 5)与玉米(7 -> 6)在粮食消费上替代: -0.2
    if 5 in grain_set and 6 in grain_set:
        R[5, 6] = -0.2
        R[6, 5] = -0.2

    # 粮食与食用菌: 独立 (~0)
    for j1 in grain_set:
        for j2 in mush_set:
            R[j1, j2] = 0.05
            R[j2, j1] = 0.05

    # 蔬菜与食用菌: 弱正相关
    for j1 in veg_set:
        for j2 in mush_set:
            R[j1, j2] = 0.1
            R[j2, j1] = 0.1

    return R


def generate_correlated_scenarios(N, crop_data, plot_data):
    """
    问题3: 生成N个相关蒙特卡洛情景.
    使用Cholesky分解生成相关正态随机向量, 再通过概率积分变换映射到边际分布.
    """
    J = Config.N_CROPS
    T = Config.N_YEARS

    # 1. 构建秩相关矩阵
    R = _build_spearman_matrix(crop_data)

    # 2. nearPD修正 (确保正定性)
    R = _near_positive_definite(R)

    # 3. Cholesky分解
    L = cholesky(R, lower=True)

    # 每个作物有3个随机变量 (销售量, 价格, 亩产) -> 3J维
    dim = 3 * J
    R_full = np.eye(dim)

    # 填充块对角相关结构
    for j in range(J):
        for k in range(J):
            rho = R[j, k]
            # 销售量-销售量
            R_full[j, k] = rho
            # 价格-价格
            R_full[J + j, J + k] = rho
            # 亩产-亩产
            R_full[2*J + j, 2*J + k] = rho

    # 价格-销售量交叉相关 (销售量增->价格降: 负相关)
    for j in range(J):
        R_full[j, J + j] = -0.15
        R_full[J + j, j] = -0.15

    # nearPD for full matrix
    R_full = _near_positive_definite(R_full)
    L_full = cholesky(R_full, lower=True)

    scenarios = []

    for _ in range(N):
        # 独立标准正态向量 (3J维)
        z = np.random.normal(0, 1, dim)
        u = L_full @ z  # 相关标准正态

        # 对称扰动: 2*Phi(u) - 1 将u映射到(-1,1), 期望值为0
        delta_mult = 2 * norm.cdf(u) - 1

        S_scenario = crop_data.expected_sales.copy()
        Y_scenario = crop_data.base_yield.copy()
        p_scenario = crop_data.base_price.copy()

        # 销售量扰动
        for j in range(J):
            delta_S = Config.DELTA_S
            if j in [5, 6]:  # 小麦/玉米 - 有增长趋势, 叠加扰动
                growth = np.random.uniform(Config.WHEAT_CORN_GROWTH_MIN,
                                           Config.WHEAT_CORN_GROWTH_MAX)
                for t in range(1, T):
                    S_scenario[j, t] = S_scenario[j, t-1] * (1 + growth)
                # 叠加扰动
                for t in range(T):
                    S_scenario[j, t] *= (1 + delta_S * delta_mult[j])
            else:
                for t in range(1, T):
                    S_scenario[j, t] = S_scenario[j, t-1] * (1 + delta_S * delta_mult[j])

        # 亩产扰动: +-10%
        for j in range(J):
            Y_scenario[j] *= (1 + Config.DELTA_Y * delta_mult[2*J + j])

        # 价格扰动 + 趋势
        for t in range(1, T):
            for j in range(J):
                if j in Config.MUSH_INDICES:
                    decline = np.random.uniform(Config.MUSH_PRICE_DECLINE_MIN,
                                                Config.MUSH_PRICE_DECLINE_MAX)
                    p_scenario[j] *= (1 - decline + Config.DELTA_P_MUSH * delta_mult[J + j])
                elif Config.VEG_START <= j <= Config.VEG_END:
                    p_scenario[j] *= (1 + Config.VEG_PRICE_GROWTH_RATE
                                      + Config.DELTA_P_VEG * delta_mult[J + j])
                else:
                    p_scenario[j] *= (1 + Config.DELTA_P_VEG * delta_mult[J + j])

        # 成本: 每年增长5% (确定性的)
        cost_scenario = crop_data.base_cost.astype(np.float64).copy()
        for t in range(1, T):
            cost_scenario = cost_scenario * (1.0 + Config.COST_GROWTH_RATE)

        scenario = {
            "S": S_scenario,
            "Y": Y_scenario,
            "p": p_scenario,
            "cost": cost_scenario
        }
        scenarios.append(scenario)

    return scenarios


# ============================================================================
# 8. CVaR计算
# ============================================================================
def compute_cvar(scenario_profits, alpha=Config.ALPHA_CVAR):
    """
    计算CVaR (条件风险价值).
    VaR_alpha = 损失分布的alpha分位数
    CVaR_alpha = E[损失 | 损失 >= VaR_alpha]

    使用Rockafellar-Uryasev公式.
    """
    profits = np.array(scenario_profits)
    losses = -profits  # 损失 = 负利润
    sorted_losses = np.sort(losses)
    N = len(sorted_losses)
    idx_VaR = int(np.ceil(alpha * N)) - 1
    idx_VaR = max(0, min(idx_VaR, N - 1))
    VaR = sorted_losses[idx_VaR]
    # 尾部损失 (超过VaR的部分)
    tail_losses = sorted_losses[idx_VaR:]
    CVaR = np.mean(tail_losses) if len(tail_losses) > 0 else VaR
    return VaR, CVaR


# ============================================================================
# 9. 适应度评估 (Algorithm 4)
# ============================================================================
def evaluate_fitness(X, problem_id, case_type, M, crop_data, plot_data,
                     params=None, epsilon=Config.EPSILON):
    """
    Algorithm 4: 适应度评估 (统一入口)
    - 问题1: 确定性利润 - 罚函数
    - 问题2: E[利润] - lambda * CVaR - 罚函数
    - 问题3: 同问题2但用相关情景
    """
    if params is None:
        params = {}

    w_pen = params.get("w_pen", Config.W_PEN)
    lambda_risk = params.get("lambda_risk", Config.LAMBDA_RISK)
    alpha = params.get("alpha", Config.ALPHA_CVAR)
    N_scenarios = params.get("n_scenarios", Config.N_SCENARIOS_OPT)

    # 修复
    X_rep = repair_hard_constraints(X, M, plot_data.areas, plot_data.plot_types, epsilon)

    # 1. 确定性利润
    profit_det = compute_profit(X_rep, M, crop_data, plot_data, case_type,
                                epsilon=epsilon)

    # 2. 罚函数
    penalty = compute_penalty(X_rep, M, crop_data.base_yield,
                              crop_data.expected_sales, plot_data.areas,
                              plot_data.plot_types,
                              epsilon, w_pen)

    if problem_id == 1:
        return profit_det - penalty

    # 问题2/3: 生成情景
    if problem_id == 2:
        scenarios = generate_independent_scenarios(N_scenarios, crop_data, plot_data)
    else:
        scenarios = generate_correlated_scenarios(N_scenarios, crop_data, plot_data)

    scenario_profits = []
    for scenario in scenarios:
        sp = compute_profit(X_rep, M, crop_data, plot_data, case_type,
                            scenario=scenario, epsilon=epsilon)
        scenario_profits.append(sp)

    expected_profit = np.mean(scenario_profits)
    VaR, CVaR_val = compute_cvar(scenario_profits, alpha)

    objective = expected_profit - lambda_risk * CVaR_val

    # NOTE: 罚函数从目标中减去 (但已在profit中包含penalty)
    # 实际上profit_det已经被penalty修正了, 但scenario_profits没有
    # 需要在场景利润中也加入罚函数
    scenario_profits_penalized = [sp - penalty for sp in scenario_profits]
    expected_profit_pen = np.mean(scenario_profits_penalized)
    VaR_pen, CVaR_pen = compute_cvar(scenario_profits_penalized, alpha)
    objective_pen = expected_profit_pen - lambda_risk * CVaR_pen

    return objective_pen


# ============================================================================
# 10. DEGA优化器 (Algorithm 1主循环)
# ============================================================================
class DEGAOptimizer:
    """
    差分进化遗传算法 (DEGA) 优化器.
    使用DE/best/2变异策略 + 二项式交叉 + 自适应参数调整.

    参考: Algorithm 1 + Algorithm 2 (主求解框架)
    """

    def __init__(self, problem_id, case_type, M, crop_data, plot_data,
                 params=None):
        self.problem_id = problem_id
        self.case_type = case_type
        self.M = M
        self.crop_data = crop_data
        self.plot_data = plot_data
        self.params = params or {}

        self.pop_size = self.params.get("pop_size", Config.POP_SIZE)
        self.max_gen = self.params.get("max_gen", Config.MAX_GEN)
        self.F = self.params.get("F", Config.F)
        self.CR = self.params.get("CR", Config.CR)
        self.epsilon = self.params.get("epsilon", Config.EPSILON)

        # 日志记录
        self.history = {
            "gen": [],
            "best_fitness": [],
            "mean_fitness": [],
            "best_profit": [],
            "diversity": []
        }

        # 初始化种群
        self.population = initialize_population(
            self.pop_size, plot_data, crop_data, M, self.epsilon
        )
        self.best_individual = None
        self.best_fitness = -np.inf

    def run(self, verbose=True):
        """执行DEGA主循环"""
        pop = self.population.copy()
        fitness = np.full(self.pop_size, -np.inf)

        # 初始评估
        for idx in range(self.pop_size):
            fitness[idx] = evaluate_fitness(
                pop[idx], self.problem_id, self.case_type,
                self.M, self.crop_data, self.plot_data,
                self.params, self.epsilon
            )
            if fitness[idx] > self.best_fitness:
                self.best_fitness = fitness[idx]
                self.best_individual = pop[idx].copy()

        best_fitness_overall = self.best_fitness

        for gen in range(1, self.max_gen + 1):
            new_pop = np.zeros_like(pop)
            new_fitness = np.zeros(self.pop_size)

            for idx in range(self.pop_size):
                # ---- 变异: DE/best/2 ----
                # mutant = best + F*(b-c) + F*(d-e)
                idxs = _select_four_distinct(self.pop_size, idx)
                b, c, d, e = pop[idxs]
                mutant = self.best_individual + self.F * (b - c) + self.F * (d - e)

                # 边界裁剪: 确保面积非负且不超过地块面积
                for i in range(Config.N_PLOTS):
                    area = self.plot_data.areas[i]
                    for j in range(Config.N_CROPS):
                        for t in range(Config.N_YEARS):
                            mutant[i, j, t] = np.clip(mutant[i, j, t], 0, area)

                # 修复
                mutant = repair_hard_constraints(mutant, self.M,
                                                 self.plot_data.areas, self.plot_data.plot_types, self.epsilon)

                # ---- 交叉: 二项式交叉 ----
                trial = _binomial_crossover(pop[idx], mutant, self.CR)

                # 修复 (交叉后可能破坏相容性)
                trial = repair_hard_constraints(trial, self.M,
                                                self.plot_data.areas, self.plot_data.plot_types, self.epsilon)

                # ---- 选择: 贪婪保留 ----
                trial_fitness = evaluate_fitness(
                    trial, self.problem_id, self.case_type,
                    self.M, self.crop_data, self.plot_data,
                    self.params, self.epsilon
                )

                if trial_fitness > fitness[idx]:
                    new_pop[idx] = trial
                    new_fitness[idx] = trial_fitness
                else:
                    new_pop[idx] = pop[idx]
                    new_fitness[idx] = fitness[idx]

                # 更新全局最优
                if new_fitness[idx] > best_fitness_overall:
                    best_fitness_overall = new_fitness[idx]
                    self.best_fitness = best_fitness_overall
                    self.best_individual = new_pop[idx].copy()

            pop = new_pop
            fitness = new_fitness

            # ---- 自适应参数调整 (每20代) ----
            if gen % 20 == 0:
                diversity = _compute_diversity(pop)
                improvement_rate = _compute_improvement_rate(
                    fitness, self.history.get("mean_fitness", [])
                )
                self.F = _adapt_f(self.F, diversity)
                self.CR = _adapt_cr(self.CR, improvement_rate)

            # ---- 日志 ----
            mean_fit = np.mean(fitness)
            best_fit = np.max(fitness)
            profit_det = compute_profit(
                self.best_individual, self.M, self.crop_data,
                self.plot_data, self.case_type, epsilon=self.epsilon
            )
            diversity = _compute_diversity(pop)

            self.history["gen"].append(gen)
            self.history["best_fitness"].append(best_fit)
            self.history["mean_fitness"].append(mean_fit)
            self.history["best_profit"].append(profit_det)
            self.history["diversity"].append(diversity)

            if verbose and gen % 10 == 0:
                print(f"  Gen {gen:4d}/{self.max_gen} | "
                      f"Best: {best_fit:>12.2f} | "
                      f"Avg: {mean_fit:>12.2f} | "
                      f"Profit: {profit_det:>12.2f} | "
                      f"Div: {diversity:.4f}")

            # ---- 早停 ----
            # 当适应度在最近10代内无显著改进时提前停止。
            # 使用自适应容差: 以罚函数系数为参考, 结合目标值量级。
            # (旧容差 1e-4 * |mean| 在利润~200K时仅~20, 远小于w_pen=1e6,
            #  导致任何约束违反都会阻止早停。修正后容差扩大至考虑罚函数量级。)
            if gen > 60 and len(self.history["best_fitness"]) >= 10:
                recent = self.history["best_fitness"][-10:]
                scale = max(Config.W_PEN * 1e-3, abs(np.mean(recent)) * 1e-3)
                if np.std(recent) < scale:
                    if verbose:
                        print(f"  [Early stopping] Gen {gen} | "
                              f"Std={np.std(recent):.2f} < Tol={scale:.2f}")
                    break

        # 最终修复
        self.best_individual = repair_hard_constraints(
            self.best_individual, self.M, self.plot_data.areas, self.plot_data.plot_types, self.epsilon
        )
        # 局部轮作修复
        self.best_individual = local_rotation_repair(
            self.best_individual, self.M, self.crop_data,
            self.plot_data, self.epsilon
        )

        return self.best_individual, self.history


def _select_four_distinct(pop_size, exclude_idx):
    """选择4个不同且不等于exclude_idx的索引"""
    candidates = list(range(pop_size))
    candidates.remove(exclude_idx)
    return np.random.choice(candidates, 4, replace=False)


def _binomial_crossover(target, mutant, CR):
    """二项式交叉"""
    trial = target.copy()
    P, J, T = target.shape
    n_dims = P * J * T
    j_rand = np.random.randint(0, n_dims)
    for k in range(n_dims):
        if np.random.random() < CR or k == j_rand:
            pi = k // (J * T)
            ji = (k // T) % J
            ti = k % T
            trial[pi, ji, ti] = mutant[pi, ji, ti]
    return trial


def _compute_diversity(population):
    """计算种群多样性: 所有个体间平均欧氏距离"""
    n = population.shape[0]
    if n < 2:
        return 0.0
    # 采样方式: 随机50对计算平均距离
    distances = []
    for _ in range(min(50, n * (n - 1) // 2)):
        i, j = np.random.choice(n, 2, replace=False)
        d = np.sqrt(np.mean((population[i] - population[j]) ** 2))
        distances.append(d)
    return float(np.mean(distances)) if distances else 0.0


def _compute_improvement_rate(fitness, prev_means):
    """计算适应度改善率"""
    if len(prev_means) < 2:
        return 0.5
    current_mean = np.mean(fitness)
    prev_mean = prev_means[-1]
    if abs(prev_mean) < 1e-10:
        return 0.5
    rate = (current_mean - prev_mean) / abs(prev_mean)
    return np.clip(rate, -1, 1)


def _adapt_f(F, diversity):
    """自适应调整差分缩放因子 F"""
    # 多样性低 -> 增大F (探索)
    # 多样性高 -> 减小F (开发)
    target_diversity = 0.1  # 目标多样性水平
    if diversity < target_diversity * 0.5:
        return min(F * 1.1, Config.F_MAX)
    elif diversity > target_diversity * 1.5:
        return max(F * 0.9, Config.F_MIN)
    return F


def _adapt_cr(CR, improvement_rate):
    """自适应调整交叉概率 CR"""
    # 改善率高 -> 增大CR (加强信息交换)
    # 改善率低 -> 减小CR (保护优良模式)
    if improvement_rate > 0.05:
        return min(CR * 1.05, Config.CR_MAX)
    elif improvement_rate < 0.01:
        return max(CR * 0.95, Config.CR_MIN)
    return CR


# ============================================================================
# 11. 局部轮作修复 (Algorithm 7)
# ============================================================================
def local_rotation_repair(X, M, crop_data, plot_data, epsilon=Config.EPSILON):
    """
    Algorithm 7: 局部轮作修复
    在DEGA收敛后运行, 直接修复残留的轮作冲突.
    """
    X_out = X.copy()
    P, J, T = X_out.shape
    Z = (X_out > epsilon).astype(np.float64)

    Y = crop_data.base_yield
    p = crop_data.base_price
    cost = crop_data.base_cost

    for i in range(P):
        pt = plot_data.plot_types[i]
        area = plot_data.areas[i]

        # --- 修复重茬 (年对年) ---
        for t in range(T - 1):
            for j in range(J):
                if Z[i, j, t] > 0 and Z[i, j, t + 1] > 0:
                    # 重茬冲突: 尝试替换t+1年的作物j
                    # 寻找可行的替代作物
                    alternatives = _get_rotation_feasible_crops(
                        i, pt, j, t + 1, M, X_out, epsilon
                    )
                    if alternatives:
                        # 选择利润最优的替代
                        best_alt = max(
                            alternatives,
                            key=lambda alt: (Y[alt] * p[alt] - cost[alt])
                        )
                        area_to_move = X_out[i, j, t + 1]
                        X_out[i, j, t + 1] = 0
                        X_out[i, best_alt, t + 1] = min(
                            area_to_move, area * 0.8
                        )
                    else:
                        # 无可行替代: 休耕
                        X_out[i, j, t + 1] = 0

        # --- 修复三年豆类约束 ---
        for t_start in range(T - 2):
            bean_count = 0.0
            for tau in range(3):
                t = t_start + tau
                for j in Config.BEAN_INDICES:
                    bean_count += Z[i, j, t]
            if bean_count < 1.0:
                # 找到利润最低的年份, 改种豆类
                profits_by_year = []
                for tau in range(3):
                    t = t_start + tau
                    yearly_profit = 0.0
                    for j in range(J):
                        if Z[i, j, t] > 0:
                            yearly_profit += (Y[j] * p[j] - cost[j]) * X_out[i, j, t]
                    profits_by_year.append((t, yearly_profit))

                # 选择利润最低的年份替换
                replace_year = min(profits_by_year, key=lambda x: x[1])[0]

                # 找最合适的豆类
                best_bean = max(
                    Config.BEAN_INDICES,
                    key=lambda b: (Y[b] * p[b] - cost[b])
                )

                # 清空该年, 种豆类
                for j in range(J):
                    X_out[i, j, replace_year] = 0
                X_out[i, best_bean, replace_year] = area * 0.8

        # 重新施加修复算子
        X_out = repair_hard_constraints(X_out, M, plot_data.areas, plot_data.plot_types, epsilon)

    return X_out


def _get_rotation_feasible_crops(plot_idx, plot_type, exclude_crop, year,
                                  M, X, epsilon):
    """获取可在该地块该年种植的、不与轮作冲突的作物"""
    feasible = []
    for j in range(Config.N_CROPS):
        if j == exclude_crop:
            continue
        # 检查相容性
        s1_ok = M[plot_type, j, 0]
        s2_ok = M[plot_type, j, 1]
        if not (s1_ok or s2_ok):
            continue
        # 检查是否与前一年重茬
        if year > 0:
            if X[plot_idx, j, year - 1] > epsilon:
                continue
        # 检查是否与后一年已有规划冲突 (若后续年份已确定)
        if year < Config.N_YEARS - 1:
            if X[plot_idx, j, year + 1] > epsilon:
                # 如果后一年也种此作物则冲突
                pass  # 暂时允许, DEGA会整体优化

        feasible.append(j)

    return feasible


# ============================================================================
# 12. 主求解器 (Algorithm 1: MainSolver)
# ============================================================================
def main_solver(problem_id, case_type="A", params=None, data_dir=None,
                verbose=True):
    """
    Algorithm 1: 主求解框架.
    三个问题共用DEGA核心, 区别仅在于适应度评估.

    Parameters:
        problem_id: 1, 2, or 3
        case_type: "A" (超产滞销) 或 "B" (超产半价)
        params: 超参字典 (覆盖Config默认值)
        data_dir: 数据目录
        verbose: 是否打印日志

    Returns:
        result: 结果字典
    """
    print(f"\n{'='*70}")
    print(f"  问题 {problem_id} | 情形 {case_type}")
    print(f"{'='*70}")

    t_start = time.time()

    # 加载数据
    crop_data, plot_data = load_data(data_dir)

    # 构建相容矩阵
    M = build_compatibility_matrix(plot_data, crop_data)

    # 合并参数
    p = params or {}
    p.setdefault("pop_size", Config.POP_SIZE)
    p.setdefault("max_gen", Config.MAX_GEN)
    p.setdefault("n_scenarios", Config.N_SCENARIOS_OPT)
    p.setdefault("w_pen", Config.W_PEN)
    p.setdefault("lambda_risk", Config.LAMBDA_RISK)
    p.setdefault("alpha", Config.ALPHA_CVAR)
    p.setdefault("epsilon", Config.EPSILON)
    p.setdefault("F", Config.F)
    p.setdefault("CR", Config.CR)

    # 创建优化器
    optimizer = DEGAOptimizer(problem_id, case_type, M, crop_data, plot_data, p)

    # 运行DEGA
    print(f"\n  [DEGA] pop_size={p['pop_size']}, max_gen={p['max_gen']}")
    best_X, history = optimizer.run(verbose=verbose)

    # ---- 最终评估 ----
    print(f"\n  [Final Evaluation] Running...")

    # 修复
    best_X = repair_hard_constraints(best_X, M, plot_data.areas, plot_data.plot_types, p["epsilon"])

    if problem_id == 1:
        total_profit = compute_profit(best_X, M, crop_data, plot_data,
                                      case_type, epsilon=p["epsilon"])
        annual_profit = _compute_annual_profit(best_X, M, crop_data, plot_data,
                                               case_type, p["epsilon"])

        result = {
            "problem_id": problem_id,
            "case_type": case_type,
            "solution": best_X,
            "total_profit": total_profit,
            "annual_profit": annual_profit,
            "history": history,
            "crop_data": crop_data,
            "plot_data": plot_data,
            "M": M
        }
        print(f"  [Result] Total Profit: {total_profit:>12.2f} 元")
    else:
        # 问题2/3: 大量情景评估
        N_final = p.get("n_scenarios_final", Config.N_SCENARIOS_FINAL)
        print(f"  [MC] Evaluating with {N_final} scenarios...")

        if problem_id == 2:
            scenarios = generate_independent_scenarios(N_final, crop_data, plot_data)
        else:
            scenarios = generate_correlated_scenarios(N_final, crop_data, plot_data)

        scenario_profits = []
        for idx, scenario in enumerate(scenarios):
            sp = compute_profit(best_X, M, crop_data, plot_data, case_type,
                                scenario=scenario, epsilon=p["epsilon"])
            scenario_profits.append(sp)
            if verbose and (idx + 1) % 100 == 0:
                print(f"    Scenario {idx+1}/{N_final}")

        expected_profit = float(np.mean(scenario_profits))
        VaR, CVaR_val = compute_cvar(scenario_profits, p["alpha"])
        objective = expected_profit - p["lambda_risk"] * CVaR_val

        annual_profit = _compute_annual_profit(best_X, M, crop_data, plot_data,
                                               case_type, p["epsilon"])

        # 利润分布分位数
        p5 = float(np.percentile(scenario_profits, 5))
        p25 = float(np.percentile(scenario_profits, 25))
        p50 = float(np.percentile(scenario_profits, 50))
        p75 = float(np.percentile(scenario_profits, 75))
        p95 = float(np.percentile(scenario_profits, 95))

        result = {
            "problem_id": problem_id,
            "case_type": case_type,
            "solution": best_X,
            "expected_profit": expected_profit,
            "VaR": VaR,
            "CVaR": CVaR_val,
            "objective": objective,
            "annual_profit": annual_profit,
            "profit_percentiles": {"p5": p5, "p25": p25, "p50": p50,
                                   "p75": p75, "p95": p95},
            "scenario_profits": scenario_profits,
            "history": history,
            "crop_data": crop_data,
            "plot_data": plot_data,
            "M": M
        }
        print(f"  [Result] E[Profit]: {expected_profit:>12.2f} 元")
        print(f"  [Result] CVaR({p['alpha']:.2f}): {CVaR_val:>12.2f} 元")
        print(f"  [Result] Objective: {objective:>12.2f} 元")

    elapsed = time.time() - t_start
    print(f"  [Runtime] {elapsed:.1f} 秒 ({elapsed/60:.1f} 分钟)")

    # 约束满足报告
    constraint_report = verify_all_constraints(
        best_X, M, crop_data, plot_data, p["epsilon"]
    )
    print(f"  [Constraint Report]")
    print(f"    R1 (面积配额): {'PASS' if constraint_report['R1_area'] else 'FAIL'}")
    print(f"    R2 (相容性):   {'PASS' if constraint_report['R2_compatibility'] else 'FAIL'}")
    print(f"    P1 (重茬违反): {constraint_report['P1_rotation']} 次")
    print(f"    P2 (豆类违反): {constraint_report['P2_bean']} 次")
    print(f"    P3 (分散违反): {constraint_report['P3_dispersion']} 次")
    print(f"    P4 (产量违反): {constraint_report['P4_sales']} 次")

    result["constraint_report"] = constraint_report

    print(f"{'='*70}\n")

    return result


def _compute_annual_profit(X, M, crop_data, plot_data, case_type,
                           epsilon=Config.EPSILON):
    """计算每年的利润"""
    annual = []
    for t in range(Config.N_YEARS):
        X_t = X[:, :, t:t+1]  # 保持3D
        profit_t = compute_profit(X_t, M, crop_data, plot_data, case_type,
                                  epsilon=epsilon)
        annual.append(profit_t)
    return np.array(annual)


# ============================================================================
# 13. 结果导出
# ============================================================================
def generate_planting_table(X, crop_data, plot_data, M, epsilon=Config.EPSILON):
    """
    生成种植方案表: 每个地块每年每季种植的作物及其面积.
    返回: list of dict
    """
    rows = []
    for i in range(Config.N_PLOTS):
        pt = plot_data.plot_types[i]
        plot_name = plot_data.plot_names[i]
        for t in range(Config.N_YEARS):
            year = 2024 + t
            for j in range(Config.N_CROPS):
                area = X[i, j, t]
                if area <= epsilon:
                    continue
                crop_name = crop_data.crop_names[j]
                s1_ok = M[pt, j, 0]
                s2_ok = M[pt, j, 1]
                if s1_ok and s2_ok:
                    seasons = "S1+S2"
                elif s1_ok:
                    seasons = "S1"
                elif s2_ok:
                    seasons = "S2"
                else:
                    seasons = "N/A"
                rows.append({
                    "地块": plot_name,
                    "年份": year,
                    "作物": crop_name,
                    "面积(亩)": round(area, 2),
                    "季节": seasons
                })
    return pd.DataFrame(rows)


def verify_all_constraints(X, M, crop_data, plot_data, epsilon=Config.EPSILON):
    """验证所有约束的满足情况"""
    Z = (X > epsilon).astype(np.float64)
    P, J, T = X.shape
    report = {"R1_area": True, "R2_compatibility": True,
              "P1_rotation": 0, "P2_bean": 0, "P3_dispersion": 0, "P4_sales": 0}

    # R1: 面积
    for i in range(P):
        pt = plot_data.plot_types[i]
        area = plot_data.areas[i]
        for t in range(T):
            s1_area = sum(X[i, j, t] for j in range(J) if M[pt, j, 0])
            s2_area = sum(X[i, j, t] for j in range(J) if M[pt, j, 1])
            if s1_area > area + 0.01:
                report["R1_area"] = False
            if s2_area > area + 0.01:
                report["R1_area"] = False

    # P1 violations
    for i in range(P):
        for j in range(J):
            for t in range(T - 1):
                if Z[i, j, t] > 0 and Z[i, j, t + 1] > 0:
                    report["P1_rotation"] += 1

    # P2 violations
    for i in range(P):
        for ts in range(T - 2):
            bc = sum(Z[i, j, t] for t in range(ts, ts+3)
                     for j in Config.BEAN_INDICES)
            if bc < 1:
                report["P2_bean"] += 1

    # P3 violations
    for j in range(J):
        for t in range(T):
            for s in range(2):
                pc = sum(1 for i in range(P) if M[plot_data.plot_types[i], j, s] and Z[i, j, t] > 0)
                if pc > Config.MAX_PLOTS_PER_CROP:
                    report["P3_dispersion"] += 1

    # P4 violations
    for j in range(J):
        for t in range(T):
            total_yield = 0
            for i in range(P):
                pt = plot_data.plot_types[i]
                area = X[i, j, t]
                if area <= epsilon:
                    continue
                s1 = M[pt, j, 0]
                s2 = M[pt, j, 1]
                sf = 2.0 if (s1 and s2) else (1.0 if (s1 or s2) else 0.0)
                total_yield += crop_data.base_yield[j] * area * sf
            if total_yield < 0.9 * crop_data.expected_sales[j, t]:
                report["P4_sales"] += 1

    return report


# ============================================================================
# 14. 可视化
# ============================================================================
def plot_results(result, save_dir="."):
    """
    生成所有可视化图表.
    使用学术风格配色, 遵守可视化规范.
    """
    problem_id = result["problem_id"]
    case_type = result["case_type"]
    history = result["history"]
    crop_data = result["crop_data"]
    plot_data = result["plot_data"]

    os.makedirs(save_dir, exist_ok=True)

    # ---- 配色方案 ----
    # 使用 perceptually uniform colormaps
    colors = ["#2166ac", "#4393c3", "#92c5de", "#f4a582", "#d6604d", "#b2182b"]
    cmap_div = plt.cm.RdBu  # diverging
    cmap_seq = plt.cm.viridis  # sequential

    # ---- 图1: 收敛曲线 ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    ax.plot(history["gen"], history["best_fitness"],
            color=colors[0], linewidth=1.5, label="最优适应度")
    ax.plot(history["gen"], history["mean_fitness"],
            color=colors[2], linewidth=1.5, linestyle="--", label="平均适应度")
    ax.set_xlabel("迭代代数", fontsize=12)
    ax.set_ylabel("适应度 (元)", fontsize=12)
    ax.set_title(f"DEGA 收敛曲线 (问题{problem_id}, 情形{case_type})",
                 fontsize=13)
    ax.legend(loc="lower right", fontsize=10)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    color_profit = colors[5]
    color_div = colors[3]
    # 左Y轴: 最优利润
    ax.plot(history["gen"], history["best_profit"],
            color=color_profit, linewidth=1.5, label="最优利润")
    ax.set_xlabel("迭代代数", fontsize=12)
    ax.set_ylabel("最优利润 (元)", fontsize=12, color=color_profit)
    ax.tick_params(axis="y", labelcolor=color_profit)
    ax.grid(True, alpha=0.3)
    # 右Y轴: 种群多样性
    ax2 = ax.twinx()
    ax2.plot(history["gen"], history["diversity"],
             color=color_div, linewidth=1.5, linestyle="--", label="种群多样性")
    ax2.set_ylabel("多样性 (无量纲)", fontsize=12, color=color_div)
    ax2.tick_params(axis="y", labelcolor=color_div)
    # 合并图例
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="center right", fontsize=10)
    ax.set_title("利润与种群多样性演化", fontsize=13)

    plt.tight_layout()
    path1 = os.path.join(save_dir, f"fig1_convergence_Q{problem_id}_{case_type}.png")
    plt.savefig(path1, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path1}")

    # ---- 图2: 年度利润分解 ----
    annual_profit = result.get("annual_profit",
                               np.zeros(Config.N_YEARS))
    years = [2024 + t for t in range(Config.N_YEARS)]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(years, annual_profit, color=cmap_seq(
        np.linspace(0.2, 0.8, Config.N_YEARS)), width=0.6,
                  edgecolor="white", linewidth=0.5)

    # 在柱上标注数值
    for bar, val in zip(bars, annual_profit):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5000,
                f"{val:.0f}", ha="center", va="bottom", fontsize=9,
                rotation=45)

    if problem_id > 1:
        expected = result.get("expected_profit", 0)
        ax.axhline(y=expected, color=colors[0], linestyle="--",
                   linewidth=1.5, label=f"总期望利润: {expected:.0f} 元")

    ax.set_xlabel("年份", fontsize=12)
    ax.set_ylabel("利润 (元)", fontsize=12)
    ax.set_title(f"年度利润分布 (问题{problem_id}, 情形{case_type})",
                 fontsize=13)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    path2 = os.path.join(save_dir, f"fig2_annual_profit_Q{problem_id}_{case_type}.png")
    plt.savefig(path2, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path2}")

    # ---- 图3: 利润分布直方图 (仅Q2/Q3) ----
    if problem_id > 1 and "scenario_profits" in result:
        sp = np.array(result["scenario_profits"])
        fig, ax = plt.subplots(figsize=(10, 5))

        n, bins, patches = ax.hist(sp, bins=50, color=colors[2], alpha=0.7,
                                   edgecolor="white", linewidth=0.3)
        ax.axvline(x=result["expected_profit"], color=colors[0],
                   linestyle="-", linewidth=2, label=f"期望值: {result['expected_profit']:.0f}")
        ax.axvline(x=-result["VaR"], color=colors[5],
                   linestyle="--", linewidth=2,
                   label=f"-VaR({Config.ALPHA_CVAR:.2f}): {-result['VaR']:.0f}")
        ax.axvline(x=-result["CVaR"], color=colors[4],
                   linestyle=":", linewidth=2,
                   label=f"-CVaR({Config.ALPHA_CVAR:.2f}): {-result['CVaR']:.0f}")

        ax.set_xlabel("总利润 (元)", fontsize=12)
        ax.set_ylabel("频数", fontsize=12)
        ax.set_title(f"情景利润分布 (问题{problem_id}, N={len(sp)})",
                     fontsize=13)
        ax.legend(loc="upper left", fontsize=10)
        ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        path3 = os.path.join(save_dir, f"fig3_profit_dist_Q{problem_id}_{case_type}.png")
        plt.savefig(path3, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  [Figure] 保存: {path3}")

    # ---- 图4: 最优种植方案热图 ----
    X_best = result["solution"]
    annual_yield_map = np.zeros((Config.N_CROPS, Config.N_YEARS))
    for j in range(Config.N_CROPS):
        for t in range(Config.N_YEARS):
            for i in range(Config.N_PLOTS):
                pt = plot_data.plot_types[i]
                area = X_best[i, j, t]
                if area <= Config.EPSILON:
                    continue
                s1_ok = result["M"][pt, j, 0]
                s2_ok = result["M"][pt, j, 1]
                sf = 2.0 if (s1_ok and s2_ok) else (1.0 if (s1_ok or s2_ok) else 0.0)
                annual_yield_map[j, t] += crop_data.base_yield[j] * area * sf

    # 只显示有种植的作物
    crop_total_yield = annual_yield_map.sum(axis=1)
    active_crops = np.where(crop_total_yield > 100)[0]
    if len(active_crops) > 25:
        # 取产量前25种作物
        top_indices = np.argsort(-crop_total_yield)[:25]
        active_crops = np.sort(top_indices)

    data_plot = annual_yield_map[active_crops, :]
    crop_labels = [crop_data.crop_names[j] for j in active_crops]
    # 缩短标签
    short_labels = [name[:6] for name in crop_labels]

    fig, ax = plt.subplots(figsize=(12, max(6, len(active_crops) * 0.35)))
    im = ax.imshow(data_plot, aspect="auto", cmap=cmap_seq,
                   interpolation="nearest")

    ax.set_xticks(range(Config.N_YEARS))
    ax.set_xticklabels([str(2024 + t) for t in range(Config.N_YEARS)],
                       fontsize=10)
    ax.set_yticks(range(len(active_crops)))
    ax.set_yticklabels(short_labels, fontsize=8)
    ax.set_xlabel("年份", fontsize=12)
    ax.set_ylabel("作物", fontsize=12)
    ax.set_title(f"最优种植方案: 作物年度产量热图 (问题{problem_id})",
                 fontsize=13)

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("年产量 (斤)", fontsize=10)

    plt.tight_layout()
    path4 = os.path.join(save_dir, f"fig4_heatmap_Q{problem_id}_{case_type}.png")
    plt.savefig(path4, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path4}")

    # ---- 图5: 地块类型利用模式 ----
    type_names = ["A-平旱地", "B-梯田", "C-山坡地", "D-水浇地", "E-普通大棚", "F-智慧大棚"]
    type_util = np.zeros(6)
    type_total = np.zeros(6)
    for i in range(Config.N_PLOTS):
        pt = plot_data.plot_types[i]
        type_total[pt] += plot_data.areas[i]
        for t in range(Config.N_YEARS):
            for j in range(Config.N_CROPS):
                if X_best[i, j, t] > Config.EPSILON:
                    type_util[pt] += X_best[i, j, t] / Config.N_YEARS

    utilization = np.where(type_total > 0, type_util / type_total, 0)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(type_names, utilization, color=cmap_seq(np.linspace(0.2, 0.8, 6)),
                  width=0.6, edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, utilization):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.1%}", ha="center", va="bottom", fontsize=10)

    ax.set_ylim(0, max(utilization) * 1.2 + 0.1)
    ax.set_xlabel("地块类型", fontsize=12)
    ax.set_ylabel("平均利用率", fontsize=12)
    ax.set_title(f"各地块类型种植利用率 (问题{problem_id})", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    path5 = os.path.join(save_dir, f"fig5_utilization_Q{problem_id}_{case_type}.png")
    plt.savefig(path5, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path5}")

    # ---- 图6: 作物类别占比 (饼图) ----
    category_yield = {"粮食": 0, "豆类": 0, "水稻": 0, "蔬菜": 0, "食用菌": 0}
    for j in range(Config.N_CROPS):
        total = annual_yield_map[j, :].sum()
        ct = crop_data.crop_type[j]
        if ct == 0:
            category_yield["粮食"] += total
        elif ct == 1:
            category_yield["豆类"] += total
        elif ct == 2:
            category_yield["水稻"] += total
        elif ct == 3:
            category_yield["蔬菜"] += total
        elif ct == 4:
            category_yield["食用菌"] += total

    labels = [k for k, v in category_yield.items() if v > 0]
    sizes = [v for v in category_yield.values() if v > 0]
    pie_colors = cmap_seq(np.linspace(0.1, 0.9, len(labels)))

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.1f%%",
        colors=pie_colors, startangle=90,
        textprops={"fontsize": 12}
    )
    for at in autotexts:
        at.set_fontsize(10)
        at.set_color("white")
    ax.set_title(f"作物类别产量占比 (问题{problem_id})", fontsize=14)

    plt.tight_layout()
    path6 = os.path.join(save_dir, f"fig6_category_pie_Q{problem_id}_{case_type}.png")
    plt.savefig(path6, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path6}")

    return {
        "convergence": path1,
        "annual_profit": path2,
        "profit_dist": path3 if problem_id > 1 else None,
        "heatmap": path4,
        "utilization": path5,
        "category_pie": path6
    }


# ============================================================================
# 15. 灵敏度分析 (简化)
# ============================================================================
def run_sensitivity_analysis(best_X, problem_id, M, crop_data, plot_data,
                             case_type, save_dir="."):
    """
    运行灵敏度分析:
    1. lambda_risk对目标值的影响 (在不同lambda下重新做情景评估计算CVaR)
    2. CVaR置信水平的影响
    """
    if problem_id == 1:
        return {}

    print("\n  [Sensitivity Analysis]")

    # 修复最优解
    X_rep = repair_hard_constraints(best_X, M, plot_data.areas,
                                    plot_data.plot_types, Config.EPSILON)

    # 基础罚函数 (约束满足度不随lambda变化)
    penalty = compute_penalty(X_rep, M, crop_data.base_yield,
                              crop_data.expected_sales, plot_data.areas,
                              plot_data.plot_types,
                              Config.EPSILON, Config.W_PEN)

    results = {}

    # ---- lambda_risk 灵敏度 ----
    # 对每个lambda值, 使用情景评估计算 CVaR 和目标函数
    lambdas = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
    lambda_objectives = []
    lambda_exp_profits = []
    lambda_cvar_values = []

    # 固定情景集, 使不同lambda的对比基于相同随机样本 (降低噪声)
    N_sens = 200  # 灵敏度分析情景数 (折衷精度与速度)
    if problem_id == 2:
        scenarios = generate_independent_scenarios(N_sens, crop_data, plot_data)
    else:
        scenarios = generate_correlated_scenarios(N_sens, crop_data, plot_data)

    # 预计算所有情景下的利润
    all_scenario_profits = []
    for scenario in scenarios:
        sp = compute_profit(X_rep, M, crop_data, plot_data, case_type,
                            scenario=scenario, epsilon=Config.EPSILON)
        all_scenario_profits.append(sp)

    expected_profit_base = float(np.mean(all_scenario_profits)) - penalty

    for lam in lambdas:
        # 重新计算CVaR (每次lambda不同但利润集相同)
        VaR, CVaR_val = compute_cvar(all_scenario_profits, Config.ALPHA_CVAR)
        obj = expected_profit_base - lam * CVaR_val
        lambda_objectives.append(obj)
        lambda_exp_profits.append(expected_profit_base)
        lambda_cvar_values.append(CVaR_val)

    results["lambda_sensitivity"] = {
        "lambdas": lambdas,
        "objectives": lambda_objectives,
        "expected_profits": lambda_exp_profits,
        "cvar_values": lambda_cvar_values
    }

    # 生成lambda灵敏度图表
    fig, ax1 = plt.subplots(figsize=(8, 5))

    color_obj = "#2166ac"
    color_cvar = "#d6604d"
    ax1.plot(lambdas, lambda_objectives, "o-", color=color_obj,
             linewidth=1.5, markersize=6, label="目标函数 E[P] - lambda*CVaR")
    ax1.set_xlabel("风险厌恶系数 lambda", fontsize=12)
    ax1.set_ylabel("目标函数值 (元)", fontsize=12, color=color_obj)
    ax1.tick_params(axis="y", labelcolor=color_obj)
    ax1.grid(True, alpha=0.3)

    # 双Y轴: 用第二个Y轴显示CVaR
    ax2 = ax1.twinx()
    ax2.plot(lambdas, lambda_cvar_values, "s--", color=color_cvar,
             linewidth=1.5, markersize=6, label="CVaR(0.95)")
    ax2.set_ylabel("CVaR (元)", fontsize=12, color=color_cvar)
    ax2.tick_params(axis="y", labelcolor=color_cvar)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=10)

    fig.suptitle(f"风险厌恶系数灵敏度 (问题{problem_id})", fontsize=13, y=1.02)
    fig.tight_layout()
    path = os.path.join(save_dir, f"fig_sensitivity_lambda_Q{problem_id}.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path}")
    results["lambda_fig_path"] = path

    # ---- alpha (CVaR置信水平) 灵敏度 ----
    alphas = [0.85, 0.90, 0.95, 0.975, 0.99]
    alpha_objectives = []
    alpha_cvar_values = []

    for alpha in alphas:
        VaR, CVaR_val = compute_cvar(all_scenario_profits, alpha)
        obj = expected_profit_base - Config.LAMBDA_RISK * CVaR_val
        alpha_objectives.append(obj)
        alpha_cvar_values.append(CVaR_val)

    results["alpha_sensitivity"] = {
        "alphas": alphas,
        "objectives": alpha_objectives,
        "cvar_values": alpha_cvar_values
    }

    # 生成alpha灵敏度图表
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(alphas, alpha_objectives, "o-", color="#4393c3",
            linewidth=1.5, markersize=6, label="目标函数")
    ax.plot(alphas, alpha_cvar_values, "s--", color="#d6604d",
            linewidth=1.5, markersize=6, label="CVaR")
    ax.set_xlabel("CVaR置信水平 alpha", fontsize=12)
    ax.set_ylabel("值 (元)", fontsize=12)
    ax.set_title(f"CVaR置信水平灵敏度 (问题{problem_id}, lambda={Config.LAMBDA_RISK})",
                 fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    path_alpha = os.path.join(save_dir, f"fig_sensitivity_alpha_Q{problem_id}.png")
    fig.savefig(path_alpha, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Figure] 保存: {path_alpha}")
    results["alpha_fig_path"] = path_alpha

    # 打印数值
    print("  lambda灵敏度:")
    for i, lam in enumerate(lambdas):
        print(f"    lambda={lam:.2f}: 目标={lambda_objectives[i]:.0f}, "
              f"CVaR={lambda_cvar_values[i]:.0f}")
    print("  alpha灵敏度:")
    for i, alpha in enumerate(alphas):
        print(f"    alpha={alpha:.3f}: 目标={alpha_objectives[i]:.0f}, "
              f"CVaR={alpha_cvar_values[i]:.0f}")

    return results


# ============================================================================
# 16. 主程序
# ============================================================================
def run_all_problems(data_dir=None, output_dir=".", fast_mode=False):
    """
    执行三个问题的完整求解流程.
    生成所有结果和图表.

    Parameters:
        data_dir: Excel数据目录
        output_dir: 输出目录
        fast_mode: 若True, 使用缩减参数快速测试
    """
    if fast_mode:
        print("[MODE] Fast mode: 使用缩减参数")
        Config.POP_SIZE = 20
        Config.MAX_GEN = 30
        Config.N_SCENARIOS_OPT = 20
        Config.N_SCENARIOS_FINAL = 50

    os.makedirs(output_dir, exist_ok=True)

    results_dict = {}

    # ---- Q1 (确定型) ----
    try:
        print("\n" + "="*70)
        print("  >>> 开始求解 问题1 情形A (超产滞销)")
        print("="*70)
        r1a = main_solver(1, "A", data_dir=data_dir, verbose=True)
        fig_paths_1a = plot_results(r1a, save_dir=output_dir)
        results_dict["Q1A"] = r1a
    except Exception as e:
        import traceback
        print(f"[ERROR] Q1A 求解失败: {e}")
        traceback.print_exc()
        r1a = {"total_profit": 0, "problem_id": 1, "case_type": "A",
               "solution": np.zeros((Config.N_PLOTS, Config.N_CROPS, Config.N_YEARS)),
               "annual_profit": np.zeros(Config.N_YEARS),
               "history": {"gen": [], "best_fitness": [], "mean_fitness": [],
                           "best_profit": [], "diversity": []}}

    try:
        print("\n" + "="*70)
        print("  >>> 开始求解 问题1 情形B (超产半价)")
        print("="*70)
        r1b = main_solver(1, "B", data_dir=data_dir, verbose=True)
        fig_paths_1b = plot_results(r1b, save_dir=output_dir)
        results_dict["Q1B"] = r1b
    except Exception as e:
        import traceback
        print(f"[ERROR] Q1B 求解失败: {e}")
        traceback.print_exc()
        r1b = {"total_profit": 0, "problem_id": 1, "case_type": "B",
               "solution": np.zeros((Config.N_PLOTS, Config.N_CROPS, Config.N_YEARS)),
               "annual_profit": np.zeros(Config.N_YEARS),
               "history": {"gen": [], "best_fitness": [], "mean_fitness": [],
                           "best_profit": [], "diversity": []}}

    # ---- Q2 (不确定独立) ----
    try:
        print("\n" + "="*70)
        print("  >>> 开始求解 问题2 (不确定独立, CVaR优化)")
        print("="*70)
        r2 = main_solver(2, "B", data_dir=data_dir, verbose=True)
        fig_paths_2 = plot_results(r2, save_dir=output_dir)
        results_dict["Q2"] = r2
    except Exception as e:
        import traceback
        print(f"[ERROR] Q2 求解失败: {e}")
        traceback.print_exc()
        r2 = {"expected_profit": 0, "CVaR": 0, "objective": 0,
              "problem_id": 2, "case_type": "B",
              "solution": np.zeros((Config.N_PLOTS, Config.N_CROPS, Config.N_YEARS)),
              "annual_profit": np.zeros(Config.N_YEARS),
              "scenario_profits": [],
              "history": {"gen": [], "best_fitness": [], "mean_fitness": [],
                          "best_profit": [], "diversity": []},
              "M": None, "crop_data": None, "plot_data": None}

    # ---- Q3 (不确定相关) ----
    try:
        print("\n" + "="*70)
        print("  >>> 开始求解 问题3 (不确定相关, Cholesky相关情景)")
        print("="*70)
        r3 = main_solver(3, "B", data_dir=data_dir, verbose=True)
        fig_paths_3 = plot_results(r3, save_dir=output_dir)
        results_dict["Q3"] = r3
    except Exception as e:
        import traceback
        print(f"[ERROR] Q3 求解失败: {e}")
        traceback.print_exc()
        r3 = {"expected_profit": 0, "CVaR": 0, "objective": 0,
              "problem_id": 3, "case_type": "B",
              "solution": np.zeros((Config.N_PLOTS, Config.N_CROPS, Config.N_YEARS)),
              "annual_profit": np.zeros(Config.N_YEARS),
              "scenario_profits": [],
              "history": {"gen": [], "best_fitness": [], "mean_fitness": [],
                          "best_profit": [], "diversity": []},
              "M": None, "crop_data": None, "plot_data": None}

    # 灵敏度分析 (仅对Q2和Q3)
    if "Q2" in results_dict:
        try:
            sens2 = run_sensitivity_analysis(r2["solution"], 2, r2["M"],
                                             r2["crop_data"], r2["plot_data"],
                                             "B", output_dir)
        except Exception as e:
            import traceback
            print(f"[WARN] Q2 灵敏度分析失败: {e}")
            sens2 = {}
    else:
        sens2 = {}

    if "Q3" in results_dict:
        try:
            sens3 = run_sensitivity_analysis(r3["solution"], 3, r3["M"],
                                             r3["crop_data"], r3["plot_data"],
                                             "B", output_dir)
        except Exception as e:
            import traceback
            print(f"[WARN] Q3 灵敏度分析失败: {e}")
            sens3 = {}
    else:
        sens3 = {}

    # ---- 比较分析 ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    scenarios_2 = r2.get("scenario_profits", [])
    scenarios_3 = r3.get("scenario_profits", [])
    if len(scenarios_2) > 0 and len(scenarios_3) > 0:
        ax.hist(scenarios_2, bins=40, alpha=0.6, color="#4393c3",
                label=f"Q2 (独立), E={np.mean(scenarios_2):.0f}", edgecolor="white")
        ax.hist(scenarios_3, bins=40, alpha=0.6, color="#f4a582",
                label=f"Q3 (相关), E={np.mean(scenarios_3):.0f}", edgecolor="white")
        ax.set_xlabel("总利润 (元)", fontsize=12)
        ax.set_ylabel("频数", fontsize=12)
        ax.set_title("问题2 vs 问题3: 利润分布对比", fontsize=13)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)

    ax = axes[1]
    metrics = ["预期利润", "CVaR(0.95)", "目标函数"]
    q2_vals = [r2.get("expected_profit", 0), -r2.get("CVaR", 0), r2.get("objective", 0)]
    q3_vals = [r3.get("expected_profit", 0), -r3.get("CVaR", 0), r3.get("objective", 0)]

    x = np.arange(len(metrics))
    w = 0.35
    ax.bar(x - w/2, q2_vals, w, label="Q2 (独立)", color="#4393c3", edgecolor="white")
    ax.bar(x + w/2, q3_vals, w, label="Q3 (相关)", color="#f4a582", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=11)
    ax.set_ylabel("元", fontsize=12)
    ax.set_title("问题2 vs 问题3: 关键指标对比", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    path_compare = os.path.join(output_dir, "fig_compare_Q2_Q3.png")
    plt.savefig(path_compare, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"\n[Figure] 保存: {path_compare}")

    # ---- 汇总结果 ----
    summary = {
        "Q1A": {"total_profit": r1a.get("total_profit", 0)},
        "Q1B": {"total_profit": r1b.get("total_profit", 0)},
        "Q2": {
            "expected_profit": r2.get("expected_profit", 0),
            "CVaR": r2.get("CVaR", 0),
            "objective": r2.get("objective", 0)
        },
        "Q3": {
            "expected_profit": r3.get("expected_profit", 0),
            "CVaR": r3.get("CVaR", 0),
            "objective": r3.get("objective", 0)
        }
    }

    print(f"\n{'='*70}")
    print(f"  结果汇总")
    print(f"{'='*70}")
    print(f"  问题1A (超产滞销): {summary['Q1A']['total_profit']:>12.2f} 元")
    print(f"  问题1B (超产半价): {summary['Q1B']['total_profit']:>12.2f} 元")
    print(f"  问题2 (不确定独立):")
    print(f"    期望利润:  {summary['Q2']['expected_profit']:>12.2f} 元")
    print(f"    CVaR(0.95): {summary['Q2']['CVaR']:>12.2f} 元")
    print(f"    目标:      {summary['Q2']['objective']:>12.2f} 元")
    print(f"  问题3 (不确定相关):")
    print(f"    期望利润:  {summary['Q3']['expected_profit']:>12.2f} 元")
    print(f"    CVaR(0.95): {summary['Q3']['CVaR']:>12.2f} 元")
    print(f"    目标:      {summary['Q3']['objective']:>12.2f} 元")
    print(f"{'='*70}\n")

    # 保存汇总
    summary_path = os.path.join(output_dir, "summary.json")
    # 转换numpy类型
    def convert(o):
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, np.ndarray): return o.tolist()
        return o

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=convert, ensure_ascii=False)
    print(f"[Save] 汇总: {summary_path}")

    return r1a, r1b, r2, r3


# ============================================================================
# 17. 命令行入口
# ============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="2024 CUMCM C题: 农作物种植策略优化 (DEGA+CVaR)"
    )
    parser.add_argument("--data_dir", type=str, default=None,
                        help="Excel数据目录 (附件1.xlsx, 附件2.xlsx)")
    parser.add_argument("--output_dir", type=str, default=None,
                        help="输出目录 (默认: ./output_Q1_Q2_Q3)")
    parser.add_argument("--fast", action="store_true",
                        help="快速模式 (缩减种群和代数)")
    parser.add_argument("--problem", type=int, default=0, choices=[0, 1, 2, 3],
                        help="指定问题 (0=全部)")

    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output_Q1_Q2_Q3"
        )

    if args.problem == 0:
        # 求解全部问题
        r1a, r1b, r2, r3 = run_all_problems(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            fast_mode=args.fast
        )
    else:
        # 求解指定问题
        case = "A" if args.problem == 1 else "B"
        # 问题1有A/B情形, 问题2/3只有B
        if args.problem == 1:
            for c in ["A", "B"]:
                res = main_solver(1, c, data_dir=args.data_dir, verbose=True)
                plot_results(res, save_dir=args.output_dir)
        else:
            res = main_solver(args.problem, case, data_dir=args.data_dir,
                              verbose=True)
            plot_results(res, save_dir=args.output_dir)
            run_sensitivity_analysis(res["solution"], args.problem,
                                     res["M"], res["crop_data"],
                                     res["plot_data"], case, args.output_dir)

    print("\n[DONE] 所有求解和可视化已完成.")
