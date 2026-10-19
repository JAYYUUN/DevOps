# NHN Cloud 공공 RDS for MariaDB 최신 백업 내보내기

## 개요

RDS에서 생성한 자동 백업 중 완료된 FULL 백업의 최신 1개를 자동으로 Object Storage로 내보내는 코드다. RDS 자동 백업은 미리 설정해 두어야 한다.

## 인증 및 백업 처리 흐름

RDS의 백업 목록을 조회하고 Object Storage로 내보내려면 RDS API를 호출해야 한다. 이때 요청을 인증하기 위해 RDS Appkey와 임시 인증 토큰을 사용한다.

토큰은 코드가 실행될 때 JSON에 입력한 User Access Key ID와 Secret Access Key로 자동 발급받는다. 발급받은 토큰으로 백업 목록 조회, 내보내기 요청, 작업 상태 조회를 진행한다. cron으로 매일 실행하면 실행할 때마다 새 토큰을 받으므로 토큰을 직접 발급하거나 JSON에 넣을 필요는 없다. User Access Key ID와 Secret Access Key는 미리 발급받아 JSON에 입력해 둔다.

인증이 끝나면 대상 DB 인스턴스의 자동 백업 목록에서 완료된 FULL 백업 중 가장 최신 1개를 선택한다. 이미 내보낸 백업이면 종료하고, 아직 처리하지 않은 백업이면 RDS 내보내기 API를 호출한다.

내보내기 요청에는 백업 ID와 Object Storage의 인증정보, 컨테이너 이름, 저장 경로를 전달한다. RDS가 해당 백업을 Object Storage로 내보내며, Python 실행 서버가 백업 파일을 내려받아 다시 업로드하는 방식은 아니다.

코드는 내보내기 작업의 완료 상태를 확인한 뒤, Object Storage에 객체가 저장됐는지 조회한다. 이 조회에는 별도의 인증이 필요하므로 JSON의 Object Storage 계정 ID와 API 비밀번호로 Object Storage용 토큰을 자동 발급받아 사용한다. 대상 경로로 시작하는 0바이트 초과 객체가 확인되면 해당 백업을 처리한 것으로 기록한다. 백업의 무결성과 복원 가능 여부는 별도로 검증해야 한다.

처리 기록은 `nhn-mariadb-export.state.json`에 저장해 다음 실행에서 중복 처리를 막는다. 이전에 진행하던 작업이 있으면 먼저 이어서 확인한다. 과거의 미처리 백업은 건너뛰며, Object Storage에 저장된 기존 백업은 삭제하지 않는다.

## JSON 설정값

`nhn-mariadb-export.example.json`을 `nhn-mariadb-export.json`으로 복사한 뒤 아래 값을 입력합니다.

| 항목 | 정확히 넣을 값 |
| --- | --- |
| `user_access_key_id` | NHN Cloud 공공 계정의 API 보안 설정에서 발급한 **User Access Key ID** |
| `secret_access_key` | 위 User Access Key ID와 함께 발급된 **Secret Access Key** |
| `rds_appkey` | 백업 대상 프로젝트의 **RDS for MariaDB Appkey** |
| `db_instance_id` | 백업 대상 **DB 인스턴스 UUID**. 접속 IP나 DB 인스턴스 그룹 ID가 아님 |
| `storage_tenant_id` | 대상 Object Storage의 API 엔드포인트 설정에서 확인한 **테넌트 ID** |
| `storage_username` | Object Storage에 접근할 **NHN Cloud 계정 ID 또는 IAM 계정 ID**. User Access Key ID가 아님 |
| `storage_api_password` | Object Storage의 API 엔드포인트 설정에서 설정한 **API 비밀번호**. 계정 로그인 비밀번호나 Secret Access Key가 아님 |
| `storage_container` | 백업을 저장할 **기존 Object Storage 컨테이너 이름** |
| `storage_prefix` | 컨테이너 내부의 백업 저장 경로. 예: `mariadb-rds`로 설정하면 `mariadb-rds/{backupId}` 경로에 저장 |

실제 인증정보를 입력한 JSON 파일은 GitHub에 올리지 않습니다. 설정 파일 권한은 `chmod 600 nhn-mariadb-export.json`으로 지정합니다.

## 실행 및 cron 설정

아래는 파일을 `/home/ubuntu/nhn-mariadb-backup-export`에 둔 경우다. 경로가 다르면 명령도 같이 변경한다.

설정값 입력 후 먼저 직접 실행해 본다.

```bash
cd /home/ubuntu/nhn-mariadb-backup-export
chmod 600 nhn-mariadb-export.json
python3 nhn_mariadb_export.py --config nhn-mariadb-export.json
```

정상 실행을 확인한 뒤 서버 시간과 Python 경로를 확인하고 로그 폴더를 만든다.

```bash
date
command -v python3
mkdir -p /home/ubuntu/nhn-mariadb-backup-export/logs
crontab -e
```

매일 06:00에 실행하려면 아래 한 줄을 등록한다. 시간은 서버의 cron 시간대 기준이며, RDS 자동 백업이 완료된 이후로 잡는다. Python 경로는 위에서 확인한 값에 맞춘다.

```cron
0 6 * * * /usr/bin/python3 /home/ubuntu/nhn-mariadb-backup-export/nhn_mariadb_export.py --config /home/ubuntu/nhn-mariadb-backup-export/nhn-mariadb-export.json >> /home/ubuntu/nhn-mariadb-backup-export/logs/nhn-mariadb-export.log 2>&1
```

등록 내용과 실행 로그는 아래 명령으로 확인한다.

```bash
crontab -l
tail -n 50 /home/ubuntu/nhn-mariadb-backup-export/logs/nhn-mariadb-export.log
```
