import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import type { Me } from "@/api/auth";
import { useAcceptInvitation, useInvitationPreview } from "@/api/orgs";
import { problemOf } from "@/auth/problem";
import { Card } from "@/components/Card";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";

import { ORG_TYPE_LABELS, ROLE_LABELS } from "./orgLabels";

const STORAGE_KEY = "bo_invite_token";

/**
 * Invitation links carry the token in the fragment (`/invite#token=...`), which browsers never send to a
 * server. It's kept in sessionStorage (this tab only) so it survives signing in, then removed from the URL.
 */
export function takeInviteToken(): string | null {
  const match = /(?:^|&)token=([^&]+)/.exec(window.location.hash.slice(1));
  if (match?.[1]) {
    const token = decodeURIComponent(match[1]);
    try {
      sessionStorage.setItem(STORAGE_KEY, token);
    } catch {
      // storage unavailable: the token still works for this page load
    }
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    return token;
  }
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function forgetInviteToken() {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing to forget
  }
}

export function InvitePage({ token, me }: { token: string | null; me: Me }) {
  const preview = useInvitationPreview(token);
  const accept = useAcceptInvitation();
  const navigate = useNavigate();
  const [confirmMismatch, setConfirmMismatch] = useState(false);

  if (!token) {
    return (
      <Card title="Invitation link incomplete">
        <p className="text-ink-muted">Open the full link from your invitation again.</p>
      </Card>
    );
  }
  if (preview.isPending) {
    return (
      <p className="text-ink-muted" aria-live="polite">
        Checking your invitation…
      </p>
    );
  }
  if (preview.isError) {
    const problem = problemOf(preview.error);
    return (
      <Card title="This invitation can't be used">
        {problem.status === 404 ? (
          <p className="text-ink-muted">It's invalid, expired or already used. Ask for a new invitation.</p>
        ) : (
          <ProblemMessage problem={problem} />
        )}
        <Link to="/" className="underline">
          Go to the start page
        </Link>
      </Card>
    );
  }

  const invite = preview.data;
  const needsConfirmation = !invite.email_matches;
  return (
    <Card title={`Join ${invite.org_name}`}>
      <p>
        You're invited to <strong>{invite.org_name}</strong> ({ORG_TYPE_LABELS[invite.org_type] ?? invite.org_type})
        as <strong>{ROLE_LABELS[invite.role] ?? invite.role}</strong>.
      </p>
      {needsConfirmation ? (
        <label className="flex items-start gap-3 rounded-card border border-warn/40 bg-warn/5 p-3 text-sm">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4"
            checked={confirmMismatch}
            onChange={(e) => setConfirmMismatch(e.target.checked)}
          />
          <span>
            This invitation was sent to {invite.email}, but you're signed in as {me.email}. Accept it with this
            account anyway.
          </span>
        </label>
      ) : null}
      {accept.isError ? <ProblemMessage problem={problemOf(accept.error)} /> : null}
      <Button
        className="w-full"
        disabled={accept.isPending || (needsConfirmation && !confirmMismatch)}
        onClick={() =>
          accept.mutate(
            { token, confirm_email_mismatch: confirmMismatch },
            {
              onSuccess: (org) => {
                forgetInviteToken();
                void navigate({ to: "/orgs/$orgId", params: { orgId: org.id } });
              },
            },
          )
        }
      >
        Accept invitation
      </Button>
    </Card>
  );
}
