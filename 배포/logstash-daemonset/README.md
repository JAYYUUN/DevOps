# Kubernetes 로그 수집 — Logstash DaemonSet

Kubernetes 환경에서 발생하는 **컨테이너 로그와 Worker Node의 시스템 로그**를 Logstash로 수집하는 구성이다. Logstash를 DaemonSet으로 배포해 각 Worker Node의 로그 파일을 직접 읽고, 필요한 정보를 추출한 뒤 출력한다. 기본 구성은 `stdout`으로 결과를 확인하며, 필요하면 **NHN Cloud 공공 Log & Crash Search**로 전송하도록 변경할 수 있다.

## 1. 로그 수집 구조

Kubernetes에서 컨테이너가 표준 출력(`stdout`)과 표준 오류(`stderr`)로 기록한 로그는 일반적으로 Worker Node의 `/var/log/pods`에 저장된다. 운영체제의 인증 및 시스템 로그는 `/var/log/auth.log`, `/var/log/syslog` 등의 파일에 기록될 수 있다.

이 구성에서는 별도의 NAS나 중계 서버를 거치지 않고, **각 노드에 배포된 Logstash가 해당 노드의 로그를 직접 수집**한다.

```text
Worker Node
├── /var/log/pods/.../*.log     ── 컨테이너 로그
├── /var/log/auth.log          ── 인증 로그
├── /var/log/syslog            ── 시스템 로그
└── /var/log/audit/audit.log   ── 감사 로그 (존재하는 경우)
              │
              ▼
      Logstash DaemonSet
       Input → Filter → Output
              │
       ┌──────┴─────────┐
       ▼                ▼
   stdout (기본)    NHN Cloud Log & Crash Search (선택)
```

### DaemonSet을 사용하는 이유

DaemonSet은 대상 Worker Node마다 Pod를 실행하도록 관리한다. 따라서 Logstash를 DaemonSet으로 구성하면 **각 노드에 저장된 로그를 해당 노드의 Logstash Pod가 수집**할 수 있다. 새 Worker Node가 추가되면 배포 조건에 따라 Logstash Pod도 함께 배치된다.

## 2. 수집 대상

| 로그 | Worker Node의 대표 경로 | 용도 |
|---|---|---|
| 컨테이너 | `/var/log/pods/*/*/*.log` | 애플리케이션 stdout/stderr |
| 인증 | `/var/log/auth.log`, `/var/log/secure` | SSH, PAM, 로그인 관련 기록 |
| 시스템 | `/var/log/syslog`, `/var/log/messages` | 운영체제 및 서비스 메시지 |
| auditd | `/var/log/audit/audit.log` | OS 감사 이벤트 |

운영체제에 따라 파일 경로가 다르며, auditd가 설치·활성화되지 않았다면 감사 로그 파일은 존재하지 않을 수 있다. **컨테이너 내부의 별도 파일에만 기록한 로그는 이 구성의 수집 대상이 아니다.**

## 3. Logstash 처리 흐름

Logstash는 **Input(읽기) → Filter(분석) → Output(전송)** 순서로 로그를 처리한다. 세 단계를 분리해 두면 로그를 어디서 가져오는지, 어떤 필드가 만들어지는지, 어디로 보내는지 쉽게 확인할 수 있다.

```text
Worker Node 로그 파일
        │
        ▼
  ① Input: 파일 읽기, 로그 종류 표시
        │
        ▼
  ② Filter: 로그 본문·경로 분석, 필드 추출
        │
        ▼
  ③ Output: stdout 또는 NHN Cloud로 전송
```

### 3.1 Input — 어떤 로그를 읽는가?

Input은 각 Worker Node의 `/var/log`에서 로그 파일을 읽는다. 호스트 경로는 Pod 내부에서 `/host/var/log`로 보이므로, **설정 파일의 경로도 `/host/var/log`로 시작**한다.

| 설정 파일 | 수집 경로(Pod 내부) | 구분 값 `[@metadata][log_kind]` |
|---|---|---|
| `container-input.yaml` | `/host/var/log/pods/*/*/*.log` | `container` |
| `system-input.yaml` | `/host/var/log/auth.log`, `/host/var/log/secure`, `/host/var/log/syslog`, `/host/var/log/messages` | `system` |
| `auditd-input.yaml` | `/host/var/log/audit/audit.log` | `auditd` |

`[@metadata][log_kind]`는 **Filter에서 어떤 규칙을 적용할지 결정하는 내부 값**이며, 일반적으로 최종 전송 이벤트에는 포함되지 않는다.

```ruby
# container-input.yaml에 포함된 Logstash 설정의 핵심
file {
  id => "container-cri"
  path => ["/host/var/log/pods/*/*/*.log"]
  start_position => "beginning"
  sincedb_path => "/usr/share/logstash/data/sincedb/container"
  add_field => { "[@metadata][log_kind]" => "container" }
}
```

