# NHN Cloud 공공 RDS for MariaDB 로그 백업

## 개요

RDS for MariaDB의 Error, General, Audit, Binary Log를 API로 조회하고 Object Storage로 내보내는 Bash 스크립트다. Rocky Linux를 기준으로 하며, 환경별 설정값은 `.env`로 분리한다.

## 인증 및 백업 처리 흐름

RDS 로그 목록 조회와 내보내기 API를 호출할 때는 RDS Appkey와 인증 토큰이 필요하다. 스크립트는 실행할 때마다 `.env`에 입력한 User Access Key ID와 Secret Access Key로 토큰을 자동 발급받아 사용한다. 토큰을 직접 발급하거나 저장해 둘 필요는 없다.

인증 후 대상 DB 인스턴스의 로그 목록을 조회하고 Error, General, Audit Log와 `mysql-bin.숫자` 형식의 Binary Log를 선택한다. 선택한 파일 목록과 Object Storage 인증정보, 컨테이너, 저장 경로를 RDS 로그 내보내기 API에 전달한다.

실제 로그 파일은 RDS 서비스에서 Object Storage로 내보낸다. 실행 서버는 인증과 API 호출만 수행한다. 저장 경로에는 실행 시점의 한국 날짜(`YYYY/MM/DD`)를 붙인다.

예를 들어 `OBJ_CONTAINER="log"`, `OBJ_BACKUP_PREFIX="db_log_backup"`이면 `log` 컨테이너의 `db_log_backup/2026/10/19/` 경로로 내보내기를 요청한다.

이 코드는 최신 로그 1개만 선택하는 방식이 아니라, 조회 응답에 포함된 대상 로그를 모두 선택한다. 성공 메시지와 Job ID는 **내보내기 요청이 접수됐다는 의미**이며, 작업 완료와 실제 객체 저장 여부는 별도로 확인해야 한다.

## 파일 구성

| 파일 | 용도 |
|---|---|
| `rds_mariadb_log_backup.sh` | 인증 토큰 발급, 로그 목록 조회 및 내보내기 요청 |
| `.env.example` | 환경 설정 예시. `.env`로 복사한 뒤 실제 값 입력 |
| `.gitignore` | 실제 `.env`와 실행 로그의 Git 추적 제외 |

## 환경 설정값

대상 Object Storage 컨테이너는 미리 생성해 둔다. 수집하려는 로그가 RDS에서 생성되고 있어야 한다.

```bash
cp .env.example .env
chmod 600 .env
vi .env
```

| 항목 | 실제 넣을 값 |
|---|---|
| `RDS_API_URL` | 공공 KR1 기준 `https://kr1-rds-mariadb.api.gov-nhncloudservice.com`. DB 접속 주소가 아닌 RDS 관리 API 주소 |
| `RDS_DB_INSTANCE_ID` | 로그를 내보낼 DB 인스턴스 UUID. DB 이름이나 접속 IP가 아님 |
| `RDS_APP_KEY` | 대상 프로젝트 RDS for MariaDB의 Appkey |
| `RDS_USER_ACCESS_KEY_ID` | NHN Cloud 공공 계정의 API 보안 설정에서 발급한 User Access Key ID |
| `RDS_SECRET_ACCESS_KEY` | 위 User Access Key ID와 함께 발급된 Secret Access Key |
| `OBJ_TENANT_ID` | 대상 Object Storage의 API 엔드포인트 설정에서 확인한 테넌트 ID |
| `OBJ_USERNAME` | Object Storage에 접근할 NHN Cloud 계정 ID 또는 IAM 계정 ID. User Access Key ID가 아님 |
| `OBJ_PASSWORD` | Object Storage API 비밀번호. 계정 로그인 비밀번호나 Secret Access Key가 아님 |
| `OBJ_CONTAINER` | 백업을 저장할 기존 Object Storage 컨테이너 이름. 예: `log` |
| `OBJ_BACKUP_PREFIX` | 컨테이너 내부의 로그 저장 경로. 예: `db_log_backup`. 앞뒤에 `/`와 날짜를 넣지 않음 |

실제 인증정보를 입력한 `.env`는 GitHub에 올리지 않는다. 토큰 발급 주소는 코드에 공공 환경 주소로 지정되어 있으므로 다른 환경에서 재사용할 때는 해당 주소도 확인한다.

## 실행

아래는 폴더를 `/home/rocky/rds-mariadb-log-backup`에 둔 경우다. 경로가 다르면 명령과 cron의 경로도 같이 변경한다.

Rocky Linux에서 필요한 도구를 준비한다. `curl`은 `--fail-with-body` 옵션을 지원하는 버전(7.76.0 이상)이 필요하다.

```bash
sudo dnf install -y curl python3
curl --version
```

환경 설정값을 입력한 뒤 실행한다.

```bash
cd /home/rocky/rds-mariadb-log-backup
chmod 600 .env
chmod 700 rds_mariadb_log_backup.sh
./rds_mariadb_log_backup.sh
```

출력된 Job ID와 저장 경로를 확인하고 Object Storage 콘솔에서 실제 로그 객체가 저장됐는지 확인한다.

## cron으로 매일 실행

서버 시간과 cron 서비스 상태를 확인한 뒤 등록한다.

```bash
date
systemctl status crond
crontab -e
```

매일 02:00에 실행하려면 아래 한 줄을 추가한다. 실행 시각은 서버의 cron 시간대 기준이다.

```cron
0 2 * * * /bin/bash /home/rocky/rds-mariadb-log-backup/rds_mariadb_log_backup.sh >> /home/rocky/rds-mariadb-log-backup/backup.log 2>&1
```

등록 내용과 실행 로그를 확인한다.

```bash
crontab -l
tail -n 50 /home/rocky/rds-mariadb-log-backup/backup.log
```

매일 실행할 때 새 토큰을 발급받아 당일 날짜 경로로 내보내기를 요청한다. 처리 이력 저장과 중복 실행 방지는 포함되어 있지 않으므로, 재실행하면 같은 로그도 다시 요청할 수 있다.

## 참고 문서

- [RDS for MariaDB API v4.0](https://docs.gov-nhncloud.com/ko/Database/RDS%20for%20MariaDB/ko/api-guide-v4.0-gov/)
- [User Access Key 토큰 발급](https://docs.gov-nhncloud.com/ko/nhncloud/ko/public-api/user-access-key-token-gov/)
