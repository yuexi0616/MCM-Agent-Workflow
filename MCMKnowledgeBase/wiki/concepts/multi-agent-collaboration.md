---
title: "Multi-Agent Collaboration"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[agent-role-specialization]]", "[[chain-intercept-workflow]]", "[[human-llm-collaboration]]", "[[math-modeling-skill]]"]
tags: ["multi-agent", "collaboration", "workflow", "mcm"]
last_compiled: 2026-05-29
---

# Multi-Agent Collaboration

多智能体协作是将复杂任务拆解为专业化子任务、由多个独立 Agent 按协议接力完成的模式。在 MCM/ICM 场景中，该模式将一支人类建模团队的分工——建模、编程、写作、审核——映射为四个独立 LLM Agent 角色的链式协作。

## 核心设计原则

每个 Agent 只承担单一职责，通过结构化输出协议（XML 标签）交接工作产物。这种设计的优势在于：(1) 每个 Agent 的 system prompt 可以极度精简、专注；(2) 中间产物可审计、可追溯；(3) 任一环节出错时可精确定位责任 Agent 而非全文返工。

## 四角色体系

系统由四个 Agent 组成闭环：[[agent-role-specialization|建模手]]负责数学推导与算法设计；[[agent-role-specialization|代码手]]负责将模型无损转化为可运行代码与可视化；[[agent-role-specialization|论文手]]负责整合前置产物为完整学术论文；[[agent-role-specialization|破坏者]]作为独立审计员在每一阶段进行拦截审查。破坏者的引入是该系统的关键创新——模拟了同行评审中"魔鬼代言人"的角色。

## 与现有技能体系的关系

该工作流主动集成本项目已有的三个技能体系：建模手调用 `math-modeling-skill` 的算法库与最佳实践；代码手与论文手遵循 `nature-skills` 的可视化与排版规范；论文手输出经 `humanizer-zh` 去 AI 化润色。这形成了从知识检索 → 模型构建 → 代码落地 → 学术产出的完整闭环。

## Karpathy 优化哲学

文档标注为"Karpathy-Optimized"，指向 [[andrej-karpathy|Andrej Karpathy]] 所倡导的 LLM 工作流设计理念：将复杂任务拆分为可验证的原子步骤，每步有明确的输入/输出契约，通过结构化标签而非自然语言传递状态。
