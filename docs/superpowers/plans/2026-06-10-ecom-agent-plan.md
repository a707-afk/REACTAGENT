# EcomAgent Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform REACTAGENT from a generic customer service Agent into an e-commerce after-sales multi-Agent system with Supervisor-Worker orchestration, 6 domain-specific tools, and mock enterprise integrations.

**Architecture:** Supervisor routes user intent (exchange/refund/complaint/tracking) to the correct flow. Exchange flow uses asyncio.gather to run 3 parallel Workers (Policy/Inventory/Logistics). All Worker internals reuse existing retrieval→gate→grade→draft→hallucination pipeline.

**Tech Stack:** Python 3.12 / FastAPI / LangGraph / Qdrant / PostgreSQL / asyncio / Locust / React 18

**Spec reference:** `docs/superpowers/specs/2026-06-10-ecom-agent-design.md`

---

## File Structure Map

```
Create:
  app/mock/__init__.py              — Mock data package
  app/mock/orders.py                — 3 order fixtures covering full/partial/denied
  app/mock/inventory.py             — Inventory mock (SKU→stock)
  app/mock/logistics.py             — Logistics mock (tracking+pickup)
  app/supervisor/__init__.py        — Supervisor package
  app/supervisor/router.py          — Intent routing (exchange/refund/complaint/tracking)
  data/docs_ecom/                   — JD售后政策 + LLM FAQ markdowns

Modify:
  app/agent/tools.py                — 6 e-com tools (3 renamed + 3 new)
  app/agent_graph/nodes.py          — Add node_exchange_parallel, modify node_reason
  app/agent_graph/graph.py          — Add parallel node + routing edges
  app/domain_router.py              — 15 CS domains → 4 intent routes
  app/config.py                     — Device auto-detection
  frontend/src/App.tsx              — Order panel + ticket timeline
  frontend/src/api.ts               — New API endpoints
  README.md                         — Rewrite for e-commerce

Preserved (no changes):
  app/retrieval_pipeline.py, app/rerank.py, app/bm25_store.py
  app/chunking.py, app/citation_verify.py, app/retrieval_gates.py
  app/behavior_guard.py, app/policy/, app/db/, app/services/
  app/agent_graph/fault_tolerance.py, app/agent_graph/state.py
  app/api/chat.py, app/api/tickets.py, app/api/deps.py
```

---

## Chunk 1: Environment Verification + Branch

### Task 1.1: Verify existing code runs

- [ ] **Step 1: Check Python and dependencies**

```bash
cd E:/经项目/rag-kb-project
.venv/Scripts/python.exe --version
pip install -r requirements.txt 2>&1 | tail -5
```
Expected: Python 3.12+, no dependency errors.

- [ ] **Step 2: Start services and test /health**

```bash
docker compose up -d
sleep 10
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}` or similar.

- [ ] **Step 3: Test /agent/ticket endpoint**

```bash
curl -X POST http://localhost:8000/agent/ticket \
  -H "Content-Type: application/json" \
  -d '{"query": "我想退款", "user_id": "u001"}'
```
Expected: Valid JSON response (may use fallback if GPU models unavailable).

- [ ] **Step 4: Record any blocking issues**

If models not found or API key missing, note as TODO. Do NOT block the plan on GPU model availability — the system should work in API-only mode for development.

- [ ] **Step 5: Commit verification report**

```bash
git add -A
git commit -m "chore: environment verification - existing code runs"
```

---

## Chunk 2: Mock Data Layer

### Task 2.1: Order mock data

**Files:**
- Create: `app/mock/__init__.py`
- Create: `app/mock/orders.py`

- [ ] **Step 1: Write `app/mock/__init__.py`**

```python
"""Mock data layer for EcomAgent — simulates order/inventory/logistics APIs."""
```

- [ ] **Step 2: Write `app/mock/orders.py`**

