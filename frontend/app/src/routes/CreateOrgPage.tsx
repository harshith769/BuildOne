import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { useCreateOrg, type OrgType } from "@/api/orgs";
import { problemOf } from "@/auth/problem";
import { Card } from "@/components/Card";
import { ProblemMessage } from "@/components/ProblemMessage";
import { Button } from "@/components/ui/button";

import { ORG_TYPE_LABELS } from "./orgLabels";

const TYPES: OrgType[] = ["company", "team", "ca_firm", "incubator"];

// S3: create an organisation. The creator becomes its first owner.
export function CreateOrgPage() {
  const create = useCreateOrg();
  const navigate = useNavigate();
  const [type, setType] = useState<OrgType>("company");
  const [name, setName] = useState("");

  return (
    <Card title="Create an organisation">
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          create.mutate(
            { type, name: name.trim() },
            { onSuccess: (org) => void navigate({ to: "/orgs/$orgId", params: { orgId: org.id } }) },
          );
        }}
      >
        <fieldset className="space-y-2">
          <legend className="font-medium">What kind of organisation?</legend>
          {TYPES.map((t) => (
            <label key={t} className="flex items-center gap-3">
              <input type="radio" name="type" value={t} checked={type === t} onChange={() => setType(t)} />
              <span>{ORG_TYPE_LABELS[t]}</span>
            </label>
          ))}
        </fieldset>
        <label className="block">
          <span className="font-medium">Name</span>
          <input
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2"
            value={name}
            maxLength={200}
            required
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        {create.isError ? <ProblemMessage problem={problemOf(create.error)} /> : null}
        <Button type="submit" className="w-full" disabled={!name.trim() || create.isPending}>
          Create
        </Button>
      </form>
    </Card>
  );
}
