import type { Metadata } from "next";

import { Sidebar } from "@/components/app-shell/sidebar";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "RoleRadarAI",
  description: "Personal SIRI / EURES job-discovery copilot",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full">
        <Providers>
          <Sidebar />
          <main className="min-w-0 flex-1 px-6 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