```python
"""Mock order data with three policy states: full refund, partial refund, denied."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class MockOrder:
    order_id: str
    user_id: str
    product_name: str
    product_sku: str
    size: str
    color: str
    amount: float
    purchase_date: str       # ISO date
    status: str              # "unopened" / "opened_damaged" / "used"
    carrier: str = "顺丰"

ORDERS: list[MockOrder] = [
    MockOrder(
        order_id="ORD-001",
        user_id="u001",
        product_name="XX品牌白色T恤",
        product_sku="TEE-WHITE",
        size="M",
        color="白色",
        amount=129.00,
        purchase_date="2026-06-05",
        status="unopened",
    ),
    MockOrder(
        order_id="ORD-002",
        user_id="u001",
        product_name="YY品牌黑色T恤",
        product_sku="TEE-BLACK",
        size="L",
        color="黑色",
        amount=89.00,
        purchase_date="2026-05-25",
        status="opened_damaged",
    ),
    MockOrder(
        order_id="ORD-003",
        user_id="u001",
        product_name="ZZ品牌卫衣",
        product_sku="HD-GREY",
        size="XL",
        color="灰色",
        amount=299.00,
        purchase_date="2026-04-01",
        status="used",
    ),
    MockOrder(
        order_id="ORD-004",
        user_id="u001",
        product_name="AA品牌运动鞋",
        product_sku="SN-RED",
        size="42",
        color="红色",
        amount=399.00,
        purchase_date="2026-06-08",
        status="unopened",
    ),
]


def lookup_orders(user_id: str, keyword: str = "", limit: int = 3) -> list[dict]:
    """Fuzzy-match orders by user_id and optional product keyword."""
    results = []
    keyword_lower = keyword.lower()
    for order in ORDERS:
        if order.user_id != user_id:
            continue
        if keyword_lower and keyword_lower not in order.product_name.lower():
            continue
        results.append({
            "order_id": order.order_id,
            "product": f"{order.product_name} {order.size}码 {order.color}",
            "sku": order.product_sku,
            "size": order.size,
            "color": order.color,
            "amount": order.amount,
            "purchase_date": order.purchase_date,
            "status": order.status,
            "carrier": order.carrier,
        })
    return results[:limit]


def get_order(order_id: str) -> dict | None:
    """Get single order by ID."""
    for order in ORDERS:
        if order.order_id == order_id:
            return {
                "order_id": order.order_id,
                "product": f"{order.product_name} {order.size}码 {order.color}",
                "sku": order.product_sku,
                "size": order.size,
                "color": order.color,
                "amount": order.amount,
                "purchase_date": order.purchase_date,
                "status": order.status,
                "carrier": order.carrier,
                "user_id": order.user_id,
            }
    return None


def days_since_purchase(order_id: str) -> int:
    """Calculate days since purchase for policy check."""
    order = get_order(order_id)
    if not order:
        return 999
    purchase = datetime.strptime(order["purchase_date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - purchase).days
```

- [ ] **Step 3: Test mock data**

```bash
cd E:/经项目/rag-kb-project
.venv/Scripts/python.exe -c "
from app.mock.orders import lookup_orders, get_order, days_since_purchase
print(lookup_orders('u001', 'T恤'))
print(get_order('ORD-001'))
print(f'Days since ORD-001: {days_since_purchase(\"ORD-001\")}')
print(f'Days since ORD-002: {days_since_purchase(\"ORD-002\")}')
"
```
Expected: ORD-001 ~5 days, ORD-002 ~16 days.

- [ ] **Step 4: Commit**

```bash
git add app/mock/__init__.py app/mock/orders.py
git commit -m "feat: add mock order data layer with 3 policy states"
```

### Task 2.2: Inventory mock

**Files:**
- Create: `app/mock/inventory.py`

- [ ] **Step 1: Write `app/mock/inventory.py`**

```python
"""Mock inventory data for EcomAgent."""

INVENTORY: dict[str, dict[str, dict[str, int]]] = {
    "TEE-WHITE": {
        "M": {"上海仓": 0, "北京仓": 0},
        "L": {"上海仓": 23, "北京仓": 0},
        "XL": {"上海仓": 5, "北京仓": 3},
    },
    "TEE-BLACK": {
        "M": {"上海仓": 8, "北京仓": 2},
        "L": {"上海仓": 5, "北京仓": 0},
    },
    "HD-GREY": {
        "L": {"上海仓": 0, "北京仓": 0},
        "XL": {"上海仓": 0, "北京仓": 0},
    },
    "SN-RED": {
        "42": {"上海仓": 10, "北京仓": 5},
    },
}


def query_inventory(sku: str, size: str, color: str = "") -> dict:
    """Query inventory for a specific SKU and size."""
    sku_data = INVENTORY.get(sku.upper(), {})
    size_data = sku_data.get(size, {})
    
    total = sum(size_data.values())
    warehouses = {k: v for k, v in size_data.items() if v > 0}

    if total == 0:
        return {
            "available": False,
            "stock": 0,
            "warehouse": None,
            "message": f"{size}码已售罄，建议查看其他尺码或颜色",
        }

    primary_warehouse = max(warehouses, key=warehouses.get) if warehouses else "上海仓"
    return {
        "available": True,
        "stock": total,
        "warehouse": primary_warehouse,
        "warehouses": warehouses,
        "estimated_delivery": "1-2天" if primary_warehouse == "上海仓" else "3-5天",
    }
```

- [ ] **Step 2: Test**

```bash
.venv/Scripts/python.exe -c "
from app.mock.inventory import query_inventory
print(query_inventory('TEE-WHITE', 'L'))   # available=23
print(query_inventory('TEE-WHITE', 'M'))   # available=False
"
```

- [ ] **Step 3: Commit**

```bash
git add app/mock/inventory.py
git commit -m "feat: add mock inventory layer"
```

### Task 2.3: Logistics mock

**Files:**
- Create: `app/mock/logistics.py`

- [ ] **Step 1: Write `app/mock/logistics.py`**

```python
"""Mock logistics data for EcomAgent."""
from datetime import datetime, timedelta, timezone

SHIPMENTS: dict[str, dict] = {
    "ORD-001": {
        "status": "已签收",
        "carrier": "顺丰",
        "last_update": "2026-06-07 10:15 已签收",
        "estimated_delivery": "2026-06-07",
    },
    "ORD-004": {
        "status": "运输中",
        "carrier": "中通",
        "last_update": "2026-06-10 14:32 已到达上海转运中心",
        "estimated_delivery": "2026-06-11",
    },
}


def track_shipment(order_id: str) -> dict:
    """Track shipment for an order."""
    if order_id in SHIPMENTS:
        return SHIPMENTS[order_id]
    return {
        "status": "未找到物流信息",
        "carrier": None,
        "last_update": None,
        "estimated_delivery": None,
        "message": "该订单暂无物流信息，可能尚未发货",
    }


def create_pickup(order_id: str, address: str) -> dict:
    """Generate a pickup request (mock)."""
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "pickup_id": f"PU{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
        "order_id": order_id,
        "address": address,
        "scheduled": f"{tomorrow} 9:00-18:00",
        "carrier": "顺丰",
        "message": f"上门取件已预约：{tomorrow} 9:00-18:00",
    }
```

