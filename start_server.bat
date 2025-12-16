@echo off
echo ==========================================
echo Starting WSWAS Server
echo ==========================================
echo.

call venv\Scripts\activate.bat

echo Finding your IP address...
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set IP=%%a
    goto :found
)
:found
echo.
echo ==========================================
echo Server will be accessible at:
echo   Local:    http://localhost:8000
echo   Network:  http:%IP%:8000
echo ==========================================
echo.
echo Press Ctrl+C to stop the server
echo.

python -m daphne -b 0.0.0.0 -p 8000 wswas.asgi:application