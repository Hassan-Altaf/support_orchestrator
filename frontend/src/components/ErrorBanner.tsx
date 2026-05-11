import { AlertTriangle } from "lucide-react";

interface ErrorBannerProps {
  title: string;
  detail?: string | null;
  requestId?: string | null;
}

export function ErrorBanner({ title, detail, requestId }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm"
    >
      <AlertTriangle className="mt-0.5 h-5 w-5 flex-none text-rose-600" aria-hidden />
      <div className="min-w-0">
        <p className="font-semibold text-rose-900">{title}</p>
        {detail && <p className="mt-1 break-words text-rose-800">{detail}</p>}
        {requestId && (
          <p className="mt-1 font-mono text-xs text-rose-700">request_id: {requestId}</p>
        )}
      </div>
    </div>
  );
}
