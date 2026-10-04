import React, { useRef, useEffect, useState } from 'react';
import type { Message } from '../../types/ticket';

interface ConversationThreadProps {
  messages: Message[];
  customerName?: string;
  streamingToken?: string;
}

interface CouponDetails {
  couponCode: string;
  value?: string;
}

export const ConversationThread: React.FC<ConversationThreadProps> = ({
  messages,
  customerName = 'Customer',
  streamingToken,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingToken]);

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
    setCopiedCode(code);
    setTimeout(() => {
      setCopiedCode((current) => (current === code ? null : current));
    }, 2000);
  };

  const extractCouponDetails = (content: string): CouponDetails | null => {
    const isCouponMentioned = content.includes('[REFUND COUPON ISSUED]') || /TRUST-REF-[A-Z0-9]+/i.test(content);
    if (!isCouponMentioned) return null;

    const match = content.match(/TRUST-REF-[A-Z0-9]+/i);
    if (!match) return null;

    const couponCode = match[0].toUpperCase();
    const valMatch = content.match(/Value:\s*(₹?[0-9,.]+)/i);
    const value = valMatch ? valMatch[1] : undefined;

    return { couponCode, value };
  };

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-white font-sans text-xs">
      {messages.length === 0 && (
        <div className="text-center py-10 text-[#93959F]">
          No messages in this conversation yet.
        </div>
      )}

      {messages.map((msg) => {
        const isCustomer = msg.sender_type === 'customer';
        const isSystem = msg.sender_type === 'system';
        const coupon = extractCouponDetails(msg.content);

        if (coupon) {
          const isCopied = copiedCode === coupon.couponCode;
          return (
            <div key={msg.id} className="flex justify-center my-3 w-full">
              <div className="w-full max-w-md bg-[#FFF9F5] border-2 border-dashed border-[#FC8019]/60 rounded-2xl p-4 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-full bg-[#FC8019] text-white flex items-center justify-center font-bold text-xs">
                      %
                    </span>
                    <span className="font-extrabold text-[#282C3F] text-xs uppercase tracking-wide">
                      Refund Voucher
                    </span>
                  </div>
                  {coupon.value && (
                    <span className="text-xs font-black text-[#2A7E15] bg-[#EBF7E9] px-2.5 py-1 rounded-full border border-[#60B246]/40">
                      {coupon.value}
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between bg-white border border-[#FFD7B0] rounded-xl p-2.5">
                  <span className="font-mono text-sm font-black text-[#FC8019] tracking-wider">
                    {coupon.couponCode}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCopyCoupon(coupon.couponCode)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs ${
                      isCopied
                        ? 'bg-[#60B246] text-white'
                        : 'bg-[#FC8019] hover:bg-[#E26A00] text-white'
                    }`}
                  >
                    {isCopied ? (
                      <>
                        <span>✓</span>
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <span>📋</span>
                        <span>Copy Coupon</span>
                      </>
                    )}
                  </button>
                </div>

                <p className="text-[11px] text-[#686B78] text-center">
                  Valid for 90 days across all partner restaurants.
                </p>
              </div>
            </div>
          );
        }

        if (isSystem) {
          return (
            <div key={msg.id} className="flex justify-center my-2">
              <div className="px-3.5 py-1.5 rounded-full bg-[#F4F5F8] border border-[#E9E9EB] text-[#686B78] text-[11px] max-w-lg text-center shadow-2xs">
                <span>{msg.content}</span>
              </div>
            </div>
          );
        }

        return (
          <div
            key={msg.id}
            className={`flex flex-col max-w-[80%] ${
              isCustomer ? 'self-start mr-auto items-start' : 'self-end ml-auto items-end'
            }`}
          >
            <div className="flex items-center gap-2 mb-1 text-[11px] text-[#686B78]">
              <span className={`font-semibold ${isCustomer ? 'text-[#282C3F]' : 'text-[#FC8019]'}`}>
                {isCustomer ? customerName : 'Support Executive'}
              </span>
              {msg.created_at && <span className="text-[#93959F] text-[10px]">{formatTime(msg.created_at)}</span>}
            </div>

            <div
              className={`p-3.5 rounded-2xl border text-xs leading-relaxed shadow-2xs ${
                isCustomer
                  ? 'bg-[#F4F5F8] text-[#282C3F] border-[#E9E9EB] rounded-tl-xs'
                  : 'bg-[#FFF9F5] text-[#282C3F] border-[#FFE6D3] rounded-tr-xs'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        );
      })}

      {streamingToken && (
        <div className="flex flex-col max-w-[80%] ml-auto items-end animate-in fade-in">
          <div className="flex items-center gap-1.5 mb-1 text-[11px] text-[#FC8019] font-semibold">
            <span className="w-2 h-2 rounded-full bg-[#FC8019] animate-pulse" />
            <span>Drafting AI response...</span>
          </div>
          <div className="p-3.5 rounded-2xl rounded-tr-xs border border-[#FC8019]/40 bg-[#FFF2E5] text-[#282C3F] text-xs leading-relaxed shadow-2xs">
            <p className="whitespace-pre-wrap">{streamingToken}</p>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
