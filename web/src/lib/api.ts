import type { ApiErrorBody, TokenPair } from "./types";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

/** Any non-2xx response, carrying the API's error code and per-field details. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: { field: string; message: string }[] = [],
  ) {
    super(message);
  }

  fieldError(field: string): string | undefined {
    return this.details.find((d) => d.field === field)?.message;
  }
}

/*
 * Token storage: the short-lived access token lives only in memory; the refresh token sits in
 * sessionStorage so a reload keeps you signed in but closing the tab ends the session.
 * (A production build would move the refresh token to an httpOnly cookie via a BFF.)
 */
const REFRESH_KEY = "rokkha.refresh";
let accessToken: string | null = null;

export const tokens = {
  get access() {
    return accessToken;
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    try {
      return sessionStorage.getItem(REFRESH_KEY);
    } catch {
      return null;
    }
  },
  set(pair: TokenPair) {
    accessToken = pair.access_token;
    try {
      sessionStorage.setItem(REFRESH_KEY, pair.refresh_token);
    } catch {
      /* storage unavailable: session lasts until reload */
    }
  },
  clear() {
    accessToken = null;
    try {
      sessionStorage.removeItem(REFRESH_KEY);
    } catch {
      /* ignore */
    }
  },
};

// One refresh at a time: parallel 401s wait for the same rotation instead of racing it
// (the API rejects a refresh token the second time it is used).
let refreshing: Promise<boolean> | null = null;

export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      const refresh = tokens.refresh;
      if (!refresh) return false;
      try {
        const pair = await request<TokenPair>("/auth/refresh", {
          method: "POST",
          body: { refresh_token: refresh },
          auth: false,
        });
        tokens.set(pair);
        return true;
      } catch {
        tokens.clear();
        return false;
      }
    })().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`;

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Can't reach the server. Check your connection.");
  }

  // Access token expired (or missing after a reload): rotate once, then retry.
  if (response.status === 401 && auth && !retried && (await refreshSession())) {
    return request<T>(path, options, true);
  }
  if (response.status === 204) return undefined as T;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = (data as ApiErrorBody | null)?.error;
    throw new ApiError(
      response.status,
      err?.code ?? "UNKNOWN",
      err?.message ?? `Request failed (${response.status})`,
      err?.details ?? [],
    );
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown, auth = true) =>
    request<T>(path, { method: "POST", body, auth }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
};
