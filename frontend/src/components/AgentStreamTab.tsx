import { useState, useEffect } from "react";
import { AuditStep, consumeSse, postJson } from "../api";

type AgentDone = {
  final_action?: string;
  human_review_required?: boolean;
  draft_reply?: string | null;
  ticket_note?: string | null;
  audit_trace?: AuditStep[];
  retrieved_chunks?: Array<{ text?: string; file_name?: string }>;
};

type HarnessResult = {
  run_id: string;
  status: string;
  final_answer: string | null;
  total_steps: number;
  total_tool_calls: number;
  total_cost_usd: number;
  total_latency_ms: number;
  plan: Array<{ step: number; action: string; tool?: string }>;
  errors: string[];
  hitl_required: boolean;
};

export function AgentStreamTab({ presetQuery }: { presetQuery?: string } = {}) {
  const [mode, setMode] = useState<"ticket" | "harness">("ticket");
  const [ticketId, setTicketId] = useState(() => `T-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,6)}`);
  const [query, setQuery] = useState(presetQuery?.trim() || "");
  const [steps, setSteps] = useState<AuditStep[]>([]);
  const [draft, setDraft] = useState("");
  const [done, setDone] = useState<AgentDone | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Harness mode state
  const [harnessResult, setHarnessResult] = useState<HarnessResult | null>(null);

  useEffect(() => {
    if (presetQuery?.trim()) {
      setQuery(presetQuery);
    }
  }, [presetQuery]);

  async function onHarnessRun(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setHarnessResult(null);
    try {
      const result = await postJson<HarnessResult>("/agent/run", {
        objective: query,
        tenant_id: "default",
        user_id: "anonymous",
      });
      setHarnessResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

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
              // draft_reply already streamed via token events
              if (d.draft_reply && !draft) setDraft(d.draft_reply);
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
    <div>
      {/* ── Mode switch ── */}
      <div className="actions" style={{ marginBottom: 12 }}>
        <button type="button" className={mode === "ticket" ? "active" : ""} onClick={() => setMode("ticket")}>工单 Agent (SSE)</button>
        <button type="button" className={mode === "harness" ? "active" : ""} onClick={() => setMode("harness")}>Harness Run</button>
      </div>

      {/* ── Shared input ── */}
      <div className="field">
        <label htmlFor="agent-query">{mode === "ticket" ? "用户问题" : "Agent 目标"}</label>
        <textarea
          id="agent-query"
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {mode === "ticket" ? (
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="agent-ticket">工单号</label>
            <input
              id="agent-ticket"
              value={ticketId}
              onChange={(e) => setTicketId(e.target.value)}
            />
          </div>
          <div className="actions">
            <button type="submit" disabled={loading || !query.trim()}>
              {loading ? "Agent 执行中…" : "流式工单"}
            </button>
          </div>
        </form>
      ) : (
        <form onSubmit={onHarnessRun}>
          <div className="actions">
            <button type="submit" disabled={loading || !query.trim()}>
              {loading ? "Harness 执行中…" : "运行 Harness"}
            </button>
          </div>
        </form>
      )}

      {error && <p className="error">{error}</p>}

      {/* ── Ticket mode results ── */}
      {mode === "ticket" && (
        <>
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
        </>
      )}

      {/* ── Harness mode results ── */}
      {mode === "harness" && harnessResult && (
        <>
          <p className="section-title">
            Harness 结果 · {harnessResult.status}
            {harnessResult.hitl_required && <span className="badge">需人工介入</span>}
          </p>
          <div className="meta" style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <span>Steps: {harnessResult.total_steps}</span>
            <span>Tool calls: {harnessResult.total_tool_calls}</span>
            <span>Latency: {Math.round(harnessResult.total_latency_ms)}ms</span>
            <span>Cost: ${harnessResult.total_cost_usd.toFixed(4)}</span>
          </div>

          {harnessResult.plan && harnessResult.plan.length > 0 && (
            <>
              <p className="section-title">执行计划</p>
              <ol className="timeline">
                {harnessResult.plan.map((p, i) => (
                  <li key={i}>
                    <strong>Step {p.step}</strong>: {p.action}
                    {p.tool && <span className="meta"> (tool: {p.tool})</span>}
                  </li>
                ))}
              </ol>
            </>
          )}

          <p className="section-title">最终回复</p>
          <div className="output">{harnessResult.final_answer || "（无回复）"}</div>

          {harnessResult.errors && harnessResult.errors.length > 0 && (
            <>
              <p className="section-title">错误</p>
              <ul className="timeline">
                {harnessResult.errors.map((err, i) => (
                  <li key={i} className="error">{err}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
