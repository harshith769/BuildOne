// The only place that talks HTTP. Types come from src/api/schema.d.ts, generated from the backend's OpenAPI
// document by `make openapi` (never hand-written; .claude/rules/frontend.md).
import createClient from "openapi-fetch";

import type { paths } from "./schema";

/** Empty in local development (Vite proxies to the API); https://api.<domain> in production. */
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export const api = createClient<paths>({ baseUrl, credentials: "include" });

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Value of a non-HttpOnly cookie (only `bo_csrf` is readable by design; docs/auth-and-tenancy.md §3). */
export function readCookie(name: string): string | undefined {
  const prefix = `${name}=`;
  for (const part of document.cookie.split("; ")) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length));
  }
  return undefined;
}

// CSRF double-submit: every unsafe request echoes the bo_csrf cookie in X-CSRF-Token.
api.use({
  onRequest({ request }) {
    if (UNSAFE_METHODS.has(request.method)) {
      const token = readCookie("bo_csrf");
      if (token) request.headers.set("X-CSRF-Token", token);
    }
    return request;
  },
});

/** Full URL of an API path, for browser navigations (sign-in) that can't go through fetch. */
export function apiUrl(path: string): string {
  return `${baseUrl}${path}`;
}

/** RFC 9457 problem details as the API returns them (docs/api-conventions.md §2). */
export interface Problem {
  type?: string;
  title: string;
  status: number;
  code: string;
  detail?: string;
  request_id?: string;
  errors?: { field: string; message: string }[];
}

export class ApiError extends Error {
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = "ApiError";
    this.problem = problem;
  }
}

/** Turn any failed response (or a network failure) into a Problem the UI can show. */
export function toProblem(error: unknown, response?: Response): Problem {
  if (error && typeof error === "object" && "code" in error && "title" in error) {
    return error as Problem;
  }
  return {
    title: response ? "The server returned an error" : "Can't reach BuildOne right now",
    status: response?.status ?? 0,
    code: response ? "http_error" : "network_error",
    detail: response ? undefined : "Check your connection and try again.",
    request_id: response?.headers.get("x-request-id") ?? undefined,
  };
}
