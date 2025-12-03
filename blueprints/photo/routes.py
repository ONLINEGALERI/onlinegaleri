from flask import Blueprint

photo_bp = Blueprint("photo", __name__)

@photo_bp.route("/upload")
def upload():
    return "Upload Photo Page"

