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
  panel_e_mapreduce: PanelEMapReduce;
  panel_f_category_flow: PanelFCategoryFlow;
  panel_g_neighbors: PanelGNeighbors;
  panel_h_threshold_outcome: PanelHThresholdOutcome;
}

/* =========================== WORKSHOP 4 (UNIT 4) =========================== */

export interface Unit3EdgeValidation {
  edges_checked: number;
  mr_edges_count: number;
  unit3_edges_count: number;
  transition_count_mismatches: number;
  max_flagged_frac_diff: number;
  max_avg_view_diff: number;
  passed: boolean;
}

export interface S10PageRankMR {
  damping: number;
  tolerance: number;
  iterations: number;
  pairs_per_iteration: number;
  total_s10_pairs: number;
  total_s10_shuffle_bytes: number;
  replication_rate_r: number;
  max_reducer_load_q: number;
  max_key_in_degree: number;
  max_abs_diff_vs_unit3: number;
  within_1e4: boolean;
  wall_time_ms: number;
  comparison: {
    category: string;
    mr_pagerank: number;
    unit3_pagerank: number;
    abs_diff: number;
  }[];
  convergence_history: { iteration: number; l1_residual: number }[];
}

export interface CostScalingRow {
  scale: string;
  factor: number;
  uploads: number;
  transitions: number;
  no_combiner_pairs: number;
  with_combiner_pairs: number;
  no_combiner_bytes: number;
  with_combiner_bytes: number;
  job1b_no_combiner_pairs: number;
  job1b_with_combiner_pairs: number;
  job1b_reduction_pct: number;
  total_pairs_reduction_pct: number;
  total_bytes_reduction_pct: number;
  no_combiner_time_ms: number;
  with_combiner_time_ms: number;
  extrapolated: boolean;
}

export interface ReducerSweepRow {
  R: number;
  max_reducer_load: number;
  min_reducer_load: number;
  mean_reducer_load: number;
  load_balance_factor: number;
  reducer_loads: number[];
  hot_key_uploader: string;
  hot_key_q: number;
  wall_time_ms: number;
}

export interface JobRQRow {
  job: string;
  key: string;
  input_records: number;
  replication_rate_r: number;
  max_reducer_size_q: number;
  hot_key: string;
  hot_key_count: number;
  notes: string;
}

export interface S14WorkerRow {
  P: number;
  skewed_time_ms: number;
  skewed_speedup: number;
  skewed_efficiency: number;
  skewed_load_balance: number;
  skewed_max_reducer_load: number;
  skewed_shuffle_pairs: number;
  mitigated_time_ms: number;
  mitigated_speedup: number;
  mitigated_efficiency: number;
  mitigated_abs_speedup_vs_base: number;
  mitigated_load_balance: number;
  mitigated_max_reducer_load: number;
  mitigated_shuffle_pairs: number;
  ideal_speedup: number;
}

export interface PanelEMapReduce {
  pipeline_validation: {
    unit3_edge_validation: Unit3EdgeValidation;
    scale_100k_metrics: {
      uploads: number;
      fragments: number;
      workers: number;
      edges: number;
      transitions: number;
      job1_wall_ms: number;
      job2_wall_ms: number;
      net_flow_sum_check: number;
    };
  };
  s10_pagerank_mr: S10PageRankMR;
  cost_analysis: {
    base_count: number;
    scaling_rows: CostScalingRow[];
    linearity: {
      r2_no_combiner_pairs: number;
      r2_with_combiner_pairs: number;
      r2_runtime: number;
      ratio_2x_to_1x_no_combiner: number;
      ratio_4x_to_1x_no_combiner: number;
      slope_pairs_per_upload_no_combiner: number;
      slope_pairs_per_upload_with_combiner: number;
      is_linear: boolean;
    };
    s10_cost: {
      pairs_per_iteration: number;
      iterations: number;
      total_pairs: number;
      total_shuffle_bytes: number;
      formula: string;
    };
    combined_1x_total_pairs_with_combiner: number;
    combined_1x_total_pairs_no_combiner: number;
  };
  reducer_analysis: {
    hot_key_uploader: string;
    hot_key_upload_count: number;
    jobs_rq: JobRQRow[];
    reducer_sweep: ReducerSweepRow[];
  };
  s14_skew_mitigation: {
    total_uploads: number;
    hot_category: string;
    hot_category_count: number;
    hot_category_share: number;
    mitigation_strategy: string;
    rows: S14WorkerRow[];
    summary_p8: {
      skewed_load_balance: number;
      mitigated_load_balance: number;
      lbf_reduction_pct: number;
      skewed_speedup: number;
      mitigated_speedup: number;
      mitigated_abs_speedup_vs_base: number;
      skewed_efficiency: number;
      mitigated_efficiency: number;
      time_improvement_factor_p8: number;
      shuffle_reduction_pct: number;
    };
  };
}

export interface CategoryNodeSummary {
  category: string;
  out_transition_count: number;
  in_transition_count: number;
  net_flow: number;
  flagged_frac: number;
  avg_view_count_1h: number;
  growing: boolean;
  high_flag: boolean;
  quadrant: string;
}

export interface PanelFCategoryFlow {
  node_summary_100k: CategoryNodeSummary[];
  node_summary_unit3: Omit<CategoryNodeSummary, "growing" | "high_flag" | "quadrant">[];
  mean_flagged_frac: number;
  unit3_edge_validation: Unit3EdgeValidation;
  s10_pagerank_mr: S10PageRankMR;
}

/* =========================== WORKSHOP 5 (UNIT 5) =========================== */

