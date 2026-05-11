import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  accent?: "blue" | "green" | "amber" | "violet" | "rose" | "slate";
  className?: string;
  children: ReactNode;
}

const ACCENT_BAR: Record<NonNullable<CardProps["accent"]>, string> = {
  blue: "bg-sky-500",
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  violet: "bg-violet-500",
  rose: "bg-rose-500",
  slate: "bg-slate-400",
};

export function Card({ title, subtitle, accent = "slate", className, children }: CardProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm",
        className,
      )}
    >
      <div className={cn("absolute inset-y-0 left-0 w-1", ACCENT_BAR[accent])} aria-hidden />
      {title && (
        <header className="border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-700">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}
