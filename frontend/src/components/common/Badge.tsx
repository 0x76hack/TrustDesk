import React from 'react';
import type { TicketStatus, TicketCategory, TicketRiskLevel } from '../../types/ticket';

interface BadgeProps {
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, className = '' }) => {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-sans font-medium border ${className}`}
    >
      {children}
    </span>
  );
};

export const PriorityBadge: React.FC<{ priority?: string | null }> = ({ priority }) => {
  if (!priority) return null;
  const p = String(priority).toLowerCase();
  const isUrgent = p === 'urgent' || p === 'high';
  const label = p.charAt(0).toUpperCase() + p.slice(1);

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-sans font-medium ${
      isUrgent
        ? 'text-[#EC3D25] bg-[#FDF0EE] border border-[#EC3D25]/30'
        : 'text-[#282C3F] bg-[#F4F5F8] border border-[#D4D5D9]'
    }`}>
      {label}
    </span>
  );
};

export const StatusBadge: React.FC<{ status: TicketStatus | string; escalationFlag?: boolean }> = ({
  status,
}) => {
  const s = (status || 'open').toLowerCase();

  switch (s) {
    case 'escalated':
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-sans font-semibold bg-[#FDF0EE] text-[#EC3D25] border border-[#EC3D25]/30 shadow-2xs">
          Escalated
        </span>
      );
    case 'working':
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-sans font-semibold bg-[#FFF2E5] text-[#FC8019] border border-[#FC8019]/40 shadow-2xs">
          In Progress
        </span>
      );
    case 'resolved':
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-sans font-semibold bg-[#EBF7E9] text-[#2A7E15] border border-[#60B246]/40 shadow-2xs">
          Resolved
        </span>
      );
    case 'open':
    default:
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-sans font-medium bg-[#F0F4FC] text-[#1D58BD] border border-[#BFDBFE]">
          Open
        </span>
      );
  }
};

export const RiskBadge: React.FC<{ risk?: TicketRiskLevel | string | null }> = ({ risk }) => {
  if (!risk) return <span className="font-sans text-xs text-[#93959F]">Standard</span>;
  const r = risk.toLowerCase();

  switch (r) {
    case 'critical':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-sans font-semibold bg-[#FDF0EE] text-[#C62828] border border-[#EC3D25]/40">
          Critical Risk
        </span>
      );
    case 'high':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-sans font-semibold bg-[#FFF2E5] text-[#D45D00] border border-[#FC8019]/40">
          High Risk
        </span>
      );
    case 'medium':
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-sans font-medium bg-[#FEFCE8] text-[#A16207] border border-[#FDE047]">
          Medium Risk
        </span>
      );
    case 'low':
    default:
      return (
        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-sans font-medium bg-[#EBF7E9] text-[#2A7E15] border border-[#60B246]/40">
          Low Risk
        </span>
      );
  }
};

export const CategoryPill: React.FC<{ category?: TicketCategory | string | null }> = ({ category }) => {
  if (!category) return null;
  const formatted = category
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-sans text-[#3D4152] bg-[#F4F5F8] border border-[#D4D5D9] font-medium">
      {formatted}
    </span>
  );
};
