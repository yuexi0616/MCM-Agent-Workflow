---
title: "纯方位无源定位"
sources: ["raw/2022/B/B035_2022/ocr/B035_2022.md"]
related: ["[[2022-b-drone-formation]]", "[[heuristic-search]]"]
tags: ["定位", "几何", "无人机", "角度测量"]
last_compiled: 2026-05-29
---

# 纯方位无源定位 (Bearing-Only Passive Localization)

被动接收多架已知位置发射源的信号，仅通过方向夹角信息确定自身位置。核心优势：不发射电磁波，保持电磁静默。

## 两种解法

### Method 1：正弦定理（极坐标）

在 $\triangle 0 S_1 R$ 和 $\triangle 0 S_2 R$ 中列正弦定理，联立求解极坐标 $(d, \theta)$：

$$\frac{r}{\sin\alpha_{0S_1}} = \frac{d}{\sin(\alpha_{0S_1} + \theta - \theta_{S_1})}$$

需要按四个象限分类讨论，较繁琐。

### Method 2：计算几何（两圆求交）

利用"等角对等边"原理：已知点 S₁ 和 O，以及观测角 $\alpha_{S_1O}$→观测点位于以 $O_{0S_1}$ 为圆心的一段优弧上。两个优弧的交点即为位置（其中一个是原点 FY00，另一个是目标位置）。

利用几何对称性：两交点在两圆心连线上对称，$R = 2H$（$H$ 为原点在连心线上的投影）。

## 圆心确定

通过向量叉积 $\overrightarrow{0S_1} \times \overrightarrow{0O_{0S_1}}$ 与 $\overrightarrow{0S_1} \times \overrightarrow{0R'}$ 同号确定正确的圆心。

## 最小发射机数量

在偏差范围内（极径误差 ≤15 m，极角误差 ≤1°），除 FY00 和 FY01 外仅需 1 架即可——通过角度误差范围遍历排除不可能编号。
