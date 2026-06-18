"""
Module: MCM 2024 E Traffic Control — Complete Solution
Description:
  Implements 4 algorithms for the 2024 MCM E problem:
    Algorithm 1: Time Period Partitioning (Contiguity-Constrained Clustering + PELT)
    Algorithm 2: Signal Timing Optimization (Webster + GA Green Wave)
    Algorithm 3: Cruising Vehicle Identification & Parking Demand
    Algorithm 4: Control Effect Evaluation (Pre-Post Comparison with Holiday Separation)
Author: Coding Expert Agent
Date: 2026-05-30
"""

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist, pdist, squareform
from scipy.stats import t as t_dist, chi2
from scipy.cluster.hierarchy import ward, fcluster
from collections import defaultdict, Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import FancyBboxPatch
import warnings
import os
import json

warnings.filterwarnings('ignore')

# ============================================================
# Global Settings
# ============================================================
np.random.seed(42)

# Plotting style: academic, low-saturation colors
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 12,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'figure.facecolor': 'white',
})

# Color palettes (perceptually uniform, low saturation)
CMAP_DIVERGING = 'RdBu'
CMAP_SEQUENTIAL = 'viridis'
COLORS_QUAL = ['#4c72b0', '#dd8452', '#55a868', '#c44e52', '#8172b3',
               '#937860', '#da8bc3', '#8c8c8c', '#ccb974', '#64b5cd']

# ============================================================
# Physical & Traffic Constants
# ============================================================
INTERSECTIONS = list(range(1, 13))  # 12 intersections
N_INTERSECTIONS = 12

# Phase config: 4 phases per intersection
# Phase 1: N-S straight, Phase 2: N-S left, Phase 3: E-W straight, Phase 4: E-W left
PHASES = [1, 2, 3, 4]
N_PHASES = 4

# Directions index: 0=N, 1=S, 2=E, 3=W
DIR_NAMES = ['N', 'S', 'E', 'W']

# Saturation flow rate: 0.5 veh/s = 1800 veh/h
SAT_SATURATION = 0.5  # veh/s

# Loss time per phase (yellow 3s + all-red 2s + start loss 2s = 7s)
# Total loss per cycle: 4 phases * 7s = 28s
LOSS_PER_PHASE = 7.0  # s

# Timing bounds
C_MIN = 60   # s
C_MAX = 180  # s
G_MIN = 15   # s (pedestrian safety)
G_MAX_DEFAULT = 50  # s

# Road network
# Weizhong Road (纬中路): intersections 1-8, approx 700m per segment
# Jingzhong Road (经中路): intersections 9-12, approx 360m per segment
SEGMENT_LENGTHS = {
    (1, 2): 700, (2, 3): 700, (3, 4): 700, (4, 5): 700,
    (5, 6): 700, (6, 7): 700, (7, 8): 700,
    (9, 10): 360, (10, 11): 360, (11, 12): 360
}
# Adjacent intersections on the main road
MAIN_SEGMENTS = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8),
                 (9, 10), (10, 11), (11, 12)]
AVG_SEGMENT_LENGTH = 530.0  # m (weighted average)
TOTAL_ROAD_LENGTH = 5300.0  # m (5.3 km total)
FREE_FLOW_SPEED = 13.89  # m/s = 50 km/h

# Time window
DT = 15  # minutes per time window
N_WINDOWS = 96  # 24h * 60min / 15min

# Date parameters
DATE_START = '2024-04-01'
DATE_END = '2024-05-06'
N_DAYS = 36

# Output directory
OUTPUT_DIR = None  # Will be set in main()

# ============================================================
# Section 0: Data Generator (Synthetic)
# ============================================================

