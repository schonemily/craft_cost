"use client";
import * as React from "react";

export default function DebtPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const [debts, setDebts] = React.useState<DebtRow[]>([
    { name: "Card A", balance: 2500, apr: 19.99, min_payment: 50 },
    { name: "Card B", balance: 1200, apr: 25.99, min_payment: 35 },
  ]);
  const [extra, setExtra] = React.useState<number>(100);
  const [strategy, setStrategy] = React.useState<string>("both");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<any>(null);

  function updateDebt(i: number, field: keyof DebtRow, value: string) {
    const valNum = ["balance", "apr", "min_payment"].includes(field as string)
      ? Number(value)
      : (value as any);
    setDebts((prev) => prev.map((d, idx) => (idx === i ? { ...d, [field]: valNum } : d)));
  }

  function addRow() {
    setDebts((prev) => [...prev, { name: "", balance: 0, apr: 0, min_payment: 0 }]);
  }

  function removeRow(i: number) {
    setDebts((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const payload: any = { debts, extra };
      if (strategy !== "both") payload.strategy = strategy;
      const r = await fetch(`${apiBase}/v1/debt/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`Sim failed (${r.status})`);
      const data = await r.json();
      setResult(data);
    } catch (err: any) {
      setError(err?.message || "Failed to simulate");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-xl font-semibold text-white/90">Debt payoff simulator</h1>
        <p className="text-sm text-[var(--muted)]">Compare snowball vs avalanche with optional extra monthly payment.</p>
      </section>

      <form onSubmit={onRun} className="space-y-4">
        <div className="overflow-x-auto rounded-lg border border-[var(--border)]/60">
          <table className="w-full text-sm">
            <thead className="bg-[var(--surface)]/60">
              <tr>
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Balance</th>
                <th className="px-3 py-2 text-left">APR %</th>
                <th className="px-3 py-2 text-left">Min Payment</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {debts.map((d, i) => (
                <tr key={i} className="border-t border-[var(--border)]/60">
                  <td className="px-3 py-2">
                    <input className="w-full bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={d.name}
                      onChange={(e) => updateDebt(i, "name", e.target.value)} placeholder="e.g., Card A" />
                  </td>
                  <td className="px-3 py-2">
                    <input type="number" min="0" step="0.01" className="w-full bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={d.balance}
                      onChange={(e) => updateDebt(i, "balance", e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <input type="number" min="0" step="0.01" className="w-full bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={d.apr}
                      onChange={(e) => updateDebt(i, "apr", e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <input type="number" min="0" step="0.01" className="w-full bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={d.min_payment}
                      onChange={(e) => updateDebt(i, "min_payment", e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <button type="button" onClick={() => removeRow(i)} className="text-xs text-red-400 hover:text-red-300">Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-3">
          <button type="button" onClick={addRow} className="rounded border border-[var(--border)]/60 px-3 py-1 text-sm hover:bg-white/5">Add debt</button>
          <div className="ml-auto flex items-center gap-2 text-sm">
            <label className="text-[var(--muted)]">Extra/month</label>
            <input type="number" min="0" step="1" className="w-28 bg-transparent outline-none border border-[var(--border)]/60 rounded px-2 py-1" value={extra}
              onChange={(e) => setExtra(Number(e.target.value))} />
            <label className="ml-4 text-[var(--muted)]">Strategy</label>
            <select className="bg-transparent outline-none border border-[var(--border)]/60 rounded px-2 py-1" value={strategy}
              onChange={(e) => setStrategy(e.target.value)}>
              <option value="both">Both</option>
              <option value="snowball">Snowball</option>
              <option value="avalanche">Avalanche</option>
            </select>
            <button type="submit" disabled={loading} className="ml-4 rounded bg-brand-600/80 hover:bg-brand-600 px-3 py-1 text-sm text-white">
              {loading ? "Simulating…" : "Run"}
            </button>
          </div>
        </div>
      </form>

      {error && (
        <div className="rounded border border-red-800/60 bg-red-900/30 p-3 text-sm text-red-200">{error}</div>
      )}

      {result && (
        <section className="grid gap-4 md:grid-cols-2">
          {("snowball" in result ? ["snowball","avalanche"] : ["strategy"]).map((key, idx) => {
            const r = key === "strategy" ? result : result[key as "snowball"|"avalanche"];
            const title = key === "strategy" ? (result.strategy || "Result") : key;
            if (!r) return null;
            return (
              <article key={idx} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
                <div className="flex items-center justify-between">
                  <h2 className="font-semibold text-white/90 capitalize">{title}</h2>
                  <div className="text-right text-sm">
                    <div className="text-white/80">Months: <strong>{r.months}</strong></div>
                    <div className="text-[var(--muted)]">Interest paid: ${Number(r.interest_paid).toFixed(2)}</div>
                    <div className="text-[var(--muted)]">Total paid: ${Number(r.total_paid).toFixed(2)}</div>
                  </div>
                </div>
                <div className="mt-3 overflow-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-[var(--muted)]">
                        <th className="px-2 py-1 text-left">Debt</th>
                        <th className="px-2 py-1 text-right">Months</th>
                        <th className="px-2 py-1 text-right">Interest</th>
                        <th className="px-2 py-1 text-right">Total Paid</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.debts?.map((d: any, i2: number) => (
                        <tr key={i2} className="border-t border-[var(--border)]/60">
                          <td className="px-2 py-1">{d.name}</td>
                          <td className="px-2 py-1 text-right">{d.months}</td>
                          <td className="px-2 py-1 text-right">${Number(d.interest_paid).toFixed(2)}</td>
                          <td className="px-2 py-1 text-right">${Number(d.total_paid).toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            );
          })}
        </section>
      )}
    </div>
  );
}

type DebtRow = {
  name: string;
  balance: number;
  apr: number;
  min_payment: number;
};
