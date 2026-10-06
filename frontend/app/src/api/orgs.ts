import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { ApiError, api, unwrap } from "./client";
import type { components } from "./schema";

export type MyOrg = components["schemas"]["MyOrgOut"];
export type OrgDetail = components["schemas"]["OrgDetailOut"];
export type Member = components["schemas"]["MemberOut"];
export type Invitation = components["schemas"]["InvitationOut"];
export type InvitationCreated = components["schemas"]["InvitationCreatedOut"];
export type InvitationPreview = components["schemas"]["InvitationPreviewOut"];
export type OrgType = components["schemas"]["OrgIn"]["type"];
export type Role = components["schemas"]["RoleIn"]["role"];

const ORGS_KEY = ["orgs"] as const;
const orgKey = (orgId: string) => ["orgs", orgId] as const;

/**
 * One Idempotency-Key per attempt (api-conventions §4): reused when the same attempt is retried after a
 * network failure, replaced once the attempt succeeds or the server answers with an error.
 */
function useIdempotencyKey() {
  const key = useRef<string | null>(null);
  return {
    current: () => (key.current ??= crypto.randomUUID()),
    reset: () => {
      key.current = null;
    },
  };
}

export function useMyOrgs() {
  return useQuery({
    queryKey: ORGS_KEY,
    queryFn: async () => (await unwrap(api.GET("/v1/orgs"))).items,
  });
}

export function useCreateOrg() {
  const queryClient = useQueryClient();
  const key = useIdempotencyKey();
  return useMutation({
    mutationFn: (body: { type: OrgType; name: string }) =>
      unwrap(api.POST("/v1/orgs", { body, params: { header: { "Idempotency-Key": key.current() } } })),
    onSuccess: () => {
      key.reset();
      void queryClient.invalidateQueries({ queryKey: ORGS_KEY });
    },
    onError: (error) => {
      if (error instanceof ApiError) key.reset(); // the server answered; a network failure keeps the key
    },
  });
}

export function useOrg(orgId: string) {
  return useQuery({
    queryKey: orgKey(orgId),
    queryFn: () => unwrap(api.GET("/v1/orgs/{org_id}", { params: { path: { org_id: orgId } } })),
    retry: false,
  });
}

export function useMembers(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...orgKey(orgId), "members"],
    queryFn: async () =>
      (await unwrap(api.GET("/v1/orgs/{org_id}/members", { params: { path: { org_id: orgId } } }))).items,
    enabled,
  });
}

export function useChangeRole(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      unwrap(
        api.PATCH("/v1/orgs/{org_id}/members/{user_id}", {
          params: { path: { org_id: orgId, user_id: userId } },
          body: { role },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: orgKey(orgId) }),
  });
}

export function useRemoveMember(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) =>
      unwrap(
        api.DELETE("/v1/orgs/{org_id}/members/{user_id}", {
          params: { path: { org_id: orgId, user_id: userId } },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ORGS_KEY }),
  });
}

export function useInvitations(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...orgKey(orgId), "invitations"],
    queryFn: async () =>
      (await unwrap(api.GET("/v1/orgs/{org_id}/invitations", { params: { path: { org_id: orgId } } }))).items,
    enabled,
  });
}

export function useCreateInvitation(orgId: string) {
  const queryClient = useQueryClient();
  const key = useIdempotencyKey();
  return useMutation({
    mutationFn: (body: { email: string; role: Role }) =>
      unwrap(
        api.POST("/v1/orgs/{org_id}/invitations", {
          params: { path: { org_id: orgId }, header: { "Idempotency-Key": key.current() } },
          body,
        }),
      ),
    onSuccess: () => {
      key.reset();
      void queryClient.invalidateQueries({ queryKey: [...orgKey(orgId), "invitations"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) key.reset(); // the server answered; a network failure keeps the key
    },
  });
}

export function useRevokeInvitation(orgId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      unwrap(
        api.DELETE("/v1/orgs/{org_id}/invitations/{invitation_id}", {
          params: { path: { org_id: orgId, invitation_id: invitationId } },
        }),
      ),
    onSettled: () => queryClient.invalidateQueries({ queryKey: [...orgKey(orgId), "invitations"] }),
  });
}

export function useInvitationPreview(token: string | null) {
  return useQuery({
    queryKey: ["invitation", token],
    queryFn: () => unwrap(api.POST("/v1/invitations/lookup", { body: { token: token ?? "" } })),
    enabled: Boolean(token),
    retry: false,
  });
}

export function useAcceptInvitation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { token: string; confirm_email_mismatch: boolean }) =>
      unwrap(api.POST("/v1/invitations/accept", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ORGS_KEY }),
  });
}