- [ ] **Step 2: Commit**

```bash
git add app/mock/logistics.py
git commit -m "feat: add mock logistics layer (tracking + pickup)"
```

---

## Chunk 3: Domain Router Refactoring

### Task 3.1: Change 15 CS domains to 4 intent routes

**Files:**
- Modify: `app/domain_router.py`

- [ ] **Step 1: Read current router to understand structure**

The existing router uses Keyword + Embedding dual-path + Zhipu LLM fallback + Platt calibration for 15 CS domains. We simplify to 4 intents with LLM-based classification.

- [ ] **Step 2: Write new router**

Replace `app/domain_router.py` content:

```python
"""Intent router for EcomAgent — classify user query into 4 intent types."""
from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

INTENTS = ["exchange", "refund", "complaint", "tracking"]

KEYWORD_MAP: dict[str, list[str]] = {
    "exchange": ["换", "换货", "尺码", "大小", "颜色", "型号", "exchange", "swap"],
    "refund": ["退", "退款", "退货", "退钱", "不要了", "refund", "return"],
    "complaint": ["投诉", "举报", "差评", "质量差", "态度", "complaint", "不满意"],
    "tracking": ["物流", "快递", "到哪", "发货", "tracking", "shipment"],
}


@dataclass
class IntentResult:
    intent: str
    confidence: float
    order_hint: str = ""
    emotion: str | None = None
    reason: str = ""


def classify_intent(query: str) -> IntentResult:
    """Classify user query into one of 4 intents using keyword + LLM fallback."""
    query_lower = query.lower()
    scores: dict[str, int] = {intent: 0 for intent in INTENTS}

    for intent, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in query_lower:
                scores[intent] += 1

    # Extract order hint (product keywords from query)
    order_hint = _extract_order_hint(query)

    # Strong keyword signal → skip LLM
    max_score = max(scores.values())
    if max_score >= 2:
        best = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return IntentResult(
            intent=best[0][0],
            confidence=min(0.95, 0.7 + max_score * 0.1),
            order_hint=order_hint,
            reason=f"keyword match: {max_score} hits",
        )

    # One keyword hit → medium confidence
    if max_score == 1:
        best = [k for k, v in scores.items() if v == 1]
        return IntentResult(
            intent=best[0],
            confidence=0.65,
            order_hint=order_hint,
            reason="single keyword match",
        )

    # No keyword → LLM fallback
    try:
        from app.llm_zhipu import chat_completion
        prompt = (
            "分析用户意图，返回JSON。\n"
            "意图类型: exchange(换货) / refund(退款) / complaint(投诉) / tracking(物流查询)\n"
            '格式: {"intent":"exchange","emotion":null,"order_hint":"T恤"}\n'
            f"用户输入: {query}"
        )
        raw = chat_completion("你是电商售后意图分类助手。", prompt)
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            obj = json.loads(m.group())
            return IntentResult(
                intent=obj.get("intent", "refund"),
                confidence=0.70,
                order_hint=obj.get("order_hint", ""),
                emotion=obj.get("emotion"),
                reason="LLM classification",
            )
    except Exception as e:
        logger.warning("Intent LLM fallback failed: %s", e)

    return IntentResult(intent="refund", confidence=0.50, order_hint=order_hint, reason="default")


def _extract_order_hint(query: str) -> str:
    """Extract product keywords from query for order lookup."""
    product_keywords = ["T恤", "卫衣", "衬衫", "裤子", "裙子", "外套", "鞋", "包", "手机", "电脑"]
    for kw in product_keywords:
        if kw in query:
            return kw
    return ""
```

- [ ] **Step 3: Test router**

```bash
.venv/Scripts/python.exe -c "
from app.domain_router import classify_intent
tests = [
    '买了件M码T恤太小了换L码',
    '我要退款，质量太差了',
    '投诉你们客服态度不好',
    '我的快递到哪了',
]
for t in tests:
    r = classify_intent(t)
    print(f'{t[:30]:30s} → {r.intent:10s} conf={r.confidence:.2f}')
"
```
Expected: exchange / refund / complaint / tracking.

- [ ] **Step 4: Commit**

```bash
git add app/domain_router.py
git commit -m "refactor: change domain_router from 15 CS domains to 4 intent routes"
```

---

## Chunk 4: Knowledge Base Replacement

### Task 4.1: Scrape JD return policy + construct FAQ

**Files:**
- Create: `data/docs_ecom/` directory
- Create: `scripts/build_ecom_kb.py`

- [ ] **Step 1: Create e-commerce knowledge base directory**

```bash
mkdir -p "E:/经项目/rag-kb-project/data/docs_ecom"
```

- [ ] **Step 2: Write `scripts/build_ecom_kb.py`**

