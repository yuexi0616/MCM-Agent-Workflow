# MCM 数学建模竞赛 — 多智能体协作系统

一套面向 MCM/ICM 数学建模竞赛的 **4-Agent 链式拦截协作系统**，实现从问题分析、数学建模、算法实现到论文撰写的全流程自动化。

## 项目亮点

- **链式拦截工作流**：建模手 → 破坏者(audit) → 代码手 → 破坏者(audit) → 论文手 → 破坏者(final audit)
- **结果真实性保障**：所有数值结果必须由数学模型公式实际计算，零容忍假数据
- **结构化知识库**：54+ 概念页、22 实体页、覆盖 2022-2025 年 CUMCM/MCM 赛题
- **持续改进闭环**：14 类错误分类体系，跨运行自我进化
- **断点续跑支持**：可从中断阶段恢复执行

## 系统架构

### 4 个专用 Agent

| Agent | 角色 | 职责 |
|-------|------|------|
| 建模手 | 首席建模科学家 | 问题拆解、假设建立、数学模型设计 |
| 代码手 | 算法工程师 | 模型实现、数值计算、可视化 |
| 论文手 | 学术主编 | 论文撰写、格式规范、去 AI 痕迹 |
| 破坏者 | 独立审计员 | 跨阶段审计、漏洞检测、质量把关 |

### 流水线协议

```
Phase 0: 数据提取（赛题参数提取）
    ↓
Phase 1: 建模设计 → 破坏者审计
    ↓
Phase 2: 代码实现 → 破坏者审计
    ↓
Phase 3: 论文总装 → 破坏者审计
    ↓
Phase 4: 最终打包（MD/DOCX/PDF + 图表 + 结果表）
```

## 快速开始

### 新赛题启动

```bash
python tools/scaffold.py --problem "2025 MCM Problem A" --year 2025 --letter A
```

### 断点续跑

```bash
# 查看当前状态
python tools/run_mcm_gates.py --resume --status

# 从中断阶段续跑
python tools/run_mcm_gates.py --resume
```

### 一键打包

```bash
python tools/package_run.py --run _workspace/run-{timestamp}
```

## 目录结构

```
MCM/
├── .claude/agents/          # Agent 定义文件
│   ├── modeling-expert.md
│   ├── coding-expert.md
│   ├── paper-writer.md
│   └── devils-advocate.md
├── MCMKnowledgeBase/        # Obsidian 知识库
│   ├── wiki/                # 概念页、实体页、年度概览
│   └ raw/                   # 赛题 PDF、附件、优秀论文 OCR
│   └── 30个常用模型对应的Python代码/
├── tools/                   # 工具脚本
│   ├── scaffold.py          # 新赛题脚手架
│   ├── run_mcm_gates.py     # 质量门禁 + 断点续跑
│   └── package_run.py       # 一键打包
├── _workspace/              # 运行工作区
│   ├── input/               # 赛题输入
│   ├── phase-1-model.xml    # 建模输出
│   ├── phase-2-code.xml     # 代码输出
│   ├── phase-3-paper.md     # 论文输出
│   └── run-{timestamp}/     # 最终产出
└── docs/                    # 文档
```

## 知识库

`MCMKnowledgeBase/` 是一个 Obsidian 知识库，包含：

- **54+ 概念页**：算法代码库、LaTeX 规范、错误分类体系等
- **22 实体页**：优秀论文、赛题实体、建模专家等
- **5 年度概览**：2022-2025 年 CUMCM/MCM 赛题风格与难度分析

### 检索协议

1. 入口：`MCMKnowledgeBase/wiki/INDEX.md`
2. 赛题检索：`wiki/entities/{year}-{letter}-{slug}.md`
3. 算法检索：`wiki/concepts/{algorithm-name}.md`

## 质量保障机制

### 破坏者审计

每个阶段完成后，破坏者进行独立审计：

- **Phase 1**：假设合理性、数学推导严谨性、量纲一致性
- **Phase 2**：代码逻辑正确性、结果真实性（零容忍）、可视化规范
- **Phase 3**：竞赛合规、跨 Agent 一致性、AIGC 检测

### 重试与错误处理

- 建模修正：最多驳回 5 次，连续 5 次后从零重新设计
- 代码修正：最多 3 次
- 建模反馈环：代码正确但结果异常时，可驳回建模重新设计（最多 3 次）

### 持续改进

每次审计完成后，错误按 14 类标准分类写入 `error-registry.json`，Agent 启动时前置自检，实现跨运行自我进化。

## 技术栈

- Python 3.x
- Obsidian（知识库管理）
- Pandoc（论文格式转换）
- Matplotlib（可视化）

## 许可证

MIT License

## 参考

- [MCM/ICM 官网](https://www.mcm-icm.org/)
- [CUMCM 官网](http://www.cumcm.org.cn/)