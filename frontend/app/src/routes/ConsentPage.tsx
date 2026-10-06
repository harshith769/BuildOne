import { Navigate, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { useAcceptConsent, useMe } from "@/api/auth";
import { Card } from "@/components/Card";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";
import { problemOf } from "@/auth/problem";

import { TermsVersions } from "./TermsVersions";

// A constant: <Navigate> re-navigates whenever its props change identity.
const SIGN_IN_SEARCH = { return_to: "/" } as const;

// S2 (returning user): the terms or privacy notice changed, so accept the new versions to continue.
export function ConsentPage() {
  const me = useMe();
  const accept = useAcceptConsent();
  const navigate = useNavigate();
  const [accepted, setAccepted] = useState(false);

  if (me.isPending) {
    return (
      <p className="text-ink-muted" aria-live="polite">
        Loading…
      </p>
    );
  }
  if (me.isError) {
    return (
      <Card title="Updated terms">
        <ProblemMessage problem={problemOf(me.error)} />
      </Card>
    );
  }
  if (me.data === null) return <Navigate to="/sign-in" search={SIGN_IN_SEARCH} replace />;
  if (!me.data.consent_required) return <Navigate to="/" replace />;

  const { terms_version, privacy_version } = me.data;
  return (
    <Card title="We've updated our terms">
      <p className="text-ink-muted">Please review and accept the current versions to keep using BuildOne.</p>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          accept.mutate({ terms_version, privacy_version }, { onSuccess: () => void navigate({ to: "/" }) });
        }}
      >
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
          />
          <span>
            I accept the terms of use and the privacy notice.
            <TermsVersions terms={terms_version} privacy={privacy_version} />
          </span>
        </label>
        {accept.isError ? <ProblemMessage problem={problemOf(accept.error)} /> : null}
        <Button type="submit" className="w-full" disabled={!accepted || accept.isPending}>
          Accept and continue
        </Button>
      </form>
    </Card>
  );
}
