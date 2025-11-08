"use client";
import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { useMotion } from "./MotionProvider";

export default function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { reduced } = useMotion();
  const animProps = reduced
    ? { initial: false as const, animate: {} as any, exit: {} as any, transition: { duration: 0 } }
    : { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -6 }, transition: { duration: 0.18, ease: "easeOut" } };
  return (
    <AnimatePresence mode="wait">
      <motion.div key={pathname} {...(animProps as any)}>
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
