# MCM 数学建模竞赛 — 最终提交材料

## 提交概览

本文件夹包含 4 个赛题的完整 MCM 参赛材料，由 4-Agent 链式拦截协作系统自动生成，经建模手→破坏者→代码手→破坏者→论文手→破坏者 完整流水线审核通过。

## 各赛题内容

| 赛题 | 类型 | 目录 | 论文 | 代码 | 图表 |
|------|------|------|:---:|:---:|:---:|
| 2022-A 波浪能最大输出功率 | 物理建模+ODE优化 | `2022A-WaveEnergy/` | `paper.md` | `solver.py` | 7张 |
| 2024-C 农作物种植策略 | 优化规划+风险决策 | `2024C-CropStrategy/` | `paper.md` | `solver.py` | 18张 |
| 2025-D 矿井突水逃生 | 图论搜索+仿真 | `2025D-MineFlood/` | `paper.md` | `solver.py` | 8张 |
| 2024-E 交通流量管控 | 交通仿真+强化学习 | `2024E-TrafficControl/` | `paper.md` | `solver.py` | 12张 |

## 每个赛题目录结构

```
{赛题名称}/
├── paper.md          # MCM 标准9节学术论文 (Summary→Introduction→...→References)
├── solver.py         # 完整可执行 Python 代码
└── figures/          # 学术风格可视化图表 (300dpi PNG)
```

## 系统信息

- **生成系统**: MCM 4-Agent Chain-Intercept Workflow (Karpathy-Optimized)
- **知识库**: MCMKnowledgeBase (54概念+22实体+5年度概览, 2022-2025)
- **审计系统**: Devil's Advocate 独立审计员, 累计捕获 130+ 漏洞
- **生成日期**: 2026-05-30

## 使用说明

每道题的 `solver.py` 可直接运行：
```bash
pip install numpy scipy matplotlib pandas
python solver.py
```
