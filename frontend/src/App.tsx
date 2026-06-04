import { useState } from "react";
import "./App.css";
import { RetrieveTab } from "./components/RetrieveTab";
import { ChatStreamTab } from "./components/ChatStreamTab";
import { AgentStreamTab } from "./components/AgentStreamTab";

type Tab = "retrieve" | "chat" | "agent";

export default function App() {
  const [tab, setTab] = useState<Tab>("retrieve");

  return (
    <div className="app">
      <header>
        <h1>RAG 知识库演示</h1>
        <p>检索 · 问答流式 · 工单 Agent 流式（阶段 K）</p>
      </header>

      <nav className="tabs">
        <button
          type="button"
          className={tab === "retrieve" ? "active" : ""}
          onClick={() => setTab("retrieve")}
        >
          检索
        </button>
        <button
          type="button"
          className={tab === "chat" ? "active" : ""}
          onClick={() => setTab("chat")}
        >
          问答流式
        </button>
        <button
          type="button"
          className={tab === "agent" ? "active" : ""}
          onClick={() => setTab("agent")}
        >
          工单 Agent
        </button>
      </nav>

      <div className="panel">
        {tab === "retrieve" && <RetrieveTab />}
        {tab === "chat" && <ChatStreamTab />}
        {tab === "agent" && <AgentStreamTab />}
      </div>
    </div>
  );
}
