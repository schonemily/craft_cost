"use client";
import * as React from "react";
import { SessionProvider as NextAuthSessionProvider, useSession } from "next-auth/react";

function PersistToken() {
  const { data } = useSession();
  React.useEffect(() => {
    try {
      const t = (data as any)?.apiToken;
      if (t) localStorage.setItem("apiToken", String(t));
      else localStorage.removeItem("apiToken");
    } catch {}
  }, [data]);
  return null;
}

export default function SessionProvider({ children }: { children: React.ReactNode }) {
  return <NextAuthSessionProvider><PersistToken />{children}</NextAuthSessionProvider>;
}
