import { useState, useEffect, useRef } from "react";
import {
  type DocumentItem,
  type DocumentList,
  type UploadResponse,
  postJson,
  getJson,
  delJson,
} from "../api";

export function DocumentsTab() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchDocs = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getJson<DocumentList>("/api/documents/?tenant_id=corp-default");
      setDocs(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDocs(); }, []);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploadMsg("上传中...");
    const form = new FormData();
    form.append("file", file);
    form.append("tenant_id", "corp-default");
    try {
      const res = await fetch("/api/documents/upload", { method: "POST", body: form });
      const data: UploadResponse = await res.json();
      setUploadMsg(`上传成功: ${data.message} (doc: ${data.document_id.slice(0, 8)}...)`);
      fetchDocs();
    } catch (e) {
      setUploadMsg(`上传失败: ${e}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确认删除此文档？")) return;
    try {
      await delJson(`/api/documents/${id}?tenant_id=corp-default`);
      fetchDocs();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div>
      <h2>文档管理 ({total})</h2>

      <div className="field">
        <label>上传文件 (PDF, DOCX, MD, TXT, PNG, JPG)</label>
        <div style={{ display: "flex", gap: 8 }}>
          <input type="file" ref={fileRef} accept=".pdf,.docx,.md,.txt,.png,.jpg,.jpeg" />
          <button className="btn" onClick={handleUpload}>上传</button>
        </div>
        {uploadMsg && <div className="info">{uploadMsg}</div>}
      </div>

      {error && <div className="error">{error}</div>}

      {loading ? <p>加载中...</p> : (
        <table className="data-table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>大小</th>
              <th>状态</th>
              <th>上传时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td>{d.file_name}</td>
                <td>{d.mime_type.split("/")[1]}</td>
                <td>{formatSize(d.file_size)}</td>
                <td><span className={`badge badge-${d.status}`}>{d.status}</span></td>
                <td>{new Date(d.created_at).toLocaleString()}</td>
                <td><button className="btn btn-sm btn-danger" onClick={() => handleDelete(d.id)}>删除</button></td>
              </tr>
            ))}
            {docs.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", color: "#999" }}>暂无文档</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
