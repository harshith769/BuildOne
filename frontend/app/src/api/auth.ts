import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, api, apiUrl, unwrap } from "./client";
import type { components } from "./schema";

export type Me = components["schemas"]["MeOut"];
export type SignupProfile = components["schemas"]["SignupProfileOut"];

export const ME_KEY = ["me"] as const;

/** Where the browser goes to sign in; the API redirects to the identity provider. */
export function signInUrl(returnTo: string): string {
  return apiUrl(`/v1/auth/login?${new URLSearchParams({ return_to: returnTo }).toString()}`);
}

/** The signed-in user, or null when nobody is signed in (401). Other failures are errors. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async (): Promise<Me | null> => {
      try {
        return await unwrap(api.GET("/v1/me"));
      } catch (err) {
        if (err instanceof ApiError && err.problem.status === 401) return null;
        throw err;
      }
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useSignupProfile() {
  return useQuery({
    queryKey: ["signup"],
    queryFn: async (): Promise<SignupProfile | null> => {
      try {
        return await unwrap(api.GET("/v1/auth/signup"));
      } catch (err) {
        if (err instanceof ApiError && err.problem.status === 401) return null;
        throw err;
      }
    },
    retry: false,
  });
}

export function useCompleteSignup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versions: { terms_version: string; privacy_version: string }) =>
      unwrap(api.POST("/v1/auth/signup", { body: { age_confirmed: true, ...versions } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useDeclineSignup() {
  return useMutation({ mutationFn: () => unwrap(api.POST("/v1/auth/signup/decline")) });
}

export function useAcceptConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (versions: { terms_version: string; privacy_version: string }) =>
      unwrap(api.POST("/v1/me/consent", { body: versions })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
}

/** Callers follow up with a full page load, which also drops every cached query holding the user's data. */
export function useSignOut() {
  return useMutation({ mutationFn: () => unwrap(api.POST("/v1/auth/logout")) });
}
