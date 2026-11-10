"""Provenance Guard — Flask API.

Run:  .venv/bin/python app.py      (serves http://127.0.0.1:5001)
"""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import storage
from certificate import check_drafts
from image_signals import canonical, run_all_image, validate_image
from labels import UNDER_REVIEW_LABEL, VERIFIED_HUMAN_LABEL, label_for
from scoring import combine
from signals import run_all, words

app = Flask(__name__)
app.json.ensure_ascii = False  # keep the label emoji readable in JSON output
app.json.sort_keys = False

# Rate limits — reasoning in README "Rate limiting" and planning.md §6.
SUBMIT_LIMIT = "10 per minute;100 per day"
APPEAL_LIMIT = "5 per hour"

limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

MIN_CHARS = 20
MAX_CHARS = 20_000

storage.init_db()


def _error(message: str, status: int):
    return jsonify({"error": message}), status


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({
        "error": "rate_limit_exceeded",
        "message": f"Too many requests: limit is {e.description}. Please wait and try again.",
    }), 429


@app.post("/submit")
@limiter.limit(SUBMIT_LIMIT)
def submit():
    body = request.get_json(silent=True) or {}
    content_type = body.get("content_type", "text")
    creator_id = body.get("creator_id")
    if content_type not in ("text", "image"):
        return _error("'content_type' must be 'text' (default) or 'image'", 400)
    if not isinstance(creator_id, str) or not creator_id.strip():
        return _error("JSON body must include a string field 'creator_id'", 400)
    if content_type == "image":
        return _submit_image(body.get("image"), creator_id.strip())

    text = body.get("text")
    if not isinstance(text, str):
        return _error("JSON body must include string fields 'text' and 'creator_id'", 400)
    text = text.strip()
    if len(text) < MIN_CHARS:
        return _error(f"text must be at least {MIN_CHARS} characters to analyze", 400)
    if len(text) > MAX_CHARS:
        return _error(f"text must be at most {MAX_CHARS} characters", 400)

    signals = run_all(text)
    result = combine(signals, len(words(text)))
    label = label_for(result["attribution"])
    sub = storage.save_submission(creator_id=creator_id.strip(), text=text, signals=signals,
                                  result=result, label=label)

    return jsonify({
        "content_id": sub["content_id"],
        "creator_id": sub["creator_id"],
        "content_type": "text",
        "timestamp": sub["created_at"],
        "attribution": result["attribution"],
        "ai_likelihood": result["ai_likelihood"],
        "confidence": result["confidence"],
        "label": label,
        "status": sub["status"],
        "signals": {
            "llm_score": signals["llm"]["score"],
            "stylometric_score": signals["stylometric"]["score"],
            "marker_score": signals["markers"]["score"],
            "llm_reasoning": signals["llm"]["details"].get("reasoning")
            or signals["llm"]["details"].get("error"),
            "stylometric_details": signals["stylometric"]["details"],
            "marker_details": signals["markers"]["details"],
        },
        "scoring_notes": result["scoring_notes"],
    })


def _submit_image(meta, creator_id: str):
    """Stretch (multi-modal): an image, described by its metadata, through the same pipeline."""
    err = validate_image(meta)
    if err:
        return _error(err, 400)
    signals = run_all_image(meta)
    result = combine(signals, content_type="image")
    label = label_for(result["attribution"], content_type="image")
    sub = storage.save_submission(creator_id=creator_id, text=canonical(meta), signals=signals,
                                  result=result, label=label, content_type="image")
    return jsonify({
        "content_id": sub["content_id"],
        "creator_id": sub["creator_id"],
        "content_type": "image",
        "timestamp": sub["created_at"],
        "attribution": result["attribution"],
        "ai_likelihood": result["ai_likelihood"],
        "confidence": result["confidence"],
        "label": label,
        "status": sub["status"],
        "signals": {
            "generator_score": signals["generator"]["score"],
            "capture_score": signals["capture"]["score"],
            "llm_score": signals["llm"]["score"],
            "llm_reasoning": signals["llm"]["details"].get("reasoning")
            or signals["llm"]["details"].get("error"),
            "generator_details": signals["generator"]["details"],
            "capture_details": signals["capture"]["details"],
        },
        "scoring_notes": result["scoring_notes"],
    })


