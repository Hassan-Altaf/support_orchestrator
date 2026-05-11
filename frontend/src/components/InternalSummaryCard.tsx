import { ClipboardList } from "lucide-react";
import type { InternalSummary } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

export function InternalSummaryCard({ data }: { data: InternalSummary }) {
  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          <ClipboardList className="h-4 w-4 text-amber-600" /> Internal handoff
        </span>
      }
      subtitle="Engineer-facing brief"
      accent="amber"
    >
      <p className="mb-3 text-base font-medium leading-snug text-slate-900">{data.headline}</p>
      <dl className="mb-4 grid gap-3 text-sm sm:grid-cols-[max-content_1fr] sm:gap-x-4">
        <dt className="font-medium text-slate-600">Intent</dt>
        <dd className="text-slate-800">{data.customer_intent}</dd>

        <dt className="font-medium text-slate-600">Diagnostic</dt>
        <dd className="text-slate-800">{data.diagnostic_notes}</dd>

        <dt className="font-medium text-slate-600">Handoff team</dt>
        <dd>
          <Badge variant="purple">{data.handoff_team}</Badge>
        </dd>
      </dl>
      <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
        Recommended actions
      </h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-800">
        {data.recommended_actions.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
    </Card>
  );
}
