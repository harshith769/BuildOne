import type { Me } from "@/api/auth";
import { Disclaimer } from "@/components/Disclaimer";

// Signed-in home. Organisations (create a team or company) arrive in milestone M3.
export function HomePage({ me }: { me: Me }) {
  return (
    <section className="mx-auto w-full max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome, {me.display_name}</h1>
      <p className="text-ink-muted">
        You're signed in as <span data-testid="me-email">{me.email}</span>. Next you'll create your team or company.
      </p>
      <Disclaimer />
    </section>
  );
}
