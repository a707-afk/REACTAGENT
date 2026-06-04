# 在 Conda 环境 rags 中安装支持 RTX 50 系（sm_120）的 PyTorch CUDA 12.8 wheel。
# 用法（PowerShell）:
#   cd rag-kb-project
#   .\scripts\setup_pytorch_cuda.ps1
# 可选: -Python "D:\conda\envs\rags\python.exe"  -UseNightly

param(
    [string]$Python = "D:\conda\envs\rags\python.exe",
    [switch]$UseNightly
)

$ErrorActionPreference = "Stop"
# 无效系统代理会导致 pip 无法访问 PyTorch 索引
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""
$env:ALL_PROXY = ""
if (-not (Test-Path $Python)) {
    Write-Error "未找到 Python: $Python。请用 -Python 指定 conda 环境解释器。"
}

Write-Host "=== 当前 torch ===" -ForegroundColor Cyan
& $Python -c "import torch; print('version', torch.__version__); print('cuda', torch.cuda.is_available()); print('built', getattr(torch.version,'cuda',None))"

Write-Host "`n=== 卸载 CPU 版 torch / torchvision / torchaudio ===" -ForegroundColor Cyan
& $Python -m pip uninstall -y torch torchvision torchaudio
if ($LASTEXITCODE -gt 1) { exit $LASTEXITCODE }

if ($UseNightly) {
    $Index = "https://download.pytorch.org/whl/nightly/cu128"
    $Extra = @("--pre")
    Write-Host "安装 nightly cu128 ..." -ForegroundColor Cyan
} else {
    $Index = "https://download.pytorch.org/whl/cu128"
    $Extra = @()
    Write-Host "安装 stable cu128 ..." -ForegroundColor Cyan
}

& $Python -m pip install @Extra torch torchvision torchaudio --index-url $Index --no-cache-dir

Write-Host "`n=== 验证 GPU ===" -ForegroundColor Cyan
& $Python -c @"
import torch
print('torch', torch.__version__)
print('built_cuda', torch.version.cuda)
print('cuda_available', torch.cuda.is_available())
if torch.cuda.is_available():
    print('device', torch.cuda.get_device_name(0))
    print('capability', torch.cuda.get_device_capability(0))
    x = torch.zeros(1, device='cuda')
    print('tensor_ok', x.device)
else:
    raise SystemExit('CUDA 仍不可用，可重试: .\\scripts\\setup_pytorch_cuda.ps1 -UseNightly')
"@

Write-Host "`n完成。运行 API/评测时请设 INFERENCE_DEVICE=auto（默认）。" -ForegroundColor Green
