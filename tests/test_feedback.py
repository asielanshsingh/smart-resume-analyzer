"""
test_feedback.py – Unit tests for the feedback engine (app/services/feedback.py).

Tests cover:
  - Each catalog rule fires under its specific trigger condition.
  - positive_strong_profile fires and is appended last.
  - De-duplication: a duplicate rule id appears only once.
  - Priority ordering: high before medium before low.
  - Cap: more than max_suggestions triggers → capped list (positive excluded from cap).
  - No suggestions when no conditions are triggered (empty actionable list).
"""

import json
import pytest
from pathlib import Path
from app.services.feedback import generate_suggestions, _evaluate_condition, load_suggestions_catalog


# ---------------------------------------------------------------------------
# Helpers – minimal result stubs
# ---------------------------------------------------------------------------

def _scoring(
    *,
    resume_score: int = 80,
    experience_score: int = 8,
    projects_score: int = 12,
    skills_score: int = 18,
    contact_score: int = 8,
    completeness_score: int = 8,
    structure_score: int = 18,
    education_score: int = 12,
    word_count: int = 400,
    action_verbs: int = 5,
    pronoun_count: int = 0,
    bullet_count: int = 5,
    has_quantified: bool = True,
    has_experience_section: bool = True,
) -> dict:
    """Build a minimal scoring_result stub that the feedback engine can consume."""

    exp_reasons = []
    if has_experience_section:
        if has_quantified:
            exp_reasons.append("Quantified achievements detected (3 metrics): +4/4")
        else:
            exp_reasons.append("Work experience listed without quantified metrics: +2/4")
    else:
        exp_reasons.append("No work experience, projects, or certifications detected: +0/10")

    # Build completeness reasons
    comp_reasons = []
    if word_count < 150:
        comp_reasons.append(f"Resume text is too brief ({word_count} words): +1/6")
    elif word_count > 1500:
        comp_reasons.append(f"Resume text is excessively long ({word_count} words): +2/6")
    else:
        comp_reasons.append(f"Optimal resume word count ({word_count} words): +6/6")

    if bullet_count >= 3:
        comp_reasons.append("Good bullet point structure used: +2/2")
    elif bullet_count > 0:
        comp_reasons.append("Standard text formatting: +1/2")

    if action_verbs >= 3 and pronoun_count <= 3:
        comp_reasons.append(f"Strong action-oriented language without excessive first-person pronouns: +2/2")
    elif pronoun_count > 5:
        comp_reasons.append(f"High first-person pronoun frequency detected ({pronoun_count} uses): +0/2")
    else:
        comp_reasons.append("Satisfactory action verb usage: +1/2")

    return {
        "resume_score": resume_score,
        "raw_score": float(resume_score),
        "breakdown": {
            "structure": {"score": structure_score, "max_score": 20, "reasons": []},
            "skills": {"score": skills_score, "max_score": 20, "reasons": []},
            "education": {"score": education_score, "max_score": 15, "reasons": []},
            "projects": {"score": projects_score, "max_score": 15, "reasons": []},
            "experience": {"score": experience_score, "max_score": 10, "reasons": exp_reasons},
            "contact": {"score": contact_score, "max_score": 10, "reasons": []},
            "completeness": {"score": completeness_score, "max_score": 10, "reasons": comp_reasons},
        }
    }


def _ats(
    *,
    ats_score: int = 75,
    missing_critical: list | None = None,
    missing_nice: list | None = None,
    deductions: list | None = None,
    contacts: dict | None = None,
    detected_sections: dict | None = None,
) -> dict:
    """Build a minimal ats_result stub."""
    default_sections = {
        "experience": "Software engineer intern at Acme Corp 2023.",
        "education": "B.Tech in CS 2024.",
        "skills": "Python, SQL, Git, Docker.",
        "projects": "Resume Analyzer project.",
        "summary": "Results-driven engineer.",
        "certifications": "AWS Cloud Practitioner 2024.",
    }
    return {
        "ats_score": ats_score,
        "missing_critical_skills": missing_critical if missing_critical is not None else [],
        "missing_nice_to_have_skills": missing_nice if missing_nice is not None else [],
        "deductions": deductions if deductions is not None else [],
        "contacts": contacts if contacts is not None else {
            "emails": ["test@example.com"],
            "phones": ["+1-555-0100"],
            "linkedin": ["linkedin.com/in/test"],
            "github": ["github.com/test"],
        },
        "detected_sections": detected_sections if detected_sections is not None else default_sections,
        "matched_skills": [],
        "keyword_match_percentage": 70.0,
        "matched_skills_count": 5,
        "total_role_skills_count": 7,
        "target_title": "Test Role",
        "category_scores": {},
    }


