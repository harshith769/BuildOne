import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

import { signInUrl, useMe } from "@/api/auth";
import { Card } from "@/components/Card";
import { Button } from "@/components/ui/button";

/** Messages for `?error=` (set by the API's callback) and `?notice=` (set by the app). */
const MESSAGES: Record<string, string> = {
  sign_in_failed: "Sign-in didn't complete. Please try again.",
  sign_in_expired: "Sign-in took too long and timed out. Please try again.",
  sign_in_cancelled: "Sign-in was cancelled.",
  account_pending_deletion:
    "This account is scheduled for deletion. Contact support within 30 days if you want to keep it.",
  under_18: "BuildOne is only for people aged 18 or older. We didn't save any of your details.",
  signed_out: "You're signed out.",
};

/** A same-app path or "/" (the API validates again; this only avoids a pointless round trip). */
function safeReturnTo(value: string | undefined): string {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\") ? value : "/";
}

// S1: Sign-in. The identity provider handles email codes/links and Google; this screen only starts the flow.
export function SignInPage({ returnTo, error, notice }: { returnTo?: string; error?: string; notice?: string }) {
  const me = useMe();
  const navigate = useNavigate();
  const signedIn = Boolean(me.data);
  useEffect(() => {
    // Already signed in (e.g. back button after sign-in): go where the user was heading.
    if (signedIn) void navigate({ href: safeReturnTo(returnTo), replace: true });
  }, [signedIn, returnTo, navigate]);
  if (signedIn) return null;

  const message = (error && (MESSAGES[error] ?? MESSAGES.sign_in_failed)) || (notice && MESSAGES[notice]);
  return (
    <Card title="Sign in to BuildOne">
      {message ? (
        <p role={error ? "alert" : "status"} className={error ? "text-bad" : "text-ink-muted"}>
          {message}
        </p>
      ) : null}
      <p className="text-ink-muted">Sign in with your email or Google account. No password needed.</p>
      <Button
        className="w-full"
        onClick={() => {
          window.location.assign(signInUrl(safeReturnTo(returnTo)));
        }}
      >
        Continue
      </Button>
    </Card>
  );
}
