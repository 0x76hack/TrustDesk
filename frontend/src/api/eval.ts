import { apiFetch } from './client';
import type { EvalRun, EvalRunDetail } from '../types/eval';

export async function triggerEvalRun(): Promise<{ run_id: string; message: string }> {
  return apiFetch<{ run_id: string; message: string }>('/eval/run', {
    method: 'POST',
  });
}

export async function listEvalRuns(): Promise<EvalRun[]> {
  return apiFetch<EvalRun[]>('/eval/runs');
}

export async function getEvalRunDetail(runId: string): Promise<EvalRunDetail> {
  return apiFetch<EvalRunDetail>(`/eval/runs/${runId}`);
}