- `path`: 읽을 파일의 경로를 지정한다.
- `start_position`: **처음 발견한 파일**을 어디서부터 읽을지 지정한다.
- `sincedb_path`: 파일별로 **마지막으로 읽은 위치**를 저장한다. 재시작해도 이미 읽은 부분을 반복 수집하지 않도록 돕는다.
- `add_field`: 로그의 종류를 표시해 다음 Filter로 전달한다.

컨테이너 Input에는 Logstash 자체의 컨테이너 로그를 제외하려는 `exclude` 규칙도 있다. 실제 제외 여부는 패턴과 파일명 일치 여부를 확인해야 한다.

### 3.2 Filter — 로그에서 어떤 정보를 추출하는가?

Filter는 Input이 지정한 `log_kind`에 따라 서로 다른 규칙을 적용한다.

| 설정 파일 | 처리 대상 | 핵심 작업 | 주요 결과 필드 |
|---|---|---|---|
| `container-filter.yaml` | 컨테이너 | CRI 로그 분리, 파일 경로에서 Pod 정보 추출, HTTP Access Log 분석 | `body`, `stream`, `namespace`, `podName`, `containerName`, `hostname`, `clientIp`, `requestPath`, `statusCode` |
| `system-filter.yaml` | 시스템·인증 | syslog 헤더 분석, SSH 로그인 성공·실패 메시지 분석 | `body`, `processName`, `logType`, `userName`, `sourceIp`, `eventOutcome` |
| `auditd-filter.yaml` | auditd | 감사 이벤트 유형, 사용자·프로세스 정보 분석 | `body`, `auditType`, `auditId`, `userId`, `auditUserId`, `processName`, `command` |
| `common-filter.yaml` | 전체 | `hostname` 보완, `timestamp` 생성, 불필요한 필드 정리 | `hostname`, `timestamp` |

**① 컨테이너 로그 분석**

Kubernetes의 CRI 로그는 보통 다음과 같은 형태로 기록된다.

```text
2026-10-18T15:00:00.123Z stdout F 10.0.0.5 - - [18/Oct/2026:15:00:00 +0000] "GET / HTTP/1.1" 200 612
```

이를 `dissect`로 분리하면 `stream=stdout`, `body=10.0.0.5 ...`가 된다. CRI 시간은 `@timestamp`로 변환한다. `F`와 같은 CRI 플래그는 내부 메타데이터로 처리한다.

로그 파일 경로에서도 Kubernetes 정보를 추출한다.

```text
/host/var/log/pods/default_nginx-7d8c9b6f4-xk2pq_<Pod-UID>/nginx/0.log
                    └─namespace─┘└─────podName──────┘           └containerName┘
```

경로 패턴이 일치하면 `hostname`에도 **실제 Pod 이름**을 넣는다. HTTP Access Log 패턴까지 일치하면 `logType=access`로 바꾸고 `httpMethod`, `requestPath`, `statusCode`, `clientIp` 등을 추가한다. 일반 컨테이너 로그는 `logType=container`로 남는다.

**② 시스템·인증 로그 분석**

`auth.log` 또는 `secure`에서 읽은 이벤트는 `logType=auth`, `syslog` 또는 `messages`에서 읽은 이벤트는 `logType=syslog`로 구분한다. syslog 헤더에서 프로세스 이름을 추출하고, SSH `Accepted`/`Failed` 패턴이 일치할 때 사용자명과 접속 IP를 추출한다.

예를 들어 `CRON`이나 PAM 세션 메시지는 **수집되더라도 SSH 전용 필드인 `sourceIp`, `userName`이 없을 수 있다.** 이는 수집 실패가 아니라 로그 형식의 차이다.

**③ auditd 로그 분석**

`type=SYSCALL`, `uid=`, `auid=`, `comm=`, `exe=`처럼 **실제 로그에 존재하는 값만** 추출한다. auditd가 설치되어 있지 않거나 파일이 없으면 해당 로그는 수집되지 않는다.

**④ 공통 필드 정리**

| 필드 | 최종 처리 방식 |
|---|---|
| `hostname` | 컨테이너는 Pod 이름, 시스템·auditd는 `${NODE_NAME}`(Worker Node 이름) |
| `timestamp` | `@timestamp` 값을 문자열 필드로 추가 |
| `body` | 로그 원문 또는 CRI에서 분리한 본문을 보존 |
| `host`, `sourceHost`, `path` | 출력 이벤트에서 제거 |

컨테이너 경로 분석에 실패하면 `_pod_path_parse_failure` 또는 `_pod_path_missing` 태그가 붙을 수 있다. 이 경우 공통 Filter가 `hostname`을 Worker Node 이름으로 보완한다.

