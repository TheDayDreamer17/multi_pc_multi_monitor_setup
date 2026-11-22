# install-windows.ps1 - Install OmniDisplay Desktop App and Auto-Start on Windows

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$StartupFolder = [System.Environment]::GetFolderPath('Startup')
$DesktopFolder = [System.Environment]::GetFolderPath('Desktop')
$StartupVbs = Join-Path $StartupFolder "OmniDisplay.vbs"

Write-Host "=== Installing OmniDisplay Desktop App on Windows ===" -ForegroundColor Cyan
Write-Host "Repository: $RepoDir"

# Find pythonw.exe or python.exe (excluding WindowsApps shim which can fail with 'file cannot be accessed')
$Pythonw = (Get-Command pythonw.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" } | Select-Object -First 1).Source
if (-not $Pythonw) {
    $Pythonw = (Get-Command python.exe -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch "WindowsApps" } | Select-Object -First 1).Source
}
if (-not $Pythonw) {
    $candidates = @(
        "$env:LOCALAPPDATA\Python\bin\pythonw.exe",
        "$env:LOCALAPPDATA\Python\bin\python.exe",
        "$env:ProgramFiles\Python*\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python*\pythonw.exe"
    )
    foreach ($cand in $candidates) {
        $found = Resolve-Path $cand -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) { $Pythonw = $found.Path; break }
    }
}
if (-not $Pythonw) {
    Write-Error "Python 3 was not found in PATH. Please install Python 3 on Windows."
}

Write-Host "Using Python: $Pythonw"

# 1. Launcher script for Auto-Start in background (avoiding here-string terminator issues)
$line1 = 'Set WshShell = CreateObject("WScript.Shell")'
$line2 = 'WshShell.CurrentDirectory = "' + $RepoDir + '"'
$line3 = 'WshShell.Run """' + $Pythonw + '"" -m omnidisplay.cli start --role pc", 0, False'
$StartupContent = $line1 + "`r`n" + $line2 + "`r`n" + $line3 + "`r`n"

Set-Content -Path $StartupVbs -Value $StartupContent -Encoding ASCII
Write-Host "✓ Auto-start registered in Windows Startup folder: $StartupVbs" -ForegroundColor Green

# 2. Desktop Shortcut that opens the Desktop Software GUI
$LnkPath = Join-Path $DesktopFolder "OmniDisplay.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($LnkPath)
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
