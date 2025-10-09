@echo off
echo Building Bullseye Injector...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Build executable
echo.
echo Building executable...
python build_simple.py

echo.
echo Build complete! Check the dist/ folder for BullseyeInjector.exe
pause
