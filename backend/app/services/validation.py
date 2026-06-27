import os
import filetype
from typing import Union, BinaryIO

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Supported MIME types and extensions
ALLOWED_MIME_TYPES = {
    # PDF
    "application/pdf",
    # Office Word (DOCX)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Office PowerPoint (PPTX)
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Office Excel (XLSX)
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # Images
    "image/png",
    "image/jpeg"
}

ALLOWED_EXTENSIONS = {"pdf", "docx", "pptx", "xlsx", "png", "jpg", "jpeg"}

class ValidationError(Exception):
    """Structured Exception for file validation errors."""
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.message = message
        self.code = code


def validate_file_size(file_size: int) -> None:
    """
    Enforce max file size boundaries (50MB) and throw structured exception on violation.
    """
    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            message=f"File size exceeds the maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB. Actual size: {file_size} bytes.",
            code="FILE_TOO_LARGE"
        )


def validate_file_type(file_content: Union[bytes, str]) -> str:
    """
    Verify magic numbers using the filetype library.
    Checks the beginning of the file content (bytes) or resolves from file path.
    Returns the resolved extension.
    Raises ValidationError if the type is invalid.
    """
    if isinstance(file_content, str):
        # It's a file path
        if not os.path.exists(file_content):
            raise ValidationError(
                message=f"File not found at path: {file_content}",
                code="FILE_NOT_FOUND"
            )
        try:
            kind = filetype.guess(file_content)
        except Exception as e:
            raise ValidationError(
                message=f"Error reading file content: {str(e)}",
                code="READ_ERROR"
            )
    elif isinstance(file_content, bytes):
        # It's raw bytes
        kind = filetype.guess(file_content)
    else:
        raise ValidationError(
            message="Invalid file content type. Must be file path (str) or raw bytes.",
            code="INVALID_INPUT_TYPE"
        )

    if not kind:
        raise ValidationError(
            message="Unable to determine the file type. The file might be corrupted or of an unsupported format.",
            code="UNSUPPORTED_FILE_TYPE"
        )

    mime = kind.mime
    ext = kind.extension.lower()

    if mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            message=f"Unsupported file format: {mime} ({ext}). Allowed formats: PDF, DOCX, PPTX, XLSX, PNG, JPG/JPEG.",
            code="INVALID_FILE_TYPE"
        )

    return ext
