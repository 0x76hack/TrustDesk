import React from 'react';
import type { UserRole } from '../../types/auth';

export type NavView = 'overview' | 'queue' | 'team' | 'settings';

interface SidebarProps {
  currentView: NavView;
  onNavigate: (view: NavView) => void;
  userRole: UserRole;
  userName: string;
  onLogout: () => void;
  pendingApprovalsCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onNavigate,
  userRole,
  userName,
  onLogout,
}) => {
  const navItems = [
    {
      id: 'overview' as NavView,
      label: 'Overview',
      roles: ['agent', 'senior_agent', 'admin'] as UserRole[],
    },
    {
      id: 'queue' as NavView,
      label: 'Ticket Queues',
      roles: ['agent', 'senior_agent', 'admin'] as UserRole[],
    },
    {
      id: 'team' as NavView,
      label: 'Team Management',
      roles: ['admin'] as UserRole[],
    },
    {
      id: 'settings' as NavView,
      label: 'Profile & Settings',
      roles: ['agent', 'senior_agent', 'admin'] as UserRole[],
    },
  ];

  const visibleItems = navItems.filter((item) => item.roles.includes(userRole));

  const formatRole = (r: string) => {
    switch (r) {
      case 'senior_agent':
        return 'Senior Agent';
      case 'admin':
        return 'Administrator';
      case 'agent':
      default:
        return 'Support Agent';
    }
  };

  return (
    <aside className="w-56 bg-[#1C1C24] border-r border-[#282C3F] flex flex-col shrink-0 h-screen select-none font-sans text-xs text-[#93959F]">
      <div className="p-4 border-b border-[#282C3F] bg-[#22232E] flex items-center justify-between">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-base font-extrabold tracking-wide text-white">
              TRUST<span className="text-[#FC8019]">DESK</span>
            </span>
            <span className="w-2 h-2 rounded-full bg-[#FC8019] animate-pulse"></span>
          </div>
          <span className="text-[10px] text-[#FC8019]/90 font-medium tracking-wide mt-0.5 block">
            Operations Console
          </span>
        </div>
      </div>

      <div className="flex-1 py-4 px-2.5 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-semibold text-[#686B78] uppercase tracking-wider">
          Navigation
        </div>

        {visibleItems.map((item) => {
          const isActive = currentView === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all cursor-pointer ${
                isActive
                  ? 'bg-[#FC8019]/15 text-[#FC8019] font-bold border-l-3 border-[#FC8019]'
                  : 'text-[#D4D5D9] hover:bg-[#282C3F] hover:text-white'
              }`}
            >
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      <div className="p-3.5 border-t border-[#282C3F] bg-[#22232E] space-y-2.5">
        <div className="space-y-0.5">
          <div className="text-[10px] text-[#686B78] font-medium">Logged In As</div>
          <div className="font-semibold text-white truncate text-xs">{userName}</div>
          <div className="text-[11px] text-[#60B246] font-medium">
            {formatRole(userRole)}
          </div>
        </div>

        <button
          type="button"
          onClick={onLogout}
          className="w-full py-1.5 text-center text-xs font-medium text-[#93959F] hover:text-[#EC3D25] border border-[#282C3F] hover:border-[#EC3D25]/40 rounded-lg transition-colors cursor-pointer"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
};
