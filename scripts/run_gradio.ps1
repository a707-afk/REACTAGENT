# 使用 Conda 环境 rags 启动 Gradio（默认调 http://127.0.0.1:8000 上已运行的 API）

$Python = "D:\conda\envs\rags\python.exe"

$Root = Split-Path -Parent $PSScriptRoot

Set-Location $Root

$env:RAG_API_BASE = if ($env:RAG_API_BASE) { $env:RAG_API_BASE } else { "http://127.0.0.1:8000" }

& $Python scripts/gradio_app.py

