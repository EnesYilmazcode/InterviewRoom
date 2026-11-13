@echo off
title Interview Room
cd /d "%~dp0"
python server.py
if errorlevel 1 pause
