import { Link } from "@tanstack/react-router";

import type { Me } from "@/api/auth";
import { useMyOrgs } from "@/api/orgs";
import { problemOf } from "@/auth/problem";
import { Disclaimer } from "@/components/Disclaimer";
import { ProblemMessage } from "@/components/ProblemMessage";

import { ORG_TYPE_LABELS, ROLE_LABELS } from "./orgLabels";

// Signed-in home: the organisations I belong to, or a start for creating one.
export function HomePage({ me }: { me: Me }) {
  const orgs = useMyOrgs();
  return (
    <section className="mx-auto w-full max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome, {me.display_name}</h1>
      <p className="text-ink-muted">
        You're signed in as <span data-testid="me-email">{me.email}</span>.
      </p>
      {orgs.isPending ? (
        <p className="text-ink-muted" aria-live="polite">
          Loading your organisations…
        </p>
      ) : orgs.isError ? (
        <ProblemMessage problem={problemOf(orgs.error)} />
      ) : orgs.data.length === 0 ? (
        <div className="rounded-card border border-line bg-surface p-5">
          <p>You don't belong to an organisation yet.</p>
          <p className="mt-1 text-sm text-ink-muted">
            Create one for your company or founding team, or open an invitation link someone sent you.
          </p>
          <Link to="/orgs/new" className="mt-3 inline-block font-medium underline">
            Create an organisation
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          <h2 className="font-medium">Your organisations</h2>
          <ul className="divide-y divide-line rounded-card border border-line bg-surface">
            {orgs.data.map((org) => (
              <li key={org.id} className="flex items-center justify-between p-3">
                <Link to="/orgs/$orgId" params={{ orgId: org.id }} className="font-medium underline">
                  {org.name}
                </Link>
                <span className="text-sm text-ink-muted">
                  {ORG_TYPE_LABELS[org.type] ?? org.type} · {ROLE_LABELS[org.role] ?? org.role}
                </span>
              </li>
            ))}
          </ul>
          <Link to="/orgs/new" className="inline-block text-sm underline">
            Create another organisation
          </Link>
        </div>
      )}
      <Disclaimer />
    </section>
  );
}
