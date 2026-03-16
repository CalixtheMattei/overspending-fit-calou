#!/usr/bin/env bash
# Upload a profile avatar image to a running instance via the API.
#
# Usage:
#   ./scripts/deploy_avatar.sh <image-file> [api-base-url]
#
# Examples:
#   # VPS production instance
#   ./scripts/deploy_avatar.sh ~/avatar.jpg https://overspending-fit-calou.com/api
#
#   # Demo instance
#   ./scripts/deploy_avatar.sh ~/avatar.jpg https://demo.overspending-fit-calou.com/api
#
#   # Local dev
#   ./scripts/deploy_avatar.sh ~/avatar.jpg http://localhost:8000
#
# The script calls POST /profile/avatar (multipart upload).
# It does NOT require authentication — protect the endpoint at the network level
# (e.g. only run this from the VPS itself, or behind a VPN).

set -euo pipefail

IMAGE_FILE="${1:-}"
API_BASE="${2:-http://localhost:8000}"

if [[ -z "$IMAGE_FILE" ]]; then
  echo "Usage: $0 <image-file> [api-base-url]" >&2
  exit 1
fi

if [[ ! -f "$IMAGE_FILE" ]]; then
  echo "Error: file not found: $IMAGE_FILE" >&2
  exit 1
fi

ENDPOINT="${API_BASE%/}/profile/avatar"

echo "Uploading avatar '$(basename "$IMAGE_FILE")' to $ENDPOINT ..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$ENDPOINT" \
  -F "file=@${IMAGE_FILE}")

if [[ "$HTTP_CODE" == "200" ]]; then
  echo "Done — avatar uploaded successfully (HTTP $HTTP_CODE)."
else
  echo "Error: unexpected HTTP status $HTTP_CODE." >&2
  exit 1
fi
