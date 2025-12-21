import type { ReactNode } from "react";

export const metadata = {
  title: "DocQ&A Demo",
  description: "Evidence-bound document Q&A demo"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
