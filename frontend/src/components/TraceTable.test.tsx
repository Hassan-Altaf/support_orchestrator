import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { TraceEntry } from "@/api/types";
import { TraceTable } from "./TraceTable";

const TRACE: TraceEntry[] = [
  { node: "classify", duration_ms: 420, outcome: "ok", detail: null },
  { node: "extract", duration_ms: 511, outcome: "retry", detail: "retries=1" },
  { node: "escalation", duration_ms: 287, outcome: "fallback", detail: "RuntimeError" },
];

describe("TraceTable", () => {
  it("renders one row per trace entry with correct outcome badges", () => {
    render(<TraceTable trace={TRACE} />);

    for (const entry of TRACE) {
      expect(screen.getByText(entry.node)).toBeInTheDocument();
    }
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("retry")).toBeInTheDocument();
    expect(screen.getByText("fallback")).toBeInTheDocument();
  });

  it("shows the cumulative duration in the subtitle", () => {
    render(<TraceTable trace={TRACE} />);
    expect(screen.getByText(/3 nodes/)).toBeInTheDocument();
    expect(screen.getByText(/1,218 ms total/)).toBeInTheDocument();
  });

  it("renders an em-dash when detail is null", () => {
    render(<TraceTable trace={[TRACE[0]]} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
