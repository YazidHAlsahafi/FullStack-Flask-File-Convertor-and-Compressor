# 🧩 Flask Document & Media Converter

A **Flask-based full-stack file converter** that:
- Converts between **PDF ↔ DOCX** with **OCR (Arabic + multilingual support)**.
- Extracts text from **PDF** files and puts them in **TXT** files.
- Converts and compresses **image and video files**.
- Stores files per temporary user session using **Flask + SQLAlchemy**.
- Automatically removes user data upon logout.

---

## ⚙️ Features

✅ PDF ↔ DOCX conversion (with OCR via `ocrmypdf`)  
✅ PDF → TXT extraction 
✅ Image and video format conversion  
✅ User-specific file management (temporary sessions)  
✅ Image and video compression (three selectable levels)  
✅ SQLite database integration with SQLAlchemy  

---
## Running through docker
This is the intended way to run the application directly through docker (you will need docker on your device): 

Step 1.
Navigate to the application folder and run the following:
``` bash 
   docker-compose build --no-cache
   docker-compose up -d
```

Step 2.
go to http://localhost:8000 and the app should be running.

---

## 🧰 Requirements for running without docker

### ⚙️ System Dependencies

| Tool              | Purpose                                         | Windows Installation                                                               |
| ----------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Tesseract OCR** | OCR engine used by `ocrmypdf`                   | [Tesseract Download (UB Mannheim)](https://github.com/UB-Mannheim/tesseract/wiki)  |
| **LibreOffice**   | Converts `.docx` → `.pdf`                       | [LibreOffice Download](https://www.libreoffice.org/download/download-libreoffice/) |
| **FFmpeg**        | Video and image format conversion + compression | [FFmpeg Download](https://ffmpeg.org/download.html)                                |


---

### 🧑‍💻 Python Dependencies
Install via:
```bash
pip install -r requirements.txt
```
---
### Running the app
Step 1.
you will need a redis server running on your device, I chose to run redis through Docker Desktop and I used the following command to start it:
```bash
docker run -d --name redis -p 6379:6379 redis:7
```
Step 2.
you will need to run celery on the redis port via: 
```bash
celery -A app.celery worker --loglevel=info --pool=solo
```
Note: --pool=solo is needed if you're running this on a windows device.

Step 3.
run the app: 
```bash
python app.py
```

### Running the test file
you will need pytest installed, run the test file via:
```bash
pytest -v
```
