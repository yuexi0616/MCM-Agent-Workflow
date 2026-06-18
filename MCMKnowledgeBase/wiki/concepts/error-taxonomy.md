---
title: "Error Taxonomy"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[continuous-improvement-loop]]", "[[agent-role-specialization]]", "[[chain-intercept-workflow]]", "[[multi-agent-collaboration]]"]
tags: ["error", "taxonomy", "quality", "mcm"]
last_compiled: 2026-05-30
---

# Error Taxonomy

错误分类法是系统从失败中学习的核心基础设施。将破坏者在审计中发现的漏洞归纳为 14 个标准类别（category），实现错误的可追溯、可统计、可预防。每条漏洞在 `_workspace/error-registry.json` 中按此分类体系标注，使后续流水线运行可精准提取历史经验。

## 分类体系（14 类，按阶段分组）

### 建模阶段（5 类）

| 分类 Tag | 含义 | 典型场景 |
|----------|------|----------|
| `physics_violation` | 违反物理定律或现实约束 | 忽略空气阻力、忽略能量守恒、超出材料强度极限 |
| `dimension_mismatch` | 量纲不一致 | 等式左边 [m]，右边 [m/s]；矩阵运算维度不匹配 |
| `missing_assumption` | 缺少必要假设或假设无依据 | 假设"数据服从正态分布"但未检验；假设未说明合理性 |
| `overly_strong_assumption` | 假设过强，丧失一般性 | 假设"所有摩擦系数为0"导致模型无法推广到现实 |
| `ambiguous_algorithm` | 算法流程不够具体，代码手无法实现 | 伪代码缺少初始条件、终止条件或关键参数设定 |

### 编码阶段（4 类）

| 分类 Tag | 含义 | 典型场景 |
|----------|------|----------|
| `data_leakage` | 使用了测试集/未来信息训练模型 | 用全数据集做标准化后再划分；特征工程中用到了标签信息 |
| `misleading_viz` | 误导性可视化 | 截断Y轴放大波动；无误差棒/置信区间；坐标轴无单位 |
| `reproducibility` | 随机种子未固定，结果不可复现 | 未设 `np.random.seed()`；随机初始化不同导致结论不一致 |
| `missing_error_handling` | 缺少边界/异常值处理 | 除数为零不检查；缺失值直接丢弃无说明；无异常值检测 |

### 论文阶段（4 类）

| 分类 Tag | 含义 | 典型场景 |
|----------|------|----------|
| `overfitting_conclusion` | 结论超出证据支撑 | "证明了最优性"但只有数值验证；过度外推超出数据范围 |
| `missing_quantitative_claim` | 摘要/结论缺少量化指标 | "效果显著提升"但未给具体提升百分比 |
| `llm_filler_phrase` | AI 写作痕迹（废话套话） | "值得注意的是"、"综上所述"、"具有一定的参考价值" |
| `data_mismatch` | 论文数据与代码输出不一致 | 论文中 RMSE=0.03，代码输出 RMSE=0.05；图表描述与数据不对应 |

### 通用（1 类）

| 分类 Tag | 含义 | 典型场景 |
|----------|------|----------|
| `xml_format_error` | XML 标签格式错误或缺失 | 缺少必需标签；标签未正确闭合；输出含多余内容破坏 XML 结构 |

## 分类体系的来源

1. **MCM 竞赛评审标准**：从历年优秀论文的共同特征（见 [[2025-mcm-competition]] 等概览）反向推导出常见失分点
2. **Agent 协作系统的角色边界**：基于 [[agent-role-specialization|四角色的职责重叠区]]，识别出跨角色交接中容易出现的典型错误
3. **数学建模常见误区**：量纲错误、过拟合、外推超出数据范围等是建模竞赛中反复出现的共性问题

每类错误关联到对应 Agent 的自检清单（Self-Check），Agent 启动时通过读取 `_workspace/error-registry.json` 中本阶段的历史错误记录，在输出前逐条对照确认是否已避免同类问题。这一机制详见 [[continuous-improvement-loop]]。
