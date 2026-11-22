# uninstall-windows.ps1 - Remove OmniDisplay from Windows Startup

$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$VbsPath = Join-Path $StartupFolder "OmniDisplay.vbs"

Write-Host "=== Uninstalling OmniDisplay from Windows Startup ===" -ForegroundColor Cyan
if (Test-Path $VbsPath) {
    Remove-Item $VbsPath -Force
    Write-Host "✓ OmniDisplay startup script removed." -ForegroundColor Green
} else {
    Write-Host "OmniDisplay was not in Startup folder." -ForegroundColor Yellow
}
