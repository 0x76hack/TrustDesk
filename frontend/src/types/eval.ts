export interface SummaryMetrics {
  total_cases?: number;
  triage_accuracy?: number;
  citation_coverage?: number;
  unsafe_block_rate?: number;
  escalation_accuracy?: number;
  [key: string]: unknown;
}

export interface EvalRun {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | string;
  summary_metrics?: SummaryMetrics | null;
  created_at: string;
}

export interface EvalResult {
  id: string;
  eval_run_id: string;
  case_id: string;
  expected: Record<string, unknown>;
  observed: Record<string, unknown>;
  triage_pass?: boolean | null;
  citation_pass?: boolean | null;
  unsafe_block_pass?: boolean | null;
  escalation_pass?: boolean | null;
}

export interface EvalRunDetail extends EvalRun {
  results: EvalResult[];
}
