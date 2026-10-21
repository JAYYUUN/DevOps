# Loki — 로그 저장 및 조회

공식 Loki Helm Chart **19.0.2**를 사용합니다. **SingleBinary** 방식으로 배포하고, 로그는 S3 호환 Object Storage에 저장합니다.

## 데이터 흐름

```text
로그 전송 클라이언트 → Loki Gateway → Loki SingleBinary ─┬─ S3: 로그 청크·인덱스
                                                      └─ PVC: WAL·캐시
Grafana Explore → Loki Gateway → Loki 조회
```

로그 수집기(Fluentd/Fluent Bit/Alloy)는 이 프로젝트에 포함하지 않았습니다.

## `values.yaml.gotmpl` 설정

| 설정 | 값 / 의미 |
|---|---|
| `deploymentMode` | `SingleBinary`: 단일 Loki 구성 |
| `loki.auth_enabled` | `false`: 내부 단일 테넌트 기준 인증 비활성화 |
| `replication_factor` | `1`: Loki 복제본 1개 |
| `schemaConfig` | `tsdb`, `v13`: 로그 인덱스 저장 형식 |
| `loki.storage.type` | `s3`: S3 호환 객체 저장소 사용 |
| `bucketNames` | `S3_BUCKET`: 로그 저장 버킷 |
| `s3.endpoint` | `S3_ENDPOINT`: S3 API 주소 |
| `s3.region` | `S3_REGION`: S3 리전 |
| `s3ForcePathStyle` | `true`: Path-style 버킷 접근 |
| `extraEnvFrom` | `loki-s3-credentials` Secret의 인증키 주입 |
| `singleBinary.persistence` | 10Gi PVC: WAL·캐시용 로컬 저장소 |
| `storageClass` | `LOKI_STORAGE_CLASS`: 클러스터의 StorageClass |
| `initContainers` | `/var/loki` 작업 폴더 생성·권한 설정 |
| `read/write/backend.replicas` | `0`: 분산 모드 컴포넌트 미사용 |

`{{ requiredEnv "..." }}` 항목은 `environments/.env`에서 불러옵니다. **S3와 PVC는 용도가 달라 둘 다 사용합니다.**

## 환경별 수정

- S3 엔드포인트·리전·버킷·StorageClass: `environments/.env`
- S3 접근키: `loki-s3-credentials` Kubernetes Secret
- PVC 크기: `singleBinary.persistence.size` (기본 `10Gi`)
- Loki 인스턴스 수: 현재 `singleBinary.replicas: 1`

환경값 작성과 Secret 생성 명령은 `environments/README.md`를 참고합니다. 적용은 프로젝트 루트에서 `helmfile sync`입니다.
