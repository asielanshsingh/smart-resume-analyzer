from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Resume(db.Model):
    """Resume model storing uploaded file details, extracted text, and structured parsed sections."""
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_time = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
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
    resume_id = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    resume_score = db.Column(db.Float, nullable=False)
    ats_score = db.Column(db.Float, nullable=False)
    breakdown_json = db.Column(db.JSON, nullable=False)
    matched_missing_json = db.Column(db.JSON, nullable=False)
    suggestions_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "role": self.role,
            "resume_score": self.resume_score,
            "ats_score": self.ats_score,
            "breakdown": self.breakdown_json,
            "matched_missing": self.matched_missing_json,
            "suggestions": self.suggestions_json,
            "created_at": self.created_at.isoformat()
        }
