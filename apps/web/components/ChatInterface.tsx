"use client";

import React, { useState } from "react";
import { Message } from "@/types";
import { MessageBubble } from "./MessageBubble";

type ChatInterfaceProps = {
  messages: Message[];
  onAsk: (question: string) => Promise<void>;
  isAsking: boolean;
  isReady: boolean;
};

export function ChatInterface({
  messages,
  onAsk,
  isAsking,
  isReady,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isAsking) return;
    onAsk(input);
    setInput("");
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
            <svg
              className="w-16 h-16 opacity-20"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-lg font-medium">
              Upload a document to start asking questions.
            </p>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        {isAsking && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-3 border border-gray-200 flex gap-1 animate-pulse">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></span>
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-75"></span>
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-150"></span>
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="p-4 border-t border-gray-100 bg-gray-50 flex gap-3 shadow-inner"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            isReady ? "Ask about the document..." : "Upload a document first..."
          }
          disabled={!isReady || isAsking}
          className="flex-1 bg-white border border-gray-300 rounded-xl px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all disabled:bg-gray-200 disabled:cursor-not-allowed"
        />
        <button
          type="submit"
          disabled={!isReady || !input.trim() || isAsking}
          className="bg-blue-600 hover:bg-blue-700 text-white p-2.5 rounded-xl disabled:opacity-50 transition-all shadow-md active:transform active:scale-95"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 5l7 7-7 7M5 5l7 7-7 7"
            />
          </svg>
        </button>
      </form>
    </div>
  );
}
