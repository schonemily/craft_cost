"use client";
import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSession } from 'next-auth/react'
import { AnimatePresence, motion } from 'framer-motion'

export default function SuggestionsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010"
  const { data: session } = useSession()
  const apiToken = (session as any)?.apiToken as string | undefined
  const query = useQuery<{ items: Suggestion[] }>({
    queryKey: ['suggestions'],
    queryFn: async () => {
      const headers: Record<string, string> = {}
      if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`
      const r = await fetch(`${apiBase}/v1/suggestions`, { headers })
      if (!r.ok) throw new Error(`suggestions ${r.status}`)
      return r.json() as Promise<{ items: Suggestion[] }>
    },
    enabled: true,
  })

  const renderEvidence = React.useCallback((evidence: any[]) => {
    if (!Array.isArray(evidence) || evidence.length === 0) return null
    const linkSets = evidence
      .map((e: any) => Array.isArray(e?.reference_links) ? e.reference_links : [])
      .filter((arr: any) => Array.isArray(arr) && arr.length) as string[][]
    const links = Array.from(new Set((linkSets.flat() as string[]).filter(Boolean)))
    // Case 1: objects with samples: [{ samples: [{date, amount, description, merchant}, ...] }]
    const hasSampleObjects = evidence.some((e: any) => Array.isArray(e?.samples) && e.samples.length && (e.samples[0].date != null || e.samples[0].description != null || e.samples[0].merchant != null))
    if (hasSampleObjects) {
      const samples: any[] = evidence.flatMap((e: any) => Array.isArray(e?.samples) ? e.samples : [])
      return (
        <ul className="mt-2 text-xs text-white/80 space-y-1">
          {samples.map((it: any, idx: number) => (
            <li key={idx} className="flex flex-wrap gap-2">
              <span className="text-[var(--muted)]">{it.date ?? '-'}</span>
              <span>{it.description ?? '-'}</span>
              {it.merchant ? <span>• {it.merchant}</span> : null}
              {typeof it.amount === 'number' ? <span>• ${Math.abs(it.amount).toFixed(2)}</span> : null}
            </li>
          ))}
        </ul>
      )
    }
    // Case 2: recurring subs evidence: [{ merchant, samples: [...] }]
    const hasMerchantSamples = evidence.some((e: any) => e?.merchant && Array.isArray(e?.samples))
    if (hasMerchantSamples) {
      return (
        <div className="mt-2 space-y-2 text-xs text-white/80">
          {evidence.map((e: any, idx: number) => (
            <div key={idx}>
              <div className="font-medium">{e.merchant}</div>
              <ul className="ml-4 list-disc space-y-1">
                {e.samples?.map((it: any, j: number) => (
                  <li key={j}>
                    <span className="text-[var(--muted)]">{it.date ?? '-'}</span> {it.description ?? '-'} • ${Math.abs(it.amount ?? 0).toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )
    }
    // Case 3: streaming consolidate evidence: [{ merchant, amount }]
    const allSimple = evidence.every((e: any) => e?.merchant && typeof e?.amount === 'number')
    if (allSimple) {
      return (
        <ul className="mt-2 text-xs text-white/80 space-y-1">
          {evidence.map((e: any, idx: number) => (
            <li key={idx} className="flex justify-between">
              <span>{e.merchant}</span>
              <span>~${Math.abs(e.amount).toFixed(2)}/mo</span>
            </li>
          ))}
        </ul>
      )
    }
    if (links.length) {
      return (
        <div className="mt-2 text-xs text-[var(--muted)]">
          <div className="mb-1 text-white/80">Reference links</div>
          <ul className="list-disc ml-4 space-y-1">
            {links.map((u) => (
              <li key={u}>
                <a href={u} target="_blank" rel="noreferrer" className="underline hover:text-white">{u}</a>
              </li>
            ))}
          </ul>
        </div>
      )
    }
    return <pre className="mt-2 overflow-auto rounded bg-black/30 p-2 text-xs text-white/80">{JSON.stringify(evidence, null, 2)}</pre>
  }, [])

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-xl font-semibold text-white/90">Suggestions</h1>
        <p className="text-sm text-[var(--muted)]">AI-driven cost reduction suggestions</p>
      </section>

      <section>
        {query.isLoading && <div className="text-sm text-[var(--muted)]">Loading…</div>}
        {query.isError && <div className="text-sm text-red-400">Failed to load suggestions</div>}
        {!query.isLoading && query.data && query.data.items.length === 0 && (
          <div className="text-sm text-[var(--muted)]">No suggestions yet. Upload transactions and try again.</div>
        )}
        <div className="grid gap-4">
          <AnimatePresence initial={false}>
          {query.data?.items?.map((s, idx) => (
            <motion.article
              key={s.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, delay: Math.min(idx, 6) * 0.02, ease: 'easeOut' }}
              className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 will-change-transform"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-white/90">{s.title}</h2>
                  <p className="mt-1 text-sm text-[var(--muted)]">{s.summary}</p>
                </div>
                <div className="text-right text-sm">
                  <div className="text-green-300">~${s.estimated_monthly_saving.toFixed(2)}/mo</div>
                  <div className="text-green-400/80">~${s.estimated_annual_saving.toFixed(2)}/yr</div>
                  <div className="mt-1 text-[var(--muted)]">confidence {(s.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
              {!!s.tags?.length && (
                <div className="mt-2 flex flex-wrap gap-1 text-xs text-[var(--muted)]">
                  {s.tags.map((t) => (
                    <span key={t} className="rounded border border-[var(--border)]/60 px-2 py-0.5">{t}</span>
                  ))}
                </div>
              )}
              {!!s.evidence?.length && (
                <details className="mt-3 text-sm">
                  <summary className="cursor-pointer text-[var(--muted)]">Evidence</summary>
                  {renderEvidence(s.evidence)}
                </details>
              )}
            </motion.article>
          ))}
          </AnimatePresence>
        </div>
      </section>
    </div>
  )
}

type Suggestion = {
  id: string
  title: string
  summary: string
  estimated_monthly_saving: number
  estimated_annual_saving: number
  confidence: number
  tags: string[]
  evidence: any[]
}
