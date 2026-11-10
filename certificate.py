"""Stretch: provenance certificate — verify a creator's draft history (planning.md §7)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

MIN_DRAFTS = 2
MAX_STEP_SIMILARITY = 0.97   # consecutive drafts this similar (char-level) are copy-paste
MIN_STEP_OVERLAP = 0.40      # share of a draft's vocabulary that must survive into the next one
MIN_FINAL_OVERLAP = 0.60     # share of the last draft's vocabulary found in the submitted text

# Divergence from planning.md §7: the spec used difflib similarity for "related" too, but a short
# outline that grows into a full piece scores ~0.2 on character similarity even though it is a
# genuine revision. Vocabulary overlap (containment) measures "did this draft grow into the next".


def _sim(a: str, b: str) -> float:
    return round(SequenceMatcher(None, a, b).ratio(), 3)


def _overlap(a: str, b: str) -> float:
    va = set(re.findall(r"[a-z']+", a.lower()))
    vb = set(re.findall(r"[a-z']+", b.lower()))
    return round(len(va & vb) / len(va), 3) if va else 0.0


def check_drafts(drafts: list[str], final_text: str) -> dict:
    """Return {"passed": bool, "reasons": [...], "evidence": {...}}."""
    reasons: list[str] = []
    drafts = [d for d in drafts if isinstance(d, str) and d.strip()]
    if len(drafts) < MIN_DRAFTS:
        return {"passed": False, "reasons": [f"provide at least {MIN_DRAFTS} earlier drafts"],
                "evidence": {"draft_count": len(drafts)}}

    chain = drafts + [final_text]
    sims = [_sim(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    overlaps = [_overlap(chain[i], chain[i + 1]) for i in range(len(chain) - 1)]
    for i, (s, o) in enumerate(zip(sims, overlaps)):
        nxt = "final text" if i == len(sims) - 1 else f"draft {i + 2}"
        if s >= MAX_STEP_SIMILARITY:
            reasons.append(f"draft {i + 1} -> {nxt} is nearly identical (similarity {s})")
        if i < len(sims) - 1 and o < MIN_STEP_OVERLAP:
            reasons.append(f"draft {i + 1} -> {nxt} looks unrelated (vocabulary overlap {o})")
    final_overlap = overlaps[-1]
    if final_overlap < MIN_FINAL_OVERLAP:
        reasons.append(f"last draft is not close enough to the submitted text "
                       f"(vocabulary overlap {final_overlap})")

    return {
        "passed": not reasons,
        "reasons": reasons,
        "evidence": {
            "draft_count": len(drafts),
            "step_char_similarities": sims,
            "step_vocabulary_overlaps": overlaps,
            "draft_lengths": [len(d) for d in drafts],
            "final_vocabulary_overlap": final_overlap,
        },
    }
