@echo off
echo ================================================
echo   BUILD SpeechPanel.exe
echo ================================================
echo.

REM Check if PyInstaller is installed
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [INSTALLING] PyInstaller not found. Installing now...
    pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo.
        echo [ERROR] Could not install PyInstaller.
        echo         Please make sure Python and pip are installed correctly.
        echo.
        pause
        exit /b 1
    )
    echo [OK] PyInstaller installed.
    echo.
)

REM Build the exe
echo [BUILDING] Creating SpeechPanel.exe ... (this may take 2-5 minutes)
echo.
pyinstaller SpeechPanel.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed. See messages above for details.
    echo.
    pause
    exit /b 1
)

REM Copy manual and readme into the output folder
if exist "speech_manual.html" (
    copy /Y "speech_manual.html" "dist\SpeechPanel\" >nul
    echo [COPY] Copied speech_manual.html to dist\SpeechPanel\
)
if exist "README.md" (
    copy /Y "README.md" "dist\SpeechPanel\" >nul
)

echo.
echo ================================================
echo   BUILD COMPLETE!
echo.
echo   Output folder:  dist\SpeechPanel\
echo.
echo   TO SHARE with another PC:
echo   1. Open the folder:  dist\SpeechPanel\
echo   2. Right-click it -> Send to -> Compressed (zip)
echo   3. Send the zip file to the other PC
echo   4. On the other PC: Extract zip, then
echo      double-click SpeechPanel.exe to run.
echo.
echo   NOTE: The other PC does NOT need Python installed.
echo ================================================
echo.
echo Press any key to open the output folder...
pause >nul
if exist "dist\SpeechPanel\" (
    explorer "dist\SpeechPanel\"
)
