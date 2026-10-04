import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { createTicket, triggerTriage } from '../../api/tickets';
import { listCustomers, listOrders } from '../../api/admin';
import type { Customer, Order } from '../../types/ticket';

interface CreateTicketModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTicketCreated: (newTicketId: string) => void;
}

export const CreateTicketModal: React.FC<CreateTicketModalProps> = ({
  isOpen,
  onClose,
  onTicketCreated,
}) => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);

  const [customerId, setCustomerId] = useState('');
  const [orderId, setOrderId] = useState('');
  const [category, setCategory] = useState<string>('refund');
  const [customCategory, setCustomCategory] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      Promise.all([
        listCustomers().catch(() => [] as Customer[]),
        listOrders().catch(() => [] as Order[]),
      ]).then(([custList, ordList]) => {
        setCustomers(custList);
        setOrders(ordList);
        if (custList.length > 0 && !customerId) {
          setCustomerId(custList[0].id);
        }
      });
    }
  }, [isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customerId.trim()) {
      setErrorMessage('Please specify the Customer Account ID (CX ID) to which this complaint is attached.');
      return;
    }
    if (!orderId.trim()) {
      setErrorMessage('Please specify the Order ID to which this complaint is raised.');
      return;
    }
    if (category === 'other' && !customCategory.trim()) {
      setErrorMessage('Please specify the custom category / issue rationale.');
      return;
    }
    if (!subject.trim()) {
      setErrorMessage('Please enter a ticket subject.');
      return;
    }
    if (!message.trim()) {
      setErrorMessage('Please enter the customer complaint / intake message.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const finalCategory = category === 'other' ? customCategory.trim() : category;

    try {
      const newTicket = await createTicket({
        customer_id: customerId.trim(),
        order_id: orderId.trim(),
        subject: subject.trim(),
        message: message.trim(),
        category: finalCategory,
      });

      triggerTriage(newTicket.id).catch((err) =>
        console.warn('Auto-trigger triage failed (worker will process):', err)
      );

      setSubject('');
      setMessage('');
      setCustomCategory('');
      onClose();
      onTicketCreated(newTicket.id);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : 'Failed to create ticket.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Register New Customer Ticket"
      description="Registers a new ticket into the Open Queue for immediate agent assignment and policy grounding."
      maxWidth="lg"
      footer={
        <div className="flex items-center justify-between w-full font-sans text-xs">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-[#686B78] hover:text-[#282C3F] font-medium cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-3.5 py-1.5 bg-[#FC8019] text-white rounded-lg font-semibold hover:bg-[#E26A00] active:bg-[#D45D00] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
          >
            {isSubmitting ? 'Registering...' : 'Register & Dispatch Ticket'}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-left font-sans text-xs">
        {errorMessage && (
          <div className="p-2.5 bg-[#FDF0EE] border border-[#F5A398] rounded-lg text-[#C62828] font-medium">
            {errorMessage}
          </div>
        )}

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Customer Account (CX ID) *
          </label>
          {customers.length > 0 ? (
            <div className="space-y-1.5">
              <select
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
              >
                <option value="">-- Select Customer Account --</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.email}) [ID: #{c.id.slice(0, 8)}]
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                placeholder="Or manually enter CX ID"
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] font-mono text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>
          ) : (
            <input
              type="text"
              required
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              placeholder="Enter Customer Account ID"
              className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] font-mono text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
            />
          )}
        </div>

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Order Reference ID *
          </label>
          {orders.length > 0 ? (
            <div className="space-y-1.5">
              <select
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
              >
                <option value="">-- Select Order ID --</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    Order #{o.id.slice(0, 8)} — {o.restaurant} (₹{o.total.toFixed(2)}) [{o.status}]
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
                placeholder="Or manually enter Order ID"
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] font-mono text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>
          ) : (
            <input
              type="text"
              required
              value={orderId}
              onChange={(e) => setOrderId(e.target.value)}
              placeholder="Enter Order ID"
              className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] font-mono text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
            />
          )}
        </div>

        <div className="space-y-2">
          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">
              Issue Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] transition-all cursor-pointer"
            >
              <option value="refund">Refund / Compensation Request</option>
              <option value="shipping">Delivery Status & Transit Delay</option>
              <option value="billing">Billing & Payment Issue</option>
              <option value="warranty">Food Quality & Freshness Claim</option>
              <option value="account_security">Account Security Incident</option>
              <option value="general">General Customer Support</option>
              <option value="other">Other Issue (Custom Category)</option>
            </select>
          </div>

          {category === 'other' && (
            <div>
              <label className="block font-semibold text-[#282C3F] mb-1">
                Specify Custom Category:
              </label>
              <input
                type="text"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                placeholder="e.g. In-store pickup voucher redemption..."
                autoFocus
                className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
              />
            </div>
          )}
        </div>

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Ticket Subject / Summary
          </label>
          <input
            type="text"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="Brief summary of the inquiry..."
            className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] transition-all"
          />
        </div>

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Customer Message Details
          </label>
          <textarea
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Record the exact customer statement..."
            className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019] resize-none transition-all leading-relaxed"
          />
        </div>
      </form>
    </Modal>
  );
};
