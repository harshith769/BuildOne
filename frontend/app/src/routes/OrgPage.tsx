import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import type { Me } from "@/api/auth";
import {
  useChangeRole,
  useCreateInvitation,
  useInvitations,
  useMembers,
  useOrg,
  useRemoveMember,
  useRevokeInvitation,
  type InvitationCreated,
  type Member,
  type Role,
} from "@/api/orgs";
import { problemOf } from "@/auth/problem";
import { Disclaimer } from "@/components/Disclaimer";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";
import { formatInstant } from "@/lib/format";

import { ORG_TYPE_LABELS, ROLE_LABELS } from "./orgLabels";

const ROLES: Role[] = ["owner", "member", "viewer"];

function MemberRow({ orgId, member, me, isOwner }: { orgId: string; member: Member; me: Me; isOwner: boolean }) {
  const changeRole = useChangeRole(orgId);
  const remove = useRemoveMember(orgId);
  const navigate = useNavigate();
  const isMe = member.user_id === me.id;
  const error = changeRole.error ?? remove.error;

  return (
    <li className="space-y-2 p-3" data-testid="member-row">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">
            {member.display_name ?? "Unknown"} {isMe ? <span className="text-ink-muted">(you)</span> : null}
          </p>
          <p className="text-sm text-ink-muted">{member.email}</p>
        </div>
        <div className="flex items-center gap-2">
          {isOwner ? (
            <select
              aria-label={`Role of ${member.display_name ?? member.email ?? "member"}`}
              className="rounded-lg border border-line bg-surface px-2 py-1 text-sm"
              value={member.role}
              disabled={changeRole.isPending}
              onChange={(e) => changeRole.mutate({ userId: member.user_id, role: e.target.value as Role })}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-sm">{ROLE_LABELS[member.role] ?? member.role}</span>
          )}
          {isOwner || isMe ? (
            <Button
              variant="outline"
              size="sm"
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(member.user_id, {
                  onSuccess: () => {
                    if (isMe) void navigate({ to: "/" });
                  },
                })
              }
            >
              {isMe ? "Leave" : "Remove"}
            </Button>
          ) : null}
        </div>
      </div>
      {error ? <ProblemMessage problem={problemOf(error)} /> : null}
    </li>
  );
}

function InviteForm({ orgId }: { orgId: string }) {
  const create = useCreateInvitation(orgId);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [created, setCreated] = useState<InvitationCreated | null>(null);
  const [copied, setCopied] = useState(false);

  return (
    <div className="space-y-3">
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          setCopied(false);
          create.mutate(
            { email: email.trim(), role },
            {
              onSuccess: (invitation) => {
                setCreated(invitation);
                setEmail("");
              },
            },
          );
        }}
      >
        <label className="flex-1">
          <span className="text-sm font-medium">Email</span>
          <input
            type="email"
            required
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          <span className="text-sm font-medium">Role</span>
          <select
            className="mt-1 block rounded-lg border border-line bg-surface px-2 py-2"
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" disabled={!email.trim() || create.isPending}>
          Invite
        </Button>
      </form>
      {create.isError ? <ProblemMessage problem={problemOf(create.error)} /> : null}
      {created?.invite_link ? (
        <div className="rounded-card border border-line bg-paper p-3 text-sm" role="status">
          <p>
            Send this link to <strong>{created.email}</strong>. It works once and expires on{" "}
            {formatInstant(created.expires_at)}. We show it only now.
          </p>
          <div className="mt-2 flex gap-2">
            <input
              readOnly
              aria-label="Invitation link"
              className="flex-1 rounded-lg border border-line bg-surface px-2 py-1 font-mono text-xs"
              value={created.invite_link}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void navigator.clipboard?.writeText(created.invite_link ?? "").then(() => setCopied(true));
              }}
            >
              {copied ? "Copied" : "Copy"}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Invitations({ orgId }: { orgId: string }) {
  const invitations = useInvitations(orgId, true);
  const revoke = useRevokeInvitation(orgId);
  if (invitations.isPending) return <p className="text-ink-muted">Loading invitations…</p>;
  if (invitations.isError) return <ProblemMessage problem={problemOf(invitations.error)} />;
  if (invitations.data.length === 0) return <p className="text-sm text-ink-muted">No open invitations.</p>;
  return (
    <ul className="divide-y divide-line rounded-card border border-line bg-surface">
      {invitations.data.map((i) => (
        <li key={i.id} className="flex items-center justify-between p-3 text-sm">
          <span>
            {i.email} · {ROLE_LABELS[i.role] ?? i.role} ·{" "}
            {i.expired ? <span className="text-warn">expired</span> : `expires ${formatInstant(i.expires_at)}`}
          </span>
          <Button variant="ghost" size="sm" disabled={revoke.isPending} onClick={() => revoke.mutate(i.id)}>
            Revoke
          </Button>
        </li>
      ))}
    </ul>
  );
}

// S4: one organisation, its members and (for owners) invitations.
export function OrgPage({ orgId, me }: { orgId: string; me: Me }) {
  const org = useOrg(orgId);
  const isMember = Boolean(org.data && org.data.access !== "grantee");
  const members = useMembers(orgId, isMember);

  if (org.isPending) {
    return (
      <p className="text-ink-muted" aria-live="polite">
        Loading…
      </p>
    );
  }
  if (org.isError) {
    const problem = problemOf(org.error);
    return (
      <section className="mx-auto max-w-xl space-y-3">
        {problem.status === 404 ? (
          <>
            <h1 className="text-2xl font-semibold">Organisation not found</h1>
            <p className="text-ink-muted">It doesn't exist, or you don't have access to it.</p>
          </>
        ) : (
          <ProblemMessage problem={problem} />
        )}
        <Link to="/" className="underline">
          Back to your organisations
        </Link>
      </section>
    );
  }

  const isOwner = org.data.access === "owner";
  return (
    <section className="mx-auto w-full max-w-2xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">{org.data.name}</h1>
        <p className="text-sm text-ink-muted">
          {ORG_TYPE_LABELS[org.data.type] ?? org.data.type} · {ROLE_LABELS[org.data.access]}
        </p>
      </header>

      {isMember ? (
        <div className="space-y-2">
          <h2 className="font-medium">Members</h2>
          {members.isPending ? (
            <p className="text-ink-muted">Loading members…</p>
          ) : members.isError ? (
            <ProblemMessage problem={problemOf(members.error)} />
          ) : (
            <ul className="divide-y divide-line rounded-card border border-line bg-surface">
              {members.data.map((m) => (
                <MemberRow key={m.user_id} orgId={orgId} member={m} me={me} isOwner={isOwner} />
              ))}
            </ul>
          )}
        </div>
      ) : (
        <p className="rounded-card border border-line bg-surface p-4 text-sm">
          This company shared its compliance plan with your organisation. You can read it, but not change it.
        </p>
      )}

      {isOwner ? (
        <div className="space-y-3">
          <h2 className="font-medium">Invite people</h2>
          <InviteForm orgId={orgId} />
          <h3 className="text-sm font-medium">Open invitations</h3>
          <Invitations orgId={orgId} />
        </div>
      ) : null}

      <Disclaimer />
    </section>
  );
}
