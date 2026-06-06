@echo off
echo ================================================
echo   ติดตั้ง SpeechPanel
echo ================================================
echo.
echo กำลังติดตั้ง Python packages...
pip install customtkinter numpy sounddevice SpeechRecognition deep-translator pyperclip keyboard google-cloud-speech
echo.
echo ================================================
echo  ติดตั้งเสร็จแล้ว!
echo  เปิดโปรแกรมด้วยการดับเบิลคลิก start_speech_panel.bat
echo ================================================
echo.
pause
