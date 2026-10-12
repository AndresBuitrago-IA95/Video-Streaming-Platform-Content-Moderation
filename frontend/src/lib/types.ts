/** Tipos extendidos reflejando el payload unificado de backend/aggregate_api.py */

export interface HistogramRow {
  load: number;
  chaining: number;
  two_choices: number;
}

export interface MethodStats {
  max_load: number;
  mean: number;
  std: number;
  empty_buckets: number;
  theoretical_max?: number;
}

export interface BucketConfig {
  n: number;
  buckets: number;
  histogram: HistogramRow[];
  stats: { chaining?: MethodStats; two_choices?: MethodStats };
}

export interface ShardingStats {
  workers: number;
  videos: number;
  distinct_uploaders: number;
  collisions: number;
  max_videos: number;
  min_videos: number;
  mean_videos: number;
  std_videos: number;
  imbalance_ratio: number;
  videos_per_worker: number[];
}

export interface CapacityContext {
  records: number;
  span_days: number;
  uploads_per_sec: number;
  growth_factor: number;
  uploads_per_sec_growth: number;
  avg_metadata_bytes: number;
  storage_per_day_bytes: number;
  storage_per_year_bytes: number;
  assumption: string;
}

export interface RuntimeRow {
  n: number;
  deterministic_ms: number;
  randomized_ms: number;
}

export interface FlagRateRow {
  category: string;
  videos: number;
  flagged: number;
  flag_rate: number;
}

export interface Moments {
  F0: number;
  F1: number;
  F2: number;
  collision_prob: number;
  uniform_baseline: number;
  skew_ratio: number;
  top_category: string | null;
  top_share: number;
}

export interface BloomRow {
  bits_per_element: number;
  hash_functions: number;
  inserted?: number;
  false_positives: number;
  negatives: number;
  fp_rate_experimental: number;
  fp_rate_theoretical: number;
  false_negatives?: number;
}

export interface HllRow {
  m: number;
  memory_bits: number;
  mean_rel_error: number;
  theoretical_error: number;
}

export interface HllTodayEstimate {
  m: number;
  memory_bits: number;
  estimate: number;
  rel_error: number;
  theoretical_error: number;
}

export interface ReservoirCategoryRow {
  category: string;
  exact: number;
  estimated: number;
  error_pct: number;
}

export interface ReservoirSizeRow {
  sample_size: number;
  mean_error_pct_over_trials: number;
  categories: ReservoirCategoryRow[];
}

export interface ChernoffUploader {
  uploader_id: string;
  videos: number;
  flagged: number;
  flag_rate: number;
  chernoff_p_observed: number;
  suspicious: boolean;
}

export interface PageRankRow {
  category: string;
  pagerank: number;
  upload_count: number;
  freq_share: number;
  pagerank_rank: number;
  frequency_rank: number;
  rank_delta: number;
  pagerank_scaled: number;
  frequency_scaled: number;
  flagged_frac: number;
  flagged_scaled: number;
  stationary: number;
}

export interface MarkovClassification {
  num_classes: number;
  classes: { states: string[]; closed: boolean }[];
  absorbing_states: string[];
  has_absorbing_sink: boolean;
  irreducible: boolean;
  period: number;
  aperiodic: boolean;
}

export interface LazyWalkResult {
  steps: number;
  seed: number;
  max_abs_error: number;
  total_variation: number;
  categories: { category: string; pi: number; empirical: number }[];
}

export interface TwoSatResult {
  variables: number;
  constraints: number;
  risk_categories: string[];
  risk_score: Record<string, number>;
  found: boolean;
  attempts: number;
  flips: number;
  assignment: Record<string, boolean>;
  checks: { clause: string; satisfied: boolean }[];
}

export interface LiveStreamSnapshot {
  position: number;
  stream_length: number;
  window: number;
  events_per_second: number;
  rolling_flag_rate_by_category: FlagRateRow[];
  overall_flag_rate: number;
  moments: Moments;
  flagged_moments: { F0: number; F1: number; F2: number };
  spam: { z_F2: number; z_flag_rate: number; threshold: number; alert: boolean };
  series: {
    position: number;
    F2: number;
    flag_rate: number;
    z_F2: number;
    spam_wave: boolean;
  }[];
  bloom_live: BloomRow[];
  distinct_uploaders_today: {
    date: string;
    true_distinct: number;
    estimates: HllTodayEstimate[];
  };
}

export interface DashboardData {
  meta: { generated_at: string; videos: number; categories: number };
  capacity: CapacityContext;
  panel_a_bucket_load: {
    key: string;
    population: string;
    default_config: string;
    configs: Record<string, BucketConfig>;
    sharding: ShardingStats;
  };
  panel_b_runtimes: {
    scenarios: Record<string, RuntimeRow[]>;
    default_scenario: string;
    worst_case_speedup: number;
    unit: string;
    verified_against_sorted: boolean;
  };
  panel_c_realtime: {
    live: LiveStreamSnapshot;
    bloom_final: BloomRow[];
    hll_by_day: { days: number; rows: HllRow[] };
    reservoir_view_count: ReservoirSizeRow[];
    chernoff: {
      summary: {
        baseline_flag_rate: number;
        threshold_rate: number;
        alpha: number;
        uploaders_evaluated: number;
        uploaders_exceeding_threshold: number;
        uploaders_suspicious: number;
      };
      top_uploaders: ChernoffUploader[];
    };
    moments_overall: { all_videos: Moments; flagged_videos: Moments };
  };
  panel_d_pagerank: {
    meta: {
      damping: number;
      iterations: number;
      spearman_rank_correlation: number | null;
      pagerank_spread: number;
    };
    categories: PageRankRow[];
    markov: {
      classification: MarkovClassification;
      stationary: {
        iterations: number;
        residual: number;
        top_category: string;
        top_value: number;
        raw_frequency_top: string;
      };
      lazy_walk: LazyWalkResult;
      two_sat: TwoSatResult;
    };
  };
}
