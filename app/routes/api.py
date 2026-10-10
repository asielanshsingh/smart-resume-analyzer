import json

from flask import current_app, jsonify, request

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
        with open(roles_path, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception:
        current_app.logger.exception("Failed to read roles file")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Failed to load job roles configuration."
            }
        }), 500

@api_bp.route("/api/upload", methods=["POST"])
def upload_resume():
    """Endpoint to validate, parse, and store uploaded resume (PDF or DOCX)."""
    from pathlib import Path
    from uuid import uuid4

    from werkzeug.utils import secure_filename

    from app.models import Resume, db
    from app.services.parser import (
        ResumeParsingError,
        compute_file_hash,
        parse_resume_bytes,
    )

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
        current_app.logger.exception("Error parsing resume upload")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred while processing the resume: {e!s}"
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
    from app.models import Resume, db
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
    from app.models import Resume, db
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


@api_bp.route("/api/ats", methods=["POST"])
def evaluate_ats():
    """Evaluates ATS keyword matching and compatibility score for a resume against a target role or job description."""
    from app.models import Resume, db
    from app.services.ats import analyze_ats_compatibility

    if not request.is_json:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Request body must be valid JSON."
            }
        }), 400

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Malformed or non-JSON body."
            }
        }), 400

    resume_id = payload.get("resume_id")
    role_id = payload.get("role_id")
    job_description = payload.get("job_description")

    if not resume_id:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Missing 'resume_id' parameter in request body."
            }
        }), 400

    if role_id and job_description:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Please specify either 'role_id' or 'job_description', not both."
            }
        }), 400

    if not role_id and not job_description:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Please provide either 'role_id' or 'job_description'."
            }
        }), 400

    # Retrieve Resume from Database
    resume = db.session.get(Resume, resume_id)
    if not resume:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": f"Resume with ID {resume_id} not found."
            }
        }), 404

    # Validate resume text content
    if not resume.extracted_text or len(resume.extracted_text.strip()) < 10:
        return jsonify({
            "error": {
                "code": "UNPROCESSABLE_ENTITY",
                "message": "Resume text is empty or too short to analyze for ATS compatibility."
            }
        }), 400

    selected_role = None
    if role_id:
        roles_path = current_app.config["ROLES_FILE"]
        try:
            with open(roles_path, encoding="utf-8") as f:
                roles_data = json.load(f)
            roles_list = roles_data.get("roles", [])
            valid_roles = [r["id"] for r in roles_list]

            for role in roles_list:
                if role["id"] == role_id:
                    selected_role = role
                    break

            if not selected_role:
                return jsonify({
                    "error": {
                        "code": "INVALID_ROLE",
                        "message": f"Unknown role_id '{role_id}'. Valid roles are: {', '.join(valid_roles)}."
                    }
                }), 400
        except Exception as e:
            current_app.logger.error(f"Failed to read roles file: {e}")
            return jsonify({
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to load job roles configuration."
                }
            }), 500

    if job_description is not None:
        max_jd_len = current_app.config.get("MAX_JD_LENGTH", 10000)
        if len(job_description) > max_jd_len:
            return jsonify({
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": f"Job description exceeds maximum allowed length of {max_jd_len} characters."
                }
            }), 400
        if not job_description.strip():
            return jsonify({
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Provided job description is empty."
                }
            }), 400

    parsed_resume = resume.to_dict(include_text=True)

    result = analyze_ats_compatibility(
        parsed_resume=parsed_resume,
        role_config=selected_role,
        job_description=job_description,
        skills_file_path=current_app.config["SKILLS_FILE"],
        ats_config_file=current_app.config["ATS_CONFIG_FILE"]
    )

    if isinstance(result, dict) and result.get("error") == "NO_RECOGNIZABLE_SKILLS":
        return jsonify({
            "error": {
                "code": "UNRECOGNIZED_JD_SKILLS",
                "message": result.get("message", "Could not extract recognizable skills from job description.")
            }
        }), 422

    return jsonify({
        "resume_id": resume.id,
        "filename": resume.filename,
        "ats_evaluation": result
    }), 200

