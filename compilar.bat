@echo off
setlocal
cd /d "%~dp0"
title Compilar Videos MP3 Downloader

echo ============================================================
echo   Compilando "Videos MP3 Downloader"
echo ============================================================
echo.

rem --- Comprobar Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Instala Python desde https://www.python.org/downloads/
    echo y marca la opcion "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

rem --- Comprobar archivos necesarios ---
if not exist "gui.py" (
    echo ERROR: no se encontro gui.py. Ejecuta este script desde la carpeta del proyecto.
    pause
    exit /b 1
)
if not exist "ffmpeg\bin\ffmpeg.exe" (
    echo ERROR: falta ffmpeg\bin\ffmpeg.exe
    echo Coloca FFmpeg en la carpeta "ffmpeg" antes de compilar.
    pause
    exit /b 1
)
if not exist "iconos\logo.ico" (
    echo ERROR: falta iconos\logo.ico
    pause
    exit /b 1
)

rem --- Avisar si el programa esta abierto (bloquea el .exe) ---
tasklist /fi "imagename eq Videos MP3 Downloader.exe" 2>nul | find /i "Videos MP3 Downloader.exe" >nul
if not errorlevel 1 (
    echo ERROR: el programa parece estar abierto.
    echo Cierralo antes de compilar y vuelve a ejecutar este script.
    echo.
    pause
    exit /b 1
)

rem --- Instalar o actualizar dependencias ---
echo Instalando/actualizando dependencias...
python -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto error

rem --- Limpiar compilaciones anteriores ---
echo.
echo Limpiando compilaciones anteriores...
if exist "build\gui" (
    attrib -r -s -h "build\gui\*.*" /s /d >nul 2>&1
    rmdir /s /q "build\gui" >nul 2>&1
)
if exist "dist\Videos MP3 Downloader.exe" del /q "dist\Videos MP3 Downloader.exe" >nul 2>&1

rem --- Compilar ---
echo.
echo Compilando el ejecutable (puede tardar varios minutos)...
python -m PyInstaller gui.spec --noconfirm --clean
if errorlevel 1 goto error

rem --- Copiar README junto al .exe ---
if exist "README.md" copy /y "README.md" "dist\README.md" >nul

echo.
echo ============================================================
echo   LISTO
echo ============================================================
echo.
echo Ejecutable creado en:
echo   %CD%\dist\Videos MP3 Downloader.exe
echo.
pause
exit /b 0

:error
echo.
echo ============================================================
echo   ERROR: la compilacion no se pudo completar
echo ============================================================
echo Revisa los mensajes anteriores. Si el problema es una
echo dependencia, prueba:
echo   python -m pip install --upgrade -r requirements.txt
echo.
pause
exit /b 1
