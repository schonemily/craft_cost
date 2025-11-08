import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-2xl font-semibold text-white/90">Page not found</h1>
      <p className="text-sm text-[var(--muted)]">The page you are looking for does not exist.</p>
      <Link href="/" className="mt-2 rounded border border-[var(--border)]/60 px-3 py-1 text-sm hover:bg-white/5">Go home</Link>
    </div>
  );
}
