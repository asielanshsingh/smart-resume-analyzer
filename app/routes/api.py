import json
from flask import jsonify, current_app, request
from app.routes import api_bp

@api_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "smart-resume-analyzer",
        "version": "1.0.0"
    }), 200

@api_bp.route("/api/roles", methods=["GET"])
def get_roles():
    """Returns list of supported target job roles loaded from data/roles.json."""
    roles_path = current_app.config["ROLES_FILE"]
    try:
        with open(roles_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Failed to read roles file: {e}")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to load job roles configuration."
            }
        }), 500

@api_bp.route("/api/upload", methods=["POST"])
def upload_resume():
    """Endpoint to validate, parse, and store uploaded resume (PDF or DOCX)."""
    from uuid import uuid4
    from pathlib import Path
    from werkzeug.utils import secure_filename
    from app.models import db, Resume
    from app.services.parser import parse_resume_bytes, compute_file_hash, ResumeParsingError

    # 1. Check file part in request
    if not request.files or ("file" not in request.files and "resume" not in request.files):
        return jsonify({
            "error": {
                "code": "NO_FILE_PROVIDED",
                "message": "No file part in the request. Please attach a file."
            }
        }), 400

    uploaded_file = request.files.get("file") or request.files.get("resume")
    if not uploaded_file or not uploaded_file.filename or uploaded_file.filename.strip() == "":
        return jsonify({
            "error": {
                "code": "NO_FILE_SELECTED",
                "message": "No file selected for upload."
            }
        }), 400

    raw_filename = uploaded_file.filename
    safe_name = secure_filename(raw_filename) or "uploaded_resume.pdf"
    raw_bytes = uploaded_file.read()

    # 2. Compute SHA-256 hash for deduplication
    file_hash = compute_file_hash(raw_bytes)

    # Check existing resume record in DB (deduplication)
    existing_resume = Resume.query.filter_by(file_hash=file_hash).first()
    if existing_resume:
        current_app.logger.info(f"Reusing existing resume record id={existing_resume.id} for hash={file_hash}")
        return jsonify(existing_resume.to_dict(include_text=True)), 200

    # 3. Store temporary file safely for parsing and delete immediately afterwards
    upload_dir = Path(current_app.config["UPLOAD_FOLDER"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = upload_dir / f"temp_{uuid4().hex}_{safe_name}"

    try:
        with open(temp_file_path, "wb") as f:
            f.write(raw_bytes)

        # 4. Parse resume bytes
        parsed_data = parse_resume_bytes(
            file_bytes=raw_bytes,
            filename=safe_name,
            sections_config_file=current_app.config["SECTIONS_CONFIG_FILE"],
            max_upload_mb=current_app.config["MAX_UPLOAD_MB"],
            min_word_count=current_app.config["MIN_WORD_COUNT"]
        )

        # 5. Save Resume to Database
        resume = Resume(
            filename=safe_name,
            extracted_text=parsed_data["raw_text"],
            file_hash=file_hash,
            page_count=parsed_data["page_count"],
            word_count=parsed_data["word_count"],
            sections_json=parsed_data["detected_sections"],
            contacts_json=parsed_data["contacts"],
            warnings_json=parsed_data["warnings"]
        )
        db.session.add(resume)
        db.session.commit()

        return jsonify(resume.to_dict(include_text=True)), 201

    except ResumeParsingError as e:
        db.session.rollback()
        return jsonify({
            "error": {
                "code": e.code,
                "message": e.message
            }
        }), e.status_code
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error parsing resume upload: {e}", exc_info=True)
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred while processing the resume: {str(e)}"
            }
        }), 500
    finally:
        # Delete temporary upload file
        if temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except Exception as e:
                current_app.logger.warning(f"Could not delete temp file {temp_file_path}: {e}")


@api_bp.route("/api/resumes/<int:resume_id>", methods=["GET"])
def get_resume(resume_id: int):
    """Retrieves parsed resume details by ID."""
    from app.models import db, Resume
    resume = db.session.get(Resume, resume_id)
    if not resume:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": f"Resume with ID {resume_id} not found."
            }
        }), 404
    return jsonify(resume.to_dict(include_text=True)), 200


@api_bp.route("/api/score", methods=["POST"])
def score_resume():
    """Calculates deterministic resume score (out of 100) and category breakdown."""
    from app.models import db, Resume
    from app.services.scoring import analyze_resume_score

    payload = request.get_json(silent=True) or {}
    resume_id = payload.get("resume_id")

    if not resume_id:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Missing 'resume_id' parameter in request body."
            }
        }), 400

    resume = db.session.get(Resume, resume_id)
    if not resume:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": f"Resume with ID {resume_id} not found."
            }
        }), 404


    parsed_data = resume.to_dict(include_text=True)
    scoring_result = analyze_resume_score(parsed_data, current_app.config["SCORING_CONFIG_FILE"])

    return jsonify({
        "resume_id": resume.id,
        "filename": resume.filename,
        "score_result": scoring_result
    }), 200


