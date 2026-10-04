import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import type { TicketDetail } from '../../types/ticket';
import { StatusBadge, CategoryPill, RiskBadge } from '../common/Badge';

interface CloseTicketModalProps {
  isOpen: boolean;
  ticket: TicketDetail;
  onClose: () => void;
  onConfirmClose: (notes: string, resolutionType: string, customResolution?: string) => Promise<void>;
}

export const CloseTicketModal: React.FC<CloseTicketModalProps> = ({
  isOpen,
  ticket,
  onClose,
  onConfirmClose,
}) => {
  const [notes, setNotes] = useState('');
  const [resolutionType, setResolutionType] = useState('inquiry_addressed');
  const [customResolution, setCustomResolution] = useState('');
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolutionTypes = [
    { value: 'inquiry_addressed', label: 'Customer Inquiry Addressed & Policy Clarified' },
    { value: 'refund_processed', label: 'Order Refund / Compensation Credit Processed' },
    { value: 'replacement_issued', label: 'Replacement Order Dispatched' },
    { value: 'fraud_mitigated', label: 'Security Threat / Fraud Intercepted & Blocked' },
    { value: 'no_action_required', label: 'Inquiry Resolved / No Further Action Required' },
    { value: 'other', label: 'Other Resolution (Specify Custom Category)' },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!notes.trim()) {
      setError('Please provide detailed resolution notes before closing ticket.');
      return;
    }
    if (resolutionType === 'other' && !customResolution.trim()) {
      setError('Please provide details for the custom resolution type.');
      return;
    }
    if (!isConfirmed) {
      setError('Please acknowledge final ticket closure checkbox.');
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await onConfirmClose(
        notes.trim(),
        resolutionType,
        resolutionType === 'other' ? customResolution.trim() : undefined
      );
      setNotes('');
      setCustomResolution('');
      setIsConfirmed(false);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to close ticket.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Resolve & Close Ticket"
      description="Sets lifecycle status to Resolved, records resolution notes, and concludes the ticket."
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
            disabled={isSubmitting || !notes.trim() || !isConfirmed}
            className="px-3.5 py-1.5 bg-[#60B246] text-white rounded-lg font-semibold hover:bg-[#4E9B36] active:bg-[#3D8028] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
          >
            {isSubmitting ? 'Resolving...' : 'Confirm & Resolve Ticket'}
          </button>
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4 text-left font-sans text-xs">
        {error && (
          <div className="p-2.5 bg-[#FDF0EE] border border-[#F5A398] rounded-lg text-[#C62828] font-medium">
            {error}
          </div>
        )}

        <div className="p-3.5 bg-[#EBF7E9] rounded-xl border border-[#BDE8B5] space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-[#2A7E15]">Ticket #{ticket.id.slice(0, 8)}</span>
            <span className="text-[#686B78] text-[11px]">
              {ticket.customer?.name || 'Customer'}
            </span>
          </div>

          <p className="font-medium text-[#282C3F] text-xs truncate">
            {ticket.subject}
          </p>

          <div className="pt-2 border-t border-[#BDE8B5] flex flex-wrap items-center gap-2">
            <StatusBadge status={ticket.status} escalationFlag={ticket.escalation_flag} />
            <CategoryPill category={ticket.category} />
            <RiskBadge risk={ticket.risk_level} />
          </div>
        </div>

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Resolution Classification:
          </label>
          <select
            value={resolutionType}
            onChange={(e) => setResolutionType(e.target.value)}
            className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#60B246] transition-all cursor-pointer"
          >
            {resolutionTypes.map((rt) => (
              <option key={rt.value} value={rt.value}>
                {rt.label}
              </option>
            ))}
          </select>
        </div>

        {resolutionType === 'other' && (
          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">
              Custom Resolution Details:
            </label>
            <input
              type="text"
              value={customResolution}
              onChange={(e) => setCustomResolution(e.target.value)}
              placeholder="e.g. Courier reassigned, meal redelivered..."
              className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#60B246] focus:bg-white transition-all"
            />
          </div>
        )}

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Resolution Notes (Mandatory):
          </label>
          <textarea
            required
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Document the investigation findings and actions taken..."
            className="w-full p-2.5 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#60B246] focus:bg-white transition-all leading-relaxed"
          />
        </div>

        <div className="p-3 bg-[#F9FAFC] border border-[#E9E9EB] rounded-xl flex items-start gap-2.5">
          <input
            type="checkbox"
            id="confirmCloseCheckbox"
            checked={isConfirmed}
            onChange={(e) => setIsConfirmed(e.target.checked)}
            className="mt-0.5 accent-[#60B246] cursor-pointer"
          />
          <label htmlFor="confirmCloseCheckbox" className="text-xs text-[#282C3F] cursor-pointer leading-relaxed">
            I confirm that this customer inquiry has been comprehensively addressed according to standard operations policies.
          </label>
        </div>
      </form>
    </Modal>
  );
};
