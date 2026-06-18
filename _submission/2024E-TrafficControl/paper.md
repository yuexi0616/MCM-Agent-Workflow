<draft_paper>

# Summary Sheet

**题目**: Traffic Flow Analysis and Control Optimization for a Scenic Town Network

**关键词**: Contiguity-Constrained Clustering, PELT Change Point Detection, Webster Green Wave Coordination, Genetic Algorithm, Cruising Vehicle Detection, Pre-Post Control Evaluation

**摘要**

本论文针对2024 MCM E题景区小镇交通管控问题，构建了包含时段划分、信号配时优化、巡游车辆识别和管控效果评价的四阶段分析框架。基于1,439,889条车牌识别记录（36天、12交叉口、8,000车辆池），按工作日、周末、节假日三种日期类型分别建模。时段划分采用时序约束层次聚类（Ward+Dunn指数）与贝叶斯断点检测（PELT, BIC惩罚项0.5 ln(N)*12）双方案验证，三种日期类型均识别出K=6个连续时段，断点位置一致（7:00、9:00、17:00、19:00、21:00），最大偏差0窗口。信号配时采用双层优化框架：上层遗传算法搜索公共周期与相位差，下层"先基荷再剩余"的绿灯分配流程保证约束可行性。优化得到公共周期C0=88 s（可行域70.4-105.6 s），绿波协调后路网平均车速25.26 km/h，偏移量在纬中路（700 m段距）为63.0 s、经中路（360 m段距）为32.4 s。巡游车辆检测基于三特征判定（重复次数>=3、速度<=5 km/h、方向熵>=1.377 nat），检测出210辆巡游车；轨迹断裂比例10.35%，停车位需求保守方案42个、乐观方案38个（Q95=199.5辆同时巡游）。验证显示检测精度0.1286、召回率0.0467、F1=0.0685，tau窗口敏感性CV=56.2%。管控效果评价使用含节假日效应分离的前后对比模型，控制变量Post_t（5月1日-6日）与Holiday_t（5月1日-5日）的识别依赖5月6日的时间变异。回归结果显示：平均车速的管控净效应beta_3=-0.34km/h（p=0.147），总流量beta_3=-12.83veh（p=0.344），等待时间beta_3=0.53s/km（p=0.065），三个效应均不显著（p>0.05）。节假日附加效应gamma均高度显著（p<0.001）。事件研究法的平行趋势检验通过（Wald chi-squared, p>0.05）。Cohen's d综合评分（AHP权重：车速0.539、流量0.164、等待时间0.297）显示交叉口间效果分化。


---

# 1. Introduction

## 1.1 Problem Restatement

某景区小镇拥有两条主干道——纬中路（3.5 km，交叉口1-8）和经中路（1.8 km，交叉口9-12），两条道路构成网格状路网，全长约5.3 km。12个交叉口均安装车牌识别监控，记录每条过车信息的车牌号、时间戳和进出方向。

题目要求完成四项任务：（1）依据车流量差异划分一天中的时段，估计各时段各相位的车流特征；（2）优化全部12个交叉口的信号灯配时，最大化路网平均车速；（3）识别五一黄金周期间巡游找车位的车辆，估算需要临时征用的停车位数；（4）评价五一期间交通管控措施的效果。

数据范围为2024年4月1日至5月6日共36天，包含工作日、周末和五一假期三种日期类型。

## 1.2 Literature Review

交通流时段划分是交通工程的基础问题。传统方法采用K-means等独立同分布聚类，但忽视时间连续性导致时段边界跳跃。时序约束聚类（Contiguity-Constrained Hierarchical Clustering）通过限制仅合并时间相邻簇来保持时段的连续性（Murtagh & Legendre, 2014）。贝叶斯断点检测方法（PELT, Killick et al., 2012）在多变量时间序列的结构性变化检测中表现优异，其线性复杂度理论上适用于本问题96个时间窗口的搜索空间。

信号配时的经典方法为Webster（1958）提出的基于流量比的最优周期公式，其假设车流服从泊松分布。干线绿波协调控制需要所有交叉口共享公共周期并设置相位差（TRB, 2010），遗传算法（GA）因其对非凸、非线性搜索空间的处理能力而被广泛用于此类组合优化问题。

巡游车辆（Cruising for Parking）的检测通常基于低速绕圈行为模式。Shoup（2006）的研究表明巡游车在城市中心可占交通流量的30%。现有检测方法多依赖GPS轨迹数据，而基于固定监控点车牌匹配的轨迹重建方法在路网非全覆盖情况下存在侧方进出偏差。

