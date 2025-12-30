"use client";

import React, { useState, useEffect, useRef } from "react";
import { Message } from "@/types";
import { MessageBubble } from "./MessageBubble";

type ChatInterfaceProps = {
  messages: Message[];
  onAsk: (question: string) => Promise<void>;
  isAsking: boolean;
  isReady: boolean;
  selectedMessageId?: string | null;
  onMessageSelect?: (message: Message) => void;
};

export function ChatInterface({
  messages,
  onAsk,
  isAsking,
  isReady,
  selectedMessageId,
  onMessageSelect,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isAsking) return;
    onAsk(input);
    setInput("");
  };

  return (
    <div className="flex-1 flex flex-col h-full relative">
      <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 scroll-smooth custom-scrollbar">
        {messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 space-y-4">
            <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                <svg
                className="w-8 h-8 opacity-40"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                >
                <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
                </svg>
            </div>
            <p className="text-sm font-display tracking-wide uppercase opacity-60">
              System Ready. Awaiting Documents.
            </p>
          </div>
        )}
        {messages.map((m) => (
          <MessageBubble 
            key={m.id} 
            message={m} 
            isSelected={m.id === selectedMessageId}
            onClick={m.role === "assistant" ? () => onMessageSelect?.(m) : undefined}
          />
        ))}
        {isAsking && (
          <div className="flex justify-start mb-6">
            <div className="bg-zinc-900 rounded-2xl px-5 py-4 border border-white/5 flex gap-1.5 items-center">
              <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-pulse"></span>
              <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-pulse delay-150"></span>
              <span className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-pulse delay-300"></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 sm:p-8 pt-2">
        <form
            onSubmit={handleSubmit}
            className="relative flex items-center group"
        >
            <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
                isReady ? "Ask a question..." : "Upload a document to begin..."
            }
            disabled={!isReady || isAsking}
            className="w-full bg-zinc-900/50 border border-white/10 rounded-xl px-5 py-4 pr-14 focus:ring-1 focus:ring-blue-500 focus:border-blue-500/50 outline-none transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm text-gray-200 placeholder-gray-600 shadow-lg backdrop-blur-sm"
            />
            <button
            type="submit"
            disabled={!isReady || !input.trim() || isAsking}
            className="absolute right-2 p-2 bg-white/10 hover:bg-white/20 text-white rounded-lg disabled:opacity-0 transition-all"
            >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 12h14M12 5l7 7-7 7"
                />
            </svg>
            </button>
        </form>
      </div>
    </div>
  );
}
