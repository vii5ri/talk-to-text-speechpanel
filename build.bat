@echo off
chcp 65001 >nul
echo ================================================
echo   สร้าง SpeechPanel.exe (PyInstaller)
echo ================================================
echo.

REM ── ตรวจสอบ PyInstaller ──────────────────────────────────────────────────────
where pyinstaller >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ติดตั้ง] PyInstaller ไม่พบ — กำลังติดตั้ง...
    pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo [ผิดพลาด] ติดตั้ง PyInstaller ไม่สำเร็จ กรุณาตรวจสอบ Python และ pip
        pause & exit /b 1
    )
)

REM ── Build ─────────────────────────────────────────────────────────────────────
echo [Build] กำลังสร้าง exe...
pyinstaller SpeechPanel.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ผิดพลาด] Build ไม่สำเร็จ ดูข้อความข้างบนเพื่อหาสาเหตุ
    pause & exit /b 1
)

REM ── Copy คู่มือและ README ──────────────────────────────────────────────────────
if exist "speech_manual.html" (
    copy /Y "speech_manual.html" "dist\SpeechPanel\" >nul
    echo [Copy] คัดลอก speech_manual.html ไปยัง dist\SpeechPanel\
)
if exist "README.md" (
    copy /Y "README.md" "dist\SpeechPanel\" >nul
)

echo.
echo ================================================
echo   Build สำเร็จ!
echo   ไฟล์ทั้งหมดอยู่ใน:  dist\SpeechPanel\
echo.
echo   วิธีแจกจ่าย:
echo   1. Zip โฟลเดอร์ dist\SpeechPanel\ ทั้งโฟลเดอร์
echo   2. ส่ง zip ให้เครื่องอื่น
echo   3. แตก zip แล้วดับเบิลคลิก SpeechPanel.exe
echo   (ไม่ต้องติดตั้ง Python หรือ pip ในเครื่องปลายทาง)
echo ================================================
echo.
pause
