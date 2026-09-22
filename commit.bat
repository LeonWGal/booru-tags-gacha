@echo off
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "%~dp0." add -A
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "%~dp0." commit -m "fix(autogacha): optimize generation speed, resolve batch duplicates, fix placeholder precedence, and support full BTG tab settings"
"t:\StabilityMatrix\PortableGit\cmd\git.exe" -C "%~dp0." push origin main
pause
