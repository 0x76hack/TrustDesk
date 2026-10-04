import React, { useState } from 'react';
import type { TicketDetail } from '../../types/ticket';
import type { UserRole } from '../../types/auth';
import { RiskBadge, StatusBadge, CategoryPill } from '../common/Badge';

interface WorkspaceHeaderProps {
  ticket: TicketDetail;
  currentUserRole?: UserRole;
  currentUserId?: string;
  onBackToQueue?: () => void;
  onAssignToMe: () => void;
  onAssignToAgent?: (userId: string) => void;
  onUnassign: () => void;
  onOpenEscalateModal: () => void;
  onOpenCloseModal: () => void;
  onOpenRefundModal?: () => void;
  availableAgents?: Array<{ id: string; name: string; username: string; role: string }>;
  isLoading?: boolean;
}

export const WorkspaceHeader: React.FC<WorkspaceHeaderProps> = ({
  ticket,
  currentUserRole = 'agent',
  currentUserId,
  onBackToQueue,
  onAssignToMe,
  onAssignToAgent,
  onUnassign,
  onOpenEscalateModal,
  onOpenCloseModal,
  onOpenRefundModal,
  availableAgents = [],
  isLoading = false,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyId = () => {
    navigator.clipboard.writeText(ticket.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const isResolved = ticket.status.toLowerCase() === 'resolved';
  const isWorking = ticket.status.toLowerCase() === 'working';
  const isEscalated = ticket.status.toLowerCase() === 'escalated' || ticket.escalation_flag;
  const isAssignedToMe = Boolean(currentUserId && ticket.assigned_to === currentUserId);

  const getAssigneeLabel = () => {
    if (!ticket.assigned_to) return 'Unassigned';
    if (
      ticket.assignee?.username === 'ai_agent' ||
      ticket.assignee_name?.toLowerCase().includes('ai agent') ||
      ticket.assigned_to.toLowerCase().includes('ai')
    ) {
      return 'TrustDesk AI Agent';
    }
    if (isAssignedToMe) {
      return 'You';
    }
    if (ticket.assignee_name) {
      return ticket.assignee_name;
    }
    return `Operative #${ticket.assigned_to.slice(0, 8)}`;
  };

  return (
    <div className="h-16 bg-white border-b border-[#E9E9EB] px-5 flex items-center justify-between gap-4 shrink-0 font-sans text-xs shadow-2xs">
      <div className="flex items-center gap-3 min-w-0">
        {onBackToQueue && (
          <button
            type="button"
            onClick={onBackToQueue}
            className="px-3 py-1.5 rounded-lg bg-[#282C3F] text-white font-semibold hover:bg-[#1C1C24] transition-all shadow-2xs cursor-pointer shrink-0 text-xs flex items-center gap-1.5"
            title="Return to Ticket Queues"
          >
            <span>←</span>
            <span>Back to Queues</span>
          </button>
        )}

        <button
          type="button"
          onClick={handleCopyId}
          className="px-2.5 py-1.5 rounded-lg bg-[#F4F5F8] border border-[#D4D5D9] font-mono font-medium text-[#282C3F] hover:border-[#FC8019] hover:text-[#FC8019] transition-colors shrink-0 cursor-pointer text-xs"
          title="Click to copy full UUID"
        >
          #{ticket.id.slice(0, 8)} {copied ? '✓' : ''}
        </button>

        <h2 className="text-sm font-bold text-[#282C3F] truncate max-w-sm">
          {ticket.subject}
        </h2>

        <div className="flex items-center gap-2 shrink-0">
          <CategoryPill category={ticket.category} />
          <RiskBadge risk={ticket.risk_level} />
        </div>
      </div>

      <div className="flex items-center gap-3 shrink-0">
        <StatusBadge status={ticket.status} escalationFlag={ticket.escalation_flag} />

        <div className="flex items-center gap-2">
          <div className={`px-2.5 py-1 rounded-lg border text-xs font-medium flex items-center gap-1.5 ${
            isAssignedToMe
              ? 'bg-[#EBF7E9] border-[#60B246]/40 text-[#2A7E15]'
              : 'bg-[#F4F5F8] border-[#E9E9EB] text-[#282C3F]'
          }`}>
            <span className="text-[#93959F] text-[11px]">Assigned:</span>
            <span className="font-semibold">{getAssigneeLabel()}</span>
          </div>

          {!isResolved && (
            <div className="flex items-center gap-1.5">
              {!isAssignedToMe && (
                <button
                  type="button"
                  onClick={onAssignToMe}
                  disabled={isLoading}
                  className="px-2.5 py-1 rounded-lg font-semibold bg-[#FC8019] text-white hover:bg-[#E26A00] transition-all shadow-xs cursor-pointer text-xs"
                  title="Assign ticket to myself"
                >
                  Assign to Me
                </button>
              )}

              {availableAgents && availableAgents.length > 0 && onAssignToAgent && (
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) {
                      onAssignToAgent(e.target.value);
                    }
                  }}
                  disabled={isLoading}
                  className="py-1 px-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-xs text-[#282C3F] focus:outline-hidden hover:border-[#FC8019] cursor-pointer"
                  title="Assign or reassign ticket to an operative"
                >
                  <option value="" disabled>Assign to...</option>
                  {availableAgents.map((ag) => (
                    <option key={ag.id} value={ag.id}>
                      {ag.name || ag.username} ({ag.role === 'admin' ? 'Admin' : ag.role === 'senior_agent' ? 'Senior' : 'Agent'})
                    </option>
                  ))}
                </select>
              )}
            </div>
          )}
        </div>

        {isEscalated && (
          currentUserRole === 'senior_agent' || currentUserRole === 'admin' ? (
            !isAssignedToMe && (
              <button
                type="button"
                onClick={onAssignToMe}
                disabled={isLoading}
                className="px-3 py-1.5 rounded-lg font-semibold bg-[#EC3D25] text-white hover:bg-[#D32F2F] transition-all shadow-xs cursor-pointer text-xs"
              >
                Claim Escalated
              </button>
            )
          ) : (
            <div className="px-3 py-1 rounded-lg bg-[#FDF0EE] border border-[#EC3D25]/30 font-medium text-[#EC3D25] text-xs">
              Awaiting Senior Review
            </div>
          )
        )}

        {ticket.order_id && !ticket.coupon_code && !isResolved && onOpenRefundModal && (
          <button
            type="button"
            onClick={onOpenRefundModal}
            disabled={isLoading}
            className="px-3.5 py-1.5 rounded-lg font-semibold bg-[#FFF2E5] text-[#FC8019] border border-[#FC8019]/40 hover:bg-[#FC8019] hover:text-white transition-all shadow-xs cursor-pointer text-xs"
          >
            Issue Refund
          </button>
        )}

        {isWorking && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onUnassign}
              disabled={isLoading}
              className="px-3 py-1.5 rounded-lg border border-[#D4D5D9] bg-white text-[#686B78] hover:bg-[#F4F5F8] hover:text-[#282C3F] transition-colors cursor-pointer text-xs font-medium"
              title="Release ticket back to Open Queue"
            >
              Release
            </button>

            <button
              type="button"
              onClick={onOpenEscalateModal}
              disabled={isLoading}
              className="px-3 py-1.5 rounded-lg font-semibold bg-[#FDF0EE] text-[#EC3D25] border border-[#EC3D25]/30 hover:bg-[#EC3D25] hover:text-white transition-all cursor-pointer text-xs"
            >
              Escalate
            </button>

            <button
              type="button"
              onClick={onOpenCloseModal}
              disabled={isLoading}
              className="px-3.5 py-1.5 rounded-lg font-semibold bg-[#60B246] text-white hover:bg-[#4E9B36] transition-all shadow-xs cursor-pointer text-xs"
            >
              Resolve & Close
            </button>
          </div>
        )}

        {isResolved && (
          <div className="px-3 py-1 rounded-lg bg-[#EBF7E9] border border-[#60B246]/40 font-semibold text-[#2A7E15] text-xs">
            Closed & Resolved
          </div>
        )}
      </div>
    </div>
  );
};
