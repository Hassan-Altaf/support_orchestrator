import { Activity } from "lucide-react";
import type { TraceEntry, TraceOutcome } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

const OUTCOME_VARIANT: Record<TraceOutcome, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  retry: "warning",
  fallback: "warning",
  error: "danger",
};

export function TraceTable({ trace }: { trace: TraceEntry[] }) {
  const totalMs = trace.reduce((acc, t) => acc + t.duration_ms, 0);

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          <Activity className="h-4 w-4 text-sky-600" /> Processing trace
        </span>
      }
      subtitle={`${trace.length} nodes · ${totalMs.toLocaleString()} ms total`}
      accent="blue"
    >
      <div className="-mx-1 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-500">
              <th className="px-2 py-1.5 font-medium">Node</th>
              <th className="px-2 py-1.5 font-medium">Outcome</th>
              <th className="px-2 py-1.5 text-right font-medium">Duration</th>
              <th className="px-2 py-1.5 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {trace.map((t, i) => (
              <tr key={`${t.node}-${i}`} className="border-b border-slate-50 last:border-b-0">
                <td className="px-2 py-2 font-mono text-slate-900">{t.node}</td>
                <td className="px-2 py-2">
                  <Badge variant={OUTCOME_VARIANT[t.outcome]}>{t.outcome}</Badge>
                </td>
                <td className="px-2 py-2 text-right font-mono text-slate-700">
                  {t.duration_ms.toLocaleString()} ms
                </td>
                <td className="px-2 py-2 text-slate-600">{t.detail ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
