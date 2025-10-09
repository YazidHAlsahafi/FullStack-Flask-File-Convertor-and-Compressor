# 🧩 Flask Document & Media Converter

A **Flask-based full-stack file converter** that:
- Converts between **PDF ↔ DOCX** with **OCR (Arabic + multilingual support)**.
- Converts and compresses **image and video files**.
- Stores files per temporary user session using **Flask + SQLAlchemy**.
- Automatically removes user data upon logout.

---

## ⚙️ Features

✅ PDF ↔ DOCX conversion (with OCR via `ocrmypdf`)  
✅ Image and video format conversion  
✅ User-specific file management (temporary sessions)  
✅ Image and video compression (three selectable levels)  
✅ SQLite database integration with SQLAlchemy  

---

## 🧰 Requirements

### ⚙️ System Dependencies

| Tool              | Purpose                                         | Windows Installation                                                               |
| ----------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Tesseract OCR** | OCR engine used by `ocrmypdf`                   | [Tesseract Download (UB Mannheim)](https://github.com/UB-Mannheim/tesseract/wiki)  |
| **LibreOffice**   | Converts `.docx` → `.pdf`                       | [LibreOffice Download](https://www.libreoffice.org/download/download-libreoffice/) |
| **FFmpeg**        | Video and image format conversion + compression | [FFmpeg Download](https://ffmpeg.org/download.html)                                |




### 🧑‍💻 Python Dependencies
Install via:
```bash
pip install -r requirements.txt
