# ============================================================
# enable_hyperv.ps1 - Switch to Docker Desktop Mode
# ============================================================
# Use this when: Docker Desktop / WSL2
# Do NOT use when: HCL / eNSP / EVE-NG (VirtualBox-based)
# Requires reboot to take effect
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Switch to: Docker Desktop Mode" -ForegroundColor Cyan
Write-Host "  Works with: Docker Desktop / WSL2" -ForegroundColor Green
Write-Host "  Breaks: HCL / eNSP / EVE-NG" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Enable Hyper-V related Windows features
$features = @(
    "Microsoft-Hyper-V-All",
    "VirtualMachinePlatform",
    "HypervisorPlatform"
)

foreach ($feature in $features) {
    Write-Host "[*] Enabling Windows feature: $feature" -ForegroundColor Yellow
    dism /online /enable-feature /featurename:$feature /norestart | Out-Null
}

# 2. Configure BCD - enable Hypervisor
Write-Host "[*] Configuring boot entry: enable Hypervisor" -ForegroundColor Yellow
bcdedit /set hypervisorlaunchtype auto

# 3. Result
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Done. Please reboot for changes to take effect." -ForegroundColor Green
Write-Host "  After reboot: Docker Desktop will work." -ForegroundColor Green
Write-Host "  After reboot: HCL / eNSP / EVE-NG will NOT work." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

$restart = Read-Host "Reboot now? (y/n)"
if ($restart -eq "y") {
    Restart-Computer -Force
}