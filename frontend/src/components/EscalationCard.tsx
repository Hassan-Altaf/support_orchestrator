import { Siren } from "lucide-react";
import type { EscalationContext } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

function severityVariant(level: number): "neutral" | "info" | "warning" | "danger" {
  if (level >= 5) return "danger";
  if (level === 4) return "warning";
  if (level === 3) return "info";
  return "neutral";
}

function formatSla(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) return `${(minutes / 60).toFixed(minutes % 60 ? 1 : 0)} h`;
  return `${(minutes / (60 * 24)).toFixed(1)} d`;
}

export function EscalationCard({ data }: { data: EscalationContext }) {
  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          <Siren className="h-4 w-4 text-rose-500" /> Escalation
        </span>
      }
      accent="rose"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge variant={severityVariant(data.severity_level)}>
          severity {data.severity_level}/5
        </Badge>
        <Badge variant="purple">team: {data.suggested_team}</Badge>
        <Badge variant="warning">SLA: {formatSla(data.sla_minutes)}</Badge>
      </div>
      <p className="text-sm leading-relaxed text-slate-700">
        <span className="font-medium text-slate-900">Reason:</span> {data.reason}
      </p>
    </Card>
  );
}
