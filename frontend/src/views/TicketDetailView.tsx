import React, { useState, useEffect, useCallback } from 'react';
import type { Ticket, TicketDetail, ToolAction, Citation } from '../types/ticket';
import type { UserRole } from '../types/auth';
import {
  getTicketDetail,
  escalateTicket,
  closeTicket,
  assignTicket,
  unassignTicket,
  postTicketMessage,
  triggerDraft,
  getLatestDraft,
  listTicketActions,
  getAvailableAgents,
  type AvailableAgent,
} from '../api/tickets';
import { streamDraftTokens } from '../api/client';
import { WorkspaceHeader } from '../components/workspace/WorkspaceHeader';
import { ConversationThread } from '../components/workspace/ConversationThread';
import { ReplyComposer } from '../components/workspace/ReplyComposer';
import { ContextPanel } from '../components/workspace/ContextPanel';
import { EscalateModal } from '../components/workspace/EscalateModal';
import { CloseTicketModal } from '../components/workspace/CloseTicketModal';
import { IssueRefundModal } from '../components/workspace/IssueRefundModal';
import { Skeleton } from '../components/common/Skeleton';

interface TicketDetailViewProps {
  ticketId: string;
  allTickets?: Ticket[];
  onSelectTicket?: (id: string) => void;
  onBackToQueue: () => void;
  currentUserRole?: UserRole;
  currentUserId?: string;
}

