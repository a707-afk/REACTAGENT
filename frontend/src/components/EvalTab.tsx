import { useState, useEffect } from "react";
import { getJson, postJson } from "../api";

type EvalSummary = {
  eval_type: string;
  mode: string;
  total_cases: number;
  timestamp: string;
  metrics: {
    recall_at_5: number;
    mrr_at_10: number;
    ndcg_at_10: number;
    citation_precision: number;
    unsupported_rate: number;
    unauthorized_in_topk: number;
    refusal_accuracy: number;
    avg_latency_ms: number;
  };
  thresholds: Record<string, { target: number; passed: boolean }>;
};

export function EvalTab() {
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchLatest = async () => {
    setLoading(true);
    setError("");
    try {
      // Try to get latest eval result
      const list = await getJson<{ items: { id: string }[]; total: number }>(
        "/api/jobs?tenant_id=corp-default&task_type=run_eval&limit=1"
      );
      if (list.items.length > 0) {
        // Fetch eval run details (simplified)
      }
    } catch {
      // No eval runs yet — that's OK
    }
    setLoading(false);
  };

  useEffect(() => { fetchLatest(); }, []);

  const runEval = async () => {
    setLoading(true);
    try {
      await postJson("/api/jobs", {
        tenant_id: "corp-default",
        task_type: "run_eval",
        task_params: { dry_run: true },
      });
      alert("评测任务已提交，完成后查看报告");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>评测报告</h2>
      <div style={{ marginBottom: 12 }}>
        <button className="btn" onClick={runEval} disabled={loading}>
          {loading ? "提交中..." : "运行评测"}
        </button>
      </div>
      {error && <div className="error">{error}</div>}

      {summary ? (
        <table className="data-table">
          <thead>
            <tr><th>指标</th><th>值</th><th>门槛</th><th>状态</th></tr>
          </thead>
          <tbody>
            {Object.entries(summary.thresholds).map(([k, v]) => (
              <tr key={k}>
                <td>{k}</td>
                <td>{(summary.metrics as any)[k]}</td>
                <td>{v.target}</td>
                <td>{v.passed ? "✅" : "❌"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="output" style={{ color: "#999", textAlign: "center", padding: 32 }}>
          暂无评测数据。点击"运行评测"提交评测任务，查看评测报告请执行：
          <br />
          <code style={{ background: "#f0f0f0", padding: "4px 8px" }}>
            python scripts/run_eval_rag.py
          </code>
        </div>
      )}
    </div>
  );
}
