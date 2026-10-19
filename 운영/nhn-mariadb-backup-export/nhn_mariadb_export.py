#!/usr/bin/env python3
"""Export only the latest completed FULL RDS for MariaDB backup to NHN Cloud Gov Object Storage."""
import argparse
import base64
import fcntl
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RDS = "https://kr1-rds-mariadb.api.gov-nhncloudservice.com"
OAUTH = "https://oauth.api.gov-nhncloudservice.com/oauth2/token/create"
IDENTITY = "https://api-identity-infrastructure.gov-nhncloudservice.com/v2.0/tokens"
FAILED = {"FAILED", "ERROR", "COMPLETED_WITH_ERROR", "CANCELED", "INTERRUPTED",
          "FAIL_TO_READY", "FAIL_TO_REGISTER", "CANNOT_PROGRESS"}


def api(url, headers=None, method="GET", body=None):
    data = None if body is None else (
        body if isinstance(body, bytes) else json.dumps(body).encode()
    )
    req = urllib.request.Request(
        url, data=data, headers=headers or {}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            result = json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"HTTP {exc.code}: {method} {url.split('?')[0]}"
        ) from exc

    if isinstance(result, dict) and result.get("header", {}).get("isSuccessful") is False:
        raise RuntimeError(
            f"RDS API error: {result['header'].get('resultCode')}"
        )
    return result


def save_state(path, state):
    temp = path.with_suffix(".tmp")
    with open(temp, "w") as file:
        os.fchmod(file.fileno(), 0o600)
        json.dump(state, file)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temp, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    if config_path.stat().st_mode & 0o077:
        raise RuntimeError("Run chmod 600 on the config file")

    cfg = json.loads(config_path.read_text())
    state_path = config_path.with_suffix(".state.json")

    # 다른 실행이 끝날 때까지 동일 스크립트의 중복 실행을 막는다.
    with open(config_path.with_suffix(".lock"), "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "Another export run is still active"
            ) from exc

        state = (
            json.loads(state_path.read_text())
            if state_path.exists()
            else {"completed": [], "pending": None}
        )
        state.setdefault("completed", [])
        state.setdefault("pending", None)

        # 1. 실행할 때마다 RDS API용 토큰을 새로 발급받는다.
        pair = f"{cfg['user_access_key_id']}:{cfg['secret_access_key']}"
        basic = base64.b64encode(pair.encode()).decode()

        token = api(
            OAUTH,
            {
                "Authorization": "Basic " + basic,
                "Content-Type": "application/x-www-form-urlencoded"
            },
            "POST",
            b"grant_type=client_credentials"
        )["access_token"]

        headers = {
            "X-TC-APP-KEY": cfg["rds_appkey"],
            "X-NHN-AUTHORIZATION": "Bearer " + token,
            "Content-Type": "application/json"
        }

        def rds(path, method="GET", body=None):
            return api(RDS + path, headers, method, body)

        def verify_object(path):
            # Object Storage 조회용 IaaS 토큰을 별도로 발급받는다.
            auth = api(
                IDENTITY,
                {"Content-Type": "application/json"},
                "POST",
                {
                    "auth": {
                        "tenantId": cfg["storage_tenant_id"],
                        "passwordCredentials": {
                            "username": cfg["storage_username"],
                            "password": cfg["storage_api_password"]
                        }
                    }
                }
            )["access"]

            service = next(
                s for s in auth["serviceCatalog"]
                if s["type"] == "object-store"
            )
            endpoint = next(
                e["publicURL"] for e in service["endpoints"]
                if e["region"] == "KR1"
            )

            url = endpoint + "/" + urllib.parse.quote(
                cfg["storage_container"], safe=""
            )
            url += "?" + urllib.parse.urlencode({
                "prefix": path,
                "format": "json"
            })

            objects = api(
                url,
                {"X-Auth-Token": auth["token"]["id"]}
            )

            if not any(
                obj.get("name", "").startswith(path)
                and obj.get("bytes", 0) > 0
                for obj in objects
            ):
                raise RuntimeError(
                    f"No nonempty Object Storage object found under {path}"
                )

        def finish_pending():
            pending = state["pending"]
            if not pending:
                return

            job_id = pending["jobId"]
            print(
                f"Checking job {job_id} for backup {pending['backupId']}",
                flush=True
            )

            deadline = time.monotonic() + 7200

            while time.monotonic() < deadline:
                status = rds(
                    f"/v4.0/jobs/{job_id}"
                )["jobStatus"]

                if status == "COMPLETED":
                    verify_object(pending["objectPath"])

                    state["completed"].append(
                        pending["backupId"]
                    )
                    state["pending"] = None
                    save_state(state_path, state)

                    print(
                        f"Verified Object Storage object for "
                        f"{pending['backupId']}",
                        flush=True
                    )
                    return

                if status in FAILED:
                    state["pending"] = None
                    save_state(state_path, state)
                    raise RuntimeError(
                        f"Export job {job_id} ended with {status}"
                    )

                time.sleep(30)

            raise RuntimeError(
                f"Job {job_id} is still pending; "
                "rerun to resume checking it"
            )

        # 2. 이전 실행에서 시작한 작업이 있으면 먼저 확인한다.
        finish_pending()

        # 3. DB 인스턴스의 자동 백업 목록을 전부 조회한다.
        backups = []
        page = 1

        while True:
            query = urllib.parse.urlencode({
                "dbInstanceId": cfg["db_instance_id"],
                "backupType": "AUTO",
                "page": page,
                "size": 100
            })

            response = rds(
                "/v4.0/backups?" + query
            )
            backups += response.get("backups", [])

            if (
                len(backups) >= response.get("totalCounts", len(backups))
                or not response.get("backups")
            ):
                break

            page += 1

        # 4. 완료된 FULL 자동 백업 중 최신 1개만 선택한다.
        for item in sorted(
            backups,
            key=lambda b: b.get("createdYmdt", ""),
            reverse=True
        ):
            backup_id = item["backupId"]

            if item.get("backupStatus") != "COMPLETED":
                continue

            detail = rds(
                "/v4.0/backups/" + backup_id
            )["backup"]

            if detail.get("backupMethodType") != "FULL":
                continue

            # 최신 FULL 백업이 이미 처리됐다면 과거 백업으로 넘어가지 않는다.
            if backup_id in state["completed"]:
                print(
                    f"Latest completed FULL automatic backup already exported: "
                    f"{backup_id}",
                    flush=True
                )
                return

            path = (
                cfg.get("storage_prefix", "mariadb-rds").strip("/")
                + "/" + backup_id
            )

            body = {
                "tenantId": cfg["storage_tenant_id"],
                "username": cfg["storage_username"],
                "password": cfg["storage_api_password"],
                "targetContainer": cfg["storage_container"],
                "objectPath": path
            }

            job_id = rds(
                f"/v4.0/backups/{backup_id}/export",
                "POST",
                body
            )["jobId"]

            state["pending"] = {
                "backupId": backup_id,
                "jobId": job_id,
                "objectPath": path
            }
            save_state(state_path, state)

            print(
                f"Started export: backup={backup_id}, job={job_id}",
                flush=True
            )
            finish_pending()
            print("Latest completed FULL automatic backup processed")
            return

        print("No completed FULL automatic backup found")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
