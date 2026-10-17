# NHN Cloud 공공 NKS — Logstash DaemonSet 로그 수집

Kubernetes Worker Node마다 Logstash Pod를 1개씩 실행하고, **하나의 Logstash Pipeline**에서 컨테이너·Linux 시스템·auditd 로그를 읽어 **NHN Cloud 공공 Log & Crash Search**로 전송하는 실습 프로젝트다.

> **배포 전 확인:** 아래 설정은 실제 Worker OS, CRI 로그 샘플, NKS의 보안 제약, NHN 네트워크 연결을 아직 확인하지 않은 **실습용 초안**이다. 운영 배포 전 스테이징에서 검증한다.

## 1. 아키텍처

```text
Worker Node 1                     Worker Node 2
/var/log/pods/...                 /var/log/pods/...
/var/log/auth.log|secure          /var/log/auth.log|secure
/var/log/syslog|messages          /var/log/syslog|messages
/var/log/audit/audit.log          /var/log/audit/audit.log
       |                                  |
  Logstash Pod                       Logstash Pod
  (DaemonSet)                        (DaemonSet)
       |                                  |
       +----------- HTTPS POST -----------+
                       |
       NHN 공공 Log & Crash Search /v2/log
```

DaemonSet은 Worker Node별 Logstash 실행을 보장하는 Kubernetes 리소스다. ConfigMap은 Pipeline 설정을 종류별로 관리한다. **ConfigMap이 8개여도 Pipeline은 1개**다. DaemonSet의 `projected` Volume이 `.conf` 8개를 같은 디렉터리에 합쳐 마운트하고 Logstash가 함께 읽는다.

## 2. 디렉터리 구조

```text
logstash-nks-project/
├── README.md
└── kubernetes/
    ├── namespace.yaml
    ├── secret.yaml.example
    ├── daemonset.yaml
    └── configmaps/
        ├── input/
        │   ├── container-input.yaml
        │   ├── system-input.yaml
        │   └── auditd-input.yaml
        ├── filter/
        │   ├── container-filter.yaml
        │   ├── system-filter.yaml
        │   ├── auditd-filter.yaml
        │   └── common-filter.yaml
        └── output/
            └── nhn-output.yaml
```

각 파일은 ConfigMap 하나를 정의한다. 내부의 `.conf` 파일은 `10-...`, `20-...` 순서로 구성한다. Logstash는 Input, Filter, Output 단계로 이벤트를 처리하며 각 Filter는 `[@metadata][log_kind]` 조건으로 자신에게 해당하는 로그만 처리한다. `@metadata`는 전송 JSON에 포함하지 않는다.

## 3. Input 설계

| 구분 | 호스트의 원래 경로 | Logstash 컨테이너 내부 경로 |
|---|---|---|
| Container | `/var/log/pods/*/*/*.log` | `/host/var/log/pods/*/*/*.log` |
| System auth | `/var/log/auth.log` 또는 `/var/log/secure` | `/host/var/log/...` |
| System general | `/var/log/syslog` 또는 `/var/log/messages` | `/host/var/log/...` |
| Auditd | `/var/log/audit/audit.log` | `/host/var/log/audit/audit.log` |

호스트 `/var/log`를 읽기 전용으로 `/host/var/log`에 마운트한다. 실제 파일이 없으면 수집하지 않는다. **journald 전용 OS**에서 위 파일이 생성되지 않는다면 별도의 journald 수집 설계가 필요하다. 컨테이너 로그는 Pod가 stdout/stderr에 기록한 것만 수집한다. 애플리케이션이 NAS/파일에만 쓰는 로그는 이 설정으로 수집되지 않는다.

각 Input은 내부적으로 `[@metadata][log_kind]`를 `container`, `system`, `auditd`로 지정한다. `sincedb`는 노드별 `/var/lib/logstash-agent`에 보존하므로 Pod 재시작 시 읽기 위치를 재사용할 수 있다. `start_position => "beginning"`은 **sincedb가 없는 파일을 처음 발견했을 때** 적용된다.

