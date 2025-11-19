from flask import Flask, request, render_template, send_file, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pathlib import Path
from io import BytesIO
import uuid
import time
import os

from celery import Celery
from celery.result import AsyncResult

from functions import (
    docx_to_pdf, pdf_to_docx, ocr_pdf_to_docx, pdf_to_docx_text, pdf_to_text,
    convert_image, convert_video,
    compress_image, compress_video
)

# --- Flask config ---
app = Flask(__name__)
app.secret_key = "supersecretkey"
db_path = os.environ.get("SQLITE_PATH", "db.sqlite3")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Upload folder ---
UPLOAD_FOLDER = Path(__file__).parent / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# --- Celery config ---
redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
celery = Celery(
    app.name,
    broker=redis_url,
    backend=redis_url,
)
celery.conf.update(
    task_track_started=True,
)

# --- Models ---
class User(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    uploads = db.relationship('Upload', backref='user', cascade="all, delete")


class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    date = db.Column(db.DateTime, default=datetime.now)
    user_id = db.Column(db.String(50), db.ForeignKey('user.id'), nullable=False)


# --- Utility functions ---
def get_or_create_user():
    if "user_id" not in session:
        user_id = str(uuid.uuid4())
        user = User(id=user_id)
        db.session.add(user)
        db.session.commit()
        session["user_id"] = user_id
    else:
        user_id = session["user_id"]
    return user_id

def cleanup_uploads():
    for f in UPLOAD_FOLDER.glob("*"):
        try:
            f.unlink()
        except Exception as e:
            print(f"Could not delete {f}: {e}")

def wait_for_file(path, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        if path.exists() and path.stat().st_size > 0:
            return True
        time.sleep(0.5)
    raise TimeoutError(f"File {path} not created in time.")

# --- Celery Tasks ---

# 1. DOCX → PDF
@celery.task(bind=True)
def async_docx_to_pdf(self, input_path, output_path, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل ملف DOCX الى PDF...'})
    docx_to_pdf(input_path, output_path)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})
    
    wait_for_file(Path(output_path))
    
    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 2. PDF → DOCX
@celery.task(bind=True)
def async_pdf_to_docx(self, input_path, output_path, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل ملف PDF الى DOCX...'})
    pdf_to_docx(input_path, output_path)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))

    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 3. OCR PDF → DOCX
@celery.task(bind=True)
def async_ocr_pdf_to_docx(self, input_path, output_path, lang, user_id):
    temp_pdf = Path(output_path).parent / "ocr_temp.pdf"
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل ملف PDF الى DOCX بأستخدام OCR ...'})
    ocr_pdf_to_docx(input_path, output_path, lang)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))

    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    Path(temp_pdf).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 4. Pdf text contents to Docx conversion
@celery.task(bind=True)
def async_pdf_to_docx_text(self, input_path, output_path, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل ملف PDF الى DOCX...'})
    pdf_to_docx_text(input_path, output_path)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))

    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}

# 5. Pdf to Text file conversion.
@celery.task(bind=True)
def async_pdf_to_text(self, input_path, output_path, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل ملف PDF الى DOCX...'})
    pdf_to_text(input_path, output_path)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))

    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 6. Image conversion
@celery.task(bind=True)
def async_convert_image(self, input_path, output_format, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل صيغة ملف الصورة...'})
    output_path = convert_image(input_path, output_format)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))

    converted_file = Upload(
        name=output_path.name,
        data=output_path.read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 7. Video conversion
@celery.task(bind=True)
def async_convert_video(self, input_path, output_format, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري تحويل صيغة ملف الفيديو...'})
    output_path = convert_video(input_path, output_format)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))
    
    converted_file = Upload(
        name=output_path.name,
        data=output_path.read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 8. Image compression
@celery.task(bind=True)
def async_compress_image(self, input_path, output_path, level, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري ظغط ملف الصورة...'})
    compress_image(input_path, output_path, level)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))
    
    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# 9. Video compression
@celery.task(bind=True)
def async_compress_video(self, input_path, output_path, level, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'جاري ظغط ملف الفيديو...'})
    compress_video(input_path, output_path, level)
    self.update_state(state='PROGRESS', meta={'progress': 80, 'status': 'جاري حفظ الملف...'})

    wait_for_file(Path(output_path))
    
    converted_file = Upload(
        name=Path(output_path).name,
        data=Path(output_path).read_bytes(),
        user_id=user_id
    )
    with app.app_context():
        db.session.add(converted_file)
        db.session.commit()
        file_id = converted_file.id
    Path(input_path).unlink()
    Path(output_path).unlink()
    return {'status': 'تم', 'file_id': file_id}


