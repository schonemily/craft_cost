import * as React from 'react'

export function Card({ title, children, href }: { title: string, children?: React.ReactNode, href?: string }) {
  const inner = (
    <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4 hover:border-brand-600/50 transition-colors">
      <div className="mb-2 text-sm font-semibold text-white/90">{title}</div>
      <div className="text-sm text-[var(--muted)]">{children}</div>
    </div>
  )
  return href ? <a href={href} className="block">{inner}</a> : inner
}
