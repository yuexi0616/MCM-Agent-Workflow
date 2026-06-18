"""
Module: MCM 2025-D Mine Flood Evacuation Simulation
Description:
  矿井突水漫延仿真与矿工逃生路径规划系统
  1. 单源水流漫延（含部分填充量追踪 + 平面/三维）
  2. 标准时变 Dijkstra 逃生路径规划
  3. 双源并行漫延 + 节点级/边级碰撞检测
  4. 在线路径重规划
Author: Coding Expert Agent
Date: 2026-05-30

References:
  - algorithm-codebase.md: 最短路径算法参考
  - graph-flow-model.md: 图网络水流漫延模型
  - dynamic-dijkstra.md: 时变 Dijkstra 路径规划
  - bfs-graph-search.md: BFS 搜索在三维扩展中的应用

修订说明（对应 error-registry.json）:
  - M-2025D-015: flow_dir_flag 在情况2（部分湿润边）中初始化为 None，中途淹没检测时
                 检查 flow_dir_flag is not None 再使用，避免 NameError
  - M-2025D-016: get_remaining_segment 辅助函数已实现；路径对象不再附着 .total_time
                 属性（改为使用字典或元组返回）
"""

import os
import sys
import math
import heapq
import warnings
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set, Any

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 非交互模式，用于服务器/脚本环境
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.colors import Normalize
import matplotlib.patches as mpatches

# ============================================================================
# 全局配置与常量
# ============================================================================

# 固定随机种子，确保可复现性
np.random.seed(42)

# 巷道断面参数（宽4m × 高3m 矩形断面）
TUNNEL_WIDTH = 4.0      # m
TUNNEL_HEIGHT = 3.0     # m
CROSS_SECTION = TUNNEL_WIDTH * TUNNEL_HEIGHT  # 12 m²

# 水位参数
H0 = 0.1       # 初始铺满水位 (m)
H_SAFE = 0.3   # 安全涉水阈值 (m)
H_MAX = 3.0    # 巷道最大高度 (m)

# 突水参数
Q_SOURCE = 30.0  # 单突水点流量 (m³/min)

# 矿工行进速度 (全部统一为 m/min)
V_DRY = 240.0       # 干燥巷道 (4 m/s × 60)
V_WITH = 120.0      # 顺水行进 (2 m/s × 60)
V_AGAINST = 60.0    # 逆水行进 (1 m/s × 60)
V_MIX = 90.0        # 部分湿润巷道中间速度 (1.5 m/s × 60)

# 逃生通知时间
T_NOTICE = 1.0  # min，突水后 1 min 发布初始逃生通知

# 第二突水点时间偏移
T_OFFSET_B_PLANAR = 4.0   # 附件一（平面网络）B1 突水时间
T_OFFSET_B_3D = 5.0       # 附件二（三维网络）B2 突水时间

# 路径切换时间
T_SWITCH = 5.0   # min，在此时刻后切换至重规划路径

# 数值容差
EPS = 1e-10
INF = float('inf')

# 配色方案（学术风格，低饱和度）
COLOR_DRY = '#4A7C9E'        # 干燥巷道 - 蓝灰色
COLOR_WET = '#3D6B8A'         # 湿润巷道 - 深蓝灰
COLOR_FLOODED = '#8B4A4A'     # 淹没巷道 - 暗红
COLOR_PATH_INIT = '#2E7D32'   # 初始路径 - 暗绿
COLOR_PATH_NEW = '#C44536'    # 新路径 - 砖红
COLOR_SOURCE_A = '#D4524E'    # 突水点A - 红
COLOR_SOURCE_B = '#4A72A4'    # 突水点B - 蓝
COLOR_SAFE = '#2E7D32'        # 安全出口 - 绿
COLOR_MINER = '#FF8C42'       # 矿工位置 - 橙


# ============================================================================
# 数据结构定义
# ============================================================================