# --- Routes ---
@app.route('/')
def index():
    get_or_create_user()
    return render_template('index.html')


@app.route("/convert/<doc_type>", methods=["GET", "POST"])
def convert_route(doc_type):
    user_id = get_or_create_user()
    if request.method == "POST":
        file = request.files["file"]
        input_path = UPLOAD_FOLDER / file.filename
        file.save(input_path)

        upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
        db.session.add(upload)
        db.session.commit()

        if doc_type == "docx":
            output_path = input_path.with_suffix(".pdf")
            task = async_docx_to_pdf.apply_async(args=(str(input_path), str(output_path), user_id))
        elif doc_type == "pdf":
            output_path = input_path.with_suffix(".docx")
            task = async_pdf_to_docx.apply_async(args=(str(input_path), str(output_path), user_id))
        elif doc_type == "pdf_ocr":
            output_path = input_path.with_suffix(".docx")
            task = async_ocr_pdf_to_docx.apply_async(args=(str(input_path), str(output_path), "ara", user_id))
        elif doc_type == "pdf_text":
            output_path = input_path.with_suffix(".docx")
            task = async_pdf_to_docx_text.apply_async(args=(str(input_path), str(output_path), user_id))
        elif doc_type == "pdf_text_only":
            output_path = input_path.with_suffix(".txt")
            task = async_pdf_to_text.apply_async(args=(str(input_path), str(output_path), user_id))
        else:
            Path(input_path).unlink()
            return "Invalid conversion type", 400

        
        return render_template("progress.html", task_id=task.id)

    return render_template("upload.html", doc=doc_type)


@app.route("/images", methods=["GET", "POST"])
def convert_images():
    user_id = get_or_create_user()
    if request.method == "POST":
        file = request.files["file"]
        target_format = request.form.get("format")
        if not file or not target_format:
            return "Missing file or format", 400

        input_path = UPLOAD_FOLDER / file.filename
        file.save(input_path)

        upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
        db.session.add(upload)
        db.session.commit()
        
        task = async_convert_image.apply_async(args=(str(input_path), target_format, user_id))
        return render_template("progress.html", task_id=task.id)
    return render_template("upload_images.html")


@app.route("/videos", methods=["GET", "POST"])
def convert_videos():
    user_id = get_or_create_user()
    if request.method == "POST":
        file = request.files["file"]
        target_format = request.form.get("format")
        if not file or not target_format:
            return "Missing file or format", 400

        input_path = UPLOAD_FOLDER / file.filename
        file.save(input_path)

        upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
        db.session.add(upload)
        db.session.commit()

        task = async_convert_video.apply_async(args=(str(input_path), target_format, user_id))
        return render_template("progress.html", task_id=task.id)
    return render_template("upload_video.html")


@app.route("/compress", methods=["GET", "POST"])
def compress_route():
    user_id = get_or_create_user()
    if request.method == "POST":
        file = request.files["file"]
        level = request.form.get("compression_level")
        input_path = UPLOAD_FOLDER / file.filename
        file.save(input_path)

        upload = Upload(name=file.filename, data=input_path.read_bytes(), user_id=user_id)
        db.session.add(upload)
        db.session.commit()
        
        output_path = UPLOAD_FOLDER / f"compressed_{file.filename}"

        mime = file.mimetype.lower()
        if "image" in mime:
            task = async_compress_image.apply_async(args=(str(input_path), str(output_path), level, user_id))
        elif "video" in mime:
            task = async_compress_video.apply_async(args=(str(input_path), str(output_path), level, user_id))
        else:
            Path(input_path).unlink()
            return "Invalid file type for compression", 400

        return render_template("progress.html", task_id=task.id)

    return render_template("compress.html")


@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = AsyncResult(task_id, app=celery)
    if task.state == "FAILURE":
        response = {"state": task.state, "error": str(task.info)}
    else:
        info = task.info if isinstance(task.info, dict) else {}
        response = {"state": task.state, **info}
    return jsonify(response)


@app.route('/download/<upload_id>')
def download(upload_id):
    upload = Upload.query.filter_by(id=upload_id, user_id=session.get("user_id")).first()
    if not upload:
        return "File not found or access denied"
    return send_file(BytesIO(upload.data), download_name=upload.name, as_attachment=True)

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


# --- Initialize database ---
def init_db():
    """Initialize database tables if they don't exist."""
    with app.app_context():
        db.create_all()
        print("✅ Database initialized")

# Initialize database on import (works for both web and worker)
init_db()

# --- Run app ---
if __name__ == "__main__":
    app.run(debug=True)