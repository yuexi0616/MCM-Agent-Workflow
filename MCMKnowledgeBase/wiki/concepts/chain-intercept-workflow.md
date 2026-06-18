---
title: "Chain-Intercept Workflow"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[multi-agent-collaboration]]", "[[agent-role-specialization]]", "[[wiki-operations]]", "[[schema]]"]
tags: ["workflow", "protocol", "audit", "xml"]
last_compiled: 2026-05-29
---

# Chain-Intercept Workflow

链式生成 + 拦截审计（Chain-Intercept）是一种多阶段工作流协议：上游 Agent 产出结构化结果，经独立审计 Agent 审查后方可传递给下游 Agent。该模式将质量控制从最终环节前置到每一个交接节点。

## 三阶段流水线

1. **问题拆解阶段**：赛题输入 → 建模手输出 `<model_design>` → 破坏者审查 → 修正后放行
2. **代码实现阶段**：`<model_design>` 输入 → 代码手输出 `<code_repo>` 与 `<data_vis>` → 破坏者审查 → 修正后放行
3. **论文总装阶段**：整合所有前置标签 → 论文手输出 `<draft_paper>` → 破坏者最终盲审

## XML 标签通信协议

各 Agent 之间不通过自由文本交接，而使用预定义的 XML 标签结构。上游 Agent 必须将产出封装在指定标签内，下游 Agent 必须提取对应标签内容作为输入。关键标签：

- `<model_design>` 包含问题分析、假设、符号表、数学模型、算法流程
- `<code_repo>` 包含依赖列表、完整 Python 代码
- `<data_vis>` 包含图表描述（文字描述而非实际图片）
- `<draft_paper>` 完整 Markdown 学术论文
- `<devils_advocate_report>` 包含漏洞列表、修正指令、APPROVED/REJECTED 状态

## 审计的独立性

破坏者的零信任原则是其核心价值：不提供修改文本，只抛出尖锐问题和驳回理由。这避免了"审查者被同化为共同作者"的滑坡效应。每次审计必须明确目标对象（模型/代码/论文），按严重等级标注漏洞，并给出明确的 APPROVED 或 REJECTED 裁决。

## 与 Wiki Ingest/Lint 的对照

该工作流与 [[wiki-operations|Wiki 的 ingest/lint 操作]] 共享同一哲学：ingest 相当于链式生成（读取→提取→写入），lint 相当于拦截审计（扫描矛盾→标记问题→要求修正）。两者都是"先建设、后审查"的双阶段模式。
