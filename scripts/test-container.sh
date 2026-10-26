#!/bin/sh
# Smoke test of a built image: UI, REST, auth, MCP and a real synthesis in German and English.
#   CONTAINER=docker|podman (default podman)  PORT=host port (default 18000)
#   scripts/test-container.sh <image>
# The synthesis downloads the models (about 650 MB) into a throwaway volume.
set -eu

IMAGE=${1:?image}
CONTAINER=${CONTAINER:-podman}
PORT=${PORT:-18000}
NAME=restfultts-smoke-$$
TOKEN=smoke-$$
URL=http://127.0.0.1:$PORT
WORK=$(mktemp -d)

cleanup() {
	rc=$?
	[ $rc -ne 0 ] && $CONTAINER logs "$NAME" 2>&1 | tail -50
	$CONTAINER rm -f "$NAME" >/dev/null 2>&1 || true
	$CONTAINER volume rm -f "$NAME" >/dev/null 2>&1 || true
	rm -rf "$WORK"
	exit $rc
}
trap cleanup EXIT INT TERM

fail() {
	echo "FAIL: $*" >&2
	exit 1
}

# expect_status <code> <curl args...>
expect_status() {
	want=$1
	shift
	got=$(curl -s -o "$WORK/body" -w '%{http_code}' --max-time 600 "$@")
	[ "$got" = "$want" ] || fail "$* -> HTTP $got, expected $want: $(head -c 300 "$WORK/body")"
	echo "ok  $want $*"
}

$CONTAINER run -d --name "$NAME" -p "127.0.0.1:$PORT:8000" -v "$NAME:/data" \
	-e RESTFULTTS_API_TOKEN="$TOKEN" -e RESTFULTTS_PRELOAD= "$IMAGE" >/dev/null

i=0
until curl -sf -o /dev/null "$URL/static/app.css"; do
	i=$((i + 1))
	[ $i -lt 60 ] || fail "server not up after 60 s"
	sleep 1
done

AUTH="Authorization: Bearer $TOKEN"
expect_status 303 "$URL/"
expect_status 200 "$URL/login"
expect_status 401 "$URL/api/v1/health"
expect_status 200 -H "$AUTH" "$URL/api/v1/health"
expect_status 200 -H "$AUTH" "$URL/api/v1/voices?language=de"
grep -q '"thorsten"' "$WORK/body" || fail "voice thorsten missing"

MCP_HEADERS="-H Content-Type:application/json -H Accept:application/json,text/event-stream"
# shellcheck disable=SC2086
expect_status 401 $MCP_HEADERS -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' "$URL/mcp"
# shellcheck disable=SC2086
expect_status 200 $MCP_HEADERS -H "$AUTH" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' "$URL/mcp"
grep -q '"synthesize"' "$WORK/body" || fail "MCP tool synthesize missing"

expect_status 200 -H "$AUTH" -H 'Content-Type: application/json' -d '{"text": "Guten Tag und willkommen."}' "$URL/tts"
[ "$(head -c 4 "$WORK/body")" = RIFF ] || fail "/tts did not return WAV"
[ "$(wc -c <"$WORK/body")" -gt 48000 ] || fail "German WAV shorter than one second"

expect_status 200 -H "$AUTH" "$URL/api/v1/synthesize?text=Hello+and+welcome.&language=en&format=ulaw"
[ "$(wc -c <"$WORK/body")" -gt 8000 ] || fail "English u-law shorter than one second"

echo "smoke test passed"
