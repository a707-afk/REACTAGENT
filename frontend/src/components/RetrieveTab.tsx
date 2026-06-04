import { useState } from "react";
import { ChunkHit, postJson } from "../api";

type RetrieveResponse = {
  query: string;
  chunks: ChunkHit[];
  gate_passed: boolean;
  error_code?: string | null;
};

export function RetrieveTab() {
  const [query, setQuery] = useState("退款流程是什么？");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RetrieveResponse | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await postJson<RetrieveResponse>("/retrieve", {
        query,
        top_k: topK,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <div className="field">
        <label htmlFor="retrieve-query">问题</label>
        <textarea
          id="retrieve-query"
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="field">
        <label htmlFor="retrieve-topk">Top K</label>
        <input
          id="retrieve-topk"
          type="number"
          min={1}
          max={30}
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
        />
      </div>
      <div className="actions">
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? "检索中…" : "检索"}
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {result && (
        <>
          <p className="meta">
            门控：{result.gate_passed ? "通过" : "未通过"}
            {result.error_code ? ` · ${result.error_code}` : ""}
          </p>
          <ul className="chunk-list">
            {result.chunks.map((c, i) => (
              <li key={i}>
                <div className="meta">
                  #{i + 1}
                  {c.file_name ? ` · ${c.file_name}` : ""}
                  {c.score != null ? ` · score=${c.score.toFixed(3)}` : ""}
                </div>
                <div>{c.text.slice(0, 400)}{c.text.length > 400 ? "…" : ""}</div>
              </li>
            ))}
          </ul>
        </>
      )}
    </form>
  );
}
