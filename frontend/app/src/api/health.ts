import { useQuery } from "@tanstack/react-query";

import { ApiError, api, toProblem } from "./client";
import type { components } from "./schema";

export type Readiness = components["schemas"]["Readiness"];

/** /readyz answers 503 with the same body when something is down, so both are data, not errors. */
export function useReadiness() {
  return useQuery({
    queryKey: ["readyz"],
    queryFn: async (): Promise<Readiness> => {
      try {
        const { data, error, response } = await api.GET("/readyz");
        if (data) return data;
        if (response.status === 503 && error) return error as Readiness;
        throw new ApiError(toProblem(error, response));
      } catch (err) {
        if (err instanceof ApiError) throw err;
        throw new ApiError(toProblem(err));
      }
    },
    refetchInterval: 30_000,
    retry: 1,
  });
}
