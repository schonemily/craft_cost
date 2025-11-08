"use client";
import * as React from "react";

export type MotionContextValue = {
  reduced: boolean;
  setReduced: (v: boolean) => void;
};

const MotionContext = React.createContext<MotionContextValue | null>(null);

function getSystemPrefers(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function MotionProvider({ children }: { children: React.ReactNode }) {
  const [reduced, setReduced] = React.useState<boolean>(() => {
    if (typeof window === "undefined") return getSystemPrefers();
    try {
      const saved = localStorage.getItem("motionReduced");
      if (saved != null) return saved === "1";
    } catch {}
    return getSystemPrefers();
  });

  React.useEffect(() => {
    try { localStorage.setItem("motionReduced", reduced ? "1" : "0"); } catch {}
  }, [reduced]);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = () => setReduced((prev) => (localStorage.getItem("motionReduced") != null ? prev : mq.matches));
    mq.addEventListener?.("change", onChange);
    return () => mq.removeEventListener?.("change", onChange);
  }, []);

  return <MotionContext.Provider value={{ reduced, setReduced }}>{children}</MotionContext.Provider>;
}

export function useMotion() {
  const ctx = React.useContext(MotionContext);
  if (!ctx) return { reduced: false, setReduced: () => {} } as MotionContextValue;
  return ctx;
}
