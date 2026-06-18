# MCM 数学建模竞赛 — 多智能体协作系统

## 项目概述

本项目包含一个用于 MCM/ICM 数学建模竞赛的 **4-Agent 链式拦截协作系统**，以及一个结构化的 **竞赛知识库**。

- **智能体系统**：建模手 → 破坏者(audit) → 代码手 → 破坏者(audit) → 论文手 → 破坏者(final audit)
- **知识库**：`MCMKnowledgeBase/` — Obsidian 保险库，含 54+ 概念页、22 实体页、5 年度概览，覆盖 2022–2025 年 CUMCM/MCM 赛题

## 快速开始

### 新赛题启动（推荐）

```
python tools/scaffold.py --problem "2025 MCM Problem A" --year 2025 --letter A
```

自动创建标准化 run 目录、复制赛题文件、初始化 `run_state.json` 和 `problem_data.json` 模板。

### 完整流水线

1. 使用 `scaffold.py` 创建新 run，或手动将赛题保存至 `_workspace/input/problem.txt`
2. 按以下流水线协议依次调用 Agent

### 手动按阶段执行

每阶段独立调用 Agent：

```
Phase 1: 建模手（数学建模设计）
Phase 2: 代码手（算法实现与可视化）
Phase 3: 论文手（论文撰写与总装）
```

每个阶段后由破坏者审计，通过后方可进入下一阶段。

## Agent 调用

项目定义了 4 个专用 Agent（定义文件位于 `.Codex/agents/`）：

| Agent | 文件 | 角色 | 关联技能 | 输出 |
|-------|------|------|---------|------|
| 建模手 | `modeling-expert.md` | 首席建模科学家 | math-modeling-skill | `<model_design>` |
| 代码手 | `coding-expert.md` | 算法工程师 | math-modeling-skill | `<code_repo>` + `<data_vis>` |
| 论文手 | `paper-writer.md` | 学术主编 | humanizer-zh, math-modeling-skill | `<draft_paper>` |
| 破坏者 | `devils-advocate.md` | 独立审计员 | math-modeling-skill | `<devils_advocate_report>` |

调用方式：直接以角色名发起对话，如 "你现在是建模手，分析以下赛题..."，系统会自动加载对应的 Agent 定义和关联技能。

## 流水线协议 (Chain-Intercept Workflow)

### Phase 0: 数据提取（必须在建模前完成）

0. **提取赛题中的硬数据**：在启动建模手之前，必须从赛题 PDF/附件中提取以下信息：
   - 所有给定的数值参数（如 R_s=10m、T_c=20s、v_m=300m/s 等）— **严禁自设或猜测**
   - 所有给定的初始坐标（导弹位置、无人机位置、目标位置）
   - 所有给定的约束条件（速度范围、时间窗口等）
   - 附件数据文件（Excel/CSV 等）的具体内容
   - **若 PDF 无法直接读取文字**：尝试 OCR、读取附件文件、或从知识库中的优秀论文反向提取赛题给定的参数值
   - 将提取的数据保存至 `_workspace/input/problem_data.json`
   - **此步骤缺失将导致全流程数值不可对标（如本 run 中 R_s=50m 自设 vs 实际 10m），破坏者应在 Phase 1 审计中检查参数来源**

### Phase 1: 问题拆解与建模

1. **启动建模手**：提供赛题文本 + `problem_data.json`
2. 建模手检索知识库 → 输出 `<model_design>`（含 problem_analysis, assumptions, symbol_table, mathematical_model, algorithm_flow）
3. 将输出保存至 `_workspace/phase-1-model.xml`
4. **启动破坏者**（audit_target=model）：审计 `<model_design>`，包含假设合理性、数学推导严谨性、量纲一致性
5. 若 `<status>REJECTED</status>`：将 `<correction_directives>` 反馈给建模手修正，返回步骤 1（**单轮建模最多驳回 5 次**）
6. 若 **连续驳回 5 次仍未通过**：当前建模方案存在根本性缺陷，建模手必须 **废弃当前方案，从零重新设计**（全新假设体系、全新数学框架，禁止在原方案上修补迭代）。新方案重新进入 Phase 1，驳回计数器重置
7. 若 `<status>APPROVED</status>`：进入 Phase 2

