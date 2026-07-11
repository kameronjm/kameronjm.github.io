import type { Metadata } from "next";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Solved Sports — Analytics Dashboard",
  description: "Sports analytics, ML models, and +EV betting engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <Sidebar />
        <main className="ml-64 min-h-screen">
          <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
        </main>
      </body>
    </html>
  );
}
