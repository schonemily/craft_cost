"use client";
import * as React from "react";
import { useSession, signIn, signOut } from "next-auth/react";

export default function AuthButtons() {
  const { data: session, status } = useSession();
  const loading = status === "loading";

  if (loading) return <div className="text-xs text-[var(--muted)]">Loading…</div>;

  if (!session) {
    return (
      <button
        onClick={() => signIn()}
        className="rounded border border-[var(--border)]/60 px-3 py-1 text-xs hover:bg-white/5"
      >
        Sign in
      </button>
    );
  }

  const email = session.user?.email ?? "user";
  const plan = (session.user as any)?.plan ?? "free";

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-[var(--muted)]">{email} · {plan}</span>
      <button
        onClick={() => signOut()}
        className="rounded border border-[var(--border)]/60 px-3 py-1 hover:bg-white/5"
      >
        Sign out
      </button>
    </div>
  );
}
