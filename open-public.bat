@echo off
setlocal
set "PORT=8765"
set "PUBLIC_DIR=%~dp0"
set "PID_FILE=%~dp0.public-server.pid"
set "URL_PATH=%~1"
if "%URL_PATH%"=="" set "URL_PATH=/"
if not "%URL_PATH:~0,1%"=="/" set "URL_PATH=/%URL_PATH%"
set "URL=http://127.0.0.1:%PORT%%URL_PATH%"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$port=%PORT%; $public='%PUBLIC_DIR%'; $pidFile='%PID_FILE%'; $url='%URL%';" ^
  "$oldPid = if (Test-Path -LiteralPath $pidFile) { [int](Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue) } else { 0 };" ^
  "if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) { Start-Process $url; exit }" ^
  "$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $port);" ^
  "try { $listener.Start(); $listener.Stop() } catch { Write-Host ('Port ' + $port + ' is already in use. Opening URL only.'); Start-Process $url; exit }" ^
  "$p = Start-Process -WindowStyle Hidden -FilePath py -ArgumentList @('-m','http.server',[string]$port,'--bind','0.0.0.0','--directory',$public) -PassThru;" ^
  "Set-Content -LiteralPath $pidFile -Value $p.Id -Encoding ascii;" ^
  "Start-Sleep -Milliseconds 700;" ^
  "Start-Process $url"

endlocal