This script creates the e-commerce knowledge base from:
1. Manually curated JD policy excerpts (saved as .md files in data/docs_ecom/)
2. LLM-generated FAQ pairs

```python
"""Build e-commerce knowledge base for EcomAgent."""
import json
import os

FAQ_ENTRIES = [
    {"topic": "return_policy", "q": "7天无理由退货条件是什么？", "a": "自签收之日起7日内，商品完好、配件齐全、不影响二次销售，可申请7天无理由退货。定制商品、生鲜、虚拟商品除外。"},
    {"topic": "return_policy", "q": "超过7天还能退货吗？", "a": "超过7天但在30天内，商品出现质量问题可申请换货或部分退款。超过30天一般不可退换，但平台会根据具体情况与商家协商。"},
    {"topic": "exchange", "q": "换货流程是怎样的？", "a": "申请换货→平台审核→预约上门取件→商家收到退货→发出新商品。全程3-5个工作日。"},
    {"topic": "exchange", "q": "换货需要自己付运费吗？", "a": "质量问题换货运费由商家承担。7天无理由换货，首次换货平台承担运费。"},
    {"topic": "refund", "q": "退款多久到账？", "a": "商家收到退货后1-3个工作日内审核，审核通过后1-7个工作日退回原支付方式。"},
    {"topic": "refund", "q": "部分退款怎么计算？", "a": "已拆封影响二次销售的商品，根据商品状态扣除10%-15%折旧费后退还剩余金额。"},
    {"topic": "complaint", "q": "如何投诉商家？", "a": "进入订单详情→点击投诉→选择投诉类型→填写投诉内容→提交。平台会在24小时内处理。"},
    {"topic": "complaint", "q": "投诉后多久回复？", "a": "一般投诉24小时内回复，紧急投诉2小时内优先级处理。涉及金额较大的投诉会升级为P0工单。"},
    {"topic": "shipping", "q": "快递查询怎么用？", "a": "在订单详情中点击查看物流，可实时追踪包裹位置和预计送达时间。"},
    {"topic": "shipping", "q": "物流超时怎么办？", "a": "物流超时超过承诺时效，可申请赔付。标准快递超时赔付订单金额的5%，生鲜超时赔付10%。"},
    # Additional ~50 entries generated similarly
    {"topic": "exchange", "q": "换货可以换不同颜色吗？", "a": "可以。换货支持更换颜色和尺码，但需为同款商品。差价多退少补。"},
    {"topic": "refund", "q": "退款时优惠券能退回吗？", "a": "全额退款时优惠券退回账户。部分退款时优惠券按比例退回。已过期优惠券不退。"},
    {"topic": "return_policy", "q": "哪些商品不支持退换？", "a": "内衣、定制商品、生鲜食品、虚拟商品、已激活的数码产品不支持7天无理由退换。"},
]


def build_faq_markdown(output_dir: str):
    """Write FAQ entries as markdown files for indexing."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Group by topic
    by_topic: dict[str, list[dict]] = {}
    for entry in FAQ_ENTRIES:
        by_topic.setdefault(entry["topic"], []).append(entry)
    
    for topic, entries in by_topic.items():
        path = os.path.join(output_dir, f"faq_{topic}.md")
        lines = [f"# {topic.replace('_', ' ').title()} FAQ\n"]
        for e in entries:
            lines.append(f"## Q: {e['q']}")
            lines.append(f"A: {e['a']}\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"Wrote {len(entries)} entries to {path}")


if __name__ == "__main__":
    build_faq_markdown("data/docs_ecom")
```

- [ ] **Step 3: Run FAQ builder**

```bash
.venv/Scripts/python.exe scripts/build_ecom_kb.py
```
Expected: Creates `data/docs_ecom/faq_return_policy.md` etc.

- [ ] **Step 4: Add JD policy documents**

Create `data/docs_ecom/jd_return_policy.md` with manually copied JD return policy text (from jd.com public pages). This is a manual step — use the actual policy text from JD's help center.

- [ ] **Step 5: Rebuild indices with ecom data**

```bash
# Update reindex script or create a new one
.venv/Scripts/python.exe -c "
from app.chunking import chunk_documents
from app.vector_index import get_vector_index
from app.bm25_store import build_bm25_index
# ... rebuild both Qdrant and BM25 for data/docs_ecom/
print('Rebuilding knowledge base with e-commerce data...')
"
```

- [ ] **Step 6: Commit**

```bash
git add data/docs_ecom/ scripts/build_ecom_kb.py
git commit -m "feat: replace knowledge base with e-commerce JD policy + FAQ"
```

---

## Chunk 5: Agent Tools Redefinition

### Task 5.1: Rewrite tools.py with 6 e-commerce tools

**Files:**
- Modify: `app/agent/tools.py`

- [ ] **Step 1: Replace `app/agent/tools.py`**

Full rewrite — replace all 4 tools with 6 tools: order_lookup, policy_check, inventory_query, create_pickup, track_shipment, create_after_sale_ticket.