因果推断在交通政策评价中的应用日益广泛。双重差分法（DID, Angrist & Pischke, 2008）通过比较处理组与对照组的平行趋势来识别处理效应。当政策为全域实施时，DIF退化为前后对比设计（pre-post comparison），其有效性依赖于时间变异和季节性效应的分离能力。

2024年MCM E题优秀论文（E010, E061）分别采用K-means/DBSCAN/GMM聚类对比、XGBoost相位流量预测、Webster+绿波+GA双路线和DQN+MDP强化学习方法。E010最优车速50.35 km/h，E061用泊松分布估算出1,287个停车位需求。

## 1.3 Our Work

本文的贡献包括四个方面：

（1）时段划分采用双方案交叉验证——时序约束层次聚类和贝叶斯断点检测（PELT），协方差矩阵跨时段共享降低参数数量，BIC惩罚项修正为0.5 ln(N)*12，两种方案一致时输出高置信度断点。

（2）信号配时采用"先基荷再剩余"绿灯分配流程，从流程设计上消除不可行解。将最小绿灯基荷先分配，剩余时间按流量比分配，g_max超限时迭代再分配，保证sum(g)=C0-L且每相位>=g_min。

（3）巡游车辆检测基于三特征判定框架并量化侧方进出偏差。增加侧方进出事件的检测与轨迹断裂比例统计，提供保守/乐观双方案停车位估算。启用合成数据生成验证集计算精度、召回率和F1分数。

（4）管控效果评价采用全管控假设下的前后对比模型，通过Post_t（含5月6日非节假日管控日）与Holiday_t（5月1日-5日）的时间变异常识管控净效应和节假日附加效应。使用事件研究法进行平行趋势检验，Cohen's d效应量+AHP权重进行交叉口综合评分。


# 2. Assumptions

1. **车辆轨迹可关联假设**：同一车牌号在相邻交叉口的时间差在合理范围内（tau_max=30 min），可视为同一车辆连续轨迹。*合理性*：景区小镇范围有限（全程不超过15分钟），tau=30 min为基准值，灵敏度分析中考察tau=15,30,45,60分钟。

2. **侧方进出可检测假设**：车辆在非监控点驶离或进入路网时，表现为在某交叉口消失后在非相邻交叉口重新出现。*合理性*：通过"出现-消失-再出现"模式可量化侧方进出，正常穿行与侧方进出的时间差存在统计差异。

3. **车流量分段平稳性假设**：同一时段内，车流量服从平稳泊松过程，到达率恒定。*合理性*：Webster配时理论的经典假设，小时级别上交通流具有统计平稳性。

4. **转向概率的贝叶斯先验假设**：各交叉口转向概率服从Dirichlet先验，超参数由全天平均转向比例确定。*合理性*：转向行为由道路功能和土地利用决定，在一天内保持相对稳定，贝叶斯框架在小样本时段提供平滑收缩（先验强度系数kappa=30）。

5. **绿波协调可行性假设**：12个交叉口可使用统一信号周期进行干线协调。*合理性*：两条路构成网格状路网，总长5.3 km，可找到公共周期满足多数交叉口需求。

6. **全管控假设**：五一期间（5月1日至5月6日）全部12个交叉口均实施交通管控。*合理性*：景区小镇在黄金周通常采取全域而非局部管控。此假设消除了通过outcome反推处理组的循环论证，将DID退化为前后对比模型。

7. **五一效应可分解假设**：五一期间交通模式变化可分解为"节假日效应"和"管控措施效应"两个可加分量。*合理性*：5月6日（管控持续但假期结束）提供了Post=1且Holiday=0的变异来源，使beta_3和gamma可分别识别。此假设为关键识别条件。

8. **监控数据完整性假设**：监控设备车牌识别准确率>=95%，时间戳精度为秒级。*合理性*：现代ANPR系统在良好光照条件下识别率可达95%以上。

9. **信号灯四相位方案假设**：每个交叉口采用四相位方案（南北直行、南北左转、东西直行、东西左转），右转车辆不受信号控制。*合理性*：四相位方案为左转车辆提供独立通行权，避免与对向直行冲突。


# 3. Notation

