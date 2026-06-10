import { useState } from "react";
import "./App.css";
import { AgentStreamTab } from "./components/AgentStreamTab";

export default function App() {
  const DEMO_SCENARIOS = [
    { label: "换货", query: "买了件M码T恤太小了想换L码" },
    { label: "退款", query: "我要退款，质量太差了" },
    { label: "投诉", query: "投诉你们客服态度太差了" },
    { label: "物流查询", query: "我的快递到哪了" },
  ];

  const [query, setQuery] = useState("");

  const handleDemoClick = (q: string) => {
    setQuery(q);
  };

  return (
    <div className="app">
      <header>
        <h1>EcomAgent</h1>
        <p>电商智能售后多Agent系统 — 换货/退款/投诉/物流</p>
      </header>

      <div className="demo-bar" style={{
        display: "flex", gap: "8px", padding: "12px 16px",
        flexWrap: "wrap", alignItems: "center",
      }}>
        <span style={{ fontSize: "13px", color: "#666", marginRight: "4px" }}>快速场景:</span>
        {DEMO_SCENARIOS.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => handleDemoClick(s.query)}
            style={{
              padding: "6px 14px", borderRadius: "6px", border: "1px solid #d0d0d0",
              background: query === s.query ? "#534AB7" : "#fff",
              color: query === s.query ? "#fff" : "#333",
              cursor: "pointer", fontSize: "12px",
            }}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="panel">
        <AgentStreamTab presetQuery={query} />
      </div>
    </div>
  );
}
