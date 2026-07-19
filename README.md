# SpeechPanel — วิธี Install

โปรแกรมแปลงเสียงเป็นข้อความ ภาษาไทย / อังกฤษ  
รองรับ 4 โหมด: Free (Google STT) | Whisper (ออฟไลน์) | Vosk (ออฟไลน์) | Google Cloud STT

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
| `F10` | เริ่ม / หยุด บันทึกเสียง |
| `F9` | บันทึกเสียงแล้วพิมพ์ลงแอปที่ใช้งานอยู่ |
| ปุ่ม 🎤 | เริ่ม / หยุด บันทึกเสียง |
| คลิกที่กล่องข้อความ | Copy ข้อความในกล่องนั้น |
| ปุ่ม ✨ บนการ์ด | AI Polish — ตัดคำสร้อย จัดประโยคให้เรียบร้อย |

## โหมด STT

| โหมด | รายละเอียด |
|------|-----------|
| 🌐 Free | ใช้ Google STT ฟรี ต้องมีอินเทอร์เน็ต |
| 🤖 Whisper | ออฟไลน์ คุณภาพสูง ใส่ punctuation อัตโนมัติ |
| 🔌 Vosk | ออฟไลน์ real-time ต้อง download model แยก |
| ☁️ Cloud | Google Cloud STT real-time คุณภาพสูง (60 นาที/เดือน ฟรี) |

---

## ✨ AI Polish — ตั้งค่า Groq API Key

ฟีเจอร์ Polish ใช้ AI ตัดคำสร้อย (เอ่อ อ่า อืม) และจัดประโยคให้อ่านง่ายขึ้น  
ใช้ **Groq API** ซึ่งมีให้ฟรี ไม่ต้องใส่บัตรเครดิต

### ขั้นตอนรับ API Key (ฟรี)

1. ไปที่ [console.groq.com](https://console.groq.com)
2. สมัคร / Login ด้วย Google หรืออีเมล
3. เมนูซ้าย → **API Keys** → **Create API Key**
4. ตั้งชื่อ key (อะไรก็ได้) → Copy key ที่ได้

### ใส่ Key ในโปรแกรม

1. เปิด SpeechPanel
2. กดปุ่ม **🔑** ที่มุมขวาบน
3. วาง API Key → กด OK
4. กด ✨ บนการ์ดใดก็ได้เพื่อทดสอบ

### ข้อจำกัด free tier

| รายการ | ค่า |
|--------|-----|
| Request/นาที | 30 |
| Request/วัน | 14,400 |
| ต้องการอินเทอร์เน็ต | ✓ |

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
