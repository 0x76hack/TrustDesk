export interface PendingApproval {
  id: string;
  ticket_id: string;
  run_id?: string | null;
  tool_id?: string | null;
  tool_name?: string | null;
  payload?: Record<string, unknown> | null;
  risk_level: string;
  status: string;
  idempotency_key: string;
  created_at: string;
  executed_at?: string | null;
  ticket_subject?: string;
  customer_name?: string;
}

export interface ApprovalDecisionRequest {
  decision: 'approved' | 'rejected';
  reason?: string;
}

export interface ApprovalResponse {
  id: string;
  action_id: string;
  approver_id: string;
  decision: 'approved' | 'rejected';
  reason?: string | null;
  decided_at?: string;
}
