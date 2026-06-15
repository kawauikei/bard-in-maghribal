@echo off
setlocal
set "PID_FILE=%~dp0.public-server.pid"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pidFile='%PID_FILE%';" ^
  "if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No public server pid file.'; exit }" ^
  "$serverPid = [int](Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue);" ^
  "if ($serverPid -and (Get-Process -Id $serverPid -ErrorAction SilentlyContinue)) { Stop-Process -Id $serverPid -Force; Write-Host ('Stopped public server process ' + $serverPid + '.') } else { Write-Host 'Public server process was not running.' }" ^
  "Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue"

endlocal
