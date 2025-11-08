"use client";
import Link from "next/link";
import toast from "react-hot-toast";
import * as React from "react";
import { loadStripe } from "@stripe/stripe-js";
import { useSession } from "next-auth/react";

export default function Page() {
  const { data: session } = useSession();
  const apiToken = (session as any)?.apiToken as string | undefined;
  const [loading, setLoading] = React.useState(false);
  const [accounts, setAccounts] = React.useState<any[]>([]);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";

  async function loadAccounts() {
    try {
      const r = await fetch(`${apiBase}/v1/finconn/accounts`, {
        headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : undefined,
      });
      const d = await r.json();
      setAccounts(Array.isArray(d?.items) ? d.items : []);
    } catch {}
  }

  React.useEffect(() => {
    loadAccounts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiToken]);

  const connect = async () => {
    try {
      setLoading(true);
      const r = await fetch(`${apiBase}/v1/finconn/session`, {
        method: "POST",
        headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : undefined,
      });
      if (!r.ok) throw new Error(`Failed to create session (${r.status})`);
      const d = await r.json();
      const clientSecret = d?.client_secret as string | undefined;
      if (!clientSecret) throw new Error("Missing client secret");
      const stripe = await loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "");
      if (!stripe) throw new Error("Stripe failed to load");
      // @ts-ignore
      const result = await stripe.collectFinancialConnectionsAccounts({ client_secret: clientSecret });
      if ((result as any)?.error) {
        throw new Error((result as any).error?.message || "Connection failed");
      }
      const sessId = (result as any)?.financial_connections_session?.id as string | undefined;
      const save = await fetch(`${apiBase}/v1/finconn/accounts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
        },
        body: JSON.stringify({ session_id: sessId }),
      });
      if (!save.ok) throw new Error("Failed to save accounts");
      toast.success("Bank connected");
      loadAccounts();
    } catch (e: any) {
      toast.error(e?.message || "Connection failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Connect accounts</h1>
        <p className="text-[var(--muted)] mt-1">Securely connect your bank via Stripe Financial Connections or upload CSVs.</p>
      </header>
      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5 flex items-center justify-between">
        <div>
          <div className="text-white/90 font-medium">Bank connection</div>
          <div className="text-xs text-[var(--muted)] mt-1">We never see your credentials. You can disconnect anytime.</div>
        </div>
        <button onClick={connect} disabled={loading} className="rounded-md bg-brand-600/90 hover:bg-brand-600 px-4 py-2 text-sm text-white disabled:opacity-60">
          {loading ? "Connecting…" : "Connect bank"}
        </button>
      </div>
      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5">
        <div className="text-sm font-medium text-white/90 mb-2">Connected accounts</div>
        {accounts.length === 0 ? (
          <div className="text-sm text-[var(--muted)]">None yet.</div>
        ) : (
          <div className="text-sm text-[var(--muted)] space-y-2">
            {accounts.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded-md border border-[var(--border)]/60 px-3 py-2">
                <div className="text-white/90">{a.institution_name || a.display_name || a.id}</div>
                <div className="text-xs">{a.category}{a.subcategory ? ` • ${a.subcategory}` : ""}{a.last4 ? ` • ••••${a.last4}` : ""}</div>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5">
        <div className="text-sm text-[var(--muted)]">Prefer manual?</div>
        <Link href="/upload" className="mt-2 inline-block rounded-md border border-[var(--border)]/60 px-3 py-1.5 text-sm hover:bg-white/5">Upload CSV</Link>
      </div>
    </div>
  );
}
