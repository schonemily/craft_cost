"use client";
import * as React from "react";
import { Button } from "@dea/ui";
import toast from "react-hot-toast";

export default function Page() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const [plaidEnabled, setPlaidEnabled] = React.useState<boolean>(false);

  React.useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/flags`);
        const d = await r.json();
        setPlaidEnabled(Boolean(d?.flags?.plaid_mock_enabled ?? false));
      } catch {
        setPlaidEnabled(false);
      }
    })();
  }, [apiBase]);

  return (
    <div className="mx-auto max-w-3xl min-h-[70vh] flex flex-col items-center justify-center text-center">
      <div className="mb-4 inline-flex items-center gap-2">
        <img src="/logo.svg" alt="craft_cost" className="h-5 w-5 opacity-90" />
        <span className="text-sm font-semibold text-white/80">craft_cost</span>
      </div>

      <h1 className="text-[2.25rem] leading-tight font-semibold text-white/90">Spend better. Simple financial clarity.</h1>

      <div className="mt-5 w-full">
        <div className="rounded-2xl p-[1.5px] bg-gradient-to-br from-brand-600/25 via-transparent to-white/10">
          <div className="flex items-center gap-3 rounded-2xl bg-[rgba(3,7,18,0.6)] px-4 py-3 backdrop-blur-md shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
            <span className="select-none text-lg text-white/30">⌕</span>
            <input
              className="flex-1 bg-transparent text-sm placeholder:text-[var(--muted)] outline-none"
              placeholder="Ask anything… e.g. ‘Top 5 categories in last 30 days’ (coming soon)"
            />
            <a href="/upload" className="rounded-md bg-brand-600/20 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600/30">
              Upload CSV
            </a>
            {plaidEnabled && (
              <Button
                size="sm"
                variant="primary"
                onClick={() => toast("Mock Plaid flow started (stub)")}
                className="ml-1"
              >
                Connect bank (mock)
              </Button>
            )}
          </div>
        </div>
        <div className="mt-2 text-xs text-[var(--muted)]">Tip: Toggle <code>plaid_mock_enabled</code> in <a className="underline" href="/flags">Flags</a> to see a mock connect CTA.</div>
      </div>
    </div>
  );
}
