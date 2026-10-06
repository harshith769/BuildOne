import { ApiError, type Problem } from "@/api/client";

export function problemOf(error: unknown): Problem {
  return error instanceof ApiError ? error.problem : { title: "Something went wrong", status: 0, code: "unknown" };
}
