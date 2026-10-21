import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
}

export function Button({ variant = "primary", size = "md", loading, children, disabled, type = "button", className = "", ...props }: PropsWithChildren<ButtonProps>) {
  return (
    <button {...props} type={type} disabled={loading || disabled} aria-busy={loading || undefined}
      className={`button button-${variant} ${size === "sm" ? "button-sm" : ""} ${className}`}>
      {loading ? "Working…" : children}
    </button>
  );
}
