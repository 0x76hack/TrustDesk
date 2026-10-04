import React from 'react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  action,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-2xl border border-[#E9E9EB] bg-white shadow-xs max-w-md mx-auto my-6 font-mono text-xs">
      <div className="font-bold text-[#282C3F] text-sm mb-1.5 uppercase">[{title}]</div>
      <p className="text-[#686B78] mb-4 max-w-xs font-sans">{description}</p>
      {action && <div>{action}</div>}
    </div>
  );
};
