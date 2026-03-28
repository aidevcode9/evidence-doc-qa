import React from "react";

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="flex-shrink-0"
    >
      <defs>
        <linearGradient id="logo-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--logo-from, #818cf8)" />
          <stop offset="100%" stopColor="var(--logo-to, #4f46e5)" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#logo-grad)" />
      {/* Stacked document pages */}
      <g transform="translate(7, 6)" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="2" width="12" height="16" rx="2" fill="white" fillOpacity="0.15" />
        <rect x="5" y="0" width="12" height="16" rx="2" fill="white" fillOpacity="0.3" />
        {/* Text lines */}
        <line x1="8" y1="5" x2="14" y2="5" strokeOpacity="0.9" />
        <line x1="8" y1="8" x2="14" y2="8" strokeOpacity="0.9" />
        <line x1="8" y1="11" x2="12" y2="11" strokeOpacity="0.9" />
      </g>
    </svg>
  );
}
