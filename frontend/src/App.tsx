import { useState } from "react";
import "./App.css";
import { AgentStreamTab } from "./components/AgentStreamTab";
import { ChatStreamTab } from "./components/ChatStreamTab";
import { RetrieveTab } from "./components/RetrieveTab";
import { DocumentsTab } from "./components/DocumentsTab";
import { ApprovalsTab } from "./components/ApprovalsTab";
import { EvalTab } from "./components/EvalTab";

const TABS = [
  { key: "chat", label: "💬 对话" },
  { key: "retrieve", label: "🔍 检索" },
  { key: "agent", label: "🤖 研究 Agent" },
  { key: "documents", label: "📄 文档" },
  { key: "approvals", label: "✅ 审批" },
  { key: "eval", label: "📊 评测" },
];

export default function App() {
  const [tab, setTab] = useState("chat");
  const [_apiKey, setApiKey] = useState(() => localStorage.getItem("apiKey") ?? "");

  const handleKeySet = (key: string) => {
    setApiKey(key);
    localStorage.setItem("apiKey", key.trim());
    alert("API Key 已保存");
  };

  return (
    <div className="app">
      <header>
        <h1>Deep Research Agent</h1>
        <p>企业级技术选型调研助手 — 自主多步检索 · 引用溯源 · 多租户隔离</p>
      </header>

      {/* ── API Key ── */}
      <div className="apikey-bar">
        <span>API Key:</span>
        <input
          type="password"
          placeholder="sk-xxx (留空使用默认)"
          defaultValue={_apiKey}
          onBlur={(e) => handleKeySet(e.target.value)}
          className="apikey-input"
        />
      </div>

      {/* ── Tabs ── */}
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={tab === t.key ? "active" : ""}>
            {t.label}
          </button>
        ))}
      </nav>

      {/* ── Tab Content ── */}
      <div className="panel">
        {tab === "chat" && <ChatStreamTab />}
        {tab === "retrieve" && <RetrieveTab />}
        {tab === "agent" && <AgentStreamTab />}
        {tab === "documents" && <DocumentsTab />}
        {tab === "approvals" && <ApprovalsTab />}
        {tab === "eval" && <EvalTab />}
      </div>
    </div>
  );
}
