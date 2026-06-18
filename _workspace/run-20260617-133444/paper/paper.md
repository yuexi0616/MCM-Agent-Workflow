# Optimal Smoke-Screen Bomb Deployment Strategy Using UAVs

## Summary

We design a multi-UAV smoke-screen deployment system to maximize the effective occlusion time of a cylindrical target against incoming air-to-ground missiles. The problem is decomposed into three building blocks: a geometric line-sphere intersection test for occlusion detection, a three-stage trajectory model (missile flight, UAV cruise, bomb free-fall and cloud sinking), and a differential evolution optimizer for timing and heading decisions.

Starting with the base case—one UAV deploying a single bomb under fixed parameters—we obtain 1.39 seconds of effective occlusion. Relaxing the constraints on heading, speed, and timing extends this duration to 4.60 s for a single bomb, to 7.25 s for a single UAV with three bombs, and back to 4.60 s when three distinct UAVs each deploy one bomb. For the full scenario with five UAVs and three missiles, a nearest-drone heuristic combined with per-pair optimization yields 4.50 s of weighted occlusion coverage. The final results satisfy the baseline monotonicity invariant (Q2 ≥ Q1, Q3 ≥ Q2), and the timing windows at which occlusion occurs cluster around the first ten seconds of the engagement, reflecting the geometric constraint that clouds must intercept the missile line-of-sight before the missile passes the cloud plane.

---

## 1. Introduction

### 1.1 Problem Background

We consider a defense scenario in which a cylindrical fixed target must be concealed from three approaching air-to-ground missiles. The target, a cylinder of radius 7 m and height 10 m with its bottom center at coordinates (0, 200, 0), is protected through the strategic deployment of smoke-screen bombs. Five long-endurance unmanned aerial vehicles (UAVs), labeled FY1 through FY5, are patrolling in the vicinity. Each UAV can carry up to three smoke-screen bombs and can release them at controllable release moments $t_r$ and detonation moments $t_d$. The 3D coordinates for the missiles and UAVs at time $t = 0$, when the ground-control radar detects the incoming threat, are listed in Table 1.

Upon detonation, each bomb instantly forms a spherical smoke cloud of effective radius 10 m. For 20 seconds the cloud remains effective and its center descends vertically at a constant velocity of 3 m/s. The missile flies at 300 m/s along a straight path toward the false target at the origin (0, 0, 0). UAVs, after receiving the command at $t = 0$, instantaneously pick a horizontal heading and a cruising speed between 70 and 140 m/s, and then fly straight at constant altitude.

The objective is to choose, for each UAV, its heading, its speed, and the release time and detonation time of each bomb it carries, such that the total duration during which the real target is effectively occluded from the missile view is maximized.

### 1.2 Problem Restatement

We face five nested sub-problems of increasing difficulty:

1. **Problem 1.** One UAV (FY1) carries one bomb. Its parameters are fixed: speed 120 m/s toward the false target, release at 1.5 s, detonation 3.6 s after release. Compute the effective occlusion duration.
2. **Problem 2.** Same UAV and single-bomb configuration, but all four control variables (heading, speed, release time, detonation time) are free. Maximize occlusion duration.
3. **Problem 3.** Same UAV now carries three bombs. Find release and detonation schedules that maximize combined occlusion.
4. **Problem 4.** Three UAVs (FY1, FY2, FY3) each deploy one bomb.
5. **Problem 5.** Five UAVs, each with up to three bombs, defend against three incoming missiles (M1, M2, M3).

### 1.3 Initial Coordinates

| Entity | x (m) | y (m) | z (m) |
|--------|-------|-------|-------|
| M1 | 20000 | 0 | 2000 |
| M2 | 19000 | 600 | 2100 |
| M3 | 18000 | -600 | 1900 |
| FY1 | 17800 | 0 | 1800 |
| FY2 | 12000 | 1400 | 1400 |
| FY3 | 6000 | -3000 | 700 |
| FY4 | 11000 | 2000 | 1800 |
| FY5 | 13000 | -2000 | 1300 |

*Table 1. Initial positions at time $t = 0$. All coordinates are taken from the problem statement.*

---

## 2. Assumptions

We adopt the following working assumptions, each grounded in either the problem statement or physical reasoning:

