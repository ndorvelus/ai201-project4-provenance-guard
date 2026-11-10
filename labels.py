"""Transparency label text (must match planning.md §3 and the README exactly)."""

LABELS = {
    "likely_ai": (
        "🤖 Likely AI-generated — Our automated checks found strong, consistent signs that this "
        "text was produced with an AI writing tool. This is an estimate, not proof, and the "
        "creator can appeal it."
    ),
    "uncertain": (
        "❔ Origin unclear — Our automated checks couldn't tell with confidence whether a person "
        "or an AI tool wrote this. Treat this as \"we don't know,\" not as an accusation."
    ),
    "likely_human": (
        "✍️ Likely human-written — Our automated checks found no strong signs of AI generation "
        "in this text."
    ),
}

UNDER_REVIEW_LABEL = (
    "⏳ Under review — The creator has disputed the automated label on this work, and a person "
    "is reviewing it. No label is shown until the review is finished."
)

VERIFIED_HUMAN_LABEL = (
    "✅ Verified human process — This creator shared earlier drafts showing how the piece "
    "developed, and Provenance Guard confirmed them."
)


def label_for(attribution: str, status: str = "classified") -> str:
    if status == "under_review":
        return UNDER_REVIEW_LABEL
    if status == "verified_human":
        return VERIFIED_HUMAN_LABEL
    return LABELS[attribution]
