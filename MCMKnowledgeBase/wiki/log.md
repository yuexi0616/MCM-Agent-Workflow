# Wiki Log

## [2026-05-29] ingest | MCM Agent Workflow Master
- New pages (concepts): [[multi-agent-collaboration]], [[chain-intercept-workflow]], [[agent-role-specialization]]
- New pages (entities): [[andrej-karpathy]]
- Updated: [[human-llm-collaboration]]（新增 Multi-Agent 扩展段落）, [[wiki-operations]]（新增 chain-intercept 对照段落）, INDEX.md（+3 概念，+1 实体）
- Notes:
  - 源文件定义了一套 4-Agent 协作系统（建模手→代码手→论文手，破坏者全程拦截审计）
  - 核心创新：XML 标签通信协议 + 破坏者的独立审计角色
  - 与现有技能体系深度集成：math-modeling-skill + nature-skills + humanizer-zh
  - 工作流与 Wiki ingest/lint 操作共享"先建设、后审查"的双阶段哲学

## [2026-05-27] ingest | 2025 MCM 竞赛全题与优秀论文
- New pages (entities): [[2025-a-smoke-screen]], [[2025-b-sic-thickness]], [[2025-c-nipt]], [[2025-d-mine-flood]], [[2025-e-long-jump]]
- New pages (concepts): [[line-sphere-occlusion]], [[hierarchical-optimization]], [[differential-evolution]], [[optical-interference-model]], [[spectral-data-preprocessing]], [[cauchy-dispersion]], [[linear-mixed-effects]], [[gaussian-process-regression]], [[survival-analysis]], [[stacking-ensemble]], [[genetic-algorithm]], [[graph-flow-model]], [[dynamic-dijkstra]], [[bfs-graph-search]]
- New pages (overviews): [[2025-mcm-competition]]
- Updated: INDEX.md (full update with all new pages)
- Notes:
  - Raw directory restructured to raw/2025/{A,B,C,D,E}/ for year-based hierarchy
  - A题优秀论文：几何建模 + 多起点变步长搜索 + 差分进化 + 分层次优化
  - B题优秀论文：双光束干涉 + Cauchy色散 + AsLS预处理 + 滑窗FFT + SG梯度下降
  - C题优秀论文：LMM + GPR+GA两阶段 + DeepHit生存网络 + LightGBM堆叠集成
  - D题优秀论文：水流漫延三类子模型 + BFS + 实时动态Dijkstra
  - E题暂未收录优秀论文，已创建占位页待后续补充
  - 横向观察：优秀论文共同特征为符号表统一、多算法交叉验证、敏感度分析、结果输出到附件

## [2026-05-29] ingest | 30个常用模型 Python 代码库
- New pages (concepts): [[algorithm-codebase]]
- Updated: INDEX.md
- Notes: 代码来源：raw/30个常用模型对应的Python代码/。30个算法按五大类组织：优化(10)、预测(4)、分类(8)、评价(4)、统计模拟(4)。格式混合(.txt/.docx/.py/.rar)。wiki页面为全索引，将每个算法映射到已有概念页和相关赛题。

## [2026-05-29] ingest | LaTeX 语法大全
- New pages (concepts): [[latex-reference]]
- Updated: INDEX.md
- Notes: 全文 11 章节涵盖基础入门、文档结构、文本排版、表格、图片、数学公式、宏包、参考文献、长文档处理、错误调试、符号速查表。wiki 页面提取了 MCM 论文最常用的部分作为速查。
- Updated entities: [[2024-a-bench-dragon]], [[2024-b-production-decision]], [[2024-c-crop-strategy]], [[2024-d-depth-charge]], [[2024-e-traffic-control]]（补充 16 篇论文方法）
- New pages (concepts): [[cvar-optimization]], [[bayesian-estimation]], [[dynamic-programming]], [[sat-collision-detection]], [[webster-signal-timing]], [[reinforcement-learning-model]], [[hypothesis-testing-sampling]]
- Updated: [[2024-mcm-competition]]（补充各题论文方法摘要）、INDEX.md（+7 概念条目，更新 5 实体摘要）
- Notes:
  - 论文来源：raw/2024/{A-E}/（16 篇完整 markdown）
  - A（5篇）：逐步逼近法、分离轴定理(SAT)碰撞检测、反证法首次碰撞证明、PSO优化龙头速度
  - B（3篇）：假设检验+(n,c)抽样法、状态-决策DP、贝叶斯Beta-Binomial、线性模拟退火
  - C（4篇）：DEGA+CVaR风险优化、LINGO精确求解、Spearman相关性、风险决策模型
  - D（1篇）：五情形讨论+三重积分、最优落点"看哪打哪"、阵列最优排布
  - E（3篇）：K-means/DBSCAN/GMM聚类、XGBoost+Webster+GA、DQN+MDP、泊松停车需求
  - 2024 年论文的方法丰富度和创新度显著高于 2022/2023 年