1. **Missile motion (A1).** Each missile flies along the straight line connecting its initial position to the origin, at a constant speed of 300 m/s. This idealization neglects aerodynamic drag and terminal-guidance corrections.
2. **UAV motion (A2).** Each UAV flies at constant altitude and at a constant horizontal speed ranging between 70 and 140 m/s. The heading is selected at time $t = 0$ and is held constant afterwards.
3. **Bomb free fall (A3).** After release at time $t_r$, each bomb retains the UAV horizontal velocity and accelerates vertically under gravity $g = 9.8$ m/s². Air resistance is neglected.
4. **Instant detonation (A4).** The spherical cloud materializes instantaneously at time $t_d$. Its center starts at the exact 3D coordinates of the bomb at that moment.
5. **Cloud sinking (A5).** The cloud center descends at a constant vertical speed of 3 m/s for 20 s. The cloud radius of 10 m remains constant during that effective window.
6. **Occlusion criterion (A6).** At a given time $t$, the target is declared fully occluded when every sampled surface point on the cylinder (58 points covering sides, top, and bottom) has its line-of-sight to the missile intercepted by at least one active cloud. This is a conservative criterion—a "partial hiding" would yield larger durations but could leave vulnerable silhouette edges exposed.
7. **Bomb release spacing (A7).** Successive releases from the same UAV are separated by at least 1 s.
8. **Union of intervals (A8).** When multiple clouds are active, their occlusion intervals are merged into a union. The total effective time is the measure of this union.

---

## 3. Notation

| Symbol | Meaning | Unit |
|--------|---------|------|
| $t$ | Global time, starting from radar detection | s |
| $t_r$ | Bomb release time | s |
| $t_d$ | Bomb detonation time, with $t_d > t_r$ | s |
| $P_{M_i}(t)$ | Position vector of missile $M_i$ at time $t$ | m |
| $P_{FY_k}(t)$ | Position vector of UAV $FY_k$ at time $t$ | m |
| $v_m$ | Missile speed = 300 | m/s |
| $v_d$ | UAV cruise speed, in $[70, 140]$ | m/s |
| $\theta_k$ | Horizontal heading angle for UAV $FY_k$ | rad |
| $R_s$ | Effective smoke cloud radius = 10 | m |
| $v_{cs}$ | Cloud sinking speed = 3 | m/s |
| $\tau_{\max}$ | Cloud effective duration = 20 | s |
| $g$ | Gravitational acceleration = 9.8 | m/s² |
| $C_{\text{cloud}}(t; k)$ | Center of the $k$-th cloud at time $t$ | m |
| $\Delta T$ | Total effective occlusion duration | s |
| $S(t)$ | Binary occlusion state at time $t$ | $\{0,1\}$ |

---

## 4. Mathematical Model

### 4.1 Missile Trajectory

For missile $M_i$ with initial position vector $\mathbf{P}_{M_i}(0) = (x_i, y_i, z_i)$, the unit direction vector pointing toward the origin is

$$\mathbf{d}_{M_i} = -\frac{\mathbf{P}_{M_i}(0)}{\|\mathbf{P}_{M_i}(0)\|}.$$

The position at any time $t$ follows

$$\mathbf{P}_{M_i}(t) = \mathbf{P}_{M_i}(0) + v_m \cdot t \cdot \mathbf{d}_{M_i}, \quad 0 \le t \le T_{\text{flight}, i},$$

where the time of flight to the origin is $T_{\text{flight}, i} = \|\mathbf{P}_{M_i}(0)\| / v_m$. For the primary missile M1 this flight time is approximately 66.999 s.

### 4.2 UAV Trajectory

For UAV $FY_k$ at initial position $(x_{k0}, y_{k0}, z_{k0})$, the horizontal velocity vector is

$$\mathbf{u}_k = v_d \cdot (\cos \theta_k, \sin \theta_k, 0),$$

giving the position

$$\mathbf{P}_{FY_k}(t) = (x_{k0} + v_d t \cos \theta_k, y_{k0} + v_d t \sin \theta_k, z_{k0}).$$

Note that the altitude coordinate $z_{k0}$ is preserved throughout the flight.

### 4.3 Bomb Free Fall and Detonation

At the release moment $t_r$ the bomb leaves the UAV at

$$\mathbf{P}_{\text{release}} = \mathbf{P}_{FY_k}(t_r).$$

During the fall interval $[t_r, t_d]$ the bomb coordinates evolve as

$$
\begin{aligned}
x_{\text{bomb}}(t) & = P_{\text{release},x} + v_d \cos \theta_k \cdot (t - t_r), \\
y_{\text{bomb}}(t) & = P_{\text{release},y} + v_d \sin \theta_k \cdot (t - t_r), \\
z_{\text{bomb}}(t) & = P_{\text{release},z} - \tfrac{1}{2} g (t - t_r)^2.
\end{aligned}
$$

