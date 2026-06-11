import { useState, useEffect } from "react";
import { type ApprovalItem, type ApprovalList, getJson, postJson } from "../api";

export function ApprovalsTab() {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchApprovals = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getJson<ApprovalList>("/api/approvals?tenant_id=corp-default&status=pending&limit=30");
      setItems(data.items);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchApprovals(); }, []);

  const handleAction = async (id: string, action: "approve" | "reject") => {
    try {
      await postJson(`/api/approvals/${id}/${action}?tenant_id=corp-default`, {
        approved_by: "admin",
        reason: action === "approve" ? "Approved" : "Rejected by reviewer",
      });
      fetchApprovals();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <h2>审批管理</h2>
      {error && <div className="error">{error}</div>}
      {loading ? <p>加载中...</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>工具</th>
              <th>原因</th>
              <th>风险级别</th>
              <th>请求时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id}>
                <td>{a.tool_name}</td>
                <td>{a.reason ?? "-"}</td>
                <td><span className={`badge badge-${a.risk_level}`}>{a.risk_level}</span></td>
                <td>{new Date(a.created_at).toLocaleString()}</td>
                <td>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button className="btn btn-sm" onClick={() => handleAction(a.id, "approve")}>批准</button>
                    <button className="btn btn-sm btn-danger" onClick={() => handleAction(a.id, "reject")}>拒绝</button>
                  </div>
                </td>
              </tr>
            ))}
            {items.length === 0 && <tr><td colSpan={5} style={{ textAlign: "center", color: "#999" }}>暂无待审批项</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}
