# install-windows.ps1 - Install OmniDisplay Desktop App and Auto-Start on Windows

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$DesktopFolder = [System.Environment]::GetFolderPath('Desktop')
$StartupVbs = Join-Path $StartupFolder "OmniDisplay.vbs"
$DesktopVbs = Join-Path $DesktopFolder "OmniDisplay.vbs"

Write-Host "=== Installing OmniDisplay Desktop App on Windows ===" -ForegroundColor Cyan
Write-Host "Repository: $RepoDir"

# Find pythonw.exe or python.exe (pythonw runs without popping up a black console window)
$Pythonw = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $Pythonw) {
    $Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $Python) {
        Write-Error "Python 3 was not found in PATH. Please install Python 3 on Windows."
    }
    $Pythonw = $Python
}

Write-Host "Using Python: $Pythonw"

# 1. Launcher script for Auto-Start in background
$StartupContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$RepoDir"
WshShell.Run """$Pythonw"" -m omnidisplay.cli start --role pc", 0, False
"@
Set-Content -Path $StartupVbs -Value $StartupContent -Encoding ASCII
Write-Host "✓ Auto-start registered in Windows Startup folder: $StartupVbs" -ForegroundColor Green

# 2. Desktop Shortcut that opens the Desktop Software GUI
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut((Join-Path $DesktopFolder "OmniDisplay.lnk"))
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "-m omnidisplay.gui.launcher"
$Shortcut.WorkingDirectory = $RepoDir
$Shortcut.Description = "OmniDisplay Multi-PC Dual Monitor Controller"
$Shortcut.Save()
Write-Host "✓ Desktop shortcut created: OmniDisplay.lnk" -ForegroundColor Green

# 3. Start background daemon now
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$StartupVbs`"" -WorkingDirectory $RepoDir

Write-Host "`n✓ OmniDisplay is installed and active!" -ForegroundColor Green
Write-Host "You can open the Desktop Software GUI anytime from the Desktop icon or by running:" -ForegroundColor Cyan
Write-Host "python -m omnidisplay.gui.launcher" -ForegroundColor Yellow