# ---------------------------------------------------------------------------
# Analyze endpoint – unified scoring + ATS + feedback pipeline
# ---------------------------------------------------------------------------

@api_bp.route("/api/analyze", methods=["POST"])
def analyze_resume():
    """
    POST /api/analyze

    Runs the full analysis pipeline (scoring, ATS, feedback) for an uploaded
    resume against a target role or custom job description.  Persists the
    result to the Analysis table and returns it.

    Request body (JSON):
        resume_id   (int, required)
        role_id     (str, optional) – mutually exclusive with job_description
        job_description (str, optional) – mutually exclusive with role_id
    """
    from app.models import Analysis, Resume, db
    from app.services.ats import analyze_ats_compatibility
    from app.services.feedback import generate_suggestions
    from app.services.scoring import analyze_resume_score

    # --- JSON body validation ---
    if not request.is_json:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Request body must be valid JSON."
            }
        }), 400

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Malformed or non-JSON body."
            }
        }), 400

    resume_id = payload.get("resume_id")
    role_id = payload.get("role_id")
    job_description = payload.get("job_description")

    if not resume_id:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Missing 'resume_id' parameter in request body."
            }
        }), 400

    if role_id and job_description:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Please specify either 'role_id' or 'job_description', not both."
            }
        }), 400

    if not role_id and not job_description:
        return jsonify({
            "error": {
                "code": "BAD_REQUEST",
                "message": "Please provide either 'role_id' or 'job_description'."
            }
        }), 400

    # --- Resume existence check ---
    resume = db.session.get(Resume, resume_id)
    if not resume:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": f"Resume with ID {resume_id} not found."
            }
        }), 404

    if not resume.extracted_text or len(resume.extracted_text.strip()) < 10:
        return jsonify({
            "error": {
                "code": "UNPROCESSABLE_ENTITY",
                "message": "Resume text is empty or too short to analyze."
            }
        }), 422

    # --- Role / job description validation ---
    selected_role = None
    role_label = "custom_job_description"

    if role_id:
        roles_path = current_app.config["ROLES_FILE"]
        try:
            with open(roles_path, encoding="utf-8") as f:
                roles_data = json.load(f)
            roles_list = roles_data.get("roles", [])
            valid_role_ids = [r["id"] for r in roles_list]

            for role in roles_list:
                if role["id"] == role_id:
                    selected_role = role
                    break

            if not selected_role:
                return jsonify({
                    "error": {
                        "code": "INVALID_ROLE",
                        "message": (
                            f"Unknown role_id '{role_id}'. "
                            f"Valid roles are: {', '.join(valid_role_ids)}."
                        )
                    }
                }), 400
        except Exception as e:
            current_app.logger.error(f"Failed to read roles file: {e}")
            return jsonify({
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Failed to load job roles configuration."
                }
            }), 500

        role_label = role_id

    if job_description is not None:
        max_jd_len = current_app.config.get("MAX_JD_LENGTH", 10000)
        if not job_description.strip():
            return jsonify({
                "error": {
                    "code": "BAD_REQUEST",
                    "message": "Provided job description is empty."
                }
            }), 400
        if len(job_description) > max_jd_len:
            return jsonify({
                "error": {
                    "code": "PAYLOAD_TOO_LARGE",
                    "message": (
                        f"Job description exceeds maximum allowed length "
                        f"of {max_jd_len} characters."
                    )
                }
            }), 400

    # --- Run analysis pipeline ---
    parsed_data = resume.to_dict(include_text=True)

    try:
        scoring_result = analyze_resume_score(
            parsed_data,
            current_app.config["SCORING_CONFIG_FILE"]
        )

        ats_result = analyze_ats_compatibility(
            parsed_resume=parsed_data,
            role_config=selected_role,
            job_description=job_description,
            skills_file_path=current_app.config["SKILLS_FILE"],
            ats_config_file=current_app.config["ATS_CONFIG_FILE"]
        )

        if isinstance(ats_result, dict) and ats_result.get("error") == "NO_RECOGNIZABLE_SKILLS":
            return jsonify({
                "error": {
                    "code": "UNRECOGNIZED_JD_SKILLS",
                    "message": ats_result.get(
                        "message",
                        "Could not extract recognizable skills from job description."
                    )
                }
            }), 422

        # Enrich ats_result with contacts + detected_sections so the feedback
        # engine can evaluate contact/section conditions without touching raw text.
        ats_result["contacts"] = parsed_data.get("contacts", {})
        ats_result["detected_sections"] = parsed_data.get("detected_sections", {})

        suggestions = generate_suggestions(
            scoring_result=scoring_result,
            ats_result=ats_result,
            suggestions_file=current_app.config["SUGGESTIONS_FILE"]
        )

    except Exception:
        current_app.logger.exception("Analysis pipeline error")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred during analysis."
            }
        }), 500

    # --- Persist to Analysis table ---
    ats_details = {
        "target_title": ats_result.get("target_title", ""),
        "ats_score": ats_result.get("ats_score", 0),
        "category_scores": ats_result.get("category_scores", {}),
        "deductions": ats_result.get("deductions", []),
    }

    matched_missing = {
        "matched_skills": ats_result.get("matched_skills", []),
        "missing_critical_skills": ats_result.get("missing_critical_skills", []),
        "missing_nice_to_have_skills": ats_result.get("missing_nice_to_have_skills", []),
        "keyword_match_percentage": ats_result.get("keyword_match_percentage", 0.0),
        "matched_skills_count": ats_result.get("matched_skills_count", 0),
        "total_role_skills_count": ats_result.get("total_role_skills_count", 0),
        "ats_details": ats_details,
    }


    try:
        analysis = Analysis(
            resume_id=resume.id,
            role=role_label,
            resume_score=float(scoring_result.get("resume_score", 0)),
            ats_score=float(ats_result.get("ats_score", 0)),
            breakdown_json=scoring_result.get("breakdown", {}),
            matched_missing_json=matched_missing,
            suggestions_json=suggestions,
        )
        db.session.add(analysis)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to persist analysis")
        return jsonify({
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "Analysis completed but could not be saved to the database."
            }
        }), 500

    res_dict = analysis.to_dict(include_sensitive=True)
    res_dict["analysis_id"] = analysis.id
    res_dict["ats_details"] = ats_details
    res_dict["matched_skills"] = ats_result.get("matched_skills", [])
    res_dict["missing_critical_skills"] = ats_result.get("missing_critical_skills", [])
    res_dict["missing_nice_to_have_skills"] = ats_result.get("missing_nice_to_have_skills", [])
    res_dict["keyword_match_percentage"] = ats_result.get("keyword_match_percentage", 0.0)
    return jsonify(res_dict), 201



