"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "next-auth/react";

export default function NavLinks() {
  const { status } = useSession();
  const pathname = usePathname();
  const onAuthPage = pathname === "/login" || pathname === "/signin";
  if (onAuthPage) return null;
  if (status !== "authenticated") return null;
  return (
    <div className="border-t border-[var(--border)]/60">
      <nav className="container py-2 overflow-x-auto">
        <div className="flex items-center gap-3 text-sm text-[var(--muted)] whitespace-nowrap">
          <Link href="/" className={`px-2 py-1 rounded-md ${pathname === "/" ? "bg-white/5 text-white" : "hover:text-white"}`}>Home</Link>
          <Link href="/upload" className={`px-2 py-1 rounded-md ${pathname === "/upload" ? "bg-white/5 text-white" : "hover:text-white"}`}>Upload CSV</Link>
          <Link href="/connect" className={`px-2 py-1 rounded-md ${pathname.startsWith("/connect") ? "bg-white/5 text-white" : "hover:text-white"}`}>Connect</Link>
          <Link href="/onboarding" className={`px-2 py-1 rounded-md ${pathname.startsWith("/onboarding") ? "bg-white/5 text-white" : "hover:text-white"}`}>Onboarding</Link>
          <Link href="/subscriptions" className={`px-2 py-1 rounded-md ${pathname.startsWith("/subscriptions") ? "bg-white/5 text-white" : "hover:text-white"}`}>Subscriptions</Link>
          <Link href="/negotiations" className={`px-2 py-1 rounded-md ${pathname.startsWith("/negotiations") ? "bg-white/5 text-white" : "hover:text-white"}`}>Negotiations</Link>
          <Link href="/intake" className={`px-2 py-1 rounded-md ${pathname.startsWith("/intake") && !pathname.startsWith("/intake-preview") ? "bg-white/5 text-white" : "hover:text-white"}`}>Intake</Link>
          <Link href="/spend" className={`px-2 py-1 rounded-md ${pathname.startsWith("/spend") ? "bg-white/5 text-white" : "hover:text-white"}`}>Spend</Link>
          <Link href="/suggestions" className={`px-2 py-1 rounded-md ${pathname.startsWith("/suggestions") ? "bg-white/5 text-white" : "hover:text-white"}`}>Suggestions</Link>
          <Link href="/debt" className={`px-2 py-1 rounded-md ${pathname.startsWith("/debt") ? "bg-white/5 text-white" : "hover:text-white"}`}>Debt</Link>
          <Link href="/dashboard" className={`px-2 py-1 rounded-md ${pathname.startsWith("/dashboard") ? "bg-white/5 text-white" : "hover:text-white"}`}>Dashboard</Link>
          <Link href="/flags" className={`px-2 py-1 rounded-md ${pathname.startsWith("/flags") ? "bg-white/5 text-white" : "hover:text-white"}`}>Flags</Link>
        </div>
      </nav>
    </div>
  );
}
