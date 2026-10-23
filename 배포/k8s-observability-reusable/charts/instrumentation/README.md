# OpenTelemetry Instrumentation Helm Chart

OpenTelemetry Operator가 애플리케이션 Pod에 주입할 **언어별 자동 계측 설정과 Tempo 전송 정책**을 관리하는 재사용 가능한 Helm 모듈입니다. 공식 Chart를 의존성으로 사용하는 Wrapper가 아니라, Kubernetes `Instrumentation` 사용자 정의 리소스(CR)를 직접 생성하는 Chart입니다.

## 구성 및 설정

```text
charts/instrumentation/
├── Chart.yaml                       # 독립 Helm Chart
├── values.yaml                      # 공통 Tempo 주소, OTLP, 전파·샘플링 설정
├── values/
│   ├── java.yaml                    # Java Instrumentation 이름·언어
│   ├── python.yaml                  # Python Instrumentation 이름·언어
│   ├── nodejs.yaml                  # Node.js Instrumentation 이름·언어
│   └── dotnet.yaml                  # .NET Instrumentation 이름·언어
├── templates/
│   └── instrumentation.yaml         # Instrumentation CR 생성 템플릿
└── README.md
```

`values.yaml`의 기본 Tempo 주소는 `http://tempo.observability.svc.cluster.local:4318`, OTLP 프로토콜은 `http/protobuf`입니다. 전파 방식은 `tracecontext`, `baggage`이고, 샘플러는 `parentbased_traceidratio` / `0.1`(기본 10% 샘플링)입니다. 언어별 파일은 Instrumentation 이름과 언어를 지정하며, 필요한 경우 Agent `image`와 추가 `env`를 설정할 수 있습니다.

`values.yaml`은 자동 적용되지만 `values/*.yaml`은 **자동 병합되지 않으므로 `-f`로 선택**해야 합니다. 기본 언어는 Java이며, 실제 언어에 맞는 파일을 반드시 선택하세요.

## 배포 전 준비

Tempo의 OTLP HTTP 수신 Service와 OpenTelemetry Operator가 먼저 배포되어 있어야 합니다. `instrumentations.opentelemetry.io` CRD가 존재하는지 확인하고, Instrumentation을 **실제 애플리케이션과 같은 네임스페이스**에 설치합니다. 언어별 자동 계측은 런타임·프레임워크·Agent 이미지와의 호환성을 검증해야 합니다.

## 배포 방법

프로젝트 최상위 디렉터리에서 실행합니다. 아래는 `payment` 네임스페이스의 Java 예시입니다.

```bash
kubectl get crd instrumentations.opentelemetry.io
helm lint ./charts/instrumentation \
  -f ./charts/instrumentation/values/java.yaml
helm template otel-java ./charts/instrumentation -n payment \
  -f ./charts/instrumentation/values/java.yaml
helm upgrade --install otel-java ./charts/instrumentation \
  -n payment --create-namespace \
  -f ./charts/instrumentation/values/java.yaml
```

애플리케이션 Deployment의 `spec.template.metadata.annotations`에 다음을 추가합니다.

```yaml
instrumentation.opentelemetry.io/inject-java: "java-instrumentation"
```

Python은 `inject-python: "python-instrumentation"`, Node.js는 `inject-nodejs: "nodejs-instrumentation"`, .NET은 `inject-dotnet: "dotnet-instrumentation"`을 사용합니다. 어노테이션은 각 언어의 전체 키(`instrumentation.opentelemetry.io/...`)로 지정해야 합니다. 주입은 **새 Pod 생성 시점**에 이뤄지므로 기존 Pod는 재생성이 필요합니다.

```bash
kubectl rollout restart deployment/<deployment-name> -n payment
```

## 배포 확인

```bash
helm list -n payment
kubectl get instrumentation -n payment
kubectl describe instrumentation java-instrumentation -n payment
kubectl get pods -n payment
```

Pod 생성 후 Agent 주입 여부, 애플리케이션 로그, Tempo에서 Trace 수신 여부를 확인하세요. `OTEL_SERVICE_NAME`은 애플리케이션 Deployment별로 지정하는 것을 권장합니다. 같은 네임스페이스에 여러 언어를 설치할 경우 **Helm Release 이름과 Instrumentation 리소스 이름이 중복되지 않아야** 합니다.

## 자동 계측과 수동 계측

자동 계측은 지원되는 HTTP·DB·Redis 등의 호출에서 Span을 생성합니다. 수동 계측은 개발자가 애플리케이션 코드에 비즈니스 Span을 추가하는 방식이며, **Instrumentation CR에 수동 계측 코드를 작성하는 것은 아닙니다.** 자동 주입된 SDK/TracerProvider와 현재 Trace Context를 공유하면 자동·수동 Span을 하나의 Trace로 연결할 수 있습니다. 별도 SDK 초기화를 중복 수행하지 않도록 주의하세요. 이 모듈은 별도 Collector 없이 Agent에서 Tempo로 직접 전송하는 구성을 전제로 합니다.