### Phase 2: 代码实现与结果产出

7. **启动代码手**：提供已批准的 `<model_design>`
8. 代码手检索知识库（算法代码库）→ 严格按 `<mathematical_model>` 中的数学公式编写计算代码 → 输出 `<code_repo>`（含 requirements + python_script）+ `<data_vis>`（含实际计算结果与图表）
9. **核心约束 — 结果真实性（最高优先级）**：
   - 所有数值结果必须由 `<mathematical_model>` 中的公式**实际计算**得出，代码中须能追踪从输入参数→公式计算→输出结果的完整链路
   - **严禁**以下行为：
     - 使用合成数据生成器替代公式计算
     - 直接导入外部预计算结果（如 `np.load('results.npy')`）
     - 任何未经过模型公式计算、无法从代码逻辑中追溯的数据
   - 破坏者对此条的审计为 **零容忍（严禁放行）**：一旦发现任何形式的假数据/假结果，直接 REJECTED，无需进一步审查其他项
10. 将输出保存至 `_workspace/phase-2-code.xml`
11. **启动破坏者**（audit_target=code）：审计代码与可视化，审计焦点：
    - 代码逻辑是否正确实现了 `<algorithm_flow>` 的每个步骤
    - **结果是否由模型公式真实计算**（对照 `<mathematical_model>` 逐项核查计算链路）
    - 可视化是否符合学术规范
12. 若 REJECTED 且原因为**代码错误**（bug、逻辑缺陷、实现偏差）：反馈修正，返回步骤 7（**单轮代码最多修正 3 次**）
13. **建模缺陷检测 — 代码正确但结果异常**：若代码逻辑经审计确认无误，但计算结果与赛题物理/经济常识严重偏离（如量级差 10 倍以上、符号反号、趋势相反），破坏者需判断是否根源于建模设计缺陷：
    - 判断为**建模问题** → 驳回至 Phase 1，建模手重新设计。**单次运行中因建模问题驳回最多 3 次**，超出则 **暂停流水线，等待人工介入**
    - 判断为模型适用范围限制（如参数敏感性导致而非设计错误）→ 在审计报告中标注，不阻塞通过
14. 若 APPROVED：**保存代码、生成的图表和计算结果**至 `_workspace/run-{timestamp}/`，包含：
    - `code/solver.py`（最终版可执行代码）
    - `code/requirements.txt`（完整依赖及版本）
    - `figures/`（全部生成图表，300dpi PNG，按 `fig{序号}_{问题}_{描述}.png` 命名）
    - `results/`（每个子问题独立 CSV 或 XLSX + `results_summary.csv`，含指标名/数值/单位/对应图表/对应公式）
    - 保存完成后进入 Phase 3

### Phase 3: 论文总装

15. **启动论文手**：提供 `<model_design>` + `<code_repo>` + `<data_vis>`
16. 论文手检索知识库（LaTeX 规范、年度概览）→ 应用 humanizer-zh 去 AI 痕迹 → 输出 `<draft_paper>`
17. 论文手重点关注：
    - **公式部分**（已有优势）：继续保持模型推导的严谨完整，公式排版规范
    - **图片插入**（需加强）：每张图必须有编号和完整题注，正文中须有交叉引用（"如图 X 所示"），图表插入位置紧随首次引用段落之后，图表与正文分析**一一对齐**（禁止文中讨论未在图表中呈现的数据，也禁止图表中存在文中未讨论的数据）
    - **文章撰写**（需加强）：段落间逻辑衔接紧凑、避免孤立的单句段落、每节开头有引导句、结果分析必须量化（禁止"效果较好""有一定提升"等模糊表述）、敏感性分析必须覆盖 3+ 维度
18. 将输出保存至 `_workspace/phase-3-paper.md`
19. **启动破坏者**（audit_target=paper）：最终盲审，审计重点：
    - **竞赛合规**：Summary Sheet ≤1页、正文 ≤25页、9节完整结构
    - **跨 Agent 一致性**：论文与 `<model_design>` + `<data_vis>` 逐项比对（假设/公式/数据/算法不得有偏差或凭空新增）
    - **AIGC 双向检测**：AIGC 率须 ≤5%（humanizer-zh 辅助）；同时检测是否因过度降 AIGC 导致语句破碎、逻辑断裂、术语失真（humanizer-zh 反向视角 + nature-skills 基准）
    - 图片-正文对齐、量化表述完整性