# ---------------------------------------------------------------------------
# Analysis fetch and history endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/api/analysis/<identifier>", methods=["GET"])
def get_analysis(identifier: str):
    """
    GET /api/analysis/<identifier>

    Returns a previously persisted analysis by its primary-key ID or share_token.
    Returns 404 if the identifier is unknown.
    """
    from app.models import Analysis, db

    analysis = None
    if identifier.isdigit():
        analysis = db.session.get(Analysis, int(identifier))

    if not analysis:
        analysis = Analysis.query.filter_by(share_token=identifier).first()

    if not analysis:
        return jsonify({
            "error": {
                "code": "NOT_FOUND",
                "message": f"Analysis with identifier '{identifier}' not found."
            }
        }), 404

    return jsonify(analysis.to_dict(include_sensitive=True)), 200


@api_bp.route("/api/history", methods=["GET"])
def get_analysis_history():
    """
    GET /api/history

    Returns a paginated list of recent analyses, newest first.
    Note: Omits sensitive contact details from history items.

    Query parameters:
        page     (int, default 1)
        per_page (int, default 10, max 50)
    """
    from app.models import Analysis, db

    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = min(50, max(1, int(request.args.get("per_page", 10))))
    except (ValueError, TypeError):
        per_page = 10

    pagination = (
        db.session.query(Analysis)
        .order_by(Analysis.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return jsonify({
        "items": [a.to_dict(include_sensitive=False) for a in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200