class TrafficDataGenerator:
    """Generate realistic synthetic traffic data for 2024 MCM E problem.

    Each record: (plate, timestamp, intersection_id, dir_in, dir_out)
    """

    def __init__(self, seed=42):
        self.rng = np.random.RandomState(seed)
        # Generate vehicle plates (simplified: integer IDs)
        self.vehicle_pool_size = 8000
        # Ground truth: plates injected with cruising patterns across all holiday days
        # (used for precision/recall/F1 validation, Fix C-20260530-004)
        self.all_cruising_plates = set()
        # Base traffic pattern parameters
        self._init_traffic_patterns()

    def _init_traffic_patterns(self):
        """Initialize base traffic flow patterns per intersection and direction."""
        # Traffic volume per 15min per direction for each intersection
        # Base volume varies by intersection (location), direction, and time of day
        self.base_volumes = {}
        for i in INTERSECTIONS:
            # Intersections on main roads have higher volume
            if i <= 8:  # Weizhong Road
                base = 40 + 10 * self.rng.randn()
                self.base_volumes[i] = max(20, base)
            else:  # Jingzhong Road
                base = 25 + 8 * self.rng.randn()
                self.base_volumes[i] = max(12, base)

        # Time-of-day pattern (scale factor for each 15-min window, [0, 2.5])
        self.tod_pattern = self._generate_tod_pattern()

    def _generate_tod_pattern(self):
        """Generate realistic time-of-day traffic pattern."""
        pattern = np.zeros(N_WINDOWS)
        # Morning peak: 7:00-9:00 (windows 28-36)
        # Evening peak: 17:00-19:00 (windows 68-76)
        # Night low: 0:00-5:00 (windows 0-20)
        for t in range(N_WINDOWS):
            hour = t * DT / 60
            if hour < 5:
                pattern[t] = 0.15 + 0.05 * self.rng.rand()
            elif hour < 7:
                pattern[t] = 0.3 + 0.1 * self.rng.rand()
            elif hour < 9:
                pattern[t] = 1.8 + 0.4 * self.rng.rand()  # morning peak
            elif hour < 12:
                pattern[t] = 1.0 + 0.15 * self.rng.rand()
            elif hour < 14:
                pattern[t] = 0.8 + 0.15 * self.rng.rand()
            elif hour < 17:
                pattern[t] = 1.0 + 0.15 * self.rng.rand()
            elif hour < 19:
                pattern[t] = 2.0 + 0.4 * self.rng.rand()  # evening peak
            elif hour < 21:
                pattern[t] = 0.9 + 0.15 * self.rng.rand()
            else:
                pattern[t] = 0.4 + 0.1 * self.rng.rand()
        return pattern

    def generate_day_data(self, date_str, date_type='weekday'):
        """Generate one day of traffic records.

        Args:
            date_str: Date string 'YYYY-MM-DD'
            date_type: 'weekday', 'weekend', or 'holiday'

        Returns:
            List of tuples (plate, timestamp, intersection_id, dir_in, dir_out)
        """
        records = []
        holiday_factor = 1.4 if date_type == 'holiday' else 1.0
        weekend_factor = 0.85 if date_type == 'weekend' else 1.0
        scaling = holiday_factor * weekend_factor

        for i in INTERSECTIONS:
            base_vol = self.base_volumes[i] * scaling
            for t_idx in range(N_WINDOWS):
                # Expected vehicles in this 15-min window at this intersection
                expected = base_vol * self.tod_pattern[t_idx]
                expected = max(0.5, expected)
                n_vehicles = self.rng.poisson(expected)

                minutes = t_idx * DT
                for _ in range(n_vehicles):
                    plate = self.rng.randint(1, self.vehicle_pool_size)
                    offset_sec = self.rng.randint(0, 59)
                    timestamp = f"{date_str}T{minutes//60:02d}:{minutes%60:02d}:{offset_sec:02d}"
                    dir_in = self.rng.choice(DIR_NAMES)
                    dir_out = self.rng.choice(DIR_NAMES)
                    records.append((plate, timestamp, i, dir_in, dir_out))
        return records

    def generate_cruising_vehicles(self, records, date_type='holiday'):
        """Inject cruising vehicle patterns into holiday data."""
        if date_type != 'holiday':
            return records

        cruising_plates = set(self.rng.choice(range(1, self.vehicle_pool_size),
                                              size=120, replace=False))
        # Store ground truth for precision/recall validation (Fix C-20260530-004)
        self.all_cruising_plates.update(cruising_plates)
        new_records = []
        plate_visits = defaultdict(list)

        for r in records:
            plate, ts_str, i, din, dout = r
            # Parse timestamp
            date_part, time_part = ts_str.split('T')
            h, m, s = time_part.split(':')
            ts_min = int(h) * 60 + int(m)
            plate_visits[plate].append((ts_min, i, din, dout))
            new_records.append(r)

        # For cruising vehicles, add extra loops (repeat visits within short time)
        for plate in cruising_plates:
            visits = plate_visits.get(plate, [])
            if len(visits) < 2:
                continue
            # Pick 30 cruising vehicles and add 3-5 extra loops within 30 min windows
            if self.rng.rand() < 0.25:
                base_visit = visits[0]
                t0, i0, din0, _ = base_visit
                for _ in range(self.rng.randint(2, 5)):
                    dt = self.rng.randint(5, 25)  # minutes later
                    t_new = t0 + dt
                    if t_new >= 1440:
                        break
                    i_new = max(1, min(12, i0 + self.rng.choice([-2, -1, 1, 2])))
                    ts_new = f"{date_part}T{t_new//60:02d}:{t_new%60:02d}:{self.rng.randint(0,59):02d}"
                    dout = self.rng.choice(DIR_NAMES)
                    new_records.append((plate, ts_new, i_new, din0, dout))
        return new_records

    def generate_full_dataset(self):
        """Generate the full 36-day dataset (2024-04-01 to 2024-05-06).

        Returns:
            pd.DataFrame with columns: plate, timestamp, intersection_id, dir_in, dir_out
        """
        all_records = []
        holidays = {1, 2, 3, 4, 5}  # May 1-5

        for day_offset in range(N_DAYS):
            from datetime import datetime, timedelta
            d = datetime(2024, 4, 1) + timedelta(days=day_offset)
            date_str = d.strftime('%Y-%m-%d')
            dow = d.weekday()  # 0=Monday

            if day_offset >= 30 and (day_offset - 29) in holidays:
                # May 1-5: holiday period
                date_type = 'holiday'
            elif dow < 5:
                date_type = 'weekday'
            else:
                date_type = 'weekend'

            day_records = self.generate_day_data(date_str, date_type)
            day_records = self.generate_cruising_vehicles(day_records, date_type)
            all_records.extend(day_records)

        df = pd.DataFrame(all_records,
                          columns=['plate', 'timestamp', 'intersection_id',
                                   'dir_in', 'dir_out'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df['time'] = df['timestamp'].dt.time
        # Add minute-of-day
        df['minute_of_day'] = (df['timestamp'].dt.hour * 60 +
                                df['timestamp'].dt.minute)
        df['window_15min'] = df['minute_of_day'] // 15
        # Direction indices
        dir_map = {'N': 0, 'S': 1, 'E': 2, 'W': 3}
        df['dir_in_idx'] = df['dir_in'].map(dir_map)
        df['dir_out_idx'] = df['dir_out'].map(dir_map)

        return df


# ============================================================
# Section 1: Data Preprocessing
# ============================================================

class DataPreprocessor:
    """Preprocess raw traffic records into feature matrices."""

    def __init__(self, df):
        self.df = df.copy()
        self.date_types = {}  # date -> type mapping

    def label_date_types(self):
        """Label each date as weekday, weekend, or holiday."""
        holidays = {5, 6, 7, 8, 9, 10}  # May 1-5 in day_offset (30 + offset)
        for day_offset in range(N_DAYS):
            from datetime import datetime, timedelta
            d = datetime(2024, 4, 1) + timedelta(days=day_offset)
            date_str = d.strftime('%Y-%m-%d')
            dow = d.weekday()
            if day_offset >= 30 and (day_offset - 29) in {1, 2, 3, 4, 5}:
                self.date_types[date_str] = 'holiday'
            elif dow < 5:
                self.date_types[date_str] = 'weekday'
            else:
                self.date_types[date_str] = 'weekend'
        return self

    def compute_phase_flow(self, dir_in, dir_out):
        """Map direction-in/out to phase index (0-11 for 12 traffic movements).

        Phase 0: N straight (in=N, out=S)
        Phase 1: N left    (in=N, out=E)
        Phase 2: N right   (in=N, out=W)
        Phase 3: S straight (in=S, out=N)
        Phase 4: S left    (in=S, out=W)
        Phase 5: S right   (in=S, out=E)
        Phase 6: E straight (in=E, out=W)
        Phase 7: E left    (in=E, out=N)
        Phase 8: E right   (in=E, out=S)
        Phase 9: W straight (in=W, out=E)
        Phase 10: W left   (in=W, out=S)
        Phase 11: W right  (in=W, out=N)

        Signal phases:
          Phase 1 (南北直行): N→S (0) + S→N (3)
          Phase 2 (南北左转): N→E (1) + S→W (4)
          Phase 3 (东西直行): E→W (6) + W→E (9)
          Phase 4 (东西左转): E→N (7) + W→S (10)
        """
        dir_map = {'N': 0, 'S': 1, 'E': 2, 'W': 3}
        din = dir_map.get(dir_in, -1)
        dout = dir_map.get(dir_out, -1)
        if din == -1 or dout == -1:
            return -1, -1

        # Movement index: 0-11
        if din == 0:  # N
            if dout == 1: mv = 0
            elif dout == 2: mv = 1
            elif dout == 3: mv = 2
            else: mv = -1
        elif din == 1:  # S
            if dout == 0: mv = 3
            elif dout == 3: mv = 4
            elif dout == 2: mv = 5
            else: mv = -1
        elif din == 2:  # E
            if dout == 3: mv = 6
            elif dout == 0: mv = 7
            elif dout == 1: mv = 8
            else: mv = -1
        elif din == 3:  # W
            if dout == 2: mv = 9
            elif dout == 1: mv = 10
            elif dout == 0: mv = 11
            else: mv = -1
        else:
            mv = -1

        # Signal phase mapping:
        signal_phase_map = {0: 1, 3: 1, 1: 2, 4: 2, 6: 3, 9: 3, 7: 4, 10: 4,
                            2: -1, 5: -1, 8: -1, 11: -1}  # right turns not controlled
        sp = signal_phase_map.get(mv, -1)
        return mv, sp

    def aggregate_flow_by_type(self):
        """Compute average 15-min flow by date type.

        Returns:
            dict: {date_type: np.array of shape (N_WINDOWS, 12)}
              where 12 = 12 movement features
        """
        self.label_date_types()
        df = self.df.copy()
        df['date_str'] = df['date'].astype(str)
        df['date_type'] = df['date_str'].map(self.date_types)

        # Handle missing date types (5月6日 = post_period without holiday)
        df.loc[df['date_str'] >= '2024-05-06', 'date_type'] = 'post_control'

        result = {}
        for dtype in ['weekday', 'weekend', 'holiday']:
            sub = df[df['date_type'] == dtype]
            if len(sub) == 0:
                result[dtype] = np.zeros((N_WINDOWS, 12))
                continue
            # Get unique dates
            dates = sub['date_str'].unique()
            n_dates = len(dates)
            flow_array = np.zeros((n_dates, N_WINDOWS, 12))

            for idx, date_str in enumerate(dates):
                day_data = sub[sub['date_str'] == date_str]
                for t in range(N_WINDOWS):
                    window_data = day_data[day_data['window_15min'] == t]
                    for _, row in window_data.iterrows():
                        mv, sp = self.compute_phase_flow(row['dir_in'], row['dir_out'])
                        if mv >= 0:
                            flow_array[idx, t, mv] += 1

            # Average over dates
            result[dtype] = flow_array.mean(axis=0)

        return result

    def get_daily_flow(self, intersection_id=None):
        """Get per-day, per-window flow for one or all intersections.

        Returns:
            pd.DataFrame with columns: date, window_15min, intersection_id, flow
        """
        df = self.df.copy()
        df['date_str'] = df['date'].astype(str)
        if intersection_id is not None:
            df = df[df['intersection_id'] == intersection_id]

        daily = df.groupby(['date_str', 'window_15min', 'intersection_id']).size().reset_index()
        daily.columns = ['date', 'window_15min', 'intersection_id', 'flow']
        return daily


# ============================================================
# Section 2: Algorithm 1 — Time Period Partitioning
# ============================================================

class TimePeriodPartitioner:
    """Algorithm 1: Time period partitioning with contiguity-constrained
    hierarchical clustering (Scheme A) and PELT Bayesian change point
    detection (Scheme B), with consistency verification."""

    def __init__(self, flow_data):
        """flow_data: dict {date_type: np.array (N_WINDOWS, n_features)}"""
        self.flow_data = flow_data
        self.n_windows = N_WINDOWS
        self.n_features = 12

    # ---- Scheme A: Contiguity-Constrained Hierarchical Clustering ----

    def _ward_delta(self, c1, c2):
        """Compute Ward's delta SSE for merging clusters c1 and c2."""
        n1 = len(c1)
        n2 = len(c2)
        mean1 = np.mean(c1, axis=0)
        mean2 = np.mean(c2, axis=0)
        return n1 * n2 / (n1 + n2) * np.sum((mean1 - mean2) ** 2)

    def contiguity_clustering(self, X, max_clusters=8):
        """Perform contiguity-constrained hierarchical clustering.

        Args:
            X: np.array (n_windows, n_features)
            max_clusters: maximum number of clusters to consider

        Returns:
            dict: {n_clusters: cluster_labels} for each K
        """
        n = len(X)
        # Initial: each window as its own cluster
        clusters = [[i] for i in range(n)]
        # Track merge history for Dunn index computation
        merge_history = []
        labels_history = {}
        labels_history[n] = np.arange(n)

        # For scipy's Ward linkage (contiguity is enforced by adjacency constraint)
        # We use a modified approach: only adjacent clusters can merge
        current_indices = list(range(n))

        for step in range(n - max_clusters + 1):
            best_delta = np.inf
            best_pair = None

            # Only consider adjacent clusters
            for j in range(len(clusters) - 1):
                c1 = clusters[j]
                c2 = clusters[j + 1]
                delta = self._ward_delta(X[c1], X[c2])
                if delta < best_delta:
                    best_delta = delta
                    best_pair = j

            # Merge best pair
            if best_pair is not None:
                merged = clusters[best_pair] + clusters[best_pair + 1]
                clusters = (clusters[:best_pair] +
                            [merged] +
                            clusters[best_pair + 2:])
                merge_history.append((best_pair, best_pair + 1, best_delta))

            n_clusters = len(clusters)
            if n_clusters <= max_clusters:
                labels = np.zeros(n, dtype=int)
                for cid, members in enumerate(clusters):
                    for m in members:
                        labels[m] = cid
                labels_history[n_clusters] = labels

        return labels_history, merge_history, clusters

    def _dunn_index(self, X, labels):
        """Compute Dunn index for cluster validation.

        Dunn = min_intercluster_dist / max_intracluster_diameter
        """
        n_clusters = len(np.unique(labels))
        if n_clusters <= 1:
            return 0

        # Intra-cluster diameters (max distance within each cluster)
        diameters = []
        for k in range(n_clusters):
            members = np.where(labels == k)[0]
            if len(members) <= 1:
                diameters.append(0)
            else:
                d = cdist(X[members], X[members], metric='euclidean')
                diameters.append(np.max(d))

        max_diameter = max(diameters)
        if max_diameter == 0:
            return 0

        # Inter-cluster distances (min distance between clusters)
        min_inter = np.inf
        for k1 in range(n_clusters):
            for k2 in range(k1 + 1, n_clusters):
                m1 = np.where(labels == k1)[0]
                m2 = np.where(labels == k2)[0]
                d = cdist(X[m1], X[m2], metric='euclidean')
                min_inter = min(min_inter, np.min(d))

        return min_inter / max_diameter if max_diameter > 0 else 0

    def scheme_a_fit(self, X):
        """Scheme A: contiguity-constrained clustering with Dunn index optimization."""
        labels_history, merge_history, clusters = self.contiguity_clustering(X)

        dunn_scores = []
        k_range = range(2, min(9, len(clusters) + 1))
        for K in k_range:
            if K in labels_history:
                dunn = self._dunn_index(X, labels_history[K])
                dunn_scores.append((K, dunn))

        if not dunn_scores:
            return 2, labels_history[2]

        # Optimal K by max Dunn index
        dunn_scores.sort(key=lambda x: x[1], reverse=True)
        K_opt = dunn_scores[0][0]

        # Create final labels: contiguous segments
        labels = labels_history[K_opt]
        # Compute breakpoints (indices where label changes)
        breakpoints = []
        for t in range(1, len(labels)):
            if labels[t] != labels[t - 1]:
                breakpoints.append(t)

        return K_opt, labels, breakpoints, dunn_scores

    # ---- Scheme B: PELT Bayesian Change Point Detection ----

    def _segment_neg_log_likelihood(self, X, start, end, mu_global=None,
                                     sigma_global=None):
        """Compute negative log-likelihood for segment X[start:end+1].

        Uses multivariate normal with shared covariance (across segments)
        and segment-specific mean.
        """
        segment = X[start:end + 1]
        n = len(segment)
        if n == 0:
            return 0

        # Segment mean
        mu_seg = np.mean(segment, axis=0)

        # Negative log-likelihood (up to constant)
        if sigma_global is not None and mu_global is not None:
            # Center the data
            centered = segment - mu_seg
            try:
                # Use pseudo-determinant for numerical stability
                sign, logdet = np.linalg.slogdet(sigma_global)
                if sign <= 0:
                    # Fall back to diagonal approximation
                    var_diag = np.diag(sigma_global)
                    var_diag = np.maximum(var_diag, 1e-10)
                    logdet = np.sum(np.log(var_diag))
                    inv_sigma = np.diag(1.0 / var_diag)
                else:
                    inv_sigma = np.linalg.inv(sigma_global)

                # Mahalanobis distance
                quad_form = np.sum((centered @ inv_sigma) * centered, axis=1)
                nll = 0.5 * n * (12 * np.log(2 * np.pi) + logdet) + 0.5 * np.sum(quad_form)
            except np.linalg.LinAlgError:
                # Fallback: independent dimensions
                var_diag = np.var(segment, axis=0) + 1e-10
                nll = 0.5 * n * np.sum(np.log(2 * np.pi * var_diag)) + \
                      0.5 * n * 12
            return nll
        else:
            # Without covariance: sum of per-dimension variance
            var_diag = np.var(segment, axis=0) + 1e-10
            nll = 0.5 * n * np.sum(np.log(2 * np.pi * var_diag)) + 0.5 * n * 12
            return nll

    def _estimate_shared_covariance(self, X, breakpoints):
        """Estimate shared covariance matrix from data, adjusting for segment means.

        Args:
            X: full data matrix (n_windows, n_features)
            breakpoints: list of change point indices

        Returns:
            Covariance matrix (n_features, n_features)
        """
        segments = []
        starts = [0] + breakpoints
        ends = breakpoints + [len(X)]
        for s, e in zip(starts, ends):
            if e > s:
                segment = X[s:e]
                segments.append(segment)

        # Pooled within-segment covariance
        all_centered = []
        for seg in segments:
            mu = np.mean(seg, axis=0)
            all_centered.append(seg - mu)

        if all_centered:
            pooled = np.vstack(all_centered)
            n = len(pooled)
            if n > 1:
                cov = np.cov(pooled, rowvar=False)
            else:
                cov = np.eye(12) * 1.0
        else:
            cov = np.eye(12) * 1.0

        # Regularize for numerical stability
        cov = 0.9 * cov + 0.1 * np.eye(12) * np.trace(cov) / 12
        return cov

    def pelt_changepoint_detection(self, X, penalty=0.5 * np.log(N_WINDOWS) * 12,
                                    initial_bp=None):
        """PELT (Pruned Exact Linear Time) change point detection.

        Args:
            X: data matrix (n_windows, n_features)
            penalty: BIC penalty term (0.5 * ln(N) * 12 due to shared covariance)

        Returns:
            breakpoints: list of change point indices
        """
        n = len(X)

        # Get initial breakpoints from Scheme A (contiguity clustering) for
        # reliable within-segment pooled covariance estimation. This avoids the
        # inflation bias of global-mean-centering when true change points exist.
        # NOTE: mu_full is always defined (even when not used in the pooled
        # estimate) because _segment_neg_log_likelihood requires it as a
        # guard parameter, though the actual centering uses segment-specific means.
        mu_full = np.mean(X, axis=0)
        if initial_bp is not None and len(initial_bp) > 0:
            sigma_full = self._estimate_shared_covariance(X, initial_bp)
        else:
            # Fallback: use global mean centering only if no initial breakpoints
            centered_full = X - mu_full
            sigma_full = np.cov(centered_full, rowvar=False)
            sigma_full = 0.9 * sigma_full + 0.1 * np.eye(12) * np.trace(sigma_full) / 12

        # PELT algorithm
        # F[t] = min_{s < t} {F[s] + cost(x_{s+1:t}) + penalty}
        F = np.zeros(n + 1)
        F[0] = 0
        # Store the optimal last change point for each position
        last_cp = np.zeros(n + 1, dtype=int)

        # Candidates set (indices of candidate last change points)
        R = [0]

        for t in range(1, n + 1):
            # Compute F[t] as min over candidates
            best_val = np.inf
            best_s = None

            for s in R:
                if s >= t:
                    continue
                cost = self._segment_neg_log_likelihood(X, s, t - 1,
                                                         mu_full, sigma_full)
                val = F[s] + cost + penalty
                if val < best_val:
                    best_val = val
                    best_s = s

            F[t] = best_val
            last_cp[t] = best_s

            # Pruning: remove indices that can never be optimal in the future
            # For PELT: if F[s] + cost(x_{s+1:t}) >= F[t], then s is dominated
            new_R = [0]  # Always keep 0
            for s in R:
                if s >= t:
                    continue
                # Check if s is still a candidate for future steps
                # Simplified: keep all, but enforce termination
                if s == best_s or s == 0:
                    new_R.append(s)
            R = sorted(set(new_R + [t]))

            # Limit R size for performance
            if len(R) > 50:
                R = R[-50:]

        # Backtrack to find breakpoints
        breakpoints = []
        cp = last_cp[n]
        while cp > 0:
            breakpoints.append(cp)
            cp = last_cp[cp]
        breakpoints.reverse()

        return breakpoints

    def scheme_b_fit(self, X, initial_bp=None):
        """Scheme B: PELT Bayesian change point detection.

        Args:
            X: data matrix (n_windows, n_features)
            initial_bp: initial breakpoints from Scheme A for shared covariance estimation

        Returns:
            K_opt: optimal number of segments
            breakpoints: list of change point indices
        """
        # PELT with shared covariance (pooled within-segment via initial_bp)
        breakpoints = self.pelt_changepoint_detection(X, initial_bp=initial_bp)

        # Deduplicate very close breakpoints (within 2 windows)
        if len(breakpoints) > 1:
            filtered = [breakpoints[0]]
            for bp in breakpoints[1:]:
                if bp - filtered[-1] > 2:
                    filtered.append(bp)
            breakpoints = filtered

        K_opt = len(breakpoints) + 1
        return K_opt, breakpoints

    def _segment_labels_from_breakpoints(self, breakpoints, n):
        """Convert breakpoints to segment labels."""
        labels = np.zeros(n, dtype=int)
        seg_id = 0
        bp_ext = [0] + breakpoints + [n]
        for idx in range(len(bp_ext) - 1):
            labels[bp_ext[idx]:bp_ext[idx + 1]] = seg_id
            seg_id += 1
        return labels

    def consistency_verification(self, bp_a, bp_b):
        """Verify consistency between Scheme A and Scheme B.

        If max deviation <= 2 windows, take mean as final breakpoints.
        Otherwise, mark as high uncertainty, take mean with ±1 error band.
        """
        # Align breakpoints (may differ in number)
        if len(bp_a) == 0 and len(bp_b) == 0:
            return [], 0.0, 'consistent'

        if len(bp_a) == 0:
            return bp_b, 0.0, 'consistent'
        if len(bp_b) == 0:
            return bp_a, 0.0, 'consistent'

        # Use the smaller set as reference
        if len(bp_a) <= len(bp_b):
            ref, cmp = bp_a, bp_b
        else:
            ref, cmp = bp_b, bp_a

        # For each reference bp, find the closest in cmp
        deviations = []
        aligned = []
        used = set()
        for bp in ref:
            distances = [abs(bp - c) for c in cmp]
            sorted_idx = np.argsort(distances)
            for idx in sorted_idx:
                if idx not in used:
                    deviations.append(distances[idx])
                    aligned.append((bp, cmp[idx]))
                    used.add(idx)
                    break

        if not deviations:
            return ref, 0.0, 'consistent'

        max_dev = max(deviations)
        # Take mean
        final_bp = sorted([int(round((a + b) / 2)) for a, b in aligned])

        if max_dev <= 2:
            return final_bp, max_dev, 'consistent'
        else:
            return final_bp, max_dev, 'high_uncertainty'

    def fit(self, date_type='weekday'):
        """Full Algorithm 1 pipeline for a given date type.

        Args:
            date_type: 'weekday', 'weekend', or 'holiday'

        Returns:
            dict with keys: K, breakpoints, labels, consistency_status
        """
        X = self.flow_data[date_type]

        # Scheme A
        K_a, labels_a, bp_a, dunn_scores = self.scheme_a_fit(X)

        # Scheme B — uses Scheme A breakpoints for pooled within-segment
        # covariance estimation (avoids global-mean-centering bias, Fix C-20260530-001)
        K_b, bp_b = self.scheme_b_fit(X, initial_bp=bp_a)

        # Consistency verification
        final_bp, max_dev, status = self.consistency_verification(bp_a, bp_b)
        final_labels = self._segment_labels_from_breakpoints(final_bp, len(X))
        K_final = len(final_bp) + 1

        return {
            'date_type': date_type,
            'K_opt': K_final,
            'breakpoints': final_bp,
            'labels': final_labels,
            'bp_scheme_a': bp_a,
            'bp_scheme_b': bp_b,
            'K_scheme_a': K_a,
            'K_scheme_b': K_b,
            'max_deviation': max_dev,
            'consistency_status': status,
            'dunn_scores': dunn_scores,
        }


# ============================================================
# Section 3: Bayesian Turning Probability Estimation
# ============================================================

class TurningProbabilityEstimator:
    """Estimate turning probabilities using Dirichlet-Multinomial Bayesian model.

    To handle small-sample issues, uses a Dirichlet prior with strength kappa=30
    from full-day MLE, then updates with period-specific counts.
    """

    def __init__(self, df, kappa=30, min_samples=5):
        self.df = df.copy()
        self.kappa = kappa  # Prior strength coefficient
        self.min_samples = min_samples  # Min sample count gate
        self.dir_map = {'N': 0, 'S': 1, 'E': 2, 'W': 3}

    def _compute_prior(self, intersection_id):
        """Compute Dirichlet prior from full-day data."""
        sub = self.df[self.df['intersection_id'] == intersection_id]
        # For each incoming direction, count outgoing directions
        alpha_prior = {}
        for din in DIR_NAMES:
            counts = np.ones(4) * 0.5  # Jeffreys prior base
            din_data = sub[sub['dir_in'] == din]
            for _, row in din_data.iterrows():
                dout = row['dir_out']
                dout_idx = self.dir_map[dout]
                counts[dout_idx] += 1

            # Normalize to get MLE proportions, then scale by kappa
            total = counts.sum()
            prop = counts / total
            alpha_prior[din] = self.kappa * prop

        return alpha_prior

    def estimate_by_period(self, intersection_id, period_labels):
        """Estimate turning probabilities for each time period.

        Args:
            intersection_id: intersection index
            period_labels: array of length N_WINDOWS, period label for each window

        Returns:
            dict: {period_id: {dir_in: {dir_out: prob}}}
        """
        # Get full prior
        alpha_prior = self._compute_prior(intersection_id)

        sub = self.df[self.df['intersection_id'] == intersection_id]
        sub = sub.copy()
        sub['window'] = sub['minute_of_day'] // 15
        sub['period'] = sub['window'].map(
            lambda w: period_labels[w] if w < len(period_labels) else period_labels[-1])

        n_periods = len(np.unique(period_labels))
        result = {}

        for p in range(n_periods):
            pdata = sub[sub['period'] == p]
            period_probs = {}
            for din in DIR_NAMES:
                din_data = pdata[pdata['dir_in'] == din]
                n_obs = len(din_data)
                dout_counts = np.zeros(4)
                for _, row in din_data.iterrows():
                    dout_idx = self.dir_map[row['dir_out']]
                    dout_counts[dout_idx] += 1

                small_sample = n_obs < self.min_samples
                if small_sample:
                    # Merge with adjacent period's counts
                    # (simplified: just use prior + current counts)
                    pass

                # Posterior = prior + counts
                alpha_post = alpha_prior[din] + dout_counts
                theta_post = alpha_post / alpha_post.sum()

                period_probs[din] = {
                    dout_dir: theta_post[idx]
                    for idx, dout_dir in enumerate(DIR_NAMES)
                }
            result[p] = period_probs

        return result


# ============================================================
# Section 4: Algorithm 2 — Signal Timing Optimization
# ============================================================

class SignalTimingOptimizer:
    """Algorithm 2: Signal timing optimization with Webster + GA green wave.

    Layer 1 (lower): Modified Webster with 'base-load then remainder' allocation.
    Layer 2 (upper): GA optimizing common cycle C_0 and offsets for green wave.
    """

    def __init__(self, flow_by_period, n_intersections=N_INTERSECTIONS,
                 n_phases=N_PHASES, g_min=G_MIN, g_max=G_MAX_DEFAULT,
                 c_min=C_MIN, c_max=C_MAX, loss_per_phase=LOSS_PER_PHASE,
                 sat_flow=SAT_SATURATION):
        """
        Args:
            flow_by_period: dict {period_id: {i: {phase: arrival_rate (veh/s)}}}
        """
        self.flow = flow_by_period
        self.n_int = n_intersections
        self.n_phases = n_phases
        self.g_min = g_min
        self.g_max = g_max
        self.c_min = c_min
        self.c_max = c_max
        self.loss_per_phase = loss_per_phase
        self.sat_flow = sat_flow
        self.n_periods = len(flow_by_period)

    def webster_optimal_cycle(self, i, period=0):
        """Compute Webster optimal cycle for one intersection.

        For Y_i >= 0.9, return C_max as Webster formula degenerates.

        Returns:
            dict: C_opt, Y_i, feasibility flag
        """
        flow_i = self.flow[period][i]
        y_vals = []
        for ph in PHASES:
            lam = flow_i.get(ph, 0.01)
            y = lam / self.sat_flow
            y_vals.append(y)

        Y_i = sum(y_vals)
        L_i = self.n_phases * self.loss_per_phase

        if Y_i >= 0.9:
            # Saturation: use max cycle
            C_opt = self.c_max
        else:
            C_opt = (1.5 * L_i + 5) / (1 - Y_i)
            C_opt = max(self.c_min, min(self.c_max, C_opt))

        # Feasibility check: sum(g_min) <= C_opt - L_i
        g_avail = C_opt - L_i
        feasible = (self.n_phases * self.g_min) <= g_avail
        if not feasible:
            C_opt = max(C_opt, self.n_phases * self.g_min + L_i)

        return {
            'C_opt': C_opt,
            'Y_i': Y_i,
            'y_vals': y_vals,
            'L_i': L_i,
            'feasible': feasible
        }

    def allocate_green(self, C_0, i, period=0):
        """Allocate green times using 'base-load then remainder' procedure.

        This is the REFACTORED procedure that eliminates the residual<0 bug.
        Natural guarantee: sum(g) = C_0 - L_i and each g_j >= g_min.

        Args:
            C_0: common cycle time (s)
            i: intersection index (1-based)
            period: period index

        Returns:
            dict: {phase: green_time} or None if infeasible
        """
        flow_i = self.flow[period][i]
        L_i = self.n_phases * self.loss_per_phase
        G_avail = C_0 - L_i

        # Step 2: Feasibility check
        total_g_min = self.n_phases * self.g_min
        if total_g_min > G_avail:
            return None  # Infeasible

        # Step 3: Allocate min green base load
        g = {ph: self.g_min for ph in PHASES}

        # Step 4: Compute remaining time (guaranteed >= 0 by check above)
        G_rem = G_avail - total_g_min

        # Step 5: Allocate remaining by flow ratio
        y_vals = {}
        for ph in PHASES:
            lam = flow_i.get(ph, 0.01)
            y_vals[ph] = lam / self.sat_flow
        Y_i = sum(y_vals.values())

        if Y_i > 0:
            for ph in PHASES:
                extra = G_rem * (y_vals[ph] / Y_i)
                g[ph] += extra

        # Step 6: Handle g_max overflow (iterative redistribution)
        max_iter = 10
        for iteration in range(max_iter):
            overflow_phases = [ph for ph in PHASES if g[ph] > self.g_max]
            if not overflow_phases:
                break

            excess_total = sum(g[ph] - self.g_max for ph in overflow_phases)
            for ph in overflow_phases:
                g[ph] = self.g_max

            # Redistribute to under-max phases
            under_max = [ph for ph in PHASES if g[ph] < self.g_max]
            if not under_max:
                # All phases at g_max: proportionally scale down so sum(g) = G_avail.
                # This avoids leaving the solution in an infeasible state
                # (Fix C-20260530-002).
                total_at_max = sum(g.values())
                scale_factor = G_avail / total_at_max
                for ph in PHASES:
                    g[ph] *= scale_factor
                break

            y_under = sum(y_vals[ph] for ph in under_max)
            if y_under > 0:
                for ph in under_max:
                    g[ph] += excess_total * (y_vals[ph] / y_under)

        # Verify constraints
        total_g = sum(g.values())
        assert abs(total_g - G_avail) < 1e-4, \
            f"Total green {total_g:.2f} != G_avail {G_avail:.2f}"
        for ph in PHASES:
            assert g[ph] >= self.g_min - 1e-4, \
                f"Phase {ph} green {g[ph]:.2f} < g_min {self.g_min}"

        return g

    def webster_delay(self, C_0, g_j, lam_j):
        """Compute Webster delay for one phase.

        d = C_0 * (1 - g/C_0)^2 / (2 * (1 - lam/S_sat))
        """
        green_ratio = g_j / C_0
        denominator = 2 * (1 - lam_j / self.sat_flow)
        if denominator <= 0:
            return 1e6  # Very large delay for saturated approach
        delay = C_0 * (1 - green_ratio) ** 2 / denominator
        return max(0, delay)

    def compute_avg_speed(self, C_0, offsets, period=0):
        """Compute average speed for a given (C_0, offsets) configuration.

        Uses critical phase delay as proxy (see mathematical model 2.5 for
        surrogate objective justification).

        Args:
            C_0: common cycle time (s)
            offsets: list of offsets between consecutive intersections
            period: period index

        Returns:
            avg_speed (km/h), total_delay (s), feasible (bool)
        """
        total_delay = 0.0
        feasible = True

        for i in INTERSECTIONS:
            g_result = self.allocate_green(C_0, i, period)
            if g_result is None:
                feasible = False
                break

            flow_i = self.flow[period][i]
            # Critical phase: phase with highest flow ratio
            y_vals = {}
            for ph in PHASES:
                lam = flow_i.get(ph, 0.01)
                y_vals[ph] = lam / self.sat_flow
            critical_phase = max(y_vals, key=y_vals.get)

            g_j = g_result[critical_phase]
            lam_j = flow_i.get(critical_phase, 0.01)
            delay = self.webster_delay(C_0, g_j, lam_j)
            total_delay += delay

        if not feasible:
            return -1e9, 1e9, False

        # Travel time = sum(L/v_free) + total delay
        travel_time_free = TOTAL_ROAD_LENGTH / FREE_FLOW_SPEED  # seconds
        total_time = travel_time_free + total_delay
        avg_speed = TOTAL_ROAD_LENGTH / max(total_time, 1e-6) * 3.6  # m/s -> km/h

        return avg_speed, total_delay, True

    # ---- GA for Green Wave Coordination ----

    def ga_optimize(self, period=0, pop_size=50, n_generations=200,
                    crossover_rate=0.8, mutation_rate=0.1, elite_ratio=0.1,
                    tournament_size=3):
        """GA optimization for common cycle and offsets.

        Chromosome: [C_0, delta_1, delta_2, ..., delta_11] (12 dimensions)
          C_0 in [C_low, C_high]
          delta_i in [0, C_0)

        Fitness: average speed (km/h), with hard penalty (-1e9) for infeasible.

        Args:
            pop_size: population size
            n_generations: number of generations
            crossover_rate: SBX crossover probability
            mutation_rate: polynomial mutation probability
            elite_ratio: fraction of elites to preserve

        Returns:
            dict with keys: best_chrom, best_fitness, history, C_0, offsets, greens
        """
        # Determine cycle range from individual intersections
        C_low = self.c_min
        C_high = self.c_max
        for i in INTERSECTIONS:
            web = self.webster_optimal_cycle(i, period)
            C_low = max(C_low, web['C_opt'] * 0.8)
            C_high = min(C_high, web['C_opt'] * 1.2)
        C_low = max(self.c_min, C_low)
        C_high = min(self.c_max, C_high)
        C_low = min(C_low, C_high)

        n_dim = 12  # C_0 + 11 offsets

        def initialize_population():
            """Initialize with heuristic: use Webster cycles as base."""
            pop = np.zeros((pop_size, n_dim))
            # Base individual: use average Webster C_0, even offsets
            avg_C = (C_low + C_high) / 2
            base = np.zeros(n_dim)
            base[0] = avg_C
            for j in range(1, n_dim):
                # Offsets based on segment length and desired speed
                if j <= 7:
                    seg_len = 700
                else:
                    seg_len = 360
                # Travel time based offset: seg_len / v_des
                v_des = 11.11  # m/s (~40 km/h desired wave speed)
                travel_time = seg_len / v_des
                # Offset within [0, C_0): travel_time mod C_0
                base[j] = travel_time % avg_C

            # Population around base with noise
            for idx in range(pop_size):
                noise = np.random.randn(n_dim) * 5
                chrom = base + noise
                chrom[0] = np.clip(chrom[0], C_low, C_high)
                chrom[1:] = np.abs(chrom[1:]) % chrom[0]
                pop[idx] = chrom

            # Inject one individual near Webster optimal
            pop[0] = base.copy()
            return pop

        def decode(chrom):
            """Decode chromosome to C_0 and offsets."""
            C_0 = np.clip(chrom[0], C_low, C_high)
            offsets = np.abs(chrom[1:]) % C_0
            return C_0, offsets

        def evaluate_population(pop):
            """Evaluate all individuals and return fitness."""
            fitness = np.zeros(pop_size)
            n_feasible = 0
            for idx in range(pop_size):
                C_0, offsets = decode(pop[idx])
                speed, delay, feasible = self.compute_avg_speed(C_0, offsets, period)
                if feasible:
                    # Slight regularization: prefer lower C_0 when speed similar
                    fitness[idx] = speed - 0.01 * (C_0 - C_low) / (C_high - C_low)
                    n_feasible += 1
                else:
                    fitness[idx] = -1e9  # Hard penalty
            return fitness

        def tournament_selection(fitness):
            """Tournament selection."""
            selected = np.zeros(pop_size, dtype=int)
            for idx in range(pop_size):
                contestants = np.random.choice(pop_size, tournament_size, replace=False)
                winner = contestants[np.argmax(fitness[contestants])]
                selected[idx] = winner
            return selected

        def sbx_crossover(parent1, parent2, eta=20):
            """Simulated Binary Crossover."""
            child1 = parent1.copy()
            child2 = parent2.copy()
            for j in range(n_dim):
                if np.random.rand() < crossover_rate:
                    u = np.random.rand()
                    if u <= 0.5:
                        beta = (2 * u) ** (1 / (eta + 1))
                    else:
                        beta = (1 / (2 * (1 - u))) ** (1 / (eta + 1))
                    child1[j] = 0.5 * ((1 + beta) * parent1[j] + (1 - beta) * parent2[j])
                    child2[j] = 0.5 * ((1 - beta) * parent1[j] + (1 + beta) * parent2[j])
            return child1, child2

        def polynomial_mutation(child, eta=20):
            """Polynomial mutation."""
            for j in range(n_dim):
                if np.random.rand() < mutation_rate:
                    u = np.random.rand()
                    if j == 0:
                        lb, ub = C_low, C_high
                    else:
                        lb, ub = 0, child[0]  # offset in [0, C_0)
                    delta = min(child[j] - lb, ub - child[j]) / (ub - lb)
                    if u <= 0.5:
                        delta_q = (2 * u + (1 - 2 * u) * (1 - delta) ** (eta + 1)) ** (1 / (eta + 1)) - 1
                    else:
                        delta_q = 1 - (2 * (1 - u) + 2 * (u - 0.5) * (1 - delta) ** (eta + 1)) ** (1 / (eta + 1))
                    child[j] += delta_q * (ub - lb)
                    child[j] = np.clip(child[j], lb, ub)
            return child

        # Main GA loop
        pop = initialize_population()
        best_fitness_history = []
        mean_fitness_history = []
        best_chrom_overall = None
        best_fitness_overall = -1e9

        n_elite = max(1, int(pop_size * elite_ratio))

        for gen in range(n_generations):
            fitness = evaluate_population(pop)

            # Track best
            best_idx = np.argmax(fitness)
            if fitness[best_idx] > best_fitness_overall:
                best_fitness_overall = fitness[best_idx]
                best_chrom_overall = pop[best_idx].copy()

            best_fitness_history.append(fitness[best_idx])
            feasible_fitness = fitness[fitness > -1e8]
            mean_fitness_history.append(
                np.mean(feasible_fitness) if len(feasible_fitness) > 0 else -1e9)

            # Selection
            selected_idx = tournament_selection(fitness)
            new_pop = []

            # Elite preservation
            elite_idx = np.argsort(fitness)[-n_elite:]
            for idx in elite_idx:
                new_pop.append(pop[idx].copy())

            # Crossover and mutation
            while len(new_pop) < pop_size:
                parents_idx = np.random.choice(selected_idx, 2, replace=False)
                p1, p2 = pop[parents_idx[0]], pop[parents_idx[1]]
                c1, c2 = sbx_crossover(p1, p2)
                c1 = polynomial_mutation(c1)
                c2 = polynomial_mutation(c2)
                # Encode constraints
                c1[0] = np.clip(c1[0], C_low, C_high)
                c2[0] = np.clip(c2[0], C_low, C_high)
                for j in range(1, n_dim):
                    c1[j] = np.abs(c1[j]) % c1[0]
                    c2[j] = np.abs(c2[j]) % c2[0]
                new_pop.append(c1)
                if len(new_pop) < pop_size:
                    new_pop.append(c2)

            pop = np.array(new_pop[:pop_size])

        # Decode best solution
        C_0_best, offsets_best = decode(best_chrom_overall)

        # Get green times for best solution
        greens_best = {}
        for i in INTERSECTIONS:
            g = self.allocate_green(C_0_best, i, period)
            greens_best[i] = g

        return {
            'C_0': C_0_best,
            'offsets': offsets_best,
            'greens': greens_best,
            'best_fitness': best_fitness_overall,
            'fitness_history': best_fitness_history,
            'mean_fitness_history': mean_fitness_history,
            'C_range': (C_low, C_high),
        }


# ============================================================
# Section 5: Algorithm 3 — Cruising Vehicle Identification
# ============================================================

class CruisingVehicleDetector:
    """Algorithm 3: Cruising vehicle identification and parking demand estimation.

    Features:
      1. Spatial-temporal repeat count N_repeat
      2. Average travel speed v_avg
      3. Direction entropy H (Shannon entropy of movement directions)

    Cruise(m) = I(N_repeat >= 3 AND v_avg <= 5 km/h AND H >= H_threshold)
    """

    def __init__(self, df, d_segment=AVG_SEGMENT_LENGTH, v_max=5.0,
                 n_threshold=3, tau_match=30):
        """
        Args:
            df: DataFrame with traffic records
            d_segment: average segment length (m)
            v_max: max speed for cruising (km/h)
            n_threshold: min repeat count for cruising
            tau_match: matching time window (min)
        """
        self.df = df.copy()
        self.d_segment = d_segment
        self.v_max = v_max  # km/h
        self.n_threshold = n_threshold
        self.tau_match = tau_match  # minutes

        # Direction index map
        self.dir_to_idx = {'N': 0, 'S': 1, 'E': 2, 'W': 3}
        self.idx_to_dir = {0: 'N', 1: 'S', 2: 'E', 3: 'W'}

    def _manhattan_dist(self, i1, i2):
        """Topological distance between intersections (index difference)."""
        return abs(i1 - i2)

    def _reconstruct_trajectories(self, date_filter=None):
        """Reconstruct vehicle trajectories from records.

        Args:
            date_filter: optional date filter string

        Returns:
            dict: {plate: [(timestamp, intersection, dir_in, dir_out), ...]}
        """
        df = self.df.copy()
        if date_filter is not None:
            df = df[df['date'].astype(str) == date_filter]

        # Sort by plate, then timestamp
        df = df.sort_values(['plate', 'timestamp'])
        trajectories = defaultdict(list)

        for _, row in df.iterrows():
            ts = row['timestamp']
            trajectories[row['plate']].append((
                ts, row['intersection_id'],
                row['dir_in'], row['dir_out']
            ))

        return dict(trajectories)

    def detect_side_entries(self, trajectories):
        """Detect side entry/exit events and compute trajectory break ratio.

        SideEntryExit: vehicle disappears at non-neighboring intersection
        and reappears within tau_match.
        """
        break_events = 0
        total_segments = 0
        break_details = []

        for plate, traj in trajectories.items():
            if len(traj) < 2:
                continue

            for k in range(len(traj) - 1):
                total_segments += 1
                i_curr = traj[k][1]
                i_next = traj[k + 1][1]
                dist = self._manhattan_dist(i_curr, i_next)

                time_diff = (traj[k + 1][0] - traj[k][0]).total_seconds()

                # Normal drive time at 1.5x free flow
                normal_drive_time = dist * self.d_segment / (FREE_FLOW_SPEED * 1.5)

                if (dist > 1 and
                        normal_drive_time < time_diff < self.tau_match * 60):
                    break_events += 1
                    break_details.append({
                        'plate': plate,
                        'from_intersection': i_curr,
                        'to_intersection': i_next,
                        'time_diff_sec': time_diff,
                        'dist': dist,
                    })

        r_break = break_events / max(total_segments, 1)
        return r_break, break_events, total_segments, break_details

    def compute_features(self, trajectories):
        """Compute cruising features for each vehicle.

        Returns:
            dict: {plate: {n_repeat, v_avg, H, n_moves, traj_len}}
        """
        features = {}
        tau_sec = self.tau_match * 60

        for plate, traj in trajectories.items():
            if len(traj) < 3:
                continue

            traj_ts = [t[0] for t in traj]
            traj_int = [t[1] for t in traj]
            traj_dout = [t[3] for t in traj]

            # 1. Repeat count: max number of visits within tau window
            n_repeat = 0
            for anchor_idx in range(len(traj)):
                count = 0
                for q_idx in range(len(traj)):
                    dt = abs((traj_ts[q_idx] - traj_ts[anchor_idx]).total_seconds())
                    di = self._manhattan_dist(traj_int[q_idx], traj_int[anchor_idx])
                    if dt <= tau_sec and di <= 2:
                        count += 1
                n_repeat = max(n_repeat, count)

            # 2. Average speed
            if len(traj) >= 2:
                total_dist = 0
                for k in range(len(traj) - 1):
                    total_dist += self._manhattan_dist(traj_int[k], traj_int[k + 1]) * self.d_segment
                total_time = (traj_ts[-1] - traj_ts[0]).total_seconds()
                v_avg = (total_dist / max(total_time, 1)) * 3.6  # m/s -> km/h
            else:
                v_avg = 60.0

            # 3. Direction entropy
            dir_counts = np.zeros(4)
            for dout in traj_dout:
                idx = self.dir_to_idx.get(dout, -1)
                if idx >= 0:
                    dir_counts[idx] += 1
            probs = dir_counts / max(dir_counts.sum(), 1)
            probs = probs[probs > 0]
            H = -np.sum(probs * np.log(probs)) if len(probs) > 0 else 0

            features[plate] = {
                'n_repeat': n_repeat,
                'v_avg': v_avg,
                'H': H,
                'n_moves': len(traj),
                'first_ts': traj_ts[0],
                'last_ts': traj_ts[-1],
            }

        return features

    def compute_h_threshold(self, features, non_cruise_features=None):
        """Compute H_threshold using dual-baseline method.

        Baseline A: 90th percentile of H during non-holiday period
        Baseline B: 90th percentile of H among non-cruising vehicles during holiday
        Final: weighted average
        """
        if non_cruise_features is not None:
            h_values_a = [f['H'] for f in non_cruise_features.values()]
        else:
            h_values_a = [f['H'] for f in features.values()]

        h_values_b = [f['H'] for f in features.values()]

        H_A = np.percentile(h_values_a, 90) if len(h_values_a) > 0 else 1.0
        H_B = np.percentile(h_values_b, 90) if len(h_values_b) > 0 else 1.0

        # If baselines differ by more than 20%, use the larger value
        if max(H_A, H_B) > 0 and abs(H_A - H_B) / max(H_A, H_B) > 0.2:
            H_threshold = max(H_A, H_B)
        else:
            w = 0.5  # Equal weight
            H_threshold = w * H_A + (1 - w) * H_B

        return H_threshold, H_A, H_B

    def classify_cruising(self, features, H_threshold):
        """Classify vehicles as cruising.

        Cruise(m) = I(N_repeat >= 3 AND v_avg <= 5 km/h AND H >= H_threshold)
        """
        cruising = {}
        for plate, feat in features.items():
            is_cruising = (feat['n_repeat'] >= self.n_threshold and
                           feat['v_avg'] <= self.v_max and
                           feat['H'] >= H_threshold)
            if is_cruising:
                cruising[plate] = feat
        return cruising

    def estimate_parking_demand(self, cruising_times, r_break=0.0,
                                 mu_occ=0.75, rho=4.0):
        """Estimate parking space demand.

        Conservative (with side-entry correction):
          P = ceil(Q_95(N_cruise(t)) * mu_occ / rho * (1 + r_break))

        Optimistic (without correction):
          P = ceil(Q_95(N_cruise(t)) * mu_occ / rho)
        """
        if len(cruising_times) == 0:
            return 0, 0

        n_windows = N_WINDOWS
        cruise_count = np.zeros(n_windows)

        for plate, info in cruising_times.items():
            first_min = info['first_ts'].hour * 60 + info['first_ts'].minute
            last_min = info['last_ts'].hour * 60 + info['last_ts'].minute
            w_first = max(0, first_min // 15)
            w_last = min(n_windows - 1, last_min // 15)
            for w in range(w_first, w_last + 1):
                cruise_count[w] += 1

        Q95 = np.percentile(cruise_count, 95) if cruise_count.max() > 0 else 0

        demand_conservative = int(np.ceil(Q95 * mu_occ / rho * (1 + r_break)))
        demand_optimistic = int(np.ceil(Q95 * mu_occ / rho))

        return demand_conservative, demand_optimistic, cruise_count, Q95

    def sensitivity_analysis(self, holiday_dates=None, mu_range=None, rho_range=None):
        """Run sensitivity analysis for tau_match, mu_occ, and rho."""
        if holiday_dates is None:
            holiday_dates = ['2024-05-01', '2024-05-02', '2024-05-03',
                             '2024-05-04', '2024-05-05']

        if mu_range is None:
            mu_range = [0.25, 0.5, 0.75, 1.0, 1.5]
        if rho_range is None:
            rho_range = [2, 4, 6, 8]

        # Filter holiday data
        df_holiday = self.df[self.df['date'].astype(str).isin(holiday_dates)]

        # ---- tau_match sensitivity ----
        tau_values = [15, 30, 45, 60]
        tau_results = {}
        for tau in tau_values:
            detector = CruisingVehicleDetector(
                df_holiday, self.d_segment, self.v_max,
                self.n_threshold, tau
            )
            trajs = detector._reconstruct_trajectories()
            r_break, _, _, _ = detector.detect_side_entries(trajs)
            feats = detector.compute_features(trajs)
            H_th, _, _ = detector.compute_h_threshold(feats)
            cruising = detector.classify_cruising(feats, H_th)
            d_cons, d_opt, _, _ = detector.estimate_parking_demand(
                cruising, r_break)
            tau_results[tau] = {
                'r_break': r_break,
                'n_cruising': len(cruising),
                'demand_conservative': d_cons,
                'demand_optimistic': d_opt,
            }

        # Compute CV for tau sensitivity
        if len(tau_results) > 1:
            demands = [v['demand_conservative'] for v in tau_results.values()]
            cv = np.std(demands) / max(np.mean(demands), 1)
        else:
            cv = 0

        # ---- mu_occ, rho sensitivity ----
        # Use tau=30 as default
        detector = CruisingVehicleDetector(
            df_holiday, self.d_segment, self.v_max,
            self.n_threshold, 30
        )
        trajs = detector._reconstruct_trajectories()
        r_break, _, _, _ = detector.detect_side_entries(trajs)
        feats = detector.compute_features(trajs)
        H_th, _, _ = detector.compute_h_threshold(feats)
        cruising = detector.classify_cruising(feats, H_th)
        _, _, cruise_counts, Q95 = detector.estimate_parking_demand(cruising, r_break)

        param_matrix = np.zeros((len(mu_range), len(rho_range)))
        for mi, mu in enumerate(mu_range):
            for ri, rho in enumerate(rho_range):
                d_cons = int(np.ceil(Q95 * mu / rho * (1 + r_break)))
                param_matrix[mi, ri] = d_cons

        return {
            'tau_sensitivity': tau_results,
            'tau_cv': cv,
            'param_matrix': param_matrix,
            'mu_range': mu_range,
            'rho_range': rho_range,
            'Q95': Q95,
            'r_break': r_break,
            'n_cruising': len(cruising),
            'n_cruising_list': list(cruising.keys()),
            'H_threshold': H_th,
        }


# ============================================================
# Section 6: Algorithm 4 — Control Effect Evaluation
# ============================================================

class ControlEffectEvaluator:
    """Algorithm 4: Control effect evaluation using pre-post comparison
    with holiday effect separation.

    Model: Y_it = beta_0 + beta_3 * Post_t + gamma * Holiday_t
                 + sum(delta_d * Weekday_d) + epsilon_it

    Key identification: beta_3 (net control effect) and gamma (holiday effect)
    are separable because May 6 (Post=1, Holiday=0) provides identifying variation.
    """

    def __init__(self, df):
        self.df = df.copy()
        self._label_periods()

    def _label_periods(self):
        """Label Post_t, Holiday_t, and Weekday_d for each record."""
        df = self.df.copy()
        df['date_str'] = df['date'].astype(str)

        # Post_t: May 1 - May 6 (control period)
        # Holiday_t: May 1 - May 5 (holiday period)
        # May 6: Post=1, Holiday=0 (key identifying variation)
        holiday_dates = {'2024-05-01', '2024-05-02', '2024-05-03',
                         '2024-05-04', '2024-05-05'}
        control_dates = {'2024-05-01', '2024-05-02', '2024-05-03',
                         '2024-05-04', '2024-05-05', '2024-05-06'}

        df['Post'] = df['date_str'].isin(control_dates).astype(int)
        df['Holiday'] = df['date_str'].isin(holiday_dates).astype(int)
        # Weekday: 1=Monday ... 7=Sunday
        df['Weekday'] = pd.to_datetime(df['date_str']).dt.dayofweek + 1

        self.df_labeled = df

    def compute_daily_metrics(self):
        """Compute daily metrics per intersection.

        Metrics:
          - avg_speed: average speed proxy (km/h) based on travel time
          - total_flow: total traffic volume (veh/day)
          - waiting_time: average waiting time proxy (s/veh)

        Returns:
            pd.DataFrame with columns:
              date, intersection_id, avg_speed, total_flow, waiting_time,
              Post, Holiday, Weekday
        """
        df = self.df_labeled

        # Compute metrics per intersection per day
        daily = df.groupby(['date_str', 'date', 'intersection_id']).agg(
            total_flow=('plate', 'count'),
            Post=('Post', 'first'),
            Holiday=('Holiday', 'first'),
            Weekday=('Weekday', 'first'),
        ).reset_index()

        # Average speed proxy: use distance between records
        # For each intersection-day, compute approximate speed from time between records
        speed_proxies = []
        for (date_str, i), group in df.groupby(['date_str', 'intersection_id']):
            if len(group) < 2:
                speed_proxies.append({'date_str': date_str, 'intersection_id': i,
                                       'avg_speed': 30.0, 'waiting_time': 30.0})
                continue
            group = group.sort_values('timestamp')
            time_diffs = group['timestamp'].diff().dt.total_seconds().dropna()
            # Filter out long gaps (>30 min)
            time_diffs = time_diffs[time_diffs < 1800]
            if len(time_diffs) > 0:
                # Speed proxy: assume avg 500m between consecutive records
                avg_time = np.mean(time_diffs)
                speed = 500 / max(avg_time, 1) * 3.6  # m/s -> km/h
                # Cap at reasonable values
                speed = min(max(speed, 5), 80)
                # Waiting time proxy: inverse of speed
                wait = 3600 / max(speed, 5)  # seconds per km
            else:
                speed = 30.0
                wait = 60.0
            speed_proxies.append({'date_str': date_str, 'intersection_id': i,
                                   'avg_speed': speed, 'waiting_time': wait})

        speed_df = pd.DataFrame(speed_proxies)
        daily = daily.merge(speed_df, on=['date_str', 'intersection_id'])

        return daily

    @staticmethod
    def _ols_estimation(X, y):
        """Compute OLS estimates: beta = (X'X)^{-1} X'y

        Returns beta, residuals, XtX_inv
        """
        n, k = X.shape
        XtX = X.T @ X
        try:
            XtX_inv = np.linalg.inv(XtX)
        except np.linalg.LinAlgError:
            XtX_inv = np.linalg.pinv(XtX)
        beta = XtX_inv @ X.T @ y
        residuals = y - X @ beta
        return beta, residuals, XtX_inv

    @staticmethod
    def _cluster_robust_se(X, residuals, cluster_ids, XtX_inv):
        """Compute cluster-robust standard errors (Liang-Zeger, 1986).

        Var(beta) = (X'X)^{-1} @ (sum X_i' u_i u_i' X_i) @ (X'X)^{-1}
        """
        unique_clusters = np.unique(cluster_ids)
        n, k = X.shape

        meat = np.zeros((k, k))
        for cid in unique_clusters:
            mask = cluster_ids == cid
            X_c = X[mask]
            u_c = residuals[mask]
            if len(u_c) > 0:
                contribution = X_c.T @ np.outer(u_c, u_c) @ X_c
                meat += contribution

        # Small sample correction: G/(G-1) * (N-1)/(N-k)
        G = len(unique_clusters)
        correction = G / max(G - 1, 1) * (n - 1) / max(n - k, 1)
        vcov = XtX_inv @ meat @ XtX_inv * correction
        se = np.sqrt(np.diag(vcov))
        return se, vcov

    def pre_post_regression(self, daily_metrics, dependent_var='avg_speed'):
        """Run pre-post comparison regression with holiday effect separation.

        Model: Y = beta_0 + beta_3 * Post + gamma * Holiday
                  + sum(delta_d * Weekday_d) + epsilon

        Returns:
            dict with all regression results
        """
        df = daily_metrics.copy()
        # Ensure Post is 0 for pre-period, 1 for control period
        # Holiday is 1 for May 1-5

        # Design matrix
        # Columns: [Intercept, Post, Holiday, Weekday_2, ..., Weekday_7]
        n = len(df)
        weekday_dummies = pd.get_dummies(df['Weekday'], prefix='W', drop_first=True)

        X = np.column_stack([
            np.ones(n),
            df['Post'].values,
            df['Holiday'].values,
            weekday_dummies.values,
        ])
        y = df[dependent_var].values

        # Column names for reference
        col_names = ['Intercept', 'Post', 'Holiday'] + \
                     [f'W{d}' for d in range(2, 8)]

        # OLS
        beta, residuals, XtX_inv = self._ols_estimation(X, y)

        # Cluster-robust SE (by intersection)
        cluster_ids = df['intersection_id'].values
        se, vcov = self._cluster_robust_se(X, residuals, cluster_ids, XtX_inv)

        # t-stats and p-values
        t_stats = beta / np.maximum(se, 1e-10)
        df_residual = n - X.shape[1]
        p_values = 2 * (1 - t_dist.cdf(np.abs(t_stats), df=df_residual))

        # 95% CI
        ci_lower = beta - t_dist.ppf(0.975, df_residual) * se
        ci_upper = beta + t_dist.ppf(0.975, df_residual) * se

        # Named results
        results = {}
        for idx, name in enumerate(col_names):
            results[name] = {
                'coef': beta[idx],
                'se': se[idx],
                't_stat': t_stats[idx],
                'p_value': p_values[idx],
                'ci_95_lower': ci_lower[idx],
                'ci_95_upper': ci_upper[idx],
            }

        # R-squared
        y_pred = X @ beta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / max(ss_tot, 1e-10)
        adj_r_squared = 1 - (1 - r_squared) * (n - 1) / max(n - X.shape[1], 1)

        return {
            'results': results,
            'beta': beta,
            'se': se,
            'p_values': p_values,
            'r_squared': r_squared,
            'adj_r_squared': adj_r_squared,
            'n_obs': n,
            'n_clusters': len(np.unique(cluster_ids)),
            'col_names': col_names,
            'residuals': residuals,
            'y_pred': y_pred,
            'dependent_var': dependent_var,
        }

    def event_study(self, daily_metrics, dependent_var='avg_speed'):
        """Dynamic event study for parallel trend test.

        Model: Y = beta_0 + sum(alpha_tau * I(tau before)) +
                    sum(beta_tau * I(tau after)) + gamma * Holiday +
                    delta * Weekday + epsilon

        tau=0 is April 30 (reference). tau<0 are pre-period indicators.
        """
        df = daily_metrics.copy()
        df['date_str'] = df['date'].astype(str)
        df['date_obj'] = pd.to_datetime(df['date_str'])
        ref_date = pd.to_datetime('2024-04-30')

        # Compute days relative to reference
        df['days_from_ref'] = (df['date_obj'] - ref_date).dt.days

        # Pre-period indicators: -7 to -1 (relative to Apr 30)
        # Post-period indicators: +1 to +5 (May 1 to May 5) + May 6+
        time_periods = list(range(-7, 6))  # -7 to +5

        # Create indicators
        df_event = df.copy()
        for tau in time_periods:
            df_event[f'T_{tau}'] = (df_event['days_from_ref'] == tau).astype(int)

        # Design matrix
        base_cols = ['Intercept', 'Holiday']
        event_cols = [f'T_{tau}' for tau in time_periods if tau != 0]  # exclude reference
        weekday_dummies = pd.get_dummies(df_event['Weekday'], prefix='W', drop_first=True)

        X_cols = ['Intercept'] + event_cols + ['Holiday'] + \
                 [c for c in weekday_dummies.columns]
        X = np.column_stack([
            np.ones(len(df_event)),
            df_event[[c for c in event_cols]].values,
            df_event['Holiday'].values,
            weekday_dummies.values,
        ])
        y = df_event[dependent_var].values

        # OLS
        beta, residuals, XtX_inv = self._ols_estimation(X, y)
        cluster_ids = df_event['intersection_id'].values
        se, vcov = self._cluster_robust_se(X, residuals, cluster_ids, XtX_inv)

        # Collect event study coefficients
        event_study_coefs = {}
        for idx, col in enumerate(X_cols):
            if col.startswith('T_'):
                tau = int(col.split('_')[1])
                event_study_coefs[tau] = {
                    'coef': beta[idx],
                    'se': se[idx],
                    'ci_lower': beta[idx] - 1.96 * se[idx],
                    'ci_upper': beta[idx] + 1.96 * se[idx],
                }

        # Parallel trend test: H0 — all pre-period coefficients are jointly zero.
        # Uses a Wald (chi-squared) test instead of the invalid averaged t-statistic
        # (Fix C-20260530-003).
        #
        # Wald statistic: W = beta_pre' * V_pre^{-1} * beta_pre  ~  chi2(q)
        # where q = number of pre-treatment periods.
        pre_taus = sorted([tau for tau in time_periods
                           if tau < 0 and tau in event_study_coefs])
        if len(pre_taus) > 0:
            # Locate pre-period coefficient indices in the full beta vector
            pre_indices = [idx for idx, col in enumerate(X_cols)
                           if col.startswith('T_')
                           and int(col.split('_')[1]) < 0]
            beta_pre = beta[pre_indices]
            V_pre = vcov[np.ix_(pre_indices, pre_indices)]

            # Regularize for numerical stability
            V_pre_reg = V_pre + np.eye(len(pre_indices)) * 1e-10
            try:
                V_pre_inv = np.linalg.inv(V_pre_reg)
            except np.linalg.LinAlgError:
                V_pre_inv = np.linalg.pinv(V_pre_reg)

            wald_stat = beta_pre @ V_pre_inv @ beta_pre
            q = len(pre_taus)
            parallel_p = 1 - chi2.cdf(wald_stat, df=q)
            parallel_trend = parallel_p > 0.05
        else:
            parallel_p = 1.0
            parallel_trend = True

        return {
            'event_study_coefs': event_study_coefs,
            'parallel_trend': parallel_trend,
            'parallel_p_value': parallel_p,
            'n_pre_periods': len(pre_taus),
        }

    @staticmethod
    def cohens_d(mean1, mean2, std1, std2, n1, n2):
        """Compute Cohen's d and pooled standard deviation."""
        pooled_std = np.sqrt(((n1 - 1) * std1 ** 2 + (n2 - 1) * std2 ** 2) /
                              max(n1 + n2 - 2, 1))
        if pooled_std == 0:
            return 0, 1.0
        d = (mean1 - mean2) / pooled_std
        return d, pooled_std

    def comprehensive_evaluation(self, daily_metrics):
        """Full evaluation: regression, event study, Cohen's d scores.

        Returns:
            dict with all results
        """
        # 1. Pre-post regression for each metric
        metrics = ['avg_speed', 'total_flow', 'waiting_time']
        regression_results = {}
        for metric in metrics:
            regression_results[metric] = self.pre_post_regression(
                daily_metrics, metric)

        # 2. Event study for avg_speed
        event_study_result = self.event_study(daily_metrics, 'avg_speed')

        # 3. Cohen's d per intersection
        df = daily_metrics.copy()
        pre_data = df[df['Post'] == 0]
        post_data = df[df['Post'] == 1]

        cohen_scores = {}
        for i in INTERSECTIONS:
            pre_i = pre_data[pre_data['intersection_id'] == i]
            post_i = post_data[post_data['intersection_id'] == i]

            scores = {}
            for metric in metrics:
                pre_vals = pre_i[metric].values
                post_vals = post_i[metric].values
                if len(pre_vals) < 2 or len(post_vals) < 2:
                    scores[metric] = {'d': 0, 'pooled_std': 1.0}
                    continue
                d, pooled_std = self.cohens_d(
                    np.mean(post_vals), np.mean(pre_vals),
                    np.std(post_vals, ddof=1), np.std(pre_vals, ddof=1),
                    len(post_vals), len(pre_vals)
                )
                # For flow and waiting time, negative change is improvement
                if metric == 'avg_speed':
                    pass  # Positive d = improvement
                else:
                    d = -d  # Sign flip: reduction = improvement
                scores[metric] = {'d': d, 'pooled_std': pooled_std}

            cohen_scores[i] = scores

        # 4. AHP weights (simplified: traffic engineers prioritize speed > flow > wait)
        # Judgment matrix A, CR = CI/RI < 0.1
        # A = [[1, 3, 2], [1/3, 1, 1/2], [1/2, 2, 1]]
        # Eigenvector: w = [0.539, 0.164, 0.297]
        # lambda_max = 3.009, CI = 0.005, RI = 0.58, CR = 0.008 < 0.1
        ahp_weights = {'avg_speed': 0.539, 'total_flow': 0.164, 'waiting_time': 0.297}

        # 5. Comprehensive scores
        comprehensive_scores = {}
        for i in INTERSECTIONS:
            S = 0
            for metric in metrics:
                S += ahp_weights[metric] * cohen_scores[i][metric]['d']
            comprehensive_scores[i] = S

        return {
            'regression': regression_results,
            'event_study': event_study_result,
            'cohen_scores': cohen_scores,
            'ahp_weights': ahp_weights,
            'comprehensive_scores': comprehensive_scores,
        }


# ============================================================
# Section 7: Visualization Module
# ============================================================

class Visualizer:
    """Generate all plots for the MCM 2024 E solution."""

    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_flow_heatmap(self, flow_by_type, partition_result, date_type='weekday'):
        """Plot 12-dimensional flow heatmap with period boundaries."""
        X = flow_by_type[date_type]
        labels = partition_result['labels']
        bp = partition_result['breakpoints']

        fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
        movements = [
            ('N', [0, 1, 2]), ('S', [3, 4, 5]),
            ('E+W', [6, 7, 8, 9, 10, 11])
        ]
        movement_labels = [
            ['N-str', 'N-L', 'N-R'],
            ['S-str', 'S-L', 'S-R'],
            ['E-str', 'E-L', 'E-R', 'W-str', 'W-L', 'W-R']
        ]

        for ax_idx, (title, mv_idx) in enumerate(movements):
            ax = axes[ax_idx]
            data = X[:, mv_idx].T
            im = ax.imshow(data, aspect='auto', cmap=CMAP_SEQUENTIAL,
                           interpolation='nearest')
            ax.set_ylabel('Movement')
            ax.set_yticks(range(len(mv_idx)))
            ax.set_yticklabels(movement_labels[ax_idx], fontsize=8)

            # Period boundaries
            for b in bp:
                ax.axvline(x=b - 0.5, color='red', linewidth=1.5, linestyle='--',
                           alpha=0.7)

            # Period labels at top
            if ax_idx == 0:
                unique_labels = np.unique(labels)
                for lbl in unique_labels:
                    indices = np.where(labels == lbl)[0]
                    if len(indices) > 0:
                        mid = indices[len(indices) // 2]
                        ax.text(mid, -1.5, f'P{lbl + 1}',
                                ha='center', va='bottom', fontsize=9,
                                fontweight='bold', color='#c44e52')

            ax.set_title(f'{title} direction movements')
            plt.colorbar(im, ax=ax, label='Flow (veh/15min)', shrink=0.8)

        axes[-1].set_xlabel('Time window (15 min)')
        axes[-1].set_xticks(range(0, 96, 8))
        axes[-1].set_xticklabels([f'{h:02d}:00' for h in range(0, 24, 2)])
        fig.suptitle(f'Traffic Flow Heatmap — {date_type.capitalize()} '
                     f'(K={partition_result["K_opt"]})',
                     fontsize=14, y=1.01)

        plt.tight_layout()
        path = os.path.join(self.output_dir, f'fig1_flow_heatmap_{date_type}.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_dunn_scores(self, dunn_scores, date_type='weekday'):
        """Plot Dunn index for cluster selection."""
        fig, ax = plt.subplots(figsize=(8, 5))
        ks = [s[0] for s in dunn_scores]
        ds = [s[1] for s in dunn_scores]
        ax.plot(ks, ds, 'o-', color=COLORS_QUAL[0], linewidth=2, markersize=8)
        best_k = ks[np.argmax(ds)]
        ax.axvline(x=best_k, color=COLORS_QUAL[3], linestyle='--', alpha=0.7,
                   label=f'Optimal K={best_k}')
        ax.set_xlabel('Number of clusters (K)')
        ax.set_ylabel('Dunn index')
        ax.set_title(f'Dunn Index for Cluster Selection — {date_type.capitalize()}')
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        path = os.path.join(self.output_dir, f'fig2_dunn_index_{date_type}.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_period_comparison(self, partition_results):
        """Compare period partitions across date types."""
        fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
        date_types = ['weekday', 'weekend', 'holiday']

        for ax_idx, dtype in enumerate(date_types):
            ax = axes[ax_idx]
            result = partition_results[dtype]
            bp = result['breakpoints']
            labels = result['labels']

            # Plot segments as colored blocks
            for t in range(len(labels)):
                ax.axvspan(t, t + 1, alpha=0.3,
                           color=plt.cm.tab10(labels[t] % 10))

            for b in bp:
                ax.axvline(x=b, color='black', linewidth=1.5, linestyle='-')

            ax.set_ylabel(f'{dtype.capitalize()}')
            ax.set_yticks([])
            ax.text(-2, 0.5, f'K={result["K_opt"]}', ha='right', va='center',
                    fontsize=10, fontweight='bold')
            ax.set_xlim(0, 96)

        axes[-1].set_xlabel('Time window (15 min)')
        axes[-1].set_xticks(range(0, 96, 8))
        axes[-1].set_xticklabels([f'{h:02d}:00' for h in range(0, 24, 2)])
        fig.suptitle('Time Period Partitioning by Date Type', fontsize=14)
        plt.tight_layout()
        path = os.path.join(self.output_dir, 'fig3_period_comparison.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_ga_convergence(self, history_dict):
        """Plot GA convergence curves."""
        fig, ax = plt.subplots(figsize=(10, 5))
        for label, history in history_dict.items():
            ax.plot(history, label=label, linewidth=1.5, alpha=0.8)
        ax.set_xlabel('Generation')
        ax.set_ylabel('Average speed (km/h)')
        ax.set_title('GA Optimization Convergence')
        ax.legend(loc='lower right')
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        path = os.path.join(self.output_dir, 'fig4_ga_convergence.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_green_wave_diagram(self, C_0, offsets, greens, period_name='peak'):
        """Plot green wave time-distance diagram."""
        fig, ax = plt.subplots(figsize=(12, 8))

        # Plot each intersection's green band
        y_positions = {}
        for idx, i in enumerate(INTERSECTIONS):
            y = idx
            y_positions[i] = y

            if greens and i in greens and greens[i] is not None:
                g_times = greens[i]
                for ph in PHASES:
                    g = g_times.get(ph, 0)
                    if g <= 0:
                        continue
                    # Phase 1 (N-S straight) as the main green band
                    if ph == 1:
                        rect = FancyBboxPatch(
                            (0, y - 0.3), g, 0.6,
                            boxstyle="round,pad=0.02",
                            facecolor=COLORS_QUAL[0], alpha=0.7,
                            edgecolor='none')
                        ax.add_patch(rect)
                        # Also show the next cycles
                        for cyc in range(1, 4):
                            rect2 = FancyBboxPatch(
                                (cyc * C_0 + g, y - 0.3), g, 0.6,
                                boxstyle="round,pad=0.02",
                                facecolor=COLORS_QUAL[0], alpha=0.4,
                                edgecolor='none')
                            ax.add_patch(rect2)

        # Plot offset lines
        cumulative_offset = 0
        for idx, i in enumerate(INTERSECTIONS):
            y = y_positions[i]
            if offsets is not None and idx < len(offsets):
                cumulative_offset += offsets[idx]
            else:
                cumulative_offset = 0
            # Mark center of green band at each intersection
            ax.plot(cumulative_offset % C_0, y, 'v', color=COLORS_QUAL[3],
                    markersize=10, zorder=5)

        # Green wave progression line
        t_start = 0
        wave_points = [(t_start, y_positions[1])]
        for idx, (i1, i2) in enumerate(MAIN_SEGMENTS):
            if offsets is not None and idx < len(offsets):
                t_start += offsets[idx]
            wave_points.append((t_start % (C_0 * 2), y_positions[i2]))
        wave_t, wave_y = zip(*wave_points)
        ax.plot(wave_t, wave_y, '-', color=COLORS_QUAL[1], linewidth=2,
                alpha=0.6, label='Green wave progression')

        ax.set_xlabel(f'Time (s), Cycle C0={C_0:.0f}s')
        ax.set_ylabel('Intersection')
        ax.set_yticks(range(N_INTERSECTIONS))
        ax.set_yticklabels([f'#{i}' for i in INTERSECTIONS])
        ax.set_title(f'Green Wave Time-Distance Diagram — {period_name}')

        # Cycle boundary lines
        for cyc in range(5):
            ax.axvline(x=cyc * C_0, color='gray', linewidth=0.5, linestyle=':',
                       alpha=0.5)
        ax.legend(loc='upper right')
        ax.set_xlim(0, C_0 * 2)
        plt.tight_layout()
        path = os.path.join(self.output_dir,
                            f'fig5_green_wave_{period_name}.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_cruising_stats(self, cruising_result):
        """Plot cruising vehicle statistics and sensitivity analysis."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Subplot 1: Tau sensitivity
        ax1 = axes[0, 0]
        tau_results = cruising_result['tau_sensitivity']
        taus = list(tau_results.keys())
        cons_demands = [tau_results[t]['demand_conservative'] for t in taus]
        opt_demands = [tau_results[t]['demand_optimistic'] for t in taus]
        break_rates = [tau_results[t]['r_break'] * 100 for t in taus]

        ax1.plot(taus, cons_demands, 'o-', color=COLORS_QUAL[0], linewidth=2,
                 markersize=8, label='Conservative')
        ax1.plot(taus, opt_demands, 's--', color=COLORS_QUAL[1], linewidth=2,
                 markersize=8, label='Optimistic')
        ax1_2 = ax1.twinx()
        ax1_2.plot(taus, break_rates, '^:', color=COLORS_QUAL[3], linewidth=2,
                   markersize=8, label='Break ratio %')
        ax1_2.set_ylabel('Trajectory break ratio (%)', color=COLORS_QUAL[3])
        ax1_2.tick_params(axis='y', labelcolor=COLORS_QUAL[3])
        ax1.set_xlabel('Matching window τ (min)')
        ax1.set_ylabel('Parking demand (spaces)')
        ax1.set_title('τ-match Sensitivity Analysis')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        # Subplot 2: Parameter sensitivity heatmap
        ax2 = axes[0, 1]
        param_matrix = cruising_result['param_matrix']
        mu_range = cruising_result['mu_range']
        rho_range = cruising_result['rho_range']
        im = ax2.imshow(param_matrix, aspect='auto', cmap=CMAP_SEQUENTIAL)
        ax2.set_xticks(range(len(rho_range)))
        ax2.set_xticklabels([str(r) for r in rho_range])
        ax2.set_yticks(range(len(mu_range)))
        ax2.set_yticklabels([str(mu) for mu in mu_range])
        ax2.set_xlabel('Turnover rate ρ (times/day)')
        ax2.set_ylabel('Avg parking time μ_occ (h)')
        ax2.set_title('Parking Demand Sensitivity\n(μ_occ × ρ)')
        plt.colorbar(im, ax=ax2, label='Parking spaces', shrink=0.8)
        # Annotate cells
        for mi in range(len(mu_range)):
            for ri in range(len(rho_range)):
                ax2.text(ri, mi, f'{int(param_matrix[mi, ri])}',
                         ha='center', va='center', fontsize=8,
                         color='white' if param_matrix[mi, ri] > np.median(param_matrix)
                         else 'black')

        # Subplot 3: Cruising time series
        ax3 = axes[1, 0]
        cruise_counts = cruising_result.get('cruise_counts', None)
        if cruise_counts is not None:
            ax3.plot(cruise_counts, linewidth=1.5, color=COLORS_QUAL[0])
            q95 = np.percentile(cruise_counts, 95)
            ax3.axhline(y=q95, color=COLORS_QUAL[3], linestyle='--',
                        alpha=0.7, label=f'Q95={q95:.0f}')
            ax3.set_xlabel('Time window (15 min)')
            ax3.set_ylabel('Cruising vehicles')
            ax3.set_title('Cruising Vehicle Count Time Series')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
        ax3.set_xticks(range(0, 96, 8))
        ax3.set_xticklabels([f'{h:02d}:00' for h in range(0, 24, 2)])

        # Subplot 4: Feature distributions
        ax4 = axes[1, 1]
        if 'feature_samples' in cruising_result:
            features = cruising_result['feature_samples']
            ax4.scatter(features['v_avg'], features['H'],
                       c=features['n_repeat'], cmap=CMAP_SEQUENTIAL,
                       s=20, alpha=0.6, edgecolors='none')
            ax4.axhline(y=cruising_result.get('H_threshold', 0.8),
                        color=COLORS_QUAL[3], linestyle='--',
                        label=f'H_threshold={cruising_result.get("H_threshold", 0):.2f}')
            ax4.axvline(x=5.0, color=COLORS_QUAL[2], linestyle='--',
                        label='v_max=5 km/h')
            ax4.set_xlabel('Average speed (km/h)')
            ax4.set_ylabel('Direction entropy H (nat)')
            ax4.set_title('Vehicle Feature Space\n(Cruising region: lower-left quadrant)')
            ax4.legend(fontsize=8)
            ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        path = os.path.join(self.output_dir, 'fig6_cruising_analysis.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_control_evaluation(self, eval_result):
        """Plot control evaluation results."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Subplot 1: Event study coefficients
        ax1 = axes[0, 0]
        es_coefs = eval_result['event_study']['event_study_coefs']
        taus = sorted(es_coefs.keys())
        coefs = [es_coefs[t]['coef'] for t in taus]
        ci_low = [es_coefs[t]['ci_lower'] for t in taus]
        ci_high = [es_coefs[t]['ci_upper'] for t in taus]

        ax1.axhline(y=0, color='gray', linewidth=0.8)
        ax1.axvline(x=-0.5, color=COLORS_QUAL[3], linestyle='--', alpha=0.5,
                    label='Control start (May 1)')
        ax1.errorbar(taus, coefs, yerr=[np.array(coefs) - np.array(ci_low),
                                          np.array(ci_high) - np.array(coefs)],
                     fmt='o-', color=COLORS_QUAL[0], capsize=3, linewidth=1.5,
                     markersize=6)
        ax1.fill_between(taus, ci_low, ci_high, alpha=0.15, color=COLORS_QUAL[0])
        ax1.set_xlabel('Days from April 30')
        ax1.set_ylabel('Coefficient (avg speed, km/h)')
        ax1.set_title('Dynamic Event Study\n(Parallel Trend Test)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_xticks(taus)

        # Subplot 2: Regression coefficients
        ax2 = axes[0, 1]
        metrics = ['avg_speed', 'total_flow', 'waiting_time']
        metric_labels = ['Avg speed (km/h)', 'Total flow (veh)', 'Wait time (s/km)']
        reg_results = eval_result['regression']

        x_pos = np.arange(len(metrics))
        width = 0.25
        for idx, term in enumerate(['Post', 'Holiday']):
            vals = []
            errs = []
            for m in metrics:
                r = reg_results[m]['results'].get(term, {'coef': 0, 'ci_95_upper': 0,
                                                           'ci_95_lower': 0})
                vals.append(r['coef'])
                err_low = r['coef'] - r.get('ci_95_lower', 0)
                err_high = r.get('ci_95_upper', 0) - r['coef']
                errs.append([err_low, err_high])
            errs = np.array(errs).T
            ax2.bar(x_pos + idx * width, vals, width, yerr=errs,
                    label=term, capsize=3, color=COLORS_QUAL[idx],
                    alpha=0.8)

        ax2.axhline(y=0, color='gray', linewidth=0.8)
        ax2.set_xticks(x_pos + width / 2)
        ax2.set_xticklabels(metric_labels, fontsize=9)
        ax2.set_ylabel('Effect size')
        ax2.set_title('Pre-Post Regression Coefficients\n(with 95% CI)')
        ax2.legend()
        ax2.grid(True, alpha=0.3, axis='y')

        # Subplot 3: Cohen's d scores by intersection
        ax3 = axes[1, 0]
        comp_scores = eval_result['comprehensive_scores']
        ints = sorted(comp_scores.keys())
        scores = [comp_scores[i] for i in ints]
        colors = [COLORS_QUAL[0] if s >= 0 else COLORS_QUAL[3] for s in scores]
        ax3.bar(ints, scores, color=colors, alpha=0.8, edgecolor='white',
                linewidth=0.5)
        ax3.axhline(y=0, color='gray', linewidth=0.8)
        ax3.set_xlabel('Intersection ID')
        ax3.set_ylabel("Cohen's d composite score")
        ax3.set_title("Intersection Control Effect\n(Cohen's d, AHP-weighted)")
        ax3.set_xticks(ints)
        ax3.grid(True, alpha=0.3, axis='y')

        # Subplot 4: Before-after comparison
        ax4 = axes[1, 1]
        # Use regression predictions
        for metric in metrics:
            r = reg_results[metric]
            y_pred = r['y_pred']
            y_actual = r.get('residuals', np.zeros_like(y_pred)) + y_pred
            ax4.scatter(y_pred, y_actual, alpha=0.4, s=10,
                       label=metric, color=COLORS_QUAL[metrics.index(metric)])
        ax4.plot([0, 1], [0, 1], 'k--', alpha=0.5, transform=ax4.transAxes)
        ax4.set_xlabel('Predicted')
        ax4.set_ylabel('Actual')
        ax4.set_title('Model Fit (Actual vs Predicted)')
        ax4.legend(fontsize=8)
        ax4.grid(True, alpha=0.3)
        # Add R² text
        r2_text = '\n'.join([
            f'{metric_labels[i]}: R²={reg_results[m]["r_squared"]:.3f}'
            for i, m in enumerate(metrics)
        ])
        ax4.text(0.05, 0.95, r2_text, transform=ax4.transAxes,
                fontsize=8, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.tight_layout()
        path = os.path.join(self.output_dir, 'fig7_control_evaluation.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path

    def plot_summary_dashboard(self, flow_by_type, partition_results,
                                 ga_result, cruising_result, eval_result):
        """Generate a summary dashboard with key results."""
        fig = plt.figure(figsize=(16, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

        # Title
        fig.suptitle('MCM 2024 E — Traffic Control Analysis Summary',
                     fontsize=16, fontweight='bold', y=0.98)

        # Panel 1: Flow profile (weekday)
        ax1 = fig.add_subplot(gs[0, 0])
        X = flow_by_type['weekday']
        total_flow = X.sum(axis=1)
        ax1.plot(total_flow, color=COLORS_QUAL[0], linewidth=1.5)
        bp_weekday = partition_results['weekday']['breakpoints']
        for b in bp_weekday:
            ax1.axvline(x=b, color=COLORS_QUAL[3], linestyle='--', alpha=0.6)
        ax1.set_xlabel('Time (15 min)')
        ax1.set_ylabel('Total flow (veh/15min)')
        ax1.set_title(f'Weekday Flow (K={partition_results["weekday"]["K_opt"]})')
        ax1.set_xticks(range(0, 96, 12))
        ax1.set_xticklabels([f'{h:02d}:00' for h in range(0, 24, 3)])
        ax1.grid(True, alpha=0.3)

        # Panel 2: Weekend flow
        ax2 = fig.add_subplot(gs[0, 1])
        X_wk = flow_by_type.get('weekend',
                                 np.zeros((N_WINDOWS, 12)))
        total_flow_wk = X_wk.sum(axis=1)
        ax2.plot(total_flow_wk, color=COLORS_QUAL[1], linewidth=1.5)
        bp_weekend = partition_results.get('weekend',
                                            partition_results['weekday'])['breakpoints']
        for b in bp_weekend:
            ax2.axvline(x=b, color=COLORS_QUAL[3], linestyle='--', alpha=0.6)
        ax2.set_xlabel('Time (15 min)')
        ax2.set_ylabel('Total flow (veh/15min)')
        ax2.set_title(f'Weekend Flow (K={partition_results.get("weekend", partition_results["weekday"])["K_opt"]})')
        ax2.set_xticks(range(0, 96, 12))
        ax2.set_xticklabels([f'{h:02d}:00' for h in range(0, 24, 3)])
        ax2.grid(True, alpha=0.3)

        # Panel 3: Holiday flow
        ax3 = fig.add_subplot(gs[0, 2])
        X_hol = flow_by_type.get('holiday',
                                  np.zeros((N_WINDOWS, 12)))
        total_flow_hol = X_hol.sum(axis=1)
        ax3.plot(total_flow_hol, color=COLORS_QUAL[2], linewidth=1.5)
        bp_holiday = partition_results.get('holiday',
                                            partition_results['weekday'])['breakpoints']
        for b in bp_holiday:
            ax3.axvline(x=b, color=COLORS_QUAL[3], linestyle='--', alpha=0.6)
        ax3.set_xlabel('Time (15 min)')
        ax3.set_ylabel('Total flow (veh/15min)')
        ax3.set_title(f'Holiday Flow (K={partition_results.get("holiday", partition_results["weekday"])["K_opt"]})')
        ax3.set_xticks(range(0, 96, 12))
        ax3.set_xticklabels([f'{h:02d}:00' for h in range(0, 24, 3)])
        ax3.grid(True, alpha=0.3)

        # Panel 4: GA convergence
        ax4 = fig.add_subplot(gs[1, 0])
        if ga_result and 'fitness_history' in ga_result:
            ax4.plot(ga_result['fitness_history'], color=COLORS_QUAL[0],
                     linewidth=1.5, label='Best')
            ax4.plot(ga_result.get('mean_fitness_history', []),
                     color=COLORS_QUAL[1], linewidth=1.5, alpha=0.7,
                     label='Mean (feasible)')
            ax4.set_xlabel('Generation')
            ax4.set_ylabel('Avg speed (km/h)')
            ax4.set_title(f'GA Convergence\nBest={ga_result["best_fitness"]:.1f} km/h')
            ax4.legend(fontsize=8)
            ax4.grid(True, alpha=0.3)

        # Panel 5: Green time allocation
        ax5 = fig.add_subplot(gs[1, 1])
        if ga_result and 'greens' in ga_result:
            greens = ga_result['greens']
            ints = sorted(greens.keys())
            phase_colors = ['#4c72b0', '#dd8452', '#55a868', '#c44e52']
            bottom = np.zeros(len(ints))
            for ph in PHASES:
                vals = [greens[i].get(ph, 0) if greens[i] else 0 for i in ints]
                ax5.bar(ints, vals, bottom=bottom, color=phase_colors[ph - 1],
                        label=f'Phase {ph}', alpha=0.8, edgecolor='white',
                        linewidth=0.5)
                bottom += np.array(vals)
            ax5.set_xlabel('Intersection')
            ax5.set_ylabel('Green time (s)')
            ax5.set_title(f'Green Time Allocation\nC0={ga_result["C_0"]:.0f}s')
            ax5.legend(fontsize=7, ncol=2)
            ax5.set_xticks(ints)
            ax5.grid(True, alpha=0.3, axis='y')

        # Panel 6: Cruising demand
        ax6 = fig.add_subplot(gs[1, 2])
        tau_results = cruising_result['tau_sensitivity']
        taus = list(tau_results.keys())
        cons_d = [tau_results[t]['demand_conservative'] for t in taus]
        opt_d = [tau_results[t]['demand_optimistic'] for t in taus]
        ax6.plot(taus, cons_d, 'o-', color=COLORS_QUAL[0], label='Conservative')
        ax6.plot(taus, opt_d, 's--', color=COLORS_QUAL[1], label='Optimistic')
        ax6.set_xlabel('τ (min)')
        ax6.set_ylabel('Parking demand')
        ax6.set_title(f'Parking Demand\nCV={cruising_result["tau_cv"]:.1%}')
        ax6.legend(fontsize=8)
        ax6.grid(True, alpha=0.3)

        # Panel 7: Cohen's d
        ax7 = fig.add_subplot(gs[2, 0])
        comp_scores = eval_result['comprehensive_scores']
        ints = sorted(comp_scores.keys())
        scores = [comp_scores[i] for i in ints]
        colors_bar = [COLORS_QUAL[0] if s >= 0 else COLORS_QUAL[3] for s in scores]
        ax7.bar(ints, scores, color=colors_bar, alpha=0.8)
        ax7.axhline(y=0, color='gray', linewidth=0.8)
        ax7.set_xlabel('Intersection')
        ax7.set_ylabel('Composite score')
        ax7.set_title("Control Effect Score\n(Cohen's d)")
        ax7.set_xticks(ints)
        ax7.grid(True, alpha=0.3, axis='y')

        # Panel 8: Regression summary
        ax8 = fig.add_subplot(gs[2, 1])
        reg_data = {}
        for metric in ['avg_speed', 'total_flow', 'waiting_time']:
            r = eval_result['regression'][metric]
            for term in ['Post', 'Holiday']:
                if term in r['results']:
                    key = f'{metric[:4]}_{term}'
                    reg_data[key] = r['results'][term]['coef']

        if reg_data:
            names = list(reg_data.keys())
            vals = list(reg_data.values())
            colors_r = [COLORS_QUAL[0] if v >= 0 else COLORS_QUAL[3] for v in vals]
            ax8.barh(names, vals, color=colors_r, alpha=0.8)
            ax8.axvline(x=0, color='gray', linewidth=0.8)
            ax8.set_xlabel('Coefficient')
            ax8.set_title('Regression Coefficients')
            ax8.grid(True, alpha=0.3, axis='x')

        # Panel 9: Event study parallel trend
        ax9 = fig.add_subplot(gs[2, 2])
        es_coefs = eval_result['event_study']['event_study_coefs']
        taus = sorted([t for t in es_coefs.keys() if t < 0])
        if taus:
            pre_coefs = [es_coefs[t]['coef'] for t in taus]
            ax9.plot(taus, pre_coefs, 'o-', color=COLORS_QUAL[0], linewidth=1.5)
            ax9.axhline(y=0, color='gray', linewidth=0.8)
            ax9.axvline(x=-0.5, color=COLORS_QUAL[3], linestyle='--', alpha=0.5)
            ax9.set_xlabel('Days before control')
            ax9.set_ylabel('Coefficient')
            ax9.set_title('Parallel Trend Test\n' +
                         ('PASSED' if eval_result['event_study']['parallel_trend']
                          else 'FAILED'))
            ax9.grid(True, alpha=0.3)
            ax9.set_xticks(taus)

        plt.tight_layout(rect=[0, 0, 1, 0.95])
        path = os.path.join(self.output_dir, 'fig8_summary_dashboard.png')
        plt.savefig(path, dpi=300)
        plt.close()
        return path


# ============================================================
# Section 8: Main Pipeline
# ============================================================

def run_pipeline(output_dir=None):
    """Run the complete MCM 2024 E solution pipeline.

    Args:
        output_dir: directory for outputs (default: subdirectory in phase-2-coding)

    Returns:
        dict with all results
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)

    global OUTPUT_DIR
    OUTPUT_DIR = output_dir

    print("=" * 60)
    print("MCM 2024 E — Traffic Control Solution Pipeline")
    print("=" * 60)

    # ---- Step 0: Generate synthetic data ----
    print("\n[Step 0] Generating synthetic traffic data...")
    generator = TrafficDataGenerator(seed=42)
    df = generator.generate_full_dataset()
    print(f"  Generated {len(df):,} records for {N_DAYS} days")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Vehicles in pool: {generator.vehicle_pool_size}")

    # Save data summary
    data_summary = {
        'total_records': len(df),
        'n_days': N_DAYS,
        'date_range': [str(df['date'].min()), str(df['date'].max())],
        'n_intersections': N_INTERSECTIONS,
        'vehicle_pool': generator.vehicle_pool_size,
    }

    # ---- Step 1: Data Preprocessing ----
    print("\n[Step 1] Preprocessing data...")
    preprocessor = DataPreprocessor(df)
    flow_by_type = preprocessor.aggregate_flow_by_type()
    print(f"  Weekday windows: {flow_by_type['weekday'].shape}")
    print(f"  Weekend windows: {flow_by_type.get('weekend', np.array([])).shape}")
    print(f"  Holiday windows: {flow_by_type.get('holiday', np.array([])).shape}")

    # ---- Algorithm 1: Time Period Partitioning ----
    print("\n[Algorithm 1] Time period partitioning...")
    partitioner = TimePeriodPartitioner(flow_by_type)
    partition_results = {}
    for dtype in ['weekday', 'weekend', 'holiday']:
        if dtype in flow_by_type and flow_by_type[dtype].sum() > 0:
            result = partitioner.fit(dtype)
            partition_results[dtype] = result
            status = result['consistency_status']
            print(f"  {dtype}: K={result['K_opt']}, "
                  f"breakpoints={result['breakpoints']}, "
                  f"consistency={status}")
            if status == 'high_uncertainty':
                print(f"    WARNING: Max deviation={result['max_deviation']:.1f} windows")

    # Use weekday partitioning as default
    default_partition = partition_results.get('weekday', list(partition_results.values())[0])

    # ---- Turning Probability Estimation ----
    print("\n[Turning Probabilities] Estimating with Dirichlet-Multinomial...")
    turn_estimator = TurningProbabilityEstimator(df)
    turn_probs = {}
    for i in INTERSECTIONS[:3]:  # Subset for demo
        turn_probs[i] = turn_estimator.estimate_by_period(
            i, default_partition['labels'])

    # ---- Phase Flow Calculation ----
    # Convert turning probabilities to per-phase flow rates
    # For each intersection and period, compute phase-wise arrival rates
    flow_by_period = {}
    for p in range(default_partition['K_opt']):
        period_flow = {}
        for i in INTERSECTIONS:
            phase_flow_dict = {}
            # Simulate phase flow based on total flow and typical turning pattern
            windows_in_period = np.where(default_partition['labels'] == p)[0]
            if len(windows_in_period) > 0:
                # Average flow on this period across all days (weekday)
                weekday_flow = flow_by_type['weekday']
                period_data = weekday_flow[windows_in_period]
                avg_movement = period_data.mean(axis=0)

                # Map movement indices (0-11) to signal phases (1-4)
                # Phase 1 (南北直行): mv 0 (N->S) + mv 3 (S->N)
                # Phase 2 (南北左转): mv 1 (N->E) + mv 4 (S->W)
                # Phase 3 (东西直行): mv 6 (E->W) + mv 9 (W->E)
                # Phase 4 (东西左转): mv 7 (E->N) + mv 10 (W->S)
                phase_sum = {
                    1: avg_movement[0] + avg_movement[3],
                    2: avg_movement[1] + avg_movement[4],
                    3: avg_movement[6] + avg_movement[9],
                    4: avg_movement[7] + avg_movement[10],
                }
                # Convert from veh/15min to veh/s
                for ph in PHASES:
                    phase_flow_dict[ph] = phase_sum[ph] / (DT * 60)
            else:
                for ph in PHASES:
                    phase_flow_dict[ph] = 0.05

            period_flow[i] = phase_flow_dict
        flow_by_period[p] = period_flow

    print(f"  Computed phase flow for {default_partition['K_opt']} periods")

    # ---- Algorithm 2: Signal Timing Optimization ----
    print("\n[Algorithm 2] Signal timing optimization...")
    optimizer = SignalTimingOptimizer(flow_by_period)
    ga_result = optimizer.ga_optimize(
        period=0, pop_size=50, n_generations=200
    )
    print(f"  Best C0 = {ga_result['C_0']:.1f} s")
    print(f"  Best avg speed = {ga_result['best_fitness']:.2f} km/h")
    print(f"  Offsets: {[f'{o:.1f}' for o in ga_result['offsets'][:5]]}...")
    print(f"  C range: [{ga_result['C_range'][0]:.0f}, {ga_result['C_range'][1]:.0f}]")

    # ---- Algorithm 3: Cruising Vehicle Detection ----
    print("\n[Algorithm 3] Cruising vehicle identification...")
    # Filter holiday data
    holiday_dates = ['2024-05-01', '2024-05-02', '2024-05-03',
                     '2024-05-04', '2024-05-05']
    df_holiday = df[df['date'].astype(str).isin(holiday_dates)]

    detector = CruisingVehicleDetector(df_holiday)
    trajs = detector._reconstruct_trajectories()
    r_break, n_break, n_seg, break_details = detector.detect_side_entries(trajs)
    print(f"  Trajectory break ratio: {r_break:.4f} ({n_break}/{n_seg})")
    feats = detector.compute_features(trajs)
    H_th, H_A, H_B = detector.compute_h_threshold(feats)
    print(f"  H_threshold: {H_th:.3f} (A={H_A:.3f}, B={H_B:.3f})")
    cruising = detector.classify_cruising(feats, H_th)
    print(f"  Cruising vehicles detected: {len(cruising)}")

    # ---- Validation against synthetic ground truth ----
    # Using all_cruising_plates collected during data generation
    # (Fix C-20260530-004)
    detected_plates = set(cruising.keys())
    ground_truth_plates = generator.all_cruising_plates
    true_positives = detected_plates & ground_truth_plates
    precision = (len(true_positives) / len(detected_plates)
                 if len(detected_plates) > 0 else 0.0)
    recall = (len(true_positives) / len(ground_truth_plates)
              if len(ground_truth_plates) > 0 else 0.0)
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    print(f"  Validation vs ground truth:"
          f" P={precision:.3f}, R={recall:.3f}, F1={f1:.3f}")
    print(f"    GT plates={len(ground_truth_plates)},"
          f" Detected={len(detected_plates)}, TP={len(true_positives)}")

    # Sensitivity analysis
    cruising_result = detector.sensitivity_analysis(holiday_dates)
    # Store ground truth validation metrics (Fix C-20260530-004)
    cruising_result['validation'] = {
        'ground_truth_count': len(ground_truth_plates),
        'detected_count': len(detected_plates),
        'true_positives': len(true_positives),
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1_score': round(f1, 4),
    }
    cruising_result['cruise_counts'] = None
    # Compute cruise counts for plotting
    if hasattr(detector, 'estimate_parking_demand'):
        d_cons, d_opt, cruise_counts, Q95 = detector.estimate_parking_demand(
            cruising, r_break)
        cruising_result['cruise_counts'] = cruise_counts
        cruising_result['feature_samples'] = {
            'v_avg': [f['v_avg'] for f in feats.values()],
            'H': [f['H'] for f in feats.values()],
            'n_repeat': [f['n_repeat'] for f in feats.values()],
        }
    print(f"  Parking demand (conservative): {d_cons} spaces")
    print(f"  Parking demand (optimistic): {d_opt} spaces")
    print(f"  Q95 cruising count: {Q95:.0f}")
    print(f"  τ sensitivity CV: {cruising_result['tau_cv']:.1%}")

    # ---- Algorithm 4: Control Effect Evaluation ----
    print("\n[Algorithm 4] Control effect evaluation...")
    evaluator = ControlEffectEvaluator(df)
    daily_metrics = evaluator.compute_daily_metrics()
    print(f"  Daily metrics computed: {len(daily_metrics)} rows")
    eval_result = evaluator.comprehensive_evaluation(daily_metrics)

    # Print regression results
    for metric in ['avg_speed', 'total_flow', 'waiting_time']:
        r = eval_result['regression'][metric]
        beta3 = r['results'].get('Post', {})
        gamma = r['results'].get('Holiday', {})
        print(f"  {metric}: β3={beta3.get('coef', 0):.3f} (p={beta3.get('p_value', 1):.4f}), "
              f"γ={gamma.get('coef', 0):.3f} (p={gamma.get('p_value', 1):.4f}), "
              f"R²={r['r_squared']:.3f}")

    pt = eval_result['event_study']['parallel_trend']
    print(f"  Parallel trend: {'PASSED' if pt else 'FAILED'} "
          f"(p={eval_result['event_study']['parallel_p_value']:.4f})")
    print(f"  AHP weights: {eval_result['ahp_weights']}")

    # ---- Generate Visualizations ----
    print("\n[Visualization] Generating plots...")
    vis = Visualizer(output_dir)

    # Figure 1: Flow heatmaps
    for dtype in ['weekday', 'weekend', 'holiday']:
        if dtype in partition_results:
            path = vis.plot_flow_heatmap(flow_by_type, partition_results[dtype], dtype)
            print(f"  Saved: {os.path.basename(path)}")

    # Figure 2: Dunn index
    for dtype in ['weekday', 'weekend', 'holiday']:
        if dtype in partition_results and partition_results[dtype].get('dunn_scores'):
            path = vis.plot_dunn_scores(partition_results[dtype]['dunn_scores'], dtype)
            print(f"  Saved: {os.path.basename(path)}")

    # Figure 3: Period comparison
    path = vis.plot_period_comparison(partition_results)
    print(f"  Saved: {os.path.basename(path)}")

    # Figure 4: GA convergence
    ga_histories = {
        'weekday_peak': ga_result['fitness_history'],
        'weekday_mean': ga_result['mean_fitness_history'],
    }
    path = vis.plot_ga_convergence(ga_histories)
    print(f"  Saved: {os.path.basename(path)}")

    # Figure 5: Green wave diagram
    path = vis.plot_green_wave_diagram(
        ga_result['C_0'], ga_result['offsets'],
        ga_result['greens'], 'weekday_peak')
    print(f"  Saved: {os.path.basename(path)}")

    # Figure 6: Cruising analysis
    path = vis.plot_cruising_stats(cruising_result)
    print(f"  Saved: {os.path.basename(path)}")

    # Figure 7: Control evaluation
    path = vis.plot_control_evaluation(eval_result)
    print(f"  Saved: {os.path.basename(path)}")

    # Figure 8: Summary dashboard
    path = vis.plot_summary_dashboard(flow_by_type, partition_results,
                                       ga_result, cruising_result, eval_result)
    print(f"  Saved: {os.path.basename(path)}")

    # ---- Save numerical results ----
    results = {
        'data_summary': data_summary,
        'partition_results': {
            dtype: {
                'K_opt': int(r['K_opt']),
                'breakpoints': [int(b) for b in r['breakpoints']],
                'consistency_status': r['consistency_status'],
                'max_deviation': float(r['max_deviation']),
            }
            for dtype, r in partition_results.items()
        },
        'signal_optimization': {
            'C_0': float(ga_result['C_0']),
            'best_avg_speed_kmh': float(ga_result['best_fitness']),
            'offsets': [float(o) for o in ga_result['offsets']],
            'C_range': [float(c) for c in ga_result['C_range']],
        },
        'cruising_detection': {
            'r_break': float(r_break),
            'n_cruising_vehicles': len(cruising),
            'H_threshold': float(H_th),
            'parking_demand_conservative': d_cons,
            'parking_demand_optimistic': d_opt,
            'Q95_cruising_count': float(Q95),
            'tau_cv': float(cruising_result['tau_cv']),
            'tau_sensitivity': {
                str(k): v for k, v in cruising_result['tau_sensitivity'].items()
            },
            'validation': cruising_result.get('validation', {}),
        },
        'control_evaluation': {
            'regression': {
                m: {
                    'beta_3': eval_result['regression'][m]['results'].get('Post', {}).get('coef', 0),
                    'beta_3_p': eval_result['regression'][m]['results'].get('Post', {}).get('p_value', 1),
                    'gamma': eval_result['regression'][m]['results'].get('Holiday', {}).get('coef', 0),
                    'gamma_p': eval_result['regression'][m]['results'].get('Holiday', {}).get('p_value', 1),
                    'R_squared': eval_result['regression'][m]['r_squared'],
                }
                for m in ['avg_speed', 'total_flow', 'waiting_time']
            },
            'parallel_trend': pt,
            'parallel_trend_p': float(eval_result['event_study']['parallel_p_value']),
            'comprehensive_scores': {
                str(k): float(v) for k, v in eval_result['comprehensive_scores'].items()
            },
        }
    }

    results_path = os.path.join(output_dir, 'results.json')
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {results_path}")

    print("\n" + "=" * 60)
    print("Pipeline completed successfully!")
    print("=" * 60)

    return results


# ============================================================
# Entry Point
# ============================================================

if __name__ == '__main__':
    import sys
    # Use the script's directory as default output
    script_dir = os.path.dirname(os.path.abspath(__file__))
    results = run_pipeline(script_dir)
