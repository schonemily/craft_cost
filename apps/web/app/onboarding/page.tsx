"use client";
import Link from "next/link";
import * as React from "react";

export default function Page() {
  const steps = [
    { title: "Upload CSV", desc: "Import your bank statements.", href: "/upload" },
    { title: "Review Preview", desc: "Check parsed rows and categories.", href: "/intake-preview" },
    { title: "Explore Spend", desc: "See trends and category insights.", href: "/spend" },
    { title: "Upgrade (optional)", desc: "Unlock Plus features and suggestions.", href: "/dashboard" },
  ];
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Welcome — Get started</h1>
        <p className="text-[var(--muted)] mt-1">Follow these quick steps to set up your account.</p>
      </header>
      <ol className="space-y-3">
        {steps.map((s, i) => (
          <li key={i} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 flex items-center justify-between">
            <div>
              <div className="text-white/90 font-medium">{i + 1}. {s.title}</div>
              <div className="text-xs text-[var(--muted)] mt-1">{s.desc}</div>
            </div>
            <Link href={s.href} className="rounded-md border border-[var(--border)]/60 px-3 py-1.5 text-sm hover:bg-white/5">Open</Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
