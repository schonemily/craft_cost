"use client";
import * as React from "react";

export default function TopbarStatus() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const [ok, setOk] = React.useState<boolean | null>(null);
  const [csvOn, setCsvOn] = React.useState<boolean | null>(null);

  React.useEffect(() => {
    let mounted = true;
    let timer: any;
    const controller = new AbortController();
    const fetchMeta = async () => {
      try {
        const r = await fetch(`${apiBase}/v1/meta`, { signal: controller.signal });
        if (!mounted) return;
        if (!r.ok) {
          setOk(false);
          return;
        }
        const d = await r.json().catch(() => ({}));
        setOk(true);
        setCsvOn(Boolean(d?.flags?.csv_ingestion_enabled ?? true));
      } catch {
        if (!mounted) return;
        setOk(false);
      }
    };
    fetchMeta();
    timer = setInterval(fetchMeta, 60000); // poll every 60s
    return () => {
      mounted = false;
      clearInterval(timer);
      controller.abort();
    };
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
