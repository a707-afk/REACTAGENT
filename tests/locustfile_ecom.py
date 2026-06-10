"""Locust load test for EcomAgent e-commerce after-sales scenarios."""
from locust import HttpUser, task, between
import random

ECOMMERCE_QUERIES = [
    "买了件M码T恤太小了想换L码",
    "我要退款，质量太差了",
    "我的快递到哪了",
    "投诉你们客服态度不好",
    "七天无理由退货有什么条件",
    "换货需要多久",
    "退款什么时候到账",
    "这个能退货吗",
    "快递太慢了我要投诉",
    "帮我查一下物流",
    "拆了包装还能退吗",
    "退货需要自己付运费吗",
    "包裹丢了怎么办",
    "退款金额不对",
    "换货可以换不同颜色吗",
]


class EcomAgentUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def ask_after_sales(self):
        query = random.choice(ECOMMERCE_QUERIES)
        ticket_id = f"perf-{random.randint(1000, 9999)}"
        self.client.post(
            "/agent/ticket",
            json={"ticket_id": ticket_id, "user_query": query},
            headers={"Content-Type": "application/json"},
        )
