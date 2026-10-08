@echo off
rem Build the portable Windows app:  dist\md2doc\md2doc-gui.exe  (desktop)  and  dist\md2doc\md2doc.exe  (command line)
rem Usage:  build_exe.bat          build the folder
rem         build_exe.bat zip      build, then also create dist\md2doc-windows.zip
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Run install.bat first.
    exit /b 1
)
set PY=.venv\Scripts\python.exe
%PY% -m pip install -q "pyinstaller>=6.10" || goto :fail
%PY% -m md2doc setup --java || goto :fail
%PY% -c "from md2doc import puml_js; puml_js.ensure_classic()" || goto :fail
%PY% packaging\make_icon.py || goto :fail
%PY% -m PyInstaller packaging\md2doc.spec --noconfirm --distpath dist --workpath build\pyinstaller || goto :fail
echo.
echo Built: dist\md2doc\md2doc-gui.exe  and  dist\md2doc\md2doc.exe
if /i "%~1"=="zip" (
    powershell -NoProfile -Command "Compress-Archive -Path 'dist\md2doc' -DestinationPath 'dist\md2doc-windows.zip' -Force" || goto :fail
    echo Zipped: dist\md2doc-windows.zip
)
exit /b 0
:fail
echo.
echo Build failed - see the messages above.
exit /b 1
