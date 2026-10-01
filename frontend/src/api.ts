export type Role = "CUSTOMER" | "SUPPORT_AGENT" | "ADMIN";
export interface User { customer_id: string; name: string; email: string; role: Role; membership_tier: string }

const TOKEN_KEY = "ns_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export class ApiError extends Error { status: number; constructor(status: number, msg: string) { super(msg); this.status = status; } }

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch("/api" + path, {
      method: opts.method || (opts.body ? "POST" : "GET"),
      headers: { "Content-Type": "application/json", ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the backend. Is it running?");
  }
  if (res.status === 401 && path !== "/auth/login") { setToken(null); window.dispatchEvent(new Event("ns-logout")); }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

export interface ChatResponse {
  conversation_id: string; message: string; intent: { intent: string; confidence: number; urgency: string };
  sentiment: { sentiment: string; urgency: string; reason: string };
  steps: { label: string; tool: string | null; ok: boolean }[];
  citations: { index: number; source: string; section: string; document: string }[];
  actions: any[]; escalation: null | { ticket_id: string; priority: string; expected_response: string };
  confirmation: null | { action: string; prompt: string; amount: number; requires_human_approval: boolean };
  approval: null | { approval_id: string };
  verification: { passed: boolean; groundedness: number; citation_accuracy: number };
  blocked: string | null; resolution_status: string; latency_ms: number;
}
