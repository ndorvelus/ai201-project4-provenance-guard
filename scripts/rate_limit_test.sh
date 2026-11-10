#!/usr/bin/env bash
# Sends 12 rapid submissions; expect 10 x 200 then 429s (limit: 10 per minute).
# Usage: bash scripts/rate_limit_test.sh   (server must be running: .venv/bin/python app.py)
BASE="${BASE:-http://localhost:5001}"
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/submit" \
    -H "Content-Type: application/json" \
    -d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
