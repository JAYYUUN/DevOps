# OpenTelemetry Operator Wrapper Chart

Kubernetes 애플리케이션에 **OpenTelemetry 자동 계측 Agent를 주입**하기 위한 재사용 가능한 Helm 모듈입니다. 공식 `opentelemetry-operator` Chart **0.126.0**을 의존성으로 사용합니다. Operator는 계측을 관리하는 컨트롤러이며, **Tempo로 Trace를 직접 전송하거나 Collector를 자동 배포하는 역할은 아닙니다.**

## 구성 및 설정

```text
charts/opentelemetry-operator/
├── Chart.yaml        # opentelemetry-operator 0.126.0 의존성
├── values.yaml       # Operator 리소스 및 Admission Webhook 설정
└── README.md
```

`values.yaml`은 Operator Replica `1`, CPU 요청 `50m`/제한 `500m`, 메모리 요청 `128Mi`/제한 `512Mi`로 구성되어 있습니다. `admissionWebhooks.create: true`이며 `certManager.enabled: false`, `autoGenerateCert.enabled: true`로 Webhook용 자체 서명 TLS 인증서 생성을 선택했습니다. `manager.collectorImage`는 Operator가 Collector를 관리할 때 사용하는 기본 이미지 설정이며 Collector Deployment를 생성하지 않습니다.

**Tempo 전송 주소·샘플링·언어별 Agent 설정은 Operator가 아닌 `charts/instrumentation/`에서 관리합니다.**

## 배포 전 준비

Helm 및 Kubernetes 버전이 Chart 0.126.0의 요구사항과 호환되는지 확인하세요. API Server에서 Admission Webhook Service로 통신할 수 있어야 하며, Webhook 인증서와 CA 신뢰 설정이 올바르게 적용되어야 합니다. 기존 cert-manager를 활용하려면 인증서 관련 values를 해당 Chart 스키마에 맞게 변경합니다.

## 배포 방법

프로젝트 최상위 디렉터리에서 실행합니다. **Instrumentation보다 먼저 설치**해야 합니다.

```bash
helm dependency build ./charts/opentelemetry-operator
helm lint ./charts/opentelemetry-operator
helm template otel-operator ./charts/opentelemetry-operator \
  -n observability > /tmp/otel-operator-rendered.yaml
helm upgrade --install otel-operator ./charts/opentelemetry-operator \
  -n observability --create-namespace --wait --timeout 10m
```

## 배포 확인

```bash
helm list -n observability
kubectl get pods -n observability
kubectl get crd instrumentations.opentelemetry.io
kubectl get mutatingwebhookconfigurations
kubectl get svc -n observability
```

Webhook Pod가 정상 실행되고 `instrumentations.opentelemetry.io` CRD가 생성되어야 합니다. Operator 설치만으로 모든 Pod에 자동 계측이 적용되지는 않습니다. **애플리케이션 네임스페이스의 Instrumentation 리소스와 Pod 템플릿 주입 어노테이션**이 추가로 필요합니다.

## 운영 시 확인사항

Webhook 장애나 TLS 인증서 만료는 주입 대상 Pod 생성에 영향을 줄 수 있습니다. Operator 및 Webhook 로그, 인증서 갱신 방식, CRD 버전을 관리하세요. Helm 업그레이드 시 CRD가 자동 갱신되지 않을 수 있으므로 릴리스 변경사항을 확인해야 합니다. 별도의 OpenTelemetry Collector는 이 모듈에서 설치하지 않습니다.
