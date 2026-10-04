import React, { useState } from 'react';
import type { PendingApproval } from '../types/approval';
import type { UserRole } from '../types/auth';
import { submitApprovalDecision } from '../api/approvals';
import { Modal } from '../components/common/Modal';
import { RiskBadge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';

interface ApprovalsViewProps {
  approvals: PendingApproval[];
  isLoading: boolean;
  userRole: UserRole;
  onRefresh: () => void;
  onViewTicket: (ticketId: string) => void;
}

export const ApprovalsView: React.FC<ApprovalsViewProps> = ({
  approvals,
  isLoading,
  userRole,
  onRefresh,
  onViewTicket,
}) => {
  const [selectedAction, setSelectedAction] = useState<PendingApproval | null>(null);
  const [decisionType, setDecisionType] = useState<'approved' | 'rejected'>('approved');
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAuthorized = userRole === 'senior_agent' || userRole === 'admin';

  const handleOpenDecision = (action: PendingApproval, decision: 'approved' | 'rejected') => {
    setSelectedAction(action);
    setDecisionType(decision);
    setReason('');
    setError(null);
  };

  const handleSubmitDecision = async () => {
    if (!selectedAction) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await submitApprovalDecision(selectedAction.id, {
        decision: decisionType,
        reason: reason.trim() || undefined,
      });
      setSelectedAction(null);
      onRefresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to submit decision');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 text-left font-sans text-xs">
      <div className="border-b border-[#E9E9EB] pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-[#282C3F]">
          Operational Approval Center
        </h1>
        <p className="text-xs text-[#686B78] mt-0.5">
          Review and authorize gated financial and operational tool executions.
        </p>
      </div>

      {!isAuthorized && (
        <div className="p-3 rounded-xl bg-[#FFF9F5] border border-[#FFD7B0] text-[#FC8019] font-bold">
          [RESTRICTION] OPERATIVE ROLE [AGENT] IS RESTRICTED. APPROVAL REQUIRES SENIOR AGENT OR ADMIN CREDENTIALS.
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="p-5 bg-white rounded-2xl border border-[#E9E9EB] shadow-xs space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-8 w-32 ml-auto" />
            </div>
          ))}
        </div>
      ) : approvals.length === 0 ? (
        <div className="p-8 bg-white rounded-2xl border border-[#E9E9EB] shadow-xs text-center text-[#686B78] space-y-1">
          <div className="font-bold text-[#282C3F]">[ZERO PENDING APPROVALS]</div>
          <p className="font-sans text-xs">All sensitive operational tool actions have been processed.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {approvals.map((action) => (
            <div
              key={action.id}
              className="p-5 bg-white rounded-2xl border border-[#E9E9EB] shadow-xs space-y-3.5"
            >
              <div className="flex items-start justify-between gap-4 border-b border-[#F2F2F6] pb-2.5">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-[#282C3F]">
                      ACTION: {action.tool_name || 'TOOL'}
                    </span>
                    <RiskBadge risk={action.risk_level} />
                    <span className="text-[10px] text-[#93959F]">
                      [#{action.id.slice(0, 8)}]
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => onViewTicket(action.ticket_id)}
                    className="text-[#FC8019] hover:text-[#E26A00] underline font-bold cursor-pointer"
                  >
                    LINKED TICKET: #{action.ticket_id.slice(0, 8)}
                  </button>
                </div>

                <span className="text-[10px] text-[#93959F]">
                  {new Date(action.created_at).toLocaleString()}
                </span>
              </div>

              <div className="space-y-1.5">
                <span className="font-bold text-[#282C3F] text-[11px]">PROPOSED PAYLOAD:</span>
                <pre className="p-3 bg-[#F9F9FB] rounded-xl border border-[#E9E9EB] text-[10px] text-[#282C3F] overflow-x-auto font-mono">
                  {JSON.stringify(action.payload || {}, null, 2)}
                </pre>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[#F2F2F6]">
                <span className="text-[10px] text-[#93959F] font-mono">
                  IDEMPOTENCY: {action.idempotency_key.slice(0, 16)}...
                </span>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleOpenDecision(action, 'rejected')}
                    disabled={!isAuthorized}
                    className="px-3.5 py-1.5 rounded-xl border border-[#F5A398] text-[#EC3D25] font-bold hover:bg-[#FDF0EE] transition-colors disabled:opacity-50 cursor-pointer"
                  >
                    [REJECT ACTION]
                  </button>
                  <button
                    type="button"
                    onClick={() => handleOpenDecision(action, 'approved')}
                    disabled={!isAuthorized}
                    className="px-3.5 py-1.5 rounded-xl bg-[#60B246] hover:bg-[#4E9B36] active:bg-[#3D8028] text-white font-bold shadow-xs transition-all disabled:opacity-50 cursor-pointer"
                  >
                    [APPROVE & EXECUTE]
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedAction && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedAction(null)}
          title={decisionType === 'approved' ? 'CONFIRM ACTION APPROVAL' : 'REJECT PROPOSED ACTION'}
          description={`Review and register final decision for action ${selectedAction.tool_name}.`}
          footer={
            <div className="flex justify-between w-full font-mono text-xs">
              <button
                type="button"
                onClick={() => setSelectedAction(null)}
                className="text-[#686B78] hover:text-[#282C3F] underline cursor-pointer"
              >
                [CANCEL]
              </button>
              <button
                type="button"
                onClick={handleSubmitDecision}
                disabled={isSubmitting}
                className={`px-4 py-2 rounded-xl text-white font-bold shadow-xs transition-all cursor-pointer ${
                  decisionType === 'approved'
                    ? 'bg-[#60B246] hover:bg-[#4E9B36] active:bg-[#3D8028]'
                    : 'bg-[#EC3D25] hover:bg-[#C62828] active:bg-[#B71C1C]'
                }`}
              >
                {isSubmitting ? '[RECORDING...]' : `[CONFIRM ${decisionType.toUpperCase()}]`}
              </button>
            </div>
          }
        >
          <div className="space-y-3 font-mono text-xs text-left">
            {error && (
              <div className="p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-[#C62828] font-bold">
                [ERROR] {error}
              </div>
            )}
            <div>
              <label className="block font-bold text-[#282C3F] mb-1.5">
                DECISION NOTES / AUDIT RATIONALE (OPTIONAL):
              </label>
              <textarea
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Specify justification for supervisor audit log..."
                className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] font-sans text-xs focus:outline-hidden focus:border-[#FC8019] focus:ring-1 focus:ring-[#FC8019] resize-none transition-all"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
