# Fluentd 재사용 모듈

`fluent/fluentd` Helm 차트로 Kubernetes 노드마다 Fluentd DaemonSet을 배포하고, CRI 컨테이너 로그를 수집해 Loki Gateway로 전송하는 모듈입니다. **Helm 배포 설정(`values/`)과 로그 처리 파이프라인(`config/`)을 분리**했습니다.

> 명령어는 저장소 최상위 디렉터리에서 실행합니다. 기본 Namespace는 `observability`, Helm 릴리스는 `fluentd`입니다.

## 1. 파일 구성

Fluentd는 입력(source) → 필터(filter) → 출력(match) 순서로 로그를 처리합니다. Kubernetes 배포 방식과 리소스는 `values/`에, 실제 로그 수집·가공·전송 규칙은 `config/`에 분리했습니다. 따라서 배포 자원 변경과 로그 처리 로직 변경을 서로 구분할 수 있습니다.

### Helm values

| 파일 | 내용 |
|---|---|
| `values/00-common.yaml` | DaemonSet, `/var/log` 마운트, ServiceAccount, RBAC |
| `values/01-resources.yaml` | CPU 요청 100m/제한 500m, 메모리 요청 256Mi/제한 512Mi |
| `values/02-plugins.yaml` | Loki, Prometheus, Kubernetes metadata 플러그인 |
| `values/03-healthcheck.yaml` | `/metrics`에 대한 liveness/readiness probe |

### Fluentd 파이프라인

| 파일 | 내용 |
|---|---|
| `config/01_sources.conf` | `/var/log/containers/*.log` tail, CRI 파싱, Prometheus 메트릭 소스 |
| `config/02_filters.conf` | Kubernetes 메타데이터 보강 |
| `config/03_dispatch.conf` | namespace, pod, container 필드 추출 |
| `config/04_outputs.conf` | Loki Gateway 전송, JSON 라인 형식, 메모리 버퍼 |

## 2. 설치 준비

Fluentd DaemonSet은 각 워커 노드의 컨테이너 로그 파일을 읽기 때문에 `/var/log` 마운트와 Kubernetes 메타데이터 조회 권한이 필요합니다. Helm 저장소와 Namespace를 준비하고, 로그 전송 대상인 Loki Gateway의 주소를 확인합니다. 파이프라인 변환에는 Python 3도 사용합니다.

```bash
kubectl config current-context
kubectl get nodes
helm version
python3 --version
helm repo add fluent https://fluent.github.io/helm-charts
helm repo update fluent
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
```

현재 Loki 출력 대상은 `http://loki-gateway.observability.svc.cluster.local`입니다. 다른 Namespace나 서비스 이름을 쓰면 `config/04_outputs.conf`의 URL을 변경해야 합니다.

## 3. 설치 및 업데이트

Helm 차트의 `fileConfigs`는 Fluentd 설정 파일의 이름과 내용을 YAML 값으로 받습니다. `build-fluentd-values.py`가 분리된 `.conf` 파일을 이 형식으로 묶고, Helm 설치 명령이 배포 설정과 함께 적용합니다. 이 과정은 설정 파일을 결합하는 작업이지 로그를 직접 수집하는 작업은 아닙니다.

```bash
bash scripts/install-module.sh fluentd
```

설치 스크립트는 `config/*.conf`를 읽어 `.generated/fluentd-pipeline.yaml`을 만든 뒤 Helm values의 **마지막 `-f`**로 전달합니다. 생성 파일은 Git에서 제외합니다.

Helm 직접 실행:

```bash
python3 scripts/build-fluentd-values.py .generated/fluentd-pipeline.yaml
helm upgrade --install fluentd fluent/fluentd \
  -n observability --wait --timeout 10m \
  -f fluentd/values/00-common.yaml \
  -f fluentd/values/01-resources.yaml \
  -f fluentd/values/02-plugins.yaml \
  -f fluentd/values/03-healthcheck.yaml \
  -f .generated/fluentd-pipeline.yaml
```

## 4. 로그 수집 흐름

`source`는 CRI 형식의 컨테이너 로그를 읽고, `filter`는 Kubernetes 메타데이터와 검색에 필요한 필드를 추가합니다. 마지막 `match`는 처리된 로그를 Loki Gateway로 전송합니다. 이처럼 처리 단계별 파일을 분리하면 로그 파싱이나 라벨 구성을 독립적으로 수정할 수 있습니다.

```text
/var/log/containers/*.log
  -> 01_sources.conf (CRI 파싱, read_from_head false)
  -> 02_filters.conf (Kubernetes metadata)
  -> 03_dispatch.conf (namespace/pod/container 필드)
  -> 04_outputs.conf (Loki Gateway, 메모리 버퍼)
  -> Loki
```

`01_sources.conf`의 Prometheus 소스가 포트 `24231`에서 `/metrics`를 제공하므로, `03-healthcheck.yaml`의 프로브와 함께 유지합니다. `read_from_head false`는 기존 로그를 처음부터 소급 수집하지 않는 설정입니다.

## 5. 상태 및 로그 확인

DaemonSet은 대상 노드마다 Fluentd Pod를 유지하는 Kubernetes 컨트롤러입니다. `rollout status`로 배포 진행 상태를 확인하고 `kubectl logs`로 Fluentd 자체 오류나 Loki 전송 메시지를 살펴봅니다. 최종 로그 조회는 Loki 또는 Grafana Explore에서 수행합니다.

```bash
helm status fluentd -n observability
kubectl get daemonset fluentd -n observability
kubectl rollout status daemonset/fluentd -n observability --timeout=180s
kubectl get pods -n observability -o wide
kubectl logs -n observability daemonset/fluentd --tail=100
```

Loki를 연결했다면 Grafana Explore에서 다음 LogQL로 확인할 수 있습니다.

```logql
{namespace="observability"}
```

## 6. 수정 위치

수집 경로와 CRI 파싱은 source, Kubernetes 메타데이터는 filter, 로그 필드 구성은 dispatch, Loki 전송은 output에서 관리합니다. CPU·메모리 및 헬스 체크는 Helm values를 수정합니다. 수정 후 Fluentd 모듈만 재설치 명령으로 업데이트하면 됩니다.

| 변경 목적 | 수정 파일 |
|---|---|
| 수집 로그 경로 / CRI 파싱 | `config/01_sources.conf` |
| Kubernetes 메타데이터 | `config/02_filters.conf` |
| 필드 추가·변환 | `config/03_dispatch.conf` |
| Loki URL / 라벨 / 버퍼 | `config/04_outputs.conf` |
| CPU·메모리 | `values/01-resources.yaml` |
| 플러그인 | `values/02-plugins.yaml` |
| 헬스 체크 | `values/03-healthcheck.yaml` |

설정을 변경한 후 `bash scripts/install-module.sh fluentd`를 다시 실행합니다. 메모리 버퍼는 Pod 재시작 시 미전송 로그가 유실될 수 있습니다. `job` 라벨은 출력 설정에 선언되어 있지만, 실제 Loki 라벨 조회 시 존재 여부는 수집된 로그의 라벨을 기준으로 확인합니다.
