$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "Project root: $ProjectRoot"
Write-Host "Python: $((Get-Command python).Source)"
python -c "import sys; print('Python version:', sys.version); print('Prefix:', sys.prefix)"

python -m pip install -U pip
python -m pip install -U pyinstaller
python -m pip install -e .

if (Test-Path ".\build") {
    Remove-Item ".\build" -Recurse -Force
}
if (Test-Path ".\dist\bilibiliTool") {
    Remove-Item ".\dist\bilibiliTool" -Recurse -Force
}
if (Test-Path ".\dist\bilibiliTool-windows.zip") {
    Remove-Item ".\dist\bilibiliTool-windows.zip" -Force
}

python -m PyInstaller --clean --noconfirm ".\packaging\bilibiliTool.spec"

$ReleaseDir = Join-Path $ProjectRoot "dist\bilibiliTool"
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "downloads") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "logs") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ReleaseDir "exports") | Out-Null
Copy-Item ".\packaging\release_readme.txt" (Join-Path $ReleaseDir "README.txt") -Force

Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath ".\dist\bilibiliTool-windows.zip" -Force

Write-Host ""
Write-Host "Build finished."
Write-Host "Release directory: $ReleaseDir"
Write-Host "Zip package: $(Join-Path $ProjectRoot 'dist\bilibiliTool-windows.zip')"