@pytest.fixture
def suggestions_file(tmp_path):
    """Copy the real suggestions.json into a tmp dir for each test."""
    real_path = Path(__file__).resolve().parent.parent / "data" / "suggestions.json"
    dest = tmp_path / "suggestions.json"
    dest.write_text(real_path.read_text(encoding="utf-8"), encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Individual rule trigger tests
# ---------------------------------------------------------------------------

class TestRuleTriggers:
    """Each test verifies exactly one rule fires under its specific condition."""

    def test_add_missing_critical_skills(self, suggestions_file):
        sr = _scoring()
        ar = _ats(missing_critical=["sql", "docker"])
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_missing_critical_skills" in ids

    def test_add_missing_critical_skills_not_when_empty(self, suggestions_file):
        sr = _scoring()
        ar = _ats(missing_critical=[])
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_missing_critical_skills" not in ids

    def test_add_nice_to_have_skills(self, suggestions_file):
        sr = _scoring()
        ar = _ats(missing_nice=["react", "docker"])
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_nice_to_have_skills" in ids

    def test_add_technical_projects_triggers_when_no_projects(self, suggestions_file):
        sr = _scoring(projects_score=0)
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "projects"}
        ar = _ats(detected_sections=sections)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_technical_projects" in ids

    def test_add_technical_projects_not_when_present(self, suggestions_file):
        sr = _scoring(projects_score=12)
        ar = _ats()  # default sections include projects
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_technical_projects" not in ids

    def test_add_certifications_triggers(self, suggestions_file):
        """Fires when certifications section missing AND resume_score < 70."""
        sr = _scoring(resume_score=60)
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "certifications"}
        ar = _ats(ats_score=60, detected_sections=sections)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_certifications" in ids

    def test_add_certifications_not_when_score_high(self, suggestions_file):
        """Does not fire when resume_score >= 70, even if section absent."""
        sr = _scoring(resume_score=80)
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "certifications"}
        ar = _ats(detected_sections=sections)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_certifications" not in ids

    def test_add_internship_experience(self, suggestions_file):
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "experience"}
        ar = _ats(detected_sections=sections)
        sr = _scoring(experience_score=0, has_experience_section=False)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_internship_experience" in ids

    def test_quantify_achievements_triggers(self, suggestions_file):
        """Fires when experience present but no quantified metrics."""
        sr = _scoring(has_experience_section=True, has_quantified=False)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "quantify_achievements" in ids

    def test_quantify_achievements_not_when_metrics_present(self, suggestions_file):
        sr = _scoring(has_experience_section=True, has_quantified=True)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "quantify_achievements" not in ids

    def test_missing_github(self, suggestions_file):
        contacts = {"emails": ["a@b.com"], "phones": ["+1"], "linkedin": ["li"], "github": []}
        ar = _ats(contacts=contacts)
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_github_link" in ids

    def test_missing_linkedin(self, suggestions_file):
        contacts = {"emails": ["a@b.com"], "phones": ["+1"], "linkedin": [], "github": ["gh"]}
        ar = _ats(contacts=contacts)
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_linkedin_link" in ids

    def test_missing_email(self, suggestions_file):
        contacts = {"emails": [], "phones": ["+1"], "linkedin": ["li"], "github": ["gh"]}
        ar = _ats(contacts=contacts)
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "missing_email" in ids

    def test_missing_phone(self, suggestions_file):
        contacts = {"emails": ["a@b.com"], "phones": [], "linkedin": ["li"], "github": ["gh"]}
        ar = _ats(contacts=contacts)
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "missing_phone" in ids

    def test_resume_too_short(self, suggestions_file):
        sr = _scoring(word_count=80, completeness_score=2)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "resume_too_short" in ids

    def test_resume_too_long(self, suggestions_file):
        sr = _scoring(word_count=2000, completeness_score=2)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "resume_too_long" in ids

    def test_use_action_verbs(self, suggestions_file):
        """Fires when action verb count < 3 (completeness reasons show no 'Strong action')."""
        sr = _scoring(action_verbs=1, pronoun_count=0)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "use_action_verbs" in ids

    def test_avoid_first_person(self, suggestions_file):
        sr = _scoring(pronoun_count=8, action_verbs=5)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "avoid_first_person" in ids

    def test_add_bullet_formatting(self, suggestions_file):
        sr = _scoring(bullet_count=0)
        ar = _ats()
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_bullet_formatting" in ids

    def test_add_summary_section(self, suggestions_file):
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "summary"}
        ar = _ats(detected_sections=sections)
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_summary_section" in ids

    def test_add_skills_section(self, suggestions_file):
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "skills"}
        ar = _ats(detected_sections=sections)
        sr = _scoring(skills_score=0)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_skills_section" in ids

    def test_add_education_section(self, suggestions_file):
        sections = {k: v for k, v in _ats()["detected_sections"].items() if k != "education"}
        ar = _ats(detected_sections=sections)
        sr = _scoring(education_score=0)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "add_education_section" in ids

    def test_non_standard_headings(self, suggestions_file):
        ar = _ats(deductions=["Missing essential section(s): education (-5.0 points)."])
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "non_standard_headings" in ids

    def test_non_standard_headings_not_without_deduction(self, suggestions_file):
        ar = _ats(deductions=["Some other deduction"])
        results = generate_suggestions(_scoring(), ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "non_standard_headings" not in ids


# ---------------------------------------------------------------------------
# Positive rule
# ---------------------------------------------------------------------------

class TestPositiveRule:
    def test_positive_fires_when_both_scores_high(self, suggestions_file):
        sr = _scoring(resume_score=80)
        ar = _ats(ats_score=75)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "positive_strong_profile" in ids

    def test_positive_is_last(self, suggestions_file):
        sr = _scoring(resume_score=80)
        ar = _ats(ats_score=75)
        results = generate_suggestions(sr, ar, suggestions_file)
        assert results[-1]["id"] == "positive_strong_profile"

    def test_positive_does_not_fire_when_resume_score_low(self, suggestions_file):
        sr = _scoring(resume_score=60)
        ar = _ats(ats_score=75)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "positive_strong_profile" not in ids

    def test_positive_does_not_fire_when_ats_score_low(self, suggestions_file):
        sr = _scoring(resume_score=80)
        ar = _ats(ats_score=65)
        results = generate_suggestions(sr, ar, suggestions_file)
        ids = [r["id"] for r in results]
        assert "positive_strong_profile" not in ids


# ---------------------------------------------------------------------------
# De-duplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_rule_ids_appear_once(self, tmp_path):
        """If the catalog has two entries with the same id, only one survives."""
        catalog = {
            "suggestions_config": {"max_suggestions": 20, "priority_weights": {"high": 3, "medium": 2, "low": 1}},
            "suggestions_catalog": [
                {
                    "id": "missing_email",
                    "category": "Contact",
                    "priority": "high",
                    "condition": {"type": "no_contact_field", "field": "emails"},
                    "message": "First copy",
                    "how_to_fix": "Fix it",
                    "example": "example@email.com"
                },
                {
                    "id": "missing_email",
                    "category": "Contact",
                    "priority": "high",
                    "condition": {"type": "no_contact_field", "field": "emails"},
                    "message": "Second copy (duplicate)",
                    "how_to_fix": "Fix it again",
                    "example": "example@email.com"
                }
            ]
        }
        f = tmp_path / "suggestions.json"
        f.write_text(json.dumps(catalog), encoding="utf-8")

        contacts = {"emails": [], "phones": ["+1"], "linkedin": [], "github": []}
        ar = _ats(contacts=contacts)
        results = generate_suggestions(_scoring(), ar, f)
        email_matches = [r for r in results if r["id"] == "missing_email"]
        assert len(email_matches) == 1


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

class TestPriorityOrdering:
    def test_high_before_medium_before_low(self, suggestions_file):
        """High priority suggestions must all appear before medium, and medium before low."""
        sr = _scoring(
            resume_score=50,
            action_verbs=1,   # use_action_verbs (medium)
            word_count=2000,  # resume_too_long (low)
        )
        contacts = {"emails": [], "phones": [], "linkedin": [], "github": []}
        ar = _ats(
            ats_score=50,
            missing_critical=["sql"],  # add_missing_critical_skills (high)
            contacts=contacts,
        )
        results = generate_suggestions(sr, ar, suggestions_file)
        # Strip the positive note if present (it is always last regardless)
        actionable = [r for r in results if r["id"] != "positive_strong_profile"]

        priority_order = {"high": 0, "medium": 1, "low": 2}
        priorities = [priority_order[r["priority"]] for r in actionable]
        assert priorities == sorted(priorities), (
            f"Expected sorted priority order, got: {[r['priority'] for r in actionable]}"
        )


# ---------------------------------------------------------------------------
# Cap behaviour
# ---------------------------------------------------------------------------

class TestCap:
    def test_cap_at_max_suggestions(self, tmp_path):
        """More than max_suggestions triggers → exactly max_suggestions returned (+ positive if fired)."""
        # Build a catalog with 20 high-priority rules that all fire via word_count_below
        rules = [
            {
                "id": f"rule_{i}",
                "category": "Test",
                "priority": "high",
                "condition": {"type": "word_count_below", "threshold": 9999},
                "message": f"Rule {i}",
                "how_to_fix": "fix",
                "example": "ex"
            }
            for i in range(20)
        ]
        catalog = {
            "suggestions_config": {"max_suggestions": 5, "priority_weights": {"high": 3, "medium": 2, "low": 1}},
            "suggestions_catalog": rules
        }
        f = tmp_path / "suggestions.json"
        f.write_text(json.dumps(catalog), encoding="utf-8")

        sr = _scoring(word_count=50)
        ar = _ats()
        results = generate_suggestions(sr, ar, f)
        assert len(results) == 5

    def test_positive_does_not_count_toward_cap(self, tmp_path):
        """positive_strong_profile fires after the cap; total can be cap + 1."""
        rules = [
            {
                "id": f"rule_{i}",
                "category": "Test",
                "priority": "high",
                "condition": {"type": "word_count_below", "threshold": 9999},
                "message": f"Rule {i}",
                "how_to_fix": "fix",
                "example": "ex"
            }
            for i in range(5)
        ]
        rules.append({
            "id": "positive_strong_profile",
            "category": "Positive",
            "priority": "low",
            "condition": {
                "type": "compound_and",
                "conditions": [
                    {"type": "score_at_least", "field": "resume_score", "threshold": 75},
                    {"type": "ats_score_at_least", "threshold": 70}
                ]
            },
            "message": "You're doing great!",
            "how_to_fix": "Keep it up",
            "example": "N/A"
        })
        catalog = {
            "suggestions_config": {"max_suggestions": 3, "priority_weights": {"high": 3, "medium": 2, "low": 1}},
            "suggestions_catalog": rules
        }
        f = tmp_path / "suggestions.json"
        f.write_text(json.dumps(catalog), encoding="utf-8")

        sr = _scoring(resume_score=80, word_count=50)
        ar = _ats(ats_score=80)
        results = generate_suggestions(sr, ar, f)
        # 3 actionable + 1 positive = 4
        assert len(results) == 4
        assert results[-1]["id"] == "positive_strong_profile"


# ---------------------------------------------------------------------------
# No suggestions scenario
# ---------------------------------------------------------------------------

class TestNoSuggestions:
    def test_empty_when_no_conditions_triggered(self, tmp_path):
        """When the catalog has no rules whose conditions match, return empty list."""
        catalog = {
            "suggestions_config": {"max_suggestions": 12, "priority_weights": {"high": 3}},
            "suggestions_catalog": [
                {
                    "id": "will_not_fire",
                    "category": "Test",
                    "priority": "high",
                    "condition": {"type": "word_count_below", "threshold": 1},
                    "message": "never",
                    "how_to_fix": "n/a",
                    "example": "n/a"
                }
            ]
        }
        f = tmp_path / "suggestions.json"
        f.write_text(json.dumps(catalog), encoding="utf-8")
        results = generate_suggestions(_scoring(word_count=400), _ats(), f)
        assert results == []


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_all_output_fields_present(self, suggestions_file):
        """Every returned suggestion must contain the six required fields."""
        sr = _scoring()
        contacts = {"emails": [], "phones": [], "linkedin": [], "github": []}
        ar = _ats(contacts=contacts)
        results = generate_suggestions(sr, ar, suggestions_file)
        assert len(results) > 0
        required_fields = {"id", "category", "priority", "message", "how_to_fix", "example"}
        for suggestion in results:
            assert required_fields.issubset(suggestion.keys()), (
                f"Suggestion missing fields: {required_fields - suggestion.keys()}"
            )