```python
"""EcomAgent tools: 6 e-commerce after-sales tools (OpenAI function-calling format)."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.agent_graph.state import TicketAgentState

logger = logging.getLogger(__name__)


# ── Tool Schema Definitions ──

TOOL_ORDER_LOOKUP = {
    "type": "function",
    "function": {
        "name": "order_lookup",
        "description": "Look up user's recent orders by keyword. Returns matching orders with product details, purchase date, and status.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User ID for order lookup."},
                "keyword": {"type": "string", "description": "Product keyword to filter orders (e.g. 'T恤')."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 3},
            },
            "required": ["user_id"],
        },
    },
}

TOOL_POLICY_CHECK = {
    "type": "function",
    "function": {
        "name": "policy_check",
        "description": "Check if an order is eligible for return/exchange based on platform policy. Considers days since purchase and product condition.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID to check."},
                "return_reason": {"type": "string", "description": "Reason for return/exchange."},
            },
            "required": ["order_id", "return_reason"],
        },
    },
}

TOOL_INVENTORY_QUERY = {
    "type": "function",
    "function": {
        "name": "inventory_query",
        "description": "Check inventory availability for a specific SKU, size, and color.",
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Product SKU."},
                "size": {"type": "string", "description": "Target size (e.g. 'L')."},
                "color": {"type": "string", "description": "Target color."},
            },
            "required": ["sku", "size"],
        },
    },
}

TOOL_CREATE_PICKUP = {
    "type": "function",
    "function": {
        "name": "create_pickup",
        "description": "Create a pickup request for return/exchange. Generates a pickup order with scheduled time.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID for pickup."},
                "address": {"type": "string", "description": "Pickup address."},
            },
            "required": ["order_id", "address"],
        },
    },
}

TOOL_TRACK_SHIPMENT = {
    "type": "function",
    "function": {
        "name": "track_shipment",
        "description": "Track the shipping status of an order.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID to track."},
            },
            "required": ["order_id"],
        },
    },
}

TOOL_CREATE_AFTER_SALE_TICKET = {
    "type": "function",
    "function": {
        "name": "create_after_sale_ticket",
        "description": "Create an after-sales ticket (exchange/refund/complaint) with priority and SLA tracking.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["exchange", "refund", "complaint"], "description": "Ticket type."},
                "priority": {"type": "string", "enum": ["p0_critical", "p1_high", "p2_medium", "p3_low"]},
                "order_id": {"type": "string", "description": "Related order ID."},
                "detail": {"type": "string", "description": "Ticket detail description."},
            },
            "required": ["type", "priority", "order_id", "detail"],
        },
    },
}

ALL_TOOLS = [
    TOOL_ORDER_LOOKUP, TOOL_POLICY_CHECK, TOOL_INVENTORY_QUERY,
    TOOL_CREATE_PICKUP, TOOL_TRACK_SHIPMENT, TOOL_CREATE_AFTER_SALE_TICKET,
]


# ── Tool Result ──

@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


# ── Tool Implementations ──

def _execute_order_lookup(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    user_id = str(args.get("user_id", state.get("user_id", "u001")))
    keyword = str(args.get("keyword", ""))
    limit = min(int(args.get("limit", 3)), 5)
    from app.mock.orders import lookup_orders
    orders = lookup_orders(user_id, keyword, limit)
    return ToolResult("order_lookup", True, data={"orders": orders, "count": len(orders)})


def _execute_policy_check(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    order_id = str(args.get("order_id", ""))
    reason = str(args.get("return_reason", "未说明"))
    from app.mock.orders import get_order, days_since_purchase
    order = get_order(order_id)
    if not order:
        return ToolResult("policy_check", False, error=f"Order {order_id} not found")

    days = days_since_purchase(order_id)
    status = order.get("status", "")
    
    if days <= 7 and status == "unopened":
        return ToolResult("policy_check", True, data={
            "eligible": True, "policy": "7天无理由退换", "refund_type": "full",
            "days": days, "reason": f"购买{days}天，未拆封，符合全额退换条件", "deduction_rate": 0,
        })
    elif days <= 30 and status == "opened_damaged":
        return ToolResult("policy_check", True, data={
            "eligible": True, "policy": "质量问题退换", "refund_type": "partial",
            "days": days, "reason": f"购买{days}天，已拆封影响二次销售，部分退款(扣10%)", "deduction_rate": 0.10,
        })
    else:
        return ToolResult("policy_check", True, data={
            "eligible": False, "policy": "超出退换期限", "refund_type": "denied",
            "days": days, "reason": f"购买{days}天，超出退换期限", "deduction_rate": 0,
        })


def _execute_inventory_query(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    sku = str(args.get("sku", "")).upper()
    size = str(args.get("size", ""))
    color = str(args.get("color", ""))
    from app.mock.inventory import query_inventory
    result = query_inventory(sku, size, color)
    return ToolResult("inventory_query", True, data=result)


def _execute_create_pickup(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    order_id = str(args.get("order_id", ""))
    address = str(args.get("address", state.get("pickup_address", "未提供地址")))
    from app.mock.logistics import create_pickup
    result = create_pickup(order_id, address)
    return ToolResult("create_pickup", True, data=result)


def _execute_track_shipment(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    order_id = str(args.get("order_id", ""))
    from app.mock.logistics import track_shipment
    result = track_shipment(order_id)
    return ToolResult("track_shipment", True, data=result)


def _execute_create_after_sale_ticket(state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    ticket_type = str(args.get("type", "refund"))
    priority = str(args.get("priority", "p2_medium"))
    order_id = str(args.get("order_id", "unknown"))
    detail = str(args.get("detail", ""))[:500]
    
    # SLA deadline calculation
    sla_hours = {"p0_critical": 2, "p1_high": 4, "p2_medium": 24, "p3_low": 72}
    hours = sla_hours.get(priority, 24)
    sla_deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    ticket_id = f"AS{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return ToolResult("create_after_sale_ticket", True, data={
        "ticket_id": ticket_id,
        "type": ticket_type,
        "priority": priority,
        "status": "NEW",
        "sla_deadline": sla_deadline.isoformat(),
        "sla_hours": hours,
        "order_id": order_id,
        "detail": detail,
    })


TOOL_DISPATCH = {
    "order_lookup": _execute_order_lookup,
    "policy_check": _execute_policy_check,
    "inventory_query": _execute_inventory_query,
    "create_pickup": _execute_create_pickup,
    "track_shipment": _execute_track_shipment,
    "create_after_sale_ticket": _execute_create_after_sale_ticket,
}


def execute_tool(tool_name: str, state: TicketAgentState, args: dict[str, Any]) -> ToolResult:
    handler = TOOL_DISPATCH.get(tool_name)
    if handler is None:
        return ToolResult(tool_name, False, error=f"Unknown tool: {tool_name}")
    try:
        return handler(state, args)
    except Exception as e:
        logger.exception("Tool %s execution failed", tool_name)
        return ToolResult(tool_name, False, error=str(e))
```

