import React from 'react';
import type { TicketCategory } from '../../types/ticket';

export type QueueTab = 'open' | 'working' | 'escalated' | 'resolved';
export type SortOption = 'newest' | 'oldest';

interface TicketFiltersProps {
  activeTab: QueueTab;
  onTabChange: (tab: QueueTab) => void;
  tabCounts: {
    open: number;
    working: number;
    escalated: number;
    resolved: number;
  };
  selectedCategory: string;
  onCategoryChange: (cat: string) => void;
  sortBy: SortOption;
  onSortChange: (sort: SortOption) => void;
}

export const TicketFilters: React.FC<TicketFiltersProps> = ({
  activeTab,
  onTabChange,
  tabCounts,
  selectedCategory,
  onCategoryChange,
  sortBy,
  onSortChange,
}) => {
  const categories: { label: string; value: TicketCategory | 'all' }[] = [
    { label: 'All Categories', value: 'all' },
    { label: 'Refund', value: 'refund' },
    { label: 'Shipping & Delivery', value: 'shipping' },
    { label: 'Billing & Payment', value: 'billing' },
    { label: 'Warranty & Food Quality', value: 'warranty' },
    { label: 'Account Security', value: 'account_security' },
    { label: 'General Inquiry', value: 'general' },
  ];

  return (
    <div className="space-y-3 font-sans text-xs">
      <div className="flex flex-wrap items-center gap-2 border-b border-[#E9E9EB] pb-3">
        <button
          type="button"
          onClick={() => onTabChange('open')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-all ${
            activeTab === 'open'
              ? 'bg-[#282C3F] text-white border-[#282C3F] shadow-xs'
              : 'bg-white text-[#686B78] border-[#D4D5D9] hover:bg-[#F4F5F8] hover:text-[#282C3F]'
          }`}
        >
          Open Queue ({tabCounts.open})
        </button>

        <button
          type="button"
          onClick={() => onTabChange('working')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-all ${
            activeTab === 'working'
              ? 'bg-[#FC8019] text-white border-[#FC8019] shadow-xs'
              : 'bg-white text-[#686B78] border-[#D4D5D9] hover:bg-[#FFF2E5] hover:text-[#FC8019] hover:border-[#FC8019]/40'
          }`}
        >
          Working Queue ({tabCounts.working})
        </button>

        <button
          type="button"
          onClick={() => onTabChange('escalated')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-all ${
            activeTab === 'escalated'
              ? 'bg-[#EC3D25] text-white border-[#EC3D25] shadow-xs'
              : 'bg-white text-[#EC3D25] border-[#EC3D25]/30 hover:bg-[#FDF0EE]'
          }`}
        >
          Escalated Queue ({tabCounts.escalated})
        </button>

        <button
          type="button"
          onClick={() => onTabChange('resolved')}
          className={`px-3.5 py-2 rounded-xl text-xs font-semibold cursor-pointer border transition-all ${
            activeTab === 'resolved'
              ? 'bg-[#60B246] text-white border-[#60B246] shadow-xs'
              : 'bg-white text-[#2A7E15] border-[#60B246]/40 hover:bg-[#EBF7E9]'
          }`}
        >
          Resolved Queue ({tabCounts.resolved})
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="ticket-category-select" className="text-[#686B78] font-medium text-xs">
            Category:
          </label>
          <select
            id="ticket-category-select"
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            className="px-2.5 py-1.5 bg-white border border-[#D4D5D9] rounded-lg text-xs text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-colors"
          >
            {categories.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>

          {selectedCategory !== 'all' && (
            <button
              type="button"
              onClick={() => onCategoryChange('all')}
              className="px-2 py-1 text-[#FC8019] hover:underline font-semibold text-xs cursor-pointer"
            >
              Reset
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="ticket-sort-select" className="text-[#686B78] font-medium text-xs">
            Sort:
          </label>
          <select
            id="ticket-sort-select"
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value as SortOption)}
            className="px-2.5 py-1.5 bg-white border border-[#D4D5D9] rounded-lg text-xs text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] transition-colors"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
          </select>
        </div>
      </div>
    </div>
  );
};
