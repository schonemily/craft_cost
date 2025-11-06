"use client";
import * as React from "react";
import { useSession, signIn, signOut } from "next-auth/react";
import { usePathname } from "next/navigation";

export default function AuthButtons() {
  const { data: session, status } = useSession();
  const loading = status === "loading";
  const pathname = usePathname();
  const onAuthPage = pathname === "/signin" || pathname === "/signup" || pathname === "/login";

  if (loading) return <div className="text-xs text-[var(--muted)]">Loading…</div>;
  if (onAuthPage) return null;

  if (!session) {
    return (
      <div className="flex items-center gap-2">
        <button
          onClick={() => signIn("google", { callbackUrl: "/" })}
          className="rounded border border-[var(--border)]/60 px-3 py-1 text-xs hover:bg-white/5"
        >
          Google
        </button>
        <button
          onClick={() => signIn("github", { callbackUrl: "/" })}
          className="rounded border border-[var(--border)]/60 px-3 py-1 text-xs hover:bg-white/5"
        >
          GitHub
        </button>
      </div>
    );
  }

  const email = session.user?.email ?? "user";
  const plan = (session.user as any)?.plan ?? "free";

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-[var(--muted)]">{email} · {plan}</span>
      <button
        onClick={() => { try { localStorage.removeItem('userName'); } catch {} ; signOut(); }}
        className="rounded border border-[var(--border)]/60 px-3 py-1 hover:bg-white/5"
      >
        Sign out
      </button>
    </div>
  );
}
