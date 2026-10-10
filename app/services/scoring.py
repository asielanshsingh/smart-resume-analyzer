import json
import math
import re
from pathlib import Path
from typing import Any


def load_scoring_config(config_path: Path) -> dict[str, Any]:
    """Loads scoring configuration rules from JSON file."""
    if not config_path.exists():
        # Safe fallback configuration
        return {
            "category_weights": {
                "structure": 20, "skills": 20, "education": 15,
                "projects": 15, "experience": 10, "contact": 10, "completeness": 10
            },
            "fresher_substitution": {
                "enabled": True, "min_experience_words": 15,
                "substitute_from_projects_max": 6, "substitute_from_certifications_max": 4
            },
            "action_verbs": ["developed", "built", "created", "designed", "implemented", "engineered", "optimized", "managed"]
        }
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def safe_clamp_score(val: Any, min_val: int = 0, max_val: int = 100) -> int:
    """Safely clamps any numeric value or fallback to integer between min_val and max_val."""
    try:
        if val is None or math.isnan(float(val)):
            return min_val
        num = float(val)
        return max(min_val, min(max_val, int(round(num))))
    except Exception:
        return min_val


def evaluate_structure(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates structure category (Max 20 pts)."""
    max_pts = config.get("category_weights", {}).get("structure", 20)
    sections = parsed_data.get("detected_sections", {})
    reasons = []
    score = 0.0

    essential_secs = config.get("structure_rules", {}).get("essential_sections", ["contact", "education", "skills"])
    recommended_secs = config.get("structure_rules", {}).get("recommended_sections", ["experience", "projects", "summary", "certifications"])

    # 1. Essential Sections Check (12 pts max)
    found_essential = [sec for sec in essential_secs if sections.get(sec, "").strip()]
    essential_pts = len(found_essential) * (12.0 / max(1, len(essential_secs)))
    score += essential_pts
    reasons.append(f"Essential sections present ({len(found_essential)}/{len(essential_secs)}: {', '.join(found_essential) if found_essential else 'none'}): +{int(round(essential_pts))}/{12}")

    # 2. Recommended Sections Check (6 pts max)
    found_recommended = [sec for sec in recommended_secs if sections.get(sec, "").strip()]
    rec_pts = min(6.0, len(found_recommended) * 1.5)
    score += rec_pts
    reasons.append(f"Recommended sections present ({len(found_recommended)}/{len(recommended_secs)}): +{int(round(rec_pts))}/6")

    # 3. Logical Order & Heading Quality (2 pts max)
    raw_text = parsed_data.get("raw_text", "").lower()
    logical_order = config.get("structure_rules", {}).get("logical_order", ["contact", "summary", "experience", "education", "skills", "projects"])
    detected_positions = []
    for sec in logical_order:
        sec_text = sections.get(sec, "").strip()
        if sec_text:
            pos = raw_text.find(sec_text[:30].lower())
            if pos != -1:
                detected_positions.append(pos)

    # Check if detected section positions are strictly increasing
    if len(detected_positions) >= 2 and detected_positions == sorted(detected_positions):
        score += 2.0
        reasons.append("Logical section ordering followed: +2/2")
    elif len(found_essential) >= 2:
        score += 1.0
        reasons.append("Acceptable section organization: +1/2")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def evaluate_skills(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates skills category (Max 20 pts)."""
    max_pts = config.get("category_weights", {}).get("skills", 20)
    sections = parsed_data.get("detected_sections", {})
    skills_text = sections.get("skills", "").strip()
    raw_text = parsed_data.get("raw_text", "")
    reasons = []
    score = 0.0

    target_text = skills_text if skills_text else raw_text

    # Extract distinct skill tokens
    skill_items = [s.strip() for s in re.split(r'[,•|\n\t;/]+', target_text) if len(s.strip()) > 1]

    # Filter out common filler words
    skill_items = [s for s in skill_items if not s.lower().startswith("skills") and len(s) <= 40]
    distinct_skills = list(dict.fromkeys(skill_items))
    skill_count = len(distinct_skills)

    min_skills = config.get("skills_rules", {}).get("min_skills_for_max_score", 10)

    if skill_count >= min_skills:
        skill_pts = 16.0
        reasons.append(f"Strong skills inventory ({skill_count} distinct skills identified): +16/16")
    elif skill_count >= 5:
        skill_pts = 12.0
        reasons.append(f"Moderate skills inventory ({skill_count} distinct skills identified): +12/16")
    elif skill_count >= 1:
        skill_pts = 6.0
        reasons.append(f"Basic skills inventory ({skill_count} skills identified): +6/16")
    else:
        skill_pts = 0.0
        reasons.append("No distinct technical skills section or skills list identified: +0/16")

    score += skill_pts

    # Categorization Check (+4 pts max)
    categorized_bonus = config.get("skills_rules", {}).get("categorized_bonus_points", 4)
    has_categories = False
    if skills_text:
        category_indicators = [":", "languages", "frameworks", "tools", "databases", "platforms", "libraries"]
        matched_indicators = [ind for ind in category_indicators if ind in skills_text.lower()]
        if len(matched_indicators) >= 2:
            has_categories = True

    if has_categories:
        score += categorized_bonus
        reasons.append(f"Skills are cleanly categorized into functional groups: +{categorized_bonus}/{categorized_bonus}")
    elif skill_count > 0:
        score += 2.0
        reasons.append("Skills are listed cleanly: +2/4")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def evaluate_education(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates education category (Max 15 pts)."""
    max_pts = config.get("category_weights", {}).get("education", 15)
    sections = parsed_data.get("detected_sections", {})
    edu_text = sections.get("education", "").strip()
    raw_text = parsed_data.get("raw_text", "")
    reasons = []
    score = 0.0

    target_text = (edu_text + "\n" + raw_text).lower()

    degree_keywords = config.get("education_rules", {}).get("degree_keywords", ["bachelor", "master", "phd", "b.tech", "b.e.", "b.s."])
    inst_keywords = config.get("education_rules", {}).get("institution_keywords", ["university", "college", "institute", "school"])
    gpa_keywords = config.get("education_rules", {}).get("gpa_keywords", ["cgpa", "gpa", "score", "grade", "percentage", "%"])

    # 1. Degree Detection (6 pts)
    matched_degrees = [deg for deg in degree_keywords if deg in target_text]
    if matched_degrees:
        score += 6.0
        reasons.append(f"Degree qualification detected ({matched_degrees[0].upper()}): +6/6")
    elif edu_text:
        score += 3.0
        reasons.append("Education section present: +3/6")
    else:
        reasons.append("No explicit degree qualification detected: +0/6")

    # 2. Institution Detection (5 pts)
    matched_insts = [inst for inst in inst_keywords if inst in target_text]
    if matched_insts:
        score += 5.0
        reasons.append(f"Educational institution detected ({matched_insts[0].title()}): +5/5")
    elif edu_text:
        score += 2.0
        reasons.append("Educational background mentioned: +2/5")

    # 3. GPA / Year / Honors Detection (4 pts)
    year_match = re.search(r'\b(19|20)\d{2}\b', target_text)
    matched_gpa = [gpa for gpa in gpa_keywords if gpa in target_text]
    if matched_gpa or year_match:
        score += 4.0
        detail = matched_gpa[0] if matched_gpa else f"Year {year_match.group(0)}"
        reasons.append(f"Academic metrics or graduation timeframe specified ({detail}): +4/4")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def evaluate_projects(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates projects category (Max 15 pts)."""
    max_pts = config.get("category_weights", {}).get("projects", 15)
    sections = parsed_data.get("detected_sections", {})
    proj_text = sections.get("projects", "").strip()
    reasons = []
    score = 0.0

    if not proj_text:
        reasons.append("No projects section detected: +0/15")
        return {"score": 0.0, "max_score": max_pts, "reasons": reasons}

    lines = [l.strip() for l in proj_text.splitlines() if l.strip()]

    # 1. Project Count Check (10 pts max)
    min_projects = config.get("project_rules", {}).get("min_projects_for_max", 2)
    # Estimate projects by bullet count or headers
    project_entries = [l for l in lines if len(l) > 15]

    if len(project_entries) >= min_projects * 2 or len(lines) >= 4:
        score += 10.0
        reasons.append("Multiple structured project entries detected: +10/10")
    elif len(project_entries) >= 1:
        score += 6.0
        reasons.append("Single project entry detected: +6/10")

    # 2. Action Verbs Check (3 pts max)
    action_verbs = config.get("action_verbs", [])
    verb_bonus = config.get("project_rules", {}).get("action_verb_bonus_points", 3)
    matched_verbs = [v for v in action_verbs if v in proj_text.lower()]
    if matched_verbs:
        score += float(verb_bonus)
        reasons.append(f"Action verbs used in project descriptions ({len(matched_verbs)} verbs): +{verb_bonus}/{verb_bonus}")

    # 3. Repository Links Check (2 pts max)
    contacts = parsed_data.get("contacts", {})
    has_links = bool(contacts.get("github") or "http" in proj_text.lower() or "github.com" in proj_text.lower())
    link_bonus = config.get("project_rules", {}).get("link_bonus_points", 2)
    if has_links:
        score += float(link_bonus)
        reasons.append(f"Project repository or live demo links included: +{link_bonus}/{link_bonus}")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def evaluate_experience(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates work experience/internships category with Fresher substitution rule (Max 10 pts)."""
    max_pts = config.get("category_weights", {}).get("experience", 10)
    sections = parsed_data.get("detected_sections", {})
    exp_text = sections.get("experience", "").strip()
    proj_text = sections.get("projects", "").strip()
    cert_text = sections.get("certifications", "").strip()
    reasons = []
    score = 0.0

    exp_words = len(exp_text.split()) if exp_text else 0
    min_exp_words = config.get("fresher_substitution", {}).get("min_experience_words", 15)

    if exp_words >= min_exp_words:
        # Standard work experience evaluation
        score += 6.0
        reasons.append("Work experience section present with structured role descriptions: +6/6")

        # Quantified metrics check (+4 pts max)
        metric_regex = config.get("experience_rules", {}).get("metric_regex", r'\b(?:\d+%\b|\$\d+|\d+\+)')
        metric_matches = re.findall(metric_regex, exp_text)
        quant_bonus = config.get("experience_rules", {}).get("quantified_metrics_bonus_points", 4)
        if metric_matches:
            score += float(quant_bonus)
            reasons.append(f"Quantified achievements detected ({len(metric_matches)} metrics): +{quant_bonus}/{quant_bonus}")
        else:
            score += 2.0
            reasons.append("Work experience listed without quantified metrics: +2/4")
    else:
        # Fresher substitution path
        fresher_config = config.get("fresher_substitution", {})
        if fresher_config.get("enabled", True):
            sub_proj_max = fresher_config.get("substitute_from_projects_max", 6)
            sub_cert_max = fresher_config.get("substitute_from_certifications_max", 4)

            proj_words = len(proj_text.split()) if proj_text else 0
            cert_words = len(cert_text.split()) if cert_text else 0

            proj_sub = min(float(sub_proj_max), (proj_words / 30.0) * sub_proj_max) if proj_words > 0 else 0.0
            cert_sub = min(float(sub_cert_max), (cert_words / 15.0) * sub_cert_max) if cert_words > 0 else 0.0

            sub_total = min(float(max_pts), proj_sub + cert_sub)
            score += sub_total

            if sub_total > 0:
                reasons.append(
                    f"Fresher evaluation active: Practical project depth (+{int(round(proj_sub))}) and certifications (+{int(round(cert_sub))}) evaluated as experience substitutes: +{int(round(sub_total))}/{max_pts}"
                )
            else:
                reasons.append("No work experience, projects, or certifications detected: +0/10")
        else:
            reasons.append("No work experience detected: +0/10")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def evaluate_contact(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates contact info category (Max 10 pts)."""
    max_pts = config.get("category_weights", {}).get("contact", 10)
    contacts = parsed_data.get("contacts", {})
    rules = config.get("contact_rules", {})
    reasons = []
    score = 0.0

    email_pts = rules.get("email_points", 3)
    phone_pts = rules.get("phone_points", 3)
    linkedin_pts = rules.get("linkedin_points", 2)
    github_pts = rules.get("github_points", 2)

    emails = contacts.get("emails", [])
    phones = contacts.get("phones", [])
    linkedin = contacts.get("linkedin", [])
    github = contacts.get("github", [])

    if emails:
        score += float(email_pts)
        reasons.append(f"Email contact provided ({emails[0]}): +{email_pts}/{email_pts}")
    else:
        reasons.append("Email contact missing: +0/3")

    if phones:
        score += float(phone_pts)
        reasons.append(f"Phone contact provided ({phones[0]}): +{phone_pts}/{phone_pts}")
    else:
        reasons.append("Phone contact missing: +0/3")

    if linkedin:
        score += float(linkedin_pts)
        reasons.append(f"LinkedIn profile link provided: +{linkedin_pts}/{linkedin_pts}")

    if github:
        score += float(github_pts)
        reasons.append(f"GitHub profile link provided: +{github_pts}/{github_pts}")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def evaluate_completeness(parsed_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Evaluates completeness, formatting, bullet usage, and action verb density (Max 10 pts)."""
    max_pts = config.get("category_weights", {}).get("completeness", 10)
    word_count = parsed_data.get("word_count", 0)
    raw_text = parsed_data.get("raw_text", "")
    rules = config.get("completeness_rules", {})
    reasons = []
    score = 0.0

    # 1. Word Count Health (6 pts max)
    opt_min = rules.get("optimal_min_words", 300)
    opt_max = rules.get("optimal_max_words", 900)
    too_short = rules.get("too_short_words", 150)
    too_long = rules.get("too_long_words", 1500)

    if opt_min <= word_count <= opt_max:
        score += 6.0
        reasons.append(f"Optimal resume word count ({word_count} words): +6/6")
    elif (too_short <= word_count < opt_min) or (opt_max < word_count <= too_long):
        score += 4.0
        reasons.append(f"Acceptable word count length ({word_count} words): +4/6")
    elif word_count < too_short:
        score += 1.0
        reasons.append(f"Resume text is too brief ({word_count} words): +1/6")
    else:
        score += 2.0
        reasons.append(f"Resume text is excessively long ({word_count} words): +2/6")

    # 2. Bullet Formatting & Layout (2 pts max)
    bullet_count = len(re.findall(r'[•\-*]\s+', raw_text))
    lines = [l for l in raw_text.splitlines() if l.strip()]
    if bullet_count >= 3 or (len(lines) > 10 and bullet_count > 0):
        score += 2.0
        reasons.append("Good bullet point structure used: +2/2")
    elif len(lines) > 5:
        score += 1.0
        reasons.append("Standard text formatting: +1/2")

    # 3. Action Verbs & Pronoun Check (2 pts max)
    action_verbs = config.get("action_verbs", [])
    verb_matches = [v for v in action_verbs if v in raw_text.lower()]

    pronouns = rules.get("first_person_pronouns", ["i", "me", "my"])
    pronoun_pattern = r'\b(' + '|'.join(pronouns) + r')\b'
    pronoun_matches = re.findall(pronoun_pattern, raw_text, re.IGNORECASE)

    if len(verb_matches) >= 3 and len(pronoun_matches) <= 3:
        score += 2.0
        reasons.append("Strong action-oriented language without excessive first-person pronouns: +2/2")
    elif len(pronoun_matches) > 5:
        score += 0.0
        reasons.append(f"High first-person pronoun frequency detected ({len(pronoun_matches)} uses): +0/2")
    else:
        score += 1.0
        reasons.append("Satisfactory action verb usage: +1/2")

    final_score = min(float(max_pts), score)
    return {
        "score": round(final_score, 1),
        "max_score": max_pts,
        "reasons": reasons
    }


def analyze_resume_score(parsed_data: dict[str, Any], config_path: Path) -> dict[str, Any]:
    """
    Main entrypoint to evaluate total deterministic resume score out of 100 points.
    Returns clamped integer total score and structured breakdown with human-readable reasons.
    """
    config = load_scoring_config(config_path)

    try:
        struct_res = evaluate_structure(parsed_data, config)
        skills_res = evaluate_skills(parsed_data, config)
        edu_res = evaluate_education(parsed_data, config)
        proj_res = evaluate_projects(parsed_data, config)
        exp_res = evaluate_experience(parsed_data, config)
        contact_res = evaluate_contact(parsed_data, config)
        comp_res = evaluate_completeness(parsed_data, config)

        raw_total = (
            struct_res["score"] +
            skills_res["score"] +
            edu_res["score"] +
            proj_res["score"] +
            exp_res["score"] +
            contact_res["score"] +
            comp_res["score"]
        )

        final_total = safe_clamp_score(raw_total, 0, 100)

        return {
            "resume_score": final_total,
            "raw_score": round(raw_total, 1),
            "breakdown": {
                "structure": struct_res,
                "skills": skills_res,
                "education": edu_res,
                "projects": proj_res,
                "experience": exp_res,
                "contact": contact_res,
                "completeness": comp_res
            }
        }
    except Exception as e:
        # Fallback safe score on unexpected errors
        return {
            "resume_score": 0,
            "raw_score": 0.0,
            "error": str(e),
            "breakdown": {
                "structure": {"score": 0, "max_score": 20, "reasons": ["Error evaluating structure"]},
                "skills": {"score": 0, "max_score": 20, "reasons": ["Error evaluating skills"]},
                "education": {"score": 0, "max_score": 15, "reasons": ["Error evaluating education"]},
                "projects": {"score": 0, "max_score": 15, "reasons": ["Error evaluating projects"]},
                "experience": {"score": 0, "max_score": 10, "reasons": ["Error evaluating experience"]},
                "contact": {"score": 0, "max_score": 10, "reasons": ["Error evaluating contact"]},
                "completeness": {"score": 0, "max_score": 10, "reasons": ["Error evaluating completeness"]}
            }
        }
