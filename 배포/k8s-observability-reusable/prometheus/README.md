# Prometheus Stack 재사용 모듈

`prometheus-community/kube-prometheus-stack` Helm 차트를 독립 설치·업데이트하는 모듈입니다. Prometheus, Grafana, Alertmanager를 함께 관리하며, Grafana에 Loki 데이터 소스를 등록합니다.

> 아래 명령어는 저장소 최상위 디렉터리(`k8s-observability-modules/`)에서 실행합니다. 기본 Namespace는 `observability`, Helm 릴리스 이름은 `monitoring`입니다.

## 1. 파일 구성

Prometheus Stack은 메트릭 수집, 대시보드, 알림 기능을 한 차트로 배포합니다. 파일을 기능별로 나누면 Grafana 데이터 소스만 변경하거나 Alertmanager 설정만 추가할 때 관련 파일을 쉽게 찾을 수 있습니다.

| 파일 | 역할 |
|---|---|
| `values/00-common.yaml` | 공통 설정을 추가할 위치(현재 주석만 있음) |
| `values/01-prometheus.yaml` | Prometheus 활성화 |
| `values/02-grafana.yaml` | Grafana 활성화, Loki 데이터 소스 URL |
| `values/03-alertmanager.yaml` | Alertmanager 활성화 |

## 2. 설치 준비

먼저 현재 `kubectl`이 연결한 클러스터와 노드 상태를 확인합니다. 이후 Prometheus Community Helm 저장소를 등록하고 모듈을 배포할 `observability` Namespace를 준비합니다. 이 단계는 클러스터를 잘못 선택해 배포하는 실수를 줄이기 위한 절차입니다.

```bash
kubectl config current-context
kubectl get nodes
helm version
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update prometheus-community
kubectl create namespace observability --dry-run=client -o yaml | kubectl apply -f -
```

Loki 데이터 소스는 `http://loki-gateway.observability.svc.cluster.local`을 바라봅니다. Loki를 설치하지 않아도 Prometheus Stack 자체는 설치할 수 있으나, Loki 로그 조회에는 Loki 모듈이 필요합니다.

## 3. 설치 및 업데이트

Helm 릴리스 `monitoring`은 Prometheus Stack 배포를 식별하는 이름입니다. `upgrade --install`은 첫 실행 시 설치, 재실행 시 업데이트를 수행하며 네 개의 values를 순서대로 병합합니다. 변경한 values만 적용되는 것이 아니라 네 파일의 최종 병합 결과가 릴리스에 반영됩니다.

권장 명령어:

```bash
bash scripts/install-module.sh prometheus
```

Helm 직접 실행:

```bash
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n observability --wait --timeout 10m \
  -f prometheus/values/00-common.yaml \
  -f prometheus/values/01-prometheus.yaml \
  -f prometheus/values/02-grafana.yaml \
  -f prometheus/values/03-alertmanager.yaml
```

설정 변경 후 같은 명령어를 다시 실행하면 해당 릴리스만 업데이트됩니다.

## 4. 배포 상태와 Grafana 접속

`helm status`는 Helm 릴리스 상태를, `kubectl get pods`는 실제 실행 중인 구성요소를 확인합니다. Grafana Service는 클러스터 내부에서 접근하므로 관리 서버에서 포트포워딩을 열고, 필요하면 SSH 터널을 이용해 작업 PC 브라우저에서 접속합니다.

```bash
helm status monitoring -n observability
kubectl get pods -n observability
kubectl get svc -n observability | grep grafana
kubectl port-forward -n observability svc/monitoring-grafana 3000:80
```

Bastion에서 포트포워딩 중이라면 작업 PC에서 별도 SSH 터널을 연결할 수 있습니다.

```bash
ssh -p <SSH_PORT> -L 3000:127.0.0.1:3000 ubuntu@<BASTION_IP>
```

작업 PC 브라우저에서 `http://localhost:3000`으로 접속합니다. 초기 Grafana 관리자 비밀번호는 아래 명령으로 확인할 수 있습니다.

```bash
kubectl get secret -n observability monitoring-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

## 5. 수집 대상 및 알림 규칙 추가

Prometheus는 메트릭을 제공하는 HTTP 엔드포인트를 주기적으로 읽어 데이터를 수집합니다. `ServiceMonitor`와 `PodMonitor`는 어떤 서비스·Pod를 수집할지 정의하고, `PrometheusRule`은 수집된 메트릭을 바탕으로 알림 조건을 정의합니다. 이 리소스는 Helm values와 별개이므로 매니페스트를 작성해 `kubectl apply`로 등록합니다.

- **ServiceMonitor / PodMonitor**: Kubernetes 서비스 또는 Pod의 메트릭 수집 대상 정의
- **PrometheusRule**: 알림 및 기록 규칙 정의
- **ScrapeConfig / Probe**: 지원되는 Operator 버전에서 추가 수집 대상 정의

필요하면 `prometheus/manifests/`를 만들고 해당 리소스를 저장한 뒤 적용합니다.

```bash
mkdir -p prometheus/manifests
kubectl apply -n observability -f prometheus/manifests/
```

`manifests/`는 현재 기본 패키지에 포함된 리소스가 아닙니다. ServiceMonitor 등의 Namespace·label 선택 조건은 설치된 Prometheus Operator의 선택자 설정에 맞춰야 합니다. 차트에서 제공하는 Helm 설정을 추가하려면 `values/04-*.yaml`을 만들면 설치 스크립트가 파일명 순서대로 병합합니다.

## 6. 자주 수정하는 파일

대시보드·데이터 소스 변경은 Grafana values, 수집기 설정은 Prometheus values, 알림 기능은 Alertmanager values에서 관리합니다. 수집 대상처럼 Kubernetes CRD가 필요한 설정은 별도 매니페스트로 분리합니다. 이렇게 나누면 설정의 목적과 적용 방식이 명확해집니다.

| 변경 사항 | 수정 파일 |
|---|---|
| Grafana 데이터 소스 | `values/02-grafana.yaml` |
| Prometheus 설정 | `values/01-prometheus.yaml` 또는 신규 values |
| Alertmanager 설정 | `values/03-alertmanager.yaml` |
| 서비스별 수집/알림 규칙 | `manifests/`에 Kubernetes YAML 추가 |

차트 버전을 고정하려면 저장소 루트의 `config/versions.env`에 `PROMETHEUS_CHART_VERSION`을 설정합니다.
