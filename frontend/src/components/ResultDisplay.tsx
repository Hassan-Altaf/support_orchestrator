import type { TicketProcessingResult } from "@/api/types";
import { ClassificationCard } from "@/components/ClassificationCard";
import { CustomerResponseCard } from "@/components/CustomerResponseCard";
import { ErrorBanner } from "@/components/ErrorBanner";
import { EscalationCard } from "@/components/EscalationCard";
import { ExtractedInfoCard } from "@/components/ExtractedInfoCard";
import { InternalSummaryCard } from "@/components/InternalSummaryCard";
import { TraceTable } from "@/components/TraceTable";

export function ResultDisplay({ result }: { result: TicketProcessingResult }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-slate-500">
        <span>
          <span className="font-medium text-slate-700">request_id:</span>{" "}
          <span className="font-mono text-slate-700">{result.request_id}</span>
        </span>
        <span>
          processed{" "}
          <time className="font-mono">
            {new Date(result.processed_at).toLocaleString()}
          </time>
        </span>
      </div>

      {result.recovered_errors.length > 0 && (
        <ErrorBanner
          title={`Recovered from ${result.recovered_errors.length} node failure${
            result.recovered_errors.length === 1 ? "" : "s"
          }`}
          detail={result.recovered_errors.join("  •  ")}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <ClassificationCard data={result.classification} />
        <ExtractedInfoCard data={result.extracted_info} />
        {result.escalation_context && (
          <div className="lg:col-span-2">
            <EscalationCard data={result.escalation_context} />
          </div>
        )}
        <div className="lg:col-span-2">
          <CustomerResponseCard text={result.customer_response} />
        </div>
        <div className="lg:col-span-2">
          <InternalSummaryCard data={result.internal_summary} />
        </div>
        <div className="lg:col-span-2">
          <TraceTable trace={result.processing_trace} />
        </div>
      </div>
    </div>
  );
}
