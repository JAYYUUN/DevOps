#!/usr/bin/env bash
set -euo pipefail
umask 077

# 1. 환경변수 로드
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
source "${SCRIPT_DIR}/.env"
set +a

# 2. 날짜별 저장 경로
BACKUP_DATE="$(TZ=Asia/Seoul date +%Y/%m/%d)"
OBJECT_PATH="${OBJ_BACKUP_PREFIX%/}/${BACKUP_DATE}"
export OBJECT_PATH

# 3. 인증 토큰 발급
AUTH_CONFIG=$(python3 - <<'PY'
import json, os
credentials = (
    os.environ["RDS_USER_ACCESS_KEY_ID"]
    + ":" +
    os.environ["RDS_SECRET_ACCESS_KEY"]
)
print("user = " + json.dumps(credentials))
PY
)

TOKEN_RESPONSE=$(printf '%s\n' "$AUTH_CONFIG" | curl \
    --fail-with-body -sS --config - \
    -X POST \
    "https://oauth.api.gov-nhncloudservice.com/oauth2/token/create" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    --data-urlencode "grant_type=client_credentials")

unset AUTH_CONFIG

RDS_ACCESS_TOKEN=$(printf '%s' "$TOKEN_RESPONSE" | python3 -c '
import json, sys
data = json.load(sys.stdin)
token = data.get("access_token")
if not token:
    sys.exit("[ERROR] 토큰 발급 실패")
print(token)
')

# 4. RDS 로그 파일 목록 조회
RESPONSE=$(curl --fail-with-body -sS \
    "${RDS_API_URL%/}/v4.0/db-instances/${RDS_DB_INSTANCE_ID}/log-files" \
    -H "X-TC-APP-KEY: ${RDS_APP_KEY}" \
    -H "X-NHN-AUTHORIZATION: Bearer ${RDS_ACCESS_TOKEN}")

# 5. 백업 대상 선택 및 요청 데이터 생성
REQUEST=$(printf '%s' "$RESPONSE" | python3 -c '
import json, os, re, sys

data = json.load(sys.stdin)

if not data.get("header", {}).get("isSuccessful"):
    sys.exit("[ERROR] 로그 목록 조회 실패")

files = []

for item in data.get("logFiles", []):
    name = item.get("logFileName", "")
    log_type = item.get("logFileType", "")

    if log_type in ("AUDIT", "GENERAL", "ERROR") and name:
        files.append(name)
    elif log_type == "BINLOG" and re.fullmatch(r"mysql-bin\.[0-9]+", name):
        files.append(name)

files = list(dict.fromkeys(files))

if not files:
    sys.exit("[ERROR] 백업할 로그가 없습니다.")

print("[INFO] 백업 대상: " + ", ".join(files), file=sys.stderr)

print(json.dumps({
    "logFileNames": files,
    "tenantId": os.environ["OBJ_TENANT_ID"],
    "username": os.environ["OBJ_USERNAME"],
    "password": os.environ["OBJ_PASSWORD"],
    "targetContainer": os.environ["OBJ_CONTAINER"],
    "objectPath": os.environ["OBJECT_PATH"]
}))
')

# 6. Object Storage로 로그 내보내기
RESULT=$(printf '%s' "$REQUEST" | curl \
    --fail-with-body -sS \
    -X POST \
    "${RDS_API_URL%/}/v4.0/db-instances/${RDS_DB_INSTANCE_ID}/log-files/export" \
    -H "X-TC-APP-KEY: ${RDS_APP_KEY}" \
    -H "X-NHN-AUTHORIZATION: Bearer ${RDS_ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary @-)

# 7. 결과 확인
printf '%s' "$RESULT" | python3 -c '
import json, sys
data = json.load(sys.stdin)

if not data.get("header", {}).get("isSuccessful"):
    sys.exit("[ERROR] 로그 내보내기 요청 실패")

print("[INFO] 로그 내보내기 요청 성공")
print("[INFO] Job ID:", data.get("jobId", "없음"))
'

echo "[INFO] 저장 경로: ${OBJ_CONTAINER}/${OBJECT_PATH}"
