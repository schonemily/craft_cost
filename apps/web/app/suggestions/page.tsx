"use client";
import * as React from 'react'
import { useQuery } from '@tanstack/react-query'

export default function SuggestionsPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
  const query = useQuery<{ items: Suggestion[] }>({
    queryKey: ['suggestions'],
    queryFn: async () => {
      const r = await fetch(`${apiBase}/v1/suggestions`)
      if (!r.ok) throw new Error(`suggestions ${r.status}`)
      return r.json() as Promise<{ items: Suggestion[] }>
    }
  })

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
          {query.data?.items?.map((s) => (
            <article key={s.id} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
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
                  <pre className="mt-2 overflow-auto rounded bg-black/30 p-2 text-xs text-white/80">{JSON.stringify(s.evidence, null, 2)}</pre>
                </details>
              )}
            </article>
          ))}
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
