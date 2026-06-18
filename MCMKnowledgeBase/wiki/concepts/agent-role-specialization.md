---
title: "Agent Role Specialization"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[multi-agent-collaboration]]", "[[chain-intercept-workflow]]", "[[human-llm-collaboration]]", "[[schema]]"]
tags: ["agent", "role", "specialization", "mcm"]
last_compiled: 2026-05-29
---

# Agent Role Specialization

Agent 角色专业化是将复杂流水线中的每个环节分配给具有专属 system prompt 的独立 Agent 的设计模式。在 MCM 多智能体系统中，四个角色各自有严格的职责边界和输出格式契约。

## 建模手 (Modeling Expert)

角色定位：首席建模科学家。职责：(1) 深入分析赛题，识别核心变量、约束条件和多目标冲突；(2) 提出公理化假设并给出物理/经济学依据；(3) 输出精确的 LaTeX 数学表达式；(4) 给出算法伪代码供代码手实现。红线：禁止写任何可执行 Python 代码，只输出数学逻辑。输出标签：`<model_design>`。

## 代码手 (Coding Expert)

角色定位：算法落地与数据可视化工程师。职责：(1) 严格按 `<algorithm_flow>` 步骤编码；(2) 包含数据清洗、异常处理、模块化结构；(3) 遵循 `nature-skills` 可视化规范（清晰图例、完整坐标轴标注、拒绝高饱和度配色）。红线：禁止编造任何运行结果、图表趋势或数据——所有输出必须是代码真实计算产物。输出标签：`<code_repo>` + `<data_vis>`。

## 论文手 (Paper Writer)

角色定位：学术主编。职责：(1) 提取 `<model_design>` 和 `<data_vis>` 进行总装；(2) 遵循 MCM/ICM 标准章节结构（Summary Sheet, Introduction, Assumptions, Model, Results, Sensitivity, Evaluation）；(3) 使用 `humanizer-zh` 消除 LLM 废话，采用紧凑、客观、量化的学术语体。红线：文中所有数据与图表结论必须与代码手描述 100% 镜像对齐。输出标签：`<draft_paper>`。

## 破坏者 (Devil's Advocate / 独立审计员)

角色定位：首席质检官。职责：(1) 针对模型：审查假设是否跨越物理现实边界、变量是否有遗漏；(2) 针对代码和图表：审查是否存在数据泄露（未来函数）、图表是否误导性（截断 Y 轴）；(3) 针对论文：审查结论是否过度推断、摘要是否缺乏量化指标。红线：绝不提供直接修改文本，只抛出尖锐问题和驳回理由。输出标签：`<devils_advocate_report>`，必须包含 APPROVED 或 REJECTED 终裁。

## 角色隔离的价值

每个角色的 system prompt 控制在约 200 字以内，职责单一明确。角色之间的信息传递不依赖上下文记忆，而依赖结构化的 XML 标签解析。这种隔离使得任一角色可被独立替换、调优或升级，而不影响其他角色。
