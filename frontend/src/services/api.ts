import type { AuthResult, User } from "../types/api";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as string | undefined;
const hostname = typeof window === "undefined" ? "" : window.location.hostname;
const localHost = hostname === "localhost" || hostname === "127.0.0.1";
const baseUrl = configuredBaseUrl || (localHost ? "/api" : "https://reglens-backend.vercel.app/api");
const TOKEN_KEY = "rl_token";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = "ApiError"; }
}

export const token = () => localStorage.getItem(TOKEN_KEY);
export function saveSession(result: { token: string }) { localStorage.setItem(TOKEN_KEY, result.token); }
export function clearSession() { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem("rl_authenticated"); }
export const errorMessage = (e: unknown, fallback = "Something went wrong") => (e instanceof Error && e.message ? e.message : fallback);

type ErrorBody = { detail?: string | Array<{ msg: string }> };
function detail(data: ErrorBody, status: number): string {
  if (Array.isArray(data.detail)) return data.detail.map((x) => x.msg).join(", ");
  if (data.detail) return data.detail;
  return status >= 500 ? "The server had a problem. Please try again." : "Something went wrong";
}

export type RequestOptions = RequestInit & { json?: unknown };
const AUTH_PATHS = ["/auth/login", "/auth/signup", "/auth/google"];

/** Single fetch wrapper: auth header, JSON in/out, uniform errors, global 401 handling. */
export async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const current = token();
  if (current) headers.set("Authorization", `Bearer ${current}`);
  let body = options.body;
  if (options.json !== undefined) { headers.set("Content-Type", "application/json"); body = JSON.stringify(options.json); }
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...options, headers, body });
  } catch {
    throw new ApiError("Can't reach the server. Check your connection and try again.", 0);
  }
  if (response.status === 401 && current && !AUTH_PATHS.includes(path)) {
    clearSession();
    window.dispatchEvent(new Event("rl:unauthorized"));
    throw new ApiError("Your session expired. Please sign in again.", 401);
  }
  if (!response.ok) {
    let data: ErrorBody = {};
    try { data = await response.json(); } catch { /* non-JSON error body */ }
    throw new ApiError(detail(data, response.status), response.status);
  }
  return response;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await request(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const auth = {
  login: (json: { email: string; password: string }) => api<AuthResult>("/auth/login", { method: "POST", json }),
  signup: (json: { name: string; email: string; password: string }) => api<AuthResult>("/auth/signup", { method: "POST", json }),
  google: (credential: string) => api<AuthResult>("/auth/google", { method: "POST", json: { credential } }),
  me: () => api<User>("/auth/me"),
  updateProfile: (name: string) => api<User>("/auth/me", { method: "PUT", json: { name } }),
  changePassword: (current: string, next: string) => api<{ ok: boolean }>("/auth/password", { method: "POST", json: { current, new: next } }),
  config: () => api<{ google_client_id: string | null }>("/config")
};

function filenameFrom(response: Response, fallback: string) {
  const header = response.headers.get("content-disposition") || "";
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return match ? decodeURIComponent(match[1]) : fallback;
}

export async function downloadFile(path: string, fallbackName: string) {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFrom(response, fallbackName);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
export const formatMoney = (n: number) => `₹${n.toLocaleString("en-IN")}`;
export const todayISO = () => new Date().toISOString().slice(0, 10);
