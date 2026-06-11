"""Locust stress test for RAG+Agent API.

Usage:
    locust -f locustfile_ecom.py --host http://localhost:8080
"""
from locust import HttpUser, task, between, constant
import json, random, time

# Realistic e-commerce queries
QUERIES = [
    "如何申请退货？",
    "换货需要多久？",
    "退款多久到账？",
    "超过7天还能退货吗？",
    "退货需要自己付运费吗？",
    "我想退这件T恤",
    "我的快递到哪了？",
    "换货可以换不同商品吗？",
    "投诉商家虚假宣传",
    "物流超时了怎么办？",
    "部分退款怎么计算？",
    "退款时优惠券能退回吗？",
    "拒收商品后怎么退款？",
    "之前申请换货但商家发错尺码了",
    "买的东西还没发货，不想要了",
]

class EcomUser(HttpUser):
    wait_time = between(1, 3)  # Think time between requests
    
    def on_start(self):
        """Setup per-user session."""
        self.headers = {"Content-Type": "application/json"}
    
    @task(3)
    def retrieve(self):
        """RAG retrieval endpoint."""
        q = random.choice(QUERIES)
        payload = {
            "query": q,
            "top_k": 10,
            "tenant_id": "t_demo",
            "roles": ["support_agent"],
        }
        with self.client.post("/retrieve", json=payload, headers=self.headers, 
                              catch_response=True, name="/retrieve") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}, Body: {resp.text[:200]}")
    
    @task(1)
    def chat(self):
        """Chat endpoint (RAG + answer generation)."""
        q = random.choice(QUERIES)
        payload = {
            "message": q,
            "tenant_id": "t_demo",
            "session_id": f"bench-{random.randint(1,100)}",
        }
        with self.client.post("/chat", json=payload, headers=self.headers,
                              catch_response=True, name="/chat") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")
    
    @task(1)
    def health(self):
        """Health check."""
        with self.client.get("/health", headers=self.headers,
                              catch_response=True, name="/health") as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Status: {resp.status_code}")
