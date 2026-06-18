---
title: "Continuous Improvement Loop"
sources: ["raw/MCM-Agent-Workflow-Master.md"]
related: ["[[error-taxonomy]]", "[[multi-agent-collaboration]]", "[[chain-intercept-workflow]]", "[[agent-role-specialization]]"]
tags: ["improvement", "learning", "error", "workflow", "mcm"]
last_compiled: 2026-05-30
---

# Continuous Improvement Loop

持续改进环是嵌入 MCM 多智能体流水线的自优化机制。核心理念：每一次破坏者审计发现的漏洞，不仅用于修正本轮流水线输出，还作为"经验"持久化存入 `_workspace/error-registry.json`，在后续（可能跨赛题、跨月份）的流水线运行中作为前置知识注入到对应 Agent，防止同类错误反复出现。

## 四步闭环

```
审计发现漏洞 → 错误分类记录 → 经验知识库累积 → 前置注入 Agent → 减少同类错误
```

1. **错误记录**：破坏者审计完成后，按 [[error-taxonomy]] 分类体系将每条漏洞追加写入 `_workspace/error-registry.json`。每条记录含运行 ID、时间戳、阶段、风险等级、分类 tag、描述、所属 Agent、修订次数。修正完成后补充 `correction` 字段并标记 `resolved: true`。

2. **经验提取**：每次新流水线启动前，各 Agent 按自身所属阶段（建模/编码/论文）从 error-registry 中提取已解决（resolved=true）的历史错误列表。聚焦本阶段直接相关的 4-5 类错误分类。

3. **前置注入**：各 Agent 在 Knowledge Retrieval 的第一步（优先级最高）读取匹配的历史错误，将其中高频或 High-risk 的错误模式纳入本次自检清单。Agent 在输出中应主动注明是否已避免了已知错误类型。

4. **模式分析**：当 error-registry 中 `total_runs >= 5` 时（或由人工触发），统计高频错误分类和易错阶段，识别系统级薄弱点，输出改进建议至 `_workspace/error-insights.md`。根据建议决定是否修订 Agent 定义文件或调整工作流协议。

## 与 Karpathy 工程哲学的关系

该设计遵循 [[andrej-karpathy|Karpathy]] 的"分解-验证-组装"工程哲学：

- **分解**：将每次运行的审计发现分解为原子化的错误实例（id + category + risk_level + description）
- **验证**：通过 [[error-taxonomy|14 类标准分类]]进行结构化标记和跨运行聚类，验证哪些错误类型是系统性的而非偶然的
- **组装**：将规律性发现（高频错误分类、易错阶段）组装为 Agent 定义文件的修订建议或 Self-Check 清单的增补项

## 与 Wiki 的协同

持续改进环与知识库的 ingest/query/lint 操作共享"先建设、后审查"的双阶段哲学。错误分类法本身是一个可演化的分类体系——随着流水线运行次数增加，新的错误模式可能被发现并添加到分类体系中，此时通过 wiki ingest 流程更新 `error-taxonomy.md`。

## 4-Agent 工作流中的运作全景图

持续改进闭环通过以下机制无缝融入三阶段流水线：

| 阶段 | 破坏者 Agent | 知识库 Agent |
|------|-----------|-----------|
| **模型设计** | 审查建模阶段错误，分类记录 | 注入历史建模错误经验 |
| **代码实现** | 审查编码阶段错误，分类记录 | 注入历史编码错误经验 |
| **论文撰写** | 审查论文阶段错误，分类记录 | 注入历史论文错误经验 |

每个 Agent 的 Knowledge Retrieval Protocol 第 0 步（最高优先级）即为历史经验检查，确保经验注入在知识检索之前完成，使后续检索方向也能受历史经验的引导。