### 3.3 Output — 분석한 로그를 어디로 보내는가?

| Output | 설정 파일 | 동작 | 용도 |
|---|---|---|---|
| **stdout (기본)** | `stdout-output.yaml` | 파싱한 이벤트를 Logstash Pod 로그로 출력 | 배포 및 필드 검증 |
| **NHN Cloud (선택)** | `nhn-output.yaml.example` | HTTP POST로 JSON 이벤트 전송 | NHN Cloud 공공 Log & Crash Search 연동 |

**stdout으로 확인하는 경우**

```bash
kubectl logs -n logging daemonset/logstash-agent -c logstash --tail=100
```

**NHN Cloud로 전송하는 경우**

예제 파일을 실제 YAML로 준비하고, 프로젝트 설정값을 입력한 다음 ConfigMap을 생성해야 한다. 또한 `daemonset.yaml`의 `pipeline` projected volume에서 `logstash-stdout-output`을 **`logstash-nhn-output`으로 교체**해야 한다.

```text
Input → Filter → HTTP Output → NHN Cloud Log & Crash Search
```

NHN Output만 사용하는 경우 `kubectl logs`에 전송 이벤트 전체가 자동으로 출력되지는 않는다. 검증을 위해 stdout을 잠시 병행할 수 있지만, 로그에 민감한 정보가 포함될 수 있으므로 주의한다.

## 4. 저장소 구조

```text
kubernetes/
├── namespace.yaml
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
        ├── stdout-output.yaml
        └── nhn-output.yaml.example
```

- `namespace.yaml`: `logging` 네임스페이스 생성
- `daemonset.yaml`: Logstash 8.17.0 배포, 노드 로그 마운트 및 ConfigMap 연결
- `input/`: 수집할 로그 파일과 `sincedb` 설정
- `filter/`: 로그 종류별 파싱 및 공통 필드 처리
- `output/`: stdout 출력 또는 NHN Cloud 전송 설정

## 5. 디렉터리 접근 권한 설정

Logstash는 **UID 1000의 일반 사용자**로 실행한다. 노드 로그를 읽기 위한 권한과 `sincedb` 상태 파일을 기록하기 위한 쓰기 권한을 구분하여 설정한다.

### 5.1 로그 파일 읽기 권한

Worker Node의 `/var/log`를 Logstash Pod의 `/host/var/log`에 **읽기 전용**으로 마운트한다.

| 항목 | 설정 |
|---|---|
| Worker Node | `/var/log` |
| Logstash Pod | `/host/var/log` |
| 마운트 | `readOnly: true` |
| 보조 그룹 | `supplementalGroups: [0, 4]` |

`root(0)` 및 `adm(4)` 보조 그룹을 통해 해당 그룹에 읽기 권한이 있는 로그 파일에 접근한다. 실제 접근 가능 여부는 파일과 상위 디렉터리 권한에 따라 달라진다.

```bash
kubectl exec -n logging daemonset/logstash-agent -c logstash -- \
  sh -c 'id; ls -l /host/var/log/auth.log; tail -n 3 /host/var/log/auth.log'
```

### 5.2 initContainer로 sincedb 디렉터리 생성

`sincedb`는 Logstash가 로그 파일을 어디까지 읽었는지 기록하는 상태 파일이다. 읽기 위치를 Pod 재시작 후에도 유지하기 위해 Worker Node의 `/var/lib/logstash-agent`를 Pod의 `/usr/share/logstash/data`에 마운트한다.

**Logstash 실행 전에 initContainer가 `sincedb` 디렉터리를 생성하도록 구성한다.**

```yaml
initContainers:
  - name: init-logstash-data
    image: busybox:1.36
    command:
      - sh
      - -c
      - mkdir -p /data/sincedb
    securityContext:
      runAsNonRoot: true
      runAsUser: 1000
      runAsGroup: 1000
    volumeMounts:
      - name: logstash-data
        mountPath: /data
```

동작 흐름은 **데이터 디렉터리 마운트 → initContainer의 `sincedb` 생성 → Logstash 컨테이너 실행 → 읽기 위치 기록** 순서다.

> **주의:** 현재 initContainer는 UID 1000으로 `mkdir -p`만 실행하며, 기존 디렉터리의 소유권을 변경하지 않는다. 따라서 신규 Worker Node에서 `hostPath`가 `root:root`로 생성되어 쓰기 권한이 없다면 초기화가 실패할 수 있다. 이 경우 해당 노드의 데이터 디렉터리 권한을 별도로 준비해야 한다.

### 5.3 권한 검증

```bash
kubectl exec -n logging daemonset/logstash-agent -c logstash -- \
  sh -c 'id; ls -ld /usr/share/logstash/data/sincedb; ls -l /usr/share/logstash/data/sincedb'
```

