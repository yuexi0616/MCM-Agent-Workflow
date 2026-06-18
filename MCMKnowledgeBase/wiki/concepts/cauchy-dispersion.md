---
title: "Cauchy 色散模型"
sources: ["raw/2025/B/B157_2025MCM优秀论文.md"]
related: ["[[optical-interference-model]]", "[[spectral-data-preprocessing]]"]
tags: ["optics", "material-science", "parameterization"]
last_compiled: 2026-05-27
---

# Cauchy 色散模型

## 物理含义

色散指材料的折射率随波长变化。Cauchy 模型给出了折射率对波长的经验关系：

$$n(\lambda) = A + \frac{B}{\lambda^2}$$

其中 A 和 B 是待定的材料参数，λ 为入射光波长。该模型适用于透明波段（远离材料吸收带）。

## 在 B 题中的作用

Cauchy 模型将折射率从固定常数变为波长依赖函数，使得双光束干涉模型能够更好地拟合实测光谱。A 和 B 作为额外参数与厚度 d 在联合拟合中同时求解。

## 局限性

Cauchy 模型无法描述吸收带附近的色散行为（此时需使用 Lorentz 或 Sellmeier 模型），但在红外透明波段（1000-4000 cm⁻¹）足够精确。
