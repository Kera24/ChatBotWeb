import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DashboardShell } from "../components/dashboard-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Conversa AI Platform",
  description: "Client dashboard foundation for ChatBotWeb / Conversa AI Platform.",
  openGraph: {
    title: "Conversa AI Platform",
    description: "Client dashboard foundation for ChatBotWeb / Conversa AI Platform.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <DashboardShell>{children}</DashboardShell>
      </body>
    </html>
  );
}
