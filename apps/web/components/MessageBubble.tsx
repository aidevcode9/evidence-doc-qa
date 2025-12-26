import React from "react";
import { Message } from "@/types";
import { CitationCard } from "./CitationCard";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? "bg-blue-600 text-white"
            : "bg-gray-100 text-gray-800 border border-gray-200"
        }`}
      >
        <div className="text-sm sm:text-base whitespace-pre-wrap">{message.text}</div>

        {message.refusal_code && (
          <div className="mt-3 p-3 bg-red-50 border border-red-100 rounded-xl flex items-start gap-3">
            <div className="mt-0.5 text-red-500">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <p className="text-[10px] font-bold text-red-800 uppercase tracking-tight leading-none mb-1">
                Refusal: {message.refusal_code.replace(/_/g, " ")}
              </p>
              <p className="text-[11px] text-red-600 font-medium">
                The system refused to answer based on safety or confidence policies.
              </p>
            </div>
          </div>
        )}

        {message.citations && message.citations.length > 0 && (
          <div className="mt-4 pt-4 border-t border-gray-200 space-y-3">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wider">
              Evidence
            </p>
            {message.citations.map((c, idx) => (
              <CitationCard key={idx} citation={c} />
            ))}
          </div>
        )}

        {message.request_id && (
          <div className="mt-2 text-[10px] text-gray-400 font-mono">
            REQ-ID: {message.request_id}
          </div>
        )}
      </div>
    </div>
  );
}
