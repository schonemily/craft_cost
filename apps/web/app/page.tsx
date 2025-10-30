"use client";
import * as React from "react";
import Image from "next/image";
import { useSession } from "next-auth/react";
import { Button } from "@dea/ui";
import toast from "react-hot-toast";
import { homeContent } from "../content/home";
import { Card } from "../components/Card";
import SubscribeButton from "../components/SubscribeButton";

export default function Page() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const [plaidEnabled, setPlaidEnabled] = React.useState<boolean>(false);
  const [heroIndex, setHeroIndex] = React.useState(0);
  const { data: session } = useSession();
  const [plan, setPlan] = React.useState<string | null>(null);
  function AnimatedNumber({ value }: { value: string }) {
    const n = parseInt(value.replace(/[^0-9]/g, ""), 10);
    const isNum = !isNaN(n);
    const [v, setV] = React.useState(0);
    React.useEffect(() => {
      if (!isNum) return;
      let start = 0;
      const end = n;
      const dur = 600;
      const t0 = performance.now();
      let raf = 0;
      const step = (t: number) => {
        const p = Math.min(1, (t - t0) / dur);
        setV(Math.round(start + (end - start) * p));
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
      return () => cancelAnimationFrame(raf);
    }, [isNum, n]);
    if (!isNum) return <>{value}</>;
    return <>{v.toLocaleString()}</>;
  }

  React.useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${apiBase}/v1/flags`);
        const d = await r.json();
        setPlaidEnabled(Boolean(d?.flags?.plaid_mock_enabled ?? false));
      } catch {
        setPlaidEnabled(false);
      }
    })();
  }, [apiBase]);

  React.useEffect(() => {
    (async () => {
      try {
        if (!(session as any)?.apiToken) return;
        const r = await fetch(`${apiBase}/v1/billing/status`, {
          headers: { Authorization: `Bearer ${(session as any).apiToken}` },
        });
        if (!r.ok) return;
        const d = await r.json();
        setPlan(String(d?.plan || (session as any)?.user?.plan || "free"));
      } catch {}
    })();
  }, [apiBase, session]);

  React.useEffect(() => {
    if (homeContent.hero.images.length <= 1) return;
    const id = setInterval(() => {
      setHeroIndex((i) => (i + 1) % homeContent.hero.images.length);
    }, 4000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-14">
      <section className="mx-auto max-w-6xl grid grid-cols-1 md:grid-cols-2 gap-10 items-center">
        <div>
          <div className="mb-3 inline-flex items-center gap-2">
            <img src="/logo.svg" alt={homeContent.appName} className="h-5 w-5 opacity-90" />
            <span className="text-sm font-semibold text-white/80">{homeContent.appName}</span>
          </div>
          <h1 className="text-4xl md:text-[2.75rem] leading-tight font-semibold text-white/90">{homeContent.hero.title}</h1>
          <p className="mt-3 text-[var(--muted)] max-w-prose">{homeContent.hero.subtitle}</p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <a href={homeContent.hero.ctaPrimary.href} className="rounded-md bg-brand-600/90 hover:bg-brand-600 px-4 py-2 text-sm text-white font-medium">{homeContent.hero.ctaPrimary.label}</a>
            <a href={homeContent.hero.ctaSecondary.href} className="rounded-md border border-[var(--border)]/60 px-4 py-2 text-sm text-white/90 hover:bg-white/5">{homeContent.hero.ctaSecondary.label}</a>
            {plaidEnabled && (
              <Button size="sm" variant="primary" onClick={() => toast("Mock Plaid flow started (stub)")}>Connect bank (mock)</Button>
            )}
            {session?.user && (
              plan === "plus" ? (
                <span className="ml-1 inline-flex items-center gap-2 rounded-md border border-emerald-600/40 bg-emerald-600/10 px-3 py-1.5 text-xs text-emerald-300">Plus active</span>
              ) : (
                <div className="ml-1">
                  <SubscribeButton />
                </div>
              )
            )}
          </div>
        </div>
        <div className="relative">
          <div className="rounded-2xl border border-[var(--border)]/60 bg-[var(--surface)]/60 p-2">
            <div className="relative overflow-hidden rounded-xl aspect-[16/10]">
              <Image src={homeContent.hero.images[heroIndex]} alt="hero" fill priority className="object-cover" />
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-tr from-black/10 via-transparent to-white/5" />
            </div>
          </div>
          <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
            {homeContent.hero.images.map((_, i) => (
              <span key={i} className={`h-1.5 w-6 rounded-full ${i === heroIndex ? "bg-white/80" : "bg-white/30"}`} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl">
        <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-4">
          {homeContent.metrics.map((m, idx) => (
            <div key={idx} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 text-center">
              <div className="text-2xl font-semibold text-white/90"><AnimatedNumber value={m.value} /></div>
              <div className="text-xs text-[var(--muted)] mt-1">{m.label}</div>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 px-4 py-3">
          <div className="flex flex-wrap items-center justify-center gap-8 opacity-80">
            {homeContent.logos.map((l, i) => (
              <Image key={i} src={l.src} alt={l.alt} width={88} height={20} className="h-5 w-auto" />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl">
        <h2 className="text-lg font-semibold text-white/90 mb-3">Pricing</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-[var(--border)]/60 bg-[var(--surface)]/60 p-6">
            <div className="text-white/90 font-semibold">Free</div>
            <div className="text-3xl font-bold mt-1">$0</div>
            <ul className="mt-3 text-sm text-[var(--muted)] space-y-1">
              <li>CSV upload</li>
              <li>Spend insights</li>
            </ul>
          </div>
          <div className="rounded-xl border border-brand-600/40 bg-brand-600/10 p-6">
            <div className="text-white/90 font-semibold">Plus</div>
            <div className="text-3xl font-bold mt-1">$ •• /mo</div>
            <ul className="mt-3 text-sm text-[var(--muted)] space-y-1">
              <li>Everything in Free</li>
              <li>Advanced suggestions</li>
              <li>Priority features</li>
            </ul>
            <div className="mt-4">
              <SubscribeButton />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl">
        <h2 className="text-lg font-semibold text-white/90 mb-3">Quick actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {homeContent.quick.map((q, idx) => (
            <Card key={idx} title={q.title} href={q.href}>{q.description}</Card>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl">
        <h2 className="text-lg font-semibold text-white/90 mb-3">{homeContent.how.headline}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {homeContent.how.steps.map((s, idx) => (
            <div key={idx} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
              <div className="mb-1 text-sm font-semibold text-white/90">{s.title}</div>
              <div className="text-sm text-[var(--muted)]">{s.description}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl">
        <h2 className="text-lg font-semibold text-white/90 mb-3">{homeContent.why.headline}</h2>
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-[var(--muted)] list-disc pl-5">
          {homeContent.why.bullets.map((b, idx) => (
            <li key={idx}>{b}</li>
          ))}
        </ul>
      </section>

      <section className="mx-auto max-w-6xl">
        <h2 className="text-lg font-semibold text-white/90 mb-3">Fees & Transparency</h2>
        <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5">
          <ul className="list-disc pl-5 text-sm text-[var(--muted)] space-y-1">
            <li>Negotiation fee: capped, transparent pricing. No hidden add‑ons.</li>
            <li>Your data remains yours; analytics are privacy‑first and minimal.</li>
            <li>Cancel anytime. No lock‑in. Export your data when you leave.</li>
          </ul>
        </div>
      </section>

      <section className="mx-auto max-w-6xl">
        <h2 className="text-lg font-semibold text-white/90 mb-3">What people say</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {homeContent.testimonials.map((t, idx) => (
            <div key={idx} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-5">
              <div className="text-white/90">“{t.quote}”</div>
              <div className="mt-2 text-xs text-[var(--muted)]">{t.author} • {t.role}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
