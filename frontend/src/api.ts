/* ── Shared types ────────────────────────────────────────── */

export type ChunkHit = {
  text: string;
  score?: number | null;
  file_name?: string | null;
  heading?: string | null;
};

export type AuditStep = {
  step: string;
  [key: string]: unknown;
};

/* ── Generic HTTP ──────────────────────────────────────── */

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function delJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

/** 解析 SSE：按 event 类型回调。 */
export async function consumeSse(
  url: string,
  body: unknown,
  handlers: {
    onEvent: (event: string, data: unknown) => void;
    onError?: (err: Error) => void;
  },
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    throw new Error(await res.text());
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const block of parts) {
      if (!block.trim()) continue;
      let event = "message";
      let dataLine = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) dataLine += line.slice(5).trim();
      }
      if (!dataLine) continue;
      try {
        handlers.onEvent(event, JSON.parse(dataLine));
      } catch (e) {
        handlers.onError?.(e instanceof Error ? e : new Error(String(e)));
      }
    }
  }
}

/* ── Document types ────────────────────────────────────── */

export type DocumentItem = {
  id: string;
  tenant_id: string;
  file_name: string;
  mime_type: string;
  file_size: number;
  content_hash: string;
  status: string;
  page_count?: number | null;
  language?: string | null;
  domain?: string | null;
  security_level: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export type DocumentList = {
  items: DocumentItem[];
  total: number;
  offset: number;
  limit: number;
};

export type UploadResponse = {
  document_id: string;
  job_id: string;
  message: string;
};

/* ── Ticket types ──────────────────────────────────────── */

export type TicketItem = {
  id: string;
  ticket_id: string;
  tenant_id: string;
  status: string;
  priority: string;
  subject?: string;
  created_at: string;
  updated_at: string;
};

export type TicketList = {
  items: TicketItem[];
  total: number;
  offset: number;
  limit: number;
};

/* ── Approval types ────────────────────────────────────── */

export type ApprovalItem = {
  id: string;
  tenant_id: string;
  run_id?: string | null;
  tool_name: string;
  reason?: string | null;
  risk_level: string;
  status: string;
  requested_by?: string | null;
  approved_by?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApprovalList = {
  items: ApprovalItem[];
  total: number;
  offset: number;
  limit: number;
};
