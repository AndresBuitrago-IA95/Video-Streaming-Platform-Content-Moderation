/** Tipos que reflejan el JSON de `analytics/aggregate_api.py` (GET /api/dashboard). */

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
}

export interface BucketConfig {
  n: number;
  buckets: number;
  histogram: HistogramRow[];
  stats: { chaining?: MethodStats; two_choices?: MethodStats };
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
  false_positives: number;
  negatives: number;
  fp_rate_experimental: number;
  fp_rate_theoretical: number;
  false_negatives: number;
}

export interface WindowRow {
  window: number;
  start_seq: number;
  end_seq: number;
  F0: number;
  F1: number;
  F2: number;
  flagged_rate: number;
  spam_wave: boolean;
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
}

export interface DashboardData {
  meta: { generated_at: string; videos: number; categories: number };
  panel_a_bucket_load: {
    default_config: string;
    configs: Record<string, BucketConfig>;
  };
  panel_b_runtimes: {
    scenarios: Record<string, RuntimeRow[]>;
    default_scenario: string;
    worst_case_speedup: number;
    unit: string;
  };
  panel_c_realtime: {
    flag_rate_by_category: FlagRateRow[];
    global_flag_rate: number;
    frequency_moments: { all_videos: Moments; flagged_videos: Moments };
    bloom_filter: { configs: BloomRow[]; highlight_bits_per_element: number };
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
    streaming: {
      stream_events: number;
      stream_flagged_rate: number;
      recent_window_flagged_rate: number;
      windows: WindowRow[];
    };
  };
  panel_d_pagerank: {
    meta: {
      damping: number;
      iterations: number;
      spearman_rank_correlation: number | null;
      pagerank_spread: number;
    };
    categories: PageRankRow[];
  };
}
