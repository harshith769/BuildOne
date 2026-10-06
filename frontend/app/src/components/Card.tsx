import type { ReactNode } from "react";

/** The page card used by the sign-in and account screens. */
export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mx-auto w-full max-w-md">
      <div className="rounded-card border border-line bg-surface p-6 shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <div className="mt-4 space-y-4">{children}</div>
      </div>
    </section>
  );
}
