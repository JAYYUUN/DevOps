# Instrumentation Helm Chart

Operator 설치 및 `instrumentations.opentelemetry.io` CRD 생성 **이후** 애플리케이션 네임스페이스에 설치. `values.yaml`은 공통 Tempo OTLP HTTP(4318), 샘플링 10%, propagator 설정. `values/<language>.yaml`은 이름과 언어만 선택하며 필요한 경우 `image`, `env`를 추가한다.

```bash
helm lint ./charts/instrumentation -f ./charts/instrumentation/values/java.yaml
helm template otel-java ./charts/instrumentation -n payment -f ./charts/instrumentation/values/java.yaml
helm upgrade --install otel-java ./charts/instrumentation -n payment --create-namespace -f ./charts/instrumentation/values/java.yaml
kubectl get instrumentation -n payment
```

애플리케이션 **Deployment의 `spec.template.metadata.annotations`** 에 다음을 추가:

```yaml
instrumentation.opentelemetry.io/inject-java: "java-instrumentation"
```

Python은 `inject-python: "python-instrumentation"`, Node.js는 `inject-nodejs: "nodejs-instrumentation"`, .NET은 `inject-dotnet: "dotnet-instrumentation"` 사용. 새 Pod 생성 시에만 주입되므로 `kubectl rollout restart deployment/<name> -n payment` 필요.

**주의:** 같은 네임스페이스에서 언어별 Helm release 이름과 Instrumentation 리소스 이름을 각각 다르게 유지. 실제 애플리케이션에는 OpenTelemetry API 패키지가 필요할 수 있으며 Python/Node.js/.NET 자동 계측은 런타임·이미지·권한·프레임워크 호환성 검증이 필요. 수동 Span은 애플리케이션 코드에서 추가하고, 자동 주입된 SDK/TracerProvider를 공유하도록 구현. 별도 SDK 초기화를 중복 실행하지 말 것.

`OTEL_SERVICE_NAME`은 각 애플리케이션 Deployment에서 개별 설정 권장. 네임스페이스별로 이 Chart를 설치해야 하며 Operator 설치만으로 모든 Pod가 자동 계측되지는 않음.