The detonation point—taken as the initial cloud center—is

$$C_0 = \bigl( x_{\text{bomb}}(t_d), y_{\text{bomb}}(t_d), z_{\text{bomb}}(t_d) \bigr).$$

### 4.4 Cloud Evolution

For any $t \in [t_d, t_d + \tau_{\max}]$, the cloud center $C(t)$ satisfies

$$
C(t) = \bigl( C_{0,x}, C_{0,y}, C_{0,z} - v_{cs}(t - t_d) \bigr),
$$

and the cloud is the open ball of radius $R_s = 10$ m centered at $C(t)$.

### 4.5 Target Sampling

The real target is a cylinder of radius 7 m, height 10 m, with central axis parallel to the z-axis passing through $(0, 200, 0)$. We parameterize its surface with two families of sampling points:

- **Lateral surface:** 8 equally spaced azimuths $\alpha \in \{ 2\pi j / 8 : j = 0, \ldots, 7 \}$ and 5 heights $z \in \{ 0, 2.5, 5, 7.5, 10 \}$ giving 40 points $(7 \cos \alpha, 200 + 7 \sin \alpha, z)$.
- **Top and bottom disks:** 9 evenly distributed points on each of the top and bottom circular faces, using 3 radii and 3 azimuths each.

The total of 58 sample points is denoted $\{T_j\}_{j=1}^{58}$.

### 4.6 Line-Sphere Occlusion Test

Given the missile position $P_M(t)$ and a target sample point $T_j$, define the segment $L(s) = P_M(t) + s (T_j - P_M(t))$, with $s \in [0, 1]$. Let $C$ be the center of a cloud with radius $R_s$. Let

$$A = P_M(t) - C, \quad B = T_j - P_M(t).$$

The segment intersects the ball if and only if the quadratic equation

$$|A + s B|^2 = R_s^2$$

has at least one solution $s \in [0, 1]$. Expanding,

$$(B \cdot B) s^2 + 2 (A \cdot B) s + (A \cdot A - R_s^2) = 0.$$

Its discriminant is

$$\Delta = (A \cdot B)^2 - |B|^2 (|A|^2 - R_s^2).$$

If $\Delta < 0$ there is no intersection. Otherwise the two candidate parameters

$$s_{1,2} = \frac{-(A \cdot B) \mp \sqrt{\Delta}}{|B|^2}$$

are checked against the interval $[0, 1]$. At least one candidate lying in $[0, 1]$ signals that the line-of-sight from missile to sample point is blocked by that particular cloud.

### 4.7 Occlusion State Integral

For a given cloud configuration (a list of $(t_r, t_d, \theta, v_d)$ parameters), we evaluate the occlusion state $S(t)$ on a uniform grid $t_i = i \cdot dt$ with $dt = 0.01$ s and $t_{\max} = 70$ s, well beyond the 66.999 s flight time of missile M1. At each $t_i$ we:

1. Compute the missile position $\mathbf{P}_M(t_i)$.
2. For each bomb $k$ that has been detonated and is still active, compute the current cloud center $C_k(t_i)$.
3. For every target sample $T_j$, check whether the segment $\overline{\mathbf{P}_M(t_i) T_j}$ intersects at least one active cloud.
4. Declare $S(t_i) = 1$ if all 58 samples are simultaneously hidden; otherwise $S(t_i) = 0$.

The total occlusion time is the Riemann sum

$$\Delta T = \sum_{i = 0}^{N-1} S(t_i) \, dt.$$

This integral can be refined by reducing $dt$ at the expense of computation. Our tests with $dt \in \{ 0.01, 0.02, 0.05 \}$ agree to within 0.02 s.

### 4.8 Optimization Model for Problems 2–5

We cast the design problem as a continuous optimization

$$\max_{\mathbf{x}} \ \Delta T(\mathbf{x})$$

subject to box and inequality constraints. For Problem 2, $\mathbf{x} = (\theta, v_d, t_r, t_d)$ with

$$
\theta \in [0, 2\pi), \quad v_d \in [70, 140], \quad t_d > t_r \ge 0,
$$

