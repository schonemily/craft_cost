"use client";
import * as React from "react";
import { useSession } from "next-auth/react";
import toast from "react-hot-toast";

export default function Page() {
  const { data: session } = useSession();
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const [loading, setLoading] = React.useState(false);
  const [tickets, setTickets] = React.useState<Array<{ id: string; merchant: string; status: string; estSave?: string }>>([]);
  const [merchant, setMerchant] = React.useState("");
  const [account, setAccount] = React.useState("");

  const fetchTickets = React.useCallback(async () => {
    if (!(session as any)?.apiToken) return;
    setLoading(true);
    try {
      const r = await fetch(`${apiBase}/v1/negotiations`, { headers: { Authorization: `Bearer ${(session as any).apiToken}` } });
      if (r.ok) {
        const d = await r.json();
        setTickets(d?.items || []);
      }
    } catch {}
    finally { setLoading(false); }
  }, [apiBase, session]);

  React.useEffect(() => { fetchTickets(); }, [fetchTickets]);

  const startTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!merchant) return toast.error("Merchant required");
    try {
      const r = await fetch(`${apiBase}/v1/negotiations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${(session as any).apiToken}` },
        body: JSON.stringify({ merchant, account }),
      });
      if (r.ok) {
        setMerchant(""); setAccount("");
        await fetchTickets();
        toast.success("Negotiation started");
      } else {
        toast.error("Failed to start");
      }
    } catch {
      toast.error("Failed to start");
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Bill negotiations</h1>
        <p className="text-[var(--muted)] mt-1">Start and track negotiations. Transparent, capped fees.</p>
      </header>

      <section className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
        <h2 className="text-sm font-medium text-white/90">Start a negotiation</h2>
        <form onSubmit={startTicket} className="mt-2 grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
          <input value={merchant} onChange={(e) => setMerchant(e.target.value)} placeholder="Merchant (e.g., Comcast)" className="rounded-md bg-black/20 border border-[var(--border)]/60 px-3 py-2 outline-none" />
          <input value={account} onChange={(e) => setAccount(e.target.value)} placeholder="Account # (optional)" className="rounded-md bg-black/20 border border-[var(--border)]/60 px-3 py-2 outline-none" />
          <div className="md:col-span-1">
            <button type="submit" className="w-full rounded-md bg-brand-600/90 hover:bg-brand-600 px-3 py-2 text-white">Start</button>
          </div>
        </form>
      </section>

      <section className="space-y-3">
        <div className="text-sm text-[var(--muted)]">{loading ? "Loading..." : `${tickets.length} ticket(s)`}</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {tickets.map((t) => (
            <div key={t.id} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
              <div className="flex items-center justify-between">
                <div className="text-white/90 font-medium">{t.merchant}</div>
                <span className="text-xs text-[var(--muted)]">{t.status}</span>
              </div>
              {t.estSave && <div className="text-xs text-[var(--muted)] mt-1">Est. savings {t.estSave}</div>}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
