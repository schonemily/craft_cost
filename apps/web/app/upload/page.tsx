"use client";
import * as React from "react";
import toast from "react-hot-toast";
import { Button } from "@dea/ui";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";

export default function UploadPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const apiToken = (session as any)?.apiToken as string | undefined;
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [status, setStatus] = React.useState<any>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [polling, setPolling] = React.useState(false);
  const pollRef = React.useRef<number | null>(null);
  const [ingestionEnabled, setIngestionEnabled] = React.useState(true);
  const [flagsLoaded, setFlagsLoaded] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [detecting, setDetecting] = React.useState(false);
  const [detectRes, setDetectRes] = React.useState<any>(null);
  const fileRef = React.useRef<HTMLInputElement | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";

  // Delete dataset control removed (API endpoint removed)

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setJobId(null);
    setStatus(null);
    const input = fileRef.current;
    if (!input || !input.files || input.files.length === 0) {
      setError("Please choose a CSV or XLSX file");
      return;
    }
    const fd = new FormData();
    fd.append("file", input.files[0]);
    setUploading(true);
    try {
      // Use unified ingest endpoint (CSV or XLSX)
      const res = await fetch(`${apiBase}/v1/statements/ingest`, {
        method: "POST",
        headers: apiToken ? { Authorization: `Bearer ${apiToken}` } : undefined,
        body: fd,
      });
      if (!res.ok) {
        throw new Error(`Upload failed (${res.status})`);
      }
      const data = await res.json();
      setJobId(data.job_id ?? null);
      toast.success("Upload started. Tracking job…");
    } catch (err: any) {
      const msg = err?.message || "Upload failed";
      setError(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }
  
  function clearFile() {
    if (fileRef.current) fileRef.current.value = "";
    setSelectedFile(null);
    setDetectRes(null);
    setDetecting(false);
    setError(null);
    setJobId(null);
    setStatus(null);
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = null;
    setPolling(false);
    toast.success("File cleared successfully.");
  }
  
  // Auto-poll when a job is created
  React.useEffect(() => {
    if (!jobId) return;
    setPolling(true);
    async function tick() {
      try {
        const res = await fetch(`${apiBase}/v1/jobs/${jobId}`);
        const data = await res.json();
        setStatus(data);
        if (data.status === "finished" || data.status === "failed") {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          setPolling(false);
          if (data.status === "finished") {
            toast.success(`Ingest completed. Rows: ${data?.result?.rows ?? 0}`);
            // Best-effort backfill in case normalized rows are missing
            try {
              const headers: Record<string, string> = {}
              if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`
              await fetch(`${apiBase}/v1/transactions/backfill`, { method: 'POST', headers })
            } catch {}
            // Redirect to Spend to immediately see updated data
            setTimeout(() => router.replace("/spend"), 600);
          } else if (data.status === "failed") {
            toast.error("Job failed. See details.");
          }
        }
      } catch (e: any) {
        setError(String(e));
      }
    }
    tick();
    pollRef.current = window.setInterval(tick, 1000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      setPolling(false);
    };
  }, [jobId, apiBase]);

  // Load flags to gate the form
  React.useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/flags`);
        const d = await r.json();
        setIngestionEnabled(Boolean(d?.flags?.csv_ingestion_enabled ?? true));
      } catch {
        // default to enabled on fetch errors in dev
        setIngestionEnabled(true);
      } finally {
        setFlagsLoaded(true);
      }
    })();
  }, [apiBase]);

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <h1 className="text-xl font-semibold text-white/90">Upload Statement</h1>
      <p className="text-sm text-[var(--muted)]">Upload your bank statement (CSV/XLSX). We'll auto-detect the format and ingest it.</p>

      {!flagsLoaded ? (
        <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 text-sm text-[var(--muted)]">Loading flags…</div>
      ) : !ingestionEnabled ? (
        <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 space-y-2">
          <div className="text-sm font-semibold text-white/90">CSV ingestion is disabled</div>
          <div className="text-sm text-[var(--muted)]">Enable <code>csv_ingestion_enabled</code> in <a href="/flags" className="underline hover:text-white">Flags</a> to use this page.</div>
        </div>
      ) : (
      <form onSubmit={onSubmit} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 space-y-3">
        <input
          className="block w-full text-sm text-[var(--muted)] file:mr-4 file:rounded-md file:border-0 file:bg-brand-600/10 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-brand-600/20"
          type="file"
          name="file"
          accept=".csv,.xlsx,.pdf,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          ref={fileRef}
          onChange={async (e) => {
            const f = e.currentTarget.files && e.currentTarget.files[0] ? e.currentTarget.files[0] : null;
            setSelectedFile(f);
            setDetectRes(null);
            if (error) setError(null);
            if (!f) return;
            try {
              setDetecting(true);
              const fd = new FormData();
              fd.append("file", f);
              const r = await fetch(`${apiBase}/v1/statements/detect`, { method: "POST", body: fd });
              const d = await r.json();
              setDetectRes(d);
              if (!d?.detected && d?.recommended_action === "convert_to_csv") {
                toast.error("Unsupported PDF format. Please export CSV from your bank and re-upload.");
              } else if (d?.detected) {
                toast.success(`Detected ${String(d.kind || "").toUpperCase()} (${d.shape?.replaceAll("_", " ") || "format"})`);
              }
            } catch (err: any) {
              setDetectRes(null);
              toast.error("Detection failed. You can still try uploading.");
            } finally {
              setDetecting(false);
            }
          }}
        />
        {detecting && <div className="text-xs text-[var(--muted)]">Detecting format…</div>}
        {detectRes && (
          <div className="rounded-md border border-[var(--border)]/60 bg-black/20 p-3 text-xs text-[var(--muted)] space-y-1">
            <div>
              <span className="text-white/80">Detected:</span> {String(detectRes.kind || "unknown")} {detectRes.shape ? `• ${String(detectRes.shape).replaceAll("_"," ")}` : ""}
            </div>
            {detectRes.mapping && (
              <div className="grid grid-cols-2 gap-2">
                <div>Date ↦ <code className="text-[var(--muted)]">{detectRes.mapping.date || "(auto)"}</code></div>
                <div>Description ↦ <code className="text-[var(--muted)]">{detectRes.mapping.description || "(auto)"}</code></div>
                <div>Amount ↦ <code className="text-[var(--muted)]">{detectRes.mapping.amount || "(split)"}</code></div>
                <div>Debit ↦ <code className="text-[var(--muted)]">{detectRes.mapping.debit || "—"}</code>, Credit ↦ <code className="text-[var(--muted)]">{detectRes.mapping.credit || "—"}</code></div>
              </div>
            )}
            {detectRes.recommended_action === "convert_to_csv" && (
              <div className="text-red-400">This file isn’t supported yet. Export a CSV from your bank and try again.</div>
            )}
          </div>
        )}
        <div className="text-xs text-[var(--muted)]">
          Supported: CSV/XLSX from Chase, Bank of America, Wells Fargo, Citi, Capital One, Amex, Discover, PNC, US Bank, Ally, TD, HSBC.
        </div>
        <Button type="submit" disabled={uploading || !selectedFile || (detectRes?.recommended_action === "convert_to_csv") }>
          {uploading ? "Uploading…" : "Upload"}
        </Button>
        <Button type="button" variant="ghost" className="ml-2" onClick={clearFile} disabled={uploading}>
          Clear File
        </Button>
      </form>
      )}

      {error && <p className="text-sm text-red-400">Error: {error}</p>}

      {jobId && (
        <section className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 space-y-2">
          <div className="text-sm">Job ID: <code className="text-[var(--muted)]">{jobId}</code></div>
          <div className="text-sm text-[var(--muted)]">Status: {status?.status ?? (polling ? "checking…" : "queued")}</div>
          {polling && <div className="text-xs text-[var(--muted)]">Polling…</div>}
          {status && (
            <pre className="mt-2 overflow-auto rounded-md border border-[var(--border)]/60 bg-black/30 p-3 text-xs">
{JSON.stringify(status, null, 2)}
            </pre>
          )}
          {status?.status === "finished" && (
            <div className="text-sm text-green-400">Done. Rows ingested: <strong>{status?.result?.rows ?? 0}</strong>. <a className="underline hover:text-white" href="/spend">View spend</a></div>
          )}
          {status?.status === "failed" && (
            <div className="text-sm text-red-400">Job failed. See error above, then try again.</div>
          )}
        </section>
      )}
    </div>
  );
}
