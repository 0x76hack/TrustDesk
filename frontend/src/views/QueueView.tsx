import React, { useState, useMemo } from 'react';
import type { Ticket } from '../types/ticket';
import type { User } from '../types/auth';
import { TicketTable } from '../components/tickets/TicketTable';
import { TicketFilters } from '../components/tickets/TicketFilters';
import type { QueueTab, SortOption } from '../components/tickets/TicketFilters';
import { assignTicket } from '../api/tickets';

interface QueueViewProps {
  tickets: Ticket[];
  isLoading: boolean;
  onSelectTicket: (ticketId: string) => void;
  onOpenCreateTicket: () => void;
  searchQuery: string;
  currentUser?: User;
  onRefresh?: () => Promise<void> | void;
}

export const QueueView: React.FC<QueueViewProps> = ({
  tickets,
  isLoading,
  onSelectTicket,
  onOpenCreateTicket,
  searchQuery,
  currentUser,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState<QueueTab>('open');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortOption>('newest');
  const [claimError, setClaimError] = useState<string | null>(null);

  const tabCounts = useMemo(() => {
    let open = 0;
    let working = 0;
    let escalated = 0;
    let resolved = 0;

    tickets.forEach((t) => {
      const s = (t.status || 'open').toLowerCase();
      if (s === 'resolved') {
        resolved++;
      } else if (s === 'escalated') {
        escalated++;
      } else if (s === 'working') {
        working++;
      } else {
        open++;
      }
    });

    return { open, working, escalated, resolved };
  }, [tickets]);

  const filteredTickets = useMemo(() => {
    return tickets.filter((t) => {
      const s = (t.status || 'open').toLowerCase();

      if (activeTab === 'open') {
        if (s !== 'open') return false;
      } else if (activeTab === 'working') {
        if (s !== 'working') return false;
      } else if (activeTab === 'escalated') {
        if (s !== 'escalated') return false;
      } else if (activeTab === 'resolved') {
        if (s !== 'resolved') return false;
      }

      if (selectedCategory !== 'all' && t.category?.toLowerCase() !== selectedCategory.toLowerCase()) {
        return false;
      }

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesId = t.id.toLowerCase().includes(q);
        const matchesSubj = t.subject.toLowerCase().includes(q);
        const matchesCust = t.customer_id.toLowerCase().includes(q);
        const matchesOrd = t.order_id?.toLowerCase().includes(q);
        if (!matchesId && !matchesSubj && !matchesCust && !matchesOrd) {
          return false;
        }
      }

      return true;
    });
  }, [tickets, activeTab, selectedCategory, searchQuery]);

  const sortedTickets = useMemo(() => {
    return [...filteredTickets].sort((a, b) => {
      const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return sortBy === 'oldest' ? dateA - dateB : dateB - dateA;
    });
  }, [filteredTickets, sortBy]);

  const handleClaimTicket = async (ticketId: string) => {
    try {
      setClaimError(null);
      await assignTicket(ticketId);
      if (onRefresh) {
        await onRefresh();
      }
      onSelectTicket(ticketId);
    } catch (err: unknown) {
      setClaimError(err instanceof Error ? err.message : 'Failed to claim ticket.');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5 text-left font-sans text-xs">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E9E9EB] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#282C3F]">
            Ticket Queues
          </h1>
          <p className="text-xs text-[#686B78] mt-0.5">
            Audit-grade ticket queues across Open, Working, Escalated, and Resolved states.
          </p>
        </div>

        <div>
          <button
            type="button"
            onClick={onOpenCreateTicket}
            className="px-3.5 py-2 bg-[#FC8019] text-white rounded-lg text-xs font-semibold hover:bg-[#E26A00] shadow-xs transition-all cursor-pointer"
          >
            + Register New Ticket
          </button>
        </div>
      </div>

      {claimError && (
        <div className="p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-xs text-[#C62828] font-medium">
          {claimError}
        </div>
      )}

      <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] shadow-xs">
        <TicketFilters
          activeTab={activeTab}
          onTabChange={setActiveTab}
          tabCounts={tabCounts}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          sortBy={sortBy}
          onSortChange={setSortBy}
        />
      </div>

      <TicketTable
        tickets={sortedTickets}
        currentUser={currentUser || null}
        onSelectTicket={onSelectTicket}
        onClaim={handleClaimTicket}
        isLoading={isLoading}
      />
    </div>
  );
};
