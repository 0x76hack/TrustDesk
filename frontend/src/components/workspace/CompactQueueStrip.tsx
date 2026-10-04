import React from 'react';
import type { Ticket } from '../../types/ticket';
import { StatusBadge } from '../common/Badge';

interface CompactQueueStripProps {
  tickets: Ticket[];
  selectedTicketId: string;
  onSelectTicket: (ticketId: string) => void;
  onBackToQueue: () => void;
}

export const CompactQueueStrip: React.FC<CompactQueueStripProps> = ({
  tickets,
  selectedTicketId,
  onSelectTicket,
  onBackToQueue,
}) => {
  return (
    <div className="w-72 bg-white border-r border-[#E9E9EB] flex flex-col h-full shrink-0 font-mono text-xs">
      <div className="p-3 border-b border-[#E9E9EB] flex items-center justify-between bg-[#F9F9FB]">
        <span className="font-bold text-[#282C3F] uppercase tracking-wider text-[11px]">
          TICKETS QUEUE ({tickets.length})
        </span>
        <button
          type="button"
          onClick={onBackToQueue}
          className="text-[11px] font-bold text-[#FC8019] hover:text-[#E26A00] underline cursor-pointer transition-colors"
        >
          [ALL QUEUES]
        </button>
      </div>

      <div className="flex-1 overflow-y-auto divide-y divide-[#F2F2F6] bg-white">
        {tickets.map((t) => {
          const isSelected = t.id === selectedTicketId;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onSelectTicket(t.id)}
              className={`w-full p-3 text-left transition-all cursor-pointer block ${
                isSelected
                  ? 'bg-[#FFF9F5] border-l-4 border-l-[#FC8019] shadow-xs'
                  : 'hover:bg-[#F9F9FB] border-l-4 border-l-transparent'
              }`}
            >
              <div className="flex items-center justify-between gap-1 mb-1">
                <span className={`font-bold text-[11px] ${isSelected ? 'text-[#FC8019]' : 'text-[#282C3F]'}`}>
                  #{t.id.slice(0, 8)}
                </span>
                <StatusBadge status={t.status} escalationFlag={t.escalation_flag} />
              </div>
              <p
                className={`text-xs truncate font-sans ${
                  isSelected ? 'text-[#282C3F] font-bold' : 'text-[#686B78]'
                }`}
              >
                {t.subject}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