## [2026-05-29] ingest | 2024~2022 年赛题与优秀论文
- New pages (entities): [[2024-a-bench-dragon]], [[2024-b-production-decision]], [[2024-c-crop-strategy]], [[2024-d-depth-charge]], [[2024-e-traffic-control]], [[2023-a-heliostat-field]], [[2023-b-multibeam-survey]], [[2023-c-vegetable-pricing]], [[2023-d-sheep-breeding]], [[2023-e-yellow-river-sediment]], [[2022-a-wave-energy]], [[2022-b-drone-formation]], [[2022-c-glass-analysis]], [[2022-d-satellite-comm]], [[2022-e-material-production]]
- New pages (concepts): [[runge-kutta-method]], [[wave-energy-dynamics]], [[bearing-only-localization]], [[heuristic-search]], [[archimedean-spiral-model]], [[heliostat-optical-efficiency]], [[multibeam-coverage-model]], [[production-scheduling]], [[monte-carlo-simulation]], [[greedy-algorithm]], [[hit-probability-integration]], [[collision-detection-model]]
- New pages (overviews): [[2024-mcm-competition]], [[2023-mcm-competition]], [[2022-mcm-competition]]
- Updated: INDEX.md (15 entities, 12 concepts, 3 overviews)
- Notes:
  - 题目来源：2024赛题/、2023赛题/、CUMCM2022Problems/
  - 优秀论文 OCR 来源：raw/2022/{A-E}/（11篇）、raw/2023/{A-D}/（10篇）
  - 2022 A: 波浪能动力学+RK4+GA；B: 纯方位定位+带阈值启发式搜索+计算几何
  - 2023 A: 定日镜五因子光学效率链+分区域同心圆规划；B: 多波束三维几何+贪心+模拟退火；D: 周期调度+蒙特卡洛
  - 2024 A: 螺线运动学+碰撞检测；B: 抽样检测+决策树；D: 多元积分+阵列优化
  - 2024 年暂无优秀论文 OCR 文件录入
  - 2023 C/E 暂无优秀论文 OCR
  - 2022 C/D/E 无需全文提取（文件过长或暂无摘要）

## [2026-05-30] ingest | Error Taxonomy & Continuous Improvement Loop
- New pages (concepts): [[error-taxonomy]], [[continuous-improvement-loop]]
- Updated: INDEX.md（+2 概念条目）
- Notes:
  - 错误分类法覆盖 14 类标准错误，按三阶段（建模 5 / 编码 4 / 论文 4）+ 通用（1）分组
  - 持续改进环形成"审计→记录→经验→前置注入→减少错误"的完整闭环
  - 分类体系来源：MCM 评审标准 + 历年优秀论文特征 + Agent 角色边界
  - 与 [[agent-role-specialization|Agent 角色定义]]、[[chain-intercept-workflow|链式拦截工作流]]、[[andrej-karpathy|Karpathy 工程哲学]]深度集成
  - 运行时数据库：`_workspace/error-registry.json`（空初始化，随流水线运行累积）

## [2026-05-27] init | Wiki bootstrapped from LLM Wiki idea document
- New pages: [[llm-wiki]], [[knowledge-compilation]], [[three-layer-architecture]], [[wiki-operations]], [[wiki-indexing]], [[human-llm-collaboration]], [[obsidian-integration]], [[wiki-links]], [[schema]], [[rag-vs-compilation]], [[cli-tools]], [[memex]]
- Overviews: [[use-cases]]
- Created CLAUDE.md schema with compiler rules, frontmatter conventions, and operational workflows
- Directory structure initialized: raw/, wiki/concepts/, wiki/entities/, wiki/overviews/