20. 若 REJECTED：反馈修正，返回步骤 15（最多重试 3 次）
21. 若 APPROVED：进入 Phase 4 最终打包

### Phase 4: 最终产出打包

> **推荐使用一键打包脚本**：`python tools/package_run.py --run _workspace/run-{timestamp}`
> 自动完成以下全部步骤（论文转换、结果提取、命名检查、完整性验证）。

22. **论文多格式转换**：基于已批准的 `<draft_paper>`，产出三格式论文：
    - **Markdown**（`.md`）：论文手原生输出，UTF-8 编码
    - **DOCX**（`.docx`）：使用 pandoc 转换，指定参考样式：
      ```bash
      pandoc paper.md -o paper.docx --from=markdown --to=docx \
        --main-font="Times New Roman" --fontsize=12 \
        --reference-doc=reference.docx 2>/dev/null || \
      pandoc paper.md -o paper.docx --from=markdown --to=docx
      ```
    - **PDF**（`.pdf`）：优先使用 `pandoc --pdf-engine=weasyprint`；若无可用引擎则标注"待安装 weasyprint 或 LaTeX 后生成"
    - **字体与格式规范**（MCM 标准）：
      - 正文：Times New Roman 12pt，1.5 倍行距
      - 页边距：上下左右 1 英寸（2.54cm）
      - 标题：14pt 加粗居中
      - 章节标题：12pt 加粗
      - 数学公式：变量使用斜体
      - 页码：底部居中
      - 中文论文：正文宋体（SimSun），标题黑体（SimHei）
23. **分题结果整理**：从 `<data_vis>` 和 `<code_repo>` 中提取每个子问题的关键结果，保存为独立表格文件：
    - `results/q1_xxx.csv` 或 `q1_xxx.xlsx` — 问题 1 的结果表（指标名、数值、单位、对应图表）
    - `results/q2_xxx.csv` 或 `q2_xxx.xlsx` — 问题 2 的结果表
    - `results/results_summary.csv` 或 `results_summary.xlsx` — 全题结果汇总表
    - 每张表至少含以下列：`problem_id`, `metric_name`, `value`, `unit`, `method`, `figure_ref`, `formula_ref`
    - XLSX 优先（支持多 Sheet：每个子问题一个 Sheet + 汇总 Sheet），CSV 作为纯文本备选
24. **最终目录结构**：
    ```
    _workspace/run-{timestamp}/
    ├── paper/
    │   ├── paper.md          # Markdown 原生论文
    │   ├── paper.docx        # Word 格式论文
    │   └── paper.pdf         # PDF 格式论文
    ├── figures/
    │   ├── fig01_xxx.png     # 按问题编号命名
    │   ├── fig02_xxx.png
    │   └── ...
    ├── results/
    │   ├── q1_xxx.xlsx       # 各子问题结果 (XLSX 优先)
    │   ├── q1_xxx.csv        # 或 CSV 纯文本备选
    │   ├── q2_xxx.xlsx
    │   └── results_summary.xlsx
    └── code/
        ├── solver.py         # 完整可执行代码
        └── requirements.txt  # 依赖列表
    ```
25. **产出完整性验证**：检查以下清单全部通过后方可标记流水线完成：
    - [ ] `paper/paper.md` 存在且包含全部 9 个标准章节
    - [ ] `paper/paper.docx` 生成成功，字体与格式符合 MCM 规范
    - [ ] `paper/paper.pdf` 生成成功（或已标注缺失引擎）
    - [ ] `figures/` 中每张图对应一个子问题，文件名含序号
    - [ ] `results/` 中每个子问题有独立 XLSX/CSV + 汇总表
    - [ ] `code/solver.py` 可直接 `python solver.py` 运行
    - [ ] `code/requirements.txt` 包含完整依赖及版本

### 状态管理

