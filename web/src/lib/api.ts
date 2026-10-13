import { getToken } from "@/lib/session";
import type {
  Appointment,
  BrokerSummary,
  ChatHistory,
  ChatStreamEvent,
  FollowupResult,
  FollowupRunResult,
  Lead,
  LeadDetail,
  Metrics,
  Property,
} from "@/lib/types";

export const UNAUTHORIZED_EVENT = "royal:unauthorized";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function errorFrom(response: Response) {
  let detail = response.statusText || "Erro inesperado";
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") detail = body.detail;
    else if (Array.isArray(body?.detail) && body.detail[0]?.msg) detail = body.detail[0].msg;
  } catch {
    detail = response.statusText || detail;
  }
  return new ApiError(response.status, detail);
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const error = await errorFrom(response);
    if (token !== undefined && response.status === 401) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw error;
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function authed<T>(path: string, init: RequestInit = {}) {
  return request<T>(path, init, getToken() ?? "");
}

function query(params: Record<string, string | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export async function* readSSE(response: Response): AsyncGenerator<ChatStreamEvent> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (value) buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseBlock(block);
      if (parsed) yield parsed;
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  const tail = parseBlock(buffer);
  if (tail) yield tail;
}

function parseBlock(block: string): ChatStreamEvent | null {
  if (!block.trim()) return null;
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) } as ChatStreamEvent;
  } catch {
    return null;
  }
}

async function streamRequest(path: string, init: RequestInit, signal?: AbortSignal) {
  const response = await fetch(path, { ...init, signal, headers: { Accept: "text/event-stream", ...init.headers } });
  if (!response.ok) throw await errorFrom(response);
  return readSSE(response);
}

export const chatApi = {
  history(sessionId: string, afterId = 0) {
    return request<ChatHistory>(`/api/chat/${encodeURIComponent(sessionId)}/messages${query({ after_id: String(afterId) })}`);
  },
  sendText(sessionId: string, message: string, signal?: AbortSignal) {
    return streamRequest(
      "/api/chat/stream",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
      },
      signal,
    );
  },
  sendAudio(sessionId: string, audio: Blob, filename: string, signal?: AbortSignal) {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("file", audio, filename);
    form.append("reply_with_audio", "true");
    return streamRequest("/api/chat/audio", { method: "POST", body: form }, signal);
  },
};

export const dashboardApi = {
  check(token: string) {
    return request<{ ok: boolean }>("/api/auth/check", {}, token);
  },
  metrics() {
    return authed<Metrics>("/api/dashboard/metrics");
  },
  leads(filters: { stage?: string; temperature?: string; intent?: string; q?: string }) {
    return authed<{ items: Lead[] }>(`/api/leads${query(filters)}`);
  },
  lead(id: string) {
    return authed<LeadDetail>(`/api/leads/${id}`);
  },
  regenerateSummary(id: string) {
    return authed<{ summary: BrokerSummary }>(`/api/leads/${id}/summary`, { method: "POST" });
  },
  pause(id: string, paused: boolean) {
    return authed<Lead>(`/api/leads/${id}/pause`, { method: "POST", body: JSON.stringify({ paused }) });
  },
  followupNow(id: string) {
    return authed<{ sent: boolean; followup: FollowupResult | null }>(`/api/leads/${id}/followup`, { method: "POST" });
  },
  deleteLead(id: string) {
    return authed<void>(`/api/leads/${id}`, { method: "DELETE" });
  },
  appointments(upcoming = true) {
    return authed<{ items: Appointment[] }>(`/api/appointments${query({ upcoming: String(upcoming) })}`);
  },
  runFollowups(force: boolean) {
    return authed<FollowupRunResult>("/api/followups/run", { method: "POST", body: JSON.stringify({ force }) });
  },
  properties(filters: { purpose?: string; kind?: string }) {
    return authed<{ items: Property[] }>(`/api/properties${query(filters)}`);
  },
  graph() {
    return authed<{ mermaid: string }>("/api/agent/graph");
  },
};
