# Optional one-time test launcher. Never closes an existing Codex process.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$picker = New-Object System.Windows.Forms.OpenFileDialog
$picker.Title = 'Select the installed Codex application (.exe)'
$picker.Filter = 'Windows applications (*.exe)|*.exe'
if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 1 }

$executable = $picker.FileName
$name = [IO.Path]::GetFileName($executable)
$running = Get-CimInstance Win32_Process -Filter "Name='$name'" | Where-Object { $_.ExecutablePath -eq $executable }
if ($running) {
    Write-Output 'RESULT: CODEX_ALREADY_RUNNING'
    Write-Output 'Exit Codex normally, then run this file again. This test will not end an open conversation.'
    exit 2
}

Start-Process -FilePath $executable -ArgumentList '--remote-debugging-address=127.0.0.1','--remote-debugging-port=9333'
Start-Sleep -Seconds 4
& "$PSScriptRoot\windows-preflight.ps1"
