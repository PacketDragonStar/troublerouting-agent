# ============================================================
# disable_hyperv.ps1 - Switch to Network Simulator Mode
# ============================================================
# Use this when: HCL / eNSP / EVE-NG (VirtualBox-based)
# Do NOT use when: Docker Desktop / WSL2
# Requires reboot to take effect
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Switch to: Network Simulator Mode" -ForegroundColor Cyan
Write-Host "  Works with: HCL / eNSP / EVE-NG" -ForegroundColor Green
Write-Host "  Breaks: Docker Desktop / WSL2" -ForegroundColor Red
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Disable Hyper-V related Windows features
$features = @(
    "Microsoft-Hyper-V-All",
    "VirtualMachinePlatform",
    "HypervisorPlatform"
)

foreach ($feature in $features) {
    Write-Host "[*] Disabling Windows feature: $feature" -ForegroundColor Yellow
    dism /online /disable-feature /featurename:$feature /norestart | Out-Null
}

# 2. Configure BCD - disable Hypervisor
Write-Host "[*] Configuring boot entry: disable Hypervisor" -ForegroundColor Yellow
bcdedit /set hypervisorlaunchtype off

# 3. Result
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Done. Please reboot for changes to take effect." -ForegroundColor Green
Write-Host "  After reboot: HCL / eNSP / EVE-NG will work." -ForegroundColor Green
Write-Host "  After reboot: Docker Desktop will NOT work." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

$restart = Read-Host "Reboot now? (y/n)"
if ($restart -eq "y") {
    Restart-Computer -Force
}