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
