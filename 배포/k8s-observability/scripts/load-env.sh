#!/usr/bin/env bash
# Usage: source scripts/load-env.sh
set -a
source "$(dirname "${BASH_SOURCE[0]}")/../environments/.env"
set +a
for key in S3_ENDPOINT S3_REGION S3_BUCKET LOKI_STORAGE_CLASS; do
  if [[ -z "${!key:-}" ]]; then echo "ERROR: $key is empty" >&2; return 1; fi
done
