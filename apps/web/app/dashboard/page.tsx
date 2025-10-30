export default function Page() {
  const cards = [
    { label: 'Open suggestions', value: 12 },
    { label: 'Spend this month', value: '$1,264' },
    { label: 'Categories over budget', value: 2 },
    { label: 'Upcoming payments', value: 3 },
  ];
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Dashboard</h1>
        <p className="text-[var(--muted)] mt-1">Overview of your finances and quick links.</p>
      </header>
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c, i) => (
          <div key={i} className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 p-4">
            <div className="text-2xl font-semibold text-white/90">{c.value}</div>
            <div className="text-xs text-[var(--muted)] mt-1">{c.label}</div>
          </div>
        ))}
      </section>
    </div>
  );
}
    