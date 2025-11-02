import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
from app import app, db, celery
import os 

# ------------------------------------------------------------------------------
# 1️⃣  Pytest Fixtures
# ------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """
    Flask test client using an in-memory SQLite database.
    Celery is configured to run tasks synchronously (no Redis required).
    """
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    # Use Celery in-memory broker & backend
    celery.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=True,  # Run tasks instantly
    )

    with app.app_context():
        yield app.test_client()


@pytest.fixture
def tmp_docx(tmp_path):
    """Create a temporary DOCX file for conversion tests."""
    docx_path = tmp_path / "test.docx"
    docx_path.write_text("Fake DOCX content")
    return docx_path


@pytest.fixture
def tmp_pdf(tmp_path):
    """Create a temporary PDF file for conversion tests."""
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_text("Fake PDF content")
    return pdf_path


@pytest.fixture
def tmp_video(tmp_path):
    """Create a fake video file (empty placeholder)."""
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"\x00" * 1024)
    return video_path


# ------------------------------------------------------------------------------
# 2️⃣  Flask App Tests
# ------------------------------------------------------------------------------

def test_index_route(client):
    """Homepage should render successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"<html" in response.data or b"<!DOCTYPE html" in response.data


# ------------------------------------------------------------------------------
# 3️⃣  Celery Configuration Test
# ------------------------------------------------------------------------------

def test_celery_ping(client):
    """Verify Celery tasks can run synchronously without Redis."""
    @celery.task
    def ping():
        return "pong"

    result = ping.delay()
    assert result.get(timeout=5) == "pong"


# ------------------------------------------------------------------------------
# 4️⃣  Conversion Logic Tests (Mocked)
# ------------------------------------------------------------------------------

@patch("functions.subprocess.run")
def test_docx_to_pdf(mock_run, tmp_docx, tmp_path):
    """Test DOCX → PDF conversion logic with mocked subprocess."""
    output_pdf = tmp_path / "output.pdf"
    from functions import docx_to_pdf
    docx_to_pdf(str(tmp_docx), str(output_pdf))

    mock_run.assert_called_once()
    # Simulate successful PDF creation
    output_pdf.write_text("fake PDF")
    assert output_pdf.exists(), "DOCX → PDF should output a PDF file"


@patch("functions.Converter")
def test_pdf_to_docx(mock_converter, tmp_pdf, tmp_path):
    """Test PDF → DOCX conversion logic (mocked)."""
    from functions import pdf_to_docx
    output_docx = tmp_path / "output.docx"

    mock_instance = mock_converter.return_value
    pdf_to_docx(str(tmp_pdf), str(output_docx))

    mock_instance.convert.assert_called_once()
    mock_instance.close.assert_called_once()


@patch("functions.fitz.open")                 # mock PyMuPDF
@patch("functions.Document")                  # mock python-docx Document
@patch("functions.arabic_reshaper.reshape")   # mock arabic reshaper
@patch("functions.get_display")               # mock bidi text display
def test_pdf_to_docx_text(
    mock_bidi, mock_reshape, mock_doc, mock_fitz, tmp_path
):
    """Test pdf_to_docx_text() end-to-end logic with mocks only."""
    from functions import pdf_to_docx_text

    # --- Setup temporary paths ---
    pdf_path = tmp_path / "input.pdf"
    output_path = tmp_path / "output.docx"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    # --- Mock fitz.open() behavior ---
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "مرحبا\nHello"
    mock_pdf.__len__.return_value = 2         # 2 pages
    mock_pdf.__getitem__.side_effect = lambda i: mock_page
    mock_fitz.return_value = mock_pdf

    # --- Mock Document behavior ---
    mock_doc_instance = MagicMock()
    mock_doc.return_value = mock_doc_instance

    # --- Mock text reshaping & bidi ---
    mock_reshape.side_effect = lambda t: f"reshaped({t})"
    mock_bidi.side_effect = lambda t: f"bidi({t})"

    # --- Run the function ---
    pdf_to_docx_text(pdf_path, output_path)

    # --- Assertions ---
    mock_fitz.assert_called_once_with(str(pdf_path))
    assert mock_pdf.__len__.called
    assert mock_doc_instance.add_paragraph.call_count > 0
    mock_doc_instance.save.assert_called_once_with(str(output_path))
    mock_pdf.close.assert_called_once()
    mock_reshape.assert_called()
    mock_bidi.assert_called()