@app.post("/appeal")
@limiter.limit(APPEAL_LIMIT)
def appeal():
    body = request.get_json(silent=True) or {}
    content_id = body.get("content_id")
    reasoning = (body.get("creator_reasoning") or "").strip()
    creator_id = body.get("creator_id")
    if not content_id:
        return _error("'content_id' is required", 400)
    if not 10 <= len(reasoning) <= 2000:
        return _error("'creator_reasoning' is required (10–2000 characters)", 400)

    sub = storage.get_submission(content_id)
    if sub is None:
        return _error("no submission with that content_id", 404)
    # creator_id is optional for compatibility with the assignment's curl example, but if it is
    # sent it must match the original submitter (basic ownership check; no real auth here).
    if creator_id is not None and creator_id != sub["creator_id"]:
        return _error("only the original creator can appeal this classification", 403)
    if sub["status"] == "under_review":
        return _error("an appeal for this content is already under review", 409)

    ap = storage.file_appeal(sub, reasoning, UNDER_REVIEW_LABEL)
    return jsonify({
        "message": "Appeal received. A person will review this classification.",
        "appeal_id": ap["appeal_id"],
        "content_id": content_id,
        "status": "under_review",
        "label": UNDER_REVIEW_LABEL,
        "appeal_reasoning": reasoning,
        "original_decision": {
            "attribution": sub["attribution"],
            "ai_likelihood": sub["ai_likelihood"],
            "confidence": sub["confidence"],
            "label": sub["label"],
        },
    })


@app.get("/content/<content_id>")
def content(content_id):
    sub = storage.get_submission(content_id)
    if sub is None:
        return _error("no submission with that content_id", 404)
    return jsonify(sub)


@app.get("/appeals")
def appeals_queue():
    return jsonify({"open_appeals": storage.open_appeals()})


@app.get("/log")
def log():
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 500)
    return jsonify({"entries": storage.get_log(limit)})


@app.post("/verify")
def verify():
    """Stretch: provenance certificate based on draft history."""
    body = request.get_json(silent=True) or {}
    sub = storage.get_submission(body.get("content_id") or "")
    if sub is None:
        return _error("no submission with that content_id", 404)
    if body.get("creator_id") != sub["creator_id"]:
        return _error("only the original creator can request verification", 403)
    if sub.get("content_type", "text") != "text":
        return _error("provenance certificates are only available for text submissions", 400)
    if sub["certificate"]:
        return jsonify({"status": "verified_human", "certificate": sub["certificate"],
                        "label": VERIFIED_HUMAN_LABEL})
    drafts = body.get("drafts")
    if not isinstance(drafts, list):
        return _error("'drafts' must be a list of earlier drafts (oldest first)", 400)

    check = check_drafts(drafts, sub["text"])
    if not check["passed"]:
        return jsonify({"status": sub["status"], "verified": False, "reasons": check["reasons"],
                        "evidence": check["evidence"]}), 422
    cert = storage.issue_certificate(sub, check["evidence"], VERIFIED_HUMAN_LABEL)
    return jsonify({"status": "verified_human", "verified": True, "certificate": cert,
                    "label": VERIFIED_HUMAN_LABEL, "evidence": check["evidence"]})


@app.get("/stats")
def stats():
    return jsonify(storage.stats())


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html", s=storage.stats(), recent=storage.get_log(15))


@app.get("/")
def index():
    return jsonify({
        "service": "Provenance Guard",
        "endpoints": ["POST /submit", "POST /appeal", "GET /content/<id>", "GET /appeals",
                      "GET /log", "POST /verify", "GET /stats", "GET /dashboard"],
        "content_types": {"text": "send 'text'", "image": "send content_type 'image' and an "
                                                           "'image' object of metadata"},
        "rate_limits": {"/submit": SUBMIT_LIMIT, "/appeal": APPEAL_LIMIT},
    })


if __name__ == "__main__":
    # Default 5001, not 5000: on macOS the AirPlay Receiver already listens on localhost:5000.
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5001")), debug=False)