@dataclass
class Node:
    """巷道网络端点节点"""
    id: int                  # 节点编号（1-based 或 0-based）
    x: float                 # x 坐标 (m)
    y: float                 # y 坐标 (m)
    z: float = 0.0           # z 坐标 (m)，平面网络为 0

    @property
    def pos_2d(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @property
    def pos_3d(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class Edge:
    """巷道边"""
    id: int                  # 边编号
    node_u: int              # 端点 u 编号
    node_v: int              # 端点 v 编号
    length: float            # 巷道长度 (m)
    dz: float = 0.0          # 高度差 z_v - z_u (m)，正值为上升
    flag_up: int = 0         # 上升巷道标志: 1=上升(dz>0), 0=水平/下行


@dataclass
class WaterState:
    """水流漫延结果状态"""
    node_arrival: Dict[int, float]          # node_id -> 首次到达时间 (min)
    edge_spread_time: Dict[int, float]      # edge_id -> 铺满 0.1m 时间 (min)
    edge_0_3m_time: Dict[int, float]        # edge_id -> 水位达 0.3m 时间 (min)
    edge_full_time: Dict[int, float]        # edge_id -> 灌满 3m 时间 (min)
    t_spread: float = 0.0                   # 全部端点铺满 0.1m 的时刻 (min)
    T_total: float = 0.0                    # 全部巷道灌满 3m 的时刻 (min)
    flow_dir: Dict[int, int] = field(default_factory=dict)  # edge_id -> 水流方向: 1=u->v, -1=v->u, 0=未知


@dataclass
class SubGraph:
    """子图（用于三维扩展中的 V_low 诱导子图）"""
    nodes: Dict[int, Node]
    edges: Dict[int, Edge]
    adj_list: Dict[int, List[int]]  # node_id -> list of neighbor node_ids


class PathResult:
    """路径规划结果"""
    def __init__(self, path: Optional[List[int]], total_time: float):
        self.path = path            # 节点序列 [v1, v2, ..., vd]
        self.total_time = total_time  # 总逃生时间 (min)

    def is_feasible(self) -> bool:
        return self.path is not None and self.total_time < INF

    def __repr__(self) -> str:
        if self.is_feasible():
            return f"PathResult(path_len={len(self.path)}, time={self.total_time:.2f}min)"
        return "PathResult(infeasible)"


# ============================================================================
# 数据加载与合成数据生成
# ============================================================================

def load_mine_network(filepath: str, is_3d: bool = False) -> Tuple[Dict[int, Node], Dict[int, Edge]]:
    """
    从 Excel 文件加载矿井巷道网络数据。

    文件格式约定（基于附件一/附件二的结构）:
    - Nodes Sheet: 列 [ID, X, Y, Z]
    - Edges Sheet: 列 [ID, Node_U, Node_V, Length]

    参数:
        filepath: Excel 文件路径
        is_3d: 是否包含 Z 坐标（三维网络）

    返回:
        nodes: node_id -> Node
        edges: edge_id -> Edge

    注意: 若文件不存在或无法读取，将回退到合成数据。
    """
    nodes = {}
    edges = {}

    if not os.path.exists(filepath):
        print(f"[WARNING] 数据文件不存在: {filepath}")
        print(f"[INFO] 将使用合成数据进行演示。若使用真实数据，请将附件 Excel 文件放置于正确路径。")
        return nodes, edges

    try:
        xls = pd.ExcelFile(filepath)

        # 读取 Nodes Sheet
        if 'Nodes' in xls.sheet_names:
            df_nodes = pd.read_excel(filepath, sheet_name='Nodes')
        else:
            df_nodes = pd.read_excel(filepath, sheet_name=0)  # 默认第一个 sheet

        for _, row in df_nodes.iterrows():
            nid = int(row.iloc[0])
            x = float(row.iloc[1])
            y = float(row.iloc[2])
            z = float(row.iloc[3]) if is_3d and len(row) > 3 else 0.0
            nodes[nid] = Node(id=nid, x=x, y=y, z=z)

        # 读取 Edges Sheet
        if 'Edges' in xls.sheet_names:
            df_edges = pd.read_excel(filepath, sheet_name='Edges')
        elif len(xls.sheet_names) > 1:
            df_edges = pd.read_excel(filepath, sheet_name=1)
        else:
            print("[WARNING] 未找到 Edges sheet，将尝试从数据推断边连接关系")
            return nodes, edges

        for _, row in df_edges.iterrows():
            eid = int(row.iloc[0])
            u = int(row.iloc[1])
            v = int(row.iloc[2])
            length = float(row.iloc[3]) if len(row) > 3 else 0.0

            if u in nodes and v in nodes:
                # 计算长度（若未提供）
                if length <= 0:
                    dx = nodes[u].x - nodes[v].x
                    dy = nodes[u].y - nodes[v].y
                    dz = nodes[u].z - nodes[v].z
                    length = math.sqrt(dx*dx + dy*dy + dz*dz)

                # 计算高度差
                dz_actual = nodes[v].z - nodes[u].z
                flag_up = 1 if dz_actual > EPS else 0

                edges[eid] = Edge(
                    id=eid, node_u=u, node_v=v,
                    length=length, dz=dz_actual, flag_up=flag_up
                )

        print(f"[INFO] 成功加载网络: {len(nodes)} 节点, {len(edges)} 边")

    except Exception as e:
        print(f"[ERROR] 加载数据文件失败: {e}")
        print(f"[INFO] 将使用合成数据进行演示。")

    return nodes, edges


def generate_synthetic_planar_network(
    n_nodes: int = 100,
    grid_width: float = 800.0,
    grid_height: float = 600.0,
    branch_prob: float = 0.6,
    seed: int = 42
) -> Tuple[Dict[int, Node], Dict[int, Edge]]:
    """
    生成平面合成矿井网络（用于演示/测试）。

    生成策略:
    1. 在矩形区域内随机生成节点坐标
    2. 基于 Delaunay 三角剖分 + 随机子采样生成边
    3. 确保网络连通性

    参数:
        n_nodes: 节点数量（默认 100 用于快速演示；真实规模约 665）
        grid_width: 区域宽度 (m)
        grid_height: 区域高度 (m)
        branch_prob: 边生长概率
        seed: 随机种子

    返回:
        nodes, edges
    """
    rng = np.random.RandomState(seed)

    # 生成节点坐标：在网格区域内均匀分布，带有一些聚类
    n_clusters = max(3, n_nodes // 20)
    cluster_centers = rng.rand(n_clusters, 2) * [grid_width, grid_height]
    cluster_assign = rng.randint(0, n_clusters, n_nodes)

    nodes = {}
    for i in range(n_nodes):
        cx, cy = cluster_centers[cluster_assign[i]]
        offset = rng.randn(2) * min(grid_width, grid_height) * 0.08
        x = max(0, min(grid_width, cx + offset[0]))
        y = max(0, min(grid_height, cy + offset[1]))
        nodes[i] = Node(id=i, x=float(x), y=float(y), z=0.0)

    # 生成边：最近邻连接 + 随机长连接
    edges = {}
    edge_id = 0

    # 方法：每个节点连接到最近的 k 个邻居
    k_nearest = min(5, n_nodes - 1)
    node_pos = np.array([[n.x, n.y] for n in nodes.values()])

    # 记录已添加的边
    added_edges = set()

    for i in range(n_nodes):
        dists = np.sqrt(np.sum((node_pos - node_pos[i])**2, axis=1))
        nearest = np.argsort(dists)

        n_connect = 0
        for j in nearest[1:]:  # 排除自身
            if n_connect >= k_nearest:
                break
            if rng.rand() > branch_prob:
                continue
            if dists[j] > math.hypot(grid_width, grid_height) * 0.5:
                continue

            # 确保无重复边
            if (i, j) in added_edges or (j, i) in added_edges:
                continue

            length = float(dists[j])
            # 平面网络 dz=0, flag_up=0
            edges[edge_id] = Edge(
                id=edge_id, node_u=i, node_v=j,
                length=length, dz=0.0, flag_up=0
            )
            added_edges.add((i, j))
            edge_id += 1
            n_connect += 1

    # 添加一些随机长连接以增加网络复杂度
    n_long = max(5, n_nodes // 20)
    for _ in range(n_long):
        i = rng.randint(0, n_nodes)
        j = rng.randint(0, n_nodes)
        if i == j or (i, j) in added_edges or (j, i) in added_edges:
            continue
        dist = float(np.sqrt(np.sum((node_pos[i] - node_pos[j])**2)))
        if dist < math.hypot(grid_width, grid_height) * 0.15:
            continue
        edges[edge_id] = Edge(
            id=edge_id, node_u=i, node_v=j,
            length=dist, dz=0.0, flag_up=0
        )
        added_edges.add((i, j))
        edge_id += 1

    # 确保连通性：通过 BFS 检查，连接不连通的组件
    adj = defaultdict(list)
    for e in edges.values():
        adj[e.node_u].append(e.node_v)
        adj[e.node_v].append(e.node_u)

    visited = set()
    stack = [0]
    while stack:
        u = stack.pop()
        if u in visited:
            continue
        visited.add(u)
        for v in adj[u]:
            if v not in visited:
                stack.append(v)

    # 将孤立组件连接到主组件
    for i in range(n_nodes):
        if i not in visited:
            # 连接到最近的已访问节点
            dists = [((nodes[i].x - nodes[j].x)**2 + (nodes[i].y - nodes[j].y)**2, j)
                     for j in visited]
            dists.sort()
            if dists:
                _, j = dists[0]
                length = math.sqrt(dists[0][0])
                edges[edge_id] = Edge(
                    id=edge_id, node_u=i, node_v=j,
                    length=float(length), dz=0.0, flag_up=0
                )
                edge_id += 1
                visited.add(i)

    print(f"[INFO] 合成平面网络: {len(nodes)} 节点, {len(edges)} 边")
    return nodes, edges


def generate_synthetic_3d_network(
    n_nodes: int = 80,
    grid_width: float = 600.0,
    grid_height: float = 600.0,
    n_levels: int = 5,
    level_height: float = 30.0,
    seed: int = 42
) -> Tuple[Dict[int, Node], Dict[int, Edge]]:
    """
    生成三维合成矿井网络（用于演示/测试）。

    参数:
        n_nodes: 节点数量
        grid_width: 水平区域宽度 (m)
        grid_height: 水平区域高度 (m)
        n_levels: 高度层数
        level_height: 每层高度 (m)
        seed: 随机种子
    """
    rng = np.random.RandomState(seed + 1)

    # 分配节点到各层
    nodes_per_level = max(3, n_nodes // n_levels)
    nodes = {}

    for level in range(n_levels):
        z_base = level * level_height
        n_this_level = nodes_per_level if level < n_levels - 1 else n_nodes - level * nodes_per_level

        for j in range(n_this_level):
            nid = level * nodes_per_level + j
            if nid >= n_nodes:
                break
            x = rng.uniform(0, grid_width)
            y = rng.uniform(0, grid_height)
            z = z_base + rng.uniform(0, level_height * 0.3)
            nodes[nid] = Node(id=nid, x=float(x), y=float(y), z=float(z))

    # 生成边
    edges = {}
    edge_id = 0
    added_edges = set()

    # 水平边（同层内）
    for level in range(n_levels):
        level_nodes = [i for i in range(level * nodes_per_level,
                                        min((level + 1) * nodes_per_level, n_nodes))]
        for i in level_nodes:
            for j in level_nodes:
                if i >= j:
                    continue
                if rng.rand() > 0.3:
                    continue
                if (i, j) in added_edges or (j, i) in added_edges:
                    continue

                dx = nodes[i].x - nodes[j].x
                dy = nodes[i].y - nodes[j].y
                dz = nodes[i].z - nodes[j].z
                length = math.sqrt(dx*dx + dy*dy + dz*dz)

                if length < 10 or length > grid_width * 0.4:
                    continue

                flag_up = 1 if dz > EPS else 0
                edges[edge_id] = Edge(
                    id=edge_id, node_u=i, node_v=j,
                    length=float(length), dz=float(dz), flag_up=flag_up
                )
                added_edges.add((i, j))
                edge_id += 1

    # 垂直边（跨层连接）
    for level in range(n_levels - 1):
        upper_nodes = [i for i in range(level * nodes_per_level,
                                         min((level + 1) * nodes_per_level, n_nodes))]
        lower_nodes = [i for i in range((level + 1) * nodes_per_level,
                                         min((level + 2) * nodes_per_level, n_nodes))]

        for i in upper_nodes:
            for j in lower_nodes:
                if rng.rand() > 0.15:
                    continue
                if (i, j) in added_edges or (j, i) in added_edges:
                    continue

                dx = nodes[i].x - nodes[j].x
                dy = nodes[i].y - nodes[j].y
                dz = nodes[j].z - nodes[i].z  # 从 i 到 j 的高度差
                length = math.sqrt(dx*dx + dy*dy + dz*dz)

                if length > math.hypot(grid_width, 2 * level_height):
                    continue

                flag_up = 1 if dz > EPS else 0
                edges[edge_id] = Edge(
                    id=edge_id, node_u=i, node_v=j,
                    length=float(length), dz=float(dz), flag_up=flag_up
                )
                added_edges.add((i, j))
                edge_id += 1

    print(f"[INFO] 合成三维网络: {len(nodes)} 节点, {len(edges)} 边")
    return nodes, edges


def build_adjacency(nodes: Dict[int, Node], edges: Dict[int, Edge]) -> Dict[int, List[int]]:
    """构建邻接表: node_id -> list of neighbor node_ids"""
    adj = defaultdict(list)
    for e in edges.values():
        adj[e.node_u].append(e.node_v)
        adj[e.node_v].append(e.node_u)
    return dict(adj)


def build_edge_lookup(nodes: Dict[int, Node], edges: Dict[int, Edge]) -> Dict[Tuple[int, int], Edge]:
    """
    构建 (u, v) -> Edge 的快速查找表。
    注意: 边是无向的，key 包含 (u,v) 和 (v,u) 两个方向。
    """
    lookup = {}
    for e in edges.values():
        lookup[(e.node_u, e.node_v)] = e
        lookup[(e.node_v, e.node_u)] = e
    return lookup


def get_edge_between(edge_lookup: Dict[Tuple[int, int], Edge], u: int, v: int) -> Optional[Edge]:
    """获取连接节点 u 和 v 的边"""
    return edge_lookup.get((u, v))


# ============================================================================
# 核心算法一：单源水流漫延（问题1）
# ============================================================================

def locate_source_edge(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    source_point: Tuple[float, float, float],
    epsilon: float = 1.0
) -> Tuple[Optional[Edge], float]:
    """
    定位突水点所在巷道。

    使用点-线段距离公式（分段函数）:
    - t < 0: 点到 v_i 端距离
    - t > 1: 点到 v_j 端距离
    - 0 <= t <= 1: 垂线距离

    参数:
        nodes: 节点字典
        edges: 边字典
        source_point: 突水点坐标 (x, y, z)
        epsilon: 容差距离 (m)

    返回:
        (nearest_edge, min_distance)
    """
    nearest_edge = None
    min_dist = INF

    sx, sy, sz = source_point
    src_vec = np.array([sx, sy, sz])

    for e in edges.values():
        vi = nodes[e.node_u]
        vj = nodes[e.node_v]

        vi_vec = np.array([vi.x, vi.y, vi.z])
        vj_vec = np.array([vj.x, vj.y, vj.z])

        vec_vjvi = vj_vec - vi_vec
        vec_src_vi = src_vec - vi_vec
        L_sq = np.dot(vec_vjvi, vec_vjvi)

        if L_sq < EPS:
            continue  # 退化边

        t_param = np.dot(vec_src_vi, vec_vjvi) / L_sq

        if t_param < 0:
            d = np.linalg.norm(src_vec - vi_vec)
        elif t_param > 1:
            d = np.linalg.norm(src_vec - vj_vec)
        else:
            cross_prod = np.cross(vec_vjvi, vec_src_vi)
            d = np.linalg.norm(cross_prod) / math.sqrt(L_sq)

        if d < min_dist:
            min_dist = d
            nearest_edge = e

    return nearest_edge, min_dist


def count_active_branches(
    node_id: int,
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    covered_set: Set[int],
    blocked_edges: Set[int],
    adj_list: Dict[int, List[int]],
    edge_lookup: Dict[Tuple[int, int], Edge]
) -> int:
    """
    计算节点的活跃出流分支数。
    活跃分支 = 邻接节点不在 covered_set 中 + 非上升巷道 + 未封闭。
    """
    active = 0
    for nbr in adj_list.get(node_id, []):
        if nbr in covered_set:
            continue
        edge = get_edge_between(edge_lookup, node_id, nbr)
        if edge is None or edge.id in blocked_edges:
            continue
        if edge.flag_up == 1:
            continue
        active += 1
    return active


def compute_node_inflow(
    node_id: int,
    flow_assign: Dict[Tuple[int, int], float],
    source_edge_info: Optional[Dict] = None
) -> float:
    """
    计算节点的入流量。
    查找 flow_assign 中所有以 node_id 为目标的边流量之和。
    对于源节点（突水点所连接的两个端点），入流量由 source_edge_info 提供。
    """
    inflow = 0.0
    for (a, b), q in flow_assign.items():
        if b == node_id:
            inflow += q

    # 若 inflow 为 0 且节点是源端，使用 source_edge_info
    if inflow == 0 and source_edge_info is not None:
        if node_id in source_edge_info.get('source_endpoints', set()):
            inflow = source_edge_info.get('endpoint_flow', 0.0)
            # 再从 flow_assign 中补充已被分配的部分
            for (a, b), q in flow_assign.items():
                if b == node_id:
                    inflow += q

    return inflow


def get_candidates_single(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    covered_set: Set[int],
    flow_assign: Dict[Tuple[int, int], float],
    partial_fill: Dict[int, float],
    blocked_edges: Set[int],
    adj_list: Dict[int, List[int]],
    edge_lookup: Dict[Tuple[int, int], Edge],
    source_endpoints: Set[int],
    endpoint_flow: float
) -> List[Tuple]:
    """
    生成候选边列表。

    每个候选边包含:
    (edge, target_node, delta_t, Q_edge, source_node)

    delta_t 考虑了部分填充量: remaining_vol = V_total - partial_fill
    """
    candidates = []

    for e in edges.values():
        if e.id in blocked_edges:
            continue
        if e.flag_up == 1:
            continue  # 铺满阶段排除上升巷道

        u, v = e.node_u, e.node_v

        # 确定方向：源端在 covered_set 中，目标端不在
        if u in covered_set and v not in covered_set:
            src, tgt = u, v
        elif v in covered_set and u not in covered_set:
            src, tgt = v, u
        else:
            continue  # 两端都在或都不在集合中

        # 计算 src 的活跃出流分支数
        active_deg = count_active_branches(
            src, nodes, edges, covered_set, blocked_edges,
            adj_list, edge_lookup
        )
        if active_deg == 0:
            continue

        # 获取 src 的入流量
        source_info = {
            'source_endpoints': source_endpoints,
            'endpoint_flow': endpoint_flow
        }
        Q_in = compute_node_inflow(src, flow_assign, source_info)
        if Q_in <= EPS:
            continue

        Q_edge = Q_in / active_deg

        # 计算考虑部分填充后的剩余体积
        V_needed = TUNNEL_WIDTH * e.length * H0  # 4 * L * 0.1
        filled = partial_fill.get(e.id, 0.0)
        remaining_vol = V_needed - filled

        if remaining_vol <= EPS:
            # 已通过部分填充累计填满
            candidates.append((e, tgt, 0.0, Q_edge, src))
        else:
            delta_t = remaining_vol / Q_edge
            candidates.append((e, tgt, delta_t, Q_edge, src))

    return candidates


def trigger_break_flow(
    flow_assign: Dict[Tuple[int, int], float],
    partial_fill: Dict[int, float],
    v_i: int,
    completed_edge: Edge,
    covered_set: Set[int],
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    blocked_edges: Set[int],
    adj_list: Dict[int, List[int]],
    edge_lookup: Dict[Tuple[int, int], Edge],
    source_endpoints: Set[int]
) -> None:
    """
    断流模型：叶节点完成填充后，流量回退到上一节点重新分配。

    1. 移除已完成边的流量分配
    2. 将流量重新分配到 v_i 的其他活跃分支
    3. 若 v_i 的所有分支均已断流，回溯到上一节点
    """
    # 获取已完成边的流量
    edge_key = (v_i, completed_edge.node_v) if completed_edge.node_u == v_i else (completed_edge.node_v, v_i)
    Q_ij_old = flow_assign.get(edge_key, 0.0)
    if Q_ij_old <= EPS:
        # 尝试反向 key
        edge_key_rev = (completed_edge.node_v, v_i) if edge_key == (v_i, completed_edge.node_v) else (v_i, completed_edge.node_v)
        Q_ij_old = flow_assign.get(edge_key_rev, 0.0)
        edge_key = edge_key_rev

    if Q_ij_old <= EPS:
        return

    # 移除该边的流量分配
    if edge_key in flow_assign:
        del flow_assign[edge_key]

    # 找出 v_i 的其他活跃分支
    active_branches = []
    for nbr in adj_list.get(v_i, []):
        if nbr == completed_edge.node_u or nbr == completed_edge.node_v:
            continue
        if nbr in covered_set:
            continue
        e = get_edge_between(edge_lookup, v_i, nbr)
        if e is None or e.id in blocked_edges:
            continue
        if e.flag_up == 1:
            continue
        active_branches.append(e)

    if len(active_branches) == 0:
        # v_i 的所有分支均已断流，回溯到上一节点
        # 查找向 v_i 供流的来源边
        for (a, b), q in list(flow_assign.items()):
            if b == v_i and a != v_i:  # a -> v_i
                inflow_edge = get_edge_between(edge_lookup, a, v_i)
                if inflow_edge is not None:
                    trigger_break_flow(
                        flow_assign, partial_fill, a, inflow_edge,
                        covered_set, nodes, edges, blocked_edges,
                        adj_list, edge_lookup, source_endpoints
                    )
        return

    # 将 Q_ij_old 平均分配到剩余分支
    Q_add = Q_ij_old / len(active_branches)
    for e_branch in active_branches:
        branch_key = (v_i, e_branch.node_v) if e_branch.node_u == v_i else (e_branch.node_u, v_i)
        Q_old = flow_assign.get(branch_key, 0.0)
        flow_assign[branch_key] = Q_old + Q_add

        # 更新剩余时间（部分填充量已在主循环中维护）
        filled = partial_fill.get(e_branch.id, 0.0)
        V_needed = TUNNEL_WIDTH * e_branch.length * H0
        if filled >= V_needed:
            continue
        # remaining_vol 和 delta_t 由主循环在下一次迭代中计算


def single_source_flood(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    source_point: Tuple[float, float, float],
    Q: float = Q_SOURCE,
    h0: float = H0,
    h_safe: float = H_SAFE,
    h_max: float = H_MAX,
    is_3d: bool = False
) -> WaterState:
    """
    单源水流漫延主算法（问题1）。

    核心思路：逐轮端点集扩展 + 部分填充量追踪。

    Phase 1: 定位突水点所在巷道
    Phase 2: 迭代端点集合扩展（含部分填充量追踪、断流检查）
    Phase 3: 铺满 0.1m 后的同步上升阶段

    参数:
        nodes: 节点字典
        edges: 边字典
        source_point: 突水点坐标 (x, y, z)
        Q: 突水量 (m³/min)
        h0: 初始水位 (m)
        h_safe: 安全涉水阈值 (m)
        h_max: 巷道最大高度 (m)
        is_3d: 是否三维网络

    返回:
        WaterState 对象，包含所有到达时间和填充时间
    """
    # 构建辅助数据结构
    adj_list = build_adjacency(nodes, edges)
    edge_lookup = build_edge_lookup(nodes, edges)

    # ────────────────────────────────────────────
    # Phase 1: 定位突水点所在巷道
    # ────────────────────────────────────────────
    source_edge, min_dist = locate_source_edge(nodes, edges, source_point)
    if source_edge is None:
        print("[ERROR] 无法定位突水点所在巷道")
        return WaterState({}, {}, {}, {}, 0.0, 0.0)

    print(f"[INFO] 突水点定位: edge_id={source_edge.id}, "
          f"nodes=({source_edge.node_u}, {source_edge.node_v}), "
          f"distance={min_dist:.2f}m")

    # 赛题约定突水点在巷道中点，两段长度各为一半
    L_total = source_edge.length
    L_left = L_total / 2.0
    L_right = L_total / 2.0

    left_node = source_edge.node_u
    right_node = source_edge.node_v

    # ────────────────────────────────────────────
    # Phase 2: 迭代端点集合扩展
    # ────────────────────────────────────────────
    covered_set = set()          # 已铺满 0.1m 的端点集合 S
    t_global = 0.0               # 全局仿真时间 (min)
    node_arrival = {}            # node_id -> 首次到达时间
    edge_spread_time = {}        # edge_id -> 铺满 0.1m 时间
    flow_assign = {}             # (src, tgt) -> Q (m³/min)
    partial_fill = defaultdict(float)  # edge_id -> 已累积填充体积 (m³)
    blocked_edges = set()        # 已封闭/已完成的边集合

    # 初始化：突水点所在巷道两端，各分得 Q/2
    # 水从突水点沿巷道向两端同时漫延
    t_left = TUNNEL_WIDTH * L_left * h0 / (Q / 2.0)
    t_right = TUNNEL_WIDTH * L_right * h0 / (Q / 2.0)

    # 两端同时到达（中点对称）
    t_first = min(t_left, t_right)
    t_global = t_first

    # 两端加入集合
    covered_set.add(left_node)
    covered_set.add(right_node)
    node_arrival[left_node] = t_global
    node_arrival[right_node] = t_global

    # 记录突水点所在边的铺满时间
    edge_spread_time[source_edge.id] = t_global

    # 流量分配：source_edge 获得全部 Q
    flow_assign[(left_node, right_node)] = Q

    # 记录源端点信息，用于入流量计算
    source_endpoints = {left_node, right_node}
    endpoint_flow = Q / 2.0  # 每个端点的入流量

    # 根据 source_edge 的方向确定 flow_dir
    # 对于单源，水流从突水点向两端扩散
    # 此处用 left_node -> right_node 方向为正，表示从中间向两端

    # 主循环：逐轮扩展
    max_iterations = len(nodes) * 2  # 防止死循环
    iteration = 0

    while len(covered_set) < len(nodes) and iteration < max_iterations:
        iteration += 1

        # Step A: 构建候选边集
        candidates = get_candidates_single(
            nodes, edges, covered_set, flow_assign, partial_fill,
            blocked_edges, adj_list, edge_lookup,
            source_endpoints, endpoint_flow
        )

        # Step B: 无候选边则终止
        if not candidates:
            print(f"[INFO] 第{iteration}轮: 无候选边，终止扩展。"
                  f"已覆盖 {len(covered_set)}/{len(nodes)} 节点")
            break

        # Step C: 选取 delta_t 最小的候选边
        candidates.sort(key=lambda x: x[2])  # 按 delta_t 排序
        best_edge, best_node, min_dt, best_Q, src_node = candidates[0]

        # Step D: 记录流量分配
        flow_assign[(src_node, best_node)] = best_Q + flow_assign.get((src_node, best_node), 0.0)

        # 记录铺满时间
        edge_spread_time[best_edge.id] = t_global + min_dt

        # 更新 flow_dir
        # 水流方向从 src_node 指向 best_node
        edge_spread_time.setdefault(best_edge.id, t_global + min_dt)

        # Step E: 更新部分填充量（非选中候选边）
        for entry in candidates[1:]:
            e, tgt, dt, Q_e, src = entry
            accumulated = partial_fill.get(e.id, 0.0)
            partial_fill[e.id] = accumulated + Q_e * min_dt

        # Step F: 更新全局时间和端点集
        t_global += min_dt
        covered_set.add(best_node)
        node_arrival[best_node] = t_global

        # Step G: 断流检查
        # G1: 若 best_node 是叶节点（度 <= 1），触发断流
        node_degree = len(adj_list.get(best_node, []))
        if node_degree <= 1:
            trigger_break_flow(
                flow_assign, partial_fill, src_node, best_edge,
                covered_set, nodes, edges, blocked_edges,
                adj_list, edge_lookup, source_endpoints
            )

        if iteration % 50 == 0:
            print(f"[INFO] 漫延迭代: 第{iteration}轮, 时间={t_global:.2f}min, "
                  f"已覆盖 {len(covered_set)}/{len(nodes)} 节点")

    print(f"[INFO] 铺满阶段完成: 共{iteration}轮, 时间={t_global:.2f}min, "
          f"覆盖 {len(covered_set)}/{len(nodes)} 节点")

    # ────────────────────────────────────────────
    # Phase 3: 同步上升阶段（0.1m -> 3m）
    # ────────────────────────────────────────────
    total_tunnel_length = sum(e.length for e in edges.values())
    t_spread = t_global

    edge_0_3m_time = {}
    edge_full_time = {}

    if total_tunnel_length > EPS:
        for e in edges.values():
            # 体积比例分配
            Q_rise = Q * (e.length / total_tunnel_length) if total_tunnel_length > 0 else 0.0

            if Q_rise > EPS:
                # 从 0.1m 到 0.3m 的时间
                V_to_0_3 = TUNNEL_WIDTH * e.length * (h_safe - h0)
                t_to_0_3 = V_to_0_3 / Q_rise
                edge_0_3m_time[e.id] = t_spread + t_to_0_3

                # 从 0.1m 到 3m 的时间
                V_to_full = TUNNEL_WIDTH * e.length * (h_max - h0)
                t_to_full = V_to_full / Q_rise
                edge_full_time[e.id] = t_spread + t_to_full
            else:
                edge_0_3m_time[e.id] = INF
                edge_full_time[e.id] = INF

    T_total = max(edge_full_time.values()) if edge_full_time else t_spread

    # 简洁估算（总水量守恒）
    V_total_all = TUNNEL_WIDTH * total_tunnel_length * h_max
    T_total_est = V_total_all / Q
    print(f"[INFO] 上升阶段完成: T_total={T_total:.2f}min (估算={T_total_est:.2f}min)")

    # 构建水流方向（用于 Dijkstra）
    flow_dir = {}
    for e in edges.values():
        t_u = node_arrival.get(e.node_u, INF)
        t_v = node_arrival.get(e.node_v, INF)
        if t_u < INF and t_v < INF:
            if t_u < t_v:
                flow_dir[e.id] = 1      # u -> v
            elif t_v < t_u:
                flow_dir[e.id] = -1     # v -> u
            else:
                flow_dir[e.id] = 0      # 同时到达
        elif t_u < INF:
            flow_dir[e.id] = 1
        elif t_v < INF:
            flow_dir[e.id] = -1
        else:
            flow_dir[e.id] = 0

    water_state = WaterState(
        node_arrival=node_arrival,
        edge_spread_time=edge_spread_time,
        edge_0_3m_time=edge_0_3m_time,
        edge_full_time=edge_full_time,
        t_spread=t_spread,
        T_total=T_total,
        flow_dir=flow_dir
    )

    return water_state


# ============================================================================
# 核心算法一扩展：三维 BFS + 平行上升（问题1 附件二）
# ============================================================================

def single_source_flood_3d(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    source_point: Tuple[float, float, float],
    Q: float = Q_SOURCE
) -> WaterState:
    """
    三维立体网络水流漫延（附件二）。

    Step 1: 筛选等于及低于突水点 z 坐标的端点 V_low
    Step 2: 在 V_low 诱导子图上运行平面漫延模型
    Step 3: V_low 子图内 BFS 连通性发现（严格限制在 E_low 内）
    Step 4: 形成完整铺满平面 S_0.1
    Step 5: 平行向上漫延

    参数:
        nodes: 三维节点字典
        edges: 三维边字典
        source_point: 突水点坐标 (x, y, z)
        Q: 突水量 (m³/min)

    返回:
        WaterState 对象
    """
    _, _, z_A = source_point

    # Step 1: 筛选 V_low
    V_low_ids = {nid for nid, n in nodes.items() if n.z <= z_A + EPS}
    E_low_ids = set()
    for e in edges.values():
        if e.node_u in V_low_ids and e.node_v in V_low_ids:
            E_low_ids.add(e.id)

    # 构建 V_low 诱导子图
    nodes_low = {nid: nodes[nid] for nid in V_low_ids}
    edges_low = {eid: edges[eid] for eid in E_low_ids}

    print(f"[INFO] 3D Step1: V_low = {len(V_low_ids)} 节点, E_low = {len(E_low_ids)} 边")

    if len(nodes_low) == 0:
        print("[WARNING] V_low 为空，突水点可能位于最低层")
        return WaterState({}, {}, {}, {}, 0.0, 0.0)

    # Step 2: 在 G_low 上运行平面漫延算法
    result_low = single_source_flood(
        nodes_low, edges_low, source_point, Q,
        is_3d=True
    )
    S_low = set(result_low.node_arrival.keys())

    # Step 3: V_low 子图内 BFS 连通性发现
    # BFS 严格限制在 E_low 内 - 只遍历两个端点均在 V_low 内的边
    adj_low = build_adjacency(nodes_low, edges_low)

    S_bfs = set()
    queue = deque(list(S_low))
    visited = set(S_low)

    while queue:
        u = queue.popleft()
        for w in adj_low.get(u, []):
            if w not in visited:
                visited.add(w)
                queue.append(w)
                if w in V_low_ids and w not in S_low:
                    S_bfs.add(w)

    # Step 4: 形成完整的铺满平面
    S_0_1 = S_low.union(S_bfs)

    # 对 BFS 发现的节点，分配到达时间
    node_arrival_3d = dict(result_low.node_arrival)  # 复制已有结果
    for v_id in S_bfs:
        # 以铺满时间为到达时间
        if v_id not in node_arrival_3d:
            node_arrival_3d[v_id] = result_low.t_spread

    print(f"[INFO] 3D Step3-4: S_low={len(S_low)}, S_bfs={len(S_bfs)}, "
          f"S_0.1={len(S_0_1)}")

    # Step 5: 平行向上漫延 — 逐层灌满至 H0 (0.1m)
    if len(S_0_1) == 0:
        z_plane = z_A
    else:
        z_plane = max(nodes[nid].z for nid in S_0_1)

    V_above = sorted(
        [nid for nid in nodes.keys() if nid not in S_0_1],
        key=lambda nid: nodes[nid].z
    )

    t_current = result_low.t_spread
    edge_spread_time = dict(result_low.edge_spread_time)

    # H4 修正: edge_0_3m_time, edge_full_time 将在 Step 6 中重新对所有边计算
    # 此处不再从 result_low 复制（仅含 E_low 边数据）
    edge_0_3m_time = {}
    edge_full_time = {}

    # 按 z 坐标分层处理
    z_groups = defaultdict(list)
    for nid in V_above:
        z_groups[nodes[nid].z].append(nid)

    for z_level in sorted(z_groups.keys()):
        nodes_at_z = z_groups[z_level]

        # 计算该层所需水量
        edges_at_z = []
        for e in edges.values():
            z_u = nodes[e.node_u].z
            z_v = nodes[e.node_v].z
            # 该层包含至少一个端点在该 z 层
            if (abs(z_u - z_level) < EPS or abs(z_v - z_level) < EPS):
                if e.id not in E_low_ids:  # 排除已处理的低层边
                    edges_at_z.append(e)

        # 去重
        seen_edge_ids = set()
        unique_edges_at_z = []
        for e in edges_at_z:
            if e.id not in seen_edge_ids:
                seen_edge_ids.add(e.id)
                unique_edges_at_z.append(e)

        # 计算该层填充时间
        V_layer = sum(TUNNEL_WIDTH * e.length * H0 for e in unique_edges_at_z)

        if V_layer > EPS and Q > EPS:
            t_layer = V_layer / Q
            t_current += t_layer
        else:
            t_layer = 0.0

        for nid in nodes_at_z:
            if nid not in node_arrival_3d:
                node_arrival_3d[nid] = t_current

        print(f"[INFO] 3D Step5: z={z_level:.1f}m, {len(nodes_at_z)} 节点, "
              f"{len(unique_edges_at_z)} 边, t_layer={t_layer:.1f}min")

    # H4 修正: Step 6 — 从 H0 同步上升至 H_SAFE (0.3m) 和 H_MAX (3.0m)
    # 此时所有已灌至 H0 的层同步上升，总入流量为 Q
    t_spread_3d = t_current  # 所有层均达到 H0 的时刻
    total_length_3d = sum(e.length for e in edges.values())
    if total_length_3d > EPS:
        for e in edges.values():
            # 按长度比例分配流量
            Q_rise = Q * (e.length / total_length_3d)
            if Q_rise > EPS:
                V_to_0_3 = TUNNEL_WIDTH * e.length * (H_SAFE - H0)
                edge_0_3m_time[e.id] = t_spread_3d + V_to_0_3 / Q_rise
                V_to_full = TUNNEL_WIDTH * e.length * (H_MAX - H0)
                edge_full_time[e.id] = t_spread_3d + V_to_full / Q_rise
            else:
                edge_0_3m_time[e.id] = INF
                edge_full_time[e.id] = INF

    T_total_3d = max(edge_full_time.values()) if edge_full_time else t_spread_3d

    print(f"[INFO] 3D 漫延完成: t_spread(H0)={t_spread_3d:.2f}min, "
          f"T_total(3m)={T_total_3d:.2f}min")

    water_state_3d = WaterState(
        node_arrival=node_arrival_3d,
        edge_spread_time=edge_spread_time,
        edge_0_3m_time=edge_0_3m_time,
        edge_full_time=edge_full_time,
        t_spread=t_spread_3d,
        T_total=T_total_3d,
        flow_dir=result_low.flow_dir
    )

    return water_state_3d


# ============================================================================
# 核心算法二：标准时变 Dijkstra（问题2）
# ============================================================================

def get_travel_time(
    edge: Edge,
    t_enter: float,
    t_arr_u: float,
    t_arr_v: float,
    t_0_3: float,
    flow_dir: int,
    debug: bool = False
) -> Tuple[float, bool]:
    """
    计算在 t_enter 时刻进入巷道所需的通行时间。

    注意: 修复 M-2025D-015 — flow_dir_flag 在所有分支中均有定义，
    情况2（部分湿润边）中使用 None 作为初始值，中途淹没检测时
    若 flow_dir_flag 为 None，仅检查时间条件。

    返回:
        (travel_time, feasible)
    """
    L = edge.length

    # 情况1: 两端均干燥 (AND 条件)
    # 修正: 使用 AND 而非 OR（对应 M-2025D-001 修复）
    if t_enter < t_arr_u and t_enter < t_arr_v:
        travel_time = L / V_DRY
        flow_dir_flag = 0  # 无水，无方向
        return (travel_time, True)

    # 情况2: 部分湿润 (XOR: 恰好一端已到达水流)
    # NOTE: 使用 XOR 判断，对应 M-2025D-001 修复
    if (t_enter < t_arr_u) != (t_enter < t_arr_v):
        travel_time = L / V_MIX
        flow_dir_flag = None  # 部分湿润，方向不确定
        # 但对于中途淹没检测，我们仍能计算安全距离
        # 使用 V_MIX 作为速度
        if t_enter < t_0_3 < t_enter + travel_time:
            safe_dist = V_MIX * (t_0_3 - t_enter)
            if safe_dist < L - EPS:
                return (travel_time, False)  # 不可完整通行
        return (travel_time, True)

    # 情况3: 两端均有水且水位 <= 0.3m
    if t_0_3 > t_enter:
        if t_arr_u < t_arr_v:
            flow_dir_flag = 1   # 水流 u -> v
        else:
            flow_dir_flag = -1  # 水流 v -> u

        if flow_dir_flag == flow_dir or flow_dir != 0:
            # 使用传入的 flow_dir 判断顺水/逆水
            if flow_dir == 1 or (flow_dir == 0 and t_arr_u < t_arr_v):
                travel_time = L / V_WITH  # 顺水
            else:
                travel_time = L / V_AGAINST  # 逆水
        else:
            travel_time = L / V_MIX  # 默认中间速度

        # 中途淹没检测
        if t_enter < t_0_3 < t_enter + travel_time:
            safe_speed = V_WITH if flow_dir_flag == 1 else V_AGAINST
            safe_dist = safe_speed * (t_0_3 - t_enter)
            if safe_dist < L - EPS:
                return (travel_time, False)

        return (travel_time, True)

    # 情况4: 水位已超标
    return (INF, False)


def time_dependent_dijkstra(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state: WaterState,
    start_node: int,
    exit_nodes: List[int],
    t_notice: float = T_NOTICE
) -> Tuple[Optional[List[int]], float]:
    """
    标准时变 Dijkstra 最短逃生路径规划（问题2）。

    边权重为时间函数，取决于进入时刻的水位和行进方向。
    复杂度 O(|E| log |V|)，对 665 节点规模可在毫秒级完成。

    参数:
        nodes: 节点字典
        edges: 边字典
        water_state: 水流漫延结果
        start_node: 起点节点编号
        exit_nodes: 安全出口节点编号列表
        t_notice: 逃生通知发布时间

    返回:
        (最优路径节点序列, 总逃生时间)
    """
    adj_list = build_adjacency(nodes, edges)
    edge_lookup = build_edge_lookup(nodes, edges)

    node_arrival = water_state.node_arrival
    edge_0_3m_time = water_state.edge_0_3m_time
    flow_dir = water_state.flow_dir

    # 检查起点是否已在淹没区
    if start_node in node_arrival:
        for e in edges.values():
            if e.node_u == start_node or e.node_v == start_node:
                t_0_3 = edge_0_3m_time.get(e.id, INF)
                if t_notice >= t_0_3:
                    print(f"[WARNING] 起点 {start_node} 在 t={t_notice}min 时已淹没")
                    return None, INF

    # Dijkstra 主循环
    dist = {nid: INF for nid in nodes}
    prev = {nid: None for nid in nodes}
    dist[start_node] = t_notice

    pq = [(dist[start_node], start_node)]
    visited = set()

    # 构建出口集合用于快速检查
    exit_set = set(exit_nodes)

    while pq:
        t_u, u = heapq.heappop(pq)

        if t_u > dist[u]:
            continue
        if u in visited:
            continue
        visited.add(u)

        # 到达任一出口即可终止
        if u in exit_set and u != start_node:
            break

        for v in adj_list.get(u, []):
            edge = get_edge_between(edge_lookup, u, v)
            if edge is None:
                continue

            # 获取水位时间参数
            t_arr_u = node_arrival.get(u, INF)
            t_arr_v = node_arrival.get(v, INF)
            t_0_3 = edge_0_3m_time.get(edge.id, INF)

            # 获取水流方向 (用于该边)
            fd = flow_dir.get(edge.id, 0)

            # 计算通行时间
            travel_time, feasible = get_travel_time(
                edge, t_u, t_arr_u, t_arr_v, t_0_3, fd
            )

            if not feasible or travel_time >= INF / 2:
                continue

            t_v = t_u + travel_time

            # 松弛操作
            if t_v < dist[v]:
                dist[v] = t_v
                prev[v] = u
                heapq.heappush(pq, (t_v, v))

    # 找到最近的出口
    best_exit = None
    best_time = INF
    for exit_node in exit_set:
        if dist.get(exit_node, INF) < best_time:
            best_time = dist[exit_node]
            best_exit = exit_node

    if best_exit is None or best_time >= INF / 2:
        return None, INF

    # 回溯路径
    path = []
    u = best_exit
    while u is not None:
        path.append(u)
        u = prev[u]
    path.reverse()

    return path, best_time


# ============================================================================
# 核心算法三：双源并行漫延 + 碰撞检测（问题3）
# ============================================================================

def get_candidates_dual(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    state_S: Set[int],
    flow_assign: Dict[Tuple[int, int], float],
    partial_fill: Dict[int, float],
    blocked_edges: Set[int],
    adj_list: Dict[int, List[int]],
    edge_lookup: Dict[Tuple[int, int], Edge],
    source_endpoints: Set[int],
    endpoint_flow: float
) -> List[Tuple]:
    """双源模型中为单源生成候选边列表（同单源算法，但考虑 blocked_edges）"""
    return get_candidates_single(
        nodes, edges, state_S, flow_assign, partial_fill,
        blocked_edges, adj_list, edge_lookup,
        source_endpoints, endpoint_flow
    )


def rollback_edge_dual(
    state_S: Set[int],
    flow_assign: Dict[Tuple[int, int], float],
    partial_fill: Dict[int, float],
    edge: Edge,
    blocked_edges: Set[int],
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    adj_list: Dict[int, List[int]],
    edge_lookup: Dict[Tuple[int, int], Edge]
) -> None:
    """
    双源模型中回退边的流量到其源端。

    1. 确定该边哪个端点在 state_S 中（即水流推进方向）
    2. 移除该边的流量分配
    3. 将流量重新分配到该端点的其他活跃分支
    """
    u, v = edge.node_u, edge.node_v

    # 确定 src_node (在 state_S 中的端点)
    if u in state_S:
        src_node = u
    elif v in state_S:
        src_node = v
    else:
        return  # 两端都不在 S 中，无可回退

    # 查找流量分配 key
    edge_key = None
    old_flow = 0.0
    for (a, b), q in list(flow_assign.items()):
        if {a, b} == {u, v}:
            edge_key = (a, b)
            old_flow = q
            break

    if edge_key is None or old_flow <= EPS:
        return

    # 移除该边的流量
    del flow_assign[edge_key]

    # 找出 src_node 的其他活跃分支
    active_branches = []
    for nbr in adj_list.get(src_node, []):
        if nbr == (v if src_node == u else u):
            continue
        if nbr in state_S:
            continue
        e = get_edge_between(edge_lookup, src_node, nbr)
        if e is None or e.id in blocked_edges:
            continue
        if e.flag_up == 1:
            continue
        active_branches.append(e)

    if len(active_branches) == 0:
        return

    # 平均分配
    Q_add = old_flow / len(active_branches)
    for e_branch in active_branches:
        branch_key = (src_node, e_branch.node_v) if e_branch.node_u == src_node else (e_branch.node_u, src_node)
        flow_assign[branch_key] = flow_assign.get(branch_key, 0.0) + Q_add


def dual_source_flood(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    source_A: Tuple[float, float, float],
    source_B: Tuple[float, float, float],
    t_offset_B: float = T_OFFSET_B_PLANAR,
    Q: float = Q_SOURCE
) -> Tuple[WaterState, Set[int], Dict[int, float]]:
    """
    双源并行漫延 + 碰撞检测（问题3）。

    两套独立的单源漫延模型并行演进，在碰撞时触发封闭模型进行局部流量重分配。
    碰撞类型：
    1. 节点级碰撞：一股水流到达已被另一股占据的节点
    2. 边级碰撞：一条巷道两端分别被两股水流占据

    参数:
        nodes: 节点字典
        edges: 边字典
        source_A: 突水点 A 坐标 (x, y, z)
        source_B: 突水点 B 坐标 (x, y, z)
        t_offset_B: B 突水点开始时间偏移 (min)
        Q: 单突水点流量 (m³/min)

    返回:
        (water_state_combined, blocked_edges_set, edge_meet_time)
    """
    adj_list = build_adjacency(nodes, edges)
    edge_lookup = build_edge_lookup(nodes, edges)

    # 定位两个源的所在巷道
    src_edge_A, _ = locate_source_edge(nodes, edges, source_A)
    src_edge_B, _ = locate_source_edge(nodes, edges, source_B)

    if src_edge_A is None or src_edge_B is None:
        print("[ERROR] 无法定位突水点所在巷道")
        empty_state = WaterState({}, {}, {}, {}, 0.0, 0.0)
        return empty_state, set(), {}

    # ---- 状态 A ----
    S_A = set()
    t_A = 0.0
    flow_A = {}
    partial_A = defaultdict(float)
    blocked = set()  # 共享的已封闭巷道集合

    # ---- 状态 B ----
    S_B = set()
    t_B = t_offset_B
    flow_B = {}
    partial_B = defaultdict(float)

    node_arrival = {}   # 合并后的到达时间
    edge_0_3m_time = {}
    edge_full_time = {}
    edge_meet_time = {}  # edge_id -> 双源相遇时间

    # 初始化 A
    L_A_total = src_edge_A.length
    L_A_half = L_A_total / 2.0
    left_A, right_A = src_edge_A.node_u, src_edge_A.node_v
    S_A.add(left_A); S_A.add(right_A)
    node_arrival[left_A] = 0.0
    node_arrival[right_A] = 0.0
    flow_A[(left_A, right_A)] = Q
    src_endpoints_A = {left_A, right_A}

    # 初始化 B
    L_B_total = src_edge_B.length
    L_B_half = L_B_total / 2.0
    left_B, right_B = src_edge_B.node_u, src_edge_B.node_v
    S_B.add(left_B); S_B.add(right_B)
    node_arrival[left_B] = min(node_arrival.get(left_B, INF), t_offset_B)
    node_arrival[right_B] = min(node_arrival.get(right_B, INF), t_offset_B)
    flow_B[(left_B, right_B)] = Q
    src_endpoints_B = {left_B, right_B}

    # 检查 B 的初始节点是否与 A 碰撞
    for nid in [left_B, right_B]:
        if nid in S_A:
            print(f"[INFO] 双源碰撞: B 初始节点 {nid} 已被 A 覆盖")
            # B 无法在此节点开始，标记相关边为封闭
            for nbr in adj_list.get(nid, []):
                e = get_edge_between(edge_lookup, nid, nbr)
                if e is not None:
                    blocked.add(e.id)

    print(f"[INFO] 双源漫延初始化: A={len(S_A)}节点, B={len(S_B)}节点, "
          f"t_offset_B={t_offset_B}min")

    # 主循环
    max_iter = len(nodes) * 3
    iteration = 0

    while iteration < max_iter:
        iteration += 1

        # 更新全局时间为两源当前时间的最小值
        t_global = min(t_A, t_B)

        if len(S_A) + len(S_B) >= len(nodes):
            print(f"[INFO] 双源漫延: 所有节点已覆盖, 终止")
            break

        # ---- 边级碰撞检测 ----
        for e in edges.values():
            if e.id in blocked:
                continue

            u, v = e.node_u, e.node_v

            in_A_u = u in S_A
            in_A_v = v in S_A
            in_B_u = u in S_B
            in_B_v = v in S_B

            # 检查是否两端分别被不同源占据
            if (in_A_u and in_B_v) or (in_A_v and in_B_u):
                # 边级碰撞!
                if e.id not in blocked:
                    # 计算相遇时间 t_meet
                    Q_A = flow_A.get((u, v), 0.0) or flow_A.get((v, u), 0.0)
                    Q_B = flow_B.get((u, v), 0.0) or flow_B.get((v, u), 0.0)
                    Q_total = Q_A + Q_B

                    if Q_total > EPS:
                        V_total = TUNNEL_WIDTH * e.length * H0
                        # 简化相遇时间：假设恒定流量
                        t_meet = (V_total + Q_A * 0.0 + Q_B * t_offset_B) / Q_total
                    else:
                        V_filled_A = partial_A.get(e.id, 0.0)
                        V_filled_B = partial_B.get(e.id, 0.0)
                        V_remain = TUNNEL_WIDTH * e.length * H0 - V_filled_A - V_filled_B
                        if V_remain > 0:
                            t_meet = t_global + V_remain / (2 * Q)
                        else:
                            t_meet = t_global

                    blocked.add(e.id)
                    edge_meet_time[e.id] = t_meet

                    print(f"[INFO] 双源边级碰撞: edge={e.id}, t_meet={t_meet:.2f}min")

                    # 流量回退
                    rollback_edge_dual(
                        S_A, flow_A, partial_A, e, blocked,
                        nodes, edges, adj_list, edge_lookup
                    )
                    rollback_edge_dual(
                        S_B, flow_B, partial_B, e, blocked,
                        nodes, edges, adj_list, edge_lookup
                    )

        # ---- 生成两源的候选边 ----
        cand_A = get_candidates_dual(
            nodes, edges, S_A, flow_A, partial_A, blocked,
            adj_list, edge_lookup, src_endpoints_A, Q/2.0
        )
        cand_B = get_candidates_dual(
            nodes, edges, S_B, flow_B, partial_B, blocked,
            adj_list, edge_lookup, src_endpoints_B, Q/2.0
        )

        if not cand_A and not cand_B:
            break

        # ---- 选择全局最小事件 ----
        def get_min(cands):
            if not cands:
                return None
            return min(cands, key=lambda x: x[2])

        min_A = get_min(cand_A)
        min_B = get_min(cand_B)

        if min_A is None and min_B is None:
            break

        if min_A is None:
            selected = min_B
            src = 'B'
        elif min_B is None:
            selected = min_A
            src = 'A'
        else:
            t_A_finish = t_A + min_A[2]
            t_B_finish = t_B + min_B[2]
            if t_A_finish <= t_B_finish:
                selected = min_A
                src = 'A'
            else:
                selected = min_B
                src = 'B'

        best_edge, best_node, delta_t, Q_edge, src_node = selected

        cur_S = S_A if src == 'A' else S_B
        cur_flow = flow_A if src == 'A' else flow_B
        cur_partial = partial_A if src == 'A' else partial_B
        cur_t = t_A if src == 'A' else t_B
        other_S = S_B if src == 'A' else S_A

        # ---- 节点级碰撞检测 ----
        if best_node in other_S:
            blocked.add(best_edge.id)
            print(f"[INFO] 节点级碰撞: {src} 试图覆盖 node={best_node}, 已被另一源占据")
            rollback_edge_dual(
                cur_S, cur_flow, cur_partial, best_edge, blocked,
                nodes, edges, adj_list, edge_lookup
            )
            continue

        # ---- 正常扩展 ----
        cur_t += delta_t
        if src == 'A':
            t_A = cur_t
        else:
            t_B = cur_t

        cur_S.add(best_node)
        cur_flow[(src_node, best_node)] = Q_edge + cur_flow.get((src_node, best_node), 0.0)

        # 更新部分填充量
        cands = cand_A if src == 'A' else cand_B
        for entry in cands:
            e, tgt, dt, q_e, s = entry
            if e.id != best_edge.id:
                cur_partial[e.id] = cur_partial.get(e.id, 0.0) + q_e * delta_t

        # 记录到达时间
        cur_t_actual = t_A if src == 'A' else t_B
        node_arrival[best_node] = min(node_arrival.get(best_node, INF), cur_t_actual)

        if iteration % 100 == 0:
            print(f"[INFO] 双源迭代#{iteration}: A覆盖{len(S_A)}, B覆盖{len(S_B)}, "
                  f"封闭{len(blocked)}, t={cur_t_actual:.1f}min")

    # ---- 计算上升阶段 ----
    # H1 修正: 双源铺满完成时间取 max(t_A, t_B) — 两源均铺满才算完成
    # H2 修正: 使用 t_spread (= max(t_A, t_B)) 作为上升阶段基准时间，
    #           联合流量 = 2*Q (两源均在 t_spread 时已激活)
    t_spread = max(t_A, t_B)
    total_length = sum(e.length for e in edges.values())
    if total_length > EPS:
        for e in edges.values():
            V_to_0_3 = TUNNEL_WIDTH * e.length * (H_SAFE - H0)
            # 每条边按长度比例分配双源总流量 2*Q
            Q_rise = 2.0 * Q * (e.length / total_length)
            if Q_rise > EPS:
                # 从 H0 升至 H_SAFE，基准时间为双源共同铺满完成时刻 t_spread
                edge_0_3m_time[e.id] = t_spread + V_to_0_3 / Q_rise
                V_to_full = TUNNEL_WIDTH * e.length * (H_MAX - H0)
                edge_full_time[e.id] = t_spread + V_to_full / Q_rise
            else:
                edge_0_3m_time[e.id] = INF
                edge_full_time[e.id] = INF

    # 总灌满时间：t_spread 后以 2Q 流量填充剩余体积 (H0 -> H_MAX)
    total_volume_remaining = TUNNEL_WIDTH * total_length * (H_MAX - H0)
    T_total_dual = t_spread + total_volume_remaining / (2.0 * Q)

    # 水流方向
    flow_dir = {}
    for e in edges.values():
        t_u = node_arrival.get(e.node_u, INF)
        t_v = node_arrival.get(e.node_v, INF)
        if t_u < t_v:
            flow_dir[e.id] = 1
        elif t_v < t_u:
            flow_dir[e.id] = -1
        else:
            flow_dir[e.id] = 0

    print(f"[INFO] 双源漫延完成: A覆盖{len(S_A)}, B覆盖{len(S_B)}, "
          f"封闭{len(blocked)}, t_spread={t_spread:.1f}min, "
          f"T_total≈{T_total_dual:.1f}min")

    edge_spread_time = {}

    water_state = WaterState(
        node_arrival=node_arrival,
        edge_spread_time=edge_spread_time,
        edge_0_3m_time=edge_0_3m_time,
        edge_full_time=edge_full_time,
        t_spread=t_spread,
        T_total=T_total_dual,
        flow_dir=flow_dir
    )

    return water_state, blocked, edge_meet_time


# ============================================================================
# 核心算法四：路径重规划（问题4）
# ============================================================================

def get_remaining_segment(
    path: List[int],
    t_switch: float,
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state: WaterState
) -> Tuple[Optional[List[int]], int]:
    """
    获取路径在 t_switch 时刻后的剩余段。
    修复 M-2025D-016: 此函数在原始伪代码中未定义。

    算法: 从路径起点开始模拟行进，追踪到达每个节点的时间，
    找到 t_switch 时刻矿工应位于的路径位置。

    返回:
        (remaining_segment, current_node_index)
        其中 remaining_segment 为从 current_node 到终点的段
    """
    if not path or len(path) < 2:
        return None, -1

    edge_lookup = build_edge_lookup(nodes, edges)
    node_arrival = water_state.node_arrival
    edge_0_3m_time = water_state.edge_0_3m_time
    flow_dir = water_state.flow_dir

    t_current = T_NOTICE  # 从逃生通知时间开始
    last_idx = 0

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge = get_edge_between(edge_lookup, u, v)
        if edge is None:
            return None, -1

        t_arr_u = node_arrival.get(u, INF)
        t_arr_v = node_arrival.get(v, INF)
        t_0_3 = edge_0_3m_time.get(edge.id, INF)
        fd = flow_dir.get(edge.id, 0)

        travel_time, feasible = get_travel_time(
            edge, t_current, t_arr_u, t_arr_v, t_0_3, fd
        )

        if not feasible:
            return None, -1

        t_arrive = t_current + travel_time

        # 检查 t_switch 是否落在这段行程中
        if t_current <= t_switch < t_arrive:
            # 矿工正在这条巷道中行进
            # 剩余路径从 v 开始
            return path[i + 1:], i + 1

        t_current = t_arrive
        last_idx = i + 1

        if t_current >= t_switch:
            # 已到达或超过切换时间
            return path[i + 1:], i + 1

    # 行程在 t_switch 前已结束
    return [], len(path) - 1


def evaluate_path_under_dual(
    path: List[int],
    water_state: WaterState,
    t_start: float,
    nodes: Dict[int, Node],
    edges: Dict[int, Edge]
) -> Tuple[bool, float]:
    """
    评估一段路径在双源模型下从 t_start 开始的可行性。

    检查每条巷道在进入时刻:
    1. 是否已淹没 (t_enter >= t_0.3)
    2. 是否会在中途被淹没 (t_enter < t_0.3 < t_exit)

    返回:
        (feasible, total_time)
    """
    edge_lookup = build_edge_lookup(nodes, edges)
    node_arrival = water_state.node_arrival
    edge_0_3m_time = water_state.edge_0_3m_time
    flow_dir = water_state.flow_dir

    t = t_start

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge = get_edge_between(edge_lookup, u, v)
        if edge is None:
            return False, INF

        t_arr_u = node_arrival.get(u, INF)
        t_arr_v = node_arrival.get(v, INF)
        t_0_3 = edge_0_3m_time.get(edge.id, INF)
        fd = flow_dir.get(edge.id, 0)

        if t >= t_0_3:
            return False, INF

        travel_time, feasible = get_travel_time(
            edge, t, t_arr_u, t_arr_v, t_0_3, fd
        )

        if not feasible:
            return False, INF

        t += travel_time

    return True, t


def replan_path(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    dual_water_state: WaterState,
    init_path: List[int],
    start_node: int,
    exit_nodes: List[int],
    t_switch: float = T_SWITCH,
    t_notice: float = T_NOTICE
) -> Tuple[Optional[List[int]], float, str]:
    """
    在线路径重规划（问题4）。

    时间线:
    - t=0: A 突水开始
    - t=1min: 发布初始逃生通知（基于仅 A 的漫延预测）
    - t=4/5min: B 开始突水
    - t=5/6min: 发布调整后的逃生方案

    策略:
    1. 计算从当前矿工位置到出口的新路径（基于双源模型）
    2. 将初始路径的剩余段在双源模型下评估
    3. 选择总时间更短的可行方案

    参数:
        nodes: 节点字典
        edges: 边字典
        dual_water_state: 双源漫延结果
        init_path: 初始逃生路径（基于单源模型）
        start_node: 矿工起点
        exit_nodes: 安全出口列表
        t_switch: 路径切换时间
        t_notice: 逃生通知时间

    返回:
        (adjusted_path, total_time, decision)
        decision: 'new_path', 'keep_original', 'infeasible', 'new_infeasible_keep_original'
    """
    # Step 1: 计算从当前矿工位置的新路径（基于双源模型）
    # 获取矿工在 t_switch 时刻的位置
    remaining_seg, current_idx = get_remaining_segment(
        init_path, t_switch, nodes, edges, dual_water_state
    )

    if remaining_seg is None or len(remaining_seg) == 0:
        # 矿工已到达出口或在切换时已无法继续
        current_node = start_node
    else:
        current_node = remaining_seg[0]

    # 新路径规划（基于双源模型）
    new_path, new_time = time_dependent_dijkstra(
        nodes, edges, dual_water_state,
        current_node, exit_nodes, t_switch
    )

    # Step 2: 评估初始路径剩余段在双源模型下的可行性
    if remaining_seg and len(remaining_seg) >= 2:
        init_feasible, init_dual_time = evaluate_path_under_dual(
            remaining_seg, dual_water_state, t_switch, nodes, edges
        )
    else:
        init_feasible = False
        init_dual_time = INF

    # Step 3: 决策
    if new_path is None or new_time >= INF / 2:
        # 新路径不可行
        if init_feasible:
            return remaining_seg, init_dual_time, 'new_infeasible_keep_original'
        else:
            return None, INF, 'infeasible'
    else:
        # 新路径可行
        if init_feasible:
            if new_time < init_dual_time:
                return new_path, new_time, 'new_path'
            else:
                return remaining_seg, init_dual_time, 'keep_original'
        else:
            return new_path, new_time, 'new_path'


# ============================================================================
# 可视化模块
# ============================================================================

def plot_network_topology(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state: Optional[WaterState] = None,
    title: str = "巷道网络拓扑图",
    highlight_nodes: Optional[Dict[int, str]] = None,
    highlight_edges: Optional[Dict[int, str]] = None,
    source_point: Optional[Tuple[float, float, float]] = None,
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """
    绘制巷道网络拓扑图。
    节点颜色可表示水流到达时间，边颜色可表示状态。
    """
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # 提取坐标
    x_coords = [n.x for n in nodes.values()]
    y_coords = [n.y for n in nodes.values()]

    # 绘制边
    for e in edges.values():
        x = [nodes[e.node_u].x, nodes[e.node_v].x]
        y = [nodes[e.node_u].y, nodes[e.node_v].y]

        # 确定边颜色
        if highlight_edges and e.id in highlight_edges:
            color = highlight_edges[e.id]
        elif water_state and e.id in water_state.edge_0_3m_time:
            t_0_3 = water_state.edge_0_3m_time.get(e.id, INF)
            if t_0_3 < INF:
                color = COLOR_WET
            else:
                color = COLOR_DRY
        else:
            color = COLOR_DRY

        ax.plot(x, y, color=color, linewidth=0.5, alpha=0.6)

    # 绘制节点
    if water_state:
        # 用到达时间着色
        arrival_times = [water_state.node_arrival.get(nid, INF) for nid in nodes]
        valid_times = [t for t in arrival_times if t < INF]

        if valid_times:
            cmap = cm.viridis
            norm = Normalize(vmin=min(valid_times), vmax=max(valid_times))

            for i, (nid, n) in enumerate(nodes.items()):
                t = arrival_times[i]
                if t < INF:
                    color = cmap(norm(t))
                else:
                    color = 'lightgray'
                ax.scatter(n.x, n.y, c=[color], s=8, alpha=0.8, zorder=3)

            sm = cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
            cbar.set_label('水流到达时间 (min)', fontsize=11)
        else:
            ax.scatter(x_coords, y_coords, c='#4A7C9E', s=8, alpha=0.8, zorder=3)
    else:
        ax.scatter(x_coords, y_coords, c='#4A7C9E', s=8, alpha=0.8, zorder=3)

    # 标记突水点
    if source_point:
        ax.scatter(source_point[0], source_point[1],
                  c='#D4524E', s=120, marker='*', zorder=5,
                  label=f'突水点 ({source_point[0]:.0f}, {source_point[1]:.0f})')

    # 标记高亮节点
    if highlight_nodes:
        for nid, label in highlight_nodes.items():
            if nid in nodes:
                ax.scatter(nodes[nid].x, nodes[nid].y,
                          s=80, marker='s', zorder=4, label=label)

    ax.set_xlabel('X 坐标 (m)', fontsize=12)
    ax.set_ylabel('Y 坐标 (m)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.8)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


def plot_flood_time_histogram(
    water_state: WaterState,
    title: str = "端点水流到达时间分布",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 6)
) -> plt.Figure:
    """绘制水流到达时间的直方图分布"""
    fig, axes = plt.subplots(1, 2, figsize=figsize)

    times = list(water_state.node_arrival.values())
    times = [t for t in times if t < INF]

    if not times:
        return fig

    # 直方图
    ax = axes[0]
    ax.hist(times, bins=30, color='#4A7C9E', edgecolor='white', alpha=0.8)
    ax.axvline(np.mean(times), color='#D4524E', linestyle='--',
               label=f'均值={np.mean(times):.1f}min')
    ax.axvline(np.median(times), color='#2E7D32', linestyle=':',
               label=f'中位数={np.median(times):.1f}min')
    ax.set_xlabel('水流到达时间 (min)', fontsize=12)
    ax.set_ylabel('端点数量', fontsize=12)
    ax.set_title('到达时间直方图', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # 累积分布
    ax = axes[1]
    sorted_times = np.sort(times)
    cum_prob = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
    ax.plot(sorted_times, cum_prob, color='#4A7C9E', linewidth=2)
    ax.axhline(0.5, color='gray', linestyle=':', alpha=0.5)
    ax.axhline(0.9, color='gray', linestyle=':', alpha=0.5)
    ax.set_xlabel('水流到达时间 (min)', fontsize=12)
    ax.set_ylabel('累积占比', fontsize=12)
    ax.set_title('累积分布函数', fontsize=13)
    ax.grid(True, alpha=0.3)

    # 添加统计信息
    stats_text = (f"节点总数: {len(times)}\n"
                  f"最小时间: {min(times):.1f} min\n"
                  f"最大时间: {max(times):.1f} min\n"
                  f"铺满时刻: {water_state.t_spread:.1f} min\n"
                  f"总灌满: {water_state.T_total:.1f} min")
    ax.text(0.95, 0.05, stats_text, transform=ax.transAxes,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
            fontsize=9)

    fig.suptitle(title, fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


def plot_water_level_curves(
    edges: Dict[int, Edge],
    water_state: WaterState,
    key_edge_ids: Optional[List[int]] = None,
    title: str = "关键巷道水位-时间曲线",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (12, 8)
) -> plt.Figure:
    """绘制关键巷道的水位随时间变化曲线"""
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    t_spread = water_state.t_spread

    # 若未指定关键边，选择长度最长的几条
    if key_edge_ids is None:
        sorted_edges = sorted(edges.values(), key=lambda e: e.length, reverse=True)
        key_edge_ids = [e.id for e in sorted_edges[:8]]

    colors = cm.viridis(np.linspace(0.2, 0.9, len(key_edge_ids)))

    for i, eid in enumerate(key_edge_ids):
        if eid not in edges:
            continue
        e = edges[eid]
        t_arr = water_state.edge_spread_time.get(eid, t_spread)
        t_0_3 = water_state.edge_0_3m_time.get(eid, INF)
        t_full = water_state.edge_full_time.get(eid, INF)

        if t_0_3 >= INF / 2:
            continue

        # 构建水位-时间曲线
        # 0-t_arr: h=0
        # t_arr-t_arr+(0.3-0.1)*rise_time: h从0.1升到0.3
        # t_0_3-t_full: h从0.3升到3.0

        # 简化：三折线
        time_points = [0, t_arr, t_arr + 0.01, t_0_3, t_full, t_full + 1000]
        level_points = [0, 0, H0, H_SAFE, H_MAX, H_MAX]

        # 裁剪 INF
        valid_mask = [t < INF / 2 for t in time_points]
        time_plot = [t for t, ok in zip(time_points, valid_mask) if ok]
        level_plot = [h for h, ok in zip(level_points, valid_mask) if ok]

        if len(time_plot) >= 2:
            ax.plot(time_plot, level_plot, color=colors[i], linewidth=1.5,
                   label=f'巷道{eid} (L={e.length:.0f}m)', alpha=0.8)

    # 安全阈值线
    ax.axhline(H_SAFE, color='#D4524E', linestyle='--', linewidth=1.5, alpha=0.7,
              label=f'安全阈值 h={H_SAFE}m')
    ax.axhline(H0, color='gray', linestyle=':', linewidth=1, alpha=0.5,
              label=f'初始水位 h={H0}m')

    ax.set_xlabel('时间 (min)', fontsize=12)
    ax.set_ylabel('水位高度 (m)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=9, framealpha=0.8, ncol=2)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, None)
    ax.set_ylim(0, H_MAX * 1.1)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


def plot_escape_paths(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    init_path: Optional[List[int]],
    new_path: Optional[List[int]],
    water_state: WaterState,
    source_points: Optional[List[Tuple[float, float, float]]] = None,
    exit_node: Optional[int] = None,
    title: str = "逃生路径规划对比",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """绘制逃生路径对比图（初始路径 vs 新路径）"""
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # 绘制背景网络
    for e in edges.values():
        x = [nodes[e.node_u].x, nodes[e.node_v].x]
        y = [nodes[e.node_u].y, nodes[e.node_v].y]

        # 根据水位着色
        t_0_3 = water_state.edge_0_3m_time.get(e.id, INF)
        t_arr = water_state.node_arrival.get(e.node_u, INF)

        if t_0_3 < T_SWITCH + 10:
            color = '#D4A0A0'  # 很快淹没
        elif t_arr < INF:
            color = '#A0B4C8'  # 有水
        else:
            color = '#C8C8C8'  # 干燥

        ax.plot(x, y, color=color, linewidth=0.5, alpha=0.4, zorder=1)

    # 绘制初始路径
    if init_path and len(init_path) >= 2:
        path_x = [nodes[nid].x for nid in init_path]
        path_y = [nodes[nid].y for nid in init_path]
        ax.plot(path_x, path_y, color='#2E7D32', linewidth=2.5,
                linestyle='-', marker='o', markersize=4, zorder=4,
                label='初始逃生路径')
        # 标记方向
        for i in range(len(init_path) - 1):
            dx = nodes[init_path[i+1]].x - nodes[init_path[i]].x
            dy = nodes[init_path[i+1]].y - nodes[init_path[i]].y
            mid_x = (nodes[init_path[i]].x + nodes[init_path[i+1]].x) / 2
            mid_y = (nodes[init_path[i]].y + nodes[init_path[i+1]].y) / 2
            ax.arrow(mid_x, mid_y, dx * 0.05, dy * 0.05,
                    head_width=5, head_length=5, fc='#2E7D32', ec='#2E7D32',
                    alpha=0.6, zorder=5)

    # 绘制新路径
    if new_path and len(new_path) >= 2:
        path_x = [nodes[nid].x for nid in new_path]
        path_y = [nodes[nid].y for nid in new_path]
        ax.plot(path_x, path_y, color='#C44536', linewidth=2.5,
                linestyle='--', marker='s', markersize=4, zorder=4,
                label='重规划路径')

    # 绘制节点
    ax.scatter([n.x for n in nodes.values()], [n.y for n in nodes.values()],
              c='#4A7C9E', s=5, alpha=0.4, zorder=2)

    # 标记突水点
    if source_points:
        for i, sp in enumerate(source_points):
            label = f'突水点 {chr(65+i)}' if i < 2 else None
            ax.scatter(sp[0], sp[1], s=150, marker='*',
                      c=[COLOR_SOURCE_A, COLOR_SOURCE_B][i] if i < 2 else '#888888',
                      zorder=6, label=label)

    # 标记安全出口
    if exit_node is not None and exit_node in nodes:
        ax.scatter(nodes[exit_node].x, nodes[exit_node].y,
                  s=200, marker='s', c='#2E7D32', edgecolors='white',
                  linewidth=2, zorder=6, label='安全出口')

    # 标记路径起点
    if init_path:
        start = init_path[0]
        if start in nodes:
            ax.scatter(nodes[start].x, nodes[start].y,
                      s=120, marker='^', c='#FF8C42', edgecolors='white',
                      linewidth=2, zorder=6, label='矿工起点')

    ax.set_xlabel('X 坐标 (m)', fontsize=12)
    ax.set_ylabel('Y 坐标 (m)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.8)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


def plot_dual_source_collision(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state_A: WaterState,
    water_state_B: WaterState,
    blocked_edges: Set[int],
    edge_meet_time: Dict[int, float],
    source_A: Tuple[float, float, float],
    source_B: Tuple[float, float, float],
    title: str = "双源漫延碰撞检测",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """绘制双源漫延碰撞检测示意"""
    fig, ax = plt.subplots(1, 1, figsize=figsize)

    # 绘制所有边
    for e in edges.values():
        x = [nodes[e.node_u].x, nodes[e.node_v].x]
        y = [nodes[e.node_u].y, nodes[e.node_v].y]

        if e.id in blocked_edges:
            # 封闭巷道
            ax.plot(x, y, color='#8B4A4A', linewidth=1.5, alpha=0.7, zorder=3)
            # 交叉标记
            mid_x = (x[0] + x[1]) / 2
            mid_y = (y[0] + y[1]) / 2
            ax.plot(mid_x, mid_y, marker='X', color='#8B4A4A', markersize=8, zorder=4)
        else:
            ax.plot(x, y, color='#B0B0B0', linewidth=0.5, alpha=0.4, zorder=1)

    # 绘制 A 源覆盖的节点（用圆形）
    for nid in water_state_A.node_arrival:
        if nid in nodes:
            ax.scatter(nodes[nid].x, nodes[nid].y,
                      c=COLOR_SOURCE_A, s=10, alpha=0.4, zorder=2)

    # 绘制 B 源覆盖的节点
    for nid in water_state_B.node_arrival:
        if nid in nodes:
            ax.scatter(nodes[nid].x, nodes[nid].y,
                      c=COLOR_SOURCE_B, s=10, alpha=0.4, zorder=2)

    # 标记突水点
    ax.scatter(source_A[0], source_A[1], s=200, marker='*',
              c=COLOR_SOURCE_A, edgecolors='white', linewidth=1,
              zorder=5, label='突水点 A (t=0)')
    ax.scatter(source_B[0], source_B[1], s=200, marker='*',
              c=COLOR_SOURCE_B, edgecolors='white', linewidth=1,
              zorder=5, label=f'突水点 B (t={T_OFFSET_B_PLANAR}min)')

    # 标记封闭巷道相遇位置
    for eid, t_meet in edge_meet_time.items():
        if eid in edges:
            e = edges[eid]
            x = (nodes[e.node_u].x + nodes[e.node_v].x) / 2
            y = (nodes[e.node_u].y + nodes[e.node_v].y) / 2
            ax.scatter(x, y, s=60, marker='X', c='#8B0000', zorder=6)
            ax.annotate(f't_meet={t_meet:.0f}min', xy=(x, y),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=7, color='#8B0000')

    ax.set_xlabel('X 坐标 (m)', fontsize=12)
    ax.set_ylabel('Y 坐标 (m)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.8)

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


def plot_network_3d(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state: Optional[WaterState] = None,
    title: str = "三维巷道网络水流漫延",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """绘制三维巷道网络及水流漫延状态"""
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection='3d')

    # 绘制边
    for e in edges.values():
        x = [nodes[e.node_u].x, nodes[e.node_v].x]
        y = [nodes[e.node_u].y, nodes[e.node_v].y]
        z = [nodes[e.node_u].z, nodes[e.node_v].z]

        if water_state and e.id in water_state.edge_0_3m_time:
            t_0_3 = water_state.edge_0_3m_time.get(e.id, INF)
            if t_0_3 < INF / 2:
                color = '#D4A0A0'
            else:
                color = '#6B8EB5'
        else:
            color = '#8A9BA8'

        ax.plot(x, y, z, color=color, linewidth=0.6, alpha=0.6)

    # 绘制节点
    xs = [n.x for n in nodes.values()]
    ys = [n.y for n in nodes.values()]
    zs = [n.z for n in nodes.values()]

    if water_state and water_state.node_arrival:
        times = [water_state.node_arrival.get(nid, INF) for nid in nodes]
        valid_mask = [t < INF / 2 for t in times]
        if any(valid_mask):
            valid_times = [t for t, ok in zip(times, valid_mask) if ok]
            if valid_times:
                cmap = cm.plasma
                norm = Normalize(vmin=min(valid_times), vmax=max(valid_times))
                colors_3d = []
                for t in times:
                    if t < INF / 2:
                        colors_3d.append(cmap(norm(t)))
                    else:
                        colors_3d.append('lightgray')

                sc = ax.scatter(xs, ys, zs, c=colors_3d, s=8, alpha=0.7, zorder=3)
            else:
                ax.scatter(xs, ys, zs, c='#6B8EB5', s=8, alpha=0.7, zorder=3)
        else:
            ax.scatter(xs, ys, zs, c='#6B8EB5', s=8, alpha=0.7, zorder=3)
    else:
        ax.scatter(xs, ys, zs, c='#6B8EB5', s=8, alpha=0.7, zorder=3)

    ax.set_xlabel('X (m)', fontsize=11)
    ax.set_ylabel('Y (m)', fontsize=11)
    ax.set_zlabel('Z (m)', fontsize=11)
    ax.set_title(title, fontsize=14, fontweight='bold')

    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


def plot_flood_animation_frames(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state: WaterState,
    n_frames: int = 6,
    title: str = "水流漫延过程快照",
    save_path: Optional[str] = None,
    figsize: Tuple[int, int] = (16, 10)
) -> plt.Figure:
    """
    绘制水流漫延过程的多帧快照（用于模拟动画效果）。
    按时间均匀采样 n_frames 个时间点，展示漫延推进过程。
    """
    times = sorted(set(water_state.node_arrival.values()))
    if len(times) < 2:
        return plt.figure(figsize=figsize)

    t_min = 0
    t_max = water_state.t_spread if water_state.t_spread > 0 else max(times)

    if t_max <= t_min:
        return plt.figure(figsize=figsize)

    snapshots = np.linspace(t_min * 0.1, t_max * 1.0, n_frames)

    n_cols = min(3, n_frames)
    n_rows = (n_frames + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_rows * n_cols > 1 else [axes]

    for idx, t_snap in enumerate(snapshots):
        if idx >= len(axes):
            break
        ax = axes[idx]

        # 确定到该时刻为止已覆盖的节点
        covered_at_t = {
            nid for nid, t_arr in water_state.node_arrival.items()
            if t_arr <= t_snap
        }

        # 绘制边
        for e in edges.values():
            x = [nodes[e.node_u].x, nodes[e.node_v].x]
            y = [nodes[e.node_u].y, nodes[e.node_v].y]

            u_covered = e.node_u in covered_at_t
            v_covered = e.node_v in covered_at_t

            if u_covered and v_covered:
                color = '#4A90D9'
                lw = 1.0
            elif u_covered or v_covered:
                color = '#8AB8E6'
                lw = 0.8
            else:
                color = '#D0D0D0'
                lw = 0.3

            ax.plot(x, y, color=color, linewidth=lw, alpha=0.6)

        # 绘制节点
        for nid, n in nodes.items():
            if nid in covered_at_t:
                ax.scatter(n.x, n.y, c='#4A90D9', s=10, alpha=0.7, zorder=3)
            else:
                ax.scatter(n.x, n.y, c='#D0D0D0', s=5, alpha=0.3, zorder=2)

        # 统计信息
        pct = len(covered_at_t) / max(len(nodes), 1) * 100
        ax.set_title(f't = {t_snap:.0f} min ({pct:.1f}%)', fontsize=11)
        ax.set_xlabel('X (m)', fontsize=9)
        ax.set_ylabel('Y (m)', fontsize=9)
        ax.set_aspect('equal')
        ax.grid(True, alpha=0.2)

    # 隐藏多余的子图
    for idx in range(len(snapshots), len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle(title, fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[INFO] 图表已保存: {save_path}")

    return fig


# ============================================================================
# 核心执行入口
# ============================================================================

def compute_spread_time_key_statistics(water_state: WaterState) -> Dict[str, float]:
    """计算水流漫延的关键统计量"""
    stats = {}
    arrival_times = list(water_state.node_arrival.values())
    arrival_times = [t for t in arrival_times if t < INF]

    if arrival_times:
        stats['n_nodes'] = len(arrival_times)
        stats['t_min_arrival'] = min(arrival_times)
        stats['t_max_arrival'] = max(arrival_times)
        stats['t_mean_arrival'] = np.mean(arrival_times)
        stats['t_median_arrival'] = np.median(arrival_times)
        stats['t_spread'] = water_state.t_spread
        stats['T_total'] = water_state.T_total

    return stats


def run_problem_1_planar(
    output_dir: str,
    use_synthetic: bool = True,
    synthetic_n_nodes: int = 100
) -> Tuple[Dict[int, Node], Dict[int, Edge], WaterState]:
    """
    运行问题1：平面网络单源水流漫延（附件一）
    """
    print("=" * 70)
    print("问题1: 平面网络单源水流漫延（附件一）")
    print("=" * 70)

    # 加载数据
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'MCMKnowledgeBase', 'raw', '2025', 'D', '附件', '附件1.xlsx'
    )

    nodes, edges = load_mine_network(data_path, is_3d=False)

    if not nodes or not edges:
        if use_synthetic:
            print(f"[INFO] 使用合成数据 ({synthetic_n_nodes} 节点)")
            nodes, edges = generate_synthetic_planar_network(
                n_nodes=synthetic_n_nodes,
                grid_width=800.0, grid_height=600.0,
                seed=42
            )
        else:
            print("[ERROR] 无可用数据")
            return {}, {}, WaterState({}, {}, {}, {}, 0.0, 0.0)

    # 突水点 A1 坐标（基于优秀论文数据）
    source_A1 = (400.0, 300.0, 0.0)

    # 运行单源漫延
    water_state = single_source_flood(nodes, edges, source_A1)

    # 输出统计
    stats = compute_spread_time_key_statistics(water_state)
    print(f"\n[RESULTS] 平面单源漫延统计:")
    for k, v in stats.items():
        print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

    # 可视化
    # 图1: 网络拓扑（着色示到达时间）
    plot_network_topology(
        nodes, edges, water_state,
        title="平面巷道网络及水流到达时间",
        source_point=source_A1,
        save_path=os.path.join(output_dir, 'fig1_network_topology_planar.png')
    )

    # 图2: 到达时间分布
    plot_flood_time_histogram(
        water_state,
        title="端点水流到达时间分布（平面网络）",
        save_path=os.path.join(output_dir, 'fig2_flood_time_histogram.png')
    )

    # 图3: 水位-时间曲线
    plot_water_level_curves(
        edges, water_state,
        title="关键巷道水位-时间曲线（平面网络）",
        save_path=os.path.join(output_dir, 'fig3_water_level_curves.png')
    )

    # 图4: 漫延过程快照
    plot_flood_animation_frames(
        nodes, edges, water_state, n_frames=6,
        title="水流漫延过程快照（平面网络）",
        save_path=os.path.join(output_dir, 'fig4_flood_frames.png')
    )

    return nodes, edges, water_state


def run_problem_1_3d(
    output_dir: str,
    use_synthetic: bool = True,
    synthetic_n_nodes: int = 60
) -> Tuple[Dict[int, Node], Dict[int, Edge], WaterState]:
    """
    运行问题1：三维网络单源水流漫延（附件二）
    """
    print("\n" + "=" * 70)
    print("问题1(三维): 立体网络单源水流漫延（附件二）")
    print("=" * 70)

    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'MCMKnowledgeBase', 'raw', '2025', 'D', '附件', '附件2.xlsx'
    )

    nodes, edges = load_mine_network(data_path, is_3d=True)

    if not nodes or not edges:
        if use_synthetic:
            print(f"[INFO] 使用合成数据 ({synthetic_n_nodes} 节点, 5层)")
            nodes, edges = generate_synthetic_3d_network(
                n_nodes=synthetic_n_nodes,
                grid_width=500.0, grid_height=500.0,
                n_levels=5, level_height=30.0,
                seed=42
            )
        else:
            print("[ERROR] 无可用数据")
            return {}, {}, WaterState({}, {}, {}, {}, 0.0, 0.0)

    # 突水点 A2（三维网络突水点坐标，位于较低层）
    z_min = min(n.z for n in nodes.values())
    z_max = max(n.z for n in nodes.values())
    source_A2 = (300.0, 300.0, z_min + (z_max - z_min) * 0.2)

    # 运行三维漫延
    water_state_3d = single_source_flood_3d(nodes, edges, source_A2)

    stats = compute_spread_time_key_statistics(water_state_3d)
    print(f"\n[RESULTS] 三维单源漫延统计:")
    for k, v in stats.items():
        print(f"  {k}: {v:.2f}" if isinstance(v, float) else f"  {k}: {v}")

    # 可视化
    plot_network_3d(
        nodes, edges, water_state_3d,
        title="三维巷道网络水流漫延",
        save_path=os.path.join(output_dir, 'fig5_network_3d.png')
    )

    return nodes, edges, water_state_3d


def run_problem_2(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state: WaterState,
    output_dir: str
) -> PathResult:
    """
    运行问题2：最佳逃生路径规划（基于平面网络单源漫延结果）
    """
    print("\n" + "=" * 70)
    print("问题2: 最佳逃生路径——时变Dijkstra")
    print("=" * 70)

    if not nodes or not edges:
        print("[ERROR] 无网络数据，跳过问题2")
        return PathResult(None, INF)

    # 确定起点（远离突水点的一个端点）和安全出口
    # 选择距离突水点最远的节点作为矿工起点
    if water_state.node_arrival:
        # 选择到达时间最晚的节点作为矿工起点（最坏情况）
        farthest_node = max(water_state.node_arrival.items(), key=lambda x: x[1])
        start_node = farthest_node[0]
    else:
        start_node = list(nodes.keys())[0]

    # 安全出口：选择网络边缘的多个节点
    # 按 x+y 最小/最大等选择
    node_list = list(nodes.values())
    exit_candidates = [
        min(node_list, key=lambda n: n.x + n.y).id,
        max(node_list, key=lambda n: n.x + n.y).id,
        min(node_list, key=lambda n: n.x - n.y).id,
        max(node_list, key=lambda n: n.x - n.y).id
    ]
    exit_nodes = list(set(exit_candidates))

    print(f"[INFO] 矿工起点: {start_node}")
    print(f"[INFO] 安全出口: {exit_nodes}")

    # 运行时变 Dijkstra
    init_path, init_time = time_dependent_dijkstra(
        nodes, edges, water_state, start_node, exit_nodes
    )

    if init_path:
        print(f"[RESULT] 初始逃生路径: {init_path}")
        print(f"[RESULT] 初始逃生时间: {init_time:.2f} min")
    else:
        print(f"[RESULT] 未找到可行逃生路径")

    # 可视化
    plot_escape_paths(
        nodes, edges, init_path, None, water_state,
        source_points=[(400.0, 300.0, 0.0)],
        exit_node=exit_nodes[0] if exit_nodes else None,
        title=f"问题2最佳逃生路径 (总时间={init_time:.1f}min)" if init_path else "问题2: 未找到可行路径",
        save_path=os.path.join(output_dir, 'fig6_escape_path_q2.png')
    )

    return PathResult(init_path, init_time)


def run_problem_3(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    output_dir: str,
    use_synthetic: bool = True,
    synthetic_n_nodes: int = 80
) -> Tuple[WaterState, Set[int], Dict[int, float]]:
    """
    运行问题3：双源并行漫延 + 碰撞检测
    """
    print("\n" + "=" * 70)
    print("问题3: 双源并行漫延 + 碰撞检测")
    print("=" * 70)

    # 若 nodes 为空（未从问题1保留），重新生成
    if not nodes or not edges:
        if use_synthetic:
            print(f"[INFO] 使用合成数据 ({synthetic_n_nodes} 节点)")
            nodes, edges = generate_synthetic_planar_network(
                n_nodes=synthetic_n_nodes,
                grid_width=800.0, grid_height=600.0,
                seed=42
            )
        else:
            print("[ERROR] 无可用数据")
            empty_state = WaterState({}, {}, {}, {}, 0.0, 0.0)
            return empty_state, set(), {}

    # 双突水点位置
    source_A1 = (400.0, 300.0, 0.0)  # A1 突水点 (t=0)
    source_B1 = (600.0, 450.0, 0.0)  # B1 突水点 (t=4min)

    # 首先独立运行两个单源漫延（用于可视化比较）
    ws_A = single_source_flood(nodes, edges, source_A1)
    # H3 修正: 为 B 源单独计算真实 WaterState，替代之前的空字典
    ws_B = single_source_flood(nodes, edges, source_B1)

    # 双源并行漫延
    dual_state, blocked, edge_meet = dual_source_flood(
        nodes, edges, source_A1, source_B1,
        t_offset_B=T_OFFSET_B_PLANAR
    )

    # 统计
    if dual_state.node_arrival:
        print(f"[RESULT] 双源漫延: t_spread={dual_state.t_spread:.1f} min, "
              f"总灌满时间 ≈ {dual_state.T_total:.1f} min")
        print(f"[RESULT] 封闭巷道数: {len(blocked)}")

    # 可视化 — 传入真实 B 源单源漫延结果
    plot_dual_source_collision(
        nodes, edges, ws_A, ws_B,
        blocked, edge_meet, source_A1, source_B1,
        title="双源漫延碰撞检测与封闭巷道",
        save_path=os.path.join(output_dir, 'fig7_dual_source_collision.png')
    )

    return dual_state, blocked, edge_meet


def run_problem_4(
    nodes: Dict[int, Node],
    edges: Dict[int, Edge],
    water_state_single: WaterState,
    dual_water_state: WaterState,
    init_path: List[int],
    output_dir: str
) -> None:
    """
    运行问题4：在线路径重规划
    """
    print("\n" + "=" * 70)
    print("问题4: 第二突水点后的路径重规划")
    print("=" * 70)

    if not nodes or not edges or not init_path:
        print("[ERROR] 缺少必要数据，跳过问题4")
        return

    # 获取起点和出口
    start_node = init_path[0]

    # 获取出口（路径最后一个节点）
    exit_node = init_path[-1]
    exit_nodes = [exit_node]

    # 重规划路径
    new_path, new_time, decision = replan_path(
        nodes, edges, dual_water_state,
        init_path, start_node, exit_nodes,
        t_switch=T_SWITCH
    )

    print(f"[RESULT] 重规划决策: {decision}")
    if new_path:
        print(f"[RESULT] 最终路径: {new_path}")
        print(f"[RESULT] 最终时间: {new_time:.2f} min")

    # 可视化对比
    plot_escape_paths(
        nodes, edges, init_path, new_path, dual_water_state,
        source_points=[(400.0, 300.0, 0.0), (600.0, 450.0, 0.0)],
        exit_node=exit_node,
        title=f"路径重规划对比 (决策: {decision}, 时间={new_time:.1f}min)" if new_path else "路径重规划: 无可行路径",
        save_path=os.path.join(output_dir, 'fig8_escape_path_q4.png')
    )


def generate_summary_table(
    results: Dict[str, Any],
    output_dir: str
) -> str:
    """
    生成结果汇总表并保存为 CSV 和文本格式。
    """
    lines = []
    lines.append("=" * 80)
    lines.append("MCM 2025-D 矿井突水漫延仿真与逃生路径规划 — 结果汇总")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"{'指标':<40} {'值':<20} {'单位':<10}")
    lines.append("-" * 80)

    for category, data in results.items():
        if isinstance(data, dict):
            lines.append(f"\n[{category}]")
            for k, v in data.items():
                if isinstance(v, float):
                    # H4 修正: T_total / t_spread / escape_time / total_time 均为时间单位
                    is_time_key = ('时间' in str(k) or '时刻' in str(k) or
                                   'T_total' in str(k) or 't_spread' in str(k) or
                                   'time' in str(k) or 'Time' in str(k))
                    lines.append(f"  {k:<38} {v:<20.2f} {'min' if is_time_key else '-'}")
                else:
                    lines.append(f"  {k:<38} {str(v):<20}")
        else:
            val = f"{data:.2f}" if isinstance(data, float) else str(data)
            lines.append(f"{category:<40} {val:<20}")

    lines.append("")
    lines.append("=" * 80)

    summary_text = '\n'.join(lines)

    # 保存
    txt_path = os.path.join(output_dir, 'summary_results.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f"[INFO] 结果汇总已保存: {txt_path}")

    return summary_text


def main():
    """主执行函数"""
    print("=" * 70)
    print("MCM 2025-D 矿井突水漫延仿真与逃生路径规划")
    print("=" * 70)

    # 确定输出目录
    output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)

    print(f"[INFO] 输出目录: {output_dir}")
    print(f"[INFO] Python: {sys.version}")
    print(f"[INFO] NumPy: {np.__version__}")

    # 修复 M-2025D-015: flow_dir_flag 初始化
    # 注：已在 get_travel_time() 函数中修复

    # 修复 M-2025D-016: get_remaining_segment 已实现
    # 注：get_remaining_segment() 和 evaluate_path_under_dual() 均已实现

    results = {}

    # ── 问题1: 平面网络单源漫延 ──
    nodes_p1, edges_p1, ws_p1 = run_problem_1_planar(
        output_dir, use_synthetic=True, synthetic_n_nodes=100
    )
    results['Problem1_平面单源'] = compute_spread_time_key_statistics(ws_p1)

    # ── 问题1: 三维网络单源漫延 ──
    nodes_3d, edges_3d, ws_3d = run_problem_1_3d(
        output_dir, use_synthetic=True, synthetic_n_nodes=60
    )
    results['Problem1_三维单源'] = compute_spread_time_key_statistics(ws_3d)

    # ── 问题2: 时变 Dijkstra ──
    path_result_p2 = run_problem_2(nodes_p1, edges_p1, ws_p1, output_dir)
    results['Problem2_逃生路径'] = {
        'path_found': path_result_p2.is_feasible(),
        'escape_time': path_result_p2.total_time if path_result_p2.is_feasible() else INF,
        'path_length': len(path_result_p2.path) if path_result_p2.is_feasible() else 0
    }

    # ── 问题3: 双源漫延 ──
    dual_state, blocked_set, edge_meet = run_problem_3(
        nodes_p1, edges_p1, output_dir,
        use_synthetic=True, synthetic_n_nodes=80
    )
    results['Problem3_双源漫延'] = {
        '封闭巷道数': len(blocked_set),
        '总灌满时间(双源)': dual_state.T_total
    }
    if edge_meet:
        results['Problem3_双源漫延']['最早碰撞时间'] = min(edge_meet.values())
        results['Problem3_双源漫延']['最晚碰撞时间'] = max(edge_meet.values())

    # ── 问题4: 路径重规划 ──
    if path_result_p2.is_feasible():
        run_problem_4(
            nodes_p1, edges_p1, ws_p1, dual_state,
            path_result_p2.path, output_dir
        )

    # ── 生成汇总表 ──
    generate_summary_table(results, output_dir)

    print("\n" + "=" * 70)
    print("所有计算完成。")
    print(f"结果保存在: {output_dir}")
    print("=" * 70)


if __name__ == '__main__':
    main()
