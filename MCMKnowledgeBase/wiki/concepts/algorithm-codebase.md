---
title: "数学建模30个常用算法 Python 代码库"
sources: ["raw/30个常用模型对应的Python代码/"]
related: ["[[genetic-algorithm]]", "[[dynamic-programming]]", "[[monte-carlo-simulation]]", "[[greedy-algorithm]]", "[[linear-mixed-effects]]", "[[gaussian-process-regression]]", "[[survival-analysis]]", "[[stacking-ensemble]]", "[[heuristic-search]]", "[[runge-kutta-method]]", "[[cvar-optimization]]", "[[bayesian-estimation]]"]
tags: ["代码库", "python", "算法", "参考"]
last_compiled: 2026-05-29
---

# 数学建模30个常用算法 Python 代码库

30 个常用数学建模算法的 Python 实现，覆盖优化、预测、分类、评价、规划五大类。

---

## 优化类 (Optimization)

| # | 算法 | 代码格式 | 相关 wiki 概念 | 典型赛题 |
|---|------|----------|---------------|----------|
| 1 | **线性规划** | .txt | — | 2024 C 作物种植 |
| 2 | **整数规划** | .docx | — | 2023 D 湖羊调度 |
| 3 | **非线性规划** | .docx | — | 2023 A 定日镜 |
| 4 | **二次规划** | .docx | — | 2025 B SiC 厚度 |
| 5 | **动态规划** | folder/.py | [[dynamic-programming]] | 2024 B 生产决策 |
| 6 | **0-1 背包 (DP)** | folder/.py | [[dynamic-programming]] | — |
| 7 | **遗传算法 (GA)** | .txt | [[genetic-algorithm]] | 2022 A 波浪能 |
| 8 | **粒子群 (PSO)** | .txt | [[genetic-algorithm]] | 2024 A 板凳龙 |
| 9 | **模拟退火 (SA)** | .txt | [[greedy-algorithm]] | 2023 B 测线布设 |
| 10 | **最短路径算法** | .docx | [[dynamic-dijkstra]], [[bfs-graph-search]] | 2025 D 矿井逃生 |

## 预测与时间序列 (Prediction & Time Series)

| # | 算法 | 代码格式 | 相关 wiki 概念 | 典型赛题 |
|---|------|----------|---------------|----------|
| 11 | **ARIMA 时间序列** | .txt | — | 2023 E 黄河水沙 |
| 12 | **灰色预测 GM(1,1)** | .txt | — | 2022 E 物料需求 |
| 13 | **马尔科夫预测** | folder/.py | — | 2023 E 水沙趋势 |
| 14 | **数学建模拟合** | .txt | [[gaussian-process-regression]] | 2025 C NIPT |

## 分类与识别 (Classification)

| # | 算法 | 代码格式 | 相关 wiki 概念 | 典型赛题 |
|---|------|----------|---------------|----------|
| 15 | **决策树分类** | .txt | — | 2022 C 玻璃分类 |
| 16 | **随机森林分类** | .txt | [[stacking-ensemble]] | 2025 C NIPT |
| 17 | **支持向量机 (SVM)** | .txt | — | 2022 C 玻璃分类 |
| 18 | **逻辑回归** | .txt | — | 2025 C NIPT |
| 19 | **BP 神经网络** | .txt | — | 2024 E 交通流量 |
| 20 | **CNN 卷积神经网络** | .txt | — | — |
| 21 | **神经网络分类** | folder/.py | — | 2025 C NIPT |
| 22 | **判别分析 (Fisher)** | .rar | — | 2022 C 玻璃分类 |

## 评价与决策 (Evaluation & Decision)

| # | 算法 | 代码格式 | 相关 wiki 概念 | 典型赛题 |
|---|------|----------|---------------|----------|
| 23 | **层次分析法 (AHP)** | .txt | — | 2022 E 物料排序 |
| 24 | **TOPSIS 综合评价** | .docx | — | 2024 D 方案优选 |
| 25 | **模糊综合评价** | .txt | — | — |
| 26 | **多目标模糊综合评价** | .docx | [[cvar-optimization]] | 2024 C 作物策略 |

## 统计与模拟 (Statistics & Simulation)

| # | 算法 | 代码格式 | 相关 wiki 概念 | 典型赛题 |
|---|------|----------|---------------|----------|
| 27 | **蒙特卡洛模型** | .docx | [[monte-carlo-simulation]] | 2023 D 湖羊 |
| 28 | **主成分分析 (PCA)** | .txt | — | 2022 C 玻璃分析 |
| 29 | **K-means 聚类** | .docx | — | 2024 E 时段划分 |
| 30 | **一维/二维插值** | .txt | — | 2025 B SiC 厚度 |

---

## 使用建议

### MCM 论文中代码调用规范
- 核心算法附在论文附录中（精简关键片段）
- 完整代码提交为支撑材料（.py 或 .ipynb）
- 论文正文只描述算法逻辑和关键公式，不贴大段代码

### 格式说明
| 格式 | 可直接使用? | 备注 |
|------|-----------|------|
| `.txt` | 复制到 `.py` 文件 | 代码在文本中，直接可用 |
| `.docx` | 从 Word 提取代码 | 代码在文档内，需复制出来 |
| `.py` (folder) | 直接运行 | 在子文件夹中 |
| `.rar` | 先解压 | Fisher判别模型 |

### 典型算法-赛题组合参考
- **优化类** → 2022 A（GA）、2023 B（SA）、2024 A（PSO）、2025 A（DE）
- **预测类** → 2022 E、2023 E、2025 C
- **分类类** → 2022 C、2025 C
- **评价类** → 2022 E、2024 D
- **模拟类** → 2023 D、2024 C
