import pytest
from backend.app.services.validation import validate_file_size, validate_file_type, ValidationError, MAX_FILE_SIZE

def test_validate_file_size_ok():
    # 10MB is fine
    validate_file_size(10 * 1024 * 1024)

def test_validate_file_size_too_large():
    with pytest.raises(ValidationError) as excinfo:
        validate_file_size(MAX_FILE_SIZE + 1)
    assert excinfo.value.code == "FILE_TOO_LARGE"

def test_validate_file_type_pdf():
    # PDF magic number: %PDF-
    pdf_bytes = b"%PDF-1.4\nother content..."
    ext = validate_file_type(pdf_bytes)
    assert ext == "pdf"

def test_validate_file_type_png():
    # PNG magic number: \x89PNG\r\n\x1a\n
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    ext = validate_file_type(png_bytes)
    assert ext == "png"

def test_validate_file_type_jpg():
    # JPG/JPEG magic number: \xff\xd8\xff
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    ext = validate_file_type(jpg_bytes)
    assert ext == "jpg" or ext == "jpeg"

def test_validate_file_type_invalid():
    # Random text bytes
    invalid_bytes = b"Hello, this is just some text, not a PDF or image."
    with pytest.raises(ValidationError) as excinfo:
        validate_file_type(invalid_bytes)
    assert excinfo.value.code in ["UNSUPPORTED_FILE_TYPE", "INVALID_FILE_TYPE"]
