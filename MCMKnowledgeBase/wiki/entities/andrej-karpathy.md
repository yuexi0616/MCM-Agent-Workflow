---
title: "Andrej Karpathy"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[multi-agent-collaboration]]", "[[chain-intercept-workflow]]", "[[llm-wiki]]"]
tags: ["person", "ai", "llm", "workflow-design"]
last_compiled: 2026-05-29
---

# Andrej Karpathy

Andrej Karpathy，前 Tesla AI 高级总监、OpenAI 创始团队成员，现任 Eureka Labs 创始人。在 LLM 工作流设计领域，Karpathy 倡导将复杂任务拆分为可验证的原子步骤，每步有明确的输入/输出契约——这一哲学被称为"Karpathy 风格"或"Karpathy-Optimized"工作流。

## 与 MCM 多智能体系统的关联

MCM-Agent-Workflow-Master 文档标注为"Karpathy-Optimized"，体现了其核心设计理念：(1) 链式生成而非一次性输出；(2) 每步产物通过结构化标签（XML）交接而非自然语言；(3) 独立审计节点拦截问题而非依赖最终人工审查。这些原则与 Karpathy 在 LLM 应用架构中反复强调的"分解、验证、组装"模式高度一致。
