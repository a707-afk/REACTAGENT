import { useState } from "react";
import { consumeSse } from "../api";

type ChatDone = {
  answer?: string;
  refused?: boolean;
  error_code?: string | null;
  citation_overlap_ratio?: number | null;
  grounding?: { passed?: boolean; unsupported_sentence_rate?: number };
  citations?: Array<{ index: number; file_name?: string; excerpt?: string }>;
};

export function ChatStreamTab() {
  const [query, setQuery] = useState("Kubernetes 滚动更新怎么做？");
  const [draft, setDraft] = useState("");
  const [done, setDone] = useState<ChatDone | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setDraft("");
    setDone(null);
    try {
      await consumeSse(
        "/chat/stream",
        { query, top_k: 5 },
        {
          onEvent: (event, data) => {
            if (event === "token") {
              const t = (data as { text?: string }).text ?? "";
              setDraft((prev) => prev + t);
            } else if (event === "done") {
              setDone(data as ChatDone);
            } else if (event === "error") {
              const msg = (data as { message?: string }).message ?? "未知错误";
              setError(msg);
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
        <label htmlFor="chat-query">问题</label>
        <textarea
          id="chat-query"
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="actions">
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? "流式生成中…" : "流式问答"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <p className="section-title">草稿（token 增量）</p>
      <div className="output">{draft || "（等待输出）"}</div>
      {done && (
        <>
          <p className="section-title">
            完成摘要
            {done.refused ? <span className="badge">已拒绝</span> : null}
          </p>
          <div className="meta">
            overlap={done.citation_overlap_ratio ?? "—"}
            {done.grounding
              ? ` · grounding=${done.grounding.passed ? "pass" : "fail"} (${(
                  (done.grounding.unsupported_sentence_rate ?? 0) * 100
                ).toFixed(0)}% unsupported)`
              : ""}
          </div>
          {done.citations && done.citations.length > 0 && (
            <ul className="chunk-list">
              {done.citations.map((c) => (
                <li key={c.index}>
                  <div className="meta">[{c.index}] {c.file_name ?? ""}</div>
                  <div>{c.excerpt}</div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </form>
  );
}
