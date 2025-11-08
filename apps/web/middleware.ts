import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  // Redirect legacy auth routes to /signin
  if (pathname === "/login" || pathname === "/signup") {
    const url = req.nextUrl.clone();
    url.pathname = "/signin";
    return NextResponse.redirect(url);
  }
  // Public routes
  if (
    pathname.startsWith("/signin") ||
    pathname.startsWith("/signup") || // still allow static generation but redirect above
    pathname.startsWith("/login") ||  // still allow but redirect above
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon.ico") ||
    pathname.startsWith("/logo.svg") ||
    pathname.startsWith("/static")
  ) {
    const res = NextResponse.next();
    // Security headers (report-only CSP to avoid breakage while rolling out)
    const api = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
    const csp = [
      "default-src 'self'",
      `connect-src 'self' ${api}`,
      "img-src 'self' data: blob:",
      "style-src 'self' 'unsafe-inline'",
      "font-src 'self' data:",
      "frame-ancestors 'none'",
      "base-uri 'self'",
    ].join('; ');
    res.headers.set('Content-Security-Policy-Report-Only', csp);
    res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
    res.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    if (process.env.NODE_ENV === 'production') {
      res.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
    }
    return res;
  }
  // Require session for all other routes
  const token = await getToken({ req, secret: process.env.NEXTAUTH_SECRET });
  if (!token) {
    const url = req.nextUrl.clone();
    url.pathname = "/signin";
    url.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(url);
  }
  const res = NextResponse.next();
  const api = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
  const csp = [
    "default-src 'self'",
    `connect-src 'self' ${api}`,
    "img-src 'self' data: blob:",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self' data:",
    "frame-ancestors 'none'",
    "base-uri 'self'",
  ].join('; ');
  res.headers.set('Content-Security-Policy-Report-Only', csp);
  res.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  if (process.env.NODE_ENV === 'production') {
    res.headers.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  }
  return res;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
