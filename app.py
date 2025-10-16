from flask import Flask, request, render_template, send_file, redirect, session
from io import BytesIO
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pathlib import Path
import uuid
from functions import *

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
@app.route('/')
def index():
    user_id = get_or_create_user()
    return render_template('index.html')

@app.route('/convert/<doc>', methods=['GET', 'POST'])
def documents(doc):
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
            if doc == "docx":
                output_path = input_path.with_suffix(".pdf")
                docx_to_pdf(input_path, output_path)
            elif doc == "pdf":
                output_path = input_path.with_suffix(".docx")
                pdf_to_docx(input_path, output_path)
            elif doc == "pdf_ocr":
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
            return render_template('upload.html', x=2, doc=doc)
    match doc:
        case 'pdf':
            return render_template('upload.html', doc=doc)
        case 'docx':
            return render_template('upload.html', doc=doc)
        case 'pdf_ocr':
            return render_template('upload.html', doc=doc)

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

        if ext == ('.'+target_format):
            cleanup_uploads()
            return render_template("upload_images.html", x=1)

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

        if ext == ('.'+target_format):
            cleanup_uploads()
            return render_template("upload_video.html", x=1)

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

# --- Run App ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
