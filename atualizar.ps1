# Atualiza o VIRAL para a versão mais nova do GitHub e cria atalhos na área de trabalho.
# Mantém seu .venv, .env e os vídeos já baixados.
$ErrorActionPreference = "Stop"

$dir = $PSScriptRoot
if (-not $dir -or -not (Test-Path (Join-Path $dir "iniciar.bat"))) {
    $dir = Get-ChildItem "$HOME\Downloads\viral" -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "iniciar.bat") } |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $dir) { Write-Host "Pasta do VIRAL nao encontrada em Downloads\viral." -ForegroundColor Red; exit 1 }

$zip = Join-Path $env:TEMP "viral-update.zip"
$tmp = Join-Path $env:TEMP "viral-update"
Write-Host "Baixando versao nova..."
Invoke-WebRequest "https://github.com/SpeedBoyMotoboy/VIRAL/archive/refs/heads/claude/keen-rubin-si5do5.zip" -OutFile $zip
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip -DestinationPath $tmp
$src = Get-ChildItem $tmp -Directory | Select-Object -First 1
robocopy $src.FullName $dir /E /XD .venv downloads /XF .env | Out-Null

$ws = New-Object -ComObject WScript.Shell
$desk = [Environment]::GetFolderPath("Desktop")
foreach ($item in @(@("VIRAL", "iniciar.bat", 13), @("Atualizar VIRAL", "atualizar.bat", 238))) {
    $lnk = $ws.CreateShortcut((Join-Path $desk ($item[0] + ".lnk")))
    $lnk.TargetPath = Join-Path $dir $item[1]
    $lnk.WorkingDirectory = $dir
    $lnk.IconLocation = "shell32.dll," + $item[2]
    $lnk.Save()
}
Write-Host "Pronto! Use o atalho VIRAL na area de trabalho." -ForegroundColor Green