- `_workspace/audit-log.md` — 追加式审计日志，记录所有审计结论
- `run_state.json` — 每个 run 目录内的运行状态文件，记录当前阶段、驳回计数、已批准阶段
- 每次运行使用 `_workspace/run-{timestamp}/` 隔离

### 断点续跑

支持从中断的阶段恢复执行：

```bash
# 查看当前运行状态
python tools/run_mcm_gates.py --resume --status

# 从当前阶段自动续跑
python tools/run_mcm_gates.py --resume

# 指定 run 续跑
python tools/run_mcm_gates.py --resume-run _workspace/run-20260601-103030
```

## 知识库集成

`MCMKnowledgeBase/` 是一个 Obsidian 知识库，目录约定详见 `MCMKnowledgeBase/AGENTS.md`。

### 检索协议（所有 Agent 必须遵循）

1. **入口**：先读 `MCMKnowledgeBase/wiki/INDEX.md` 定位相关页面
2. **赛题检索**：若已知年份/题号，直接读 `wiki/entities/{year}-{letter}-{slug}.md`
3. **算法检索**：读 `wiki/concepts/{algorithm-name}.md` 获取方法与参考实现
4. **年度上下文**：读 `wiki/overviews/{year}-mcm-competition.md` 了解同届整体风格与难度
5. **交叉引用**：Wiki 页面使用 `[[wiki-links]]`，按链接遍历相关内容
6. **源码**：`raw/` 目录含赛题 PDF、附件、优秀论文 OCR（只读，不修改）

### 关键知识页面速查

| 类型 | 页面 | 内容 |
|------|------|------|
| 概念 | `algorithm-codebase.md` | 30 个常用算法的 Python 参考实现 |
| 概念 | `latex-reference.md` | LaTeX 排版规范与数学公式参考 |
| 概念 | `multi-agent-collaboration.md` | 多智能体协作系统架构 |
| 概念 | `chain-intercept-workflow.md` | 链式拦截工作流协议 |
| 概念 | `agent-role-specialization.md` | 各 Agent 角色边界与职责 |
| 实体 | `andrej-karpathy.md` | Karpathy 工程哲学（分解-验证-组装） |
| 概念 | `error-taxonomy.md` | 14 类标准漏洞分类体系与自检清单 |
| 概念 | `continuous-improvement-loop.md` | 审计→分类→经验→前置注入的四步闭环 |

## 工作区约定

```
_workspace/
├── input/                  # 赛题输入
│   └── problem.txt
├── phase-1-model.xml       # 建模手输出
├── phase-2-code.xml        # 代码手输出
├── phase-3-paper.md        # 论文手输出
├── audit-log.md            # 审计日志
├── error-registry.json     # 错误记录数据库
├── quality-gate-log.md     # 质量门禁日志
├── reference.docx          # DOCX 参考样式模板（可选）
└── run-{timestamp}/        # 单次运行最终产出
    ├── run_state.json      # 运行状态与驳回计数
    ├── input/              # 赛题副本
    ├── phase-1-modeling/   # 建模阶段产物
    ├── phase-2-coding/     # 编码阶段产物
    ├── phase-3-paper/      # 论文阶段产物
    ├── paper/
    │   ├── paper.md        # Markdown 论文
    │   ├── paper.docx      # Word 论文
    │   └── paper.pdf       # PDF 论文
    ├── figures/
    │   └── fig*.png        # 按问题编号命名的图表
    ├── results/
    │   ├── q1_*.xlsx        # 各子问题结果 (XLSX 优先，多 Sheet)
    │   ├── q1_*.csv         # CSV 备选
    │   └── results_summary.xlsx
    └── code/
        ├── solver.py       # 可执行代码
        └── requirements.txt
```

## 重试与错误处理

- **Phase 1 建模修正**：单轮建模最多驳回 5 次；连续 5 次驳回后建模手必须从零重新设计（废弃原方案，全新假设与数学框架）
- **Phase 2 代码修正**：代码 bug 类修正最多 3 次
- **建模反馈环**：代码正确但结果异常时，破坏者判断若为建模缺陷 → 驳回建模重新设计，最多 3 次；超出则暂停流水线，等待人工介入
- **Phase 3 论文修正**：最多重试 3 次
- **结果真实性零容忍**：一旦发现假数据/合成数据/未经模型公式计算的结果，破坏者直接 REJECTED，不可协商，不计入常规修正次数
- **XML 完整性检查**：Agent 输出前自检所有必需标签是否存在且格式正确
- **知识库不可用**：若 KB 无法访问，Agent 应基于通用数学建模规范继续，并在输出中注明信息缺口

