# SpeechPanel v2 — วิธี Install

โปรแกรมแปลงเสียงเป็นข้อความ ภาษาไทย / อังกฤษ  
รองรับ 3 โหมด: Free (Google STT) | Vosk (ออฟไลน์) | Google Cloud STT

---

## สิ่งที่ต้องเตรียม

- Windows 10 / 11
- Python 3.11 ขึ้นไป
- อินเทอร์เน็ต (สำหรับโหมด Free และ Google Cloud)

---

## ขั้นตอนการติดตั้ง

### ขั้นที่ 1 — ติดตั้ง Python

1. ไปที่ [python.org](https://www.python.org/downloads/)
2. ดาวน์โหลด Python 3.11 หรือใหม่กว่า
3. เปิดตัวติดตั้ง → **ติ๊ก "Add Python to PATH"** (สำคัญมาก)
4. กด Install Now รอจนเสร็จ

### ขั้นที่ 2 — ติดตั้ง Packages

1. เปิดโฟลเดอร์ `Talk to Text SpeechPanel`
2. ดับเบิลคลิก **`install.bat`**
3. รอจนหน้าต่างแสดง "ติดตั้งเสร็จแล้ว!" แล้วกด Enter

> ถ้าต้องการติดตั้งเองให้เปิด Command Prompt แล้วพิมพ์:
> ```
> pip install customtkinter numpy sounddevice SpeechRecognition deep-translator pyperclip keyboard google-cloud-speech
> ```

### ขั้นที่ 3 — ตั้งค่า Google Cloud (โหมด gcloud)

> ข้ามขั้นนี้ได้ถ้าจะใช้โหมด Free แทน

1. ติดตั้ง [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
2. เปิด Command Prompt แล้วพิมพ์:
   ```
   gcloud auth application-default login
   ```
3. Browser จะเปิดขึ้น → Login บัญชี Google → Allow
4. เปิดโปรแกรม → กด ⚙️ → เลือก Service Account JSON file

### ขั้นที่ 4 — เปิดโปรแกรม

ดับเบิลคลิก **`start_speech_panel.bat`**

โปรแกรมจะเปิดที่ขอบซ้ายของหน้าจอ

---

## การใช้งาน

| ปุ่ม / คีย์ | ฟังก์ชัน |
|------------|---------|
| `Ctrl+Shift+Space` | แสดง / ซ่อนหน้าต่าง |
| `Space` | เริ่ม / หยุด บันทึกเสียง |
| ปุ่ม 🎤 | เริ่ม / หยุด บันทึกเสียง |
| คลิกที่กล่องข้อความ | Copy ข้อความในกล่องนั้น |

## โหมด STT

| โหมด | รายละเอียด |
|------|-----------|
| 🌐 Free | ใช้ Google STT ฟรี ต้องมีอินเทอร์เน็ต |
| 🔌 Vosk | ออฟไลน์ real-time ต้อง download model แยก |
| ☁️ Cloud | Google Cloud STT real-time คุณภาพสูง (60 นาที/เดือน ฟรี) |

---

## ไฟล์ในโฟลเดอร์นี้

| ไฟล์ | หน้าที่ |
|------|--------|
| `speech_panel.py` | โปรแกรมหลัก |
| `speech_panel_config.json` | ไฟล์ตั้งค่า (โหมด, credentials path) |
| `start_speech_panel.bat` | เปิดโปรแกรม |
| `install.bat` | ติดตั้ง Python packages |
| `requirements.txt` | รายการ packages |
| `SpeechPanel.spec` | สำหรับ build เป็น .exe (ถ้าต้องการ) |
