import { useState, useEffect } from "react";
import { type TicketItem, type TicketList, getJson } from "../api";

export function TicketsTab() {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const fetchTickets = async () => {
    setLoading(true);
    setError("");
    try {
      const url = `/api/tickets?tenant_id=corp-default&limit=50${statusFilter ? `&status=${statusFilter}` : ""}`;
      const data = await getJson<TicketList>(url);
      setTickets(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTickets(); }, [statusFilter]);

  return (
    <div>
      <h2>工单列表 ({total})</h2>

      <div className="field">
        <label>状态过滤</label>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">全部</option>
          <option value="open">打开</option>
          <option value="in_progress">处理中</option>
          <option value="resolved">已解决</option>
          <option value="closed">已关闭</option>
        </select>
      </div>

      {error && <div className="error">{error}</div>}

      {loading ? <p>加载中...</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>工单ID</th>
              <th>状态</th>
              <th>优先级</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id}>
                <td>{t.id?.slice(0, 8) ?? t.ticket_id}</td>
                <td><span className={`badge badge-${t.status}`}>{t.status}</span></td>
                <td><span className={`badge badge-${t.priority}`}>{t.priority}</span></td>
                <td>{new Date(t.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {tickets.length === 0 && <tr><td colSpan={4} style={{ textAlign: "center", color: "#999" }}>暂无工单</td></tr>}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: 8, color: "#666", fontSize: 13 }}>
        共 {total} 条工单
      </div>
    </div>
  );
}
