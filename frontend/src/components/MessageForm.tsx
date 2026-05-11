import { useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { SAMPLE_MESSAGES } from "@/lib/samples";

interface MessageFormProps {
  onSubmit: (message: string) => void;
  pending: boolean;
}

const MIN_LEN = 5;
const MAX_LEN = 10_000;

export function MessageForm({ onSubmit, pending }: MessageFormProps) {
  const [message, setMessage] = useState("");

  const trimmedLength = message.trim().length;
  const tooShort = trimmedLength > 0 && trimmedLength < MIN_LEN;
  const tooLong = trimmedLength > MAX_LEN;
  const canSubmit = !pending && trimmedLength >= MIN_LEN && !tooLong;

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (canSubmit) onSubmit(message.trim());
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="message" className="text-sm font-semibold text-slate-800">
          Customer support message
        </label>
        <select
          aria-label="Load a sample message"
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:border-slate-500 focus:outline-none"
          value=""
          disabled={pending}
          onChange={(e) => {
            const sample = SAMPLE_MESSAGES.find((s) => s.id === e.target.value);
            if (sample) setMessage(sample.message);
          }}
        >
          <option value="">Load a sample…</option>
          {SAMPLE_MESSAGES.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
      <textarea
        id="message"
        rows={6}
        value={message}
        disabled={pending}
        placeholder="Paste the customer's message here, or pick a sample above."
        className="w-full resize-y rounded-lg border border-slate-300 bg-white p-3 text-sm leading-relaxed text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200 disabled:opacity-60"
        onChange={(e) => setMessage(e.target.value)}
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-slate-500">
          {tooShort && (
            <span className="text-rose-600">Message must be at least {MIN_LEN} characters.</span>
          )}
          {tooLong && (
            <span className="text-rose-600">
              Message exceeds the {MAX_LEN.toLocaleString()}-character limit.
            </span>
          )}
          {!tooShort && !tooLong && (
            <span>
              {trimmedLength.toLocaleString()} / {MAX_LEN.toLocaleString()} characters
            </span>
          )}
        </div>
        <Button type="submit" disabled={!canSubmit}>
          {pending ? <Spinner /> : <Send className="h-4 w-4" />}
          {pending ? "Processing…" : "Process message"}
        </Button>
      </div>
    </form>
  );
}
