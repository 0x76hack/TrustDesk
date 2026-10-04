import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { issueTicketRefund } from '../../api/tickets';

interface IssueRefundModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  orderTotal?: number | null;
  onSuccess: (couponCode: string, amount: number) => void;
}

export const IssueRefundModal: React.FC<IssueRefundModalProps> = ({
  isOpen,
  onClose,
  ticketId,
  orderTotal,
  onSuccess,
}) => {
  const [amount, setAmount] = useState<string>('');
  const [reason, setReason] = useState<string>('Damaged or spilled food items');
  const [customReason, setCustomReason] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setAmount(orderTotal ? orderTotal.toFixed(2) : '');
      setReason('Damaged or spilled food items');
      setCustomReason('');
      setError(null);
    }
  }, [isOpen, orderTotal]);

  const reasons = [
    'Damaged or spilled food items',
    'Missing dishes or items from order',
    'Severe delivery transit delay',
    'Food quality or hygiene discrepancy',
    'Other reason (Specify custom rationale)',
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const parsedAmount = parseFloat(amount);
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Please enter a valid refund amount greater than ₹0.');
      return;
    }

    if (orderTotal && parsedAmount > orderTotal) {
      setError(`Refund amount cannot exceed order total of ₹${orderTotal.toFixed(2)}.`);
      return;
    }

    const isOther = reason.startsWith('Other');
    if (isOther && !customReason.trim()) {
      setError('Please describe the custom refund reason.');
      return;
    }

    const finalReason = isOther ? customReason.trim() : reason;

    setIsSubmitting(true);
    try {
      const res = await issueTicketRefund(ticketId, parsedAmount, finalReason);
      onSuccess(res.coupon_code, parsedAmount);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to issue refund coupon.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Issue Refund Coupon"
      description="Authorize and generate a verified refund coupon for the customer."
      footer={
        <div className="flex items-center justify-end gap-2 w-full font-sans text-xs">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 text-xs font-semibold text-[#686B78] hover:text-[#282C3F] rounded-xl hover:bg-[#F2F2F6] transition-all cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="px-4 py-2 bg-[#FC8019] text-white rounded-xl text-xs font-semibold hover:bg-[#E26A00] shadow-xs disabled:opacity-50 transition-all cursor-pointer"
          >
            {isSubmitting ? 'Generating Coupon...' : 'Authorize & Issue Coupon'}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 font-sans text-xs">
        {error && (
          <div className="p-3 bg-[#FDF0EE] border border-[#F5A398] rounded-xl text-xs text-[#C62828] font-medium">
            {error}
          </div>
        )}

        {orderTotal != null && (
          <div className="p-3 bg-[#FFF9F5] border border-[#FFD7B0] rounded-xl flex items-center justify-between text-xs">
            <span className="text-[#686B78]">Linked Order Value:</span>
            <span className="font-bold font-mono text-[#282C3F]">₹{orderTotal.toFixed(2)}</span>
          </div>
        )}

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Refund Amount (₹) *
          </label>
          <input
            type="number"
            step="0.01"
            min="1"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] font-mono text-sm focus:outline-hidden focus:border-[#FC8019]"
          />
        </div>

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Refund Rationale *
          </label>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019]"
          >
            {reasons.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>

        {reason.startsWith('Other') && (
          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">
              Custom Rationale Details *
            </label>
            <textarea
              rows={2}
              required
              value={customReason}
              onChange={(e) => setCustomReason(e.target.value)}
              placeholder="Describe the reason for approving this refund..."
              className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-xl text-[#282C3F] text-xs focus:outline-hidden focus:border-[#FC8019]"
            />
          </div>
        )}

        <div className="p-3 bg-[#F4F5F8] rounded-xl text-[11px] text-[#686B78] space-y-1">
          <p className="font-medium text-[#282C3F]">Verification Rule:</p>
          <p>
            The generated coupon will be bound strictly to this ticket and order. Only one refund coupon may be issued per order.
          </p>
        </div>
      </form>
    </Modal>
  );
};
