"use client";
import * as React from "react";

export default function TopbarStatus() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  const [ok, setOk] = React.useState<boolean | null>(null);
  const [csvOn, setCsvOn] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    (async () => {
      try {
        const h = await fetch(`${apiBase}/healthz`);
        setOk(h.ok);
      } catch {
        setOk(false);
      }
      try {
        const f = await fetch(`${apiBase}/v1/flags`);
        const d = await f.json();
        setCsvOn(Boolean(d?.flags?.csv_ingestion_enabled ?? true));
      } catch {
        setCsvOn(true);
      }
    })();
  }, [apiBase]);

  const color = ok == null ? "bg-gray-500" : ok ? "bg-emerald-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-3 text-xs">
      <div className="flex items-center gap-1">
        <span className={`inline-block h-2 w-2 rounded-full ${color}`}></span>
        <span className="text-[var(--muted)]">API</span>
      </div>
      {csvOn === false && (
        <span className="rounded-md bg-yellow-500/10 px-2 py-1 text-[10px] font-medium text-yellow-300">CSV off</span>
      )}
    </div>
  );
}
