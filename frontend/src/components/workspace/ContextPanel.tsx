import React, { useState, useEffect, useCallback } from 'react';
import type { TicketDetail, ToolAction, Citation, InternalNote, TimelineEvent } from '../../types/ticket';
import { RiskBadge, CategoryPill } from '../common/Badge';
import { getTicketHistory, getTicketNotes, createTicketNote } from '../../api/tickets';

interface ContextPanelProps {
  ticket: TicketDetail;
  actions?: ToolAction[];
  citations?: Citation[];
}

type PanelTab = 'context' | 'history' | 'notes';

export const ContextPanel: React.FC<ContextPanelProps> = ({
  ticket,
  actions = [],
  citations = [],
}) => {
  const [activeTab, setActiveTab] = useState<PanelTab>('context');

  const [historyEvents, setHistoryEvents] = useState<TimelineEvent[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);

  const [notes, setNotes] = useState<InternalNote[]>([]);
  const [isNotesLoading, setIsNotesLoading] = useState(false);
  const [newNoteContent, setNewNoteContent] = useState('');
  const [isSubmittingNote, setIsSubmittingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [copiedActionId, setCopiedActionId] = useState<string | null>(null);

  const handleCopyActionCoupon = (id: string, code: string) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(code).catch(() => {
        try {
          const textArea = document.createElement('textarea');
          textArea.value = code;
          document.body.appendChild(textArea);
          textArea.select();
          document.execCommand('copy');
          document.body.removeChild(textArea);
        } catch {
        }
      });
    } else {
      try {
        const textArea = document.createElement('textarea');
        textArea.value = code;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      } catch {
      }
    }
    setCopiedActionId(id);
    setTimeout(() => {
      setCopiedActionId((curr) => (curr === id ? null : curr));
    }, 2000);
  };

  const order = ticket.order;
  const customer = ticket.customer;

  useEffect(() => {
    setNotes([]);
    setHistoryEvents([]);
    setNewNoteContent('');
    setNoteError(null);
  }, [ticket.id]);

  const loadHistory = useCallback(async () => {
    const targetId = ticket.id;
    try {
      setIsHistoryLoading(true);
      const data = await getTicketHistory(targetId);
      if (ticket.id === targetId) {
        setHistoryEvents(data);
      }
    } catch {
      if (ticket.id === targetId) {
        setHistoryEvents([]);
      }
    } finally {
      if (ticket.id === targetId) {
        setIsHistoryLoading(false);
      }
    }
  }, [ticket.id]);

  const loadNotes = useCallback(async () => {
    const targetId = ticket.id;
    try {
      setIsNotesLoading(true);
      const data = await getTicketNotes(targetId);
      if (ticket.id === targetId) {
        setNotes(data);
      }
    } catch {
      if (ticket.id === targetId) {
        setNotes([]);
      }
    } finally {
      if (ticket.id === targetId) {
        setIsNotesLoading(false);
      }
    }
  }, [ticket.id]);

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory();
    } else if (activeTab === 'notes') {
      loadNotes();
    }
  }, [activeTab, ticket.id, ticket.updated_at, loadHistory, loadNotes]);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteContent.trim()) return;
    try {
      setIsSubmittingNote(true);
      setNoteError(null);
      const created = await createTicketNote(ticket.id, newNoteContent.trim());
      setNotes((prev) => [...prev, created]);
      setNewNoteContent('');
    } catch (err: unknown) {
      setNoteError(err instanceof Error ? err.message : 'Failed to record internal note.');
    } finally {
      setIsSubmittingNote(false);
    }
  };

  const getOrderStageIndex = (status?: string): number => {
    const s = (status || '').toLowerCase();
    if (s === 'delivered') return 3;
    if (s === 'dispatched') return 2;
    if (s === 'preparing' || s === 'confirmed') return 1;
    if (s === 'placed') return 0;
    return 0;
  };

  const orderStage = getOrderStageIndex(order?.status);

  return (
    <aside className="w-96 bg-[#F9FAFC] border-l border-[#E9E9EB] flex flex-col h-full overflow-hidden shrink-0 font-sans text-xs">
      <div className="flex border-b border-[#E9E9EB] bg-[#F4F5F8]">
        <button
          type="button"
          onClick={() => setActiveTab('context')}
          className={`flex-1 py-3 px-2 text-center font-semibold text-xs border-r border-[#E9E9EB] transition-all cursor-pointer ${
            activeTab === 'context'
              ? 'bg-white text-[#FC8019] border-b-2 border-b-[#FC8019]'
              : 'text-[#686B78] hover:bg-[#FFF2E5] hover:text-[#FC8019]'
          }`}
        >
          Context & Order
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('history')}
          className={`flex-1 py-3 px-2 text-center font-semibold text-xs border-r border-[#E9E9EB] transition-all cursor-pointer ${
            activeTab === 'history'
              ? 'bg-white text-[#FC8019] border-b-2 border-b-[#FC8019]'
              : 'text-[#686B78] hover:bg-[#FFF2E5] hover:text-[#FC8019]'
          }`}
        >
          Audit History
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('notes')}
          className={`flex-1 py-3 px-2 text-center font-semibold text-xs transition-all cursor-pointer ${
            activeTab === 'notes'
              ? 'bg-white text-[#FC8019] border-b-2 border-b-[#FC8019]'
              : 'text-[#686B78] hover:bg-[#FFF2E5] hover:text-[#FC8019]'
          }`}
        >
          Notes {notes.length > 0 && `(${notes.length})`}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeTab === 'context' && (
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-[11px] text-[#282C3F] uppercase tracking-wider">
                  Live Order Tracking
                </span>
                {order && (
                  <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                    order.status === 'delivered'
                      ? 'bg-[#EBF7E9] text-[#2A7E15] border border-[#60B246]/40'
                      : order.status === 'cancelled'
                      ? 'bg-[#FDF0EE] text-[#EC3D25] border border-[#EC3D25]/40'
                      : 'bg-[#FFF2E5] text-[#FC8019] border border-[#FC8019]/40'
                  }`}>
                    {order.status === 'delivered' ? 'Delivered' : order.status === 'dispatched' ? 'On the Way' : order.status === 'preparing' ? 'In Kitchen' : order.status}
                  </span>
                )}
              </div>

              {order ? (
                <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] space-y-3.5 shadow-2xs">
                  <div>
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-bold text-sm text-[#282C3F]">{order.restaurant}</h3>
                        {order.restaurant_address && (
                          <p className="text-[11px] text-[#686B78] mt-0.5">{order.restaurant_address}</p>
                        )}
                      </div>
                      <span className="font-mono text-[11px] font-bold text-[#FC8019] bg-[#FFF2E5] px-2 py-0.5 rounded-md">
                        {order.id}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 pb-1">
                    <div className="relative flex items-center justify-between">
                      <div className="absolute left-3 right-3 top-3.5 h-0.5 bg-[#E9E9EB] -z-0" />
                      <div
                        className="absolute left-3 top-3.5 h-0.5 bg-[#60B246] -z-0 transition-all duration-500"
                        style={{
                          width: `${(orderStage / 3) * 100}%`,
                        }}
                      />

                      <div className="relative z-10 flex flex-col items-center">
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold ${
                          orderStage >= 0 ? 'bg-[#60B246] text-white shadow-xs' : 'bg-white border-2 border-[#D4D5D9] text-[#686B78]'
                        }`}>
                          ✓
                        </div>
                        <span className="text-[10px] font-semibold text-[#282C3F] mt-1.5 text-center">
                          Placed
                        </span>
                      </div>

                      <div className="relative z-10 flex flex-col items-center">
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-all ${
                          orderStage > 1
                            ? 'bg-[#60B246] text-white shadow-xs'
                            : orderStage === 1
                            ? 'bg-[#FC8019] text-white ring-4 ring-[#FFF2E5] shadow-xs'
                            : 'bg-white border-2 border-[#D4D5D9] text-[#686B78]'
                        }`}>
                          {orderStage > 1 ? '✓' : '2'}
                        </div>
                        <span className="text-[10px] font-semibold text-[#282C3F] mt-1.5 text-center">
                          Preparing
                        </span>
                      </div>

                      <div className="relative z-10 flex flex-col items-center">
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-all ${
                          orderStage > 2
                            ? 'bg-[#60B246] text-white shadow-xs'
                            : orderStage === 2
                            ? 'bg-[#FC8019] text-white ring-4 ring-[#FFF2E5] shadow-xs'
                            : 'bg-white border-2 border-[#D4D5D9] text-[#686B78]'
                        }`}>
                          {orderStage > 2 ? '✓' : '3'}
                        </div>
                        <span className="text-[10px] font-semibold text-[#282C3F] mt-1.5 text-center">
                          On the Way
                        </span>
                      </div>

                      <div className="relative z-10 flex flex-col items-center">
                        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-all ${
                          orderStage === 3
                            ? 'bg-[#60B246] text-white shadow-xs ring-4 ring-[#EBF7E9]'
                            : 'bg-white border-2 border-[#D4D5D9] text-[#686B78]'
                        }`}>
                          {orderStage === 3 ? '✓' : '4'}
                        </div>
                        <span className="text-[10px] font-semibold text-[#282C3F] mt-1.5 text-center">
                          Delivered
                        </span>
                      </div>
                    </div>
                  </div>

                  {order.delay_reason && (
                    <div className="p-3 rounded-xl bg-[#FFF9F5] border border-[#FFD7B0] text-[#D45D00] space-y-1">
                      <div className="flex items-center gap-1.5 font-bold text-xs">
                        <span>⚠️ Delay Update</span>
                      </div>
                      <p className="text-[11px] text-[#686B78] leading-relaxed">
                        {order.delay_reason}
                      </p>
                    </div>
                  )}

                  {order.live_status_message && !order.delay_reason && (
                    <div className="p-2.5 rounded-xl bg-[#F4F5F8] border border-[#E9E9EB] text-[#282C3F] text-[11px] flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[#60B246] animate-pulse shrink-0" />
                      <span>{order.live_status_message}</span>
                    </div>
                  )}

                  {order.delivery_partner_name && (
                    <div className="p-2.5 rounded-xl bg-[#F9FAFC] border border-[#E9E9EB] flex items-center justify-between text-[11px]">
                      <div>
                        <span className="text-[#686B78] block text-[10px]">Delivery Partner</span>
                        <span className="font-bold text-[#282C3F]">{order.delivery_partner_name}</span>
                      </div>
                      {order.delivery_partner_phone && (
                        <span className="text-[#FC8019] font-semibold">{order.delivery_partner_phone}</span>
                      )}
                    </div>
                  )}

                  {order.items && order.items.length > 0 && (
                    <div className="pt-1 border-t border-[#F2F2F6]">
                      <div className="text-[10px] uppercase font-bold text-[#93959F] mb-1.5">
                        Items Ordered ({order.items.length})
                      </div>
                      <div className="divide-y divide-[#F9FAFC]">
                        {order.items.map((item) => (
                          <div key={item.id} className="py-1.5 flex items-center justify-between text-xs">
                            <span className="text-[#282C3F] font-medium">
                              {item.quantity}x {item.item_name}
                            </span>
                            <span className="font-semibold text-[#282C3F]">
                              ₹{((Number(item.unit_price) || 0) * (Number(item.quantity) || 1)).toFixed(2)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="pt-2 border-t border-[#E9E9EB] space-y-1.5">
                    <div className="flex items-center justify-between font-bold text-xs">
                      <span className="text-[#686B78]">Total Paid</span>
                      <span className="text-sm font-extrabold text-[#282C3F]">₹{(Number(order.total) || 0).toFixed(2)}</span>
                    </div>
                    {(order.coupon_code || ticket.coupon_code) && !ticket.coupon_abuse_flag && (
                      <div className="flex items-center justify-between text-[11px] p-2 bg-[#F0FDF4] rounded-lg border border-[#60B246]/30">
                        <span className="text-[#2A7E15] font-semibold flex items-center gap-1">
                          <span>🎟️</span> Coupon Applied
                        </span>
                        <div className="text-right">
                          <span className="font-mono font-bold text-[#2A7E15] text-[10px] block">
                            {order.coupon_code || ticket.coupon_code}
                          </span>
                          {(order.discount_amount || ticket.coupon_discount) && (
                            <span className="text-[10px] font-bold text-[#2A7E15] font-mono">
                              -₹{(Number(order.discount_amount || ticket.coupon_discount) || 0).toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                    {ticket.coupon_abuse_flag && (
                      <div className="p-2 bg-[#FFF5F5] rounded-lg border border-[#EC3D25]/30 text-[10px] text-[#EC3D25] font-bold">
                        🚨 Duplicate Coupon Reuse Rejected (409 Conflict)
                      </div>
                    )}
                    {order.payment_method && (
                      <div className="flex items-center justify-between text-[11px] text-[#686B78]">
                        <span>Payment Mode</span>
                        <span className="font-medium text-[#282C3F]">{order.payment_method}</span>
                      </div>
                    )}
                    {order.placed_at && (
                      <div className="flex items-center justify-between text-[10px] text-[#93959F]">
                        <span>Placed At</span>
                        <span>{new Date(order.placed_at).toLocaleString()}</span>
                      </div>
                    )}
                    {order.delivered_at && (
                      <div className="flex items-center justify-between text-[10px] text-[#2A7E15] font-semibold">
                        <span>Delivered At</span>
                        <span>{new Date(order.delivered_at).toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-white rounded-2xl border border-[#E9E9EB] text-[#93959F] text-center text-xs">
                  No commerce order associated with this ticket.
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="font-bold text-[11px] text-[#282C3F] uppercase tracking-wider">
                Customer Record
              </div>
              <div className="bg-white p-4 rounded-2xl border border-[#E9E9EB] space-y-2 shadow-2xs">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-bold text-[#282C3F] text-sm">{customer?.name || 'Customer'}</h4>
                    <span className="text-[10px] text-[#686B78] font-mono">ID: {ticket.customer_id ? ticket.customer_id.slice(0, 12) : 'N/A'}</span>
                  </div>
                  {customer?.membership_tier && (
                    <span className="px-2 py-0.5 rounded-full bg-[#FFF2E5] text-[#FC8019] font-bold text-[10px] border border-[#FFD7B0]">
                      {customer.membership_tier}
                    </span>
                  )}
                </div>

                <div className="space-y-1 text-xs text-[#686B78] pt-1">
                  <div className="flex justify-between">
                    <span>Email:</span>
                    <span className="text-[#282C3F] font-medium">{customer?.email || 'N/A'}</span>
                  </div>
                  {customer?.phone && (
                    <div className="flex justify-between">
                      <span>Phone:</span>
                      <span className="text-[#282C3F] font-medium">{customer.phone}</span>
                    </div>
                  )}
                  {customer?.address && (
                    <div className="pt-1.5 border-t border-[#F2F2F6]">
                      <span className="text-[10px] text-[#93959F] block">Delivery Address</span>
                      <p className="text-[11px] text-[#282C3F] leading-relaxed mt-0.5">{customer.address}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="font-bold text-[11px] text-[#282C3F] uppercase tracking-wider">
                Triage & Risk Assessment
              </div>
              <div className="bg-white p-3.5 rounded-2xl border border-[#E9E9EB] space-y-2.5 shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="text-[#686B78]">Category:</span>
                  <CategoryPill category={ticket.category} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[#686B78]">Risk Level:</span>
                  <RiskBadge risk={ticket.risk_level} />
                </div>
                {ticket.escalation_flag && (
                  <div className="p-2.5 rounded-xl bg-[#FDF0EE] border border-[#EC3D25]/30 text-[#EC3D25] text-xs font-semibold">
                    Senior agent review required for this issue.
                  </div>
                )}
                {ticket.close_reason && (
                  <div className="p-2.5 rounded-xl bg-[#FDF0EE] border border-[#EC3D25]/30 text-[#EC3D25] text-xs space-y-0.5">
                    <div className="font-bold uppercase tracking-wider text-[10px]">Close Reason</div>
                    <div className="font-medium font-mono text-[11px] leading-tight break-all">{ticket.close_reason}</div>
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="font-bold text-[11px] text-[#282C3F] uppercase tracking-wider">
                Automated Actions
              </div>
              {actions.length > 0 ? (
                <div className="space-y-2">
                  {actions.map((act) => {
                    const rawCoupon = (act.payload as Record<string, unknown> | null)?.coupon_code;
                    const couponCode = typeof rawCoupon === 'string' ? rawCoupon : null;
                    const isRefundAction = act.tool_name === 'issue_refund' || !!couponCode;
                    const isCopied = copiedActionId === act.id;

                    return (
                      <div key={act.id} className="bg-white p-3 rounded-xl border border-[#E9E9EB] space-y-1.5 shadow-2xs">
                        <div className="flex items-center justify-between font-bold">
                          <span className="text-[#282C3F]">{act.tool_name || 'Action'}</span>
                          <span className="text-[10px] text-[#FC8019] bg-[#FFF2E5] px-2 py-0.5 rounded border border-[#FC8019]/40 font-semibold">
                            {act.status}
                          </span>
                        </div>
                        {isRefundAction && (
                          <div className="p-2.5 bg-[#FFF9F5] border border-[#FFD7B0] rounded-xl flex items-center justify-between">
                            <div>
                              <span className="text-[10px] text-[#686B78] block">Refund Coupon Code</span>
                              <span className="font-mono text-xs font-black text-[#FC8019] tracking-wider">
                                {couponCode || 'Pending generation'}
                              </span>
                            </div>
                            {couponCode && (
                              <button
                                type="button"
                                onClick={() => handleCopyActionCoupon(act.id, couponCode)}
                                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all cursor-pointer flex items-center gap-1 shadow-2xs ${
                                  isCopied
                                    ? 'bg-[#60B246] text-white'
                                    : 'bg-[#FC8019] hover:bg-[#E26A00] text-white'
                                }`}
                              >
                                {isCopied ? <span>✓ Copied!</span> : <span>📋 Copy</span>}
                              </button>
                            )}
                          </div>
                        )}
                        {act.payload && (
                          <pre className="p-2 bg-[#F4F5F8] rounded text-[11px] text-[#282C3F] overflow-x-auto border border-[#E9E9EB] font-mono">
                            {JSON.stringify(act.payload, null, 2)}
                          </pre>
                        )}
                        <div className="flex justify-between text-[11px] text-[#686B78]">
                          <span>Risk: {act.risk_level}</span>
                          <span>{act.status === 'executed' ? 'Completed' : ''}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="bg-white p-3.5 rounded-2xl border border-[#E9E9EB] text-center shadow-2xs">
                  <p className="text-[#686B78] text-xs">No actions proposed for this ticket.</p>
                </div>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="font-bold text-[11px] text-[#282C3F] uppercase tracking-wider">
                Knowledge Base Policies
              </div>
              {citations.length > 0 ? (
                <div className="space-y-1.5">
                  {citations.map((c) => (
                    <div key={c.id || c.doc_id} className="bg-white p-3 rounded-xl border border-[#E9E9EB] space-y-1 shadow-2xs">
                      <div className="flex items-center justify-between font-bold text-[#282C3F]">
                        <span className="font-mono text-[11px]">{c.doc_id}</span>
                        {c.relevance_score != null && (
                          <span className="text-[10px] text-[#2A7E15] bg-[#EBF7E9] px-1.5 py-0.5 rounded border border-[#60B246]/40 font-bold">
                            {(c.relevance_score * 100).toFixed(0)}% Match
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-[#686B78]">
                        Grounding evidence retrieved from policy manual.
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 bg-white rounded-xl border border-[#E9E9EB] text-[#93959F] text-center text-xs">
                  No policy documents cited for this ticket.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-[#E9E9EB]">
              <span className="font-bold text-[11px] text-[#282C3F] uppercase">
                Chronological Audit Trail
              </span>
              <button
                type="button"
                onClick={loadHistory}
                className="text-xs text-[#FC8019] hover:underline font-semibold cursor-pointer"
              >
                Refresh
              </button>
            </div>

            {isHistoryLoading ? (
              <div className="p-4 text-center text-[#686B78] text-xs">
                Fetching audit timeline...
              </div>
            ) : historyEvents.length === 0 ? (
              <div className="p-4 bg-white rounded-xl border border-[#E9E9EB] text-center text-[#93959F] text-xs">
                No historical events logged yet.
              </div>
            ) : (
              <div className="relative border-l-2 border-[#FC8019]/40 ml-2 space-y-3 py-1">
                {historyEvents.map((evt) => (
                  <div key={evt.id} className="relative pl-4">
                    <div className="absolute -left-[6px] top-1.5 w-2.5 h-2.5 bg-[#FC8019] rounded-full border-2 border-white" />
                    <div className="bg-white p-3 rounded-xl border border-[#E9E9EB] space-y-1 shadow-2xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#282C3F] text-xs">
                          {evt.title}
                        </span>
                        <span className="text-[10px] text-[#93959F]">
                          {new Date(evt.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#686B78] flex justify-between">
                        <span>Actor: {evt.actor_name}</span>
                        <span className="text-[#282C3F] font-semibold">({evt.actor_role})</span>
                      </div>
                      {evt.details && (
                        <p className="text-xs text-[#282C3F] bg-[#F4F5F8] p-2 rounded-lg border border-[#E9E9EB]">
                          {evt.details}
                        </p>
                      )}
                      <div className="text-[10px] text-[#93959F]">
                        {new Date(evt.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'notes' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pb-1 border-b border-[#E9E9EB]">
              <span className="font-bold text-[11px] text-[#282C3F] uppercase">
                Operative Handover & Notes
              </span>
              <button
                type="button"
                onClick={loadNotes}
                className="text-xs text-[#FC8019] hover:underline font-semibold cursor-pointer"
              >
                Refresh
              </button>
            </div>

            <form onSubmit={handleAddNote} className="bg-white p-3.5 rounded-xl border border-[#E9E9EB] space-y-2 shadow-2xs">
              <label className="block text-xs font-semibold text-[#282C3F]">
                Add internal note:
              </label>
              <textarea
                value={newNoteContent}
                onChange={(e) => setNewNoteContent(e.target.value)}
                placeholder="Type internal investigation notes, supervisor remarks, or courier contact notes..."
                rows={3}
                className="w-full p-2.5 bg-[#F4F5F8] border border-[#D4D5D9] rounded-lg text-xs text-[#282C3F] focus:outline-hidden focus:border-[#FC8019] focus:bg-white transition-colors leading-relaxed"
              />
              {noteError && (
                <p className="text-[11px] text-[#EC3D25] font-semibold">{noteError}</p>
              )}
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSubmittingNote || !newNoteContent.trim()}
                  className="px-3.5 py-1.5 bg-[#FC8019] hover:bg-[#E26A00] text-white rounded-lg text-xs font-semibold disabled:opacity-50 cursor-pointer shadow-xs"
                >
                  {isSubmittingNote ? 'Saving...' : 'Save Note'}
                </button>
              </div>
            </form>

            {isNotesLoading ? (
              <div className="p-4 text-center text-[#686B78] text-xs">
                Fetching notes...
              </div>
            ) : notes.length === 0 ? (
              <div className="p-4 bg-white rounded-xl border border-[#E9E9EB] text-center text-[#93959F] text-xs">
                No internal notes posted on this ticket yet.
              </div>
            ) : (
              <div className="space-y-2.5">
                {notes.map((n) => (
                  <div key={n.id} className="bg-white p-3 rounded-xl border border-[#E9E9EB] space-y-1.5 shadow-2xs">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-[#282C3F]">{n.author_name}</span>
                      <span className="text-[10px] text-[#FC8019] bg-[#FFF2E5] px-1.5 py-0.5 rounded border border-[#FC8019]/30 font-semibold">
                        {n.author_role}
                      </span>
                    </div>
                    <p className="text-xs text-[#282C3F] whitespace-pre-wrap leading-relaxed">
                      {n.content}
                    </p>
                    <div className="text-[10px] text-[#93959F] pt-1 border-t border-[#F4F5F8]">
                      {new Date(n.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </aside>
  );
};
