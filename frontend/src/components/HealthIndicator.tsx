import { useHealth } from "@/hooks/useHealth";
import { cn } from "@/lib/cn";

export function HealthIndicator() {
  const { data, isError, isLoading } = useHealth();

  let label: string;
  let dot: string;

  if (isLoading) {
    label = "checking…";
    dot = "bg-slate-300";
  } else if (isError || !data || data.status !== "ok") {
    label = "unreachable";
    dot = "bg-rose-500";
  } else {
    label = `online · v${data.version}`;
    dot = "bg-emerald-500";
  }

  return (
    <div
      className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200"
      role="status"
      aria-live="polite"
    >
      <span className={cn("h-2 w-2 rounded-full", dot)} aria-hidden />
      <span>{label}</span>
    </div>
  );
}
