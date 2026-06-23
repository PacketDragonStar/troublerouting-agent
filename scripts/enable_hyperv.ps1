# ============================================================
# enable_hyperv.ps1 — 开启 Hyper-V 模式
# ============================================================
# 适用场景：你要用 Docker Desktop、WSL2
# 不适用：HCL、eNSP、EVE-NG（VirtualBox 模拟器会异常）
# 运行后需要重启电脑才能生效
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  切换到 Hyper-V 模式" -ForegroundColor Cyan
Write-Host "  适用：Docker Desktop / WSL2" -ForegroundColor Green
Write-Host "  不适用：HCL / eNSP / EVE-NG" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 开启 Hyper-V 相关 Windows 功能
$features = @(
    "Microsoft-Hyper-V-All",
    "VirtualMachinePlatform",
    "HypervisorPlatform"
)

foreach ($feature in $features) {
    Write-Host "[*] 启用 Windows 功能: $feature" -ForegroundColor Yellow
    dism /online /enable-feature /featurename:$feature /norestart | Out-Null
}

# 2. 设置 BCD 启动项——启用 Hypervisor
Write-Host "[*] 配置启动项: 启用 Hypervisor" -ForegroundColor Yellow
bcdedit /set hypervisorlaunchtype auto

# 3. 结果
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  配置完成！请重启电脑使 Hyper-V 生效。" -ForegroundColor Green
Write-Host "  重启后 Docker Desktop 可以正常使用。" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

$restart = Read-Host "是否现在重启？(y/n)"
if ($restart -eq "y") {
    Restart-Computer -Force
}