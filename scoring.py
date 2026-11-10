"""Combine signal scores into a calibrated attribution (planning.md §1 "Combining" and §2)."""

from __future__ import annotations

BASE_WEIGHTS = {"llm": 0.50, "stylometric": 0.30, "markers": 0.20}
# Images (stretch: multi-modal): an explicit generator fingerprint is the strongest evidence; the
# LLM only sees the same metadata, so it gets the smallest weight. See README "Multi-modal".
IMAGE_WEIGHTS = {"generator": 0.45, "capture": 0.30, "llm": 0.25}
SHORT_TEXT_WORDS = 40          # below this, pure-Python statistics are unreliable
DISAGREEMENT_SPREAD = 0.5      # max - min signal score above which we shrink toward 0.5
SHRINK_FACTOR = 0.6

AI_THRESHOLD = 0.75            # ai_likelihood >= this (plus corroboration) -> likely_ai
HUMAN_THRESHOLD = 0.35         # ai_likelihood <= this -> likely_human
LLM_CORROBORATION = 0.6        # LLM must be at least this sure for an AI verdict
LOCAL_CORROBORATION = 0.5      # ...and stylometric or markers must be at least this
FINGERPRINT_CORROBORATION = 0.6  # images: generator fingerprint must be at least this


def _corroborated(scores: dict, content_type: str) -> bool:
    if content_type == "image":
        # An AI verdict on an image needs an explicit fingerprint plus one other signal agreeing.
        # Missing camera metadata alone can never produce "likely AI" (it is easy to strip).
        return (scores.get("generator", 0) >= FINGERPRINT_CORROBORATION
                and (scores.get("llm", 0) >= LOCAL_CORROBORATION
                     or scores.get("capture", 0) >= LOCAL_CORROBORATION))
    llm = scores.get("llm")
    return (
        llm is not None
        and llm >= LLM_CORROBORATION
        and (scores.get("stylometric", 0) >= LOCAL_CORROBORATION
             or scores.get("markers", 0) >= LOCAL_CORROBORATION)
    )


def combine(signals: dict, word_count: int | None = None, content_type: str = "text") -> dict:
    scores = {name: s["score"] for name, s in signals.items() if s.get("score") is not None}

    weights = dict(IMAGE_WEIGHTS if content_type == "image" else BASE_WEIGHTS)
    short_text = content_type == "text" and word_count is not None and word_count < SHORT_TEXT_WORDS
    if short_text:
        weights["stylometric"] *= 0.5
        weights["markers"] *= 0.5
    used = {k: weights[k] for k in scores}
    total = sum(used.values())

    if not scores or total == 0:
        ai = 0.5
    else:
        ai = sum(used[k] * scores[k] for k in scores) / total

    spread = (max(scores.values()) - min(scores.values())) if len(scores) > 1 else 0.0
    disagree = spread > DISAGREEMENT_SPREAD
    if disagree:
        ai = 0.5 + (ai - 0.5) * SHRINK_FACTOR

    llm = scores.get("llm")
    corroborated = _corroborated(scores, content_type)

    # Refinement found in testing (not in the original spec): an uncorroborated score above the AI
    # threshold used to come back as "uncertain" with confidence 0.9, which contradicts the label.
    # Cap it just under the threshold so the number and the label tell the same story.
    capped = False
    if ai >= AI_THRESHOLD and not corroborated:
        ai = AI_THRESHOLD - 0.01
        capped = True

    if ai >= AI_THRESHOLD and corroborated:
        attribution = "likely_ai"
    elif ai <= HUMAN_THRESHOLD:
        attribution = "likely_human"
    else:
        attribution = "uncertain"

    ai = round(ai, 3)
    return {
        "attribution": attribution,
        "ai_likelihood": ai,
        "confidence": round(max(ai, 1 - ai), 3),
        "scoring_notes": {
            "weights_used": {k: round(v / total, 3) for k, v in used.items()} if total else {},
            "short_text_guard": short_text,
            "signal_spread": round(spread, 3),
            "signals_disagree": disagree,
            "ai_verdict_corroborated": corroborated,
            "capped_uncorroborated": capped,
            "llm_available": llm is not None,
        },
    }
