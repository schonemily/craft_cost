"use client";
import * as React from "react";
import Image from "next/image";
import { homeContent } from "../content/home";
import { Card } from "../components/Card";
import SubscribeButton from "../components/SubscribeButton";
import { HeroGeometric } from "@/components/ui/shape-landing-hero";

export default function Page() {
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

  return (
    <div className="space-y-14">
      <section>
        <HeroGeometric badge={homeContent.appName} title1="Elevate Your Financial Clarity" title2="Crafting Smart Savings" />
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
