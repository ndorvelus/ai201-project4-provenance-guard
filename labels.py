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

# Stretch (multi-modal): images are judged from file metadata, so the wording says so.
IMAGE_LABELS = {
    "likely_ai": (
        "🤖 Likely AI-generated image — This image's file information carries strong, consistent "
        "signs that it was made with an AI image generator. This is an estimate, not proof, and "
        "the creator can appeal it."
    ),
    "uncertain": (
        "❔ Origin unclear — We couldn't tell from this image's file information whether it was "
        "photographed, made by hand, or made with an AI tool. Many sites strip this information, "
        "so treat this as \"we don't know,\" not as an accusation."
    ),
    "likely_human": (
        "📷 Likely camera or human-made — This image's file information shows signs of a real "
        "camera capture and no signs of an AI image generator."
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


def label_for(attribution: str, status: str = "classified", content_type: str = "text") -> str:
    if status == "under_review":
        return UNDER_REVIEW_LABEL
    if status == "verified_human":
        return VERIFIED_HUMAN_LABEL
    return (IMAGE_LABELS if content_type == "image" else LABELS)[attribution]