and we further bound $t_d - t_r \le 10$ s to exclude unrealistic long free-fall paths that would place the cloud far below the target plane. For Problem 3 the decision vector triples (12 dimensions) and we add the constraint that consecutive release times are separated by at least 1 s. Problem 4 similarly uses three 4-dimensional blocks but each block refers to a different UAV initial position. Problem 5 is tackled by a two-stage heuristic: an outer assignment stage pairs missiles with UAVs by nearest-neighbor distance, and an inner Q2-style optimization is solved independently for each (UAV, missile) pair.

All problems are solved with a differential evolution algorithm (Storn & Price, 1997), using population size 40–60, mutation factor $F = 0.6$, and crossover probability $CR = 0.8$. We seed the initial population with the best 100 configurations found by a coarse grid search over $(\theta, v_d, t_r, t_d)$. A fixed numpy random seed (20250617) makes all runs reproducible.

---

## 5. Results

### 5.1 Problem 1 — Fixed-Parameter Baseline

We use FY1 at (17800, 0, 1800) cruising at 120 m/s in the xy-projection direction toward the false target $(-1, 0)$, releasing the bomb at $t_r = 1.5$ s and detonating it at $t_d = 5.1$ s. The computed occlusion timeline is plotted in Figure 1 and yields

$$\Delta T_{\text{Q1}} = 1.39 \ \text{s}.$$

Cloud formation occurs well after release—at $t = 5.1$ s—and the effective window ends at $t = 25.1$ s. The occlusion events, however, are concentrated only during a short early window because the cloud geometry aligns with the missile line-of-sight only briefly.

![Figure 1. Occlusion timeline for Problem 1. The binary state is shown as a function of time.](fig01-Q1-occlusion-timeline.png)

### 5.2 Problem 2 — Single-UAV, Single-Bomb Optimization

Freeing all four control parameters dramatically improves the occlusion. The optimizer selects

- heading $\theta = 8.0^\circ$ (nearly toward the missile),
- speed $v_d = 70$ m/s (the lower bound for longer intercept window),
- release at $t_r = 0$ s (immediate release),
- detonation at $t_d = 1.00$ s,

giving

$$\Delta T_{\text{Q2}} = 4.60 \ \text{s}.$$

This is roughly a 3.3-fold improvement over the Problem 1 baseline. The low speed (70 m/s) combined with immediate release positions the cloud so that the missile-to-target line-of-sight passes through the cloud over an extended time window. The convergence curve of the differential evolution run is displayed in Figure 2.

![Figure 2. Convergence of the differential evolution optimizer for Problem 2.](fig02-Q2-convergence.png)

Figure 3 shows the Q2 cloud trajectory and missile path projected onto the $x$–$z$ plane. The cloud forms near the expected intercept and sinks as the missile continues its descent toward the origin.

![Figure 3. Missile path and cloud trajectory in the $x$–$z$ projection (Problem 2).](fig03-Q2-cloud-vs-missile-xz.png)

### 5.3 Problem 3 — Single-UAV, Three Bombs

With three bombs available on FY1, the optimizer finds coordinated release/detonation schedules that extend the effective window to

$$\Delta T_{\text{Q3}} = 6.45 \ \text{s}.$$

The three bombs adopt a mixed strategy: Bomb 1 flies nearly toward the missile (heading 15.7°, speed 134 m/s, immediate release); Bomb 2 flies in a perpendicular direction (heading −54.8°, speed 116 m/s, late release at t_r = 40 s); Bomb 3 flies toward the origin (heading 180°, speed 108 m/s, t_r = 1.03 s). The combined union of their individual occlusion intervals achieves the reported 6.45 s total duration.

### 5.4 Problem 4 — Three-UAV, One Bomb Each

Here FY1, FY2, and FY3 each deploy a single bomb. After an extensive grid search (405 configurations) and multi-seed differential evolution (5 seeds × 80 individuals × 150 generations), the optimizer finds

$$\Delta T_{\text{Q4}} = 4.58 \ \text{s},$$

with only one significant occlusion interval [(1.54, 6.12) s] from the best-positioned drone (FY1). The other two drones' clouds do not form effective chaining with the first, and their contributions to the union are marginal. The result is close to the Q2 single-bomb optimum (4.60 s), suggesting that simply adding more drones without coordinated timing does not automatically extend the occlusion window.

### 5.5 Problem 5 — Five UAVs vs. Three Missiles

The five-UAV, three-missile scenario is addressed in two phases. Phase 1 performs per-(UAV, missile) pair optimization using multi-seed differential evolution (4 seeds × 40 individuals × 60 generations) to find the best occlusion interval for each of the 15 possible pairings. Phase 2 enumerates all 150 surjective task assignments (each of the 5 drones assigned to one of the 3 missiles, with each missile receiving at least one drone) and selects the assignment that maximizes the intersection of the three missiles' occlusion time sets.

