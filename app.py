from flask import Flask, request, render_template, send_file, redirect, session
from io import BytesIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pathlib import Path
import subprocess
from pdf2docx import Converter
from PIL import Image
from moviepy import VideoFileClip
import uuid
import mimetypes

# --- Conversion Functions ---
def docx_to_pdf(input_path, output_path):
    """
    On Linux servers, the path to soffice.exe will change to just 'libreoffice'
    """
    subprocess.run([
        "C:\Program Files\LibreOffice\program\soffice.exe", "--headless", "--convert-to", "pdf",
        "--outdir", str(Path(output_path).parent), str(input_path)
    ], check=True)


def ocr_pdf_to_docx(pdf_path, output_path, lang):
    import subprocess
    temp_pdf = UPLOAD_FOLDER / "ocr_temp.pdf"

    # Run OCRmyPDF command
    subprocess.run([
        "ocrmypdf",
       "--force-ocr",
        "--language", lang,
        str(pdf_path),
        str(temp_pdf)
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




# --- File Upload Config ---
"""
On a Linux server, change to:
UPLOAD_FOLDER = "/tmp/uploads"
"""
UPLOAD_FOLDER = Path(__file__).parent / "uploads"
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)

# --- Flask Config ---
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for session management
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# --- Models ---
class User(db.Model):
    id = db.Column(db.String(50), primary_key=True)  # Use UUIDs for temp users
    created_at = db.Column(db.DateTime, default=datetime.now)
    uploads = db.relationship('Upload', backref='user', cascade="all, delete")


class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    date = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.String(50), db.ForeignKey('user.id'), nullable=False)


# --- Utility Functions ---
def get_or_create_user():
    """Create a temporary user if not in session"""
    if "user_id" not in session:
        user_id = str(uuid.uuid4())
        user = User(id=user_id)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user_id
        print(f"New temporary user created: {user_id}")
    else:
        user_id = session["user_id"]
    return user_id

def cleanup_uploads():
    for f in UPLOAD_FOLDER.glob("*"):
        try:
            f.unlink()
        except Exception as e:
            print(f"Could not delete {f}: {e}")


# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def index():
    user_id = get_or_create_user()

    if request.method == 'POST':
        file = request.files['file']
        input_path = Path(UPLOAD_FOLDER) / file.filename
        file.save(input_path)
        ext = input_path.suffix.lower()

        if ext in [".docx", ".pdf"]:
            # Save uploaded file
            upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
            db.session.add(upload)

            # Convert
            if ext == ".docx":
                output_path = input_path.with_suffix(".pdf")
                docx_to_pdf(input_path, output_path)
            elif ext == ".pdf":
                output_path = input_path.with_suffix(".docx")
                ocr_pdf_to_docx(input_path, output_path, lang='ara')

            # Save converted file
            converted_file = Upload(name=output_path.name, data=output_path.read_bytes(), user_id=user_id)
            db.session.add(converted_file)
            db.session.commit()

            # Clean up uploads folder
            cleanup_uploads()

            return render_template('download.html', ids=converted_file.id)
        else:
            # Delete invalid upload
            cleanup_uploads()
            return render_template('upload.html', x=2)
    return render_template('upload.html')



@app.route('/images', methods = ['GET','POST'])
def images():
    user_id = get_or_create_user()

    if request.method == "POST":
        file = request.files["file"]
        target_format = request.form.get("format")  # jpg/png/webp

        if not file or not target_format:
            return "Missing file or target format", 400

        input_path = UPLOAD_FOLDER / file.filename
        file.save(input_path)
        ext = input_path.suffix.lower()

        if ext in ['.png','.jpg','.jpeg','.webp']:
            upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
            db.session.add(upload)

            output_path = convert_image(input_path, target_format)

            converted_file = Upload(name=output_path.name, data=output_path.read_bytes(), user_id=user_id)
            db.session.add(converted_file)
            db.session.commit()
            cleanup_uploads()

            return render_template("download.html", ids=converted_file.id)
        else:
            cleanup_uploads()
            return render_template("upload_images.html", x=2)
    return render_template("upload_images.html")

