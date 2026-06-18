---
title: "Agent-Human Benchmark"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[error-taxonomy]]", "[[continuous-improvement-loop]]", "[[multi-agent-collaboration]]", "[[agent-role-specialization]]", "[[2022-a-wave-energy]]", "[[2024-c-crop-strategy]]", "[[2025-d-mine-flood]]", "[[2024-e-traffic-control]]"]
tags: ["benchmark", "comparison", "improvement", "mcm"]
last_compiled: 2026-05-30
---

# Agent-Human Benchmark

Agent vs Human Benchmark 是 MCM 多智能体系统的外部对标机制：将 Agent 生成论文与历年优秀论文（国家一等奖/特等奖）在方法、数值、结构、创新四个维度进行系统对比，识别 Agent 的方法论优势与数据短板，驱动持续改进环中的"外部校准"环节。

## 对比维度

四维对标框架：
1. **数值对标**：关键定量结果（最优值、利润、时间等）与优秀论文的差距
2. **方法对标**：建模方法的技术深度、严谨性、创新性
3. **结构对标**：论文组织与 MCM 评审标准的符合度
4. **诚实性对标**：对局限性和负面结果的坦诚程度（Agent 的核心优势）

## 首批 4 题对标结论（2026-05-30）

### Agent 的系统性优势

- **方法论严谨性**：每题均有可验证的方法论创新（能量平衡验证、修复+惩罚范式、标准 Dijkstra、时序约束+PELT），不依赖黑箱调参
- **学术诚实性**：F1=0.0685、p>0.05、Q3未完成等负面结果正面标注，超越多数真实竞赛论文的粉饰倾向
- **符号表和敏感度分析**：28-80符号完整含单位，5+维度灵敏度测试——这两项是 MCM 评审的加分项
- **代码可复现性**：种子固定，输出与论文一致，可通过 `python solver.py` 复现全部结果

### Agent 的核心短板

- **数据真实性**：4/4题使用合成数据，导致数值无法与优秀论文直接对标。2024-C 利润差10倍主要来自参数校准
- **计算资源适配过度**：GA 快模式参数(pop=15/gen=30)牺牲了全局收敛性
- **进阶问题完成度不足**：高维相关采样(Cholesky 123维)和深度学习(lifelines缺失)时卡顿

### 改进路线

| 优先级 | 改进项 | 预期提升 |
|:---:|------|------|
| P0 | 真实数据替换合成数据 | 数值可比性建立 |
| P0 | 2024-C参数校准(亩产/价格/成本) | 利润从21.7万→千万级 |
| P1 | 2022-A GA参数恢复(50/100) | 功率从193W→220W+ |
| P1 | 真实网络(665节点)运行 | 对标D037的1672/5016/50162min |
| P2 | 增加对标分析表 | 论文说服力 |

每次流水线运行后，破坏者的审计报告应包含与对应优秀论文的数值偏差检查——当偏差超过 50% 时标记为 `[Risk Level: Med] [Category: benchmark_deviation]`。
