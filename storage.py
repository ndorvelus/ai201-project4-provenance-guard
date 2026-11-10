"""SQLite persistence: submissions, appeals, certificates and the structured audit log."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.getenv("PROVENANCE_DB", os.path.join(os.path.dirname(__file__), "provenance.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    content_id        TEXT PRIMARY KEY,
    creator_id        TEXT NOT NULL,
    text              TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    attribution       TEXT NOT NULL,
    ai_likelihood     REAL NOT NULL,
    confidence        REAL NOT NULL,
    llm_score         REAL,
    stylometric_score REAL,
    marker_score      REAL,
    signals_json      TEXT NOT NULL,
    label             TEXT NOT NULL,
    status            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS appeals (
    appeal_id   TEXT PRIMARY KEY,
    content_id  TEXT NOT NULL REFERENCES submissions(content_id),
    creator_id  TEXT NOT NULL,
    reasoning   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    status      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS certificates (
    certificate_id TEXT PRIMARY KEY,
    content_id     TEXT NOT NULL REFERENCES submissions(content_id),
    creator_id     TEXT NOT NULL,
    issued_at      TEXT NOT NULL,
    evidence_json  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    event             TEXT NOT NULL,
    content_id        TEXT NOT NULL,
    creator_id        TEXT,
    attribution       TEXT,
    ai_likelihood     REAL,
    confidence        REAL,
    llm_score         REAL,
    stylometric_score REAL,
    marker_score      REAL,
    status            TEXT,
    appeal_filed      INTEGER NOT NULL DEFAULT 0,
    appeal_id         TEXT,
    appeal_reasoning  TEXT,
    details_json      TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def _signal_scores(signals: dict) -> tuple:
    return (
        signals["llm"]["score"],
        signals["stylometric"]["score"],
        signals["markers"]["score"],
    )


def write_audit(conn: sqlite3.Connection, *, event: str, sub: dict, appeal_id: str | None = None,
                appeal_reasoning: str | None = None, details: dict | None = None) -> None:
    conn.execute(
        """INSERT INTO audit_log (timestamp, event, content_id, creator_id, attribution,
               ai_likelihood, confidence, llm_score, stylometric_score, marker_score, status,
               appeal_filed, appeal_id, appeal_reasoning, details_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            now_iso(), event, sub["content_id"], sub["creator_id"], sub["attribution"],
            sub["ai_likelihood"], sub["confidence"], sub["llm_score"], sub["stylometric_score"],
            sub["marker_score"], sub["status"], 1 if appeal_id or sub.get("appeal_filed") else 0,
            appeal_id, appeal_reasoning, json.dumps(details or {}),
        ),
    )


