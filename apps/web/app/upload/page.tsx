"use client";
import * as React from "react";
import toast from "react-hot-toast";
import { Button } from "@dea/ui";

export default function UploadPage() {
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [status, setStatus] = React.useState<any>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [polling, setPolling] = React.useState(false);
  const pollRef = React.useRef<number | null>(null);
  const [ingestionEnabled, setIngestionEnabled] = React.useState(true);
  const [flagsLoaded, setFlagsLoaded] = React.useState(false);
  const [uploading, setUploading] = React.useState(false);

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setJobId(null);
    setStatus(null);
    const form = e.currentTarget;
    const input = form.querySelector<HTMLInputElement>("input[type=file]");
    if (!input || !input.files || input.files.length === 0) {
      setError("Please choose a CSV file");
      return;
    }
    const fd = new FormData();
    fd.append("file", input.files[0]);
    setUploading(true);
    try {
      const res = await fetch(`${apiBase}/v1/transactions/csv`, { method: "POST", body: fd });
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
      <h1 className="text-xl font-semibold text-white/90">Upload CSV</h1>
      <p className="text-sm text-[var(--muted)]">Week 2 – CSV ingestion: enqueue a background job and track its status.</p>

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
          accept=".csv,text/csv"
        />
        <Button type="submit" disabled={uploading}>
          {uploading ? "Uploading…" : "Upload"}
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
