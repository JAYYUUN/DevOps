# Prometheus Wrapper Chart

Kubernetes 클러스터의 메트릭 수집, 시각화 및 알림을 위한 재사용 가능한 Helm 모듈입니다. 공식 `kube-prometheus-stack` Chart를 의존성으로 사용하며 Prometheus, Grafana, Alertmanager를 함께 구성합니다.

Grafana에는 **Loki(로그)**와 **Tempo(분산 추적)** 데이터소스를 자동 등록하여 메트릭, 로그, Trace를 통합 조회할 수 있도록 구성합니다.

## 구성 및 설정

```text
charts/prometheus/
├── Chart.yaml                 # kube-prometheus-stack 92.7.0 의존성
├── values.yaml                # 배포 시 자동 적용되는 기본 설정
└── values/
    ├── 00-common.yaml        # 공통 설정
    ├── 01-prometheus.yaml    # Prometheus 활성화
    ├── 02-grafana.yaml       # Grafana 및 Loki·Tempo 데이터소스
    └── 03-alertmanager.yaml  # Alertmanager 활성화
```

현재 기본 설정에서는 Prometheus, Grafana, Alertmanager를 활성화합니다.

Grafana 데이터소스는 다음과 같이 구성합니다.

| 데이터소스 | 역할 | 연결 주소 |
|---|---|---|
| Prometheus | Kubernetes 메트릭 조회 | kube-prometheus-stack 기본 설정 |
| Loki | Kubernetes 로그 조회 | `http://loki-gateway.observability.svc.cluster.local` |
| Tempo | 분산 추적(Trace) 조회 | `http://tempo.observability.svc.cluster.local:3200` |

Loki와 Tempo는 각각의 Helm Chart로 배포하며, Grafana는 Kubernetes Service 주소를 통해 연결합니다. 서비스 이름이나 Namespace가 다르면 데이터소스 URL을 변경해야 합니다.

`Chart.yaml`은 공식 Chart 의존성을 선언합니다. `values.yaml`은 Helm이 자동으로 읽고, `values/*.yaml`은 기능별 참고 및 선택적 오버라이드 파일입니다.

**`values/` 파일만 수정하면 기본 배포에 반영되지 않으므로**, 공통 설정을 변경할 때는 루트 `values.yaml`도 수정하거나 변경한 파일을 `-f`로 전달하세요.

### Grafana 데이터소스 설정

`values.yaml`과 `values/02-grafana.yaml`에서 다음 설정을 관리합니다.

```yaml
kube-prometheus-stack:
  grafana:
    enabled: true
    additionalDataSources:
      - name: Loki
        type: loki
        access: proxy
        url: http://loki-gateway.observability.svc.cluster.local
        isDefault: false

      - name: Tempo
        uid: tempo
        type: tempo
        access: proxy
        url: http://tempo.observability.svc.cluster.local:3200
        isDefault: false
```

- `additionalDataSources`: Grafana에 데이터소스를 자동 등록하는 설정
- `type`: 데이터소스 종류 (`loki`, `tempo`)
- `access: proxy`: Grafana 서버가 해당 서비스에 직접 접근
- `url`: Kubernetes 내부 서비스 주소
- `isDefault: false`: 기본 데이터소스로 지정하지 않음

## 배포 방법

프로젝트 최상위 디렉터리(`k8s-observability-reusable/`)에서 실행합니다. Helm CLI와 Kubernetes 클러스터 접근 권한이 필요합니다.

```bash
helm dependency build ./charts/prometheus
helm lint ./charts/prometheus
helm template monitoring ./charts/prometheus -n observability > /tmp/prometheus-rendered.yaml
helm upgrade --install monitoring ./charts/prometheus -n observability --create-namespace --wait --timeout 10m
```

추가 설정 파일을 적용하려면 다음처럼 **파일을 명시적으로 지정**합니다.

```bash
helm upgrade --install monitoring ./charts/prometheus -n observability \
  -f ./charts/prometheus/values/02-grafana.yaml
```

## 배포 확인

```bash
helm list -n observability
kubectl get pods -n observability
kubectl get svc -n observability
helm get values monitoring -n observability
```

Grafana에서 **Connections → Data sources**로 이동하여 Prometheus, Loki, Tempo 데이터소스가 등록되어 있는지 확인합니다.

기존 Helm CLI가 관리하는 동일 리소스를 Argo CD가 동시에 관리하지 않도록 주의하세요.
