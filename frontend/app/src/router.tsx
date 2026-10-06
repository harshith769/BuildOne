import { createRootRoute, createRoute, createRouter, Link, Outlet } from "@tanstack/react-router";

import { useMe, useSignOut } from "@/api/auth";
import { RequireUser } from "@/auth/RequireUser";
import { Button } from "@/components/ui/button";
import { ConsentPage } from "@/routes/ConsentPage";
import { HomePage } from "@/routes/HomePage";
import { SignInPage } from "@/routes/SignInPage";
import { StatusPage } from "@/routes/StatusPage";
import { WelcomePage } from "@/routes/WelcomePage";

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
          <AccountMenu />
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
const statusRoute = createRoute({ getParentRoute: () => rootRoute, path: "/status", component: StatusPage });

export const router = createRouter({
  routeTree: rootRoute.addChildren([homeRoute, signInRoute, welcomeRoute, consentRoute, statusRoute]),
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
