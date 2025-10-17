import * as React from "react";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
  size?: "sm" | "md";
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant = "primary", size = "md", ...props }, ref) => {
    const base = "inline-flex items-center rounded-md font-medium transition disabled:opacity-50";
    const tone =
      variant === "primary"
        ? "bg-brand-600 text-white hover:bg-brand-700"
        : "border border-[var(--border)]/60 text-white hover:border-brand-600/50";
    const pad = size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-2 text-sm";
    return (
      <button ref={ref} className={`${base} ${tone} ${pad} ${className}`} {...props} />
    );
  }
);
Button.displayName = "Button";