- [ ] **Step 2: Test all 6 tools**

```bash
.venv/Scripts/python.exe -c "
from app.agent.tools import execute_tool, ToolResult
state = {'user_id': 'u001', 'trace_id': 'test'}
print(execute_tool('order_lookup', state, {'user_id': 'u001', 'keyword': 'T恤'}))
print(execute_tool('policy_check', state, {'order_id': 'ORD-001', 'return_reason': '尺码不合适'}))
print(execute_tool('inventory_query', state, {'sku': 'TEE-WHITE', 'size': 'L'}))
print(execute_tool('create_pickup', state, {'order_id': 'ORD-001', 'address': '上海'}))
print(execute_tool('track_shipment', state, {'order_id': 'ORD-004'}))
print(execute_tool('create_after_sale_ticket', state, {'type': 'exchange', 'priority': 'p2_medium', 'order_id': 'ORD-001', 'detail': '换L码'}))
"
```

- [ ] **Step 3: Commit**

```bash
git add app/agent/tools.py
git commit -m "feat: replace 4 CS tools with 6 e-commerce after-sales tools"
```

---

## Chunk 6: Supervisor + Worker Orchestration

### Task 6.1: Add Supervisor router module

**Files:**
- Create: `app/supervisor/__init__.py`
- Create: `app/supervisor/router.py`

- [ ] **Step 1: Write `app/supervisor/router.py`**

```python
"""Supervisor intent router — classifies user intent and dispatches to Worker flows."""
from __future__ import annotations
import json
import logging
import re
from typing import Any

from app.agent_graph.state import TicketAgentState
from app.domain_router import classify_intent, IntentResult

logger = logging.getLogger(__name__)

SUPERVISOR_PROMPT = (
    "你是电商售后AI智能体的Supervisor。分析用户输入，输出JSON：\n"
    '{"intent":"exchange|refund|complaint|tracking","emotion":null|"angry"|"neutral","order_hint":"商品关键词"}\n'
    "intent规则：\n"
    "- exchange: 用户想换货（换尺码/颜色/型号）\n"
    "- refund: 用户想退款/退货\n"
    "- complaint: 用户投诉/不满\n"
    "- tracking: 查询物流/快递\n"
    "emotion规则（仅complaint时输出）：\n"
    "- angry: 愤怒（用了感叹号、脏话、威胁投诉）\n"
    "- neutral: 一般不满\n"
)


def route_intent(state: TicketAgentState) -> dict[str, Any]:
    """Supervisor node: classify intent and prepare routing."""
    query = (state.get("user_query") or "").strip()
    
    # Use the domain_router for classification
    result = classify_intent(query)
    
    # For complaints, also detect emotion (inline in Supervisor, not separate tool)
    emotion = None
    if result.intent == "complaint":
        emotion = _detect_emotion(query)
    
    return {
        "intent": result.intent,
        "emotion": emotion,
        "order_hint": result.order_hint,
        "intent_confidence": result.confidence,
        "audit_trace": state.get("audit_trace", []) + [{
            "step": "supervisor",
            "intent": result.intent,
            "emotion": emotion,
            "confidence": result.confidence,
        }],
    }


def _detect_emotion(query: str) -> str:
    """Inline emotion detection — angry keywords or LLM fallback."""
    angry_keywords = ["垃圾", "骗子", "投诉你", "差评", "举报", "气死", "退款", "!!!", "！！"]
    query_lower = query.lower()
    for kw in angry_keywords:
        if kw in query_lower:
            return "angry"
    
    # Check for exclamation intensity
    if query.count("!") + query.count("！") >= 2:
        return "angry"
    
    return "neutral"


def route_after_supervisor(state: TicketAgentState) -> str:
    """LangGraph routing function: direct to correct flow based on intent."""
    intent = state.get("intent", "refund")
    if intent == "exchange":
        return "exchange_parallel"
    elif intent == "refund":
        return "retrieve"  # Standard refund flow uses existing retrieve→draft pipeline
    elif intent == "complaint":
        emotion = state.get("emotion", "neutral")
        if emotion == "angry":
            return "complaint_urgent"
        return "complaint_standard"
    elif intent == "tracking":
        return "tracking_lookup"
    return "retrieve"
```

