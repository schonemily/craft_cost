export const metadata = {
  title: 'craft_cost',
  description: 'Spend better. Simple financial clarity.',
}

import './globals.css'
import Link from 'next/link'
import Image from 'next/image'
import { Inter } from 'next/font/google'
import TopbarStatus from '../components/TopbarStatus'
import QueryProvider from '../components/QueryProvider'
import { Toaster } from 'react-hot-toast'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen`}>
        <header className="border-b border-[var(--border)]/60 bg-[var(--surface)]/60 backdrop-blur">
          <nav className="container flex items-center justify-between py-3">
            <Link href="/" className="flex items-center gap-2 text-sm font-semibold">
              <Image src="/logo.svg" alt="craft_cost" width={16} height={16} className="opacity-90" />
              craft_cost
            </Link>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-4 text-sm text-[var(--muted)]">
                <Link href="/" className="hover:text-white">Home</Link>
                <Link href="/upload" className="hover:text-white">Upload CSV</Link>
                <Link href="/spend" className="hover:text-white">Spend</Link>
                <Link href="/suggestions" className="hover:text-white">Suggestions</Link>
                <Link href="/debt" className="hover:text-white">Debt</Link>
                <Link href="/flags" className="hover:text-white">Flags</Link>
              </div>
              <TopbarStatus />
            </div>
          </nav>
        </header>
        <QueryProvider>
          <main className="container py-8">
            {children}
          </main>
          <Toaster position="top-right" toastOptions={{
            style: { background: 'rgba(15,19,32,0.9)', color: 'white', border: '1px solid rgba(31,36,51,0.6)' }
          }} />
        </QueryProvider>
      </body>
    </html>
  )
}