interface ErrorBoundaryProps {
  children: React.ReactNode;
  onBackToQueue: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class TicketErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('TicketDetailView render failure:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-xl mx-auto font-sans text-xs text-left">
          <button
            type="button"
            onClick={this.props.onBackToQueue}
            className="text-[#686B78] hover:text-[#282C3F] font-medium mb-4 cursor-pointer flex items-center gap-1.5"
          >
            <span>←</span>
            <span>Back to Ticket Queues</span>
          </button>
          <div className="p-6 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs space-y-3">
            <div className="font-bold text-[#EC3D25] text-base">Unable to Display Ticket</div>
            <p className="text-[#686B78] leading-relaxed">
              {this.state.error?.message || 'A client-side error occurred while rendering the ticket details.'}
            </p>
            <button
              type="button"
              onClick={this.props.onBackToQueue}
              className="px-3.5 py-2 bg-[#FC8019] text-white font-semibold rounded-lg hover:bg-[#E26A00] shadow-xs cursor-pointer transition-all text-xs"
            >
              Return to Ticket Queues
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const TicketDetailViewContent: React.FC<TicketDetailViewProps> = ({
  ticketId,
  onBackToQueue,
  currentUserRole,
  currentUserId,
}) => {
  const [ticket, setTicket] = useState<TicketDetail | null>(null);
  const [actions, setActions] = useState<ToolAction[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [draftText, setDraftText] = useState('');
  const [streamingToken, setStreamingToken] = useState<string | undefined>(undefined);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isEscalateOpen, setIsEscalateOpen] = useState(false);
  const [isCloseOpen, setIsCloseOpen] = useState(false);
  const [isRefundOpen, setIsRefundOpen] = useState(false);
  const [isStatusUpdating, setIsStatusUpdating] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'error' | 'success' | 'info' } | null>(null);

  const showToast = useCallback((message: string, type: 'error' | 'success' | 'info' = 'error') => {
    setToast({ message, type });
    const timer = setTimeout(() => {
      setToast((prev) => (prev?.message === message ? null : prev));
    }, 4500);
    return () => clearTimeout(timer);
  }, []);

  const activeCoupon = React.useMemo(() => {
    for (const act of actions) {
      const code = (act.payload as Record<string, unknown> | null)?.coupon_code;
      if (typeof code === 'string' && code) return code;
    }
    for (const msg of ticket?.messages || []) {
      const match = msg.content.match(/SWIGGY-REF-[A-Z0-9]+/i);
      if (match) return match[0].toUpperCase();
    }
    return null;
  }, [actions, ticket?.messages]);

  const loadData = useCallback(async (id: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const [ticketData, actionsData] = await Promise.all([
        getTicketDetail(id),
        listTicketActions(id).catch(() => [] as ToolAction[]),
      ]);
      setTicket(ticketData);
      setActions(actionsData);

      try {
        const draftData = await getLatestDraft(id);
        if (draftData) {
          setDraftText(draftData.body || '');
          setCitations(draftData.citations || []);
        }
      } catch {
        setDraftText('');
        setCitations([]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load ticket details');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const [availableAgents, setAvailableAgents] = useState<AvailableAgent[]>([]);

  useEffect(() => {
    loadData(ticketId);
  }, [ticketId, loadData]);

  useEffect(() => {
    getAvailableAgents().then(setAvailableAgents).catch(() => {});
  }, []);

  const handleAssignToAgent = async (userId: string) => {
    if (!ticket) return;
    setIsStatusUpdating(true);
    try {
      const updated = await assignTicket(ticket.id, userId);
      await loadData(updated.id);
      showToast('Ticket assigned successfully', 'success');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to assign ticket', 'error');
      await loadData(ticket.id);
    } finally {
      setIsStatusUpdating(false);
    }
  };

  const handleAssignToMe = async () => {
    if (!ticket) return;
    setIsStatusUpdating(true);
    try {
      const updated = await assignTicket(ticket.id, currentUserId);
      await loadData(updated.id);
      showToast('Ticket assigned successfully', 'success');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to assign ticket', 'error');
      await loadData(ticket.id);
    } finally {
      setIsStatusUpdating(false);
    }
  };

  const handleUnassign = async () => {
    if (!ticket) return;
    setIsStatusUpdating(true);
    try {
      const updated = await unassignTicket(ticket.id);
      await loadData(updated.id);
      showToast('Ticket unassigned', 'info');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to unassign ticket', 'error');
    } finally {
      setIsStatusUpdating(false);
    }
  };

  const handleConfirmEscalate = async (reason: string, note?: string, customReason?: string) => {
    if (!ticket) return;
    const updated = await escalateTicket(ticket.id, { reason, note, custom_reason: customReason });
    await loadData(updated.id);
  };

  const handleConfirmClose = async (notes: string, resolutionType: string, customResolution?: string) => {
    if (!ticket) return;
    const updated = await closeTicket(ticket.id, {
      notes,
      resolution_type: resolutionType,
      custom_resolution: customResolution,
    });
    await loadData(updated.id);
  };

  const handleRequestAiDraft = async () => {
    if (!ticket) return;
    setIsStreaming(true);
    setStreamingToken('');

    try {
      await triggerDraft(ticket.id);

      let accumulated = '';
      const stopStream = streamDraftTokens(
        ticket.id,
        (token) => {
          accumulated += token;
          setStreamingToken(accumulated);
          setDraftText(accumulated);
        },
        async (doneData) => {
          setIsStreaming(false);
          setStreamingToken(undefined);
          try {
            const latest = await getLatestDraft(ticket.id);
            if (latest) {
              setDraftText(latest.body || '');
              setCitations(latest.citations || []);
            }
          } catch {
            if (doneData.citations) {
              setCitations(
                doneData.citations.map((docId) => ({ id: docId, doc_id: docId }))
              );
            }
          }
        },
        (streamErr) => {
          console.warn('SSE stream error, falling back to polling latest draft:', streamErr);
          setTimeout(async () => {
            try {
              const latest = await getLatestDraft(ticket.id);
              if (latest) {
                setDraftText(latest.body || '');
                setCitations(latest.citations || []);
              }
            } catch (pollErr) {
              console.error('Draft poll failed:', pollErr);
            } finally {
              setIsStreaming(false);
              setStreamingToken(undefined);
            }
          }, 1500);
        }
      );

      setTimeout(() => {
        setIsStreaming(false);
        setStreamingToken(undefined);
        stopStream();
      }, 15000);
    } catch (err: unknown) {
      setIsStreaming(false);
      setStreamingToken(undefined);
      showToast(err instanceof Error ? err.message : 'Draft generation failed', 'error');
    }
  };

  const handleSendReply = async (content: string) => {
    if (!ticket) return;
    try {
      await postTicketMessage(ticket.id, content);
      await loadData(ticket.id);
      setDraftText('');
      showToast('Reply sent successfully', 'success');
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : 'Failed to send reply', 'error');
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-full">
        <div className="w-72 border-r border-[#E9E9EB] p-4 space-y-3">
          <Skeleton className="h-6 w-32" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
        <div className="flex-1 p-6 space-y-4">
          <Skeleton className="h-10 w-3/4" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="p-8 max-w-xl mx-auto font-sans text-xs text-left">
        <button
          type="button"
          onClick={onBackToQueue}
          className="text-[#686B78] hover:text-[#282C3F] font-medium mb-4 cursor-pointer flex items-center gap-1.5"
        >
          <span>←</span>
          <span>Back to Ticket Queues</span>
        </button>
        <div className="p-6 bg-white border border-[#E9E9EB] rounded-2xl shadow-xs space-y-3">
          <div className="font-bold text-[#282C3F] text-base">Ticket Not Found</div>
          <p className="text-[#686B78]">{error || 'Unable to retrieve the requested ticket record.'}</p>
          <button
            type="button"
            onClick={onBackToQueue}
            className="px-3.5 py-2 bg-[#FC8019] text-white font-semibold rounded-lg hover:bg-[#E26A00] shadow-xs cursor-pointer transition-all text-xs"
          >
            Return to Ticket Queues
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      <WorkspaceHeader
        ticket={ticket}
        currentUserRole={currentUserRole}
        currentUserId={currentUserId}
        onBackToQueue={onBackToQueue}
        onAssignToMe={handleAssignToMe}
        onAssignToAgent={handleAssignToAgent}
        onUnassign={handleUnassign}
        onOpenEscalateModal={() => setIsEscalateOpen(true)}
        onOpenCloseModal={() => setIsCloseOpen(true)}
        onOpenRefundModal={() => setIsRefundOpen(true)}
        availableAgents={availableAgents}
        isLoading={isStatusUpdating}
      />

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col h-full overflow-hidden border-r border-[#E9E9EB]">
          {ticket.close_reason && ticket.close_reason.startsWith('security_attack_blocked') && (
            <div className="mx-6 mt-4 p-4 bg-[#FFF5F5] border-2 border-[#EC3D25]/40 rounded-2xl flex items-start gap-3 shadow-xs">
              <div className="text-xl">🛑</div>
              <div className="flex-1">
                <div className="text-xs font-bold text-[#EC3D25] tracking-wide uppercase font-sans">
                  Security Attack Blocked & Auto-Closed
                </div>
                <p className="text-xs text-[#282C3F] mt-0.5 font-sans leading-relaxed">
                  This ticket was terminated automatically after detecting a web application exploit (
                  <span className="font-semibold text-[#EC3D25]">
                    {ticket.close_reason.includes(': ') ? ticket.close_reason.split(': ')[1] : ticket.close_reason}
                  </span>
                  ). The payload was neutralized, logged for audit, and marked critical risk.
                </p>
              </div>
            </div>
          )}

          {ticket.coupon_abuse_flag && (
            <div className="mx-6 mt-4 p-4 bg-[#FFF9F5] border-2 border-[#FC8019]/40 rounded-2xl flex items-start gap-3 shadow-xs">
              <div className="text-xl">🚨</div>
              <div className="flex-1">
                <div className="text-xs font-bold text-[#EC3D25] tracking-wide uppercase font-sans">
                  Duplicate Coupon Abuse: Auto-Closed (409 Conflict)
                </div>
                <p className="text-xs text-[#282C3F] mt-0.5 font-sans leading-relaxed">
                  This ticket was automatically rejected and closed as a duplicate due to an attempt to reuse coupon{' '}
                  <span className="font-mono font-bold text-[#FC8019] bg-[#FFF2E5] px-1.5 py-0.5 rounded border border-[#FC8019]/30">
                    {ticket.coupon_code || 'VOUCHER'}
                  </span>{' '}
                  which was already redeemed on another order.
                </p>
              </div>
            </div>
          )}

          {ticket.coupon_code && !ticket.coupon_abuse_flag && (
            <div className="mx-6 mt-4 p-3 bg-[#F0FDF4] border border-[#60B246]/40 rounded-2xl flex items-center justify-between shadow-xs">
              <div className="flex items-center gap-2">
                <span className="text-base">🎟️</span>
                <span className="text-xs font-bold text-[#2A7E15] font-sans uppercase">
                  Verified Refund Coupon Applied:
                </span>
                <span className="font-mono font-bold text-xs text-[#282C3F] bg-white px-2 py-0.5 rounded-lg border border-[#60B246]/30">
                  {ticket.coupon_code}
                </span>
              </div>
              {ticket.coupon_discount ? (
                <span className="text-xs font-bold font-mono text-[#2A7E15]">
                  -₹{(Number(ticket.coupon_discount) || 0).toFixed(2)}
                </span>
              ) : null}
            </div>
          )}

          <ConversationThread
            messages={ticket.messages || []}
            customerName={ticket.customer?.name}
            streamingToken={streamingToken}
          />
          <ReplyComposer
            ticketId={ticket.id}
            ticketStatus={ticket.status}
            onSendReply={handleSendReply}
            onRequestAiDraft={handleRequestAiDraft}
            isStreamingDraft={isStreaming}
            citations={citations}
            draftText={draftText}
            onDraftTextChange={setDraftText}
            activeCoupon={activeCoupon}
          />
        </div>

        <ContextPanel
          key={`${ticket.id}-${ticket.updated_at}`}
          ticket={ticket}
          actions={actions}
          citations={citations}
        />
      </div>

      <EscalateModal
        isOpen={isEscalateOpen}
        onClose={() => setIsEscalateOpen(false)}
        ticketId={ticket.id}
        ticketSubject={ticket.subject}
        onConfirmEscalate={handleConfirmEscalate}
      />

      <CloseTicketModal
        isOpen={isCloseOpen}
        ticket={ticket}
        onClose={() => setIsCloseOpen(false)}
        onConfirmClose={handleConfirmClose}
      />

      <IssueRefundModal
        isOpen={isRefundOpen}
        onClose={() => setIsRefundOpen(false)}
        ticketId={ticket.id}
        orderTotal={ticket.order?.total}
        onSuccess={async (couponCode, amt) => {
          showToast(`Refund coupon ${couponCode} (₹${amt.toFixed(2)}) issued successfully.`, 'success');
          await loadData(ticket.id);
        }}
      />

      {toast && (
        <div
          role="status"
          className={`fixed bottom-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg border text-xs font-medium ${
            toast.type === 'error'
              ? 'bg-[#FDF0EE] text-[#EC3D25] border-[#EC3D25]/30'
              : toast.type === 'success'
              ? 'bg-[#EBF7E9] text-[#2A7E15] border-[#60B246]/40'
              : 'bg-[#FFF2E5] text-[#FC8019] border-[#FC8019]/40'
          }`}
        >
          <span>{toast.message}</span>
          <button
            type="button"
            onClick={() => setToast(null)}
            className="ml-2 p-0.5 rounded-md text-current opacity-70 hover:opacity-100 hover:bg-black/5 transition-all cursor-pointer flex items-center justify-center"
            aria-label="Dismiss toast"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
};

export const TicketDetailView: React.FC<TicketDetailViewProps> = (props) => (
  <div className="flex flex-col h-full">
    <TicketErrorBoundary onBackToQueue={props.onBackToQueue}>
      <TicketDetailViewContent {...props} />
    </TicketErrorBoundary>
  </div>
);
