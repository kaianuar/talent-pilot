#!/bin/bash
# Smoke test for a running TalentPilot container.
#
# Usage:
#   ./smoke-test.sh                    # test http://localhost:9000
#   ./smoke-test.sh https://talentpilot.fc.aliyuncs.com  # test a remote URL
#
# Exits 0 if all checks pass, 1 otherwise.

set -e

BASE_URL="${1:-http://localhost:9000}"
echo "=== TalentPilot smoke test against ${BASE_URL} ==="
echo

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1"; FAILED=1; }

FAILED=0

# 1. Frontend reachable
echo "[1/6] Frontend (React SPA)..."
if curl -sf "${BASE_URL}/" -o /dev/null; then
    pass "GET / returns 200"
else
    fail "GET / did not return 200"
fi

# 2. Status endpoint reports service config
echo "[2/6] Backend /status..."
STATUS=$(curl -sf "${BASE_URL}/status" || true)
if [ -n "$STATUS" ]; then
    pass "GET /status returned: ${STATUS}"
    # Check for required keys
    if echo "$STATUS" | grep -q "version"; then
        pass "/status includes version"
    else
        fail "/status missing version key"
    fi
else
    fail "GET /status did not return a body"
fi

# 3. Jobs endpoint returns the seed list
echo "[3/6] Jobs list..."
JOBS_COUNT=$(curl -sf "${BASE_URL}/jobs" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' 2>/dev/null || echo "0")
if [ "$JOBS_COUNT" -ge 30 ]; then
    pass "GET /jobs returned ${JOBS_COUNT} jobs (expected >= 30)"
else
    fail "GET /jobs returned ${JOBS_COUNT} jobs (expected >= 30)"
fi

# 4. Candidates endpoint exists and returns 404 for unknown id
echo "[4/6] Candidates endpoint..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "${BASE_URL}/candidates/unknown-id" || true)
if [ "$HTTP_CODE" = "404" ]; then
    pass "GET /candidates/unknown-id returned 404 (expected)"
else
    fail "GET /candidates/unknown-id returned ${HTTP_CODE} (expected 404)"
fi

# 5. Match endpoint rejects missing candidate_id with 422
echo "[5/6] Match endpoint validation..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "${BASE_URL}/match" -H "Content-Type: application/json" -d '{}' || true)
if [ "$HTTP_CODE" = "422" ]; then
    pass "POST /match with empty body returned 422 (expected validation error)"
else
    fail "POST /match with empty body returned ${HTTP_CODE} (expected 422)"
fi

# 6. CORS — frontend served from a different origin should still work
echo "[6/6] CORS preflight..."
CORS_HEADERS=$(curl -sI -X OPTIONS "${BASE_URL}/status" \
    -H "Origin: https://example.com" \
    -H "Access-Control-Request-Method: GET" | grep -i "access-control-allow-origin" || true)
if [ -n "$CORS_HEADERS" ]; then
    pass "CORS headers present: ${CORS_HEADERS}"
else
    fail "CORS headers missing"
fi

echo
if [ "$FAILED" = "0" ]; then
    echo "=== ALL CHECKS PASSED ==="
    exit 0
else
    echo "=== SOME CHECKS FAILED ==="
    exit 1
fi
