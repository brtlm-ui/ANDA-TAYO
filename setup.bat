@echo off
REM ===================================================================
REM  Anda Tayo - one-time setup (double-click this file)
REM  Needs: Python (added to PATH) and XAMPP with MySQL STARTED.
REM  It is safe to run again; it skips anything already done.
REM ===================================================================
setlocal
cd /d "%~dp0"
echo.
echo ===== Anda Tayo setup =====
echo.

REM --- 1. Python --------------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
    echo [X] Python was not found. Install Python and tick "Add python.exe to PATH".
    goto :fail
)

REM --- 2. XAMPP MySQL ---------------------------------------------------
set "MYSQL=C:\xampp\mysql\bin\mysql.exe"
if not exist "%MYSQL%" (
    echo [X] XAMPP MySQL not found at %MYSQL%
    echo     If XAMPP is installed somewhere else, edit the MYSQL line in setup.bat.
    goto :fail
)
"%MYSQL%" -u root -e "SELECT 1" >nul 2>nul
if errorlevel 1 (
    echo [X] MySQL is not running. Open the XAMPP Control Panel, click Start next to MySQL,
    echo     then run setup.bat again.
    goto :fail
)
echo [1/5] Creating database andatayo_db (if it does not exist yet)...
"%MYSQL%" -u root -e "CREATE DATABASE IF NOT EXISTS andatayo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
if errorlevel 1 goto :fail

REM --- 3. Virtual environment + packages ------------------------------
if not exist "venv\Scripts\python.exe" (
    echo [2/5] Creating the virtual environment ^(venv^)...
    python -m venv venv
    if errorlevel 1 goto :fail
) else (
    echo [2/5] Virtual environment already exists.
)
call "venv\Scripts\activate.bat"
echo [3/5] Installing packages (Django, mysqlclient, Pillow)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 goto :fail

REM --- 4. Database tables + demo data ----------------------------------
cd AndaTayo
echo [4/5] Creating the tables (migrate)...
python manage.py migrate
if errorlevel 1 goto :fail
echo [5/5] Loading demo spots and photos...
python manage.py seed_demo
if errorlevel 1 goto :fail
python manage.py seed_accounts
if errorlevel 1 goto :fail

REM --- 5. Admin account (optional) ------------------------------------
echo.
set "MAKEADMIN=n"
set /p "MAKEADMIN=Create an admin login now? (y/n): "
if /i "%MAKEADMIN%"=="y" python manage.py createsuperuser

echo.
echo ===== Setup done! =====
echo Next time, just double-click run.bat
echo Starting the site at http://127.0.0.1:8000/   (press Ctrl+C to stop)
echo.
python manage.py runserver
goto :eof

:fail
echo.
echo Setup stopped. Fix the problem above and run setup.bat again.
pause
exit /b 1
