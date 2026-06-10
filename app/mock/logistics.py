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
