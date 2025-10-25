import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import EmailProvider from "next-auth/providers/email";
import { PrismaAdapter } from "@next-auth/prisma-adapter";
import prisma from "../../../../lib/prisma";

const apiExternal = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8010";
const apiInternal = process.env.API_INTERNAL_URL || apiExternal;

const handler = NextAuth({
  secret: process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt" },
  pages: {
    signIn: "/signin",
  },
  adapter: PrismaAdapter(prisma) as any,
  providers: [
    EmailProvider({
      server: {
        host: process.env.SMTP_HOST || "mailhog",
        port: Number(process.env.SMTP_PORT || 1025),
        auth: (process.env.SMTP_USER && process.env.SMTP_PASS) ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS } : undefined,
        secure: String(process.env.SMTP_USE_SSL || "false").toLowerCase() === "true",
      },
      from: process.env.EMAIL_FROM || "noreply@craft_cost.local",
      maxAge: 60 * 60, // 1h magic link
    }),
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials: any) {
        if (!credentials?.email || !credentials?.password) return null;
        try {
          const res = await fetch(`${apiInternal}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: credentials.email, password: credentials.password }),
          });
          if (!res.ok) return null;
          const data = await res.json();
          const token = (data as any)?.token || (data as any)?.access_token;
          if (!token) return null;
          // Prefer user from auth response if present
          const u1 = (data as any)?.user || {};
          if (u1 && (u1.id || u1.email)) {
            return {
              id: String(u1.id ?? ""),
              email: String(u1.email ?? credentials.email),
              role: String(u1.role ?? "user"),
              plan: String(u1.plan ?? "free"),
              apiToken: token,
            } as any;
          }
          // Fallback to /v1/auth/me
          const me = await fetch(`${apiInternal}/v1/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
          if (!me.ok) {
            return { id: "0", email: String(credentials.email), role: "user", plan: "free", apiToken: token } as any;
          }
          const meData = await me.json();
          const u = meData?.user || {};
          return {
            id: String(u.id ?? ""),
            email: String(u.email ?? credentials.email),
            role: String(u.role ?? "user"),
            plan: String(u.plan ?? "free"),
            apiToken: token,
          } as any;
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }: any) {
      if (user) {
        (token as any).apiToken = (user as any).apiToken;
        (token as any).role = (user as any).role;
        (token as any).plan = (user as any).plan;
      }
      // Mint API token if missing and we have an email
      if (!(token as any).apiToken && token?.email) {
        try {
          const mintRes = await fetch(`${apiInternal}/v1/auth/mint`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Internal-Secret": String(process.env.MINT_TOKEN_SECRET || "dev_mint_secret"),
            },
            body: JSON.stringify({ email: token.email }),
          });
          if (mintRes.ok) {
            const mint = await mintRes.json();
            const apiToken = mint?.access_token as string | undefined;
            if (apiToken) {
              (token as any).apiToken = apiToken;
              // enrich role/plan
              const meRes = await fetch(`${apiInternal}/v1/auth/me`, { headers: { Authorization: `Bearer ${apiToken}` } });
              if (meRes.ok) {
                const me = await meRes.json();
                (token as any).role = me?.user?.role || (token as any).role;
                (token as any).plan = me?.user?.plan || (token as any).plan;
              }
            }
          }
        } catch {}
      }
      return token;
    },
    async session({ session, token }: any) {
      (session as any).apiToken = (token as any).apiToken;
      if (session.user) {
        (session.user as any).role = (token as any).role;
        (session.user as any).plan = (token as any).plan;
      }
      return session;
    },
  },
});

export { handler as GET, handler as POST };
