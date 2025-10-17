import * as React from "react";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  size?: "sm" | "md";
};

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className = "", size = "md", ...props }, ref) => {
    const base = "rounded-md bg-black/20 text-sm text-white placeholder:text-[var(--muted)] outline-none focus:ring-2 focus:ring-brand-600/40";
    const pad = size === "sm" ? "px-2 py-1" : "px-3 py-2";
    return <input ref={ref} className={`${base} ${pad} ${className}`} {...props} />;
  }
);
Input.displayName = "Input";
