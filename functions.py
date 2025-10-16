from pathlib import Path
import subprocess
from pdf2docx import Converter
from PIL import Image
from moviepy import VideoFileClip
import shutil
import platform

def find_libreoffice():
    """
    Detects LibreOffice executable depending on OS.
    Returns full path or raises FileNotFoundError.
    """
    system = platform.system()
    if system == "Windows":
        # Default installation paths
        possible_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path
        raise FileNotFoundError("LibreOffice not found. Please install or update path.")
    else:
        # Linux / Mac
        path = shutil.which("libreoffice") or shutil.which("soffice")
        if path:
            return path
        raise FileNotFoundError("LibreOffice not found in PATH.")


# --- Conversion Functions ---
def docx_to_pdf(input_path, output_path):
    """
    On Linux servers, the path to soffice.exe will change to just 'libreoffice'
    """
    subprocess.run([
        "C:\Program Files\LibreOffice\program\soffice.exe", "--headless", "--convert-to", "pdf",
        "--outdir", str(Path(output_path).parent), str(input_path)
    ], check=True)


def pdf_to_docx(pdf_path, output_path):

    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    
    cv = Converter(str(pdf_path))
    # Convert all pages
    cv.convert(str(output_path), start=0, end=None)
    cv.close()


def ocr_pdf_to_docx(pdf_path, output_path, lang):
    temp_pdf = "ocr_temp.pdf"

    # Run OCRmyPDF command
    subprocess.run([
        "ocrmypdf",
       "--force-ocr",
        "--language", lang,
        pdf_path,
        temp_pdf
    ], check=True)

    # Convert to DOCX
    cv = Converter(temp_pdf)
    cv.convert(output_path, start=0, end=None)
    cv.close()
    print(f"✅ OCR-based DOCX saved: {output_path}")






def convert_image(input_path, output_format):
    """
    Converts images between formats using Pillow (PIL).
    Example: PNG -> JPG, WEBP -> PNG, etc.
    """
    img = Image.open(input_path).convert("RGB")  # Convert to RGB to avoid mode issues
    output_path = Path(input_path).with_suffix(f".{output_format.lower()}")
    img.save(output_path)
    print(f"✅ Image converted to {output_path}")
    return output_path

def convert_video(input_path, output_format):
    """
    Converts video formats using MoviePy and FFmpeg.
    Example: MKV -> MP4, AVI -> MOV, etc.
    """
    input_path = Path(input_path)
    output_path = input_path.with_suffix(f".{output_format.lower()}")
    with VideoFileClip(str(input_path)) as clip:
        clip.write_videofile(str(output_path), codec='libx264', audio_codec='aac')
    print(f"✅ Video converted to {output_path}")
    return output_path







# --- Compression Functions ---

def compress_image(input_path, output_path, level):
    """Compress image based on user-selected level (high, medium, low)."""
    quality_map = {
        "high": 30,      # smallest file
        "medium": 60,    # balanced
        "low": 85        # best quality
    }
    quality = quality_map.get(level.lower())

    if quality is None:
        raise ValueError(f"Invalid compression level: {level}")

    img = Image.open(input_path)
    img.save(output_path, optimize=True, quality=quality)
    print(f"🖼️ Image compressed at {level} level → {output_path}")


def compress_video(input_path, output_path, level):
    """Compress video using ffmpeg based on user-selected level (high, medium, low)."""
    bitrate_map = {
        "high": "500k",     # smallest file
        "medium": "1000k",  # balanced
        "low": "2000k"      # best quality
    }
    bitrate = bitrate_map.get(level.lower())

    if bitrate is None:
        raise ValueError(f"Invalid compression level: {level}")

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-b:v", bitrate,
        str(output_path)
    ], check=True)
    print(f"🎬 Video compressed at {level} level → {output_path}")