- [ ] **Step 2: Commit**

```bash
git add app/supervisor/
git commit -m "feat: add Supervisor intent router + emotion detection"
```

### Task 6.2: Add exchange_parallel node to nodes.py

**Files:**
- Modify: `app/agent_graph/nodes.py`

- [ ] **Step 1: Add `node_exchange_parallel` to end of nodes.py**

```python
async def node_exchange_parallel(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """Exchange flow: run Policy + Inventory + Logistics checks in parallel via asyncio.gather."""
    _ = settings
    from app.agent.tools import execute_tool
    import asyncio
    
    order_id = state.get("order_id") or (state.get("retrieved_chunks") or [{}])[0].get("order_id", "ORD-001")
    reason = state.get("return_reason") or "尺码不合适"
    
    # Extract SKU info from state or order lookup
    sku = state.get("product_sku", "TEE-WHITE")
    size = state.get("target_size", "L")
    color = state.get("target_color", "白色")
    address = state.get("pickup_address", "默认地址（Mock）")
    
    async def policy_worker():
        return execute_tool("policy_check", state, {"order_id": order_id, "return_reason": reason})
    
    async def inventory_worker():
        return execute_tool("inventory_query", state, {"sku": sku, "size": size, "color": color})
    
    async def logistics_worker():
        return execute_tool("create_pickup", state, {"order_id": order_id, "address": address})
    
    # Parallel execution — slowest worker determines total response time
    policy_r, inventory_r, logistics_r = await asyncio.gather(
        policy_worker(), inventory_worker(), logistics_worker(),
        return_exceptions=True,
    )
    
    def _unwrap(r):
        if isinstance(r, Exception):
            return {"success": False, "error": str(r)}
        if isinstance(r, dict):
            return r
        return r.__dict__ if hasattr(r, '__dict__') else str(r)
    
    policy_data = _unwrap(policy_r) if not isinstance(policy_r, Exception) else {"success": False, "error": str(policy_r)}
    inventory_data = _unwrap(inventory_r) if not isinstance(inventory_r, Exception) else {"success": False, "error": str(inventory_r)}
    logistics_data = _unwrap(logistics_r) if not isinstance(logistics_r, Exception) else {"success": False, "error": str(logistics_r)}
    
    all_ok = (
        not isinstance(policy_r, Exception) and
        not isinstance(inventory_r, Exception) and
        not isinstance(logistics_r, Exception)
    )
    
    # Build human-readable summary
    lines = []
    if policy_data.get("success", True) and not policy_data.get("error"):
        pd = policy_data.get("data", policy_data)
        if pd.get("eligible"):
            lines.append(f"**Policy**: {pd.get('policy', '可退换')} — {pd.get('reason', '')}")
        else:
            lines.append(f"**Policy**: 不符合退换条件 — {pd.get('reason', '')}")
    
    if inventory_data.get("success", True) and not inventory_data.get("error"):
        id_ = inventory_data.get("data", inventory_data)
        if id_.get("available"):
            lines.append(f"**Inventory**: {size}码有货（{id_.get('warehouse', '仓库')}，库存{id_.get('stock', 0)}件）")
        else:
            lines.append(f"**Inventory**: {size}码已售罄 — {id_.get('message', '')}")
    
    if logistics_data.get("success", True) and not logistics_data.get("error"):
        ld = logistics_data.get("data", logistics_data)
        lines.append(f"**Logistics**: 取件已预约 — {ld.get('scheduled', '')}（{ld.get('carrier', '顺丰')}）")
    
    summary = "\n".join(f"  {line}" for line in lines)
    
    return {
        "policy_result": policy_data,
        "inventory_result": inventory_data,
        "logistics_result": logistics_data,
        "exchange_ready": all_ok,
        "exchange_summary": summary,
        "retrieved_chunks": [{"text": summary}],
        "audit_trace": state.get("audit_trace", []) + [{
            "step": "exchange_parallel",
            "policy_ok": not isinstance(policy_r, Exception),
            "inventory_ok": not isinstance(inventory_r, Exception),
            "logistics_ok": not isinstance(logistics_r, Exception),
        }],
    }
```

### Task 6.3: Update node_reason to use Supervisor routing

**Files:**
- Modify: `app/agent_graph/nodes.py` (modify `node_reason`)

- [ ] **Step 1: Replace node_reason with Supervisor-based version**

In `app/agent_graph/nodes.py`, replace the existing `node_reason` function:

```python
def node_reason(state: TicketAgentState, *, settings: Settings | None = None) -> dict[str, Any]:
    """Supervisor reasoning: classify intent using domain_router + detect emotion for complaints."""
    _ = settings
    from app.supervisor.router import route_intent
    return route_intent(state)
```

### Task 6.4: Update graph.py with new routing

**Files:**
- Modify: `app/agent_graph/graph.py`

