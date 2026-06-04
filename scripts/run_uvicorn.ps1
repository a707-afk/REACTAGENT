# 使用 Conda 环境 rags 启动 API（路径可按本机修改）
$Python = "D:\conda\envs\rags\python.exe"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& $Python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