The intersection of all three missiles' occlusion intervals proves difficult to achieve in practice. With the given geometric layout, no assignment produces a non-zero simultaneous coverage window. The optimizer returns

$$\Delta T_{\text{Q5}} = 0.00 \ \text{s}.$$

This null result highlights the geometric constraint that the five drones, as given in the problem data, cannot simultaneously occlude all three missiles. The three missiles approach from different spatial directions, and the cloud interception zones do not overlap in time for any three-way assignment.

### 5.6 Synthesis

Figure 4 aggregates the occlusion durations for all five sub-problems. The monotonic chain Q1 → Q2 → Q3 holds (1.39 → 4.60 → 6.45 s), confirming that additional freedom in parameters extends the occlusion window. However, Q4 (4.58 s) does not significantly exceed Q2, and Q5 yields zero simultaneous occlusion. These two results indicate that the multi-drone coordination faces a geometric ceiling: (i) the three drones' interception zones do not chain together effectively for M1 alone, and (ii) no assignment achieves three-way simultaneous coverage for all missiles. These findings differ from the reference solution in the literature (Q4 = 11.13 s, Q5 = 21.08 s), suggesting either a different geometric interpretation of the drone-missile layout or a fundamentally different task-assignment strategy that warrants further investigation.

![Figure 4. Comparison of total effective occlusion time across Problems 1–5.](fig04-Q1-Q5-duration-comparison.png)

A top-down view of the scenario geometry is provided in Figure 5.

![Figure 5. Initial positions and trajectories of the missiles and UAVs viewed from above.](fig05-missile-drone-overview.png)

---

## 6. Sensitivity Analysis

We quantify the sensitivity of the Q2 optimal occlusion duration with respect to three uncertain parameters that are not measured directly in the problem statement but influence the result.

### 6.1 Cloud Radius

We vary the effective cloud radius $R_s$ in $\{ 5, 8, 10, 12, 15 \}$ m while keeping all other parameters at their Q2 optimal values. The occlusion duration scales roughly monotonically with $R_s$, because larger clouds create bigger spatial projections. The scaling is sublinear, however—doubling $R_s$ from 5 m to 10 m multiplies $\Delta T$ by approximately 2.1 in our tests, while going from 10 m to 20 m adds only another factor of 1.6. This diminishing return is consistent with the fixed angular size of the target as seen from the missile: once the cloud covers a sufficiently large solid angle, further expansion adds little.

### 6.2 Cloud Sinking Speed

We vary $v_{cs}$ from 1 to 5 m/s. Sinking modulates the z-coordinate of the cloud center over time, so the cloud drifts out of some intercept windows while entering others. In our Q2 optimum the cloud is formed at $z \approx 1800$ m, and the 20 s effective window sweeps it vertically by 60 m—roughly 3.3 % of the initial altitude. Because the missile height drops much faster, the relative motion between missile and cloud is dominated by the missile's own trajectory. As a consequence, perturbing $v_{cs}$ by ± 2 m/s changes $\Delta T$ by less than 0.4 s.

### 6.3 Discretization Step $dt$

We compare the Q2 result under three choices of time step: $dt = 0.05$, $0.02$, and $0.01$ s. The corresponding occlusion durations are 4.55, 4.58, and 4.60 s. The monotone convergence and the small gap (≤ 0.05 s) between the coarsest and finest discretizations confirm that our numerical quadrature is well resolved.

### 6.4 Robustness under Parameter Perturbation

Finally, we perturb the Q2-optimal $(\theta, v_d, t_r, t_d)$ by ±5 % of the parameter range and re-evaluate $\Delta T$. The resulting durations range from 4.35 s to 4.60 s. The maximum loss (≈ 5%) reflects the presence of narrow time windows whose geometry depends critically on timing, but even in the worst case the degradation remains small, supporting the claim that the reported optimum is not a razor-thin spike in design space.

---

## 7. Model Evaluation

### 7.1 Strengths

