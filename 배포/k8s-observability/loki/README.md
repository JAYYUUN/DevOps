# loki — 로그 저장/조회

`values.yaml.gotmpl`은 공식 `grafana-community/loki` **19.0.2** 차트의 오버라이드입니다. Helmfile이 `environments/.env`에서 불러온 환경변수를 렌더링합니다.

## 주요 설정

- `deploymentMode: SingleBinary`: Loki 단일 프로세스, 1개 replica (HA 아님)
- `loki.schemaConfig`: TSDB v13, 24시간 인덱스 주기
- `loki.storage`: S3 호환 객체 스토리지, 버킷/엔드포인트/리전은 외부 입력
- `singleBinary.extraEnvFrom`: Kubernetes Secret `loki-s3-credentials`에서 AWS 자격증명 주입
- `singleBinary.persistence`: 10Gi PVC로 WAL/캐시 영속화, StorageClass는 외부 입력
- `singleBinary.initContainers`: `/var/loki` 디렉터리 생성 및 소유권 조정 (root 실행)
- `read/write/backend.replicas: 0`: 분산 모드 컴포넌트 비활성화

## 준비와 검증

`../environments/README.md`대로 값을 채우고 루트 README의 Secret 생성 및 `helmfile sync` 명령을 실행합니다.

```bash
kubectl get pods,pvc -n observability
kubectl logs -n observability loki-0 -c loki --tail=100
kubectl get svc -n observability | grep loki
```

S3 설정만으로 객체 기록까지 검증되지는 않습니다. 테스트 로그를 넣고 충분한 시간이 지난 후 버킷의 실제 객체 생성 여부를 별도로 확인하세요. StorageClass가 정적 PV 전용이라면 PVC 자동 생성이 안 될 수 있습니다. `initContainer` 볼륨 이름 `storage`는 차트 버전과 실제 렌더링 결과를 확인해야 합니다.
