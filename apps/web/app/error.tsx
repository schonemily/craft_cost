'use client'

import * as React from 'react'
import Link from 'next/link'

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-2xl font-semibold text-white/90">Something went wrong</h1>
      <p className="text-sm text-[var(--muted)]">An unexpected error occurred.</p>
      <div className="mt-2 flex items-center gap-2">
        <button onClick={() => reset()} className="rounded border border-[var(--border)]/60 px-3 py-1 text-sm hover:bg-white/5">Try again</button>
        <Link href="/" className="rounded border border-[var(--border)]/60 px-3 py-1 text-sm hover:bg-white/5">Go home</Link>
      </div>
    </div>
  )
}
