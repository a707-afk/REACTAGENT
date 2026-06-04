# OPA 外部策略集成

> 可选能力：在本地规则引擎 **之后** 调用 Open Policy Agent（OPA）。默认 **关闭**；出错时默认 **fail-open**（不拦截）。

---

## 启用

```powershell
$env:OPA_ENABLED="true"
$env:OPA_URL="http://localhost:8181"
$env:OPA_POLICY_PATH="rag/allow"
$env:OPA_FAIL_OPEN="true"
```

启动 OPA 并加载策略：

```powershell
opa run --server data/opa/rag_allow.rego
```

---

## 决策流

1. 本地规则层（`app/policy/engine.py`）选出 winner。
2. 若 `OPA_ENABLED=true` 且规则未 intercept，POST `{OPA_URL}/v1/data/{OPA_POLICY_PATH}`，body `{"input": {...}}`。
3. `result.allow == false` → intercept。
4. OPA 不可用：若 `OPA_FAIL_OPEN=true`（默认）则放行；若为 `false` 则 intercept。

---

## 示例策略

见 `data/opa/rag_allow.rego`：默认 allow；含「绕过权限」或 guest+「机密」时 deny。

---

## 客户端

`app/opa/client.py` — `query_opa_allow(settings, input_payload=...)`，httpx 超时 2s。
