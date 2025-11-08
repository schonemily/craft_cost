"use client";
import * as React from "react";
import { useMotion } from "./MotionProvider";

export default function MotionToggle() {
  const { reduced, setReduced } = useMotion();
  return (
    <button
      type="button"
      onClick={() => setReduced(!reduced)}
      className="rounded border border-[var(--border)]/60 px-2 py-1 text-xs hover:bg-white/5"
      aria-pressed={reduced ? "true" : "false"}
      title={reduced ? "Enable animations" : "Reduce motion"}
    >
      {reduced ? "Motion: Off" : "Motion: On"}
    </button>
  );
}
