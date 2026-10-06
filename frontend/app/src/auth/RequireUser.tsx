import { useLocation, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type ReactNode } from "react";

import { useMe, type Me } from "@/api/auth";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";

import { problemOf } from "./problem";

/** Renders children only for a signed-in user who has accepted the current terms (auth-and-tenancy.md §5). */
export function RequireUser({ children }: { children: (me: Me) => ReactNode }) {
  const me = useMe();
  const navigate = useNavigate();
  // Captured once and navigated to from an effect: a <Navigate> with a fresh `search` object re-navigates
  // on every render while the router is still on this route, which loops forever.
  const [returnTo] = useState(useLocation().href);
  const redirect = me.data === null ? "sign-in" : me.data?.consent_required ? "consent" : null;

  useEffect(() => {
    if (redirect === "sign-in") void navigate({ to: "/sign-in", search: { return_to: returnTo }, replace: true });
    if (redirect === "consent") void navigate({ to: "/consent", replace: true });
  }, [redirect, returnTo, navigate]);

  if (me.isPending) {
    return (
      <p className="text-ink-muted" aria-live="polite">
        Loading…
      </p>
    );
  }
  if (me.isError) {
    return (
      <div className="mx-auto max-w-md space-y-3">
        <ProblemMessage problem={problemOf(me.error)} />
        <Button variant="outline" size="sm" onClick={() => void me.refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  if (redirect || !me.data) return null;
  return <>{children(me.data)}</>;
}
