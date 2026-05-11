import { Github } from "lucide-react";
import { ApiError } from "@/api/client";
import { ErrorBanner } from "@/components/ErrorBanner";
import { HealthIndicator } from "@/components/HealthIndicator";
import { MessageForm } from "@/components/MessageForm";
import { ResultDisplay } from "@/components/ResultDisplay";
import { useProcessSupport } from "@/hooks/useProcessSupport";

export function App() {
  const mutation = useProcessSupport();

  const error = mutation.error;
  const isApiError = error instanceof ApiError;

  return (
    <div className="min-h-full bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div>
            <h1 className="text-base font-semibold text-slate-900">Support Orchestrator</h1>
            <p className="text-xs text-slate-500">
              FastAPI + LangGraph multi-step pipeline · this UI is a thin client.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/Hassan-Altaf/support_orchestrator.git"
              target="_blank"
              rel="noreferrer"
              className="hidden text-slate-400 hover:text-slate-700 sm:inline"
              aria-label="GitHub"
            >
              <Github className="h-4 w-4" />
            </a>
            <HealthIndicator />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-4 px-4 py-6 sm:px-6 sm:py-8">
        <MessageForm
          pending={mutation.isPending}
          onSubmit={(message) => mutation.mutate({ message })}
        />

        {error && (
          <ErrorBanner
            title={
              isApiError ? `Request failed (HTTP ${error.status})` : "Request failed"
            }
            detail={isApiError ? (error.body?.detail ?? error.message) : error.message}
            requestId={isApiError ? error.body?.request_id : null}
          />
        )}

        {mutation.data && <ResultDisplay result={mutation.data} />}

        {!mutation.data && !mutation.isPending && !error && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
            <p className="font-medium text-slate-700">No result yet.</p>
            <p className="mt-1">
              Paste a customer message above (or pick a sample) and submit to see the full
              pipeline.
            </p>
          </div>
        )}
      </main>

      <footer className="mx-auto max-w-5xl px-4 py-6 text-center text-xs text-slate-400 sm:px-6">
        <p>
          Trace, classification, and escalation are computed server-side by the LangGraph
          pipeline. This UI just renders the API response.
        </p>
      </footer>
    </div>
  );
}
