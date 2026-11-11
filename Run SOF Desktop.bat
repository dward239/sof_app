@echo off
pushd "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\run_desktop.ps1"
popd