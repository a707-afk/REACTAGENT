"""把原始法律语料（.md/.txt/.json/.jsonl）统一导入为项目可索引的"四分库带 front matter Markdown"。

四分库 (domain)：statute 法律法规 / interpretation 司法解释 / case 裁判文书 / faq 法律问答。

用法（在 rag-kb-project 根目录执行）：

    # 1) 按分库放原始文件到 data/raw_legal/{statute,interpretation,case,faq}/
    # 2) 导入（转成带 front matter 的 .md 落到 data/docs/legal/<分库>/）
    python scripts/ingest_legal_corpus.py --src data/raw_legal --out data/docs/legal

    # 只看会导多少、不写文件
    python scripts/ingest_legal_corpus.py --src data/raw_legal --out data/docs/legal --dry-run

    # 全部强制归为某个分库（原始文件没分目录时）
    python scripts/ingest_legal_corpus.py --src data/raw_legal/all --out data/docs/legal --subindex statute

    # CAIL 风格 JSON/JSONL（裁判文书/问答），用内置字段映射
    python scripts/ingest_legal_corpus.py --src data/raw_legal/cail --out data/docs/legal --format cail --subindex case

随后执行 python scripts/reindex.py 重建向量 + BM25 索引。
依赖：仅标准库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

SUBINDEXES = ("statute", "interpretation", "case", "faq")
TEXT_SUFFIXES = (".md", ".txt", ".markdown")
JSON_SUFFIXES = (".json", ".jsonl")

# JSON 记录里常见的正文 / 标题字段候选（按优先级），CAIL 与通用都覆盖
_DEFAULT_TEXT_FIELDS = ("text", "content", "body", "fact", "casename_text", "answer", "reply")
_DEFAULT_TITLE_FIELDS = ("title", "casename", "name", "question", "caseid", "id")
# CAIL 常见：fact（案情）、meta、casename；问答：question/answer
_CAIL_TEXT_FIELDS = ("fact", "text", "content", "answer", "reply")
_CAIL_TITLE_FIELDS = ("casename", "title", "question", "caseid", "id")


@dataclass
class IngestStats:
    written: dict[str, int] = field(default_factory=lambda: {k: 0 for k in SUBINDEXES})
    skipped_short: int = 0
    skipped_empty: int = 0
    errors: int = 0

    def total(self) -> int:
        return sum(self.written.values())


def _slugify(value: str, max_len: int = 60) -> str:
    """中文/标点 → 安全文件名片段：保留 ASCII 字母数字与连字符，其余压成连字符。"""
    value = (value or "").strip()
    # 保留中文（文件系统支持），把空白与多数标点换成连字符
    value = re.sub(r"[\s/\\:*?\"<>|,，。；;]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    if not value:
        value = "doc"
    if len(value) > max_len:
        value = value[:max_len].rstrip("-")
    return value


def _short_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:8]


def _strip_existing_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """若文件已带 --- front matter，解析为 dict 并返回正文（避免二次包裹）。"""
    text = raw.lstrip("\ufeff")
    if not text.startswith("---"):
        return {}, raw
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, raw
    meta: dict[str, str] = {}
    for line in lines[1:end]:
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        k, v = s.split(":", 1)
        k = k.strip()
        v = v.strip().strip("'\"")
        if k:
            meta[k] = v
    body = "\n".join(lines[end + 1:]).lstrip()
    return meta, body


def _fm_value(value: str) -> str:
    """front matter 值：含冒号/特殊字符时加引号，否则原样。"""
    v = str(value).replace("\n", " ").strip()
    if v == "" or re.search(r"[:#\"']", v):
        return '"' + v.replace('"', "'") + '"'
    return v


def _render_frontmatter(meta: dict[str, str]) -> str:
    order = [
        "domain", "subdomain", "source_type", "title", "security_level",
        "tenant_id", "audience", "status", "version", "source_origin",
    ]
    keys = order + [k for k in meta if k not in order]
    lines = ["---"]
    for k in keys:
        if k in meta and str(meta.get(k, "")).strip() != "":
            lines.append(f"{k}: {_fm_value(meta[k])}")
    lines.append("---")
    return "\n".join(lines)


def _infer_subindex_from_path(path: Path, src_root: Path, override: str | None) -> str:
    if override:
        return override
    try:
        rel_parts = path.resolve().relative_to(src_root.resolve()).parts
    except ValueError:
        rel_parts = path.parts
    for part in rel_parts:
        if part.lower() in SUBINDEXES:
            return part.lower()
    return "statute"  # 默认；建议用子目录或 --subindex 明确


def _infer_subdomain(title: str, filename: str) -> str:
    base = (title or filename or "").lower()
    table = {
        "民法典": "minfadian", "刑法": "xingfa", "劳动": "laodong",
        "公司法": "gongsifa", "婚姻": "hunyin", "合同": "hetong",
        "继承": "jicheng", "诉讼": "susong", "行政": "xingzheng",
        "消费者": "xiaofeizhe", "知识产权": "zhishichanquan",
    }
    for zh, py in table.items():
        if zh in base:
            return py
    return _slugify(Path(filename).stem, max_len=30) or "general"


def _build_doc_md(*, title: str, body: str, subindex: str, origin: str,
                  extra_meta: dict[str, str]) -> str:
    meta = {
        "domain": subindex,
        "subdomain": _infer_subdomain(title, origin),
        "source_type": subindex,
        "title": title or Path(origin).stem,
        "security_level": "public",
        "tenant_id": "corp-default",
        "audience": "legal,public",
        "status": "active",
        "version": "v1.0",
        "source_origin": origin,
    }
    # 已有 front matter 的字段优先保留（但 domain 用我们推断的分库，保证分库一致）
    for k, v in (extra_meta or {}).items():
        if k not in ("domain", "source_origin") and str(v).strip():
            meta[k] = v
    fm = _render_frontmatter(meta)
    title_line = f"# {meta['title']}\n\n" if not body.lstrip().startswith("#") else ""
    return f"{fm}\n\n{title_line}{body.strip()}\n"


def _write_doc(out_root: Path, subindex: str, title: str, content_md: str,
               dedup_key: str, *, dry_run: bool, stats: IngestStats) -> None:
    slug = _slugify(title or "doc", max_len=50)
    fname = f"{slug}-{_short_hash(dedup_key)}.md"
    target_dir = out_root / subindex
    target = target_dir / fname
    if dry_run:
        stats.written[subindex] += 1
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(content_md, encoding="utf-8")
    stats.written[subindex] += 1


def _ingest_text_file(path: Path, src_root: Path, out_root: Path, args,
                      stats: IngestStats) -> None:
    raw = path.read_text(encoding="utf-8", errors="ignore").lstrip("\ufeff")
    existing_meta, body = _strip_existing_frontmatter(raw)
    if len(body.strip()) < args.min_chars:
        stats.skipped_short += 1
        return
    subindex = _infer_subindex_from_path(path, src_root, args.subindex)
    title = existing_meta.get("title") or _first_heading(body) or path.stem
    origin = _rel_origin(path)
    content_md = _build_doc_md(
        title=title, body=body, subindex=subindex, origin=origin,
        extra_meta=existing_meta,
    )
    _write_doc(out_root, subindex, title, content_md, dedup_key=body[:2000],
               dry_run=args.dry_run, stats=stats)


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s.lstrip("#").strip()
        if s:
            return s[:60]
    return ""


def _rel_origin(path: Path) -> str:
    """相对项目根的 POSIX 风格来源路径；不在根下则用绝对路径。"""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _pick_field(record: dict, candidates: tuple[str, ...], override: str | None) -> str:
    if override and override in record and str(record[override]).strip():
        return str(record[override])
    for c in candidates:
        if c in record and str(record[c]).strip():
            return str(record[c])
    return ""


def _iter_json_records(path: Path):
    if path.suffix.lower() == ".jsonl":
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return
    if isinstance(data, list):
        yield from (r for r in data if isinstance(r, dict))
    elif isinstance(data, dict):
        # 形如 {"data": [...]} 或单条
        if isinstance(data.get("data"), list):
            yield from (r for r in data["data"] if isinstance(r, dict))
        else:
            yield data


def _ingest_json_file(path: Path, src_root: Path, out_root: Path, args,
                      stats: IngestStats) -> None:
    is_cail = args.format == "cail"
    text_fields = _CAIL_TEXT_FIELDS if is_cail else _DEFAULT_TEXT_FIELDS
    title_fields = _CAIL_TITLE_FIELDS if is_cail else _DEFAULT_TITLE_FIELDS
    base_subindex = _infer_subindex_from_path(path, src_root, args.subindex)
    for record in _iter_json_records(path):
        text = _pick_field(record, text_fields, args.text_field)
        if not text or len(text.strip()) < args.min_chars:
            stats.skipped_short += 1
            continue
        title = _pick_field(record, title_fields, args.title_field) or "案例"
        subindex = base_subindex
        if args.subindex_field and record.get(args.subindex_field):
            cand = str(record[args.subindex_field]).lower()
            if cand in SUBINDEXES:
                subindex = cand
        origin = _rel_origin(path)
        body = text if text.lstrip().startswith("#") else text
        content_md = _build_doc_md(
            title=title, body=body, subindex=subindex, origin=f"{origin}#{title[:20]}",
            extra_meta={},
        )
        _write_doc(out_root, subindex, title, content_md,
                   dedup_key=text[:2000], dry_run=args.dry_run, stats=stats)


def ingest(args) -> IngestStats:
    src_root = Path(args.src)
    out_root = Path(args.out)
    if not src_root.exists():
        raise SystemExit(f"--src 不存在: {src_root}（请先建目录并放入原始语料，见 docs/DATA-SOURCES.md）")
    stats = IngestStats()
    files = [p for p in sorted(src_root.rglob("*")) if p.is_file()]
    count = 0
    for path in files:
        if args.max and count >= args.max:
            break
        suffix = path.suffix.lower()
        try:
            if suffix in TEXT_SUFFIXES and args.format in ("auto", "md", "txt"):
                _ingest_text_file(path, src_root, out_root, args, stats)
                count += 1
            elif suffix in JSON_SUFFIXES and args.format in ("auto", "cail", "json"):
                before = stats.total()
                _ingest_json_file(path, src_root, out_root, args, stats)
                count += stats.total() - before
            else:
                continue
        except Exception as exc:  # 单文件失败不应中断整批
            stats.errors += 1
            print(f"[WARN] 处理失败 {path}: {exc}", file=sys.stderr)
    return stats


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", required=True, help="原始语料根目录（建议按 statute/interpretation/case/faq 分子目录）")
    p.add_argument("--out", default="data/docs/legal", help="输出目录（默认 data/docs/legal，doc_group=legal）")
    p.add_argument("--subindex", choices=SUBINDEXES, default=None,
                   help="强制全部归为某分库；不指定则按子目录名推断")
    p.add_argument("--format", choices=("auto", "md", "txt", "json", "cail"), default="auto",
                   help="auto 按扩展名；cail 用 CAIL 字段映射")
    p.add_argument("--text-field", default=None, help="JSON 正文字段名（覆盖默认推断）")
    p.add_argument("--title-field", default=None, help="JSON 标题字段名（覆盖默认推断）")
    p.add_argument("--subindex-field", default=None, help="JSON 中标识分库的字段名（值须是四分库之一）")
    p.add_argument("--min-chars", type=int, default=80, help="正文最小字符数，过短跳过（默认 80）")
    p.add_argument("--max", type=int, default=0, help="最多导入文件/记录数，0=不限")
    p.add_argument("--dry-run", action="store_true", help="只统计不写文件")
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    stats = ingest(args)
    print("=" * 48)
    print(f"导入{'（DRY-RUN 未写文件）' if args.dry_run else ''}完成 → {args.out}")
    for sub in SUBINDEXES:
        print(f"  {sub:<14} {stats.written[sub]:>6} 篇")
    print(f"  {'合计':<12} {stats.total():>6} 篇")
    print(f"  跳过(过短)     {stats.skipped_short:>6}")
    print(f"  错误           {stats.errors:>6}")
    print("=" * 48)
    if not args.dry_run and stats.total() > 0:
        print("下一步：python scripts/reindex.py 重建索引；再去 docs/REAL-DATA-BASELINE.md 跑基线。")


if __name__ == "__main__":
    main()
