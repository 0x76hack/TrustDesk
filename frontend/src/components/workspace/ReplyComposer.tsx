import React, { useState } from 'react';
import type { Citation } from '../../types/ticket';

interface ReplyComposerProps {
  ticketId: string;
  ticketStatus?: string;
  onSendReply: (content: string) => Promise<void>;
  onRequestAiDraft: () => Promise<void>;
  onOpenEscalateModal?: () => void;
  isStreamingDraft?: boolean;
  citations?: Citation[];
  draftText?: string;
  onDraftTextChange?: (text: string) => void;
  activeCoupon?: string | null;
}

export const ReplyComposer: React.FC<ReplyComposerProps> = ({
  ticketStatus = 'open',
  onSendReply,
  onRequestAiDraft,
  isStreamingDraft = false,
  citations = [],
  draftText = '',
  onDraftTextChange,
  activeCoupon,
}) => {
  const [localText, setLocalText] = useState(draftText);
  const [isSending, setIsSending] = useState(false);
  const [isCopiedCoupon, setIsCopiedCoupon] = useState(false);

  React.useEffect(() => {
    setLocalText(draftText);
  }, [draftText]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setLocalText(e.target.value);
    onDraftTextChange?.(e.target.value);
  };

  const handleSend = async () => {
    if (!localText.trim()) return;
    setIsSending(true);
    try {
      await onSendReply(localText.trim());
      setLocalText('');
      onDraftTextChange?.('');
    } finally {
      setIsSending(false);
    }
  };

  const handleCopyCoupon = (code: string) => {
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
    setIsCopiedCoupon(true);
    setTimeout(() => {
      setIsCopiedCoupon(false);
    }, 2000);
  };

  if (ticketStatus.toLowerCase() === 'resolved') {
    return (
      <div className="p-3.5 bg-[#EBF7E9] border-t border-[#60B246]/30 flex items-center justify-center font-sans text-xs font-semibold text-[#2A7E15]">
        ✓ This ticket has been resolved and closed. Customer chat is archived.
      </div>
    );
  }

  if (ticketStatus.toLowerCase() === 'open' || ticketStatus.toLowerCase() === 'escalated') {
    return (
      <div className="p-3.5 bg-[#FFF2E5] border-t border-[#FFD7B0] flex items-center justify-center font-sans text-xs font-semibold text-[#FC8019]">
        {ticketStatus.toLowerCase() === 'escalated'
          ? 'Ticket is currently in Escalated Queue. Claim ticket to activate composer.'
          : 'Ticket is currently in Open Queue. Claim ticket to start composing a reply.'}
      </div>
    );
  }

  return (
    <div className="p-4 bg-white border-t border-[#E9E9EB] space-y-2.5 shrink-0 font-sans text-xs shadow-2xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {citations && citations.length > 0 && (
          <div className="p-2 rounded-xl bg-[#FFF9F5] border border-[#FFD7B0] flex items-center gap-2 text-xs">
            <span className="font-semibold text-[#FC8019]">
              Policy Grounded: {citations.length} Citations
            </span>
            <div className="flex items-center gap-1.5 overflow-x-auto max-w-xs">
              {citations.map((c) => (
                <span
                  key={c.id || c.doc_id}
                  className="px-2 py-0.5 rounded-md bg-white border border-[#FFD7B0] text-[10px] text-[#FC8019] font-mono font-semibold"
                >
                  {c.doc_id}
                </span>
              ))}
            </div>
          </div>
        )}

        {activeCoupon && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-[11px] text-[#686B78] font-medium">Coupon:</span>
            <button
              type="button"
              onClick={() => handleCopyCoupon(activeCoupon)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-mono font-bold transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs border ${
                isCopiedCoupon
                  ? 'bg-[#EBF7E9] text-[#2A7E15] border-[#60B246]/40'
                  : 'bg-[#FFF2E5] hover:bg-[#FFE6D3] text-[#FC8019] border-[#FC8019]/40'
              }`}
            >
              <span>{activeCoupon}</span>
              <span className="text-[10px]">{isCopiedCoupon ? '✓ Copied' : '📋 Copy'}</span>
            </button>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-[#D4D5D9] bg-[#F4F5F8] focus-within:border-[#FC8019] focus-within:bg-white transition-all shadow-2xs overflow-hidden">
        <textarea
          rows={3}
          value={localText}
          onChange={handleChange}
          placeholder="Compose customer response, or click 'Draft with AI'..."
          className="w-full p-3 bg-transparent font-sans text-xs text-[#282C3F] placeholder-[#93959F] outline-hidden resize-none leading-relaxed"
          disabled={isSending || isStreamingDraft}
        />

        <div className="flex items-center justify-between px-3 py-2 border-t border-[#E9E9EB] bg-[#F9FAFC]">
          <div>
            <button
              type="button"
              onClick={onRequestAiDraft}
              disabled={isStreamingDraft}
              className="px-3 py-1.5 rounded-lg bg-[#282C3F] text-white text-xs font-semibold hover:bg-[#1C1C24] disabled:opacity-60 transition-colors cursor-pointer shadow-2xs"
            >
              {isStreamingDraft ? 'Generating draft...' : 'Draft with AI'}
            </button>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[11px] text-[#93959F]">
              {localText.length} characters
            </span>
            <button
              type="button"
              onClick={handleSend}
              disabled={!localText.trim() || isStreamingDraft || isSending}
              className="px-4 py-1.5 rounded-lg bg-[#FC8019] hover:bg-[#E26A00] text-white text-xs font-semibold disabled:opacity-50 transition-all cursor-pointer shadow-xs"
            >
              {isSending ? 'Sending...' : 'Send Reply'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
