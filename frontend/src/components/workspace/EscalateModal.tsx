import React, { useState } from 'react';
import { Modal } from '../common/Modal';

interface EscalateModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketId: string;
  ticketSubject: string;
  onConfirmEscalate: (reason: string, note?: string, customReason?: string) => Promise<void>;
}

export const EscalateModal: React.FC<EscalateModalProps> = ({
  isOpen,
  onClose,
  ticketId,
  ticketSubject,
  onConfirmEscalate,
}) => {
  const [selectedReason, setSelectedReason] = useState('Customer requested supervisor review');
  const [customReason, setCustomReason] = useState('');
  const [note, setNote] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const predefinedReasons = [
    'Customer requested supervisor review',
    'Complex food safety or merchant compliance dispute',
    'Suspected fraud or account compromise',
    'Financial dispute exceeding automated refund threshold',
    'Legal, regulatory or policy exception required',
    'Other reason (Specify custom rationale)',
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const isOther = selectedReason.startsWith('Other');
    if (isOther && !customReason.trim()) {
      setError('Please specify the custom escalation rationale.');
      return;
    }

    const finalReason = isOther ? customReason.trim() : selectedReason;

    setIsSubmitting(true);
    setError(null);
    try {
      await onConfirmEscalate(finalReason, note.trim() || undefined, isOther ? customReason.trim() : undefined);
      setSelectedReason(predefinedReasons[0]);
      setCustomReason('');
      setNote('');
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to escalate ticket.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Escalate Ticket to Senior Review"
      description="Transfers ticket into the Escalated Queue for supervisor intervention and logs an audit record."
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
            className="px-3.5 py-1.5 bg-[#EC3D25] text-white rounded-lg font-semibold hover:bg-[#C62828] active:bg-[#B71C1C] shadow-xs disabled:opacity-50 cursor-pointer transition-all"
          >
            {isSubmitting ? 'Escalating...' : 'Confirm Escalation'}
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

        <div className="p-3 bg-[#FDF0EE] rounded-xl border border-[#FFD7B0]">
          <span className="font-semibold text-[#EC3D25]">Ticket #{ticketId.slice(0, 8)}</span>
          <p className="text-[#282C3F] font-medium text-xs mt-0.5 truncate">{ticketSubject}</p>
        </div>

        <div className="space-y-1.5">
          <label className="block font-semibold text-[#282C3F]">
            Select Escalation Reason:
          </label>
          <div className="space-y-1.5">
            {predefinedReasons.map((r) => (
              <label
                key={r}
                className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-colors ${
                  selectedReason === r
                    ? 'bg-[#FDF0EE] border-[#EC3D25] font-semibold text-[#C62828]'
                    : 'bg-white border-[#E9E9EB] text-[#686B78] hover:bg-[#F9F9FB]'
                }`}
              >
                <input
                  type="radio"
                  name="escalationReason"
                  checked={selectedReason === r}
                  onChange={() => setSelectedReason(r)}
                  className="accent-[#EC3D25]"
                />
                <span className="text-xs">{r}</span>
              </label>
            ))}
          </div>
        </div>

        {selectedReason.startsWith('Other') && (
          <div>
            <label className="block font-semibold text-[#282C3F] mb-1">
              Specify Custom Reason:
            </label>
            <input
              type="text"
              value={customReason}
              onChange={(e) => setCustomReason(e.target.value)}
              placeholder="Provide exact details for supervisor routing..."
              autoFocus
              className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#EC3D25] focus:bg-white transition-all"
            />
          </div>
        )}

        <div>
          <label className="block font-semibold text-[#282C3F] mb-1">
            Supervisor Handover Note (Optional):
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add context for the senior agent..."
            rows={2}
            className="w-full p-2 bg-[#F9F9FB] border border-[#E9E9EB] rounded-lg text-[#282C3F] text-xs focus:outline-hidden focus:border-[#EC3D25] focus:bg-white transition-all"
          />
        </div>
      </form>
    </Modal>
  );
};
