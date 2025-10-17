"use client";
import * as React from "react";
import { Button } from "@dea/ui";

type Flags = Record<string, boolean>;

export default function FlagsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const [flags, setFlags] = React.useState<Flags>({});
  const [newKey, setNewKey] = React.useState("");
  const [newVal, setNewVal] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function load() {
    try {
      const res = await fetch(`${apiBase}/v1/flags`);
      const data = await res.json();
      setFlags(data.flags || {});
    } catch (e: any) {
      setError(String(e));
    }
  }

  React.useEffect(() => { load(); /* eslint-disable-line */ }, []);

  async function setFlag(key: string, value: boolean) {
    setBusy(true);
    setError(null);
    try {
      await fetch(`${apiBase}/v1/flags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value })
      });
      setFlags(prev => ({ ...prev, [key]: value }));
    } catch (e: any) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-white/90">Feature Flags</h1>
        <p className="text-sm text-[var(--muted)]">Toggle features safely. These values persist in the database.</p>
      </header>

      <section className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
        <div className="text-sm font-semibold text-white/90 mb-2">Flags</div>
        <div className="divide-y divide-[var(--border)]/60">
          {Object.keys(flags).length === 0 && (
            <div className="py-2 text-sm text-[var(--muted)]">No flags yet.</div>
          )}
          {Object.entries(flags).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between py-2 text-sm">
              <span className="text-white/90">{k}</span>
              <button
                onClick={() => setFlag(k, !v)}
                disabled={busy}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${v ? 'bg-brand-600' : 'bg-gray-600/50'} disabled:opacity-50`}
                aria-pressed={v}
              >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${v ? 'translate-x-5' : 'translate-x-1'}`} />
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 space-y-3">
        <div className="text-sm font-semibold text-white/90">Add Flag</div>
        <div className="flex items-center gap-2">
          <input
            value={newKey}
            onChange={e => setNewKey(e.target.value)}
            placeholder="flag_key"
            className="flex-1 rounded-md bg-black/20 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-600/50"
          />
          <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <input type="checkbox" checked={newVal} onChange={e => setNewVal(e.target.checked)} />
            Enabled
          </label>
          <Button onClick={() => newKey.trim() && setFlag(newKey.trim(), newVal)} disabled={busy || !newKey.trim()}>
            Save
          </Button>
        </div>
        {error && <div className="text-sm text-red-400">Error: {error}</div>}
      </section>
    </div>
  );
}
