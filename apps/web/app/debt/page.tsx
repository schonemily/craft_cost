"use client";
import * as React from "react";
import toast from "react-hot-toast";
import { useSession } from "next-auth/react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";

export default function DebtPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const { data: session } = useSession();
  const apiToken = (session as any)?.apiToken as string | undefined;
  const signedIn = Boolean(session);
  const [debts, setDebts] = React.useState<DebtRow[]>([
    { name: "Card A", balance: 2500, apr: 19.99, min_payment: 50 },
    { name: "Card B", balance: 1200, apr: 25.99, min_payment: 35 },
  ]);
  const [extra, setExtra] = React.useState<number>(100);
  const [strategy, setStrategy] = React.useState<string>("both");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<any>(null);
  const [includeSchedule, setIncludeSchedule] = React.useState<boolean>(true);
  const [extraSchedule, setExtraSchedule] = React.useState<ExtraRow[]>([]);
  const [email, setEmail] = React.useState<string>("");
  const [pro, setPro] = React.useState<boolean>(false);

  function updateDebt(i: number, field: keyof DebtRow, value: string) {
    const valNum = ["balance", "apr", "min_payment", "promo_apr", "promo_months"].includes(field as string)
      ? Number(value)
      : (value as any);
    setDebts((prev) => prev.map((d, idx) => (idx === i ? { ...d, [field]: valNum } : d)));
  }

  async function onDownloadPdf() {
    try {
      if (!signedIn) {
        toast.error("Please sign in to download PDF");
        return;
      }
      const payload: any = { debts, extra, include_schedule: true, extra_schedule: extraSchedule, format: "pdf", strategy: strategy === "both" ? undefined : strategy };
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiToken) headers["Authorization"] = `Bearer ${apiToken}`;
      const r = await fetch(`${apiBase}/v1/debt/export`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error(`Export failed (${r.status})`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "debt-plan.pdf";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Downloaded PDF");
    } catch (e: any) {
      toast.error(e?.message || "Failed to export PDF");
    }
  }

  async function onEmailPlan() {
    try {
      if (!signedIn) {
        toast.error("Please sign in to email your plan");
        return;
      }
      const payload: any = { debts, extra, include_schedule: true, extra_schedule: extraSchedule, format: "email", email, strategy: strategy === "both" ? undefined : strategy };
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiToken) headers["Authorization"] = `Bearer ${apiToken}`;
      const r = await fetch(`${apiBase}/v1/debt/export`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
      if (r.status === 402) {
        toast.error("Email export is a Pro feature. Upgrade to enable.");
        return;
      }
      if (!r.ok) throw new Error(`Email failed (${r.status})`);
      toast.success("Email sent (MailHog in dev)");
    } catch (e: any) {
      toast.error(e?.message || "Failed to email plan");
    }
  }

  function addRow() {
    setDebts((prev) => [...prev, { name: "", balance: 0, apr: 0, min_payment: 0, promo_apr: 0, promo_months: 0 }]);
  }

  function removeRow(i: number) {
    setDebts((prev) => prev.filter((_, idx) => idx !== i));
  }

  function addExtraRow() {
    setExtraSchedule((prev) => [...prev, { month: 1, amount: 100 }]);
  }

  function updateExtra(i: number, field: keyof ExtraRow, value: string) {
    const v = Number(value);
    setExtraSchedule((prev) => prev.map((r, idx) => (idx === i ? { ...r, [field]: v } : r)));
  }

  function removeExtra(i: number) {
    setExtraSchedule((prev) => prev.filter((_, idx) => idx !== i));
  }

  React.useEffect(() => {
    (async () => {
      try {
        const headers: Record<string, string> = {};
        if (apiToken) headers["Authorization"] = `Bearer ${apiToken}`;
        const r = await fetch(`${apiBase}/v1/flags`, { headers });
        const data = await r.json();
        setPro(Boolean(data?.flags?.pro_enabled));
      } catch {}
    })();
  }, [apiBase, apiToken]);

  async function onRun(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      if (!signedIn) {
        setLoading(false);
        toast.error("Please sign in to run simulations");
        return;
      }
      const payload: any = { debts, extra, include_schedule: includeSchedule, extra_schedule: extraSchedule };
      if (strategy !== "both") payload.strategy = strategy;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (apiToken) headers["Authorization"] = `Bearer ${apiToken}`;
      const r = await fetch(`${apiBase}/v1/debt/simulate`, {
        method: "POST",
        headers,
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
                <th className="px-3 py-2 text-left">Promo APR %</th>
                <th className="px-3 py-2 text-left">Promo Months</th>
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
                    <input type="number" min="0" step="0.01" className="w-full bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={d.promo_apr ?? 0}
                      onChange={(e) => updateDebt(i, "promo_apr", e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <input type="number" min="0" step="1" className="w-full bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={d.promo_months ?? 0}
                      onChange={(e) => updateDebt(i, "promo_months", e.target.value)} />
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
            <label className="ml-4 inline-flex items-center gap-2 text-[var(--muted)]">
              <input type="checkbox" className="accent-[var(--brand)]" checked={includeSchedule} onChange={(e) => setIncludeSchedule(e.target.checked)} />
              Include schedule (charts)
            </label>
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

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button type="button" onClick={onDownloadPdf} className="rounded border border-[var(--border)]/60 px-3 py-1 hover:bg-white/5">Download PDF</button>
        <div className="flex items-center gap-2">
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" className="w-56 bg-transparent outline-none border border-[var(--border)]/60 rounded px-2 py-1" />
          <button type="button" onClick={onEmailPlan} className="rounded border border-[var(--border)]/60 px-3 py-1 hover:bg-white/5">
            Email plan{!pro ? " (Pro)" : ""}
          </button>
        </div>
      </div>

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
                {includeSchedule && r.monthly && r.monthly.some((m: any) => (m.principal ?? 0) <= 0) && (
                  <div className="mt-3 rounded border border-yellow-800/60 bg-yellow-900/30 p-3 text-sm text-yellow-200">
                    Warning: One or more months pay little to no principal. Consider increasing your payment or scheduling extra payments to avoid negative amortization.
                  </div>
                )}
                {includeSchedule && r.monthly && (
                  <div className="mt-4 grid gap-4 md:grid-cols-2">
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={(r.monthly as any[])?.map((m: any) => ({ m: m.month, bal: m.balance }))}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                          <XAxis dataKey="m" stroke="rgba(255,255,255,0.5)" />
                          <YAxis stroke="rgba(255,255,255,0.5)" />
                          <Tooltip />
                          <Legend />
                          <Line type="monotone" dataKey="bal" name="Balance" stroke="#60a5fa" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="h-64 w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={(r.monthly as any[])?.map((m: any) => ({ m: m.month, principal: m.principal, interest: m.interest }))}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                          <XAxis dataKey="m" stroke="rgba(255,255,255,0.5)" />
                          <YAxis stroke="rgba(255,255,255,0.5)" />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="principal" stackId="a" fill="#34d399" name="Principal" />
                          <Bar dataKey="interest" stackId="a" fill="#f472b6" name="Interest" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}
                {includeSchedule && r.monthly && (
                  <div className="mt-3 flex items-center gap-3">
                    <button type="button" onClick={() => exportCsv(r, title)} className="rounded border border-[var(--border)]/60 px-3 py-1 text-sm hover:bg-white/5">Export CSV</button>
                    <span className="text-xs text-[var(--muted)]">Assumptions: monthly accrual; payments end-of-month; issuer minimum approximated as max(floor, percent of balance). Charts shown only when schedule is included.</span>
                  </div>
                )}
              </article>
            );
          })}
        </section>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-white/80">Extra payments (optional)</h2>
        <div className="overflow-x-auto rounded border border-[var(--border)]/60">
          <table className="w-full text-sm">
            <thead className="bg-[var(--surface)]/60">
              <tr>
                <th className="px-3 py-2 text-left">Month</th>
                <th className="px-3 py-2 text-left">Amount</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {extraSchedule.map((row, i) => (
                <tr key={i} className="border-t border-[var(--border)]/60">
                  <td className="px-3 py-2">
                    <input type="number" min="1" step="1" className="w-28 bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={row.month}
                      onChange={(e) => updateExtra(i, "month", e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <input type="number" min="1" step="1" className="w-28 bg-transparent outline-none border border-transparent focus:border-[var(--border)]/60 rounded px-2 py-1" value={row.amount}
                      onChange={(e) => updateExtra(i, "amount", e.target.value)} />
                  </td>
                  <td className="px-3 py-2">
                    <button type="button" onClick={() => removeExtra(i)} className="text-xs text-red-400 hover:text-red-300">Remove</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" onClick={addExtraRow} className="rounded border border-[var(--border)]/60 px-3 py-1 text-sm hover:bg-white/5">Add extra payment</button>
      </section>
    </div>
  );
}

type DebtRow = {
  name: string;
  balance: number;
  apr: number;
  min_payment: number;
  promo_apr?: number;
  promo_months?: number;
};

type ExtraRow = {
  month: number;
  amount: number;
};

function exportCsv(r: any, title: string) {
  const rows = [
    ["month", "balance", "interest", "principal"],
    ...((r.monthly || []) as any[]).map((m: any) => [m.month, m.balance, m.interest, m.principal])
  ];
  const csv = rows.map((row) => row.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `debt_schedule_${title}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
