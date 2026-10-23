# fluentd Wrapper Chart

- 공식 의존 Chart: `fluentd` 버전 `0.5.3` (배포 전 기존 설치 버전과 호환성 확인)
- `Chart.yaml`: 의존성 선언
- `values.yaml`: **기본적으로 자동 적용되는 통합 설정**. 기존 원본 설정을 보존함
- `values/*.yaml`: 기능별로 분리한 **선택적 오버라이드**. Helm은 이 폴더를 자동 병합하지 않음
- `config/*.conf`: 기존 Fluentd 설정 원본. Wrapper `templates/configmap.yaml`이 자동으로 ConfigMap에 포함
- `fluentd.extraFilesConfigMapNameOverride`: 공식 Chart가 생성한 DaemonSet이 `fluentd-wrapper-files`를 `/etc/fluent/config.d`에 마운트하도록 연결. 공식 Chart의 기본 `fluent.conf`는 `@include config.d/*.conf`를 사용함
- `.conf` 변경 후 Helm CLI 업그레이드 또는 Argo CD Sync 필요. ConfigMap 변경만으로 Fluentd 프로세스가 즉시 재시작된다고 가정하지 마세요

```bash
helm dependency build ./charts/fluentd
helm template fluentd ./charts/fluentd -n observability > /tmp/fluentd-rendered.yaml
helm upgrade --install fluentd ./charts/fluentd -n observability --create-namespace
```

환경별 오버라이드가 필요한 경우 `-f ./charts/fluentd/values/01-*.yaml`처럼 **정확한 파일명을** 추가하세요. `values.yaml`에 이미 동일한 기본 설정이 포함되어 있으므로 모든 파일을 다시 넘길 필요는 없습니다.
