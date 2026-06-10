# EcomAgent API Reference

> Base URL: `http://localhost:8000`

## Agent Endpoints

### POST /agent/ticket
Execute full agent workflow (intent classification → workers → draft → hallucination check)

**Request Body:**
```json
{
  "ticket_id": "ex-001",
  "user_query": "我想把T恤从M码换成L码",
  "top_k": 5,
  "user_context": {
    "tenant_id": "corp-default",
    "roles": ["support_agent"]
  },
  "customer_id": null,
  "customer_tier": null,
  "session_id": null,
  "conversation_history": null
}
```

**Response:**
```json
{
  "ticket_id": "ex-001",
  "user_query": "我想把T恤从M码换成L码",
  "final_action": "draft_ready",
  "human_review_required": false,
  "draft_reply": "- 您的换货申请符合7天无理由退换政策...\n- L码有库存（上海仓23件）...",
  "ticket_note": "已生成建议回复，可经客服确认后发送。",
  "gate_passed": true,
  "audit_trace": [
    {"step": "policy", "skip_rag": false, "action": "allow_log"},
    {"step": "supervisor", "intent": "exchange", "emotion": null, "domain": "exchange", "confidence": 0.9},
    ...
  ]
}
```

**Intents:** The agent auto-detects intent from the user query:
- `exchange` — parallel Policy + Inventory + Logistics checks
- `refund` — quality check + refund policy + ticket creation
- `complaint` — emotion-aware (angry → urgent, neutral → normal)
- `tracking` — shipment status lookup

### POST /agent/ticket/stream
SSE-streamed version of the agent workflow. Events:

| Event | Payload | Description |
|-------|---------|-------------|
| `step` | `{"step":"policy","skip_rag":false}` | Audit step completed |
| `token` | `{"text":"回复内容..."}` | Draft token (simulated streaming) |
| `done` | Full response object | Workflow completed |
| `error` | `{"message":"...","status_code":503}` | Error occurred |

**Intent Routing (Supervisor):**

| Input Domain | Routed Intent | Parallel Workers |
|-------------|---------------|-----------------|
| exchange | exchange | policy_check + inventory_query + create_pickup |
| refund | refund | retrieve → gate → grader → draft (serial) |
| return_policy | refund | Same as refund |
| complaint | complaint | emotion detection → escalated ticket |
| shipping | tracking | Shipment lookup |

## RAG Endpoints

### POST /retrieve
Vector + BM25 hybrid retrieval.

**Request:**
```json
{
  "query": "退货政策是什么？",
  "top_k": 5,
  "include_all_domains": true
}
```

### POST /chat
RAG chat with LLM response.

## Ticket Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/tickets | List all tickets |
| POST | /api/tickets | Create new ticket |
| GET | /api/tickets/{id} | Get ticket detail |
| PUT | /api/tickets/{id} | Update ticket |

## System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Liveness check |
| GET | /health/ready | Readiness probe (checks BM25 + Qdrant) |
| GET | /health/config | Runtime configuration dump |
| GET | /metrics | Prometheus-format metrics |
| GET | /docs | OpenAPI Swagger UI |

## Error Codes

| Code | Description |
|------|-------------|
| `NO_RESULTS` | RAG pipeline returned zero chunks |
| `GATE_FAIL` | Similarity gate threshold not met |
| `TIMEOUT` | Agent workflow exceeded timeout |
| `LLM_FAILURE` | LLM call failed after retries |

## Tool Schemas (OpenAI function-calling format)

Six e-commerce after-sales tools are registered for agent use:

- `order_lookup`: Fuzzy order search by user/product keyword
- `policy_check`: Return eligibility evaluation (7-day/damaged/denied)
- `inventory_query`: Multi-warehouse stock by SKU + size
- `create_pickup`: Return pickup scheduling (next-day)
- `track_shipment`: Real-time logistics tracking
- `create_after_sale_ticket`: SLA-tiered ticket creation (P0 2h - P3 72h)
