---
title: "CVaR 条件风险价值优化"
sources: ["raw/2024/C/C038_2024.md"]
related: ["[[2024-c-crop-strategy]]", "[[genetic-algorithm]]", "[[monte-carlo-simulation]]"]
tags: ["风险度量", "优化", "金融数学", "不确定性"]
last_compiled: 2026-05-29
---

# CVaR 条件风险价值优化

CVaR（Conditional Value at Risk）是 VaR 的改进版，度量超过 VaR 阈值部分的期望损失，能更全面地捕捉尾部风险。

## 定义

对损失分布 $L$ 和置信水平 $\alpha$：
$$\text{CVaR}_\alpha = \mathbb{E}[L \mid L \geq \text{VaR}_\alpha]$$

即损失超过 VaR 阈值时的条件期望。CVaR 是凸的风险度量（VaR 不一定是凸的），因此更适合优化。

## MCM 应用（2024 C 题）

在农作物种植策略中，考虑四种不确定性（预期销售量 ±5%、亩产量 ±10%、种植成本年增 5%、销售价格波动）：

- **目标函数**：$\max \; \mathbb{E}[\text{Profit}] - \lambda \cdot \text{CVaR}_\alpha$
- 参数 $\lambda$ 控制风险厌恶程度
- CVaR 项捕获"极端低利润"情景的期望损失

## 与 DEGA 的结合

差分进化遗传算法（DEGA）搜索决策空间，每次评估目标函数时：
1. 对不确定参数采样（蒙特卡洛或多情景）
2. 计算利润分布
3. 计算 $\mathbb{E}[\text{Profit}]$ 和 CVaR
4. 返回加权目标值

## 对比

- **VaR**：仅关注分位点，忽视尾部形状
- **CVaR**：关注整个尾部，对极端风险的度量更稳健
- 在 2024 C 题中，CVaR 优化使七年总利润比不考虑不确定性时仅降低约 5%（2153→1710 万）
