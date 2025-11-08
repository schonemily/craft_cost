import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import GitHubProvider from "next-auth/providers/github";
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
    GoogleProvider({
      clientId: String(process.env.GOOGLE_CLIENT_ID || ""),
      clientSecret: String(process.env.GOOGLE_CLIENT_SECRET || ""),
      allowDangerousEmailAccountLinking: true,
    }),
    GitHubProvider({
      clientId: String(process.env.GITHUB_CLIENT_ID || ""),
      clientSecret: String(process.env.GITHUB_CLIENT_SECRET || ""),
      allowDangerousEmailAccountLinking: true,
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
        (session.user as any).id = (token as any).sub;
      }
      return session;
    },
  },
});

export { handler as GET, handler as POST };
