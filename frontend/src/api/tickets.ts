import { apiFetch } from './client';
import type {
  Ticket,
  TicketDetail,
  Message,
  DraftDetail,
  ToolAction,
  TicketCreateRequest,
  TicketUpdateRequest,
  TicketEscalateRequest,
} from '../types/ticket';

export interface ListTicketsParams {
  limit?: number;
  offset?: number;
  queue?: 'open' | 'escalated' | 'resolved' | 'working' | string;
  category?: string;
}

export async function listTickets(params: ListTicketsParams = {}): Promise<Ticket[]> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  if (params.queue) query.set('queue', params.queue);
  if (params.category) query.set('category', params.category);

  const qs = query.toString();
  return apiFetch<Ticket[]>(`/tickets/${qs ? `?${qs}` : ''}`);
}

export async function assignTicket(ticketId: string, userId?: string): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${ticketId}/assign`, {
    method: 'POST',
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function unassignTicket(ticketId: string): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${ticketId}/unassign`, {
    method: 'POST',
  });
}

export async function postTicketMessage(ticketId: string, content: string): Promise<Message> {
  return apiFetch<Message>(`/tickets/${ticketId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, sender_type: 'agent' }),
  });
}

export async function getTicketDetail(ticketId: string): Promise<TicketDetail> {
  return apiFetch<TicketDetail>(`/tickets/${ticketId}`);
}

export async function getTicketMessages(ticketId: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/tickets/${ticketId}/messages`);
}

export async function createTicket(data: TicketCreateRequest): Promise<Ticket> {
  return apiFetch<Ticket>('/tickets/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTicket(
  ticketId: string,
  data: TicketUpdateRequest
): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${ticketId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function escalateTicket(
  ticketId: string,
  data: TicketEscalateRequest
): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${ticketId}/escalate`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function closeTicket(
  ticketId: string,
  data: { notes: string; resolution_type?: string; custom_resolution?: string }
): Promise<Ticket> {
  return apiFetch<Ticket>(`/tickets/${ticketId}/close`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function triggerTriage(ticketId: string): Promise<{ run_id: string }> {
  return apiFetch<{ run_id: string }>(`/tickets/${ticketId}/triage`, {
    method: 'POST',
  });
}

export async function triggerDraft(ticketId: string): Promise<{ run_id: string }> {
  return apiFetch<{ run_id: string }>(`/tickets/${ticketId}/draft`, {
    method: 'POST',
  });
}

export async function getLatestDraft(ticketId: string): Promise<DraftDetail> {
  return apiFetch<DraftDetail>(`/tickets/${ticketId}/draft`);
}

export async function triggerAction(
  ticketId: string,
  actionData: { tool_name: string; payload?: Record<string, unknown> }
): Promise<{ run_id: string }> {
  return apiFetch<{ run_id: string }>(`/tickets/${ticketId}/actions`, {
    method: 'POST',
    body: JSON.stringify(actionData),
  });
}

export async function listTicketActions(ticketId: string): Promise<ToolAction[]> {
  return apiFetch<ToolAction[]>(`/tickets/${ticketId}/actions`);
}

export async function getTicketNotes(ticketId: string) {
  return apiFetch<import('../types/ticket').InternalNote[]>(`/tickets/${ticketId}/notes`);
}

export async function createTicketNote(ticketId: string, content: string) {
  return apiFetch<import('../types/ticket').InternalNote>(`/tickets/${ticketId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export async function getTicketHistory(ticketId: string) {
  return apiFetch<import('../types/ticket').TimelineEvent[]>(`/tickets/${ticketId}/history`);
}

export async function getMyHandledTickets() {
  return apiFetch<Ticket[]>('/tickets/my-history');
}

export async function issueTicketRefund(
  ticketId: string,
  amount: number,
  reason?: string
): Promise<{ coupon_code: string; amount: number; ticket_id: string; order_id?: string; status: string; message?: string }> {
  return apiFetch(`/tickets/${ticketId}/refund`, {
    method: 'POST',
    body: JSON.stringify({ amount, reason }),
  });
}

export interface AvailableAgent {
  id: string;
  name: string;
  username: string;
  role: string;
  email: string;
}

export async function getAvailableAgents(): Promise<AvailableAgent[]> {
  return apiFetch<AvailableAgent[]>('/tickets/agents');
}

