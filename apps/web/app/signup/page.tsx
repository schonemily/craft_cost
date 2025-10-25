"use client";
import * as React from "react";
import toast from "react-hot-toast";
import { signIn } from "next-auth/react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function SignupInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const { data: session } = useSession();
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (session) {
      const cb = searchParams.get("callbackUrl") || "/";
      router.replace(cb);
    }
  }, [session, router, searchParams]);

  function validate(): string | null {
    const em = email.trim();
    const nm = name.trim();
    if (!nm || nm.length < 2) return "Please enter your full name";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) return "Enter a valid email";
    if ((password || "").length < 8) return "Password must be at least 8 characters";
    if (password !== confirm) return "Passwords do not match";
    return null;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const err = validate();
    if (err) {
      toast.error(err);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      if (res.status === 403) {
        toast.error("Sign-up is disabled in this environment");
        return;
      }
      if (!res.ok) {
        let msg = "Sign-up failed";
        let code: string | undefined = undefined;
        try {
          const body = await res.json();
          code = body?.error?.code || body?.detail?.code;
          msg = body?.error?.message || body?.detail?.message || body?.message || msg;
        } catch {}
        if (code === "email_taken") {
          // Try to sign you in with the entered credentials
          const cb2 = searchParams.get("callbackUrl") || "/";
          const s2 = await signIn("credentials", { email, password, redirect: false, callbackUrl: cb2 });
          if ((s2 as any)?.ok || (s2 as any)?.url) {
            router.replace((s2 as any)?.url || cb2);
            return;
          }
        }
        toast.error(msg);
        return;
      }
      // If backend returns new shape, we could persist token immediately as a fallback
      try {
        const body = await res.json();
        const t = (body as any)?.token;
        if (t) {
          try { localStorage.setItem("apiToken", String(t)); } catch {}
        }
      } catch {}
      // Auto sign-in via credentials after register
      try { localStorage.setItem("userName", name.trim()); } catch {}
      const cb = searchParams.get("callbackUrl") || "/";
      const s = await signIn("credentials", { email, password, redirect: false, callbackUrl: cb });
      if ((s as any)?.error || s === undefined) {
        toast.error("Signed up, but sign-in failed");
      } else if ((s as any)?.ok || (s as any)?.url) {
        router.replace((s as any)?.url || cb);
      }
    } catch {
      toast.error("Sign-up failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm">
      <h1 className="text-xl font-semibold text-white/90 mb-4">Create your account</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Name</label>
          <input
            type="text"
            className="w-full bg-transparent outline-none border border-[var(--border)]/60 rounded px-3 py-2"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
          />
        </div>
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
            minLength={8}
          />
        </div>
        <div>
          <label className="block text-sm text-[var(--muted)] mb-1">Confirm password</label>
          <input
            type="password"
            className="w-full bg-transparent outline-none border border-[var(--border)]/60 rounded px-3 py-2"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={8}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-brand-600/80 hover:bg-brand-600 px-3 py-2 text-sm text-white"
        >
          {loading ? "Creating…" : "Sign up"}
        </button>
        <p className="text-xs text-[var(--muted)]">Already have an account? <Link className="underline hover:text-white" href="/signin">Sign in</Link></p>
      </form>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-sm text-sm text-[var(--muted)]">Loading…</div>}>
      <SignupInner />
    </Suspense>
  );
}
