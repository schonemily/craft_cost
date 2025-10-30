"use client";
import Link from "next/link";
import toast from "react-hot-toast";

export default function Page() {
  const connect = () => {
    toast("Bank connect coming soon — using CSV for now");
  };
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Connect accounts</h1>
        <p className="text-[var(--muted)] mt-1">Plaid/MX OAuth will enable live sync. Until then, you can upload CSVs.</p>
      </header>
      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5 flex items-center justify-between">
        <div>
          <div className="text-white/90 font-medium">Bank connection (stub)</div>
          <div className="text-xs text-[var(--muted)] mt-1">Secure OAuth flow to be enabled.</div>
        </div>
        <button onClick={connect} className="rounded-md bg-brand-600/90 hover:bg-brand-600 px-4 py-2 text-sm text-white">Connect bank</button>
      </div>
      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5">
        <div className="text-sm text-[var(--muted)]">Prefer manual?</div>
        <Link href="/upload" className="mt-2 inline-block rounded-md border border-[var(--border)]/60 px-3 py-1.5 text-sm hover:bg-white/5">Upload CSV</Link>
      </div>
    </div>
  );
}
