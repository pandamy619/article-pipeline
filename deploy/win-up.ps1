# Запуск стека на Windows (GPU), без make.
# Запуск:  powershell -ExecutionPolicy Bypass -File deploy\win-up.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")   # корень проекта

$compose = "docker compose -f deploy/docker-compose.yml --profile gpu"

Write-Host "Сборка и запуск стека (GPU)..." -ForegroundColor Cyan
Invoke-Expression "$compose up -d --build"

Write-Host "`nГотово. Модели качаются в фоне (это долго). Прогресс:" -ForegroundColor Green
Write-Host "  $compose logs -f ollama-pull"
Write-Host "Логи бота/планировщика:" -ForegroundColor Green
Write-Host "  $compose logs -f app"
Write-Host "Админка:  http://localhost:3000" -ForegroundColor Green
