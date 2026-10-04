import React from 'react';
import type { Ticket } from '../../types/ticket';
import { StatusBadge, CategoryPill } from '../common/Badge';

interface TicketCardProps {
  ticket: Ticket;
  isSelected?: boolean;
  onClick: () => void;
}

export const TicketCard: React.FC<TicketCardProps> = ({
  ticket,
  isSelected = false,
  onClick,
}) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopyId = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(ticket.id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const getRelativeTime = (dateStr?: string) => {
    if (!dateStr) return '--';
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const mins = Math.max(1, Math.floor(diffMs / 60000));
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  };

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-2xl border transition-all cursor-pointer text-left font-mono text-xs ${
        isSelected
          ? 'bg-[#FFF9F5] border-[#FC8019] ring-1 ring-[#FC8019] shadow-xs'
          : 'bg-white border-[#E9E9EB] hover:border-[#FFD7B0] hover:shadow-xs'
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <button
          type="button"
          onClick={handleCopyId}
          className="font-bold text-[#FC8019] hover:underline cursor-pointer"
        >
          #{ticket.id.slice(0, 8)} {copied ? '[COPIED]' : ''}
        </button>
        <StatusBadge status={ticket.status} escalationFlag={ticket.escalation_flag} />
      </div>

      <h3 className="font-bold text-[#282C3F] text-sm mb-2 font-sans truncate">
        {ticket.subject}
      </h3>

      <div className="flex items-center justify-between pt-2 border-t border-[#F2F2F6] text-[10px] text-[#93959F]">
        <CategoryPill category={ticket.category} />
        <span className="font-sans">{getRelativeTime(ticket.created_at)}</span>
      </div>
    </div>
  );
};
