# loki Wrapper Chart

- 공식 의존 Chart: `loki` 버전 `6.55.0` (배포 전 기존 설치 버전과 호환성 확인)
- `Chart.yaml`: 의존성 선언
- `values.yaml`: **기본적으로 자동 적용되는 통합 설정**. 기존 원본 설정을 보존함
- `values/*.yaml`: 기능별로 분리한 **선택적 오버라이드**. Helm은 이 폴더를 자동 병합하지 않음

```bash
helm dependency build ./charts/loki
helm template loki ./charts/loki -n observability > /tmp/loki-rendered.yaml
helm upgrade --install loki ./charts/loki -n observability --create-namespace
```

환경별 오버라이드가 필요한 경우 `-f ./charts/loki/values/01-*.yaml`처럼 **정확한 파일명을** 추가하세요. `values.yaml`에 이미 동일한 기본 설정이 포함되어 있으므로 모든 파일을 다시 넘길 필요는 없습니다.
