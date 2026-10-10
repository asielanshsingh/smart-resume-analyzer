import secrets
from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_score_band(score: float):
    """Calculates score gauge label, band, and accessibility visual metadata based on numeric score."""
    val = float(score or 0)
    if val >= 85:
        return {
            "label": "Excellent Match",
            "band": "excellent",
            "color_class": "emerald",
            "badge_bg": "bg-emerald-50",
            "badge_text": "text-emerald-700",
            "badge_border": "border-emerald-200",
            "stroke_color": "#10b981"
        }
    elif val >= 70:
        return {
            "label": "Good Match",
            "band": "good",
            "color_class": "indigo",
            "badge_bg": "bg-indigo-50",
            "badge_text": "text-indigo-700",
            "badge_border": "border-indigo-200",
            "stroke_color": "#4f46e5"
        }
    elif val >= 50:
        return {
            "label": "Needs Improvement",
            "band": "fair",
            "color_class": "amber",
            "badge_bg": "bg-amber-50",
            "badge_text": "text-amber-700",
            "badge_border": "border-amber-200",
            "stroke_color": "#f59e0b"
        }
    else:
        return {
            "label": "Significant Gaps",
            "band": "poor",
            "color_class": "rose",
            "badge_bg": "bg-rose-50",
            "badge_text": "text-rose-700",
            "badge_border": "border-rose-200",
            "stroke_color": "#f43f5e"
        }

class Resume(db.Model):
    """Resume model storing uploaded file details, extracted text, and structured parsed sections."""
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    extracted_text = db.Column(db.Text, nullable=True)
    file_hash = db.Column(db.String(64), index=True, nullable=False)
    page_count = db.Column(db.Integer, default=1, nullable=False)
    word_count = db.Column(db.Integer, default=0, nullable=False)
    sections_json = db.Column(db.JSON, nullable=True)
    contacts_json = db.Column(db.JSON, nullable=True)
    warnings_json = db.Column(db.JSON, nullable=True)

    analyses = db.relationship("Analysis", backref="resume", cascade="all, delete-orphan", lazy=True)

    def to_dict(self, include_text: bool = False):
        data = {
            "resume_id": self.id,
            "filename": self.filename,
            "upload_time": self.upload_time.isoformat(),
            "file_hash": self.file_hash,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "detected_sections": self.sections_json or {},
            "contacts": self.contacts_json or {
                "emails": [],
                "phones": [],
                "linkedin": [],
                "github": []
            },
            "warnings": self.warnings_json or []
        }
        if include_text:
            data["raw_text"] = self.extracted_text
        return data


class Analysis(db.Model):
    """Analysis model storing scoring output, ATS compatibility, breakdown and suggestions."""
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    share_token = db.Column(db.String(64), unique=True, index=True, nullable=False, default=lambda: secrets.token_urlsafe(16))
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    resume_score = db.Column(db.Float, nullable=False)
    ats_score = db.Column(db.Float, nullable=False)
    breakdown_json = db.Column(db.JSON, nullable=False)
    matched_missing_json = db.Column(db.JSON, nullable=False)
    suggestions_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    def to_dict(self, include_sensitive: bool = True):
        res_score_band = get_score_band(self.resume_score)
        ats_score_band = get_score_band(self.ats_score)

        data = {
            "id": self.id,
            "share_token": self.share_token,
            "resume_id": self.resume_id,
            "filename": self.resume.filename if self.resume else "",
            "role": self.role,
            "resume_score": self.resume_score,
            "resume_score_band": res_score_band,
            "ats_score": self.ats_score,
            "ats_score_band": ats_score_band,
            "ats_details": self.matched_missing_json.get("ats_details", {}) if isinstance(self.matched_missing_json, dict) else {},
            "breakdown": self.breakdown_json,
            "matched_missing": self.matched_missing_json,

            "suggestions": self.suggestions_json,
            "detected_sections": self.resume.sections_json if self.resume else {},
            "page_count": self.resume.page_count if self.resume else 1,
            "word_count": self.resume.word_count if self.resume else 0,
            "created_at": self.created_at.isoformat()
        }
        if include_sensitive:
            data["contacts"] = self.resume.contacts_json if self.resume else {}
        return data

