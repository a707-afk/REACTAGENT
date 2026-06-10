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
    purchase_date: str  # ISO date
    status: str  # "unopened" / "opened_damaged" / "used"
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
        results.append(
            {
                "order_id": order.order_id,
                "product": f"{order.product_name} {order.size}码 {order.color}",
                "sku": order.product_sku,
                "size": order.size,
                "color": order.color,
                "amount": order.amount,
                "purchase_date": order.purchase_date,
                "status": order.status,
                "carrier": order.carrier,
            }
        )
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
