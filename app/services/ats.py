import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

_nlp = None

def get_spacy_nlp():
    """Lazy singleton loader for spaCy model."""
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def build_skill_regex(skill: str) -> re.Pattern:
    """
    Builds a word-boundary safe regex for skill strings, including terms with
    special characters like C++, C#, .NET, Node.js, and CI/CD.
    Uses custom lookarounds (?<![A-Za-z0-9]) and (?![A-Za-z0-9]) around escaped skill.
    """
    escaped = re.escape(skill.strip())
    pattern = r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])"
    return re.compile(pattern, re.IGNORECASE)


def match_skills_in_text(
    skill: str,
    aliases: List[str],
    raw_text: str,
    sections_json: Optional[Dict[str, str]] = None
) -> Tuple[bool, Optional[str], List[str]]:
    """
    Checks if canonical skill or any of its aliases match in raw_text or sections.
    Returns (is_matched, matched_by_term, list_of_sections_found).
    """
    terms_to_check = [skill] + [a for a in aliases if a.strip().lower() != skill.strip().lower()]
    sections_found: Set[str] = set()
    matched_term: Optional[str] = None
    is_matched = False

    for term in terms_to_check:
        regex = build_skill_regex(term)
        
        # Check explicit sections first
        term_matched = False
        if sections_json and isinstance(sections_json, dict):
            for sec_name, sec_content in sections_json.items():
                if sec_content and regex.search(sec_content):
                    sections_found.add(sec_name)
                    term_matched = True
        
        # Check overall raw_text
        if raw_text and regex.search(raw_text):
            term_matched = True
            if not sections_found:
                sections_found.add("general_body")
        
        if term_matched:
            is_matched = True
            if not matched_term:
                matched_term = term

    return is_matched, matched_term, sorted(list(sections_found))


def extract_skills_from_jd(
    jd_text: str,
    skills_file_path: Path
) -> Dict[str, List[str]]:
    """
    Extracts technical skills generically from custom job description text
    using master skill dictionary in skills.json and spaCy lemma/phrase matching.
    """
    if not jd_text or not jd_text.strip():
        return {"required_skills": [], "preferred_skills": [], "skill_aliases": {}}

    try:
        with open(skills_file_path, "r", encoding="utf-8") as f:
            skills_data = json.load(f)
            master_skills: List[str] = skills_data.get("skills", [])
    except Exception:
        master_skills = []

    matched_skills: Set[str] = set()
    jd_clean = jd_text.lower()

    # Search master skills using custom lookaround regexes
    for skill in master_skills:
        regex = build_skill_regex(skill)
        if regex.search(jd_clean):
            matched_skills.add(skill)

    if not matched_skills:
        return {"required_skills": [], "preferred_skills": [], "skill_aliases": {}}

    sorted_matched = sorted(list(matched_skills))
    
    # Split skills into required (first ~65%) and preferred (remaining)
    split_idx = max(1, int(len(sorted_matched) * 0.65))
    required = sorted_matched[:split_idx]
    preferred = sorted_matched[split_idx:]

    return {
        "required_skills": required,
        "preferred_skills": preferred,
        "skill_aliases": {}
    }


