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
import NavLinks from '../components/NavLinks'
import { Toaster } from 'react-hot-toast'
import SessionProvider from '../components/SessionProvider'
import AuthButtons from '../components/AuthButtons'

const inter = Inter({ subsets: ['latin'] })

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen`}>
        <SessionProvider>
          <header className="border-b border-[var(--border)]/60 bg-[var(--surface)]/60 backdrop-blur">
            <div className="container flex items-center justify-between py-3">
              <Link href="/" className="flex items-center gap-2 text-sm font-semibold">
                <Image src="/logo.svg" alt="craft_cost" width={16} height={16} className="opacity-90" />
                craft_cost
              </Link>
              <div className="flex items-center gap-4">
                <TopbarStatus />
                <AuthButtons />
              </div>
            </div>
            <NavLinks />
          </header>
          <QueryProvider>
            <main className="container py-8">
              {children}
            </main>
            <Toaster position="top-right" toastOptions={{
              style: { background: 'rgba(15,19,32,0.9)', color: 'white', border: '1px solid rgba(31,36,51,0.6)' }
            }} />
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  )
}
