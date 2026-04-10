import { ReactNode } from "react";
import Navbar from "./Navbar";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f7f8f5] text-[#2b2b2b]">
      <Navbar />
      <main className="mx-auto max-w-7xl px-6 py-10">{children}</main>
    </div>
  );
}