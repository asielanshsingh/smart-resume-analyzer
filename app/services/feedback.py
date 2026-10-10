"""
feedback.py – Smart Feedback Engine (Module 4).

Reads the suggestions catalog from data/suggestions.json and evaluates each
rule's condition against the combined scoring + ATS results.  Never reads
resume text directly; all inputs come from already-computed service outputs.
"""

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Catalog loader
# ---------------------------------------------------------------------------

def load_suggestions_catalog(suggestions_file: Path) -> dict[str, Any]:
    """Load the full suggestions catalog JSON.  Returns the parsed dict."""
    with open(suggestions_file, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Condition evaluators
# ---------------------------------------------------------------------------

def _get_word_count(scoring_result: dict[str, Any]) -> int:
    """Extract word_count from the scoring_result breakdown (completeness reasons)."""
    try:
        completeness_reasons = (
            scoring_result.get("breakdown", {})
            .get("completeness", {})
            .get("reasons", [])
        )
        for reason in completeness_reasons:
            m = re.search(r'(\d+)\s+words', reason)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 0


def _get_action_verb_count(scoring_result: dict[str, Any]) -> int:
    """Extract the action verb count from completeness breakdown reasons."""
    try:
        completeness_reasons = (
            scoring_result.get("breakdown", {})
            .get("completeness", {})
            .get("reasons", [])
        )
        for reason in completeness_reasons:
            # Looks for "N verbs" pattern in completeness reasons
            m = re.search(r'(\d+)\s+verb', reason)
            if m:
                return int(m.group(1))
            # Also check for the positive pattern "Strong action-oriented" which
            # implies >= 3 verbs were found
            if "Strong action-oriented" in reason:
                return 3
    except Exception:
        pass
    return 0


def _get_pronoun_count(scoring_result: dict[str, Any]) -> int:
    """Extract first-person pronoun count from completeness breakdown reasons."""
    try:
        completeness_reasons = (
            scoring_result.get("breakdown", {})
            .get("completeness", {})
            .get("reasons", [])
        )
        for reason in completeness_reasons:
            m = re.search(r'(\d+)\s+use', reason)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return 0


def _get_bullet_count(scoring_result: dict[str, Any]) -> int:
    """Infer bullet count from completeness reasons (>= 3 bullets → 'Good bullet point')."""
    try:
        completeness_reasons = (
            scoring_result.get("breakdown", {})
            .get("completeness", {})
            .get("reasons", [])
        )
        for reason in completeness_reasons:
            if "Good bullet point" in reason:
                return 3  # at least 3 confirmed
            if "Standard text" in reason:
                return 1  # some bullets but < 3
    except Exception:
        pass
    return 0


def _evaluate_condition(
    condition: dict[str, Any],
    scoring_result: dict[str, Any],
    ats_result: dict[str, Any],
) -> bool:
    """
    Evaluate a single condition dict against scoring + ATS results.

    Supported condition types:
      - missing_skills_non_empty
      - section_missing
      - section_present
      - no_contact_field
      - score_below
      - score_at_least
      - ats_score_below  (kept for forward-compat, not used by current catalog)
      - ats_score_at_least
      - word_count_below
      - word_count_above
      - action_verb_count_below
      - pronoun_count_above
      - bullet_count_below
      - no_quantified_metrics
      - ats_deduction_contains
      - compound_and
      - compound_or
    """
    ctype = condition.get("type", "")

    if ctype == "missing_skills_non_empty":
        field = condition.get("field", "missing_critical_skills")
        return bool(ats_result.get(field))

    if ctype == "section_missing":
        section = condition.get("section", "")
        detected = scoring_result.get("breakdown", {})
        sections_data = {}
        # Detected sections are implicit in the scoring breakdown:
        # a section "scores" > 0 or has content if its score > 0, but we
        # need the raw sections dict from ATS result (passed through).
        # We store it in ats_result under "detected_sections" in the analyze
        # endpoint; fall back to checking whether the breakdown score > 0.
        if "detected_sections" in ats_result:
            sections_data = ats_result["detected_sections"]
            return not sections_data.get(section, "").strip()
        # Fallback: use scoring breakdown — if the section scored 0 and max > 0
        breakdown = scoring_result.get("breakdown", {})
        sec_data = breakdown.get(section, {})
        if not sec_data:
            return False  # unknown section, cannot determine
        return sec_data.get("score", 0) == 0

    if ctype == "section_present":
        section = condition.get("section", "")
        if "detected_sections" in ats_result:
            sections_data = ats_result["detected_sections"]
            return bool(sections_data.get(section, "").strip())
        breakdown = scoring_result.get("breakdown", {})
        sec_data = breakdown.get(section, {})
        return sec_data.get("score", 0) > 0

    if ctype == "no_contact_field":
        field = condition.get("field", "emails")
        # ats_result carries contacts passed through from the analyze endpoint
        contacts = ats_result.get("contacts", {})
        value = contacts.get(field)
        if isinstance(value, list):
            return len(value) == 0
        return not bool(value)

    if ctype == "score_below":
        field = condition.get("field", "resume_score")
        threshold = condition.get("threshold", 0)
        score = scoring_result.get(field, scoring_result.get("resume_score", 0))
        return score < threshold

    if ctype == "score_at_least":
        field = condition.get("field", "resume_score")
        threshold = condition.get("threshold", 0)
        score = scoring_result.get(field, scoring_result.get("resume_score", 0))
        return score >= threshold

    if ctype == "ats_score_below":
        threshold = condition.get("threshold", 0)
        return ats_result.get("ats_score", 0) < threshold

    if ctype == "ats_score_at_least":
        threshold = condition.get("threshold", 0)
        return ats_result.get("ats_score", 0) >= threshold

    if ctype == "word_count_below":
        threshold = condition.get("threshold", 150)
        return _get_word_count(scoring_result) < threshold

    if ctype == "word_count_above":
        threshold = condition.get("threshold", 1500)
        return _get_word_count(scoring_result) > threshold

    if ctype == "action_verb_count_below":
        threshold = condition.get("threshold", 3)
        return _get_action_verb_count(scoring_result) < threshold

    if ctype == "pronoun_count_above":
        threshold = condition.get("threshold", 5)
        return _get_pronoun_count(scoring_result) > threshold

    if ctype == "bullet_count_below":
        threshold = condition.get("threshold", 3)
        return _get_bullet_count(scoring_result) < threshold

    if ctype == "no_quantified_metrics":
        # Quantified metrics are in the experience breakdown reason
        try:
            exp_reasons = (
                scoring_result.get("breakdown", {})
                .get("experience", {})
                .get("reasons", [])
            )
            for reason in exp_reasons:
                if "Quantified achievements" in reason:
                    return False
        except Exception:
            pass
        return True

    if ctype == "ats_deduction_contains":
        substring = condition.get("substring", "")
        deductions = ats_result.get("deductions", [])
        return any(substring in d for d in deductions)

    if ctype == "compound_and":
        sub_conditions = condition.get("conditions", [])
        return all(
            _evaluate_condition(sc, scoring_result, ats_result)
            for sc in sub_conditions
        )

    if ctype == "compound_or":
        sub_conditions = condition.get("conditions", [])
        return any(
            _evaluate_condition(sc, scoring_result, ats_result)
            for sc in sub_conditions
        )

    # Unknown condition type — skip silently (generic-safe)
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_suggestions(
    scoring_result: dict[str, Any],
    ats_result: dict[str, Any],
    suggestions_file: Path,
) -> list[dict[str, Any]]:
    """
    Evaluate all catalog rules against scoring and ATS results.

    Steps:
      1. Load catalog.
      2. Evaluate each rule's condition.
      3. De-duplicate by rule id (defensive).
      4. Separate the positive "doing well" rule from actionable ones.
      5. Sort actionable suggestions: priority (high→low) then impact weight desc.
      6. Cap actionable list at max_suggestions.
      7. Append positive note if it fired (never counts toward the cap).
      8. Return list of clean dicts (id, category, priority, message, how_to_fix, example).

    Args:
        scoring_result: Output of ``analyze_resume_score()``.
        ats_result: Output of ``analyze_ats_compatibility()``.
        suggestions_file: Path to ``data/suggestions.json``.

    Returns:
        Ordered list of triggered suggestion dicts, capped sensibly.
    """
    catalog_data = load_suggestions_catalog(suggestions_file)
    rules: list[dict[str, Any]] = catalog_data.get("suggestions_catalog", [])
    config: dict[str, Any] = catalog_data.get("suggestions_config", {})

    max_suggestions: int = config.get("max_suggestions", 12)
    priority_weights: dict[str, int] = config.get(
        "priority_weights", {"high": 3, "medium": 2, "low": 1}
    )

    POSITIVE_ID = "positive_strong_profile"

    triggered: dict[str, dict[str, Any]] = {}  # id → rule; de-dups by id

    for rule in rules:
        rule_id = rule.get("id", "")
        if not rule_id:
            continue
        condition = rule.get("condition", {})
        if _evaluate_condition(condition, scoring_result, ats_result):
            if rule_id not in triggered:
                triggered[rule_id] = rule

    positive_rule = triggered.pop(POSITIVE_ID, None)

    # Build sorted actionable list
    def _sort_key(rule: dict[str, Any]):
        priority = rule.get("priority", "low")
        weight = priority_weights.get(priority, 1)
        return (-weight, rule.get("id", ""))  # secondary: stable alphabetic

    actionable = sorted(triggered.values(), key=_sort_key)
    actionable = actionable[:max_suggestions]

    if positive_rule:
        actionable.append(positive_rule)

    output_fields = ("id", "category", "priority", "message", "how_to_fix", "example")
    return [
        {k: rule.get(k, "") for k in output_fields}
        for rule in actionable
    ]
