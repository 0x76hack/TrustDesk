import React from 'react';

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => {
  return <div className={`animate-pulse bg-[#E2E8F0] rounded-md ${className}`} />;
};

export const TicketCardSkeleton: React.FC = () => {
  return (
    <div className="bg-white p-4 rounded-xl border border-[#E2E8F0] shadow-2xs space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <div className="flex gap-2">
          <Skeleton className="h-4 w-14 rounded-full" />
          <Skeleton className="h-4 w-16 rounded-full" />
        </div>
      </div>
      <Skeleton className="h-5 w-3/4" />
      <div className="flex items-center justify-between pt-2">
        <Skeleton className="h-3.5 w-32" />
        <Skeleton className="h-3.5 w-16" />
      </div>
    </div>
  );
};

export const TableRowSkeleton: React.FC<{ cols?: number }> = ({ cols = 4 }) => {
  return (
    <div className="flex items-center space-x-4 py-3 border-b border-[#F1F5F9]">
      {Array.from({ length: cols }).map((_, i) => (
        <Skeleton key={i} className="h-4 flex-1" />
      ))}
    </div>
  );
};
