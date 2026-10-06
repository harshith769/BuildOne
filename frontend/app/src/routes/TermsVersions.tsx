/** Which versions are being accepted. The lawyer-reviewed texts are published before the pilot (M13). */
export function TermsVersions({ terms, privacy }: { terms: string; privacy: string }) {
  return (
    <span className="mt-1 block text-xs text-ink-muted">
      Terms of use version <code className="font-mono">{terms}</code> · Privacy notice version{" "}
      <code className="font-mono">{privacy}</code>
    </span>
  );
}
