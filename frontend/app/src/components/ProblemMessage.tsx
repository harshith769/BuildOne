import type { Problem } from "@/api/client";

/** Error state for any data view: plain message plus the request ID to quote to support. */
export function ProblemMessage({ problem }: { problem: Problem }) {
  return (
    <div role="alert" className="rounded-card border border-bad/40 bg-bad/5 p-4 text-sm">
      <p className="font-medium text-bad">{problem.title}</p>
      {problem.detail && problem.detail !== problem.title ? <p className="mt-1 text-ink">{problem.detail}</p> : null}
      {problem.request_id ? (
        <p className="mt-2 text-xs text-ink-muted">
          Request ID <code className="font-mono">{problem.request_id}</code>
        </p>
      ) : null}
    </div>
  );
}
