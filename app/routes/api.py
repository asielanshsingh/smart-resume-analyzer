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

@api_bp.route("/api/placeholder-analysis", methods=["GET"])
def get_placeholder_analysis():
    """Returns mock placeholder analysis data for frontend dashboard layout preview."""
    return jsonify({
        "role": "Software Engineer",
        "resume_score": 82.5,
        "ats_score": 78.0,
        "breakdown": {
            "required_skills_score": 85,
            "preferred_skills_score": 70,
            "section_presence_score": 90,
            "formatting_length_score": 80
        },
        "matched_missing": {
            "matched_skills": ["Python", "JavaScript", "SQL", "Git", "REST API", "Flask", "Pytest"],
            "missing_skills": ["Docker", "Data Structures", "Algorithms", "AWS", "CI/CD"]
        },
        "suggestions": [
            {
                "id": "missing_required_skills",
                "category": "Skills",
                "severity": "High",
                "title": "Add Missing Core Skills",
                "description": "Highlight experience with Data Structures and Algorithms to improve core requirement score."
            },
            {
                "id": "quantifiable_impact",
                "category": "Content",
                "severity": "Medium",
                "title": "Quantify Achievements",
                "description": "Include numeric metrics (e.g. 'Reduced latency by 25%') in project bullet points."
            },
            {
                "id": "resume_too_short",
                "category": "Length",
                "severity": "Low",
                "title": "Expand Cloud & DevOps Details",
                "description": "Elaborate on deployment experience with Docker or AWS if applicable."
            }
        ]
    }), 200