@app.route('/videos', methods = ['GET','POST'])
def video():
    user_id = get_or_create_user()

    if request.method == "POST":
        file = request.files["file"]
        target_format = request.form.get("format")  # mp4/mkv/avi/mov

        if not file or not target_format:
            return "Missing file or target format", 400

        input_path = UPLOAD_FOLDER / file.filename
        file.save(input_path)
        ext = input_path.suffix.lower()

        if ext in ['.mkv','.mp4','.avi','.mov']:
            upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
            db.session.add(upload)

            output_path = convert_video(input_path, target_format)

            converted_file = Upload(name=output_path.name, data=output_path.read_bytes(), user_id=user_id)
            db.session.add(converted_file)
            db.session.commit()
            cleanup_uploads()

            return render_template("download.html", ids=converted_file.id)
        else:
            cleanup_uploads()
            return render_template("upload_video.html", x=2)

    return render_template("upload_video.html")


@app.route('/download/<upload_id>')
def download(upload_id):
    try:
        upload = Upload.query.filter_by(id=upload_id, user_id=session.get("user_id")).first()
        if not upload:
            return "File not found or access denied"
        return send_file(BytesIO(upload.data), download_name=upload.name, as_attachment=True)
    except Exception as e:
        return f"There was an issue downloading this file: {e}"


@app.route('/delete/<upload_id>')
def delete(upload_id):
    upload = Upload.query.filter_by(id=upload_id, user_id=session.get("user_id")).first()
    if not upload:
        return "File not found or access denied"
    try:
        db.session.delete(upload)
        db.session.commit()
        return redirect('/files')
    except:
        return 'There was an issue deleting this file'




@app.route('/files')
def files():
    user_id = get_or_create_user()
    user_files = Upload.query.filter_by(user_id=user_id).order_by(Upload.id).all()
    return render_template('files.html', files=user_files)


@app.route('/logout')
def logout():
    """Delete all user data and log out"""
    user_id = session.get("user_id")
    if user_id:
        user = User.query.filter_by(id=user_id).first()
        if user:
            db.session.delete(user)
            db.session.commit()
            print(f"Deleted user {user_id} and their uploads.")
        session.pop("user_id", None)
    return redirect('/')


@app.route('/compress', methods=['GET', 'POST'])
def compress():
    user_id = get_or_create_user()

    if request.method == 'POST':
        file = request.files['file']
        compression_level = request.form['compression_level'] 

        input_path = Path(UPLOAD_FOLDER) / file.filename
        file.save(input_path)

        mime = file.mimetype.lower()
        output_path = input_path.with_name(f"compressed_{file.filename}")

        try:
            if "image" in mime:
                upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
                compress_image(input_path, output_path, compression_level)
            elif "video" in mime:
                upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
                compress_video(input_path, output_path, compression_level)
            else:
                cleanup_uploads()
                return render_template('compress.html', x=2)

            compressed_data = output_path.read_bytes()

            compressed_upload = Upload(
                name=output_path.name,
                data=compressed_data,
                user_id=user_id
            )
            db.session.add(upload)
            db.session.add(compressed_upload)
            db.session.commit()

            cleanup_uploads()

            return render_template('download.html', ids=compressed_upload.id , x= 2, ogsize = round((len(upload.data)/ 1024**2), 2),
                                    csize = round((len(compressed_upload.data)/ 1024**2), 2))

        except Exception as e:
            return render_template('compress.html', error=f"Compression failed: {e}")

    return render_template('compress.html')



@app.route('/go/<page>')
def navigate(page):
    match page:
        case '1':
            return redirect('/')
        case '3':
            return redirect('/files')
        case '2':
            return redirect('/images')
        case '4':
            return redirect('/videos')
        case '5':
            return redirect('/compress')


# --- Run App ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
