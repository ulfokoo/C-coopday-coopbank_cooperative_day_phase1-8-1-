"""File-security helpers, used from Phase 4 (documents) onward.
Kept here now so the pattern is established early: never trust a
user-supplied filename or extension."""
import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename):
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def safe_stored_filename(original_filename):
    """Generate a random, collision-free, path-traversal-safe filename
    while preserving the (sanitized) extension only."""
    original_filename = secure_filename(original_filename)
    ext = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else ""
    token = uuid.uuid4().hex
    return f"{token}.{ext}" if ext else token


def upload_path(*parts):
    return os.path.join(current_app.config["UPLOAD_FOLDER"], *parts)
