import React from 'react';
import { Activity } from 'lucide-react';

interface TopBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onOpenCreateTicket: () => void;
  isBackendHealthy: boolean | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  notificationCount?: number;
  userRole?: string;
  onOpenObservability?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  searchQuery,
  onSearchChange,
  onOpenCreateTicket,
  isBackendHealthy,
  onRefresh,
  isRefreshing = false,
  notificationCount = 0,
  userRole,
  onOpenObservability,
}) => {
  return (
    <header className="h-14 bg-white border-b border-[#E9E9EB] px-5 flex items-center justify-between gap-4 shrink-0 font-sans text-xs shadow-2xs">
      <div className="flex-1 max-w-lg flex items-center gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search by Ticket ID, Customer, Order ID, or Subject..."
          className="w-full px-3 py-1.5 bg-[#F4F5F8] text-xs text-[#282C3F] placeholder-[#93959F] rounded-lg border border-[#D4D5D9] focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-all"
        />
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center">
          {isBackendHealthy === true ? (
            <span className="text-[#2A7E15] bg-[#EBF7E9] border border-[#60B246]/30 px-2.5 py-0.5 rounded-full text-[11px] font-medium flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#60B246]" />
              System Online
            </span>
          ) : isBackendHealthy === false ? (
            <span className="text-[#EC3D25] bg-[#FDF0EE] border border-[#EC3D25]/30 px-2.5 py-0.5 rounded-full text-[11px] font-medium flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#EC3D25]" />
              System Offline
            </span>
          ) : (
            <span className="text-[#686B78] bg-[#F4F5F8] border border-[#D4D5D9] px-2.5 py-0.5 rounded-full text-[11px] font-medium flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#93959F] animate-pulse" />
              Connecting...
            </span>
          )}
        </div>

        {userRole === 'admin' && onOpenObservability && (
          <button
            type="button"
            onClick={onOpenObservability}
            title="Open Live Observability & Diagnostics Dashboard"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[#282C3F] bg-[#1C1C24] hover:bg-[#282C3F] text-[#FC8019] font-medium text-xs transition-colors cursor-pointer"
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Diagnostics</span>
          </button>
        )}

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="px-3 py-1.5 rounded-lg border border-[#D4D5D9] bg-white hover:bg-[#FFF2E5] hover:text-[#FC8019] text-[#282C3F] font-medium text-xs transition-colors cursor-pointer"
          >
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        )}

        {notificationCount > 0 && (
          <div className="px-2.5 py-1 rounded-full bg-[#FDF0EE] border border-[#EC3D25]/30 text-[#EC3D25] font-semibold text-xs animate-pulse">
            {notificationCount} Escalated
          </div>
        )}

        <button
          type="button"
          onClick={onOpenCreateTicket}
          className="px-3.5 py-1.5 bg-[#FC8019] hover:bg-[#E26A00] text-white rounded-lg font-semibold text-xs shadow-xs hover:shadow-sm transition-all cursor-pointer"
        >
          + New Ticket
        </button>
      </div>
    </header>
  );
};
