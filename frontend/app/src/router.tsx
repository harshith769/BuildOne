import { createRootRoute, createRoute, createRouter, Link, Outlet } from "@tanstack/react-router";

import { StatusPage } from "@/routes/StatusPage";

function Shell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center px-4">
          <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight text-ink">
            <img src="/favicon.svg" alt="" className="h-6 w-6" />
            BuildOne
          </Link>
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

const rootRoute = createRootRoute({ component: Shell, notFoundComponent: NotFound });
const statusRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: StatusPage });

export const router = createRouter({ routeTree: rootRoute.addChildren([statusRoute]) });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
