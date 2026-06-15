<!-- source: AI辅助整理 | category: infrastructure/multi-tenant | language: zh-CN -->

# 多租户 RAG 架构：ACL 设计与数据隔离

## 为什么单租户 RAG 不适合企业

企业场景下，研发部和管理部的文档不能互相检索。如果缓存键里没有 tenant_id，用户 A 的敏感检索结果会被缓存并返回给用户 B——这是生产级安全漏洞。

## 三层隔离

### 第一层：Qdrant Payload Filter（数据库层）
在向量检索时直接带 filter，不事后过滤。
```
filter: { tenant_id: "team-a", clearance: { lte: user.clearance } }
```
事后过滤的隐患：fetch top_k×3 再过滤可能漏掉大量候选；而且"无意中看到了其他租户的 chunk"本身就是数据泄露。

### 第二层：BM25 语料隔离
BM25 corpus 按租户分文件（bm25_corpus_{tenant}.jsonl），检索时只查自己的文件。

### 第三层：缓存键租户化
缓存键必须包含 `tenant_id + clearance + roles` 三元组。缺失任一项 → 拒绝缓存写入。

## ACL 默认 Fail-Closed

没有 tenant_id 标记的 chunk → 拒绝所有人访问（强制入库时标注）。这和常见做法相反——通常默认"没标记就放行"（fail-open），安全上不可接受。

## 面试回答要点
"我的多租户隔离是三层：Qdrant payload filter 在数据库层做（不是事后过滤）、BM25 语料按租户分文件、缓存键包含租户标识。默认 fail-closed——没打租户标记的 chunk 谁都看不到。这确保不会出现跨租户数据泄露。"
