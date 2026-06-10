import { useState, useEffect } from "react";
import { AuditStep, consumeSse } from "../api";

type AgentDone = {
  final_action?: string;
  human_review_required?: boolean;
  draft_reply?: string | null;
  ticket_note?: string | null;
  audit_trace?: AuditStep[];
  retrieved_chunks?: Array<{ text?: string; file_name?: string }>;
};

export function AgentStreamTab({ presetQuery }: { presetQuery?: string }) {
  const [ticketId, setTicketId] = useState("T-DEMO-001");
  const [query, setQuery] = useState(presetQuery?.trim() || "输入电商售后问题...");
  const [steps, setSteps] = useState<AuditStep[]>([]);
  const [draft, setDraft] = useState("");
  const [done, setDone] = useState<AgentDone | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (presetQuery?.trim()) {
      setQuery(presetQuery);
    }
  }, [presetQuery]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSteps([]);
    setDraft("");
    setDone(null);
    try {
      await consumeSse(
        "/agent/ticket/stream",
        {
          ticket_id: ticketId,
          user_query: query,
          top_k: 5,
          user_context: {
            tenant_id: "corp-default",
            roles: ["support_agent"],
          },
        },
        {
          onEvent: (event, data) => {
            if (event === "step") {
              setSteps((prev) => [...prev, data as AuditStep]);
            } else if (event === "token") {
              const t = (data as { text?: string }).text ?? "";
              setDraft((prev) => prev + t);
            } else if (event === "done") {
              const d = data as AgentDone;
              setDone(d);
              if (d.draft_reply) setDraft(d.draft_reply);
              if (d.audit_trace?.length) setSteps(d.audit_trace);
            } else if (event === "error") {
              setError((data as { message?: string }).message ?? "未知错误");
            }
          },
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <div className="field">
        <label htmlFor="agent-ticket">工单号</label>
        <input
          id="agent-ticket"
          value={ticketId}
          onChange={(e) => setTicketId(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="agent-query">用户问题</label>
        <textarea
          id="agent-query"
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="actions">
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? "Agent 执行中…" : "流式工单"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      <p className="section-title">audit_trace 时间线</p>
      <ul className="timeline">
        {steps.map((s, i) => (
          <li key={i}>
            <strong>{s.step}</strong>
            <div className="meta">{JSON.stringify({ ...s, step: undefined })}</div>
          </li>
        ))}
        {steps.length === 0 && <li className="meta">（等待步骤）</li>}
      </ul>

      <p className="section-title">草稿回复</p>
      <div className="output">{draft || "（等待 draft）"}</div>

      {done && (
        <>
          <p className="section-title">
            结果 · {done.final_action}
            {done.human_review_required ? (
              <span className="badge">需人工复核</span>
            ) : null}
          </p>
          {done.ticket_note && <div className="meta">{done.ticket_note}</div>}
          {done.retrieved_chunks && done.retrieved_chunks.length > 0 && (
            <>
              <p className="section-title">引用片段</p>
              <ul className="chunk-list">
                {done.retrieved_chunks.map((c, i) => (
                  <li key={i}>
                    <div className="meta">{c.file_name ?? `chunk-${i + 1}`}</div>
                    <div>{(c.text ?? "").slice(0, 300)}</div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </form>
  );
}
