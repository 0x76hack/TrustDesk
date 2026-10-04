import React from 'react';
import type { Ticket } from '../../types/ticket';
import type { User } from '../../types/auth';
import { StatusBadge, CategoryPill } from '../common/Badge';

interface TicketTableProps {
  tickets: Ticket[];
  currentUser: User | null;
  onSelectTicket: (ticketId: string) => void;
  onClaim?: (ticketId: string) => Promise<void>;
  isLoading?: boolean;
}

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return '--';
  const created = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - created.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return '<1m ago';
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function formatAssignee(ticket: Ticket): string {
  if (ticket.status === 'resolved') {
    if (ticket.close_reason?.startsWith('security_attack_blocked')) {
      return 'Auto-Closed (Security Defense)';
    }
    if (ticket.close_reason?.startsWith('duplicate_coupon')) {
      return 'Auto-Closed (Duplicate Replay)';
    }
    if (
      ticket.assignee?.username === 'ai_agent' ||
      ticket.assignee_name?.toLowerCase().includes('ai agent') ||
      ticket.assigned_to?.toLowerCase().includes('ai')
    ) {
      return 'Auto-Resolved by AI';
    }
    if (ticket.assignee_name) {
      return `Closed by ${ticket.assignee_name}`;
    }
    if (ticket.assignee?.name) {
      return `Closed by ${ticket.assignee.name}`;
    }
    return 'Resolved (System)';
  }
  if (!ticket.assigned_to) return 'Unassigned';
  if (
    ticket.assignee?.username === 'ai_agent' ||
    ticket.assignee?.name?.toLowerCase().includes('ai agent') ||
    ticket.assigned_to.toLowerCase().includes('ai')
  ) {
    return 'TrustDesk AI Agent';
  }
  if (ticket.assignee_name) {
    return ticket.assignee_name;
  }
  if (ticket.assignee?.name) {
    return ticket.assignee.name;
  }
  return `Operative #${ticket.assigned_to.slice(0, 8)}`;
}

export const TicketTable: React.FC<TicketTableProps> = ({
  tickets,
  currentUser,
  onSelectTicket,
  onClaim,
  isLoading = false,
}) => {
  const canClaim = (ticket: Ticket): boolean => {
    if (ticket.status === 'resolved') return false;
    if (ticket.assigned_to) return false;
    if (ticket.status === 'escalated') {
      return currentUser?.role === 'senior_agent' || currentUser?.role === 'admin';
    }
    return true;
  };

  if (isLoading) {
    return (
      <div className="border border-[#E9E9EB] rounded-2xl bg-white p-8 text-center text-xs font-sans text-[#686B78] shadow-xs">
        Loading queue tickets...
      </div>
    );
  }

  if (tickets.length === 0) {
    return (
      <div className="border border-[#E9E9EB] rounded-2xl bg-white p-10 text-center text-xs font-sans text-[#93959F] shadow-xs">
        No tickets currently present in this queue.
      </div>
    );
  }

  return (
    <div className="border border-[#E9E9EB] rounded-2xl bg-white shadow-xs overflow-hidden font-sans text-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-[#F9FAFC] border-b border-[#E9E9EB] text-[#686B78] text-[11px] font-semibold">
              <th className="py-3 px-3.5">Ticket ID</th>
              <th className="py-3 px-3.5">Customer & Subject</th>
              <th className="py-3 px-3.5">Category</th>
              <th className="py-3 px-3.5">Status</th>
              <th className="py-3 px-3.5">Assignment</th>
              <th className="py-3 px-3.5">Age</th>
              <th className="py-3 px-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E9E9EB]">
            {tickets.map((t) => {
              const isAssignedToMe = currentUser && t.assigned_to === currentUser.id;
              const allowClaim = canClaim(t);

              return (
                <tr
                  key={t.id}
                  tabIndex={0}
                  onClick={() => onSelectTicket(t.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      onSelectTicket(t.id);
                    }
                  }}
                  className="hover:bg-[#FFF9F5] cursor-pointer transition-colors focus:outline-hidden focus:bg-[#FFF2E5]"
                >
                  <td className="py-3 px-3.5 font-bold whitespace-nowrap">
                    <a
                      href={`#ticket-${t.id}`}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        onSelectTicket(t.id);
                      }}
                      className="text-[#FC8019] hover:text-[#E26A00] underline font-mono cursor-pointer font-bold"
                      title={`Open ticket #${t.id.slice(0, 8)}`}
                    >
                      #{t.id.slice(0, 8)}
                    </a>
                  </td>
                  <td className="py-3 px-3.5 max-w-xs">
                    <div className="font-semibold text-[#282C3F] truncate">{t.subject}</div>
                    <div className="text-[11px] font-mono text-[#686B78] truncate">
                      CX: {t.customer_id.slice(0, 8)}
                    </div>
                  </td>
                  <td className="py-3 px-3.5 whitespace-nowrap">
                    <CategoryPill category={t.category} />
                  </td>
                  <td className="py-3 px-3.5 whitespace-nowrap">
                    <StatusBadge status={t.status} escalationFlag={t.escalation_flag} />
                  </td>
                  <td className="py-3 px-3.5 text-[11px] whitespace-nowrap text-[#282C3F]">
                    <span
                      className={
                        t.status === 'resolved'
                          ? 'font-medium text-[#2A7E15]'
                          : t.assigned_to
                          ? isAssignedToMe
                            ? 'font-semibold text-[#FC8019]'
                            : 'text-[#282C3F]'
                          : 'text-[#93959F] italic'
                      }
                    >
                      {formatAssignee(t)}
                    </span>
                  </td>
                  <td className="py-3 px-3.5 text-[11px] text-[#686B78] whitespace-nowrap">
                    {formatRelativeTime(t.created_at)}
                  </td>
                  <td className="py-3 px-3.5 text-right whitespace-nowrap">
                    <div className="inline-flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      {allowClaim && onClaim && (
                        <button
                          type="button"
                          onClick={() => onClaim(t.id)}
                          className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-[#FC8019] text-white hover:bg-[#E26A00] transition-colors shadow-2xs cursor-pointer"
                        >
                          Claim
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => onSelectTicket(t.id)}
                        className="px-2.5 py-1 text-xs font-medium rounded-lg border border-[#D4D5D9] bg-white text-[#282C3F] hover:bg-[#FFF2E5] hover:text-[#FC8019] hover:border-[#FC8019]/40 transition-colors cursor-pointer"
                      >
                        View
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="py-2.5 px-4 bg-[#F9FAFC] border-t border-[#E9E9EB] text-[11px] text-[#686B78] flex justify-between items-center">
        <span>Showing {tickets.length} tickets</span>
        <span className="font-medium text-[#FC8019]">Live Operations Active</span>
      </div>
    </div>
  );
};
