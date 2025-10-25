"use client";
import * as React from "react";
import { signIn } from "next-auth/react";
import toast from "react-hot-toast";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Suspense } from "react";

function SignInInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [sending, setSending] = React.useState(false);

  React.useEffect(() => {
    if (session) {
      const cb = searchParams.get("callbackUrl") || "/";
      router.replace(cb);
    }
  }, [session, router, searchParams]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const cb = searchParams.get("callbackUrl") || "/";
      const res = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl: cb,
      });
      if ((res as any)?.error || res === undefined) {
        toast.error("Invalid credentials");
      } else if ((res as any)?.ok || (res as any)?.url) {
        router.replace((res as any)?.url || cb);
      }
    } catch {
      toast.error("Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  async function onMagicLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email) {
      toast.error("Enter your email first");
      return;
    }
    setSending(true);
    try {
      await signIn("email", { email, redirect: true, callbackUrl: "/" });
      toast.success("Check your email for a magic link");
    } catch {
      toast.error("Failed to send magic link");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-xl font-semibold text-white/90 mb-4">Sign in</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Email</label>
          <input
            type="email"
            className="w-full bg-transparent outline-none border border-[var(--border)]/60 rounded px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Password</label>
          <input
            type="password"
            className="w-full bg-transparent outline-none border border-[var(--border)]/60 rounded px-3 py-2"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-brand-600/80 hover:bg-brand-600 px-3 py-2 text-sm text-white"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <div className="text-xs text-[var(--muted)]">or</div>
        <button
          type="button"
          onClick={onMagicLink}
          disabled={sending}
          className="rounded border border-[var(--border)]/60 px-3 py-2 text-sm hover:bg-white/5"
        >
          {sending ? "Sending…" : "Send magic link"}
        </button>
      </form>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-sm text-sm text-[var(--muted)]">Loading…</div>}>
      <SignInInner />
    </Suspense>
  );
}