def save_submission(*, creator_id: str, text: str, signals: dict, result: dict,
                    label: str) -> dict:
    llm, stylo, marker = _signal_scores(signals)
    sub = {
        "content_id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "created_at": now_iso(),
        "attribution": result["attribution"],
        "ai_likelihood": result["ai_likelihood"],
        "confidence": result["confidence"],
        "llm_score": llm,
        "stylometric_score": stylo,
        "marker_score": marker,
        "label": label,
        "status": "classified",
    }
    with connect() as conn:
        conn.execute(
            """INSERT INTO submissions (content_id, creator_id, text, created_at, attribution,
                   ai_likelihood, confidence, llm_score, stylometric_score, marker_score,
                   signals_json, label, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sub["content_id"], creator_id, text, sub["created_at"], sub["attribution"],
             sub["ai_likelihood"], sub["confidence"], llm, stylo, marker,
             json.dumps(signals), label, sub["status"]),
        )
        write_audit(conn, event="classified", sub=sub,
                    details={"signals": signals, "scoring_notes": result["scoring_notes"]})
    return sub


def get_submission(content_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM submissions WHERE content_id = ?", (content_id,)).fetchone()
        if row is None:
            return None
        sub = dict(row)
        sub["signals"] = json.loads(sub.pop("signals_json"))
        sub["appeals"] = [dict(r) for r in conn.execute(
            "SELECT * FROM appeals WHERE content_id = ? ORDER BY created_at", (content_id,))]
        cert = conn.execute("SELECT certificate_id, issued_at FROM certificates WHERE content_id = ?",
                            (content_id,)).fetchone()
        sub["certificate"] = dict(cert) if cert else None
        return sub


def file_appeal(sub: dict, reasoning: str, new_label: str) -> dict:
    appeal = {
        "appeal_id": str(uuid.uuid4()),
        "content_id": sub["content_id"],
        "creator_id": sub["creator_id"],
        "reasoning": reasoning,
        "created_at": now_iso(),
        "status": "open",
    }
    with connect() as conn:
        conn.execute(
            "INSERT INTO appeals VALUES (:appeal_id,:content_id,:creator_id,:reasoning,:created_at,:status)",
            appeal,
        )
        conn.execute("UPDATE submissions SET status = 'under_review', label = ? WHERE content_id = ?",
                     (new_label, sub["content_id"]))
        audit_sub = {**sub, "status": "under_review"}
        write_audit(
            conn, event="appeal_filed", sub=audit_sub, appeal_id=appeal["appeal_id"],
            appeal_reasoning=reasoning,
            details={"original_label": sub["label"], "original_status": sub["status"]},
        )
    return appeal


def issue_certificate(sub: dict, evidence: dict, new_label: str) -> dict:
    cert = {
        "certificate_id": "PG-" + uuid.uuid4().hex[:12].upper(),
        "content_id": sub["content_id"],
        "creator_id": sub["creator_id"],
        "issued_at": now_iso(),
    }
    with connect() as conn:
        conn.execute("INSERT INTO certificates VALUES (?,?,?,?,?)",
                     (cert["certificate_id"], cert["content_id"], cert["creator_id"],
                      cert["issued_at"], json.dumps(evidence)))
        conn.execute("UPDATE submissions SET status = 'verified_human', label = ? WHERE content_id = ?",
                     (new_label, sub["content_id"]))
        write_audit(conn, event="certificate_issued", sub={**sub, "status": "verified_human"},
                    details={"certificate_id": cert["certificate_id"], "evidence": evidence})
    return cert


def get_log(limit: int = 50) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    entries = []
    for r in rows:
        e = dict(r)
        e["appeal_filed"] = bool(e["appeal_filed"])
        e["details"] = json.loads(e.pop("details_json") or "{}")
        entries.append(e)
    return entries


def open_appeals() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.appeal_id, a.created_at AS appeal_filed_at, a.reasoning AS creator_reasoning,
                      a.status AS appeal_status, s.content_id, s.creator_id, s.text,
                      s.attribution AS original_attribution, s.ai_likelihood, s.confidence,
                      s.signals_json, s.created_at AS classified_at
               FROM appeals a JOIN submissions s USING (content_id)
               WHERE a.status = 'open' ORDER BY a.created_at"""
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["signals"] = json.loads(d.pop("signals_json"))
        out.append(d)
    return out


def stats() -> dict:
    with connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        by_attr = {r[0]: r[1] for r in conn.execute(
            "SELECT attribution, COUNT(*) FROM submissions GROUP BY attribution")}
        by_status = {r[0]: r[1] for r in conn.execute(
            "SELECT status, COUNT(*) FROM submissions GROUP BY status")}
        appealed = conn.execute("SELECT COUNT(DISTINCT content_id) FROM appeals").fetchone()[0]
        avg_conf = conn.execute("SELECT AVG(confidence) FROM submissions").fetchone()[0]
        certs = conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
        disagree = 0
        for (dj,) in conn.execute(
                "SELECT details_json FROM audit_log WHERE event = 'classified'"):
            if json.loads(dj).get("scoring_notes", {}).get("signals_disagree"):
                disagree += 1
        ai_appeals = conn.execute(
            """SELECT COUNT(DISTINCT a.content_id) FROM appeals a JOIN submissions s USING (content_id)
               WHERE s.attribution = 'likely_ai'""").fetchone()[0]

    def pct(n, d):
        return round(100 * n / d, 1) if d else 0.0

    attrs = {k: by_attr.get(k, 0) for k in ("likely_ai", "uncertain", "likely_human")}
    return {
        "total_submissions": total,
        "attribution_counts": attrs,
        "attribution_percent": {k: pct(v, total) for k, v in attrs.items()},
        "status_counts": by_status,
        "appeal_rate_percent": pct(appealed, total),
        "appeal_rate_on_ai_verdicts_percent": pct(ai_appeals, attrs["likely_ai"]),
        "average_confidence": round(avg_conf, 3) if avg_conf is not None else None,
        "signal_disagreement_rate_percent": pct(disagree, total),
        "certificates_issued": certs,
    }
