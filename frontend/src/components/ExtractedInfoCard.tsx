import type { ExtractedInfo, Urgency } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";

const URGENCY_VARIANT: Record<Urgency, "neutral" | "info" | "warning" | "danger"> = {
  not_urgent: "neutral",
  normal: "info",
  urgent: "warning",
  immediate: "danger",
};

export function ExtractedInfoCard({ data }: { data: ExtractedInfo }) {
  return (
    <Card title="Extracted info" accent="violet">
      <dl className="grid gap-3 text-sm sm:grid-cols-[max-content_1fr] sm:gap-x-4">
        <dt className="font-medium text-slate-600">Product area</dt>
        <dd className="font-mono text-slate-900">{data.product_area}</dd>

        <dt className="font-medium text-slate-600">Urgency</dt>
        <dd>
          <Badge variant={URGENCY_VARIANT[data.urgency]}>
            {data.urgency.replaceAll("_", " ")}
          </Badge>
        </dd>

        <dt className="font-medium text-slate-600">Summary</dt>
        <dd className="text-slate-800">{data.issue_summary}</dd>

        <dt className="font-medium text-slate-600">Tags</dt>
        <dd className="flex flex-wrap gap-1.5">
          {data.suggested_tags.map((t) => (
            <Badge key={t} variant="neutral">
              {t}
            </Badge>
          ))}
        </dd>

        {data.affected_features.length > 0 && (
          <>
            <dt className="font-medium text-slate-600">Affected features</dt>
            <dd className="flex flex-wrap gap-1.5">
              {data.affected_features.map((f) => (
                <Badge key={f} variant="info">
                  {f}
                </Badge>
              ))}
            </dd>
          </>
        )}
      </dl>
    </Card>
  );
}