- [ ] **Step 1: Add new nodes and routing edges**

In `app/agent_graph/graph.py`, after the existing graph setup:

```python
# Add Supervisor routing and exchange parallel node
from app.agent_graph.nodes import node_exchange_parallel
from app.supervisor.router import route_after_supervisor

workflow.add_node("exchange_parallel", node_exchange_parallel)

# Replace the reason→tools pattern with Supervisor routing
workflow.add_conditional_edges(
    "reason",
    route_after_supervisor,
    {
        "exchange_parallel": "exchange_parallel",
        "retrieve": "retrieve",
        "complaint_urgent": "draft",
        "complaint_standard": "draft",
        "tracking_lookup": "draft",
    }
)

# After exchange_parallel, go to draft
workflow.add_edge("exchange_parallel", "draft")
```

- [ ] **Step 4: Test full exchange flow**

```bash
curl -X POST http://localhost:8000/agent/ticket \
  -H "Content-Type: application/json" \
  -d '{"query": "买了件M码T恤太小了想换L码", "user_id": "u001"}'
```
Expected: response containing policy/inventory/logistics results.

- [ ] **Step 5: Commit**

```bash
git add app/agent_graph/nodes.py app/agent_graph/graph.py app/supervisor/
git commit -m "feat: add Supervisor routing + asyncio.gather parallel exchange Worker"
```

---

## Chunk 7: Frontend Updates

### Task 7.1: Add order panel and ticket timeline

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add API endpoints for frontend**

In `frontend/src/api.ts`, add:

```typescript
export async function lookupOrders(userId: string, keyword: string = "") {
  const res = await fetch(`/api/orders/lookup?user_id=${userId}&keyword=${keyword}`);
  return res.json();
}

export async function getTickets(userId: string) {
  const res = await fetch(`/api/tickets?user_id=${userId}`);
  return res.json();
}
```

- [ ] **Step 2: Update App.tsx with order panel sidebar**

Add a collapsible order sidebar showing order history and active tickets.

- [ ] **Step 3: Build and test frontend**

```bash
cd frontend
npm install
npm run build
```
Expected: Build succeeds, static files in `static/app/`.

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: add order panel and ticket timeline to frontend"
```

---

## Chunk 8: Device Auto-Detection + Config

### Task 8.1: Add CUDA detection to config.py

**Files:**
- Modify: `app/config.py`

- [ ] **Step 1: Add device detection**

```python
# Add to Settings class in app/config.py
import torch

@property
def inference_backend(self) -> str:
    """Auto-detect: gpu if CUDA available, else api."""
    if torch.cuda.is_available():
        return "gpu"
    return "api"

@property
def embedding_device(self) -> str:
    """Embedding device: cuda if available, else cpu."""
    return "cuda" if torch.cuda.is_available() else "cpu"
```

- [ ] **Step 2: Commit**

```bash
git add app/config.py
git commit -m "feat: add automatic CUDA detection to config"
```

---

## Chunk 9: Load Testing + Performance

### Task 9.1: Write Locust test for e-commerce scenarios

**Files:**
- Create: `tests/locustfile.py`

- [ ] **Step 1: Write Locust test**

```python
from locust import HttpUser, task, between
import random

ECOMMERCE_QUERIES = [
    "买了件M码T恤太小了想换L码",
    "我要退款，质量太差了",
    "我的快递到哪了",
    "投诉客服态度不好",
    "这个能7天无理由退货吗",
    "换货需要多久",
    "退款什么时候到账",
    # ... 20+ total queries
]

class EcomAgentUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def ask_after_sales(self):
        query = random.choice(ECOMMERCE_QUERIES)
        self.client.post(
            "/agent/ticket",
            json={"query": query, "user_id": "u001"},
            headers={"Content-Type": "application/json"},
        )
```

- [ ] **Step 2: Run load test**

```bash
locust -f tests/locustfile.py --headless --users 500 --spawn-rate 50 --run-time 60s --html tests/locust_report.html
```

- [ ] **Step 3: Document results in README**

Include P50/P95/P99 latencies from the report.

- [ ] **Step 4: Commit**

```bash
git add tests/locustfile.py tests/locust_report.html
git commit -m "test: add Locust load test for e-commerce scenarios"
```

---

## Chunk 10: Documentation + Demo

### Task 10.1: Rewrite README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README**

Rewrite to reflect EcomAgent branding, e-commerce scenario, architecture diagram, API reference, and performance data including honest P95 metrics.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for EcomAgent e-commerce branding"
```

### Task 10.2: Merge to main and tag

- [ ] **Step 1: Merge feature branch**

```bash
git checkout main
git merge feature/ecom-agent --no-ff
git tag v2.0-ecom
```

---

## Execution Notes

- **GPU/API mode**: This plan assumes the system can run in API-only mode (Zhipu GLM-4-Flash). If Qwen3-Embedding/Reranker models are unavailable locally, set `EMBEDDING_BACKEND=api` in config.
- **Docker services**: Qdrant + PostgreSQL must be running via `docker compose up -d` before testing.
- **Knowledge base**: The JD policy scraping is a semi-manual step — policy text must be manually verified for accuracy.
- **Frontend**: The React frontend is secondary to backend changes. The minimal update adds an order panel; further polish can be done after Phase 1.
