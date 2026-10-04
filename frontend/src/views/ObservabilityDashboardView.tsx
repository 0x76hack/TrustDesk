import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Activity,
  ShieldAlert,
  Server,
  Database,
  Cpu,
  RefreshCw,
  Search,
  CheckCircle,
  Clock,
  Lock,
  Layers,
  Zap,
  DollarSign,
  Bot,
  ShieldCheck,
} from 'lucide-react';
import {
  fetchObservabilityStats,
  fetchObservabilityLogs,
  fetchObservabilityTraces,
  fetchSecuritySummary,
  type ObservabilityStats,
  type LogEntry,
  type TraceEntry,
  type SecuritySummaryResponse,
} from '../api/observability';

interface ObservabilityDashboardViewProps {
  onBackToApp?: () => void;
}

type DashboardTab = 'vitals' | 'ai' | 'traces' | 'security' | 'logs';

export const ObservabilityDashboardView: React.FC<ObservabilityDashboardViewProps> = ({ onBackToApp }) => {
  const [activeTab, setActiveTab] = useState<DashboardTab>('vitals');
  const [stats, setStats] = useState<ObservabilityStats | null>(null);
  const [securitySummary, setSecuritySummary] = useState<SecuritySummaryResponse | null>(null);
  const [traces, setTraces] = useState<TraceEntry[]>([]);
  const [totalTraces, setTotalTraces] = useState<number>(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [totalLogs, setTotalLogs] = useState<number>(0);

  const [loading, setLoading] = useState<boolean>(true);
  const [tracesLoading, setTracesLoading] = useState<boolean>(false);
  const [logLoading, setLogLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [traceRunType, setTraceRunType] = useState<string>('');
  const [traceRiskLevel, setTraceRiskLevel] = useState<string>('');
  const [traceModel, setTraceModel] = useState<string>('');

  const [logLevel, setLogLevel] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState<number>(5);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);
  const [expandedLogIdx, setExpandedLogIdx] = useState<number | null>(null);

  const timerRef = useRef<any>(null);

  const loadStats = useCallback(async () => {
    try {
      const [data, sec] = await Promise.all([
        fetchObservabilityStats(),
        fetchSecuritySummary().catch(() => null),
      ]);
      setStats(data);
      if (sec) setSecuritySummary(sec);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch observability stats');
    }
  }, []);

  const loadTraces = useCallback(async () => {
    setTracesLoading(true);
    try {
      const res = await fetchObservabilityTraces({
        run_type: traceRunType || undefined,
        risk_level: traceRiskLevel || undefined,
        model_used: traceModel || undefined,
        limit: 50,
      });
      setTraces(res.traces);
      setTotalTraces(res.total);
    } catch (err: unknown) {
      console.error('Failed to load traces', err);
    } finally {
      setTracesLoading(false);
    }
  }, [traceRunType, traceRiskLevel, traceModel]);

  const loadLogs = useCallback(async () => {
    setLogLoading(true);
    try {
      const res = await fetchObservabilityLogs({
        level: logLevel,
        search: searchQuery,
        request_id: selectedRequestId || undefined,
        limit: 100,
      });
      setLogs(res.logs);
      setTotalLogs(res.total_in_buffer);
    } catch (err: unknown) {
      console.error('Failed to load logs', err);
    } finally {
      setLogLoading(false);
    }
  }, [logLevel, searchQuery, selectedRequestId]);

  const refreshAll = useCallback(async () => {
    await Promise.all([loadStats(), loadTraces(), loadLogs()]);
    setLoading(false);
  }, [loadStats, loadTraces, loadLogs]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (autoRefreshInterval > 0) {
      timerRef.current = setInterval(() => {
        loadStats();
        if (activeTab === 'traces') loadTraces();
        if (activeTab === 'logs') loadLogs();
      }, autoRefreshInterval * 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoRefreshInterval, activeTab, loadStats, loadTraces, loadLogs]);

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / (3600 * 24));
    const h = Math.floor((seconds % (3600 * 24)) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m ${s}s`;
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#F2F2F6] overflow-hidden font-sans text-xs">
      <header className="flex items-center justify-between px-6 py-3.5 bg-white border-b border-[#E9E9EB] shadow-xs shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-xl bg-[#FFF2E5] text-[#FC8019]">
            <Activity className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-extrabold text-[#282C3F] tracking-tight">TrustDesk Observability</h1>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#EBF7E9] text-[#2A7E15] border border-[#60B246]/30">
                Live Telemetry
              </span>
            </div>
            <p className="text-[11px] text-[#686B78] mt-0.5">
              Production analytics, distributed traces, model telemetry, database latency, and security monitoring.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl px-2.5 py-1.5 text-xs text-[#282C3F]">
            <Clock className="w-3.5 h-3.5 text-[#686B78]" />
            <span className="text-[11px] text-[#686B78]">Auto-refresh:</span>
            <select
              value={autoRefreshInterval}
              onChange={(e) => setAutoRefreshInterval(Number(e.target.value))}
              className="bg-transparent font-semibold text-[#FC8019] focus:outline-hidden cursor-pointer"
            >
              <option value={0}>Off</option>
              <option value={3}>3s</option>
              <option value={5}>5s</option>
              <option value={15}>15s</option>
              <option value={30}>30s</option>
            </select>
          </div>

          <button
            type="button"
            onClick={refreshAll}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#FFF2E5] text-[#FC8019] hover:bg-[#FFE6D0] rounded-xl font-semibold transition-all cursor-pointer shadow-xs disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Sync</span>
          </button>

          {onBackToApp && (
            <button
              type="button"
              onClick={onBackToApp}
              className="px-3.5 py-1.5 bg-[#282C3F] text-white hover:bg-[#1E212D] rounded-xl font-semibold transition-all cursor-pointer shadow-xs"
            >
              ← Support Workspace
            </button>
          )}
        </div>
      </header>

      <nav className="flex items-center gap-2 px-6 bg-white border-b border-[#E9E9EB] shrink-0 overflow-x-auto">
        <button
          type="button"
          onClick={() => setActiveTab('vitals')}
          className={`flex items-center gap-2 py-3 px-3 font-bold text-xs border-b-2 transition-all cursor-pointer ${
            activeTab === 'vitals'
              ? 'border-[#FC8019] text-[#FC8019]'
              : 'border-transparent text-[#686B78] hover:text-[#282C3F]'
          }`}
        >
          <Server className="w-3.5 h-3.5" />
          <span>Infrastructure & Vitals</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('ai')}
          className={`flex items-center gap-2 py-3 px-3 font-bold text-xs border-b-2 transition-all cursor-pointer ${
            activeTab === 'ai'
              ? 'border-[#FC8019] text-[#FC8019]'
              : 'border-transparent text-[#686B78] hover:text-[#282C3F]'
          }`}
        >
          <Bot className="w-3.5 h-3.5" />
          <span>AI & LLM Telemetry</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab('traces');
            loadTraces();
          }}
          className={`flex items-center gap-2 py-3 px-3 font-bold text-xs border-b-2 transition-all cursor-pointer ${
            activeTab === 'traces'
              ? 'border-[#FC8019] text-[#FC8019]'
              : 'border-transparent text-[#686B78] hover:text-[#282C3F]'
          }`}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>Distributed Traces ({totalTraces})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('security')}
          className={`flex items-center gap-2 py-3 px-3 font-bold text-xs border-b-2 transition-all cursor-pointer ${
            activeTab === 'security'
              ? 'border-[#FC8019] text-[#FC8019]'
              : 'border-transparent text-[#686B78] hover:text-[#282C3F]'
          }`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>Fraud & Security Intelligence</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab('logs');
            loadLogs();
          }}
          className={`flex items-center gap-2 py-3 px-3 font-bold text-xs border-b-2 transition-all cursor-pointer ${
            activeTab === 'logs'
              ? 'border-[#FC8019] text-[#FC8019]'
              : 'border-transparent text-[#686B78] hover:text-[#282C3F]'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>System Logs ({totalLogs})</span>
        </button>
      </nav>

      {error && (
        <div className="mx-6 mt-4 p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-[#C62828] font-semibold flex items-center justify-between">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)} className="text-[#C62828] hover:underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {activeTab === 'vitals' && stats && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">System Uptime</span>
                  <Server className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-xl font-extrabold text-[#282C3F] font-mono">
                  {formatUptime(stats.system.uptime_seconds)}
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="w-2 h-2 rounded-full bg-[#60B246]" />
                  <span className="text-[11px] text-[#2A7E15] font-semibold uppercase tracking-wider">
                    {stats.system.status}
                  </span>
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">PostgreSQL Database</span>
                  <Database className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-xl font-extrabold text-[#282C3F] font-mono">
                  {stats.system.database_latency_ms !== undefined ? `${stats.system.database_latency_ms} ms` : 'Connected'}
                </div>
                <div className="text-[11px] text-[#686B78] mt-2">
                  Round-trip latency • pgvector enabled
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Redis Cache & Queue</span>
                  <Zap className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-xl font-extrabold text-[#282C3F] font-mono">
                  {stats.system.redis_latency_ms !== undefined ? `${stats.system.redis_latency_ms} ms` : 'Online'}
                </div>
                <div className="text-[11px] text-[#686B78] mt-2">
                  Memory: {stats.system.redis_memory_mb || 0} MB • ARQ Worker Pool
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Host Resources</span>
                  <Cpu className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-xl font-extrabold text-[#282C3F] font-mono">
                  {stats.system.memory_usage_mb} MB
                </div>
                <div className="text-[11px] text-[#686B78] mt-2">
                  Process CPU: {stats.system.cpu_percent}%
                </div>
              </div>
            </div>

            {stats.database_inventory && (
              <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Database Table Inventory</h2>
                <div className="grid grid-cols-3 md:grid-cols-9 gap-3 text-center">
                  {Object.entries(stats.database_inventory).map(([tbl, cnt]) => (
                    <div key={tbl} className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                      <div className="text-[10px] text-[#686B78] font-bold uppercase tracking-wider truncate">{tbl}</div>
                      <div className="text-base font-extrabold text-[#282C3F] font-mono mt-1">{cnt}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Live Support Queues</h2>
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Open Unassigned</span>
                    <div className="text-lg font-bold text-[#FC8019] mt-1">{stats.queues.open}</div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Actively Handled</span>
                    <div className="text-lg font-bold text-[#282C3F] mt-1">{stats.queues.working}</div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Escalated High Risk</span>
                    <div className="text-lg font-bold text-[#EC3D25] mt-1">{stats.queues.escalated}</div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Successfully Resolved</span>
                    <div className="text-lg font-bold text-[#60B246] mt-1">{stats.queues.resolved}</div>
                  </div>
                </div>
              </div>

              <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Automated Actions Governance</h2>
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 bg-[#FFF9F5] rounded-xl border border-[#FFD7B0]">
                    <span className="text-[11px] text-[#FC8019] font-semibold">Pending Approval</span>
                    <div className="text-lg font-bold text-[#FC8019] mt-1">{stats.actions.pending_approval}</div>
                  </div>
                  <div className="p-3 bg-[#EBF7E9] rounded-xl border border-[#60B246]/30">
                    <span className="text-[11px] text-[#2A7E15] font-semibold">Executed</span>
                    <div className="text-lg font-bold text-[#2A7E15] mt-1">{stats.actions.executed}</div>
                  </div>
                  <div className="p-3 bg-[#FDF0EE] rounded-xl border border-[#F5A398]">
                    <span className="text-[11px] text-[#C62828] font-semibold">Rejected</span>
                    <div className="text-lg font-bold text-[#C62828] mt-1">{stats.actions.rejected}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'ai' && stats && stats.ai_telemetry && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Total Model Invocations</span>
                  <Bot className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-2xl font-extrabold text-[#282C3F] font-mono">
                  {stats.ai_telemetry.total_runs}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  Autonomous triage, drafting & actions
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Total Tokens Processed</span>
                  <Zap className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-2xl font-extrabold text-[#282C3F] font-mono">
                  {stats.ai_telemetry.total_tokens.toLocaleString()}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  Prompt: {stats.ai_telemetry.total_prompt_tokens.toLocaleString()} • Completion: {stats.ai_telemetry.total_completion_tokens.toLocaleString()}
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Estimated LLM Spend</span>
                  <DollarSign className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-2xl font-extrabold text-[#2A7E15] font-mono">
                  ${stats.ai_telemetry.estimated_cost_usd}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  Blended rate via OpenRouter routing
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Guardrail Injections Blocked</span>
                  <ShieldCheck className="w-4 h-4 text-[#60B246]" />
                </div>
                <div className="text-2xl font-extrabold text-[#EC3D25] font-mono">
                  {stats.ai_telemetry.guardrail_threats_blocked.prompt_injection}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  Prompt attacks quarantined
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Model Invocations Distribution</h2>
                <div className="space-y-3">
                  {Object.entries(stats.ai_telemetry.models_used).map(([model, cnt]) => {
                    const pct = stats.ai_telemetry ? Math.round((cnt / (stats.ai_telemetry.total_runs || 1)) * 100) : 0;
                    return (
                      <div key={model} className="space-y-1">
                        <div className="flex justify-between font-semibold text-xs">
                          <span className="text-[#282C3F] font-mono">{model}</span>
                          <span className="text-[#686B78]">{cnt} calls ({pct}%)</span>
                        </div>
                        <div className="w-full h-2 bg-[#F2F2F6] rounded-full overflow-hidden">
                          <div className="h-full bg-[#FC8019] rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Latency Percentiles by Model (ms)</h2>
                <div className="space-y-3 overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-[#E9E9EB] text-[#686B78] text-[11px]">
                        <th className="pb-2">Model</th>
                        <th className="pb-2">p50</th>
                        <th className="pb-2">p90</th>
                        <th className="pb-2">p95</th>
                        <th className="pb-2">p99</th>
                        <th className="pb-2">Avg</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E9E9EB] font-mono text-xs text-[#282C3F]">
                      {Object.entries(stats.ai_telemetry.latency_by_model).map(([model, p]) => (
                        <tr key={model} className="hover:bg-[#FFFBF7]">
                          <td className="py-2 font-semibold font-sans truncate max-w-[140px]">{model}</td>
                          <td className="py-2">{p.p50}</td>
                          <td className="py-2">{p.p90}</td>
                          <td className="py-2 text-[#FC8019] font-bold">{p.p95}</td>
                          <td className="py-2">{p.p99}</td>
                          <td className="py-2">{p.avg}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'traces' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
              <div className="flex items-center gap-3">
                <span className="font-semibold text-xs text-[#282C3F]">Filter Traces:</span>
                <select
                  value={traceRunType}
                  onChange={(e) => setTraceRunType(e.target.value)}
                  className="p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-xs text-[#282C3F] focus:outline-hidden"
                >
                  <option value="">All Run Types</option>
                  <option value="triage">Triage</option>
                  <option value="draft">Draft Generation</option>
                  <option value="action">Tool Execution</option>
                  <option value="eval">Evaluation</option>
                </select>

                <select
                  value={traceRiskLevel}
                  onChange={(e) => setTraceRiskLevel(e.target.value)}
                  className="p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-xs text-[#282C3F] focus:outline-hidden"
                >
                  <option value="">All Risk Levels</option>
                  <option value="low">Low Risk</option>
                  <option value="medium">Medium Risk</option>
                  <option value="high">High Risk</option>
                  <option value="critical">Critical Risk</option>
                </select>

                <select
                  value={traceModel}
                  onChange={(e) => setTraceModel(e.target.value)}
                  className="p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-xs text-[#282C3F] focus:outline-hidden"
                >
                  <option value="">All Models</option>
                  <option value="google/gemini-2.0-flash-001">gemini-2.0-flash-001</option>
                  <option value="google/gemini-2.5-flash-preview-05-20">gemini-2.5-flash</option>
                  <option value="google/gemini-2.5-pro-preview-05-06">gemini-2.5-pro</option>
                </select>
              </div>

              <button
                type="button"
                onClick={loadTraces}
                disabled={tracesLoading}
                className="px-3.5 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] transition-all cursor-pointer shadow-xs disabled:opacity-50"
              >
                {tracesLoading ? 'Loading...' : 'Apply Filter'}
              </button>
            </div>

            <div className="bg-white border border-[#E9E9EB] rounded-2xl shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="bg-[#F9F9FB] border-b border-[#E9E9EB] text-[#686B78] text-[11px] font-semibold uppercase tracking-wider">
                      <th className="py-3 px-4">Run Type</th>
                      <th className="py-3 px-4">Model Used</th>
                      <th className="py-3 px-4">Latency</th>
                      <th className="py-3 px-4">Tokens</th>
                      <th className="py-3 px-4">Risk Level</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E9E9EB] text-xs">
                    {traces.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-8 text-center text-[#93959F]">
                          No trace records found matching criteria.
                        </td>
                      </tr>
                    ) : (
                      traces.map((tr) => (
                        <React.Fragment key={tr.id}>
                          <tr
                            onClick={() => setExpandedTraceId(expandedTraceId === tr.id ? null : tr.id)}
                            className="hover:bg-[#FFFBF7] transition-colors cursor-pointer"
                          >
                            <td className="py-3 px-4 font-bold text-[#282C3F] uppercase tracking-wider text-[10px]">
                              {tr.run_type}
                            </td>
                            <td className="py-3 px-4 font-mono text-[11px] text-[#686B78]">
                              {tr.model_used}
                            </td>
                            <td className="py-3 px-4 font-mono font-bold text-[#FC8019]">
                              {tr.latency_ms !== null ? `${tr.latency_ms} ms` : '—'}
                            </td>
                            <td className="py-3 px-4 font-mono text-[11px] text-[#282C3F]">
                              {tr.token_usage?.total_tokens || 0}
                            </td>
                            <td className="py-3 px-4">
                              <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                                tr.risk_level === 'critical' || tr.risk_level === 'high'
                                  ? 'bg-[#FDF0EE] text-[#C62828] border border-[#F5A398]'
                                  : tr.risk_level === 'medium'
                                  ? 'bg-[#FFF9F5] text-[#FC8019] border border-[#FFD7B0]'
                                  : 'bg-[#EBF7E9] text-[#2A7E15] border border-[#60B246]/30'
                              }`}>
                                {tr.risk_level || 'low'}
                              </span>
                            </td>
                            <td className="py-3 px-4 font-medium text-[#282C3F]">
                              {tr.final_status}
                            </td>
                            <td className="py-3 px-4 text-[#93959F] text-[11px]">
                              {tr.created_at ? new Date(tr.created_at).toLocaleTimeString() : '—'}
                            </td>
                          </tr>
                          {expandedTraceId === tr.id && (
                            <tr className="bg-[#FFFBF7]">
                              <td colSpan={7} className="p-4 space-y-2 text-[11px]">
                                <div className="font-mono text-[#686B78]">
                                  Trace ID: <span className="text-[#282C3F] font-bold">{tr.id}</span> • Run ID: {tr.run_id} • Ticket ID: {tr.ticket_id || 'N/A'}
                                </div>
                                <div className="p-3 bg-white border border-[#E9E9EB] rounded-xl font-mono overflow-x-auto">
                                  <div>Tokens: {JSON.stringify(tr.token_usage)}</div>
                                  <div>Retrieved Docs: {tr.retrieved_doc_count}</div>
                                  <div>Guardrail: {JSON.stringify(tr.guardrail_result)}</div>
                                  <div>Risk Factors: {JSON.stringify(tr.risk_factors)}</div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Critical Security Events (24h)</span>
                  <ShieldAlert className="w-4 h-4 text-[#EC3D25]" />
                </div>
                <div className="text-2xl font-extrabold text-[#EC3D25] font-mono">
                  {securitySummary?.critical_events_24h || 0}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  High-risk actions & blocked attacks
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Prompt Injections Quarantined</span>
                  <Lock className="w-4 h-4 text-[#FC8019]" />
                </div>
                <div className="text-2xl font-extrabold text-[#FC8019] font-mono">
                  {securitySummary?.prompt_injections_blocked_24h || 0}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  Input fencing triggered
                </div>
              </div>

              <div className="p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <div className="flex items-center justify-between text-[#686B78] mb-2">
                  <span className="font-semibold text-xs">Idempotency & Replay Blocks</span>
                  <CheckCircle className="w-4 h-4 text-[#60B246]" />
                </div>
                <div className="text-2xl font-extrabold text-[#2A7E15] font-mono">
                  {securitySummary?.idempotency_conflicts_prevented_24h || 0}
                </div>
                <div className="text-[11px] text-[#686B78] mt-1">
                  Duplicate coupon & action attempts thwarted
                </div>
              </div>
            </div>

            {stats?.fraud_mitigation?.coupon_stats && (
              <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
                <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Refund & Coupon Fraud Prevention</h2>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Total Issued</span>
                    <div className="text-lg font-bold text-[#282C3F] mt-1">
                      {stats.fraud_mitigation.coupon_stats.total_issued}
                    </div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Active Unredeemed</span>
                    <div className="text-lg font-bold text-[#FC8019] mt-1">
                      {stats.fraud_mitigation.coupon_stats.active}
                    </div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Successfully Redeemed</span>
                    <div className="text-lg font-bold text-[#60B246] mt-1">
                      {stats.fraud_mitigation.coupon_stats.redeemed}
                    </div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Expired</span>
                    <div className="text-lg font-bold text-[#93959F] mt-1">
                      {stats.fraud_mitigation.coupon_stats.expired}
                    </div>
                  </div>
                  <div className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB]">
                    <span className="text-[11px] text-[#686B78]">Total Volume Issued</span>
                    <div className="text-lg font-bold text-[#282C3F] mt-1">
                      ₹{stats.fraud_mitigation.coupon_stats.total_refund_value_inr}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="p-5 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
              <h2 className="text-sm font-extrabold text-[#282C3F] mb-3">Live Security Threat Audit Trail</h2>
              <div className="space-y-2">
                {!securitySummary?.recent_threats || securitySummary.recent_threats.length === 0 ? (
                  <div className="text-center py-6 text-[#93959F]">No high-risk threats detected in last 24h.</div>
                ) : (
                  securitySummary.recent_threats.map((threat) => (
                    <div key={threat.id} className="p-3 bg-[#FFFBF7] border border-[#FFD7B0] rounded-xl flex items-center justify-between">
                      <div>
                        <div className="font-bold text-[#282C3F]">{threat.action}</div>
                        <div className="text-[11px] text-[#686B78] mt-0.5">
                          Actor: {threat.actor_id || 'Anonymous'} • Resource: {threat.resource_type} • Risk: {threat.risk_level}
                        </div>
                      </div>
                      <span className="text-[11px] text-[#93959F] font-mono">
                        {threat.created_at ? new Date(threat.created_at).toLocaleTimeString() : ''}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs">
              <div className="flex items-center gap-3">
                <span className="font-semibold text-xs text-[#282C3F]">Filter Level:</span>
                <select
                  value={logLevel}
                  onChange={(e) => setLogLevel(e.target.value)}
                  className="p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-xs text-[#282C3F] focus:outline-hidden"
                >
                  <option value="ALL">All Levels</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="DEBUG">DEBUG</option>
                </select>

                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[#93959F]" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search logs message..."
                    className="pl-8 pr-3 py-1.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-xs text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
                  />
                </div>

                <input
                  type="text"
                  value={selectedRequestId || ''}
                  onChange={(e) => setSelectedRequestId(e.target.value.trim() || null)}
                  placeholder="Filter by Request ID..."
                  className="px-3 py-1.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-xs text-[#282C3F] focus:outline-hidden focus:border-[#FC8019]"
                />
              </div>

              <button
                type="button"
                onClick={loadLogs}
                disabled={logLoading}
                className="px-3.5 py-2 bg-[#FC8019] text-white rounded-xl font-semibold hover:bg-[#E26A00] transition-all cursor-pointer shadow-xs disabled:opacity-50"
              >
                {logLoading ? 'Filtering...' : 'Search Logs'}
              </button>
            </div>

            <div className="bg-[#1E212D] text-[#E9E9EB] rounded-2xl p-4 font-mono text-xs shadow-xs space-y-2 max-h-[600px] overflow-y-auto">
              {logs.length === 0 ? (
                <div className="text-center py-8 text-[#686B78]">No log entries in ring buffer.</div>
              ) : (
                logs.map((log, idx) => (
                  <div
                    key={idx}
                    onClick={() => setExpandedLogIdx(expandedLogIdx === idx ? null : idx)}
                    className="p-2 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[#93959F] text-[10px]">{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                        log.level === 'ERROR'
                          ? 'bg-[#C62828] text-white'
                          : log.level === 'WARNING'
                          ? 'bg-[#FC8019] text-white'
                          : 'bg-white/10 text-white'
                      }`}>
                        {log.level}
                      </span>
                      <span className="text-[#FC8019] text-[11px]">[{log.component}]</span>
                      <span className="text-white truncate flex-1">{log.message}</span>
                    </div>
                    {expandedLogIdx === idx && (
                      <div className="mt-2 p-2 bg-black/40 rounded text-[11px] text-[#93959F] space-y-1">
                        <div>Logger: {log.logger}</div>
                        <div>Request ID: {log.request_id || 'N/A'}</div>
                        <div>User ID: {log.user_id || 'N/A'}</div>
                        <div className="text-white whitespace-pre-wrap">{log.message}</div>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
