import { createRootRoute, createRoute, createRouter, Link, Outlet, useNavigate, useParams } from "@tanstack/react-router";
import { useState } from "react";

import { useMe, useSignOut } from "@/api/auth";
import { useMyOrgs } from "@/api/orgs";
import { RequireUser } from "@/auth/RequireUser";
import { Button } from "@/components/ui/button";
import { ConsentPage } from "@/routes/ConsentPage";
import { CreateOrgPage } from "@/routes/CreateOrgPage";
import { HomePage } from "@/routes/HomePage";
import { InvitePage, takeInviteToken } from "@/routes/InvitePage";
import { OrgPage } from "@/routes/OrgPage";
import { SignInPage } from "@/routes/SignInPage";
import { StatusPage } from "@/routes/StatusPage";
import { WelcomePage } from "@/routes/WelcomePage";

/** Switch between the organisations I belong to (FR-PLT-02); each screen shows one organisation's data. */
function OrgSwitcher() {
  const me = useMe();
  const orgs = useMyOrgs();
  const navigate = useNavigate();
  const params = useParams({ strict: false });
  if (!me.data || me.data.consent_required || !orgs.data || orgs.data.length === 0) return null;
  const current = typeof params.orgId === "string" ? params.orgId : "";
  return (
    <select
      aria-label="Organisation"
      className="max-w-48 rounded-lg border border-line bg-surface px-2 py-1 text-sm"
      value={current}
      onChange={(e) => {
        if (e.target.value) void navigate({ to: "/orgs/$orgId", params: { orgId: e.target.value } });
      }}
    >
      <option value="" disabled>
        Choose an organisation
      </option>
      {orgs.data.map((org) => (
        <option key={org.id} value={org.id}>
          {org.name}
        </option>
      ))}
    </select>
  );
}

function AccountMenu() {
  const me = useMe();
  const signOut = useSignOut();
  if (!me.data) return null;
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-ink-muted" data-testid="account-name">
        {me.data.display_name}
      </span>
      <Button
        variant="outline"
        size="sm"
        disabled={signOut.isPending}
        onClick={() =>
          signOut.mutate(undefined, {
            onSettled: () => window.location.assign("/sign-in?notice=signed_out"),
          })
        }
      >
        Sign out
      </Button>
    </div>
  );
}

function Shell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight text-ink">
            <img src="/favicon.svg" alt="" className="h-6 w-6" />
            BuildOne
          </Link>
          <div className="flex items-center gap-3">
            <OrgSwitcher />
            <AccountMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10">
        <Outlet />
      </main>
    </div>
  );
}

function NotFound() {
  return (
    <section className="mx-auto max-w-xl">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-ink-muted">
        <Link to="/" className="underline">
          Go to the start page
        </Link>
      </p>
    </section>
  );
}

type SignInSearch = { return_to?: string; error?: string; notice?: string };

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value !== "" ? value : undefined;
}

const rootRoute = createRootRoute({ component: Shell, notFoundComponent: NotFound });

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <RequireUser>{(me) => <HomePage me={me} />}</RequireUser>,
});

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sign-in",
  validateSearch: (search: Record<string, unknown>): SignInSearch => ({
    return_to: optionalString(search.return_to),
    error: optionalString(search.error),
    notice: optionalString(search.notice),
  }),
  component: function SignInRoute() {
    const search = signInRoute.useSearch();
    return <SignInPage returnTo={search.return_to} error={search.error} notice={search.notice} />;
  },
});

const welcomeRoute = createRoute({ getParentRoute: () => rootRoute, path: "/welcome", component: WelcomePage });
const consentRoute = createRoute({ getParentRoute: () => rootRoute, path: "/consent", component: ConsentPage });
const createOrgRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/orgs/new",
  component: () => <RequireUser>{() => <CreateOrgPage />}</RequireUser>,
});

const orgRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/orgs/$orgId",
  component: function OrgRoute() {
    const { orgId } = orgRoute.useParams();
    return <RequireUser>{(me) => <OrgPage key={orgId} orgId={orgId} me={me} />}</RequireUser>;
  },
});

const inviteRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/invite",
  component: function InviteRoute() {
    // Before RequireUser: the token must be taken out of the URL fragment before any sign-in redirect.
    const [token] = useState(takeInviteToken);
    return <RequireUser>{(me) => <InvitePage token={token} me={me} />}</RequireUser>;
  },
});

const statusRoute = createRoute({ getParentRoute: () => rootRoute, path: "/status", component: StatusPage });

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    homeRoute,
    signInRoute,
    welcomeRoute,
    consentRoute,
    createOrgRoute,
    orgRoute,
    inviteRoute,
    statusRoute,
  ]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