def calculate_ats_compatibility_score(
    parsed_resume: Dict[str, Any],
    keyword_match_pct: float,
    ats_config_file: Path
) -> Dict[str, Any]:
    """
    Calculates ATS compatibility score out of 100 based on keyword match,
    section headings, contact info, text extraction, layout risk flags, and word count.
    Returns score and array of deduction reason strings.
    """
    try:
        with open(ats_config_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {
            "category_weights": {
                "keyword_match": 40,
                "standard_sections": 20,
                "contact_info": 15,
                "text_extraction": 10,
                "layout_formatting": 10,
                "length_suitability": 5
            }
        }

    weights = cfg.get("category_weights", {})
    deductions: List[str] = []

    # 1. Keyword Match (Max 40)
    kw_weight = weights.get("keyword_match", 40)
    kw_score = (keyword_match_pct / 100.0) * kw_weight
    if kw_score < kw_weight:
        lost = kw_weight - kw_score
        deductions.append(f"Keyword match rate was {keyword_match_pct:.1f}%, resulting in a deduction of {lost:.1f} points.")

    # 2. Standard Section Headings (Max 20)
    sec_weight = weights.get("standard_sections", 20)
    detected_secs = parsed_resume.get("sections_json") or {}
    essential = ["contact", "education", "experience", "skills"]
    missing_essential = [s for s in essential if s not in detected_secs]
    
    sec_score = sec_weight
    if missing_essential:
        deduction_per_sec = 5
        lost = len(missing_essential) * deduction_per_sec
        sec_score = max(0, sec_weight - lost)
        deductions.append(f"Missing essential section(s): {', '.join(missing_essential)} (-{lost:.1f} points).")

    # 3. Parseable Contact Info (Max 15)
    contact_weight = weights.get("contact_info", 15)
    contacts = parsed_resume.get("contacts_json") or {}
    email = contacts.get("email")
    phone = contacts.get("phone")
    
    contact_score = 0
    if email:
        contact_score += 8
    else:
        deductions.append("No email address detected (-8 points).")
        
    if phone:
        contact_score += 7
    else:
        deductions.append("No phone number detected (-7 points).")

    # 4. Text Extraction Quality (Max 10)
    text_weight = weights.get("text_extraction", 10)
    raw_text = parsed_resume.get("extracted_text", "")
    word_count = parsed_resume.get("word_count", 0)
    
    text_score = text_weight
    if not raw_text or word_count < 30:
        text_score = 0
        deductions.append("Resume text extraction yielded very few words, severely reducing ATS readability (-10 points).")

    # 5. Layout & Formatting Risk Check (Max 10)
    layout_weight = weights.get("layout_formatting", 10)
    warnings = parsed_resume.get("warnings_json") or []
    
    layout_score = layout_weight
    if warnings:
        lost = min(layout_weight, len(warnings) * 3.5)
        layout_score = max(0, layout_weight - lost)
        deductions.append(f"Layout/formatting risks detected ({', '.join(warnings)}) (-{lost:.1f} points).")

    # 6. Length Suitability (Max 5)
    length_weight = weights.get("length_suitability", 5)
    length_score = length_weight
    if word_count < 100:
        length_score = 0
        deductions.append(f"Resume is extremely short ({word_count} words). Aim for 300-1000 words (-5 points).")
    elif word_count < 300 or word_count > 1000:
        length_score = 2.5
        deductions.append(f"Resume length ({word_count} words) is outside optimal 300-1000 word range (-2.5 points).")

    total_score = round(kw_score + sec_score + contact_score + text_score + layout_score + length_score)
    final_score = max(0, min(100, total_score))

    return {
        "ats_score": final_score,
        "category_scores": {
            "keyword_match": round(kw_score, 1),
            "standard_sections": round(sec_score, 1),
            "contact_info": round(contact_score, 1),
            "text_extraction": round(text_score, 1),
            "layout_formatting": round(layout_score, 1),
            "length_suitability": round(length_score, 1)
        },
        "deductions": deductions
    }


def analyze_ats_compatibility(
    parsed_resume: Dict[str, Any],
    role_config: Optional[Dict[str, Any]] = None,
    job_description: Optional[str] = None,
    skills_file_path: Optional[Path] = None,
    ats_config_file: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Main evaluation pipeline for ATS keyword checker & compatibility score.
    """
    raw_text = parsed_resume.get("extracted_text", "")
    sections_json = parsed_resume.get("sections_json") or {}

    # 1. Determine role skill requirements & aliases
    if role_config:
        req_skills = role_config.get("required_skills", [])
        pref_skills = role_config.get("preferred_skills", [])
        aliases_map = role_config.get("skill_aliases", {})
        target_title = role_config.get("title", "Target Role")
    elif job_description and skills_file_path:
        extracted = extract_skills_from_jd(job_description, skills_file_path)
        req_skills = extracted.get("required_skills", [])
        pref_skills = extracted.get("preferred_skills", [])
        aliases_map = extracted.get("skill_aliases", {})
        target_title = "Custom Job Description"
    else:
        req_skills = []
        pref_skills = []
        aliases_map = {}
        target_title = "Unknown Target"

    if not req_skills and not pref_skills:
        # No recognizable skills found
        return {
            "error": "NO_RECOGNIZABLE_SKILLS",
            "message": "No technical skills or requirements could be identified for evaluation."
        }

    # 2. Evaluate Required / Critical Skills
    matched_skills_list: List[Dict[str, Any]] = []
    missing_critical: List[str] = []
    missing_nice_to_have: List[str] = []

    matched_req_count = 0
    for skill in req_skills:
        aliases = aliases_map.get(skill, [])
        is_matched, matched_by, sec_found = match_skills_in_text(
            skill, aliases, raw_text, sections_json
        )
        if is_matched:
            matched_req_count += 1
            matched_skills_list.append({
                "skill": skill,
                "type": "critical",
                "matched_by": matched_by,
                "sections": sec_found
            })
        else:
            missing_critical.append(skill)

    # 3. Evaluate Preferred / Nice-to-Have Skills
    matched_pref_count = 0
    for skill in pref_skills:
        aliases = aliases_map.get(skill, [])
        is_matched, matched_by, sec_found = match_skills_in_text(
            skill, aliases, raw_text, sections_json
        )
        if is_matched:
            matched_pref_count += 1
            matched_skills_list.append({
                "skill": skill,
                "type": "nice_to_have",
                "matched_by": matched_by,
                "sections": sec_found
            })
        else:
            missing_nice_to_have.append(skill)

    # 4. Keyword Match Percentage Calculation
    total_role_skills = len(req_skills) + len(pref_skills)
    total_matched_skills = matched_req_count + matched_pref_count
    
    if total_role_skills > 0:
        keyword_match_pct = (total_matched_skills / total_role_skills) * 100.0
    else:
        keyword_match_pct = 0.0

    keyword_match_pct = round(keyword_match_pct, 1)

    # 5. Calculate ATS Compatibility Score & Deductions
    if ats_config_file:
        ats_eval = calculate_ats_compatibility_score(parsed_resume, keyword_match_pct, ats_config_file)
    else:
        ats_eval = {"ats_score": 0, "category_scores": {}, "deductions": []}

    return {
        "target_title": target_title,
        "ats_score": ats_eval["ats_score"],
        "category_scores": ats_eval.get("category_scores", {}),
        "keyword_match_percentage": keyword_match_pct,
        "matched_skills_count": total_matched_skills,
        "total_role_skills_count": total_role_skills,
        "matched_skills": matched_skills_list,
        "missing_critical_skills": missing_critical,
        "missing_nice_to_have_skills": missing_nice_to_have,
        "deductions": ats_eval["deductions"]
    }
