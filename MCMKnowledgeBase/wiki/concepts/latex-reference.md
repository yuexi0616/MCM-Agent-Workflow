---
title: "LaTeX 语法参考"
sources: ["raw/LaTeX语法大全.md"]
related: ["[[math-modeling-skill]]", "[[2025-mcm-competition]]", "[[2024-mcm-competition]]"]
tags: ["latex", "排版", "写作工具", "参考"]
last_compiled: 2026-05-29
---

# LaTeX 语法参考

LaTeX 是数学建模论文写作的标准排版工具。本文档为 MCM 论文写作中常用的 LaTeX 语法速查。

## 编译器选择

中文 MCM 论文推荐使用 `lualatex` 或 `xelatex` + `ctex` 文档类（`ctexart`, `ctexrep`）。

## 论文常用结构

```latex
\documentclass[12pt,a4paper]{ctexart}
\usepackage{amsmath,amssymb,amsthm} % 数学
\usepackage{graphicx}                % 图片
\usepackage{booktabs}                % 三线表
\usepackage{geometry}                % 页边距
\usepackage{hyperref}                % 超链接
\usepackage[ruled]{algorithm2e}      % 算法

\newtheorem{theorem}{定理}[section]
\newtheorem{definition}{定义}[section]

\begin{document}
\title{论文标题}
\author{团队编号}
\maketitle
\tableofcontents
...
\end{document}
```

## 数学公式速查

### 行内公式 `$...$`；行间公式 `\[...\]` 或 `equation` 环境

### 多行对齐
```latex
\begin{align}
(a+b)^2 &= a^2 + 2ab + b^2 \\
(a-b)^2 &= a^2 - 2ab + b^2
\end{align}
```

### 分段函数
```latex
f(x) = \begin{cases}
x^2 & x \geq 0 \\
-x^2 & x < 0
\end{cases}
```

### 矩阵（pmatrix/bmatrix）
```latex
\mathbf{A} = \begin{pmatrix}
a_{11} & a_{12} \\
a_{21} & a_{22}
\end{pmatrix}
```

### 自适应括号
`\left( ... \right)` — 自动匹配括号大小

### 常用符号
- 上下标: `x^2`, `a_n`, `x^{2n+1}`
- 分式: `\frac{a}{b}`, 根式: `\sqrt{x}`, `\sqrt[3]{x}`
- 希腊字母: `\alpha, \beta, \gamma, \delta, \theta, \lambda, \mu, \pi, \sigma, \phi, \omega`
- 求和/积分: `\sum_{i=1}^n`, `\int_a^b`, `\prod`
- 比较: `\leq, \geq, \neq, \approx`
- 箭头: `\to, \rightarrow, \Rightarrow, \mapsto`

## 表格

学术论文推荐三线表（`booktabs`）：

```latex
\begin{table}[htbp]
  \centering
  \caption{表格标题}
  \label{tab:xxx}
  \begin{tabular}{lcc}
    \toprule
    列1 & 列2 & 列3 \\
    \midrule
    值1 & 值2 & 值3 \\
    \bottomrule
  \end{tabular}
\end{table}
```

## 图片

```latex
\begin{figure}[htbp]
  \centering
  \includegraphics[width=0.6\textwidth]{figure.png}
  \caption{图片标题}
  \label{fig:xxx}
\end{figure}
```

并排图片：两个 `\includegraphics[width=0.45\textwidth]{...}` 用 `\qquad` 分隔。

## 交叉引用

`\label{sec:xxx}` → `\ref{sec:xxx}`（编号引用）/ `\pageref{sec:xxx}`（页码引用）。需编译两次。

## 算法排版

```latex
\usepackage[ruled]{algorithm2e}
\begin{algorithm}
\caption{算法名}
初始化\;
\While{条件}{
  迭代步骤\;
}
\end{algorithm}
```

## 参考文献

推荐 `biblatex`，从 `.bib` 文件管理引用，`\textcite{}`/`\parencite{}` 引用，`\printbibliography` 输出。

## 实用工具

- [Overleaf](https://www.overleaf.com) — 在线编辑器
- [Detexify](https://detexify.kirelabs.org) — 手绘反查 LaTeX 命令
- [TeX-LaTeX StackExchange](https://tex.stackexchange.com) — 社区问答

> 完整语法手册见源文件 `raw/LaTeX语法大全.md`，覆盖 11 个章节的详尽命令。