## 4. Filter 설계

### 공통 필드

| 필드 | 의미 |
|---|---|
| `timestamp` | Logstash 이벤트 시각 문자열. 원본 로그 시각 파싱에 실패하면 수집 시각 |
| `logSource` | 로그 발생 워크로드/시스템 |
| `logType` | `access`, `auth`, `audit`, `syslog`, `container` 등 |
| `sourceHost` | 실제 Worker Node 이름 (`spec.nodeName`) |
| `body` | 원본 로그 메시지 |
| `projectName`, `projectVersion`, `logVersion` | NHN 수집 API용 필수 필드 |

### Container Filter

CRI 포맷에서 `stream`을 추출하고, 파일 경로에서 `namespace`와 `podName`을 추출한다. `containerName`은 저장하지 않는다.

**중요:** `podName`은 Kubernetes 원래 Pod 이름 전체가 아니라 **Deployment 형태의 두 접미사**(`-replicasetHash-random`)를 제거한 워크로드 식별명으로 사용한다. StatefulSet/Job/직접 생성 Pod는 접미사 제거 없이 원래 이름이 남을 수 있다. 워크로드 이름이 우연히 같은 규칙을 만족하면 잘못 잘릴 가능성이 있으므로 실환경에서 검증해야 한다.

HTTP access 로그가 기본 Nginx combined 형식과 일치할 때에만 `clientIp`, `httpMethod`, `requestPath`, `statusCode`를 추출하고 `logType=access`로 지정한다. Tomcat AccessLogValve 형식이나 JSON 애플리케이션 로그는 실제 샘플을 보고 패턴을 추가해야 한다. `stdout=access`, `stderr=error`라고 단정하지 않는다.

### System Filter

파일 경로로 `auth`와 `syslog`를 구분한다. SSH의 `Accepted`/`Failed` 패턴이 일치하면 `userName`, `sourceIp`, `eventOutcome`을 추출한다. syslog 헤더가 일치하면 `processName`을 추출한다. OS 및 sshd 설정에 따라 로그 문법이 달라질 수 있다.

### Auditd Filter

`auditType`, `auditId`, `userId`, `auditUserId`, `processName`, `eventOutcome`을 가능한 경우에만 추출한다. `command`는 예시 구현에서 `exe="..."` 경로를 담으며 **실제 명령행 전체를 복원하지 않는다**. `EXECVE`의 `a0`, `a1` 등을 조합하거나 동일 `auditId`의 여러 레코드를 결합하는 기능은 **미구현**이다. 모든 원본 행은 `body`에 보존한다.

### NHN 사용자 정의 필드 주의

NHN 공식 API 문서에는 사용자 정의 필드 이름이 영문자로 시작해야 하고, 사용할 수 있는 문자가 제한된다고 명시돼 있다. 그래서 `@timestamp`, `@version` 등 Logstash 내부 필드는 Output 전에 제거한다. 일반 사용자 정의 필드는 **정확 일치 검색**이 기본이고, 긴 문자열/부분 검색은 NHN 문서의 `txt*` 접두어 규칙을 별도로 검토해야 한다. 원본 검색에 필요한 `body`는 공식 기본 필드로 유지한다.

## 5. Output 설계

모든 이벤트를 하나의 HTTP Output으로 전송한다.

- **주소:** `https://api-logncrash.gov-nhncloudservice.com/v2/log`
- **방식:** POST, `application/json`, 이벤트당 JSON 1건
- **필수 값:** `projectName`=Log & Crash Search Appkey, `projectVersion`=`1.0.0`, `logVersion`=`v2`
- **Appkey 관리:** Kubernetes Secret `nhn-logncrash`, key `appkey`; 환경 변수 `NHN_LNC_APPKEY`로 전달
- **전송 실패:** HTTP Output 재시도 + Logstash Persistent Queue를 사용하지만 **완전 무손실을 보장하지 않는다**.

