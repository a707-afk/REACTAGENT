# Qdrant 迁移 + 权限评测（企业索引）
# 用法：在 rag-kb-project 根目录
#   .\scripts\run_qdrant_migrate_eval.ps1
# 可选：$env:ACCESS_EVAL_USE_RERANK="false"  # Windows CPU 崩溃时

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$py = $env:RAGS_PYTHON
if (-not $py) {
    foreach ($c in @(
        "D:\conda\envs\rags\python.exe",
        "C:\Users\Lenovo\anaconda3\envs\rags\python.exe"
    )) {
        if (Test-Path $c) { $py = $c; break }
    }
}
if (-not $py) { $py = "python" }

$env:VECTOR_BACKEND = "qdrant"
$env:QDRANT_URL = "http://localhost:6333"
$env:DOCS_DIR = "data/docs/enterprise_ai_ops"
$env:CHROMA_COLLECTION_NAME = "enterprise_ai_ops"
$env:BM25_CORPUS_PATH = "data/bm25_enterprise_corpus.jsonl"
$env:EVAL_ENTERPRISE_STRICT = "1"

Write-Host "=== Qdrant reindex (302 nodes est.) ===" -ForegroundColor Cyan
& $py scripts/reindex.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== Access control eval (Qdrant) ===" -ForegroundColor Cyan
$env:ACCESS_EVAL_OUTPUT_JSON = "docs/eval_access_control_qdrant.json"
$env:ACCESS_EVAL_OUTPUT_MD = "docs/ACCESS-CONTROL-EVAL-QDRANT.md"
& $py scripts/run_eval_access_control.py
exit $LASTEXITCODE
