@echo off
pushd %~dp0
pushd ..\..\..\..
call npm run assets:optimize
if errorlevel 1 (
  popd
  popd
  exit /b 1
)
popd
python update_data.py
popd
exit /b %errorlevel%
