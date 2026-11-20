@echo off
REM ===================================================================
REM  Anda Tayo - start the site (double-click). Run setup.bat once first.
REM  Remember: start MySQL in the XAMPP Control Panel before this.
REM ===================================================================
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo The venv is missing. Run setup.bat first.
    pause
    exit /b 1
)
call "venv\Scripts\activate.bat"
cd AndaTayo
REM apply any new migrations your partner pushed, then start the server
python manage.py migrate
echo.
echo Anda Tayo is running at http://127.0.0.1:8000/   (press Ctrl+C to stop)
echo.
python manage.py runserver
pause