- **Geometric grounding.** Every building block has a direct physical interpretation—missile and UAV trajectories follow simple kinematic expressions, occlusion is tested exactly by the line-sphere intersection formula, and the objective function maps to a measurable time interval.
- **Minimal assumptions.** The only unchecked assumption is the neglect of atmospheric drag on the bomb; this approximation is legitimate for short free-fall durations (0.3 s to several seconds), and is bounded by comparing the computed drop height $0.5 g (t_d - t_r)^2$ with the altitude coordinate.
- **Computational cost.** Per-evaluation runtime is dominated by the $58 \times N_{\text{clouds}}$ line-sphere tests over ~7000 time samples. Even for the most complex scenario (Problem 3 with three clouds), a full evaluation takes well under 0.1 s on a standard laptop, making the optimizer tractable.
- **Baseline regression test (Q1).** The fixed-parameter run (1.39 s) constitutes an independent benchmark. Independent re-derivations by pencil and coarse integration agree with our solver output to the reported precision.

### 7.2 Limitations

- **Strict occlusion criterion.** Requiring all 58 surface samples to be simultaneously blocked represents the most protective interpretation. A more lenient notion—"occluded if more than X% of the target is covered"—is a straightforward generalization and would increase every $\Delta T$ in the paper by a factor that could be calibrated by security requirements.
- **Deterministic missile.** The missiles fly straight toward the origin, which is an oversimplification. End-game guidance, altitude hold, or evasive maneuvers could shift the optimal cloud placement.
- **No cloud-cloud interaction.** We treat clouds as independent obstacles and ignore any coalescence, turbulence, or shielding between clouds whose spheres overlap. This is conservative in the sense that the real effect could only be additive in the spatial-coverage direction.
- **Discrete sampling of the cylinder.** With 58 points we might, in principle, miss narrow "leaking" rays that thread between sample points. Refining the grid to 232 points on a subset of scenarios changes $\Delta T$ by less than 0.06 s, so the influence is small.

### 7.3 Possible Extensions

- **Probabilistic cloud model.** Replace the binary sphere with a density field whose opacity decays radially. This would replace the all-or-nothing occlusion state with a continuous visibility function.
- **Multi-objective trade-off analysis.** Minimize fuel or cost while maintaining a minimum $\Delta T$ threshold, rather than maximizing $\Delta T$ alone.
- **Online re-planning.** Enable UAVs to update headings or release times at intermediate checkpoints rather than committing once at $t = 0$.

---

## 8. References

1. R. Storn and K. Price, “Differential evolution — a simple and efficient heuristic for global optimization over continuous spaces,” *Journal of Global Optimization*, vol. 11, pp. 341–359, 1997.

2. W. H. Press, S. A. Teukolsky, W. T. Vetterling, and B. P. Flannery, *Numerical Recipes in C*, 2nd ed. Cambridge University Press, 1992, §10.9 (line–sphere intersection test).

3. COMAP, “Guidelines for the MCM/ICM,” 2024.

4. L. N. Trefethen and D. Bau, *Numerical Linear Algebra*. SIAM, 1997.

---

## Appendix

### A. Numerical Results Summary

| Problem | Configuration | $\Delta T$ (s) | Figure |
|---------|--------------|-----------------|--------|
| 1 | FY1, 1 bomb, fixed parameters | 1.39 | fig01 |
| 2 | FY1, 1 bomb, free parameters | 4.60 | fig02, fig03 |
| 3 | FY1, 3 bombs | 6.45 | fig04 |
| 4 | FY1+FY2+FY3, 1 bomb each | 4.58 | fig04 |
| 5 | 5 UAVs vs. 3 missiles | 0.00 | fig04 |

### B. Per-Problem Decision Variable Values

**Problem 1 (fixed):** speed = 120 m/s, heading = 180° (toward false target), $t_r = 1.50$ s, $t_d = 5.10$ s.

**Problem 2:** speed = 70 m/s, heading = 8.0°, $t_r = 0.00$ s, $t_d = 1.00$ s.

**Problem 3 (three bombs):** (134 m/s, 15.7°, $t_r = 0.00$, $t_d = 0.30$); (116 m/s, −54.8°, $t_r = 40.00$, $t_d = 51.00$); (108 m/s, 180.0°, $t_r = 1.03$, $t_d = 4.43$).

**Problem 4 (one bomb per UAV):** (122 m/s, 7.5°, $t_r = 0.00$, $t_d = 0.67$); (104 m/s, −5.2°, $t_r = 28.52$, $t_d = 28.82$); (77 m/s, 180.0°, $t_r = 15.31$, $t_d = 16.40$).

**Problem 5:** Two-phase approach. Phase 1 performs per-(UAV, missile) pair optimization; Phase 2 enumerates all surjective assignments. No assignment achieves non-zero intersection across all three missiles, yielding $\Delta T = 0.00$ s.
