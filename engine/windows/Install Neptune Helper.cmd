@echo off
rem Neptune Helper for Windows: double-click to check and install prerequisites, then create shortcuts.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-neptune-helper.ps1" %*
if errorlevel 1 (
  echo.
  echo Setup did not finish. Nothing was submitted. Double-click this file to retry.
)
pause
