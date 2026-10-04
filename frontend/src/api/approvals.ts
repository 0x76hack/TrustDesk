import { apiFetch } from './client';
import type { PendingApproval, ApprovalDecisionRequest, ApprovalResponse } from '../types/approval';

export async function listPendingApprovals(): Promise<PendingApproval[]> {
  return apiFetch<PendingApproval[]>('/approvals/pending');
}

export async function submitApprovalDecision(
  actionId: string,
  req: ApprovalDecisionRequest
): Promise<ApprovalResponse> {
  return apiFetch<ApprovalResponse>(`/approvals/${actionId}`, {
    method: 'POST',
    body: JSON.stringify(req),
  });
}
