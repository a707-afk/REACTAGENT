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
    # color is embedded in SKU (e.g. TEE-WHITE), so we pass it through for downstream routing
    sku_data = INVENTORY.get(sku.upper(), {})
    size_data = sku_data.get(size, {})

    total = sum(size_data.values())
    warehouses = {k: v for k, v in size_data.items() if v > 0}

    if total == 0:
        return {
            "available": False,
            "stock": 0,
            "warehouse": None,
            "warehouses": {},
            "message": f"{size}码已售罄，建议查看其他尺码或颜色",
        }

    primary_warehouse = max(warehouses, key=warehouses.get) if warehouses else "上海仓"
    return {
        "available": True,
        "stock": total,
        "warehouse": primary_warehouse,
        "warehouses": warehouses,
        "requested_color": color,
        "estimated_delivery": "1-2天" if primary_warehouse == "上海仓" else "3-5天",
    }
