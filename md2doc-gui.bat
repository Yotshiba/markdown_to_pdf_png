@echo off
rem Launch the md2doc desktop app (optionally: md2doc-gui.bat notes.md)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m md2doc.gui.app %*
