import Link from "next/link";
import { Card } from "../../components/Card";

export default function Page() {
  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Intake</h1>
        <p className="text-[var(--muted)] mt-1">Upload transactions and review a sample before finalizing.</p>
      </header>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="Upload CSV" href="/upload">Import a new bank statement file.</Card>
        <Card title="Preview" href="/intake-preview">Check a parsed sample of your file.</Card>
        <Card title="Spend" href="/spend">Explore spend after import.</Card>
      </section>

      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5 text-sm text-[var(--muted)]">
        Need a template? Download a sample CSV from <Link className="underline" href="/upload">Upload</Link> to see the expected columns.
      </div>
    </div>
  );
}
