"use client";
import * as React from "react";
import { useSession } from "next-auth/react";
import { loadStripe } from "@stripe/stripe-js";
import toast from "react-hot-toast";

const stripePromise = typeof window !== "undefined"
  ? loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "")
  : (Promise.resolve(null) as unknown as Promise<any>);

export default function SubscribeButton({ plan = "plus" }: { plan?: "plus" | "free" }) {
  const { data: session } = useSession();
  const canSee = Boolean(session?.user?.email);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const [loading, setLoading] = React.useState(false);

  const openCheckout = async (period: "monthly" | "annual") => {
    try {
      setLoading(true);
      const res = await fetch(`${apiBase}/v1/billing/stripe/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${(session as any)?.apiToken}` },
        body: JSON.stringify({ period }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail?.message || "Could not start checkout");
      }
      const data = await res.json();
      const sid = data?.id as string | undefined;
      const url = data?.url as string | undefined;
      const pk = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || "";
      if (sid && pk) {
        const stripe = await stripePromise;
        if (stripe) {
          const { error } = await stripe.redirectToCheckout({ sessionId: sid });
          if (error) throw error;
          return;
        }
      }
      if (url) {
        window.location.href = url;
        return;
      }
      throw new Error("No checkout session available");
    } catch (e: any) {
      console.error(e);
      toast.error(e?.message || "Checkout failed to start");
    } finally {
      setLoading(false);
    }
  };

  if (!canSee) return null;
  const userPlan = (session?.user as any)?.plan || "free";
  if (userPlan === "plus") {
    return (
      <span className="inline-flex items-center gap-2 rounded-md border border-emerald-600/40 bg-emerald-600/10 px-3 py-1.5 text-xs text-emerald-300">
        Plus active
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={loading}
        onClick={() => openCheckout("monthly")}
        className="rounded-md bg-brand-600/90 hover:bg-brand-600 disabled:opacity-60 px-3 py-1.5 text-sm text-white"
      >
        Upgrade – Monthly
      </button>
      <button
        type="button"
        disabled={loading}
        onClick={() => openCheckout("annual")}
        className="rounded-md border border-[var(--border)]/60 hover:bg-white/5 disabled:opacity-60 px-3 py-1.5 text-sm text-white/90"
      >
        Annual
      </button>
    </div>
  );
}