## 持续改进协议 (Continuous Improvement Loop)

系统通过 `[[error-taxonomy]]` 和 `[[continuous-improvement-loop]]` 两个概念页定义的机制，实现跨运行的自我进化。

### 错误记录

每次破坏者审计完成后，按 `[[error-taxonomy|14 类标准分类]]` 将漏洞追加写入 `_workspace/error-registry.json`。每条记录含：run_id、timestamp、phase、risk_level、category、description、agent、revision_count。修正完成后补充 `correction` 字段并标记 `resolved: true`。

### 前置经验注入

每个 Agent 启动时，Knowledge Retrieval 的**第 0 步**（最高优先级）：读取 `_workspace/error-registry.json` 中本阶段（phase=modeling/coding/paper）且 resolved=true 的历史错误，对照 `MCMKnowledgeBase/wiki/concepts/error-taxonomy.md` 中对应分类，逐条自检。若主动避免了某类已知错误，在输出中注明。

### 模式分析

当 `total_runs >= 5` 时（或由人工触发），统计高频错误分类 → 识别系统级薄弱点 → 输出改进建议至 `_workspace/error-insights.md`。根据建议决定是否修订 Agent 定义文件或调整工作流。

## 可用技能

- `math-modeling-skill` — 通用数学建模方法论
- `humanizer-zh` — 学术中文去 AI 痕迹润色

## 建模与代码阶段优化补丁

后续 Phase 1/Phase 2 必须同时遵循 `docs/MODEL_CODE_OPTIMIZATION.md`。核心新增要求：

- 建模输出必须包含参数来源映射、可行性预检、基线与单调性不变量、实现契约、验证计划和复杂度预算。
- 代码输出必须保留从 `problem_data.json` 到公式实现再到结果表的可追踪链路，优化结果必须通过基线回归检查。
- Phase 1 后运行：`python tools/run_mcm_gates.py --phase modeling`
- Phase 2 后运行：`python tools/run_mcm_gates.py --phase coding --run _workspace/run-{timestamp}`
- `tools/run_mcm_gates.py` 默认严格模式，并追加 `_workspace/quality-gate-log.md`；探索阶段可加 `--non-strict`。
- 正式进入破坏者审计前，任何 ERROR 或 WARN 均需解释或修正。

## 工具链

| 工具 | 用途 | 示例 |
|------|------|------|
| `tools/scaffold.py` | 新赛题启动脚手架 | `python tools/scaffold.py --problem "2025 MCM Problem A" --year 2025 --letter A` |
| `tools/run_mcm_gates.py` | 质量门禁 + 断点续跑 | `python tools/run_mcm_gates.py --phase modeling --resume` |
| `tools/package_run.py` | Phase 4 一键打包 | `python tools/package_run.py --run _workspace/run-{timestamp}` |

### scaffold.py 参数

| 参数 | 说明 |
|------|------|
| `--problem` | 赛题描述，如 `"2025 MCM Problem A"` |
| `--year` | 赛题年份 |
| `--letter` | 赛题字母 (A/B/C/D/E) |
| `--competition` | 竞赛类型: `mcm` (默认) 或 `cumcm` |
| `--list` | 列出知识库中可用的赛题 |

### run_mcm_gates.py 断点续跑参数

| 参数 | 说明 |
|------|------|
| `--resume` | 自动检测最新 run 并从当前阶段续跑 |
| `--resume-run PATH` | 指定 run 续跑 |
| `--status` | 查看 run_state.json 状态（需配合 `--resume` 或 `--resume-run`） |

### package_run.py 参数

| 参数 | 说明 |
|------|------|
| `--run PATH` | Run 目录路径（必填） |
| `--skip-pdf` | 跳过 PDF 生成 |
| `--skip-docx` | 跳过 DOCX 生成 |
| `--check-only` | 仅运行完整性检查，不生成文件 |
