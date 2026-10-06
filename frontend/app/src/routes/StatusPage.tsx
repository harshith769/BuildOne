import { useReadiness, type Readiness } from "@/api/health";
import { ApiError } from "@/api/client";
import { Disclaimer } from "@/components/Disclaimer";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";

const CHECK_LABELS: Record<string, string> = {
  database: "Database",
  migrations: "Database migrations",
  queue: "Background jobs",
};

function CheckRow({ name, status }: { name: string; status: string }) {
  const ok = status === "ok";
  return (
    <li className="flex items-center justify-between border-b border-line py-3 last:border-b-0">
      <span>{CHECK_LABELS[name] ?? name}</span>
      <span className={ok ? "font-medium text-ok" : "font-medium text-bad"}>{ok ? "Working" : "Not working"}</span>
    </li>
  );
}

function Checks({ readiness }: { readiness: Readiness }) {
  const ready = readiness.status === "ready";
  return (
    <>
      <p className={ready ? "text-ok" : "text-warn"} data-testid="readiness-summary">
        {ready ? "All systems are working." : "Some parts of BuildOne are not working right now."}
      </p>
      <ul className="mt-4">
        {Object.entries(readiness.checks).map(([name, status]) => (
          <CheckRow key={name} name={name} status={status} />
        ))}
      </ul>
    </>
  );
}

export function StatusPage() {
  const query = useReadiness();

  return (
    <section className="mx-auto w-full max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">System status</h1>
      <p className="mt-1 text-sm text-ink-muted">
        This page confirms the app can reach the API. Product screens arrive from milestone M8.
      </p>

      <div className="mt-6 rounded-card border border-line bg-surface p-5 shadow-sm">
        {query.isPending ? (
          <p className="text-ink-muted" aria-live="polite">
            Checking…
          </p>
        ) : query.isError ? (
          <div className="space-y-3">
            <ProblemMessage
              problem={
                query.error instanceof ApiError
                  ? query.error.problem
                  : { title: "Something went wrong", status: 0, code: "unknown" }
              }
            />
            <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
              Try again
            </Button>
          </div>
        ) : (
          <Checks readiness={query.data} />
        )}
      </div>

      <div className="mt-6">
        <Disclaimer />
      </div>
    </section>
  );
}
