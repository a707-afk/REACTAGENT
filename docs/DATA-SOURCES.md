# 法律语料来源与导入指引 DATA-SOURCES

> 目标：你自己下载 **1K~3K 篇**中文法律语料丢进来，导入成本项目能吃的"四分库带 front matter Markdown"。
> 我只给来源 + 导入脚本，**不替你下载**（省你 token，也避免我编造法条）。

---

## 1. 为什么选法律领域

法律语料天然分多个子库，正好讲"分库召回"的工程故事（对应就业文档里电力案例的 运行规程/检修规程/设备说明书 分库）：

| 分库 (`domain`) | 含义 | 典型内容 | 检索特点 |
|---|---|---|---|
| `statute` | 法律法规 | 民法典、刑法、劳动法、公司法… | 结构强（编/章/节/条），精确法条号查询多 → BM25 词法路价值大 |
| `interpretation` | 司法解释 | 最高法/最高检关于 XX 的解释 | 依附于某部法律，跨域歧义高（容易和原法条混） |
| `case` | 裁判文书/案例 | 判决书、指导性案例、相似案例 | 长文本、口语化检索多（"类似 XX 的案例"） |
| `faq` | 法律问答 | 普法问答、咨询对 | 最口语化 → Query Rewrite 价值大 |

这套划分让"分库路由""混合检索""Query 改写""检索意图加权"每个功能都有**能讲出带数字故事**的落点。

---

## 2. 免费数据来源（按推荐度）

### 2.1 首选：GitHub 中文法律 Markdown 合集仓
- **为什么首选**：每部法律一个 `.md`，已是规范 Markdown（标题层级 = 编/章/节/条），最干净，直接喂 `chunk_strategy=markdown_heading_overlap` 能吃满 D-04 标题切分的好处。
- **找法**：GitHub 搜索关键词 `中华人民共和国 法律 markdown`、`chinese-law markdown`、`法律法规 数据库 md`。常见仓里有"民法典/刑法/劳动法…"逐部 `.md`。
- **落地**：把这些 `.md` 放到 `data/raw_legal/statute/` 下（按分库分文件夹，见 §4）。

### 2.2 最权威：国家法律法规数据库 `flk.npc.gov.cn`
- **内容**：现行有效的法律、行政法规、地方性法规、司法解释，官方原文，最权威。
- **取数**：网页可逐部查看/下载（含 Word/PDF）。法律放 `statute/`，司法解释放 `interpretation/`。
- **注意**：PDF/Word 需先转成 `.md` 或 `.txt`（保留标题层级最好）。脚本支持 `.txt`，但 `.md` 带标题效果最好。

### 2.3 案例/问答：CAIL 中国法研杯数据集
- **内容**：裁判文书、相似案例匹配、法律问答对，**已标注**，适合做 `case`/`faq` 分库，也是评测题（`data/eval_questions.jsonl`）的好来源。
- **找法**：搜索 `CAIL 数据集 github`（中国法律智能技术评测，历年公开 train/test JSON）。
- **格式**：通常是 JSON/JSONL，每条一个案例或问答对。用本脚本 `--format cail` 导入（字段映射见 §5）。

> 合规提示：仅用于个人学习/项目演示。裁判文书注意脱敏（CAIL 多数已脱敏）；不要把语料再公开分发。

---

## 3. 目标规模与配比建议

- 总量 **1K~3K 篇**（chunk 后约 1万~5万 节点，足够暴露"生产级数据量才有的问题"）。
- 建议配比：`statute` 40% · `interpretation` 20% · `case` 30% · `faq` 10%。
- 评测集：从中抽 **200~300 条**标注问题（用 `data/eval_questions.template.jsonl` 的 schema），覆盖 5 类坏例（见 `docs/REAL-DATA-BASELINE.md`）。

---

## 4. 你要做的事（3 步）

```text
1) 建原始目录，按分库放文件：
   data/raw_legal/
     ├── statute/          ← 法律法规 .md/.txt
     ├── interpretation/   ← 司法解释 .md/.txt
     ├── case/             ← 裁判文书 .md/.txt/.json
     └── faq/              ← 法律问答 .md/.txt/.json

2) 跑导入脚本（把原始文件转成带 front matter 的分库 .md，落到 data/docs/legal/<分库>/）：
   python scripts/ingest_legal_corpus.py --src data/raw_legal --out data/docs/legal

3) 重建索引（向量 + BM25 语料）：
   python scripts/reindex.py
```

> 子目录名（statute/interpretation/case/faq）即分库；若文件没分目录，可用 `--subindex statute` 全部指定为某一库，或用 `--format cail` 时由脚本按记录类型推断。

---

## 5. 导入脚本说明（`scripts/ingest_legal_corpus.py`）

把 `.md / .txt / .json / .jsonl` 统一转成项目要吃的格式：每篇一个 `.md`，顶部带 front matter：

```markdown
---
domain: statute
subdomain: minfadian
source_type: statute
title: 中华人民共和国民法典 婚姻家庭编
security_level: public
tenant_id: corp-default
audience: legal,public
status: active
version: v1.0
source_origin: data/raw_legal/statute/minfadian-hunyin.md
---

# 中华人民共和国民法典 婚姻家庭编
...（正文，保留原标题层级）...
```

- `domain` = 分库（statute/interpretation/case/faq），用于分库路由与 `expected_domain` 评测。
- `subdomain` = 从文件名/法律名推断的细分（如 `minfadian`、`laodongfa`）。
- 输出文件名 slug 化（中文转拼音不强制，默认保留可读 ASCII + 原名 hash 防重名）。
- JSON/JSONL：每条记录 → 一篇文档，字段映射可用 `--text-field`/`--title-field` 覆盖，CAIL 用 `--format cail` 有默认映射。

完整参数见脚本 `--help`。

---

## 6. 导入后自检

```bash
# 看四分库各导了多少篇
python scripts/ingest_legal_corpus.py --src data/raw_legal --out data/docs/legal --dry-run

# 索引后看节点数与分库分布（reindex 会打印总节点数）
python scripts/reindex.py
```

导入完成后，下一步去 `docs/REAL-DATA-BASELINE.md`：跑基线 + 坏例归因。
