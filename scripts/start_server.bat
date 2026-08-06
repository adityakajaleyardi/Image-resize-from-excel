@echo off
REM Double click this file to start the Image Processor web app.
REM It runs start_server.ps1 with a policy override, because unsigned scripts
REM are usually blocked on a managed Windows machine.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server.ps1" %*
pause
