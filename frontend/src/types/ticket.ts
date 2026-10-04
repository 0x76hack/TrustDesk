export interface Customer {
  id: string;
  name: string;
  email: string;
  phone?: string | null;
  address?: string | null;
  membership_tier?: string | null;
  total_orders?: number | null;
  created_at?: string;
}

export interface OrderItem {
  id: string;
  order_id: string;
  item_name: string;
  quantity: number;
  unit_price: number;
}

export interface Order {
  id: string;
  customer_id: string;
  restaurant: string;
  restaurant_address?: string | null;
  delivery_address?: string | null;
  status: 'placed' | 'confirmed' | 'preparing' | 'dispatched' | 'delivered' | 'cancelled' | string;
  live_status_message?: string | null;
  delivery_partner_name?: string | null;
  delivery_partner_phone?: string | null;
  estimated_delivery_at?: string | null;
  delay_reason?: string | null;
  payment_method?: string | null;
  total: number;
  currency: string;
  coupon_code?: string | null;
  discount_amount?: number | null;
  placed_at?: string | null;
  delivered_at?: string | null;
  items?: OrderItem[];
}

export interface Message {
  id: string;
  ticket_id: string;
  sender_type: 'customer' | 'agent' | 'system';
  content: string;
  created_at?: string;
}

export type TicketCategory = 'shipping' | 'refund' | 'warranty' | 'billing' | 'account_security' | 'general';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';
export type TicketRiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type TicketStatus = 'open' | 'working' | 'escalated' | 'resolved';

export interface Ticket {
  id: string;
  customer_id: string;
  order_id?: string | null;
  subject: string;
  category?: TicketCategory | null;
  priority?: TicketPriority | null;
  status: TicketStatus;
  escalation_flag: boolean;
  risk_level?: TicketRiskLevel | null;
  assigned_to?: string | null;
  assigned_at?: string | null;
  first_response_at?: string | null;
  resolved_at?: string | null;
  notes?: string | null;
  assignee_name?: string | null;
  coupon_code?: string | null;
  coupon_discount?: number | null;
  coupon_status?: string | null;
  coupon_abuse_flag?: boolean;
  close_reason?: string | null;
  assignee?: {
    id: string;
    name: string;
    username: string;
    role: string;
  } | null;
  created_at?: string;
  updated_at?: string;
}

export interface TicketDetail extends Ticket {
  customer?: Customer | null;
  order?: Order | null;
  messages: Message[];
  assignee_name?: string | null;
}

export interface InternalNote {
  id: string;
  ticket_id: string;
  author_id: string;
  author_name: string;
  author_role: string;
  content: string;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  title: string;
  actor_name: string;
  actor_role: string;
  details?: string | null;
  created_at: string;
}


export interface Citation {
  id: string;
  doc_id: string;
  chunk_id?: string | null;
  relevance_score?: number | null;
}

export interface DraftDetail {
  id: string;
  ticket_id: string;
  run_id?: string | null;
  body: string;
  status: 'pending' | 'ready' | 'sent' | 'discarded';
  citations: Citation[];
  created_at?: string;
}

export interface ToolAction {
  id: string;
  ticket_id: string;
  run_id?: string | null;
  tool_id?: string | null;
  tool_name?: string | null;
  payload?: Record<string, unknown> | null;
  risk_level: string;
  status: 'proposed' | 'pending_approval' | 'approved' | 'executed' | 'rejected';
  idempotency_key: string;
  created_at: string;
  executed_at?: string | null;
}

export interface TicketCreateRequest {
  customer_id: string;
  order_id?: string | null;
  subject: string;
  message: string;
  category?: string | null;
}

export interface TicketUpdateRequest {
  status?: string;
  priority?: string;
  category?: string;
  escalation_flag?: boolean;
}

export interface TicketEscalateRequest {
  reason: string;
  note?: string;
  custom_reason?: string;
}

export interface TicketCloseRequest {
  notes: string;
  resolution_type?: string;
  custom_resolution?: string;
}

