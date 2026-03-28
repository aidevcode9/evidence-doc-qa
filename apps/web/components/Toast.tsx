"use client";

import { useEffect, useState } from "react";

type ToastVariant = "info" | "warning" | "error";

type ToastProps = {
  message: string;
  variant?: ToastVariant;
  duration?: number;
  onClose: () => void;
};

const variantStyles: Record<ToastVariant, { bg: string; border: string; text: string; icon: string }> = {
  info: {
    bg: "bg-primary/10",
    border: "border-primary/20",
    text: "text-primary",
    icon: "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
  warning: {
    bg: "bg-warning/10",
    border: "border-warning/20",
    text: "text-warning",
    icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z",
  },
  error: {
    bg: "bg-destructive/10",
    border: "border-destructive/20",
    text: "text-destructive",
    icon: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z",
  },
};

export function Toast({ message, variant = "info", duration = 4000, onClose }: ToastProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onClose, 300);
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onClose]);

  const s = variantStyles[variant];

  return (
    <div
      className={`
        fixed top-20 right-6 z-50 flex items-center gap-3
        ${s.bg} ${s.border} border rounded-lg px-4 py-3 shadow-lg backdrop-blur-md
        transition-all duration-300 ease-out
        ${visible ? "opacity-100 translate-x-0" : "opacity-0 translate-x-4"}
      `}
    >
      <svg className={`w-4 h-4 ${s.text} flex-shrink-0`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={s.icon} />
      </svg>
      <span className={`text-sm ${s.text}`}>{message}</span>
      <button
        onClick={() => { setVisible(false); setTimeout(onClose, 300); }}
        className="text-muted-foreground hover:text-foreground ml-2"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
