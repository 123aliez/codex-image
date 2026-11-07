@echo off
setlocal
rem Use a Python runtime with the standard-library TOML parser.
py -3 -c "import tomllib" >nul 2>nul
if errorlevel 1 goto try_python
py -3 "%~dp0run.py" %*
exit /b %errorlevel%

:try_python
python -c "import tomllib" >nul 2>nul
if errorlevel 1 goto try_python3
python "%~dp0run.py" %*
exit /b %errorlevel%

:try_python3
python3 -c "import tomllib" >nul 2>nul
if errorlevel 1 goto missing_python
python3 "%~dp0run.py" %*
exit /b %errorlevel%

:missing_python
echo Python 3.11+ with tomllib is required. Install Python and enable its launcher or PATH entry. >&2
exit /b 1
