"use client";
import * as React from "react";
import { useSession } from "next-auth/react";
import toast from "react-hot-toast";

export default function Page() {
  const { data: session } = useSession();
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const [loading, setLoading] = React.useState(false);
  const [items, setItems] = React.useState<Array<any>>([]);
  const [deletingId, setDeletingId] = React.useState<string | null>(null);

  React.useEffect(() => {
    (async () => {
      if (!(session as any)?.apiToken) return;
      setLoading(true);
      try {
        const r = await fetch(`${apiBase}/v1/subscriptions`, { headers: { Authorization: `Bearer ${(session as any).apiToken}` } });
        if (r.ok) {
          const d = await r.json();
          setItems(d?.items || []);
        }
      } catch {}
      finally { setLoading(false); }
    })();
  }, [apiBase, session]);

  const [mName, setMName] = React.useState("");
  const [mAmount, setMAmount] = React.useState("");
  const [mCadence, setMCadence] = React.useState("monthly");

  const addManual = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mName || !mAmount) return toast.error("Name and amount required");
    try {
      const r = await fetch(`${apiBase}/v1/subscriptions/manual`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${(session as any).apiToken}` },
        body: JSON.stringify({ title: mName, amount: Number(mAmount), cadence: mCadence }),
      });
      if (r.ok) {
        const d = await r.json();
        setItems((prev) => [d.item, ...prev]);
        setMName(""); setMAmount(""); setMCadence("monthly");
        toast.success("Saved");
      } else {
        toast.error("Failed to save");
      }
    } catch {
      toast.error("Failed to save");
    }
  };

  const deleteManual = async (id: string) => {
    if (!id.startsWith("manual:")) return;
    setDeletingId(id);
    try {
      const r = await fetch(`${apiBase}/v1/subscriptions/manual/${encodeURIComponent(id)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${(session as any).apiToken}` },
      });
      if (r.ok) {
        setItems((prev) => prev.filter((x) => String(x.id) !== id));
        toast.success("Deleted");
      } else {
        toast.error("Failed to delete");
      }
    } catch {
      toast.error("Failed to delete");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Subscriptions</h1>
        <p className="text-[var(--muted)] mt-1">Detected recurring charges and manual entries.</p>
      </header>

      <section className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
        <h2 className="text-sm font-medium text-white/90">Add manual subscription</h2>
        <form onSubmit={addManual} className="mt-2 grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
          <input value={mName} onChange={(e) => setMName(e.target.value)} placeholder="Name (e.g., Gym)" className="rounded-md bg-black/20 border border-[var(--border)]/60 px-3 py-2 outline-none" />
          <input value={mAmount} onChange={(e) => setMAmount(e.target.value)} placeholder="Amount (e.g., 12.99)" className="rounded-md bg-black/20 border border-[var(--border)]/60 px-3 py-2 outline-none" />
          <select value={mCadence} onChange={(e) => setMCadence(e.target.value)} className="rounded-md bg-black/20 border border-[var(--border)]/60 px-3 py-2 outline-none">
            <option value="monthly">Monthly</option>
            <option value="annual">Annual</option>
          </select>
          <button type="submit" className="rounded-md bg-brand-600/90 hover:bg-brand-600 px-3 py-2 text-white">Save</button>
        </form>
      </section>

      <section className="space-y-3">
        <div className="text-sm text-[var(--muted)]">{loading ? "Loading..." : `${items.length} item(s)`}</div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((s, i) => (
            <div key={i} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-white/90 font-medium">{s.title}</div>
                  <div className="text-xs text-[var(--muted)] mt-1">{s.summary}</div>
                </div>
                {String(s?.id || "").startsWith("manual:") && (
                  <button
                    aria-label="Delete"
                    title="Delete"
                    onClick={() => deleteManual(String(s.id))}
                    disabled={deletingId === String(s.id)}
                    className="rounded-md border border-[var(--border)]/60 p-2 text-[var(--muted)] hover:text-red-400 hover:border-red-400/60 disabled:opacity-50"
                  >
                    {/* trash can icon */}
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                      <path d="M9 3h6a1 1 0 0 1 1 1v1h4v2H4V5h4V4a1 1 0 0 1 1-1Zm1 6h2v9h-2V9Zm4 0h2v9h-2V9Zm-8 0h2v9H6V9Z" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
