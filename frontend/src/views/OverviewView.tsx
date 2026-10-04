import React, { useMemo } from 'react';
import type { Ticket } from '../types/ticket';
import type { NavView } from '../components/navigation/Sidebar';
import { Skeleton } from '../components/common/Skeleton';

interface OverviewViewProps {
  tickets: Ticket[];
  isLoading: boolean;
  onNavigate: (view: NavView) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  tickets,
  isLoading,
  onNavigate,
}) => {
  const { totalTickets, openTickets, workingTickets, escalatedTickets, resolvedTickets, categoryCounts } = useMemo(() => {
    const total = tickets.length;
    let open = 0;
    let working = 0;
    let escalated = 0;
    let resolved = 0;
    const catCounts: Record<string, number> = {};

    for (const t of tickets) {
      const st = (t.status || 'open').toLowerCase();
      if (st === 'open') open++;
      else if (st === 'working') working++;
      else if (st === 'escalated') escalated++;
      else if (st === 'resolved') resolved++;

      const cat = t.category || 'general';
      catCounts[cat] = (catCounts[cat] || 0) + 1;
    }

    return {
      totalTickets: total,
      openTickets: open,
      workingTickets: working,
      escalatedTickets: escalated,
      resolvedTickets: resolved,
      categoryCounts: catCounts,
    };
  }, [tickets]);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 max-w-7xl mx-auto font-sans text-xs text-left">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="p-5 bg-white rounded-2xl border border-[#E9E9EB] space-y-2 shadow-xs">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3 w-32" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const formatCategoryName = (c: string) => {
    return c
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(' ');
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6 text-left font-sans text-xs">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E9E9EB] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#282C3F]">
            Operations & Queue Overview
          </h1>
          <p className="text-xs text-[#686B78] mt-0.5">
            Real-time queue distribution across Open, Working, Escalated, and Resolved lifecycle states.
          </p>
        </div>

        <button
          type="button"
          onClick={() => onNavigate('queue')}
          className="px-3.5 py-2 bg-[#FC8019] hover:bg-[#E26A00] text-white rounded-lg font-semibold transition-all shadow-xs cursor-pointer text-xs"
        >
          View Ticket Queues →
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          role="button"
          tabIndex={0}
          aria-label="View Open Queue tickets"
          onClick={() => onNavigate('queue')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onNavigate('queue');
            }
          }}
          className="p-5 bg-white rounded-2xl border border-[#E9E9EB] hover:border-[#BFDBFE] space-y-2 shadow-xs transition-all cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-[#FC8019]"
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-[#282C3F]">Open Queue</span>
            <span className="text-[#1D58BD] bg-[#F0F4FC] px-2 py-0.5 rounded-full font-medium text-[11px]">Inbound</span>
          </div>
          <div className="text-3xl font-extrabold text-[#282C3F]">{openTickets}</div>
          <p className="text-[11px] text-[#686B78]">
            Unassigned inbound tickets awaiting agent pickup.
          </p>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-label="View Working Queue tickets"
          onClick={() => onNavigate('queue')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onNavigate('queue');
            }
          }}
          className="p-5 bg-white rounded-2xl border border-[#E9E9EB] hover:border-[#FFD7B0] space-y-2 shadow-xs transition-all cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-[#FC8019]"
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-[#282C3F]">Working Queue</span>
            <span className="text-[#FC8019] bg-[#FFF2E5] px-2 py-0.5 rounded-full font-medium text-[11px]">In Progress</span>
          </div>
          <div className="text-3xl font-extrabold text-[#FC8019]">{workingTickets}</div>
          <p className="text-[11px] text-[#686B78]">
            Tickets actively assigned and being handled by operatives.
          </p>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-label="View Escalated Queue tickets"
          onClick={() => onNavigate('queue')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onNavigate('queue');
            }
          }}
          className="p-5 bg-white rounded-2xl border border-[#E9E9EB] hover:border-[#EC3D25]/30 space-y-2 shadow-xs transition-all cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-[#EC3D25]"
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-[#282C3F]">Escalated Queue</span>
            <span className="text-[#EC3D25] bg-[#FDF0EE] px-2 py-0.5 rounded-full font-medium text-[11px]">Supervisor</span>
          </div>
          <div className="text-3xl font-extrabold text-[#EC3D25]">{escalatedTickets}</div>
          <p className="text-[11px] text-[#686B78]">
            Gated disputes awaiting senior agent review.
          </p>
        </div>

        <div
          role="button"
          tabIndex={0}
          aria-label="View Resolved Queue tickets"
          onClick={() => onNavigate('queue')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onNavigate('queue');
            }
          }}
          className="p-5 bg-white rounded-2xl border border-[#E9E9EB] hover:border-[#60B246]/40 space-y-2 shadow-xs transition-all cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-[#60B246]"
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-[#282C3F]">Resolved Queue</span>
            <span className="text-[#2A7E15] bg-[#EBF7E9] px-2 py-0.5 rounded-full font-medium text-[11px]">Concluded</span>
          </div>
          <div className="text-3xl font-extrabold text-[#60B246]">{resolvedTickets}</div>
          <p className="text-[11px] text-[#686B78]">
            Completed tickets with recorded resolution notes.
          </p>
        </div>
      </div>

      <div className="bg-white p-5 rounded-2xl border border-[#E9E9EB] space-y-4 shadow-xs">
        <div className="flex items-center justify-between border-b border-[#E9E9EB] pb-3">
          <span className="font-bold text-xs text-[#282C3F] uppercase tracking-wide">
            Ticket Volume by Classification
          </span>
          <span className="text-xs text-[#686B78]">Total Active: {totalTickets}</span>
        </div>

        {totalTickets === 0 ? (
          <div className="p-8 text-center text-[#93959F]">
            No tickets currently in queues. All operational queues are clear.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(categoryCounts).map(([cat, count]) => {
              const pct = totalTickets > 0 ? Math.round((count / totalTickets) * 100) : 0;
              return (
                <div key={cat} className="p-3 rounded-xl bg-[#F9FAFC] border border-[#E9E9EB] space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-[#282C3F]">
                      {formatCategoryName(cat)}
                    </span>
                    <span className="text-[#686B78] font-medium">
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div className="h-2 w-full bg-[#E9E9EB] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#FC8019] rounded-full transition-all duration-300"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