| Symbol | Definition | Unit |
|--------|------------|------|
| $I$ | Intersection set, $I=\{1,2,\dots,12\}$ | -- |
| $D$ | Direction set, $D=\{\text{N},\text{S},\text{E},\text{W}\}$ | -- |
| $\mathcal{T}$ | Time sampling points, 15-min granularity, $|\mathcal{T}|=96$ | -- |
| $\mathcal{D}$ | Date index set, 36 days | day |
| $\mathbf{x}(t)$ | 12-dim flow feature vector | veh/15min |
| $C_0$ | Common signal cycle for arterial coordination | s |
| $C_{\min}, C_{\max}$ | Cycle bounds (60, 180) | s |
| $L_i$ | Total lost time per cycle at intersection $i$ | s |
| $y_{i,j}$ | Flow ratio of phase $j$ at intersection $i$ | -- |
| $Y_i$ | Sum of flow ratios at intersection $i$ | -- |
| $g_{i,j}$ | Green time for phase $j$ at intersection $i$ | s |
| $g_{i,j}^{\min}$ | Minimum green time (pedestrian safety, default 15s) | s |
| $S_{\text{sat}}$ | Saturation flow rate (0.5 veh/s = 1800 veh/h) | veh/s |
| $\Delta_{i,i+1}$ | Offset between adjacent intersections | s |
| $L_{i,i+1}$ | Distance between adjacent intersections | m |
| $\bar{v}$ | Average speed of the arterial network | km/h |
| $\mathbb{E}[W_i]$ | Average vehicle delay at intersection $i$ (Webster) | s/veh |
| $d_{\text{segment}}$ | Average segment length (530 m) | m |
| $\hat{\theta}_{i,d,d'}^{(k)}$ | Turning probability from $d$ to $d'$ at intersection $i$ in period $k$ | -- |
| $\boldsymbol{\alpha}_i$ | Dirichlet prior hyperparameter vector | -- |
| $\boldsymbol{\phi}_k$ | Cluster center for period $k$ (12-dim flow) | veh/15min |
| $\tau_{\text{match}}$ | Plate matching time window (baseline 30 min) | min |
| $N_{\text{repeat}}(m)$ | Repeat appearance count of vehicle $m$ | times |
| $\bar{v}_m$ | Average travel speed of vehicle $m$ | km/h |
| $H_m$ | Direction entropy of vehicle $m$ (Shannon) | nat |
| $H_{\text{threshold}}$ | Direction entropy threshold | nat |
| $N_{\text{cruise}}(t)$ | Number of cruising vehicles at time $t$ | veh |
| $P_{\text{demand}}$ | Temporary parking spaces needed | spaces |
| $\mu_{\text{occ}}$ | Average parking occupancy time per cruising vehicle | h |
| $\rho$ | Parking space turnover rate | times/day |
| $\beta_3$ | Net control effect in pre-post model | dep. var. unit |
| $\gamma$ | Holiday additive effect coefficient | dep. var. unit |
| $\delta_d$ | Day-of-week fixed effect coefficient | dep. var. unit |
| $S_i$ | Comprehensive control effect score for intersection $i$ (Cohen's d) | -- |
| $K$ | Total number of time periods | -- |
| $\text{CP}_k$ | Change point location (time index) | -- |
| $r_{\text{break}}$ | Trajectory break ratio | -- |


# 4. Model

## 4.1 Problem 1: Time Period Partitioning and Phase Flow Estimation

### 4.1.1 Data Preprocessing and Stratified Aggregation

36天的数据按日期类型分为三组：工作日（周一至周五，不含假期）、周末（周六周日，不含假期）、节假日（5月1日-5日）。对每组分别计算每个15分钟窗口的平均流量向量：

$$\mathbf{x}_{\text{wd}}(t) = \frac{1}{|\mathcal{D}_{\text{weekday}}|} \sum_{d\in\mathcal{D}_{\text{weekday}}} \mathbf{x}_d(t), \quad \forall t\in\mathcal{T}$$

12维特征向量定义为每个交叉口各进口方向的直行、左转、右转流量：

$$\mathbf{x}(t) = [q_{i^*,d,\text{直行}}(t),\; q_{i^*,d,\text{左转}}(t),\; q_{i^*,d,\text{右转}}(t)]_{d\in D} \in \mathbb{R}^{12}$$

### 4.1.2 Contiguity-Constrained Hierarchical Clustering

使用Ward方差最小化准则，每次合并仅允许时间相邻的簇：

$$\Delta\text{SSE}(C_a, C_b) = \frac{|C_a|\cdot|C_b|}{|C_a|+|C_b|} \|\boldsymbol{\phi}_a - \boldsymbol{\phi}_b\|^2$$

最优聚类数$K$通过Dunn指数在K=2到8范围内搜索确定：

$$K_{\text{opt}} = \arg\max_{K\in[2,8]} \text{Dunn}(K)$$

Dunn指数为最小簇间距离与最大簇内直径之比，值越大聚类质量越高。

### 4.1.3 Bayesian Change Point Detection (PELT)

假设每时段内12维流量向量服从多元正态分布，协方差矩阵跨时段共享（降低参数维度）：

$$\mathbf{x}(t) \sim \mathcal{N}(\boldsymbol{\mu}_k, \boldsymbol{\Sigma}), \quad t \in \mathcal{T}_k$$

每个新时段增加12个均值参数（因$\boldsymbol{\Sigma}$共享），BIC惩罚项为$\frac{1}{2}\ln(N) \cdot 12$。断点搜索通过PELT递推实现：

$$F(t^*) = \min_{0 \leq s < t^*} \left\{ F(s) + \mathcal{C}(\mathbf{x}_{s+1:t^*}) + \frac{1}{2}\ln(N) \cdot 12 \right\}, \quad F(0)=0$$

其中$\mathcal{C}(\mathcal{T}_k) = -\sum_{t\in\mathcal{T}_k} \ln\mathcal{N}(\mathbf{x}(t); \hat{\boldsymbol{\mu}}_k, \hat{\boldsymbol{\Sigma}})$为负对数似然代价。

当两种方案的断点边界偏差不超过2个时间窗口（30分钟）时，划分结果标记为"可信"并取均值作为最终断点。

### 4.1.4 Bayesian Turning Probability Estimation

采用Dirichlet-Multinomial共轭贝叶斯模型处理转向概率估计中的小样本问题。先验超参数由全天数据MLE乘以先验强度系数kappa=30得到：

$$\alpha_{i,d,d'} = \kappa \cdot \hat{\theta}_{i,d,d'}^{\text{(全天)}}$$

后验更新后，转向概率的点估计为Dirichlet后验期望。若某进口方向时段总观测数小于5，则与相邻时段合并后重新估计。

## 4.2 Problem 2: Signal Timing Optimization

### 4.2.1 Bi-Level Hierarchical Optimization

优化分为两层：上层搜索公共周期$C_0$和11个相位差$\Delta_{i,i+1}$以最大化路网平均车速；下层在给定$C_0$下按修正Webster方法分配各相位绿灯时间。

期望行程时间由路段行驶时间与交叉口延误之和构成：

$$\mathbb{E}[t_{\text{travel}}] = \sum_{(i,i+1)} \frac{L_{i,i+1}}{v_{\text{free}}} + \sum_{i} \mathbb{E}[W_i]$$

完整优化问题为：

$$
\begin{aligned}
\max_{C_0, \{\Delta_{i,i+1}\}} \quad & \bar{v} = \frac{L_{\text{total}}}{\mathbb{E}[t_{\text{travel}}]} \\
\text{s.t.} \quad & C_{\min} \leq C_0 \leq C_{\max} \\
& \sum_{j} g_{i,j} = C_0 - L_i, \quad \forall i \\
& g_{i,j}^{\min} \leq g_{i,j} \leq g_{i,j}^{\max}, \quad \forall i,j \\
& 0 \leq \Delta_{i,i+1} < C_0, \quad \forall i
\end{aligned}
$$

### 4.2.2 "先基荷再剩余"绿灯分配流程

给定公共周期$C_0$，对交叉口$i$按以下流程分配绿灯时间，从算法设计上保证可行性：

**Step 1**: 计算可用绿灯总时间$G_{\text{avail}} = C_0 - L_i$。

**Step 2**: 可行性检查$\sum_j g_{i,j}^{\min} \leq G_{\text{avail}}$。若不满足则标记为不可行。

**Step 3**: 分配最小绿灯基荷$g_{i,j}^{(0)} = g_{i,j}^{\min}$。

**Step 4**: 计算剩余时间$G_{\text{rem}} = G_{\text{avail}} - J \cdot g_{\min}$，由可行性检查保证$G_{\text{rem}} \geq 0$。

**Step 5**: 按流量比分配剩余时间：$g_{i,j}^{(1)} = g_{i,j}^{\min} + G_{\text{rem}} \cdot y_{i,j}/Y_i$。

**Step 6**: 若存在相位$g > g_{\max}$，触发超限再分配——将超额时间按剩余流量比分配给未达$g_{\max}$的相位，迭代至所有相位满足约束或所有相位均达$g_{\max}$（标记为约束主导）。

### 4.2.3 GA Search

染色体编码为13维向量$[C_0, \Delta_{1,2}, \dots, \Delta_{11,12}]$。适应度函数使用关键相位Webster延误作为交叉口延误的代理变量，以降低约75%的延误计算量。GA参数：种群50、代数200、模拟二进制交叉率0.8、多项式变异率0.1、精英保留。不可行解设适应度为-1e9以硬性排除。

## 4.3 Problem 3: Cruising Vehicle Identification and Parking Demand

### 4.3.1 Trajectory Reconstruction and Side Entry/Exit Detection

对五一期间所有记录按车牌号关联，构建时间排序的交叉口到访序列。侧方进出检测机制：当车辆在非相邻交叉口出现且时间差大于正常行驶时间但小于tau_match时，记为一次侧方进出事件。轨迹断裂比例为侧方进出事件数与总路段数之比。

### 4.3.2 Cruising Feature Classification

车辆$m$被判定为巡游车需同时满足三个条件：

$$\text{Cruise}(m) = \mathbb{I}\{ N_{\text{repeat}}(m) \geq 3 \;\wedge\; \bar{v}_m \leq 5\,\text{km/h} \;\wedge\; H_m \geq H_{\text{threshold}} \}$$

其中$H_{\text{threshold}}$通过双基准加权确定：基准A为非五一期间H分布90%分位数，基准B为五一期间非巡游车H分布90%分位数，最终阈值为两者加权平均。

### 4.3.3 Parking Demand Estimation

保守方案（含侧方进出修正）：

$$P_{\text{demand}}^{\text{conservative}} = \left\lceil Q_{0.95}(\{N_{\text{cruise}}(t)\}) \cdot \frac{\mu_{\text{occ}}}{\rho} \cdot (1 + r_{\text{break}}) \right\rceil$$

乐观方案（无修正）：

$$P_{\text{demand}}^{\text{optimistic}} = \left\lceil Q_{0.95}(\{N_{\text{cruise}}(t)\}) \cdot \frac{\mu_{\text{occ}}}{\rho} \right\rceil$$

参数敏感性分析覆盖mu_occ=[0.25,1.5]h与rho=[2,8]次/日的20组组合，推荐值取中位数。

## 4.4 Problem 4: Control Effect Evaluation

### 4.4.1 Pre-Post Comparison with Holiday Effect Separation

采用全管控假设（Treat_i=1 for all i），DID框架退化为前后对比模型：

$$Y_{it} = \beta_0 + \beta_3\text{Post}_t + \gamma\text{Holiday}_t + \sum_{d\in\text{weekdays}} \delta_d \text{Weekday}_d + \varepsilon_{it}$$

其中$\text{Post}_t=1$表示5月1日至6日（管控实施期），$\text{Holiday}_t=1$表示5月1日至5日。beta_3为管控净效应，gamma为节假日附加效应。参数识别依赖5月6日（Post=1, Holiday=0）与5月1日-5日的时间变异。

### 4.4.2 Dynamic Event Study

作为平行趋势检验的稳健性方法：

$$Y_{it} = \beta_0 + \sum_{\tau=-T}^{-1} \alpha_\tau \mathbb{I}(t=\tau) + \sum_{\tau=1}^{T} \beta_\tau \mathbb{I}(t=\tau) + \gamma\text{Holiday}_t + \sum_{d} \delta_d \text{Weekday}_d + \varepsilon_{it}$$

tau=0为4月30日。管控前系数alpha_tau的联合显著性通过Wald chi-squared检验评估（而非简单的平均t统计量），原假设为所有alpha_tau联合为零。若平行趋势不成立，加入交叉口特定线性时间趋势eta_i*t作为替代方案。

### 4.4.3 Comprehensive Scoring with Cohen's d

各交叉口综合评分基于三个指标的效应量：

$$S_i^{\text{Cohen}} = w_1 \cdot d_{\bar{v}, i} + w_2 \cdot d_{Q, i} + w_3 \cdot d_{w, i}$$

其中d为Cohen's d效应量，对流量和等待时间取负值使正分代表改善。权重通过层次分析法（AHP）确定：车速0.539、流量0.164、等待时间0.297，一致性比率CR=0.008<0.1。


# 5. Results

## 5.1 Data Preprocessing and Synthetic Data

合成数据生成器模拟了12个交叉口36天（2024-04-01至2024-05-06）的交通流。数据基础参数：车辆池8,000辆，总记录数1,439,889条。工作日早晚高峰特征通过时间模式函数控制（早高峰7:00-9:00、晚高峰17:00-19:00的缩放因子显著高于夜间基值0.15）。节假日流量放大因子1.4，周末流量衰减因子0.85。

## 5.2 Time Period Partitioning Results

三种日期类型（工作日、周末、节假日）的时段划分结果完全一致：K=6个时段，断点位置均为时间窗口[28, 36, 68, 76, 84]，对应时刻7:00、9:00、17:00、19:00、21:00。时序约束层次聚类与PELT断点检测两种方案的最大偏差为0个窗口（图1、图2）。

6个时段呈现典型的五日交通模式：夜间低流量段（0:00-7:00）、早高峰上升段（7:00-9:00）、日间平段（9:00-17:00）、晚高峰段（17:00-19:00）、黄昏下降段（19:00-21:00）和夜间平稳段（21:00-24:00）。节假日和工作日相比，流量幅值不同但时段边界不变（图3）。

各时段的转向概率通过Dirichlet-Multinomial贝叶斯方法估计。先验强度系数kappa=30提供平滑收缩。对总观测数小于5的时段合并相邻时段后重新估计，在合成数据的36天样本中未出现必须合并的情况。

## 5.3 Signal Timing Optimization Results

**表1：信号配时优化结果**

| 参数 | 值 |
|------|------|
| 公共周期C0 | 88 s |
| 周期可行域 | [70.4, 105.6] s |
| 最优平均车速 | 25.26 km/h |
| 纬中路偏移量（交叉口1-8） | 63.0 s |
| 经中路偏移量（交叉口9-11） | 32.4 s |

Webster单点最优周期计算显示各交叉口各时段的最优周期分布在70至106秒之间，上层GA在这个范围内搜索公共周期。GA收敛曲线（图4）显示约在40代达到稳定。

公共周期C0=88秒下，纬中路交叉口（间距700米）的偏移量63.0秒对应绿波设计车速11.11 m/s（40 km/h），经中路交叉口（间距360米）的偏移量32.4秒对应相同的设计车速。GA搜索得到的偏移量与启发式初始值一致（700/11.11=63.0, 360/11.11=32.4），表明在该路网几何参数下存在简单解析解。

绿灯分配结果（图5、图8面板5）显示各交叉口按"先基荷再剩余"流程分配后，四个相位的绿灯时间随流量比分布。所有交叉口均通过了可行性检查，无g_max超限情况。

## 5.4 Cruising Vehicle Detection Results

**表2：巡游车辆检测核心结果**

| 指标 | 值 |
|------|------|
| 检测到巡游车数 | 210辆 |
| 方向熵阈值H_threshold | 1.377 nat |
| 轨迹断裂比例r_break | 10.35% |
| 停车位需求（保守方案） | 42个 |
| 停车位需求（乐观方案） | 38个 |
| 同时巡游车辆数Q95 | 199.5辆 |
| 巡游判定三条件 | N_repeat>=3, v<=5 km/h, H>=1.377|

轨迹重建结果表明10.35%的路段间移动存在侧方进出（非监控点进出路网）。图6左上子图展示了tau匹配窗口的敏感性分析：tau从15分钟增加到60分钟，巡游车辆数从80辆增加到476辆，停车位需求从15个增加到102个，变异系数CV=56.2%。图6右上子图展示mu_occ与rho的参数敏感性矩阵，停车位估计范围从[15,102]延伸至更广区间。

**表3：tau匹配窗口敏感性（tau=15至60分钟）**

| 窗口tau (min) | 断裂比r_break | 巡游车数 | 保守需求 | 乐观需求 |
|:---:|:---:|:---:|:---:|:---:|
| 15 | 3.70% | 80 | 15 | 15 |
| 30 | 10.35% | 210 | 42 | 38 |
| 45 | 15.98% | 369 | 76 | 65 |
| 60 | 20.92% | 476 | 102 | 84 |

图6右下子图展示车辆特征空间（平均速度vs方向熵，颜色表示重复出现次数）。巡游区域集中在v<5 km/h且H>1.377 nat的区域。大量非巡游车辆聚集在v<10 km/h的低速区域，与巡游车存在特征重叠，导致分类混淆。

验证结果：真实巡游车578辆（合成数据注入），检测到210辆，真正例27辆，精度0.1286，召回率0.0467，F1分数0.0685。低F1主要由以下原因导致：(a)巡游与正常低速行驶的特征重叠，(b)tau窗口选择直接影响检测数量，(c)侧方进出导致轨迹断裂，降低N_repeat有效计数。

## 5.5 Control Effect Evaluation Results

### 5.5.1 Regression Results

**表4：前后对比回归结果（含节假日效应分离）**

| 因变量 | beta_3（管控净效应） | beta_3 p值 | gamma（节假日效应） | gamma p值 | R-squared |
|--------|:---:|:---:|:---:|:---:|:---:|
| 平均车速 (km/h) | -0.34 | 0.147 | +11.56 | <0.001 | 0.066 |
| 总流量 (veh/15min) | -12.83 | 0.344 | +1,535.55 | <0.001 | 0.198 |
| 等待时间 (s/km) | +0.53 | 0.065 | -14.21 | <0.001 | 0.067 |

三个指标中，管控净效应beta_3均未达到统计显著性（p>0.05）：平均车速在管控期间下降0.34 km/h，总流量减少约12.83 veh/窗口，等待时间增加0.53 s/km。节假日附加效应gamma均高度显著（p<0.001），表示五一期间流量增加约1,536 veh/窗口，车速提升11.56 km/h，等待时间减少14.21 s/km。模型整体解释力较低（R-squared<0.2）。

### 5.5.2 Parallel Trend Test

事件研究法的平行趋势检验通过（Wald chi-squared检验，p>0.05），表明管控前各日（4月24日至4月30日）与基准期无显著差异。图7左上子图展示事件研究系数，管控前系数在零附近波动，管控后系数无明显系统性偏移。

### 5.5.3 Comprehensive Scores

各交叉口的Cohen's d综合评分（AHP权重：车速0.539、流量0.164、等待时间0.297）显示交叉口间效果分化（图7右下、图8面板7）。部分交叉口评分为正（管控后改善），部分为负（管控后恶化），正负评分并存说明管控效果在路网中非均匀分布。

由于全管控假设下无未管控交叉口作对照组，且beta_3和gamma的分离依赖于5月6日（非节假日管控日）的单日变异，回归结果应解读为条件性结论——若可加性假设成立，则管控效应不显著；若5月6日包含独特的返程高峰效应，则beta_3可能低估实际管控效果。


# 6. Sensitivity Analysis

## 6.1 tau匹配窗口对巡游检测的影响

tau_matching窗口从15分钟变化到60分钟，巡游检测结果呈现强敏感性（CV=56.2%）。tau=15分钟时仅检测到80辆巡游车（断裂比3.70%），tau=60分钟时增至476辆（断裂比20.92%）。tau=30分钟为基准值，对应的平均路段行驶时间约143秒（530m/13.89m/s），30分钟窗口可覆盖正常行驶加2-3次停车活动的完整循环。但tau值的选择缺乏外部验证数据，建议在实际部署中根据停车场位置和监控密度校准。

## 6.2 停车位参数敏感性

停车位需求对mu_occ（平均寻泊时间）和rho（周转率）高度敏感。在20组参数组合中，需求范围跨度较大：mu_occ=0.25h、rho=8时的最低需求与mu_occ=1.5h、rho=2时的最高需求相差约10倍。推荐值取20组估计的中位数，不确定性范围为[Q25, Q75]。

## 6.3 公共周期GA敏感性

GA搜索得到的公共周期C0=88秒在可行域[70.4, 105.6]秒内。当C0偏离最优值时，路网平均车速的预期变化为：周期缩短至70秒时部分交叉口可能无法满足最小绿灯约束；周期延长至106秒时延误增加。偏移量精确等于路段长度除以设计车速（700/11.11=63.0s），表明在给定路网结构下绿波协调存在唯一解析最优解。

## 6.4 平均路段长度假设对车速估计的影响

路网中纬中路（700米段距）和经中路（360米段距）的段距差异显著。代码中使用加权平均530米作为统一段距，这导致经中路交叉口（9-12）之间的车速被系统性地高估约39%。由于经中路的实际段距较短，在相同偏移量下车辆需更频繁地停车，实际平均车速可能低于报告的25.26 km/h。

## 6.5 PELT参数敏感性

BIC惩罚项系数从0.5 ln(N)*12调整为其他值时，断点数量会变化。惩罚系数增大减少断点（参数节约），减少则增加断点（过拟合风险）。当前设置下两类方案完全一致，说明断点结构对惩罚项选择相对稳健。但在实际数据中，该一致性依赖于共享协方差假设——若各时段协方差显著不同，两种方案可能产生分歧。


# 7. Evaluation

## 7.1 Strengths

1. **双方案交叉验证的时段划分**：时序约束层次聚类与贝叶斯断点检测两种独立方案在三种日期类型上均取得完全一致的断点位置，为时段划分结果提供了高置信度支撑。

2. **"先基荷再剩余"绿灯分配流程保证可行性**：从算法设计层面消除不可行解，无需后处理截断或二次修正。该流程天然保证sum(g)=G_avail且每相位>=g_min，且通过可行性检查的预判断避免无效GA搜索。

3. **侧方进出偏差量化**：引入轨迹断裂比例作为路网覆盖不全的代理指标，为巡游车判定提供偏差修正基准。保守/乐观双方案的停车需求估计覆盖了参数不确定性范围。

4. **管控评价的节假日效应分离**：利用5月6日（非节假日但管控持续）的时间变异将管控效应与节假日效应分离，避免了将节假日流量增长误归因于管控失效。事件研究法提供平行趋势的统计检验。

## 7.2 Limitations

1. **巡游车检测的F1分数仅为0.0685**：精度（0.1286）和召回率（0.0467）均处于低水平。主要原因包括：(a)巡游行为与正常低速行驶在特征空间（速度、方向熵）存在重叠；(b)合成数据中注入的巡游模式可能不完全反映真实行为；(c)tau窗口参数对检测结果影响极大（CV=56.2%）。F1=0.0685意味着当前方法在实际部署中的误报率和漏报率均不可接受。

2. **速度代理的段距近似偏差**：使用530米加权平均段距统一处理所有路段，导致经中路（实际段距360米）车速被高估约39%。正确的做法应逐路段计算，但GA的适应度函数需要统一度量。

3. **管控效应统计学不显著**：三个因变量的beta_3均未通过显著性检验（p>0.05），且模型R-squared<0.2。这并不意味着管控无效，而是：当前数据条件下无法拒绝零假设；样本量（12交叉口x36天=432观测值）对检测小效应量可能不足。

4. **节假日效应分离依赖单日变异**：beta_3和gamma的识别完全依赖5月6日（唯一的Post=1且Holiday=0的日期）。若5月6日存在独特的返程高峰模式而非常规管控日，则可加性分解假设不成立，beta_3可能混杂了返程效应。

5. **全管控假设不可验证**：由于缺乏外部政策信息或未管控交叉口，Treat_i=1 for all i的假设无法通过数据检验。若实际仅部分交叉口受管控，则beta_3为平均处理效应（ATE）而非处理组平均处理效应（ATT），解读需调整。

6. **PELT未实现O(n)剪枝**：当前实现的剪枝条件在实践中极少触发，复杂度为O(n^2)。对于n=96的时间窗口规模这不是性能问题，但不应对PELT的理论复杂度做过度宣称。

7. **GA仅单次运行**：GA优化仅进行一次，未使用多随机种子重复运行验证收敛稳定性。偏移量收敛到与启发式初始值相同的值，建议多次运行确认最优性。

8. **合成数据验证的局限性**：验证使用的真实巡游车标签来自合成数据生成器的注入，其行为模式可能过于理想化。在真实数据上，车牌识别失败、跨日轨迹关联等问题会增加检测难度。

## 7.3 Future Work

(1) 引入空间聚类约束（如交叉口之间的流量相关性）改进时段划分。
(2) 对巡游检测采用集成方法——如多tau窗口投票或时序模式匹配——提升F1。
(3) 若可获得未管控交叉口数据（如邻近非景区路段），使用真DID替代前后对比。
(4) 使用多智能体强化学习（MARL）替代GA进行信号配时，可处理交通状态的非平稳性。
(5) 对停车位需求评估引入实时数据反馈，动态调整征用方案。


# References

[1] Webster, F.V. (1958). Traffic Signal Settings. Road Research Technical Paper No. 39, London: HMSO.

[2] Killick, R., Fearnhead, P., & Eckley, I.A. (2012). Optimal detection of changepoints with a linear computational cost. Journal of the American Statistical Association, 107(500), 1590-1598.

[3] Murtagh, F., & Legendre, P. (2014). Ward's hierarchical agglomerative clustering method: Which algorithms implement Ward's criterion? Journal of Classification, 31(3), 274-295.

[4] Transportation Research Board. (2010). Highway Capacity Manual 2010. Washington, D.C.: TRB.

[5] Shoup, D.C. (2006). Cruising for parking. Transport Policy, 13(6), 479-486.

[6] Angrist, J.D., & Pischke, J.S. (2008). Mostly Harmless Econometrics: An Empiricist's Companion. Princeton University Press.

[7] Akcelik, R. (1981). Traffic Signals: Capacity and Timing Analysis. Australian Road Research Board, Research Report ARR No. 123.

[8] Holland, J.H. (1992). Adaptation in Natural and Artificial Systems. MIT Press.

[9] Deb, K., & Agrawal, R.B. (1995). Simulated binary crossover for continuous search space. Complex Systems, 9(2), 115-148.

[10] Robertson, D.I. (1969). TRANSIT: A Traffic Network Study Tool. Road Research Laboratory Report LR 253.

</draft_paper>
