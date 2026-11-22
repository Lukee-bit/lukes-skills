@echo off
rem Installs every Luke's skills tool on the harnesses found on this machine. Pass other arguments to change that, for example: Install.cmd ask --harness cursor
cd /d "%~dp0"
set ARGS=%*
if "%ARGS%"=="" set ARGS=all
where python >nul 2>nul && (python install.py %ARGS% & goto done)
where py >nul 2>nul && (py -3 install.py %ARGS% & goto done)
echo Python 3.8 or newer was not found. Install it from https://www.python.org/downloads/ and run this again.
:done
pause
