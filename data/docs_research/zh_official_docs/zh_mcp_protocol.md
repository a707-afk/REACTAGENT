<!-- source: AI辅助整理 | category: mcp/tools | language: zh-CN -->

# MCP 协议：Agent 与外部工具的标准接口

## 什么是 MCP（Model Context Protocol）

Anthropic 提出的开放协议，定义 Agent 和外部工具/数据源之间的标准通信方式。类似于"AI 工具世界的 HTTP 协议"。

传统方式：每个工具自己定义接口（函数签名、错误格式、权限模型各不相同）。MCP 统一了这些。

## 核心概念

### Server（工具提供方）
独立进程，暴露一组 tools/prompts/resources。
```
qdrant-mcp-server → Agent 可以通过 MCP 调用 Qdrant 操作
github-mcp-server → Agent 可以通过 MCP 操作 GitHub API
```

### Client（Agent 所在端）
通过 JSON-RPC over stdio/SSE 与 Server 通信。

### 工作流
1. Client 启动时连接 Server
2. Server 注册自己提供的 tools/prompts/resources
3. Agent 运行时，工具调用走 MCP 协议（标准化格式）
4. Server 返回标准化响应

## 为什么重要

MCP 让 Agent 的工具生态从"每个自研"变成"插件市场"。你的 Agent 可以直接用社区已有的 MCP Server，无需自己写 wrapper。

## 面试回答要点
"我的工具系统预留了 MCP 兼容接口。这意味着社区已有的 qdrant-mcp-server、langchain-mcp-server 可以直接接入。不需要每个工具都自研 wrapper。"
