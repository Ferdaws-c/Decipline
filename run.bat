@echo off
title Decipline Launcher
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Decipline" >nul 2>&1
taskkill /F /IM Decipline.exe >nul 2>&1
python write_window.py
start "" pythonw main.py
exit