export interface DistributionBlock {
  stats: {
    mean: number;
    std: number;
    min: number;
    p5: number;
    median: number;
    p95: number;
    max: number;
    cv_std_over_mean: number;
    relative_contrast: number;
    max_over_min: number;
  };
  histogram: { bin_start: number; bin_end: number; label: string; count: number }[];
}

export interface NeighborHit {
  uploader_id: string;
  score: number;
  flagged_frac: number;
  cluster_id: string | null;
}

export interface QueryUploaderDetail {
  uploader_id: string;
  flagged_frac: number;
  is_flagged_account: boolean;
  seq_length: number;
  avg_view_count_1h: number;
  shingle_count: number;
  cluster_id: string | null;
  candidates_examined: {
    minhash_lsh: number;
    cosine_lsh: number;
    lcs_candidates: number;
  };
  overlap_at_5: {
    minhash_vs_cosine: number;
    minhash_vs_lcs: number;
    cosine_vs_lcs: number;
  };
  neighbors: {
    minhash_lsh: NeighborHit[];
    cosine_lsh: NeighborHit[];
    unit5_lcs: NeighborHit[];
  };
}

export interface PanelGNeighbors {
  meta: {
    n_uploaders: number;
    planted_clusters: number;
    malicious_clusters: number;
    planted_accounts: number;
    background_accounts: number;
    dataset_file: string;
  };
  task1_representations: {
    n_uploaders: number;
    vector_dim: number;
    vector_features: string[];
    excluded_outcome_field: string;
    random_pairs_evaluated: number;
    distributions: {
      jaccard: DistributionBlock;
      cosine: DistributionBlock;
      l1: DistributionBlock;
      l2: DistributionBlock;
    };
    correlations_500_pairs: {
      pairs: number;
      jaccard_vs_cosine: { pearson: number; spearman: number };
      jaccard_vs_lcs: { pearson: number; spearman: number };
      cosine_vs_lcs: { pearson: number; spearman: number };
    };
    distance_concentration: {
      space: string;
      dims: number;
      l2_cv: number;
      l1_cv: number;
      l2_p95_p5_ratio: number;
      l1_p95_p5_ratio: number;
      l2_rel_contrast_p95: number;
    }[];
  };
  task2_hyperplanes: {
    angle_verification_pairs: number;
    queries_evaluated: number;
    configs: {
      n_hyperplanes: number;
      bands: number;
      rows_per_band: number;
      angle_mae_deg: number;
      angle_rmse_deg: number;
      angle_correlation: number;
      mean_agreement_diff: number;
      recall_at_5: number;
      avg_candidates: number;
      comparisons_saved_frac: number;
    }[];
    scatter_n128: { true_angle: number; estimated_angle: number; bit_agreement: number }[];
    selected_cosine_lsh: { n_hyperplanes: number; bands: number; rows_per_band: number };
  };
  task3_k_shingles: {
    rows: {
      k: number;
      avg_set_size: number;
      possible_shingles: number;
      observed_shingles: number;
      coverage_pct: number;
      intra_cluster_jaccard: number;
      inter_cluster_jaccard: number;
      separation_margin: number;
      separation_ratio: number;
    }[];
    best_k: number;
    intra_pairs_evaluated: number;
    inter_pairs_evaluated: number;
    justification: string;
  };
  queries_count: number;
  mean_overlap_at_5: {
    minhash_vs_cosine: number;
    minhash_vs_lcs: number;
    cosine_vs_lcs: number;
  };
  disagreement_explanation: string;
  queries: QueryUploaderDetail[];
}

export interface PanelHThresholdOutcome {
  meta: PanelGNeighbors["meta"];
  threshold_lsh: {
    n_hashes: number;
    selected_b: number;
    selected_r: number;
    s_threshold: number;
    theoretical_threshold_t: number;
    theoretical_prob_s06: number;
    theoretical_fnr_s08: number;
    total_pairs: number;
    candidate_pairs: number;
    comparisons_saved_pct: number;
    ground_truth_pairs_s06: number;
    ground_truth_pairs_s08: number;
    true_positives: number;
    false_positives: number;
    false_negatives: number;
    precision: number;
    recall: number;
    f1: number;
    empirical_fnr_s08: number;
    mapreduce_runner_metrics: {
      num_fragments: number;
      num_workers: number;
      num_reducers: number;
      map_output_pairs: number;
      shuffle_pairs: number;
      max_reducer_load: number;
      load_balance_factor: number;
      wall_time_ms: number;
    };
    design_table: {
      b: number;
      r: number;
      n_used: number;
      threshold_t: number;
      prob_s_02: number;
      prob_s_06: number;
      prob_s_08: number;
      fnr_s_08: number;
      meets_fnr_1pct: boolean;
      meets_s06_target: boolean;
      selected: boolean;
    }[];
    s_curve: Record<string, number>[];
    pr_sweep: {
      config: string;
      b: number;
      r: number;
      candidate_pairs: number;
      precision: number;
      recall: number;
      fnr_at_08: number;
      comparisons_saved_pct: number;
    }[];
  };
  outcome_test: {
    flagged_threshold: number;
    flagged_accounts_count: number;
    unflagged_accounts_count: number;
    excluded_from_vector: boolean;
    minhash_lift_vs_random: number;
    cosine_lift_vs_random: number;
    z_statistic: number;
    p_value: number;
    significant: boolean;
    groups: {
      group: string;
      short_label: string;
      mean_neighbor_flagged_frac: number;
      pct_neighbors_flagged: number;
      lift_vs_random: number;
      sample_accounts: number;
    }[];
  };
}
