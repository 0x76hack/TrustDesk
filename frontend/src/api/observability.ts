import { apiFetch } from './client';

export interface SystemStats {
  status: 'healthy' | 'degraded';
  uptime_seconds: number;
  environment: string;
  enforce_https: boolean;
  database_connected: boolean;
  database_latency_ms?: number;
  redis_connected: boolean;
  redis_latency_ms?: number;
  redis_memory_mb?: number;
  memory_usage_mb: number;
  cpu_percent: number;
}

export interface DatabaseInventory {
  tickets: number;
  messages: number;
  orders: number;
  customers: number;
  coupons: number;
  audit_logs: number;
  traces: number;
  kb_chunks: number;
  users: number;
}

export interface QueueStats {
  open: number;
  working: number;
  escalated: number;
  resolved: number;
  total: number;
}

export interface ActionStats {
  pending_approval: number;
  executed: number;
  rejected: number;
  total: number;
}

export interface SecurityStats {
  critical_events_24h: number;
  secrets_manager: {
    is_secure: boolean;
    issues: string[];
    provider_in_use: string;
  };
}

export interface PercentileStats {
  p50: number;
  p90: number;
  p95: number;
  p99: number;
  avg: number;
  min: number;
  max: number;
  sample_count: number;
}

export interface ProcessingRateStats {
  tickets_resolved_24h: number;
  tickets_resolved_1h: number;
  velocity_per_hour: number;
  runs_completed_24h: number;
  total_runs_24h: number;
  run_success_rate_percent: number;
}

export interface PerformanceStats {
  processing_rates: ProcessingRateStats;
  ticket_resolution_time_seconds: PercentileStats;
  pipeline_latency_ms: {
    overall: PercentileStats;
    by_type: Record<string, PercentileStats>;
  };
  http_latency_ms: PercentileStats;
}

export interface AITelemetryStats {
  total_runs: number;
  models_used: Record<string, number>;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number;
  latency_by_model: Record<string, PercentileStats>;
  guardrail_threats_blocked: {
    prompt_injection: number;
    conflict_or_bypass: number;
    total: number;
  };
}

export interface FraudMitigationStats {
  coupon_stats: {
    total_issued: number;
    active: number;
    redeemed: number;
    expired: number;
    total_refund_value_inr: number;
  };
  duplicate_replay_blocks: number;
}

export interface ObservabilityStats {
  system: SystemStats;
  database_inventory?: DatabaseInventory;
  queues: QueueStats;
  categories: Record<string, number>;
  actions: ActionStats;
  ai_telemetry?: AITelemetryStats;
  fraud_mitigation?: FraudMitigationStats;
  security: SecurityStats;
  performance?: PerformanceStats;
}

export interface LogEntry {
  timestamp: string;
  level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  logger: string;
  component: string;
  message: string;
  request_id?: string | null;
  user_id?: string | null;
}

export interface LogsResponse {
  count: number;
  total_in_buffer: number;
  logs: LogEntry[];
}

export interface AuditStreamEntry {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  outcome: string;
  risk_level: string | null;
  guardrail_result?: unknown;
  created_at: string | null;
}

export interface TraceEntry {
  id: string;
  ticket_id: string | null;
  run_id: string | null;
  run_type: string;
  model_used: string;
  latency_ms: number | null;
  token_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  risk_level: string | null;
  risk_factors: unknown[];
  guardrail_result: unknown;
  retrieved_doc_count: number;
  final_status: string;
  created_at: string | null;
}

export interface TraceListResponse {
  total: number;
  limit: number;
  offset: number;
  traces: TraceEntry[];
}

export interface SecuritySummaryResponse {
  critical_events_24h: number;
  prompt_injections_blocked_24h: number;
  idempotency_conflicts_prevented_24h: number;
  secrets_manager: {
    is_secure: boolean;
    issues: string[];
    provider_in_use: string;
  };
  recent_threats: AuditStreamEntry[];
}

export async function fetchObservabilityStats(): Promise<ObservabilityStats> {
  return apiFetch<ObservabilityStats>('/observability/stats');
}

export async function fetchObservabilityLogs(params: {
  level?: string;
  search?: string;
  request_id?: string;
  component?: string;
  limit?: number;
  offset?: number;
}): Promise<LogsResponse> {
  const query = new URLSearchParams();
  if (params.level && params.level !== 'ALL') query.set('level', params.level);
  if (params.search) query.set('search', params.search);
  if (params.request_id) query.set('request_id', params.request_id);
  if (params.component) query.set('component', params.component);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));

  const qs = query.toString();
  return apiFetch<LogsResponse>(`/observability/logs${qs ? `?${qs}` : ''}`);
}

export async function fetchAuditStream(params: {
  action?: string;
  risk_level?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditStreamEntry[]> {
  const query = new URLSearchParams();
  if (params.action) query.set('action', params.action);
  if (params.risk_level) query.set('risk_level', params.risk_level);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));

  const qs = query.toString();
  return apiFetch<AuditStreamEntry[]>(`/observability/audit-stream${qs ? `?${qs}` : ''}`);
}

export async function fetchObservabilityTraces(params: {
  run_type?: string;
  risk_level?: string;
  model_used?: string;
  ticket_id?: string;
  limit?: number;
  offset?: number;
}): Promise<TraceListResponse> {
  const query = new URLSearchParams();
  if (params.run_type) query.set('run_type', params.run_type);
  if (params.risk_level) query.set('risk_level', params.risk_level);
  if (params.model_used) query.set('model_used', params.model_used);
  if (params.ticket_id) query.set('ticket_id', params.ticket_id);
  if (params.limit) query.set('limit', String(params.limit));
  if (params.offset) query.set('offset', String(params.offset));

  const qs = query.toString();
  return apiFetch<TraceListResponse>(`/observability/traces${qs ? `?${qs}` : ''}`);
}

export async function fetchSecuritySummary(): Promise<SecuritySummaryResponse> {
  return apiFetch<SecuritySummaryResponse>('/observability/security-summary');
}
