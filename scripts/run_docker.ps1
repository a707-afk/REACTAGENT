# Docker 一键启动（PowerShell）
# 用法：.\scripts\run_docker.ps1
# 需已安装 Docker Desktop

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "构建并启动 api + qdrant …" -ForegroundColor Cyan
docker compose up -d --build

Write-Host ""
Write-Host "API:     http://127.0.0.1:8000/health" -ForegroundColor Green
Write-Host "前端 UI: http://127.0.0.1:8000/app/" -ForegroundColor Green
Write-Host "Qdrant:  http://127.0.0.1:6333/" -ForegroundColor Green
Write-Host ""
Write-Host "查看日志: docker compose logs -f api" -ForegroundColor Yellow
Write-Host "停止:     docker compose down" -ForegroundColor Yellow
