import { ShieldAlert, ShieldCheck } from "lucide-react";
import type { Classification, Priority } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

const PRIORITY_VARIANT: Record<Priority, "neutral" | "info" | "warning" | "danger"> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "danger",
};

export function ClassificationCard({ data }: { data: Classification }) {
  const confidencePct = Math.round(data.confidence * 100);

  return (
    <Card title="Classification" accent="blue">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge variant="purple">{data.category.replaceAll("_", " ")}</Badge>
        <Badge variant={PRIORITY_VARIANT[data.priority]}>priority: {data.priority}</Badge>
        {data.escalation_required ? (
          <Badge variant="danger">
            <ShieldAlert className="mr-1 h-3 w-3" />
            escalation required
          </Badge>
        ) : (
          <Badge variant="success">
            <ShieldCheck className="mr-1 h-3 w-3" />
            no escalation
          </Badge>
        )}
      </div>

      <div className="mb-3">
        <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
          <span>Confidence</span>
          <span className="font-mono">{confidencePct}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100" aria-hidden>
          <div
            className="h-full bg-slate-700"
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      <p className="text-sm leading-relaxed text-slate-700">
        <span className="font-medium text-slate-900">Reasoning:</span> {data.reasoning}
      </p>
    </Card>
  );
}