**중요한 한계:** NHN API는 HTTP 200 응답 본문에 `header.isSuccessful=false`를 반환할 수 있다. 일반 Logstash HTTP Output은 이 비즈니스 성공 필드를 자동으로 검증하지 않으므로, 운영 적용 시 별도의 응답 검증·실패 감시 체계를 고려해야 한다.

참고 공식 문서:
- [NHN 공공 Log & Crash Search API 가이드](https://docs.gov-nhncloud.com/ko/Data%20%26%20Analytics/Log%20%26%20Crash%20Search/ko/gov-api-guide/)
- [NHN 공공 Logstash SDK 사용 가이드](https://docs.gov-nhncloud.com/ko/Data%20%26%20Analytics/Log%20%26%20Crash%20Search/ko/gov-logstash-sdk-guide/)

## 6. 배포 전 점검

**6-1. Worker Node 로그 경로 확인**

```bash
# Worker Node에서 직접 실행
sudo ls -ld /var/log/pods /var/log/audit
sudo ls -l /var/log/auth.log /var/log/secure /var/log/syslog /var/log/messages 2>/dev/null
sudo ls -l /var/log/audit/audit.log 2>/dev/null
sudo find /var/log/pods -name '*.log' | head
```

NKS 관리형 Worker에서 노드 직접 접속이 제한되면 노드 진단 절차를 따르거나 별도 테스트 Pod를 활용한다. Auditd가 설치/활성화되지 않았으면 해당 파일은 존재하지 않는다.

**6-2. Log & Crash Search 프로젝트 및 네트워크**

NHN Cloud 공공 콘솔에서 Log & Crash Search 프로젝트를 준비하고 **Appkey**를 확인한다. Worker에서 공공 수집 엔드포인트에 대한 DNS, HTTPS 443 아웃바운드 경로가 필요하다. 실제 Appkey를 Git/블로그에 올리지 않는다.

**6-3. 호스트 저장소 및 권한**

DaemonSet은 호스트의 `/var/log`를 읽고 `/var/lib/logstash-agent`에 sincedb와 Persistent Queue를 저장한다. 호스트 경로를 생성할 수 있는 권한, Logstash 프로세스의 파일 읽기/쓰기 권한을 확인해야 한다. **공식 Logstash 이미지의 기본 실행 UID가 호스트 로그 파일을 읽지 못할 수 있다.** Pod를 무조건 privileged/root로 설정하지 말고 NKS 보안 정책과 실제 파일 권한에 맞춰 최소 권한을 구성한다.

## 7. 배포 절차

```bash
kubectl apply -f kubernetes/namespace.yaml

# Secret 예시 YAML을 그대로 apply 하지 않는다.
# 셸 히스토리에 Appkey를 남기지 않도록 대화형 입력을 사용한다.
read -rs -p 'NHN Log & Crash Search Appkey: ' NHN_APPKEY; echo
kubectl -n logging create secret generic nhn-logncrash \
  --from-literal=appkey="$NHN_APPKEY"
unset NHN_APPKEY

kubectl apply -f kubernetes/configmaps/input/
kubectl apply -f kubernetes/configmaps/filter/
kubectl apply -f kubernetes/configmaps/output/
kubectl apply -f kubernetes/daemonset.yaml
```

기존 Secret이 있으면 생성 명령은 실패하므로 갱신 작업은 별도로 수행한다. **Secret 값은 Kubernetes API/etcd에 저장되므로 RBAC와 암호화 설정도 확인한다.**

## 8. 배포 상태 및 로그 확인

```bash
kubectl -n logging get ds logstash-agent -o wide
kubectl -n logging get pods -l app=logstash-agent -o wide
kubectl -n logging describe ds logstash-agent
kubectl -n logging logs -l app=logstash-agent --all-containers=true --tail=100 --prefix=true
```

Pipeline 문법/설정 확인은 다음처럼 Pod 내부에서 실행할 수 있다. 다만 실행 중인 Pod의 설정과 동일한 환경 변수 및 파일을 사용해야 한다.

```bash
POD=$(kubectl -n logging get pod -l app=logstash-agent -o jsonpath='{.items[0].metadata.name}')
kubectl -n logging exec "$POD" -- \
  /usr/share/logstash/bin/logstash -t -f /usr/share/logstash/pipeline
```

**검증 순서:** DaemonSet Ready 확인 → 로그 파일 읽기 권한 확인 → Logstash 오류/재시도 확인 → 테스트 HTTP/SSH/auditd 로그 생성 → NHN Cloud 콘솔에서 `logSource`, `logType`, `sourceHost`, `body` 검색.

필터 테스트 시에는 실제 로그 샘플과 예상 필드를 비교한다. HTTP Output은 정상 연결이라도 응답 본문의 수집 성공 여부를 확인하지 못할 수 있으므로 NHN 콘솔에서 수신 여부까지 검증해야 한다.

## 9. ConfigMap 변경

```bash
kubectl apply -f kubernetes/configmaps/input/
kubectl apply -f kubernetes/configmaps/filter/
kubectl apply -f kubernetes/configmaps/output/
kubectl -n logging rollout restart daemonset/logstash-agent
```

Logstash Pipeline 자동 리로드를 별도 설정하지 않았으므로 **ConfigMap 변경 후 Pod 재시작**을 수행한다.

## 10. 운영 적용 전에 보완할 사항

1. **권한 검증:** 기본 Logstash 컨테이너 UID로 호스트 auditd/secure 로그를 읽을 수 있는지 확인. NKS의 Pod Security, SELinux/AppArmor 정책 점검.
2. **실제 포맷 확인:** Nginx/Tomcat access/error, syslog, auditd 샘플에 맞게 Grok 패턴 조정.
3. **CRI 부분 로그:** CRI `P`(partial) 레코드는 현재 재조합하지 않는다. 긴 메시지는 분리된 채 저장될 수 있다.
4. **큐/위치 관리:** 노드 로컬 `/var/lib/logstash-agent`는 노드 교체 시 함께 소실될 수 있다. 디스크 용량/큐 크기/재시도 정책과 보관 정책을 별도로 정한다.
5. **로그 회전:** OS 로그 rotation, auditd rotation, inode 재사용 시 중복/누락 검증.
6. **스케줄링:** 노드 taint/toleration 및 Worker Node 종류를 확인. 필요 시 nodeSelector, tolerations 추가.
7. **전송 성공 판정:** HTTP 2xx만으로 NHN 수집 성공을 단정하지 않는다.
8. **민감정보:** 인증 로그, IP, 사용자명, 명령행 등에 개인정보/비밀정보가 포함되지 않도록 마스킹·접근제어 정책 적용.
9. **버전 검증:** Logstash 8.17.0 이미지의 플러그인 및 CLI 옵션, Pipeline 문법을 테스트 환경에서 먼저 검증.

## 11. 구성 요소별 역할

| 파일 | 역할 |
|---|---|
| `namespace.yaml` | logging 네임스페이스 생성 |
| `secret.yaml.example` | Appkey Secret 작성 예시 (실제 키 미포함) |
| `daemonset.yaml` | 노드별 Logstash 배포, ConfigMap 병합 마운트, 호스트 로그/데이터 마운트 |
| `*-input.yaml` | 파일 입력 경로 및 내부 `log_kind` 지정 |
| `*-filter.yaml` | 로그별 파싱, 필드 추출, 공통 NHN API 필드 추가 |
| `nhn-output.yaml` | 공공 Log & Crash Search 수집 API로 HTTPS POST |
