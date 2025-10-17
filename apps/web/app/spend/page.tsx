"use client";
import * as React from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Button } from '@dea/ui'

type Tx = {
  id: number
  user_id: number
  category: string | null
  merchant: string | null
  date: string | null
  amount: number | null
  description: string | null
}

export default function SpendPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"
  const [period, setPeriod] = React.useState<'last_7d' | 'last_30d' | 'last_90d'>('last_30d')
  const [category, setCategory] = React.useState<string | null>(null)
  const queryClient = useQueryClient()

  const CATEGORIES = [
    "housing","utilities","telco","insurance","transport","grocery","dining","entertainment",
    "subscriptions","health","personal","fees","income","other"
  ] as const

  const summaryQuery = useQuery<{ period: string; total: number; by_category: Record<string, number> }>({
    queryKey: ['summary', period],
    queryFn: async () => {
      const r = await fetch(`${apiBase}/v1/spend/summary?period=${period}`)
      if (!r.ok) throw new Error(`summary ${r.status}`)
      return r.json() as Promise<{ period: string; total: number; by_category: Record<string, number> }>
    },
  })

  const txQuery = useInfiniteQuery<{ items: Tx[]; next_cursor: number | null }>({
    queryKey: ['transactions', { category }],
    queryFn: async ({ pageParam }) => {
      const url = new URL(`${apiBase}/v1/transactions`)
      const cur = pageParam != null ? Number(pageParam) : undefined
      if (cur) url.searchParams.set('cursor', String(cur))
      url.searchParams.set('limit', '20')
      if (category) url.searchParams.set('category', category)
      const r = await fetch(url.toString())
      if (!r.ok) throw new Error(`transactions ${r.status}`)
      return r.json() as Promise<{ items: Tx[]; next_cursor: number | null }>
    },
    initialPageParam: undefined,
    getNextPageParam: (lastPage: { next_cursor: number | null }) => lastPage.next_cursor ?? undefined,
  })

  // Toast query errors
  React.useEffect(() => {
    if (summaryQuery.isError) toast.error('Failed to load summary')
  }, [summaryQuery.isError])
  React.useEffect(() => {
    if (txQuery.isError) toast.error('Failed to load transactions')
  }, [txQuery.isError])

  // Recategorize mutation
  const recatMutation = useMutation({
    mutationFn: async ({ id, category }: { id: number; category: string | null }) => {
      const normalized = category && category.length ? category : 'other'
      const res = await fetch(`${apiBase}/v1/transactions/${id}/recategorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: normalized })
      })
      if (!res.ok) throw new Error(`recat ${res.status}`)
      return res.json() as Promise<Tx>
    },
    onSuccess: () => {
      toast.success('Recategorized')
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['summary'] })
    },
    onError: () => toast.error('Failed to recategorize'),
  })

  const items: Tx[] = (txQuery.data?.pages ?? []).flatMap((p: any) => p.items) as Tx[]
  const nextCursor: number | null = txQuery.data?.pages?.[txQuery.data.pages.length - 1]?.next_cursor ?? null

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-xl font-semibold text-white/90">Spend</h1>
        <p className="text-sm text-[var(--muted)]">Transactions and summary (read-only)</p>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
          <div className="text-sm font-semibold text-white/90">Total</div>
          {summaryQuery.isLoading ? (
            <div className="mt-2 h-7 w-24 animate-pulse rounded bg-white/10" />
          ) : summaryQuery.isError ? (
            <div className="mt-2 text-xs text-red-400">Error loading summary</div>
          ) : (
            <div className="mt-2 text-2xl">${Math.abs(summaryQuery.data?.total ?? 0).toFixed(2)}</div>
          )}
        </div>
        <div className="sm:col-span-2 rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold text-white/90">By Category</div>
            <div className="flex items-center gap-2 text-xs">
              <label className="text-[var(--muted)]">Period</label>
              <select value={period} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setPeriod(e.target.value as any)} className="rounded-md bg-black/20 px-2 py-1 outline-none">
                <option value="last_7d">Last 7d</option>
                <option value="last_30d">Last 30d</option>
                <option value="last_90d">Last 90d</option>
              </select>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
            {summaryQuery.isLoading && (
              <>
                <div className="h-4 w-full animate-pulse rounded bg-white/10" />
                <div className="h-4 w-full animate-pulse rounded bg-white/10" />
                <div className="h-4 w-full animate-pulse rounded bg-white/10" />
                <div className="h-4 w-full animate-pulse rounded bg-white/10" />
              </>
            )}
            {!summaryQuery.isLoading && summaryQuery.data && Object.entries(summaryQuery.data.by_category as Record<string, number>).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="text-[var(--muted)]">{k}</span>
                <span>${Math.abs(v).toFixed(2)}</span>
              </div>
            ))}
            {!summaryQuery.isLoading && !summaryQuery.data && <div className="text-[var(--muted)]">No data</div>}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-[var(--muted)]">
              <tr>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Description</th>
                <th className="px-4 py-2">Merchant</th>
                <th className="px-4 py-2">Category</th>
                <th className="px-4 py-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {items.map((tx: Tx) => (
                <tr key={tx.id} className="border-t border-[var(--border)]/60">
                  <td className="px-4 py-2 whitespace-nowrap">{tx.date ?? ''}</td>
                  <td className="px-4 py-2">{tx.description ?? ''}</td>
                  <td className="px-4 py-2">{tx.merchant ?? ''}</td>
                  <td className="px-4 py-2">
                    <select
                      value={tx.category ?? ''}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) => recatMutation.mutate({ id: tx.id, category: e.target.value || null })}
                      className="rounded-md bg-black/20 px-2 py-1 text-xs outline-none"
                    >
                      <option value="">(none)</option>
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-2 text-right">{tx.amount != null ? `$${Math.abs(tx.amount).toFixed(2)}` : ''}</td>
                </tr>
              ))}
              {items.length === 0 && txQuery.isLoading && (
                <>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <tr key={`sk-${i}`} className="border-t border-[var(--border)]/60">
                      <td className="px-4 py-2"><div className="h-4 w-20 animate-pulse rounded bg-white/10" /></td>
                      <td className="px-4 py-2"><div className="h-4 w-64 animate-pulse rounded bg-white/10" /></td>
                      <td className="px-4 py-2"><div className="h-4 w-40 animate-pulse rounded bg-white/10" /></td>
                      <td className="px-4 py-2"><div className="h-4 w-28 animate-pulse rounded bg-white/10" /></td>
                      <td className="px-4 py-2 text-right"><div className="ml-auto h-4 w-16 animate-pulse rounded bg-white/10" /></td>
                    </tr>
                  ))}
                </>
              )}
              {items.length === 0 && (
                <tr>
                  <td className="px-4 py-6 text-center text-[var(--muted)]" colSpan={5}>
                    {txQuery.isError ? <span className="text-red-400">Failed to load transactions.</span> : 'No transactions yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex justify-between items-center p-3">
          <div className="flex items-center gap-2 text-xs">
            <label className="text-[var(--muted)]">Category</label>
            <select value={category ?? ''} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCategory(e.target.value || null)} className="rounded-md bg-black/20 px-2 py-1 outline-none">
              <option value="">All</option>
              <option value="housing">housing</option>
              <option value="utilities">utilities</option>
              <option value="telco">telco</option>
              <option value="insurance">insurance</option>
              <option value="transport">transport</option>
              <option value="grocery">grocery</option>
              <option value="dining">dining</option>
              <option value="entertainment">entertainment</option>
              <option value="subscriptions">subscriptions</option>
              <option value="health">health</option>
              <option value="personal">personal</option>
              <option value="fees">fees</option>
              <option value="income">income</option>
              <option value="other">other</option>
            </select>
          </div>
          {nextCursor && (
            <Button onClick={() => txQuery.fetchNextPage()} disabled={txQuery.isFetchingNextPage} variant="ghost">
              {txQuery.isFetchingNextPage ? 'Loading...' : 'Load more'}
            </Button>
          )}
        </div>
      </section>
    </div>
  )
}
