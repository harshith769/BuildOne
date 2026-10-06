import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { useCompleteSignup, useDeclineSignup, useSignupProfile } from "@/api/auth";
import { Card } from "@/components/Card";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";
import { problemOf } from "@/auth/problem";

import { TermsVersions } from "./TermsVersions";

// S2 (first sign-in): confirm 18+ and accept the terms. The account is created only on "Create my account".
export function WelcomePage() {
  const profile = useSignupProfile();
  const complete = useCompleteSignup();
  const decline = useDeclineSignup();
  const navigate = useNavigate();
  const [adult, setAdult] = useState(false);
  const [accepted, setAccepted] = useState(false);

  if (profile.isPending) {
    return (
      <p className="text-ink-muted" aria-live="polite">
        Loading…
      </p>
    );
  }
  if (profile.isError) {
    return (
      <Card title="Welcome">
        <ProblemMessage problem={problemOf(profile.error)} />
        <Button variant="outline" size="sm" onClick={() => void profile.refetch()}>
          Try again
        </Button>
      </Card>
    );
  }
  if (profile.data === null) {
    return (
      <Card title="Your sign-up has expired">
        <p className="text-ink-muted">For your security, unfinished sign-ups expire after 30 minutes.</p>
        <Link to="/sign-in" className="underline">
          Sign in again
        </Link>
      </Card>
    );
  }

  const { data } = profile;
  const busy = complete.isPending || decline.isPending;
  return (
    <Card title="Welcome to BuildOne">
      <p>
        You're signing up as <strong>{data.display_name}</strong> ({data.email}).
      </p>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          complete.mutate(
            { terms_version: data.terms_version, privacy_version: data.privacy_version },
            { onSuccess: (result) => void navigate({ href: result.return_to }) },
          );
        }}
      >
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4"
            checked={adult}
            onChange={(e) => setAdult(e.target.checked)}
          />
          <span>I am 18 years old or older.</span>
        </label>
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
          />
          <span>
            I accept the terms of use and the privacy notice.
            <TermsVersions terms={data.terms_version} privacy={data.privacy_version} />
          </span>
        </label>
        {complete.isError ? <ProblemMessage problem={problemOf(complete.error)} /> : null}
        <Button type="submit" className="w-full" disabled={!adult || !accepted || busy}>
          Create my account
        </Button>
      </form>
      <div className="border-t border-line pt-4">
        <Button
          variant="ghost"
          className="w-full"
          disabled={busy}
          onClick={() =>
            decline.mutate(undefined, {
              onSettled: () => void navigate({ to: "/sign-in", search: { notice: "under_18" } }),
            })
          }
        >
          I'm under 18
        </Button>
      </div>
    </Card>
  );
}
