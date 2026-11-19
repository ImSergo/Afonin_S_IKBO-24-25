@echo off
setlocal
pushd "%~dp0" || exit /b 1
if defined PYTHON goto selected
where py >nul 2>nul && (set "PYTHON=py" & goto selected)
set "PYTHON=python"
:selected
if /i "%~1"=="test" goto tests
"%PYTHON%" -m src %*
goto finish
:tests
"%PYTHON%" -m unittest discover -s tests -v
:finish
set "result=%errorlevel%"
popd
exit /b %result%
