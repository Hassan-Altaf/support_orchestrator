import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Variant = "neutral" | "info" | "success" | "warning" | "danger" | "purple";

interface BadgeProps {
  variant?: Variant;
  className?: string;
  children: ReactNode;
}

const STYLES: Record<Variant, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  info: "bg-sky-100 text-sky-800 ring-sky-200",
  success: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  warning: "bg-amber-100 text-amber-900 ring-amber-200",
  danger: "bg-rose-100 text-rose-800 ring-rose-200",
  purple: "bg-violet-100 text-violet-800 ring-violet-200",
};

export function Badge({ variant = "neutral", className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        STYLES[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
