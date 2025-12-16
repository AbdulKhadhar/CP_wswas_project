@echo off
echo ==========================================
echo WSWAS - Windows Setup Script
echo ==========================================
echo.

echo [1/5] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo.
echo [2/5] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [3/5] Running migrations...
python manage.py makemigrations
python manage.py migrate

echo.
echo [4/5] Creating superuser...
echo Please create admin account:
python manage.py createsuperuser

echo.
echo [5/5] Collecting static files...
python manage.py collectstatic --noinput

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo To start the server, run:
echo   venv\Scripts\activate
echo   python -m daphne -b 0.0.0.0 -p 8000 wswas.asgi:application
echo.
pause