@patch("functions.fitz.open")  # mock PyMuPDF open
def test_pdf_to_text(mock_fitz, tmp_path):
    """Test pdf_to_text() logic using mocks for PyMuPDF and file I/O."""
    from functions import pdf_to_text

    # --- Setup ---
    pdf_path = tmp_path / "sample.pdf"
    output_path = tmp_path / "output.txt"
    pdf_path.write_bytes(b"%PDF-1.4 mock")

    # Mock PDF pages
    mock_pdf = [MagicMock(), MagicMock()]
    mock_pdf[0].get_text.return_value = "Page one content"
    mock_pdf[1].get_text.return_value = "Page two content"
    mock_fitz.return_value = mock_pdf

    # Mock file open
    with patch("builtins.open", mock_open()) as mocked_file:
        pdf_to_text(pdf_path, output_path)

    # --- Assertions ---
    mock_fitz.assert_called_once_with(pdf_path)
    # Ensure file was opened in binary write mode
    mocked_file.assert_called_once_with(str(output_path), "wb")

    handle = mocked_file()
    # Confirm write() was called for each page
    assert handle.write.call_count == len(mock_pdf)
    handle.write.assert_any_call(b"Page one content")
    handle.write.assert_any_call(b"Page two content")

@patch("functions.Converter")           # mock pdf2docx.Converter
@patch("functions.subprocess.run")      # mock OCRmyPDF subprocess
def test_ocr_pdf_to_docx(mock_run, mock_converter, tmp_pdf, tmp_path):
    """Test OCR PDF → DOCX conversion logic (fully mocked)."""
    from functions import ocr_pdf_to_docx

    output_docx = tmp_path / "output.docx"
    fake_ocr_temp = tmp_path / "ocr_temp.pdf"

    # Create fake ocr_temp.pdf so the path exists
    fake_ocr_temp.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

    # Mock Converter instance
    mock_instance = mock_converter.return_value
    mock_instance.convert.return_value = None
    mock_instance.close.return_value = None

    # Run inside temp dir so relative paths resolve correctly
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        ocr_pdf_to_docx(str(tmp_pdf), str(output_docx), lang="eng")
    finally:
        os.chdir(old_cwd)

    # --- Assertions ---
    mock_run.assert_called_once()
    mock_converter.assert_called_once_with(str(fake_ocr_temp))  # ✅ corrected
    mock_instance.convert.assert_called_once()
    mock_instance.close.assert_called_once()

# ------------------------------------------------------------------------------
# 5️⃣  Image Conversion / Compression Tests
# ------------------------------------------------------------------------------

def test_image_conversion(tmp_path):
    """Verify image format conversion."""
    from functions import convert_image
    from PIL import Image

    input_path = tmp_path / "test.png"
    img = Image.new("RGB", (50, 50), color="red")
    img.save(input_path)

    output_path = convert_image(input_path, "jpg")
    assert output_path.exists()
    assert output_path.suffix == ".jpg"


def test_image_compression(tmp_path):
    """Verify image compression creates output file."""
    from functions import compress_image
    from PIL import Image

    input_path = tmp_path / "input.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(input_path)

    output_path = tmp_path / "output.jpg"
    compress_image(str(input_path), str(output_path), "medium")
    assert output_path.exists()


# ------------------------------------------------------------------------------
# 6️⃣  Video Conversion / Compression Tests (Mocked)
# ------------------------------------------------------------------------------

@patch("functions.VideoFileClip")
def test_video_conversion_and_compression(mock_clip, tmp_video, tmp_path):
    """Mock MoviePy for video conversion & compression."""
    from functions import convert_video, compress_video

    # Mock VideoFileClip context
    mock_instance = mock_clip.return_value.__enter__.return_value
    mock_instance.write_videofile.return_value = None

    # --- Test conversion ---
    output_path = convert_video(str(tmp_video), "avi")
    assert output_path.suffix == ".avi"

    # --- Test compression ---
    out_compressed = tmp_path / "compressed.mp4"
    with patch("functions.subprocess.run") as mock_run:
        compress_video(str(tmp_video), str(out_compressed), "medium")
        mock_run.assert_called_once()
        assert out_compressed.suffix == ".mp4"
