@echo off
REM Thin wrapper -- see scripts\cloud_dev.py for the actual logic and full
REM usage docs. Requires python on PATH.
python "%~dp0cloud_dev.py" %*
