export default function Page() {
  const sample = [
    { date: '2025-09-01', description: 'Coffee Shop', amount: -4.5, category: 'Food & Drink' },
    { date: '2025-09-02', description: 'Grocery Market', amount: -64.21, category: 'Groceries' },
    { date: '2025-09-03', description: 'Salary', amount: 2450.0, category: 'Income' },
  ];
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-white/90">Intake preview</h1>
        <p className="text-[var(--muted)] mt-1">This is a sample of the first few parsed rows for a typical CSV.</p>
      </header>
      <div className="rounded-lg border border-[var(--border)]/60 bg-[var(--surface)]/60 overflow-auto">
        <table className="min-w-full text-sm">
          <thead className="text-[var(--muted)] border-b border-[var(--border)]/60">
            <tr>
              <th className="px-4 py-2 text-left">Date</th>
              <th className="px-4 py-2 text-left">Description</th>
              <th className="px-4 py-2 text-left">Amount</th>
              <th className="px-4 py-2 text-left">Category</th>
            </tr>
          </thead>
          <tbody>
            {sample.map((r, i) => (
              <tr key={i} className="border-b border-[var(--border)]/30">
                <td className="px-4 py-2 whitespace-nowrap">{r.date}</td>
                <td className="px-4 py-2">{r.description}</td>
                <td className="px-4 py-2 whitespace-nowrap text-white/90">{r.amount.toLocaleString(undefined, { style: 'currency', currency: 'USD' })}</td>
                <td className="px-4 py-2 whitespace-nowrap">{r.category}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