`Permission denied`가 발생하면 해당 Worker Node의 `/var/lib/logstash-agent` 소유권 및 쓰기 권한을 확인한다.

## 6. 배포

아래 명령어는 **저장소 루트 디렉터리**에서 실행한다. 기본 `stdout` Output 기준이다. 먼저 **5장의 노드별 디렉터리 권한 설정**을 완료한다.

### 7.1 네임스페이스와 ConfigMap 생성

```bash
kubectl apply -f kubernetes/namespace.yaml
kubectl apply -f kubernetes/configmaps/input/
kubectl apply -f kubernetes/configmaps/filter/
kubectl apply -f kubernetes/configmaps/output/stdout-output.yaml
```

### 7.2 DaemonSet 배포

```bash
kubectl apply -f kubernetes/daemonset.yaml
kubectl rollout status daemonset/logstash-agent -n logging
kubectl get pods -n logging -o wide
```

### 7.3 설정 변경 후 롤링 재시작

ConfigMap을 수정했다면 다시 적용하고 DaemonSet을 재시작한다.

```bash
kubectl apply -f kubernetes/configmaps/filter/
kubectl rollout restart daemonset/logstash-agent -n logging
kubectl rollout status daemonset/logstash-agent -n logging
```

## 7. 로그 수집 확인

### 7.1 Logstash 상태 확인

```bash
kubectl get daemonset logstash-agent -n logging
kubectl get pods -n logging -o wide
kubectl logs -n logging daemonset/logstash-agent -c logstash --tail=100
```

마지막 명령어는 선택된 Logstash Pod 하나의 로그를 보여준다. 기본 stdout Output을 사용 중이라면 파싱된 이벤트를 확인할 수 있다. **NHN Cloud HTTP Output만 활성화한 경우 `kubectl logs`에 전송 이벤트 전체가 출력되지는 않는다.**

### 7.2 노드 로그 파일 확인

```bash
kubectl exec -n logging daemonset/logstash-agent -c logstash -- \
  sh -c 'find /host/var/log/pods -type f -name "*.log" | head'

kubectl exec -n logging daemonset/logstash-agent -c logstash -- \
  sh -c 'id; ls -l /host/var/log/auth.log 2>&1'
```

`auth.log`는 파일이 존재하는 것뿐 아니라 Logstash 계정이 실제로 읽을 수 있는지도 확인해야 한다. `auth.log`가 없는 OS에서는 `/var/log/secure` 등을 확인한다.

### 7.3 새 로그 발생 후 확인

수집 여부는 과거 로그보다 **새로 발생한 로그**로 검증하는 것이 정확하다. 예를 들어 Nginx Pod에 요청을 보내 Access Log가 생성되는지 확인하고, stdout 또는 NHN Cloud에서 해당 시간대의 이벤트를 검색한다. 여러 Worker Node가 있다면 **해당 Pod가 실행되는 노드의 Logstash**를 확인한다.

## 8. 점검할 사항

### 컨테이너 로그가 보이지 않는 경우

Input 경로와 실제 `/host/var/log/pods` 파일을 비교하고, 파일 읽기 권한 및 `sincedb`를 확인한다. `sincedb`는 이전 읽기 위치를 기억하므로 기존 로그가 재전송되지 않는 것은 정상일 수 있다.

### `auth.log`가 보이지 않는 경우

먼저 파일 존재 여부와 읽기 권한을 확인한다. Ubuntu에서는 `auth.log`, RHEL 계열에서는 `secure`가 일반적이다. SSH 로그인 로그뿐 아니라 CRON/PAM 메시지도 기록될 수 있으므로, **SSH 관련 필드가 없다는 이유만으로 수집 실패라고 판단하지 않는다.**

### `hostname`에 Pod 이름이 없는 경우

컨테이너 로그의 파일 경로에서 Pod 이름을 추출했는지 확인한다. 경로가 예상 패턴과 일치하지 않으면 `_pod_path_parse_failure` 또는 `_pod_path_missing` 태그가 생성될 수 있다. 이 경우 공통 Filter의 Worker Node 이름이 `hostname`에 들어갈 수 있다.

### NHN Cloud에서 로그가 검색되지 않는 경우

Logstash의 Input/Filter 처리와 HTTP 전송을 구분해 확인한다. `stdout`을 임시로 활성화하면 **NHN 전송 이전의 이벤트 필드**를 확인할 수 있다. 다만 인증·감사 로그에 민감한 정보가 포함될 수 있으므로 검증 후 제거한다.

---

이 프로젝트는 **노드별 로그 수집 → 로그 종류별 파싱 → 출력·전송**이라는 기본 흐름을 확인하기 위한 구성이다. 운영 환경에서는 로그 보존 기간, 전송 실패 시 재처리, 리소스 사용량, 접근 권한, 민감정보 처리 등을 추가로 검토해야 한다.
