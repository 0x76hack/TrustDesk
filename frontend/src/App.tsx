import { useState, useEffect, useCallback, useMemo } from 'react';
import type { User } from './types/auth';
import type { Ticket } from './types/ticket';
import { getStoredUser, logout } from './api/auth';
import { listTickets } from './api/tickets';
import { checkHealth } from './api/admin';

const TICKET_POLL_INTERVAL_MS = 4000;
const HEALTH_CHECK_INTERVAL_MS = 15000;

import { Sidebar } from './components/navigation/Sidebar';
import type { NavView } from './components/navigation/Sidebar';
import { TopBar } from './components/navigation/TopBar';
import { AuthModal } from './components/auth/AuthModal';
import { CreateTicketModal } from './components/tickets/CreateTicketModal';

import { OverviewView } from './views/OverviewView';
import { QueueView } from './views/QueueView';
import { TicketDetailView } from './views/TicketDetailView';
import { TeamManagementView } from './views/TeamManagementView';
import { SettingsView } from './views/SettingsView';
import { ObservabilityDashboardView } from './views/ObservabilityDashboardView';

export default function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(() => getStoredUser());

  const [currentView, setCurrentView] = useState<NavView>('queue');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);

  const [isObservabilityOpen, setIsObservabilityOpen] = useState<boolean>(() => {
    return typeof window !== 'undefined' && window.location.hash === '#observability';
  });

  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isCreateTicketOpen, setIsCreateTicketOpen] = useState(false);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isTicketsLoading, setIsTicketsLoading] = useState(false);

  const pingHealth = useCallback(async () => {
    try {
      const res = await checkHealth();
      setIsBackendHealthy(res.status === 'healthy');
    } catch {
      setIsBackendHealthy(false);
    }
  }, []);

  const loadTickets = useCallback(async () => {
    try {
      const res = await listTickets();
      setTickets(res);
    } catch {
      setTickets([]);
    } finally {
      setIsTicketsLoading(false);
    }
  }, []);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([loadTickets(), pingHealth()]);
    setIsRefreshing(false);
  }, [loadTickets, pingHealth]);

  useEffect(() => {
    pingHealth();
    if (currentUser) {
      handleRefresh();
    }
    const interval = setInterval(pingHealth, HEALTH_CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [currentUser, handleRefresh, pingHealth]);

  useEffect(() => {
    if (!currentUser) return;
    const livePoll = setInterval(() => {
      loadTickets();
    }, TICKET_POLL_INTERVAL_MS);
    return () => clearInterval(livePoll);
  }, [currentUser, loadTickets]);

  useEffect(() => {
    const handleHash = () => {
      if (window.location.hash === '#observability') {
        setIsObservabilityOpen(true);
      }
    };
    window.addEventListener('hashchange', handleHash);
    return () => window.removeEventListener('hashchange', handleHash);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      setCurrentUser(null);
      setIsAuthModalOpen(true);
    };
    window.addEventListener('trustdesk:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('trustdesk:unauthorized', handleUnauthorized);
  }, []);

  const handleLogout = useCallback(() => {
    logout();
    setCurrentUser(null);
    setIsObservabilityOpen(false);
    setIsAuthModalOpen(true);
  }, []);

  const handleTicketCreated = useCallback((newTicketId: string) => {
    handleRefresh();
    setSelectedTicketId(newTicketId);
  }, [handleRefresh]);

  const escalatedCount = useMemo(
    () => tickets.filter((t) => t.status === 'escalated').length,
    [tickets]
  );

  if (!currentUser) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-[#F2F2F6] p-4">
        <AuthModal
          isOpen={true}
          onLoginSuccess={(user: User) => {
            setCurrentUser(user);
            setIsAuthModalOpen(false);
          }}
          onClose={() => {}}
        />
      </div>
    );
  }

  const activeUser = currentUser;

  if (isObservabilityOpen && activeUser.role === 'admin') {
    return (
      <ObservabilityDashboardView
        onBackToApp={() => {
          setIsObservabilityOpen(false);
          if (window.location.hash === '#observability') {
            window.location.hash = '';
          }
        }}
      />
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F2F2F6] text-[#282C3F]">
      <Sidebar
        currentView={currentView}
        onNavigate={(view) => {
          setCurrentView(view);
          setSelectedTicketId(null);
        }}
        userRole={activeUser.role}
        userName={activeUser.name}
        onLogout={handleLogout}
      />

      <div className="flex-1 flex flex-col h-full min-w-0 overflow-hidden">
        <TopBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onOpenCreateTicket={() => setIsCreateTicketOpen(true)}
          isBackendHealthy={isBackendHealthy}
          onRefresh={handleRefresh}
          isRefreshing={isRefreshing}
          notificationCount={escalatedCount}
          userRole={activeUser.role}
          onOpenObservability={() => setIsObservabilityOpen(true)}
        />

        <main className={`flex-1 ${selectedTicketId ? 'overflow-hidden flex flex-col' : 'overflow-y-auto'}`}>
          {selectedTicketId ? (
            <TicketDetailView
              ticketId={selectedTicketId}
              allTickets={tickets}
              onSelectTicket={setSelectedTicketId}
              onBackToQueue={() => setSelectedTicketId(null)}
              currentUserRole={activeUser.role}
              currentUserId={activeUser.id}
            />
          ) : currentView === 'overview' ? (
            <OverviewView
              tickets={tickets}
              isLoading={isTicketsLoading}
              onNavigate={setCurrentView}
            />
          ) : currentView === 'queue' ? (
            <QueueView
              tickets={tickets}
              isLoading={isTicketsLoading}
              onSelectTicket={setSelectedTicketId}
              onOpenCreateTicket={() => setIsCreateTicketOpen(true)}
              searchQuery={searchQuery}
              currentUser={activeUser}
              onRefresh={handleRefresh}
            />
          ) : currentView === 'team' ? (
            <TeamManagementView
              currentUserRole={activeUser.role}
              currentUserId={activeUser.id}
            />
          ) : (
            <SettingsView
              currentUser={activeUser}
              onLogout={handleLogout}
              onSelectTicket={setSelectedTicketId}
            />
          )}
        </main>
      </div>

      {isAuthModalOpen && (
        <AuthModal
          isOpen={isAuthModalOpen}
          onLoginSuccess={(user: User) => {
            setCurrentUser(user);
            setIsAuthModalOpen(false);
            handleRefresh();
          }}
          onClose={() => {
            if (currentUser) setIsAuthModalOpen(false);
          }}
        />
      )}

      {isCreateTicketOpen && (
        <CreateTicketModal
          isOpen={isCreateTicketOpen}
          onClose={() => setIsCreateTicketOpen(false)}
          onTicketCreated={handleTicketCreated}
        />
      )}
    </div>
  );
}
